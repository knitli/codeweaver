# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Unit tests for CodeWeaverError and associated exception infrastructure.

Covers:
- ``__str__`` conciseness (message + location only)
- ``log_record()`` dict shape and values
- ``format_for_display()`` inclusion flags
- ``issue_information`` public ClassVar
- ``_collect_codeweaver_chain`` chain walking and depth cap
- ``_get_external_root`` external exception detection
- ``_deduplicate_suggestions`` order-preserving dedup
- ``CLIErrorHandler`` chain rendering: deduplicated suggestions, condensed causes,
  boilerplate printed once
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest

from codeweaver.cli.ui.error_handler import (
    CLIErrorHandler,
    _collect_codeweaver_chain,
    _deduplicate_suggestions,
    _get_external_root,
)
from codeweaver.core.exceptions import CodeWeaverError, IndexingError, LocationInfo


pytestmark = [pytest.mark.unit]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_error(
    msg: str = "something failed",
    *,
    details: dict | None = None,
    suggestions: list[str] | None = None,
) -> CodeWeaverError:
    """Build a CodeWeaverError with a stable synthetic location."""
    return CodeWeaverError(
        msg,
        details=details,
        suggestions=suggestions,
        location=LocationInfo(filename="/app/main.py", line_number=42, module_name="app.main"),
    )


def _make_chain(depth: int = 3) -> CodeWeaverError:
    """Build a raise-from chain of ``depth`` CodeWeaverError nodes."""
    root = CodeWeaverError(
        "root cause",
        suggestions=["fix root"],
        location=LocationInfo(filename="/app/root.py", line_number=1, module_name="root"),
    )
    current: Exception = root
    for i in range(1, depth):
        next_err = CodeWeaverError(
            f"level {i}",
            suggestions=[f"fix level {i}", "fix root"],  # intentional duplicate of root
            location=LocationInfo(
                filename=f"/app/level{i}.py", line_number=i * 10, module_name=f"app.level{i}"
            ),
        )
        try:
            raise next_err from current
        except CodeWeaverError as exc:
            current = exc
    assert isinstance(current, CodeWeaverError)
    return current


# ---------------------------------------------------------------------------
# CodeWeaverError.__str__
# ---------------------------------------------------------------------------


@pytest.mark.mock_only
@pytest.mark.unit
class TestCodeWeaverErrorStr:
    """__str__ returns a concise message with location, no boilerplate."""

    def test_includes_message(self) -> None:
        """String representation contains the error message."""
        err = _make_error("disk full")
        assert "disk full" in str(err)

    def test_includes_module_and_line(self) -> None:
        """String representation includes module name and line number."""
        err = _make_error()
        s = str(err)
        assert "app.main" in s
        assert "42" in s

    def test_no_issue_links(self) -> None:
        """String representation does not include issue/GitHub links."""
        err = _make_error()
        s = str(err)
        assert "github" not in s.lower()
        assert "alpha" not in s.lower()

    def test_no_suggestions(self) -> None:
        """String representation does not include suggestions."""
        err = _make_error(suggestions=["do this", "do that"])
        assert "do this" not in str(err)

    def test_no_location_when_missing(self) -> None:
        """String representation falls back to message only when no location."""
        err = CodeWeaverError("bare message", location=None)
        # Force no location (from_frame might capture something, override)
        err.location = None
        assert str(err) == "bare message"


# ---------------------------------------------------------------------------
# CodeWeaverError.log_record
# ---------------------------------------------------------------------------


@pytest.mark.mock_only
@pytest.mark.unit
class TestLogRecord:
    """log_record() returns a well-formed dict for structured logging."""

    def test_returns_dict(self) -> None:
        """log_record returns a plain dict."""
        err = _make_error()
        record = err.log_record()
        assert isinstance(record, dict)

    def test_required_keys(self) -> None:
        """log_record contains all required top-level keys."""
        err = _make_error()
        record = err.log_record()
        assert set(record.keys()) == {"error_type", "message", "details", "suggestions", "location"}

    def test_error_type_is_class_name(self) -> None:
        """error_type is the concrete exception class name."""
        err = IndexingError("file missing")
        assert err.log_record()["error_type"] == "IndexingError"

    def test_message_matches(self) -> None:
        """message field matches the original message."""
        err = _make_error("the message")
        assert err.log_record()["message"] == "the message"

    def test_details_is_copy(self) -> None:
        """details in log_record is a separate copy."""
        original = {"key": "val"}
        err = _make_error(details=original)
        record = err.log_record()
        record["details"]["key"] = "mutated"
        assert err.details["key"] == "val"  # original unchanged

    def test_suggestions_is_copy(self) -> None:
        """suggestions in log_record is a separate copy."""
        err = _make_error(suggestions=["a", "b"])
        record = err.log_record()
        record["suggestions"].append("c")
        assert err.suggestions == ["a", "b"]

    def test_location_dict_shape(self) -> None:
        """location sub-dict has filename, line_number, module_name."""
        err = _make_error()
        loc = err.log_record()["location"]
        assert isinstance(loc, dict)
        assert loc["filename"] == "/app/main.py"
        assert loc["line_number"] == 42
        assert loc["module_name"] == "app.main"

    def test_location_none_when_missing(self) -> None:
        """location is None when the exception has no location info."""
        err = CodeWeaverError("no location")
        err.location = None
        assert err.log_record()["location"] is None

    def test_empty_collections_when_no_extras(self) -> None:
        """details and suggestions are empty collections when not provided."""
        err = _make_error()
        record = err.log_record()
        assert record["details"] == {}
        assert record["suggestions"] == []


