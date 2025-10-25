# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Tests for semantic chunker content deduplication per T009.

These tests validate hash-based deduplication, batch ID tracking, and UUIDStore
integration. All tests are expected to FAIL initially as the implementation is pending.
"""

from __future__ import annotations

import re

from pathlib import Path

import pytest

from codeweaver.engine.chunker.base import ChunkGovernor
from codeweaver.engine.chunker.semantic import SemanticChunker


@pytest.fixture
def chunk_governor() -> ChunkGovernor:
    """Create a ChunkGovernor instance for testing.

    Uses mock capabilities to provide chunk limits.
    """
    from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities

    # Create mock capability with test limits
    capabilities = (EmbeddingModelCapabilities(name="test-model", context_window=8192),)
    return ChunkGovernor(capabilities=capabilities)


@pytest.fixture
def semantic_chunker(chunk_governor: ChunkGovernor) -> SemanticChunker:
    """Create a SemanticChunker instance for testing."""
    from codeweaver.core.language import SemanticSearchLanguage

    return SemanticChunker(governor=chunk_governor, language=SemanticSearchLanguage.PYTHON)


@pytest.fixture
def python_file_with_duplicates(tmp_path: Path) -> Path:
    """Create a Python file with duplicate function definitions.

    Contains identical function code repeated multiple times to test
    hash-based deduplication.
    """
    file_path = tmp_path / "duplicates.py"
    content = '''
def calculate_sum(a: int, b: int) -> int:
    """Calculate the sum of two numbers."""
    return a + b

def calculate_difference(x: int, y: int) -> int:
    """Calculate the difference between two numbers."""
    return x - y

# Duplicate of calculate_sum - identical code
def calculate_sum(a: int, b: int) -> int:
    """Calculate the sum of two numbers."""
    return a + b

# Another duplicate of calculate_sum
def calculate_sum(a: int, b: int) -> int:
    """Calculate the sum of two numbers."""
    return a + b

def calculate_product(x: int, y: int) -> int:
    """Calculate the product of two numbers."""
    return x * y
'''
    file_path.write_text(content)
    return file_path


@pytest.fixture
def python_file_with_unique_functions(tmp_path: Path) -> Path:
    """Create a Python file with similar but different functions.

    All functions have similar structure but different content,
    ensuring no deduplication should occur.
    """
    file_path = tmp_path / "unique.py"
    content = '''
def calculate_sum(a: int, b: int) -> int:
    """Calculate the sum of two numbers."""
    return a + b

def calculate_difference(x: int, y: int) -> int:
    """Calculate the difference between two numbers."""
    return x - y

def calculate_product(m: int, n: int) -> int:
    """Calculate the product of two numbers."""
    return m * n

def calculate_quotient(numerator: int, denominator: int) -> float:
    """Calculate the quotient of two numbers."""
    if denominator == 0:
        raise ValueError("Cannot divide by zero")
    return numerator / denominator

def calculate_remainder(dividend: int, divisor: int) -> int:
    """Calculate the remainder of division."""
    if divisor == 0:
        raise ValueError("Cannot divide by zero")
    return dividend % divisor
'''
    file_path.write_text(content)
    return file_path


def test_duplicate_functions_deduplicated(
    semantic_chunker: SemanticChunker, python_file_with_duplicates: Path
) -> None:
    """Test that duplicate function definitions are deduplicated.

    Verifies:
    - Only one chunk created for duplicate content
    - Deduplication detected (fewer chunks than definitions)
    - Hash store tracks content hashes

    Expected to FAIL until SemanticChunker implements _deduplicate_chunks()
    and hash-based deduplication.
    """
    content = python_file_with_duplicates.read_text()

    # Chunk the file containing duplicates
    chunks = semantic_chunker.chunk(content, file_path=python_file_with_duplicates)

    # Count function definitions in original content
    function_count = len(re.findall(r"^def \w+\(", content, re.MULTILINE))

    # Assert deduplication occurred
    assert len(chunks) < function_count, (
        f"Expected deduplication: {len(chunks)} chunks from {function_count} functions"
    )

    # Verify we have unique function chunks only
    # Expected: calculate_sum (1), calculate_difference (1), calculate_product (1) = 3 chunks
    unique_function_names = {"calculate_sum", "calculate_difference", "calculate_product"}
    chunk_names = {chunk.metadata.get("name") for chunk in chunks if chunk.metadata}

    assert chunk_names == unique_function_names, (
        f"Expected {unique_function_names}, got {chunk_names}"
    )

    # Verify hash store is being used (check for _hash_store attribute)
    assert hasattr(SemanticChunker, "_hash_store"), (
        "SemanticChunker should have _hash_store class attribute for deduplication"
    )

    # Verify hash store contains content hashes
    # This assumes _hash_store is a BlakeStore[UUID7] that stores hash -> chunk_id mappings
    assert semantic_chunker._hash_store is not None, (
        "Hash store should be initialized for deduplication tracking"
    )


def test_unique_chunks_preserved(
    semantic_chunker: SemanticChunker, python_file_with_unique_functions: Path
) -> None:
    """Test that unique functions are all preserved.

    Verifies:
    - All unique chunks preserved (no false deduplication)
    - Number of chunks matches number of unique functions

    Expected to FAIL until SemanticChunker properly implements
    deduplication logic that only removes true duplicates.
    """
    content = python_file_with_unique_functions.read_text()

    # Chunk the file with all unique functions
    chunks = semantic_chunker.chunk(content, file_path=python_file_with_unique_functions)

    # Count function definitions in original content
    function_count = len(re.findall(r"^def \w+\(", content, re.MULTILINE))

    # Assert no deduplication occurred (all functions unique)
    assert len(chunks) == function_count, (
        f"Expected {function_count} unique chunks, got {len(chunks)}. "
        "All functions should be preserved as they are unique."
    )

    # Verify all expected function names are present
    expected_names = {
        "calculate_sum",
        "calculate_difference",
        "calculate_product",
        "calculate_quotient",
        "calculate_remainder",
    }
    chunk_names = {chunk.metadata.get("name") for chunk in chunks if chunk.metadata}

    assert chunk_names == expected_names, (
        f"Expected {expected_names}, got {chunk_names}. "
        "All unique functions should have corresponding chunks."
    )

    # Verify each chunk has unique content
    chunk_contents = [chunk.content for chunk in chunks]
    assert len(chunk_contents) == len(set(chunk_contents)), (
        "All chunks should have unique content (no duplicate content strings)"
    )


def test_batch_id_tracking(
    semantic_chunker: SemanticChunker, python_file_with_unique_functions: Path
) -> None:
    """Test batch ID assignment and tracking.

    Verifies:
    - All chunks in batch have same batch_id
    - batch_id is UUID7 format
    - Chunks retrievable from UUIDStore by batch

    Expected to FAIL until SemanticChunker implements batch ID generation
    and UUIDStore integration for batch tracking.
    """
    from pydantic import UUID7

    content = python_file_with_unique_functions.read_text()

    # Chunk the file
    chunks = semantic_chunker.chunk(content, file_path=python_file_with_unique_functions)

    # Verify all chunks have a batch ID
    assert all(chunk.embedding_batch_id is not None for chunk in chunks), (
        "All chunks should have an embedding_batch_id assigned"
    )

    # Verify all chunks share the same batch ID
    batch_ids = {chunk.embedding_batch_id for chunk in chunks}
    assert len(batch_ids) == 1, (
        f"Expected single batch_id for all chunks, got {len(batch_ids)}: {batch_ids}"
    )

    # Get the batch ID
    batch_id = chunks[0].embedding_batch_id

    # Verify it's a UUID7 instance
    assert isinstance(batch_id, UUID7), f"batch_id should be UUID7 instance, got {type(batch_id)}"

    # Verify batch_id follows UUID7 format (version 7 timestamp-based)
    # UUID7 has version bits set to 0111 (7) in the version field
    uuid_str = str(batch_id)
    version_digit = uuid_str[14]  # 15th character is the version digit
    assert version_digit == "7", (
        f"batch_id should be UUID7 format (version 7), got version {version_digit}"
    )

    # Verify chunks are stored in UUIDStore by batch
    # This assumes SemanticChunker has a class-level _store: UUIDStore[list[CodeChunk]]
    assert hasattr(SemanticChunker, "_store"), (
        "SemanticChunker should have _store class attribute (UUIDStore[list[CodeChunk]])"
    )

    # Verify batch is retrievable from store
    assert semantic_chunker._store is not None, "UUIDStore should be initialized for batch tracking"

    # Attempt to retrieve chunks by batch_id
    # This assumes _store.get(batch_id) returns the list of chunks for that batch
    stored_chunks = semantic_chunker._store.get(batch_id)

    assert stored_chunks is not None, (
        f"Chunks should be retrievable from UUIDStore by batch_id {batch_id}"
    )

    assert len(stored_chunks) == len(chunks), (
        f"Expected {len(chunks)} chunks in store, got {len(stored_chunks)}"
    )

    # Verify stored chunks match the chunked results
    stored_chunk_ids = {chunk.chunk_id for chunk in stored_chunks}
    result_chunk_ids = {chunk.chunk_id for chunk in chunks}

    assert stored_chunk_ids == result_chunk_ids, (
        "Chunks in UUIDStore should match the chunking results"
    )
