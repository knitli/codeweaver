# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Provider enums moved to core to break circular dependencies."""

from __future__ import annotations

import contextlib
import os

from collections.abc import Generator, Iterable
from functools import cached_property
from typing import TYPE_CHECKING, Any, Literal, Self, cast

from codeweaver.core.types.enum import BaseEnum
from codeweaver.core.types.env import EnvVarInfo, ProviderEnvVars
from codeweaver.core.utils.lazy_importer import LazyImport


if TYPE_CHECKING:
    from codeweaver.core.types import (
        ProviderCategoryLiteralString,
        ProviderLiteralString,
        SDKClientLiteralString,
    )
    from codeweaver.core.types.aliases import ModelNameT
    from codeweaver.core.types.service_cards import ServiceCard


class ProviderCategory(BaseEnum):
    """Enumeration of available provider categories."""

    DATA = "data"
    EMBEDDING = "embedding"
    SPARSE_EMBEDDING = "sparse_embedding"
    RERANKING = "reranking"
    VECTOR_STORE = "vector-store"
    AGENT = "agent"
    UNSET = "unset"

    @classmethod
    def categories(cls) -> Generator[ProviderCategory]:
        """Get all categories."""
        yield from cls.members()

    @classmethod
    def _provider_cls(cls) -> type[Provider]:
        """Get the provider class for this category.

        (A little hacky but, it does the job).
        """
        return Provider

    @cached_property
    def providers(self) -> Generator[Provider]:
        """Get all providers that support this category."""
        from codeweaver.core.types.service_cards import get_providers_for_category

        if self == ProviderCategory.UNSET:
            yield from Provider
        else:
            yield from get_providers_for_category(self)


def get_default_provider_import_for_category(
    provider: Provider | ProviderLiteralString,
    category: ProviderCategory | ProviderCategoryLiteralString,
) -> LazyImport[Any] | None:
    """Get the default provider import for a given provider and category."""
    from codeweaver.core.types.service_cards import get_service_card

    provider = provider if isinstance(provider, Provider) else Provider.from_string(provider)
    category = (
        category
        if isinstance(category, ProviderCategory)
        else ProviderCategory.from_string(category)
    )
    if service_card := get_service_card(provider.variable, category.variable):
        return service_card.provider_cls
    return None


