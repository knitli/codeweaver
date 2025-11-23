# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Tests for embedding metadata tracking in file manifest (v1.1.0)."""

import tempfile

from pathlib import Path

import pytest

from codeweaver.core.stores import get_blake_hash
from codeweaver.engine.indexer.manifest import FileManifestManager, IndexFileManifest


pytestmark = [pytest.mark.unit]


@pytest.fixture
def temp_project_dir():
    """Create a temporary project directory."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def manifest(temp_project_dir):
    """Create a manifest for testing."""
    return IndexFileManifest(project_path=temp_project_dir)


class TestEmbeddingMetadataTracking:
    """Tests for v1.1.0 embedding metadata features."""

    def test_add_file_with_dense_embedding_metadata(self, manifest):
        """Test adding file with dense embedding metadata."""
        path = Path("test.py")
        content_hash = get_blake_hash(b"test content")
        chunk_ids = ["chunk1", "chunk2"]
        
        manifest.add_file(
            path,
            content_hash,
            chunk_ids,
            dense_embedding_provider="openai",
            dense_embedding_model="text-embedding-3-large",
            has_dense_embeddings=True,
        )
        
        entry = manifest.get_file(path)
        assert entry is not None
        assert entry["dense_embedding_provider"] == "openai"
        assert entry["dense_embedding_model"] == "text-embedding-3-large"
        assert entry["has_dense_embeddings"] is True
        assert entry.get("has_sparse_embeddings") is False

    def test_add_file_with_sparse_embedding_metadata(self, manifest):
        """Test adding file with sparse embedding metadata."""
        path = Path("test.py")
        content_hash = get_blake_hash(b"test content")
        chunk_ids = ["chunk1"]
        
        manifest.add_file(
            path,
            content_hash,
            chunk_ids,
            sparse_embedding_provider="fastembed",
            sparse_embedding_model="bm25",
            has_sparse_embeddings=True,
        )
        
        entry = manifest.get_file(path)
        assert entry is not None
        assert entry["sparse_embedding_provider"] == "fastembed"
        assert entry["sparse_embedding_model"] == "bm25"
        assert entry["has_sparse_embeddings"] is True
        assert entry.get("has_dense_embeddings") is False

    def test_add_file_with_both_embedding_types(self, manifest):
        """Test adding file with both dense and sparse embeddings."""
        path = Path("test.py")
        content_hash = get_blake_hash(b"test content")
        chunk_ids = ["chunk1", "chunk2"]
        
        manifest.add_file(
            path,
            content_hash,
            chunk_ids,
            dense_embedding_provider="voyage",
            dense_embedding_model="voyage-code-2",
            sparse_embedding_provider="fastembed",
            sparse_embedding_model="bm42",
            has_dense_embeddings=True,
            has_sparse_embeddings=True,
        )
        
        entry = manifest.get_file(path)
        assert entry is not None
        assert entry["dense_embedding_provider"] == "voyage"
        assert entry["dense_embedding_model"] == "voyage-code-2"
        assert entry["sparse_embedding_provider"] == "fastembed"
        assert entry["sparse_embedding_model"] == "bm42"
        assert entry["has_dense_embeddings"] is True
        assert entry["has_sparse_embeddings"] is True

    def test_backward_compatibility_v1_0_0(self, manifest):
        """Test that v1.0.0 manifests without embedding metadata still work."""
        path = Path("legacy.py")
        content_hash = get_blake_hash(b"legacy content")
        chunk_ids = ["chunk1"]
        
        # Add file without embedding metadata (simulating v1.0.0 entry)
        manifest.add_file(path, content_hash, chunk_ids)
        
        entry = manifest.get_file(path)
        assert entry is not None
        assert entry["path"] == str(path)
        assert entry["content_hash"] == str(content_hash)
        # Optional fields should not raise KeyError
        assert entry.get("dense_embedding_provider") is None
        assert entry.get("has_dense_embeddings") is False


class TestModelChangeDetection:
    """Tests for embedding model change detection."""

    def test_file_needs_reindexing_new_file(self, manifest):
        """Test that new files need indexing."""
        path = Path("new_file.py")
        current_hash = get_blake_hash(b"new content")
        
        needs_reindex, reason = manifest.file_needs_reindexing(path, current_hash)
        
        assert needs_reindex is True
        assert reason == "new_file"

    def test_file_needs_reindexing_content_changed(self, manifest):
        """Test that files with changed content need reindexing."""
        path = Path("test.py")
        original_hash = get_blake_hash(b"original content")
        manifest.add_file(path, original_hash, ["chunk1"])
        
        new_hash = get_blake_hash(b"modified content")
        needs_reindex, reason = manifest.file_needs_reindexing(path, new_hash)
        
        assert needs_reindex is True
        assert reason == "content_changed"

    def test_file_needs_reindexing_dense_model_changed(self, manifest):
        """Test that dense model changes trigger reindexing."""
        path = Path("test.py")
        content_hash = get_blake_hash(b"test content")
        
        # Index with model A
        manifest.add_file(
            path,
            content_hash,
            ["chunk1"],
            dense_embedding_provider="openai",
            dense_embedding_model="text-embedding-ada-002",
            has_dense_embeddings=True,
        )
        
        # Check with different model
        needs_reindex, reason = manifest.file_needs_reindexing(
            path,
            content_hash,
            current_dense_provider="openai",
            current_dense_model="text-embedding-3-large",
        )
        
        assert needs_reindex is True
        assert reason == "dense_embedding_model_changed"

    def test_file_needs_reindexing_sparse_model_changed(self, manifest):
        """Test that sparse model changes trigger reindexing."""
        path = Path("test.py")
        content_hash = get_blake_hash(b"test content")
        
        # Index with sparse model A
        manifest.add_file(
            path,
            content_hash,
            ["chunk1"],
            sparse_embedding_provider="fastembed",
            sparse_embedding_model="bm25",
            has_sparse_embeddings=True,
        )
        
        # Check with different sparse model
        needs_reindex, reason = manifest.file_needs_reindexing(
            path,
            content_hash,
            current_sparse_provider="fastembed",
            current_sparse_model="bm42",
        )
        
        assert needs_reindex is True
        assert reason == "sparse_embedding_model_changed"

    def test_file_unchanged_same_models(self, manifest):
        """Test that files with same content and models don't need reindexing."""
        path = Path("test.py")
        content_hash = get_blake_hash(b"test content")
        
        manifest.add_file(
            path,
            content_hash,
            ["chunk1"],
            dense_embedding_provider="voyage",
            dense_embedding_model="voyage-code-2",
            has_dense_embeddings=True,
        )
        
        needs_reindex, reason = manifest.file_needs_reindexing(
            path,
            content_hash,
            current_dense_provider="voyage",
            current_dense_model="voyage-code-2",
        )
        
        assert needs_reindex is False
        assert reason == "unchanged"

    def test_file_unchanged_no_embeddings(self, manifest):
        """Test backward compatibility: files without embedding metadata."""
        path = Path("test.py")
        content_hash = get_blake_hash(b"test content")
        
        # Add file without embedding metadata (v1.0.0 style)
        manifest.add_file(path, content_hash, ["chunk1"])
        
        # Check with current models - should trigger reindex due to model mismatch
        needs_reindex, reason = manifest.file_needs_reindexing(
            path,
            content_hash,
            current_dense_provider="voyage",
            current_dense_model="voyage-code-2",
        )
        
        # Should need reindexing because manifest has no model info
        assert needs_reindex is True
        assert reason == "dense_embedding_model_changed"


