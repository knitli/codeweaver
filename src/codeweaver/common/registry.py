# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Provider and model registries for dynamic registration and lookup.

This module exposes two orthogonal registries:

- ProviderRegistry — wires provider enums (e.g., Provider.VOYAGE) to concrete provider
    implementations (e.g., a class that can call an API). It also supports getting
    singleton instances.
- ModelRegistry — stores capabilities metadata for models (embedding, sparse,
    reranking) and optional agentic profiles (pydantic-ai style) with glob-based
    matching per provider.

Both are process-singletons via module-level globals and accessors.
"""

from __future__ import annotations

import contextlib
import importlib
import logging

from collections import defaultdict
from collections.abc import Callable, Iterable, MutableMapping, Sequence
from enum import IntFlag, auto
from fnmatch import fnmatch
from functools import partial
from types import MappingProxyType
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    ClassVar,
    Literal,
    NotRequired,
    Required,
    TypedDict,
    cast,
    override,
)

from pydantic import ConfigDict, Field, computed_field
from pydantic.alias_generators import to_pascal
from pydantic_ai.models import Model
from rich.console import Console

from codeweaver.common.utils.lazy_importer import LazyImport, lazy_import
from codeweaver.config.providers import ProviderSettingsDict
from codeweaver.config.settings import CodeWeaverSettingsDict
from codeweaver.core.types import BasedModel, BaseEnum, LiteralStringT, ModelName
from codeweaver.core.types.dictview import DictView
from codeweaver.exceptions import ConfigurationError
from codeweaver.providers.embedding.providers.base import EmbeddingProvider
from codeweaver.providers.provider import Provider, ProviderKind
from codeweaver.providers.reranking.providers.base import RerankingProvider
from codeweaver.providers.vector_stores.base import VectorStoreProvider


if TYPE_CHECKING:
    from pydantic_ai.providers import Provider as AgentProvider

    from codeweaver.config.providers import (
        AgentProviderSettings,
        DataProviderSettings,
        EmbeddingProviderSettings,
        ProviderSettingsDict,
        RerankingProviderSettings,
        VectorStoreSettings,
    )
    from codeweaver.providers.embedding.capabilities.base import (
        EmbeddingModelCapabilities,
        SparseEmbeddingModelCapabilities,
    )
    from codeweaver.providers.reranking.capabilities.base import RerankingModelCapabilities


type AgenticProfile = Any
type AgenticProfileSpec = Callable[[str], Any] | Any | None

_provider_settings: DictView[ProviderSettingsDict] | None

logger = logging.getLogger(__name__)
console = Console(markup=True)


def get_provider_settings() -> DictView[ProviderSettingsDict]:
    """Get the provider settings."""
    global _provider_settings
    if not _provider_settings:
        from codeweaver.config.settings import get_settings_map

        _provider_settings = DictView(get_settings_map()["providers"])
    if not _provider_settings:
        raise ValueError("Provider settings are not available.")
    return _provider_settings


# TODO: We need to integrate feature detection into service registration and validation


@override
class Feature(IntFlag, BaseEnum):  # pyright: ignore[reportIncompatibleVariableOverride, reportIncompatibleMethodOverride]
    # We intentionally override BaseEnum here to get the IntFlag behavior where they overlap
    """Features supported by the CodeWeaver server.

    `Feature` uses `IntFlag` to allow bitwise operations to resolve dependencies and available feature sets.

    Example usage:
    ```python
    # merge features
    requested_features = Feature.HYBRID_SEARCH | Feature.RERANKING
    print(f"Requested: {requested_features}")

    # Get all required features including dependencies
    required = requested_features.resolve_all_dependencies()
    print(f"Required (with deps): {required}")

    # Check what's missing
    current_features = Feature.FILE_DISCOVERY | Feature.BASIC_SEARCH
    # calculate difference
    missing = required & ~current_features
    print(f"Missing: {missing}")

    # Validate a configuration
    config = Feature.VECTOR_SEARCH | Feature.BASIC_SEARCH | Feature.FILE_DISCOVERY
    print(f"Config valid: {config.validate_dependencies()}")

    # Get minimal set for specific features
    minimal = Feature.minimal_set_for(Feature.PRECONTEXT_AGENT)
    print(f"Minimal for PRECONTEXT_AGENT: {minimal}")
    ```
    """

    # Infrastructure
    FILE_DISCOVERY = auto()
    FILE_FILTER = auto()
    FILE_WATCHER = auto()
    LOGGING = auto()
    HEALTH = auto()
    ERROR_HANDLING = auto()
    RATE_LIMITING = auto()
    STATISTICS = auto()

    # Indexing
    SPARSE_INDEXING = auto()
    VECTOR_INDEXING = auto()
    AUTOMATIC_INDEXING = auto()

    # Search
    BASIC_SEARCH = auto()
    SEMANTIC_SEARCH = auto()
    VECTOR_SEARCH = auto()
    HYBRID_SEARCH = auto()
    RERANKING = auto()

    # AI/Agents
    AGENT = auto()
    MCP_CONTEXT_AGENT = auto()
    PRECONTEXT_AGENT = auto()
    WEB_SEARCH = auto()

    UNKNOWN = auto()

    @classmethod
    def get_dependencies(cls, feature: Feature) -> set[Feature]:
        """Get individual feature dependencies."""
        deps = {
            cls.BASIC_SEARCH: {cls.FILE_DISCOVERY},
            cls.SEMANTIC_SEARCH: {cls.BASIC_SEARCH},
            cls.VECTOR_SEARCH: {cls.BASIC_SEARCH, cls.VECTOR_INDEXING},
            cls.HYBRID_SEARCH: {cls.SPARSE_INDEXING, cls.VECTOR_INDEXING, cls.BASIC_SEARCH},
            cls.RERANKING: {cls.BASIC_SEARCH, cls.VECTOR_SEARCH},
            cls.AUTOMATIC_INDEXING: {cls.FILE_DISCOVERY, cls.FILE_WATCHER},
            cls.FILE_WATCHER: {cls.FILE_DISCOVERY, cls.FILE_FILTER},
            cls.MCP_CONTEXT_AGENT: {cls.VECTOR_SEARCH, cls.RERANKING},
            cls.PRECONTEXT_AGENT: {cls.VECTOR_SEARCH, cls.RERANKING, cls.AGENT},
            cls.WEB_SEARCH: {cls.AGENT},
        }
        return deps.get(feature, set())

    def resolve_all_dependencies(self) -> Feature:
        """Resolve all dependencies for the enabled features."""
        resolved = Feature(0)
        to_process = {
            feature for feature in Feature if feature in self and feature != Feature.UNKNOWN
        }
        # Recursively resolve dependencies
        while to_process:
            feature = to_process.pop()
            if feature not in resolved:
                resolved |= feature
                # Add dependencies to process
                deps = self.get_dependencies(feature)
                to_process.update(deps - set(resolved))

        return resolved

    def validate_dependencies(self) -> bool:
        """Check if all dependencies are satisfied."""
        resolved = self.resolve_all_dependencies()
        return (resolved & self) == resolved

    def missing_dependencies(self) -> Feature:
        """Get the missing dependencies."""
        resolved = self.resolve_all_dependencies()
        return resolved & ~self

    @classmethod
    def minimal_set_for(cls, *features: Feature) -> Feature:
        """Get minimal feature set including dependencies."""
        requested = cls(0)
        for feature in features:
            requested |= feature
        return requested.resolve_all_dependencies()


type ServiceName = Annotated[
    str,
    Field(description="""The name of the service""", max_length=100, pattern=r"^[a-zA-Z0-9_]+$"),
]


class ServiceCardDict(TypedDict, total=False):
    """Dictionary representing a service and its status."""

    name: Required[ServiceName]
    provider_kind: Required[ProviderKind]
    feature: Required[
        Feature
        | Literal[
            "agent",
            "automatic indexing",
            "basic search",
            "error handling",
            "file discovery",
            "file filter",
            "file watcher",
            "health",
            "hybrid search",
            "logging",
            "mcp context agent",
            "precontext agent",
            "rate limiting",
            "reranking",
            "semantic search",
            "sparse indexing",
            "statistics",
            "vector indexing",
            "vector search",
            "web search",
        ]
    ]
    base_class: Required[type]
    import_path: Required[str]
    enabled: Required[bool]
    dependencies: NotRequired[list[Feature] | None]

    status_hook: NotRequired[Callable[..., Any] | None]
    instance: NotRequired[Any | None]


class ServiceCard(BasedModel):
    """Card representing a service and its status."""

    model_config = BasedModel.model_config | ConfigDict(validate_assignment=True, defer_build=True)

    name: ServiceName
    feature: Annotated[Feature, Field(description="""The feature enum identifier""")]
    base_class: type
    import_path: str
    enabled: bool
    dependencies: list[Feature]

    status_hook: Annotated[
        Callable[..., Any] | None, Field(description="""Hook to call for status updates""")
    ] = None
    instance: Annotated[Any | None, Field(description="""The service instance""")] = None

    def _telemetry_keys(self) -> None:
        return None

    @classmethod
    def from_dict(cls, data: ServiceCardDict) -> ServiceCard:
        """Create a ServiceCard from a dictionary."""
        if isinstance(data["feature"], str):
            data["feature"] = Feature.from_string(data["feature"])
        dependencies = data.get("dependencies", [])
        return cls(**{**data, "dependencies": dependencies})  # pyright: ignore[reportArgumentType]

    @computed_field
    @property
    def fully_available(self) -> bool:
        """Check if the service is fully available (enabled and dependencies met)."""
        return self.enabled and all(
            dep in Feature(0) or dep in self.dependencies for dep in self.dependencies
        )


class ServicesRegistry(BasedModel):
    """Registry for managing available services."""

    model_config = BasedModel.model_config | ConfigDict(
        arbitrary_types_allowed=True, validate_assignment=True, defer_build=True
    )

    _services: ClassVar[MutableMapping[Feature, list[ServiceCard]]] = {
        feature: [] for feature in Feature if feature != Feature.UNKNOWN
    }

    _instance: ServicesRegistry | None = None

    def __init__(self) -> None:
        """Initialize the services registry."""
        # TODO register default services

    def _telemetry_keys(self) -> None:
        return None

    @classmethod
    def get_instance(cls) -> ServicesRegistry:
        """Get or create the global services registry instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register_service(self, card: ServiceCard | ServiceCardDict) -> None:
        """Register a service feature as enabled or disabled.

        Args:
            card: The service card to register
        """
        if isinstance(card, dict):
            card = ServiceCard.from_dict(card)
        self._services[card.feature].append(card)

    def is_service_enabled(self, feature: Feature) -> bool:
        """Check if a service feature is enabled.

        Args:
            feature: The feature enum identifier

        Returns:
            True if the feature is enabled, False otherwise
        """
        cards = self._services.get(feature, ())
        return len(cards) > 0 and any(card.enabled for card in cards)

    def list_available_services(self) -> MappingProxyType[Feature, list[ServiceCard]]:
        """List all available services.

        Returns:
            Returns a read-only mapping of features to lists of ServiceCard instances
        """
        return MappingProxyType(self._services)

    def get_service_dependencies(self, feature: Feature) -> set[Feature]:
        """Get the dependencies for a service feature.

        Args:
            feature: The feature enum identifier

        Returns:
            A set of feature dependencies
        """
        cards = self._services.get(feature, ())
        return {dep for card in cards for dep in card.dependencies}

    def get_service_status(self) -> tuple[ServiceCard, ...]:
        """Get the status of all registered services.

        Returns:
            A tuple of ServiceCard instances representing the status of each service
        """
        raise NotImplementedError("Service status tracking is not implemented yet.")


