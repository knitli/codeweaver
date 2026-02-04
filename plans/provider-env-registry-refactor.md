<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Provider Environment Variable Registry Refactor

**Status**: Planning
**Created**: 2025-02-03
**Priority**: High (tail end of config/DI refactor)
**Estimated Effort**: 2-3 days

## Problem Statement

Current `Provider.other_env_vars` property:
- ❌ ~500+ lines of repetitive match statement boilerplate
- ❌ Difficult to test comprehensively
- ❌ Hard to maintain and extend (adding providers requires significant code)
- ❌ Mixes data definition with query logic
- ❌ No validation of configuration correctness
- ❌ Not well covered by tests

## Goals

1. **Reduce boilerplate** by ~80% for common provider patterns
2. **Improve maintainability** - adding providers should be trivial
3. **Enable testing** - each provider config testable in isolation
4. **Optimize startup performance** - avoid heavy BaseModel overhead
5. **Support monorepo separation** - respect package boundaries
6. **Enable extensibility** - allow external provider registration
7. **Maintain compatibility** - preserve existing API surface

## Architecture Decisions

### 1. Data Structures: Frozen Dataclasses

**Decision**: Use `@dataclass(frozen=True, slots=True)` instead of BaseModel/BasedModel

**Rationale**:
- ✅ Lightweight - minimal runtime overhead
- ✅ Immutable - perfect for static configuration data
- ✅ `slots=True` - reduces memory footprint
- ✅ Type-safe with static analysis
- ✅ Fast instantiation (important for startup)
- ✅ Can add `__post_init__` for basic validation if needed
- ⚠️ No automatic validation - addressed via build-time validation

**Alternative considered**: BasedModel
- ❌ Heavy startup cost with many instances
- ❌ Validation overhead not needed for static data
- ✅ But provides rich validation if we need it later

**Migration path**: If we need validation later, dataclasses can convert to BasedModel with minimal changes.

### 2. Validation Strategy: Build-Time + Optional Runtime

**Decision**: Validate at build time, assume correctness at runtime

**Implementation**:
```python
# scripts/validate_provider_configs.py - run at build + commit hook
# Validates:
# - All env var names follow conventions
# - Required fields present
# - No duplicate env vars across providers
# - Client names are valid
# - Inheritance chains are valid

# Runtime: Lightweight assertions only (optional, can be disabled in prod)
```

**Trigger points**:
1. Pre-commit hook (fast validation)
2. CI/CD build step (comprehensive validation)
3. `mise run check` (developer workflow)
4. Optional runtime assertions for development

### 3. Registry Pattern: Lazy Loading with External Registration

**Decision**: Central registry with lazy initialization, support external registration

**Features**:
- Lazy loading (only initialize when first accessed)
- External registration API for plugins/extensions
- Thread-safe initialization
- Minimal overhead for unused providers

### 4. Monorepo Package Separation

**Package Boundaries**:
```
core/           # No dependency on providers
├── types/      # Shared types (EnvFormat, VariableInfo)
└── utils/      # has_package utility

providers/      # Depends on core
├── env_registry/   # New registry system
│   ├── models.py      # Dataclass definitions
│   ├── registry.py    # Registry implementation
│   ├── builders.py    # Composable builders
│   └── definitions/   # Provider configs
└── provider.py     # Provider enum (updated to use registry)
```

**Cross-package handling**:
```python
# In core if we ever need to check provider env vars
from codeweaver.core.utils import has_package

if has_package("codeweaver.providers"):
    from codeweaver.providers.env_registry import ProviderEnvRegistry
    # Use registry
else:
    # Graceful degradation or skip
```

## Detailed Design

### File Structure

```
src/codeweaver/providers/env_registry/
├── __init__.py              # Public API exports
├── models.py                # Dataclass models
├── builders.py              # Composable builder functions
├── registry.py              # Registry implementation
├── validation.py            # Runtime validation helpers (dev mode)
└── definitions/
    ├── __init__.py          # Auto-discover and register
    ├── openai_compatible.py # ~15 OpenAI-compatible providers
    ├── cloud_platforms.py   # Azure, Heroku multi-client providers
    └── specialized.py       # Qdrant, Bedrock, unique configs

scripts/
└── validate_provider_configs.py  # Build-time validation

tests/providers/env_registry/
├── test_models.py
├── test_builders.py
├── test_registry.py
├── test_validation.py
└── test_definitions/
    ├── test_openai_compatible.py
    ├── test_cloud_platforms.py
    └── test_specialized.py
```

### Core Models (`models.py`)

```python
"""Lightweight dataclass models for provider environment configuration.

Uses frozen dataclasses with slots for performance and immutability.
Validation happens at build-time, not runtime.
"""
from dataclasses import dataclass, field
from typing import Literal

# Import from core (no circular dependency)
from codeweaver.core.types.env import EnvFormat, VariableInfo


@dataclass(frozen=True, slots=True)
class EnvVarConfig:
    """Configuration for a single environment variable.

    Immutable, lightweight, validated at build-time.
    """
    env: str
    description: str
    variable_name: str | None = None
    variables: tuple[VariableInfo, ...] | None = None
    is_secret: bool = False
    fmt: EnvFormat | None = None
    choices: frozenset[str] | None = None  # Use frozenset for immutability
    default: str | None = None

    def __post_init__(self):
        """Optional lightweight validation for development."""
        # Only runs if DEBUG_PROVIDER_VALIDATION env var is set
        if __debug__ and os.getenv("DEBUG_PROVIDER_VALIDATION"):
            if not self.env:
                raise ValueError("env cannot be empty")
            if self.choices and not isinstance(self.choices, frozenset):
                # Auto-convert for convenience
                object.__setattr__(self, 'choices', frozenset(self.choices))


@dataclass(frozen=True, slots=True)
class ProviderEnvConfig:
    """Complete environment configuration for a provider.

    Represents one "set" of environment variables for a provider.
    Multi-client providers (like Azure) have multiple instances.
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

        Returns tuple for immutability and hashability.
        """
        vars_list = []

        # Standard fields
        for attr in ('api_key', 'host', 'endpoint', 'region', 'port',
                     'log_level', 'account_id', 'tls_on_off', 'tls_cert_path',
                     'tls_key_path'):
            if value := getattr(self, attr):
                vars_list.append(value)

        # Other/custom fields
        vars_list.extend(cfg for _, cfg in self.other)

        return tuple(vars_list)

    def get_other(self, key: str) -> EnvVarConfig | None:
        """Get a custom field from 'other' by key."""
        return next((cfg for k, cfg in self.other if k == key), None)

    def to_dict(self) -> dict:
        """Convert to dictionary for serialization (MCP registry script)."""
        result = {
            "provider": self.provider,
            "clients": list(self.clients),
        }

        if self.note:
            result["note"] = self.note

        # Add standard fields
        for attr in ('api_key', 'host', 'endpoint', 'region', 'port',
                     'log_level', 'account_id', 'tls_on_off', 'tls_cert_path',
                     'tls_key_path'):
            if value := getattr(self, attr):
                result[attr] = {
                    "env": value.env,
                    "description": value.description,
                    "is_secret": value.is_secret,
                    # Include other relevant fields
                }

        # Add other fields
        if self.other:
            result["other"] = {
                key: {
                    "env": cfg.env,
                    "description": cfg.description,
                    "is_secret": cfg.is_secret,
                }
                for key, cfg in self.other
            }

        if self.inherits_from:
            result["inherits_from"] = self.inherits_from

        return result
```

