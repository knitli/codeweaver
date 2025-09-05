# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

from typing import TYPE_CHECKING, Any, Literal

from fastmcp import FastMCP

if TYPE_CHECKING: ...
LOGO_ASCII = ...

def log_server_banner(
    server: FastMCP[Any],
    transport: Literal["stdio", "http", "sse", "streamable-http"],
    *,
    host: str | None = ...,
    port: int | None = ...,
    path: str | None = ...,
) -> None:
    ...
