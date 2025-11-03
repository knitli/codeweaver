# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""
Types for the find_code tool.
"""

from collections.abc import Sequence
from typing import TYPE_CHECKING, Any, NamedTuple

from codeweaver.agent_api.models import SearchStrategy


if TYPE_CHECKING:
    from qdrant_client.http.models import FusionQuery, Prefetch


class StrategizedQuery(NamedTuple):
    """NamedTuple representing a strategized query for code search."""

    query: str
    dense: Sequence[float] | Sequence[int] | None
    sparse: Sequence[float] | Sequence[int] | None
    strategy: SearchStrategy

    def is_empty(self) -> bool:
        """Check if both dense and sparse embeddings are None or empty."""
        dense_empty = self.dense is None or len(self.dense) == 0
        sparse_empty = self.sparse is None or len(self.sparse) == 0
        return dense_empty and sparse_empty

    def has_dense(self) -> bool:
        """Check if dense embedding is present and non-empty."""
        return self.dense is not None and len(self.dense) > 0

    def has_sparse(self) -> bool:
        """Check if sparse embedding is present and non-empty."""
        return self.sparse is not None and len(self.sparse) > 0

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
        return {
            "query": FusionQuery(fusion=Fusion.RRF),
            "prefetch": [
                Prefetch(query=self.dense, using="dense", **query_kwargs),
                Prefetch(query=SparseVector(self.sparse), using="sparse", **query_kwargs),
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

        return {"query": self.dense if self.has_dense() else SparseVector(self.sparse), **kwargs}
