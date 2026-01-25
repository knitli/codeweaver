# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Tests for VectorNames mapping between intents and physical vector names."""


from codeweaver.core.types.strategy import EmbeddingStrategy, VectorStrategy
from codeweaver.providers.vector_stores.vector_names import VectorNames


@pytest.mark.unit
class TestVectorNames:
    """Test VectorNames mapping."""

    def test_resolve_mapped_intent(self):
        """Test resolving an intent with explicit mapping."""
        names = VectorNames(
            mapping={
                "primary": "voyage_large_2",
                "sparse": "bm25_sparse",
                "backup": "jina_v3",
            }
        )

        assert names.resolve("primary") == "voyage_large_2"
        assert names.resolve("sparse") == "bm25_sparse"
        assert names.resolve("backup") == "jina_v3"

    def test_resolve_unmapped_intent_fallback(self):
        """Test that unmapped intents fallback to the intent name itself."""
        names = VectorNames(mapping={"primary": "voyage_large_2"})

        # Unmapped intent falls back to the intent name
        assert names.resolve("unknown") == "unknown"
        assert names.resolve("new_intent") == "new_intent"

    def test_from_strategy_voyage_model(self):
        """Test auto-generation from strategy with Voyage model."""
        strategy = EmbeddingStrategy(
            vectors={"primary": VectorStrategy.dense("voyage-large-2-instruct")}
        )

        names = VectorNames.from_strategy(strategy)

        # "voyage-large-2-instruct" → "voyage_large_2" (simplified)
        assert "primary" in names.mapping
        physical_name = names.resolve("primary")
        assert "voyage" in physical_name.lower()
        assert "-" not in physical_name  # Hyphens converted to underscores

    def test_from_strategy_multiple_vectors(self):
        """Test auto-generation with multiple vectors."""
        strategy = EmbeddingStrategy(
            vectors={
                "primary": VectorStrategy.dense("voyage-large-2-instruct"),
                "sparse": VectorStrategy.sparse("Alibaba-NLP/gte-multilingual-mlm-base"),
                "backup": VectorStrategy.dense("jinaai/jina-embeddings-v3"),
            }
        )

        names = VectorNames.from_strategy(strategy)

        assert len(names.mapping) == 3
        assert "primary" in names.mapping
        assert "sparse" in names.mapping
        assert "backup" in names.mapping

        # Verify all names are lowercase with underscores
        for intent in ["primary", "sparse", "backup"]:
            physical = names.resolve(intent)
            assert physical.islower()
            assert "-" not in physical

    def test_from_strategy_with_org_prefix(self):
        """Test that org prefixes (before /) are stripped."""
        strategy = EmbeddingStrategy(
            vectors={
                "model1": VectorStrategy.dense("jinaai/jina-embeddings-v3"),
                "model2": VectorStrategy.sparse("Alibaba-NLP/gte-multilingual"),
            }
        )

        names = VectorNames.from_strategy(strategy)

        # "jinaai/jina-embeddings-v3" → "jina_embeddings_v3"
        model1_name = names.resolve("model1")
        assert "jinaai" not in model1_name.lower()  # org prefix removed
        assert "jina" in model1_name.lower()

        # "Alibaba-NLP/gte-multilingual" → "gte_multilingual"
        model2_name = names.resolve("model2")
        assert "alibaba" not in model2_name.lower()  # org prefix removed
        assert "gte" in model2_name.lower()

    def test_simplification_removes_suffix(self):
        """Test that common suffixes like 'instruct', 'base' are removed."""
        strategy = EmbeddingStrategy(
            vectors={
                "model1": VectorStrategy.dense("voyage-large-2-instruct"),
                "model2": VectorStrategy.dense("model-name-base"),
                "model3": VectorStrategy.dense("test-model-small"),
            }
        )

        names = VectorNames.from_strategy(strategy)

        # Simplification removes common suffixes from long names
        model1 = names.resolve("model1")
        # Should be simplified: "voyage-large-2-instruct" → "voyage_large_2"
        assert model1.count("_") <= 2  # Simplified to fewer parts

    def test_explicit_mapping_overrides(self):
        """Test that explicit mapping takes precedence."""
        names = VectorNames(
            mapping={
                "primary": "custom_vector_name",
                "sparse": "my_sparse",
            }
        )

        assert names.resolve("primary") == "custom_vector_name"
        assert names.resolve("sparse") == "my_sparse"
        # Fallback for unmapped
        assert names.resolve("unmapped") == "unmapped"

    def test_case_normalization(self):
        """Test that physical names are lowercase."""
        strategy = EmbeddingStrategy(
            vectors={
                "model1": VectorStrategy.dense("UPPER-CASE-MODEL"),
                "model2": VectorStrategy.sparse("MixedCase-Model"),
            }
        )

        names = VectorNames.from_strategy(strategy)

        model1 = names.resolve("model1")
        model2 = names.resolve("model2")

        assert model1.islower()
        assert model2.islower()

    def test_empty_mapping(self):
        """Test VectorNames with empty mapping."""
        names = VectorNames(mapping={})

        # All intents fall back to themselves
        assert names.resolve("anything") == "anything"
        assert names.resolve("primary") == "primary"
