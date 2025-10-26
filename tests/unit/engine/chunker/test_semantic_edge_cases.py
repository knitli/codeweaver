# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Edge case tests for SemanticChunker."""

from pathlib import Path

import pytest

from codeweaver.core.language import SemanticSearchLanguage
from codeweaver.engine.chunker import SemanticChunker
from codeweaver.engine.chunker.base import ChunkGovernor
from codeweaver.engine.chunker.exceptions import BinaryFileError


def test_empty_file(chunk_governor: ChunkGovernor, discovered_empty_file) -> None:
    """Verify empty file returns empty list."""
    content = discovered_empty_file.contents

    chunker = SemanticChunker(chunk_governor, SemanticSearchLanguage.PYTHON)
    chunks = chunker.chunk(content, file=discovered_empty_file)

    assert len(chunks) == 0, "Empty file should return no chunks"


def test_whitespace_only_file(chunk_governor: ChunkGovernor, discovered_whitespace_only_file) -> None:
    """Verify whitespace-only file returns single chunk with edge_case metadata."""
    # Read raw content directly to preserve whitespace (DiscoveredFile.contents normalizes/strips)
    content = discovered_whitespace_only_file.path.read_text()

    chunker = SemanticChunker(chunk_governor, SemanticSearchLanguage.PYTHON)
    chunks = chunker.chunk(content, file=discovered_whitespace_only_file)

    assert len(chunks) == 1, "Whitespace-only file should return single chunk"
    assert chunks[0].metadata.get("edge_case") == "whitespace_only"


def test_single_line_file(chunk_governor: ChunkGovernor, discovered_single_line_file) -> None:
    """Verify single-line file returns single chunk with edge_case metadata."""
    content = discovered_single_line_file.contents

    chunker = SemanticChunker(chunk_governor, SemanticSearchLanguage.PYTHON)
    chunks = chunker.chunk(content, file=discovered_single_line_file)

    assert len(chunks) == 1, "Single-line file should return single chunk"
    assert chunks[0].metadata.get("edge_case") == "single_line"


def test_binary_file_detection(chunk_governor: ChunkGovernor, discovered_binary_mock_file) -> None:
    """Verify binary file detection raises BinaryFileError."""
    content = discovered_binary_mock_file.path.read_text(encoding="utf-8", errors="ignore")

    chunker = SemanticChunker(chunk_governor, SemanticSearchLanguage.PYTHON)

    with pytest.raises(BinaryFileError):
        _ = chunker.chunk(content, file=discovered_binary_mock_file)
