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

from collections.abc import Callable, Iterable, MutableMapping, Sequence
from enum import IntFlag, auto
from fnmatch import fnmatch
from types import MappingProxyType
from typing import TYPE_CHECKING, Annotated, Any, ClassVar, NotRequired, Required, TypedDict

from pydantic import BaseModel, ConfigDict, Field, computed_field
from pydantic.alias_generators import to_pascal

from codeweaver._common import BaseEnum, LiteralStringT
from codeweaver.embedding.capabilities.base import (
    EmbeddingModelCapabilities,
    SparseEmbeddingModelCapabilities,
)
from codeweaver.embedding.providers import EmbeddingProvider
from codeweaver.exceptions import ConfigurationError
from codeweaver.provider import Provider, ProviderKind
from codeweaver.reranking.capabilities.base import RerankingModelCapabilities
from codeweaver.reranking.providers.base import RerankingProvider
from codeweaver.vector_stores.base import VectorStoreProvider


type AgenticProfile = Any
type AgenticProfileSpec = Callable[[str], Any] | Any | None

if TYPE_CHECKING:
    from pydantic_ai.providers import Provider as AgentProvider

    from codeweaver.settings import CodeWeaverSettings

# I think I've defined this in like four places, but it's just for clarity
type ModelName = str


class Feature(BaseEnum, IntFlag):
    """Enum for features supported by the CodeWeaver server."""

    BASIC_SEARCH = auto()  # simple keyword search across the codebase
    SEMANTIC_SEARCH = auto()  # ast-grep AST search
    VECTOR_SEARCH = auto()  # embedding-based search
    HYBRID_SEARCH = auto()  # combination of sparse and vector search
    RERANKING = auto()  # reranking of search results

    AGENT = auto()  # agentic LLMs

    WEB_SEARCH = auto()  # tavily, duckduckgo

    SPARSE_INDEXING = auto()  # sparse indexing
    VECTOR_INDEXING = auto()  # vector indexing

    FILE_DISCOVERY = auto()  # file discovery
    AUTOMATIC_INDEXING = auto()  # indexing on file changes
    FILE_WATCHER = auto()  # file watcher service
    FILE_FILTER = auto()  # file filtering

    MCP_CONTEXT_AGENT = auto()  # mcp_context_agent
    PRECONTEXT_AGENT = auto()  # precontext_agent

    HEALTH = auto()  # health
    LOGGING = auto()  # logging
    ERROR_HANDLING = auto()  # error_handling
    RATE_LIMITING = auto()  # rate_limiting
    STATISTICS = auto()  # statistics

    UNKNOWN = auto()  # unknown

    @property
    def dependencies(self) -> Feature:
        """Get the flag dependencies for a feature."""
        deps: dict[Feature, Feature] = {
            Feature.BASIC_SEARCH: Feature.FILE_DISCOVERY,
            Feature.SEMANTIC_SEARCH: Feature.BASIC_SEARCH,
            Feature.VECTOR_SEARCH: Feature.BASIC_SEARCH,
            Feature.HYBRID_SEARCH: Feature.SPARSE_INDEXING & Feature.VECTOR_INDEXING,
            Feature.RERANKING: Feature.BASIC_SEARCH & Feature.VECTOR_SEARCH,
            Feature.AUTOMATIC_INDEXING: Feature.FILE_DISCOVERY & Feature.FILE_WATCHER,
            Feature.FILE_WATCHER: Feature.FILE_DISCOVERY & Feature.FILE_FILTER,
            Feature.MCP_CONTEXT_AGENT: Feature.VECTOR_SEARCH & Feature.RERANKING,
            Feature.PRECONTEXT_AGENT: Feature.VECTOR_SEARCH & Feature.RERANKING & Feature.AGENT,
            Feature.WEB_SEARCH: Feature.AGENT,
        }
        return deps.get(self, Feature(0))


type ServiceName = Annotated[
    str,
    Field(description="""The name of the service", max_length=100, pattern=r"^[a-zA-Z0-9_]+$"""),
]


class ServiceCardDict(TypedDict, total=False):
    """Dictionary representing a service and its status."""

    name: Required[ServiceName]
    feature: Required[Feature | str]
    base_class: Required[type]
    import_path: Required[str]
    enabled: Required[bool]
    dependencies: NotRequired[list[Feature] | None]

    status_hook: NotRequired[Callable[..., Any] | None]
    instance: NotRequired[Any | None]


