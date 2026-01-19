# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Module for tracking indexing progress and statistics.

PURE state management and reporting. No UI dependencies.
"""

from __future__ import annotations

import time

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypedDict

from pydantic import Field

from codeweaver.core import BaseEnum, elapsed_time_to_human_readable
from codeweaver.core.types import BasedModel


if TYPE_CHECKING:
    from codeweaver.core import AnonymityConversion, FilteredKeyT


class IndexingErrorDict(TypedDict):
    """Structured error information for failed file indexing."""

    file_path: str
    error_type: str
    error_message: str
    phase: str
    timestamp: str


class IndexingStats(BasedModel):
    """Statistics tracking for indexing progress."""

    files_discovered: int = Field(0)
    files_processed: int = Field(0)
    chunks_created: int = Field(0)
    chunks_embedded: int = Field(0)
    chunks_indexed: int = Field(0)
    start_time: float = Field(default_factory=time.time)
    stopwatch_time: int = Field(default_factory=lambda: int(time.monotonic()))
    files_with_errors: list[Path] = Field(default_factory=list)
    structured_errors: list[IndexingErrorDict] = Field(default_factory=list)

    def elapsed_time(self) -> float:
        """Calculate elapsed time since indexing started."""
        return time.monotonic() - self.stopwatch_time

    def human_elapsed_time(self) -> str:
        """Get human-readable elapsed time."""
        return elapsed_time_to_human_readable(self.elapsed_time())

    def processing_rate(self) -> float:
        """Files processed per second."""
        elapsed = self.elapsed_time()
        return 0.0 if elapsed <= 0 else self.files_processed / elapsed

    def total_errors(self) -> int:
        """Total number of files with errors."""
        return len(self.files_with_errors)

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        from codeweaver.core import AnonymityConversion, FilteredKey

        return {
            FilteredKey("files_with_errors"): AnonymityConversion.COUNT,
            FilteredKey("structured_errors"): AnonymityConversion.COUNT,
        }

    def add_error(self, file_path: Path, error: Exception, phase: str) -> None:
        """Add a structured error to the tracking system."""
        if file_path not in self.files_with_errors:
            self.files_with_errors.append(file_path)
            self.structured_errors.append(
                IndexingErrorDict(
                    file_path=str(file_path),
                    error_type=type(error).__name__,
                    error_message=str(error),
                    phase=phase,
                    timestamp=datetime.now(UTC).isoformat(),
                )
            )

    def get_error_summary(self) -> dict[str, Any]:
        """Get summary of errors by phase and type."""
        if not self.structured_errors:
            return {"total_errors": 0, "by_phase": {}, "by_type": {}}

        by_phase: dict[str, int] = {}
        by_type: dict[str, int] = {}

        for error in self.structured_errors:
            phase = error["phase"]
            error_type = error["error_type"]
            by_phase[phase] = by_phase.get(phase, 0) + 1
            by_type[error_type] = by_type.get(error_type, 0) + 1

        return {
            "total_errors": len(self.structured_errors),
            "by_phase": by_phase,
            "by_type": by_type,
        }


class IndexingPhase(str, BaseEnum):
    """Enum representing different phases of the indexing process."""

    DISCOVERY = "discovery"
    CHUNKING = "chunking"
    EMBEDDING = "embedding"
    INDEXING = "indexing"
    COMPLETE = "complete"

    __slots__ = ()


class IndexingProgressTracker:
    """Pure state tracker for indexing progress.

    No UI code. Maintains IndexingStats and phase.
    """

    def __init__(self) -> None:
        """Initialize the tracker."""
        self.stats = IndexingStats()
        self.current_phase: IndexingPhase = IndexingPhase.DISCOVERY

    def update_phase(self, phase: IndexingPhase | str) -> None:
        """Update the current indexing phase."""
        self.current_phase = IndexingPhase(phase) if isinstance(phase, str) else phase

    def get_stats(self) -> IndexingStats:
        """Return the current stats."""
        return self.stats


__all__ = ("IndexingErrorDict", "IndexingPhase", "IndexingProgressTracker", "IndexingStats")