# ---------------------------------------------------------------------------
# CodeWeaverError.issue_information (public ClassVar)
# ---------------------------------------------------------------------------


@pytest.mark.mock_only
@pytest.mark.unit
class TestIssueInformation:
    """issue_information is a public ClassVar accessible without leading underscore."""

    def test_accessible_on_class(self) -> None:
        """issue_information is accessible via the class."""
        info = CodeWeaverError.issue_information
        assert isinstance(info, tuple)

    def test_non_empty(self) -> None:
        """issue_information contains at least one string."""
        assert len(CodeWeaverError.issue_information) > 0

    def test_contains_url(self) -> None:
        """issue_information contains a GitHub URL."""
        combined = " ".join(CodeWeaverError.issue_information)
        assert "https://github.com/knitli/codeweaver" in combined


# ---------------------------------------------------------------------------
# _collect_codeweaver_chain
# ---------------------------------------------------------------------------


@pytest.mark.mock_only
@pytest.mark.unit
class TestCollectCodeWeaverChain:
    """_collect_codeweaver_chain walks __cause__/__context__ chains correctly."""

    def test_single_exception_returns_one_element(self) -> None:
        """Single CodeWeaverError returns a list with one element."""
        err = _make_error()
        chain = _collect_codeweaver_chain(err)
        assert len(chain) == 1
        assert chain[0] is err

    def test_chain_order_outermost_first(self) -> None:
        """Chain is returned outermost-first."""
        outer = _make_chain(depth=3)
        chain = _collect_codeweaver_chain(outer)
        # The outermost is level 2, then level 1, then root
        assert chain[0] is outer

    def test_chain_length(self) -> None:
        """All CodeWeaverError nodes in the chain are collected."""
        outer = _make_chain(depth=3)
        chain = _collect_codeweaver_chain(outer)
        assert len(chain) == 3

    def test_stops_at_non_codeweaver_error(self) -> None:
        """Chain walking stops when it hits a non-CodeWeaverError."""
        external = OSError("disk full")
        cw_err = CodeWeaverError("wrapping", location=LocationInfo("/a.py", 1, "a"))
        try:
            raise cw_err from external
        except CodeWeaverError as exc:
            chain = _collect_codeweaver_chain(exc)
        # Only the CodeWeaverError node; OSError terminates the walk
        assert len(chain) == 1
        assert isinstance(chain[0], CodeWeaverError)

    def test_depth_cap(self) -> None:
        """Chain is capped at _MAX_CHAIN_DEPTH even for very deep chains."""
        from codeweaver.cli.ui.error_handler import _MAX_CHAIN_DEPTH

        outer = _make_chain(depth=_MAX_CHAIN_DEPTH + 5)
        chain = _collect_codeweaver_chain(outer)
        assert len(chain) <= _MAX_CHAIN_DEPTH

    def test_non_codeweaver_root_not_included(self) -> None:
        """Non-CodeWeaverError root exception does not appear in the chain."""
        external = ValueError("bad value")
        cw = CodeWeaverError("wrap", location=LocationInfo("/a.py", 1, "a"))
        try:
            raise cw from external
        except CodeWeaverError as exc:
            chain = _collect_codeweaver_chain(exc)
        assert all(isinstance(e, CodeWeaverError) for e in chain)


# ---------------------------------------------------------------------------
# _get_external_root
# ---------------------------------------------------------------------------


@pytest.mark.mock_only
@pytest.mark.unit
class TestGetExternalRoot:
    """_get_external_root surfaces the first non-CodeWeaverError in the chain."""

    def test_all_codeweaver_returns_none(self) -> None:
        """Returns None when the entire chain is CodeWeaverError nodes."""
        outer = _make_chain(depth=2)
        assert _get_external_root(outer) is None

    def test_finds_external_cause(self) -> None:
        """Returns the external exception when one exists."""
        external = OSError("disk full")
        cw = CodeWeaverError("wrap", location=LocationInfo("/a.py", 1, "a"))
        try:
            raise cw from external
        except CodeWeaverError as exc:
            root = _get_external_root(exc)
        assert root is external

    def test_does_not_return_starting_exception(self) -> None:
        """Does not return the exception itself even if it is not a CodeWeaverError."""
        non_cw = OSError("start")
        assert _get_external_root(non_cw) is None


