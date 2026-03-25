# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Unified error handling for CLI commands."""

from __future__ import annotations

import contextlib
import sys

from types import GeneratorType
from typing import TYPE_CHECKING

from codeweaver.core import CodeWeaverError
from codeweaver.core.utils import get_codeweaver_prefix


if TYPE_CHECKING:
    from codeweaver.cli.ui.status_display import StatusDisplay


# ---------------------------------------------------------------------------
# Exception-chain helpers
# ---------------------------------------------------------------------------

_MAX_CHAIN_DEPTH = 10
_BULLET = "\u2022"


def _collect_codeweaver_chain(exc: BaseException) -> list[CodeWeaverError]:
    """Walk ``__cause__`` / ``__context__`` and return all CodeWeaverError nodes.

    Returns nodes in outermost-first order (the exception itself is first).
    Stops following the chain when it hits a non-CodeWeaverError or exceeds
    ``_MAX_CHAIN_DEPTH`` to guard against unexpectedly long or cyclic chains.

    Args:
        exc: The exception to start from.

    Returns:
        List of CodeWeaverError instances from outermost to root.
    """
    chain: list[CodeWeaverError] = []
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None and len(chain) < _MAX_CHAIN_DEPTH:
        exc_id = id(current)
        if exc_id in seen:
            break
        seen.add(exc_id)
        if isinstance(current, CodeWeaverError):
            chain.append(current)
        # Explicit cause (raise X from Y) takes priority; fall back to implicit
        # context only when it has not been suppressed by ``raise X from None``.
        next_exc: BaseException | None = current.__cause__ or (
            current.__context__ if not current.__suppress_context__ else None
        )
        current = next_exc
    return chain


def _get_external_root(exc: BaseException) -> BaseException | None:
    """Return the first non-CodeWeaverError exception at the root of the chain.

    This surfaces the original third-party or built-in exception (e.g.
    ``OSError``, ``ImportError``) that triggered the CodeWeaver chain so users
    can see what actually went wrong at the lowest level.

    Args:
        exc: The outermost exception.

    Returns:
        The non-CodeWeaverError root exception, or ``None`` if the entire chain
        is made up of CodeWeaverError instances.
    """
    seen: set[int] = set()
    current: BaseException | None = exc
    while current is not None:
        exc_id = id(current)
        if exc_id in seen:
            break
        seen.add(exc_id)
        next_exc: BaseException | None = current.__cause__ or (
            current.__context__ if not current.__suppress_context__ else None
        )
        # We found an external exception in the chain (not the root of the walk)
        if not isinstance(current, CodeWeaverError) and current is not exc:
            return current
        current = next_exc
    return None


def _deduplicate_suggestions(suggestions: list[str]) -> list[str]:
    """Return *suggestions* with duplicates removed, preserving original order.

    Args:
        suggestions: Possibly-duplicated suggestion strings.

    Returns:
        De-duplicated list in original order.
    """
    seen: set[str] = set()
    result: list[str] = []
    for s in suggestions:
        if s not in seen:
            seen.add(s)
            result.append(s)
    return result


# ---------------------------------------------------------------------------
# Error handler
# ---------------------------------------------------------------------------


