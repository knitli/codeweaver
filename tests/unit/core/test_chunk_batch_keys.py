# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Tests for CodeChunk batch_keys functionality.

Validates that:
- set_batch_keys returns a new instance with batch keys set
- Original chunk remains unchanged (immutability)
- Metadata is not shared between instances
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from codeweaver.common.utils import uuid7
from codeweaver.core.chunks import BatchKeys, CodeChunk
from codeweaver.core.metadata import ChunkSource, ExtKind, Metadata
from codeweaver.core.spans import Span


@pytest.fixture
def sample_chunk() -> CodeChunk:
    """Create a sample CodeChunk for testing."""
    metadata: Metadata = {
        "chunk_id": uuid7(),
        "created_at": datetime.now(UTC).timestamp(),
        "name": "test_function",
    }

    return CodeChunk(
        content="def hello():\n    print('world')",
        file_path=Path("test.py"),
        line_range=Span(start=1, end=2, _source_id=uuid7()),
        ext_kind=ExtKind.from_file("test.py"),
        language="python",
        source=ChunkSource.SEMANTIC,
        metadata=metadata,
    )


def test_set_batch_keys_returns_new_instance(sample_chunk: CodeChunk) -> None:
    """Test that set_batch_keys returns a new CodeChunk instance."""
    batch_keys = BatchKeys(id=uuid7(), idx=0)
    updated_chunk = sample_chunk.set_batch_keys(batch_keys)

    # Should return a new instance
    assert updated_chunk is not sample_chunk

    # New instance should have batch keys
    assert updated_chunk._embedding_index is not None
    assert batch_keys == updated_chunk._embedding_index.primary_dense

    # Original should remain unchanged
    assert sample_chunk._embedding_index is None


def test_set_batch_keys_preserves_metadata(sample_chunk: CodeChunk) -> None:
    """Test that set_batch_keys preserves metadata correctly."""
    batch_keys = BatchKeys(id=uuid7(), idx=0)
    updated_chunk = sample_chunk.set_batch_keys(batch_keys)

    # Metadata should be preserved
    assert updated_chunk.metadata is not None
    assert updated_chunk.metadata["name"] == "test_function"

    # Metadata should not be the same dict instance (avoid shared references)
    assert updated_chunk.metadata is not sample_chunk.metadata


def test_set_batch_keys_does_not_duplicate(sample_chunk: CodeChunk) -> None:
    """Test that setting the same batch keys twice returns existing instance."""
    batch_keys = BatchKeys(id=uuid7(), idx=0)
    first_update = sample_chunk.set_batch_keys(batch_keys)
    second_update = first_update.set_batch_keys(batch_keys)

    # Should return same instance if batch keys already set
    assert first_update is second_update


def test_set_batch_keys_allows_multiple_batches(sample_chunk: CodeChunk) -> None:
    """Test that multiple different batch keys can be set."""
    batch_id = uuid7()
    batch_keys_1 = BatchKeys(id=batch_id, idx=0)
    batch_keys_2 = BatchKeys(id=batch_id, idx=1, sparse=True)

    updated_1 = sample_chunk.set_batch_keys(batch_keys_1)
    updated_2 = updated_1.set_batch_keys(batch_keys_2)

    # Should have both batch keys
    assert updated_2._embedding_index is not None
    assert batch_keys_1 == updated_2._embedding_index.primary_dense
    assert batch_keys_2 == updated_2._embedding_index.primary_sparse


def test_metadata_isolation_after_set_batch_keys(sample_chunk: CodeChunk) -> None:
    """Test that modifying metadata after set_batch_keys doesn't affect original."""
    batch_keys = BatchKeys(id=uuid7(), idx=0)
    updated_chunk = sample_chunk.set_batch_keys(batch_keys)

    # Modify the updated chunk's metadata
    if updated_chunk.metadata:
        updated_chunk.metadata["kind"] = "modified"

    # Original chunk's metadata should not have the modification
    assert sample_chunk.metadata is not None
    assert sample_chunk.metadata.get("kind") is None
