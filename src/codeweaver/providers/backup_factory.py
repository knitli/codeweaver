# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Dynamic class factory for creating namespaced provider variants.

Creates backup (and future tagged) providers that operate independently with their own
configuration, state, and lifecycle. The namespacing via inheritance makes identification
trivial - isinstance(p, BackupEmbeddingProvider) or p.is_provider_backup.

Design Rationale:
- Earlier backup systems piled providers with multiple configs, creating state management nightmares
- This factory creates distinct types that DI can resolve independently
- Inheriting from Backup* bases preserves type-level discrimination and existing patterns
- Caching ensures consistent class identity across calls
- Future extension point for strategy tagging (fast, precise, etc.)
"""

from __future__ import annotations

from typing import Any, cast


# Cache for dynamic backup classes - ensures consistent class identity
_backup_class_cache: dict[type, type] = {}

_tagged_class_cache: dict[tuple[tuple[str, ...], type], type] = {}

def _safe_to_create_tagged_class(provider_cls: type, processed_tag: str) -> bool:
    """Check if it's safe to create a tagged class for the given provider class.

    Ensures that the provider class is not already a tagged class itself.
    """
    if not hasattr(provider_cls, "__mro__"):
        return False
    if any(
        base.__name__.startswith(processed_tag) and base is not provider_cls
        for base in provider_cls.__mro__
    ):
        return False
    

def create_backup_class[T: type[T], TaggedT: type[T]](
    provider_cls: type[T], *, extra_namespace: dict[str, Any] | None = None
) -> TaggedT:
    """Create a tagged variant of a provider class.

    Uses inheritance from appropriate Backup* base class to preserve:
    - is_provider_backup property returning True
    - isinstance checks working correctly
    - Type-level DI discrimination

    Args:
        provider_cls: The concrete provider class (e.g., SentenceTransformersProvider)
        extra_namespace: Additional class attributes/methods to add

    Returns:
        A new class like BackupSentenceTransformersProvider

    Raises:
        TypeError: If no backup base class is found for the provider type
    """
    # Return cached class if already created
    if provider_cls in _backup_class_cache:
        return cast(TaggedT, _backup_class_cache[provider_cls])

    class_name = f"Backup{provider_cls.__name__}"
    namespace = {
        "__doc__": f"Backup variant of {provider_cls.__name__}.",
        "__module__": provider_cls.__module__,
        **(extra_namespace or {}),
    }

    # Create class inheriting from both backup base and concrete provider
    # MRO: BackupSentenceTransformersProvider -> BackupEmbeddingProvider -> SentenceTransformersProvider -> ...
    backup_cls = type(class_name, (backup_base, provider_cls), namespace)

    _backup_class_cache[provider_cls] = backup_cls
    return backup_cls  # type: ignore[return-value]


def clear_backup_class_cache() -> None:
    """Clear the backup class cache. Primarily for testing."""
    _backup_class_cache.clear()


def create_tagged_class[T](
    provider_cls: type[T], tags: frozenset[str], *, extra_namespace: dict[str, Any] | None = None
) -> type[T]:
    """Create a tagged variant of a provider class.

    Tags could include: "fast", "precise", "backup", "experimental", etc.
    This allows DI resolution by capability/strategy rather than just type.
    """
    class_name = f"{provider_cls.__name__}_" + "_".join(sorted(tags))
    namespace = {
        "__doc__": f"Tagged variant of {provider_cls.__name__} with tags: {', '.join(sorted(tags))}.",
        "__module__": provider_cls.__module__,
        "tags": tags,
        **(extra_namespace or {}),
    }
    return type(class_name, (provider_cls,), namespace)


__all__ = (
    "clear_backup_class_cache",
    "create_backup_class",
    "create_tagged_class",
\)
