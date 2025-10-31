# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Shared test fixtures for chunker tests."""

from pathlib import Path
from unittest.mock import Mock

import pytest

from codeweaver.config.chunker import ChunkerSettings, PerformanceSettings
from codeweaver.core.chunks import CodeChunk
from codeweaver.engine.chunker.base import ChunkGovernor

# Rebuild models to resolve forward references
# This must happen after all imports to ensure all referenced types are available
# Import types needed for forward reference resolution
from codeweaver.engine.chunker.delimiters import DelimiterPattern, LanguageFamily
from codeweaver.engine.chunker.governance import ResourceGovernor
from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities
from codeweaver.providers.embedding.types import EmbeddingBatchInfo  # noqa: F401


# Build namespace for Pydantic to resolve string annotations
namespace = {
    "DelimiterPattern": DelimiterPattern,
    "LanguageFamily": LanguageFamily,
    "ChunkerSettings": ChunkerSettings,
    "CodeChunk": CodeChunk,
}
# Ensure ChunkerSettings models are rebuilt first
ChunkerSettings._ensure_models_rebuilt()
# Then rebuild ChunkGovernor and CodeChunk with full namespace
ChunkGovernor.model_rebuild(_types_namespace=namespace)
CodeChunk.model_rebuild(_types_namespace=namespace)


@pytest.fixture
def performance_settings() -> PerformanceSettings:
    """Create PerformanceSettings with test-friendly values."""
    return PerformanceSettings(
        max_file_size_mb=10,
        chunk_timeout_seconds=30,
        parse_timeout_seconds=10,
        max_chunks_per_file=5000,
        max_memory_mb_per_operation=100,
        max_ast_depth=200,
    )


@pytest.fixture
def chunker_settings(performance_settings: PerformanceSettings) -> ChunkerSettings:
    """Create ChunkerSettings with test configuration."""
    return ChunkerSettings(semantic_importance_threshold=0.2, performance=performance_settings)


@pytest.fixture
def mock_embedding_capability() -> EmbeddingModelCapabilities:
    """Create mock embedding capability with 2000 token context window."""
    capability = Mock(spec=EmbeddingModelCapabilities)
    capability.context_window = 2000
    capability.max_batch_size = 100
    return capability


@pytest.fixture
def chunk_governor(
    mock_embedding_capability: EmbeddingModelCapabilities, chunker_settings: ChunkerSettings
) -> ChunkGovernor:
    """Create properly configured ChunkGovernor for tests.

    This fixture provides a real ChunkGovernor instance with:
    - chunk_limit: 2000 tokens (from mock capability)
    - simple_overlap: 50-200 tokens (calculated as 20% of chunk_limit)
    - settings: Full ChunkerSettings hierarchy with PerformanceSettings
    """
    return ChunkGovernor(capabilities=(mock_embedding_capability,), settings=chunker_settings)


@pytest.fixture
def resource_governor(performance_settings: PerformanceSettings) -> ResourceGovernor:
    """Create ResourceGovernor for tests."""
    return ResourceGovernor(performance_settings)


@pytest.fixture
def fixture_path() -> Path:
    """Get base path for test fixtures."""
    return Path("tests/fixtures")


@pytest.fixture
def sample_python_file(fixture_path: Path) -> Path:
    """Get path to sample Python fixture."""
    return fixture_path / "sample.py"


@pytest.fixture
def sample_javascript_file(fixture_path: Path) -> Path:
    """Get path to sample JavaScript fixture."""
    return fixture_path / "sample.js"


@pytest.fixture
def sample_rust_file(fixture_path: Path) -> Path:
    """Get path to sample Rust fixture."""
    return fixture_path / "sample.rs"


@pytest.fixture
def sample_go_file(fixture_path: Path) -> Path:
    """Get path to sample Go fixture."""
    return fixture_path / "sample.go"


@pytest.fixture
def malformed_python_file(fixture_path: Path) -> Path:
    """Get path to malformed Python fixture."""
    return fixture_path / "malformed.py"


@pytest.fixture
def huge_function_file(fixture_path: Path) -> Path:
    """Get path to huge function fixture."""
    return fixture_path / "huge_function.py"


@pytest.fixture
def deep_nesting_file(fixture_path: Path) -> Path:
    """Get path to deep nesting fixture."""
    return fixture_path / "deep_nesting.py"


@pytest.fixture
def empty_file(fixture_path: Path) -> Path:
    """Get path to empty file fixture."""
    return fixture_path / "empty.py"


@pytest.fixture
def single_line_file(fixture_path: Path) -> Path:
    """Get path to single line fixture."""
    return fixture_path / "single_line.py"


