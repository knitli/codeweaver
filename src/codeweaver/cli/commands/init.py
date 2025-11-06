# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Unified init command for CodeWeaver configuration and MCP client setup.

Handles both CodeWeaver project configuration and MCP client configuration
in a single command with proper HTTP streaming transport support.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import sys

from datetime import UTC, datetime
from pathlib import Path
from typing import Annotated, Any

import cyclopts

from rich.console import Console
from rich.prompt import Confirm


console = Console()

# Create cyclopts app at module level
app = cyclopts.App(
    "init",
    help="Initialize CodeWeaver configuration and MCP client setup.",
    console=console,
)


def _get_mcp_client_config_path(client: str) -> Path:
    """Get MCP client configuration file path.

    Args:
        client: MCP client name (claude_code, claude_desktop, cursor, continue)

    Returns:
        Path to client's MCP configuration file

    Raises:
        ValueError: If client is unknown or not supported on current platform
    """
    system = platform.system()
    home = Path.home()

    match client:
        case "claude_code":
            return home / ".config" / "claude" / "claude_code_config.json"
        case "claude_desktop":
            if system == "Darwin":
                return (
                    home
                    / "Library"
                    / "Application Support"
                    / "Claude"
                    / "claude_desktop_config.json"
                )
            if system == "Windows":
                appdata = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
                return appdata / "Claude" / "claude_desktop_config.json"
            raise ValueError(
                f"Claude Desktop not officially supported on {system}. "
                "Use claude_code, cursor, or continue instead."
            )
        case "cursor":
            # Prefer project-local .cursor/config.json
            project_cursor = Path.cwd() / ".cursor" / "config.json"
            return project_cursor if project_cursor.parent.exists() else home / ".cursor" / "config.json"
        case "continue":
            return home / ".continue" / "config.json"
        case _:
            raise ValueError(
                f"Unknown MCP client: {client}. "
                "Valid options: claude_code, claude_desktop, cursor, continue"
            )


def _generate_http_mcp_config(project_path: Path, host: str = "127.0.0.1", port: int = 9328) -> dict[str, Any]:
    """Generate HTTP streaming MCP server configuration for CodeWeaver.

    CodeWeaver uses HTTP streaming transport (not STDIO) for MCP protocol.
    This enables:
    - Single shared server instance across all clients
    - Background indexing that persists between client sessions
    - Concurrent request handling
    - Proper session management

    Args:
        project_path: Path to project directory for CodeWeaver to index
        host: Server host address (default: 127.0.0.1)
        port: Server port (default: 9328, 'WEAV' on phone keypad)

    Returns:
        Dictionary containing MCP server configuration for HTTP transport
    """
    # Note: Using 'codeweaver' command directly, not 'fastmcp run'
    # Server must be started separately: codeweaver server
    return {
        "command": "codeweaver",
        "args": ["server", "--transport", "http", "--host", host, "--port", str(port)],
        "env": {
            "CODEWEAVER_PROJECT_PATH": str(project_path.resolve()),
            "VOYAGE_API_KEY": "${VOYAGE_API_KEY}",  # Will be replaced by user's actual key
        },
    }