class TestGetEmbeddingModelInfo:
    """Tests for retrieving embedding model information."""

    def test_get_embedding_model_info_with_metadata(self, manifest):
        """Test retrieving embedding model info for file with metadata."""
        path = Path("test.py")
        content_hash = get_blake_hash(b"test content")
        
        manifest.add_file(
            path,
            content_hash,
            ["chunk1"],
            dense_embedding_provider="openai",
            dense_embedding_model="text-embedding-3-large",
            sparse_embedding_provider="fastembed",
            sparse_embedding_model="bm25",
            has_dense_embeddings=True,
            has_sparse_embeddings=True,
        )
        
        info = manifest.get_embedding_model_info(path)
        
        assert info["dense_provider"] == "openai"
        assert info["dense_model"] == "text-embedding-3-large"
        assert info["sparse_provider"] == "fastembed"
        assert info["sparse_model"] == "bm25"
        assert info["has_dense"] is True
        assert info["has_sparse"] is True

    def test_get_embedding_model_info_nonexistent_file(self, manifest):
        """Test retrieving model info for nonexistent file."""
        path = Path("nonexistent.py")
        
        info = manifest.get_embedding_model_info(path)
        
        assert info == {}

    def test_get_embedding_model_info_legacy_file(self, manifest):
        """Test retrieving model info for legacy file without metadata."""
        path = Path("legacy.py")
        content_hash = get_blake_hash(b"legacy content")
        
        # Add file without embedding metadata
        manifest.add_file(path, content_hash, ["chunk1"])
        
        info = manifest.get_embedding_model_info(path)
        
        assert info["dense_provider"] is None
        assert info["dense_model"] is None
        assert info["sparse_provider"] is None
        assert info["sparse_model"] is None
        assert info["has_dense"] is False
        assert info["has_sparse"] is False


class TestManifestPersistence:
    """Tests for saving/loading manifests with embedding metadata."""

    def test_save_and_load_with_embedding_metadata(self, temp_project_dir):
        """Test that embedding metadata persists across save/load."""
        manager = FileManifestManager(project_path=temp_project_dir)
        manifest = manager.create_new()
        
        # Add file with embedding metadata
        path = Path("test.py")
        content_hash = get_blake_hash(b"test content")
        manifest.add_file(
            path,
            content_hash,
            ["chunk1", "chunk2"],
            dense_embedding_provider="voyage",
            dense_embedding_model="voyage-code-2",
            has_dense_embeddings=True,
        )
        
        # Save
        assert manager.save(manifest) is True
        
        # Load
        loaded_manifest = manager.load()
        assert loaded_manifest is not None
        assert loaded_manifest.manifest_version == "1.1.0"
        
        # Verify embedding metadata preserved
        entry = loaded_manifest.get_file(path)
        assert entry is not None
        assert entry["dense_embedding_provider"] == "voyage"
        assert entry["dense_embedding_model"] == "voyage-code-2"
        assert entry["has_dense_embeddings"] is True


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
