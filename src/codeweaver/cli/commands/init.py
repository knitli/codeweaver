# sourcery skip: no-complex-if-expressions
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

from pydantic import AnyHttpUrl
from pydantic_core import from_json as from_json
from pydantic_core import to_json as to_json
from rich.prompt import Confirm

from codeweaver.cli.ui import CLIErrorHandler, get_display
from codeweaver.cli.utils import resolve_project_root
from codeweaver.common.utils.utils import get_user_config_dir
from codeweaver.exceptions import CodeWeaverError


if TYPE_CHECKING:
    from codeweaver.cli.ui import StatusDisplay
    from codeweaver.config.mcp import CodeWeaverMCPConfig, StdioCodeWeaverConfig

type MCPClient = Literal[
    "claude_code", "claude_desktop", "cursor", "gemini_cli", "vscode", "mcpjson"
]


def _lazy_import_httpx() -> None:
    """Lazy import httpx for type checking compatibility.

    This function ensures httpx is imported at runtime when needed,
    following the lazy import pattern used elsewhere in the CLI.

    Note: The actual httpx usage happens in FastMCP dependencies,
    but we maintain the lazy import pattern in our code.
    """
    import httpx  # noqa: F401


_display: StatusDisplay = get_display()

# Create cyclopts app at module level
app = cyclopts.App(
    "init",
    help="Initialize CodeWeaver configuration and MCP client setup.",
    console=_display.console,
)


def _backup_config(path: Path) -> Path:
    """Create timestamped backup of configuration file.

    Only creates a backup if the file content differs from the most recent backup.

    Args:
        path: Path to configuration file to backup

    Returns:
        Path to backup file (may be existing backup if content unchanged)
    """
    display = _display
    timestamp = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
    backup_path = path.parent / f"{path.stem}.backup_{timestamp}{path.suffix}"

    if not path.exists():
        return backup_path

    # Check for existing backups
    existing_backups = sorted(
        path.parent.glob(f"{path.stem}.backup_*{path.suffix}"),
        key=lambda p: p.stat().st_mtime,
        reverse=True,
    )

    # If we have a recent backup with identical content, reuse it
    current_content = path.read_bytes()
    if existing_backups:
        latest_backup = existing_backups[0]
        if latest_backup.read_bytes() == current_content:
            display.print_info(f"Using existing backup (content unchanged): {latest_backup}")
            return latest_backup

    # Content changed or no backup exists - create new backup
    shutil.copy2(path, backup_path)
    display.print_success(f"Created backup: {backup_path}")

    return backup_path


def _create_codeweaver_config(
    project_path: Path,
    *,
    profile: Literal["recommended", "quickstart", "test"],
    vector_deployment: Literal["local", "cloud"] = "local",
    vector_url: AnyHttpUrl | None = None,
    config_path: Path,
) -> Path:
    """Create CodeWeaver configuration file with defaults or from profile.

    Args:
        project_path: Path to project directory
        profile: Profile name to use ("recommended", "quickstart", "test")
        vector_deployment: Vector store deployment type ("local" or "cloud")
        vector_url: URL for cloud vector deployment (required if vector_deployment="cloud")
        config_path: Custom config file path (defaults to codeweaver.toml in project)

    Returns:
        Path to created configuration file
    """
    display = _display

    config_path.parent.mkdir(parents=True, exist_ok=True)
    from codeweaver.config.profiles import get_profile

    deployment_profile = (
        get_profile("backup" if profile == "test" else profile, vector_deployment, url=vector_url)  # ty: ignore[no-matching-overload]
        if profile
        else None
    )  # ty: ignore[no-matching-overload]
    from codeweaver.config.settings import get_settings, update_settings

    settings = get_settings()
    # Don't pass config_file when creating a new config - the file doesn't exist yet
    _settings_view = update_settings(
        **({"project_path": project_path} | (deployment_profile or {}))  # type: ignore
    )
    # The reference should reflect the updated settings, but we'll refetch to be sure
    settings = get_settings()

    # Save to TOML file
    settings.save_to_file(config_path)

    display.print_success(f"Created configuration file: {config_path}")
    if profile:
        display.print_info(f"Profile: {profile}")

    return config_path


