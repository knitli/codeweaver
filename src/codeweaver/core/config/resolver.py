"""Configuration resolution system using DI container.

This module provides cross-config dependency resolution, allowing configs to
depend on other configs (e.g., vector store needs embedding dimension).

Extended in Phase 5 to support:
- Indexed config references: "embedding[0]" for primary, "embedding[*]" for all
- Collection-based resolution: Handle tuples of configs (primary + backups)
- Type-safe resolution with proper error handling
"""

from __future__ import annotations

import contextlib
import re

from typing import TYPE_CHECKING, Any, Protocol

from codeweaver.core.di import get_container


if TYPE_CHECKING:
    from codeweaver.core.config.registry import ConfigurableComponent


class ConfigurationSupplier(Protocol):
    """Protocol for supplying configuration instances."""

    async def get_configuration(self) -> Any:
        """Get the configuration instance.

        Returns:
            Configuration instance.
        """
        ...


class ConfigurableComponent(Protocol):
    """Protocol for components participating in config resolution.

    Components implementing this protocol can:
    1. Declare what other configs they depend on
    2. Receive resolved instances and adjust their own config

    Extended in Phase 5 to support indexed config references:
    - "embedding" - primary embedding config (backward compatible)
    - "embedding[0]" - primary embedding config (explicit)
    - "embedding[*]" - all embedding configs (primary + backups)
    - "embedding[1]" - first backup config
    """

    def config_dependencies(self) -> dict[str, type]:
        """Return types this config needs to resolve against.

        Returns:
            Dict mapping dependency name to type from DI container.

        Examples:
            Simple reference (backward compatible):
                {"embedding": EmbeddingProviderSettings}

            Indexed reference (Phase 5):
                {"embedding[0]": EmbeddingProviderSettings}  # Primary only
                {"embedding[*]": EmbeddingProviderSettings}  # All configs

            Multiple dependencies:
                {
                    "embedding[0]": EmbeddingProviderSettings,
                    "reranking": RerankingProviderSettings,
                }
        """
        ...

    async def apply_resolved_config(self, **resolved: Any) -> None:
        """Apply resolved configuration from dependencies.

        Args:
            **resolved: Resolved dependency instances from DI container.
                       Keys match those from config_dependencies().

        Note:
            Indexed references like "embedding[0]" will have the index
            stripped from the key, so you'll receive "embedding" as the key.
        """
        ...


def _parse_config_reference(ref: str) -> tuple[str, int | None]:
    """Parse a config reference into base name and optional index.

    Args:
        ref: Config reference string (e.g., "embedding", "embedding[0]", "embedding[*]")

    Returns:
        Tuple of (base_name, index) where:
        - base_name: The config kind (e.g., "embedding")
        - index: The index number, -1 for "*" (all), or None for no index

    Examples:
        >>> _parse_config_reference("embedding")
        ("embedding", None)
        >>> _parse_config_reference("embedding[0]")
        ("embedding", 0)
        >>> _parse_config_reference("embedding[*]")
        ("embedding", -1)
    """
    # Pattern: "name" or "name[index]" where index is a number or "*"
    match = re.match(r"^([a-z_]+)(?:\[(\d+|\*)\])?$", ref)
    if not match:
        return ref, None

    base_name = match.group(1)
    index_str = match.group(2)

    if index_str is None:
        return base_name, None
    if index_str == "*":
        return base_name, -1  # -1 means "all"
    return base_name, int(index_str)


async def _resolve_indexed_config(
    dep_name: str,
    dep_type: type,
    container: Any,
) -> Any | None:
    """Resolve a config dependency with optional indexing.

    Args:
        dep_name: Dependency name (may include index like "embedding[0]")
        dep_type: Type to resolve from DI container
        container: DI container instance

    Returns:
        Resolved config instance(s) or None if resolution fails

    Examples:
        "embedding" → primary config (backward compatible)
        "embedding[0]" → primary config (explicit)
        "embedding[*]" → tuple of all configs
        "embedding[1]" → first backup config
    """
    base_name, index = _parse_config_reference(dep_name)

    # Try to resolve the config
    with contextlib.suppress(AttributeError, KeyError, TypeError, ValueError, ImportError):
        resolved = await container.resolve(dep_type)

        # No indexing - return as-is (backward compatible)
        if index is None:
            return resolved

        # All configs requested (embedding[*])
        if index == -1:
            # If resolved is already a collection, return it
            if isinstance(resolved, tuple | list):
                return resolved
            # Otherwise wrap in tuple
            return (resolved,)

        # Specific index requested (embedding[0], embedding[1], etc.)
        # If resolved is a collection, extract the indexed item
        if isinstance(resolved, tuple | list):
            try:
                return resolved[index]
            except IndexError:
                # Index out of range - return None
                return None

        # If resolved is not a collection but index is 0, return it
        # (primary config case)
        if index == 0:
            return resolved

        # Otherwise we can't index into a non-collection
        return None

    return None


async def resolve_all_configs() -> None:
    """Resolve all configurations across the application.

    This should be called during settings finalization, after all
    configs are initialized but before the application starts.

    Extended in Phase 5 to support indexed config references:
    - "embedding" - resolves to primary config (backward compatible)
    - "embedding[0]" - resolves to primary config (explicit)
    - "embedding[*]" - resolves to all configs (tuple)
    - "embedding[1]" - resolves to first backup config

    Example:
        class VectorStoreConfig:
            def config_dependencies(self):
                return {"embedding[0]": EmbeddingProviderSettings}

            async def apply_resolved_config(self, embedding=None, **resolved):
                if embedding:
                    self._resolved_dimension = await embedding.get_dimension()
    """
    from codeweaver.core.config.registry import get_configurable_components

    container = get_container()
    configurables = get_configurable_components()

    for configurable in configurables:
        deps = configurable.config_dependencies()
        resolved = {}

        for dep_name, dep_type in deps.items():
            # Parse and resolve with indexing support
            resolved_config = await _resolve_indexed_config(dep_name, dep_type, container)

            if resolved_config is not None:
                # Strip index from key for apply_resolved_config()
                # "embedding[0]" becomes "embedding"
                base_name, _ = _parse_config_reference(dep_name)
                resolved[base_name] = resolved_config

        if resolved:
            await configurable.apply_resolved_config(**resolved)


__all__ = ("ConfigurableComponent", "resolve_all_configs")