# ---------------------------------------------------------------------------
# _deduplicate_suggestions
# ---------------------------------------------------------------------------


@pytest.mark.mock_only
@pytest.mark.unit
class TestDeduplicateSuggestions:
    """_deduplicate_suggestions removes duplicates while preserving order."""

    def test_no_duplicates_unchanged(self) -> None:
        """List without duplicates is returned unchanged."""
        suggestions = ["a", "b", "c"]
        assert _deduplicate_suggestions(suggestions) == ["a", "b", "c"]

    def test_duplicates_removed(self) -> None:
        """Duplicate entries are removed."""
        result = _deduplicate_suggestions(["a", "b", "a", "c", "b"])
        assert result == ["a", "b", "c"]

    def test_order_preserved(self) -> None:
        """First occurrence order is preserved."""
        result = _deduplicate_suggestions(["z", "a", "z"])
        assert result == ["z", "a"]

    def test_empty_list(self) -> None:
        """Empty list returns empty list."""
        assert _deduplicate_suggestions([]) == []


# ---------------------------------------------------------------------------
# CLIErrorHandler chain rendering
# ---------------------------------------------------------------------------


def _make_rich_console() -> MagicMock:
    """Return a mock console that records print calls."""
    console = MagicMock()
    console.print = MagicMock()
    console.print_exception = MagicMock()
    return console


def _make_display(console: MagicMock) -> MagicMock:
    """Return a mock StatusDisplay wrapping *console*."""
    display = MagicMock()
    display.console = console
    return display


def _all_printed(console: MagicMock) -> str:
    """Collect all text passed to console.print into one string."""
    parts = []
    for call in console.print.call_args_list:
        args = call.args
        if args:
            parts.append(str(args[0]))
    return "\n".join(parts)


@pytest.mark.mock_only
@pytest.mark.unit
class TestCLIErrorHandlerChainRendering:
    """CLIErrorHandler._handle_codeweaver_error renders chains correctly."""

    def _handler(self, *, verbose: bool = False) -> tuple[CLIErrorHandler, MagicMock]:
        console = _make_rich_console()
        display = _make_display(console)
        handler = CLIErrorHandler(display, verbose=verbose, prefix="[cw]")
        return handler, console

    def test_single_error_shows_message(self) -> None:
        """Primary error message is always displayed."""
        handler, console = self._handler()
        err = _make_error("primary message")
        handler._handle_codeweaver_error(err, "Indexing")
        output = _all_printed(console)
        assert "primary message" in output

    def test_context_label_in_header(self) -> None:
        """Context label appears in the failure header."""
        handler, console = self._handler()
        err = _make_error()
        handler._handle_codeweaver_error(err, "My Context")
        output = _all_printed(console)
        assert "My Context" in output

    def test_causes_rendered_as_arrows(self) -> None:
        """Deeper causes are shown as condensed → lines, not full boilerplate."""
        handler, console = self._handler()
        outer = _make_chain(depth=3)
        handler._handle_codeweaver_error(outer, "Startup")
        output = _all_printed(console)
        assert "→" in output

    def test_suggestions_deduplicated_once(self) -> None:
        """Duplicate suggestions across the chain appear only once."""
        handler, console = self._handler()
        outer = _make_chain(depth=3)  # chain has duplicate "fix root" suggestions
        handler._handle_codeweaver_error(outer, "Test")
        output = _all_printed(console)
        # "fix root" should appear exactly once in suggestions
        assert output.count("fix root") == 1

    def test_issue_information_once(self) -> None:
        """Issue-reporting boilerplate appears exactly once regardless of chain depth.

        The issue_information tuple itself contains two github.com URLs (issues + discussions).
        We verify the boilerplate block appears only once by checking the issues URL count.
        """
        handler, console = self._handler()
        outer = _make_chain(depth=4)
        handler._handle_codeweaver_error(outer, "Test")
        output = _all_printed(console)
        # The issues URL (distinct from the discussions URL) appears exactly once
        issues_url_count = output.count("knitli/codeweaver/issues")
        assert issues_url_count == 1

    def test_no_traceback_without_verbose(self) -> None:
        """print_exception is not called unless verbose or debug is set."""
        handler, console = self._handler(verbose=False)
        err = _make_error()
        handler._handle_codeweaver_error(err, "Test")
        console.print_exception.assert_not_called()

    def test_traceback_with_verbose(self) -> None:
        """print_exception is called when verbose is True."""
        handler, console = self._handler(verbose=True)
        err = _make_error()
        handler._handle_codeweaver_error(err, "Test")
        console.print_exception.assert_called_once()