def _load_json_config(path: Path) -> dict[str, Any]:
    """Load JSON configuration from file.

    Args:
        path: Path to JSON configuration file

    Returns:
        Parsed JSON as dictionary, or empty dict if file doesn't exist

    Raises:
        json.JSONDecodeError: If file exists but contains invalid JSON
    """
    if not path.exists():
        return {}

    try:
        with path.open("r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        console.print(f"[yellow]⚠[/yellow]  Warning: Config file exists but contains invalid JSON: {path}")
        console.print(f"   Error: {e}")
        raise


def _backup_config(path: Path) -> Path:
    """Create timestamped backup of configuration file.

    Args:
        path: Path to configuration file to backup

    Returns:
        Path to backup file
    """
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
    backup_path = path.parent / f"{path.stem}.backup_{timestamp}{path.suffix}"

    if path.exists():
        shutil.copy2(path, backup_path)
        console.print(f"[green]✓[/green] Created backup: {backup_path}")

    return backup_path


def _save_json_config(path: Path, config: dict[str, Any]) -> None:
    """Save JSON configuration to file with proper formatting.

    Args:
        path: Path to save configuration file
        config: Configuration dictionary to save
    """
    path.parent.mkdir(parents=True, exist_ok=True)

    with path.open("w", encoding="utf-8") as f:
        json.dump(config, f, indent=2, ensure_ascii=False)
        f.write("\n")  # Add trailing newline


def _merge_mcp_config(
    existing: dict[str, Any],
    project_path: Path,
    *,
    force: bool = False,
    host: str = "127.0.0.1",
    port: int = 9328,
) -> tuple[dict[str, Any], bool]:
    """Merge CodeWeaver configuration into existing MCP config.

    Args:
        existing: Existing configuration dictionary
        project_path: Path to project for CodeWeaver
        force: Whether to overwrite existing CodeWeaver configuration
        host: Server host address
        port: Server port

    Returns:
        Tuple of (merged config dict, whether changes were made)
    """
    config = existing.copy()

    # Ensure mcpServers key exists
    if "mcpServers" not in config:
        config["mcpServers"] = {}

    # Check if CodeWeaver already configured
    if "codeweaver" in config["mcpServers"]:
        if not force:
            console.print("[yellow]⚠[/yellow]  CodeWeaver already configured. Use --force to overwrite.")
            return config, False
        console.print("[yellow]🔄[/yellow] Overwriting existing CodeWeaver configuration (--force enabled)")

    # Add or update CodeWeaver configuration
    config["mcpServers"]["codeweaver"] = _generate_http_mcp_config(project_path, host, port)

    return config, True


def _create_codeweaver_config(project_path: Path, quick: bool = False) -> Path:
    """Create CodeWeaver configuration file interactively.

    Args:
        project_path: Path to project directory
        quick: Use recommended defaults without prompting

    Returns:
        Path to created configuration file
    """
    from codeweaver.cli.commands.config import init as config_init_wizard

    # Use existing config wizard
    config_path = project_path / ".codeweaver.toml"

    if quick:
        # Use recommended default profile
        console.print("[cyan]Creating configuration with recommended defaults...[/cyan]")
        # For quick mode, we'll use the config wizard with default answers
        # This will be implemented by the config wizard's quick mode

    # Call the existing config wizard
    config_init_wizard(output=config_path, force=False)

    return config_path


@app.default
def init(
    *,
    project: Annotated[Path | None, cyclopts.Parameter(name=["--project", "-p"])] = None,
    config_only: Annotated[bool, cyclopts.Parameter(name=["--config-only"])] = False,
    mcp_only: Annotated[bool, cyclopts.Parameter(name=["--mcp-only"])] = False,
    quick: Annotated[bool, cyclopts.Parameter(name=["--quick", "-q"])] = False,
    client: Annotated[str, cyclopts.Parameter(name=["--client", "-c"])] = "claude_code",
    host: Annotated[str, cyclopts.Parameter(name=["--host"])] = "127.0.0.1",
    port: Annotated[int, cyclopts.Parameter(name=["--port"])] = 9328,
    force: Annotated[bool, cyclopts.Parameter(name=["--force", "-f"])] = False,
) -> None:
    """Initialize CodeWeaver configuration and MCP client setup.

    By default, creates both CodeWeaver config and MCP client config.
    Use --config-only or --mcp-only to create just one.

    ARCHITECTURE NOTE:
    CodeWeaver uses HTTP streaming (not STDIO) for the MCP protocol.
    This means:
    - Single server instance shared across all clients
    - Background indexing persists between client sessions
    - Server must be started separately: codeweaver server

    This is why we don't use 'fastmcp install' - it assumes STDIO
    per-client processes which breaks CodeWeaver's architecture.

    Args:
        project: Path to project directory (defaults to current directory)
        config_only: Only create CodeWeaver config file
        mcp_only: Only create MCP client config
        quick: Use recommended defaults without prompting
        client: MCP client to configure (claude_code, claude_desktop, cursor, continue)
        host: Server host address for MCP config (default: 127.0.0.1)
        port: Server port for MCP config (default: 9328)
        force: Overwrite existing configurations

    Examples:
        codeweaver init --quick              # Full setup with defaults
        codeweaver init --config-only        # Just config file
        codeweaver init --mcp-only           # Just MCP client config
        codeweaver init --client cursor      # Setup for Cursor
    """
    console.print("\n[bold cyan]CodeWeaver Initialization[/bold cyan]\n")

    # Determine project path
    project_path = (project or Path.cwd()).resolve()
    if not project_path.exists():
        console.print(f"[red]✗[/red] Project path does not exist: {project_path}")
        sys.exit(1)

    if not project_path.is_dir():
        console.print(f"[red]✗[/red] Path is not a directory: {project_path}")
        sys.exit(1)

    console.print(f"[dim]Project:[/dim] {project_path}\n")

    # Default: do both if neither flag specified
    if not config_only and not mcp_only:
        config_only = mcp_only = True

    # Part 1: CodeWeaver Configuration
    if config_only:
        console.print("[bold]Step 1: CodeWeaver Configuration[/bold]\n")

        config_path = project_path / ".codeweaver.toml"

        if config_path.exists() and not force:
            overwrite = Confirm.ask(
                f"[yellow]Configuration file already exists at {config_path}. Overwrite?[/yellow]",
                default=False,
            )
            if not overwrite:
                console.print("[yellow]Skipping CodeWeaver config creation.[/yellow]\n")
            else:
                config_path = _create_codeweaver_config(project_path, quick)
                console.print(f"[green]✓[/green] Config created: {config_path}\n")
        else:
            config_path = _create_codeweaver_config(project_path, quick)
            console.print(f"[green]✓[/green] Config created: {config_path}\n")

    # Part 2: MCP Client Configuration
    if mcp_only:
        console.print("[bold]Step 2: MCP Client Configuration[/bold]\n")

        try:
            # Get client config path
            client_config_path = _get_mcp_client_config_path(client)
            console.print(f"[dim]Client:[/dim] {client}")
            console.print(f"[dim]Config:[/dim] {client_config_path}\n")

            # Load existing config
            existing_config = _load_json_config(client_config_path)

            # Backup if file exists
            if client_config_path.exists():
                _backup_config(client_config_path)

            # Merge CodeWeaver configuration
            merged_config, changed = _merge_mcp_config(
                existing_config, project_path, force=force, host=host, port=port
            )

            if not changed:
                console.print("[yellow]No changes made to MCP config.[/yellow]\n")
            else:
                # Save updated configuration
                _save_json_config(client_config_path, merged_config)
                console.print(f"[green]✓[/green] MCP config updated: {client_config_path}\n")

        except ValueError as e:
            console.print(f"[red]✗[/red] {e}")
            sys.exit(1)
        except json.JSONDecodeError:
            console.print("[red]✗[/red] Failed to parse existing MCP config file")
            sys.exit(1)
        except Exception as e:
            console.print(f"[red]✗[/red] Unexpected error: {e}")
            sys.exit(1)

    # Final Instructions
    console.print("[bold green]Setup complete![/bold green]\n")
    console.print("[bold]Next steps:[/bold]")
    console.print("  1. Set VOYAGE_API_KEY environment variable:")
    console.print("     [dim]export VOYAGE_API_KEY='your-api-key'[/dim]")
    console.print("  2. Start the server: [cyan]codeweaver server[/cyan]")
    console.print(f"  3. Restart {client} to load MCP config")
    console.print("  4. Test with a query:")
    console.print("     [dim]'Find the authentication logic'[/dim]\n")

    console.print("[bold]Architecture Note:[/bold]")
    console.print("CodeWeaver uses HTTP streaming transport, meaning the server")
    console.print("must be running before your MCP client can connect. Background")
    console.print("indexing persists between client sessions.\n")


def main() -> None:
    """CLI entry point for init command."""
    try:
        app()
    except KeyboardInterrupt:
        console.print("\n[yellow]Initialization cancelled by user.[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"[red]✗[/red] Initialization failed: {e}")
        sys.exit(1)


# Legacy compatibility - deprecated
def add(
    *,
    project: Path | None = None,
    claude_code: bool = False,
    claude_desktop: bool = False,
    cursor: bool = False,
    gemini_cli: bool = False,
    mcp_json: Path | None = None,
    force: bool = False,
    all_clients: bool = False,
) -> None:
    """Add CodeWeaver MCP server configuration to specified clients.

    [DEPRECATED] Use 'codeweaver init' instead. This command will be removed in v0.2.

    Args:
        project: Path to project directory (defaults to current directory)
        claude_code: Add to Claude Code configuration
        claude_desktop: Add to Claude Desktop configuration
        cursor: Add to Cursor configuration
        gemini_cli: Add to Gemini CLI configuration (not yet supported)
        mcp_json: Path to custom MCP JSON config file
        force: Overwrite existing CodeWeaver configuration if present
        all_clients: Configure all available clients
    """
    console.print(
        "[yellow]⚠ WARNING: This command is deprecated. Use 'codeweaver init' instead.[/yellow]"
    )
    console.print("[yellow]   This command will be removed in v0.2.[/yellow]\n")

    # Map old client flags to new client parameter
    if claude_code or all_clients:
        client = "claude_code"
    elif claude_desktop or all_clients:
        client = "claude_desktop"
    elif cursor or all_clients:
        client = "cursor"
    else:
        console.print("[red]✗[/red] Please specify at least one client to configure.")
        console.print("[yellow]   Use 'codeweaver init' for the new unified interface.[/yellow]")
        sys.exit(1)

    # Call new unified init with mcp_only=True
    init(project=project, mcp_only=True, client=client, force=force)
