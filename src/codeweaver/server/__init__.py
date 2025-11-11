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
    from codeweaver.server.app_bindings import find_code_tool, register_app_bindings, register_tool
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
    from codeweaver.server.server import (
        AppState,
        HealthInfo,
        ServerSetup,
        build_app,
        get_health_info,
        get_state,
        lifespan,
    )


_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "AppState": (__spec__.parent, "server"),
    "EmbeddingProviderServiceInfo": (__spec__.parent, "health_models"),
    "HealthInfo": (__spec__.parent, "server"),
    "HealthResponse": (__spec__.parent, "health_models"),
    "HealthService": (__spec__.parent, "health_service"),
    "IndexingInfo": (__spec__.parent, "health_models"),
    "IndexingProgressInfo": (__spec__.parent, "health_models"),
    "RerankingServiceInfo": (__spec__.parent, "health_models"),
    "ServerSetup": (__spec__.parent, "server"),
    "ServicesInfo": (__spec__.parent, "health_models"),
    "SparseEmbeddingServiceInfo": (__spec__.parent, "health_models"),
    "StatisticsInfo": (__spec__.parent, "health_models"),
    "VectorStoreServiceInfo": (__spec__.parent, "health_models"),
    "build_app": (__spec__.parent, "server"),
    "find_code_tool": (__spec__.parent, "app_bindings"),
    "get_health": (__spec__.parent, "health_endpoint"),
    "get_health_info": (__spec__.parent, "server"),
    "get_state": (__spec__.parent, "server"),
    "lifespan": (__spec__.parent, "server"),
    "register_app_bindings": (__spec__.parent, "app_bindings"),
    "register_tool": (__spec__.parent, "app_bindings"),
})

__getattr__ = create_lazy_getattr(_dynamic_imports, globals(), __name__)


__all__ = (
    "AppState",
    "EmbeddingProviderServiceInfo",
    "HealthInfo",
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
    "find_code_tool",
    "get_health",
    "get_health_info",
    "get_state",
    "lifespan",
    "register_app_bindings",
    "register_tool",
)


def __dir__() -> list[str]:
    return list(__all__)
