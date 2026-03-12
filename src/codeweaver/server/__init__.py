# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""CodeWeaver server package initialization."""

from __future__ import annotations

from types import MappingProxyType

# === MANAGED EXPORTS ===
# Exportify manages this section. It contains lazy-loading infrastructure
# for the package: imports and runtime declarations (__all__, __getattr__,
# __dir__). Manual edits will be overwritten by `exportify fix`.
from typing import TYPE_CHECKING

from lateimport import create_late_getattr


if TYPE_CHECKING:
    from codeweaver.server._assets import CODEWEAVER_SVG_ICON
    from codeweaver.server._logging import setup_logger
    from codeweaver.server.agent_api import get_user_agent
    from codeweaver.server.agent_api.search import CodeWeaverSettingsType, MatchedSection, find_code
    from codeweaver.server.agent_api.search.intent import (
        IntentResult,
        IntentType,
        QueryComplexity,
        QueryIntent,
    )
    from codeweaver.server.agent_api.search.types import (
        CodeMatch,
        CodeMatchType,
        FindCodeResponseSummary,
        FindCodeSubmission,
    )
    from codeweaver.server.background_services import run_background_indexing, start_watcher
    from codeweaver.server.config.helpers import get_settings, get_settings_map, update_settings
    from codeweaver.server.config.mcp import (
        CodeWeaverMCPConfig,
        MCPConfig,
        MCPServerConfig,
        StdioCodeWeaverConfig,
        update_mcp_config_file,
    )
    from codeweaver.server.config.middleware import (
        DefaultMiddlewareSettings,
        ErrorHandlingMiddlewareSettings,
        LoggingMiddlewareSettings,
        MiddlewareOptions,
        RateLimitingMiddlewareSettings,
        ResponseCachingMiddlewareSettings,
        RetryMiddlewareSettings,
    )
    from codeweaver.server.config.server_defaults import (
        DefaultEndpointSettings,
        DefaultFastMcpHttpRunArgs,
        DefaultFastMcpServerSettings,
        DefaultUvicornSettings,
        DefaultUvicornSettingsForMcp,
    )
    from codeweaver.server.config.settings import (
        BaseFastMcpServerSettings,
        CodeWeaverSettings,
        CodeWeaverSettingsDict,
        FastMcpHttpServerSettings,
        FastMcpStdioServerSettings,
    )
    from codeweaver.server.config.types import (
        CodeWeaverMCPConfigDict,
        EndpointSettingsDict,
        FastMcpHttpRunArgs,
        FastMcpServerSettingsDict,
        MCPConfigDict,
        StdioCodeWeaverConfigDict,
        UvicornServerSettings,
        UvicornServerSettingsDict,
    )
    from codeweaver.server.dependencies import (
        CodeWeaverStateDep,
        HealthServiceDep,
        ManagementServerDep,
    )
    from codeweaver.server.health.health_service import HealthService
    from codeweaver.server.health.models import (
        EmbeddingProviderServiceInfo,
        FailoverInfo,
        HealthResponse,
        IndexingInfo,
        IndexingProgressInfo,
        RerankingServiceInfo,
        ResourceInfo,
        ServicesInfo,
        SparseEmbeddingServiceInfo,
        StatisticsInfo,
        VectorStoreServiceInfo,
    )
    from codeweaver.server.lifespan import background_services_lifespan, http_lifespan
    from codeweaver.server.management import (
        ManagementServer,
        favicon,
        health,
        settings,
        settings_info,
        shutdown_handler,
        state_info,
        stats_info,
        status_info,
        version_info,
    )
    from codeweaver.server.mcp.middleware.fastmcp import (
        DetailedTimingMiddleware,
        ErrorHandlingMiddleware,
        LoggingMiddleware,
        McpMiddleware,
        RateLimitingMiddleware,
        ResponseCachingMiddleware,
        RetryMiddleware,
        StructuredLoggingMiddleware,
    )
    from codeweaver.server.mcp.middleware.statistics import StatisticsMiddleware
    from codeweaver.server.mcp.server import (
        StdioClientLifespan,
        create_http_server,
        create_stdio_server,
    )
    from codeweaver.server.mcp.state import CwMcpHttpState, FastMCPServerSettings
    from codeweaver.server.mcp.tools import (
        ContextAgentToolkit,
        ToolCollectionDict,
        get_bulk_tool,
        register_tool,
    )
    from codeweaver.server.mcp.types import ToolAnnotationsDict, ToolRegistrationDict
    from codeweaver.server.mcp.user_agent import find_code_tool
    from codeweaver.server.server import BRACKET_PATTERN, CodeWeaverState, lifespan

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "BRACKET_PATTERN": (__spec__.parent, "server"),
    "CODEWEAVER_SVG_ICON": (__spec__.parent, "_assets"),
    "BaseFastMcpServerSettings": (__spec__.parent, "config.settings"),
    "CodeMatch": (__spec__.parent, "agent_api.search.types"),
    "CodeMatchType": (__spec__.parent, "agent_api.search.types"),
    "CodeWeaverSettings": (__spec__.parent, "config.settings"),
    "CodeWeaverSettingsDict": (__spec__.parent, "config.settings"),
    "CodeWeaverSettingsType": (__spec__.parent, "agent_api.search"),
    "CodeWeaverState": (__spec__.parent, "server"),
    "CodeWeaverStateDep": (__spec__.parent, "dependencies"),
    "ContextAgentToolkit": (__spec__.parent, "mcp.tools"),
    "CwMcpHttpState": (__spec__.parent, "mcp.state"),
    "DefaultEndpointSettings": (__spec__.parent, "config.server_defaults"),
    "DefaultFastMcpHttpRunArgs": (__spec__.parent, "config.server_defaults"),
    "DefaultFastMcpServerSettings": (__spec__.parent, "config.server_defaults"),
    "DefaultMiddlewareSettings": (__spec__.parent, "config.middleware"),
    "DefaultUvicornSettings": (__spec__.parent, "config.server_defaults"),
    "DefaultUvicornSettingsForMcp": (__spec__.parent, "config.server_defaults"),
    "DetailedTimingMiddleware": (__spec__.parent, "mcp.middleware.fastmcp"),
    "EmbeddingProviderServiceInfo": (__spec__.parent, "health.models"),
    "EndpointSettingsDict": (__spec__.parent, "config.types"),
    "ErrorHandlingMiddleware": (__spec__.parent, "mcp.middleware.fastmcp"),
    "ErrorHandlingMiddlewareSettings": (__spec__.parent, "config.middleware"),
    "FailoverInfo": (__spec__.parent, "health.models"),
    "FastMcpHttpRunArgs": (__spec__.parent, "config.types"),
    "FastMcpHttpServerSettings": (__spec__.parent, "config.settings"),
    "FastMcpServerSettingsDict": (__spec__.parent, "config.types"),
    "FastMcpStdioServerSettings": (__spec__.parent, "config.settings"),
    "FindCodeResponseSummary": (__spec__.parent, "agent_api.search.types"),
    "FindCodeSubmission": (__spec__.parent, "agent_api.search.types"),
    "HealthResponse": (__spec__.parent, "health.models"),
    "HealthService": (__spec__.parent, "health.health_service"),
    "HealthServiceDep": (__spec__.parent, "dependencies"),
    "IndexingInfo": (__spec__.parent, "health.models"),
    "IndexingProgressInfo": (__spec__.parent, "health.models"),
    "IntentResult": (__spec__.parent, "agent_api.search.intent"),
    "IntentType": (__spec__.parent, "agent_api.search.intent"),
    "LoggingMiddleware": (__spec__.parent, "mcp.middleware.fastmcp"),
    "LoggingMiddlewareSettings": (__spec__.parent, "config.middleware"),
    "ManagementServer": (__spec__.parent, "management"),
    "ManagementServerDep": (__spec__.parent, "dependencies"),
    "MatchedSection": (__spec__.parent, "agent_api.search"),
    "McpMiddleware": (__spec__.parent, "mcp.middleware.fastmcp"),
    "MiddlewareOptions": (__spec__.parent, "config.middleware"),
    "QueryComplexity": (__spec__.parent, "agent_api.search.intent"),
    "QueryIntent": (__spec__.parent, "agent_api.search.intent"),
    "RateLimitingMiddleware": (__spec__.parent, "mcp.middleware.fastmcp"),
    "RateLimitingMiddlewareSettings": (__spec__.parent, "config.middleware"),
    "RerankingServiceInfo": (__spec__.parent, "health.models"),
    "ResourceInfo": (__spec__.parent, "health.models"),
    "ResponseCachingMiddleware": (__spec__.parent, "mcp.middleware.fastmcp"),
    "ResponseCachingMiddlewareSettings": (__spec__.parent, "config.middleware"),
    "RetryMiddleware": (__spec__.parent, "mcp.middleware.fastmcp"),
    "RetryMiddlewareSettings": (__spec__.parent, "config.middleware"),
    "ServicesInfo": (__spec__.parent, "health.models"),
    "SparseEmbeddingServiceInfo": (__spec__.parent, "health.models"),
    "StatisticsInfo": (__spec__.parent, "health.models"),
    "StatisticsMiddleware": (__spec__.parent, "mcp.middleware.statistics"),
    "StdioClientLifespan": (__spec__.parent, "mcp.server"),
    "StdioCodeWeaverConfig": (__spec__.parent, "config.mcp"),
    "StdioCodeWeaverConfigDict": (__spec__.parent, "config.types"),
    "StructuredLoggingMiddleware": (__spec__.parent, "mcp.middleware.fastmcp"),
    "ToolAnnotationsDict": (__spec__.parent, "mcp.types"),
    "ToolCollectionDict": (__spec__.parent, "mcp.tools"),
    "ToolRegistrationDict": (__spec__.parent, "mcp.types"),
    "UvicornServerSettings": (__spec__.parent, "config.types"),
    "UvicornServerSettingsDict": (__spec__.parent, "config.types"),
    "VectorStoreServiceInfo": (__spec__.parent, "health.models"),
    "background_services_lifespan": (__spec__.parent, "lifespan"),
    "CodeWeaverMCPConfig": (__spec__.parent, "config.mcp"),
    "CodeWeaverMCPConfigDict": (__spec__.parent, "config.types"),
    "create_http_server": (__spec__.parent, "mcp.server"),
    "create_stdio_server": (__spec__.parent, "mcp.server"),
    "FastMCPServerSettings": (__spec__.parent, "mcp.state"),
    "favicon": (__spec__.parent, "management"),
    "find_code": (__spec__.parent, "agent_api.search"),
    "find_code_tool": (__spec__.parent, "mcp.user_agent"),
    "get_bulk_tool": (__spec__.parent, "mcp.tools"),
    "get_settings": (__spec__.parent, "config.helpers"),
    "get_settings_map": (__spec__.parent, "config.helpers"),
    "get_user_agent": (__spec__.parent, "agent_api"),
    "health": (__spec__.parent, "management"),
    "http_lifespan": (__spec__.parent, "lifespan"),
    "lifespan": (__spec__.parent, "server"),
    "MCPConfig": (__spec__.parent, "config.mcp"),
    "MCPConfigDict": (__spec__.parent, "config.types"),
    "MCPServerConfig": (__spec__.parent, "config.mcp"),
    "register_tool": (__spec__.parent, "mcp.tools"),
    "run_background_indexing": (__spec__.parent, "background_services"),
    "settings": (__spec__.parent, "management"),
    "settings_info": (__spec__.parent, "management"),
    "setup_logger": (__spec__.parent, "_logging"),
    "shutdown_handler": (__spec__.parent, "management"),
    "start_watcher": (__spec__.parent, "background_services"),
    "state_info": (__spec__.parent, "management"),
    "stats_info": (__spec__.parent, "management"),
    "status_info": (__spec__.parent, "management"),
    "update_mcp_config_file": (__spec__.parent, "config.mcp"),
    "update_settings": (__spec__.parent, "config.helpers"),
    "version_info": (__spec__.parent, "management"),
})

