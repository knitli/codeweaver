# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Exception hierarchy for the chunking system.

This module defines a comprehensive exception hierarchy for handling various
chunking failures. All exceptions inherit from ChunkingError which itself
inherits from the unified CodeWeaverError base class.

The exception hierarchy provides specific exceptions for different failure
modes including parsing errors, size constraints, timeouts, and resource limits.
"""

from __future__ import annotations

from typing import Any

from codeweaver.exceptions import CodeWeaverError


class ChunkingError(CodeWeaverError):
    """Base exception for all chunking operation failures.

    This exception serves as the root of the chunking exception hierarchy
    and should be caught when handling any chunking-related errors generically.

    Attributes:
        message: Human-readable error description
        details: Additional context about the failure
        suggestions: Actionable guidance for resolving the error
    """


class ParseError(ChunkingError):
    """AST parsing failed for the provided source code.

    Raised when the parser cannot create an abstract syntax tree from the
    source file, typically due to syntax errors or unsupported language
    constructs. The system may fall back to alternative chunking strategies.

    Common causes include malformed code, encoding issues, or parser bugs.
    """

    def __init__(
        self,
        message: str,
        *,
        file_path: str | None = None,
        line_number: int | None = None,
        details: dict[str, Any] | None = None,
        suggestions: list[str] | None = None,
    ) -> None:
        """Initialize parse error with location context.

        Args:
            message: Description of the parsing failure
            file_path: Path to the file that failed to parse
            line_number: Approximate line where parsing failed
            details: Additional diagnostic information
            suggestions: Steps to resolve the parsing error
        """
        error_details = details or {}
        if file_path:
            error_details["file_path"] = file_path
        if line_number:
            error_details["line_number"] = line_number

        default_suggestions = suggestions or [
            "Check for syntax errors in the source file",
            "Verify file encoding is UTF-8 compatible",
            "Consider using a fallback chunking strategy",
        ]

        super().__init__(message, details=error_details, suggestions=default_suggestions)
        self.file_path = file_path
        self.line_number = line_number


class OversizedChunkError(ChunkingError):
    """Chunk exceeds token limit after applying all reduction strategies.

    Raised when a code segment cannot be reduced below the maximum allowed
    token count even after applying aggressive chunking strategies. This
    typically indicates extremely dense or complex code that requires manual
    intervention or alternative processing approaches.

    The system has exhausted all automatic strategies including structural
    decomposition, overlap reduction, and content trimming.
    """

    def __init__(
        self,
        message: str,
        *,
        actual_tokens: int | None = None,
        max_tokens: int | None = None,
        chunk_content: str | None = None,
        details: dict[str, Any] | None = None,
        suggestions: list[str] | None = None,
    ) -> None:
        """Initialize oversized chunk error with size metrics.

        Args:
            message: Description of the size constraint violation
            actual_tokens: Number of tokens in the oversized chunk
            max_tokens: Maximum allowed token count
            chunk_content: Preview of the problematic chunk content
            details: Additional size-related diagnostics
            suggestions: Strategies for handling the oversized content
        """
        error_details = details or {}
        if actual_tokens:
            error_details["actual_tokens"] = actual_tokens
        if max_tokens:
            error_details["max_tokens"] = max_tokens
            if actual_tokens:
                error_details["overflow_percentage"] = (
                    (actual_tokens - max_tokens) / max_tokens * 100
                )
        if chunk_content:
            # Include preview without exposing entire content
            error_details["content_preview"] = f"{chunk_content[:200]}..."

        default_suggestions = suggestions or [
            "Refactor code to reduce function/class complexity",
            "Split large structures into smaller components",
            "Increase token limit configuration if appropriate",
            "Consider excluding this file from semantic search",
        ]

        super().__init__(message, details=error_details, suggestions=default_suggestions)
        self.actual_tokens = actual_tokens
        self.max_tokens = max_tokens


class ChunkingTimeoutError(ChunkingError):
    """Chunking operation exceeded the configured time limit.

    Raised when processing a file takes longer than the maximum allowed
    duration. This typically indicates pathological input, performance issues,
    or misconfigured timeout settings.

    The system enforces timeouts to prevent resource exhaustion and ensure
    responsive operation across large codebases.
    """

    def __init__(
        self,
        message: str,
        *,
        timeout_seconds: float | None = None,
        elapsed_seconds: float | None = None,
        file_path: str | None = None,
        details: dict[str, Any] | None = None,
        suggestions: list[str] | None = None,
    ) -> None:
        """Initialize timeout error with timing metrics.

        Args:
            message: Description of the timeout condition
            timeout_seconds: Configured timeout threshold
            elapsed_seconds: Actual time elapsed before timeout
            file_path: Path to the file being processed
            details: Additional timing diagnostics
            suggestions: Steps to resolve timeout issues
        """
        error_details = details or {}
        if timeout_seconds:
            error_details["timeout_seconds"] = timeout_seconds
        if elapsed_seconds:
            error_details["elapsed_seconds"] = elapsed_seconds
        if file_path:
            error_details["file_path"] = file_path

        default_suggestions = suggestions or [
            "Increase timeout configuration for large files",
            "Check for infinite loops in parsing logic",
            "Consider excluding problematic files from processing",
            "Profile chunking performance for optimization opportunities",
        ]

        super().__init__(message, details=error_details, suggestions=default_suggestions)
        self.timeout_seconds = timeout_seconds
        self.elapsed_seconds = elapsed_seconds
        self.file_path = file_path


class ChunkLimitExceededError(ChunkingError):
    """File produced more chunks than the configured maximum.

    Raised when a single file generates an excessive number of chunks,
    potentially indicating overly aggressive chunking or pathological input.
    This limit prevents resource exhaustion and index bloat.

    Exceeding chunk limits typically suggests the file should be processed
    differently or excluded from semantic search.
    """

    def __init__(
        self,
        message: str,
        *,
        chunk_count: int | None = None,
        max_chunks: int | None = None,
        file_path: str | None = None,
        details: dict[str, Any] | None = None,
        suggestions: list[str] | None = None,
    ) -> None:
        """Initialize chunk limit error with count metrics.

        Args:
            message: Description of the limit violation
            chunk_count: Number of chunks generated
            max_chunks: Configured maximum chunk count
            file_path: Path to the file exceeding limits
            details: Additional count-related diagnostics
            suggestions: Strategies for handling excessive chunking
        """
        error_details = details or {}
        if chunk_count:
            error_details["chunk_count"] = chunk_count
        if max_chunks:
            error_details["max_chunks"] = max_chunks
            if chunk_count:
                error_details["overflow_count"] = chunk_count - max_chunks
        if file_path:
            error_details["file_path"] = file_path

        default_suggestions = suggestions or [
            "Increase chunk limit configuration if appropriate",
            "Refactor code to reduce structural complexity",
            "Adjust chunking strategy to produce larger chunks",
            "Consider excluding this file from semantic search",
        ]

        super().__init__(message, details=error_details, suggestions=default_suggestions)
        self.chunk_count = chunk_count
        self.max_chunks = max_chunks
        self.file_path = file_path


class BinaryFileError(ChunkingError):
    """Binary or non-text content detected in file.

    Raised when the chunking system encounters binary data that cannot be
    processed as text. This prevents corruption and ensures only appropriate
    content enters the semantic search index.

    Binary files should be filtered during discovery, but this exception
    provides a safety net for edge cases.
    """

    def __init__(
        self,
        message: str,
        *,
        file_path: str | None = None,
        detected_encoding: str | None = None,
        details: dict[str, Any] | None = None,
        suggestions: list[str] | None = None,
    ) -> None:
        """Initialize binary file error with detection context.

        Args:
            message: Description of the binary content detection
            file_path: Path to the binary file
            detected_encoding: Encoding detected during analysis
            details: Additional detection diagnostics
            suggestions: Steps for handling binary content
        """
        error_details = details or {}
        if file_path:
            error_details["file_path"] = file_path
        if detected_encoding:
            error_details["detected_encoding"] = detected_encoding

        default_suggestions = suggestions or [
            "Add file extension to binary exclusion filters",
            "Update file discovery patterns to skip binary files",
            "Check if file is actually text with unusual encoding",
        ]

        super().__init__(message, details=error_details, suggestions=default_suggestions)
        self.file_path = file_path
        self.detected_encoding = detected_encoding


class ASTDepthExceededError(ChunkingError):
    """Abstract syntax tree nesting exceeds safe depth limit.

    Raised when the AST contains deeply nested structures that may cause
    stack overflow or excessive memory usage during traversal. This limit
    protects against pathological input and ensures robust operation.

    Excessive AST depth typically indicates generated code, obfuscation,
    or unusual coding patterns that require special handling.
    """

    def __init__(
        self,
        message: str,
        *,
        actual_depth: int | None = None,
        max_depth: int | None = None,
        file_path: str | None = None,
        details: dict[str, Any] | None = None,
        suggestions: list[str] | None = None,
    ) -> None:
        """Initialize AST depth error with nesting metrics.

        Args:
            message: Description of the depth limit violation
            actual_depth: Measured AST nesting depth
            max_depth: Configured maximum safe depth
            file_path: Path to the file with deep nesting
            details: Additional depth-related diagnostics
            suggestions: Strategies for handling deep nesting
        """
        error_details = details or {}
        if actual_depth:
            error_details["actual_depth"] = actual_depth
        if max_depth:
            error_details["max_depth"] = max_depth
            if actual_depth:
                error_details["depth_overflow"] = actual_depth - max_depth
        if file_path:
            error_details["file_path"] = file_path

        default_suggestions = suggestions or [
            "Increase AST depth limit configuration if safe",
            "Refactor code to reduce nesting complexity",
            "Consider using iterative traversal for deep structures",
            "Exclude generated or obfuscated files from processing",
        ]

        super().__init__(message, details=error_details, suggestions=default_suggestions)
        self.actual_depth = actual_depth
        self.max_depth = max_depth
        self.file_path = file_path


__all__ = (
    "ASTDepthExceededError",
    "BinaryFileError",
    "ChunkLimitExceededError",
    "ChunkingError",
    "ChunkingTimeoutError",
    "OversizedChunkError",
    "ParseError",
)
