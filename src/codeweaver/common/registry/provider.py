# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Provider registry for managing provider implementations and settings."""
# sourcery skip: no-complex-if-expressions

from __future__ import annotations

import contextlib
import importlib
import logging

from collections.abc import Callable, Mapping, MutableMapping
from functools import partial
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, ClassVar, Literal, TypeGuard, cast, overload

from pydantic import ConfigDict, SecretStr
from textcase import pascal
from typing_extensions import TypeIs

from codeweaver.common.utils.lazy_importer import LazyImport, lazy_import
from codeweaver.config.providers import SparseEmbeddingProviderSettings
from codeweaver.config.types import CodeWeaverSettingsDict
from codeweaver.core.types.aliases import LiteralStringT
from codeweaver.core.types.dictview import DictView
from codeweaver.core.types.models import BasedModel
from codeweaver.exceptions import ConfigurationError
from codeweaver.providers.agent.agent_providers import AgentProvider
from codeweaver.providers.embedding.capabilities.base import SparseEmbeddingModelCapabilities
from codeweaver.providers.embedding.providers.base import EmbeddingProvider, SparseEmbeddingProvider

# NOTE: Re-export Provider and ProviderKind for easier access -- anyone importing the registry likely needs these too
from codeweaver.providers.provider import Provider as Provider
from codeweaver.providers.provider import ProviderKind as ProviderKind
from codeweaver.providers.reranking.providers.base import RerankingProvider
from codeweaver.providers.vector_stores.base import VectorStoreProvider


if TYPE_CHECKING:
    from openai import AsyncOpenAI

    from codeweaver.common.registry.types import (
        LiteralDataKinds,
        LiteralKinds,
        LiteralModelKinds,
        LiteralVectorStoreKinds,
    )
    from codeweaver.config.providers import (
        AgentProviderSettings,
        DataProviderSettings,
        EmbeddingProviderSettings,
        RerankingProviderSettings,
        VectorStoreProviderSettings,
    )
    from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities
    from codeweaver.providers.types import LiteralProvider, LiteralProviderKind


