# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Tests for semantic chunker content deduplication per T009.

These tests validate hash-based deduplication, batch ID tracking, and UUIDStore
integration. All tests are expected to FAIL initially as the implementation is pending.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from codeweaver.engine import ChunkGovernor, SemanticChunker


pytestmark = [pytest.mark.unit]


@pytest.fixture
def chunk_governor() -> ChunkGovernor:
    """Create a ChunkGovernor instance for testing.

    Uses mock capabilities to provide chunk limits.
    """
    from codeweaver.providers import EmbeddingModelCapabilities

    # Create mock capability with test limits
    capabilities = (EmbeddingModelCapabilities(name="test-model", context_window=8192),)
    return ChunkGovernor(capabilities=capabilities)


@pytest.fixture(autouse=True)
def clear_semantic_chunker_stores():
    """Clear SemanticChunker class-level stores before each test for test isolation."""
    from codeweaver.engine import SemanticChunker

    # Clear the internal store dictionaries directly to avoid weak reference issues
    SemanticChunker._store.store.clear()
    SemanticChunker._hash_store.store.clear()
    yield
    # Clear after test as well
    SemanticChunker._store.store.clear()
    SemanticChunker._hash_store.store.clear()


@pytest.fixture
def semantic_chunker(chunk_governor: ChunkGovernor) -> SemanticChunker:
    """Create a SemanticChunker instance for testing."""
    from codeweaver.core import SemanticSearchLanguage

    return SemanticChunker(governor=chunk_governor, language=SemanticSearchLanguage.PYTHON)