@app.command
def config(
    *,
    project: Annotated[Path | None, cyclopts.Parameter(name=["--project", "-p"])] = None,
    profile: Annotated[
        Literal["recommended", "quickstart", "test"],
        cyclopts.Parameter(
            name=["--profile"],
            help="Configuration profile to use (recommended, quickstart, or test)",
        ),
    ] = "recommended",
    quickstart: Annotated[
        bool,
        cyclopts.Parameter(
            name=["--quickstart"],
            help="Use the quickstart local-only profile instead of the recommended profile.",
        ),
    ] = False,
    vector_deployment: Annotated[
        Literal["local", "cloud"],
        cyclopts.Parameter(name=["--vector-deployment"], help="Vector store deployment type"),
    ] = "local",
    vector_url: Annotated[
        str | None,
        cyclopts.Parameter(
            name=["--vector-url"],
            help="URL for cloud vector deployment (required if --vector-deployment=cloud)",
        ),
    ] = None,
    config_path: Annotated[
        Path | None,
        cyclopts.Parameter(
            name=["--config-path"],
            help="Custom path for configuration file (defaults to codeweaver.toml in project root)",
        ),
    ] = None,
    config_extension: Annotated[
        Literal["toml", "yaml", "yml", "json"], cyclopts.Parameter(name=["--config-extension"])
    ] = "toml",
    config_level: Annotated[
        Literal["local", "project", "user"],
        cyclopts.Parameter(
            name=["--config-level"],
            help="Configuration level. Local configs (which end in 'local') should be gitignored and are for personal use. Project-level are for shared configuration in a repository and should not be gitignored. User-level are for personal configurations across multiple projects.",
        ),
    ] = "project",
    force: Annotated[bool, cyclopts.Parameter(name=["--force", "-f"])] = False,
) -> None:
    """Set up CodeWeaver configuration file.

    Args:
        project: Path to project directory (defaults to current directory)
        profile: Configuration profile to use (recommended, quickstart, or backup)
        vector_deployment: Vector store deployment type (local or cloud)
        vector_url: URL for cloud vector deployment
        config_path: Custom path for configuration file
        force: Overwrite existing configuration file
    """
    display = _display
    error_handler = CLIErrorHandler(display)

    display.print_command_header("init config", "Initialize CodeWeaver configuration file.")

    if quickstart:
        profile = "quickstart"

    # Validate vector_url if cloud deployment
    project_path = project or resolve_project_root()
    parsed_vector_url: AnyHttpUrl | None = None
    if vector_deployment == "cloud" and not vector_url:
        error_handler.handle_error(
            CodeWeaverError(
                "Vector URL is required for cloud vector deployment. "
                "Please provide a valid --vector-url when using --vector-deployment=cloud."
            ),
            "Configuration validation",
            exit_code=1,
        )

    if not config_path:
        if config_level == "local":
            config_path = project_path / f"codeweaver.local.{config_extension}"
        elif config_level == "project":
            config_path = project_path / f"codeweaver.{config_extension}"
        else:
            config_path = get_user_config_dir() / f"codeweaver.{config_extension}"

    if not project_path.is_dir():
        error_handler.handle_error(
            CodeWeaverError(
                f"Project path is not a directory: {project_path}. "
                "Please provide a valid project path."
            ),
            "Project validation",
            exit_code=1,
        )

    display.console.print(f"[dim]Project:[/dim] {project_path}\n")

    # Determine final config path
    final_config_path = config_path or project_path / f"codeweaver.{config_extension}"

    if final_config_path.exists() and not force:
        if Confirm.ask(
            f"[yellow]Configuration file already exists at {final_config_path}. Overwrite?[/yellow]",
            default=False,
        ):
            created_path = _create_codeweaver_config(
                project_path,
                profile=profile,
                vector_deployment=vector_deployment,
                vector_url=parsed_vector_url,
                config_path=final_config_path,
            )
            display.print_success(f"Config created: {created_path}\n")
        else:
            display.print_warning("Skipping CodeWeaver config creation.\n")
    else:
        created_path = _create_codeweaver_config(
            project_path,
            profile=profile,
            vector_deployment=vector_deployment,
            vector_url=parsed_vector_url,
            config_path=final_config_path,
        )
        display.print_completion(f"Config created: {created_path}\n")


