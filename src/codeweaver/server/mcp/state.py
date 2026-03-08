# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Defines the MCP server state object for HTTP deployments."""

from __future__ import annotations

import logging
import time

from typing import TYPE_CHECKING, Annotated, Any

from fastmcp import FastMCP
from pydantic import Field, NonNegativeFloat, NonNegativeInt, PrivateAttr, computed_field

from codeweaver.core import DictView, SettingsMapDep, Unset, elapsed_time_to_human_readable
from codeweaver.core.config.settings_type import CodeWeaverSettingsType
from codeweaver.core.config.types import CodeWeaverSettingsDict
from codeweaver.core.constants import DEFAULT_MCP_PORT, LOCALHOST
from codeweaver.core.di.depends import INJECTED
from codeweaver.core.types import BasedModel
from codeweaver.server.config import (
    DefaultFastMcpHttpRunArgs,
    FastMcpHttpRunArgs,
    FastMcpHttpServerSettings,
    FastMcpServerSettingsDict,
    FastMcpStdioServerSettings,
)
from codeweaver.server.mcp.middleware import McpMiddleware


type FastMCPServerSettings = FastMcpHttpServerSettings | FastMcpStdioServerSettings

if TYPE_CHECKING:
    from fastmcp import FastMCP


logger = logging.getLogger(__name__)


def _get_settings_map(settings: SettingsMapDep = INJECTED) -> DictView[CodeWeaverSettingsDict]:
    """Get the current settings map."""
    return settings


def _get_fastmcp_settings_map(*, http: bool = False) -> DictView[FastMcpServerSettingsDict]:
    """Get the current FastMCP server settings."""
    from codeweaver.server.config import FastMcpHttpServerSettings, FastMcpStdioServerSettings

    settings_map = _get_settings_map()
    if http:
        return (
            settings_map.get_subview("mcp_server")
            if settings_map.get("mcp_server") is not Unset
            else DictView(FastMcpHttpServerSettings().as_settings())
        )
    return (
        settings_map.get_subview("stdio_server")
        if settings_map.get("stdio_server") is not Unset
        else DictView(FastMcpStdioServerSettings().as_settings())
    )


class CwMcpHttpState(BasedModel):
    """State object for MCP HTTP server deployments."""

    app: Annotated[FastMCP[Any], PrivateAttr()]

    logger: Annotated[
        logging.Logger,
        Field(
            default_factory=lambda: logging.getLogger("codeweaver.server.mcp.http"),
            description="Logger instance for the MCP HTTP server.",
        ),
    ]

    settings: Annotated[
        CodeWeaverSettingsType, Field(description="CodeWeaver configuration settings")
    ]

    mcp_settings: FastMCPServerSettings = Field(
        default_factory=lambda data: data["settings"].mcp_server,
        description="FastMCP server settings for the MCP HTTP server.",
    )

    run_args: FastMcpHttpRunArgs = Field(
        default_factory=lambda data: data["mcp_settings"].pop(
            "run_args", DefaultFastMcpHttpRunArgs
        ),
        description="Run arguments for the MCP HTTP server.",
    )

    middleware_instances: list[McpMiddleware] = Field(
        default_factory=lambda data: data["app"].middleware,
        description="Middleware instances applied to the MCP server.",
    )

    start_time: NonNegativeInt = Field(default_factory=lambda: int(time.time()))

    stopwatch_start: NonNegativeFloat = Field(default_factory=time.monotonic)

    @computed_field
    def uptime_seconds(self) -> NonNegativeInt:
        """Get the uptime of the server in seconds."""
        return int(time.monotonic() - self.stopwatch_start)

    @computed_field
    def human_uptime(self) -> str:
        """Get the uptime of the server in a human-readable format."""
        return elapsed_time_to_human_readable(self.uptime_seconds())

    @computed_field
    def human_start_time(self) -> str:
        """Get the server start time in a human-readable format."""
        from datetime import datetime

        return datetime.fromtimestamp(self.start_time).isoformat(sep=" ", timespec="seconds")

    @property
    def port(self) -> int:
        """Get the port the server is running on, if available."""
        return self.run_args.get("port") or self.mcp_settings.get("uvicorn_config", {}).get(
            "port", DEFAULT_MCP_PORT
        )

    @property
    def host(self) -> str:
        """Get the host the server is running on, if available."""
        return self.run_args.get("host") or self.mcp_settings.get("uvicorn_config", {}).get(
            "host", LOCALHOST
        )

    @classmethod
    def from_app(cls, app: FastMCP[Any], **kwargs: Any) -> CwMcpHttpState:
        """Create state from app setup with the app and optional kwargs."""
        assembled_kwargs: dict[str, Any] = {"app": app}
        if run_args := kwargs.get("run_args"):
            assembled_kwargs["run_args"] = run_args
        if middleware_instances := kwargs.get("middleware"):
            assembled_kwargs["middleware_instances"] = middleware_instances
        # we are dealing with FastMcpServerSettingsDict here
        if "instructions" in kwargs:
            assembled_kwargs |= {
                "mcp_settings": {k: v for k, v in kwargs.items() if k != "run_args"}
            }
        return cls(**assembled_kwargs)


__all__ = ("CwMcpHttpState", "FastMCPServerSettings")
