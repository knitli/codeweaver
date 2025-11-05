# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Init-related CLI commands for CodeWeaver.

Adds CodeWeaver MCP server configuration to various MCP clients.
"""

from __future__ import annotations

import json
import os
import platform
import shutil
import sys

from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def _get_config_paths() -> dict[str, Path | None]:
    """Get configuration file paths for various MCP clients based on OS.

    Returns:
        Dictionary mapping client names to their config file paths.
        Returns None for paths that don't apply to the current OS.
    """
    system = platform.system()
    home = Path.home()

    paths: dict[str, Path | None] = {}

    # Claude Code - cross-platform
    paths["claude_code"] = home / ".config" / "claude" / "claude_code_config.json"

    # Claude Desktop - OS-specific
    if system == "Darwin":  # macOS
        paths["claude_desktop"] = (
            home / "Library" / "Application Support" / "Claude" / "claude_desktop_config.json"
        )
    elif system == "Windows":
        appdata = Path(os.environ.get("APPDATA", home / "AppData" / "Roaming"))
        paths["claude_desktop"] = appdata / "Claude" / "claude_desktop_config.json"
    else:  # Linux - Claude Desktop not officially supported but some use Wine
        paths["claude_desktop"] = None

    # Cursor - cross-platform, check both project and home directory
    project_cursor = Path.cwd() / ".cursor" / "config.json"
    home_cursor = home / ".cursor" / "config.json"
    paths["cursor"] = project_cursor if project_cursor.parent.exists() else home_cursor

    # Gemini CLI - based on typical CLI tool config patterns
    # Note: As of 2025, Google's Gemini CLI MCP configuration is not well documented.
    # This assumes XDG-style config location pending official documentation.
    if system == "Windows":
        paths["gemini_cli"] = None  # Not typically available on Windows
    else:
        xdg_config = Path(os.environ.get("XDG_CONFIG_HOME", home / ".config"))
        paths["gemini_cli"] = xdg_config / "gemini" / "mcp_config.json"

    return paths


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
        print(f"⚠️  Warning: Config file exists but contains invalid JSON: {path}")
        print(f"   Error: {e}")
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
        print(f"✅ Created backup: {backup_path}")

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


def _create_codeweaver_config(project_path: Path) -> dict[str, Any]:
    """Create CodeWeaver MCP server configuration entry.

    Args:
        project_path: Path to project directory for CodeWeaver to index

    Returns:
        Dictionary containing CodeWeaver MCP server configuration
    """
    return {
        "command": "fastmcp",
        "args": ["run", "codeweaver.server.server:app"],
        "env": {
            "CODEWEAVER_PROJECT_PATH": str(project_path.resolve())
        }
    }


def _merge_mcp_config(
    existing: dict[str, Any],
    project_path: Path,
    *,
    force: bool = False
) -> tuple[dict[str, Any], bool]:
    """Merge CodeWeaver configuration into existing MCP config.

    Args:
        existing: Existing configuration dictionary
        project_path: Path to project for CodeWeaver
        force: Whether to overwrite existing CodeWeaver configuration

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
            print("⚠️  CodeWeaver already configured. Use --force to overwrite.")
            return config, False
        print("🔄 Overwriting existing CodeWeaver configuration (--force enabled)")

    # Add or update CodeWeaver configuration
    config["mcpServers"]["codeweaver"] = _create_codeweaver_config(project_path)

    return config, True


def _add_to_client(
    client_name: str,
    config_path: Path | None,
    project_path: Path,
    *,
    force: bool = False
) -> bool:
    """Add CodeWeaver configuration to specific MCP client.

    Args:
        client_name: Name of the MCP client
        config_path: Path to client's configuration file
        project_path: Path to project for CodeWeaver
        force: Whether to overwrite existing configuration

    Returns:
        True if configuration was added/updated, False otherwise
    """
    if config_path is None:
        print(f"❌ {client_name}: Not supported on {platform.system()}")
        return False

    print(f"\n📝 Configuring {client_name}...")
    print(f"   Config: {config_path}")

    try:
        # Load existing configuration
        existing_config = _load_json_config(config_path)

        # Backup if file exists
        if config_path.exists():
            _backup_config(config_path)

        # Merge CodeWeaver configuration
        merged_config, changed = _merge_mcp_config(existing_config, project_path, force=force)

        if not changed:
            return False

        # Save updated configuration
        _save_json_config(config_path, merged_config)

        print(f"✅ {client_name}: Successfully configured!")

    except json.JSONDecodeError:
        print(f"❌ {client_name}: Failed due to invalid JSON in config file")
        return False
    except Exception as e:
        print(f"❌ {client_name}: Failed with error: {e}")
        return False
    else:
        return True


