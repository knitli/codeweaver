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

from typing import Any, ClassVar


# TODO: We got into a bad habit of not using native exception types. We need to systematically go through and improve exception handling and information.


class CodeWeaverError(Exception):
    """Base exception for all CodeWeaver errors.

    Provides structured error information including details and suggestions
    for resolution.
    """

    _issue_information: ClassVar[tuple[str, ...]] = (
        "CodeWeaver is still in beta. If you encounter issues, and think they are bugs, please report them at https://github.com/knitli/codeweaver-mcp/issues",
        "",
        "If you're not sure, you can open a discussion at: https://github.com/knitli/codeweaver-mcp/discussions",
        "",
        "Thank you for helping us improve CodeWeaver!",
    )

    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        suggestions: list[str] | None = None,
    ) -> None:
        """Initialize CodeWeaver error.

        Args:
            message: Human-readable error message
            details: Additional context about the error
            suggestions: Actionable suggestions for resolving the error
            _issue_information: Preformatted issue reporting information
        """
        super().__init__(message)
        self.message = message
        self.details = details or {}
        self.suggestions = suggestions or []

    @property
    def _reporting_info(self) -> str:
        """Generate issue reporting information."""
        return "\n".join((
            "Include the following information when reporting issues:",
            f"- Error Message: {self.message}",
            "- Details: " + ", ".join(f"{k}: {v}" for k, v in self.details.items())
            if self.details
            else "- No additional details provided.",
            "- Suggestions: " + ", ".join(self.suggestions)
            if self.suggestions
            else "- No suggestions provided.",
            "",
            "If you're not sure, you can open a discussion at: https://github.com/knitli/codeweaver-mcp/discussions",
            "",
            "Thank you for helping us improve CodeWeaver!",
        ))

    @property
    def report(self) -> str:
        """Generate a full error report including reporting information."""
        about = type(self)._issue_information
        return f"{'\n'.join(about)}\n\n{self._reporting_info}"


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