@pytest.fixture
def whitespace_only_file(fixture_path: Path) -> Path:
    """Get path to whitespace only fixture."""
    return fixture_path / "whitespace_only.py"


@pytest.fixture
def binary_mock_file(fixture_path: Path) -> Path:
    """Get path to binary mock fixture."""
    return fixture_path / "binary_mock.txt"


@pytest.fixture
def large_class_file(fixture_path: Path) -> Path:
    """Get path to large class fixture."""
    return fixture_path / "large_class.py"


@pytest.fixture
def huge_string_literal_file(fixture_path: Path) -> Path:
    """Get path to huge string literal fixture."""
    return fixture_path / "huge_string_literal.py"


@pytest.fixture
def many_functions_file(fixture_path: Path) -> Path:
    """Get path to many functions fixture."""
    return fixture_path / "many_functions.py"


# DiscoveredFile fixtures (corresponding to Path fixtures above)


@pytest.fixture
def discovered_sample_python_file(sample_python_file: Path):
    """Create DiscoveredFile for sample Python fixture."""
    from codeweaver.core.discovery import DiscoveredFile

    return DiscoveredFile.from_path(sample_python_file)


@pytest.fixture
def discovered_sample_javascript_file(sample_javascript_file: Path):
    """Create DiscoveredFile for sample JavaScript fixture."""
    from codeweaver.core.discovery import DiscoveredFile

    return DiscoveredFile.from_path(sample_javascript_file)


@pytest.fixture
def discovered_sample_rust_file(sample_rust_file: Path):
    """Create DiscoveredFile for sample Rust fixture."""
    from codeweaver.core.discovery import DiscoveredFile

    return DiscoveredFile.from_path(sample_rust_file)


@pytest.fixture
def discovered_sample_go_file(sample_go_file: Path):
    """Create DiscoveredFile for sample Go fixture."""
    from codeweaver.core.discovery import DiscoveredFile

    return DiscoveredFile.from_path(sample_go_file)


@pytest.fixture
def discovered_malformed_python_file(malformed_python_file: Path):
    """Create DiscoveredFile for malformed Python fixture."""
    from codeweaver.core.discovery import DiscoveredFile

    return DiscoveredFile.from_path(malformed_python_file)


@pytest.fixture
def discovered_huge_function_file(huge_function_file: Path):
    """Create DiscoveredFile for huge function fixture."""
    from codeweaver.core.discovery import DiscoveredFile

    return DiscoveredFile.from_path(huge_function_file)


@pytest.fixture
def discovered_deep_nesting_file(deep_nesting_file: Path):
    """Create DiscoveredFile for deep nesting fixture."""
    from codeweaver.core.discovery import DiscoveredFile

    return DiscoveredFile.from_path(deep_nesting_file)


@pytest.fixture
def discovered_empty_file(empty_file: Path):
    """Create DiscoveredFile for empty file fixture."""
    from codeweaver.core.discovery import DiscoveredFile

    return DiscoveredFile.from_path(empty_file)


@pytest.fixture
def discovered_single_line_file(single_line_file: Path):
    """Create DiscoveredFile for single line fixture."""
    from codeweaver.core.discovery import DiscoveredFile

    return DiscoveredFile.from_path(single_line_file)


@pytest.fixture
def discovered_whitespace_only_file(whitespace_only_file: Path):
    """Create DiscoveredFile for whitespace only fixture."""
    from codeweaver.core.discovery import DiscoveredFile

    return DiscoveredFile.from_path(whitespace_only_file)


@pytest.fixture
def discovered_binary_mock_file(binary_mock_file: Path):
    """Create DiscoveredFile for binary mock fixture."""
    from codeweaver.core.discovery import DiscoveredFile

    return DiscoveredFile.from_path(binary_mock_file)


@pytest.fixture
def discovered_large_class_file(large_class_file: Path):
    """Create DiscoveredFile for large class fixture."""
    from codeweaver.core.discovery import DiscoveredFile

    return DiscoveredFile.from_path(large_class_file)


@pytest.fixture
def discovered_huge_string_literal_file(huge_string_literal_file: Path):
    """Create DiscoveredFile for huge string literal fixture."""
    from codeweaver.core.discovery import DiscoveredFile

    return DiscoveredFile.from_path(huge_string_literal_file)


@pytest.fixture
def discovered_many_functions_file(many_functions_file: Path):
    """Create DiscoveredFile for many functions fixture."""
    from codeweaver.core.discovery import DiscoveredFile

    return DiscoveredFile.from_path(many_functions_file)
