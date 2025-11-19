# sourcery skip: no-complex-if-expressions
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Unified exception hierarchy for CodeWeaver.

This module provides a single, unified exception hierarchy to prevent exception
proliferation. All CodeWeaver exceptions inherit from CodeWeaverError and
are organized into five primary categories.
"""

from __future__ import annotations

import os
import sys

from typing import Any, ClassVar, NamedTuple


class LocationInfo(NamedTuple):
    """Location information for where an exception was raised.

    Attributes:
        filename: The name of the file
        line_number: The line number in the file
    """

    filename: str
    line_number: int
    module_name: str

    @classmethod
    def from_frame(cls, frame: int = 2) -> LocationInfo | None:
        """Create LocationInfo from a stack frame.

        Args:
            frame: The stack frame to inspect (default: 2)

        Returns:
            LocationInfo instance or None if unavailable.
        """
        try:
            tb = sys._getframe(frame)
            filename = tb.f_code.co_filename
            line_number = tb.f_lineno
            module_name = tb.f_globals.get("__name__", "<unknown>")
            return cls(filename, line_number, module_name)
        except (AttributeError, ValueError):
            return None


def _is_tty() -> bool:
    """Check if the output is a TTY in an interactive terminal."""
    return sys.stdout.isatty() if hasattr(sys, "stdout") and sys.stdout else False


def _get_issue_information() -> tuple[str, ...]:
    """Generate issue reporting information."""
    if _is_tty():
        return (
            "[dark orange]CodeWeaver[/dark orange] [bold magenta]is in alpha[/bold magenta]. Please report possible bugs at https://github.com/knitli/codeweaver/issues",
            "",
            "If you're not sure something is a bug, you can open a discussion at: https://github.com/knitli/codeweaver/discussions",
            "",
            "[bold]Thank you for helping us improve CodeWeaver! ❤️[/bold]",
        )
    return (
        "CodeWeaver is in alpha. Please report possible bugs at https://github.com/knitli/codeweaver/issues",
        "",
        "If you're not sure something is a bug, you can open a discussion at: https://github.com/knitli/codeweaver/discussions",
        "",
        "Thank you for helping us improve CodeWeaver!",
    )


def _get_reporting_info(detail_parts: list[str]) -> str:
    """Generate issue reporting information."""
    detail_parts = detail_parts or []
    if not os.environ.get("CODEWEAVER_TEST_MODE", False) and _is_tty():
        return "\n".join((
            "[magenta]Include the following information when reporting issues:[/magenta]",
            "- [bold][red]Error[/red] Details:[/bold] " + ", ".join(detail_parts)
            if detail_parts
            else "- [bold]Details:[/bold] No additional details provided.",
            "",
        ))
    return "\n".join((
        "Include the following information when reporting issues:",
        "- Details: " + ", ".join(detail_parts)
        if detail_parts
        else "- No additional details provided.",
        "",
    ))


class CodeWeaverError(Exception):
    """Base exception for all CodeWeaver errors.

    Provides structured error information including details and suggestions
    for resolution.
    """

    _issue_information: ClassVar[tuple[str, ...]] = _get_issue_information()

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        suggestions: list[str] | None = None,
        location: LocationInfo | None = None,
    ) -> None:
        """Initialize CodeWeaver error.

        Args:
            message: Human-readable error message
            details: Additional context about the error
            suggestions: Actionable suggestions for resolving the error
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.suggestions = suggestions or []
        self.location = location or LocationInfo.from_frame(2)

    def __str__(self) -> str:
        """Return descriptive error message with context details."""
        # Start with base message
        from codeweaver.cli.utils import format_file_link

        if _is_tty():
            location_info = (
                f"\n[bold red]Encountered error[/bold red] in '{self.location.module_name}' "
                f"at {format_file_link(self.location.filename, self.location.line_number)}\n"
                if self.location and self.location.filename
                else ""
            )
        else:
            location_info = (
                f"\nEncountered error in '{self.location.module_name}' "
                f"at {format_file_link(self.location.filename, self.location.line_number)}\n"
                if self.location and self.location.filename
                else ""
            )
        parts: list[str] = [self.message, location_info]

        # Add important details if present
        if self.details:
            detail_parts: list[str] = []
            # Include file_path if present
            if "file_path" in self.details:
                detail_parts.append(f"file: {self.details['file_path']}")
            # Include numeric metrics if present
            detail_parts.extend(
                f"{key.replace('_', ' ')}: {self.details[key]}"
                for key in [
                    "actual_depth",
                    "max_depth",
                    "actual_tokens",
                    "max_tokens",
                    "chunk_count",
                    "max_chunks",
                    "timeout_seconds",
                    "elapsed_seconds",
                    "line_number",
                ]
                if key in self.details
            )
            if detail_parts:
                parts.append(_get_reporting_info(detail_parts))
        parts.extend(type(self)._issue_information)
        return "\n".join(parts)