### Composable Builders (`builders.py`)

```python
"""Composable builder functions for common provider patterns.

These reduce boilerplate by providing templates for common configurations.
"""
from typing import Any


def httpx_env_vars() -> frozenset[tuple[str, EnvVarConfig]]:
    """Standard httpx environment variables used by most HTTP-based providers."""
    return frozenset([
        ("http_proxy", EnvVarConfig(
            env="HTTPS_PROXY",
            description="HTTP proxy for requests",
            variables=(VariableInfo(variable="proxy", dest="httpx"),),
        )),
        ("ssl_cert_file", EnvVarConfig(
            env="SSL_CERT_FILE",
            description="Path to the SSL certificate file for requests",
            fmt=EnvFormat.FILEPATH,
            variables=(VariableInfo(variable="verify", dest="httpx"),),
        )),
    ])


def openai_compatible_provider(
    provider_name: str,
    *,
    api_key_env: str,
    base_url_env: str | None = None,
    default_url: str | None = None,
    additional_clients: tuple[str, ...] = (),
    note: str | None = None,
    extra_vars: dict[str, EnvVarConfig] | None = None,
) -> ProviderEnvConfig:
    """Build configuration for OpenAI-compatible provider.

    This template covers ~15 providers that use the OpenAI SDK client
    with provider-specific API keys and base URLs.

    Args:
        provider_name: Display name (e.g., "DeepSeek", "Fireworks")
        api_key_env: Environment variable name for API key
        base_url_env: Optional env var for base URL
        default_url: Optional default base URL
        additional_clients: Extra client names beyond "openai"
        note: Optional note about the provider
        extra_vars: Additional custom environment variables

    Returns:
        Configured ProviderEnvConfig with OpenAI inheritance

    Example:
        >>> DEEPSEEK = openai_compatible_provider(
        ...     "DeepSeek",
        ...     api_key_env="DEEPSEEK_API_KEY",
        ... )
    """
    clients = ("openai",) + additional_clients
    other_vars = httpx_env_vars()

    if extra_vars:
        other_vars = other_vars | frozenset(extra_vars.items())

    kwargs: dict[str, Any] = {
        "provider": provider_name.lower(),
        "clients": clients,
        "note": note or f"These variables are for the {provider_name} service.",
        "api_key": EnvVarConfig(
            env=api_key_env,
            description=f"Your {provider_name} API Key",
            is_secret=True,
            variable_name="api_key",
        ),
        "other": other_vars,
        "inherits_from": "openai",
    }

    if base_url_env:
        kwargs["host"] = EnvVarConfig(
            env=base_url_env,
            description=f"Host URL for {provider_name} service",
            variable_name="base_url",
            default=default_url,
        )

    return ProviderEnvConfig(**kwargs)


def simple_api_key_provider(
    provider_name: str,
    client: str,
    api_key_env: str,
    *,
    base_url_env: str | None = None,
    additional_vars: dict[str, EnvVarConfig] | None = None,
    note: str | None = None,
) -> ProviderEnvConfig:
    """Build configuration for simple API key-based provider.

    For providers with their own SDK client (not OpenAI-compatible).

    Example:
        >>> VOYAGE = simple_api_key_provider(
        ...     "Voyage",
        ...     client="voyage",
        ...     api_key_env="VOYAGE_API_KEY",
        ... )
    """
    other_vars = httpx_env_vars()
    if additional_vars:
        other_vars = other_vars | frozenset(additional_vars.items())

    kwargs: dict[str, Any] = {
        "provider": provider_name.lower(),
        "clients": (client,),
        "note": note or f"These variables are for the {provider_name} service.",
        "api_key": EnvVarConfig(
            env=api_key_env,
            description=f"Your {provider_name} API Key",
            is_secret=True,
            variable_name="api_key",
        ),
        "other": other_vars,
    }

    if base_url_env:
        kwargs["host"] = EnvVarConfig(
            env=base_url_env,
            description=f"Host URL for {provider_name} service",
            variable_name="base_url",
        )

    return ProviderEnvConfig(**kwargs)


def multi_client_provider(
    provider_name: str,
    configs: list[ProviderEnvConfig],
) -> list[ProviderEnvConfig]:
    """Build multi-client provider configuration (like Azure).

    Some providers (Azure, Heroku) support multiple underlying clients
    with different environment variables for each.

    Example:
        >>> AZURE = multi_client_provider(
        ...     "azure",
        ...     [azure_openai_config, azure_cohere_config, azure_anthropic_config],
        ... )
    """
    # Recreate each config with updated provider name
    return [
        ProviderEnvConfig(
            provider=provider_name,
            clients=cfg.clients,
            note=cfg.note,
            api_key=cfg.api_key,
            host=cfg.host,
            endpoint=cfg.endpoint,
            region=cfg.region,
            port=cfg.port,
            log_level=cfg.log_level,
            account_id=cfg.account_id,
            tls_on_off=cfg.tls_on_off,
            tls_cert_path=cfg.tls_cert_path,
            tls_key_path=cfg.tls_key_path,
            other=cfg.other,
            inherits_from=cfg.inherits_from,
        )
        for cfg in configs
    ]
```

### Registry Implementation (`registry.py`)

```python
"""Central registry for provider environment configurations.

Provides lazy loading, caching, and query API for provider configs.
Thread-safe, supports external registration.
"""
import threading
from typing import ClassVar
from functools import cache


class ProviderEnvRegistry:
    """Central registry for provider environment configurations.

    Features:
    - Lazy initialization (only loads when first accessed)
    - Thread-safe initialization
    - External registration support
    - Efficient lookup and querying
    - Inheritance resolution
    """

    _registry: ClassVar[dict[str, list[ProviderEnvConfig]]] = {}
    _lock: ClassVar[threading.Lock] = threading.Lock()
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

        Example (internal use only):
            >>> ProviderEnvRegistry.register(
            ...     "myprovider",
            ...     ProviderEnvConfig(...),
            ...     external=True,
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
        """
        configs = cls.get(provider)
        return tuple(cfg.api_key.env for cfg in configs if cfg.api_key)

    @classmethod
    @cache
    def get_for_client(cls, provider: str, client: str) -> tuple[ProviderEnvConfig, ...]:
        """Get configs for provider filtered by client SDK.

        Args:
            provider: Provider name
            client: Client SDK name (e.g., "openai", "anthropic")

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
            Tuple of provider names (lowercase)
        """
        cls._ensure_initialized()
        return tuple(sorted(cls._registry.keys()))

    @classmethod
    def all_configs(cls) -> dict[str, list[ProviderEnvConfig]]:
        """Get all registered provider configurations.

        Returns:
            Dictionary mapping provider names to their configs
        """
        cls._ensure_initialized()
        return cls._registry.copy()

    @classmethod
    def to_dict(cls) -> dict[str, list[dict]]:
        """Export all configurations as dictionaries.

        Used by MCP registry generation script.

        Returns:
            Serializable dictionary of all configs
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
            from . import definitions

            # Discover all uppercase attributes that are configs
            for name in dir(definitions):
                if name.startswith('_') or not name.isupper():
                    continue

                value = getattr(definitions, name)

                # Handle both single configs and lists
                if isinstance(value, ProviderEnvConfig):
                    cls.register(name.lower(), value)
                elif isinstance(value, list) and value and isinstance(value[0], ProviderEnvConfig):
                    cls.register(name.lower(), value)

            cls._initialized = True

    @classmethod
    def _reset(cls) -> None:
        """Reset registry (for testing only)."""
        with cls._lock:
            cls._registry.clear()
            cls._initialized = False
            # Clear caches
            cls.get_api_key_envs.cache_clear()
            cls.get_for_client.cache_clear()
```

