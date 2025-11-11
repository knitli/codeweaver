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
from types import EllipsisType
from typing import TYPE_CHECKING, Any, is_typeddict

from fastmcp import FastMCP
from pydantic import FilePath
from typing_extensions import TypeIs

from codeweaver.common.utils import lazy_import
from codeweaver.core.types.sentinel import Unset
from codeweaver.exceptions import InitializationError
from codeweaver.providers.provider import Provider as Provider  # needed for pydantic models


if TYPE_CHECKING:
    from codeweaver.config.settings import CodeWeaverSettings
    from codeweaver.server import AppState, ServerSetup

logger = logging.getLogger(__name__)


def is_server_setup(obj: Any) -> TypeIs[ServerSetup]:
    """Type guard to check if an object is a ServerSetup TypedDict."""
    return (
        is_typeddict(obj)
        and all(key in obj for key in ("app", "settings"))
        and isinstance(obj["settings"], CodeWeaverSettings)
    )


async def start_server(server: FastMCP[AppState] | ServerSetup, **kwargs: Any) -> None:
    """Start CodeWeaver's FastMCP server.

    We start a minimal server here, and once it's up, we register components and merge in settings.
    """
    app = server if isinstance(server, FastMCP) else server["app"]
    resolved_kwargs: dict[str, Any] = kwargs or {}
    server_setup: ServerSetup | EllipsisType = server if is_server_setup(server) else ...
    if server_setup and is_server_setup(server_setup):
        settings: CodeWeaverSettings = server_setup["settings"]
        new_kwargs = {  # type: ignore
            "transport": "streamable-http"
            if isinstance(settings.server, Unset)
            else settings.server.transport,
            "host": server_setup.pop("host", "127.0.0.1"),
            "port": server_setup.pop("port", 9328),
            "log_level": server_setup.pop("log_level", "INFO"),
            "path": server_setup.pop("streamable_http_path", "/codeweaver"),
            "middleware": server_setup.pop("middleware", set()),
            "uvicorn_config": settings.uvicorn or {},
        }
        resolved_kwargs = new_kwargs | kwargs
    else:
        resolved_kwargs = {  # type: ignore
            "transport": "streamable-http",
            "host": "127.0.0.1",
            "port": 9328,
            "log_level": "INFO",
            "path": "/codeweaver",
            "middleware": set(),
            "uvicorn_config": {},
            **kwargs.copy(),
        }  # type: ignore
    registry = lazy_import("codeweaver.common.registry.provider", "get_provider_registry")  # type: ignore
    _ = registry()  # type: ignore
    await app.run_http_async(**resolved_kwargs)  # type: ignore


async def run(
    *,
    config_file: FilePath | None = None,
    project_path: Path | None = None,
    host: str = "127.0.0.1",
    port: int = 9328,
) -> None:
    """Run the CodeWeaver server."""
    from codeweaver.server import build_app
    from codeweaver.server.app_bindings import register_app_bindings, register_tool

    server_setup = build_app()
    if host:
        server_setup["host"] = host
    if port:
        server_setup["port"] = port
    if config_file or project_path:
        from codeweaver.config.settings import get_settings

        server_setup["settings"] = get_settings(config_file=config_file)
    if project_path:
        from codeweaver.config.settings import update_settings

        logger.debug("Type of server_setup['settings']: %s", type(server_setup["settings"]))
        _ = update_settings(**{
            **server_setup["settings"].model_dump(),
            "project_path": project_path,
        })
    server_setup["app"], server_setup["middleware"] = await register_app_bindings(  # type: ignore
        server_setup["app"],
        server_setup.get("middleware", set()),
        server_setup.get("middleware_settings", {}),
    )
    server_setup["app"] = register_tool(server_setup["app"])
    await start_server(server_setup)


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except Exception as e:
        logging.getLogger(__name__).exception("Failed to start CodeWeaver server: ")
        raise InitializationError("Failed to start CodeWeaver server.") from e

__all__ = ("run", "start_server")
