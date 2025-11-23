# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Tests for manifest vector store validation and selective reindexing."""

from pathlib import Path

import pytest

from codeweaver.core.stores import get_blake_hash
from codeweaver.engine.indexer.manifest import IndexFileManifest


pytestmark = [pytest.mark.unit]


class TestManifestVectorStoreValidation:
    """Test vector store validation functionality."""

    def test_get_all_chunk_ids(self, tmp_path: Path) -> None:
        """Test getting all chunk IDs from manifest."""
        manifest = IndexFileManifest(project_path=tmp_path)

        # Add files with chunks
        manifest.add_file(
            path=Path("file1.py"),
            content_hash=get_blake_hash("content1"),
            chunk_ids=["chunk-1", "chunk-2", "chunk-3"],
        )
        manifest.add_file(
            path=Path("file2.py"),
            content_hash=get_blake_hash("content2"),
            chunk_ids=["chunk-4", "chunk-5"],
        )

        # Get all chunk IDs
        all_chunk_ids = manifest.get_all_chunk_ids()

        assert len(all_chunk_ids) == 5
        assert "chunk-1" in all_chunk_ids
        assert "chunk-2" in all_chunk_ids
        assert "chunk-3" in all_chunk_ids
        assert "chunk-4" in all_chunk_ids
        assert "chunk-5" in all_chunk_ids

    def test_get_all_chunk_ids_empty(self, tmp_path: Path) -> None:
        """Test getting chunk IDs from empty manifest."""
        manifest = IndexFileManifest(project_path=tmp_path)
        all_chunk_ids = manifest.get_all_chunk_ids()
        assert len(all_chunk_ids) == 0

    def test_get_files_by_embedding_config_dense_only(self, tmp_path: Path) -> None:
        """Test filtering files by dense embedding configuration."""
        manifest = IndexFileManifest(project_path=tmp_path)

        # Add file with only dense embeddings
        manifest.add_file(
            path=Path("dense_only.py"),
            content_hash=get_blake_hash("content1"),
            chunk_ids=["chunk-1"],
            has_dense_embeddings=True,
            has_sparse_embeddings=False,
        )

        # Add file with both
        manifest.add_file(
            path=Path("both.py"),
            content_hash=get_blake_hash("content2"),
            chunk_ids=["chunk-2"],
            has_dense_embeddings=True,
            has_sparse_embeddings=True,
        )

        # Add file with neither
        manifest.add_file(
            path=Path("neither.py"),
            content_hash=get_blake_hash("content3"),
            chunk_ids=["chunk-3"],
            has_dense_embeddings=False,
            has_sparse_embeddings=False,
        )

        # Get files with dense embeddings
        files_with_dense = manifest.get_files_by_embedding_config(has_dense=True)
        assert len(files_with_dense) == 2
        assert Path("dense_only.py") in files_with_dense
        assert Path("both.py") in files_with_dense

        # Get files without dense embeddings
        files_without_dense = manifest.get_files_by_embedding_config(has_dense=False)
        assert len(files_without_dense) == 1
        assert Path("neither.py") in files_without_dense

    def test_get_files_by_embedding_config_sparse_only(self, tmp_path: Path) -> None:
        """Test filtering files by sparse embedding configuration."""
        manifest = IndexFileManifest(project_path=tmp_path)

        # Add file with only sparse embeddings
        manifest.add_file(
            path=Path("sparse_only.py"),
            content_hash=get_blake_hash("content1"),
            chunk_ids=["chunk-1"],
            has_dense_embeddings=False,
            has_sparse_embeddings=True,
        )

        # Add file with both
        manifest.add_file(
            path=Path("both.py"),
            content_hash=get_blake_hash("content2"),
            chunk_ids=["chunk-2"],
            has_dense_embeddings=True,
            has_sparse_embeddings=True,
        )

        # Get files with sparse embeddings
        files_with_sparse = manifest.get_files_by_embedding_config(has_sparse=True)
        assert len(files_with_sparse) == 2
        assert Path("sparse_only.py") in files_with_sparse
        assert Path("both.py") in files_with_sparse

    def test_get_files_by_embedding_config_both(self, tmp_path: Path) -> None:
        """Test filtering files by both dense and sparse configuration."""
        manifest = IndexFileManifest(project_path=tmp_path)

        # Add various files
        manifest.add_file(
            path=Path("dense_only.py"),
            content_hash=get_blake_hash("content1"),
            chunk_ids=["chunk-1"],
            has_dense_embeddings=True,
            has_sparse_embeddings=False,
        )
        manifest.add_file(
            path=Path("sparse_only.py"),
            content_hash=get_blake_hash("content2"),
            chunk_ids=["chunk-2"],
            has_dense_embeddings=False,
            has_sparse_embeddings=True,
        )
        manifest.add_file(
            path=Path("both.py"),
            content_hash=get_blake_hash("content3"),
            chunk_ids=["chunk-3"],
            has_dense_embeddings=True,
            has_sparse_embeddings=True,
        )

        # Get files with both embeddings
        files_with_both = manifest.get_files_by_embedding_config(has_dense=True, has_sparse=True)
        assert len(files_with_both) == 1
        assert Path("both.py") in files_with_both


