"""FastMCP Server Creation and Lifespan Management for CodeWeaver."""

from __future__ import annotations

import logging

from collections.abc import AsyncIterator, Container
from typing import TYPE_CHECKING, Any, cast

from fastmcp import FastMCP
from fastmcp.client.transports import StreamableHttpTransport
from fastmcp.server.proxy import FastMCPProxy, ProxyClient
from fastmcp.tools import Tool

from codeweaver.common.utils import lazy_import
from codeweaver.config.middleware import DefaultMiddlewareSettings, MiddlewareOptions
from codeweaver.config.settings import FastMcpHttpServerSettings, FastMcpStdioServerSettings
from codeweaver.core.types import DictView, Unset
from codeweaver.mcp.state import CwMcpHttpState


if TYPE_CHECKING:
    from codeweaver.config.types import FastMcpServerSettingsDict
    from codeweaver.mcp.middleware import McpMiddleware, StatisticsMiddleware

TOOLS_TO_REGISTER = ("find_code",)

type StdioClientLifespan = AsyncIterator[Any]


def _get_fastmcp_settings_map(*, http: bool = False) -> DictView[FastMcpServerSettingsDict]:
    """Get the current settings."""
    from codeweaver.config.settings import get_settings_map

    settings_map = get_settings_map()
    if http:
        return (
            settings_map.get_subview("mcp_server")
            if settings_map.get("mcp_server") is not Unset
            else DictView(FastMcpServerSettingsDict(**FastMcpHttpServerSettings().as_settings()))
        )
    return (
        settings_map.get_subview("stdio_server")
        if settings_map.get("stdio_server") is not Unset
        else DictView(FastMcpServerSettingsDict(**FastMcpStdioServerSettings().as_settings()))
    )


def _get_middleware_settings() -> DictView[MiddlewareOptions]:
    """Get the current middleware settings."""
    from codeweaver.config.settings import get_settings_map

    settings_map = get_settings_map()
    return (
        settings_map.get_subview("middleware")
        if settings_map.get("middleware") is not Unset
        else DictView(DefaultMiddlewareSettings)
    )  # type: ignore[arg-type]


def _get_default_middleware() -> Container[type[McpMiddleware]]:
    """Get the default middleware for the application."""
    from codeweaver.mcp.middleware import default_middleware_for_transport

    fastmcp_settings = _get_fastmcp_settings_map()
    transport = fastmcp_settings.get("transport", "streamable-http")
    return default_middleware_for_transport(transport)


def get_statistics_middleware(settings: MiddlewareOptions) -> StatisticsMiddleware:
    """Get the statistics middleware instance."""
    from codeweaver.common.statistics import get_session_statistics
    from codeweaver.mcp.middleware.statistics import StatisticsMiddleware

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
    app: FastMCP[StdioClientLifespan] | FastMCP[CwMcpHttpState],
    middleware: Container[type[McpMiddleware]],
    middleware_settings: MiddlewareOptions,
) -> FastMCP[StdioClientLifespan] | FastMCP[CwMcpHttpState]:
    """Register middleware with the application."""
    for mw in setup_middleware(middleware, middleware_settings):
        _ = app.add_middleware(mw)
    return app


def register_tools(
    app: FastMCP[StdioClientLifespan] | FastMCP[CwMcpHttpState],
) -> FastMCP[StdioClientLifespan] | FastMCP[CwMcpHttpState]:
    """Register tools with the application."""
    from codeweaver.mcp.tools import TOOL_DEFINITIONS, register_tool

    for tool_name in TOOLS_TO_REGISTER:
        if tool_name not in TOOL_DEFINITIONS:
            continue
        app = register_tool(
            app,
            tool if (tool := TOOL_DEFINITIONS[tool_name]) and isinstance(tool, Tool) else tool(app),
        )
    return app


def _setup_server(
    args: DictView[FastMcpServerSettingsDict],
) -> FastMCP[StdioClientLifespan] | FastMCP[CwMcpHttpState]:
    """Set class args for FastMCP server settings."""
    from codeweaver.config.middleware import default_for_transport

    is_http = bool(args.get("run_args"))
    # `run_args` is only set for HTTP transport
    middleware_opts = default_for_transport("streamable-http" if is_http else "stdio")
    mutable_args = dict(args)
    middleware = mutable_args.pop("middleware", [])
    app = FastMCP(
        "CodeWeaver",
        **(
            mutable_args
            | {"icons": [lazy_import("codeweaver.server._assets", "CODEWEAVER_SVG_ICON")]}
        ),  # ty: ignore[invalid-argument-type]
    )
    app = register_tools(app)
    return register_middleware(app, cast(list[type[McpMiddleware]], middleware), middleware_opts)


# Note: FastMCP's parameterized type is the server's lifespan. For stdio servers, the client manages lifespan, so we use AsyncIterator[Any] aliased as StdioClientLifespan.
async def create_stdio_server() -> FastMCPProxy:
    """Get a FastMCP server configured for stdio transport."""
    stdio_settings = _get_fastmcp_settings_map(http=False)
    app = _setup_server(stdio_settings)
    http_settings = _get_fastmcp_settings_map(http=True)
    url = f"http://{http_settings['run_args']['host']}:{http_settings['run_args']['port']}{http_settings.get('path', '/mcp/')}"
    return app.as_proxy(backend=ProxyClient(transport=StreamableHttpTransport(url=url)))