def _get_client_config_path(
    client: MCPClient, config_level: Literal["project", "user"], project_path: Path
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
            return get_user_config_dir(base_only=True) / "mcp" / "mcp.json"

        case "claude_code":
            if config_level == "project":
                return project_path / ".claude" / "mcp.json"
            return _get_user_config_path(sys, "claude-code", "mcp.json", os)
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
            return _get_user_config_path(sys, "Claude", "claude_desktop_config.json", os)


def _get_user_config_path(sys, provider: str, file_name: str, os):
    """Get user config path for specific provider based on OS."""
    from codeweaver.common.utils.utils import get_user_config_dir

    user_configdir = get_user_config_dir(base_only=True)
    return user_configdir / provider / file_name


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
        args: Arguments for the command (default: ["server"])
        env: Environment variables for the process
        timeout: Connection timeout in seconds
        authentication: Authentication configuration
        transport: Transport type (always "stdio")

    Returns:
        StdioCodeWeaverConfig instance
    """
    from codeweaver.config.mcp import StdioCodeWeaverConfig

    # Build the command - CodeWeaver doesn't need uv environment
    # stdio is the default transport, so we just run: cw server
    command = cmd or "codeweaver"
    command_args = args or ["server"]

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
    auth: str | Literal["oauth"] | Any | None = None,  # httpx.Auth at runtime
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
    client: MCPClient,
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

    display = _display
    error_handler = CLIErrorHandler(display)

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
                display.print_warning(
                    f"Could not parse existing config file at {config_path!s}. Creating new one. Error: {e}"
                )
                # Create new empty config
                config_file = MCPConfig.model_validate({"mcpServers": {}})
        else:
            # Create new empty config
            config_file = MCPConfig.model_validate({"mcpServers": {}})

        # Add/update cw server in the config
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

        display.print_success(f"MCP config written: {config_path}\n")
        display.print_info("Configuration details:")
        display.console.print(mcp_config.model_dump_json(exclude_none=True, indent=2))

    except ValueError as e:
        error_handler.handle_error(
            CodeWeaverError(f"Configuration error: {e}"), "MCP configuration", exit_code=1
        )
    except Exception as e:
        error_handler.handle_error(e, "MCP configuration write", exit_code=1)


def handle_output(
    mcp_config: StdioCodeWeaverConfig | CodeWeaverMCPConfig,
    output: Literal["write", "print", "copy"],
    config_level: Literal["project", "user"],
    client: MCPClient,
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
    display = _display
    error_handler = CLIErrorHandler(display)

    match output:
        case "write":
            _handle_write_output(mcp_config, config_level, client, file_path, project_path)
        case "print":
            display.print_info("MCP Client Configuration:")
            display.console.print(mcp_config.model_dump_json(indent=2))
        case "copy":
            try:
                import pyperclip

                pyperclip.copy(mcp_config.model_dump_json())
                display.print_success("MCP configuration copied to clipboard.")
            except ImportError:
                error_handler.handle_error(
                    CodeWeaverError(
                        "pyperclip not installed. Cannot copy to clipboard. "
                        "Install with: pip install pyperclip"
                    ),
                    "Clipboard operation",
                    exit_code=1,
                )


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
    clients: Annotated[
        list[MCPClient] | None,
        cyclopts.Parameter(
            name=["--client", "-c"],
            consume_multiple=True,
            help="MCP client to configure, you can provide multiple clients by repeating this flag. Defaults to 'mcpjson' if none specified.",
        ),
    ] = None,
    host: Annotated[str, cyclopts.Parameter(name=["--host"])] = "http://127.0.0.1",
    port: Annotated[int, cyclopts.Parameter(name=["--port"])] = 9328,
    transport: Annotated[
        Literal["stdio", "streamable-http"],
        cyclopts.Parameter(
            name=["--transport", "-t"],
            help="Transport type for MCP communication",
            show_default=True,
            show_choices=True,
        ),
    ] = "stdio",
    timeout: Annotated[
        int,
        cyclopts.Parameter(
            name=["--timeout"], help="Timeout in seconds for MCP client connections"
        ),
    ] = 120,
    auth: Annotated[
        str | Literal["oauth"] | Any | None,
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
            name=["--env"], help="**stdio-only** Environment variables for MCP client process"
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
    - `stdio` (default): Standard input/output transport that proxies to the HTTP backend
    - `streamable-http`: Direct HTTP-based transport for persistent server connections

    **Tip**: Set a default MCP config in your CodeWeaver config, then just run
    `cw init mcp --client your_client --client another_client` to generate the config for those clients.

    Args:
        clients: MCP clients to configure (claude_code, claude_desktop, cursor, vscode, gemini_cli, mcpjson)
        output: Output method for MCP client configuration
        project: Path to project directory (auto-detected if not provided)
        config_level: Configuration level (project or user)
        transport: Transport type for MCP communication

        host: [http-only] Server host address (default: http://127.0.0.1)
        port: [http-only] Server port (default: 9328)
        auth: [http-only] Authentication method

        cmd: [stdio-only] Command to start MCP server process (default: "codeweaver")
        args: [stdio-only] Arguments for the command (default: ["server"])
        env: [stdio-only] Environment variables for the process

        timeout: Timeout in seconds for connections
        authentication: Authentication configuration
        file_path: Custom file path for configuration output
    """
    if clients is None:
        clients = ["mcpjson"]
    display = _display
    display.print_command_header("init mcp", "Initialize MCP client configuration for CodeWeaver.")
    display.print_section("MCP Client Configuration Setup")

    # Determine project path
    project_path = project or resolve_project_root()
    project_path = Path(project_path).resolve()
    display.console.print(f"[dim]Project:[/dim] {project_path}\n")

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
        display.console.print("[dim]Transport:[/dim] stdio (launches CodeWeaver per-session)\n")
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
        display.console.print(
            f"[dim]Transport:[/dim] streamable-http (connects to {host}:{port})\n"
        )

    # Handle output
    for client in clients:
        handle_output(config, output, config_level, client, file_path, project_path)


@app.default
def init(
    *,
    project: Annotated[Path | None, cyclopts.Parameter(name=["--project", "-p"])] = None,
    config_only: Annotated[bool, cyclopts.Parameter(name=["--config-only"])] = False,
    mcp_only: Annotated[bool, cyclopts.Parameter(name=["--mcp-only"])] = False,
    quickstart: Annotated[bool, cyclopts.Parameter(name=["--quickstart", "-q"])] = False,
    profile: Annotated[
        Literal["recommended", "quickstart", "test"],
        cyclopts.Parameter(
            name=["--profile"],
            help="Configuration profile to use (recommended, quickstart, or test). Defaults to 'recommended' with --recommended.",
        ),
    ] = "recommended",
    vector_deployment: Annotated[
        Literal["local", "cloud"],
        cyclopts.Parameter(name=["--vector-deployment"], help="Vector store deployment type"),
    ] = "local",
    vector_url: Annotated[
        str | None,
        cyclopts.Parameter(
            name=["--vector-url"],
            help="URL for cloud vector deployment (required if --vector-deployment=cloud)",
        ),
    ] = None,
    clients: Annotated[
        list[MCPClient] | None,
        cyclopts.Parameter(
            name=["--client", "-c"],
            help="MCP clients to configure. Defaults to 'mcpjson' if none specified. You can provide multiple clients by repeating this flag.",
            consume_multiple=True,
        ),
    ] = None,
    host: Annotated[
        str, cyclopts.Parameter(name=["--host"], help="CodeWeaver server host")
    ] = "http://127.0.0.1",
    port: Annotated[int, cyclopts.Parameter(name=["--port"], help="CodeWeaver server port")] = 9328,
    force: Annotated[
        bool, cyclopts.Parameter(name=["--force", "-f"], help="Force overwrite existing config")
    ] = False,
    transport: Annotated[
        Literal["stdio", "streamable-http"], cyclopts.Parameter(name=["--transport", "-t"])
    ] = "stdio",
    config_extension: Annotated[
        Literal["toml", "yaml", "yml", "json"], cyclopts.Parameter(name=["--config-extension"])
    ] = "toml",
    config_path: Annotated[
        Path | None,
        cyclopts.Parameter(
            name=["--config-path"], help="Custom path for CodeWeaver configuration file"
        ),
    ] = None,
    mcp_config_level: Annotated[
        Literal["project", "user"],
        cyclopts.Parameter(
            name=["--mcp-config-level"],
            help="The level of mcp configuration to write to (project or user)",
        ),
    ] = "project",
    config_level: Annotated[
        Literal["local", "project", "user"],
        cyclopts.Parameter(
            name=["--config-level"],
            help="Configuration level for CodeWeaver config (local, project, or user)",
        ),
    ] = "project",
) -> None:
    """Initialize CodeWeaver configuration and MCP client setup.

    This command sets up both the CodeWeaver configuration file and the MCP client configuration
    in one step. It does not expose all available options; if you want more control, use the
    `cw init config` and `cw init mcp` commands directly.

    By default, creates both CodeWeaver config and MCP client config.
    Use --config-only or --mcp-only to create just one.

    ARCHITECTURE NOTE:
    CodeWeaver uses STDIO transport by default, which proxies to the HTTP backend daemon.
    This means:
    - Start the daemon first: `cw start` (runs background services + HTTP backend)
    - MCP clients connect via stdio, which proxies to the daemon
    - Single server instance shared across all clients
    - Background indexing persists between client sessions

    You can use --transport streamable-http for direct HTTP connections.

    Args:
        project: Path to project directory (defaults to current directory)
        config_only: Only create CodeWeaver config file
        mcp_only: Only create MCP client config
        quick: Use recommended profile with defaults
        profile: Configuration profile to use (recommended, quickstart, or test)
        vector_deployment: Vector store deployment type (local or cloud)
        vector_url: URL for cloud vector deployment
        clients: MCP clients to configure (claude_code, claude_desktop, cursor, gemini_cli, vscode, mcpjson).
        host: Server host address for MCP config (default: 127.0.0.1)
        port: Server port for MCP config (default: 9328)
        transport: Transport type (stdio or streamable-http). Stdio is default and recommended.
        config_level: Configuration level (project or user)
        force: Overwrite existing configurations

    Examples:
        cw init --quickstart              # Full setup with quickstart profile (free/offline)
        cw init                           # Full setup with recommended profile
        cw init --config-only             # Just config file
        cw init --mcp-only                # Just MCP client config
        cw init --client cursor           # Setup for Cursor
        cw init --transport streamable-http  # Use direct HTTP transport
    """
    if clients is None:
        clients = ["mcpjson"]
    display = _display
    error_handler = CLIErrorHandler(display)

    display.print_command_header(
        "init", "Create a CodeWeaver config and/or add CodeWeaver to your MCP clients."
    )

    if quickstart:
        profile = "quickstart"

    # Determine project path
    project_path = (project or resolve_project_root()).resolve()
    if not project_path.exists():
        error_handler.handle_error(
            CodeWeaverError(f"Project path does not exist: {project_path}"),
            "Project validation",
            exit_code=1,
        )

    if not project_path.is_dir():
        error_handler.handle_error(
            CodeWeaverError(f"Path is not a directory: {project_path}"),
            "Project validation",
            exit_code=1,
        )

    display.print_info(f"Project: {project_path}\n")

    # Default: do both if neither flag specified
    # This makes 'cw init' do the full setup by default, so the 'only' here are a little misleading because both 'only' are true now.
    if not config_only and not mcp_only:
        config_only = mcp_only = True

    # Part 1: CodeWeaver Configuration
    if config_only:
        display.print_section("Step 1: CodeWeaver Configuration")

        config(
            project=project_path,
            profile=profile,
            quickstart=quickstart,
            vector_deployment=vector_deployment,
            vector_url=vector_url,
            force=force,
            config_level=config_level,
            config_extension=config_extension,
            config_path=config_path,
        )

    # Part 2: MCP Client Configuration
    # if client args were passed, then we count that as a 'mcp_only' request
    if mcp_only or (len(clients) > 1) or (clients and clients[0] != "mcpjson"):
        display.print_section("Step 2: MCP Client Configuration")

        # Call the mcp() command directly with the provided parameters
        try:
            mcp(
                output="write",
                project=project_path,
                config_level=mcp_config_level,
                clients=clients,
                host=host,
                port=port,
                transport=transport,
            )
        except Exception as e:
            error_handler.handle_error(e, "MCP configuration", exit_code=1)

    # Final Instructions
    display.print_section("Setup Complete!")
    if mcp_only:
        display.print_completion("MCP client configuration created successfully.\n")
    if config_only:
        display.print_completion("CodeWeaver configuration created successfully.\n")
        display.print_list(
            [
                "Set VOYAGE_API_KEY environment variable:\n    [dim]export VOYAGE_API_KEY='your-api-key'[/dim]",
                "Start the server: [dim]cw server[/dim]",
                "Test with a query: [dim]codeweaver search 'authentication configuration'[/dim]",
            ],
            title="Next Steps:",
            numbered=True,
        )
    if transport == "stdio":
        display.print_list(
            [
                "CodeWeaver uses stdio transport that proxies to the HTTP backend daemon.",
                "Start the daemon first: [dim]cw start[/dim]",
                "MCP clients will connect via stdio, sharing the same indexed codebase.",
                "Background indexing persists between client sessions.",
            ],
            title="Important Notes:",
        )

    else:
        display.print_list(
            [
                "CodeWeaver is configured for direct HTTP streaming transport.",
                "Ensure the CodeWeaver server is running before starting your MCP client.",
                "Start the server: [dim]cw server --transport streamable-http[/dim]",
                "Background indexing will persist between client sessions.",
            ],
            title="Important Notes:",
        )

    display.print_section("Using CodeWeaver")
    display.print_list(
        [
            "We recommend you start the daemon while you code: [dim]cw start[/dim]",
            "You can use a tool like `mise` to automatically start the daemon when you enter your project directory.",
            "Or, just get in the habit of running [dim]cw start[/dim] when you start coding.",
            "You can use CodeWeaver to search your codebase outside of an MCP client with [dim]codeweaver search[/dim]",
            "Check status with [dim]cw status[/dim]",
            "To check your config setup, run [dim]codeweaver doctor[/dim]",
            "[red]CodeWeaver is in Alpha. There are bugs.[/red] Help us by reporting them: https://github.com/knitli/codeweaver/issues",
        ],
        title="Tips for Best Experience:",
    )


def main() -> None:
    """CLI entry point for init command."""
    display = _display
    error_handler = CLIErrorHandler(display)

    try:
        app()
    except KeyboardInterrupt:
        display.print_warning("Looks like you cancelled the operation. Exiting.")
        sys.exit(0)
    except Exception as e:
        error_handler.handle_error(e, "Init command", exit_code=1)


if __name__ == "__main__":
    main()


__all__ = ("app",)
