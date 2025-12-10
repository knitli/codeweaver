# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Resource governance for chunking operations.

This module provides resource limit enforcement during chunking operations
to prevent resource exhaustion and ensure responsive operation across large
codebases. The ResourceGovernor enforces timeouts and chunk count limits
through a context manager protocol.
"""

from __future__ import annotations

import time

from typing import TYPE_CHECKING, Any

from codeweaver.engine.chunker.exceptions import ChunkingTimeoutError, ChunkLimitExceededError


if TYPE_CHECKING:
    # Temporarily using Any as placeholder for type checking
    from typing import Protocol, Self

    class PerformanceSettings(Protocol):
        """Protocol for performance settings configuration."""

        chunk_timeout_seconds: int
        max_chunks_per_file: int


class ResourceGovernor:
    """Enforces resource limits during chunking operations.

    This context manager tracks operation timing and chunk counts to prevent
    resource exhaustion. It enforces two critical limits:

    1. **Timeout limit**: Maximum time allowed for chunking a single file
    2. **Chunk count limit**: Maximum chunks that can be generated per file

    The governor uses a context manager protocol to automatically initialize
    and clean up resource tracking. All resource checks are thread-safe through
    the use of instance-local state with no shared mutable data.

    Usage:
        ```python
        with ResourceGovernor(settings) as governor:
            for node in nodes:
                governor.check_timeout()  # Verify not timed out
                chunk = create_chunk(node)
                governor.register_chunk()  # Track and check limits
        ```

    Attributes:
        settings: Performance configuration containing timeout and limit values
        _start_time: Timestamp when context manager was entered (None when inactive)
        _chunk_count: Number of chunks registered in current operation

    Raises:
        ChunkingTimeoutError: When operation exceeds configured timeout
        ChunkLimitExceededError: When chunk count exceeds configured maximum
    """

    def __init__(self, settings: PerformanceSettings | Any) -> None:
        """Initialize resource governor with performance settings.

        Args:
            settings: Performance configuration containing:
                - chunk_timeout_seconds: Maximum operation time in seconds
                - max_chunks_per_file: Maximum chunks per file
        """
        self.settings = settings
        self._start_time: float | None = None
        self._chunk_count: int = 0

    def __enter__(self) -> Self:
        """Start resource tracking.

        Initializes timing and chunk counting for the current operation.
        Should be called automatically when entering the context manager.

        Returns:
            Self reference for use in with statement
        """
        self._start_time = time.time()
        self._chunk_count = 0
        return self

    def __exit__(
        self, exc_type: type[BaseException] | None, exc_val: BaseException | None, exc_tb: object
    ) -> None:
        """Clean up resource tracking.

        Resets internal state after operation completion or failure.
        Should be called automatically when exiting the context manager.

        Args:
            exc_type: Exception type if an error occurred
            exc_val: Exception value if an error occurred
            exc_tb: Exception traceback if an error occurred
        """
        self._start_time = None
        self._chunk_count = 0

    def check_timeout(self) -> None:
        """Check if operation has exceeded timeout limit.

        Compares elapsed time against configured timeout threshold.
        Safe to call even if context manager is not active (no-op).

        Raises:
            ChunkingTimeoutError: When elapsed time exceeds timeout_seconds
        """
        if self._start_time is None:
            return

        elapsed = time.time() - self._start_time
        if elapsed > self.settings.chunk_timeout_seconds:
            # Log resource limit violation for observability
            from pathlib import Path

            from codeweaver.engine.chunker import _logging as chunker_logging

            chunker_logging.log_chunking_resource_limit(
                file_path=Path("<governed>"),
                limit_type="timeout",
                limit_value=float(self.settings.chunk_timeout_seconds),
                actual_value=elapsed,
                extra_context={"chunk_count": self._chunk_count},
            )

            raise ChunkingTimeoutError(
                f"Chunking exceeded timeout of {self.settings.chunk_timeout_seconds}s",
                timeout_seconds=float(self.settings.chunk_timeout_seconds),
                elapsed_seconds=elapsed,
            )

    def check_chunk_limit(self) -> None:
        """Check if chunk count has exceeded configured limit.

        Compares current chunk count against maximum allowed per file.
        This prevents memory exhaustion and index bloat from pathological input.

        Raises:
            ChunkLimitExceededError: When chunk count exceeds maximum
        """
        if self._chunk_count > self.settings.max_chunks_per_file:
            # Log resource limit violation for observability
            from pathlib import Path

            from codeweaver.engine.chunker import _logging as chunker_logging

            chunker_logging.log_chunking_resource_limit(
                file_path=Path("<governed>"),
                limit_type="chunk_count",
                limit_value=float(self.settings.max_chunks_per_file),
                actual_value=float(self._chunk_count),
                extra_context={
                    "elapsed_seconds": time.time() - self._start_time if self._start_time else 0
                },
            )

            raise ChunkLimitExceededError(
                f"Exceeded maximum of {self.settings.max_chunks_per_file} chunks per file",
                chunk_count=self._chunk_count,
                max_chunks=self.settings.max_chunks_per_file,
            )

    def register_chunk(self) -> None:
        """Register a new chunk and enforce all resource limits.

        Increments the chunk counter and checks both timeout and chunk limits.
        This is the primary method to call after creating each chunk.

        Call this after successfully creating each chunk to maintain accurate
        resource tracking and enforcement.

        Raises:
            ChunkingTimeoutError: If timeout limit exceeded
            ChunkLimitExceededError: If chunk count limit exceeded
        """
        self._chunk_count += 1
        self.check_chunk_limit()
        self.check_timeout()


__all__ = ("ResourceGovernor",)