class CLIErrorHandler:
    """Unified error handling for CLI commands.

    Provides consistent error display across all CLI commands with appropriate
    detail levels based on error type and verbosity flags.

    When a ``CodeWeaverError`` exception chain is displayed, each node in the
    chain contributes its message and location, but suggestions are aggregated
    and de-duplicated across the whole chain, and the issue-reporting
    boilerplate is printed exactly once.  This prevents walls of identical
    advice when multiple CodeWeaver exceptions wrap one another.
    """

    def __init__(
        self,
        display: StatusDisplay,
        *,
        verbose: bool = False,
        debug: bool = False,
        prefix: str | None = None,
    ) -> None:
        """Initialize error handler.

        Args:
            display: StatusDisplay instance for output
            verbose: Enable verbose error output
            debug: Enable debug error output (includes verbose)
            prefix: Prefix to use in messages
        """
        if not prefix:
            prefix: str = get_codeweaver_prefix()
        self.display = display
        self.verbose = verbose
        self.debug = debug
        self.prefix = prefix

    def handle_error(self, error: Exception, context: str, *, exit_code: int = 1) -> None:
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
        """Display a CodeWeaver exception chain without repeating boilerplate.

        Walks the full ``__cause__`` / ``__context__`` chain and:

        * Shows the outermost error in full (message, location, details).
        * Shows each deeper cause condensed to a single line.
        * Surfaces the first non-CodeWeaverError root cause if present.
        * Aggregates all suggestions across the chain, de-duplicates them, and
          displays them once.
        * Prints the issue-reporting boilerplate exactly once at the end.

        Args:
            error: The outermost CodeWeaverError to display.
            context: Human-readable context for the failure (e.g. "Indexing").
        """
        chain = _collect_codeweaver_chain(error)

        self.display.console.print(f"\n{self.prefix}\n  [bold red]✗ {context} failed[/bold red]\n")
        self._print_primary_error(error)

        if len(chain) > 1:
            self._print_cause_chain(chain[1:])

        ext_root = _get_external_root(error)
        if ext_root:
            self.display.console.print(
                f"[dim]Underlying cause: {type(ext_root).__name__}: {ext_root}[/dim]\n"
            )

        all_suggestions = _deduplicate_suggestions([s for exc in chain for s in exc.suggestions])
        if all_suggestions:
            self.display.console.print("[yellow]Suggestions:[/yellow]")
            for suggestion in all_suggestions:
                self.display.console.print(f"  {_BULLET} {suggestion}")
            self.display.console.print()

        for line in CodeWeaverError._issue_information:
            self.display.console.print(line)

        if self.verbose or self.debug:
            self.display.console.print("\n[dim]Full traceback:[/dim]")
            self.display.console.print_exception(show_locals=self.debug)

    def _print_primary_error(self, error: CodeWeaverError) -> None:
        """Print the outermost error with its message, location, and details.

        Args:
            error: The primary CodeWeaverError to render.
        """
        from pydantic_core import to_json

        from codeweaver.core.utils.environment import format_file_link

        self.display.console.print(f"[bold red]Error:[/bold red] {error.message}")
        if error.location and error.location.filename:
            link = format_file_link(error.location.filename, error.location.line_number)
            self.display.console.print(f"  [dim]in '{error.location.module_name}' at {link}[/dim]")
        self.display.console.print()

        if error.details:
            self.display.console.print("[yellow]Details:[/yellow]")
            if isinstance(error.details, dict):
                self.display.console.print(
                    to_json(error.details, round_trip=True, indent=2).decode("utf-8")
                )
            else:
                self.display.console.print(str(error.details))
            self.display.console.print()

    def _print_cause_chain(self, causes: list[CodeWeaverError]) -> None:
        """Print a condensed cause chain (all nodes except the outermost).

        Each cause is rendered on a single ``→ ExcType: message (location)``
        line so users can follow the chain without reading repeated boilerplate.

        Args:
            causes: Chain nodes in outermost-to-root order, excluding the
                primary node already rendered by ``_print_primary_error``.
        """
        self.display.console.print("[dim]Caused by:[/dim]")
        for cause in causes:
            location_str = ""
            if cause.location and cause.location.filename:
                location_str = (
                    f" [dim](in '{cause.location.module_name}', "
                    f"line {cause.location.line_number})[/dim]"
                )
            self.display.console.print(
                f"  [dim]→ {type(cause).__name__}: {cause.message}{location_str}[/dim]"
            )
        self.display.console.print()

    def _handle_unexpected_error(self, error: Exception, context: str) -> None:
        """Display unexpected errors.

        Always shows full details for unexpected errors since they indicate bugs.

        Args:
            error: Exception to display
            context: Context description
        """
        # Print header
        self.display.console.print(
            f"\n{self.prefix} [bold red]✗ {context} crashed unexpectedly[/bold red]\n"
        )

        # Print error type and message
        self.display.console.print(f"[red]Error:[/red] {type(error).__name__}: {error}\n")

        # Always show full traceback for unexpected errors
        self.display.console.print("[yellow]Full traceback:[/yellow]")
        self.display.console.print_exception(show_locals=self.debug, word_wrap=True)

        # Suggest reporting the issue
        self.display.console.print(
            "\n[dim]Tip: Please report this error with the traceback above[/dim]\n"
        )


@contextlib.contextmanager
def handle_keyboard_interrupt_gracefully() -> GeneratorType[None, None, None]:
    """Context manager to handle KeyboardInterrupt gracefully for CLI commands."""
    try:
        yield
    except KeyboardInterrupt:
        from codeweaver.cli.__main__ import _handle_keyboard_interrupt

        _handle_keyboard_interrupt()


__all__ = (
    "CLIErrorHandler",
    "_collect_codeweaver_chain",
    "_deduplicate_suggestions",
    "_get_external_root",
    "handle_keyboard_interrupt_gracefully",
)
