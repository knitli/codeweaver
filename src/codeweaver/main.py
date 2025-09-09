# sourcery skip: avoid-global-variables
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Main FastMCP server entrypoint for CodeWeaver with linear bootstrap."""

from __future__ import annotations

import asyncio
import logging

from typing import TYPE_CHECKING, Any, is_typeddict

from codeweaver._server import build_app
from codeweaver.app_bindings import register_app_bindings


if TYPE_CHECKING:
    from fastmcp import FastMCP

    from codeweaver._server import AppState, ServerSetup


async def start_server(server: FastMCP[AppState] | ServerSetup, **kwargs: dict[str, Any]) -> None:
    """Start CodeWeaver's FastMCP server.

    We start a minimal server here, and once it's up, we register components and merge in settings.
    """
    from fastmcp import FastMCP

    app = server if isinstance(server, FastMCP) else server["app"]
    kwargs = kwargs or {}
    server_setup: ServerSetup = ...  # type: ignore
    if is_typeddict(server):
        server_setup: ServerSetup = server
    if server_setup and hasattr(server_setup, "get"):
        settings = server_setup["settings"]
        new_kwargs = {
            "transport": settings.server.transport or "streamable-http",
            "host": server_setup.pop("host", "127.0.0.1"),
            "port": server_setup.pop("port", 9328),
            "log_level": server_setup.pop("log_level", "INFO"),
            "path": server_setup.pop("streamable_http_path", "/codeweaver"),
            "middleware": server_setup.pop("middleware", set()),
            "uvicorn_config": settings.uvicorn_settings.model_dump(
                mode="python", exclude_unset=True
            )
            if settings.uvicorn_settings
            else {},
        }
        kwargs = new_kwargs | kwargs  # pyright: ignore[reportAssignmentType]
    else:
        kwargs = {
            "transport": "streamable-http",
            "host": "127.0.0.1",
            "port": 9328,
            "log_level": "INFO",
            "path": "/codeweaver",
            "middleware": set(),
            "uvicorn_config": {},
            **kwargs.copy(),
        }  # type: ignore
    await app.run_http_async(**kwargs)  # type: ignore


async def run() -> None:
    """Run the CodeWeaver server."""
    server_setup = build_app()
    server_setup["app"], server_setup["middleware"] = register_app_bindings(
        server_setup["app"],
        server_setup.get("middleware", set()),
        server_setup.get("middleware_settings", {}),
    )
    await start_server(server_setup)


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except Exception as e:
        logging.getLogger(__name__).exception("Failed to start CodeWeaver server: ")
        raise RuntimeError("Failed to start CodeWeaver server.") from e

__all__ = ("run", "start_server")
