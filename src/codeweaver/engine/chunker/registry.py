# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Registry for maintaining per-file source IDs for span consistency."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING
from weakref import WeakValueDictionary

from pydantic import UUID7

from codeweaver.core.discovery import DiscoveredFile
from codeweaver.core.stores import UUIDStore
from codeweaver.core.types.aliases import UUID7Hex, UUID7HexT


if TYPE_CHECKING:
    from codeweaver.core.types import AnonymityConversion, FilteredKeyT


class SourceIdRegistry(UUIDStore[DiscoveredFile]):
    """Maintains per-file source IDs to ensure span consistency within files.

    This registry ensures that all spans from the same file share the same source_id, enabling set-like span operations and clean merging/splitting.
    """

    store: dict[UUID7, DiscoveredFile]

    _trash_heap: WeakValueDictionary[UUID7, DiscoveredFile]

    def __init__(self) -> None:
        """Initialize the registry."""
        self.store: dict[UUID7, DiscoveredFile] = {}
        # Keep weak references to avoid memory leaks for temporary file processing
        self._trash_heap: WeakValueDictionary[UUID7, DiscoveredFile] = WeakValueDictionary()

        self._value_type = DiscoveredFile
        self._size_limit = 1024 * 1024 * 5  # 5MB

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        from codeweaver.core.types import AnonymityConversion, FilteredKey

        return {
            FilteredKey("store"): AnonymityConversion.COUNT,
            FilteredKey("_trash_heap"): AnonymityConversion.FORBIDDEN,
        }

    def source_id_for(self, file: DiscoveredFile) -> UUID7HexT:
        """Get or create a source ID for the given file.

        Uses the DiscoveredFile's existing source_id instead of generating a new one.
        This ensures consistency across the codeweaver system where DiscoveredFile
        objects serve as the canonical source of truth for file identity.

        Args:
            file: DiscoveredFile instance with existing source_id

        Returns:
            Hex string (newtype) representation of the file's UUID7 source_id
        """
        # Use the DiscoveredFile's existing source_id, don't generate a new one
        if file not in self.store.values():
            self.store[file.source_id] = file
        return UUID7Hex(file.source_id.hex)

    def clear(self) -> None:
        """Clear the registry."""
        self.store.clear()
        self._trash_heap.clear()

    def remove(self, value: UUID7 | DiscoveredFile) -> bool:
        """Remove a file from the registry.

        Args:
            value: UUID7 source ID or DiscoveredFile instance to remove

        Returns:
            True if the file was in the registry, False otherwise
        """
        if isinstance(value, DiscoveredFile):
            file = next((k for k, v in self.store.items() if v == value), None)
            if file is None:
                return False
        else:
            file = value
        removed = file in self.store
        _ = self.store.pop(file, None)
        _ = self._trash_heap.pop(file, None)
        return removed


# Global registry instance for the process
_globalstore: SourceIdRegistry | None = None


def source_id_for(file: DiscoveredFile) -> UUID7HexT:
    """Get or create a source ID for the given file path using the global registry.

    Args:
        file: DiscoveredFile instance

    Returns:
        Hex string representation of the UUID7 source ID
    """
    global _globalstore
    if _globalstore is None:
        _globalstore = SourceIdRegistry()
    return _globalstore.source_id_for(file)


def for_file_path(file_path: str | Path) -> UUID7HexT:
    """Get or create a source ID for the given file path using the global registry.

    Args:
        file_path: Path to the file as a string or Path object

    Returns:
        Hex string representation of the UUID7 source ID
    """
    from codeweaver.core.discovery import DiscoveredFile

    if discovered_file := DiscoveredFile.from_path(
        file_path if isinstance(file_path, Path) else Path(file_path)
    ):
        return source_id_for(discovered_file)
    raise ValueError(f"Could not discover file from path: {file_path}")


def clear_store() -> None:
    """Clear the global registry."""
    global _globalstore
    if _globalstore is not None:
        _globalstore.clear()


def get_store() -> SourceIdRegistry:
    """Get the global registry instance."""
    global _globalstore
    if _globalstore is None:
        _globalstore = SourceIdRegistry()
    return _globalstore


__all__ = ("SourceIdRegistry", "clear_store", "get_store", "source_id_for")
