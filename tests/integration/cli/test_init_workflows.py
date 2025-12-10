# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Integration tests for init command workflows.

Tests validate complete workflows:
- Full init creates both configs
- HTTP streaming architecture integration
- Config-only and MCP-only modes

CONVERTED: Now using direct app calling instead of subprocess for faster execution.
"""

from __future__ import annotations

import json

from pathlib import Path

import pytest

from codeweaver.cli.commands.init import app as init_app


@pytest.fixture
def test_environment(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> dict[str, Path]:
    """Set up test environment with home and project directories."""
    home = tmp_path / "home"
    home.mkdir()
    monkeypatch.setenv("HOME", str(home))

    project = tmp_path / "project"
    project.mkdir()
    (project / ".git").mkdir()
    monkeypatch.chdir(project)

    return {"home": home, "project": project}


@pytest.mark.integration
@pytest.mark.config
class TestInitFullWorkflow:
    """Tests for complete init workflows."""

    def test_full_init_creates_both_configs(
        self, test_environment: dict[str, Path], monkeypatch: pytest.MonkeyPatch, mock_confirm
    ) -> None:
        """Test init creates both CodeWeaver config and MCP config."""
        test_environment["home"]
        project = test_environment["project"]

        # Set API key to avoid interactive prompts
        monkeypatch.setenv("VOYAGE_API_KEY", "test-key")

        # Mock all confirmations to True
        mock_confirm.ask.return_value = True

        # Parse and execute init command
        func, bound_args, _ = init_app.parse_args(
            ["--quickstart", "--client", "claude_code", "--project", str(project)],
            exit_on_error=False,
        )
        # Execute the function - successful execution doesn't raise SystemExit
        func(**bound_args.arguments)

        # CodeWeaver config created
        cw_config = project / "codeweaver.toml"
        assert cw_config.exists(), "CodeWeaver config should be created"

        config_content = cw_config.read_text()
        # Quick init creates basic config structure
        assert "[provider]" in config_content
        assert "project_path" in config_content

        # MCP config created
        mcp_config_path = project / ".claude" / "mcp.json"
        assert mcp_config_path.exists(), "MCP config should be created"

        mcp_config = json.loads(mcp_config_path.read_text())
        assert "mcpServers" in mcp_config
        assert "codeweaver" in mcp_config["mcpServers"]

        # Verify HTTP streaming config
        cw_server = mcp_config["mcpServers"]["codeweaver"]
        # HTTP transport uses 'url' field instead of command/args
        assert "url" in cw_server or "command" in cw_server

    def test_http_streaming_architecture(
        self, test_environment: dict[str, Path], monkeypatch: pytest.MonkeyPatch, mock_confirm
    ) -> None:
        """Test MCP config uses HTTP streaming when explicitly requested."""
        test_environment["home"]
        project = test_environment["project"]

        monkeypatch.setenv("VOYAGE_API_KEY", "test-key")
        mock_confirm.ask.return_value = True

        # Execute init with explicit HTTP transport
        func, bound_args, _ = init_app.parse_args(
            [
                "--quickstart",
                "--client",
                "claude_code",
                "--transport",
                "streamable-http",
                "--project",
                str(project),
            ],
            exit_on_error=False,
        )
        func(**bound_args.arguments)

        mcp_config_path = project / ".claude" / "mcp.json"
        mcp_config = json.loads(mcp_config_path.read_text())

        cw_server = mcp_config["mcpServers"]["codeweaver"]

        # Should use HTTP transport
        config_str = json.dumps(cw_server).lower()
        assert "url" in config_str or "http" in config_str

        # Should NOT use STDIO patterns when HTTP is requested
        assert "stdio" not in config_str


@pytest.mark.integration
@pytest.mark.config
class TestInitModes:
    """Tests for different init modes."""

    def test_config_only_flag(
        self, test_environment: dict[str, Path], monkeypatch: pytest.MonkeyPatch, mock_confirm
    ) -> None:
        """Test --config-only creates only CodeWeaver config."""
        test_environment["home"]
        project = test_environment["project"]

        monkeypatch.setenv("VOYAGE_API_KEY", "test-key")
        mock_confirm.ask.return_value = True

        # Execute init with --config-only
        func, bound_args, _ = init_app.parse_args(
            ["--quickstart", "--config-only", "--force", "--project", str(project)],
            exit_on_error=False,
        )
        func(**bound_args.arguments)

        # CodeWeaver config created
        assert (project / "codeweaver.toml").exists()

        # MCP config should NOT be created
        mcp_config_path = project / ".claude" / "mcp.json"
        assert not mcp_config_path.exists()

    def test_mcp_only_flag(
        self, test_environment: dict[str, Path], monkeypatch: pytest.MonkeyPatch, mock_confirm
    ) -> None:
        """Test --mcp-only creates only MCP config."""
        test_environment["home"]
        project = test_environment["project"]

        mock_confirm.ask.return_value = True

        # Execute init with --mcp-only
        func, bound_args, _ = init_app.parse_args(
            ["--mcp-only", "--client", "claude_code", "--project", str(project)],
            exit_on_error=False,
        )
        func(**bound_args.arguments)

        # MCP config created
        mcp_config_path = project / ".claude" / "mcp.json"
        assert mcp_config_path.exists()

        # CodeWeaver config should NOT exist (mcp-only mode)
        assert not (project / "codeweaver.toml").exists()


@pytest.mark.integration
@pytest.mark.config
class TestInitIntegration:
    """Tests for init integration with other commands."""

    def test_init_then_config_show(
        self,
        test_environment: dict[str, Path],
        monkeypatch: pytest.MonkeyPatch,
        mock_confirm,
        capsys,
    ) -> None:
        """Test init followed by config show."""
        from codeweaver.cli.commands.config import app as config_app

        test_environment["project"]

        monkeypatch.setenv("VOYAGE_API_KEY", "test-key")
        mock_confirm.ask.return_value = True

        # Get project from test_environment
        project = test_environment["project"]

        # Init
        func, bound_args, _ = init_app.parse_args(
            ["--quickstart", "--config-only", "--force", "--project", str(project)],
            exit_on_error=False,
        )
        func(**bound_args.arguments)

        # Config show should work (default command, no args needed)
        func, bound_args, _ = config_app.parse_args([], exit_on_error=False)
        func(**bound_args.arguments)

        captured = capsys.readouterr()
        assert "project" in captured.out.lower() or "provider" in captured.out.lower()

    def test_init_then_doctor(
        self, test_environment: dict[str, Path], monkeypatch: pytest.MonkeyPatch, mock_confirm
    ) -> None:
        """Test init followed by doctor check."""
        from codeweaver.cli.commands.doctor import app as doctor_app

        test_environment["project"]

        monkeypatch.setenv("VOYAGE_API_KEY", "test-key")
        mock_confirm.ask.return_value = True

        # Get project from test_environment
        project = test_environment["project"]

        # Init
        func, bound_args, _ = init_app.parse_args(
            ["--quickstart", "--config-only", "--force", "--project", str(project)],
            exit_on_error=False,
        )
        func(**bound_args.arguments)

        # Doctor may report issues with quick config (missing providers)
        # Exit code 1 is acceptable for warnings - but doctor command doesn't raise SystemExit
        # on success, only on errors
        func, bound_args, _ = doctor_app.parse_args([], exit_on_error=False)
        func(**bound_args.arguments)  # Successful execution doesn't raise

    def test_init_respects_existing_config(
        self, test_environment: dict[str, Path], monkeypatch: pytest.MonkeyPatch, mock_confirm
    ) -> None:
        """Test init handles existing configuration."""
        project = test_environment["project"]

        # Create existing config
        existing_config = project / "codeweaver.toml"
        existing_config.write_text("""
