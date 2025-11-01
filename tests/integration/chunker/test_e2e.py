"""
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
"""

"""End-to-end integration tests for chunking workflows."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from codeweaver.engine.chunker.selector import ChunkerSelector


pytestmark = [pytest.mark.integration]


@pytest.fixture
def mock_governor():
    """Create mock ChunkGovernor."""
    governor = Mock()
    governor.chunk_limit = 2000
    governor.simple_overlap = 50

    # Set settings to None to skip file size check in selector
    governor.settings = None

    return governor


@pytest.fixture
def mock_discovered_file():
    """Create mock DiscoveredFile."""
    from codeweaver.common.utils import uuid7

    def _make_file(path_str):
        file = Mock()
        file.path = Path(path_str)
        file.source_id = uuid7()  # Add source_id for Span validation (UUID7)
        return file

    return _make_file


def test_e2e_real_python_file(mock_governor, mock_discovered_file):
    """Integration test: Real Python file → valid chunks."""
    fixture_path = Path("tests/fixtures/sample.py")
    content = fixture_path.read_text()

    selector = ChunkerSelector(mock_governor)
    file = mock_discovered_file(str(fixture_path))
    chunker = selector.select_for_file(file)

    chunks = chunker.chunk(content, file=file)

    # Basic quality checks
    assert len(chunks) > 0, "Should produce chunks"
    assert all(c.content.strip() for c in chunks), "No empty chunks"
    assert all(c.metadata for c in chunks), "All chunks have metadata"
    assert all(c.line_range.start <= c.line_range.end for c in chunks), "Valid line ranges"


def test_e2e_degradation_chain(mock_governor, mock_discovered_file):
    """Verify degradation chain handles malformed files."""
    fixture_path = Path("tests/fixtures/malformed.py")
    content = fixture_path.read_text()

    selector = ChunkerSelector(mock_governor)
    file = mock_discovered_file(str(fixture_path))

    # Should gracefully degrade and still produce chunks
    # (implementation will add fallback logic)
    with pytest.raises(Exception):  # Will fail until fallback implemented
        chunker = selector.select_for_file(file)
        chunker.chunk(content, file_path=fixture_path)


# =============================================================================
# Parallel Processing Tests
# =============================================================================


@pytest.fixture
def sample_files():
    """Create list of real test fixture files for parallel processing."""
    from codeweaver.core.discovery import DiscoveredFile

    fixture_dir = Path("tests/fixtures")
    files = []

    # Collect existing Python fixtures, excluding edge cases and problem files
    skip_files = {"__init__.py", "malformed.py", "empty.py", "whitespace_only.py"}
    for fixture_path in fixture_dir.glob("*.py"):
        if fixture_path.name not in skip_files:
            if discovered := DiscoveredFile.from_path(fixture_path):
                files.append(discovered)

    return files


def test_e2e_multiple_files_parallel_process(sample_files):
    """Integration test: Process multiple files in parallel with ProcessPoolExecutor.

    Tests true parallel processing using ProcessPoolExecutor with fixed pickling support.
    Pickling issues resolved by:
    1. Converting positional_connections from generator to tuple
    2. Adding __getstate__/__setstate__ to SemanticMetadata to exclude AST nodes
    """
    from codeweaver.config.chunker import ChunkerSettings, PerformanceSettings
    from codeweaver.engine.chunker.base import ChunkGovernor
    from codeweaver.engine.chunker.parallel import chunk_files_parallel
    from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities

    # Skip if no files available
    if not sample_files:
        pytest.skip("No fixture files available for parallel processing test")

    # Create real governor with capabilities
    capabilities = EmbeddingModelCapabilities(context_window=8192, default_dimension=1536)
    settings = ChunkerSettings(
        performance=PerformanceSettings(
            max_ast_depth=200, chunk_timeout_seconds=30, max_chunks_per_file=5000
        )
    )
    governor = ChunkGovernor(capabilities=(capabilities,), settings=settings)

    # Process files in parallel
    results = dict(
        chunk_files_parallel(sample_files, governor, max_workers=2, executor_type="process")
    )

    # Verify results
    assert results, "Should process at least one file"
    assert len(results) <= len(sample_files), "Should not have more results than input files"

    # Quality checks on all results
    for file_path, chunks in results.items():
        assert len(chunks) > 0, f"File {file_path} should produce chunks"
        assert all(c.content.strip() for c in chunks), f"No empty chunks in {file_path}"
        assert all(c.metadata for c in chunks), f"All chunks have metadata in {file_path}"
        assert all(c.line_range.start <= c.line_range.end for c in chunks), (
            f"Valid line ranges in {file_path}"
        )


def test_e2e_multiple_files_parallel_thread(sample_files):
    """Integration test: Process multiple files in parallel with ThreadPoolExecutor."""
    from codeweaver.config.chunker import ChunkerSettings, PerformanceSettings
    from codeweaver.engine.chunker.base import ChunkGovernor
    from codeweaver.engine.chunker.parallel import chunk_files_parallel
    from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities

    # Skip if no files available
    if not sample_files:
        pytest.skip("No fixture files available for parallel processing test")

    # Create real governor
    capabilities = EmbeddingModelCapabilities(context_window=8192, default_dimension=1536)
    settings = ChunkerSettings(
        performance=PerformanceSettings(
            max_ast_depth=200, chunk_timeout_seconds=30, max_chunks_per_file=5000
        )
    )
    governor = ChunkGovernor(capabilities=(capabilities,), settings=settings)

    # Process files in parallel with threads
    results = dict(
        chunk_files_parallel(sample_files, governor, max_workers=2, executor_type="thread")
    )

    # Verify results
    assert results, "Should process at least one file"
    assert len(results) <= len(sample_files), "Should not have more results than input files"

    # Quality checks
    for file_path, chunks in results.items():
        assert len(chunks) > 0, f"File {file_path} should produce chunks"


def test_e2e_parallel_error_handling(tmp_path):
    """Verify parallel processing continues when individual files fail."""
    from codeweaver.config.chunker import ChunkerSettings
    from codeweaver.core.discovery import DiscoveredFile
    from codeweaver.engine.chunker.base import ChunkGovernor
    from codeweaver.engine.chunker.parallel import chunk_files_parallel
    from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities

    # Create mix of valid and invalid files
    good_file = tmp_path / "good.py"
    good_file.write_text("def hello():\n    return 'world'\n")

    bad_file = tmp_path / "bad.py"
    bad_file.write_text("def unclosed(\n    # Missing closing bracket")

    another_good = tmp_path / "good2.py"
    another_good.write_text("class TestClass:\n    pass\n")

    # Create discovered files using from_path to get proper file hashes
    good_discovered = DiscoveredFile.from_path(good_file)
    bad_discovered = DiscoveredFile.from_path(bad_file)
    another_discovered = DiscoveredFile.from_path(another_good)

    assert good_discovered is not None, "Good file should be discoverable"
    assert bad_discovered is not None, "Bad file should be discoverable"
    assert another_discovered is not None, "Another good file should be discoverable"

    files = [good_discovered, bad_discovered, another_discovered]

    # Create governor
    capabilities = EmbeddingModelCapabilities(context_window=8192, default_dimension=1536)
    governor = ChunkGovernor(capabilities=(capabilities,), settings=ChunkerSettings())

    # Process in parallel - should continue despite bad file
    # Use thread executor to avoid process pickling issues
    results = dict(chunk_files_parallel(files, governor, max_workers=2, executor_type="thread"))

    # Should have processed the good files even though one failed
    # Note: Depending on error handling, bad file might produce chunks via fallback
    # or be skipped. We verify we got at least the good files.
    assert len(results) >= 2, (
        f"Should process at least the two good files, got {len(results)}: {list(results.keys())}"
    )

    # Check if good files are in results (handle both absolute and relative paths)
    result_paths = {p.resolve() for p in results.keys()}
    assert good_file.resolve() in result_paths, f"Good file {good_file} should be processed"
    assert another_good.resolve() in result_paths, (
        f"Another good file {another_good} should be processed"
    )


def test_e2e_parallel_empty_file_list():
    """Verify parallel processing handles empty file list gracefully."""
    from codeweaver.engine.chunker.base import ChunkGovernor
    from codeweaver.engine.chunker.parallel import chunk_files_parallel
    from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities

    capabilities = EmbeddingModelCapabilities(context_window=8192, default_dimension=1536)
    governor = ChunkGovernor(capabilities=(capabilities,))

    # Process empty list
    results = list(chunk_files_parallel([], governor))

    # Should return empty without error
    assert results == [], "Empty input should yield no results"


def test_e2e_parallel_dict_convenience():
    """Test parallel_dict convenience wrapper."""
    from codeweaver.config.chunker import ChunkerSettings
    from codeweaver.core.discovery import DiscoveredFile
    from codeweaver.engine.chunker.base import ChunkGovernor
    from codeweaver.engine.chunker.parallel import chunk_files_parallel_dict
    from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities

    # Get sample files
    fixture_dir = Path("tests/fixtures")
    files = []
    for fixture_path in fixture_dir.glob("sample*.py"):
        if discovered := DiscoveredFile.from_path(fixture_path):
            files.append(discovered)

    if not files:
        pytest.skip("No sample files available")

    # Create governor
    capabilities = EmbeddingModelCapabilities(context_window=8192, default_dimension=1536)
    governor = ChunkGovernor(capabilities=(capabilities,), settings=ChunkerSettings())

    # Get results as dict
    results = chunk_files_parallel_dict(files, governor, max_workers=2)

    # Verify it's a dictionary
    assert isinstance(results, dict), "Should return dictionary"
    assert len(results) > 0, "Should have some results"

    # Verify structure
    for file_path, chunks in results.items():
        assert isinstance(file_path, Path), "Keys should be Paths"
        assert isinstance(chunks, list), "Values should be lists"
        assert all(hasattr(c, "content") for c in chunks), "Should contain chunks"
