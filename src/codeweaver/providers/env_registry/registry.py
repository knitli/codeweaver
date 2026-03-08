# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Central registry for provider environment configurations.

Provides lazy loading, caching, and query API for provider configs.
Thread-safe, supports external registration.
"""

import threading

from functools import cache
from typing import Any, ClassVar

from codeweaver.providers.env_registry.models import ProviderEnvConfig


class ProviderEnvRegistry:
    """Central registry for provider environment configurations.

    Features:
    - Lazy initialization (only loads when first accessed)
    - Thread-safe initialization
    - External registration support
    - Efficient lookup and querying
    - Inheritance resolution

    Example:
        >>> # Get all configs for a provider
        >>> configs = ProviderEnvRegistry.get("deepseek")
        >>>
        >>> # Get just API key env vars
        >>> api_keys = ProviderEnvRegistry.get_api_key_envs("openai")
        >>>
        >>> # Get configs for specific client
        >>> azure_openai = ProviderEnvRegistry.get_for_client("azure", "openai")
    """

    _registry: ClassVar[dict[str, list[ProviderEnvConfig]]] = {}
    _lock: ClassVar[threading.RLock] = threading.RLock()
    _initialized: ClassVar[bool] = False

    @classmethod
    def register(
        cls,
        provider: str,
        config: ProviderEnvConfig | list[ProviderEnvConfig],
        *,
        external: bool = False,
    ) -> None:
        """Register provider configuration.

        Note: External registration is an internal API and may change.
        CodeWeaver has no stable public API during alpha phase.

        Args:
            provider: Provider name (lowercase)
            config: Single config or list of configs
            external: If True, this is an external registration (plugin/extension).
                     Prevents conflicts with built-in providers.

        Raises:
            ValueError: If external provider conflicts with built-in provider

        Example (internal use only):
            >>> ProviderEnvRegistry.register(
            ...     "myprovider", ProviderEnvConfig(...), external=True
            ... )
        """
        if isinstance(config, ProviderEnvConfig):
            config = [config]

        provider_key = provider.lower()

        with cls._lock:
            # Check for conflicts if external
            if external and provider_key in cls._registry:
                raise ValueError(
                    f"Cannot register external provider '{provider}': "
                    f"conflicts with built-in provider"
                )

            cls._registry[provider_key] = config

    @classmethod
    def get(cls, provider: str) -> list[ProviderEnvConfig]:
        """Get all configurations for a provider.

        Handles inheritance - if a config has `inherits_from`, the parent's
        configs are included in the result.

        Args:
            provider: Provider name (case-insensitive)

        Returns:
            List of ProviderEnvConfig instances (empty if not found)

        Example:
            >>> configs = ProviderEnvRegistry.get("deepseek")
            >>> # Returns [DeepSeek config, OpenAI inherited configs]
        """
        cls._ensure_initialized()

        provider_key = provider.lower()
        configs = cls._registry.get(provider_key, [])

        # Resolve inheritance
        resolved = []
        for cfg in configs:
            if cfg.inherits_from:
                # Add parent configs first
                parent_configs = cls.get(cfg.inherits_from)
                resolved.extend(parent_configs)
            resolved.append(cfg)

        return resolved

    @classmethod
    @cache
    def get_api_key_envs(cls, provider: str) -> tuple[str, ...]:
        """Get API key environment variable names for a provider.

        Cached for performance.

        Args:
            provider: Provider name

        Returns:
            Tuple of environment variable names (e.g., ("OPENAI_API_KEY",))

        Example:
            >>> api_keys = ProviderEnvRegistry.get_api_key_envs("openai")
            >>> print(api_keys)
            ('OPENAI_API_KEY',)
        """
        configs = cls.get(provider)
        return tuple(cfg.api_key.env for cfg in configs if cfg.api_key)

    @classmethod
    def get_for_client(cls, provider: str, client: str) -> tuple[ProviderEnvConfig, ...]:
        """Get configs for provider filtered by client SDK.

        Args:
            provider: Provider name
            client: SDK provider's name (e.g., "openai", "anthropic"); the result of `SDKClient.SOME_MEMBER.variable`

        Returns:
            Tuple of matching configs

        Example:
            >>> configs = ProviderEnvRegistry.get_for_client("azure", "openai")
            >>> # Returns only Azure OpenAI config, not Cohere or Anthropic
        """
        configs = cls.get(provider)
        return tuple(cfg for cfg in configs if client in cfg.clients)

    @classmethod
    def all_providers(cls) -> tuple[str, ...]:
        """Get all registered provider names.

        Returns:
            Tuple of provider names (lowercase, sorted)

        Example:
            >>> providers = ProviderEnvRegistry.all_providers()
            >>> print(len(providers))
            40
        """
        cls._ensure_initialized()
        return tuple(sorted(cls._registry.keys()))

    @classmethod
    def all_configs(cls) -> dict[str, list[ProviderEnvConfig]]:
        """Get all registered provider configurations.

        Returns:
            Dictionary mapping provider names to their configs

        Example:
            >>> all_configs = ProviderEnvRegistry.all_configs()
            >>> for provider, configs in all_configs.items():
            ...     print(f"{provider}: {len(configs)} config(s)")
        """
        cls._ensure_initialized()
        return cls._registry.copy()

    @classmethod
    def to_dict(cls) -> dict[str, list[dict[str, Any]]]:
        """Export all configurations as dictionaries.

        Used by MCP registry generation script.

        Returns:
            Serializable dictionary of all configs

        Example:
            >>> import json
            >>> data = ProviderEnvRegistry.to_dict()
            >>> json.dumps(data, indent=2)
        """
        cls._ensure_initialized()
        return {
            provider: [cfg.to_dict() for cfg in configs]
            for provider, configs in cls._registry.items()
        }

    @classmethod
    def _ensure_initialized(cls) -> None:
        """Lazy initialization of registry.

        Thread-safe. Only runs once per process.
        Automatically discovers and registers all provider definitions.
        """
        if cls._initialized:
            return

        with cls._lock:
            # Double-check after acquiring lock
            if cls._initialized:
                return

            # Import and auto-register from definition modules
            from codeweaver.providers.env_registry import definitions

            # Discover all uppercase attributes that are configs
            for name in dir(definitions):
                if name.startswith("_") or not name.isupper():
                    continue

                value = getattr(definitions, name)

                # Handle both single configs and lists
                if isinstance(value, ProviderEnvConfig) or (
                    isinstance(value, list) and value and isinstance(value[0], ProviderEnvConfig)
                ):
                    cls.register(name.lower(), value)

            cls._initialized = True

    @classmethod
    def _reset(cls) -> None:
        """Reset registry (for testing only).

        Warning:
            This method is only intended for use in tests.
            Do not call in production code.
        """
        with cls._lock:
            cls._registry.clear()
            cls._initialized = False
            # Clear caches
            cls.get_api_key_envs.cache_clear()


__all__ = ("ProviderEnvRegistry",)
