# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Shared fixtures for chunker integration tests."""

from __future__ import annotations

from collections.abc import Generator

import pytest


@pytest.fixture(autouse=True)
def clear_semantic_chunker_state() -> Generator[None, None, None]:
    """Clear SemanticChunker class-level deduplication stores between tests.

    SemanticChunker uses class-level Blake3 hash stores to detect duplicate
    chunks across chunking sessions. Without clearing these between tests,
    a file chunked in one test will appear as 100% duplicates in subsequent
    tests that chunk the same file, producing 0 unique chunks.
    """
    from codeweaver.engine.chunker.semantic import SemanticChunker

    SemanticChunker.clear_deduplication_stores()
    yield
    SemanticChunker.clear_deduplication_stores()
