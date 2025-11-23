# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Configuration Models for mcp.json-type configuration files.

These are wrappers around FastMCP's configuration models, adding CodeWeaver defaults
and types where appropriate.

## MCP Transports

Current MCP specification allows two primary transports: HTTP streaming and STDIO (SSE is also supported but will be deprecated). Most MCP servers use STDIO transport (local 1-to-1 synchronous connection). CodeWeaver *can* use STDIO, but STDIO significantly degrades CodeWeaver's capabilities.

## Why Not STDIO?

STDIO transport spawns a separate server process per client instance and isolates each session. This means:
- Each client has its own server instance (no sharing)
- CodeWeaver cannot index or watch for changes in the background between client sessions
- A single server instance cannot handle concurrent requests from multiple clients
- Session management is limited to the lifespan of the client process (no or limited persistence)
- CodeWeaver can't expose features directly to users outside of MCP clients
- We also can't have long-lived sessions, background indexing and file watching, shared state

As far as we know, there are no existing comparable tools to CodeWeaver, but tools with less robust search and discovery use one of two approaches:

1. They aren't an MCP server at all (e.g., standalone search UIs, like in IDEs or integrated into an MCP client itself (like Roo)). This limits interoperability and the ability to leverage multiple clients and agents. CodeWeaver doesn't lock you into a single client or IDE.
2. They use STDIO MCP servers but sacrifice advanced features, with limited indexing capabilities, caching, no background indexing, and limited session management. Serena is an example of this approach, where any caching is to files in your project directory. Serena relies solely on language servers for code understanding, which limits it capabilities compared to CodeWeaver's approach.

## Streaming HTTP Transport

CodeWeaver uses HTTP streaming transport for MCP by default and strongly recommends users do the same.