### Provider Definitions - OpenAI Compatible (`definitions/openai_compatible.py`)

```python
"""OpenAI-compatible provider definitions.

All providers in this file use the OpenAI SDK client with provider-specific
environment variables. This covers ~15 providers with minimal boilerplate.

Pattern:
    PROVIDER = openai_compatible_provider(
        "ProviderName",
        api_key_env="PROVIDER_API_KEY",
        base_url_env="PROVIDER_URL",  # optional
    )
"""
from ..builders import openai_compatible_provider

# ============================================================================
# OpenAI-compatible providers (alphabetical)
# ============================================================================

ALIBABA = openai_compatible_provider(
    "Alibaba",
    api_key_env="ALIBABA_API_KEY",
)

CEREBRAS = openai_compatible_provider(
    "Cerebras",
    api_key_env="CEREBRAS_API_KEY",
    base_url_env="CEREBRAS_API_URL",
    additional_clients=("cerebras",),
)

DEEPSEEK = openai_compatible_provider(
    "DeepSeek",
    api_key_env="DEEPSEEK_API_KEY",
)

FIREWORKS = openai_compatible_provider(
    "Fireworks",
    api_key_env="FIREWORKS_API_KEY",
    base_url_env="FIREWORKS_API_URL",
)

GITHUB = openai_compatible_provider(
    "GitHub",
    api_key_env="GITHUB_TOKEN",
)

GROQ = openai_compatible_provider(
    "Groq",
    api_key_env="GROQ_API_KEY",
    base_url_env="GROQ_BASE_URL",
    default_url="https://api.groq.com",
    additional_clients=("groq",),
)

MOONSHOT = openai_compatible_provider(
    "Moonshot",
    api_key_env="MOONSHOTAI_API_KEY",
    note="These variables are for the Moonshot service.",
)

MORPH = openai_compatible_provider(
    "Morph",
    api_key_env="MORPH_API_KEY",
    base_url_env="MORPH_API_URL",
    default_url="https://api.morphllm.com/v1",
)

NEBIUS = openai_compatible_provider(
    "Nebius",
    api_key_env="NEBIUS_API_KEY",
    base_url_env="NEBIUS_API_URL",
)

OLLAMA = openai_compatible_provider(
    "Ollama",
    api_key_env="OLLAMA_API_KEY",  # Usually not needed for local
    base_url_env="OLLAMA_BASE_URL",
    default_url="http://localhost:11434",
)

OVHCLOUD = openai_compatible_provider(
    "OVHCloud",
    api_key_env="OVHCLOUD_API_KEY",
    base_url_env="OVHCLOUD_API_URL",
)

PERPLEXITY = openai_compatible_provider(
    "Perplexity",
    api_key_env="PERPLEXITY_API_KEY",
)

SAMBANOVA = openai_compatible_provider(
    "SambaNova",
    api_key_env="SAMBANOVA_API_KEY",
    base_url_env="SAMBANOVA_API_URL",
)

TOGETHER = openai_compatible_provider(
    "Together",
    api_key_env="TOGETHER_API_KEY",
    note="These variables are for the Together service.",
)

X_AI = openai_compatible_provider(
    "X.AI",
    api_key_env="XAI_API_KEY",
)

# ============================================================================
# OpenAI itself (base for inheritance)
# ============================================================================

OPENAI = [
    ProviderEnvConfig(
        provider="openai",
        clients=("openai",),
        note=(
            "These variables are for any OpenAI-compatible service, including "
            "OpenAI itself, Azure OpenAI, and others -- any provider that we "
            "use the OpenAI client to connect to."
        ),
        api_key=EnvVarConfig(
            env="OPENAI_API_KEY",
            description=(
                "API key for OpenAI-compatible services (not necessarily an API key "
                "*for* OpenAI). The OpenAI client also requires an API key, even if "
                "you don't actually need one for your provider (like local Ollama). "
                "So provide a dummy key if needed."
            ),
            is_secret=True,
            variable_name="api_key",
        ),
        log_level=EnvVarConfig(
            env="OPENAI_LOG",
            description="One of: 'debug', 'info', 'warning', 'error'",
            choices=frozenset({"debug", "info", "warning", "error"}),
        ),
        other=httpx_env_vars() | frozenset([
            ("organization", EnvVarConfig(
                env="OPENAI_ORG_ID",
                description="Organization ID for OpenAI.",
                variable_name="organization",
            )),
            ("project", EnvVarConfig(
                env="OPENAI_PROJECT_ID",
                description="An openai project id for tracking usage.",
                variable_name="project",
            )),
            ("webhook_secret", EnvVarConfig(
                env="OPENAI_WEBHOOK_SECRET",
                description="Webhook secret for verifying incoming webhooks from OpenAI.",
                is_secret=True,
                variable_name="webhook_secret",
            )),
        ]),
    )
]

# Before refactor: ~750 lines
# After refactor:  ~150 lines (80% reduction)
```

### Provider Definitions - Specialized (`definitions/specialized.py`)

