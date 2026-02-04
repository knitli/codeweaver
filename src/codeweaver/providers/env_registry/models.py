# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Lightweight dataclass models for provider environment configuration.

Uses frozen dataclasses with slots for performance and immutability.
Validation happens at build-time, not runtime.
"""

from __future__ import annotations

import os

from dataclasses import dataclass, field
from typing import Any

from codeweaver.core.types.env import EnvFormat, VariableInfo


@dataclass(frozen=True, slots=True)
class EnvVarConfig:
    """Configuration for a single environment variable.

    Immutable, lightweight, validated at build-time.

    Attributes:
        env: Environment variable name (e.g., "OPENAI_API_KEY")
        description: Human-readable description
        variable_name: Optional variable name in provider config
        variables: Optional tuple of VariableInfo for nested config
        is_secret: Whether this is a secret/sensitive value
        fmt: Optional format specification (e.g., EnvFormat.FILEPATH)
        choices: Optional frozenset of valid values
        default: Optional default value

    Example:
        >>> EnvVarConfig(
        ...     env="OPENAI_API_KEY",
        ...     description="Your OpenAI API Key",
        ...     is_secret=True,
        ...     variable_name="api_key",
        ... )
    """

    env: str
    description: str
    variable_name: str | None = None
    variables: tuple[VariableInfo, ...] | None = None
    is_secret: bool = False
    fmt: EnvFormat | None = None
    choices: frozenset[str] | None = None
    default: str | None = None

    def __post_init__(self) -> None:
        """Optional lightweight validation for development.

        Only runs if DEBUG_PROVIDER_VALIDATION environment variable is set.
        """
        if __debug__ and os.getenv("DEBUG_PROVIDER_VALIDATION"):
            if not self.env:
                raise ValueError("env cannot be empty")
            # Auto-convert choices to frozenset for convenience
            if self.choices is not None and not isinstance(self.choices, frozenset):
                object.__setattr__(self, "choices", frozenset(self.choices))


@dataclass(frozen=True, slots=True)
class ProviderEnvConfig:
    """Complete environment configuration for a provider.

    Represents one "set" of environment variables for a provider.
    Multi-client providers (like Azure) have multiple instances.

    Attributes:
        provider: Provider name (lowercase)
        clients: Tuple of client SDK names (e.g., ("openai",))
        note: Optional note about the provider
        api_key: Optional API key configuration
        host: Optional host/base_url configuration
        endpoint: Optional endpoint configuration
        region: Optional region configuration
        port: Optional port configuration
        log_level: Optional log level configuration
        account_id: Optional account ID configuration
        tls_on_off: Optional TLS enable/disable configuration
        tls_cert_path: Optional TLS certificate path configuration
        tls_key_path: Optional TLS key path configuration
        other: Frozenset of custom/provider-specific fields as (key, EnvVarConfig) tuples
        inherits_from: Optional parent provider for inheritance

    Example:
        >>> ProviderEnvConfig(
        ...     provider="deepseek",
        ...     clients=("openai",),
        ...     api_key=EnvVarConfig(
        ...         env="DEEPSEEK_API_KEY", description="API Key", is_secret=True
        ...     ),
        ...     inherits_from="openai",
        ... )
    """

    provider: str
    clients: tuple[str, ...]
    note: str | None = None

    # Standard fields (most common across providers)
    api_key: EnvVarConfig | None = None
    host: EnvVarConfig | None = None
    endpoint: EnvVarConfig | None = None
    region: EnvVarConfig | None = None
    port: EnvVarConfig | None = None
    log_level: EnvVarConfig | None = None
    account_id: EnvVarConfig | None = None

    # TLS-related
    tls_on_off: EnvVarConfig | None = None
    tls_cert_path: EnvVarConfig | None = None
    tls_key_path: EnvVarConfig | None = None

    # Custom/provider-specific fields
    other: frozenset[tuple[str, EnvVarConfig]] = field(default_factory=frozenset)

    # Inheritance from other providers (e.g., "openai" for OpenAI-compatible)
    inherits_from: str | None = None

    def all_vars(self) -> tuple[EnvVarConfig, ...]:
        """Get all environment variable configs including 'other'.

        Returns:
            Tuple of all EnvVarConfig instances (immutable and hashable)

        Example:
            >>> config = ProviderEnvConfig(...)
            >>> all_vars = config.all_vars()
            >>> api_keys = [v for v in all_vars if v.is_secret]
        """
        variables = [
            resolved_attr
            for attr in (
                "api_key",
                "host",
                "endpoint",
                "region",
                "port",
                "log_level",
                "account_id",
                "tls_on_off",
                "tls_cert_path",
                "tls_key_path",
            )
            if (resolved_attr := getattr(self, attr, None))
        ]

        # Other/custom fields
        variables.extend(cfg for _, cfg in self.other)

        return tuple(variables)

    def get_other(self, key: str) -> EnvVarConfig | None:
        """Get a custom field from 'other' by key.

        Args:
            key: The key to look up in the 'other' dict

        Returns:
            EnvVarConfig if found, None otherwise

        Example:
            >>> config = ProviderEnvConfig(...)
            >>> webhook_secret = config.get_other("webhook_secret")
        """
        return next((cfg for k, cfg in self.other if k == key), None)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for serialization (such as for MCP registry script).

        Returns:
            dictionary suitable for JSON serialization

        Example:
            >>> config = ProviderEnvConfig(...)
            >>> data = config.to_dict()
            >>> import json
            >>> json.dumps(data)
        """
        from pydantic import TypeAdapter

        adapter = TypeAdapter(type(self))
        return adapter.dump_python(self, round_trip=True)


__all__ = ("EnvVarConfig", "ProviderEnvConfig")