This enables:
- Single shared server instance across all clients -- your code is indexed once and available to all clients
- Collective context across multiple clients -- sessions can persist and share state, and eventually we can get better understanding of what you're working on across clients to provide better results
- Background indexing that stays relevant regardless of client sessions -- CodeWeaver can watch your files and keep the index up to date even when no clients are connected.
- CLI-based search for humans outside of MCP clients (because we keep the index up to date in the background)
- Concurrent request handling
- Proper session management
- Less resource usage -- a single server process instead of one per client
"""

from __future__ import annotations

import datetime

from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, NotRequired, Required, TypedDict

from fastmcp.mcp_config import MCPConfig as FastMCPConfig
from fastmcp.mcp_config import RemoteMCPServer as FastMCPRemoteMCPServer
from fastmcp.mcp_config import StdioMCPServer as FastMCPStdioMCPServer
from fastmcp.mcp_config import update_config_file as update_mcp_config_file
from pydantic_core import from_json

from codeweaver.core.types.models import BasedModel
from codeweaver.exceptions import MissingValueError


if TYPE_CHECKING:
    from codeweaver.core.types.aliases import FilteredKeyT
    from codeweaver.core.types.enum import AnonymityConversion

CODEWEAVER_DESCRIPTION = "CodeWeaver advanced code search and understanding server."
# TODO: add icon
CODEWEAVER_ICON = None


class CodeWeaverMCPConfig(BasedModel, FastMCPRemoteMCPServer):
    """Configuration model for CodeWeaver configuration in mcp.json files."""

    url: str = "127.0.0.1:9328"

    timeout: int | None = 120
    description: str | None = CODEWEAVER_DESCRIPTION
    icon: str | None = CODEWEAVER_ICON

    @property
    def name_key(self) -> Literal["codeweaver"]:
        """Get the name key for the MCP server.

        Returns:
            The name key as a string.
        """
        return "codeweaver"

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        """Get telemetry keys for the MCP server.

        Returns:
            A dictionary of telemetry keys.
        """
        from codeweaver.core.types.aliases import FilteredKey
        from codeweaver.core.types.enum import AnonymityConversion

        return {
            FilteredKey("auth"): AnonymityConversion.BOOLEAN,
            FilteredKey("url"): AnonymityConversion.HASH,
            FilteredKey("headers"): AnonymityConversion.COUNT,
            FilteredKey("env"): AnonymityConversion.COUNT,
            FilteredKey("authentication"): AnonymityConversion.BOOLEAN,
        }


class StdioCodeWeaverConfig(BasedModel, FastMCPStdioMCPServer):
    """Configuration model for CodeWeaver mcp.json files using stdio communication."""

    command: str = "cw server --transport stdio"
    type: Literal["stdio"] | None = "stdio"
    description: str | None = CODEWEAVER_DESCRIPTION
    icon: str | None = CODEWEAVER_ICON

    @property
    def name_key(self) -> Literal["codeweaver"]:
        """Get the name key for the MCP server.

        Returns:
            The name key as a string.
        """
        return "codeweaver"

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        """Get telemetry keys for the MCP server.

        Returns:
            A dictionary of telemetry keys.
        """
        from codeweaver.core.types.aliases import FilteredKey
        from codeweaver.core.types.enum import AnonymityConversion

        return {
            FilteredKey("command"): AnonymityConversion.HASH,
            FilteredKey("args"): AnonymityConversion.COUNT,
            FilteredKey("env"): AnonymityConversion.COUNT,
            FilteredKey("cwd"): AnonymityConversion.HASH,
            FilteredKey("authentication"): AnonymityConversion.BOOLEAN,
        }


type MCPServerConfig = CodeWeaverMCPConfig | StdioCodeWeaverConfig


class MCPConfig(BasedModel, FastMCPConfig):
    """Configuration model for mcp.json files.

    Represents the overall MCP configuration, including CodeWeaver-specific settings.
    """

    # Add MCP configuration fields here as needed

    def serialize_for_vscode(self) -> dict[str, Any]:
        """Serialize the configuration for use in VSCode settings.

        Returns:
            A dictionary representation of the configuration suitable for VSCode.
        """
        serialized_self = self.model_dump(round_trip=True, exclude_none=True)
        return {"servers": serialized_self["mcpServers"]}

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion] | None:
        """Get telemetry keys for the MCP configuration.

        Returns:
            A dictionary of telemetry keys or None.
        """
        # MCPConfig doesn't have specific telemetry keys beyond what's in mcpServers
        return None

    @classmethod
    def from_vscode(
        cls, path: Path | None = None, data: dict[str, Any] | str | None = None
    ) -> MCPConfig:
        # sourcery skip: remove-redundant-if
        """Validate the configuration for use in VSCode settings.

        Raises:
            ValueError: If the configuration is invalid for VSCode.
        """
        if not data and not path:
            raise MissingValueError(
                field="`path` or `data`",
                msg="One of these must be provided to load MCPConfig from VSCode format.",
                suggestions=[
                    "Provide a valid path to the mcp.json file (for repos it is usually `.vscode/mcp.json`).",
                    "Provide the configuration data as a dictionary or JSON string.",
                ],
            )

        if data:
            data = data if isinstance(data, dict) else from_json(data)
        elif path:
            data = from_json(path.read_text(encoding="utf-8"))
        return cls.model_validate(data)


class CodeWeaverMCPConfigDict(TypedDict, total=False):
    """TypedDict for CodeWeaverMCPConfig serialization."""

    url: Required[str]
    transport: NotRequired[Literal["http", "streamable-http"] | None]
    timeout: NotRequired[int | None]
    auth: NotRequired[str | Literal["oauth"] | Any | None]  # httpx.Auth at runtime
    authentication: NotRequired[dict[str, Any] | None]
    headers: NotRequired[dict[str, str] | None]
    description: NotRequired[str | None]
    icon: NotRequired[str | None]
    sse_read_timeout: NotRequired[int | datetime.timedelta | float | None]  # deprecated


class StdioCodeWeaverConfigDict(TypedDict, total=False):
    """TypedDict for StdioCodeWeaverConfig serialization."""

    command: Required[str]
    args: NotRequired[list[str] | None]
    env: NotRequired[dict[str, Any] | None]
    transport: NotRequired[Literal["stdio"]]
    cwd: NotRequired[str | None]
    timeout: NotRequired[int | None]
    authentication: NotRequired[dict[str, Any] | None]
    type: NotRequired[Literal["stdio"] | None]
    description: NotRequired[str | None]
    icon: NotRequired[str | None]


class MCPConfigDict(TypedDict):
    """TypedDict for MCPConfig serialization."""

    mcpServers: list[CodeWeaverMCPConfigDict | StdioCodeWeaverConfigDict]


__all__ = (
    "CodeWeaverMCPConfig",
    "CodeWeaverMCPConfigDict",
    "MCPConfig",
    "MCPConfigDict",
    "StdioCodeWeaverConfigDict",
    "update_mcp_config_file",
)
