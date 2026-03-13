# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Shared fixtures and model setup for chunker performance benchmarks.

Two issues solved here:

1. ChunkGovernor and related models use forward references that must be resolved
   before instantiation. Perform the required model_rebuild() calls so that
   performance tests can directly construct ChunkGovernor without the
   PydanticUserError: `ChunkGovernor` is not fully defined error.

2. DiscoveredFile.__init__ takes `project_path: ResolvedProjectPathDep = INJECTED`.
   When tests create DiscoveredFile(path=Path("fake.py")) synchronously the DI
   container is not invoked — Python just uses the INJECTED proxy as the default
   value. The absolute_path property then crashes with:
       TypeError: unsupported operand type(s) for /: '_InjectedProxy' and 'PosixPath'
   because `_InjectedProxy.__bool__` returns True (so the proxy branch is taken)
   but `_InjectedProxy` does not implement __truediv__.

   Fix: wrap DiscoveredFile.__init__ at module import so that any test in this
   directory that passes no project_path (or passes the INJECTED proxy) gets
   Path.cwd() instead.  The wrapper is applied once at conftest import time so
   it covers the module-scoped `performance_selector` fixture too.
"""

from pathlib import Path

from codeweaver.core import CodeChunk, DelimiterPattern, EmbeddingBatchInfo, LanguageFamily
from codeweaver.core.di.dependency import INJECTED, _InjectedProxy
from codeweaver.core.discovery import DiscoveredFile
from codeweaver.engine import ChunkGovernor
from codeweaver.engine.config import ChunkerSettings


# ---------------------------------------------------------------------------
# 1. Model rebuild — forward references in ChunkGovernor / CodeChunk
# ---------------------------------------------------------------------------

# Build namespace for Pydantic to resolve string annotations
_namespace = {
    "DelimiterPattern": DelimiterPattern,
    "LanguageFamily": LanguageFamily,
    "ChunkerSettings": ChunkerSettings,
    "CodeChunk": CodeChunk,
}

# Ensure ChunkerSettings models are rebuilt first, then dependents
ChunkerSettings.model_rebuild()
ChunkGovernor.model_rebuild(_types_namespace=_namespace)
CodeChunk.model_rebuild(_types_namespace=_namespace)
EmbeddingBatchInfo.model_rebuild(_types_namespace=_namespace)


# ---------------------------------------------------------------------------
# 2. INJECTED proxy fix — wrap DiscoveredFile.__init__
# ---------------------------------------------------------------------------

_original_discovered_file_init = DiscoveredFile.__init__


def _patched_discovered_file_init(
    self: DiscoveredFile,
    path: Path,
    *args: object,
    project_path: object = INJECTED,
    **kwargs: object,
) -> None:
    """Replace the INJECTED sentinel with Path.cwd() for synchronous test construction.

    When DiscoveredFile is instantiated directly (not through the async DI container)
    with the default project_path=INJECTED, the _InjectedProxy is stored and later
    causes a TypeError in the absolute_path property.  Substituting Path.cwd() gives
    the test a real DirectoryPath so the rest of the chunker pipeline can run.
    """
    if project_path is INJECTED or isinstance(project_path, _InjectedProxy):
        project_path = Path.cwd()
    _original_discovered_file_init(self, path, *args, project_path=project_path, **kwargs)


DiscoveredFile.__init__ = _patched_discovered_file_init  # ty: ignore[method-assign]


# ---------------------------------------------------------------------------
# 3. Deduplication store reset fixture
# ---------------------------------------------------------------------------

from collections.abc import Generator

import pytest


@pytest.fixture(autouse=True)
def clear_semantic_deduplication_stores() -> Generator[None, None, None]:
    """Clear SemanticChunker class-level deduplication stores before each test.

    Performance benchmarks call chunk() multiple times with identical content to
    get timing statistics.  SemanticChunker._hash_store is class-level and persists
    across calls: after the first call every subsequent call with the same content
    returns an empty list (all hashes already seen = all duplicates).

    Clearing the store before each test gives each benchmark a clean slate while
    still allowing cross-iteration dedup *within* a single file-chunking operation.
    """
    from codeweaver.engine.chunker.semantic import SemanticChunker

    SemanticChunker.clear_deduplication_stores()
    yield
    # Clear after test too so other test modules aren't affected
    SemanticChunker.clear_deduplication_stores()