class ModelRegistry(BasedModel):
    """Registry for managing available embedding, reranking, and sparse embedding models."""

    model_config = BasedModel.model_config | ConfigDict(
        arbitrary_types_allowed=True, validate_assignment=True, defer_build=True
    )

    def __init__(self) -> None:
        """Initialize the model registry."""
        # provider -> (model_name -> capabilities)
        self._embedding_capabilities: MutableMapping[
            Provider, MutableMapping[ModelName, tuple[EmbeddingModelCapabilities, ...]]
        ] = defaultdict(dict)
        self._sparse_embedding_capabilities: MutableMapping[
            Provider, MutableMapping[ModelName, tuple[SparseEmbeddingModelCapabilities, ...]]
        ] = defaultdict(dict)
        self._reranking_capabilities: MutableMapping[
            Provider, MutableMapping[ModelName, tuple[RerankingModelCapabilities, ...]]
        ] = defaultdict(dict)

        # provider -> list[(model_glob, AgenticProfileSpec)] for agentic profiles
        self._agentic_profiles: MutableMapping[Provider, list[tuple[str, AgenticProfileSpec]]] = (
            defaultdict(list)
        )

        # flag to allow one-time default population by caller
        self._populated_defaults: bool = False

    def _register_builtin_embedding_models(self) -> None:
        """Register built-in embedding models."""
        from codeweaver.providers.embedding.capabilities import (
            load_default_capabilities,
            load_sparse_capabilities,
        )

        for cap in load_default_capabilities():
            self.register_embedding_capabilities(cap, replace=False)
        for cap in load_sparse_capabilities():
            self.register_sparse_embedding_capabilities(cap, replace=False)

    def _register_builtin_reranking_models(self) -> None:
        from codeweaver.providers.reranking.capabilities import load_default_capabilities

        for cap in load_default_capabilities():
            self.register_reranking_capabilities(cap, replace=False)

    def _register_builtin_models(self) -> None:
        self._register_builtin_embedding_models()
        self._register_builtin_reranking_models()

    # ---------- Embedding capabilities ----------
    def register_embedding_capabilities(
        self,
        capabilities: EmbeddingModelCapabilities | Iterable[EmbeddingModelCapabilities],
        *,
        replace: bool = True,
    ) -> None:
        """Register one or more embedding model capabilities for a provider.

        Adds embedding model capability metadata to the registry, replacing
        existing entries for the same model name and provider if `replace` is True.

        Args:
            capabilities: A single EmbeddingModelCapabilities or a sequence of them to register.
            replace: Whether to replace existing capabilities for the same model name and provider.
        """
        caps_seq: tuple[EmbeddingModelCapabilities, ...] = (
            (capabilities,)
            if isinstance(capabilities, EmbeddingModelCapabilities)
            else tuple(capabilities)
        )
        for cap in caps_seq:
            prov = cap.provider
            name_key = cap.name.strip().lower()
            if not replace and name_key in self._embedding_capabilities.get(prov, {}):
                continue
            if name_key not in self._embedding_capabilities.get(prov, {}):
                self._embedding_capabilities[prov][ModelName(cast(LiteralStringT, name_key))] = (
                    cap,
                )
            else:
                self._embedding_capabilities[prov][ModelName(cast(LiteralStringT, name_key))] += (
                    cap,
                )

    def get_embedding_capabilities(
        self, provider: Provider, name: str
    ) -> tuple[EmbeddingModelCapabilities, ...] | None:
        """Get embedding capabilities for a specific provider and model name."""
        prov_map = self._embedding_capabilities.get(provider)
        return (
            prov_map.get(ModelName(cast(LiteralStringT, name.strip().lower())))
            if prov_map
            else None
        )

    def list_embedding_models(
        self, provider: Provider | None = None
    ) -> tuple[EmbeddingModelCapabilities, ...]:
        """List all embedding models for a specific provider or all providers."""
        if provider is None:
            return tuple(
                cap
                for prov_map in self._embedding_capabilities.values()
                for cap in prov_map.values()
            )  # type: ignore
        return tuple(self._embedding_capabilities.get(provider, {}).values())  # type: ignore

    # ---------- Sparse embedding capabilities ----------
    def register_sparse_embedding_capabilities(
        self,
        capabilities: SparseEmbeddingModelCapabilities
        | Sequence[SparseEmbeddingModelCapabilities]
        | Iterable[SparseEmbeddingModelCapabilities],
        *,
        replace: bool = True,
    ) -> None:
        """Register one or more sparse embedding model capabilities for a provider."""
        caps_seq: Sequence[SparseEmbeddingModelCapabilities] = (
            (capabilities,)
            if isinstance(capabilities, SparseEmbeddingModelCapabilities)
            else tuple(capabilities)
        )
        for cap in caps_seq:
            prov = cap.provider  # type: ignore[attr-defined]
            name_key = cap.name.strip().lower()  # type: ignore[attr-defined]
            prov_map = self._sparse_embedding_capabilities.setdefault(prov, {})
            if not replace and name_key in prov_map:
                continue
            prov_map[ModelName(cast(LiteralStringT, name_key))] = (cap,)

    def get_sparse_embedding_capabilities(
        self, provider: Provider, name: str
    ) -> tuple[SparseEmbeddingModelCapabilities, ...] | None:
        """Get sparse embedding capabilities for a specific provider and model name."""
        prov_map = self._sparse_embedding_capabilities.get(provider)
        return (
            prov_map.get(ModelName(cast(LiteralStringT, name.strip().lower())))
            if prov_map
            else None
        )

    def list_sparse_embedding_models(
        self, provider: Provider | None = None
    ) -> tuple[SparseEmbeddingModelCapabilities, ...]:
        """List all sparse embedding models for a specific provider or all providers."""
        if provider is None:
            return tuple(
                cap
                for prov_map in self._sparse_embedding_capabilities.values()
                for cap_tuple in prov_map.values()
                for cap in cap_tuple
            )
        prov_map = self._sparse_embedding_capabilities.get(provider, {})
        return tuple(cap for cap_tuple in prov_map.values() for cap in cap_tuple)

    # ---------- Reranking capabilities ----------
    def register_reranking_capabilities(
        self,
        capabilities: RerankingModelCapabilities
        | Sequence[RerankingModelCapabilities]
        | Iterable[RerankingModelCapabilities],
        *,
        replace: bool = True,
    ) -> None:
        """Register one or more reranking model capabilities for a provider."""
        caps_seq: Sequence[RerankingModelCapabilities] = (
            (capabilities,)
            if isinstance(capabilities, RerankingModelCapabilities)
            else tuple(capabilities)
        )
        for cap in caps_seq:
            prov_map = self._reranking_capabilities.setdefault(cap.provider, {})
            name_key = cap.name.strip().lower()
            if not replace and name_key in prov_map:
                continue
            if name_key not in prov_map:
                prov_map[ModelName(cast(LiteralStringT, name_key))] = (cap,)
            else:
                prov_map[ModelName(cast(LiteralStringT, name_key))] += (cap,)

    def get_reranking_capabilities(
        self, provider: Provider, name: str
    ) -> tuple[RerankingModelCapabilities, ...] | None:
        """Get reranking capabilities for a specific provider and model name."""
        prov_map = self._reranking_capabilities.get(provider)
        return (
            prov_map.get(ModelName(cast(LiteralStringT, name.strip().lower())))
            if prov_map
            else None
        )

    def list_reranking_models(
        self, provider: Provider | None = None
    ) -> tuple[RerankingModelCapabilities, ...]:
        """List all reranking models for a specific provider or all providers."""
        if provider is None:
            return tuple(
                cap
                for prov_map in self._reranking_capabilities.values()
                for cap_tuple in prov_map.values()
                for cap in cap_tuple
            )
        prov_map = self._reranking_capabilities.get(provider, {})
        return tuple(cap for cap_tuple in prov_map.values() for cap in cap_tuple)

    # ---------- Agentic model profiles (pydantic-ai) ----------
    def register_agentic_profile(
        self,
        provider: Provider,
        model_glob: str,
        profile: AgenticProfileSpec,
        *,
        replace: bool = True,
    ) -> None:
        """Register an agentic profile for a specific provider and model glob."""
        rules = self._agentic_profiles.setdefault(provider, [])
        if replace:
            rules[:] = [(g, p) for (g, p) in rules if g != model_glob]
        rules.append((model_glob, profile))

    def resolve_agentic_profile(self, provider: Provider, model_name: str) -> AgenticProfile | None:
        """Resolve the agentic profile for a specific model name."""
        rules = self._agentic_profiles.get(provider) or []
        name = model_name.strip()
        return next(
            (
                spec(name) if callable(spec) else spec
                for glob, spec in rules
                if glob == name or fnmatch(name, glob)
            ),
            None,
        )

    def _register_builtin_agentic_profiles(self) -> None:
        """Register built-in agentic profiles."""
        from codeweaver.providers.agent import KnownAgentModelName, infer_model

        model_names = KnownAgentModelName.__value__.__dict__["__args__"][:-1]
        for model_name in model_names:
            with contextlib.suppress(ValueError, AttributeError, ImportError):
                profile: Model = infer_model(model_name)
                provider = Provider.from_string(
                    profile._profile.split(":")[1]  # type: ignore
                    if len(profile._profile.split(":")) > 1  # type: ignore
                    else profile._profile  # type: ignore
                )
                if not provider:
                    console.print(
                        f"[yellow]Warning:[/yellow] Could not infer provider for model '{model_name}' with profile '{profile._profile}'. Skipping registration."  # pyright: ignore[reportPrivateUsage]
                    )
                else:
                    self.register_agentic_profile(provider, model_name, profile, replace=False)

    # ---------- Population helpers ----------
    def mark_defaults_populated(self) -> None:
        """Mark the default capabilities as populated."""
        self._populated_defaults = True

    def defaults_populated(self) -> bool:
        """Check if the default capabilities have been populated."""
        return self._populated_defaults

    def is_empty(self) -> bool:
        """Check if the registry is empty."""
        return not any(self._embedding_capabilities.values()) and not any(
            self._agentic_profiles.values()
        )

    def _telemetry_keys(self) -> None:
        return None


