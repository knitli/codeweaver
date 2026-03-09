# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Tests for EmbeddingBatchInfo with required intent field."""

import pytest

from uuid_extensions import uuid7

from codeweaver.core.types import CodeWeaverSparseEmbedding, EmbeddingBatchInfo, EmbeddingKind


@pytest.mark.unit
class TestEmbeddingBatchInfoIntent:
    """Test EmbeddingBatchInfo with intent field."""

    def test_create_dense_with_default_intent(self):
        """Test creating dense embedding with default intent."""
        info = EmbeddingBatchInfo.create_dense(
            batch_id=uuid7(),
            batch_index=0,
            chunk_id=uuid7(),
            model="test-model",
            embeddings=[0.1, 0.2, 0.3],
            dimension=3,
        )

        assert info.intent == "primary"  # Default for dense
        assert info.kind == EmbeddingKind.DENSE
        assert info.is_dense
        assert not info.is_sparse

    def test_create_dense_with_custom_intent(self):
        """Test creating dense embedding with custom intent."""
        info = EmbeddingBatchInfo.create_dense(
            batch_id=uuid7(),
            batch_index=0,
            chunk_id=uuid7(),
            model="test-model",
            embeddings=[0.1, 0.2, 0.3],
            dimension=3,
            intent="backup",
        )

        assert info.intent == "backup"
        assert info.kind == EmbeddingKind.DENSE

    def test_create_sparse_with_default_intent(self):
        """Test creating sparse embedding with default intent."""
        sparse_emb = CodeWeaverSparseEmbedding(indices=[1, 2], values=[0.8, 0.7])
        sparse_emb = CodeWeaverSparseEmbedding(indices=[1, 2], values=[0.8, 0.7])

        info = EmbeddingBatchInfo.create_sparse(
            batch_id=uuid7(),
            batch_index=0,
            chunk_id=uuid7(),
            model="test-sparse-model",
            embeddings=sparse_emb,
        )

        assert info.intent == "sparse"  # Default for sparse
        assert info.kind == EmbeddingKind.SPARSE
        assert info.is_sparse
        assert not info.is_dense

    def test_create_sparse_with_custom_intent(self):
        """Test creating sparse embedding with custom intent."""
        sparse_emb = CodeWeaverSparseEmbedding(indices=[1, 2], values=[0.8, 0.7])
        sparse_emb = CodeWeaverSparseEmbedding(indices=[1, 2], values=[0.8, 0.7])

        info = EmbeddingBatchInfo.create_sparse(
            batch_id=uuid7(),
            batch_index=0,
            chunk_id=uuid7(),
            model="test-sparse-model",
            embeddings=sparse_emb,
            intent="function_signatures",
        )

        assert info.intent == "function_signatures"
        assert info.kind == EmbeddingKind.SPARSE

    def test_intent_is_self_describing(self):
        """Test that embeddings are self-describing with intent field."""
        chunk_id = uuid7()

        dense_info = EmbeddingBatchInfo.create_dense(
            batch_id=uuid7(),
            batch_index=0,
            chunk_id=chunk_id,
            model="dense-model",
            embeddings=[0.1] * 512,
            dimension=512,
            intent="primary",
        )

        backup_info = EmbeddingBatchInfo.create_dense(
            batch_id=uuid7(),
            batch_index=0,
            chunk_id=chunk_id,
            model="backup-model",
            embeddings=[0.2] * 256,
            dimension=256,
            intent="backup",
        )

        # Can distinguish embeddings by their intent field
        assert dense_info.intent != backup_info.intent
        assert dense_info.intent == "primary"
        assert backup_info.intent == "backup"

    def test_multiple_intents_same_kind(self):
        """Test that multiple embeddings of same kind can have different intents."""
        chunk_id = uuid7()

        # Two different dense embeddings with different intents
        primary = EmbeddingBatchInfo.create_dense(
            batch_id=uuid7(),
            batch_index=0,
            chunk_id=chunk_id,
            model="model-1",
            embeddings=[0.1] * 512,
            dimension=512,
            intent="primary",
        )

        summary = EmbeddingBatchInfo.create_dense(
            batch_id=uuid7(),
            batch_index=0,
            chunk_id=chunk_id,
            model="model-2",
            embeddings=[0.2] * 256,
            dimension=256,
            intent="summary",
        )

        assert primary.kind == summary.kind == EmbeddingKind.DENSE
        assert primary.intent != summary.intent
        assert primary.model != summary.model
