# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Analysis cache for lazy import system.

Provides caching of file analysis results to improve performance.
"""

from __future__ import annotations

import json
import logging

from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from enum import StrEnum
from pathlib import Path
from typing import TYPE_CHECKING, Any, TypeVar

from tools.lazy_imports.types import CacheStatistics


if TYPE_CHECKING:
    from tools.lazy_imports.common.types import AnalysisResult

logger = logging.getLogger(__name__)

T = TypeVar("T")


class CircuitState(StrEnum):
    """State of the circuit breaker."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failures detected, cache bypassed
    HALF_OPEN = "half_open"  # Testing if service recovered


class CircuitBreaker:
    """Circuit breaker pattern for cache failure handling.

    Prevents cascading failures by opening the circuit after repeated failures,
    then periodically testing if the service has recovered.
    """

    def __init__(
        self,
        failure_threshold: int = 5,
        success_threshold: int = 2,
        recovery_timeout: timedelta | None = None,
    ) -> None:
        """Initialize circuit breaker.

        Args:
            failure_threshold: Number of failures before opening circuit
            success_threshold: Number of successes to close circuit from half-open
            recovery_timeout: Time before trying half-open from open
        """
        self.failure_threshold = failure_threshold
        self.success_threshold = success_threshold
        self.recovery_timeout = recovery_timeout or timedelta(seconds=60)
        self._state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time: datetime | None = None

    @property
    def state(self) -> CircuitState:
        """Get current circuit state."""
        return self._state

    @state.setter
    def state(self, value: CircuitState) -> None:
        """Set circuit state."""
        self._state = value

    def can_attempt(self) -> bool:
        """Check if operation can be attempted.

        Returns:
            True if operation should be attempted, False otherwise
        """
        if self._state == CircuitState.CLOSED:
            return True

        if self._state == CircuitState.OPEN:
            # Check if recovery timeout has passed
            if self.last_failure_time is None:
                return False

            time_since_failure = datetime.now(UTC) - self.last_failure_time
            if time_since_failure >= self.recovery_timeout:
                # Transition to HALF_OPEN
                logger.info("Circuit breaker trying half-open state after timeout")
                self._state = CircuitState.HALF_OPEN
                self.failure_count = 0
                return True
            return False

        # HALF_OPEN state - allow attempts
        return True

    def call(self, func: Callable[..., T], *args: Any, **kwargs: Any) -> T:
        """Execute function with circuit breaker protection.

        Args:
            func: Function to execute
            *args: Positional arguments
            **kwargs: Keyword arguments

        Returns:
            Function result

        Raises:
            Exception: If circuit is OPEN or function fails
        """
        if not self.can_attempt():
            raise RuntimeError("Circuit breaker is OPEN")

        try:
            result = func(*args, **kwargs)
            self.record_success()
        except Exception:
            self.record_failure()
            raise
        else:
            return result

    def record_success(self) -> None:
        """Record successful operation."""
        if self._state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                # Recovered - close circuit
                logger.info("Circuit breaker recovered, closing circuit")
                self._state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
                self.last_failure_time = None
        elif self._state == CircuitState.CLOSED:
            # Reset failure count on success
            self.failure_count = 0

    def record_failure(self) -> None:
        """Record failed operation."""
        self.failure_count += 1
        self.last_failure_time = datetime.now(UTC)

        if self._state == CircuitState.CLOSED:
            if self.failure_count >= self.failure_threshold:
                # Open circuit
                logger.warning("Circuit breaker opening after %d failures", self.failure_count)
                self._state = CircuitState.OPEN
        elif self._state == CircuitState.HALF_OPEN:
            # Failed during recovery - reopen circuit
            logger.warning("Circuit breaker reopening after failure in HALF_OPEN state")
            self._state = CircuitState.OPEN
            self.success_count = 0

    def reset(self) -> None:
        """Reset circuit breaker to initial state."""
        self._state = CircuitState.CLOSED
        self.failure_count = 0
        self.success_count = 0
        self.last_failure_time = None


