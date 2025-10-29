# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""CodeWeaver server package initialization."""

from codeweaver.server.health_endpoint import get_health
from codeweaver.server.health_models import (
    EmbeddingProviderServiceInfo,
    HealthResponse,
    IndexingInfo,
    IndexingProgressInfo,
    RerankerServiceInfo,
    ServicesInfo,
    SparseEmbeddingServiceInfo,
    StatisticsInfo,
    VectorStoreServiceInfo,
)
from codeweaver.server.health_service import HealthService
from codeweaver.server.server import (
    AppState,
    HealthInfo,
    HealthStatus,
    ServerSetup,
    build_app,
    get_health_info,
    get_state,
    lifespan,
)


__all__ = (
    "AppState",
    "EmbeddingProviderServiceInfo",
    "HealthInfo",
    "HealthResponse",
    "HealthService",
    "HealthStatus",
    "IndexingInfo",
    "IndexingProgressInfo",
    "RerankerServiceInfo",
    "ServerSetup",
    "ServicesInfo",
    "SparseEmbeddingServiceInfo",
    "StatisticsInfo",
    "VectorStoreServiceInfo",
    "build_app",
    "get_health",
    "get_health_info",
    "get_state",
    "lifespan",
)