class SDKClient(BaseEnum):
    """Enumeration of available SDK clients.

    There's not a 1-to-1 match of Provider to SDKClient, because some providers
    use the same SDK client (like OpenAI, which has 10+ providers using their SDK, at least for agents).
    """

    ANTHROPIC = "anthropic"
    BEDROCK = "bedrock"
    COHERE = "cohere"
    DUCKDUCKGO = "duckduckgo"
    EXA = "exa"
    FASTEMBED = "fastembed"
    GOOGLE = "google"
    GROQ = "groq"
    HUGGINGFACE_INFERENCE = "hf_inference"
    MISTRAL = "mistral"
    OPENAI = "openai"
    PYDANTIC_GATEWAY = "gateway"
    QDRANT = "qdrant"
    SENTENCE_TRANSFORMERS = "sentence_transformers"
    TAVILY = "tavily"
    VOYAGE = "voyage"
    X_AI = "x_ai"

    @classmethod
    def for_provider_and_category(
        cls, provider: Provider, category: ProviderCategory
    ) -> Generator[SDKClient]:
        """Get the SDK clients for a given provider and category."""
        from codeweaver.core.types.service_cards import get_sdk_client

        if sdk_clients := get_sdk_client(provider, category):
            yield from (sdk_clients if isinstance(sdk_clients, tuple) else (sdk_clients,))

    @property
    def cards(self) -> Generator[ServiceCard]:
        """Get all service cards that use this SDK client."""
        from codeweaver.core.types.service_cards import get_service_cards

        yield from get_service_cards(client=self.variable)

    def card_for_provider_and_category(
        self, provider: Provider, category: ProviderCategory, model_hint: ModelNameT | None = None
    ) -> ServiceCard | None:
        """Get the service card for a given provider and category that uses this SDK client."""
        from codeweaver.core.types.service_cards import get_service_card

        return get_service_card(
            provider.variable,
            category.variable,
            client_preference=self.variable,
            model_hint=str(model_hint) if model_hint else None,
        )

    @classmethod
    def clients(cls) -> Generator[tuple[SDKClient, LazyImport[Any]]]:
        """Get all SDK clients as lazy imports."""
        from codeweaver.core.types.service_cards import get_service_cards

        cards = get_service_cards()
        yield from {
            (cls.from_string(card.client), card.client_cls)
            for card in cards
            if card.client is not None
        }

    @property
    def client(self) -> SDKClient:
        """Get a lazy import for the SDK client (not the provider class)."""
        return next(client for client, client_cls in type(self).clients() if client == self)

    def client_available(self) -> bool:
        """Check if the SDK client package is available."""

        def try_import(lazy_import: LazyImport[Any]) -> Literal[True] | None:
            try:
                _ = lazy_import._resolve()
            except ImportError:
                return None
            else:
                return True

        try:
            if isinstance(self.client, LazyImport):
                _ = self.client._resolve()
            elif isinstance(self.client, dict):
                for lazy_import in self.client.values():
                    if try_import(lazy_import):
                        return True
        except (ImportError, AttributeError, KeyError):
            return False
        else:
            return True
        return False

    @property
    def agent_provider(self) -> LazyImport[Any] | None:
        """Get the default agent provider for the SDK client."""
        return get_default_provider_import_for_category(self.as_provider(), ProviderCategory.AGENT)

    @property
    def data_provider(self) -> LazyImport[Any] | None:
        """Get the default data provider for the SDK client."""
        return get_default_provider_import_for_category(self.as_provider(), ProviderCategory.DATA)

    @property
    def embedding_provider(self) -> LazyImport[Any] | None:
        """Get the default embedding provider for the SDK client."""
        return get_default_provider_import_for_category(
            self.as_provider(), ProviderCategory.EMBEDDING
        )

    @property
    def sparse_embedding_provider(self) -> LazyImport[Any] | None:
        """Get the default sparse embedding provider for the SDK client."""
        return get_default_provider_import_for_category(
            self.as_provider(), ProviderCategory.SPARSE_EMBEDDING
        )

    @property
    def reranking_provider(self) -> LazyImport[Any] | None:
        """Get the default reranking provider for the SDK client."""
        return get_default_provider_import_for_category(
            self.as_provider(), ProviderCategory.RERANKING
        )

    @property
    def vector_store_provider(self) -> LazyImport[Any] | None:
        """Get the default vector store provider for the SDK client."""
        return get_default_provider_import_for_category(
            self.as_provider(), ProviderCategory.VECTOR_STORE
        )

    def as_provider(self) -> Provider:
        """Get the provider as a member of Provider."""
        return Provider.from_string(self.variable)

    @classmethod
    def _providers(cls) -> Generator[Provider]:
        """Get all providers that use this SDK client."""
        yield from (client.as_provider() for client in cls.members())

    @classmethod
    def _any_provider(cls) -> Provider:
        """Get a provider instance representing an SDKClient member as a provider member."""
        return next(cls._providers())

    @classmethod
    def _categories(cls) -> Generator[ProviderCategory]:
        """Get all categories that use this SDK client."""
        yield from ProviderCategory

    @classmethod
    def _any_category(cls) -> ProviderCategory:
        """Get a category instance representing an SDKClient member as a category member."""
        return next(cls._categories())


def get_categories(provider: Provider) -> tuple[ProviderCategory, ...]:
    """Get the categories of a provider."""
    from codeweaver.core.types.service_cards import get_categories

    return tuple(ProviderCategory.from_string(category) for category in get_categories(provider))