@pytest.fixture
def python_file_with_duplicates(tmp_path: Path) -> Path:
    """Create a Python file with duplicate method content.

    Contains classes with identical methods to test hash-based deduplication.
    The methods have the same name, signature, and body - true duplicates.
    """
    file_path = tmp_path / "duplicates.py"
    content = '''
class MathOpsA:
    def add(self, a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

class MathOpsB:
    def add(self, a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

class MathOpsC:
    def add(self, a: int, b: int) -> int:
        """Add two numbers."""
        return a + b

class MathOpsD:
    def subtract(self, a: int, b: int) -> int:
        """Subtract two numbers."""
        return a - b

class MathOpsE:
    def multiply(self, a: int, b: int) -> int:
        """Multiply two numbers."""
        return a * b
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
    """Test that duplicate AST node content is deduplicated.

    The semantic chunker creates chunks for all semantically important AST nodes,
    not just top-level functions and classes. With 3 identical 'add' methods,
    duplicate identifiers like 'add', 'self', 'a', 'b' should be deduplicated.

    Verifies:
    - Deduplication is working (duplicate AST nodes removed)
    - Hash store tracks content hashes
    - Chunks have proper metadata including content_hash
    """
    content = python_file_with_duplicates.read_text()

    # Create DiscoveredFile and chunk the file containing duplicates
    from codeweaver.core import DiscoveredFile

    discovered_file = DiscoveredFile.from_path(python_file_with_duplicates)
    chunks = semantic_chunker.chunk(content, file=discovered_file)

    # The semantic chunker creates chunks for all AST nodes, not just functions/classes
    # With duplicate methods, we expect deduplication at the AST node level
    # Expected: ~40-50 chunks (all unique AST nodes across 5 classes/methods)
    # Without dedup, we'd have ~60+ chunks (3 duplicate methods * ~15 nodes each = ~45 extra)

    # Verify we get a reasonable number of chunks (semantic parsing creates many nodes)
    assert len(chunks) > 0, "Should create at least some chunks"
    assert len(chunks) < 100, f"Too many chunks created: {len(chunks)}"

    # Verify that all chunks have content hashes
    content_hashes = {
        chunk.metadata["context"]["content_hash"]
        for chunk in chunks
        if chunk.metadata and "context" in chunk.metadata
    }

    # All chunks should have content hashes
    assert len(content_hashes) == len(chunks), (
        f"Expected {len(chunks)} unique hashes, got {len(content_hashes)}"
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

    # Verify hash store has same number of entries as unique chunks
    assert len(semantic_chunker._hash_store.store) == len(chunks), (
        f"Hash store should have {len(chunks)} entries, got {len(semantic_chunker._hash_store.store)}"
    )

    # Verify deduplication is working by checking for duplicate identifiers
    # We have 3 identical 'add' methods, so 'add', 'self', 'a', 'b' should appear once
    identifier_chunks = [
        chunk
        for chunk in chunks
        if chunk.metadata
        and "semantic_meta" in chunk.metadata
        and hasattr(chunk.metadata["semantic_meta"], "thing")
        and chunk.metadata["semantic_meta"].thing.name == "identifier"
    ]

    # Get all identifier content
    identifier_contents = [chunk.content for chunk in identifier_chunks]

    # 'add' appears in 3 methods but should only create 1 chunk due to deduplication
    add_count = identifier_contents.count("add")
    assert add_count == 1, (
        f"Expected 'add' identifier to appear once (deduplicated), got {add_count}"
    )

    # 'self' appears in 3 methods but should only create 1 chunk due to deduplication
    self_count = identifier_contents.count("self")
    assert self_count == 1, (
        f"Expected 'self' identifier to appear once (deduplicated), got {self_count}"
    )


def test_unique_chunks_preserved(
    semantic_chunker: SemanticChunker, python_file_with_unique_functions: Path
) -> None:
    """Test that unique AST nodes are preserved without false deduplication.

    The semantic chunker creates chunks for all semantically important AST nodes.
    With 5 unique functions, all AST nodes should be unique and preserved.

    Verifies:
    - All unique AST node chunks preserved (no false deduplication)
    - All expected function names are present in the chunks
    - No duplicate content exists (all chunks have unique content)
    """
    content = python_file_with_unique_functions.read_text()

    # Create DiscoveredFile and chunk the file with all unique functions
    from codeweaver.core import DiscoveredFile

    discovered_file = DiscoveredFile.from_path(python_file_with_unique_functions)
    chunks = semantic_chunker.chunk(content, file=discovered_file)

    # The semantic chunker creates chunks for all AST nodes, not just functions
    # With 5 unique functions, we expect many unique AST node chunks
    assert len(chunks) > 0, "Should create at least some chunks"
    assert len(chunks) < 200, f"Too many chunks created: {len(chunks)}"

    # Verify all expected function names are present in function_definition chunks
    expected_names = {
        "calculate_sum",
        "calculate_difference",
        "calculate_product",
        "calculate_quotient",
        "calculate_remainder",
    }

    # Find all function_definition chunks
    function_chunks = [
        chunk
        for chunk in chunks
        if chunk.metadata
        and "semantic_meta" in chunk.metadata
        and hasattr(chunk.metadata["semantic_meta"], "thing")
        and chunk.metadata["semantic_meta"].thing.name == "function_definition"
    ]

    function_names = {chunk.metadata.get("name") for chunk in function_chunks if chunk.metadata}

    assert function_names == expected_names, (
        f"Expected {expected_names}, got {function_names}. "
        "All unique functions should have corresponding function_definition chunks."
    )

    # Verify each chunk has unique content (no false deduplication)
    chunk_contents = [chunk.content for chunk in chunks]
    assert len(chunk_contents) == len(set(chunk_contents)), (
        "All chunks should have unique content (no duplicate content strings)"
    )

    # Verify all chunks have unique content hashes
    content_hashes = [
        chunk.metadata.get("context", {}).get("content_hash")
        for chunk in chunks
        if chunk.metadata and "context" in chunk.metadata
    ]
    assert len(content_hashes) == len(set(content_hashes)), (
        "All chunks should have unique content hashes (no false deduplication)"
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
    from uuid import UUID

    content = python_file_with_unique_functions.read_text()

    # Create DiscoveredFile and chunk the file
    from codeweaver.core import DiscoveredFile

    discovered_file = DiscoveredFile.from_path(python_file_with_unique_functions)
    chunks = semantic_chunker.chunk(content, file=discovered_file)

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

    # Verify it's a UUID instance
    assert isinstance(batch_id, UUID), f"batch_id should be UUID instance, got {type(batch_id)}"

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