```python
"""Specialized provider definitions with unique configurations.

Providers that don't fit the standard patterns and require custom configs.
"""
from ..models import ProviderEnvConfig, EnvVarConfig
from ..builders import httpx_env_vars
from codeweaver.core.types.env import EnvFormat, VariableInfo


# ============================================================================
# Qdrant (unique nested env var structure)
# ============================================================================

QDRANT = ProviderEnvConfig(
    provider="qdrant",
    clients=("qdrant",),
    note=(
        "Qdrant supports setting **all** configuration options using environment "
        "variables. Like with CodeWeaver, nested variables are separated by double "
        "underscores (`__`). For all options, see [the Qdrant documentation]"
        "(https://qdrant.tech/documentation/guides/configuration/)"
    ),
    api_key=EnvVarConfig(
        env="QDRANT__SERVICE__API_KEY",
        is_secret=True,
        description="API key for Qdrant service",
        variable_name="api_key",
    ),
    host=EnvVarConfig(
        env="QDRANT__SERVICE__HOST",
        description="Hostname of the Qdrant service; do not use for URLs with schemes (e.g. 'http://')",
        variable_name="host",
    ),
    port=EnvVarConfig(
        env="QDRANT__SERVICE__HTTP_PORT",
        description="Port number for the Qdrant service",
        variable_name="port",
    ),
    log_level=EnvVarConfig(
        env="QDRANT__LOG_LEVEL",
        description="Log level for Qdrant service",
        choices=frozenset({"DEBUG", "INFO", "WARNING", "ERROR"}),
    ),
    tls_on_off=EnvVarConfig(
        env="QDRANT__SERVICE__ENABLE_TLS",
        description="Enable TLS for Qdrant service, expects truthy or false value (e.g. 1 for on, 0 for off).",
        fmt=EnvFormat.BOOLEAN,
        choices=frozenset({"true", "false"}),
        variable_name="https",
    ),
    tls_cert_path=EnvVarConfig(
        env="QDRANT__TLS__CERT",
        description=(
            "Path to the TLS certificate file for Qdrant service. Only needed if using "
            "a self-signed certificate. If you're using qdrant-cloud, you don't need this."
        ),
        fmt=EnvFormat.FILEPATH,
        variable_name="kwargs",
        variables=(
            VariableInfo(variable="verify", dest="client"),
            VariableInfo(variable="verify", dest="httpx"),
        ),
    ),
)

# ============================================================================
# AWS Bedrock (complex auth, multiple methods)
# ============================================================================

BEDROCK = ProviderEnvConfig(
    provider="bedrock",
    clients=("bedrock", "anthropic"),
    note=(
        "AWS allows for setting many configuration options by environment variable. "
        "See [the AWS documentation](https://boto3.amazonaws.com/v1/documentation/api/"
        "latest/guide/configuration.html#using-environment-variables) for more details. "
        "Because AWS has multiple authentication methods, and ways to configure settings, "
        "we don't provide them here. We'd just confuse people. Unlike other providers, "
        "we also don't check for AWS's environment variables, we just assume you're "
        "authorized to do what you need to do."
    ),
    region=EnvVarConfig(
        env="AWS_REGION",
        description="AWS region for Bedrock service",
        variable_name="region_name",
    ),
    account_id=EnvVarConfig(
        env="AWS_ACCOUNT_ID",
        description="AWS Account ID for Bedrock service",
        variable_name="aws_account_id",
    ),
    api_key=EnvVarConfig(
        env="AWS_SECRET_ACCESS_KEY",
        description="AWS Secret Access Key for Bedrock service",
        is_secret=True,
        variable_name="aws_secret_access_key",
    ),
    other=frozenset([
        ("aws_access_key_id", EnvVarConfig(
            env="AWS_ACCESS_KEY_ID",
            description="AWS Access Key ID for Bedrock service",
            is_secret=True,
            variable_name="aws_access_key_id",
        )),
        ("aws_bearer_token_bedrock", EnvVarConfig(
            env="AWS_BEARER_TOKEN_BEDROCK",
            description="AWS Bearer Token for Bedrock service",
            is_secret=True,
            variable_name="aws_bearer_token_bedrock",
        )),
    ]),
)

# Continue for other specialized providers (Anthropic, Voyage, etc.)
# ...
```

### Provider Definitions - Cloud Platforms (`definitions/cloud_platforms.py`)

```python
"""Cloud platform provider definitions.

Multi-client providers like Azure and Heroku that support multiple
underlying SDK clients with different configurations.
"""
from ..models import ProviderEnvConfig, EnvVarConfig
from ..builders import httpx_env_vars, multi_client_provider
from codeweaver.core.types.env import VariableInfo


# ============================================================================
# Azure (supports OpenAI, Cohere, Anthropic clients)
# ============================================================================

_azure_openai = ProviderEnvConfig(
    provider="azure",  # Will be set by multi_client_provider
    clients=("openai",),
    note="These variables are for the Azure OpenAI service. (OpenAI models on Azure)",
    api_key=EnvVarConfig(
        env="AZURE_OPENAI_API_KEY",
        is_secret=True,
        description="API key for Azure OpenAI service (OpenAI models on Azure)",
        variables=(
            VariableInfo(variable="api_key", dest="client"),
            VariableInfo(variable="api_key", dest="provider_settings"),
        ),
    ),
    endpoint=EnvVarConfig(
        env="AZURE_OPENAI_ENDPOINT",
        description="Endpoint for Azure OpenAI service (OpenAI models on Azure)",
        variables=(
            VariableInfo(variable="base_url", dest="client"),
            VariableInfo(variable="endpoint", dest="provider_settings"),
        ),
    ),
    region=EnvVarConfig(
        env="AZURE_OPENAI_REGION",
        description="Region for Azure OpenAI service (OpenAI models on Azure)",
        variables=(VariableInfo(variable="region_name", dest="provider"),),
    ),
    other=httpx_env_vars(),
    inherits_from="openai",
)

_azure_cohere = ProviderEnvConfig(
    provider="azure",
    clients=("cohere",),
    note="These variables are for the Azure Cohere service.",
    api_key=EnvVarConfig(
        env="AZURE_COHERE_API_KEY",
        is_secret=True,
        description="API key for Azure Cohere service (cohere models on Azure)",
        variable_name="api_key",
    ),
    endpoint=EnvVarConfig(
        env="AZURE_COHERE_ENDPOINT",
        description="Endpoint for Azure Cohere service (cohere models on Azure)",
        variable_name="base_url",
    ),
    region=EnvVarConfig(
        env="AZURE_COHERE_REGION",
        description="Region for Azure Cohere service",
        variable_name="region_name",
    ),
    other=httpx_env_vars(),
)

_azure_anthropic = ProviderEnvConfig(
    provider="azure",
    clients=("anthropic",),
    note="These variables are for the Azure Anthropic service.",
    api_key=EnvVarConfig(
        env="ANTHROPIC_FOUNDRY_API_KEY",
        is_secret=True,
        description="API key for Azure Anthropic service (Anthropic models on Azure)",
        variable_name="api_key",
    ),
    endpoint=EnvVarConfig(
        env="ANTHROPIC_FOUNDRY_BASE_URL",
        description="Endpoint for Azure Anthropic service (Anthropic models on Azure)",
        variable_name="base_url",
    ),
    region=EnvVarConfig(
        env="ANTHROPIC_FOUNDRY_REGION",
        description="Region for Azure Anthropic service",
        variable_name="region_name",
    ),
    other=frozenset([
        ("resource", EnvVarConfig(
            env="ANTHROPIC_FOUNDRY_RESOURCE",
            description="Resource name for Azure Anthropic service",
            variable_name="resource",
        ))
    ]),
)

AZURE = multi_client_provider(
    "azure",
    [_azure_openai, _azure_cohere, _azure_anthropic],
)

# ============================================================================
# Heroku (supports OpenAI and Cohere clients)
# ============================================================================

_heroku_base = ProviderEnvConfig(
    provider="heroku",
    clients=("openai", "cohere"),
    note="These variables are for the Heroku service.",
    api_key=EnvVarConfig(
        env="INFERENCE_KEY",
        is_secret=True,
        description="API key for Heroku service",
        variable_name="api_key",
    ),
    host=EnvVarConfig(
        env="INFERENCE_URL",
        description="Host URL for Heroku service",
        variable_name="base_url",
    ),
    other=httpx_env_vars() | frozenset([
        ("model_id", EnvVarConfig(
            env="INFERENCE_MODEL_ID",
            description="Model ID for Heroku service",
            variables=(VariableInfo(variable="model", dest="embed"),),
        )),
    ]),
    inherits_from="openai",  # Also inherits from cohere
)

HEROKU = [_heroku_base]

# ============================================================================
# Vercel (multiple auth methods with OpenAI)
# ============================================================================

_vercel_api_key = ProviderEnvConfig(
    provider="vercel",
    clients=("openai",),
    note=(
        "You may also use the OpenAI-compatible environment variables with Vercel, "
        "since it uses the OpenAI client."
    ),
    api_key=EnvVarConfig(
        env="VERCEL_AI_GATEWAY_API_KEY",
        is_secret=True,
        description="API key for Vercel service",
        variable_name="api_key",
    ),
    other=httpx_env_vars(),
    inherits_from="openai",
)

_vercel_oidc = ProviderEnvConfig(
    provider="vercel",
    clients=("openai",),
    api_key=EnvVarConfig(
        env="VERCEL_OIDC_TOKEN",
        is_secret=True,
        description="OIDC token for Vercel service",
        variable_name="api_key",
    ),
    inherits_from="openai",
)

VERCEL = [_vercel_api_key, _vercel_oidc]
```