class Provider(BaseEnum):
    """Enumeration of available providers."""

    ALIBABA = "alibaba"
    ANTHROPIC = "anthropic"
    AZURE = "azure"
    BEDROCK = "bedrock"
    CEREBRAS = "cerebras"
    COHERE = "cohere"
    DEEPSEEK = "deepseek"
    DUCKDUCKGO = "duckduckgo"
    EXA = "exa"
    FASTEMBED = "fastembed"
    FIREWORKS = "fireworks"
    GITHUB = "github"
    GOOGLE = "google"
    GROQ = "groq"
    HEROKU = "heroku"
    HUGGINGFACE_INFERENCE = "hf-inference"
    LITELLM = "litellm"
    MEMORY = "memory"
    MISTRAL = "mistral"
    MOONSHOT = "moonshot"
    MORPH = "morph"
    NEBIUS = "nebius"
    NOT_SET = "not_set"
    OLLAMA = "ollama"
    OPENAI = "openai"
    OPENROUTER = "openrouter"
    OVHCLOUD = "ovhcloud"
    # OUTLINES = "outlines"  # not implemented yet
    PERPLEXITY = "perplexity"
    PYDANTIC_GATEWAY = "gateway"
    QDRANT = "qdrant"
    SAMBANOVA = "sambanova"
    SENTENCE_TRANSFORMERS = "sentence-transformers"
    TAVILY = "tavily"
    TOGETHER = "together"
    VERCEL = "vercel"
    VOYAGE = "voyage"
    X_AI = "x-ai"

    @classmethod
    def validate(cls, value: str) -> Self:
        """Validate provider-specific settings."""
        from codeweaver.core import ConfigurationError

        with contextlib.suppress(AttributeError, KeyError, ValueError):
            if value_in_self := cls.from_string(value.strip()):
                return value_in_self
        raise ConfigurationError(f"Invalid provider: {value}")

    @property
    def other_env_vars(self) -> tuple[ProviderEnvVars, ...] | None:
        """Get the environment variables used by the provider's client that are not part of CodeWeaver's settings."""
        with contextlib.suppress(ImportError):
            from codeweaver.providers.env_registry.conversion import (
                get_provider_env_vars_from_registry,
            )

            if registry_vars := get_provider_env_vars_from_registry(self.value):
                return registry_vars

        return None

    @cached_property
    def api_key_env_vars(self) -> tuple[str, ...] | None:
        """Get the environment variable names used for API keys by the provider's client that are not part of CodeWeaver's settings."""
        if envs := self.other_env_vars:
            return tuple(env["api_key"].env for env in envs if "api_key" in env)
        return None

    @property
    def always_local(self) -> bool:
        """Check if the provider is a local provider."""
        from codeweaver.core.types.service_cards import get_local_only_provider_members

        return self in get_local_only_provider_members(type(self))

    @property
    def is_local_provider(self) -> bool:
        """Check if the provider can be used as a local provider."""
        from codeweaver.core.types.service_cards import get_sometimes_local_provider_members

        return self in get_sometimes_local_provider_members(type(self)) or self.always_local

    @property
    def is_cloud_provider(self) -> bool:
        """Check if the provider is a cloud provider."""
        return not self.always_local

    @property
    def always_cloud(self) -> bool:
        """Check if the provider is always a cloud provider."""
        return not self.is_local_provider

    @property
    def is_huggingface_model_provider(self) -> bool:
        """Check if the provider is a Hugging Face model provider."""
        return self in {
            Provider.CEREBRAS,
            Provider.FASTEMBED,
            Provider.FIREWORKS,
            Provider.GROQ,
            Provider.HUGGINGFACE_INFERENCE,
            Provider.LITELLM,
            Provider.OLLAMA,
            Provider.SENTENCE_TRANSFORMERS,
            Provider.TOGETHER,
        }

    @property
    def requires_auth(self) -> bool:
        """Check if the provider requires authentication."""
        return not self.is_local_provider and self != Provider.DUCKDUCKGO

    @property
    def uses_openai_api(self) -> bool:
        """Check if the provider uses the OpenAI API."""
        from codeweaver.core.types.service_cards import get_openai_provider_members

        return self in get_openai_provider_members(type(self))

    @staticmethod
    def _flatten_envvars(env_vars: ProviderEnvVars) -> list[EnvVarInfo]:
        """Flatten a ProviderEnvVars TypedDict into a list of EnvVarInfo tuples."""
        from codeweaver.core.types.env import EnvVarInfo as EnvVarInfo

        found_vars: list[EnvVarInfo] = []
        for key, value in env_vars.items():
            if key not in ("note", "other") and isinstance(value, EnvVarInfo):
                found_vars.append(value)
            elif key == "other" and isinstance(value, dict) and value:
                found_vars.extend(iter(cast(Iterable[EnvVarInfo], value.values())))
        return found_vars

    @classmethod
    def all_envs(cls) -> tuple[tuple[Provider, EnvVarInfo], ...]:
        """Get all environment variables used by all providers."""
        found_vars: list[tuple[Provider, EnvVarInfo]] = []
        for p in cls:
            if (v := p.other_env_vars) is not None:
                # We need to handle both single ProviderEnvVars and tuple of them
                if isinstance(v, tuple):
                    for env_vars_dict in v:
                        found_vars.extend(
                            (p, var_info) for var_info in cls._flatten_envvars(env_vars_dict)
                        )
                else:
                    found_vars.extend((p, var_info) for var_info in cls._flatten_envvars(v))
        return tuple(found_vars)

    def all_envs_for_client(
        self, client: SDKClient | SDKClientLiteralString
    ) -> tuple[EnvVarInfo, ...]:
        """Get all environment variables used by this provider for a specific client."""
        found_vars: list[EnvVarInfo] = []
        if envs := self.other_env_vars:
            for env_vars_dict in envs:
                if "client" in env_vars_dict and client in env_vars_dict["client"]:
                    found_vars.extend(self._flatten_envvars(env_vars_dict))
        return tuple(found_vars)

    def has_capability(
        self, category: LiteralProviderCategory | ProviderCategoryLiteralString
    ) -> bool:
        """Check if the provider has a specific capability."""
        return category in get_categories(self)

    def is_embedding_provider(self) -> bool:
        """Check if the provider is an embedding provider."""
        return any(category == ProviderCategory.EMBEDDING for category in get_categories(self))

    def is_sparse_provider(self) -> bool:
        """Check if the provider is a sparse embedding provider."""
        return ProviderCategory.SPARSE_EMBEDDING in get_categories(self)

    def is_reranking_provider(self) -> bool:
        """Check if the provider is a reranking provider."""
        return ProviderCategory.RERANKING in get_categories(self)

    def is_agent_provider(self) -> bool:
        """Check if the provider is an agent model provider."""
        return ProviderCategory.AGENT in get_categories(self)

    def is_data_provider(self) -> bool:
        """Check if the provider is a data provider."""
        return ProviderCategory.DATA in get_categories(self)

    def get_env_api_key(self) -> str | None:
        """Get the API key from environment variables, if set."""
        if env_vars := self.api_key_env_vars:
            for env_var in env_vars:
                if api_key := os.getenv(env_var):
                    return api_key
        return None

    @cached_property
    def has_env_auth(self) -> bool:
        """Check if API key or TLS certs are set for the provider."""
        if self.other_env_vars:
            auth_vars = ("api_key", "tls_cert_path", "tls_key_path")
            for env_info in self.other_env_vars:
                for var in auth_vars:
                    if (env_var := env_info.get(var)) and (env := env_var.env) and os.getenv(env):
                        return True
        return False

    @cached_property
    def never_uses_own_client(self) -> bool:
        """Check if the provider never uses its own SDK client."""
        return self in {Provider.AZURE, Provider.MEMORY} | {
            provider
            for provider in type(self)
            if (provider.uses_openai_api and provider not in (Provider.OPENAI, Provider.GROQ))
        }

    @cached_property
    def only_uses_own_client(self) -> bool:
        """Check if the provider only uses its own SDK client. Importantly, this does not consider a provider's **models**. Cohere, for example, which makes models -- you can use Cohere models with many SDKs, but in CodeWeaver, Cohere, as a provider (someone you pay for a service), is only ever used with the Cohere SDK client."""
        return self not in (
            {Provider.AZURE, Provider.HEROKU, Provider.MEMORY}
            | {
                provider
                for provider in type(self)
                if (provider.uses_openai_api and provider != Provider.OPENAI)
            }
        )

    @classmethod
    def _category_cls(cls) -> type[ProviderCategory]:
        """Get the ProviderCategory class."""
        return ProviderCategory