class ServiceCard(BaseModel):
    """Card representing a service and its status."""

    model_config = ConfigDict(validate_assignment=True, defer_build=True, str_strip_whitespace=True)

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


class ServicesRegistry(BaseModel):
    """Registry for managing available services."""

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True,
        defer_build=True,
        str_strip_whitespace=True,
    )

    _services: MutableMapping[Feature, list[ServiceCard]] = {
        feature: [] for feature in Feature if feature != Feature.UNKNOWN
    }

    _instance: ServicesRegistry | None = None

    def __init__(self) -> None:
        """Initialize the services registry."""
        # TODO register default services

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

    def get_service_status(self) -> tuple[ServiceCard, ...]:
        """Get the status of all registered services.

        Returns:
            A tuple of ServiceCard instances representing the status of each service
        """
        raise NotImplementedError("Service status tracking is not implemented yet.")


class ModelRegistry(BaseModel):
    """Registry for managing available embedding, reranking, and sparse embedding models."""

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True,
        defer_build=True,
        str_strip_whitespace=True,
    )

    def __init__(self) -> None:
        """Initialize the model registry."""
        # provider -> (model_name -> capabilities)
        self._embedding_capabilities: MutableMapping[
            Provider, MutableMapping[ModelName, EmbeddingModelCapabilities]
        ] = {}
        self._sparse_embedding_capabilities: MutableMapping[
            Provider, MutableMapping[ModelName, SparseEmbeddingModelCapabilities]
        ] = {}
        self._reranking_capabilities: MutableMapping[
            Provider, MutableMapping[ModelName, RerankingModelCapabilities]
        ] = {}

        # provider -> list[(model_glob, ModelProfileSpec)] for pydantic-ai agentic profiles
        self._agentic_profiles: MutableMapping[Provider, list[tuple[str, AgenticProfileSpec]]] = {}

        # flag to allow one-time default population by caller
        self._populated_defaults: bool = False

    # ---------- Embedding capabilities ----------
    def register_embedding_capabilities(
        self,
        capabilities: EmbeddingModelCapabilities
        | Sequence[EmbeddingModelCapabilities]
        | Iterable[EmbeddingModelCapabilities],
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
            prov_map = self._embedding_capabilities.setdefault(prov, {})
            if not replace and name_key in prov_map:
                continue
            prov_map[name_key] = cap

    def get_embedding_capabilities(
        self, provider: Provider, name: str
    ) -> EmbeddingModelCapabilities | None:
        """Get embedding capabilities for a specific provider and model name."""
        prov_map = self._embedding_capabilities.get(provider)
        return prov_map.get(name.strip().lower()) if prov_map else None

    def list_embedding_models(
        self, provider: Provider | None = None
    ) -> tuple[EmbeddingModelCapabilities, ...]:
        """List all embedding models for a specific provider or all providers."""
        if provider is None:
            return tuple(
                cap
                for prov_map in self._embedding_capabilities.values()
                for cap in prov_map.values()
            )
        return tuple(self._embedding_capabilities.get(provider, {}).values())

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
            prov_map[name_key] = cap

    def get_sparse_embedding_capabilities(
        self, provider: Provider, name: str
    ) -> SparseEmbeddingModelCapabilities | None:
        """Get sparse embedding capabilities for a specific provider and model name."""
        prov_map = self._sparse_embedding_capabilities.get(provider)
        return prov_map.get(name.strip().lower()) if prov_map else None

    def list_sparse_embedding_models(
        self, provider: Provider | None = None
    ) -> tuple[SparseEmbeddingModelCapabilities, ...]:
        """List all sparse embedding models for a specific provider or all providers."""
        if provider is None:
            return tuple(
                cap
                for prov_map in self._sparse_embedding_capabilities.values()
                for cap in prov_map.values()
            )
        return tuple(self._sparse_embedding_capabilities.get(provider, {}).values())

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
            prov = cap.provider  # type: ignore[attr-defined]
            name_key = cap.name.strip().lower()  # type: ignore[attr-defined]
            prov_map = self._reranking_capabilities.setdefault(prov, {})
            if not replace and name_key in prov_map:
                continue
            prov_map[name_key] = cap

    def get_reranking_capabilities(
        self, provider: Provider, name: str
    ) -> RerankingModelCapabilities | None:
        """Get reranking capabilities for a specific provider and model name."""
        prov_map = self._reranking_capabilities.get(provider)
        return prov_map.get(name.strip().lower()) if prov_map else None

    def list_reranking_models(
        self, provider: Provider | None = None
    ) -> tuple[RerankingModelCapabilities, ...]:
        """List all reranking models for a specific provider or all providers."""
        if provider is None:
            return tuple(
                cap
                for prov_map in self._reranking_capabilities.values()
                for cap in prov_map.values()
            )
        return tuple(self._reranking_capabilities.get(provider, {}).values())

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
                profile(name) if callable(profile) else profile
                for glob, profile in rules
                if glob == name or fnmatch(name, glob)
            ),
            None,
        )

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