### Definitions Module Init (`definitions/__init__.py`)

```python
"""Provider environment variable definitions.

Auto-exports all provider configurations for registry discovery.
"""

# Import all provider configs
from .openai_compatible import *  # noqa: F403
from .cloud_platforms import *    # noqa: F403
from .specialized import *        # noqa: F403

# Export explicitly for clarity (optional, but helpful for IDE)
__all__ = [
    # OpenAI-compatible
    "ALIBABA", "CEREBRAS", "DEEPSEEK", "FIREWORKS", "GITHUB", "GROQ",
    "MOONSHOT", "MORPH", "NEBIUS", "OLLAMA", "OPENAI", "OPENROUTER",
    "OVHCLOUD", "PERPLEXITY", "SAMBANOVA", "TOGETHER", "X_AI",

    # Cloud platforms
    "AZURE", "HEROKU", "VERCEL",

    # Specialized
    "ANTHROPIC", "BEDROCK", "COHERE", "GOOGLE", "HUGGINGFACE_INFERENCE",
    "MISTRAL", "PYDANTIC_GATEWAY", "QDRANT", "TAVILY", "VOYAGE",

    # Special providers
    "FASTEMBED", "SENTENCE_TRANSFORMERS", "MEMORY", "LITELLM", "DUCKDUCKGO",
]
```

### Updated Provider Enum (`provider.py`)

```python
"""Provider enumeration with registry integration."""
import os
import contextlib
from functools import cached_property
from typing import cast

from codeweaver.core import BaseEnum


class Provider(BaseEnum):
    """Enumeration of available providers.

    Environment variable configuration is now managed by ProviderEnvRegistry.
    This enum provides a clean query API over the registry.
    """

    ALIBABA = "alibaba"
    ANTHROPIC = "anthropic"
    # ... all provider enum values (unchanged)

    @classmethod
    def validate(cls, value: str) -> BaseEnum:
        """Validate provider-specific settings."""
        from codeweaver.core import ConfigurationError

        with contextlib.suppress(AttributeError, KeyError, ValueError):
            if value_in_self := cls.from_string(value.strip()):
                return value_in_self
        raise ConfigurationError(f"Invalid provider: {value}")

    @property
    def other_env_vars(self) -> tuple[ProviderEnvVars, ...] | None:
        """Get environment variables from registry.

        Returns TypedDict format for backward compatibility.
        """
        from codeweaver.providers.env_registry import ProviderEnvRegistry

        configs = ProviderEnvRegistry.get(self.value)
        if not configs:
            return None

        # Convert to TypedDict format for backward compatibility
        return tuple(self._config_to_typeddict(cfg) for cfg in configs)

    @cached_property
    def api_key_env_vars(self) -> tuple[str, ...] | None:
        """Get API key environment variable names."""
        from codeweaver.providers.env_registry import ProviderEnvRegistry

        env_vars = ProviderEnvRegistry.get_api_key_envs(self.value)
        return env_vars if env_vars else None

    def all_envs_for_client(
        self,
        client: Literal[
            "anthropic", "bedrock", "cohere", "duckduckgo", "fastembed",
            "google", "groq", "hf_inference", "mistral", "openai",
            "qdrant", "sentence_transformers", "tavily",
        ],
    ) -> tuple[ProviderEnvVarInfo, ...]:
        """Get environment variables for specific client."""
        from codeweaver.providers.env_registry import ProviderEnvRegistry

        configs = ProviderEnvRegistry.get_for_client(self.value, client)

        # Flatten all vars from all configs
        all_vars = []
        for cfg in configs:
            all_vars.extend(cfg.all_vars())

        # Convert to ProviderEnvVarInfo (TypedDict) format
        return tuple(self._envconfig_to_info(var) for var in all_vars)

    @staticmethod
    def _config_to_typeddict(cfg: ProviderEnvConfig) -> ProviderEnvVars:
        """Convert ProviderEnvConfig to ProviderEnvVars TypedDict.

        Maintains backward compatibility with existing code.
        """
        from codeweaver.core.types.env import EnvVarInfo as ProviderEnvVarInfo

        result: dict = {"client": cfg.clients}

        if cfg.note:
            result["note"] = cfg.note

        # Map standard fields
        for field in ('api_key', 'host', 'endpoint', 'region', 'port',
                     'log_level', 'tls_on_off', 'tls_cert_path'):
            if value := getattr(cfg, field):
                result[field] = ProviderEnvVarInfo(
                    env=value.env,
                    description=value.description,
                    variable_name=value.variable_name,
                    variables=value.variables,
                    is_secret=value.is_secret,
                    fmt=value.fmt,
                    choices=set(value.choices) if value.choices else None,
                    default=value.default,
                )

        # Map 'other' fields
        if cfg.other:
            result["other"] = {
                key: ProviderEnvVarInfo(
                    env=ecfg.env,
                    description=ecfg.description,
                    variable_name=ecfg.variable_name,
                    variables=ecfg.variables,
                    is_secret=ecfg.is_secret,
                    fmt=ecfg.fmt,
                    choices=set(ecfg.choices) if ecfg.choices else None,
                    default=ecfg.default,
                )
                for key, ecfg in cfg.other
            }

        return cast(ProviderEnvVars, result)

    @staticmethod
    def _envconfig_to_info(cfg: EnvVarConfig) -> ProviderEnvVarInfo:
        """Convert EnvVarConfig to ProviderEnvVarInfo."""
        from codeweaver.core.types.env import EnvVarInfo as ProviderEnvVarInfo

        return ProviderEnvVarInfo(
            env=cfg.env,
            description=cfg.description,
            variable_name=cfg.variable_name,
            variables=cfg.variables,
            is_secret=cfg.is_secret,
            fmt=cfg.fmt,
            choices=set(cfg.choices) if cfg.choices else None,
            default=cfg.default,
        )

    # All other properties remain unchanged
    @classmethod
    def all_envs(cls) -> tuple[tuple[Provider, ProviderEnvVarInfo], ...]:
        """Get all environment variables used by all providers."""
        from codeweaver.providers.env_registry import ProviderEnvRegistry

        found_vars: list[tuple[Provider, ProviderEnvVarInfo]] = []

        for provider_name in ProviderEnvRegistry.all_providers():
            try:
                provider = cls.from_string(provider_name)
                configs = ProviderEnvRegistry.get(provider_name)

                for cfg in configs:
                    for var in cfg.all_vars():
                        found_vars.append((provider, cls._envconfig_to_info(var)))
            except (AttributeError, KeyError, ValueError):
                # Skip providers not in enum
                continue

        return tuple(found_vars)

    # Properties like uses_openai_api, requires_auth, etc. remain unchanged
    # ...
```

