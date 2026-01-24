# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Vector name resolution for mapping intents to physical Qdrant vector names."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from pydantic import Field

from codeweaver.core import BasedModel
from codeweaver.core.types.utils import generate_field_title


if TYPE_CHECKING:
    from codeweaver.core.types.strategy import EmbeddingStrategy


class VectorNames(BasedModel):
    """Maps logical intent names to physical Qdrant vector names (minimal implementation).

    This allows decoupling the semantic intent (e.g., "primary", "backup") from the
    physical storage name in Qdrant (e.g., "voyage_large_2", "jina_v3").
    """

    mapping: Annotated[
        dict[str, str],
        Field(
            description="Intent to physical vector name mapping",
            field_title_generator=generate_field_title,
        ),
    ]

    def resolve(self, intent: str) -> str:
        """Get physical vector name for an intent.

        Args:
            intent: Logical intent name (e.g., "primary", "backup", "sparse")

        Returns:
            str: Physical Qdrant vector name (falls back to intent if not mapped)
        """
        return self.mapping.get(intent, intent)

    @classmethod
    def from_strategy(cls, strategy: EmbeddingStrategy) -> VectorNames:
        """Auto-generate vector names from an embedding strategy.

        Converts model names to valid Qdrant vector names:
        - "voyage-large-2-instruct" → "voyage_large_2"
        - "jinaai/jina-embeddings-v3" → "jina_embeddings_v3"

        Args:
            strategy: EmbeddingStrategy to generate names from

        Returns:
            VectorNames: Configured mapping
        """
        mapping = {}
        for intent, vec_strategy in strategy.vectors.items():
            # Extract model name (handle "org/model" format)
            model_name = str(vec_strategy.model).split("/")[-1]
            # Convert to valid vector name (replace hyphens with underscores, lowercase)
            vector_name = model_name.replace("-", "_").lower()
            # Simplify common patterns (remove trailing version numbers if present)
            # e.g., "voyage_large_2_instruct" → "voyage_large_2"
            parts = vector_name.split("_")
            if len(parts) > 3 and parts[-1] in ("instruct", "base", "small", "large"):
                vector_name = "_".join(parts[:-1])

            mapping[intent] = vector_name

        return cls(mapping=mapping)


__all__ = ("VectorNames",)
