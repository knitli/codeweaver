# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Registry for maintaining per-file source IDs for span consistency."""

from __future__ import annotations

from pathlib import Path
from weakref import WeakValueDictionary

from pydantic import UUID7

from codeweaver._common import BasedModel
from codeweaver._utils import uuid7


class SourceIdRegistry(BasedModel):
    """Maintains per-file source IDs to ensure span consistency within files.

    This registry ensures that all spans from the same file share the same source_id, enabling set-like span operations and clean merging/splitting.
    """

    def __init__(self) -> None:
        """Initialize the registry."""
        self._registry: dict[Path, UUID7] = {}
        # Keep weak references to avoid memory leaks for temporary file processing
        self._weak_registry: WeakValueDictionary[Path, UUID7] = WeakValueDictionary()

    def source_id_for(self, file_path: Path) -> UUID7:
        """Get or create a source ID for the given file path.

        Args:
            file_path: Path to the file

        Returns:
            Hex string representation of the UUID7 source ID
        """
        if file_path not in self._registry:
            self._registry[file_path] = uuid7()
        return self._registry[file_path]

    def clear(self) -> None:
        """Clear the registry."""
        self._registry.clear()
        self._weak_registry.clear()

    def remove(self, file_path: Path) -> bool:
        """Remove a file from the registry.

        Args:
            file_path: Path to remove

        Returns:
            True if the file was in the registry, False otherwise
        """
        # TODO: We need to send a signal to vector stores to remove associated vectors
        removed = file_path in self._registry
        _ = self._registry.pop(file_path, None)
        _ = self._weak_registry.pop(file_path, None)
        return removed

    def __len__(self) -> int:
        """Return the number of files in the registry."""
        return len(self._registry)

    def __contains__(self, file_path: Path) -> bool:
        """Check if a file path is in the registry."""
        return file_path in self._registry


# Global registry instance for the process
_global_registry = SourceIdRegistry()


def source_id_for(file_path: Path) -> UUID7:
    """Get or create a source ID for the given file path using the global registry.

    Args:
        file_path: Path to the file

    Returns:
        Hex string representation of the UUID7 source ID
    """
    return _global_registry.source_id_for(file_path)


def clear_registry() -> None:
    """Clear the global registry."""
    _global_registry.clear()


def get_registry() -> SourceIdRegistry:
    """Get the global registry instance."""
    return _global_registry
