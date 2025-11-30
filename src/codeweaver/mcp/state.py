"""Defines the MCP server state object for HTTP deployments."""

import logging
import time

from typing import TYPE_CHECKING, Any

from anthropic._models import computed_field
from fastmcp import FastMCP
from pydantic import ConfigDict, Field, PrivateAttr
from pydantic.dataclasses import dataclass
from pydantic.types import NonNegativeFloat, NonNegativeInt

from codeweaver.common.utils.lazy_importer import lazy_import
from codeweaver.common.utils.utils import elapsed_time_to_human_readable
from codeweaver.config.server_defaults import DefaultFastMcpHttpRunArgs
from codeweaver.config.types import (
    CodeWeaverSettingsDict,
    FastMcpHttpRunArgs,
    FastMcpServerSettingsDict,
)
from codeweaver.core.types.dictview import DictView
from codeweaver.core.types.models import DATACLASS_CONFIG, DataclassSerializationMixin
from codeweaver.core.types.sentinel import Unset
from codeweaver.mcp.middleware import McpMiddleware


get_settings_map = lazy_import("codeweaver.config.settings", "get_settings_map")


def _get_fastmcp_settings_map(*, http: bool = False) -> DictView[FastMcpServerSettingsDict]:
    """Get the current FastMCP server settings."""
    from codeweaver.config.settings import (
        FastMcpHttpServerSettings,
        FastMcpStdioServerSettings,
        get_settings_map,
    )

    settings_map = get_settings_map()
    if http:
        return (
            settings_map.get_subview("mcp_server")
            if settings_map.get("mcp_server") is not Unset
            else DictView(FastMcpHttpServerSettings().as_settings())
        )  # type: ignore[arg-type]
    return (
        settings_map.get_subview("stdio_server")
        if settings_map.get("stdio_server") is not Unset
        else DictView(FastMcpStdioServerSettings().as_settings())
    )


@dataclass(config=DATACLASS_CONFIG | ConfigDict(extra="forbid"))
class CwMcpHttpState(DataclassSerializationMixin):
    """State object for MCP HTTP server deployments."""

    app: FastMCP[Any] = PrivateAttr()

    logger: logging.Logger = Field(
        default_factory=lambda: logging.getLogger(__name__),
        description="Logger instance for the MCP HTTP server.",
    )

    settings: DictView[CodeWeaverSettingsDict] = Field(
        default_factory=lambda: get_settings_map(), description="CodeWeaver settings view."
    )

    mcp_settings: DictView[FastMcpServerSettingsDict] = Field(
        default_factory=_get_fastmcp_settings_map,
        description="FastMCP server settings view for the MCP HTTP server.",
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

    if TYPE_CHECKING:
        from fastmcp import FastMCP

    @computed_field
    def uptime_seconds(self) -> NonNegativeInt:
        """Get the uptime of the server in seconds."""
        return int(time.monotonic() - self.stopwatch_start)

    @computed_field
    def human_uptime(self) -> str:
        """Get the uptime of the server in a human-readable format."""
        return elapsed_time_to_human_readable(self.uptime_seconds)

    @computed_field
    def human_start_time(self) -> str:
        """Get the server start time in a human-readable format."""
        from datetime import datetime

        return datetime.fromtimestamp(self.start_time).isoformat(sep=" ", timespec="seconds")

    @property
    def port(self) -> int:
        """Get the port the server is running on, if available."""
        return self.run_args.get("port") or self.mcp_settings.get("uvicorn_config", {}).get(
            "port", 9328
        )

    @property
    def host(self) -> str:
        """Get the host the server is running on, if available."""
        return self.run_args.get("host") or self.mcp_settings.get("uvicorn_config", {}).get(
            "host", "127.0.0.1"
        )


__all__ = ("CwMcpHttpState",)
