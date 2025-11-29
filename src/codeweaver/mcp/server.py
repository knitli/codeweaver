"""FastMCP Server Creation and Lifespan Management for CodeWeaver."""

from __future__ import annotations

import logging

from collections.abc import Container
from typing import TYPE_CHECKING, Any

from fastmcp import FastMCP

from codeweaver.config.middleware import MiddlewareOptions
from codeweaver.core.types import DictView, Unset
from codeweaver.mcp.middleware import McpMiddleware


if TYPE_CHECKING:
    from codeweaver.config.types import FastMcpSettingsDict
    from codeweaver.middleware.statistics import StatisticsMiddleware


def _get_fastmcp_settings_map() -> DictView[FastMcpSettingsDict]:
    """Get the current settings."""
    from codeweaver.config.server_defaults import DefaultFastMcpServerSettings
    from codeweaver.config.settings import get_settings_map

    settings_map = get_settings_map()
    fastmcp_settings = settings_map.get("server") if settings_map.get("server") is not Unset else {}
    return DictView({**DefaultFastMcpServerSettings, **fastmcp_settings})


def _get_middleware_settings() -> MiddlewareOptions:
    """Get the current middleware settings."""
    from codeweaver.config.settings import get_settings_map

    settings_map = get_settings_map()
    return settings_map.get("middleware") if settings_map.get("middleware") is not Unset else {}


def _get_default_middleware() -> Container[type[McpMiddleware]]:
    """Get the default middleware for the application."""
    from codeweaver.mcp.middleware import default_middleware_for_transport

    fastmcp_settings = _get_fastmcp_settings_map()
    transport = fastmcp_settings.get("transport", "streamable-http")
    return default_middleware_for_transport(transport)


def get_statistics_middleware(settings: MiddlewareOptions) -> StatisticsMiddleware:
    """Get the statistics middleware instance."""
    from codeweaver.common.statistics import get_session_statistics
    from codeweaver.middleware.statistics import StatisticsMiddleware

    return StatisticsMiddleware(
        statistics=get_session_statistics(),
        logger=settings.get("logging", {}).get("logger", logging.getLogger(__name__)),
        log_level=settings.get("logging", {}).get("log_level", 30),
    )


def setup_middleware(
    middleware: Container[type[McpMiddleware]], middleware_settings: MiddlewareOptions
) -> set[McpMiddleware]:
    """Setup middleware for the application."""
    # Convert container to set for modification
    result: set[McpMiddleware] = set()

    # Apply middleware settings
    # ty gets very confused here, so we ignore most issues
    for mw in middleware:  # type: ignore
        mw: type[McpMiddleware]  # type: ignore
        match mw.__name__:  # type: ignore[reportUnknownMemberType, reportUnknownArgumentType, reportAttributeAccessIssue]
            case "ErrorHandlingMiddleware":
                instance = mw(**middleware_settings.get("error_handling", {}))  # type: ignore[reportCallIssue]
            case "RetryMiddleware":
                instance = mw(**middleware_settings.get("retry", {}))  # type: ignore[reportCallIssue]
            case "RateLimitingMiddleware":
                instance = mw(**middleware_settings.get("rate_limiting", {}))  # type: ignore[reportCallIssue]
            case "LoggingMiddleware" | "StructuredLoggingMiddleware":
                instance = mw(**middleware_settings.get("logging", {}))  # type: ignore[reportCallIssue]
            case "ResponseCachingMiddleware":
                instance = mw(**middleware_settings.get("caching", {}))  # type: ignore
            case _:
                if any_settings := middleware_settings.get(mw.__name__.lower()):  # type: ignore[reportUnknownMemberType, reportUnknownArgumentType, reportAttributeAccessIssue]
                    instance = mw(**any_settings)  # type: ignore[reportCallIssue, reportUnknownVariableType]
                else:
                    instance = mw()  # type: ignore[reportCallIssue, reportUnknownVariableType]
        result.add(instance)
    result.add(get_statistics_middleware(middleware_settings))
    return result


def register_middleware(
    app: FastMCP[Any],
    middleware: Container[type[McpMiddleware]],
    middleware_settings: MiddlewareOptions,
) -> FastMCP[Any]:
    """Register middleware with the application."""
    for mw in setup_middleware(middleware, middleware_settings):
        app = app.add_middleware(mw)
    return app


async def create_stdio_server() -> FastMCP[Any]:
    """Get a FastMCP server configured for stdio transport."""
    from codeweaver.config.middleware import default_for_transport

    middleware_opts = default_for_transport("stdio")
    fastmcp_settings = dict(_get_fastmcp_settings_map())
    middleware = fastmcp_settings.pop("middleware", [])
    middleware = sorted(
        (set(middleware) | set(default_for_transport("stdio"))), key=lambda x: x.__name__
    )
    for setting_key in {"host", "port", "auth"}:
        _ = fastmcp_settings.pop(setting_key, None)
    app = await FastMCP("CodeWeaver", **fastmcp_settings).run_stdio_async(
        show_banner=False, log_level="warning"
    )
    return register_middleware(app, middleware, middleware_opts)