__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    "BRACKET_PATTERN",
    "CODEWEAVER_SVG_ICON",
    "BaseFastMcpServerSettings",
    "CodeMatch",
    "CodeMatchType",
    "CodeWeaverMCPConfig",
    "CodeWeaverMCPConfigDict",
    "CodeWeaverSettings",
    "CodeWeaverSettingsDict",
    "CodeWeaverSettingsType",
    "CodeWeaverState",
    "CodeWeaverStateDep",
    "ContextAgentToolkit",
    "CwMcpHttpState",
    "DefaultEndpointSettings",
    "DefaultFastMcpHttpRunArgs",
    "DefaultFastMcpServerSettings",
    "DefaultMiddlewareSettings",
    "DefaultUvicornSettings",
    "DefaultUvicornSettingsForMcp",
    "DetailedTimingMiddleware",
    "EmbeddingProviderServiceInfo",
    "EndpointSettingsDict",
    "ErrorHandlingMiddleware",
    "ErrorHandlingMiddlewareSettings",
    "FailoverInfo",
    "FastMCPServerSettings",
    "FastMcpHttpRunArgs",
    "FastMcpHttpServerSettings",
    "FastMcpServerSettingsDict",
    "FastMcpStdioServerSettings",
    "FindCodeResponseSummary",
    "FindCodeSubmission",
    "HealthResponse",
    "HealthService",
    "HealthServiceDep",
    "IndexingInfo",
    "IndexingProgressInfo",
    "IntentResult",
    "IntentType",
    "LoggingMiddleware",
    "LoggingMiddlewareSettings",
    "MCPConfig",
    "MCPConfigDict",
    "MCPServerConfig",
    "ManagementServer",
    "ManagementServerDep",
    "MatchedSection",
    "McpMiddleware",
    "MiddlewareOptions",
    "QueryComplexity",
    "QueryIntent",
    "RateLimitingMiddleware",
    "RateLimitingMiddlewareSettings",
    "RerankingServiceInfo",
    "ResourceInfo",
    "ResponseCachingMiddleware",
    "ResponseCachingMiddlewareSettings",
    "RetryMiddleware",
    "RetryMiddlewareSettings",
    "ServicesInfo",
    "SparseEmbeddingServiceInfo",
    "StatisticsInfo",
    "StatisticsMiddleware",
    "StdioClientLifespan",
    "StdioCodeWeaverConfig",
    "StdioCodeWeaverConfigDict",
    "StructuredLoggingMiddleware",
    "ToolAnnotationsDict",
    "ToolCollectionDict",
    "ToolRegistrationDict",
    "UvicornServerSettings",
    "UvicornServerSettingsDict",
    "VectorStoreServiceInfo",
    "background_services_lifespan",
    "create_http_server",
    "create_stdio_server",
    "favicon",
    "find_code",
    "find_code_tool",
    "get_bulk_tool",
    "get_settings",
    "get_settings_map",
    "get_user_agent",
    "health",
    "http_lifespan",
    "lifespan",
    "register_tool",
    "run_background_indexing",
    "settings",
    "settings_info",
    "setup_logger",
    "shutdown_handler",
    "start_watcher",
    "state_info",
    "stats_info",
    "status_info",
    "update_mcp_config_file",
    "update_settings",
    "version_info",
)


def __dir__() -> list[str]:
    """List available attributes for the package."""
    return list(__all__)