### Build-Time Validation (`scripts/validate_provider_configs.py`)

```python
#!/usr/bin/env python3
"""Validate provider environment configurations at build time.

This script validates all provider configs to catch errors early:
- Environment variable naming conventions
- Required fields presence
- No duplicate env vars
- Valid client names
- Inheritance chains resolve correctly

Run as:
    python scripts/validate_provider_configs.py

Or add to pre-commit hook:
    mise run check  # includes this validation
"""
import sys
from pathlib import Path
from collections import defaultdict

# Add src to path
sys.path.insert(0, str(Path(__file__).parent.parent / "src"))

from codeweaver.providers.env_registry import ProviderEnvRegistry
from codeweaver.providers.env_registry.models import EnvVarConfig


class ValidationError(Exception):
    """Validation error with context."""
    pass


def validate_env_var_naming(env_name: str, provider: str) -> None:
    """Validate environment variable naming conventions."""
    # Check uppercase
    if not env_name.isupper() and "__" not in env_name:
        raise ValidationError(
            f"Provider '{provider}': Env var '{env_name}' should be uppercase"
        )

    # Check no spaces
    if " " in env_name:
        raise ValidationError(
            f"Provider '{provider}': Env var '{env_name}' contains spaces"
        )

    # Warn about non-standard names (not a hard error)
    if not any(env_name.startswith(prefix) for prefix in [
        "OPENAI_", "AWS_", "AZURE_", "ANTHROPIC_", "COHERE_", "GOOGLE_",
        "MISTRAL_", "VOYAGE_", "QDRANT__", "HF_", "GROQ_", "GEMINI_",
    ]):
        print(f"⚠️  Provider '{provider}': Env var '{env_name}' uses non-standard prefix")


def validate_required_fields(cfg: ProviderEnvConfig, provider: str) -> None:
    """Validate required fields are present."""
    if not cfg.clients:
        raise ValidationError(f"Provider '{provider}': No clients specified")

    if not cfg.provider:
        raise ValidationError(f"Provider '{provider}': No provider name")

    # Most providers should have api_key unless they're local-only
    local_providers = {"fastembed", "sentence_transformers", "memory", "ollama"}
    if cfg.provider not in local_providers and not cfg.api_key:
        print(f"⚠️  Provider '{provider}': No API key config (might be intentional)")


def validate_no_duplicate_env_vars(all_configs: dict[str, list[ProviderEnvConfig]]) -> None:
    """Validate no duplicate environment variable names across providers."""
    env_to_providers: dict[str, list[str]] = defaultdict(list)

    for provider, configs in all_configs.items():
        for cfg in configs:
            for var in cfg.all_vars():
                env_to_providers[var.env].append(provider)

    # Check for problematic duplicates
    for env_var, providers in env_to_providers.items():
        if len(providers) > 1:
            # Some duplicates are expected (OpenAI inheritance)
            if env_var.startswith("OPENAI_"):
                continue

            # HTTPX vars are shared
            if env_var in ("HTTPS_PROXY", "SSL_CERT_FILE"):
                continue

            print(f"⚠️  Env var '{env_var}' used by multiple providers: {', '.join(providers)}")


def validate_inheritance(all_configs: dict[str, list[ProviderEnvConfig]]) -> None:
    """Validate inheritance chains are valid."""
    for provider, configs in all_configs.items():
        for cfg in configs:
            if cfg.inherits_from:
                if cfg.inherits_from not in all_configs:
                    raise ValidationError(
                        f"Provider '{provider}': Inherits from unknown provider '{cfg.inherits_from}'"
                    )


def validate_client_names(all_configs: dict[str, list[ProviderEnvConfig]]) -> None:
    """Validate client names are from known set.

    Note: Unknown clients produce warnings (not errors) to support extensibility.
    External providers may use custom client names.
    """
    known_clients = {
        "anthropic", "bedrock", "cerebras", "cohere", "duckduckgo",
        "fastembed", "gateway", "google", "groq", "hf_inference",
        "mistral", "openai", "qdrant", "sentence_transformers", "tavily",
        "voyage",
    }

    for provider, configs in all_configs.items():
        for cfg in configs:
            for client in cfg.clients:
                if client not in known_clients:
                    print(f"⚠️  Provider '{provider}': Unknown client '{client}' (may be custom/external)")


def main() -> int:
    """Run all validations."""
    print("🔍 Validating provider environment configurations...")

    try:
        # Load all configs
        all_configs = ProviderEnvRegistry.all_configs()

        if not all_configs:
            raise ValidationError("No provider configs found!")

        print(f"✓ Found {len(all_configs)} providers")

        # Run validations
        errors = []

        for provider, configs in all_configs.items():
            for cfg in configs:
                try:
                    # Validate required fields
                    validate_required_fields(cfg, provider)

                    # Validate each env var
                    for var in cfg.all_vars():
                        validate_env_var_naming(var.env, provider)

                except ValidationError as e:
                    errors.append(str(e))

        # Cross-provider validations
        try:
            validate_no_duplicate_env_vars(all_configs)
            validate_inheritance(all_configs)
            validate_client_names(all_configs)
        except ValidationError as e:
            errors.append(str(e))

        # Report results
        if errors:
            print("\n❌ Validation errors:")
            for error in errors:
                print(f"  • {error}")
            return 1

        print("✅ All validations passed!")
        return 0

    except Exception as e:
        print(f"\n💥 Validation failed: {e}")
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
```

### Updated MCP Registry Script (`scripts/build/generate-mcp-server-json.py`)

```python
"""Generate MCP server registry JSON with provider environment variables.

Updated to use new ProviderEnvRegistry system.
"""
import json
from pathlib import Path

from codeweaver.providers.env_registry import ProviderEnvRegistry


def generate_mcp_registry() -> dict:
    """Generate MCP server registry data."""
    # Get all provider configs as dicts
    provider_envs = ProviderEnvRegistry.to_dict()

    # Build MCP registry structure
    registry = {
        "name": "codeweaver",
        "version": "0.1.0",  # Get from package
        "description": "Semantic code search MCP server",
        "providers": provider_envs,
        # ... other MCP registry fields
    }

    return registry


def main():
    """Generate and write MCP registry JSON."""
    registry = generate_mcp_registry()

    output_path = Path("dist/mcp-registry.json")
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, "w") as f:
        json.dump(registry, f, indent=2)

    print(f"✓ Generated MCP registry: {output_path}")


if __name__ == "__main__":
    main()
```

## Migration Plan

### Phase 1: Foundation (Day 1 morning)

**Goal**: Build new system alongside existing code (no breaking changes)

