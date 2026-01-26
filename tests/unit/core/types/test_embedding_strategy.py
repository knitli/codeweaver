# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Tests for EmbeddingStrategy and VectorStrategy types."""

import pytest

from codeweaver.core.types import EmbeddingKind
from codeweaver.core.types.strategy import EmbeddingStrategy, VectorStrategy


@pytest.mark.unit
class TestVectorStrategy:
    """Test VectorStrategy configuration."""

    def test_create_dense_strategy(self):
        """Test creating dense vector strategy."""
        strategy = VectorStrategy.dense("voyage-large-2-instruct")

        assert strategy.kind == EmbeddingKind.DENSE
        assert str(strategy.model) == "voyage-large-2-instruct"
        assert strategy.lazy is False

    def test_create_sparse_strategy(self):
        """Test creating sparse vector strategy."""
        strategy = VectorStrategy.sparse("Alibaba-NLP/gte-multilingual-mlm-base")

        assert strategy.kind == EmbeddingKind.SPARSE
        assert "Alibaba-NLP" in str(strategy.model)
        assert strategy.lazy is False

    def test_lazy_vector_strategy(self):
        """Test creating lazy vector strategy."""
        strategy = VectorStrategy.dense("jinaai/jina-embeddings-v3", lazy=True)

        assert strategy.kind == EmbeddingKind.DENSE
        assert strategy.lazy is True

    def test_vector_strategy_from_constructor(self):
        """Test creating VectorStrategy from constructor."""
        from codeweaver.core.types import ModelName

        strategy = VectorStrategy(
            model=ModelName("test-model"), kind=EmbeddingKind.DENSE, lazy=False
        )

        assert str(strategy.model) == "test-model"
        assert strategy.kind == EmbeddingKind.DENSE
        assert strategy.lazy is False


@pytest.mark.unit
class TestEmbeddingStrategy:
    """Test EmbeddingStrategy configuration."""

    def test_default_strategy(self):
        """Test default embedding strategy."""
        strategy = EmbeddingStrategy.default()

        assert "primary" in strategy.intents
        assert "sparse" in strategy.intents
        assert len(strategy.intents) == 2

        primary = strategy.get_strategy("primary")
        assert primary.kind == EmbeddingKind.DENSE
        assert "voyage" in str(primary.model).lower()

        sparse = strategy.get_strategy("sparse")
        assert sparse.kind == EmbeddingKind.SPARSE

    def test_with_backup_strategy(self):
        """Test embedding strategy with failover backup."""
        strategy = EmbeddingStrategy.with_backup()

        assert "primary" in strategy.intents
        assert "sparse" in strategy.intents
        assert "backup" in strategy.intents
        assert len(strategy.intents) == 3

        backup = strategy.get_strategy("backup")
        assert backup.kind == EmbeddingKind.DENSE
        assert backup.lazy is True  # Backup is lazy by default

    def test_custom_strategy(self):
        """Test creating custom embedding strategy."""
        strategy = EmbeddingStrategy(
            vectors={
                "primary": VectorStrategy.dense("model-1"),
                "sparse": VectorStrategy.sparse("model-2"),
                "summary": VectorStrategy.dense("model-3", lazy=True),
                "ast": VectorStrategy.sparse("model-4", lazy=True),
            }
        )

        assert len(strategy.intents) == 4
        assert "primary" in strategy.intents
        assert "sparse" in strategy.intents
        assert "summary" in strategy.intents
        assert "ast" in strategy.intents

        # Check lazy configuration
        assert strategy.get_strategy("primary").lazy is False
        assert strategy.get_strategy("summary").lazy is True
        assert strategy.get_strategy("ast").lazy is True

    def test_get_strategy(self):
        """Test retrieving strategy by intent."""
        strategy = EmbeddingStrategy.with_backup()

        primary = strategy.get_strategy("primary")
        assert primary.kind == EmbeddingKind.DENSE

        backup = strategy.get_strategy("backup")
        assert backup.kind == EmbeddingKind.DENSE
        assert backup.lazy is True

    def test_intents_property(self):
        """Test intents property returns all configured intents."""
        strategy = EmbeddingStrategy(
            vectors={
                "intent1": VectorStrategy.dense("model-1"),
                "intent2": VectorStrategy.sparse("model-2"),
                "intent3": VectorStrategy.dense("model-3"),
            }
        )

        intents = strategy.intents
        assert len(intents) == 3
        assert "intent1" in intents
        assert "intent2" in intents
        assert "intent3" in intents

    def test_mixed_eager_and_lazy(self):
        """Test strategy with mix of eager and lazy vectors."""
        strategy = EmbeddingStrategy(
            vectors={
                "primary": VectorStrategy.dense("model-1", lazy=False),
                "sparse": VectorStrategy.sparse("model-2", lazy=False),
                "backup": VectorStrategy.dense("model-3", lazy=True),
                "function_sig": VectorStrategy.sparse("model-4", lazy=True),
            }
        )

        # Eager vectors
        assert strategy.get_strategy("primary").lazy is False
        assert strategy.get_strategy("sparse").lazy is False

        # Lazy vectors
        assert strategy.get_strategy("backup").lazy is True
        assert strategy.get_strategy("function_sig").lazy is True

    def test_multiple_dense_vectors(self):
        """Test strategy with multiple dense vectors for different purposes."""
        strategy = EmbeddingStrategy(
            vectors={
                "primary": VectorStrategy.dense("voyage-large-2"),
                "backup": VectorStrategy.dense("jina-v3"),
                "summary": VectorStrategy.dense("voyage-large-2"),  # Same model, different intent
            }
        )

        assert len(strategy.intents) == 3
        assert all(
            strategy.get_strategy(intent).kind == EmbeddingKind.DENSE for intent in strategy.intents
        )

    def test_empty_strategy(self):
        """Test that empty strategy is technically valid but useless."""
        strategy = EmbeddingStrategy(vectors={})

        assert len(strategy.intents) == 0
