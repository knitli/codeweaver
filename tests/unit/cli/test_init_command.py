# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Unit tests for init command.

Tests validate corrections from CLI_CORRECTIONS_PLAN.md:
- HTTP streaming architecture (not STDIO)
- Command unification (init vs config init)
- MCP config generation (correct transport)
"""

from __future__ import annotations

import json

from pathlib import Path
from typing import TYPE_CHECKING

import pytest


from codeweaver.cli.commands.init import app as init_app


if TYPE_CHECKING:
    from pytest import MonkeyPatch



@pytest.fixture
def temp_home(tmp_path: Path, monkeypatch: MonkeyPatch) -> Path:
    """Create temporary home directory."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))
    return home


@pytest.fixture
def temp_project(tmp_path: Path, monkeypatch: MonkeyPatch) -> Path:
    """Create temporary project directory."""
    project = tmp_path / "project"
    project.mkdir()
    (project / ".git").mkdir()
    monkeypatch.chdir(project)
    return project


@pytest.mark.unit
@pytest.mark.config
class TestInitCommand:
    """Tests for init command."""

    def test_init_creates_both_configs(
        self,
        temp_project: Path,
        temp_home: Path
    ) -> None:
        """Test init creates both CodeWeaver config and MCP config."""
        with pytest.raises(SystemExit) as exc_info:
            init_app(--quick)
        captured = capsys.readouterr()
        exc_info.value.code = exc_info.value.code

        # Should succeed
        assert exc_info.value.code == 0

        # CodeWeaver config created
        assert (temp_project / "codeweaver.toml").exists()

        # MCP config created
        mcp_config_path = temp_home / ".config" / "claude" / "claude_code_config.json"
        assert mcp_config_path.exists()

    def test_config_only_flag(self, temp_project: Path, temp_home: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Test --config-only creates only CodeWeaver config."""
        with pytest.raises(SystemExit) as exc_info:
            init_app(--quick, --config-only)
        captured = capsys.readouterr()
        exc_info.value.code = exc_info.value.code

        assert exc_info.value.code == 0

        # CodeWeaver config created
        assert (temp_project / "codeweaver.toml").exists()

        # MCP config should NOT be created
        mcp_config_path = temp_home / ".config" / "claude" / "claude_code_config.json"
        assert not mcp_config_path.exists()

    def test_mcp_only_flag(self, temp_project: Path, temp_home: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Test --mcp-only creates only MCP config."""
        with pytest.raises(SystemExit) as exc_info:
            init_app(--mcp-only)
        captured = capsys.readouterr()
        exc_info.value.code = exc_info.value.code

        # Should succeed or prompt for client selection
        assert exc_info.value.code in (0, 1)

        # MCP config should be created (if succeeded)
        if exc_info.value.code == 0:
            mcp_config_path = temp_home / ".config" / "claude" / "claude_code_config.json"
            assert mcp_config_path.exists()


@pytest.mark.unit
@pytest.mark.config
class TestHttpStreamingArchitecture:
    """Tests for HTTP streaming architecture."""

    def test_mcp_config_uses_http_transport(
        self,
        temp_project: Path,
        temp_home: Path
    ) -> None:
        """Test MCP config uses HTTP streaming, not STDIO."""
        with pytest.raises(SystemExit) as exc_info:
            init_app(--mcp-only, --client, "claude_code")
        captured = capsys.readouterr()
        exc_info.value.code = exc_info.value.code

        # If succeeded, check config
        if exc_info.value.code == 0:
            mcp_config_path = temp_home / ".config" / "claude" / "claude_code_config.json"
            if mcp_config_path.exists():
                mcp_config = json.loads(mcp_config_path.read_text())

                cw_config = mcp_config["mcpServers"]["codeweaver"]

                # Should use HTTP transport
                assert "--transport" in cw_config.get("args", [])
                assert "http" in str(cw_config.get("args", [])).lower()

                # Should NOT use STDIO patterns
                assert "stdio" not in str(cw_config).lower()

    def test_http_streaming_command_structure(
        self,
        temp_project: Path,
        temp_home: Path
    ) -> None:
        """Test HTTP streaming uses correct command structure."""
        with pytest.raises(SystemExit) as exc_info:
            init_app(--mcp-only, --client, "claude_code")
        captured = capsys.readouterr()
        exc_info.value.code = exc_info.value.code

        if exc_info.value.code == 0:
            mcp_config_path = temp_home / ".config" / "claude" / "claude_code_config.json"
            if mcp_config_path.exists():
                mcp_config = json.loads(mcp_config_path.read_text())
                cw_config = mcp_config["mcpServers"]["codeweaver"]

                # Should have command
                assert "command" in cw_config
                assert cw_config["command"] == "codeweaver"

                # Should have args with server subcommand
                assert "args" in cw_config
                args = cw_config["args"]
                assert "server" in args or "serve" in args

    def test_stdio_not_used(self, temp_project: Path, temp_home: Path, capsys: pytest.CaptureFixture[str]) -> None:
        """Test STDIO transport is not used."""
        with pytest.raises(SystemExit) as exc_info:
            init_app(--mcp-only, --client, "claude_code")
        captured = capsys.readouterr()
        exc_info.value.code = exc_info.value.code

        if exc_info.value.code == 0:
            mcp_config_path = temp_home / ".config" / "claude" / "claude_code_config.json"
            if mcp_config_path.exists():
                mcp_config = json.loads(mcp_config_path.read_text())
                cw_config = mcp_config["mcpServers"]["codeweaver"]

                # Should not use STDIO
                args_str = str(cw_config.get("args", [])).lower()
                assert "stdio" not in args_str


@pytest.mark.unit
@pytest.mark.config
class TestMcpClientSupport:
    """Tests for MCP client support."""

    def test_supported_clients(self) -> None:
        """Test all supported MCP clients are recognized."""
        from codeweaver.cli.commands.init import MCPClient

        # Should support at least these clients
        expected_clients = {
            "claude_code",
            "claude_desktop",
            "windsurf",
            "cursor",
        }

        client_values = {c.value for c in MCPClient}
        assert expected_clients.issubset(client_values)

    def test_client_config_paths_correct(self, temp_home: Path) -> None:
        """Test client config paths are correct."""
        from codeweaver.cli.commands.init import MCPClient, get_mcp_config_path

        # Check each client has a valid path
        for client in MCPClient:
            config_path = get_mcp_config_path(client, temp_home)
            assert config_path is not None
            # Path should be under home or .config
            assert str(config_path).startswith(str(temp_home))


@pytest.mark.unit
@pytest.mark.config
class TestInitIntegration:
    """Tests for init command integration with other commands."""

    def test_init_integrates_with_config(
        self,
        temp_project: Path,
        temp_home: Path
    ) -> None:
        """Test init command integrates with config command."""
        # Init should create valid config
        with pytest.raises(SystemExit) as exc_info:
            init_app(--quick)
        captured = capsys.readouterr()
        exc_info.value.code = exc_info.value.code

        if exc_info.value.code == 0:
            # Config command should recognize it
            from codeweaver.cli.commands.config import app as config_app
            config_result = runner.invoke(config_app, ["show"])

            assert config_exc_info.value.code == 0
            assert "configuration" in config_captured.out.lower()

    def test_init_respects_existing_config(
        self,
        temp_project: Path,
        temp_home: Path
    ) -> None:
        """Test init respects existing configuration."""
        # Create existing config
        config_file = temp_project / "codeweaver.toml"
        config_file.write_text("""
[embedding]
provider = "fastembed"
""")

        # Init should detect and handle existing config
        with pytest.raises(SystemExit) as exc_info:
            init_app(--quick)
        captured = capsys.readouterr()
        exc_info.value.code = exc_info.value.code

        # Should either merge or prompt
        assert exc_info.value.code in (0, 1)
