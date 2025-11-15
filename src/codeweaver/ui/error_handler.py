# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Unified error handling for CLI commands."""

from __future__ import annotations

import json
import sys

from typing import TYPE_CHECKING

from codeweaver.exceptions import CodeWeaverError


if TYPE_CHECKING:
    from codeweaver.ui.status_display import StatusDisplay


class CLIErrorHandler:
    """Unified error handling for CLI commands.

    Provides consistent error display across all CLI commands with appropriate
    detail levels based on error type and verbosity flags.
    """

    def __init__(
        self, display: StatusDisplay, *, verbose: bool = False, debug: bool = False
    ) -> None:
        """Initialize error handler.

        Args:
            display: StatusDisplay instance for output
            verbose: Enable verbose error output
            debug: Enable debug error output (includes verbose)
        """
        self.display = display
        self.verbose = verbose
        self.debug = debug

    def handle_error(
        self, error: Exception, context: str, *, exit_code: int = 1
    ) -> None:
        """Handle and display errors appropriately.

        Args:
            error: Exception to handle
            context: Context description (e.g., "Server startup")
            exit_code: Exit code to use (default: 1)
        """
        if isinstance(error, CodeWeaverError):
            self._handle_codeweaver_error(error, context)
        else:
            self._handle_unexpected_error(error, context)

        sys.exit(exit_code)

    def _handle_codeweaver_error(self, error: CodeWeaverError, context: str) -> None:
        """Display CodeWeaver-specific errors.

        Args:
            error: CodeWeaverError to display
            context: Context description
        """
        from codeweaver.common import CODEWEAVER_PREFIX

        # Print header with error context
        self.display.console.print(
            f"\n{CODEWEAVER_PREFIX} [bold red]✗ {context} failed[/bold red]\n"
        )

        # Print error message
        self.display.console.print(f"[red]Error:[/red] {error}\n")

        # Show details if available
        if hasattr(error, "details") and error.details:
            self.display.console.print("[yellow]Details:[/yellow]")
            if isinstance(error.details, dict):
                self.display.console.print(json.dumps(error.details, indent=2))
            else:
                self.display.console.print(str(error.details))
            self.display.console.print()

        # Show suggestions if available
        if hasattr(error, "suggestions") and error.suggestions:
            self.display.console.print("[yellow]Suggestions:[/yellow]")
            for suggestion in error.suggestions:
                self.display.console.print(f"  • {suggestion}")
            self.display.console.print()

        # Show full traceback in verbose/debug mode
        if self.verbose or self.debug:
            self.display.console.print("[dim]Full traceback:[/dim]")
            self.display.console.print_exception(show_locals=self.debug)

    def _handle_unexpected_error(self, error: Exception, context: str) -> None:
        """Display unexpected errors.

        Always shows full details for unexpected errors since they indicate bugs.

        Args:
            error: Exception to display
            context: Context description
        """
        from codeweaver.common import CODEWEAVER_PREFIX

        # Print header
        self.display.console.print(
            f"\n{CODEWEAVER_PREFIX} [bold red]✗ {context} crashed unexpectedly[/bold red]\n"
        )

        # Print error type and message
        self.display.console.print(
            f"[red]Error:[/red] {type(error).__name__}: {error}\n"
        )

        # Always show full traceback for unexpected errors
        self.display.console.print("[yellow]Full traceback:[/yellow]")
        self.display.console.print_exception(show_locals=self.debug, word_wrap=True)

        # Suggest reporting the issue
        self.display.console.print(
            "\n[dim]Tip: Please report this error with the traceback above[/dim]\n"
        )


__all__ = ("CLIErrorHandler",)