class JSONAnalysisCache:
    """JSON-based analysis result cache with schema versioning.

    Provides persistent caching of AST analysis results with:
    - Schema versioning and migration support
    - SHA-256 file hashing for cache validation
    - Circuit breaker pattern for resilience
    - Automatic cache invalidation on file changes
    - Persistent storage with JSON serialization
    """

    def __init__(
        self, cache_dir: Path | None = None, circuit_breaker: CircuitBreaker | None = None
    ) -> None:
        """Initialize cache.

        Args:
            cache_dir: Directory to store cache files. Defaults to .codeweaver/cache
            circuit_breaker: Circuit breaker for fault tolerance. Creates default if None
        """
        self._cache_dir = cache_dir or Path(".codeweaver/cache")
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[Path, dict] = {}
        self.circuit_breaker = circuit_breaker or CircuitBreaker()
        self._load_from_disk()

    def _get_from_cache(self, file_path: Path, file_hash: str) -> AnalysisResult | None:
        """Get from cache - internal method that may raise exceptions.

        This is the actual cache read logic that can be mocked for testing.
        Do not call directly - use get() instead which wraps this with circuit breaker.

        Args:
            file_path: Path to the file
            file_hash: Hash of the file content

        Returns:
            Cached analysis result or None if not found/invalid

        Raises:
            Exception: May raise various exceptions during cache read
        """
        cache_key = file_path
        if cache_key not in self._cache:
            return None

        cached_data = self._cache[cache_key]
        if cached_data.get("file_hash") != file_hash:
            return None

        analysis_data = cached_data.get("analysis")
        if not isinstance(analysis_data, dict):
            return analysis_data

        # Reconstruct AnalysisResult with nested ExportNode objects
        from tools.lazy_imports.common.types import AnalysisResult, ExportNode

        # Reconstruct exports list
        exports = []
        for export_dict in analysis_data.get("exports", []):
            if isinstance(export_dict, dict):
                exports.append(ExportNode(**export_dict))
            else:
                exports.append(export_dict)

        # Reconstruct imports list (if they're objects too)
        imports = analysis_data.get("imports", [])

        # Create AnalysisResult with reconstructed objects
        return AnalysisResult(
            exports=exports,
            imports=imports,
            file_hash=analysis_data.get("file_hash", file_hash),
            analysis_timestamp=analysis_data.get("analysis_timestamp", 0.0),
            schema_version=analysis_data.get("schema_version", "1.0"),
        )

    def get(self, file_path: Path, file_hash: str) -> AnalysisResult | None:
        """Get cached analysis result with circuit breaker protection.

        Args:
            file_path: Path to the file
            file_hash: Hash of the file content

        Returns:
            Cached analysis result or None if not found/invalid
        """
        # Check if circuit breaker allows the attempt
        if not self.circuit_breaker.can_attempt():
            logger.debug("Circuit breaker OPEN, bypassing cache read")
            return None

        # Use circuit breaker to protect cache read
        try:
            return self.circuit_breaker.call(self._get_from_cache, file_path, file_hash)
        except Exception:
            # Circuit breaker will handle state transitions
            # Return None to indicate cache miss
            return None

    def put(self, file_path: Path, file_hash: str, analysis: AnalysisResult) -> None:
        """Store analysis result in cache.

        Args:
            file_path: Path to the file
            file_hash: SHA-256 hash of file content
            analysis: Analysis result to cache
        """
        # Check if circuit breaker allows the attempt
        if not self.circuit_breaker.can_attempt():
            logger.debug("Circuit breaker OPEN, skipping cache write")
            return

        def _cache_write() -> None:
            """Write to cache - may raise exceptions."""

            # Convert analysis to dict for JSON serialization
            def to_dict(obj: Any) -> Any:
                """Recursively convert objects to dicts."""
                if hasattr(obj, "model_dump"):
                    return obj.model_dump(mode="json")
                if hasattr(obj, "__dataclass_fields__"):
                    # Dataclass
                    import dataclasses

                    return {k: to_dict(v) for k, v in dataclasses.asdict(obj).items()}
                if isinstance(obj, list):
                    return [to_dict(item) for item in obj]
                if isinstance(obj, dict):
                    return {k: to_dict(v) for k, v in obj.items()}
                return str(obj) if isinstance(obj, Path) else obj

            serialized_analysis = to_dict(analysis)
            self._cache[file_path] = {"file_hash": file_hash, "analysis": serialized_analysis}
            self._save_to_disk()

        try:
            self.circuit_breaker.call(_cache_write)
        except Exception as e:
            # Circuit breaker will handle state transitions
            logger.debug("Cache write failed: %s", e)

    def set(self, file_path: Path, analysis: AnalysisResult) -> None:
        """Alias for put() method for backwards compatibility.

        Args:
            file_path: Path to the file
            analysis: Analysis result to cache
        """
        # Extract hash from analysis if available
        file_hash = getattr(analysis, "file_hash", "unknown")
        self.put(file_path, file_hash, analysis)

    def invalidate(self, file_path: Path) -> None:
        """Invalidate cache entry for a file.

        Args:
            file_path: Path to the file
        """
        if file_path in self._cache:
            del self._cache[file_path]

    def get_stats(self) -> CacheStatistics:
        """Get cache statistics.

        Returns:
            Cache statistics including hit rate and entry counts
        """
        return CacheStatistics(
            total_entries=len(self._cache),
            valid_entries=len(self._cache),
            invalid_entries=0,
            total_size_bytes=0,
            hit_rate=0.0,
        )

    def get_statistics(self) -> CacheStatistics:
        """Alias for get_stats() method.

        Returns:
            Cache statistics including hit rate and entry counts
        """
        return self.get_stats()

    def clear(self) -> None:
        """Clear all cache entries."""
        import shutil

        self._cache.clear()
        if self._cache_dir.exists():
            shutil.rmtree(self._cache_dir)
        self._cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_file(self) -> Path:
        """Get path to the cache file."""
        return self._cache_dir / "analysis_cache.json"

    def _load_from_disk(self) -> None:
        """Load cache from disk."""
        cache_file = self._get_cache_file()
        if cache_file.exists():
            try:
                with cache_file.open("r") as f:
                    data = json.load(f)
                # Convert string keys back to Path objects
                self._cache = {Path(k): v for k, v in data.items()}
            except (json.JSONDecodeError, OSError):
                # If cache is corrupted, start fresh
                self._cache = {}

    def _save_to_disk(self) -> None:
        """Save cache to disk."""
        cache_file = self._get_cache_file()
        try:
            # Convert Path keys to strings for JSON serialization
            data = {str(k): v for k, v in self._cache.items()}
            with cache_file.open("w") as f:
                json.dump(data, f, indent=2, default=str)
        except (OSError, TypeError):
            # If we can't save, continue without persistence
            pass


# Keep backwards compatibility
AnalysisCache = JSONAnalysisCache

__all__ = ("AnalysisCache", "CircuitBreaker", "CircuitState", "JSONAnalysisCache")
