# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

import datetime

from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, Literal

import httpx

from fastmcp.client.transports import SSETransport, StdioTransport, StreamableHttpTransport
from pydantic import AnyUrl, BaseModel, Field

"""Canonical MCP Configuration Format.

This module defines the standard configuration format for Model Context Protocol (MCP) servers.
It provides a client-agnostic, extensible format that can be used across all MCP implementations.

The configuration format supports both stdio and remote (HTTP/SSE) transports, with comprehensive
field definitions for server metadata, authentication, and execution parameters.

Example configuration:
    {
        "mcpServers": {
            "my-server": {
                "command": "npx",
                "args": ["-y", "@my/mcp-server"],
                "env": {"API_KEY": "secret"},
                "timeout": 30000,
                "description": "My MCP server"
            }
        }
    }
"""
if TYPE_CHECKING: ...

def infer_transport_type_from_url(url: str | AnyUrl) -> Literal["http", "sse"]:
    ...

class StdioMCPServer(BaseModel):


    command: str
    args: list[str] = ...
    env: dict[str, Any] = ...
    transport: Literal["stdio"] = ...
    type: Literal["stdio"] | None = ...
    cwd: str | None = ...
    timeout: int | None = ...
    description: str | None = ...
    icon: str | None = ...
    authentication: dict[str, Any] | None = ...
    model_config = ...
    def to_transport(self) -> StdioTransport: ...

class RemoteMCPServer(BaseModel):


    url: str
    transport: Literal["http", "streamable-http", "sse"] | None = ...
    headers: dict[str, str] = ...
    auth: Annotated[
        str | Literal["oauth"] | httpx.Auth | None,
        Field(
            description='Either a string representing a Bearer token, the literal "oauth" to use OAuth authentication, or an httpx.Auth instance for custom authentication.'
        ),
    ] = ...
    sse_read_timeout: datetime.timedelta | int | float | None = ...
    timeout: int | None = ...
    description: str | None = ...
    icon: str | None = ...
    authentication: dict[str, Any] | None = ...
    model_config = ...
    def to_transport(self) -> StreamableHttpTransport | SSETransport: ...

class MCPConfig(BaseModel):


    mcpServers: dict[str, StdioMCPServer | RemoteMCPServer]
    model_config = ...
    @classmethod
    def from_dict(cls, config: dict[str, Any]) -> MCPConfig:
        ...

    def to_dict(self) -> dict[str, Any]:
        ...

    def write_to_file(self, file_path: Path) -> None:
        ...

    @classmethod
    def from_file(cls, file_path: Path) -> MCPConfig:
        ...

    def add_server(self, name: str, server: StdioMCPServer | RemoteMCPServer) -> None:
        ...

    def remove_server(self, name: str) -> None:
        ...

def update_config_file(
    file_path: Path, server_name: str, server_config: StdioMCPServer | RemoteMCPServer
) -> None:
    ...
