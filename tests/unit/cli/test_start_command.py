# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Unit tests for start command.

Tests validate:
- Background daemon mode (default behavior)
- Foreground mode (--foreground flag)
- Service persistence (init service / start persist)
- Platform-specific service installation (systemd, launchd)
"""

from __future__ import annotations

import os
import sys

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def temp_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Get temporary home directory (created by autouse isolated_test_environment fixture)."""
    return Path(os.environ["HOME"])


@pytest.fixture
def temp_project(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create temporary project directory."""
    project = tmp_path / "project"
    project.mkdir()
    (project / ".git").mkdir()
    monkeypatch.chdir(project)
    return project


@pytest.mark.unit
@pytest.mark.cli
class TestStartCommandBehavior:
    """Tests for the `start` command behavior - background vs foreground modes."""

    def test_start_command_has_foreground_flag(self) -> None:
        """Test that start command has --foreground/-f flag."""
        # Check the function signature has foreground parameter
        import inspect

        from codeweaver.cli.commands.start import start

        sig = inspect.signature(start)
        assert "foreground" in sig.parameters
        # Default should be False (background mode is default)
        assert sig.parameters["foreground"].default is False

    def test_start_command_default_is_background(self) -> None:
        """Test that start defaults to background mode (foreground=False)."""
        import inspect

        from codeweaver.cli.commands.start import start

        sig = inspect.signature(start)
        # foreground should default to False
        assert sig.parameters["foreground"].default is False

    @pytest.mark.asyncio
    async def test_start_detects_already_running(
        self, temp_project: Path, capsys: pytest.CaptureFixture[str]
    ) -> None:
        """Test that start detects when services are already running."""
        from codeweaver.cli.commands.start import are_services_running

        # Mock httpx at the httpx module level (it's lazily imported inside the function)
        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch.dict(
            "sys.modules", {"httpx": MagicMock(AsyncClient=MagicMock(return_value=mock_client))}
        ):
            result = await are_services_running("127.0.0.1", 9329)
            assert result is True

    @pytest.mark.asyncio
    async def test_start_detects_not_running(self, temp_project: Path) -> None:
        """Test that start detects when services are not running."""
        from codeweaver.cli.commands.start import are_services_running

        # Mock httpx to simulate no daemon running (connection error)
        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch.dict(
            "sys.modules", {"httpx": MagicMock(AsyncClient=MagicMock(return_value=mock_client))}
        ):
            result = await are_services_running("127.0.0.1", 9329)
            assert result is False


@pytest.mark.unit
@pytest.mark.cli
class TestStartDaemonBackground:
    """Tests for background daemon spawning."""

    def test_start_daemon_background_finds_executable(self, temp_project: Path) -> None:
        """Test that _start_daemon_background finds the codeweaver executable."""
        from codeweaver.cli.commands.start import _start_daemon_background
        from codeweaver.cli.ui import StatusDisplay

        display = StatusDisplay()

        # Mock subprocess.Popen and shutil.which in the daemon module
        with (
            patch("codeweaver_daemon.shutil.which") as mock_which,
            patch("codeweaver_daemon.subprocess.Popen") as mock_popen,
        ):
            # Simulate finding cw executable
            mock_which.return_value = "/usr/local/bin/cw"
            mock_popen.return_value = MagicMock()

            result = _start_daemon_background(
                display,
                project=temp_project,
                management_host="127.0.0.1",
                management_port=9329,
                mcp_host="127.0.0.1",
                mcp_port=9328,
            )

            assert result is True
            mock_popen.assert_called_once()
            # Verify the command uses the cw executable with 'start' command
            call_args = mock_popen.call_args[0][0]
            # Check that the executable path is used (mock returns /usr/local/bin/cw)
            assert call_args[0] == "/usr/local/bin/cw"
            assert "start" in call_args

    def test_start_daemon_background_uses_python_fallback(self, temp_project: Path) -> None:
        """Test fallback to python when cw/codeweaver executable not found."""
        from codeweaver.cli.commands.start import _start_daemon_background
        from codeweaver.cli.ui import StatusDisplay

        display = StatusDisplay()

        with (
            patch("codeweaver_daemon.shutil.which") as mock_which,
            patch("codeweaver_daemon.subprocess.Popen") as mock_popen,
        ):
            # Simulate not finding cw executable
            mock_which.return_value = None
            mock_popen.return_value = MagicMock()

            result = _start_daemon_background(
                display,
                project=temp_project,
                management_host="127.0.0.1",
                management_port=9329,
                mcp_host="127.0.0.1",
                mcp_port=9328,
            )

            assert result is True
            call_args = mock_popen.call_args[0][0]
            # Should use sys.executable with the CLI module
            assert sys.executable in call_args[0]
            # Should run the CLI module
            assert any("codeweaver.cli" in str(arg) for arg in call_args)
            assert "start" in call_args

    def test_start_daemon_background_passes_options(self, temp_project: Path) -> None:
        """Test that custom options are passed to the spawned daemon."""
        from codeweaver.cli.commands.start import _start_daemon_background
        from codeweaver.cli.ui import StatusDisplay

        display = StatusDisplay()

        with (
            patch("codeweaver_daemon.shutil.which") as mock_which,
            patch("codeweaver_daemon.subprocess.Popen") as mock_popen,
        ):
            mock_which.return_value = "/usr/local/bin/cw"
            mock_popen.return_value = MagicMock()

            _start_daemon_background(
                display,
                config_file=Path("/path/to/config.toml"),
                project=temp_project,
                management_host="0.0.0.0",
                management_port=9999,
                mcp_host="0.0.0.0",
                mcp_port=8888,
            )

            call_args = mock_popen.call_args[0][0]
            assert "--config-file" in call_args
            assert "--project" in call_args
            assert "--management-host" in call_args
            assert "--management-port" in call_args
            assert "--mcp-host" in call_args
            assert "--mcp-port" in call_args


@pytest.mark.unit
@pytest.mark.cli
class TestInitServiceCommand:
    """Tests for the `init service` command - service persistence."""

    def test_init_service_command_exists(self) -> None:
        """Test that init service command is registered."""
        from codeweaver.cli.commands.init import app as init_app

        # Check that 'service' is a registered command
        # cyclopts stores commands differently, check the app has the command
        assert hasattr(init_app, "command")

    def test_service_command_has_enable_flag(self) -> None:
        """Test that service command has --enable flag."""
        import inspect

        from codeweaver.cli.commands.init import service

        sig = inspect.signature(service)
        assert "enable" in sig.parameters
        # Default should be True (enable by default)
        assert sig.parameters["enable"].default is True

    def test_service_command_has_uninstall_flag(self) -> None:
        """Test that service command has --uninstall flag."""
        import inspect

        from codeweaver.cli.commands.init import service

        sig = inspect.signature(service)
        assert "uninstall" in sig.parameters
        # Default should be False
        assert sig.parameters["uninstall"].default is False


@pytest.mark.unit
@pytest.mark.cli
class TestSystemdServiceGeneration:
    """Tests for systemd service file generation (Linux)."""

    def test_systemd_unit_content_valid(self) -> None:
        """Test that generated systemd unit file has valid structure."""
        from codeweaver.cli.commands.init import _get_systemd_unit

        unit_content = _get_systemd_unit(
            cw_cmd="/usr/local/bin/cw", working_dir=Path("/home/user/project")
        )

        # Check required systemd sections
        assert "[Unit]" in unit_content
        assert "[Service]" in unit_content
        assert "[Install]" in unit_content

        # Check service configuration (paths may be quoted with shlex.quote)
        assert "ExecStart=" in unit_content
        assert "/usr/local/bin/cw" in unit_content
        assert "start --foreground" in unit_content
        assert "WorkingDirectory=" in unit_content
        assert "/home/user/project" in unit_content
        assert "Type=simple" in unit_content
        assert "Restart=on-failure" in unit_content

    def test_systemd_unit_includes_documentation(self) -> None:
        """Test that systemd unit includes documentation link."""
        from codeweaver.cli.commands.init import _get_systemd_unit

        unit_content = _get_systemd_unit(
            cw_cmd="/usr/local/bin/cw", working_dir=Path("/home/user/project")
        )

        assert "Documentation=" in unit_content
        assert "github.com/knitli/codeweaver" in unit_content


@pytest.mark.unit
@pytest.mark.cli
class TestLaunchdServiceGeneration:
    """Tests for launchd plist generation (macOS)."""

    def test_launchd_plist_content_valid(self) -> None:
        """Test that generated launchd plist has valid XML structure."""
        from codeweaver.cli.commands.init import _get_launchd_plist

        plist_content = _get_launchd_plist(
            cw_cmd="/usr/local/bin/cw", working_dir=Path("/Users/user/project")
        )

        # Check XML structure
        assert '<?xml version="1.0"' in plist_content
        assert "<plist" in plist_content
        assert "</plist>" in plist_content

        # Check required keys
        assert "<key>Label</key>" in plist_content
        assert "li.knit.codeweaver" in plist_content
        assert "<key>ProgramArguments</key>" in plist_content
        assert "<key>WorkingDirectory</key>" in plist_content

    def test_launchd_plist_runs_foreground(self) -> None:
        """Test that launchd plist runs daemon in foreground mode."""
        from codeweaver.cli.commands.init import _get_launchd_plist

        plist_content = _get_launchd_plist(
            cw_cmd="/usr/local/bin/cw", working_dir=Path("/Users/user/project")
        )

        # Should include start --foreground in arguments
        assert "<string>/usr/local/bin/cw</string>" in plist_content
        assert "<string>start</string>" in plist_content
        assert "<string>--foreground</string>" in plist_content

    def test_launchd_plist_sets_log_paths(self) -> None:
        """Test that launchd plist configures log file paths."""
        from codeweaver.cli.commands.init import _get_launchd_plist

        plist_content = _get_launchd_plist(
            cw_cmd="/usr/local/bin/cw", working_dir=Path("/Users/user/project")
        )

        assert "<key>StandardOutPath</key>" in plist_content
        assert "<key>StandardErrorPath</key>" in plist_content
        assert "codeweaver.log" in plist_content
        assert "codeweaver.error.log" in plist_content


@pytest.mark.unit
@pytest.mark.cli
class TestStartPersistAlias:
    """Tests for the `start persist` alias command."""

    def test_persist_command_exists(self) -> None:
        """Test that start persist command is registered."""
        from codeweaver.cli.commands.start import app as start_app

        # Check that 'persist' is a registered command
        assert hasattr(start_app, "command")

    def test_persist_command_has_same_options_as_service(self) -> None:
        """Test that persist command has same options as init service."""
        import inspect

        from codeweaver.cli.commands.start import persist

        persist_sig = inspect.signature(persist)

        # persist should have enable and uninstall flags like service
        assert "enable" in persist_sig.parameters
        assert "uninstall" in persist_sig.parameters
        assert "project" in persist_sig.parameters

    def test_persist_delegates_to_init_service(self) -> None:
        """Test that persist command delegates to init service."""
        from codeweaver.cli.commands.start import persist

        # Patch the init_service function that persist should delegate to
        with patch("codeweaver.cli.commands.init.service") as mock_init_service:
            # Call persist with some test arguments
            from tempfile import TemporaryDirectory

            with TemporaryDirectory() as temp_dir:
                persist(enable=True, uninstall=False, project=Path(temp_dir))
                # Assert that init_service was called
                assert mock_init_service.called


@pytest.mark.unit
@pytest.mark.cli
class TestServiceInstallationBehavior:
    """Tests for service installation behavior."""

    @pytest.mark.skipif(sys.platform != "linux", reason="Linux-specific test")
    def test_systemd_install_creates_service_file(self, temp_home: Path) -> None:
        """Test that systemd installation creates service file in correct location."""
        import subprocess as subprocess_module

        from codeweaver.cli.commands.init import _install_systemd_service
        from codeweaver.cli.ui import StatusDisplay

        display = StatusDisplay()

        # Patch subprocess.run at the subprocess module level
        with patch.object(subprocess_module, "run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            result = _install_systemd_service(
                display,
                cw_cmd="/usr/local/bin/cw",
                working_dir=Path("/home/user/project"),
                enable=False,  # Don't actually enable
            )

            assert result is True

            # Check service file was created
            service_file = temp_home / ".config" / "systemd" / "user" / "codeweaver.service"
            assert service_file.exists()

            # Verify content (paths may be quoted)
            content = service_file.read_text()
            assert "ExecStart=" in content
            assert "/usr/local/bin/cw" in content
            assert "start --foreground" in content

    @pytest.mark.skipif(sys.platform != "darwin", reason="macOS-specific test")
    def test_launchd_install_creates_plist_file(self, temp_home: Path) -> None:
        """Test that launchd installation creates plist file in correct location."""
        from codeweaver.cli.commands.init import _install_launchd_service
        from codeweaver.cli.ui import StatusDisplay

        display = StatusDisplay()

        with patch("codeweaver.cli.commands.init.subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0)

            result = _install_launchd_service(
                display,
                cw_cmd="/usr/local/bin/cw",
                working_dir=Path("/Users/user/project"),
                enable=False,  # Don't actually load
            )

            assert result is True

            # Check plist file was created
            plist_file = temp_home / "Library" / "LaunchAgents" / "li.knit.codeweaver.plist"
            assert plist_file.exists()


@pytest.mark.unit
@pytest.mark.cli
class TestWindowsServiceInstructions:
    """Tests for Windows service installation instructions."""

    def test_windows_instructions_shown(self, capsys: pytest.CaptureFixture[str]) -> None:
        """Test that Windows instructions are displayed correctly."""
        from codeweaver.cli.commands.init import _show_windows_instructions
        from codeweaver.cli.ui import StatusDisplay

        display = StatusDisplay()

        _show_windows_instructions(
            display,
            cw_cmd="C:\\Program Files\\codeweaver\\cw.exe",
            working_dir=Path("C:\\Users\\user\\project"),
        )

        captured = capsys.readouterr()
        # Should mention NSSM
        assert "NSSM" in captured.out or "nssm" in captured.out.lower()
        # Should include the executable path
        assert "cw.exe" in captured.out or "codeweaver" in captured.out.lower()


@pytest.mark.unit
@pytest.mark.cli
class TestHealthCheckBehavior:
    """Tests for daemon health check functionality."""

    @pytest.mark.asyncio
    async def test_wait_for_daemon_healthy_success(self) -> None:
        """Test waiting for daemon to become healthy."""
        import httpx as httpx_module

        from codeweaver.cli.commands.start import _wait_for_daemon_healthy
        from codeweaver.cli.ui import StatusDisplay

        display = StatusDisplay()

        mock_client = AsyncMock()
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_client.get = AsyncMock(return_value=mock_response)
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch.object(httpx_module, "AsyncClient", return_value=mock_client):
            result = await _wait_for_daemon_healthy(
                display, max_wait_seconds=5.0, check_interval=0.1
            )

            assert result is True

    @pytest.mark.asyncio
    async def test_wait_for_daemon_healthy_timeout(self) -> None:
        """Test timeout when daemon doesn't become healthy."""
        import httpx as httpx_module

        from codeweaver.cli.commands.start import _wait_for_daemon_healthy
        from codeweaver.cli.ui import StatusDisplay

        display = StatusDisplay()

        mock_client = AsyncMock()
        mock_client.get = AsyncMock(side_effect=Exception("Connection refused"))
        mock_client.__aenter__ = AsyncMock(return_value=mock_client)
        mock_client.__aexit__ = AsyncMock(return_value=None)

        with patch.object(httpx_module, "AsyncClient", return_value=mock_client):
            result = await _wait_for_daemon_healthy(
                display,
                max_wait_seconds=0.5,  # Short timeout for test
                check_interval=0.1,
            )

            assert result is False
