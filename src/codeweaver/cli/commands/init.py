# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Unified init command for CodeWeaver configuration and MCP client setup.

Handles both CodeWeaver project configuration and MCP client configuration
in a single command with proper HTTP streaming transport support.
"""

from __future__ import annotations

import shutil
import sys

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, Literal

import cyclopts
import httpx

from fastmcp.cli.install import claude_code, claude_desktop, cursor, gemini_cli, mcp_json
from pydantic_core import from_json as from_json
from pydantic_core import to_json as to_json
from rich.console import Console
from rich.prompt import Confirm

from codeweaver.common.utils.utils import get_user_config_dir


if TYPE_CHECKING:
    from codeweaver.config.mcp import CodeWeaverMCPConfig, StdioCodeWeaverConfig


client_modules = {
    "claude_code": claude_code,
    "claude_desktop": claude_desktop,
    "cursor": cursor,
    "mcpjson": mcp_json,
    "gemini_cli": gemini_cli,
}

console = Console(markup=True, emoji=True)

# Create cyclopts app at module level
app = cyclopts.App(
    "init", help="Initialize CodeWeaver configuration and MCP client setup.", console=console
)


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


def _create_codeweaver_config(project_path: Path, *, quick: bool = False) -> Path:
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


@app.command
def config(
    *,
    project: Annotated[Path | None, cyclopts.Parameter(name=["--project", "-p"])] = None,
    interactive: Annotated[bool, cyclopts.Parameter(name=["--interactive", "-i"])] = True,
    quick: Annotated[bool, cyclopts.Parameter(name=["--quick", "-q"])] = False,
    force: Annotated[bool, cyclopts.Parameter(name=["--force", "-f"])] = False,
) -> None:
    """Set up CodeWeaver configuration file.

    Args:
        project: Path to project directory (defaults to current directory)
        quick: Use recommended defaults without prompting
        force: Overwrite existing configuration file
    """
    console.print("\n[bold cyan]CodeWeaver Configuration Setup[/bold cyan]\n")

    # Determine project path
    project_path = (project or Path.cwd()).resolve()
    if not project_path.exists():
        console.print(f"[red]✗[/red] Project path does not exist: {project_path}")
        sys.exit(1)

    if not project_path.is_dir():
        console.print(f"[red]✗[/red] Path is not a directory: {project_path}")
        sys.exit(1)

    console.print(f"[dim]Project:[/dim] {project_path}\n")

    config_path = project_path / ".codeweaver.toml"

    if config_path.exists() and not force:
        if Confirm.ask(
            f"[yellow]Configuration file already exists at {config_path}. Overwrite?[/yellow]",
            default=False,
        ):
            config_path = _create_codeweaver_config(project_path, quick=quick)
            console.print(f"[green]✓[/green] Config created: {config_path}\n")
        else:
            console.print("[yellow]Skipping CodeWeaver config creation.[/yellow]\n")
    else:
        config_path = _create_codeweaver_config(project_path, quick=quick)
        console.print(f"[green]✓[/green] Config created: {config_path}\n")


def _get_client_config_path(
    client: Literal["claude_code", "claude_desktop", "cursor", "gemini_cli", "vscode", "mcpjson"],
    config_level: Literal["project", "user"],
    project_path: Path,
) -> Path:
    """Get the configuration file path for a specific MCP client.

    Args:
        client: MCP client name
        config_level: Configuration level ('project' or 'user')
        project_path: Path to project directory

    Returns:
        Path to the client's configuration file

    Raises:
        ValueError: If client doesn't support the requested config level
    """
    import os
    import sys

    match client:
        case "vscode":
            if config_level == "project":
                return project_path / ".vscode" / "mcp.json"
            return Path.home() / ".vscode" / "mcp.json"

        case "mcpjson":
            if config_level == "project":
                return project_path / ".mcp.json"
            return get_user_config_dir(base_only=True) / "mcp.json"

        case "claude_code":
            if config_level == "project":
                return project_path / ".claude" / "mcp.json"
            # User-level config paths
            if sys.platform == "win32":
                return Path(Path.home(), "AppData", "Roaming", "claude-code", "mcp.json")
            if sys.platform == "darwin":
                return Path(
                    Path.home(), "Library", "Application Support", "claude-code", "mcp.json"
                )
            # Linux
            return Path(
                os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"),
                "claude-code",
                "mcp.json",
            )

        case "cursor":
            if config_level == "project":
                return project_path / ".cursor" / "mcp.json"
            raise ValueError(
                "Cursor does not support user-level configuration. Use project-level only."
            )

        case "gemini_cli":
            if config_level == "project":
                return project_path / ".gemini" / "mcp.json"
            raise ValueError(
                "Gemini CLI user-level config not yet implemented. Use project-level only."
            )

        case "claude_desktop":
            if config_level == "project":
                raise ValueError(
                    "Claude Desktop does not support project-level configuration. Use user-level or switch to claude_code."
                )
            # User-level Claude Desktop config
            if sys.platform == "win32":
                return Path(
                    Path.home(), "AppData", "Roaming", "Claude", "claude_desktop_config.json"
                )
            if sys.platform == "darwin":
                return Path(
                    Path.home(),
                    "Library",
                    "Application Support",
                    "Claude",
                    "claude_desktop_config.json",
                )
            # Linux
            return Path(
                os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config"),
                "Claude",
                "claude_desktop_config.json",
            )


def _create_stdio_config(
    cmd: str | None = None,
    args: list[str] | None = None,
    env: dict[str, Any] | None = None,
    timeout: int = 120,
    authentication: dict[str, Any] | None = None,
    transport: Literal["stdio"] = "stdio",
) -> StdioCodeWeaverConfig:
    """Create a StdioCodeWeaverConfig instance for stdio transport.

    Args:
        cmd: Command to execute (default: "codeweaver")
        args: Arguments for the command (default: ["server", "--transport", "stdio"])
        env: Environment variables for the process
        timeout: Connection timeout in seconds
        authentication: Authentication configuration
        transport: Transport type (always "stdio")

    Returns:
        StdioCodeWeaverConfig instance
    """
    from codeweaver.config.mcp import StdioCodeWeaverConfig

    # Build the command - CodeWeaver doesn't need uv environment
    # We directly execute: codeweaver server --transport stdio
    command = cmd or "codeweaver"
    command_args = args or ["server", "--transport", "stdio"]

    # Combine command and args into single command string
    full_command = f"{command} {' '.join(command_args)}"

    config_data: dict[str, Any] = {"command": full_command, "type": "stdio"}

    if env:
        config_data["env"] = env
    if timeout:
        config_data["timeout"] = timeout
    if authentication:
        config_data["authentication"] = authentication

    return StdioCodeWeaverConfig.model_validate(config_data)


def _create_remote_config(
    host: str = "127.0.0.1",
    port: int = 9328,
    auth: str | Literal["oauth"] | httpx.Auth | None = None,
    timeout: int = 120,
    authentication: dict[str, Any] | None = None,
    transport: Literal["streamable-http"] = "streamable-http",
) -> CodeWeaverMCPConfig:
    """Create a CodeWeaverMCPConfig instance for HTTP transport.

    Args:
        host: Server host address
        port: Server port number
        auth: Authentication method (bearer token, 'oauth', httpx.Auth, or None)
        timeout: Connection timeout in seconds
        authentication: Authentication configuration
        transport: Transport type (always "streamable-http")

    Returns:
        CodeWeaverMCPConfig instance
    """
    from codeweaver.config.mcp import CodeWeaverMCPConfig

    # For HTTP transport, we just need the URL
    # No command execution needed - client connects directly to running server
    url = f"{host}:{port}"

    config_data: dict[str, Any] = {"url": url}

    if timeout:
        config_data["timeout"] = timeout
    if auth:
        config_data["auth"] = auth
    if authentication:
        config_data["authentication"] = authentication

    return CodeWeaverMCPConfig.model_validate(config_data)


def _handle_write_output(
    mcp_config: StdioCodeWeaverConfig | CodeWeaverMCPConfig,
    config_level: Literal["project", "user"],
    client: Literal["claude_code", "claude_desktop", "cursor", "gemini_cli", "vscode", "mcpjson"],
    file_path: Path | None,
    project_path: Path,
) -> None:
    """Handle writing MCP configuration to file.

    Args:
        mcp_config: MCP configuration instance
        config_level: Configuration level ('project', 'user')
        client: MCP client name
        file_path: Custom file path for writing config
        project_path: Path to project directory

    Raises:
        ValueError: If configuration is invalid or client doesn't support the config level
    """
    from codeweaver.config.mcp import MCPConfig

    try:
        # Determine config file path
        if file_path:
            config_path = file_path
            if file_path.is_dir():
                config_path = file_path / "mcp.json"
        else:
            config_path = _get_client_config_path(client, config_level, project_path)

        # Ensure parent directory exists
        config_path.parent.mkdir(parents=True, exist_ok=True)

        # Backup existing config if present
        if config_path.exists():
            _ = _backup_config(config_path)

        # Load or create MCPConfig
        if config_path.exists():
            try:
                # Load existing config
                config_text = config_path.read_text(encoding="utf-8")
                config_data = from_json(config_text)

                # Handle VSCode format (uses "servers" key instead of "mcpServers")
                if config_path.parent.name == ".vscode":
                    # VSCode format - from_vscode expects "servers" key
                    config_file = MCPConfig.from_vscode(path=config_path)
                else:
                    # Standard format - validate directly
                    config_file = MCPConfig.model_validate(config_data)
            except Exception as e:
                console.print(
                    f"[yellow]Warning: Could not parse existing config file at {config_path!s}. Creating new one. Error: {e}[/yellow]"
                )
                # Create new empty config
                config_file = MCPConfig.model_validate({"mcpServers": {}})
        else:
            # Create new empty config
            config_file = MCPConfig.model_validate({"mcpServers": {}})

        # Add/update codeweaver server in the config
        # The config_file should have an mcpServers dict we can update
        serialized_config = config_file.model_dump(exclude_none=True)
        if "mcpServers" not in serialized_config:
            serialized_config["mcpServers"] = {}

        # Add codeweaver configuration
        serialized_config["mcpServers"]["codeweaver"] = mcp_config.model_dump(exclude_none=True)

        # Update the config file
        config_file = MCPConfig.model_validate(serialized_config)

        # Write to file
        # Handle VSCode format when writing
        if config_path.parent.name == ".vscode":
            # VSCode uses "servers" key
            vscode_data = config_file.serialize_for_vscode()
            _ = config_path.write_text(
                to_json(vscode_data, indent=2).decode("utf-8"), encoding="utf-8"
            )
        else:
            # Standard format uses "mcpServers" key
            _ = config_path.write_text(
                to_json(serialized_config, indent=2).decode("utf-8"), encoding="utf-8"
            )

        console.print(f"[green]✓[/green] MCP config written: {config_path}\n")
        console.print("[dim]Configuration details:[/dim]")
        console.print_json(mcp_config.model_dump_json(exclude_none=True))

    except ValueError as e:
        console.print(f"[red]✗[/red] Configuration error: {e}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]✗[/red] Unexpected error: {e}")
        import traceback

        console.print(f"[dim]{traceback.format_exc()}[/dim]")
        sys.exit(1)


def handle_output(
    mcp_config: StdioCodeWeaverConfig | CodeWeaverMCPConfig,
    output: Literal["write", "print", "copy"],
    config_level: Literal["project", "user"],
    client: Literal["claude_code", "claude_desktop", "cursor", "vscode", "mcpjson"],
    file_path: Path | None,
    project_path: Path,
) -> None:
    """Handle output of MCP configuration based on specified method.

    Args:
        mcp_config: MCP configuration instance
        config_level: Configuration level ('project', 'user')
        output: Output method ('write', 'print', 'copy')
        client: MCP client name
        file_path: Custom file path for writing config
        project_path: Path to project directory
    """
    match output:
        case "write":
            _handle_write_output(mcp_config, config_level, client, file_path, project_path)
        case "print":
            console.print("[bold]MCP Client Configuration:[/bold]\n")
            console.print_json(mcp_config.model_dump_json())
        case "copy":
            try:
                import pyperclip

                pyperclip.copy(mcp_config.model_dump_json())
                console.print("[green]✓[/green] MCP configuration copied to clipboard.\n")
            except ImportError:
                console.print("[red]✗[/red] pyperclip not installed. Cannot copy to clipboard.")
                sys.exit(1)


@app.command
def mcp(
    *,
    output: Annotated[
        Literal["write", "print", "copy"],
        cyclopts.Parameter(
            name=["--output", "-o"],
            help="Output method for MCP client configuration. 'write' to file, 'print' to stdout, 'copy' to clipboard.",
        ),
    ] = "write",
    project: Annotated[Path | None, cyclopts.Parameter(name=["--project", "-p"])] = None,
    config_level: Annotated[
        Literal["project", "user"],
        cyclopts.Parameter(name=["--config-level", "-l"], help="Configuration level to write to."),
    ] = "project",
    file_path: Annotated[
        Path | None,
        cyclopts.Parameter(
            name=["--file-path", "-f"], help="Custom path to MCP client configuration file."
        ),
    ] = None,
    client: Annotated[
        Literal["claude_code", "claude_desktop", "cursor", "vscode", "mcpjson"],
        cyclopts.Parameter(
            name=["--client", "-c"],
            help="MCP client to configure, you can provide multiple clients by repeating this flag",
        ),
    ] = "mcpjson",
    host: Annotated[str, cyclopts.Parameter(name=["--host"])] = "127.0.0.1",
    port: Annotated[int, cyclopts.Parameter(name=["--port"])] = 9328,
    transport: Annotated[
        Literal["streamable-http", "stdio"],
        cyclopts.Parameter(
            name=["--transport", "-t"],
            help="Transport type for MCP communication",
            show_default=True,
            show_choices=True,
        ),
    ] = "streamable-http",
    timeout: Annotated[
        int,
        cyclopts.Parameter(
            name=["--timeout"], help="Timeout in seconds for MCP client connections"
        ),
    ] = 120,
    auth: Annotated[
        str | Literal["oauth"] | httpx.Auth | None,
        cyclopts.Parameter(
            name=["--auth"],
            help="Authentication method for MCP client (bearer token, 'oauth', an httpx.Auth object, or None)",
        ),
    ] = None,
    cmd: Annotated[
        str | None,
        cyclopts.Parameter(name=["--cmd"], help="[stdio-only] Command to start MCP client process"),
    ] = None,
    args: Annotated[
        list[str] | None,
        cyclopts.Parameter(
            name=["--args"],
            help="[stdio-only] Arguments for MCP client process command",
            negative="",
        ),
    ] = None,
    env: Annotated[
        dict[str, Any] | None,
        cyclopts.Parameter(
            name=["--env"], help="[stdio-only] Environment variables for MCP client process"
        ),
    ] = None,
    authentication: Annotated[
        dict[str, Any] | None,
        cyclopts.Parameter(
            name=["--authentication"], help="Authentication configuration for MCP client"
        ),
    ] = None,
) -> None:
    """Set up MCP client configuration for CodeWeaver.

    This command generates MCP client configuration that allows AI assistants like Claude Code,
    Cursor, or VSCode to connect to CodeWeaver's MCP server.

    **Transport Types:**
    - `streamable-http` (default): HTTP-based transport for persistent server connections
    - `stdio`: Standard input/output transport that launches CodeWeaver per-session

    **Tip**: Set a default MCP config in your CodeWeaver config, then just run
    `codeweaver init mcp --client your_client` to generate the config for that client.

    Args:
        client: MCP client to configure (claude_code, claude_desktop, cursor, vscode, mcpjson)
        output: Output method for MCP client configuration
        project: Path to project directory (auto-detected if not provided)
        config_level: Configuration level (project or user)
        transport: Transport type for MCP communication

        host: [http-only] Server host address (default: 127.0.0.1)
        port: [http-only] Server port (default: 9328)
        auth: [http-only] Authentication method

        cmd: [stdio-only] Command to start MCP server process (default: "codeweaver")
        args: [stdio-only] Arguments for the command (default: ["server", "--transport", "stdio"])
        env: [stdio-only] Environment variables for the process

        timeout: Timeout in seconds for connections
        authentication: Authentication configuration
        file_path: Custom file path for configuration output
    """
    console.print("\n[bold cyan]MCP Client Configuration Setup[/bold cyan]\n")
    from codeweaver.config.settings import get_settings_map

    # Determine project path
    project_path = project or get_settings_map().get("project_path") or Path.cwd()
    project_path = Path(project_path).resolve()
    console.print(f"[dim]Project:[/dim] {project_path}\n")

    # Determine transport and create appropriate config
    if transport == "stdio":
        # Create stdio config
        config = _create_stdio_config(
            cmd=cmd,
            args=args,
            env=env,
            timeout=timeout,
            authentication=authentication,
            transport="stdio",
        )
        console.print("[dim]Transport:[/dim] stdio (launches CodeWeaver per-session)\n")
    else:
        # Create HTTP config
        config = _create_remote_config(
            host=host,
            port=port,
            auth=auth,
            timeout=timeout,
            authentication=authentication,
            transport="streamable-http",
        )
        console.print(f"[dim]Transport:[/dim] streamable-http (connects to {host}:{port})\n")

    # Handle output
    handle_output(config, output, config_level, client, file_path, project_path)


@app.default
def init(
    *,
    project: Annotated[Path | None, cyclopts.Parameter(name=["--project", "-p"])] = None,
    config_only: Annotated[bool, cyclopts.Parameter(name=["--config-only"])] = False,
    mcp_only: Annotated[bool, cyclopts.Parameter(name=["--mcp-only"])] = False,
    quick: Annotated[bool, cyclopts.Parameter(name=["--quick", "-q"])] = False,
    client: Annotated[
        Literal["claude_code", "claude_desktop", "cursor", "vscode", "mcpjson"],
        cyclopts.Parameter(name=["--client", "-c"]),
    ] = "claude_code",
    host: Annotated[str, cyclopts.Parameter(name=["--host"])] = "127.0.0.1",
    port: Annotated[int, cyclopts.Parameter(name=["--port"])] = 9328,
    force: Annotated[bool, cyclopts.Parameter(name=["--force", "-f"])] = False,
    transport: Annotated[
        Literal["streamable-http", "stdio"], cyclopts.Parameter(name=["--transport", "-t"])
    ] = "streamable-http",
    config_level: Annotated[
        Literal["project", "user"], cyclopts.Parameter(name=["--config-level", "-l"])
    ] = "project",
) -> None:
    """Initialize CodeWeaver configuration and MCP client setup.

    By default, creates both CodeWeaver config and MCP client config.
    Use --config-only or --mcp-only to create just one.

    ARCHITECTURE NOTE:
    CodeWeaver uses HTTP streaming (not STDIO) for the MCP protocol by default.
    This means:
    - Single server instance shared across all clients
    - Background indexing persists between client sessions
    - Server must be started separately: codeweaver server

    You can use --transport stdio if you prefer per-session server instances.

    Args:
        project: Path to project directory (defaults to current directory)
        config_only: Only create CodeWeaver config file
        mcp_only: Only create MCP client config
        quick: Use recommended defaults without prompting
        client: MCP client to configure (claude_code, claude_desktop, cursor, vscode, mcpjson)
        host: Server host address for MCP config (default: 127.0.0.1)
        port: Server port for MCP config (default: 9328)
        transport: Transport type (streamable-http or stdio)
        config_level: Configuration level (project or user)
        force: Overwrite existing configurations

    Examples:
        codeweaver init --quick              # Full setup with defaults
        codeweaver init --config-only        # Just config file
        codeweaver init --mcp-only           # Just MCP client config
        codeweaver init --client cursor      # Setup for Cursor
        codeweaver init --transport stdio    # Use stdio transport
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
            if Confirm.ask(
                f"[yellow]Configuration file already exists at {config_path}. Overwrite?[/yellow]",
                default=False,
            ):
                config_path = _create_codeweaver_config(project_path, quick=quick)
                console.print(f"[green]✓[/green] Config created: {config_path}\n")
            else:
                console.print("[yellow]Skipping CodeWeaver config creation.[/yellow]\n")
        else:
            config_path = _create_codeweaver_config(project_path, quick=quick)
            console.print(f"[green]✓[/green] Config created: {config_path}\n")

    # Part 2: MCP Client Configuration
    if mcp_only:
        console.print("[bold]Step 2: MCP Client Configuration[/bold]\n")

        # Call the mcp() command directly with the provided parameters
        try:
            mcp(
                output="write",
                project=project_path,
                config_level=config_level,
                file_path=None,
                client=client,
                host=host,
                port=port,
                transport=transport,
                timeout=120,
                auth=None,
                cmd=None,
                args=None,
                env=None,
                authentication=None,
            )
        except Exception as e:
            console.print(f"[red]✗[/red] Failed to create MCP config: {e}")
            import traceback

            console.print(f"[dim]{traceback.format_exc()}[/dim]")
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

    if transport == "streamable-http":
        console.print("[bold]Architecture Note:[/bold]")
        console.print("CodeWeaver uses HTTP streaming transport, meaning the server")
        console.print("must be running before your MCP client can connect. Background")
        console.print("indexing persists between client sessions.\n")
    else:
        console.print("[bold]Architecture Note:[/bold]")
        console.print("Using stdio transport - CodeWeaver will launch per-session.")
        console.print("Each client session starts a new server instance.\n")


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


if __name__ == "__main__":
    main()
