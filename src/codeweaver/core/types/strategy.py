# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Embedding strategy type definitions for multi-vector architectures."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from codeweaver.core import BasedModel
from codeweaver.core.types.aliases import ModelName, ModelNameT
from codeweaver.core.types.embeddings import EmbeddingKind
from codeweaver.core.types.utils import generate_field_title


class VectorStrategy(BasedModel):
    """Configuration for a single vector type (minimal implementation).

    Defines how a specific embedding vector should be generated and used.
    """

    model: Annotated[
        ModelNameT,
        Field(
            description="Model name for generating this embedding",
            field_title_generator=generate_field_title,
        ),
    ]
    kind: Annotated[
        EmbeddingKind,
        Field(
            description="Kind of embedding (dense or sparse)",
            field_title_generator=generate_field_title,
        ),
    ]
    lazy: Annotated[
        bool,
        Field(
            description="Generate on-demand (True) vs upfront (False)",
            field_title_generator=generate_field_title,
        ),
    ] = False

    @classmethod
    def dense(cls, model: str | ModelNameT, *, lazy: bool = False) -> VectorStrategy:
        """Create a dense vector strategy.

        Args:
            model: Model name for dense embeddings
            lazy: Whether to generate on-demand (default: False)

        Returns:
            VectorStrategy: Configured for dense embeddings
        """
        return cls(model=ModelName(model), kind=EmbeddingKind.DENSE, lazy=lazy)

    @classmethod
    def sparse(cls, model: str | ModelNameT, *, lazy: bool = False) -> VectorStrategy:
        """Create a sparse vector strategy.

        Args:
            model: Model name for sparse embeddings
            lazy: Whether to generate on-demand (default: False)

        Returns:
            VectorStrategy: Configured for sparse embeddings
        """
        return cls(model=ModelName(model), kind=EmbeddingKind.SPARSE, lazy=lazy)


class EmbeddingStrategy(BasedModel):
    """Multi-vector embedding strategy (minimal implementation).

    Defines the complete set of embedding vectors to generate for each chunk.
    """

    vectors: Annotated[
        dict[str, VectorStrategy],
        Field(
            description="Vector strategies keyed by intent name",
            field_title_generator=generate_field_title,
        ),
    ]

    @classmethod
    def default(cls) -> EmbeddingStrategy:
        """Create default embedding strategy with primary dense and sparse vectors.

        Returns:
            EmbeddingStrategy: Default configuration
        """
        return cls(
            vectors={
                "primary": VectorStrategy.dense("voyage-large-2-instruct"),
                "sparse": VectorStrategy.sparse("Alibaba-NLP/gte-multilingual-mlm-base"),
            }
        )

    @classmethod
    def with_backup(cls) -> EmbeddingStrategy:
        """Create embedding strategy with backup dense vector.

        Returns:
            EmbeddingStrategy: Configuration with primary, sparse, and backup
        """
        return cls(
            vectors={
                "primary": VectorStrategy.dense("voyage-large-2-instruct"),
                "sparse": VectorStrategy.sparse("Alibaba-NLP/gte-multilingual-mlm-base"),
                "backup": VectorStrategy.dense("jinaai/jina-embeddings-v3", lazy=True),
            }
        )

    @property
    def intents(self) -> set[str]:
        """Get all intent names defined in this strategy.

        Returns:
            set[str]: Set of intent names
        """
        return set(self.vectors.keys())


__all__ = ("EmbeddingStrategy", "VectorStrategy")