class ProviderRegistry(BasedModel):
    """Registry for managing provider implementations and settings."""

    model_config = BasedModel.model_config | ConfigDict(validate_assignment=True)

    _instance: ProviderRegistry | None = None
    _settings: DictView[CodeWeaverSettingsDict] | None = None
    _embedding_prefix: ClassVar[LiteralStringT] = "codeweaver.providers.embedding.providers."
    _sparse_prefix: ClassVar[LiteralStringT] = "codeweaver.providers.embedding.providers."
    _rerank_prefix: ClassVar[LiteralStringT] = "codeweaver.providers.reranking.providers."
    _agent_prefix: ClassVar[LiteralStringT] = "codeweaver.providers.agent."
    _vector_store_prefix: ClassVar[LiteralStringT] = "codeweaver.providers.vector_stores."
    _provider_map: ClassVar[
        MappingProxyType[
            ProviderKind,
            dict[
                Provider, partial[LazyImport[Any]]
            ],  # ProviderKind.EMBEDDING -> Provider.AZURE, Literal["EXCEPTION"] but I couldn't find a way to type it correctly
        ]
    ] = MappingProxyType({
        ProviderKind.AGENT: {
            Provider.ANTHROPIC: partial(lazy_import, f"{_agent_prefix}agent_providers"),
            Provider.AZURE: partial(lazy_import, f"{_agent_prefix}agent_providers"),
            Provider.BEDROCK: partial(lazy_import, f"{_agent_prefix}agent_providers"),
            Provider.CEREBRAS: partial(lazy_import, f"{_agent_prefix}agent_providers"),
            Provider.COHERE: partial(lazy_import, f"{_agent_prefix}agent_providers"),
            Provider.DEEPSEEK: partial(lazy_import, f"{_agent_prefix}agent_providers"),
            Provider.FIREWORKS: partial(lazy_import, f"{_agent_prefix}agent_providers"),
            Provider.HEROKU: partial(lazy_import, f"{_agent_prefix}agent_providers"),
            Provider.HUGGINGFACE_INFERENCE: partial(lazy_import, f"{_agent_prefix}agent_providers"),
            Provider.GITHUB: partial(lazy_import, f"{_agent_prefix}agent_providers"),
            Provider.GOOGLE: partial(lazy_import, f"{_agent_prefix}agent_providers"),
            Provider.LITELLM: partial(lazy_import, f"{_agent_prefix}agent_providers"),
            Provider.MISTRAL: partial(lazy_import, f"{_agent_prefix}agent_providers"),
            Provider.MOONSHOT: partial(lazy_import, f"{_agent_prefix}agent_providers"),
            Provider.OPENAI: partial(lazy_import, f"{_agent_prefix}agent_providers"),
            Provider.OPENROUTER: partial(lazy_import, f"{_agent_prefix}agent_providers"),
            Provider.TOGETHER: partial(lazy_import, f"{_agent_prefix}agent_providers"),
            Provider.VERCEL: partial(lazy_import, f"{_agent_prefix}agent_providers"),
            Provider.X_AI: partial(lazy_import, f"{_agent_prefix}agent_providers"),
        },
        ProviderKind.EMBEDDING: {
            Provider.AZURE: "EXCEPTION",
            Provider.BEDROCK: partial(lazy_import, f"{_embedding_prefix}bedrock"),
            Provider.COHERE: partial(lazy_import, f"{_embedding_prefix}cohere"),
            Provider.FASTEMBED: partial(lazy_import, f"{_embedding_prefix}fastembed"),
            Provider.FIREWORKS: partial(lazy_import, f"{_embedding_prefix}openai_factory"),
            Provider.GITHUB: partial(lazy_import, f"{_embedding_prefix}openai_factory"),
            Provider.GOOGLE: partial(lazy_import, f"{_embedding_prefix}google"),
            Provider.GROQ: partial(lazy_import, f"{_embedding_prefix}openai_factory"),
            Provider.HEROKU: partial(lazy_import, f"{_embedding_prefix}openai_factory"),
            Provider.HUGGINGFACE_INFERENCE: partial(lazy_import, f"{_embedding_prefix}huggingface"),
            Provider.MISTRAL: partial(lazy_import, f"{_embedding_prefix}mistral"),
            Provider.OPENAI: partial(lazy_import, f"{_embedding_prefix}openai_factory"),
            Provider.OLLAMA: partial(lazy_import, f"{_embedding_prefix}openai_factory"),
            Provider.SENTENCE_TRANSFORMERS: partial(
                lazy_import, f"{_embedding_prefix}sentence_transformers"
            ),
            Provider.VERCEL: partial(lazy_import, f"{_embedding_prefix}openai_factory"),
            Provider.VOYAGE: partial(lazy_import, f"{_embedding_prefix}voyage"),
        },
        ProviderKind.SPARSE_EMBEDDING: {
            Provider.FASTEMBED: partial(lazy_import, f"{_sparse_prefix}fastembed"),
            Provider.SENTENCE_TRANSFORMERS: partial(
                lazy_import, f"{_sparse_prefix}sentence_transformers"
            ),
        },
        ProviderKind.RERANKING: {
            Provider.BEDROCK: partial(lazy_import, f"{_rerank_prefix}bedrock"),
            Provider.COHERE: partial(lazy_import, f"{_rerank_prefix}cohere"),
            Provider.FASTEMBED: partial(lazy_import, f"{_rerank_prefix}fastembed"),
            Provider.SENTENCE_TRANSFORMERS: partial(
                lazy_import, f"{_rerank_prefix}sentence_transformers"
            ),
            Provider.VOYAGE: partial(lazy_import, f"{_rerank_prefix}voyage"),
        },
        ProviderKind.VECTOR_STORE: {
            Provider.QDRANT: partial(lazy_import, f"{_vector_store_prefix}qdrant"),
            Provider.MEMORY: partial(lazy_import, f"{_vector_store_prefix}inmemory"),
        },
        ProviderKind.DATA: {
            Provider.DUCKDUCKGO: partial(lazy_import, "codeweaver.providers.tools"),
            Provider.TAVILY: partial(lazy_import, "codeweaver.providers.tools"),
        },
    })

    def __init__(self) -> None:
        """Initialize the provider registry."""
        # Provider implementation registries
        # we store lazy references to the providers and only try to fetch them when called
        self._embedding_providers: MutableMapping[
            Provider, LazyImport[type[EmbeddingProvider[Any]]] | type[EmbeddingProvider[Any]]
        ] = {}
        self._sparse_embedding_providers: MutableMapping[
            Provider, LazyImport[type[EmbeddingProvider[Any]]] | type[EmbeddingProvider[Any]]
        ] = {}
        self._vector_store_providers: MutableMapping[
            Provider, LazyImport[type[VectorStoreProvider[Any]]] | type[VectorStoreProvider[Any]]
        ] = {}
        self._reranking_providers: MutableMapping[
            Provider, LazyImport[type[RerankingProvider[Any]]] | type[RerankingProvider[Any]]
        ] = {}
        self._agent_providers: MutableMapping[Provider, LazyImport[type[Any]] | type[Any]] = {}
        self._data_providers: MutableMapping[Provider, LazyImport[type[Any]] | type[Any]] = {}

        self._embedding_instances: MutableMapping[Provider, EmbeddingProvider[Any]] = {}
        self._sparse_embedding_instances: MutableMapping[Provider, EmbeddingProvider[Any]] = {}
        self._vector_store_instances: MutableMapping[Provider, VectorStoreProvider[Any]] = {}
        self._reranking_instances: MutableMapping[Provider, RerankingProvider[Any]] = {}
        self._agent_instances: MutableMapping[Provider, Any] = {}
        self._data_instances: MutableMapping[Provider, Any] = {}

    def _telemetry_keys(self) -> None:
        return None

    @classmethod
    def get_instance(cls) -> ProviderRegistry:
        """Get or create the global provider registry instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register(
        self, provider: Provider, provider_kind: ProviderKind, provider_class: LazyImport[type]
    ) -> None:
        """Register a provider implementation.

        Args:
            provider: The provider enum identifier
            provider_kind: The type of provider (embedding or vector store)
            provider_class: The provider implementation class
        """
        match provider_kind:
            case ProviderKind.AGENT:
                self.register_agent_provider(provider, provider_class)
            case ProviderKind.DATA:
                self.register_data_provider(provider, provider_class)
            case ProviderKind.EMBEDDING:
                self.register_embedding_provider(provider, provider_class)
            case ProviderKind.SPARSE_EMBEDDING:
                self.register_sparse_embedding_provider(provider, provider_class)
            case ProviderKind.VECTOR_STORE:
                self.register_vector_store_provider(provider, provider_class)
            case ProviderKind.RERANKING:
                self.register_reranking_provider(provider, provider_class)
            case _:
                pass

    def _register_builtin_pydantic_ai_providers(self) -> None:
        """Register built-in Pydantic AI providers."""
        agent_module = importlib.import_module(self._agent_prefix)
        if providers := getattr(agent_module, "load_default_agent_providers", None):
            for provider_class in providers:
                provider = next(
                    p for p in Provider if str(p).lower() in provider_class.__name__.lower()
                )
                self.register(provider, ProviderKind.AGENT, provider_class)
        tool_module = importlib.import_module("codeweaver.agent_api")
        if tools := getattr(tool_module, "load_default_data_providers", None):
            for tool in tools:
                provider = (
                    Provider.DUCKDUCKGO if "duck" in tool.__name__.lower() else Provider.TAVILY
                )
                self.register(provider, ProviderKind.DATA, tool)

    def _register_builtin_providers(self) -> None:
        """Register built-in provider implementations."""
        # Register embedding providers dynamically
        for provider_kind, prov_map in self._provider_map.items():
            if provider_kind == ProviderKind.AGENT:
                # TODO: Agent registration not implemented yet, v.20 task
                continue
            for provider, module_importer in prov_map.items():
                if (  # these need special handling
                    provider in (Provider.TAVILY, Provider.DUCKDUCKGO)
                    or module_importer == "EXCEPTION"  # type: ignore  # <-- here's our exception (EMBEDDING -> AZURE -> "EXCEPTION")
                ):
                    continue
                self._register_provider_by_kind(provider_kind, provider, module_importer)
        self._register_azure_exception_providers(Provider.AZURE)
        # * NOTE: Embedding providers using OpenAIEmbeddingBase still need a class *created* before getting instantiated. But no point building it until it's needed.
        # * OpenAIEmbeddingBase is a class factory

    def _register_provider_by_kind(
        self, provider_kind: ProviderKind, provider: Provider, module: partial[LazyImport[Any]]
    ) -> None:
        """Register a provider based on its kind."""
        match provider_kind:
            case ProviderKind.EMBEDDING | ProviderKind.SPARSE_EMBEDDING:
                self._register_embedding_provider_from_module(
                    provider, module, destination=provider_kind
                )
            case ProviderKind.RERANKING:
                self._register_reranking_provider_from_module(provider, module)
            case ProviderKind.VECTOR_STORE:
                self._register_vector_store_provider_from_module(provider, module)
            case _:
                pass

    def _register_embedding_provider_from_module(
        self, provider: Provider, module: partial[LazyImport[Any]], destination: ProviderKind
    ) -> None:
        """Register an embedding provider from a module."""
        provider_name = self._get_embedding_provider_name(provider, module)
        lazy_class_import = module(provider_name)

        if provider_class := getattr(lazy_class_import, provider_name, None):
            if destination == ProviderKind.EMBEDDING:
                self.register_embedding_provider(provider, provider_class)
            self.register_sparse_embedding_provider(provider, provider_class)

    def _get_embedding_provider_name(
        self, provider: Provider, module: partial[LazyImport[Any]]
    ) -> str:
        """Get the provider name for embedding providers."""
        if provider == Provider.HUGGINGFACE_INFERENCE:
            return "HuggingFaceEmbeddingProvider"
        if module.args[0]._module_name == "codeweaver.providers.embedding.providers.openai_factory":
            return "OpenAIEmbeddingBase"
        return f"{to_pascal(str(provider))}EmbeddingProvider"

    def _register_azure_exception_providers(self, provider: Provider) -> None:
        """Register Azure exception providers."""
        module_name = f"{self._embedding_prefix}openai_factory"
        class_name = f"{to_pascal(str(provider))}OpenAIEmbeddingBase"
        self.register_embedding_provider(provider, LazyImport(module_name, class_name))

        module_name = f"{self._embedding_prefix}cohere"
        self.register_embedding_provider(
            provider, LazyImport(module_name, "CohereEmbeddingProvider")
        )

    def _register_reranking_provider_from_module(
        self, provider: Provider, module: partial[LazyImport[type[RerankingProvider[Any]]]]
    ) -> None:
        """Register a reranking provider from a module."""
        provider_name = f"{to_pascal(str(provider))}RerankingProvider"
        self.register_reranking_provider(provider, module(provider_name))

    def _register_vector_store_provider_from_module(
        self, provider: Provider, module: partial[LazyImport[type[VectorStoreProvider[Any]]]]
    ) -> None:
        """Register a vector store provider from a module."""
        provider_name = f"{to_pascal(str(provider))}VectorStoreProvider"
        self.register_vector_store_provider(provider, module(provider_name))

    def register_agent_provider(
        self, provider: Provider, provider_class: LazyImport[type[Any]] | type[Any]
    ) -> None:
        """Register an agent provider implementation.

        Args:
            provider: The provider enum identifier
            provider_class: The provider implementation class
        """
        self._agent_providers[provider] = provider_class

    def register_data_provider(
        self, provider: Provider, provider_class: LazyImport[type[Any]] | type[Any]
    ) -> None:
        """Register a data provider implementation.

        Args:
            provider: The provider enum identifier
            provider_class: The provider implementation class
        """
        self._data_providers[provider] = provider_class

    def register_embedding_provider(
        self,
        provider: Provider,
        provider_class: LazyImport[type[EmbeddingProvider[Any]]] | type[EmbeddingProvider[Any]],
    ) -> None:
        """Register an embedding provider implementation.

        Args:
            provider: The provider enum identifier
            provider_class: The provider implementation class
        """
        self._embedding_providers[provider] = provider_class

    def register_sparse_embedding_provider(
        self,
        provider: Provider,
        provider_class: LazyImport[type[EmbeddingProvider[Any]]] | type[EmbeddingProvider[Any]],
    ) -> None:
        """Register a sparse embedding provider implementation.

        Args:
            provider: The provider enum identifier
            provider_class: The provider implementation class
        """
        self._sparse_embedding_providers[provider] = provider_class

    def register_reranking_provider(
        self,
        provider: Provider,
        provider_class: LazyImport[type[RerankingProvider[Any]]] | type[RerankingProvider[Any]],
    ) -> None:
        """Register a reranking provider implementation.

        Args:
            provider: The provider enum identifier
            provider_class: The provider implementation class
        """
        self._reranking_providers[provider] = provider_class

    def register_vector_store_provider(
        self,
        provider: Provider,
        provider_class: LazyImport[type[VectorStoreProvider[Any]]] | type[VectorStoreProvider[Any]],
    ) -> None:
        """Register a vector store provider implementation.

        Args:
            provider: The provider enum identifier
            provider_class: The provider implementation class
        """
        self._vector_store_providers[provider] = provider_class

    def get_embedding_provider_class(
        self, provider: Provider
    ) -> LazyImport[type[EmbeddingProvider[Any]]] | type[EmbeddingProvider[Any]]:
        """Get an embedding provider class by provider enum.

        Args:
            provider: The provider enum identifier

        Returns:
            The provider class as a lazy import (imports on access) if it's a builtin, else the class itself

        Raises:
            ConfigurationError: If provider is not registered
        """
        if provider not in self._embedding_providers:
            raise ConfigurationError(f"Embedding provider '{provider}' is not registered")

        return self._embedding_providers[provider]

    def get_sparse_embedding_provider_class(
        self, provider: Provider
    ) -> LazyImport[type[EmbeddingProvider[Any]]] | type[EmbeddingProvider[Any]]:
        """Get a sparse embedding provider class by provider enum.

        Args:
            provider: The provider enum identifier

        Returns:
            The provider class as a lazy import (imports on access) if it's a builtin, else the class itself

        Raises:
            ConfigurationError: If provider is not registered
        """
        if provider not in self._sparse_embedding_providers:
            raise ConfigurationError(f"Sparse embedding provider '{provider}' is not registered")

        return self._sparse_embedding_providers[provider]

    def get_reranking_provider_class(
        self, provider: Provider
    ) -> LazyImport[type[RerankingProvider[Any]]] | type[RerankingProvider[Any]]:
        """Get a reranking provider class by provider enum.

        Args:
            provider: The provider enum identifier

        Returns:
            The provider class as a lazy import (imports on access) if it's a builtin, else the class itself

        Raises:
            ConfigurationError: If provider is not registered
        """
        if provider not in self._reranking_providers:
            raise ConfigurationError(f"Reranking provider '{provider}' is not registered")

        return self._reranking_providers[provider]

    def get_vector_store_provider_class(
        self, provider: Provider
    ) -> LazyImport[type[VectorStoreProvider[Any]]] | type[VectorStoreProvider[Any]]:
        """Get a vector store provider class by provider enum.

        Args:
            provider: The provider enum identifier

        Returns:
            The provider class as a lazy import (imports on access) if it's a builtin, else the class itself

        Raises:
            ConfigurationError: If provider is not registered
        """
        if provider not in self._vector_store_providers:
            raise ConfigurationError(f"Vector store provider '{provider}' is not registered")

        return self._vector_store_providers[provider]

    def get_agent_provider_class(
        self, provider: Provider
    ) -> LazyImport[type[AgentProvider[Any]]] | type[AgentProvider[Any]]:
        """Get an agent provider class by provider enum.

        Args:
            provider: The provider enum identifier

        Returns:
            The provider class as a lazy import (imports on access) if it's a builtin, else the class itself

        Raises:
            ConfigurationError: If provider is not registered
        """
        if provider not in self._agent_providers:
            raise ConfigurationError(f"Agent provider '{provider}' is not registered")

        return self._agent_providers[provider]

    def get_data_provider_class(self, provider: Provider) -> LazyImport[type[Any]] | type[Any]:
        """Get a data provider class by provider enum.

        Args:
            provider: The provider enum identifier

        Returns:
            The provider class as a lazy import (imports on access) if it's a builtin, else the class itself

        Raises:
            ConfigurationError: If provider is not registered
        """
        if provider not in self._data_providers:
            raise ConfigurationError(f"Data provider '{provider}' is not registered")

        return self._data_providers[provider]

    def create_embedding_provider(
        self, provider: Provider, **kwargs: Any
    ) -> EmbeddingProvider[Any]:
        """Create an embedding provider instance.

        Args:
            provider: The provider enum identifier
            **kwargs: Provider-specific initialization arguments

        Returns:
            An initialized provider instance
        """
        provider_class_import = self.get_embedding_provider_class(provider)
        # we need to access a property to execute the import and ensure it exists
        name = None
        with contextlib.suppress(Exception):
            name = provider_class_import.__name__
        if not name:
            logger.warning("Embedding provider '%s' could not be imported.", provider)
            raise ConfigurationError(f"Embedding provider '{provider}' could not be imported.")
        return cast(EmbeddingProvider[Any], provider_class_import(**kwargs))

    def create_sparse_embedding_provider(
        self, provider: Provider, **kwargs: Any
    ) -> EmbeddingProvider[Any]:
        """Create a sparse embedding provider instance.

        Args:
            provider: The provider enum identifier
            **kwargs: Provider-specific initialization arguments

        Returns:
            An initialized provider instance
        """
        return self._create_provider(
            provider, self.get_sparse_embedding_provider_class(provider), **kwargs
        )

    def create_reranking_provider(
        self, provider: Provider, **kwargs: Any
    ) -> RerankingProvider[Any]:
        """Create a reranking provider instance.

        Args:
            provider: The provider enum identifier
            **kwargs: Provider-specific initialization arguments

        Returns:
            An initialized provider instance
        """
        return self._create_provider(
            provider, self.get_reranking_provider_class(provider), **kwargs
        )

    def _create_provider(
        self, provider: Provider, importer: LazyImport[type[Any]], **kwargs: Any
    ) -> Any:
        """Create a provider instance using the given importer.

        Args:
            provider: The provider enum identifier
            importer: The lazy import of the provider class
            **kwargs: Provider-specific initialization arguments

        Returns:
            An initialized provider instance
        """
        resolved = None
        try:
            resolved = importer._resolve()  # type: ignore  # yes, we're accessing a private attribute in our own app
        except Exception as e:
            logger.exception("Provider '%s' could not be imported.", provider)
            raise ConfigurationError(f"Provider '{provider}' could not be imported.") from e
        return resolved(**kwargs)

    def create_vector_store_provider(
        self, provider: Provider, **kwargs: Any
    ) -> VectorStoreProvider[Any]:
        """Create a vector store provider instance.

        Args:
            provider: The provider enum identifier
            **kwargs: Provider-specific initialization arguments

        Returns:
            An initialized provider instance
        """
        return self._create_provider(
            provider, self.get_vector_store_provider_class(provider), **kwargs
        )

    def create_agent_provider(self, provider: Provider, **kwargs: Any) -> AgentProvider[Any]:
        """Create an agent provider instance.

        Args:
            provider: The provider enum identifier
            **kwargs: Provider-specific initialization arguments

        Returns:
            An initialized provider instance
        """
        return self._create_provider(provider, self.get_agent_provider_class(provider), **kwargs)

    def create_data_provider(self, provider: Provider, **kwargs: Any) -> Any:
        """Create a data provider instance.

        Args:
            provider: The provider enum identifier
            **kwargs: Provider-specific initialization arguments

        Returns:
            An initialized provider instance
        """
        return self._create_provider(provider, self.get_data_provider_class(provider), **kwargs)

    def get_embedding_provider_instance(
        self, provider: Provider, *, singleton: bool = False, **kwargs: Any
    ) -> EmbeddingProvider[Any]:
        """Get an embedding provider instance, optionally cached.

        Args:
            provider: The provider enum identifier
            singleton: Whether to cache and reuse the instance
            **kwargs: Provider-specific initialization arguments

        Returns:
            A provider instance
        """
        if singleton and provider in self._embedding_instances:
            return self._embedding_instances[provider]

        instance = self.create_embedding_provider(provider, **kwargs)

        if singleton:
            self._embedding_instances[provider] = instance

        return instance

    def get_sparse_embedding_provider_instance(
        self, provider: Provider, *, singleton: bool = False, **kwargs: Any
    ) -> EmbeddingProvider[Any]:
        """Get a sparse embedding provider instance, optionally cached.

        Args:
            provider: The provider enum identifier
            singleton: Whether to cache and reuse the instance
            **kwargs: Provider-specific initialization arguments

        Returns:
            A provider instance
        """
        if singleton and provider in self._sparse_embedding_instances:
            return self._sparse_embedding_instances[provider]

        instance = self.create_sparse_embedding_provider(provider, **kwargs)

        if singleton:
            self._sparse_embedding_instances[provider] = instance

        return instance

    def get_reranking_provider_instance(
        self, provider: Provider, *, singleton: bool = False, **kwargs: Any
    ) -> RerankingProvider[Any]:
        """Get a reranking provider instance, optionally cached.

        Args:
            provider: The provider enum identifier
            singleton: Whether to cache and reuse the instance
            **kwargs: Provider-specific initialization arguments

        Returns:
            A provider instance
        """
        if singleton and provider in self._reranking_instances:
            return self._reranking_instances[provider]

        instance = self.create_reranking_provider(provider, **kwargs)

        if singleton:
            self._reranking_instances[provider] = instance

        return instance

    def get_vector_store_provider_instance(
        self, provider: Provider, *, singleton: bool = False, **kwargs: Any
    ) -> VectorStoreProvider[Any]:
        """Get a vector store provider instance, optionally cached.

        Args:
            provider: The provider enum identifier
            singleton: Whether to cache and reuse the instance
            **kwargs: Provider-specific initialization arguments

        Returns:
            A provider instance
        """
        if singleton and provider in self._vector_store_instances:
            return self._vector_store_instances[provider]

        instance = self.create_vector_store_provider(provider, **kwargs)

        if singleton:
            self._vector_store_instances[provider] = instance

        return instance

    def get_agent_provider_instance(
        self, provider: Provider, *, singleton: bool = False, **kwargs: Any
    ) -> AgentProvider[Any]:
        """Get an agent provider instance, optionally cached.

        Args:
            provider: The provider enum identifier
            singleton: Whether to cache and reuse the instance
            **kwargs: Provider-specific initialization arguments

        Returns:
            A provider instance
        """
        if singleton and provider in self._agent_instances:
            return self._agent_instances[provider]

        instance = self.create_agent_provider(provider, **kwargs)

        if singleton:
            self._agent_instances[provider] = instance

        return instance

    def get_data_provider_instance(
        self, provider: Provider, *, singleton: bool = False, **kwargs: Any
    ) -> Any:
        """Get a data provider instance, optionally cached.

        Args:
            provider: The provider enum identifier
            singleton: Whether to cache and reuse the instance
            **kwargs: Provider-specific initialization arguments

        Returns:
            A provider instance
        """
        if singleton and provider in self._data_instances:
            return self._data_instances[provider]

        instance = self.create_data_provider(provider, **kwargs)

        if singleton:
            self._data_instances[provider] = instance

        return instance

    def list_providers(self, provider_kind: ProviderKind) -> list[Provider]:
        """List available providers for a given provider kind.

        Args:
            provider_kind: The type of provider to list

        Returns:
            List of available provider enums
        """
        if provider_kind == ProviderKind.EMBEDDING:
            return sorted(self._embedding_providers.keys())
        if provider_kind == ProviderKind.VECTOR_STORE:
            return sorted(self._vector_store_providers.keys())
        if provider_kind == ProviderKind.RERANKING:
            return sorted(self._reranking_providers.keys())
        if provider_kind == ProviderKind.SPARSE_EMBEDDING:
            return sorted(self._sparse_embedding_providers.keys())
        if provider_kind == ProviderKind.AGENT:
            return sorted(self._agent_providers.keys())
        if provider_kind == ProviderKind.DATA:
            return sorted(self._data_providers.keys())
        return []

    def _check_for_provider_availability(
        self, provider: Provider, provider_kind: ProviderKind
    ) -> bool:
        """Check if a provider is available in any provider kind.

        Args:
            provider: The provider to check
            provider_kind: The type of provider to check
        """
        if (
            provider_class_method := getattr(
                self, f"_create_{provider_kind.name.lower()}_provider", None
            )
        ) and (provider_class := provider_class_method(provider)):
            resolved = None
            try:
                resolved = provider_class._resolve()
            except Exception:
                return False
            else:  # make extra sure we don't have something that would return a truthy result and not be what we want :)
                return not isinstance(resolved, LazyImport) and resolved is not None
        return False

    def is_provider_available(self, provider: Provider, provider_kind: ProviderKind) -> bool:
        """Check if a provider is available for a given provider kind.

        Args:
            provider: The provider to check
            provider_kind: The type of provider to check

        Returns:
            True if the provider is available
        """
        if provider_kind == ProviderKind.EMBEDDING:
            return self._check_for_provider_availability(provider, provider_kind)
        if provider_kind == ProviderKind.VECTOR_STORE:
            return self._check_for_provider_availability(provider, provider_kind)
        if provider_kind == ProviderKind.RERANKING:
            return self._check_for_provider_availability(provider, provider_kind)
        if provider_kind == ProviderKind.SPARSE_EMBEDDING:
            return self._check_for_provider_availability(provider, provider_kind)
        if provider_kind == ProviderKind.AGENT:
            return self._check_for_provider_availability(provider, provider_kind)
        if provider_kind == ProviderKind.DATA:
            return self._check_for_provider_availability(provider, provider_kind)
        return False

    def get_configured_provider_settings(
        self, provider_kind: ProviderKind
    ) -> (
        tuple[DictView[DataProviderSettings], ...]
        | DictView[
            EmbeddingProviderSettings
            | RerankingProviderSettings
            | VectorStoreSettings
            | AgentProviderSettings
        ]
        | None
    ):
        """Get a list of providers that have been configured in settings for a given provider kind.

        Args:
            provider_kind: The type of provider to check
        Returns:
            List of configured providers
        """
        settings = get_provider_settings()
        match provider_kind:
            case ProviderKind.EMBEDDING | ProviderKind.SPARSE_EMBEDDING:
                embedding_settings = settings.get("embedding", {})
                return (
                    DictView(
                        next(
                            setting
                            for setting in embedding_settings
                            if (
                                setting.get("model_settings")
                                if ProviderKind.EMBEDDING
                                else setting.get("sparse_model_settings")
                            )
                            and setting.get("enabled")
                        )
                    )
                    if embedding_settings
                    else None
                )
            case ProviderKind.VECTOR_STORE:
                vector_store_settings = settings.get("vector", {})
                return (
                    DictView(
                        next((store for store in vector_store_settings if store.get("enabled")), {})
                    )
                    if vector_store_settings
                    else None
                )  # type: ignore
            case ProviderKind.RERANKING:
                reranking_settings = settings.get("reranking", {})
                return (
                    DictView(
                        next(
                            (setting for setting in reranking_settings if setting.get("enabled")),
                            {},
                        )
                    )
                    if reranking_settings
                    else None
                )  # type: ignore
            case ProviderKind.AGENT:
                agent_settings = settings.get("agent", {})
                return (
                    DictView(
                        next((setting for setting in agent_settings if setting.get("enabled")), {})
                    )
                    if agent_settings
                    else None
                )  # type: ignore
            case ProviderKind.DATA:
                data_settings = settings.get("data", {})
                return (
                    tuple(DictView(setting) for setting in data_settings if setting.get("enabled"))
                    if data_settings
                    else None
                )  # type: ignore
            case _:
                return None

    def get_embedding_provider(self, *, sparse: bool = False) -> Provider | None:
        """Get the default embedding provider from settings.

        Args:
            sparse: Whether to get the sparse embedding provider

        Returns:
            The default embedding provider enum or None
        """
        embedding_settings: DictView[EmbeddingProviderSettings] = (
            self.get_configured_provider_settings(
                ProviderKind.SPARSE_EMBEDDING if sparse else ProviderKind.EMBEDDING
            )
        )  # type: ignore
        if embedding_settings and (provider := embedding_settings.get("provider")):
            provider: Provider = (
                Provider.from_string(provider) if isinstance(provider, str) else provider
            )
            if self.is_provider_available(
                provider, ProviderKind.SPARSE_EMBEDDING if sparse else ProviderKind.EMBEDDING
            ):
                return provider
        return None

    def get_reranking_provider(self) -> Provider | None:
        """Get the default reranking provider from settings.

        Returns:
            The default reranking provider enum or None
        """
        reranking_settings: DictView[RerankingProviderSettings] = (
            self.get_configured_provider_settings(ProviderKind.RERANKING)
        )  # type: ignore
        if reranking_settings and (provider := reranking_settings.get("provider")):
            provider: Provider = (
                Provider.from_string(provider) if isinstance(provider, str) else provider
            )
            if self.is_provider_available(provider, ProviderKind.RERANKING):
                return provider
        return None

    def get_vector_store_provider(self) -> Provider | None:
        """Get the default vector store provider from settings.

        Returns:
            The default vector store provider enum or None
        """
        vector_store_settings: DictView[VectorStoreSettings] = (
            self.get_configured_provider_settings(ProviderKind.VECTOR_STORE)
        )  # type: ignore
        if vector_store_settings and (provider := vector_store_settings.get("provider")):
            provider: Provider = (
                Provider.from_string(provider) if isinstance(provider, str) else provider
            )
            if self.is_provider_available(provider, ProviderKind.VECTOR_STORE):
                return provider
        return None

    def get_agent_provider(self) -> Provider | None:
        """Get the default agent provider from settings.

        Returns:
            The default agent provider enum or None
        """
        agent_settings: DictView[AgentProviderSettings] = self.get_configured_provider_settings(
            ProviderKind.AGENT
        )  # type: ignore
        if agent_settings and (provider := agent_settings.get("provider")):
            provider: Provider = (
                Provider.from_string(provider) if isinstance(provider, str) else provider
            )
            if self.is_provider_available(provider, ProviderKind.AGENT):
                return provider
        return None

    def get_data_providers(self) -> tuple[Provider, ...] | None:
        """Get all data providers from settings.

        Returns:
            A tuple of all data provider enums
        """
        if data_settings := self.get_configured_provider_settings(ProviderKind.DATA):
            providers = [
                setting.get("provider")
                for setting in data_settings
                if isinstance(setting, DictView | dict)
            ]
            return tuple(
                Provider.from_string(provider) if isinstance(provider, str) else provider
                for provider in providers
                if provider and self.is_provider_available(provider, ProviderKind.DATA)
            )
        return None

    def clear_instances(self) -> None:
        """Clear all cached provider instances."""
        self._embedding_instances.clear()
        self._vector_store_instances.clear()
        self._reranking_instances.clear()
        self._sparse_embedding_instances.clear()
        self._agent_instances.clear()
        self._data_instances.clear()


# global services registry instance
_services_registry = ServicesRegistry()

# Global provider registry instance
_provider_registry = ProviderRegistry()

# Global model registry instance
_model_registry = ModelRegistry()


def get_provider_registry() -> ProviderRegistry:
    """Get the global provider registry instance."""
    return _provider_registry


def get_model_registry() -> ModelRegistry:
    """Get the global model registry instance."""
    return _model_registry


def get_services_registry() -> ServicesRegistry:
    """Get the global services registry instance."""
    return _services_registry


def register_service(service: ServiceCard | ServiceCardDict) -> None:
    """Register a service with the global registry.

    Args:
        service: The service card or dictionary to register
    """
    _services_registry.register_service(service)


def register_embedding_provider(
    provider: Provider, provider_class: type[EmbeddingProvider[Any]]
) -> None:
    """Register an embedding provider with the global registry.

    Args:
        provider: The provider enum identifier
        provider_class: The provider implementation class
    """
    _provider_registry.register_embedding_provider(provider, provider_class)


def register_sparse_embedding_provider(
    provider: Provider, provider_class: type[EmbeddingProvider[Any]]
) -> None:
    """Register a sparse embedding provider with the global registry.

    Args:
        provider: The provider enum identifier
        provider_class: The provider implementation class
    """
    _provider_registry.register_sparse_embedding_provider(provider, provider_class)


def register_reranking_provider(
    provider: Provider, provider_class: type[RerankingProvider[Any]]
) -> None:
    """Register a reranking provider with the global registry.

    Args:
        provider: The provider enum identifier
        provider_class: The provider implementation class
    """
    _provider_registry.register_reranking_provider(provider, provider_class)


def register_vector_store_provider(
    provider: Provider, provider_class: type[VectorStoreProvider[Any]]
) -> None:
    """Register a vector store provider with the global registry.

    Args:
        provider: The provider enum identifier
        provider_class: The provider implementation class
    """
    _provider_registry.register_vector_store_provider(provider, provider_class)


def register_agent_provider(provider: Provider, provider_class: type[AgentProvider[Any]]) -> None:
    """Register an agent provider with the global registry.

    Args:
        provider: The provider enum identifier
        provider_class: The provider implementation class
    """
    _provider_registry.register_agent_provider(provider, provider_class)


def register_data_provider(provider: Provider, provider_class: type[Any]) -> None:
    """Register a data provider with the global registry.

    Args:
        provider: The provider enum identifier
        provider_class: The provider implementation class
    """
    _provider_registry.register_data_provider(provider, provider_class)


# --- Convenience helpers for model capability registration ---
def register_embedding_capabilities(
    capabilities: EmbeddingModelCapabilities
    | Sequence[EmbeddingModelCapabilities]
    | Iterable[EmbeddingModelCapabilities],
    *,
    replace: bool = True,
) -> None:
    """Register embedding model capabilities globally."""
    _model_registry.register_embedding_capabilities(capabilities, replace=replace)


def register_sparse_embedding_capabilities(
    capabilities: SparseEmbeddingModelCapabilities
    | Sequence[SparseEmbeddingModelCapabilities]
    | Iterable[SparseEmbeddingModelCapabilities],
    *,
    replace: bool = True,
) -> None:
    """Register sparse embedding model capabilities globally."""
    _model_registry.register_sparse_embedding_capabilities(capabilities, replace=replace)


def register_reranking_capabilities(
    capabilities: RerankingModelCapabilities
    | Sequence[RerankingModelCapabilities]
    | Iterable[RerankingModelCapabilities],
    *,
    replace: bool = True,
) -> None:
    """Register reranking model capabilities globally."""
    _model_registry.register_reranking_capabilities(capabilities, replace=replace)


def register_agentic_profile(
    provider: Provider, model_glob: str, profile: AgenticProfileSpec, *, replace: bool = True
) -> None:
    """Register an agentic profile globally."""
    _model_registry.register_agentic_profile(provider, model_glob, profile, replace=replace)


def resolve_agentic_profile(provider: Provider, model_name: str) -> AgenticProfile | None:
    """
    Resolve an agentic profile for a given provider and model name.
    """
    return _model_registry.resolve_agentic_profile(provider, model_name)


def initialize_registries() -> None:
    """Initialize the global registries."""
    global _model_registry, _provider_registry, _services_registry
    _model_registry._register_builtin_models()  # type: ignore
    _provider_registry._register_builtin_providers()  # type: ignore
    # TODO: Services registry... we'll need to deconflict available providers, capabilities, against registered services to figure out what's actually available


__all__ = (
    "Feature",
    "ModelRegistry",
    "ProviderRegistry",
    "ServiceCard",
    "ServiceCardDict",
    "ServicesRegistry",
    "get_model_registry",
    "get_provider_registry",
    "get_services_registry",
    "initialize_registries",
    "register_agent_provider",
    "register_agentic_profile",
    "register_data_provider",
    "register_embedding_capabilities",
    "register_embedding_provider",
    "register_reranking_capabilities",
    "register_reranking_provider",
    "register_service",
    "register_sparse_embedding_capabilities",
    "register_sparse_embedding_provider",
    "register_vector_store_provider",
    "resolve_agentic_profile",
)