**Tasks**:
1. ✅ Create `src/codeweaver/providers/env_registry/` directory structure
2. ✅ Implement `models.py` (dataclasses)
3. ✅ Implement `builders.py` (helper functions)
4. ✅ Implement `registry.py` (registry system)
5. ✅ Write unit tests for models, builders, registry

**Validation**: Tests pass, no integration yet

### Phase 2: Proof of Concept (Day 1 afternoon)

**Goal**: Port 3-4 providers to validate approach

**Tasks**:
1. ✅ Create `definitions/openai_compatible.py`
2. ✅ Port DEEPSEEK, FIREWORKS, TOGETHER (simple OpenAI-compatible)
3. ✅ Port OPENAI (base for inheritance)
4. ✅ Write tests for these definitions
5. ✅ Verify registry lookup works correctly

**Validation**: Can query registry for these 4 providers, tests pass

### Phase 3: Bulk Migration - OpenAI Compatible (Day 1 evening)

**Goal**: Port all ~15 OpenAI-compatible providers

**Tasks**:
1. ✅ Port remaining OpenAI-compatible providers:
   - ALIBABA, CEREBRAS, GITHUB, GROQ, MOONSHOT, MORPH
   - NEBIUS, OLLAMA, OPENROUTER, OVHCLOUD, PERPLEXITY
   - SAMBANOVA, X_AI
2. ✅ Verify all use `openai_compatible_provider` builder
3. ✅ Write parameterized tests for all

**Validation**: All OpenAI-compatible providers migrated, tests pass

**Time saved**: ~10 lines per provider → 1-2 lines = ~120 lines → ~30 lines

### Phase 4: Cloud Platforms (Day 2 morning)

**Goal**: Port multi-client providers (Azure, Heroku, Vercel)

**Tasks**:
1. ✅ Create `definitions/cloud_platforms.py`
2. ✅ Port AZURE (3 client configs: OpenAI, Cohere, Anthropic)
3. ✅ Port HEROKU (2 client configs)
4. ✅ Port VERCEL (2 auth methods)
5. ✅ Write tests for multi-client providers

**Validation**: Multi-client providers work correctly, inheritance resolves

### Phase 5: Specialized Providers (Day 2 afternoon)

**Goal**: Port unique providers (Qdrant, Bedrock, Anthropic, etc.)

**Tasks**:
1. ✅ Create `definitions/specialized.py`
2. ✅ Port specialized providers:
   - QDRANT (unique nested structure)
   - BEDROCK (complex AWS auth)
   - ANTHROPIC (multiple auth methods)
   - VOYAGE, COHERE, GOOGLE, MISTRAL (simple clients)
   - HUGGINGFACE_INFERENCE, TAVILY, PYDANTIC_GATEWAY
3. ✅ Port local-only providers: FASTEMBED, SENTENCE_TRANSFORMERS, MEMORY
4. ✅ Write tests for each

**Validation**: All providers migrated, comprehensive test coverage

### Phase 6: Integration & Cleanup (Day 2 evening)

**Goal**: Remove old code, update Provider enum

**Tasks**:
1. ✅ Update `Provider.other_env_vars` to use registry
2. ✅ Update helper methods (`api_key_env_vars`, `all_envs`, etc.)
3. ✅ Remove old match statement (~500 lines deleted!)
4. ✅ Update all tests to use new system
5. ✅ Verify backward compatibility (existing code still works)

**Validation**: All tests pass, no breaking changes

### Phase 7: Build Tools & Validation (Day 3 morning)

**Goal**: Set up build-time validation and tooling

**Tasks**:
1. ✅ Implement `scripts/validate_provider_configs.py`
2. ✅ Update MCP registry generation script
3. ✅ Add validation to `mise run check`
4. ✅ Add pre-commit hook for validation
5. ✅ Update CI/CD to run validation

**Validation**: Build validates configs, MCP registry generates correctly

### Phase 8: Documentation & Polish (Day 3 afternoon)

**Goal**: Document new system, update guides

**Tasks**:
1. ✅ Write README for `env_registry/` package
2. ✅ Update CLAUDE.md with new architecture
3. ✅ Add examples for adding new providers
4. ✅ Document external registration API
5. ✅ Add architecture decision record (ADR)

**Validation**: Documentation complete, examples work

## Testing Strategy

### Unit Tests

```python
# tests/providers/env_registry/test_models.py
def test_envvarconfig_immutable():
    """Test EnvVarConfig is immutable."""
    cfg = EnvVarConfig(env="TEST", description="Test")
    with pytest.raises(dataclasses.FrozenInstanceError):
        cfg.env = "CHANGED"

def test_providerenvconfig_all_vars():
    """Test all_vars includes standard and other fields."""
    cfg = ProviderEnvConfig(
        provider="test",
        clients=("test",),
        api_key=EnvVarConfig(env="TEST_KEY", description="Key"),
        other=frozenset([("custom", EnvVarConfig(env="CUSTOM", description="Custom"))]),
    )
    all_vars = cfg.all_vars()
    assert len(all_vars) == 2
    assert all_vars[0].env == "TEST_KEY"
    assert all_vars[1].env == "CUSTOM"


# tests/providers/env_registry/test_builders.py
def test_openai_compatible_provider_basic():
    """Test basic OpenAI-compatible provider creation."""
    cfg = openai_compatible_provider(
        "TestProvider",
        api_key_env="TEST_API_KEY",
    )
    assert cfg.provider == "testprovider"
    assert "openai" in cfg.clients
    assert cfg.api_key.env == "TEST_API_KEY"
    assert cfg.api_key.is_secret
    assert cfg.inherits_from == "openai"

def test_openai_compatible_with_base_url():
    """Test provider with custom base URL."""
    cfg = openai_compatible_provider(
        "TestProvider",
        api_key_env="TEST_KEY",
        base_url_env="TEST_URL",
        default_url="https://test.example.com",
    )
    assert cfg.host.env == "TEST_URL"
    assert cfg.host.default == "https://test.example.com"


# tests/providers/env_registry/test_registry.py
def test_registry_lazy_initialization():
    """Test registry initializes lazily."""
    registry = ProviderEnvRegistry()
    assert not registry._initialized
    _ = registry.get("openai")
    assert registry._initialized

def test_registry_get_with_inheritance():
    """Test inheritance resolution."""
    configs = ProviderEnvRegistry.get("deepseek")
    # Should include both DeepSeek config and inherited OpenAI config
    assert len(configs) > 1
    assert any(cfg.provider == "deepseek" for cfg in configs)
    assert any(cfg.provider == "openai" for cfg in configs)

def test_registry_external_registration():
    """Test external provider registration."""
    custom_cfg = ProviderEnvConfig(
        provider="custom",
        clients=("custom",),
        api_key=EnvVarConfig(env="CUSTOM_KEY", description="Custom"),
    )
    ProviderEnvRegistry.register("custom", custom_cfg, external=True)

    configs = ProviderEnvRegistry.get("custom")
    assert len(configs) == 1
    assert configs[0].provider == "custom"

@pytest.mark.parametrize("provider_name", [
    "deepseek", "fireworks", "together", "groq",  # OpenAI-compatible
    "azure", "heroku",  # Multi-client
    "qdrant", "bedrock",  # Specialized
])
def test_all_providers_registered(provider_name):
    """Test all providers are properly registered."""
    configs = ProviderEnvRegistry.get(provider_name)
    assert configs, f"Provider {provider_name} not registered"
    assert all(isinstance(cfg, ProviderEnvConfig) for cfg in configs)
```

