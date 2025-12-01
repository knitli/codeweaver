# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""FastMCP Server Creation and Lifespan Management for CodeWeaver.

This module handles the setup, configuration, and instantiation of FastMCP servers. **It does not *start* the servers;** instead, it provides factory functions to create server instances configured for either HTTP or stdio transport.
"""

from __future__ import annotations

import logging

from collections.abc import AsyncIterator, Container
from typing import TYPE_CHECKING, Any, Literal, cast, overload

from fastmcp import FastMCP
from fastmcp.client.transports import StreamableHttpTransport
from fastmcp.server.proxy import FastMCPProxy, ProxyClient
from fastmcp.tools import Tool

from codeweaver.common.utils import lazy_import
from codeweaver.config.middleware import MiddlewareOptions, default_for_transport
from codeweaver.config.settings import FastMcpHttpServerSettings, FastMcpStdioServerSettings
from codeweaver.config.types import FastMcpHttpRunArgs, FastMcpServerSettingsDict
from codeweaver.core.types import DictView, Unset
from codeweaver.mcp.middleware import McpMiddleware


if TYPE_CHECKING:
    from codeweaver.config.types import CodeWeaverSettingsDict, FastMcpServerSettingsDict
    from codeweaver.mcp.middleware import StatisticsMiddleware
    from codeweaver.mcp.state import CwMcpHttpState


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


def _get_middleware_settings() -> DictView[MiddlewareOptions] | None:
    """Get the current middleware settings."""
    from codeweaver.config.settings import get_settings_map

    settings_map = get_settings_map()
    return (
        settings_map.get_subview("middleware")
        if settings_map.get("middleware") is not Unset
        else None
    )  # type: ignore[arg-type]


def _get_default_middleware() -> Container[type[McpMiddleware]]:
    """Get the default middleware for the application."""
    from codeweaver.mcp.middleware import default_middleware_for_transport

    fastmcp_settings = _get_fastmcp_settings_map()
    transport = fastmcp_settings.get("transport", "streamable-http")
    return default_middleware_for_transport(transport)


def get_statistics_middleware(
    settings: MiddlewareOptions | DictView[MiddlewareOptions],
) -> StatisticsMiddleware:
    """Get the statistics middleware instance."""
    from codeweaver.common.statistics import get_session_statistics
    from codeweaver.mcp.middleware.statistics import StatisticsMiddleware

    return StatisticsMiddleware(
        statistics=get_session_statistics(),
        logger=logging.getLogger("codeweaver.middleware.statistics"),
        log_level=settings.get("logging", {}).get("log_level", 30),
    )


def configure_uvicorn_logging(
    run_args: FastMcpHttpRunArgs,
    host: str | None = None,
    port: int | None = None,
    *,
    verbose: bool = False,
    debug: bool = False,
) -> FastMcpHttpRunArgs:
    """Configure uvicorn logging based on verbosity settings."""
    # Make a mutable copy to avoid modifying the input
    mutable_run_args = dict(run_args)
    uvicorn_config = dict(mutable_run_args.get("uvicorn_config", {}))

    # host, port, and name go in run_args top-level only (FastMCP extracts them)
    # Also filter out invalid uvicorn.Config parameters
    invalid_params = {"host", "port", "name", "data_header"}  # data_header should be date_header
    uvicorn_config = {k: v for k, v in uvicorn_config.items() if k not in invalid_params}

    # Update mutable_run_args with the cleaned uvicorn_config
    mutable_run_args["uvicorn_config"] = uvicorn_config

    if port:
        mutable_run_args["port"] = port
    if host:
        mutable_run_args["host"] = host

    if verbose or debug:
        # Verbose/debug mode: Enable uvicorn access logs
        mutable_run_args["uvicorn_config"] = {
            **uvicorn_config,
            "access_log": True,  # Enable access logging in verbose mode
            "log_level": "debug" if debug else "info",  # Match verbosity level
        }
        return FastMcpHttpRunArgs(**mutable_run_args)
    # Non-verbose mode: Suppress all uvicorn logging
    # Just set log_level to critical and disable access_log
    # Don't pass custom log_config as it's complex to get right with Pydantic validation
    mutable_run_args["uvicorn_config"] = {
        **uvicorn_config,
        "access_log": False,  # Disable access logging
        "log_level": "critical",  # Only critical errors (minimal logging)
    }
    return FastMcpHttpRunArgs(**mutable_run_args)


def setup_runargs(
    run_args: FastMcpHttpRunArgs | DictView[FastMcpHttpRunArgs],
    host: str | None,
    port: int | None,
    *,
    verbose: bool = False,
    debug: bool = False,
) -> FastMcpHttpRunArgs:
    """Setup run arguments for the server."""
    mutable_run_args = dict(run_args) if isinstance(run_args, DictView) else run_args
    # Configure uvicorn logging and clean up host/port from uvicorn_config
    return configure_uvicorn_logging(
        FastMcpHttpRunArgs(**mutable_run_args), host=host, port=port, verbose=verbose, debug=debug
    )


def _attempt_import(mw: str) -> type[McpMiddleware] | None:
    """Attempt to import a middleware class from a string."""
    from importlib import import_module

    try:
        imported = import_module(mw.rsplit(".", 1)[0])
        imported = getattr(imported, mw.rsplit(".", 1)[1])
        if isinstance(imported, type) and issubclass(imported, McpMiddleware):
            return imported
    except (ImportError, AttributeError):
        logging.getLogger("codeweaver.mcp.server").warning(
            "Failed to import middleware class '%s'", mw
        )
    return None


def setup_middleware(
    middleware: Container[type[McpMiddleware]],
    middleware_settings: MiddlewareOptions | DictView[MiddlewareOptions],
) -> set[McpMiddleware]:
    """Setup middleware for the application."""
    # Convert container to set for modification
    result: set[McpMiddleware] = set()

    # Apply middleware settings
    # ty gets very confused here, so we ignore most issues

    for mw in middleware:  # type: ignore
        mw = mw
        match mw.__name__:  # type: ignore[reportUnknownMemberType, reportUnknownArgumentType, reportAttributeAccessIssue]
            case "ErrorHandlingMiddleware":
                instance = mw(
                    **(
                        middleware_settings.get("error_handling", {})
                        | {"logger": logging.getLogger("codeweaver.middleware.error_handling")}  # type: ignore[reportCallIssue]
                    )
                )
            case "RetryMiddleware":
                instance = mw(
                    **(middleware_settings.get("retry", {}))
                    | {"logger": logging.getLogger("codeweaver.middleware.retry")}  # type: ignore[reportCallIssue]
                )
            case "RateLimitingMiddleware":
                instance = mw(**middleware_settings.get("rate_limiting", {}))  # type: ignore[reportCallIssue]
            case "LoggingMiddleware" | "StructuredLoggingMiddleware":
                instance = mw(
                    **(middleware_settings.get("logging", {}))
                    | {"logger": logging.getLogger("codeweaver.middleware.logging")}  # type: ignore[reportCallIssue]
                )
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
    middleware_settings: MiddlewareOptions | DictView[MiddlewareOptions],
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


@overload
def _setup_server(
    args: DictView[FastMcpServerSettingsDict],
    transport: Literal["stdio"],
    host: None = None,
    port: None = None,
    *,
    verbose: Literal[False] = False,
    debug: Literal[False] = False,
) -> FastMCP[StdioClientLifespan]: ...
@overload
def _setup_server(
    args: DictView[FastMcpServerSettingsDict],
    transport: Literal["streamable-http"],
    host: str | None = None,
    port: int | None = None,
    *,
    verbose: bool,
    debug: bool,
) -> CwMcpHttpState: ...
def _setup_server[TransportT: Literal["stdio", "streamable-http"]](
    args: DictView[FastMcpServerSettingsDict],
    transport: TransportT,
    host: str | None = None,
    port: int | None = None,
    *,
    verbose: bool = False,
    debug: bool = False,
) -> FastMCP[StdioClientLifespan] | CwMcpHttpState:
    """Set class args for FastMCP server settings."""
    is_http = bool(args.get("run_args")) or transport == "streamable-http"
    # `run_args` is only set for HTTP transport
    middleware_opts = _get_middleware_settings() or default_for_transport(
        "streamable-http" if is_http else "stdio"
    )
    mutable_args = dict(args)
    # Middleware in settings is just configuration names/options, not classes
    # Remove it from args and always use default middleware classes for the transport
    mutable_args.pop("middleware", None)
    run_args = mutable_args.pop("run_args", {})
    # Remove transport from args - it's not a FastMCP constructor parameter
    mutable_args.pop("transport", None)

    # Always use default middleware classes for this transport
    from codeweaver.mcp.middleware import default_middleware_for_transport

    middleware = default_middleware_for_transport(transport)

    if is_http:
        run_args = setup_runargs(run_args, host, port, verbose=verbose, debug=debug)
    app = FastMCP(
        "CodeWeaver",
        **(
            mutable_args
            | {"icons": [lazy_import("codeweaver.server._assets", "CODEWEAVER_SVG_ICON")]}
        ),  # ty: ignore[invalid-argument-type]
    )
    app = register_tools(app)
    app = register_middleware(app, cast(list[type[McpMiddleware]], middleware), middleware_opts)
    if is_http:
        from codeweaver.mcp.state import CwMcpHttpState

        # Pass the instantiated middleware from app.middleware, not the classes
        return CwMcpHttpState.from_app(
            app, **(mutable_args | {"run_args": run_args, "middleware": app.middleware})
        )
    return cast(FastMCP[StdioClientLifespan], app)


# Note: FastMCP's parameterized type is the server's lifespan. For stdio servers, the client manages lifespan, so we use AsyncIterator[Any] aliased as StdioClientLifespan.
async def create_stdio_server(
    *,
    settings: CodeWeaverSettingsDict | None = None,
    host: str | None = None,
    port: int | None = None,
    verbose: bool = False,
    debug: bool = False,
) -> FastMCPProxy:
    """Get a FastMCP server configured for stdio transport.

    Args:
        settings: Optional FastMCP server settings dictionary, constructed when a custom config file is passed to the main CLI.
        host: Optional host for the server (this is the host/port for the *codeweaver http mcp server* that the stdio client will be proxied to -- only needed if not default or not what's in your config).
        port: Optional port for the server (this is the host/port for the *codeweaver http mcp server* that the stdio client will be proxied to -- only needed if not default or not what's in your config).
        verbose: Enable verbose logging.
        debug: Enable debug logging.

    Returns:
        Configured FastMCP stdio server instance.
    """
    if settings and (stdio_settings := settings.get("stdio_server")) is not Unset:
        stdio_settings = DictView(FastMcpServerSettingsDict(**cast(dict, stdio_settings)))
    else:
        stdio_settings = _get_fastmcp_settings_map(http=False)
    app = _setup_server(stdio_settings, transport="stdio")
    if settings and (http_settings := settings.get("mcp_server")) is not Unset:
        http_settings = DictView(FastMcpServerSettingsDict(**cast(dict, http_settings)))
    else:
        http_settings = _get_fastmcp_settings_map(http=True)
        run_args = http_settings.get("run_args", {})
    url = f"http://{host or run_args.get('host', '127.0.0.1')}:{port or run_args.get('port', 9328)}{http_settings.get('path', '/mcp')}"
    return app.as_proxy(backend=ProxyClient(transport=StreamableHttpTransport(url=url)))


async def create_http_server(
    *, host: str | None = None, port: int | None = None, verbose: bool = False, debug: bool = False
) -> CwMcpHttpState:
    """Get a FastMCP server configured for HTTP transport."""
    http_settings = _get_fastmcp_settings_map(http=True)
    return _setup_server(
        http_settings,
        transport="streamable-http",
        host=host,
        port=port,
        verbose=verbose,
        debug=debug,
    )


__all__ = ("create_http_server", "create_stdio_server")
