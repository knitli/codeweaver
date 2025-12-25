# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Core search types for CodeWeaver."""

from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, NamedTuple

from pydantic import AfterValidator, ConfigDict, Field, NonNegativeFloat

from codeweaver.core.chunks import CodeChunk
from codeweaver.core.discovery import DiscoveredFile
from codeweaver.core.metadata import Metadata
from codeweaver.core.types.enum import BaseEnum
from codeweaver.core.types.embeddings import SparseEmbedding
from codeweaver.core.types.models import BasedModel
from codeweaver.core.types.utils import generate_field_title
from codeweaver.core.utils import set_relative_path


if TYPE_CHECKING:
    from qdrant_client.http.models import FusionQuery, Prefetch

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

    # Alias for HYBRID_SEARCH for backward compatibility
    HYBRID = HYBRID_SEARCH


class StrategizedQuery(NamedTuple):
    """NamedTuple representing a strategized query for code search."""

    query: str
    dense: Sequence[float] | Sequence[int] | None
    sparse: Annotated[
        SparseEmbedding | None,
        Field(description="Sparse embedding data", field_title_generator=generate_field_title),
    ]
    strategy: Annotated[
        SearchStrategy,
        Field(description="Search strategy to use", field_title_generator=generate_field_title),
    ]

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
        from qdrant_client.http.models import Prefetch, Rrf, RrfQuery, SparseVector

        from codeweaver.exceptions import QueryError

        if not self.is_hybrid():
            raise QueryError(
                "Cannot create hybrid query: both dense and sparse embeddings required",
                details={
                    "has_dense": self.has_dense(),
                    "has_sparse": self.has_sparse(),
                    "strategy": self.strategy.variable,
                },
                suggestions=[
                    "Ensure both embedding providers are configured",
                    "Use dense-only or sparse-only search if one provider fails",
                    "Check embedding provider logs for errors",
                ],
            )

        # Convert sparse dict to SparseVector with indices and values
        assert self.sparse is not None  # noqa: S101
        sparse_vector = SparseVector(
            indices=list(self.sparse.indices), values=list(self.sparse.values)
        )

        # Extract Prefetch-specific parameters (limit, score_threshold, filter, params)
        prefetch_params = {
            k: v
            for k, v in query_kwargs.items()
            if k in ("limit", "score_threshold", "filter", "params")
        }

        # Extract top-level query_points parameters
        top_level_params = {
            k: v
            for k, v in query_kwargs.items()
            if k
            in (
                "with_payload",
                "with_vectors",
                "query_filter",
                "limit",
                "offset",
                "consistency",
                "shard_key_selector",
                "timeout",
                "lookup_from",
            )
            and v is not None
        }

        # Use bare vectors with 'using' parameter for named vector search in Prefetch
        assert self.dense is not None  # noqa: S101
        return {
            "query": RrfQuery(rrf=Rrf(k=2)),
            "prefetch": [
                Prefetch(query=list(self.dense), using="dense", **prefetch_params),
                Prefetch(query=sparse_vector, using="sparse", **prefetch_params),
            ],
            **top_level_params,
            **kwargs,
        }

    def to_query(self, kwargs: dict[str, Any]) -> dict[str, FusionQuery | list[Prefetch] | Any]:
        """Convert to a query dict based on available embeddings."""
        from codeweaver.exceptions import QueryError

        if self.is_empty():
            raise QueryError(
                "Cannot create query: at least one embedding type required",
                details={
                    "has_dense": self.has_dense(),
                    "has_sparse": self.has_sparse(),
                    "query": self.query,
                },
                suggestions=[
                    "Configure at least one embedding provider (dense or sparse)",
                    "Verify embedding provider initialization succeeded",
                    "Check embedding provider logs for errors",
                ],
            )
        if self.is_hybrid():
            return self.to_hybrid_query({}, kwargs)
        from qdrant_client.http.models import SparseVector

        if self.has_dense():
            # Dense-only
            assert self.dense is not None  # noqa: S101
            return {"query": list(self.dense), "using": "dense", **kwargs}

        # Sparse-only
        assert self.sparse is not None  # noqa: S101
        sparse_vector = SparseVector(
            indices=list(self.sparse.indices), values=list(self.sparse.values)
        )
        return {"query": sparse_vector, "using": "sparse", **kwargs}


class SearchResult(BasedModel):
    """Result from vector search operations."""

    model_config = ConfigDict(validate_assignment=False, extra="allow")

    content: CodeChunk
    file_path: Annotated[
        Path | None,
        Field(description="""Path to the source file"""),
        AfterValidator(set_relative_path),
    ]
    score: Annotated[NonNegativeFloat, Field(description="""Similarity score""")]
    metadata: Annotated[
        Metadata | None, Field(description="""Additional metadata about the result""")
    ] = None
    strategized_query: Annotated[
        StrategizedQuery | None, Field(description="""The query used for the search""")
    ] = None

    # Fields for hybrid search and rescoring
    dense_score: NonNegativeFloat | None = None
    sparse_score: NonNegativeFloat | None = None
    rerank_score: NonNegativeFloat | None = None
    relevance_score: NonNegativeFloat | None = None

    @property
    def chunk(self) -> CodeChunk:
        """Alias for content field for backward compatibility."""
        return self.content

    @property
    def file(self) -> Any:
        """Property to access file info from chunk."""
        if isinstance(self.content, CodeChunk) and hasattr(self.content, "file"):
            return DiscoveredFile.from_chunk(self.content)

        class _FileInfo:
            def __init__(self, path: Path) -> None:
                self.path = path

        return _FileInfo(self.file_path) if self.file_path else None

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        from codeweaver.core.types import AnonymityConversion, FilteredKey

        return {
            FilteredKey("file_path"): AnonymityConversion.BOOLEAN,
            FilteredKey("metadata"): AnonymityConversion.BOOLEAN,
        }


__all__ = ("SearchResult", "SearchStrategy", "StrategizedQuery")
