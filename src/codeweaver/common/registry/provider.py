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

from collections.abc import Mapping, MutableMapping
from functools import partial
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, ClassVar, Literal, cast, overload

from pydantic import ConfigDict
from textcase import pascal

from codeweaver.common.utils.lazy_importer import LazyImport, lazy_import
from codeweaver.config.types import CodeWeaverSettingsDict
from codeweaver.core.types.aliases import LiteralStringT
from codeweaver.core.types.dictview import DictView
from codeweaver.core.types.models import BasedModel
from codeweaver.exceptions import ConfigurationError
from codeweaver.providers.agent.agent_providers import AgentProvider
from codeweaver.providers.embedding.providers.base import EmbeddingProvider
from codeweaver.providers.provider import Provider, ProviderKind
from codeweaver.providers.reranking.providers.base import RerankingProvider
from codeweaver.providers.vector_stores.base import VectorStoreProvider


if TYPE_CHECKING:
    from codeweaver.config.providers import (
        AgentProviderSettings,
        DataProviderSettings,
        EmbeddingProviderSettings,
        RerankingProviderSettings,
        VectorStoreProviderSettings,
    )


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
        MappingProxyType[
            ProviderKind,
            Mapping[
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

    @property
    def _registry_map(
        self,
    ) -> dict[
        ProviderKind | str,
        tuple[
            MutableMapping[
                Provider,
                LazyImport[type[EmbeddingProvider[Any]]]
                | type[EmbeddingProvider[Any]]
                | LazyImport[type[RerankingProvider[Any]]]
                | type[RerankingProvider[Any]]
                | LazyImport[type[VectorStoreProvider[Any]]]
                | type[VectorStoreProvider[Any]]
                | LazyImport[type[Any]]
                | type[Any],
            ],
            str,
        ],
    ]:
        """Get the registry map for provider classes."""
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
        }

    @property
    def _instances_map(
        self,
    ) -> dict[
        ProviderKind | str,
        MutableMapping[
            Provider,
            EmbeddingProvider[Any]
            | RerankingProvider[Any]
            | VectorStoreProvider[Any]
            | AgentProvider[Any]
            | Any,
        ],
    ]:
        """Get the instances map for cached provider instances."""
        return {
            ProviderKind.EMBEDDING: self._embedding_instances,
            "embedding": self._embedding_instances,
            ProviderKind.SPARSE_EMBEDDING: self._sparse_embedding_instances,
            "sparse_embedding": self._sparse_embedding_instances,
            ProviderKind.RERANKING: self._reranking_instances,
            "reranking": self._reranking_instances,
            ProviderKind.VECTOR_STORE: self._vector_store_instances,
            "vector_store": self._vector_store_instances,
            ProviderKind.AGENT: self._agent_instances,
            "agent": self._agent_instances,
            ProviderKind.DATA: self._data_instances,
            "data": self._data_instances,
        }

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
        return f"{pascal(str(provider))}EmbeddingProvider"

    def _register_azure_exception_providers(self, provider: Provider) -> None:
        """Register Azure exception providers."""
        module_name = f"{self._embedding_prefix}openai_factory"
        class_name = f"{pascal(str(provider))}OpenAIEmbeddingBase"
        self.register_embedding_provider(provider, LazyImport(module_name, class_name))

        module_name = f"{self._embedding_prefix}cohere"
        self.register_embedding_provider(
            provider, LazyImport(module_name, "CohereEmbeddingProvider")
        )

    def _register_reranking_provider_from_module(
        self, provider: Provider, module: partial[LazyImport[type[RerankingProvider[Any]]]]
    ) -> None:
        """Register a reranking provider from a module."""
        provider_name = f"{pascal(str(provider))}RerankingProvider"
        self.register_reranking_provider(provider, module(provider_name))

    def _register_vector_store_provider_from_module(
        self, provider: Provider, module: partial[LazyImport[type[VectorStoreProvider[Any]]]]
    ) -> None:
        """Register a vector store provider from a module."""
        provider_name = f"{pascal(str(provider))}VectorStoreProvider"
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

    @overload
    def get_provider_class(
        self, provider: Provider, provider_kind: Literal[ProviderKind.EMBEDDING, "embedding"]
    ) -> LazyImport[type[EmbeddingProvider[Any]]] | type[EmbeddingProvider[Any]]: ...

    @overload
    def get_provider_class(
        self,
        provider: Provider,
        provider_kind: Literal[ProviderKind.SPARSE_EMBEDDING, "sparse_embedding"],
    ) -> LazyImport[type[EmbeddingProvider[Any]]] | type[EmbeddingProvider[Any]]: ...

    @overload
    def get_provider_class(
        self, provider: Provider, provider_kind: Literal[ProviderKind.RERANKING, "reranking"]
    ) -> LazyImport[type[RerankingProvider[Any]]] | type[RerankingProvider[Any]]: ...

    @overload
    def get_provider_class(
        self, provider: Provider, provider_kind: Literal[ProviderKind.VECTOR_STORE, "vector_store"]
    ) -> LazyImport[type[VectorStoreProvider[Any]]] | type[VectorStoreProvider[Any]]: ...

    @overload
    def get_provider_class(
        self, provider: Provider, provider_kind: Literal[ProviderKind.AGENT, "agent"]
    ) -> LazyImport[type[AgentProvider[Any]]] | type[AgentProvider[Any]]: ...

    @overload
    def get_provider_class(
        self, provider: Provider, provider_kind: Literal[ProviderKind.DATA, "data"]
    ) -> LazyImport[type[Any]] | type[Any]: ...

    def get_provider_class(
        self,
        provider: Provider,
        provider_kind: Literal[
            ProviderKind.AGENT,
            "agent",
            ProviderKind.DATA,
            "data",
            ProviderKind.EMBEDDING,
            "embedding",
            ProviderKind.SPARSE_EMBEDDING,
            "sparse_embedding",
            ProviderKind.RERANKING,
            "reranking",
            ProviderKind.VECTOR_STORE,
            "vector_store",
        ],
    ) -> (
        LazyImport[type[EmbeddingProvider[Any]]]
        | type[EmbeddingProvider[Any]]
        | LazyImport[type[RerankingProvider[Any]]]
        | type[RerankingProvider[Any]]
        | LazyImport[type[VectorStoreProvider[Any]]]
        | type[VectorStoreProvider[Any]]
        | LazyImport[type[AgentProvider[Any]]]
        | type[AgentProvider[Any]]
        | LazyImport[type[Any]]
        | type[Any]
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
        registry, kind_name = self._registry_map[provider_kind]
        if provider not in registry:
            raise ConfigurationError(f"{kind_name} provider '{provider}' is not registered")

        return registry[provider]

    # Maintain backward compatibility with individual methods
    def get_embedding_provider_class(
        self, provider: Provider
    ) -> LazyImport[type[EmbeddingProvider[Any]]] | type[EmbeddingProvider[Any]]:
        """Get an embedding provider class by provider enum."""
        return self.get_provider_class(provider, ProviderKind.EMBEDDING)

    def get_sparse_embedding_provider_class(
        self, provider: Provider
    ) -> LazyImport[type[EmbeddingProvider[Any]]] | type[EmbeddingProvider[Any]]:
        """Get a sparse embedding provider class by provider enum."""
        return self.get_provider_class(provider, ProviderKind.SPARSE_EMBEDDING)

    def get_reranking_provider_class(
        self, provider: Provider
    ) -> LazyImport[type[RerankingProvider[Any]]] | type[RerankingProvider[Any]]:
        """Get a reranking provider class by provider enum."""
        return self.get_provider_class(provider, ProviderKind.RERANKING)

    def get_vector_store_provider_class(
        self, provider: Provider
    ) -> LazyImport[type[VectorStoreProvider[Any]]] | type[VectorStoreProvider[Any]]:
        """Get a vector store provider class by provider enum."""
        return self.get_provider_class(provider, ProviderKind.VECTOR_STORE)

    def get_agent_provider_class(
        self, provider: Provider
    ) -> LazyImport[type[AgentProvider[Any]]] | type[AgentProvider[Any]]:
        """Get an agent provider class by provider enum."""
        return self.get_provider_class(provider, ProviderKind.AGENT)

    def get_data_provider_class(self, provider: Provider) -> LazyImport[type[Any]] | type[Any]:
        """Get a data provider class by provider enum."""
        return self.get_provider_class(provider, ProviderKind.DATA)

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
    ) -> EmbeddingProvider[Any]: ...

    @overload
    def create_provider(
        self,
        provider: Provider,
        provider_kind: Literal[ProviderKind.RERANKING, "reranking"],
        **kwargs: Any,
    ) -> RerankingProvider[Any]: ...

    @overload
    def create_provider(
        self,
        provider: Provider,
        provider_kind: Literal[ProviderKind.VECTOR_STORE, "vector_store"],
        **kwargs: Any,
    ) -> VectorStoreProvider[Any]: ...

    @overload
    def create_provider(
        self,
        provider: Provider,
        provider_kind: Literal[ProviderKind.AGENT, "agent"],
        **kwargs: Any,
    ) -> AgentProvider[Any]: ...

    @overload
    def create_provider(
        self, provider: Provider, provider_kind: Literal[ProviderKind.DATA, "data"], **kwargs: Any
    ) -> Any: ...

    def create_provider(
        self,
        provider: Provider,
        provider_kind: Literal[
            ProviderKind.AGENT,
            "agent",
            ProviderKind.DATA,
            "data",
            ProviderKind.EMBEDDING,
            "embedding",
            ProviderKind.SPARSE_EMBEDDING,
            "sparse_embedding",
            ProviderKind.RERANKING,
            "reranking",
            ProviderKind.VECTOR_STORE,
            "vector_store",
        ],
        **kwargs: Any,
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
        retrieved_cls = self.get_provider_class(provider, provider_kind)

        # Special handling for embedding provider (has different logic)
        if provider_kind in (ProviderKind.EMBEDDING, "embedding"):
            # we need to access a property to execute the import and ensure it exists
            name = None
            with contextlib.suppress(Exception):
                name = retrieved_cls.__name__
            if not name:
                logger.warning("Embedding provider '%s' could not be imported.", provider)
                raise ConfigurationError(f"Embedding provider '{provider}' could not be imported.")
            return cast(EmbeddingProvider[Any], retrieved_cls(**kwargs))

        # Standard handling for other providers
        if isinstance(retrieved_cls, LazyImport):
            return self._create_provider(provider, retrieved_cls, **kwargs)
        return retrieved_cls(**kwargs)

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

    # Maintain backward compatibility with individual methods
    def create_embedding_provider(
        self, provider: Provider, **kwargs: Any
    ) -> EmbeddingProvider[Any]:
        """Create an embedding provider instance."""
        return self.create_provider(provider, ProviderKind.EMBEDDING, **kwargs)

    def create_sparse_embedding_provider(
        self, provider: Provider, **kwargs: Any
    ) -> EmbeddingProvider[Any]:
        """Create a sparse embedding provider instance."""
        return self.create_provider(provider, ProviderKind.SPARSE_EMBEDDING, **kwargs)

    def create_reranking_provider(
        self, provider: Provider, **kwargs: Any
    ) -> RerankingProvider[Any]:
        """Create a reranking provider instance."""
        return self.create_provider(provider, ProviderKind.RERANKING, **kwargs)

    def create_vector_store_provider(
        self, provider: Provider, **kwargs: Any
    ) -> VectorStoreProvider[Any]:
        """Create a vector store provider instance."""
        return self.create_provider(provider, ProviderKind.VECTOR_STORE, **kwargs)

    def create_agent_provider(self, provider: Provider, **kwargs: Any) -> AgentProvider[Any]:
        """Create an agent provider instance."""
        return self.create_provider(provider, ProviderKind.AGENT, **kwargs)

    def create_data_provider(self, provider: Provider, **kwargs: Any) -> Any:
        """Create a data provider instance."""
        return self.create_provider(provider, ProviderKind.DATA, **kwargs)

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
    ) -> EmbeddingProvider[Any]: ...

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
        provider_kind: Literal[ProviderKind.VECTOR_STORE, "vector_store"],
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
        provider_kind: Literal[ProviderKind.DATA, "data"],
        *,
        singleton: bool = False,
        **kwargs: Any,
    ) -> Any: ...

    def get_provider_instance(
        self,
        provider: Provider,
        provider_kind: Literal[
            ProviderKind.AGENT,
            "agent",
            ProviderKind.DATA,
            "data",
            ProviderKind.EMBEDDING,
            "embedding",
            ProviderKind.SPARSE_EMBEDDING,
            "sparse_embedding",
            ProviderKind.RERANKING,
            "reranking",
            ProviderKind.VECTOR_STORE,
            "vector_store",
        ],
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
            **kwargs: Provider-specific initialization arguments

        Returns:
            A provider instance
        """
        instances = self._instances_map[provider_kind]

        if singleton and provider in instances:
            return instances[provider]

        instance = self.create_provider(provider, provider_kind, **kwargs)

        if singleton:
            instances[provider] = instance

        return instance

    # Maintain backward compatibility with individual methods
    def get_embedding_provider_instance(
        self, provider: Provider, *, singleton: bool = False, **kwargs: Any
    ) -> EmbeddingProvider[Any]:
        """Get an embedding provider instance, optionally cached."""
        return self.get_provider_instance(provider, ProviderKind.EMBEDDING, singleton=singleton, **kwargs)

    def get_sparse_embedding_provider_instance(
        self, provider: Provider, *, singleton: bool = False, **kwargs: Any
    ) -> EmbeddingProvider[Any]:
        """Get a sparse embedding provider instance, optionally cached."""
        return self.get_provider_instance(
            provider, ProviderKind.SPARSE_EMBEDDING, singleton=singleton, **kwargs
        )

    def get_reranking_provider_instance(
        self, provider: Provider, *, singleton: bool = False, **kwargs: Any
    ) -> RerankingProvider[Any]:
        """Get a reranking provider instance, optionally cached."""
        return self.get_provider_instance(provider, ProviderKind.RERANKING, singleton=singleton, **kwargs)

    def get_vector_store_provider_instance(
        self, provider: Provider, *, singleton: bool = False, **kwargs: Any
    ) -> VectorStoreProvider[Any]:
        """Get a vector store provider instance, optionally cached."""
        return self.get_provider_instance(
            provider, ProviderKind.VECTOR_STORE, singleton=singleton, **kwargs
        )

    def get_agent_provider_instance(
        self, provider: Provider, *, singleton: bool = False, **kwargs: Any
    ) -> AgentProvider[Any]:
        """Get an agent provider instance, optionally cached."""
        return self.get_provider_instance(provider, ProviderKind.AGENT, singleton=singleton, **kwargs)

    def get_data_provider_instance(
        self, provider: Provider, *, singleton: bool = False, **kwargs: Any
    ) -> Any:
        """Get a data provider instance, optionally cached."""
        return self.get_provider_instance(provider, ProviderKind.DATA, singleton=singleton, **kwargs)

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

    @overload
    def get_configured_provider_settings(
        self, provider_kind: Literal[ProviderKind.DATA, "data"]
    ) -> tuple[DictView[DataProviderSettings], ...]: ...
    @overload
    def get_configured_provider_settings(
        self, provider_kind: Literal[ProviderKind.EMBEDDING, "embedding"]
    ) -> DictView[EmbeddingProviderSettings]: ...

    @overload
    def get_configured_provider_settings(
        self, provider_kind: Literal[ProviderKind.RERANKING, "reranking"]
    ) -> DictView[RerankingProviderSettings]: ...
    @overload
    def get_configured_provider_settings(
        self, provider_kind: Literal[ProviderKind.VECTOR_STORE, "vector_store"]
    ) -> DictView[VectorStoreProviderSettings]: ...

    @overload
    def get_configured_provider_settings(
        self, provider_kind: Literal[ProviderKind.AGENT, "agent"]
    ) -> DictView[AgentProviderSettings]: ...

    def get_configured_provider_settings(
        self,
        provider_kind: Literal[
            ProviderKind.AGENT,
            "agent",
            ProviderKind.DATA,
            "data",
            ProviderKind.EMBEDDING,
            "embedding",
            ProviderKind.RERANKING,
            "reranking",
            ProviderKind.VECTOR_STORE,
            "vector_store",
        ],
    ) -> (
        DictView[DataProviderSettings]
        | DictView[EmbeddingProviderSettings]
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

        if provider_kind == ProviderKind.DATA:
            return get_data_configs()
        if provider_kind == ProviderKind.VECTOR_STORE:
            return get_vector_store_config()
        if provider_kind not in (
            ProviderKind.EMBEDDING,
            ProviderKind.SPARSE_EMBEDDING,
            ProviderKind.RERANKING,
            ProviderKind.AGENT,
            "agent",
            "embedding",
            "reranking",
            "sparse_embedding",
        ):
            raise ValueError("We didn't recognize that provider kind, %s.", provider_kind)
        return get_model_config(provider_kind)  # type: ignore

    def get_embedding_provider(self) -> Provider | None:
        """Get the configured embedding provider enum from settings.

        Args:
            sparse: Whether to get the sparse embedding provider

        Returns:
            The configured embedding provider enum or None
        """
        return (self.get_configured_provider_settings(ProviderKind.EMBEDDING) or {}).get("provider")

    def get_reranking_provider(self) -> Provider | None:
        """Get the configured reranking provider enum from settings.

        Returns:
            The configured reranking provider enum or None
        """
        return (self.get_configured_provider_settings(ProviderKind.RERANKING) or {}).get("provider")

    def get_vector_store_provider(self) -> Provider | None:
        """Get the default vector store provider from settings.

        Returns:
            The default vector store provider enum or None
        """
        return (self.get_configured_provider_settings(ProviderKind.VECTOR_STORE) or {}).get(
            "provider"
        )

    def get_agent_provider(self) -> Provider | None:
        """Get the default agent provider from settings.

        Returns:
            The default agent provider enum or None
        """
        return (self.get_configured_provider_settings(ProviderKind.AGENT) or {}).get("provider")

    def get_data_providers(self) -> tuple[Provider, ...] | None:
        """Get all data providers from settings.

        Returns:
            A tuple of all data provider enums
        """
        return (
            tuple(setting.get("provider") for setting in data)
            if (data := self.get_configured_provider_settings(ProviderKind.DATA))
            else None
        )

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


__all__ = ("ProviderRegistry", "get_provider_registry")
