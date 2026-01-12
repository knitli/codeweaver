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

import logging

from typing import Any, Literal, cast

import textcase


_BASE_CLASS_NAMES = (
    "BaseEmbeddingConfig",
    "BaseProviderSettings",
    "BaseRerankingConfig",
    "ClientOptions",
    "EmbeddingCapabilityResolver",
    "EmbeddingProvider",
    "EmbeddingProviderCapabilities",
    "RerankingCapabilityResolver",
    "RerankingProvider",
    "RerankingProviderCapabilities",
    "SparseEmbeddingCapabilityResolver",
    "SparseEmbeddingProvider",
    "SparseEmbeddingProviderCapabilities",
    "VectorStoreOptions",
)

logger = logging.getLogger(__name__)

# Cache for dynamic backup classes - ensures consistent class identity
_backup_class_cache: dict[type, type] = {}

_tagged_class_cache: dict[tuple[tuple[str, ...], type], type] = {}


def _safe_to_create_tagged_class(provider_cls: type, processed_tag: str) -> bool:
    """Check if it's safe to create a tagged class for the given provider class.

    Ensures that the provider class is not already a tagged class itself.
    """
    if not hasattr(provider_cls, "__mro__"):
        return False
    return processed_tag not in provider_cls.__name__


def _make_tagged_classname(provider_cls: type, tags: frozenset[str] | Literal["backup"]) -> str:
    if tags == "backup":
        return f"{textcase.pascal(cast(Literal['backup'], tags))}{provider_cls.__name__}"
    # textcase.pascal will convert "fast_precise" to "FastPrecise"
    return f"{provider_cls.__name__}__{textcase.pascal('_'.join(sorted(tags)))}"


def _create_namespace(
    newcls: type, extra_namespace: dict[str, Any] | None = None
) -> dict[str, Any]:
    ns = {
        "__qualname__": f"Backup{newcls.__qualname__}",
        "__doc__": f"Backup variant of {newcls.__name__}.",
        "__module__": newcls.__module__,
        "is_provider_backup": True,
    }
    if extra_namespace:
        ns |= extra_namespace
    return ns


def _make_parent_backup(provider_cls: type, parent_cls: type) -> type:
    if parent_cls in _backup_class_cache:
        return _backup_class_cache[parent_cls]
    _backup_class_cache[parent_cls] = type(
        _make_tagged_classname(parent_cls, "backup"),
        parent_cls.__bases__,
        _create_namespace(parent_cls),
    )
    return _backup_class_cache[parent_cls]


def _make_inherited_backup(
    provider_cls: type, parent_cls: type, namespace: dict[str, Any] | None = None
) -> type:
    def _create_backup_class(final_parent: type) -> type:
        _backup_class_cache[provider_cls] = type(
            _make_tagged_classname(provider_cls, "backup"),
            tuple(cls if cls is not parent_cls else final_parent for cls in provider_cls.__bases__),
            _create_namespace(provider_cls, namespace),
        )
        return _backup_class_cache[provider_cls]

    if base_backup_made := next(
        (cls for cls in provider_cls.__mro__ if cls in _backup_class_cache), None
    ):
        return _create_backup_class(base_backup_made)
    parent_backup = _make_parent_backup(provider_cls, parent_cls)
    return _create_backup_class(parent_backup)


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
    if not hasattr(provider_cls, "__name__") or not hasattr(provider_cls, "__mro__"):
        logger.warning(
            "Provider class %s lacks __name__ or __mro__; cannot create backup class.", provider_cls
        )
        raise TypeError(f"Cannot create backup class for {provider_cls}")
    if "backup" in provider_cls.__name__.lower():
        return cast(TaggedT, provider_cls)
    if not (_is_base_class := provider_cls.__name__ in _BASE_CLASS_NAMES) and (
        base := next(
            (cls for cls in provider_cls.__mro__ if cls.__name__ in _BASE_CLASS_NAMES), None
        )
    ):
        return cast(TaggedT, _make_inherited_backup(provider_cls, base, extra_namespace))
    _backup_class_cache[provider_cls] = type(
        _make_tagged_classname(provider_cls, "backup"),
        provider_cls.__bases__,
        _create_namespace(provider_cls, extra_namespace),
    )
    return cast(TaggedT, _backup_class_cache[provider_cls])


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
    class_name = _make_tagged_classname(provider_cls, tags)
    namespace = {
        "__doc__": f"Tagged variant of {provider_cls.__name__} with tags: {', '.join(sorted(tags))}.",
        "__module__": provider_cls.__module__,
        "tags": tags,
        **(extra_namespace or {}),
    }
    return cast(type[T], type(class_name, (provider_cls,), namespace))


__all__ = ("clear_backup_class_cache", "create_backup_class", "create_tagged_class")
