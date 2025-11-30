# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""CodeWeaver server package initialization."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from codeweaver.common.utils import create_lazy_getattr


if TYPE_CHECKING:
    from codeweaver.server.health_endpoint import get_health
    from codeweaver.server.health_models import (
        EmbeddingProviderServiceInfo,
        HealthResponse,
        IndexingInfo,
        IndexingProgressInfo,
        RerankingServiceInfo,
        ServicesInfo,
        SparseEmbeddingServiceInfo,
        StatisticsInfo,
        VectorStoreServiceInfo,
    )
    from codeweaver.server.health_service import HealthService
    from codeweaver.server.server import CodeWeaverState, build_app, get_state, lifespan


_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "CodeWeaverState": (__spec__.parent, "server"),
    "EmbeddingProviderServiceInfo": (__spec__.parent, "health_models"),
    "HealthResponse": (__spec__.parent, "health_models"),
    "HealthService": (__spec__.parent, "health_service"),
    "IndexingInfo": (__spec__.parent, "health_models"),
    "IndexingProgressInfo": (__spec__.parent, "health_models"),
    "RerankingServiceInfo": (__spec__.parent, "health_models"),
    "ServicesInfo": (__spec__.parent, "health_models"),
    "SparseEmbeddingServiceInfo": (__spec__.parent, "health_models"),
    "StatisticsInfo": (__spec__.parent, "health_models"),
    "VectorStoreServiceInfo": (__spec__.parent, "health_models"),
    "build_app": (__spec__.parent, "server"),
    "get_health": (__spec__.parent, "health_endpoint"),
    "get_state": (__spec__.parent, "server"),
    "lifespan": (__spec__.parent, "server"),
})

__getattr__ = create_lazy_getattr(_dynamic_imports, globals(), __name__)


__all__ = (
    "CodeWeaverState",
    "EmbeddingProviderServiceInfo",
    "HealthResponse",
    "HealthService",
    "IndexingInfo",
    "IndexingProgressInfo",
    "RerankingServiceInfo",
    "ServerSetup",
    "ServicesInfo",
    "SparseEmbeddingServiceInfo",
    "StatisticsInfo",
    "VectorStoreServiceInfo",
    "build_app",
    "get_health",
    "get_state",
    "lifespan",
)


def __dir__() -> list[str]:
    return list(__all__)