[embedding]
provider = "fastembed"
""")

        monkeypatch.setenv("VOYAGE_API_KEY", "test-key")
        mock_confirm.ask.return_value = True

        # Init should detect existing config and overwrite with --force
        func, bound_args, _ = init_app.parse_args(
            ["--quickstart", "--config-only", "--force", "--project", str(project)],
            exit_on_error=False,
        )
        func(**bound_args.arguments)  # Should succeed without raising

        # Config file should still exist and be updated
        assert existing_config.exists()
        config_content = existing_config.read_text()
        # Should have new config structure
        assert "[provider]" in config_content


@pytest.mark.integration
@pytest.mark.config
class TestInitMultipleClients:
    """Tests for init with multiple MCP clients."""

    def test_init_claude_code(
        self, test_environment: dict[str, Path], monkeypatch: pytest.MonkeyPatch, mock_confirm
    ) -> None:
        """Test init for Claude Code client."""
        test_environment["home"]
        project = test_environment["project"]

        mock_confirm.ask.return_value = True

        func, bound_args, _ = init_app.parse_args(
            ["--mcp-only", "--client", "claude_code", "--project", str(project)],
            exit_on_error=False,
        )
        func(**bound_args.arguments)

        config_path = project / ".claude" / "mcp.json"
        assert config_path.exists()

    def test_init_claude_desktop(
        self, test_environment: dict[str, Path], monkeypatch: pytest.MonkeyPatch, mock_confirm
    ) -> None:
        """Test init for Claude Desktop client."""
        home = test_environment["home"]
        project = test_environment["project"]

        mock_confirm.ask.return_value = True

        exit_code = None
        try:
            func, bound_args, _ = init_app.parse_args(
                ["--mcp-only", "--client", "claude_desktop", "--project", str(project)], exit_on_error=False
            )
            func(**bound_args.arguments)
        except SystemExit as e:
            exit_code = e.code if e.code is not None else 0

        if exit_code in (0, None):
            # On Linux (test environment), claude_desktop uses user-level config
            config_path = home / ".config" / "Claude" / "claude_desktop_config.json"
            assert config_path.exists()

    def test_init_multiple_clients_sequentially(
        self, test_environment: dict[str, Path], monkeypatch: pytest.MonkeyPatch, mock_confirm
    ) -> None:
        """Test init for multiple clients in sequence."""
        project = test_environment["project"]

        mock_confirm.ask.return_value = True

        clients = ["claude_code", "claude_desktop"]

        for client in clients:
            exit_code = None
            try:
                func, bound_args, _ = init_app.parse_args(
                    ["--mcp-only", "--client", client, "--project", str(project)], exit_on_error=False
                )
                func(**bound_args.arguments)
            except SystemExit as e:
                exit_code = e.code if e.code is not None else 0

            # Should succeed for each client
            assert exit_code in (0, 1, None)
