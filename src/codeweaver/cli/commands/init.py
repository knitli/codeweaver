# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

# scaffolding for the init CLI command to add MCP configurations and generate a codeweaver config
"""Init-related CLI commands for CodeWeaver."""

from pathlib import Path


def add(
    *,
    project: Path | None = None,
    claude_code: bool = False,
    claude_desktop: bool = False,
    cursor: bool = False,
    gemini_cli: bool = False,
    mcp_json: bool = False,
) -> None:
    """Scaffold for init command."""
    import shutil

    clients = {
        "claude_code": claude_code,
        "claude_desktop": claude_desktop,
        "cursor": cursor,
        "gemini_cli": gemini_cli,
        "mcp_json": mcp_json,
    }
    if not any(clients.values()):
        print("You need to specify at least one client to configure!")
        return

    if has_fastmcp := shutil.which("fastmcp"):
        print(f"Found FastMCP at {has_fastmcp}, proceeding to initialize MCP configuration...")
        # Future implementation will go here
