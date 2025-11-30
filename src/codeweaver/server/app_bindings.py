# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Application bindings for FastMCP server setup.

This module provides functions to register middleware and tools with
the FastMCP application instance.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from fastmcp import FastMCP
from fastmcp.server.middleware.middleware import Middleware


if TYPE_CHECKING:
    from codeweaver.config.middleware import MiddlewareOptions
    from codeweaver.server.server import CodeWeaverState


async def register_app_bindings(
    app: FastMCP[CodeWeaverState],
    middleware: set[type[Middleware]] | set[Middleware],
    middleware_settings: MiddlewareOptions,
) -> tuple[FastMCP[CodeWeaverState], set[type[Middleware]] | set[Middleware]]:
    """Register middleware and other bindings with the FastMCP application.

    Args:
        app: FastMCP application instance
        middleware: Set of middleware classes or instances to register
        middleware_settings: Settings for configuring middleware instances

    Returns:
        Tuple of (configured app, registered middleware set)
    """
    from codeweaver.mcp.server import setup_middleware

    # Set up middleware instances with their settings
    # Only call setup_middleware if we have middleware types (classes), not instances
    if middleware and all(isinstance(m, type) for m in middleware):
        configured_middleware = setup_middleware(middleware, middleware_settings)  # type: ignore[arg-type]
        # Register each middleware instance with the app
        for mw in configured_middleware:
            _ = app.add_middleware(mw)
    else:
        # Middleware are already instances, register directly
        for mw in middleware:
            if isinstance(mw, Middleware):
                _ = app.add_middleware(mw)

    return app, middleware


def register_tool(app: FastMCP[Any]) -> FastMCP[Any]:
    """Register CodeWeaver tools with the FastMCP application.

    Args:
        app: FastMCP application instance

    Returns:
        The app with tools registered
    """
    from codeweaver.mcp.tools import TOOL_DEFINITIONS
    from codeweaver.mcp.tools import register_tool as _register_tool

    # Register the find_code tool
    find_code_tool = TOOL_DEFINITIONS.get("find_code")
    if find_code_tool:
        app = _register_tool(app, find_code_tool)

    return app


__all__ = ("register_app_bindings", "register_tool")
