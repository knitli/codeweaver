# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Configuration Models for mcp.json-type configuration files.

These are wrappers around FastMCP's configuration models, adding CodeWeaver defaults
and types where appropriate.

## MCP Transports

CodeWeaver supports two MCP transports: STDIO (default) and HTTP streaming.

## Architecture: STDIO with HTTP Backend

CodeWeaver uses a daemon architecture that provides the best of both worlds:

1. **Daemon** (`codeweaver start`): Runs background services as a persistent process
   - Background indexing and file watching
   - HTTP MCP server on port 9328
   - Management server on port 9329

2. **STDIO Transport** (default): MCP clients spawn stdio processes that proxy to the daemon
   - Compatible with all MCP clients (Claude Desktop, VS Code, etc.)
   - Each stdio process is lightweight - just a proxy to the HTTP backend
   - All clients share the same indexed codebase via the daemon

This architecture enables:
- **Universal compatibility**: STDIO works with any MCP client
- **Shared state**: All clients access the same index via the HTTP backend
- **Background indexing**: The daemon keeps your index up to date between sessions
- **Concurrent access**: Multiple clients can connect simultaneously
- **Resource efficiency**: One daemon serves all clients

## When to Use HTTP Transport Directly

Use `--transport streamable-http` when:
- Running CodeWeaver as a standalone service (e.g., in Docker)
- Connecting from clients that support HTTP transport natively
- You don't need STDIO compatibility

## Quick Start

```bash
# Start the daemon (runs HTTP backend + background services)
codeweaver start

# MCP clients will automatically use STDIO transport to connect to the daemon
# Or run STDIO server manually:
codeweaver server  # defaults to --transport stdio
```
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal

from fastmcp.mcp_config import MCPConfig as FastMCPConfig
from fastmcp.mcp_config import RemoteMCPServer as FastMCPRemoteMCPServer
from fastmcp.mcp_config import StdioMCPServer as FastMCPStdioMCPServer
from fastmcp.mcp_config import update_config_file as update_mcp_config_file
from pydantic import Field
from pydantic_core import from_json

from codeweaver.core.types.models import BasedModel
from codeweaver.exceptions import MissingValueError


if TYPE_CHECKING:
    from codeweaver.config.types import CodeWeaverMCPConfigDict, StdioCodeWeaverConfigDict
    from codeweaver.core.types.aliases import FilteredKeyT
    from codeweaver.core.types.enum import AnonymityConversion

CODEWEAVER_DESCRIPTION = "CodeWeaver advanced code search and understanding server."

CODEWEAVER_ICON = (
    "https://raw.githubusercontent.com/knitli/codeweaver/main/docs/assets/codeweaver-primary.svg"
)


class CodeWeaverMCPConfig(BasedModel, FastMCPRemoteMCPServer):
    """Configuration model for CodeWeaver configuration in mcp.json files."""

    url: str = "http://127.0.0.1:9328/mcp"

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

    def as_mcp_config(self) -> dict[Literal["codeweaver"], CodeWeaverMCPConfigDict]:
        """Serialize the configuration to a dictionary suitable for MCP config files.

        Returns:
            A dictionary representation of the CodeWeaver MCP configuration.
        """
        return {self.name_key: self.model_dump(round_trip=True, exclude_none=True)}

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
    """Configuration model for CodeWeaver mcp.json files using stdio communication (default)."""

    command: str = "cw"
    args: list[str] = Field(default_factory=lambda: ["server"])
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

    def as_mcp_config(self) -> dict[Literal["codeweaver"], StdioCodeWeaverConfigDict]:
        """Serialize the configuration to a dictionary suitable for MCP config files.

        Returns:
            A dictionary representation of the CodeWeaver MCP configuration.
        """
        return {self.name_key: self.model_dump(round_trip=True, exclude_none=True)}

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        """Get telemetry keys for the MCP server.

        Returns:
            A dictionary of telemetry keys.
        """
        from codeweaver.core.types.aliases import FilteredKey
        from codeweaver.core.types.enum import AnonymityConversion

        return {
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


__all__ = ("CodeWeaverMCPConfig", "MCPConfig", "StdioCodeWeaverConfig", "update_mcp_config_file")