type LiteralSDKClient = Literal[
    SDKClient.ANTHROPIC,
    SDKClient.BEDROCK,
    SDKClient.COHERE,
    SDKClient.DUCKDUCKGO,
    SDKClient.EXA,
    SDKClient.FASTEMBED,
    SDKClient.GOOGLE,
    SDKClient.GROQ,
    SDKClient.HUGGINGFACE_INFERENCE,
    SDKClient.MISTRAL,
    SDKClient.OPENAI,
    SDKClient.PYDANTIC_GATEWAY,
    SDKClient.QDRANT,
    SDKClient.SENTENCE_TRANSFORMERS,
    SDKClient.TAVILY,
    SDKClient.VOYAGE,
    SDKClient.X_AI,
]


type LiteralProviderCategory = Literal[
    ProviderCategory.AGENT,
    ProviderCategory.DATA,
    ProviderCategory.EMBEDDING,
    ProviderCategory.RERANKING,
    ProviderCategory.SPARSE_EMBEDDING,
    ProviderCategory.VECTOR_STORE,
]
type LiteralProvider = Literal[
    Provider.ALIBABA,
    Provider.ANTHROPIC,
    Provider.AZURE,
    Provider.BEDROCK,
    Provider.CEREBRAS,
    Provider.COHERE,
    Provider.DEEPSEEK,
    Provider.DUCKDUCKGO,
    Provider.EXA,
    Provider.FASTEMBED,
    Provider.FIREWORKS,
    Provider.GITHUB,
    Provider.GOOGLE,
    Provider.GROQ,
    Provider.HEROKU,
    Provider.HUGGINGFACE_INFERENCE,
    Provider.LITELLM,
    Provider.MISTRAL,
    Provider.MOONSHOT,
    Provider.MEMORY,
    Provider.NEBIUS,
    Provider.OLLAMA,
    Provider.OPENAI,
    Provider.OPENROUTER,
    Provider.OVHCLOUD,
    # Provider.OUTLINES,
    Provider.PERPLEXITY,
    Provider.PYDANTIC_GATEWAY,
    Provider.QDRANT,
    Provider.SENTENCE_TRANSFORMERS,
    Provider.TAVILY,
    Provider.TOGETHER,
    Provider.VERCEL,
    Provider.VOYAGE,
    Provider.X_AI,
]


__all__ = (
    "LiteralProvider",
    "LiteralProviderCategory",
    "LiteralSDKClient",
    "Provider",
    "ProviderCategory",
    "SDKClient",
    "get_categories",
)
