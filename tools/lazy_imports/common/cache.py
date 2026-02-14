# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Analysis cache for lazy import system.

Provides caching of file analysis results to improve performance.
"""

from __future__ import annotations

import json
from pathlib import Path

from tools.lazy_imports.types import CacheStatistics


class JSONAnalysisCache:
    """Cache for analysis results.

    This is a placeholder implementation. The full version would:
    - Store analysis results in JSON files
    - Validate cache entries against file hashes
    - Provide efficient lookup and invalidation

    NOTE: Current implementation is in-memory only and does not persist across instances.
    """

    def __init__(self, cache_dir: Path | None = None) -> None:
        """Initialize cache.

        Args:
            cache_dir: Directory to store cache files. Defaults to .codeweaver/cache
        """
        self._cache_dir = cache_dir or Path(".codeweaver/cache")
        self._cache_dir.mkdir(parents=True, exist_ok=True)
        self._cache: dict[Path, dict] = {}
        self._load_from_disk()

    def get(self, file_path: Path, file_hash: str):
        """Get cached analysis result.

        Args:
            file_path: Path to the file
            file_hash: Hash of the file content

        Returns:
            Cached analysis result or None if not found/invalid
        """
        cache_key = file_path
        if cache_key in self._cache:
            cached_data = self._cache[cache_key]
            if cached_data.get("file_hash") == file_hash:
                analysis_data = cached_data.get("analysis")
                if isinstance(analysis_data, dict):
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
                return analysis_data
        return None

    def put(self, file_path: Path, file_hash: str, analysis) -> None:
        """Store analysis result in cache.

        Args:
            file_path: Path to the file
            file_hash: Hash of the file content
            analysis: Analysis result to cache
        """
        # Convert analysis to dict for JSON serialization
        def to_dict(obj):
            """Recursively convert objects to dicts."""
            if hasattr(obj, "model_dump"):
                return obj.model_dump(mode="json")
            elif hasattr(obj, "__dataclass_fields__"):
                # Dataclass
                import dataclasses
                return {k: to_dict(v) for k, v in dataclasses.asdict(obj).items()}
            elif isinstance(obj, list):
                return [to_dict(item) for item in obj]
            elif isinstance(obj, dict):
                return {k: to_dict(v) for k, v in obj.items()}
            elif isinstance(obj, Path):
                return str(obj)
            else:
                return obj

        analysis_dict = to_dict(analysis)
        self._cache[file_path] = {"file_hash": file_hash, "analysis": analysis_dict}
        self._save_to_disk()

    def set(self, file_path: Path, analysis) -> None:
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
        # Placeholder implementation
        if file_path in self._cache:
            del self._cache[file_path]

    def get_stats(self) -> CacheStatistics:
        """Get cache statistics.

        Returns:
            Cache statistics including hit rate and entry counts
        """
        # Placeholder implementation
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

__all__ = ("AnalysisCache", "JSONAnalysisCache")
