"""Entry point for engine services package."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from codeweaver.core import create_lazy_getattr


if TYPE_CHECKING:
    from codeweaver.engine.services.chunking_service import ChunkingService
    from codeweaver.engine.services.failover_service import FailoverService
    from codeweaver.engine.services.indexing_service import IndexingService
    from codeweaver.engine.services.watching_service import FileWatchingService


_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "ChunkingService": (__spec__.parent, "ChunkingService"),
    "FailoverService": (__spec__.parent, "FailoverService"),
    "IndexingService": (__spec__.parent, "IndexingService"),
    "FileWatchingService": (__spec__.parent, "FileWatchingService"),
})

__getattr__ = create_lazy_getattr(_dynamic_imports, globals(), __name__)

__all__ = ("ChunkingService", "FailoverService", "FileWatchingService", "IndexingService")


def __dir__():
    """Return a list of all public objects of this module."""
    return list(__all__)
