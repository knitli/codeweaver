# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Registry for maintaining per-file source IDs for span consistency."""

from __future__ import annotations

import logging

from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING
from weakref import WeakValueDictionary

from pydantic import UUID7

from codeweaver.core import UUID7Hex, UUID7HexT, UUIDStore


ONE_MEGABYTE = 1024 * 1024


if TYPE_CHECKING:
    from codeweaver.core import AnonymityConversion, FilteredKeyT
    from codeweaver.core.discovery import DiscoveredFile

logger = logging.getLogger(__name__)


class SourceIdRegistry(UUIDStore["DiscoveredFile"]):
    """Maintains per-file source IDs to ensure span consistency within files.

    This registry ensures that all spans from the same file share the same source_id, enabling set-like span operations and clean merging/splitting.
    """

    store: dict[UUID7, "DiscoveredFile"]

    _trash_heap: WeakValueDictionary[UUID7, "DiscoveredFile"]

    def __init__(self) -> None:
        """Initialize the registry."""
        from codeweaver.core.di.container import get_container
        from codeweaver.core.discovery import DiscoveredFile

        try:
            container = get_container()
            container.register(type(self), lambda: self, singleton=True)
        except Exception as e:
            # Log if DI not available (monorepo compatibility)
            logger.debug(
                "Dependency injection container not available, skipping registration of SourceIdRegistry: %s",
                e,
            )
        super().__init__(
            store={},
            size_limit=ONE_MEGABYTE * 5,
            _value_type=DiscoveredFile,
            _trash_heap=WeakValueDictionary(),
        )

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        from codeweaver.core import AnonymityConversion, FilteredKey

        return {
            FilteredKey("store"): AnonymityConversion.COUNT,
            FilteredKey("_trash_heap"): AnonymityConversion.FORBIDDEN,
        }

    @property
    def path_mapping(self) -> MappingProxyType[Path, UUID7]:
        """Mapping from file paths to their corresponding source IDs."""
        return MappingProxyType({file.path: file.source_id for file in self.store.values()})

    def file_from_path(self, path: Path) -> "DiscoveredFile | None":
        """Get the DiscoveredFile instance for a given file path."""
        # first we need to normalize the path
        path = path.resolve()
        source_id = self.path_mapping.get(path)
        return None if source_id is None else self.store.get(source_id)

    def source_id_for(self, file: "DiscoveredFile") -> UUID7HexT:
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
        if file.source_id in self.store and self.store[file.source_id] is not file:
            self.store[file.source_id] = file
        return UUID7Hex(file.source_id.hex)

    def clear(self) -> None:
        """Clear the registry."""
        self.store.clear()
        self._trash_heap.clear()

    def remove(self, value: UUID7 | "DiscoveredFile") -> bool:
        """Remove a file from the registry.

        Args:
            value: UUID7 source ID or DiscoveredFile instance to remove

        Returns:
            True if the file was in the registry, False otherwise
        """
        from codeweaver.core.discovery import DiscoveredFile

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


__all__ = ("SourceIdRegistry",)
