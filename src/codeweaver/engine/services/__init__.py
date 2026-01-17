from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from codeweaver.core import create_lazy_getattr


if TYPE_CHECKING:
    from codeweaver.engine.services.chunking_service import ChunkingService
    from codeweaver.engine.services.failover_service import FailoverService
    from codeweaver.engine.services.indexing_service import IndexingService
