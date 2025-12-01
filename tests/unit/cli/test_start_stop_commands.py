# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Unit tests for start and stop commands.

Tests validate:
- Daemon process management (PID file handling)
- Start command daemon and foreground modes
- Stop command graceful and forced shutdown
- Process status checking
"""

from __future__ import annotations

import os
import subprocess
import sys
import time

from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest


pytestmark = [pytest.mark.unit, pytest.mark.cli]


@pytest.fixture
def temp_config_dir(tmp_path: Path) -> Path:
    """Create a temporary config directory for PID file tests."""
    config_dir = tmp_path / "codeweaver"
    config_dir.mkdir(parents=True, exist_ok=True)
    return config_dir


@pytest.fixture
def mock_display() -> MagicMock:
    """Create a mock StatusDisplay for testing."""
    display = MagicMock()
    display.print_info = MagicMock()
    display.print_success = MagicMock()
    display.print_warning = MagicMock()
    display.print_error = MagicMock()
    display.print_command_header = MagicMock()
    return display


class TestPidFileManagement:
    """Tests for PID file operations."""

    def test_get_pid_file_path(self, temp_config_dir: Path) -> None:
        """Test PID file path generation."""
        with patch(
            "codeweaver.common.utils.utils.get_user_config_dir", return_value=temp_config_dir
        ):
            from codeweaver.common.utils.procs import get_pid_file_path

            pid_file = get_pid_file_path()
            assert pid_file.parent == temp_config_dir
            assert pid_file.name == "codeweaver.pid"

    def test_write_and_read_pid_file(self, temp_config_dir: Path) -> None:
        """Test writing and reading PID file."""
        with patch(
            "codeweaver.common.utils.utils.get_user_config_dir", return_value=temp_config_dir
        ):
            from codeweaver.common.utils.procs import read_pid_file, write_pid_file

            test_pid = 12345
            pid_file = write_pid_file(test_pid)

            assert pid_file.exists()
            assert read_pid_file() == test_pid

    def test_write_pid_file_current_process(self, temp_config_dir: Path) -> None:
        """Test writing current process PID."""
        with patch(
            "codeweaver.common.utils.utils.get_user_config_dir", return_value=temp_config_dir
        ):
            from codeweaver.common.utils.procs import read_pid_file, write_pid_file

            pid_file = write_pid_file()

            assert pid_file.exists()
            assert read_pid_file() == os.getpid()

    def test_read_pid_file_nonexistent(self, temp_config_dir: Path) -> None:
        """Test reading nonexistent PID file."""
        with patch(
            "codeweaver.common.utils.utils.get_user_config_dir", return_value=temp_config_dir
        ):
            from codeweaver.common.utils.procs import read_pid_file

            assert read_pid_file() is None

    def test_read_pid_file_invalid_content(self, temp_config_dir: Path) -> None:
        """Test reading PID file with invalid content."""
        with patch(
            "codeweaver.common.utils.utils.get_user_config_dir", return_value=temp_config_dir
        ):
            from codeweaver.common.utils.procs import get_pid_file_path, read_pid_file

            pid_file = get_pid_file_path()
            pid_file.write_text("not-a-number")

            assert read_pid_file() is None

    def test_remove_pid_file(self, temp_config_dir: Path) -> None:
        """Test removing PID file."""
        with patch(
            "codeweaver.common.utils.utils.get_user_config_dir", return_value=temp_config_dir
        ):
            from codeweaver.common.utils.procs import (
                get_pid_file_path,
                remove_pid_file,
                write_pid_file,
            )

            write_pid_file(12345)
            assert get_pid_file_path().exists()

            assert remove_pid_file() is True
            assert not get_pid_file_path().exists()

    def test_remove_pid_file_nonexistent(self, temp_config_dir: Path) -> None:
        """Test removing nonexistent PID file."""
        with patch(
            "codeweaver.common.utils.utils.get_user_config_dir", return_value=temp_config_dir
        ):
            from codeweaver.common.utils.procs import remove_pid_file

            assert remove_pid_file() is False


class TestProcessStatus:
    """Tests for process status checking."""

    def test_is_process_running_current(self) -> None:
        """Test checking if current process is running."""
        from codeweaver.common.utils.procs import is_process_running

        # Current process should always be running
        assert is_process_running(os.getpid()) is True

    def test_is_process_running_invalid_pid(self) -> None:
        """Test checking invalid PID."""
        from codeweaver.common.utils.procs import is_process_running

        # Use a very high PID that's unlikely to exist
        assert is_process_running(999999999) is False

    def test_get_daemon_status_not_running(self, temp_config_dir: Path) -> None:
        """Test daemon status when not running."""
        with patch(
            "codeweaver.common.utils.utils.get_user_config_dir", return_value=temp_config_dir
        ):
            from codeweaver.common.utils.procs import get_daemon_status

            is_running, pid = get_daemon_status()
            assert is_running is False
            assert pid is None

    def test_get_daemon_status_stale_pid(self, temp_config_dir: Path) -> None:
        """Test daemon status with stale PID file."""
        with patch(
            "codeweaver.common.utils.utils.get_user_config_dir", return_value=temp_config_dir
        ):
            from codeweaver.common.utils.procs import get_daemon_status, write_pid_file

            # Write a PID that doesn't exist
            write_pid_file(999999999)

            is_running, pid = get_daemon_status()
            assert is_running is False
            assert pid == 999999999


class TestStopCommand:
    """Tests for the stop command."""

    @pytest.mark.asyncio
    async def test_stop_no_daemon_running(
        self, temp_config_dir: Path, mock_display: MagicMock
    ) -> None:
        """Test stop command when no daemon is running."""
        with patch(
            "codeweaver.common.utils.utils.get_user_config_dir", return_value=temp_config_dir
        ):
            from codeweaver.cli.commands.stop import stop_daemon_process

            result = await stop_daemon_process(mock_display)

            assert result is False

    @pytest.mark.asyncio
    async def test_stop_stale_pid_file(
        self, temp_config_dir: Path, mock_display: MagicMock
    ) -> None:
        """Test stop command cleans up stale PID file."""
        with patch(
            "codeweaver.common.utils.utils.get_user_config_dir", return_value=temp_config_dir
        ):
            from codeweaver.cli.commands.stop import stop_daemon_process
            from codeweaver.common.utils.procs import get_pid_file_path, write_pid_file

            # Create stale PID file
            write_pid_file(999999999)
            assert get_pid_file_path().exists()

            result = await stop_daemon_process(mock_display)

            assert result is False
            # Should have cleaned up stale PID file
            assert not get_pid_file_path().exists()


class TestStartCommand:
    """Tests for the start command."""

    def test_start_daemon_imports(self) -> None:
        """Test that start command can be imported."""
        from codeweaver.cli.commands.start import (
            app,
            are_services_running,
            start,
            start_daemon_process,
        )

        assert app is not None
        assert start is not None
        assert start_daemon_process is not None
        assert are_services_running is not None

    def test_start_command_has_no_daemon_flag(self) -> None:
        """Test that start command has --no-daemon flag."""
        import inspect

        from codeweaver.cli.commands.start import start

        sig = inspect.signature(start)
        params = sig.parameters

        assert "no_daemon" in params
        assert params["no_daemon"].default is False

    def test_start_command_has_management_params(self) -> None:
        """Test that start command has management server parameters."""
        import inspect

        from codeweaver.cli.commands.start import start

        sig = inspect.signature(start)
        params = sig.parameters

        assert "management_host" in params
        assert "management_port" in params
        assert params["management_host"].default == "127.0.0.1"
        assert params["management_port"].default == 9329


class TestStopCommandParams:
    """Tests for stop command parameters."""

    def test_stop_command_has_force_flag(self) -> None:
        """Test that stop command has --force flag."""
        import inspect

        from codeweaver.cli.commands.stop import stop

        sig = inspect.signature(stop)
        params = sig.parameters

        assert "force" in params
        assert params["force"].default is False

    def test_stop_command_has_timeout_param(self) -> None:
        """Test that stop command has --timeout parameter."""
        import inspect

        from codeweaver.cli.commands.stop import stop

        sig = inspect.signature(stop)
        params = sig.parameters

        assert "timeout" in params
        assert params["timeout"].default == 10.0


class TestTerminateProcess:
    """Tests for process termination logic."""

    def test_terminate_nonexistent_process(self) -> None:
        """Test terminating a process that doesn't exist."""
        from codeweaver.common.utils.procs import terminate_process

        # Should return False for non-existent process
        result = terminate_process(999999999)
        assert result is False

    @pytest.mark.skipif(sys.platform == "win32", reason="Signal tests not reliable on Windows")
    def test_terminate_subprocess(self) -> None:
        """Test terminating a subprocess."""
        from codeweaver.common.utils.procs import is_process_running, terminate_process

        # Start a simple subprocess that sleeps
        proc = subprocess.Popen(
            [sys.executable, "-c", "import time; time.sleep(30)"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

        try:
            # Wait a moment for the process to start
            time.sleep(0.5)

            # Verify it's running
            assert is_process_running(proc.pid) is True

            # Terminate it
            result = terminate_process(proc.pid, timeout=5.0)
            assert result is True

            # Should not be running anymore
            time.sleep(0.5)
            assert is_process_running(proc.pid) is False
        finally:
            # Cleanup in case test fails - need to wait() to reap zombie
            try:
                proc.kill()
                proc.wait(timeout=1)
            except Exception:
                pass


class TestStatusCommandIntegration:
    """Tests for status command daemon status display."""

    def test_status_displays_daemon_info(self) -> None:
        """Test that status command imports daemon status functions."""
        from codeweaver.cli.commands.status import _display_management_status

        # Just verify the function exists and can be called
        assert _display_management_status is not None