class TestSelectiveReindexing:
    """Test selective reindexing functionality."""

    def test_get_files_needing_dense_embeddings(self, tmp_path: Path) -> None:
        """Test finding files that need dense embeddings added."""
        manifest = IndexFileManifest(project_path=tmp_path)

        # Add file without dense embeddings
        manifest.add_file(
            path=Path("needs_dense.py"),
            content_hash=get_blake_hash("content1"),
            chunk_ids=["chunk-1"],
            has_dense_embeddings=False,
            has_sparse_embeddings=True,
        )

        # Add file with dense embeddings
        manifest.add_file(
            path=Path("has_dense.py"),
            content_hash=get_blake_hash("content2"),
            chunk_ids=["chunk-2"],
            has_dense_embeddings=True,
            has_sparse_embeddings=False,
        )

        # Find files needing dense embeddings
        files_needing = manifest.get_files_needing_embeddings(
            current_dense_provider="openai", current_dense_model="text-embedding-3-large"
        )

        assert len(files_needing["dense_only"]) == 1
        assert Path("needs_dense.py") in files_needing["dense_only"]
        assert len(files_needing["sparse_only"]) == 0

    def test_get_files_needing_sparse_embeddings(self, tmp_path: Path) -> None:
        """Test finding files that need sparse embeddings added."""
        manifest = IndexFileManifest(project_path=tmp_path)

        # Add file without sparse embeddings
        manifest.add_file(
            path=Path("needs_sparse.py"),
            content_hash=get_blake_hash("content1"),
            chunk_ids=["chunk-1"],
            has_dense_embeddings=True,
            has_sparse_embeddings=False,
        )

        # Add file with sparse embeddings
        manifest.add_file(
            path=Path("has_sparse.py"),
            content_hash=get_blake_hash("content2"),
            chunk_ids=["chunk-2"],
            has_dense_embeddings=False,
            has_sparse_embeddings=True,
        )

        # Find files needing sparse embeddings
        files_needing = manifest.get_files_needing_embeddings(
            current_sparse_provider="fastembed", current_sparse_model="prithivida/Splade_PP_en_v1"
        )

        assert len(files_needing["sparse_only"]) == 1
        assert Path("needs_sparse.py") in files_needing["sparse_only"]
        assert len(files_needing["dense_only"]) == 0

    def test_get_files_needing_embeddings_no_provider(self, tmp_path: Path) -> None:
        """Test that files are not flagged when no provider is configured."""
        manifest = IndexFileManifest(project_path=tmp_path)

        # Add file without embeddings
        manifest.add_file(
            path=Path("no_embeddings.py"),
            content_hash=get_blake_hash("content1"),
            chunk_ids=["chunk-1"],
            has_dense_embeddings=False,
            has_sparse_embeddings=False,
        )

        # No providers configured - should return empty
        files_needing = manifest.get_files_needing_embeddings()

        assert len(files_needing["dense_only"]) == 0
        assert len(files_needing["sparse_only"]) == 0

    def test_get_files_needing_embeddings_all_complete(self, tmp_path: Path) -> None:
        """Test when all files have required embeddings."""
        manifest = IndexFileManifest(project_path=tmp_path)

        # Add file with all embeddings
        manifest.add_file(
            path=Path("complete.py"),
            content_hash=get_blake_hash("content1"),
            chunk_ids=["chunk-1"],
            dense_embedding_provider="openai",
            dense_embedding_model="text-embedding-3-large",
            sparse_embedding_provider="fastembed",
            sparse_embedding_model="prithivida/Splade_PP_en_v1",
            has_dense_embeddings=True,
            has_sparse_embeddings=True,
        )

        # Should return empty
        files_needing = manifest.get_files_needing_embeddings(
            current_dense_provider="openai",
            current_dense_model="text-embedding-3-large",
            current_sparse_provider="fastembed",
            current_sparse_model="prithivida/Splade_PP_en_v1",
        )

        assert len(files_needing["dense_only"]) == 0
        assert len(files_needing["sparse_only"]) == 0

    def test_priority_dense_over_sparse(self, tmp_path: Path) -> None:
        """Test that dense embeddings take priority in categorization."""
        manifest = IndexFileManifest(project_path=tmp_path)

        # Add file needing both dense and sparse
        manifest.add_file(
            path=Path("needs_both.py"),
            content_hash=get_blake_hash("content1"),
            chunk_ids=["chunk-1"],
            has_dense_embeddings=False,
            has_sparse_embeddings=False,
        )

        files_needing = manifest.get_files_needing_embeddings(
            current_dense_provider="openai",
            current_dense_model="text-embedding-3-large",
            current_sparse_provider="fastembed",
            current_sparse_model="prithivida/Splade_PP_en_v1",
        )

        # File should appear in dense_only (processed first)
        assert len(files_needing["dense_only"]) == 1
        assert Path("needs_both.py") in files_needing["dense_only"]
        # Should not appear in sparse_only due to continue statement
        assert len(files_needing["sparse_only"]) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
