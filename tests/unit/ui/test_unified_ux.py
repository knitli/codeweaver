# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Unit tests for unified CLI UX components.

Tests the StatusDisplay and CLIErrorHandler classes for consistent CLI output.
"""

from __future__ import annotations

from io import StringIO

import pytest

from rich.console import Console
from rich.table import Table

from codeweaver.exceptions import CodeWeaverError
from codeweaver.ui import CLIErrorHandler, StatusDisplay


@pytest.mark.unit
class TestStatusDisplay:
    """Tests for StatusDisplay class."""

    def test_status_display_initialization(self) -> None:
        """Test StatusDisplay can be initialized."""
        display = StatusDisplay()
        assert display.console is not None
        assert isinstance(display.console, Console)

    def test_status_display_with_custom_console(self) -> None:
        """Test StatusDisplay accepts custom console."""
        buffer = StringIO()
        custom_console = Console(file=buffer, markup=False, emoji=False)
        display = StatusDisplay(console=custom_console)

        assert display.console is custom_console

    def test_print_info(self) -> None:
        """Test print_info method."""
        buffer = StringIO()
        console = Console(file=buffer, markup=False, emoji=False, width=120)
        display = StatusDisplay(console=console)

        display.print_info("Test message")
        output = buffer.getvalue()

        assert "Test message" in output

    def test_print_success(self) -> None:
        """Test print_success method."""
        buffer = StringIO()
        console = Console(file=buffer, markup=False, emoji=False, width=120)
        display = StatusDisplay(console=console)

        display.print_success("Operation successful")
        output = buffer.getvalue()

        assert "Operation successful" in output

    def test_print_error(self) -> None:
        """Test print_error method."""
        buffer = StringIO()
        console = Console(file=buffer, markup=False, emoji=False, width=120)
        display = StatusDisplay(console=console)

        display.print_error("An error occurred")
        output = buffer.getvalue()

        assert "An error occurred" in output

    def test_print_warning(self) -> None:
        """Test print_warning method."""
        buffer = StringIO()
        console = Console(file=buffer, markup=False, emoji=False, width=120)
        display = StatusDisplay(console=console)

        display.print_warning("Warning message")
        output = buffer.getvalue()

        assert "Warning message" in output

    def test_print_section(self) -> None:
        """Test print_section method."""
        buffer = StringIO()
        console = Console(file=buffer, markup=False, emoji=False, width=120)
        display = StatusDisplay(console=console)

        display.print_section("Section Title")
        output = buffer.getvalue()

        assert "Section Title" in output

    def test_print_table(self) -> None:
        """Test print_table method."""
        buffer = StringIO()
        console = Console(file=buffer, markup=False, emoji=False, width=120)
        display = StatusDisplay(console=console)

        table = Table()
        table.add_column("Name")
        table.add_column("Value")
        table.add_row("test", "123")

        display.print_table(table)
        output = buffer.getvalue()

        assert "test" in output
        assert "123" in output

    def test_print_progress(self) -> None:
        """Test print_progress method."""
        buffer = StringIO()
        console = Console(file=buffer, markup=False, emoji=False, width=120)
        display = StatusDisplay(console=console)

        display.print_progress(50, 100, "Processing files")
        output = buffer.getvalue()

        assert "50" in output
        assert "100" in output
        assert "Processing files" in output


@pytest.mark.unit
class TestCLIErrorHandler:
    """Tests for CLIErrorHandler class."""

    def test_cli_error_handler_initialization(self) -> None:
        """Test CLIErrorHandler can be initialized."""
        display = StatusDisplay()
        handler = CLIErrorHandler(display)

        assert handler.display is display
        assert handler.verbose is False
        assert handler.debug is False

    def test_cli_error_handler_verbose_mode(self) -> None:
        """Test CLIErrorHandler with verbose mode."""
        display = StatusDisplay()
        handler = CLIErrorHandler(display, verbose=True)

        assert handler.verbose is True
        assert handler.debug is False

    def test_cli_error_handler_debug_mode(self) -> None:
        """Test CLIErrorHandler with debug mode."""
        display = StatusDisplay()
        handler = CLIErrorHandler(display, debug=True)

        assert handler.verbose is False
        assert handler.debug is True

    def test_handle_codeweaver_error(self) -> None:
        """Test handling of CodeWeaverError."""
        buffer = StringIO()
        console = Console(file=buffer, markup=False, emoji=False, width=120)
        display = StatusDisplay(console=console)
        handler = CLIErrorHandler(display, verbose=False, debug=False)

        error = CodeWeaverError("Test error message")

        # This will exit, so we catch it
        with pytest.raises(SystemExit) as exc_info:
            handler.handle_error(error, "Test operation")

        assert exc_info.value.code == 1
        output = buffer.getvalue()
        assert "Test error message" in output
        assert "Test operation" in output

    def test_handle_unexpected_error(self) -> None:
        """Test handling of unexpected error."""
        buffer = StringIO()
        console = Console(file=buffer, markup=False, emoji=False, width=120)
        display = StatusDisplay(console=console)
        handler = CLIErrorHandler(display, verbose=False, debug=False)

        error = ValueError("Unexpected error")

        # This will exit, so we catch it
        with pytest.raises(SystemExit) as exc_info:
            handler.handle_error(error, "Test operation")

        assert exc_info.value.code == 1
        output = buffer.getvalue()
        assert "Unexpected error" in output


@pytest.mark.unit
class TestUnifiedUXIntegration:
    """Integration tests for unified UX system."""

    def test_display_and_error_handler_work_together(self) -> None:
        """Test StatusDisplay and CLIErrorHandler work together."""
        buffer = StringIO()
        console = Console(file=buffer, markup=False, emoji=False, width=120)
        display = StatusDisplay(console=console)
        handler = CLIErrorHandler(display, verbose=False, debug=False)

        # Test normal output
        display.print_info("Starting operation")
        display.print_success("Operation completed")

        output = buffer.getvalue()
        assert "Starting operation" in output
        assert "Operation completed" in output

        # Verify handler has access to display
        assert handler.display is display
        assert handler.display.console is console


@pytest.mark.unit
class TestDoctorConsoleProxy:
    """Tests for doctor.py console proxy functionality."""

    def test_console_proxy_delegates_to_current_display(self) -> None:
        """Test that doctor console proxy always uses current display."""
        # Import here to avoid circular dependencies
        from codeweaver.cli.commands import doctor

        # Get initial display
        initial_display = doctor._get_display()
        initial_console_id = id(initial_display.console)

        # Create a new display and reassign module display
        from io import StringIO

        from rich.console import Console

        buffer = StringIO()
        new_console = Console(file=buffer, markup=False, emoji=False, width=120)
        new_display = StatusDisplay(console=new_console)
        doctor._display = new_display

        # Now console.print should use the new display's console
        doctor.console.print("Test message")
        output = buffer.getvalue()

        assert "Test message" in output, "Console proxy should use new display's console"

        # Verify the proxy is dynamic
        assert id(doctor._get_display().console) != initial_console_id
        assert id(doctor._get_display().console) == id(new_console)

    def test_console_proxy_has_required_methods(self) -> None:
        """Test that console proxy has all required methods."""
        from codeweaver.cli.commands import doctor

        # Verify proxy has the methods check functions use
        assert hasattr(doctor.console, "print"), "Console proxy should have print method"
        assert hasattr(doctor.console, "input"), "Console proxy should have input method"
        assert callable(doctor.console.print), "Console print should be callable"
        assert callable(doctor.console.input), "Console input should be callable"