class ProviderRegistry(BaseModel):
    """Registry for managing provider implementations and settings."""

    model_config = ConfigDict(
        arbitrary_types_allowed=True,
        validate_assignment=True,
        defer_build=True,
        str_strip_whitespace=True,
    )

    _instance: ProviderRegistry | None = None
    _settings: CodeWeaverSettings | None = None
    _embedding_prefix: ClassVar[LiteralStringT] = "codeweaver.embedding.providers."
    _sparse_prefix: ClassVar[LiteralStringT] = "codeweaver.embedding.providers."
    _rerank_prefix: ClassVar[LiteralStringT] = "codeweaver.reranking.providers."
    _agent_import: ClassVar[LiteralStringT] = (
        "codeweaver.agent_providers"  # no end dot because it's a module
    )
    _vector_store_prefix: ClassVar[LiteralStringT] = "codeweaver.vector_stores.providers."
    _provider_map: ClassVar[
        MappingProxyType[ProviderKind, MappingProxyType[Provider, LiteralStringT]]
    ] = MappingProxyType({
        ProviderKind.AGENT: MappingProxyType(
            dict.fromkeys(
                (
                    Provider.ANTHROPIC,
                    Provider.AZURE,
                    Provider.BEDROCK,
                    Provider.COHERE,
                    Provider.DEEPSEEK,
                    Provider.FIREWORKS,
                    Provider.HEROKU,
                    Provider.HUGGINGFACE_INFERENCE,
                    Provider.GITHUB,
                    Provider.GOOGLE,
                    Provider.MISTRAL,
                    Provider.MOONSHOT,
                    Provider.OPENAI,
                    Provider.OPENROUTER,
                    Provider.TOGETHER,
                    Provider.VERCEL,
                    Provider.X_AI,
                ),
                _agent_import,
            )
        ),
        ProviderKind.EMBEDDING: MappingProxyType({
            Provider.AZURE: "EXCEPTION",
            Provider.BEDROCK: f"{_embedding_prefix}bedrock",
            Provider.COHERE: f"{_embedding_prefix}cohere",
            Provider.FASTEMBED: f"{_embedding_prefix}fastembed",
            Provider.FIREWORKS: f"{_embedding_prefix}openai_factory",
            Provider.GITHUB: f"{_embedding_prefix}openai_factory",
            Provider.GOOGLE: f"{_embedding_prefix}google",
            Provider.GROQ: f"{_embedding_prefix}openai_factory",
            Provider.HEROKU: f"{_embedding_prefix}openai_factory",
            Provider.HUGGINGFACE_INFERENCE: f"{_embedding_prefix}huggingface",
            Provider.MISTRAL: f"{_embedding_prefix}mistral",
            Provider.OPENAI: f"{_embedding_prefix}openai_factory",
            Provider.OLLAMA: f"{_embedding_prefix}openai_factory",
            Provider.SENTENCE_TRANSFORMERS: f"{_embedding_prefix}sentence_transformers",
            Provider.VERCEL: f"{_embedding_prefix}openai_factory",
            Provider.VOYAGE: f"{_embedding_prefix}voyage",
        }),
        ProviderKind.SPARSE_EMBEDDING: MappingProxyType({
            Provider.FASTEMBED: f"{_sparse_prefix}fastembed",
            Provider.SENTENCE_TRANSFORMERS: f"{_sparse_prefix}sentence_transformers",
        }),
        ProviderKind.RERANKING: MappingProxyType({
            Provider.BEDROCK: f"{_rerank_prefix}bedrock",
            Provider.COHERE: f"{_rerank_prefix}cohere",
            Provider.FASTEMBED: f"{_rerank_prefix}fastembed",
            Provider.SENTENCE_TRANSFORMERS: f"{_rerank_prefix}sentence_transformers",
            Provider.VOYAGE: f"{_rerank_prefix}voyage",
        }),
        ProviderKind.VECTOR_STORE: MappingProxyType({
            Provider.QDRANT: f"{_vector_store_prefix}qdrant"
        }),
        ProviderKind.DATA: MappingProxyType({
            Provider.DUCKDUCKGO: "codeweaver.tools",
            Provider.TAVILY: "codeweaver.tools",
        }),
    })

    def __init__(self) -> None:
        """Initialize the provider registry."""
        # Provider implementation registries
        self._embedding_providers: MutableMapping[Provider, type[EmbeddingProvider[Any]]] = {}
        self._sparse_embedding_providers: MutableMapping[
            Provider, type[EmbeddingProvider[Any]]
        ] = {}
        self._vector_store_providers: MutableMapping[Provider, type[VectorStoreProvider[Any]]] = {}
        self._reranking_providers: MutableMapping[Provider, type[RerankingProvider[Any]]] = {}
        self._agent_providers: MutableMapping[Provider, type[Any]] = {}
        self._data_providers: MutableMapping[Provider, type[Any]] = {}

        self._embedding_instances: MutableMapping[Provider, EmbeddingProvider[Any]] = {}
        self._sparse_embedding_instances: MutableMapping[Provider, EmbeddingProvider[Any]] = {}
        self._vector_store_instances: MutableMapping[Provider, VectorStoreProvider[Any]] = {}
        self._reranking_instances: MutableMapping[Provider, RerankingProvider[Any]] = {}
        self._agent_instances: MutableMapping[Provider, Any] = {}
        self._data_instances: MutableMapping[Provider, Any] = {}

        # Initialize with built-in providers
        self._register_builtin_providers()

    @classmethod
    def get_instance(cls) -> ProviderRegistry:
        """Get or create the global provider registry instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def settings(self) -> CodeWeaverSettings | None:
        """Get the CodeWeaver settings."""
        if self._settings is None:
            self._settings = importlib.import_module("codeweaver.settings").get_settings()
        return self._settings

    def register(
        self, provider: Provider, provider_kind: ProviderKind, provider_class: type
    ) -> None:
        """Register a provider implementation.

        Args:
            provider: The provider enum identifier
            provider_kind: The type of provider (embedding or vector store)
            provider_class: The provider implementation class
        """
        if provider_kind == ProviderKind.EMBEDDING:
            self.register_embedding_provider(provider, provider_class)
        elif provider_kind == ProviderKind.VECTOR_STORE:
            self.register_vector_store_provider(provider, provider_class)

    def _register_builtin_providers(self) -> None:
        """Register built-in provider implementations."""
        # Register embedding providers dynamically
        for provider_kind, prov_map in self._provider_map.items():
            for provider, module_path in prov_map.items():
                with contextlib.suppress(ImportError, AttributeError):
                    module = __import__(module_path, fromlist=["*"])
                    self._register_provider_by_kind(provider_kind, provider, module, module_path)

    def _register_provider_by_kind(
        self, provider_kind: ProviderKind, provider: Provider, module: Any, module_path: str
    ) -> None:
        """Register a provider based on its kind."""
        match provider_kind:
            case ProviderKind.AGENT:
                self._register_agent_provider_from_module(provider, module)
            case ProviderKind.DATA:
                self._register_data_provider_from_module(provider, module)
            case ProviderKind.EMBEDDING | ProviderKind.SPARSE_EMBEDDING:
                self._register_embedding_provider_from_module(
                    provider, module, module_path, destination=provider_kind
                )
            case ProviderKind.RERANKING:
                self._register_reranking_provider_from_module(provider, module)
            case ProviderKind.VECTOR_STORE:
                self._register_vector_store_provider_from_module(provider, module)
            case _:
                pass

    def _register_agent_provider_from_module(self, provider: Provider, module: Any) -> None:
        """Register an agent provider from a module."""
        if (provider_func := getattr(module, "get_agent_model_provider", None)) and (
            provider_class := provider_func(provider)
        ):
            self.register_agent_provider(provider, provider_class)

    def _register_data_provider_from_module(self, provider: Provider, module: Any) -> None:
        """Register a data provider from a module."""
        if (provider_func := getattr(module, "get_data_provider", None)) and (
            data_provider_class := provider_func(provider)
        ):
            self.register_data_provider(provider, data_provider_class)
        if provider_func and (data_provider_class := provider_func(provider)):
            self.register_data_provider(provider, data_provider_class)

    def _register_embedding_provider_from_module(
        self, provider: Provider, module: Any, module_path: str, destination: ProviderKind
    ) -> None:
        """Register an embedding provider from a module."""
        provider_name = self._get_embedding_provider_name(provider, module_path)
        if provider_class := getattr(module, provider_name, None):
            if destination == ProviderKind.EMBEDDING:
                self.register_embedding_provider(provider, provider_class)
            self.register_sparse_embedding_provider(provider, provider_class)

        if module_path == "EXCEPTION" and provider == Provider.AZURE:
            self._register_azure_exception_providers(provider)

    def _get_embedding_provider_name(self, provider: Provider, module_path: str) -> str:
        """Get the provider name for embedding providers."""
        if provider == Provider.HUGGINGFACE_INFERENCE:
            return "HuggingFaceEmbeddingProvider"
        if module_path.endswith("factory"):
            return "OpenAIEmbeddingBase"
        return f"{to_pascal(str(provider))}EmbeddingProvider"

    def _register_azure_exception_providers(self, provider: Provider) -> None:
        """Register Azure exception providers."""
        with contextlib.suppress(ImportError):
            module = __import__(f"{self._embedding_prefix}openai_factory", fromlist=["*"])
            class_name = f"{to_pascal(str(provider))}OpenAIEmbeddingBase"
            if provider_class := getattr(module, class_name, None):
                self.register_embedding_provider(provider, provider_class)

        with contextlib.suppress(ImportError):
            module = __import__(f"{self._embedding_prefix}cohere", fromlist=["*"])
            if provider_class := getattr(module, "CohereEmbeddingProvider", None):
                self.register_embedding_provider(provider, provider_class)

    def _register_reranking_provider_from_module(self, provider: Provider, module: Any) -> None:
        """Register a reranking provider from a module."""
        provider_name = f"{to_pascal(str(provider))}RerankingProvider"
        if provider_class := getattr(module, provider_name, None):
            self.register_reranking_provider(provider, provider_class)

    def _register_vector_store_provider_from_module(self, provider: Provider, module: Any) -> None:
        """Register a vector store provider from a module."""
        provider_name = f"{to_pascal(str(provider))}VectorStoreProvider"
        if provider_class := getattr(module, provider_name, None):
            self.register_vector_store_provider(provider, provider_class)

    def add_settings(self, settings: CodeWeaverSettings) -> None:
        """Add settings to the provider registry."""
        self._settings = settings

    def register_agent_provider(self, provider: Provider, provider_class: type[Any]) -> None:
        """Register an agent provider implementation.

        Args:
            provider: The provider enum identifier
            provider_class: The provider implementation class
        """
        self._agent_providers[provider] = provider_class

    def register_data_provider(self, provider: Provider, provider_class: type[Any]) -> None:
        """Register a data provider implementation.

        Args:
            provider: The provider enum identifier
            provider_class: The provider implementation class
        """
        self._data_providers[provider] = provider_class

    def register_embedding_provider(
        self, provider: Provider, provider_class: type[EmbeddingProvider[Any]]
    ) -> None:
        """Register an embedding provider implementation.

        Args:
            provider: The provider enum identifier
            provider_class: The provider implementation class
        """
        self._embedding_providers[provider] = provider_class

    def register_sparse_embedding_provider(
        self, provider: Provider, provider_class: type[EmbeddingProvider[Any]]
    ) -> None:
        """Register a sparse embedding provider implementation.

        Args:
            provider: The provider enum identifier
            provider_class: The provider implementation class
        """
        self._sparse_embedding_providers[provider] = provider_class

    def register_reranking_provider(
        self, provider: Provider, provider_class: type[RerankingProvider[Any]]
    ) -> None:
        """Register a reranking provider implementation.

        Args:
            provider: The provider enum identifier
            provider_class: The provider implementation class
        """
        self._reranking_providers[provider] = provider_class

    def register_vector_store_provider(
        self, provider: Provider, provider_class: type[VectorStoreProvider[Any]]
    ) -> None:
        """Register a vector store provider implementation.

        Args:
            provider: The provider enum identifier
            provider_class: The provider implementation class
        """
        self._vector_store_providers[provider] = provider_class

    def get_embedding_provider_class(self, provider: Provider) -> type[EmbeddingProvider[Any]]:
        """Get an embedding provider class by provider enum.

        Args:
            provider: The provider enum identifier

        Returns:
            The provider class

        Raises:
            ConfigurationError: If provider is not registered
        """
        if provider not in self._embedding_providers:
            raise ConfigurationError(f"Embedding provider '{provider}' is not registered")

        return self._embedding_providers[provider]

    def get_sparse_embedding_provider_class(
        self, provider: Provider
    ) -> type[EmbeddingProvider[Any]]:
        """Get a sparse embedding provider class by provider enum.

        Args:
            provider: The provider enum identifier

        Returns:
            The provider class

        Raises:
            ConfigurationError: If provider is not registered
        """
        if provider not in self._sparse_embedding_providers:
            raise ConfigurationError(f"Sparse embedding provider '{provider}' is not registered")

        return self._sparse_embedding_providers[provider]

    def get_reranking_provider_class(self, provider: Provider) -> type[RerankingProvider[Any]]:
        """Get a reranking provider class by provider enum.

        Args:
            provider: The provider enum identifier

        Returns:
            The provider class

        Raises:
            ConfigurationError: If provider is not registered
        """
        if provider not in self._reranking_providers:
            raise ConfigurationError(f"Reranking provider '{provider}' is not registered")

        return self._reranking_providers[provider]

    def get_vector_store_provider_class(self, provider: Provider) -> type[VectorStoreProvider[Any]]:
        """Get a vector store provider class by provider enum.

        Args:
            provider: The provider enum identifier

        Returns:
            The provider class

        Raises:
            ConfigurationError: If provider is not registered
        """
        if provider not in self._vector_store_providers:
            raise ConfigurationError(f"Vector store provider '{provider}' is not registered")

        return self._vector_store_providers[provider]

    def get_agent_provider_class(self, provider: Provider) -> type[AgentProvider[Any]]:
        """Get an agent provider class by provider enum.

        Args:
            provider: The provider enum identifier

        Returns:
            The provider class

        Raises:
            ConfigurationError: If provider is not registered
        """
        if provider not in self._agent_providers:
            raise ConfigurationError(f"Agent provider '{provider}' is not registered")

        return self._agent_providers[provider]

    def get_data_provider_class(self, provider: Provider) -> type[Any]:
        """Get a data provider class by provider enum.

        Args:
            provider: The provider enum identifier

        Returns:
            The provider class

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
        provider_class = self.get_embedding_provider_class(provider)
        return provider_class(**kwargs)

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
        provider_class = self.get_embedding_provider_class(provider)
        return provider_class(**kwargs)

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
        provider_class = self.get_reranking_provider_class(provider)
        return provider_class(**kwargs)

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
        provider_class = self.get_vector_store_provider_class(provider)
        return provider_class(**kwargs)

    def create_agent_provider(self, provider: Provider, **kwargs: Any) -> AgentProvider[Any]:
        """Create an agent provider instance.

        Args:
            provider: The provider enum identifier
            **kwargs: Provider-specific initialization arguments

        Returns:
            An initialized provider instance
        """
        provider_class = self.get_agent_provider_class(provider)
        return provider_class(**kwargs)

    def create_data_provider(self, provider: Provider, **kwargs: Any) -> Any:
        """Create a data provider instance.

        Args:
            provider: The provider enum identifier
            **kwargs: Provider-specific initialization arguments

        Returns:
            An initialized provider instance
        """
        provider_class = self.get_data_provider_class(provider)
        return provider_class(**kwargs)

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

    def is_provider_available(self, provider: Provider, provider_kind: ProviderKind) -> bool:
        """Check if a provider is available for a given provider kind.

        Args:
            provider: The provider to check
            provider_kind: The type of provider to check

        Returns:
            True if the provider is available
        """
        if provider_kind == ProviderKind.EMBEDDING:
            return provider in self._embedding_providers
        if provider_kind == ProviderKind.VECTOR_STORE:
            return provider in self._vector_store_providers
        if provider_kind == ProviderKind.RERANKING:
            return provider in self._reranking_providers
        if provider_kind == ProviderKind.SPARSE_EMBEDDING:
            return provider in self._sparse_embedding_providers
        if provider_kind == ProviderKind.AGENT:
            return provider in self._agent_providers
        if provider_kind == ProviderKind.DATA:
            return provider in self._data_providers
        return False

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


def update_settings(settings: CodeWeaverSettings) -> None:
    """Update the global settings registry instance."""
    return _provider_registry.add_settings(settings)


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