def _print_next_steps(configured_clients: list[str]) -> None:
    """Print next steps after configuration.

    Args:
        configured_clients: List of successfully configured client names
    """
    if not configured_clients:
        print("\n⚠️  No clients were configured. Nothing to do.")
        return

    print("\n" + "="*60)
    print("🎉 Configuration Complete!")
    print("="*60)

    print("\n📋 Next Steps:")
    print("   1. Restart your MCP client(s):")

    for client in configured_clients:
        if client == "claude_desktop":
            print("      • Claude Desktop: Quit completely and relaunch")
        elif client == "claude_code":
            print("      • Claude Code: Restart VS Code or reload window")
        elif client == "cursor":
            print("      • Cursor: Restart Cursor editor")
        elif client == "gemini_cli":
            print("      • Gemini CLI: No restart needed, takes effect on next query")

    print("\n   2. Verify CodeWeaver is loaded:")
    print("      • Look for the hammer icon (🔨) in your MCP client")
    print("      • Check that 'codeweaver' appears in available servers")

    print("\n   3. Test with a query:")
    print("      • Try: 'Find the authentication logic'")
    print("      • Try: 'Show me the database models'")
    print("      • Try: 'Where is the API endpoint for users?'")

    print("\n📚 Troubleshooting:")
    print("   • If server doesn't load, check that 'fastmcp' is in PATH")
    print("   • Verify project path is correct in the config")
    print("   • Check client logs for error messages")
    print("   • See: https://docs.codeweaver.dev/troubleshooting")
    print()


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

    Args:
        project: Path to project directory (defaults to current directory)
        claude_code: Add to Claude Code configuration
        claude_desktop: Add to Claude Desktop configuration
        cursor: Add to Cursor configuration
        gemini_cli: Add to Gemini CLI configuration
        mcp_json: Path to custom MCP JSON config file
        force: Overwrite existing CodeWeaver configuration if present
        all_clients: Configure all available clients
    """
    # Check for fastmcp
    if not (fastmcp_path := shutil.which("fastmcp")):
        print("❌ Error: 'fastmcp' not found in PATH")
        print("   Install with: pip install fastmcp")
        print("   Or: uv tool install fastmcp")
        sys.exit(1)

    print(f"✅ Found fastmcp at: {fastmcp_path}")

    # Determine project path
    project_path = (project or Path.cwd()).resolve()
    if not project_path.exists():
        print(f"❌ Error: Project path does not exist: {project_path}")
        sys.exit(1)

    print(f"📁 Project: {project_path}")

    # Check if any clients specified
    clients_selected = {
        "claude_code": claude_code or all_clients,
        "claude_desktop": claude_desktop or all_clients,
        "cursor": cursor or all_clients,
        "gemini_cli": gemini_cli or all_clients,
    }

    has_custom_mcp_json = mcp_json is not None

    if not any(clients_selected.values()) and not has_custom_mcp_json:
        print("\n❌ Error: You need to specify at least one client to configure!")
        print("\nOptions:")
        print("  --claude-code      Configure Claude Code")
        print("  --claude-desktop   Configure Claude Desktop")
        print("  --cursor          Configure Cursor")
        print("  --gemini-cli      Configure Gemini CLI")
        print("  --mcp-json PATH   Configure custom MCP JSON file")
        print("  --all-clients     Configure all available clients")
        sys.exit(1)

    # Get config paths
    config_paths = _get_config_paths()

    # Configure selected clients
    configured_clients: list[str] = []

    for client_name, should_configure in clients_selected.items():
        if should_configure and _add_to_client(
            client_name,
            config_paths[client_name],
            project_path,
            force=force
        ):
            configured_clients.append(client_name)

    # Handle custom MCP JSON
    if has_custom_mcp_json and mcp_json is not None:
        print(f"\n📝 Configuring custom MCP JSON: {mcp_json}")

        if _add_to_client("mcp_json", mcp_json, project_path, force=force):
            configured_clients.append("mcp_json")

    # Print next steps
    _print_next_steps(configured_clients)
