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

from collections.abc import MutableMapping
from functools import partial
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, ClassVar, cast

from pydantic import ConfigDict
from textcase import pascal

from codeweaver.common.registry.utils import get_provider_settings
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
        VectorStoreSettings,
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
        if (retrieved_cls := self.get_sparse_embedding_provider_class(provider)) and isinstance(
            retrieved_cls, LazyImport
        ):
            return self._create_provider(provider, retrieved_cls, **kwargs)
        return retrieved_cls(**kwargs)

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
        if (retrieved_cls := self.get_reranking_provider_class(provider)) and isinstance(
            retrieved_cls, LazyImport
        ):
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
        if (retrieved_cls := self.get_vector_store_provider_class(provider)) and isinstance(
            retrieved_cls, LazyImport
        ):
            return self._create_provider(provider, retrieved_cls, **kwargs)
        return retrieved_cls(**kwargs)

    def create_agent_provider(self, provider: Provider, **kwargs: Any) -> AgentProvider[Any]:
        """Create an agent provider instance.

        Args:
            provider: The provider enum identifier
            **kwargs: Provider-specific initialization arguments

        Returns:
            An initialized provider instance
        """
        if (retrieved_cls := self.get_agent_provider_class(provider)) and isinstance(
            retrieved_cls, LazyImport
        ):
            return self._create_provider(provider, retrieved_cls, **kwargs)
        return retrieved_cls(**kwargs)

    def create_data_provider(self, provider: Provider, **kwargs: Any) -> Any:
        """Create a data provider instance.

        Args:
            provider: The provider enum identifier
            **kwargs: Provider-specific initialization arguments

        Returns:
            An initialized provider instance
        """
        if (retrieved_cls := self.get_data_provider_class(provider)) and isinstance(
            retrieved_cls, LazyImport
        ):
            return self._create_provider(provider, retrieved_cls, **kwargs)
        return retrieved_cls(**kwargs)

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
