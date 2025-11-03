# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""
Types and models for the find_code agent API.
"""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Annotated, Any, NamedTuple

from pydantic import ConfigDict, Field, NonNegativeFloat, NonNegativeInt, model_validator

from codeweaver.agent_api.find_code.intent import IntentType
from codeweaver.core.chunks import CodeChunk
from codeweaver.core.discovery import DiscoveredFile
from codeweaver.core.language import SemanticSearchLanguage
from codeweaver.core.spans import Span
from codeweaver.core.types import LanguageName
from codeweaver.core.types.enum import BaseEnum
from codeweaver.core.types.models import BASEDMODEL_CONFIG, BasedModel
from codeweaver.providers.embedding.types import SparseEmbedding


if TYPE_CHECKING:
    from qdrant_client.http.models import FusionQuery, Prefetch
    from rich.table import Table

    from codeweaver.core.types import AnonymityConversion, FilteredKeyT


class SearchStrategy(BaseEnum):
    """Enumeration of search types."""

    COMMIT_SEARCH = "commit_search"
    FILE_DISCOVERY = "file_discovery"
    LANGUAGE_SEARCH = "language_search"
    SYMBOL_SEARCH = "symbol_search"
    TEXT_SEARCH = "text_search"
    HYBRID_SEARCH = "hybrid_search"
    SEMANTIC_RERANK = "semantic_rerank"
    SPARSE_ONLY = "sparse_only"
    DENSE_ONLY = "dense_only"
    KEYWORD_FALLBACK = "keyword_fallback"


class CodeMatchType(BaseEnum):
    """Enumeration of code match types."""

    SEMANTIC = "semantic"
    SYNTACTIC = "syntactic"
    KEYWORD = "keyword"
    FILE_PATTERN = "file_pattern"


class CodeMatch(BasedModel):
    """Individual code match with context and metadata."""

    model_config = BASEDMODEL_CONFIG | ConfigDict(defer_build=True)

    # File information
    file: Annotated[DiscoveredFile, Field(description="""File information""")]

    # Content
    content: Annotated[CodeChunk, Field(description="""The relevant code chunk.""")]

    span: Annotated[Span, Field(description="""Start and end line numbers""")]

    # Relevance scoring
    relevance_score: Annotated[
        NonNegativeFloat,
        Field(
            le=1.0,
            description="""\
        Adjusted relevance score (0.0-1.0).

        This is not the raw similarity score returned by a vector database. CodeWeaver applies multiple layers of adjustments based on factors such as:
        - Repo/code structures
        - Weighting of different search strategies, confidence levels, and likely relevance for the task
        - Semantic importance/significance
        - Language-specific heuristics
        - The goal and reason for the search (i.e., if the user or agent wants to debug a function, matches in test files with no direct connections to the function may be excluded or downranked)

        The final relevance score, which is what this field represents, is a value between 0.0 and 1.0, where 1.0 indicates the highest relevance to the search query (screened results are normalized to 1, where 1 is the most relevant).

        If you persistently have issues where a relevance score seems off or isn't returning quality results for a particular task, please [start a discussion](https://github.com/knitli/codeweaver-mcp/discussions) or [open an issue](https://github.com/knitli/codeweaver-mcp/issues). Results aren't perfect but we are going to try to get there!
    """,
        ),
    ]

    match_type: Annotated[
        CodeMatchType, Field(description="""The type of match for this code match""")
    ]

    related_symbols: Annotated[
        tuple[str, ...],
        Field(default_factory=tuple, description="""Related functions, classes, or symbols"""),
    ]

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        from codeweaver.core.types import AnonymityConversion, FilteredKey

        return {FilteredKey("related_symbols"): AnonymityConversion.COUNT}

    @model_validator(mode="after")
    def validate_span(self) -> CodeMatch:
        """Validate span consistency."""
        # Access Span attributes directly instead of unpacking
        if self.span.start > self.span.end:
            raise ValueError("Start line must be <= end line")
        if self.span.start < 1:
            raise ValueError("Line numbers must start from 1")
        return self

    def serialize_for_cli(self) -> dict[str, Any]:
        """Serialize code match for CLI display.

        Returns a dict suitable for rendering in CLI output formats.
        """
        return self.model_dump() | {
            "file": self.file.serialize_for_cli(),
            "span": self.span.serialize_for_cli(),
            "content": self.content.serialize_for_cli(),
            "relevance_score": self.relevance_score,
            "match_type": self.match_type.as_title,
            "related_symbols": self.related_symbols,
        }


class FindCodeResponseSummary(BasedModel):
    """Structured response from find_code tool."""

    model_config = BASEDMODEL_CONFIG | ConfigDict(defer_build=True)

    # Core results
    matches: Annotated[
        list[CodeMatch], Field(description="""Relevant code matches ranked by relevance""")
    ]

    summary: Annotated[
        str, Field(description="""High-level summary or explanation of findings""", max_length=1000)
    ]

    query_intent: Annotated[
        IntentType | None, Field(description="""Detected or specified intent""")
    ]

    total_matches: Annotated[
        NonNegativeInt, Field(description="""Total matches found *before* ranking""")
    ]

    total_results: Annotated[
        NonNegativeInt, Field(description="""Total results returned in this response""")
    ]

    token_count: Annotated[NonNegativeInt, Field(description="""Actual tokens used in response""")]

    execution_time_ms: Annotated[NonNegativeFloat, Field(description="""Total processing time""")]

    # Context information
    search_strategy: Annotated[
        tuple[SearchStrategy, ...], Field(description="""Search methods used""")
    ]

    languages_found: Annotated[
        tuple[SemanticSearchLanguage | LanguageName, ...],
        Field(
            description="""Programming languages in the results. If the language is supported for semantic search, it will be a `SemanticSearchLanguage`, otherwise a `LanguageName` NewType (str) from languages in `codeweaver.core.file_extensions.py`""",
            default_factory=tuple,
        ),
    ]

    @model_validator(mode="after")
    def populate_computed_fields(self) -> FindCodeResponseSummary:
        """Populate computed fields from other data."""
        # Set total_results from matches count if not already set
        if self.total_results == 0 and self.matches:
            object.__setattr__(self, "total_results", len(self.matches))

        # Set languages_found from matches if not already populated
        if not self.languages_found and self.matches:
            languages = tuple(
                match.file.ext_kind.language
                for match in self.matches
                if match and match.file and match.file.ext_kind and match.file.ext_kind.language
            )
            object.__setattr__(self, "languages_found", languages)

        return self

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        from codeweaver.core.types import AnonymityConversion, FilteredKey

        return {FilteredKey("summary"): AnonymityConversion.TEXT_COUNT}

    @classmethod
    def get_schema(cls) -> dict[str, Any]:
        """Get the JSON schema for the model as a Python dictionary."""
        return cls.model_json_schema(mode="serialization")

    def assemble_cli_summary(self) -> Table:
        """Assemble a concise CLI summary of the response."""
        from rich.table import Table

        table = Table(title="Find Code Response Summary")
        table.add_column("Metric", justify="left", style="cyan", no_wrap=True)
        table.add_column("Value", justify="right", style="magenta")

        table.add_row("Total Matches Found", str(self.total_matches))
        table.add_row("Total Results Returned", str(self.total_results))
        table.add_row(
            "Languages Found", ", ".join(str(lang) for lang in self.languages_found) or "None"
        )
        table.add_row(
            "Search Strategies Used",
            ", ".join(strategy.as_title for strategy in self.search_strategy),
        )
        table.add_row("Execution Time", f"{self.execution_time_ms:.2f} ms")
        table.add_row("Token Count", str(self.token_count))
        table.add_row("Summary", self.summary)
        return table


# Rebuild models to resolve forward references
if not CodeMatch.__pydantic_complete__:
    _ = CodeMatch.model_rebuild()
if not FindCodeResponseSummary.__pydantic_complete__:
    _ = FindCodeResponseSummary.model_rebuild()


class StrategizedQuery(NamedTuple):
    """NamedTuple representing a strategized query for code search."""

    query: str
    dense: Sequence[float] | Sequence[int] | None
    sparse: Annotated[SparseEmbedding | None, Field(description="Sparse embedding data")]
    strategy: Annotated[SearchStrategy, Field(description="Search strategy to use")]

    def is_empty(self) -> bool:
        """Check if both dense and sparse embeddings are None or empty."""
        dense_empty = self.dense is None or len(self.dense) == 0
        sparse_empty = self.sparse is None or (
            len(self.sparse.indices) == 0 and len(self.sparse.values) == 0
        )
        return dense_empty and sparse_empty

    def has_dense(self) -> bool:
        """Check if dense embedding is present and non-empty."""
        return self.dense is not None and len(self.dense) > 0

    def has_sparse(self) -> bool:
        """Check if sparse embedding is present and non-empty."""
        return (
            self.sparse is not None and len(self.sparse.indices) > 0 and len(self.sparse.values) > 0
        )

    def is_hybrid(self) -> bool:
        """Check if both dense and sparse embeddings are present and non-empty."""
        return self.has_dense() and self.has_sparse()

    def to_hybrid_query(
        self, query_kwargs: dict[str, Any], kwargs: dict[str, Any]
    ) -> dict[str, FusionQuery | list[Prefetch] | Any]:
        """Convert to a FusionQuery for hybrid search."""
        from qdrant_client.http.models import Fusion, FusionQuery, Prefetch, SparseVector

        if not self.is_hybrid():
            raise ValueError("Both dense and sparse embeddings must be present for hybrid query.")

        # Convert sparse dict to SparseVector with indices and values
        assert self.sparse is not None  # noqa: S101
        sparse_vector = SparseVector(
            indices=list(self.sparse.indices), values=list(self.sparse.values)
        )

        return {
            "query": FusionQuery(fusion=Fusion.RRF),
            "prefetch": [
                Prefetch(query=self.dense, using="dense", **query_kwargs),
                Prefetch(query=sparse_vector, using="sparse", **query_kwargs),
            ],
            **kwargs,
        }

    def to_query(self, kwargs: dict[str, Any]) -> dict[str, FusionQuery | list[Prefetch] | Any]:
        """Convert to a FusionQuery based on available embeddings."""
        if self.is_empty():
            raise ValueError(
                "At least one of dense or sparse embeddings must be present for query."
            )
        if self.is_hybrid():
            return self.to_hybrid_query({}, kwargs)
        from qdrant_client.http.models import SparseVector

        if self.has_dense():
            return {"query": self.dense, **kwargs}

        # Convert sparse dict to SparseVector
        assert self.sparse is not None  # noqa: S101
        sparse_vector = SparseVector(
            indices=list(self.sparse.indices), values=list(self.sparse.values)
        )
        return {"query": sparse_vector, **kwargs}


__all__ = (
    "CodeMatch",
    "CodeMatchType",
    "FindCodeResponseSummary",
    "SearchStrategy",
    "StrategizedQuery",
)
