# sourcery skip: lambdas-should-be-short
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Core models for CodeWeaver responses and data structures."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any

from pydantic import ConfigDict, Field, NonNegativeFloat, NonNegativeInt, model_validator

from codeweaver.agent_api.intent import IntentType
from codeweaver.core.chunks import CodeChunk
from codeweaver.core.discovery import DiscoveredFile
from codeweaver.core.language import SemanticSearchLanguage
from codeweaver.core.spans import Span
from codeweaver.core.types import LanguageName
from codeweaver.core.types.enum import BaseEnum
from codeweaver.core.types.models import BASEDMODEL_CONFIG, BasedModel


if TYPE_CHECKING:
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


__all__ = ("CodeMatch", "CodeMatchType", "FindCodeResponseSummary", "SearchStrategy")


# Rebuild models to resolve forward references
if not CodeMatch.__pydantic_complete__:
    _ = CodeMatch.model_rebuild()
if not FindCodeResponseSummary.__pydantic_complete__:
    _ = FindCodeResponseSummary.model_rebuild()