### Integration Tests

```python
# tests/providers/test_provider_enum_integration.py
def test_provider_enum_uses_registry():
    """Test Provider enum correctly queries registry."""
    from codeweaver.providers import Provider

    # Test simple provider
    deepseek = Provider.DEEPSEEK
    env_vars = deepseek.other_env_vars
    assert env_vars is not None
    assert any("DEEPSEEK_API_KEY" in str(ev) for ev in env_vars)

def test_provider_api_key_env_vars():
    """Test API key lookup."""
    from codeweaver.providers import Provider

    openai = Provider.OPENAI
    api_keys = openai.api_key_env_vars
    assert "OPENAI_API_KEY" in api_keys

def test_provider_client_filtering():
    """Test client-specific env vars."""
    from codeweaver.providers import Provider

    azure = Provider.AZURE
    openai_vars = azure.all_envs_for_client("openai")
    assert any("AZURE_OPENAI_API_KEY" in str(v) for v in openai_vars)

    cohere_vars = azure.all_envs_for_client("cohere")
    assert any("AZURE_COHERE_API_KEY" in str(v) for v in cohere_vars)
```

### Build-Time Validation Tests

```python
# tests/scripts/test_validate_provider_configs.py
def test_validation_script_succeeds():
    """Test validation script runs successfully."""
    result = subprocess.run(
        ["python", "scripts/validate_provider_configs.py"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "All validations passed" in result.stdout
```

## Performance Considerations

### Startup Performance

**Before**: Match statement evaluated every time `other_env_vars` accessed
**After**:
- Lazy loading (only initialize when first accessed)
- Cached lookups (`@cache` decorator)
- Frozen dataclasses (fast instantiation, low memory)

**Benchmarks**:
```python
# Quick benchmark
import timeit

# Old system (match statement)
time_old = timeit.timeit(
    "Provider.DEEPSEEK.other_env_vars",
    setup="from codeweaver.providers import Provider",
    number=1000,
)

# New system (registry)
time_new = timeit.timeit(
    "Provider.DEEPSEEK.other_env_vars",
    setup="from codeweaver.providers import Provider",
    number=1000,
)

print(f"Old: {time_old:.4f}s, New: {time_new:.4f}s, Speedup: {time_old/time_new:.2f}x")
```

### Memory Usage

- **Frozen dataclasses with slots**: ~50% memory reduction vs dict/BaseModel
- **Frozensets**: Immutable, hashable, memory-efficient
- **Shared references**: httpx_env_vars reused across providers

## Package Separation Considerations

### Core Package

```python
# codeweaver/core/types/env.py
# Already exists, no changes needed
class EnvFormat(enum.Enum):
    """Environment variable format types."""
    STRING = "string"
    INTEGER = "integer"
    BOOLEAN = "boolean"
    FILEPATH = "filepath"

@dataclass(frozen=True)
class VariableInfo:
    """Information about where an env var is used."""
    variable: str
    dest: str
```

### Providers Package

```python
# codeweaver/providers/env_registry/__init__.py
"""Provider environment variable registry.

This package is part of the providers package and depends on core.
"""
from .models import EnvVarConfig, ProviderEnvConfig
from .registry import ProviderEnvRegistry
from .builders import (
    httpx_env_vars,
    openai_compatible_provider,
    simple_api_key_provider,
    multi_client_provider,
)

__all__ = [
    "EnvVarConfig",
    "ProviderEnvConfig",
    "ProviderEnvRegistry",
    "httpx_env_vars",
    "openai_compatible_provider",
    "simple_api_key_provider",
    "multi_client_provider",
]
```

### Cross-Package Access (if needed in core)

```python
# Example: If core ever needs provider info
from codeweaver.core.utils import has_package

if has_package("codeweaver.providers"):
    from codeweaver.providers.env_registry import ProviderEnvRegistry
    # Use registry
else:
    # Graceful degradation - core works without providers
    ProviderEnvRegistry = None
```

## Benefits Summary

### Quantitative

- **~80% reduction in boilerplate** (~500 lines → ~100 lines)
- **~90% faster to add new providers** (50 lines → 1-2 lines)
- **~50% memory reduction** (frozen dataclasses vs BaseModel)
- **100% test coverage** (each provider testable in isolation)

### Qualitative

- ✅ **Maintainability**: Adding providers is trivial
- ✅ **Readability**: Clear data definitions, obvious patterns
- ✅ **Testability**: Each component testable independently
- ✅ **Performance**: Fast startup, efficient memory usage
- ✅ **Validation**: Build-time validation catches errors early
- ✅ **Extensibility**: External registration for plugins
- ✅ **Constitutional compliance**: Pydantic ecosystem (dataclasses), proven patterns
- ✅ **Monorepo ready**: Clean package separation

## Risks & Mitigation

### Risk 1: Breaking Changes

**Mitigation**:
- Maintain backward compatibility (TypedDict interface preserved)
- Comprehensive integration tests
- Gradual migration (new system alongside old initially)

### Risk 2: Performance Regression

**Mitigation**:
- Benchmark before/after
- Use frozen dataclasses (not BaseModel)
- Caching for expensive operations

### Risk 3: Complex Providers Not Fitting Pattern

**Mitigation**:
- Specialized providers can define custom configs
- Registry is flexible (accepts any ProviderEnvConfig)
- Builders are optional helpers, not requirements

### Risk 4: External Registration Conflicts

**Mitigation**:
- Explicit `external=True` flag
- Conflict detection raises clear errors
- Documentation on registration best practices

## Success Criteria

1. ✅ All existing tests pass with new system
2. ✅ Provider enum API unchanged (backward compatible)
3. ✅ MCP registry script generates correct output
4. ✅ Build-time validation passes for all providers
5. ✅ Adding new provider takes <5 minutes and <5 lines of code
6. ✅ Documentation complete with examples
7. ✅ No performance regression (startup time)
8. ✅ Code coverage ≥95% for new registry system

## Decisions Made

1. ✅ **Validation level**: Warnings for extensibility concerns (unknown clients, non-standard env var prefixes). Errors only for structural issues (missing required fields, invalid references).
2. ✅ **External registration**: Keep internal for now - CodeWeaver explicitly has no stable public API during alpha. Document in code comments but not public docs.
3. ✅ **API evolution**: Plan to eventually return dataclasses directly instead of TypedDict conversion. Maintain backward compatibility initially, then deprecate/migrate in future release.
4. ✅ **Migration timing**: Ready to proceed now - tail end of config/DI refactor is complete.

## Next Steps

1. **Review and approve this plan** (you!)
2. **Set up branch**: `feat/provider-env-registry-refactor`
3. **Begin Phase 1**: Foundation implementation
4. **Daily check-ins**: Brief status updates on progress
5. **Final review**: Before merging to main

---

**Estimated Timeline**: 2-3 days full-time work
**Estimated Lines Changed**: -400 lines (huge reduction!)
**Risk Level**: Medium (significant refactor, but well-planned)
**Impact**: High (makes future provider additions trivial)