class InitializationError(CodeWeaverError):
    """Initialization and startup errors.

    Raised when there are issues during application startup, such as missing
    dependencies, configuration errors, or environment setup problems.
    """


class ConfigurationError(CodeWeaverError):
    """Configuration and settings errors.

    Raised when there are issues with configuration files, environment variables,
    settings validation, or provider configuration.
    """


class ProviderError(CodeWeaverError):
    """Provider integration errors.

    Raised when there are issues with embedding providers, vector stores,
    or other external service integrations.
    """


class ModelSwitchError(ProviderError):
    """Model switching detection error.

    Raised when the system detects that the embedding model has changed
    from what was used to create the existing vector store collection.
    """


class RerankingProviderError(ProviderError):
    """Reranking provider errors.

    Raised when there are issues specific to the reranking provider, such as
    invalid input formats, failed API calls, or unexpected response structures.
    """


class ProviderSwitchError(ProviderError):
    """Provider switching detection error.

    Raised when the system detects that the vector store collection was created
    with a different provider than the currently configured one.
    """


class DimensionMismatchError(ProviderError):
    """Embedding dimension mismatch error.

    Raised when embedding dimensions don't match the vector store collection
    configuration.
    """


class CollectionNotFoundError(ProviderError):
    """Collection not found error.

    Raised when attempting operations on a non-existent collection.
    """


class PersistenceError(ProviderError):
    """Persistence operation error.

    Raised when in-memory provider persistence operations fail.
    """


class IndexingError(CodeWeaverError):
    """File indexing and processing errors.

    Raised when there are issues with file discovery, content processing,
    or index building operations.
    """


class QueryError(CodeWeaverError):
    """Query processing and search errors.

    Raised when there are issues with query validation, search execution,
    or result processing.
    """


class ValidationError(CodeWeaverError):
    """Input validation and schema errors.

    Raised when there are issues with input validation, data model validation,
    or schema compliance.
    """


class MissingValueError(CodeWeaverError):
    """Missing value errors.

    Raised when a required value is missing in the context of an operation.
    This is a specific case of validation error.
    """

    def __init__(
        self,
        msg: str | None,
        field: str,
        details: dict[str, Any] | None = None,
        suggestions: list[str] | None = None,
    ) -> None:
        """Initialize MissingValueError.

        Args:
            field: The name of the missing field
        """
        super().__init__(
            message=msg or f"Missing value for field: {field}",
            details=details,
            suggestions=suggestions,
        )
        self.field = field


__all__ = (
    "CodeWeaverError",
    "CollectionNotFoundError",
    "ConfigurationError",
    "DimensionMismatchError",
    "IndexingError",
    "InitializationError",
    "MissingValueError",
    "PersistenceError",
    "ProviderError",
    "ProviderSwitchError",
    "QueryError",
    "RerankingProviderError",
    "ValidationError",
)
