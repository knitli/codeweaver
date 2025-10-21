# sourcery skip: avoid-global-variables, snake-case-variable-declarations
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Main FastMCP server entrypoint for CodeWeaver with linear bootstrap."""

from __future__ import annotations

import asyncio
import logging

from pathlib import Path
from typing import TYPE_CHECKING, Any, is_typeddict

from pydantic import FilePath

from codeweaver._server import build_app
from codeweaver._utils import lazy_importer
from codeweaver.app_bindings import register_app_bindings, register_tool
from codeweaver.provider import Provider as Provider  # needed for pydantic models


if TYPE_CHECKING:
    from fastmcp import FastMCP

    from codeweaver._server import AppState, ServerSetup


async def start_server(server: FastMCP[AppState] | ServerSetup, **kwargs: dict[str, Any]) -> None:
    """Start CodeWeaver's FastMCP server.

    We start a minimal server here, and once it's up, we register components and merge in settings.
    """
    from fastmcp import FastMCP

    # Pydantic will need these at runtime
    _server_module = lazy_importer("codeweaver._server")
    ServerSetup: ServerSetup = _server_module.ServerSetup  # pyright: ignore[reportUnusedVariable] # noqa: F841, N806
    AppState: AppState = _server_module.AppState  # pyright: ignore[reportUnusedVariable] # noqa: F841, N806

    app = server if isinstance(server, FastMCP) else server["app"]
    kwargs = kwargs or {}
    server_setup: ServerSetup = ...  # type: ignore
    if is_typeddict(server):
        server_setup: ServerSetup = server  # type: ignore
    if server_setup and hasattr(server_setup, "get"):
        settings = server_setup["settings"]
        new_kwargs = {  # type: ignore
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
        kwargs = new_kwargs | kwargs  # pyright: ignore[reportUnknownVariableType, reportAssignmentType]
    else:
        kwargs = {  # type: ignore
            "transport": "streamable-http",
            "host": "127.0.0.1",
            "port": 9328,
            "log_level": "INFO",
            "path": "/codeweaver",
            "middleware": set(),
            "uvicorn_config": {},
            **kwargs.copy(),
        }  # type: ignore
    registry = lazy_importer("codeweaver._registry")
    registry.initialize_registries()
    await app.run_http_async(**kwargs)  # type: ignore


async def run(
    *,
    config_file: FilePath | None = None,
    project_path: Path | None = None,
    host: str = "127.0.0.1",
    port: int = 9328,
) -> None:
    """Run the CodeWeaver server."""
    server_setup = build_app()
    if host:
        server_setup["host"] = host
    if port:
        server_setup["port"] = port
    if config_file or project_path:
        from codeweaver.settings import get_settings

        server_setup["settings"] = get_settings(path=config_file)
    if project_path:
        from codeweaver.settings import update_settings

        _ = update_settings(**{
            **server_setup["settings"].model_dump(),
            "project_path": project_path,
        })  # pyright: ignore[reportArgumentType]
    server_setup["app"], server_setup["middleware"] = await register_app_bindings(  # type: ignore
        server_setup["app"],
        server_setup.get("middleware", set()),  # pyright: ignore[reportArgumentType]
        server_setup.get("middleware_settings", {}),
    )
    server_setup["app"] = register_tool(server_setup["app"])
    await start_server(server_setup)


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except Exception as e:
        logging.getLogger(__name__).exception("Failed to start CodeWeaver server: ")
        raise RuntimeError("Failed to start CodeWeaver server.") from e

__all__ = ("run", "start_server")