logger = logging.getLogger(__name__)


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
        MappingProxyType[LiteralProviderKind, Mapping[LiteralProvider, partial[LazyImport[Any]]]]
    ] = cast(
        "MappingProxyType[LiteralProviderKind, Mapping[LiteralProvider, partial[LazyImport[Any]]]]",
        MappingProxyType({
            ProviderKind.AGENT: {
                Provider.ANTHROPIC: partial(lazy_import, f"{_agent_prefix}agent_providers"),
                Provider.AZURE: partial(lazy_import, f"{_agent_prefix}agent_providers"),
                Provider.BEDROCK: partial(lazy_import, f"{_agent_prefix}agent_providers"),
                Provider.CEREBRAS: partial(lazy_import, f"{_agent_prefix}agent_providers"),
                Provider.COHERE: partial(lazy_import, f"{_agent_prefix}agent_providers"),
                Provider.DEEPSEEK: partial(lazy_import, f"{_agent_prefix}agent_providers"),
                Provider.FIREWORKS: partial(lazy_import, f"{_agent_prefix}agent_providers"),
                Provider.HEROKU: partial(lazy_import, f"{_agent_prefix}agent_providers"),
                Provider.HUGGINGFACE_INFERENCE: partial(
                    lazy_import, f"{_agent_prefix}agent_providers"
                ),
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
            },  # ProviderKind.EMBEDDING -> Provider.AZURE, Literal["EXCEPTION"] but I couldn't find a way to type it correctly
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
                Provider.HUGGINGFACE_INFERENCE: partial(
                    lazy_import, f"{_embedding_prefix}huggingface"
                ),
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
        }),
    )

    def __init__(self) -> None:
        """Initialize the provider registry.

        For builtin providers, we register lazy imports to avoid unnecessary imports until the provider is needed. For third-party providers, we expect the class to be provided directly.
        """
        # Provider implementation registries
        # we store lazy references to the providers and only try to fetch them when called
        self._embedding_providers: MutableMapping[
            Provider, LazyImport[type[EmbeddingProvider[Any]]] | type[EmbeddingProvider[Any]]
        ] = {}
        self._sparse_embedding_providers: MutableMapping[
            Provider,
            LazyImport[type[SparseEmbeddingProvider[Any]]] | type[SparseEmbeddingProvider[Any]],
        ] = {}
        self._vector_store_providers: MutableMapping[
            Provider, LazyImport[type[VectorStoreProvider[Any]]] | type[VectorStoreProvider[Any]]
        ] = {}
        self._reranking_providers: MutableMapping[
            Provider, LazyImport[type[RerankingProvider[Any]]] | type[RerankingProvider[Any]]
        ] = {}
        self._agent_providers: MutableMapping[
            Provider, LazyImport[type[AgentProvider[Any]]] | type[AgentProvider[Any]]
        ] = {}
        self._data_providers: MutableMapping[Provider, LazyImport[type[Any]] | type[Any]] = {}

        self._embedding_instances: MutableMapping[Provider, EmbeddingProvider[Any]] = {}
        self._sparse_embedding_instances: MutableMapping[
            Provider, SparseEmbeddingProvider[Any]
        ] = {}
        self._vector_store_instances: MutableMapping[Provider, VectorStoreProvider[Any]] = {}
        self._reranking_instances: MutableMapping[Provider, RerankingProvider[Any]] = {}
        self._agent_instances: MutableMapping[Provider, AgentProvider[Any]] = {}
        self._data_instances: MutableMapping[Provider, Any] = {}

        # Register builtin providers
        self._register_builtin_pydantic_ai_providers()
        self._register_builtin_providers()

    def _telemetry_keys(self) -> None:
        return None

    @classmethod
    def get_instance(cls) -> ProviderRegistry:
        """Get or create the global provider registry instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    @property
    def _registry_map(
        self,
    ) -> dict[
        ProviderKind | str,
        tuple[
            MutableMapping[
                Provider,
                type[
                    EmbeddingProvider[Any]
                    | SparseEmbeddingProvider[Any]
                    | RerankingProvider[Any]
                    | VectorStoreProvider[Any]
                    | AgentProvider[Any]
                    | Any
                ]
                | LazyImport[type[EmbeddingProvider[Any]]]
                | LazyImport[type[SparseEmbeddingProvider[Any]]]
                | LazyImport[type[RerankingProvider[Any]]]
                | LazyImport[type[VectorStoreProvider[Any]]]
                | LazyImport[type[AgentProvider[Any]]]
                | LazyImport[type[Any]],
            ],
            str,
        ],
    ]:
        """Map provider kinds to their runtime registries and human-readable names.

        Returns mapping of provider kind to (registry, kind_name) tuples where:
        - registry: The mutable mapping storing provider implementations
        - kind_name: Human-readable name for error messages
        """
        return {
            ProviderKind.EMBEDDING: (self._embedding_providers, "Embedding"),
            "embedding": (self._embedding_providers, "Embedding"),
            ProviderKind.SPARSE_EMBEDDING: (self._sparse_embedding_providers, "Sparse embedding"),
            "sparse_embedding": (self._sparse_embedding_providers, "Sparse embedding"),
            ProviderKind.RERANKING: (self._reranking_providers, "Reranking"),
            "reranking": (self._reranking_providers, "Reranking"),
            ProviderKind.VECTOR_STORE: (self._vector_store_providers, "Vector store"),
            "vector_store": (self._vector_store_providers, "Vector store"),
            ProviderKind.AGENT: (self._agent_providers, "Agent"),
            "agent": (self._agent_providers, "Agent"),
            ProviderKind.DATA: (self._data_providers, "Data"),
            "data": (self._data_providers, "Data"),
        }  # type: ignore

    def _is_literal_data_kind(self, kind: Any) -> TypeIs[Literal[ProviderKind.DATA, "data"]]:
        """Check if the kind is a data provider kind."""
        return kind in (ProviderKind.DATA, "data")

    def _is_literal_vector_store_kind(
        self, kind: Any
    ) -> TypeIs[Literal[ProviderKind.VECTOR_STORE, "vector_store"]]:
        """Check if the kind is a vector store provider kind."""
        return kind in (ProviderKind.VECTOR_STORE, "vector_store")

    def _is_literal_model_kind(
        self, kind: Any
    ) -> TypeIs[
        Literal[
            ProviderKind.AGENT,
            "agent",
            ProviderKind.EMBEDDING,
            "embedding",
            ProviderKind.SPARSE_EMBEDDING,
            "sparse_embedding",
            ProviderKind.RERANKING,
            "reranking",
        ]
    ]:
        """Check if the kind is a model provider kind."""
        return kind in (
            ProviderKind.AGENT,
            "agent",
            ProviderKind.EMBEDDING,
            "embedding",
            ProviderKind.SPARSE_EMBEDDING,
            "sparse_embedding",
            ProviderKind.RERANKING,
            "reranking",
        )

    def _is_literal_agent_kind(self, kind: Any) -> TypeIs[Literal[ProviderKind.AGENT, "agent"]]:
        """Check if the kind is an agent provider kind."""
        return kind in (ProviderKind.AGENT, "agent")

    def _is_literal_embedding_kind(
        self, kind: Any
    ) -> TypeIs[Literal[ProviderKind.EMBEDDING, "embedding"]]:
        """Check if the kind is an embedding provider kind."""
        return kind in (ProviderKind.EMBEDDING, "embedding")

    def _is_literal_sparse_embedding_kind(
        self, kind: Any
    ) -> TypeIs[Literal[ProviderKind.SPARSE_EMBEDDING, "sparse_embedding"]]:
        """Check if the kind is a sparse embedding provider kind."""
        return kind in (ProviderKind.SPARSE_EMBEDDING, "sparse_embedding")

    def _is_literal_reranking_kind(
        self, kind: Any
    ) -> TypeIs[Literal[ProviderKind.RERANKING, "reranking"]]:
        """Check if the kind is a reranking provider kind."""
        return kind in (ProviderKind.RERANKING, "reranking")

    def _is_any_provider_kind(self, kind: Any) -> TypeIs[ProviderKind]:
        """Check if the kind is any valid ProviderKind."""
        return kind in ProviderKind

    def register(  # how?
        self,
        provider: Provider | str,
        provider_kind: LiteralKinds,
        provider_class: LazyImport[type] | type,
    ) -> None:
        """Register a provider implementation.

        Args:
            provider: The provider enum identifier or string equivalent
            provider_kind: The type of provider (embedding or vector store)
            provider_class: The provider implementation class
        """
        if not isinstance(provider, Provider):
            provider = Provider.from_string(provider)
        if not isinstance(provider_kind, ProviderKind):
            provider_kind = ProviderKind(provider_kind)  # type: ignore
        match provider_kind:
            case ProviderKind.AGENT:
                if self._is_literal_agent_kind(provider_kind):
                    self._agent_providers[provider] = provider_class
            case ProviderKind.DATA:
                if self._is_literal_data_kind(provider_kind):
                    self._data_providers[provider] = provider_class
            case ProviderKind.EMBEDDING:
                if self._is_literal_embedding_kind(provider_kind):
                    self._embedding_providers[provider] = provider_class
            case ProviderKind.SPARSE_EMBEDDING:
                if self._is_literal_sparse_embedding_kind(provider_kind):
                    self._sparse_embedding_providers[provider] = provider_class
            case ProviderKind.VECTOR_STORE:
                if self._is_literal_vector_store_kind(provider_kind):
                    self._vector_store_providers[provider] = provider_class
            case ProviderKind.RERANKING:
                if self._is_literal_reranking_kind(provider_kind):
                    self._reranking_providers[provider] = provider_class
            case _:
                pass

    def _register_builtin_pydantic_ai_providers(self) -> None:
        """Register built-in Pydantic AI providers."""
        with contextlib.suppress(Exception):
            agent_module = importlib.import_module(self._agent_prefix.rstrip("."))
            if providers_func := getattr(agent_module, "load_default_agent_providers", None):
                providers = providers_func()
                for provider_class in providers:
                    if provider := next(
                        (p for p in Provider if str(p).lower() in provider_class.__name__.lower()),
                        None,
                    ):
                        self.register(provider, ProviderKind.AGENT, provider_class)
        data_module = importlib.import_module("codeweaver.providers.data")
        if tools_func := getattr(data_module, "load_default_data_providers", None):
            for tool in tools_func():
                provider = (
                    Provider.DUCKDUCKGO if "duck" in tool.__name__.lower() else Provider.TAVILY
                )
                self.register(provider, ProviderKind.DATA, tool)

    def _register_builtin_providers(self) -> None:
        """Register built-in provider implementations."""
        # Register embedding providers dynamically
        for provider_kind, prov_map in self._provider_map.items():
            if provider_kind == ProviderKind.AGENT:
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
        provider_name = self._get_embedding_provider_name(provider, module, destination)
        lazy_class_import = module(provider_name)

        if getattr(lazy_class_import, provider_name, None):
            if destination == ProviderKind.EMBEDDING:
                self._embedding_providers[provider] = lazy_class_import
            elif destination == ProviderKind.SPARSE_EMBEDDING:
                self._sparse_embedding_providers[provider] = lazy_class_import

    def _get_embedding_provider_name(
        self,
        provider: Provider,
        module: partial[LazyImport[Any]],
        destination: ProviderKind | None = None,
    ) -> str:
        """Get the provider name for embedding providers."""
        if provider == Provider.HUGGINGFACE_INFERENCE:
            return "HuggingFaceEmbeddingProvider"

        # Special handling for fastembed - uses different class names
        if provider == Provider.FASTEMBED:
            if destination == ProviderKind.SPARSE_EMBEDDING:
                return "FastEmbedSparseProvider"
            return "FastEmbedEmbeddingProvider"

        # Handle both string and LazyImport module names
        module_name = module.args[0]
        if hasattr(module_name, "_module_name"):
            module_name = module_name._module_name

        if module_name == "codeweaver.providers.embedding.providers.openai_factory":
            return "OpenAIEmbeddingBase"
        return f"{pascal(str(provider))}EmbeddingProvider"

    def _register_azure_exception_providers(self, provider: Provider) -> None:
        """Register Azure exception providers."""
        module_name = f"{self._embedding_prefix}openai_factory"
        class_name = f"{pascal(str(provider))}OpenAIEmbeddingBase"
        self._embedding_providers[provider] = LazyImport(module_name, class_name)

        module_name = f"{self._embedding_prefix}cohere"
        self._embedding_providers[provider] = LazyImport(module_name, "CohereEmbeddingProvider")

    def _register_reranking_provider_from_module(
        self, provider: Provider, module: partial[LazyImport[type[RerankingProvider[Any]]]]
    ) -> None:
        """Register a reranking provider from a module."""
        provider_name = f"{pascal(str(provider))}RerankingProvider"
        self._reranking_providers[provider] = module(provider_name)

    def _register_vector_store_provider_from_module(
        self, provider: Provider, module: partial[LazyImport[type[VectorStoreProvider[Any]]]]
    ) -> None:
        """Register a vector store provider from a module."""
        provider_name = f"{pascal(str(provider))}VectorStoreProvider"
        self._vector_store_providers[provider] = module(provider_name)

    def _is_openai_factory(
        self, provider: Provider, provider_kind: LiteralProviderKind
    ) -> TypeGuard[LazyImport[type[Any]] | type[Any]]:
        """Check if a provider needs a class created in the openai class factory.

        Args:
            provider: the provider
            provider_kind: the kind of provider

        Returns:
            True if this is the OpenAI factory class
        """
        return (
            provider.is_embedding_provider
            and provider_kind == ProviderKind.EMBEDDING
            and provider.uses_openai_api
        )

    def _get_capabilities_for_provider(
        self, provider: Provider
    ) -> tuple[EmbeddingModelCapabilities, ...]:
        """Get capabilities for a provider.

        Args:
            provider: The provider to get capabilities for

        Returns:
            EmbeddingModelCapabilities instance for the provider
        """
        from codeweaver.providers.embedding.capabilities import load_default_capabilities

        # Get all capabilities for this provider type
        all_caps = load_default_capabilities()

        return tuple(cap for cap in all_caps if cap.provider == provider)

    def _get_default_model_for_provider(
        self, provider: Provider, capabilities: EmbeddingModelCapabilities
    ) -> str:
        """Get default model name for a provider.

        Args:
            provider: The provider to get model for
            capabilities: Capabilities containing default model

        Returns:
            Model name string
        """
        # Check config first
        from codeweaver.common.registry.utils import get_model_config

        config = get_model_config("embedding")
        if config and config.get("model_settings"):
            model_settings = config["model_settings"]
            if model_name := model_settings.get("model_name"):
                return model_name

        # Fallback to capabilities
        return capabilities.name

    def _get_base_url_for_provider(self, provider: Provider, **kwargs: Any) -> str | None:
        """Map Provider enum to default base URLs.

        Args:
            provider: The provider to get base URL for

        Returns:
            Base URL string or None
        """
        url_map: dict[Provider, LazyImport[Callable[[Mapping[str, Any]], str]] | str] = {
            Provider.AZURE: lazy_import(
                "codeweaver.providers.embedding.providers.openai_factory", "try_for_azure_endpoint"
            ),
            Provider.CEREBRAS: "https://api.cerebras.ai/v1",
            Provider.FIREWORKS: "https://api.fireworks.ai/inference/v1",
            Provider.GITHUB: "https://models.inference.ai.azure.com",
            Provider.GROQ: "https://api.groq.com/openai/v1",
            Provider.HEROKU: lazy_import(
                "codeweaver.providers.embedding.providers.openai_factory", "try_for_heroku_endpoint"
            ),
            Provider.OLLAMA: "http://localhost:11434/v1",
            Provider.OPENAI: "https://api.openai.com/v1",
            Provider.VERCEL: "https://ai-gateway.vercel.sh/v1",
        }
        if (value := url_map.get(provider)) and isinstance(value, str):
            return value
        return value._resolve()(**kwargs) if value else None  # type: ignore

    # 🔧 NEW: Client Factory Methods

    def collect_env_vars(self, provider: Provider) -> dict[str, str]:
        """Collect relevant environment variables for a provider.

        Args:
            provider: The provider to collect env vars for

        Returns:
            Dictionary mapping environment variable names to their values
        """
        import os

        from codeweaver.providers.provider import ProviderEnvVarInfo, ProviderEnvVars

        env_vars: tuple[ProviderEnvVars, ...] | None = provider.other_env_vars
        if env_vars is None:
            return {}
        assembled_vars: dict[str, str] = {}
        for provider_vars in env_vars:
            for role, var_info in provider_vars.items():
                if role == "note":
                    continue
                if role == "other":
                    other_vars: dict[str, ProviderEnvVarInfo] = var_info  # type: ignore[assignment]
                    values: list[ProviderEnvVarInfo] = list(other_vars.values())
                    for info in values:
                        if (var_present := os.getenv(info.env)) and info.env not in (
                            # these are httpx env variables that can be used for providers with httpx backends but shouldn't get passed
                            "HTTPS_PROXY",
                            "SSL_CERT_FILE",
                        ):
                            assembled_vars[info.variable_name or role] = var_present
                if isinstance(var_info, ProviderEnvVarInfo) and (
                    var_present := os.getenv(var_info.env)
                ):
                    if (
                        (name := var_info.variable_name or role) == "host"
                        and provider == Provider.QDRANT
                        and "http" in var_present.lower()
                        and var_present.lower() not in ("localhost", "127.0.0.1")
                    ):
                        # Qdrant is particular about what attribute gets the URL
                        # you'd think host + port is equivalent to URL.... but apparently not
                        # ... and it likes to fail in a way that tells you nothing about the issue
                        assembled_vars["url"] = var_present
                    assembled_vars[name] = var_present

        return assembled_vars

    def _create_client_from_map(
        self,
        provider: Provider,
        provider_kind: ProviderKind | str,
        provider_settings: dict[str, Any] | None,
        client_options: dict[str, Any] | None,
    ) -> Any:
        """Create client instance using CLIENT_MAP from capabilities.

        Args:
            provider: Provider enum (VOYAGE, OPENAI, QDRANT, etc.)
            provider_kind: Provider kind (embedding, reranking, vector_store, etc.)
            provider_settings: Provider-specific auth/config (API keys, endpoints, paths)
            client_options: User-specified client options (timeout, retries, etc.)

        Returns:
            Configured client instance ready for use, or None if:
            - Provider doesn't require a client
            - Provider is pydantic-ai origin (handled elsewhere)
            - Client creation should be delegated to provider

        Raises:
            ConfigurationError: If client creation fails due to missing dependencies
                or invalid configuration.
        """
        from codeweaver.exceptions import ConfigurationError
        from codeweaver.providers.capabilities import CLIENT_MAP, get_client_map

        # Normalize provider_kind to ProviderKind enum if string
        if isinstance(provider_kind, str):
            provider_kind = ProviderKind(provider_kind)
        if provider not in CLIENT_MAP:
            logger.debug("No CLIENT_MAP entry for provider '%s'", provider)
            return None
        # Get client entries for this provider
        client_entries = get_client_map(cast("LiteralProvider", provider))
        if not client_entries:
            logger.debug("No CLIENT_MAP entry for provider '%s'", provider)
            return None

        matching_client = next(
            (client_entry for client_entry in client_entries if client_entry.kind == provider_kind),
            None,
        )
        if not matching_client:
            logger.debug(
                "No CLIENT_MAP entry for provider '%s' with kind '%s'", provider, provider_kind
            )
            return None

        # Skip pydantic-ai providers - not yet integrated
        if matching_client.origin == "pydantic-ai":
            logger.debug(
                "Provider '%s' (%s) is pydantic-ai origin, skipping client creation",
                provider,
                provider_kind,
            )
            return None

        # Skip if no client class defined
        if not matching_client.client:
            logger.debug("Provider '%s' (%s) has no client class defined", provider, provider_kind)
            return None

        # Resolve the lazy import to get actual client class
        try:
            client_class = matching_client.client._resolve()  # type: ignore
        except Exception as e:
            logger.exception(
                "Failed to resolve client import for provider '%s' (%s)", provider, provider_kind
            )
            raise ConfigurationError(
                f"Provider '{provider}' client import failed. Ensure the required package is installed."
            ) from e

        # Prepare client options
        provider_settings = provider_settings or {}
        opts_raw = self.get_configured_provider_settings(provider_kind) or client_options or {}  # type: ignore
        # Convert DictView to dict for union operations
        opts = dict(opts_raw) if opts_raw else {}
        # Extract nested provider_settings from configured settings if present
        if "provider_settings" in opts:
            opts = opts["provider_settings"]  # type: ignore
        env_vars = self.collect_env_vars(provider)
        # Merge settings and filter out 'provider' key to avoid conflicts
        merged_settings = provider_settings | env_vars | opts
        base_url_kwargs = {k: v for k, v in merged_settings.items() if k != "provider"}
        base_url = self._get_base_url_for_provider(provider, **base_url_kwargs)
        if base_url and (
            "base_url" not in provider_settings or not provider_settings.get("base_url")
        ):
            provider_settings |= {"base_url": base_url} | env_vars

        # Create client based on provider type
        try:
            return self._instantiate_client(
                provider, provider_kind, client_class, provider_settings, opts
            )
        except Exception as e:
            logger.exception(
                "Failed to create client for provider '%s' (%s)", provider, provider_kind
            )
            raise ConfigurationError(f"Provider '{provider}' client creation failed: {e}") from e

    def _instantiate_client(
        self,
        provider: Provider,
        provider_kind: ProviderKind,
        client_class: type[Any],
        provider_settings: dict[str, Any],
        client_options: dict[str, Any],
    ) -> Any:
        """Instantiate a client with provider-specific configuration.

        Args:
            provider: Provider enum
            provider_kind: Provider kind enum
            client_class: Resolved client class
            provider_settings: Provider-specific settings
            client_options: Client options

        Returns:
            Configured client instance
        """
        from urllib.parse import urlparse

        # Handle special cases first
        if provider_kind == ProviderKind.UNSET:
            raise ConfigurationError(
                f"Cannot create client for provider '{provider}' with unset kind."
            )

        # 1. Boto3 clients (Bedrock)
        if provider == Provider.BEDROCK:
            provider_settings = provider_settings or {}
            return client_class(
                "bedrock-runtime"
                if provider_kind == ProviderKind.EMBEDDING
                else "bedrock-agent-runtime",
                **(provider_settings | client_options),
            )

        # 3. Qdrant (supports URL, path, or memory)
        if provider in (Provider.QDRANT, Provider.MEMORY):
            if provider == Provider.QDRANT:
                try:
                    # Merge options, with provider_settings taking precedence
                    # But exclude provider-specific settings that aren't client parameters
                    qdrant_client_settings = {
                        k: v.get_secret_value() if isinstance(v, SecretStr) else v
                        for k, v in (provider_settings or {}).items()
                        if k not in ("collection_name", "provider")
                    }
                    merged_opts = (client_options or {}) | qdrant_client_settings
                    # Also remove collection_name from client_options if present
                    merged_opts = {k: v for k, v in merged_opts.items() if k != "collection_name"}

                    # Fall back to environment variable for API key if not in config
                    if not merged_opts.get("api_key") and (
                        env_api_key := provider.get_env_api_key()
                    ):
                        merged_opts["api_key"] = env_api_key

                    if merged_opts.get("url") and urlparse(merged_opts["url"]).netloc.endswith(
                        ".qdrant.io"
                    ):
                        # it likes to complain about being unable to check compatibility with qdrant.io
                        merged_opts["check_compatibility"] = False
                    client = client_class(**merged_opts)
                except Exception as e:
                    logger.warning("Failed to create Qdrant client: %s", e)
                    logger.info("Falling back to in-memory mode")
                    # For in-memory fallback, remove ALL connection-related options
                    # Only keep generic client options like timeout, grpc_port, etc.
                    # qdrant_client also does this, but better safe than sorry
                    clean_opts = {}
                    return client_class(location=":memory:", **clean_opts)
                else:
                    return client
            return client_class(location=":memory:")

        # 4. Local model libraries (no authentication needed)
        if provider in (Provider.FASTEMBED, Provider.SENTENCE_TRANSFORMERS):
            # These take model name/path in provider_settings, not client_options
            # Ensure lazy_load is set for fastembed to avoid blocking model downloads
            if provider == Provider.FASTEMBED:
                # Set default cache_dir to persistent location if not provided
                if "cache_dir" not in (client_options or {}):
                    from codeweaver.common.utils.utils import get_user_config_dir

                    models_cache = get_user_config_dir() / ".models"
                    models_cache.mkdir(parents=True, exist_ok=True)
                    client_options = {
                        "cache_dir": str(models_cache),
                        "lazy_load": True,
                        **(client_options or {}),
                    }
                else:
                    client_options = {"lazy_load": True, **(client_options or {})}

                if provider_kind == ProviderKind.EMBEDDING:
                    # The client_class for embeddings is returned by `get_text_embedder()` in `codeweaver.providers.embedding.fastembed_extensions`
                    # We need to call it first.
                    client_class = client_class()

            model_name_or_path = provider_settings.get("model") if provider_settings else None
            if model_name_or_path:
                return client_class(model_name=model_name_or_path, **client_options)
            if (capabilities := self.get_configured_provider_settings(provider_kind)) and (
                model_settings := capabilities.get("model_settings")
            ):  # type: ignore
                model: str = model_settings["model"]
                return client_class(model_name=model, **client_options)
            # Let provider handle default model selection
            return client_class(**client_options)

        # Construct client based on what parameters it accepts
        from codeweaver.common.utils.introspect import clean_args

        provider_settings = provider_settings or {}
        merged_settings = provider_settings | client_options
        args, kwargs = clean_args(merged_settings, client_class)
        args = tuple(arg.get_secret_value() if isinstance(arg, SecretStr) else arg for arg in args)
        kwargs = {
            k: v.get_secret_value() if isinstance(v, SecretStr) else v for k, v in kwargs.items()
        }
        return client_class(*args, **kwargs)

    def _create_vector_store_client(
        self,
        provider: Provider,
        provider_settings: dict[str, Any] | None,
        client_options: dict[str, Any] | None,
    ) -> Any:
        """Create client instance for vector store providers.

        This method is now a thin wrapper around _create_client_from_map.

        Args:
            provider: Provider enum
            provider_settings: Provider-specific connection config
            client_options: User-specified client options

        Returns:
            Configured client instance or None
        """
        return self._create_client_from_map(
            provider, ProviderKind.VECTOR_STORE, provider_settings, client_options
        )

    def _construct_openai_provider_class(
        self, provider: Provider, factory: Any, **kwargs: Any
    ) -> Any:
        """Construct the actual provider class from OpenAI factory.

        Args:
            provider: The provider enum
            factory: LazyImport or class reference to OpenAIEmbeddingBase
            **kwargs: Additional parameters that may contain overrides

        Returns:
            The constructed provider class type
        """
        # Resolve LazyImport if needed
        factory_class = factory._resolve() if isinstance(factory, LazyImport) else factory  # type: ignore

        # Get capabilities for this provider
        capabilities = self._get_capabilities_for_provider(provider)

        # Get model name (kwargs override config)
        model_name = kwargs.get("model") or self._get_default_model_for_provider(
            provider, capabilities[0]
        )

        # Get base URL (kwargs override defaults)
        base_url = kwargs.get("base_url") or self._get_base_url_for_provider(provider)

        # Get provider-specific kwargs
        provider_kwargs = kwargs.get("provider_kwargs")

        # Get client if provided
        client: AsyncOpenAI | None = kwargs.get("client")
        from codeweaver.providers.embedding.providers.openai_factory import OpenAIEmbeddingBase

        # Call the factory method to construct the provider class
        return cast(OpenAIEmbeddingBase, factory_class).get_provider_class(
            model_name=model_name,
            provider=provider,
            capabilities=capabilities[0],
            base_url=base_url,
            provider_kwargs=provider_kwargs,
            client=client,
        )

    @overload
    def get_provider_class(
        self, provider: Provider, provider_kind: Literal[ProviderKind.EMBEDDING, "embedding"]
    ) -> LazyImport[type[EmbeddingProvider[Any]]] | type[EmbeddingProvider[Any]]: ...
    @overload
    def get_provider_class(
        self,
        provider: Provider,
        provider_kind: Literal[ProviderKind.SPARSE_EMBEDDING, "sparse_embedding"],
    ) -> LazyImport[type[SparseEmbeddingProvider[Any]]] | type[SparseEmbeddingProvider[Any]]: ...
    @overload
    def get_provider_class(
        self, provider: Provider, provider_kind: Literal[ProviderKind.RERANKING, "reranking"]
    ) -> LazyImport[type[RerankingProvider[Any]]] | type[RerankingProvider[Any]]: ...
    @overload
    def get_provider_class(
        self, provider: Provider, provider_kind: LiteralVectorStoreKinds
    ) -> LazyImport[type[VectorStoreProvider[Any]]] | type[VectorStoreProvider[Any]]: ...
    @overload
    def get_provider_class(
        self, provider: Provider, provider_kind: Literal[ProviderKind.AGENT, "agent"]
    ) -> LazyImport[type[AgentProvider[Any]]] | type[AgentProvider[Any]]: ...
    @overload
    def get_provider_class(
        self, provider: Provider, provider_kind: LiteralDataKinds
    ) -> tuple[type[Any], ...] | tuple[LazyImport[type[Any]], ...] | None: ...
    def get_provider_class(
        self, provider: Provider, provider_kind: LiteralKinds
    ) -> (
        type[
            EmbeddingProvider[Any]
            | SparseEmbeddingProvider[Any]
            | RerankingProvider[Any]
            | VectorStoreProvider[Any]
            | AgentProvider[Any]
            | Any
        ]
        | tuple[type[Any], ...]
        | LazyImport[
            type[
                EmbeddingProvider[Any]
                | SparseEmbeddingProvider[Any]
                | RerankingProvider[Any]
                | VectorStoreProvider[Any]
                | AgentProvider[Any]
                | Any
            ]
        ]
        | tuple[LazyImport[type[Any]], ...]
    ):
        """Get a provider class by provider enum and provider kind.

        Args:
            provider: The provider enum identifier
            provider_kind: The type of provider

        Returns:
            The provider class as a lazy import (imports on access) if it's a builtin, else the class itself

        Raises:
            ConfigurationError: If provider is not registered
        """
        if self._is_any_provider_kind(provider_kind):
            registry, kind_name = self._registry_map[provider_kind]
            if provider not in registry:
                raise ConfigurationError(f"{kind_name} provider '{provider}' is not registered")
            return registry[provider]
        raise ConfigurationError(f"Invalid provider kind '{provider_kind}' specified")

    @overload
    def create_provider(
        self,
        provider: Provider,
        provider_kind: Literal[ProviderKind.EMBEDDING, "embedding"],
        **kwargs: Any,
    ) -> EmbeddingProvider[Any]: ...
    @overload
    def create_provider(
        self,
        provider: Provider,
        provider_kind: Literal[ProviderKind.SPARSE_EMBEDDING, "sparse_embedding"],
        **kwargs: Any,
    ) -> SparseEmbeddingProvider[Any]: ...
    @overload
    def create_provider(
        self,
        provider: Provider,
        provider_kind: Literal[ProviderKind.RERANKING, "reranking"],
        **kwargs: Any,
    ) -> RerankingProvider[Any]: ...
    @overload
    def create_provider(
        self, provider: Provider, provider_kind: LiteralVectorStoreKinds, **kwargs: Any
    ) -> VectorStoreProvider[Any]: ...
    @overload
    def create_provider(
        self, provider: Provider, provider_kind: Literal[ProviderKind.AGENT, "agent"], **kwargs: Any
    ) -> AgentProvider[Any]: ...
    @overload
    def create_provider(
        self, provider: Provider, provider_kind: Literal[ProviderKind.DATA, "data"], **kwargs: Any
    ) -> Any: ...
    def create_provider(
        self, provider: Provider, provider_kind: LiteralKinds, **kwargs: Any
    ) -> (
        EmbeddingProvider[Any]
        | RerankingProvider[Any]
        | VectorStoreProvider[Any]
        | AgentProvider[Any]
        | Any
    ):
        """Create a provider instance by provider enum and provider kind.

        Args:
            provider: The provider enum identifier
            provider_kind: The type of provider
            **kwargs: Provider-specific initialization arguments

        Returns:
            An initialized provider instance
        """
        provider_kind = (
            provider_kind
            if isinstance(provider_kind, ProviderKind)
            else ProviderKind.from_string(provider_kind)
        )
        retrieved_cls = None
        if self._is_literal_model_kind(provider_kind):
            retrieved_cls = self.get_provider_class(provider, provider_kind)  # type: ignore
        if self._is_literal_vector_store_kind(provider_kind):
            retrieved_cls = self.get_provider_class(provider, provider_kind)
        if self._is_literal_data_kind(provider_kind):
            retrieved_cls = self.get_provider_class(provider, provider_kind)  # type: ignore

        # 🔧 NEW: Create client instance if not provided
        if "client" not in kwargs:
            # Extract settings for client creation
            # For vector stores, settings are in "config" key (from _prepare_vector_store_kwargs)
            # For other providers, settings are in "provider_settings" key
            if self._is_literal_vector_store_kind(provider_kind):
                provider_settings = kwargs.get("config")
            else:
                provider_settings = kwargs.get("provider_settings")
            client_options = kwargs.get("client_options")

            # Create appropriate client using CLIENT_MAP
            try:
                client = self._create_client_from_map(
                    provider, provider_kind, provider_settings, client_options
                )
                if client is not None:
                    kwargs["client"] = client
                    logger.debug(
                        "Created client for %s provider (kind: %s)", provider, provider_kind
                    )
                else:
                    # Client creation returned None - provider may not need a client or is misconfigured
                    logger.debug(
                        "No client created for %s provider (kind: %s) - provider may handle client internally",
                        provider,
                        provider_kind,
                    )
            except Exception as e:
                logger.warning(
                    "Client creation failed for %s provider (kind: %s): %s. Provider may handle client internally.",
                    provider,
                    provider_kind,
                    e,
                )

        # Clean up kwargs before passing to provider constructor
        # Remove provider_settings and client_options as they're only used for client creation
        kwargs_for_provider = {
            k: v for k, v in kwargs.items() if k not in ("provider_settings", "client_options")
        }

        # Note: We don't validate client presence here because:
        # 1. Client creation failure is already logged as a warning above
        # 2. The provider class will fail naturally if it needs a client but doesn't have one
        # 3. Some providers may not need a client at all
        # 4. Client creation can fail for valid reasons (missing API keys, optional deps not installed)
        #    but the provider is still "configured" - the error should happen on first use, not here

        # However, for model providers that require a client, we should fail early with a clear message
        # if client creation was attempted but failed (rather than letting __init__ fail with TypeError)
        if (
            self._is_literal_model_kind(provider_kind)
            and "caps" in kwargs_for_provider
            and "client" not in kwargs_for_provider
        ):
            # Client was supposed to be created (caps present) but wasn't (client missing)
            # This means client creation failed, so we can't instantiate the provider
            raise ConfigurationError(
                f"Provider '{provider}' (kind: {provider_kind}) requires a client, but client creation failed. "
                f"Check the warning messages above for details on why client creation failed."
            )

        # Special handling for embedding provider (has different logic)
        if (
            provider_kind in (ProviderKind.EMBEDDING, "embedding")
            and self._is_any_provider_kind(provider_kind)
            and retrieved_cls is not None
            and not isinstance(retrieved_cls, tuple)
        ):
            return self._build_embedding_provider(
                provider, provider_kind, retrieved_cls, kwargs_for_provider
            )
        # Standard handling for other providers
        # Handle None case
        if retrieved_cls is None:
            raise ConfigurationError(
                f"Provider '{provider}' of kind '{provider_kind}' is not registered"
            )

        # Handle tuple types (data providers return tuples)
        if isinstance(retrieved_cls, tuple):
            # For data providers, we need different instantiation logic
            # This should be handled by caller or needs special logic here
            raise ConfigurationError(
                f"Provider '{provider}' of kind '{provider_kind}' returned tuple type - use appropriate getter"
            )

        if isinstance(retrieved_cls, LazyImport):
            resolved_cls = retrieved_cls._resolve()
            return resolved_cls(**kwargs_for_provider)

        return retrieved_cls(**kwargs_for_provider)

    def _build_embedding_provider(
        self,
        provider: Provider,
        provider_kind: LiteralProviderKind,
        retrieved_cls: EmbeddingProvider[Any] | LazyImport[EmbeddingProvider[Any]],
        kwargs_for_provider: Any,
    ):
        # Check if this is an OpenAI factory that needs construction
        if self._is_openai_factory(provider, provider_kind):
            retrieved_cls = self._construct_openai_provider_class(
                provider, retrieved_cls, **kwargs_for_provider
            )
        was_lazy = False
        # Resolve LazyImport if needed before accessing __name__
        if isinstance(retrieved_cls, LazyImport):
            was_lazy = True
            retrieved_cls = retrieved_cls._resolve()

        # we need to access a property to execute the import and ensure it exists
        name = None
        with contextlib.suppress(ImportError, AttributeError):
            name = retrieved_cls.__name__
        if not name:
            logger.warning("Embedding provider '%s' could not be imported.", provider)
            raise ConfigurationError(
                f"We were unable to import the class for provider '{provider}'.",
                details={
                    "provider": provider,
                    "retrieved_cls": retrieved_cls,
                    "lazy_class_import": was_lazy,
                },
                suggestions=[
                    "Ensure the required package for this provider is installed.",
                    "Check for typos in provider registration.",
                ],
            )
        return cast(EmbeddingProvider[Any], retrieved_cls(**kwargs_for_provider))  # ty: ignore[call-non-callable]  # I promise it is

    @overload
    def get_provider_instance(
        self,
        provider: Provider,
        provider_kind: Literal[ProviderKind.EMBEDDING, "embedding"],
        *,
        singleton: bool = False,
        **kwargs: Any,
    ) -> EmbeddingProvider[Any]: ...
    @overload
    def get_provider_instance(
        self,
        provider: Provider,
        provider_kind: Literal[ProviderKind.SPARSE_EMBEDDING, "sparse_embedding"],
        *,
        singleton: bool = False,
        **kwargs: Any,
    ) -> SparseEmbeddingProvider[Any]: ...
    @overload
    def get_provider_instance(
        self,
        provider: Provider,
        provider_kind: Literal[ProviderKind.RERANKING, "reranking"],
        *,
        singleton: bool = False,
        **kwargs: Any,
    ) -> RerankingProvider[Any]: ...
    @overload
    def get_provider_instance(
        self,
        provider: Provider,
        provider_kind: LiteralVectorStoreKinds,
        *,
        singleton: bool = False,
        **kwargs: Any,
    ) -> VectorStoreProvider[Any]: ...
    @overload
    def get_provider_instance(
        self,
        provider: Provider,
        provider_kind: Literal[ProviderKind.AGENT, "agent"],
        *,
        singleton: bool = False,
        **kwargs: Any,
    ) -> AgentProvider[Any]: ...

    @overload
    def get_provider_instance(
        self,
        provider: Provider,
        provider_kind: LiteralDataKinds,
        *,
        singleton: bool = False,
        **kwargs: Any,
    ) -> Any: ...

    def get_provider_instance(
        self,
        provider: Provider,
        provider_kind: LiteralKinds,
        *,
        singleton: bool = False,
        **kwargs: Any,
    ) -> (
        EmbeddingProvider[Any]
        | RerankingProvider[Any]
        | VectorStoreProvider[Any]
        | AgentProvider[Any]
        | Any
    ):
        """Get a provider instance by provider enum and provider kind, optionally cached.

        Args:
            provider: The provider enum identifier
            provider_kind: The type of provider
            singleton: Whether to cache and reuse the instance
            **kwargs: Provider-specific initialization arguments (override config)

        Returns:
            A provider instance
        """
        provider_kind = (
            provider_kind
            if isinstance(provider_kind, ProviderKind)
            else ProviderKind.from_string(provider_kind)
        )
        # Get instance cache for this provider kind
        instance_cache = self._get_instance_cache_for_kind(provider_kind)

        # Check singleton cache first
        if singleton and provider in instance_cache:
            return instance_cache[provider]

        # Get configuration for this provider
        config = self.get_configured_provider_settings(provider_kind)  # type: ignore
        if not config:
            logger.warning(
                "No configuration found for provider '%s' of kind '%s'", provider, provider_kind
            )

        # Prepare constructor kwargs from config
        constructor_kwargs = self._prepare_constructor_kwargs(provider_kind, config, **kwargs)

        # Create the instance with proper type narrowing
        if provider_kind != ProviderKind.UNSET and (
            self._is_literal_embedding_kind(provider_kind)
            or self._is_literal_sparse_embedding_kind(provider_kind)
            or self._is_literal_reranking_kind(provider_kind)
            or self._is_literal_vector_store_kind(provider_kind)
            or self._is_literal_agent_kind(provider_kind)
            or self._is_literal_data_kind(provider_kind)
        ):
            instance = self.create_provider(provider, provider_kind, **constructor_kwargs)
        else:
            raise ConfigurationError(f"Invalid provider kind '{provider_kind}' specified")

        # Cache if singleton
        if singleton:
            instance_cache[provider] = instance

        return instance

    def _get_instance_cache_for_kind(
        self, provider_kind: LiteralKinds
    ) -> MutableMapping[Provider, Any]:
        """Get the instance cache for a specific provider kind.

        Args:
            provider_kind: The type of provider

        Returns:
            The appropriate instance cache dictionary
        """
        if provider_kind == ProviderKind.UNSET:
            return {}
        if self._is_literal_embedding_kind(provider_kind):
            return self._embedding_instances
        if self._is_literal_sparse_embedding_kind(provider_kind):
            return self._sparse_embedding_instances
        if self._is_literal_reranking_kind(provider_kind):
            return self._reranking_instances
        if self._is_literal_vector_store_kind(provider_kind):
            return self._vector_store_instances
        if self._is_literal_agent_kind(provider_kind):
            return self._agent_instances
        if self._is_literal_data_kind(provider_kind):
            return self._data_instances
        # Fallback - create empty dict (should not reach here with type guards)
        return {}

    def _prepare_constructor_kwargs(
        self,
        provider_kind: LiteralKinds,
        config: (
            DictView[EmbeddingProviderSettings]
            | DictView[SparseEmbeddingProviderSettings]
            | DictView[RerankingProviderSettings]
            | DictView[VectorStoreProviderSettings]
            | DictView[AgentProviderSettings]
            | DictView[DataProviderSettings]
            | tuple[DictView[DataProviderSettings], ...]
            | None
        ),
        **user_kwargs: Any,
    ) -> dict[str, Any]:
        """Prepare constructor kwargs from config and user overrides.

        Args:
            provider_kind: The type of provider
            config: Provider configuration
            **user_kwargs: User-provided kwargs that override config

        Returns:
            Complete kwargs dictionary for provider constructor
        """
        provider_kind = (
            provider_kind
            if isinstance(provider_kind, ProviderKind)
            else ProviderKind.from_string(provider_kind)
        )
        if self._is_literal_model_kind(provider_kind):
            return self._prepare_model_provider_kwargs(config, **user_kwargs)  # type: ignore
        if self._is_literal_vector_store_kind(provider_kind):
            return self._prepare_vector_store_kwargs(config, **user_kwargs)  # type: ignore
        if self._is_literal_data_kind(provider_kind):
            return self._prepare_data_provider_kwargs(config, **user_kwargs)  # type: ignore
        return user_kwargs

    def _prepare_model_provider_kwargs(
        self,
        config: (
            DictView[EmbeddingProviderSettings]
            | DictView[SparseEmbeddingProviderSettings]
            | DictView[RerankingProviderSettings]
            | DictView[AgentProviderSettings]
            | None
        ),
        **user_kwargs: Any,
    ) -> dict[str, Any]:
        """Prepare kwargs for model providers (embedding, sparse, reranking, agent).

        Args:
            config: Model provider configuration
            **user_kwargs: User-provided kwargs

        Returns:
            Complete kwargs with caps, model settings, and provider settings
        """
        if not config:
            return user_kwargs

        kwargs: dict[str, Any] = {}

        # Extract model settings
        self._add_model_settings_to_kwargs(config, kwargs, user_kwargs)

        # Extract provider settings and merge into client_options
        self._add_provider_settings_to_kwargs(config, kwargs)

        # User kwargs override everything
        kwargs |= user_kwargs
        return kwargs

    def _add_model_settings_to_kwargs(
        self, config: DictView[Any], kwargs: dict[str, Any], user_kwargs: dict[str, Any]
    ) -> None:
        """Add model settings to kwargs."""
        model_settings = config.get("model_settings")
        if not model_settings:
            return

        if (model_name := user_kwargs.get("model") or model_settings.get("model")) and (
            caps := self._get_capabilities_for_model(model_name, config["provider"])
        ):
            kwargs["caps"] = caps

        # Collect model-specific settings into nested kwargs dict
        # These will be passed as the 'kwargs' parameter to EmbeddingProvider.__init__
        provider_kwargs: dict[str, Any] = {}
        for key in ("dimension", "data_type", "custom_prompt", "embed_options", "model_options"):
            if value := model_settings.get(key):
                provider_kwargs[key] = value

        # Always set kwargs parameter (required by EmbeddingProvider.__init__)
        # Pass empty dict if no settings, as the parameter doesn't have a default
        kwargs["kwargs"] = provider_kwargs or {}

    def _add_provider_settings_to_kwargs(
        self, config: DictView[Any], kwargs: dict[str, Any]
    ) -> None:
        """Add provider-specific settings to client_options in kwargs."""
        provider_settings = config.get("provider_settings")
        if not provider_settings:
            return

        client_options = kwargs.get("client_options", {})

        # AWS settings (Bedrock)
        for key in (
            "region_name",
            "model_arn",
            "aws_access_key_id",
            "aws_secret_access_key",
            "aws_session_token",
        ):
            if value := provider_settings.get(key):
                client_options[key] = value

        # Azure settings
        for key in ("model_deployment", "api_key", "azure_resource_name"):
            if value := provider_settings.get(key):
                client_options[key] = value

        # Fastembed settings
        for key in ("cache_dir", "threads"):
            if value := provider_settings.get(key):
                client_options[key] = value
            elif key == "cache_dir":
                # Set default cache_dir to persistent location
                from codeweaver.common.utils.utils import get_user_config_dir

                models_cache = get_user_config_dir() / ".models"
                models_cache.mkdir(parents=True, exist_ok=True)
                client_options["cache_dir"] = str(models_cache)

        if client_options:
            kwargs["client_options"] = client_options

    def _prepare_vector_store_kwargs(
        self, config: DictView[VectorStoreProviderSettings] | None, **user_kwargs: Any
    ) -> dict[str, Any]:
        """Prepare kwargs for vector store providers.

        Args:
            config: Vector store provider configuration
            **user_kwargs: User-provided kwargs

        Returns:
            Complete kwargs with config parameter
        """
        if not config:
            return user_kwargs

        kwargs: dict[str, Any] = {}

        if provider_settings := config.get("provider_settings"):
            # Start with provider_settings (QdrantConfig/MemoryConfig)
            merged_config = dict(provider_settings)

            # Merge in root-level api_key if not already in provider_settings
            if config.get("api_key") and not merged_config.get("api_key"):
                merged_config["api_key"] = config["api_key"]

            # Merge in root-level client_options
            if root_client_options := config.get("client_options"):
                existing_client_options = merged_config.get("client_options", {})
                merged_config["client_options"] = root_client_options | existing_client_options

            kwargs["config"] = merged_config

        # User kwargs override
        kwargs |= user_kwargs
        return kwargs

    def _prepare_data_provider_kwargs(
        self,
        config: DictView[DataProviderSettings] | tuple[DictView[DataProviderSettings], ...] | None,
        **user_kwargs: Any,
    ) -> dict[str, Any]:
        """Prepare kwargs for data providers.

        Args:
            config: Data provider configuration
            **user_kwargs: User-provided kwargs

        Returns:
            User kwargs (data providers are simple pass-through)
        """
        # Data providers typically don't need complex configuration
        # Just pass through user kwargs
        return user_kwargs

    def _normalize_model_name(self, name: str) -> str:
        """Normalize model name for fuzzy matching.

        Handles common variations like hyphens vs underscores.

        Args:
            name: Original model name

        Returns:
            Normalized model name (lowercased with normalized separators)
        """
        return name.lower().replace("-", "_").replace(" ", "_")

    def _get_capabilities_for_model(
        self, model_name: str, provider: Provider
    ) -> SparseEmbeddingModelCapabilities | EmbeddingModelCapabilities | None:
        """Get capabilities for a specific model.

        Capabilities are a convenience for validation and optimization, not a requirement.
        If no capability is found, the model will still be passed to the provider.

        Args:
            model_name: The model name to look up
            provider: The provider for the model

        Returns:
            EmbeddingModelCapabilities if found, None otherwise (which is OK!)
        """
        from codeweaver.providers.embedding.capabilities import load_default_capabilities

        # Try exact match first
        for cap in load_default_capabilities():
            if cap.name == model_name and cap.provider == provider:
                return cap

        # Try sparse capabilities for SENTENCE_TRANSFORMERS/FASTEMBED
        if provider.name in ("SENTENCE_TRANSFORMERS", "FASTEMBED"):
            from codeweaver.providers.embedding.capabilities.base import get_sparse_caps

            sparse_caps = get_sparse_caps()
            for cap in sparse_caps:
                if model_name == cap.name and cap.provider == provider:
                    return cap

        # Try fuzzy matching (handles hyphens vs underscores, case differences)
        normalized_model_name = self._normalize_model_name(model_name)

        for cap in load_default_capabilities():
            if (
                self._normalize_model_name(cap.name) == normalized_model_name
                and cap.provider == provider
            ):
                logger.debug(
                    "Found capability via fuzzy match: '%s' matched '%s' for provider '%s'",
                    model_name,
                    cap.name,
                    provider,
                )
                return cap

        if provider.name in ("SENTENCE_TRANSFORMERS", "FASTEMBED"):
            from codeweaver.providers.embedding.capabilities.base import get_sparse_caps

            sparse_caps = get_sparse_caps()
            for cap in sparse_caps:
                if (
                    self._normalize_model_name(cap.name) == normalized_model_name
                    and cap.provider == provider
                ):
                    logger.debug(
                        "Found sparse capability via fuzzy match: '%s' matched '%s' for provider '%s'",
                        model_name,
                        cap.name,
                        provider,
                    )
                    return cap

        # No capability found - that's OK! Provider will validate the model name.
        # Capabilities are a convenience, not a requirement.
        logger.debug(
            "No capability found for model '%s' and provider '%s'. Provider will validate model name.",
            model_name,
            provider,
        )
        return None

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
        """Check if a provider package is available (can be imported).

        Args:
            provider: The provider to check
            provider_kind: The type of provider to check
        """
        # Get the appropriate provider dictionary based on kind
        provider_kind_name = f"_{provider_kind.name.lower()}_providers"
        provider_info = getattr(self, provider_kind_name, None)

        if provider_info is None or provider not in provider_info:
            return False

        provider_class = provider_info[provider]

        # If it's not a LazyImport, it's already available
        if not isinstance(provider_class, LazyImport):
            return True

        # Try to resolve the LazyImport
        try:
            resolved = provider_class._resolve()
        except Exception as e:
            # Log the actual error for debugging
            import logging

            logger = logging.getLogger(__name__)
            logger.debug(
                "Failed to resolve %s provider %s: %s",
                provider_kind.name,
                provider.value,
                e.__class__.__name__,
                exc_info=True,
            )
            return False
        else:
            # Check if it resolved to a real class (not still a LazyImport)
            is_available = not isinstance(resolved, LazyImport) and resolved is not None
            if not is_available:
                import logging

                logger = logging.getLogger(__name__)
                logger.debug(
                    "Provider %s resolved but not available: resolved=%s, is_lazy=%s",
                    provider.as_title,
                    type(resolved).__name__,
                    str(isinstance(resolved, LazyImport)),
                )
            return is_available

    def is_provider_available(self, provider: Provider, provider_kind: ProviderKind) -> bool:
        """Check if a provider is available for a given provider kind.

        Args:
            provider: The provider to check
            provider_kind: The type of provider to check

        Returns:
            True if the provider is available
        """
        if provider_kind not in (
            ProviderKind.EMBEDDING,
            ProviderKind.SPARSE_EMBEDDING,
            ProviderKind.RERANKING,
            ProviderKind.VECTOR_STORE,
            ProviderKind.AGENT,
            ProviderKind.DATA,
        ) or provider not in self.list_providers(provider_kind):
            return False
        return self._check_for_provider_availability(provider, provider_kind)

    @overload
    def get_configured_provider_settings(
        self, provider_kind: LiteralDataKinds
    ) -> tuple[DictView[DataProviderSettings], ...]: ...
    @overload
    def get_configured_provider_settings(
        self, provider_kind: Literal[ProviderKind.EMBEDDING, "embedding"]
    ) -> DictView[EmbeddingProviderSettings]: ...
    @overload
    def get_configured_provider_settings(
        self, provider_kind: Literal[ProviderKind.SPARSE_EMBEDDING, "sparse_embedding"]
    ) -> DictView[SparseEmbeddingProviderSettings]: ...
    @overload
    def get_configured_provider_settings(
        self, provider_kind: Literal[ProviderKind.RERANKING, "reranking"]
    ) -> DictView[RerankingProviderSettings]: ...

    @overload
    def get_configured_provider_settings(
        self, provider_kind: LiteralVectorStoreKinds
    ) -> DictView[VectorStoreProviderSettings]: ...

    @overload
    def get_configured_provider_settings(
        self, provider_kind: Literal[ProviderKind.AGENT, "agent"]
    ) -> DictView[AgentProviderSettings]: ...

    def get_configured_provider_settings(
        self, provider_kind: LiteralKinds
    ) -> (
        DictView[DataProviderSettings]
        | DictView[EmbeddingProviderSettings]
        | DictView[SparseEmbeddingProviderSettings]
        | DictView[RerankingProviderSettings]
        | DictView[VectorStoreProviderSettings]
        | DictView[AgentProviderSettings]
        | tuple[DictView[DataProviderSettings], ...]
        | None
    ):
        """Get a list of providers that have been configured in settings for a given provider kind.

        Args:
            provider_kind: The type of provider to check
        Returns:
            List of configured providers
        """
        from codeweaver.common.registry.utils import (
            get_data_configs,
            get_model_config,
            get_vector_store_config,
        )

        provider_kind = (
            provider_kind
            if isinstance(provider_kind, ProviderKind)
            else ProviderKind.from_string(provider_kind)
        )  # type: ignore
        if provider_kind == ProviderKind.DATA:
            configs = get_data_configs()
            return tuple(
                cfg
                for cfg in configs
                if self.is_provider_available(cfg["provider"], ProviderKind.DATA)
            )
        if provider_kind == ProviderKind.VECTOR_STORE:
            return (
                cfg
                if (cfg := get_vector_store_config())
                and self.is_provider_available(cfg["provider"], ProviderKind.VECTOR_STORE)
                else None
            )
        if provider_kind not in (
            ProviderKind.EMBEDDING,
            ProviderKind.SPARSE_EMBEDDING,
            ProviderKind.RERANKING,
            ProviderKind.AGENT,
        ):
            raise ValueError("We didn't recognize that provider kind, %s.", provider_kind)
        # Type is now narrowed to valid get_model_config kinds
        return (
            cfg
            if (cfg := get_model_config(provider_kind))  # type: ignore
            and self.is_provider_available(cfg["provider"], provider_kind)  # type: ignore
            else None
        )  # type: ignore

    @overload
    def get_provider_enum_for(self, kind: LiteralDataKinds) -> tuple[Provider, ...] | None: ...
    @overload
    def get_provider_enum_for(
        self, kind: LiteralModelKinds | LiteralVectorStoreKinds
    ) -> Provider | None: ...
    def get_provider_enum_for(
        self, kind: LiteralModelKinds | LiteralVectorStoreKinds | LiteralDataKinds
    ) -> Provider | tuple[Provider, ...] | None:
        """Get the provider enum for a given provider kind."""
        if kind in (ProviderKind.DATA, "data"):
            configs = self.get_configured_provider_settings(
                cast(Literal[ProviderKind.DATA, "data"], kind)
            )
            return tuple(cfg["provider"] for cfg in configs if cfg["provider"])
        if config := self.get_configured_provider_settings(kind):  # type: ignore
            return config["provider"]  # type: ignore
        return None

    def clear_instances(self) -> None:
        """Clear all cached provider instances."""
        self._embedding_instances.clear()
        self._vector_store_instances.clear()
        self._reranking_instances.clear()
        self._sparse_embedding_instances.clear()
        self._agent_instances.clear()
        self._data_instances.clear()


_provider_registry: ProviderRegistry | None = None


def get_provider_registry() -> ProviderRegistry:
    """Get the global provider registry instance.

    Returns:
        The global ProviderRegistry instance
    """
    global _provider_registry
    if _provider_registry is None:
        _provider_registry = ProviderRegistry()
    return _provider_registry


@overload
def get_provider_config_for(
    kind: Literal[ProviderKind.EMBEDDING, "embedding"],
) -> DictView[EmbeddingProviderSettings]: ...
@overload
def get_provider_config_for(
    kind: Literal[ProviderKind.SPARSE_EMBEDDING, "sparse_embedding"],
) -> DictView[SparseEmbeddingProviderSettings]: ...
@overload
def get_provider_config_for(
    kind: Literal[ProviderKind.RERANKING, "reranking"],
) -> DictView[RerankingProviderSettings]: ...
@overload
def get_provider_config_for(
    kind: LiteralVectorStoreKinds,
) -> DictView[VectorStoreProviderSettings]: ...
@overload
def get_provider_config_for(
    kind: Literal[ProviderKind.AGENT, "agent"],
) -> DictView[AgentProviderSettings]: ...
@overload
def get_provider_config_for(
    kind: LiteralDataKinds,
) -> tuple[DictView[DataProviderSettings], ...]: ...
def get_provider_config_for(
    kind: LiteralKinds,
) -> (
    DictView[EmbeddingProviderSettings]
    | DictView[SparseEmbeddingProviderSettings]
    | DictView[RerankingProviderSettings]
    | DictView[VectorStoreProviderSettings]
    | DictView[AgentProviderSettings]
    | tuple[DictView[DataProviderSettings], ...]
    | None
):
    """Get the provider configuration for a given provider kind.

    Args:
        kind: The type of provider to get configuration for

    Returns:
        The provider configuration dictionary view
    """
    registry = get_provider_registry()
    return registry.get_configured_provider_settings(kind)  # type: ignore


__all__ = (
    "Provider",
    "ProviderKind",
    "ProviderRegistry",
    "get_provider_config_for",
    "get_provider_registry",
)
