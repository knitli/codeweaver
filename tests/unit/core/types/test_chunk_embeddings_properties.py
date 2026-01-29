# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Tests for ChunkEmbeddings helper properties (has_dense, has_sparse, is_complete)."""

from pathlib import Path

import pytest

from uuid_extensions import uuid7

from codeweaver.core import CodeChunk, Span
from codeweaver.core.metadata import ChunkKind, ExtKind
from codeweaver.core.types import ChunkEmbeddings, EmbeddingBatchInfo, SparseEmbedding


@pytest.fixture
def sample_chunk():
    """Create a sample CodeChunk for testing."""
    chunk_id = uuid7()
    return CodeChunk(
        chunk_id=chunk_id,
        ext_kind=ExtKind.from_language("python", ChunkKind.CODE),
        chunk_name="test.py:func",
        file_path=Path("test.py"),
        language="python",
        content="def test(): pass",
        line_range=Span(start=1, end=1, source_id=chunk_id),
    )


@pytest.mark.unit
class TestChunkEmbeddingsProperties:
    """Test ChunkEmbeddings helper properties."""

    def test_has_dense_with_primary(self, sample_chunk):
        """Test has_dense returns True when primary dense embedding exists."""
        dense_info = EmbeddingBatchInfo.create_dense(
            batch_id=uuid7(),
            batch_index=0,
            chunk_id=sample_chunk.chunk_id,
            model="test-model",
            embeddings=[0.1, 0.2, 0.3],
            dimension=3,
            intent="primary",
        )

        embeddings = ChunkEmbeddings(chunk=sample_chunk).add(dense_info)

        assert embeddings.has_dense is True
        assert embeddings.has_sparse is False
        assert embeddings.is_complete is False  # Missing sparse

    def test_has_sparse_with_sparse(self, sample_chunk):
        """Test has_sparse returns True when sparse embedding exists."""
        sparse_emb = SparseEmbedding(indices=[1, 2], values=[0.8, 0.7])
        sparse_info = EmbeddingBatchInfo.create_sparse(
            batch_id=uuid7(),
            batch_index=0,
            chunk_id=sample_chunk.chunk_id,
            model="sparse-model",
            embeddings=sparse_emb,
            intent="sparse",
        )

        embeddings = ChunkEmbeddings(chunk=sample_chunk).add(sparse_info)

        assert embeddings.has_sparse is True
        assert embeddings.has_dense is False
        assert embeddings.is_complete is False  # Missing dense

    def test_is_complete_with_both(self, sample_chunk):
        """Test is_complete returns True when both dense and sparse exist."""
        dense_info = EmbeddingBatchInfo.create_dense(
            batch_id=uuid7(),
            batch_index=0,
            chunk_id=sample_chunk.chunk_id,
            model="dense-model",
            embeddings=[0.1] * 512,
            dimension=512,
            intent="primary",
        )

        sparse_emb = SparseEmbedding(indices=[1, 2, 3], values=[0.8, 0.7, 0.6])
        sparse_info = EmbeddingBatchInfo.create_sparse(
            batch_id=uuid7(),
            batch_index=0,
            chunk_id=sample_chunk.chunk_id,
            model="sparse-model",
            embeddings=sparse_emb,
            intent="sparse",
        )

        embeddings = ChunkEmbeddings(chunk=sample_chunk).add(dense_info).add(sparse_info)

        assert embeddings.has_dense is True
        assert embeddings.has_sparse is True
        assert embeddings.is_complete is True

    def test_has_dense_with_backup_only(self, sample_chunk):
        """Test has_dense returns True even with only backup dense embedding."""
        backup_info = EmbeddingBatchInfo.create_dense(
            batch_id=uuid7(),
            batch_index=0,
            chunk_id=sample_chunk.chunk_id,
            model="backup-model",
            embeddings=[0.1] * 256,
            dimension=256,
            intent="backup",
        )

        embeddings = ChunkEmbeddings(chunk=sample_chunk).add(backup_info)

        # has_dense should be True for ANY dense embedding
        assert embeddings.has_dense is True
        assert embeddings.has_sparse is False

    def test_has_dense_with_multiple_dense(self, sample_chunk):
        """Test has_dense with multiple dense embeddings (primary + backup)."""
        primary_info = EmbeddingBatchInfo.create_dense(
            batch_id=uuid7(),
            batch_index=0,
            chunk_id=sample_chunk.chunk_id,
            model="primary-model",
            embeddings=[0.1] * 512,
            dimension=512,
            intent="primary",
        )

        backup_info = EmbeddingBatchInfo.create_dense(
            batch_id=uuid7(),
            batch_index=0,
            chunk_id=sample_chunk.chunk_id,
            model="backup-model",
            embeddings=[0.2] * 256,
            dimension=256,
            intent="backup",
        )

        embeddings = ChunkEmbeddings(chunk=sample_chunk).add(primary_info).add(backup_info)

        assert embeddings.has_dense is True
        assert len([emb for emb in embeddings.embeddings.values() if emb.is_dense]) == 2

    def test_empty_embeddings(self, sample_chunk):
        """Test properties with no embeddings."""
        embeddings = ChunkEmbeddings(chunk=sample_chunk)

        assert embeddings.has_dense is False
        assert embeddings.has_sparse is False
        assert embeddings.is_complete is False

    def test_multiple_sparse_kinds(self, sample_chunk):
        """Test has_sparse with different sparse intents."""
        sparse1 = SparseEmbedding(indices=[1], values=[0.9])
        sparse_info1 = EmbeddingBatchInfo.create_sparse(
            batch_id=uuid7(),
            batch_index=0,
            chunk_id=sample_chunk.chunk_id,
            model="bm25",
            embeddings=sparse1,
            intent="sparse",
        )

        sparse2 = SparseEmbedding(indices=[2, 3], values=[0.8, 0.7])
        sparse_info2 = EmbeddingBatchInfo.create_sparse(
            batch_id=uuid7(),
            batch_index=0,
            chunk_id=sample_chunk.chunk_id,
            model="function-sig",
            embeddings=sparse2,
            intent="function_signatures",
        )

        embeddings = ChunkEmbeddings(chunk=sample_chunk).add(sparse_info1).add(sparse_info2)

        assert embeddings.has_sparse is True
        assert len([emb for emb in embeddings.embeddings.values() if emb.is_sparse]) == 2

    def test_is_complete_logic(self, sample_chunk):
        """Test that is_complete requires at least one dense AND one sparse."""
        dense_info = EmbeddingBatchInfo.create_dense(
            batch_id=uuid7(),
            batch_index=0,
            chunk_id=sample_chunk.chunk_id,
            model="model",
            embeddings=[0.1] * 512,
            dimension=512,
        )

        sparse_emb = SparseEmbedding(indices=[1], values=[0.9])
        sparse_info = EmbeddingBatchInfo.create_sparse(
            batch_id=uuid7(),
            batch_index=0,
            chunk_id=sample_chunk.chunk_id,
            model="sparse",
            embeddings=sparse_emb,
        )

        # Dense only - not complete
        embeddings_dense_only = ChunkEmbeddings(chunk=sample_chunk).add(dense_info)
        assert not embeddings_dense_only.is_complete

        # Sparse only - not complete
        embeddings_sparse_only = ChunkEmbeddings(chunk=sample_chunk).add(sparse_info)
        assert not embeddings_sparse_only.is_complete

        # Both - complete
        embeddings_both = ChunkEmbeddings(chunk=sample_chunk).add(dense_info).add(sparse_info)
        assert embeddings_both.is_complete
