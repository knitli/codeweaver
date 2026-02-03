# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Provider enums moved to core to break circular dependencies."""

from __future__ import annotations

import contextlib
import os

from functools import cached_property
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Literal, TypedDict, cast

from codeweaver.core.types.enum import BaseEnum
from codeweaver.core.types.env import ProviderEnvVars
from codeweaver.core.utils import has_package
from codeweaver.core.utils.lazy_importer import LazyImport, lazy_import


if TYPE_CHECKING:
    from codeweaver.core.types.env import EnvVarInfo as ProviderEnvVarInfo

if TYPE_CHECKING and has_package("sentence_transformers"):
    from sentence_transformers import CrossEncoder, SentenceTransformer, SparseEncoder
else:
    SentenceTransformer = Any
    CrossEncoder = Any
    SparseEncoder = Any

if TYPE_CHECKING and (has_package("fastembed") or has_package("fastembed-gpu")):
    from fastembed.rerank.cross_encoder import TextCrossEncoder
    from fastembed.sparse import SparseTextEmbedding
    from fastembed.text import TextEmbedding
else:
    TextEmbedding = Any
    TextCrossEncoder = Any
    SparseTextEmbedding = Any

if TYPE_CHECKING and has_package("anthropic"):
    from anthropic import (
        AsyncAnthropic,
        AsyncAnthropicBedrock,
        AsyncAnthropicFoundry,
        AsyncAnthropicVertex,
    )
else:
    AsyncAnthropic = Any
    AsyncAnthropicBedrock = Any
    AsyncAnthropicFoundry = Any
    AsyncAnthropicVertex = Any


class LazyImportDict(TypedDict):
    """A typed dict for lazy imports when a client provider has multiple possible clients.

    This class specifically is kind of an abstract base class for such dicts.
    """


class FastEmbedClientLazyImportDict(LazyImportDict):
    """A typed dict for lazy imports for FastEmbed client providers."""

    embed: LazyImport[TextEmbedding]
    sparse: LazyImport[SparseTextEmbedding]
    reranking: LazyImport[TextCrossEncoder]


class SentenceTransformersLazyImportDict(LazyImportDict):
    """A typed dict for lazy imports for Sentence Transformers client providers."""

    embed: LazyImport[SentenceTransformer]
    sparse: LazyImport[SparseEncoder]
    reranking: LazyImport[CrossEncoder]


class AnthropicAgentLazyImportDict(TypedDict):
    """A typed dict for lazy imports for Anthropic clients by provider."""

    anthropic: LazyImport[AsyncAnthropic]
    azure: LazyImport[AsyncAnthropicFoundry]
    bedrock: LazyImport[AsyncAnthropicBedrock]
    google: LazyImport[AsyncAnthropicVertex]


class ProviderKind(BaseEnum):
    """Enumeration of available provider kinds."""

    DATA = "data"
    EMBEDDING = "embedding"
    SPARSE_EMBEDDING = "sparse_embedding"
    RERANKING = "reranking"
    VECTOR_STORE = "vector-store"
    AGENT = "agent"
    UNSET = "unset"


class SDKClient(BaseEnum):
    """Enumeration of available SDK clients.

    There's not a 1-to-1 match of Provider to SDKClient, because some providers
    use the same SDK client (like OpenAI, which has 10+ providers using their SDK, at least for agents).
    """

    ANTHROPIC = "anthropic"
    BEDROCK = "bedrock"
    COHERE = "cohere"
    DUCKDUCKGO = "duckduckgo"
    FASTEMBED = "fastembed"
    GOOGLE = "google"
    GROQ = "groq"
    HUGGINGFACE_INFERENCE = "hf_inference"
    MISTRAL = "mistral"
    OPENAI = "openai"
    PYDANTIC_GATEWAY = "gateway"
    QDRANT = "qdrant"
    SENTENCE_TRANSFORMERS = "sentence-transformers"
    TAVILY = "tavily"
    VOYAGE = "voyage"

    @property
    def client(  # noqa: C901
        self,
    ) -> (
        LazyImport[Any]
        | AnthropicAgentLazyImportDict
        | FastEmbedClientLazyImportDict
        | SentenceTransformersLazyImportDict
    ):
        """Get a lazy import for the SDK client (not the provider class)."""
        match self:
            case SDKClient.ANTHROPIC:
                return AnthropicAgentLazyImportDict(
                    anthropic=lazy_import("anthropic", "AsyncAnthropic"),
                    azure=lazy_import("anthropic", "AsyncAnthropicFoundry"),
                    bedrock=lazy_import("anthropic", "AsyncAnthropicBedrock"),
                    google=lazy_import("anthropic", "AsyncAnthropicVertex"),
                )
            case SDKClient.BEDROCK:
                return lazy_import("boto3", "client")
            case SDKClient.COHERE:
                return lazy_import("cohere", "AsyncClientV2")
            case SDKClient.DUCKDUCKGO:
                return lazy_import("ddgs.ddgs", "DDGS")
            case SDKClient.FASTEMBED:
                return FastEmbedClientLazyImportDict(
                    embed=lazy_import(
                        "codeweaver.providers.embedding.fastembed_extensions", "get_text_embedder"
                    ),
                    sparse=lazy_import(
                        "codeweaver.providers.embedding.fastembed_extensions", "get_sparse_embedder"
                    ),
                    reranking=lazy_import("fastembed.rerank.cross_encoder", "TextCrossEncoder"),
                )
            case SDKClient.GOOGLE:
                return lazy_import("google.genai", "Client")
            case SDKClient.GROQ:
                return lazy_import("groq", "AsyncGroq")
            case SDKClient.HUGGINGFACE_INFERENCE:
                return lazy_import("huggingface_hub", "AsyncInferenceClient")
            case SDKClient.MISTRAL:
                return lazy_import("mistralai", "Mistral")
            case SDKClient.OPENAI:
                return lazy_import("openai", "AsyncOpenAI")
            case SDKClient.PYDANTIC_GATEWAY:
                # Pydantic Gateway isn't a true client. It handles the machinery for multiple clients.
                return lazy_import("pydantic_ai.providers.gateway", "gateway_provider")
            case SDKClient.QDRANT:
                return lazy_import("qdrant_client", "AsyncQdrantClient")
            case SDKClient.SENTENCE_TRANSFORMERS:
                return SentenceTransformersLazyImportDict(
                    embed=lazy_import("sentence_transformers", "SentenceTransformer"),
                    sparse=lazy_import("sentence_transformers", "SparseEncoder"),
                    reranking=lazy_import("sentence_transformers", "CrossEncoder"),
                )
            case SDKClient.TAVILY:
                return lazy_import("tavily", "AsyncTavilyClient")
            case SDKClient.VOYAGE:
                return lazy_import("voyageai.client_async", "AsyncClient")
            case _:
                raise ValueError(f"Unsupported SDK client: {self.value}")

    @property
    def agent_provider(self) -> LazyImport[Any] | None:
        """Get the default agent provider for the SDK client."""
        match self:
            case SDKClient.ANTHROPIC:
                return lazy_import("pydantic_ai.providers.anthropic", "AnthropicProvider")
            case SDKClient.GOOGLE:
                return lazy_import("pydantic_ai.providers.google", "GoogleProvider")
            case SDKClient.BEDROCK:
                return lazy_import("pydantic_ai.providers.bedrock", "BedrockProvider")
            case SDKClient.COHERE:
                return lazy_import("pydantic_ai.providers.cohere", "CohereProvider")
            case SDKClient.GROQ:
                return lazy_import("pydantic_ai.providers.groq", "GroqProvider")
            case SDKClient.HUGGINGFACE_INFERENCE:
                return lazy_import("pydantic_ai.providers.huggingface", "HuggingFaceProvider")
            case SDKClient.MISTRAL:
                return lazy_import("pydantic_ai.providers.mistral", "MistralProvider")
            case SDKClient.OPENAI:
                return lazy_import("pydantic_ai.providers.openai", "OpenAIProvider")
            case SDKClient.PYDANTIC_GATEWAY:
                # this actually returns based on the upstream provider
                # for an openai model, for example, it returns OpenAIProvider
                return lazy_import("pydantic_ai.providers.gateway", "gateway_provider")
            case _:
                return None

    @property
    def data_provider(self) -> LazyImport[Any] | None:
        """Get the default data provider for the SDK client."""
        match self:
            case SDKClient.TAVILY:
                return lazy_import("pydantic_ai.common_tools.tavily", "TavilySearchTool")
            case SDKClient.DUCKDUCKGO:
                return lazy_import("pydantic_ai.common_tools.duckduckgo", "DuckDuckGoSearchTool")
            case _:
                return None

    @property
    def embedding_provider(self) -> LazyImport[Any] | None:
        """Get the default embedding provider for the SDK client."""
        match self:
            case SDKClient.BEDROCK:
                return lazy_import(
                    "codeweaver.providers.embedding.providers.bedrock", "BedrockEmbeddingProvider"
                )
            case SDKClient.COHERE:
                return lazy_import(
                    "codeweaver.providers.embedding.providers.cohere", "CohereEmbeddingProvider"
                )
            case SDKClient.FASTEMBED:
                return lazy_import(
                    "codeweaver.providers.embedding.providers.fastembed",
                    "FastEmbedEmbeddingProvider",
                )
            case SDKClient.GOOGLE:
                return lazy_import(
                    "codeweaver.providers.embedding.providers.google", "GoogleEmbeddingProvider"
                )
            case SDKClient.HUGGINGFACE_INFERENCE:
                return lazy_import(
                    "codeweaver.providers.embedding.providers.hf_inference",
                    "HuggingFaceInferenceEmbeddingProvider",
                )
            case SDKClient.MISTRAL:
                return lazy_import(
                    "codeweaver.providers.embedding.providers.mistral", "MistralEmbeddingProvider"
                )
            case SDKClient.OPENAI:
                # because of the number of providers that use OpenAI, we have a factory method here
                return lazy_import(
                    "codeweaver.providers.embedding.providers.openai_factory.OpenAIEmbeddingBase",
                    "get_provider_class",
                )
            case SDKClient.SENTENCE_TRANSFORMERS:
                return lazy_import(
                    "codeweaver.providers.embedding.providers.sentence_transformers",
                    "SentenceTransformersEmbeddingProvider",
                )
            case SDKClient.VOYAGE:
                return lazy_import(
                    "codeweaver.providers.embedding.providers.voyage", "VoyageEmbeddingProvider"
                )
            case _:
                return None

    @property
    def sparse_embedding_provider(self) -> LazyImport[Any] | None:
        """Get the default sparse embedding provider for the SDK client."""
        match self:
            case SDKClient.FASTEMBED:
                return lazy_import(
                    "codeweaver.providers.embedding.providers.fastembed",
                    "FastEmbedSparseEmbeddingProvider",
                )
            case SDKClient.SENTENCE_TRANSFORMERS:
                return lazy_import(
                    "codeweaver.providers.embedding.providers.sentence_transformers",
                    "SentenceTransformersSparseEmbeddingProvider",
                )
            case _:
                return None

    @property
    def reranking_provider(self) -> LazyImport[Any] | None:
        """Get the default reranking provider for the SDK client."""
        match self:
            case SDKClient.FASTEMBED:
                return lazy_import(
                    "codeweaver.providers.reranking.providers.fastembed",
                    "FastEmbedRerankingProvider",
                )
            case SDKClient.SENTENCE_TRANSFORMERS:
                return lazy_import(
                    "codeweaver.providers.reranking.providers.sentence_transformers",
                    "SentenceTransformersRerankingProvider",
                )
            case SDKClient.BEDROCK:
                return lazy_import(
                    "codeweaver.providers.reranking.providers.bedrock", "BedrockRerankingProvider"
                )
            case SDKClient.COHERE:
                return lazy_import(
                    "codeweaver.providers.reranking.providers.cohere", "CohereRerankingProvider"
                )
            case SDKClient.VOYAGE:
                return lazy_import(
                    "codeweaver.providers.reranking.providers.voyage", "VoyageRerankingProvider"
                )
            case _:
                return None

    @property
    def vector_store_provider(self) -> LazyImport[Any] | None:
        """Get the default vector store provider for the SDK client."""
        match self:
            case SDKClient.QDRANT:
                return lazy_import(
                    "codeweaver.providers.vector_store.providers.qdrant",
                    "QdrantVectorStoreProvider",
                )
            case _:
                return None


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
    def validate(cls, value: str) -> BaseEnum:
        """Validate provider-specific settings."""
        from codeweaver.core import ConfigurationError

        with contextlib.suppress(AttributeError, KeyError, ValueError):
            if value_in_self := cls.from_string(value.strip()):
                return value_in_self
        raise ConfigurationError(f"Invalid provider: {value}")

    @property
    def other_env_vars(  # noqa: C901
        self,
    ) -> tuple[ProviderEnvVars, ...] | None:
        """Get the environment variables used by the provider's client that are not part of CodeWeaver's settings."""
        from codeweaver.core.types.env import EnvFormat, VariableInfo
        from codeweaver.core.types.env import EnvVarInfo as ProviderEnvVarInfo

        httpx_env_vars = {
            "http_proxy": ProviderEnvVarInfo(
                env="HTTPS_PROXY",
                description="HTTP proxy for requests",
                variables=(VariableInfo(variable="proxy", dest="httpx"),),
            ),
            "ssl_cert_file": ProviderEnvVarInfo(
                env="SSL_CERT_FILE",
                description="Path to the SSL certificate file for requests",
                fmt=EnvFormat.FILEPATH,
                variables=(VariableInfo(variable="verify", dest="httpx"),),
            ),
        }
        match self:
            case Provider.QDRANT:
                return (
                    ProviderEnvVars(
                        note="Qdrant supports setting **all** configuration options using environment variables. Like with CodeWeaver, nested variables are separated by double underscores (`__`). For all options, see [the Qdrant documentation](https://qdrant.tech/documentation/guides/configuration/)",
                        client=("qdrant",),
                        log_level=ProviderEnvVarInfo(
                            env="QDRANT__LOG_LEVEL",
                            description="Log level for Qdrant service",
                            choices={"DEBUG", "INFO", "WARNING", "ERROR"},
                        ),
                        api_key=ProviderEnvVarInfo(
                            env="QDRANT__SERVICE__API_KEY",
                            is_secret=True,
                            description="API key for Qdrant service",
                            variable_name="api_key",
                        ),
                        tls_on_off=ProviderEnvVarInfo(
                            env="QDRANT__SERVICE__ENABLE_TLS",
                            description="Enable TLS for Qdrant service, expects truthy or false value (e.g. 1 for on, 0 for off).",
                            fmt=EnvFormat.BOOLEAN,
                            choices={"true", "false"},
                            variable_name="https",
                        ),
                        tls_cert_path=ProviderEnvVarInfo(
                            env="QDRANT__TLS__CERT",
                            description="Path to the TLS certificate file for Qdrant service. Only needed if using a self-signed certificate. If you're using qdrant-cloud, you don't need this.",
                            fmt=EnvFormat.FILEPATH,
                            variable_name="kwargs",
                            variables=(
                                VariableInfo(variable="verify", dest="client"),
                                VariableInfo(variable="verify", dest="httpx"),
                            ),
                        ),
                        host=ProviderEnvVarInfo(
                            env="QDRANT__SERVICE__HOST",
                            description="Hostname of the Qdrant service; do not use for URLs with schemes (e.g. 'http://')",
                            variable_name="host",
                        ),
                        port=ProviderEnvVarInfo(
                            env="QDRANT__SERVICE__HTTP_PORT",
                            description="Port number for the Qdrant service",
                            variable_name="port",
                        ),
                    ),
                )
            case Provider.VOYAGE:
                return (
                    ProviderEnvVars(
                        client=("voyage",),
                        api_key=ProviderEnvVarInfo(
                            env="VOYAGE_API_KEY",
                            is_secret=True,
                            description="API key for Voyage service",
                            variable_name="api_key",
                        ),
                        **httpx_env_vars,
                    ),
                )
            case Provider.ANTHROPIC:
                return (
                    ProviderEnvVars(
                        client=("anthropic",),
                        api_key=ProviderEnvVarInfo(
                            env="ANTHROPIC_API_KEY",
                            is_secret=True,
                            description="API key for Anthropic service",
                            variable_name="api_key",
                        ),
                        host=ProviderEnvVarInfo(
                            env="ANTHROPIC_BASE_URL",
                            description="Host URL for Anthropic service",
                            variable_name="base_url",
                        ),
                        **httpx_env_vars,
                    ),
                    ProviderEnvVars(
                        client=("anthropic",),
                        api_key=ProviderEnvVarInfo(
                            env="ANTHROPIC_AUTH_TOKEN",
                            is_secret=True,
                            description="Auth token for Anthropic provider",
                            variable_name="auth_token",
                        ),
                    ),
                )
            case Provider.AZURE:
                # Azure has env vars by model provider, so we return a tuple of them.
                return (
                    ProviderEnvVars(
                        note="These variables are for the Azure OpenAI service. (OpenAI models on Azure)",
                        client=("openai",),
                        api_key=ProviderEnvVarInfo(
                            env="AZURE_OPENAI_API_KEY",
                            is_secret=True,
                            description="API key for Azure OpenAI service (OpenAI models on Azure)",
                            variables=(
                                VariableInfo(variable="api_key", dest="client"),
                                VariableInfo(variable="api_key", dest="provider_settings"),
                            ),
                        ),
                        endpoint=ProviderEnvVarInfo(
                            env="AZURE_OPENAI_ENDPOINT",
                            description="Endpoint for Azure OpenAI service (OpenAI models on Azure)",
                            variables=(
                                VariableInfo(variable="base_url", dest="client"),
                                VariableInfo(variable="endpoint", dest="provider_settings"),
                            ),
                        ),
                        region=ProviderEnvVarInfo(
                            env="AZURE_OPENAI_REGION",
                            description="Region for Azure OpenAI service (OpenAI models on Azure)",
                            variables=(VariableInfo(variable="region_name", dest="provider"),),
                        ),
                        **httpx_env_vars,
                    ),
                    ProviderEnvVars(
                        note="These variables are for the Azure Cohere service.",
                        client=("cohere",),
                        api_key=ProviderEnvVarInfo(
                            env="AZURE_COHERE_API_KEY",
                            is_secret=True,
                            description="API key for Azure Cohere service (cohere models on Azure)",
                            variable_name="api_key",
                        ),
                        endpoint=ProviderEnvVarInfo(
                            env="AZURE_COHERE_ENDPOINT",
                            description="Endpoint for Azure Cohere service (cohere models on Azure)",
                            variable_name="base_url",
                        ),
                        region=ProviderEnvVarInfo(
                            env="AZURE_COHERE_REGION",
                            description="Region for Azure Cohere service",
                            variable_name="region_name",
                        ),
                        **httpx_env_vars,
                    ),
                    ProviderEnvVars(
                        client=("anthropic",),
                        note="These variables are for the Azure Anthropic service.",
                        api_key=ProviderEnvVarInfo(
                            env="ANTHROPIC_FOUNDRY_API_KEY",
                            is_secret=True,
                            description="API key for Azure Anthropic service (Anthropic models on Azure)",
                            variable_name="api_key",
                        ),
                        endpoint=ProviderEnvVarInfo(
                            env="ANTHROPIC_FOUNDRY_BASE_URL",
                            description="Endpoint for Azure Anthropic service (Anthropic models on Azure)",
                            variable_name="base_url",
                        ),
                        region=ProviderEnvVarInfo(
                            env="ANTHROPIC_FOUNDRY_REGION",
                            description="Region for Azure Anthropic service",
                            variable_name="region_name",
                        ),
                        other={
                            "resource": ProviderEnvVarInfo(
                                env="ANTHROPIC_FOUNDRY_RESOURCE",
                                description="Resource name for Azure Anthropic service",
                                variable_name="resource",
                            )
                        },
                    ),
                    cast(ProviderEnvVars, *type(self).OPENAI.other_env_vars),
                )
            case Provider.VERCEL:
                return (
                    ProviderEnvVars(
                        note="You may also use the OpenAI-compatible environment variables with Vercel, since it uses the OpenAI client.",
                        client=("openai",),
                        api_key=ProviderEnvVarInfo(
                            env="VERCEL_AI_GATEWAY_API_KEY",
                            is_secret=True,
                            description="API key for Vercel service",
                            variable_name="api_key",
                        ),
                        other=httpx_env_vars,
                    ),
                    ProviderEnvVars(
                        client=("openai",),
                        api_key=ProviderEnvVarInfo(
                            env="VERCEL_OIDC_TOKEN",
                            is_secret=True,
                            description="OIDC token for Vercel service",
                            variable_name="api_key",
                        ),
                    ),
                    cast(ProviderEnvVars, *type(self).OPENAI.other_env_vars),
                )
            case Provider.TOGETHER:
                return (
                    ProviderEnvVars(
                        client=("openai",),
                        note="These variables are for the Together service.",
                        api_key=ProviderEnvVarInfo(
                            env="TOGETHER_API_KEY",
                            is_secret=True,
                            description="API key for Together service",
                            variable_name="api_key",
                        ),
                        other=httpx_env_vars,
                    ),
                    cast(ProviderEnvVars, *type(self).OPENAI.other_env_vars),
                )
            case Provider.HEROKU:
                return (
                    ProviderEnvVars(
                        client=("openai", "cohere"),
                        note="These variables are for the Heroku service.",
                        api_key=ProviderEnvVarInfo(
                            env="INFERENCE_KEY",
                            is_secret=True,
                            description="API key for Heroku service",
                            variable_name="api_key",
                        ),
                        host=ProviderEnvVarInfo(
                            env="INFERENCE_URL",
                            description="Host URL for Heroku service",
                            variable_name="base_url",
                        ),
                        other={
                            "model_id": ProviderEnvVarInfo(
                                env="INFERENCE_MODEL_ID",
                                description="Model ID for Heroku service",
                                variables=(VariableInfo(variable="model", dest="embed"),),
                            ),
                            **httpx_env_vars,
                        },
                    ),
                    cast(ProviderEnvVars, *type(self).OPENAI.other_env_vars),
                    cast(ProviderEnvVars, *type(self).COHERE.other_env_vars),
                )
            case Provider.DEEPSEEK:
                return (
                    ProviderEnvVars(
                        note="These variables are for the DeepSeek service.",
                        client=("openai",),
                        api_key=ProviderEnvVarInfo(
                            env="DEEPSEEK_API_KEY",
                            is_secret=True,
                            description="API key for DeepSeek service",
                            variable_name="api_key",
                        ),
                        other=httpx_env_vars,
                    ),
                    cast(ProviderEnvVars, *type(self).OPENAI.other_env_vars),
                )
            case Provider.OPENAI:
                return (
                    ProviderEnvVars(
                        client=("openai",),
                        note="These variables are for any OpenAI-compatible service, including OpenAI itself, Azure OpenAI, and others -- any provider that we use the OpenAI client to connect to.",
                        api_key=ProviderEnvVarInfo(
                            env="OPENAI_API_KEY",
                            description="API key for OpenAI-compatible services (not necessarily an API key *for* OpenAI). The OpenAI client also requires an API key, even if you don't actually need one for your provider (like local Ollama). So provide a dummy key if needed.",
                            is_secret=True,
                            variable_name="api_key",
                        ),
                        log_level=ProviderEnvVarInfo(
                            env="OPENAI_LOG",
                            description="One of: 'debug', 'info', 'warning', 'error'",
                            choices={"debug", "info", "warning", "error"},
                        ),
                        other=httpx_env_vars
                        | {
                            "organization": ProviderEnvVarInfo(
                                env="OPENAI_ORG_ID",
                                description="Organization ID for OpenAI.",
                                variable_name="organization",
                            ),
                            "project": ProviderEnvVarInfo(
                                env="OPENAI_PROJECT_ID",
                                description="An openai project id for tracking usage.",
                                variable_name="project",
                            ),
                            "webhook_secret": ProviderEnvVarInfo(
                                env="OPENAI_WEBHOOK_SECRET",
                                description="Webhook secret for verifying incoming webhooks from OpenAI.",
                                is_secret=True,
                                variable_name="webhook_secret",
                            ),
                        },
                    ),
                )
            case Provider.OPENROUTER:
                return (
                    ProviderEnvVars(
                        client=("openai",),
                        note="These variables are for the OpenRouter service.",
                        api_key=ProviderEnvVarInfo(
                            env="OPENROUTER_API_KEY",
                            is_secret=True,
                            description="API key for OpenRouter service",
                            variable_name="api_key",
                        ),
                        other=httpx_env_vars,
                    ),
                    cast(ProviderEnvVars, *type(self).OPENAI.other_env_vars),
                )
            case Provider.CEREBRAS:
                return (
                    ProviderEnvVars(
                        client=("cerebras", "openai"),
                        api_key=ProviderEnvVarInfo(
                            env="CEREBRAS_API_KEY",
                            description="Your Cerebras API Key",
                            is_secret=True,
                            variable_name="api_key",
                        ),
                        host=ProviderEnvVarInfo(
                            env="CEREBRAS_API_URL",
                            description="Host URL for Cerebras service",
                            variable_name="base_url",
                        ),
                        other=httpx_env_vars,
                    ),
                    cast(ProviderEnvVars, *type(self).OPENAI.other_env_vars),
                )
            case Provider.FIREWORKS:
                return (
                    ProviderEnvVars(
                        client=("openai",),
                        api_key=ProviderEnvVarInfo(
                            env="FIREWORKS_API_KEY",
                            description="Your Fireworks API Key",
                            is_secret=True,
                            variable_name="api_key",
                        ),
                        host=ProviderEnvVarInfo(
                            env="FIREWORKS_API_URL",
                            description="Host URL for Fireworks service",
                            variable_name="base_url",
                        ),
                        other=httpx_env_vars,
                    ),
                    cast(ProviderEnvVars, *type(self).OPENAI.other_env_vars),
                )
            case Provider.MORPH:
                return (
                    ProviderEnvVars(
                        client=("openai",),
                        api_key=ProviderEnvVarInfo(
                            env="MORPH_API_KEY",
                            description="Your Morph API Key",
                            is_secret=True,
                            variable_name="api_key",
                        ),
                        host=ProviderEnvVarInfo(
                            env="MORPH_API_URL",
                            default="https://api.morphllm.com/v1",
                            description="Host URL for Morph service",
                            variable_name="base_url",
                        ),
                        other=httpx_env_vars,
                    ),
                    cast(ProviderEnvVars, *type(self).OPENAI.other_env_vars),
                )
            case Provider.NEBIUS:
                return (
                    ProviderEnvVars(
                        client=("openai",),
                        api_key=ProviderEnvVarInfo(
                            env="NEBIUS_API_KEY",
                            description="Your Nebius API Key",
                            is_secret=True,
                            variable_name="api_key",
                        ),
                        host=ProviderEnvVarInfo(
                            env="NEBIUS_API_URL",
                            description="Host URL for Nebius service",
                            variable_name="base_url",
                        ),
                        other=httpx_env_vars,
                    ),
                    cast(ProviderEnvVars, *type(self).OPENAI.other_env_vars),
                )
            case Provider.OVHCLOUD:
                return (
                    ProviderEnvVars(
                        client=("openai",),
                        api_key=ProviderEnvVarInfo(
                            env="OVHCLOUD_API_KEY",
                            description="Your OVHCloud API Key",
                            is_secret=True,
                            variable_name="api_key",
                        ),
                        host=ProviderEnvVarInfo(
                            env="OVHCLOUD_API_URL",
                            description="Host URL for OVHCloud service",
                            variable_name="base_url",
                        ),
                        other=httpx_env_vars,
                    ),
                    cast(ProviderEnvVars, *type(self).OPENAI.other_env_vars),
                )
            case Provider.SAMBANOVA:
                return (
                    ProviderEnvVars(
                        client=("openai",),
                        api_key=ProviderEnvVarInfo(
                            env="SAMBANOVA_API_KEY",
                            description="Your SambaNova API Key",
                            is_secret=True,
                            variable_name="api_key",
                        ),
                        host=ProviderEnvVarInfo(
                            env="SAMBANOVA_API_URL",
                            description="Host URL for SambaNova service",
                            variable_name="base_url",
                        ),
                        other=httpx_env_vars,
                    ),
                    cast(ProviderEnvVars, *type(self).OPENAI.other_env_vars),
                )
            case Provider.HUGGINGFACE_INFERENCE:
                return (
                    ProviderEnvVars(
                        client=("hf_inference",),
                        note="Hugging Face allows for setting many configuration options by environment variable. See [the Hugging Face documentation](https://huggingface.co/docs/huggingface_hub/package_reference/environment_variables) for more details.",
                        api_key=ProviderEnvVarInfo(
                            env="HF_TOKEN",
                            description="API key/token for Hugging Face service",
                            variable_name="token",
                            is_secret=True,
                        ),
                        log_level=ProviderEnvVarInfo(
                            env="HF_HUB_VERBOSITY",
                            description="Log level for Hugging Face Hub client",
                            choices={"debug", "info", "warning", "error", "critical"},
                        ),
                        other=httpx_env_vars,
                    ),
                )
            case Provider.BEDROCK:
                return (
                    (
                        ProviderEnvVars(
                            client=("bedrock", "anthropic"),
                            note="AWS allows for setting many configuration options by environment variable. See [the AWS documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html#using-environment-variables) for more details. Because AWS has multiple authentication methods, and ways to configure settings, we don't provide them here. We'd just confuse people. Unlike other providers, we also don't check for AWS's environment variables, we just assume you're authorized to do what you need to do.",
                            region=ProviderEnvVarInfo(
                                env="AWS_REGION",
                                description="AWS region for Bedrock service",
                                variable_name="region_name",
                            ),
                            account_id=ProviderEnvVarInfo(
                                env="AWS_ACCOUNT_ID",
                                description="AWS Account ID for Bedrock service",
                                variable_name="aws_account_id",
                            ),
                            api_key=ProviderEnvVarInfo(
                                env="AWS_SECRET_ACCESS_KEY",
                                description="AWS Secret Access Key for Bedrock service",
                                is_secret=True,
                                variable_name="aws_secret_access_key",
                            ),
                            other={
                                "aws_access_key_id": ProviderEnvVarInfo(
                                    env="AWS_ACCESS_KEY_ID",
                                    description="AWS Access Key ID for Bedrock service",
                                    is_secret=True,
                                    variable_name="aws_access_key_id",
                                ),
                                "aws_bearer_token_bedrock": ProviderEnvVarInfo(
                                    env="AWS_BEARER_TOKEN_BEDROCK",
                                    description="AWS Bearer Token for Bedrock service",
                                    is_secret=True,
                                    variable_name="aws_bearer_token_bedrock",
                                ),
                            },
                        )
                    ),
                )
            case Provider.COHERE:
                return (
                    ProviderEnvVars(
                        client=("cohere",),
                        api_key=ProviderEnvVarInfo(
                            env="COHERE_API_KEY",
                            description="Your Cohere API Key",
                            is_secret=True,
                            variable_name="api_key",
                        ),
                        host=ProviderEnvVarInfo(
                            env="CO_API_URL",
                            description="Host URL for Cohere service",
                            variable_name="base_url",
                        ),
                        other=httpx_env_vars,
                    ),
                )
            case Provider.TAVILY:
                return (
                    ProviderEnvVars(
                        client=("tavily",),
                        api_key=ProviderEnvVarInfo(
                            env="TAVILY_API_KEY",
                            description="Your Tavily API Key",
                            is_secret=True,
                            variable_name="api_key",
                        ),
                        other=httpx_env_vars,
                    ),
                )
            case Provider.GOOGLE:
                return (
                    ProviderEnvVars(
                        client=("google",),
                        api_key=ProviderEnvVarInfo(
                            env="GEMINI_API_KEY",
                            description="Your Google Gemini API Key",
                            is_secret=True,
                            variable_name="api_key",
                        ),
                        other=httpx_env_vars,
                    ),
                    ProviderEnvVars(
                        client=("google",),
                        api_key=ProviderEnvVarInfo(
                            env="GOOGLE_API_KEY",
                            description="Your Google API Key",
                            is_secret=True,
                            variable_name="api_key",
                        ),
                    ),
                )
            case Provider.GROQ:
                return (
                    ProviderEnvVars(
                        client=("groq", "openai"),
                        api_key=ProviderEnvVarInfo(
                            env="GROQ_API_KEY",
                            description="Your Groq API Key",
                            is_secret=True,
                            variable_name="api_key",
                        ),
                        host=ProviderEnvVarInfo(
                            env="GROQ_BASE_URL",
                            default="https://api.groq.com",
                            description="Host URL for Groq service",
                            variable_name="base_url",
                        ),
                        other=httpx_env_vars,
                    ),
                    cast(ProviderEnvVars, *type(self).OPENAI.other_env_vars),
                )
            case Provider.MISTRAL:
                return (
                    ProviderEnvVars(
                        client=("mistral",),
                        api_key=ProviderEnvVarInfo(
                            env="MISTRAL_API_KEY",
                            description="Your Mistral API Key",
                            is_secret=True,
                            variable_name="api_key",
                        ),
                        other=httpx_env_vars,
                    ),
                )
            case Provider.PYDANTIC_GATEWAY:
                return (
                    ProviderEnvVars(
                        client=("gateway",),
                        api_key=ProviderEnvVarInfo(
                            env="PYDANTIC_AI_GATEWAY_API_KEY",
                            description="Your Pydantic AI Gateway API Key",
                            is_secret=True,
                            variable_name="api_key",
                        ),
                        other=httpx_env_vars,
                    ),
                )
            case Provider.MOONSHOT:
                return (
                    ProviderEnvVars(
                        client=("openai",),
                        note="These variables are for the Moonshot service.",
                        api_key=ProviderEnvVarInfo(
                            env="MOONSHOTAI_API_KEY",
                            is_secret=True,
                            description="API key for Moonshot service",
                            variable_name="api_key",
                        ),
                        other=httpx_env_vars,
                    ),
                    cast(ProviderEnvVars, *type(self).OPENAI.other_env_vars),
                )
            case _:
                if self.uses_openai_api:
                    return cast(tuple[ProviderEnvVars, ...], *type(self).OPENAI.other_env_vars)
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
        return self in {Provider.FASTEMBED, Provider.SENTENCE_TRANSFORMERS, Provider.MEMORY}

    @property
    def is_local_provider(self) -> bool:
        """Check if the provider can be used as a local provider."""
        return self.always_local or self in {Provider.OLLAMA, Provider.QDRANT, Provider.LITELLM}

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
        return self not in {
            # Qdrant may not require auth -- we check for API key presence elsewhere
            Provider.FASTEMBED,
            Provider.MEMORY,
            Provider.DUCKDUCKGO,
            Provider.SENTENCE_TRANSFORMERS,
            # Ollama does for cloud, but generally people associate it as local
            Provider.OLLAMA,
        }

    @property
    def uses_openai_api(self) -> bool:
        """Check if the provider uses the OpenAI API."""
        return self in {
            Provider.ALIBABA,
            Provider.AZURE,
            Provider.CEREBRAS,
            Provider.DEEPSEEK,
            Provider.FIREWORKS,
            Provider.GITHUB,
            Provider.GROQ,
            Provider.HEROKU,
            Provider.LITELLM,
            Provider.MOONSHOT,
            Provider.MORPH,
            Provider.NEBIUS,
            Provider.OLLAMA,
            Provider.OPENAI,
            Provider.OPENROUTER,
            Provider.OVHCLOUD,
            Provider.PERPLEXITY,
            Provider.SAMBANOVA,
            Provider.TOGETHER,
            Provider.VERCEL,
            Provider.X_AI,
        }

    @staticmethod
    def _flatten_envvars(env_vars: ProviderEnvVars) -> list[ProviderEnvVarInfo]:
        """Flatten a ProviderEnvVars TypedDict into a list of ProviderEnvVarInfo tuples."""
        from codeweaver.core.types.env import EnvVarInfo as ProviderEnvVarInfo

        found_vars: list[ProviderEnvVarInfo] = []
        for key, value in env_vars.items():
            if key not in ("note", "other") and isinstance(value, ProviderEnvVarInfo):
                found_vars.append(value)
            elif key == "other" and isinstance(value, dict) and value:
                found_vars.extend(iter(value.values()))
        return found_vars

    @classmethod
    def all_envs(cls) -> tuple[tuple[Provider, ProviderEnvVarInfo], ...]:
        """Get all environment variables used by all providers."""
        found_vars: list[tuple[Provider, ProviderEnvVarInfo]] = []
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
        self,
        client: Literal[
            "anthropic",
            "bedrock",
            "cohere",
            "duckduckgo",
            "fastembed",
            "google",
            "groq",
            "hf_inference",
            "mistral",
            "openai",
            "qdrant",
            "sentence_transformers",
            "tavily",
        ],
    ) -> tuple[ProviderEnvVarInfo, ...]:
        """Get all environment variables used by this provider for a specific client."""
        found_vars: list[ProviderEnvVarInfo] = []
        if envs := self.other_env_vars:
            for env_vars_dict in envs:
                if "client" in env_vars_dict and client in env_vars_dict["client"]:
                    found_vars.extend(self._flatten_envvars(env_vars_dict))
        return tuple(found_vars)

    def has_capability(self, kind: LiteralProviderKindType) -> bool:
        """Check if the provider has a specific capability."""
        return kind in get_provider_kinds(cast(LiteralProviderType, self))

    def is_embedding_provider(self) -> bool:
        """Check if the provider is an embedding provider."""
        return any(
            kind == ProviderKind.EMBEDDING
            for kind in get_provider_kinds(cast(LiteralProviderType, self))
        )

    def is_sparse_provider(self) -> bool:
        """Check if the provider is a sparse embedding provider."""
        return ProviderKind.SPARSE_EMBEDDING in get_provider_kinds(cast(LiteralProviderType, self))

    def is_reranking_provider(self) -> bool:
        """Check if the provider is a reranking provider."""
        return ProviderKind.RERANKING in get_provider_kinds(cast(LiteralProviderType, self))

    def is_agent_provider(self) -> bool:
        """Check if the provider is an agent model provider."""
        return ProviderKind.AGENT in get_provider_kinds(cast(LiteralProviderType, self))

    def is_data_provider(self) -> bool:
        """Check if the provider is a data provider."""
        return ProviderKind.DATA in get_provider_kinds(cast(LiteralProviderType, self))

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
            {Provider.AZURE, Provider.HEROKU, Provider.MEMORY, Provider.GOOGLE}
            | {
                provider
                for provider in type(self)
                if (provider.uses_openai_api and provider != Provider.OPENAI)
            }
        )


SDK_MAP: MappingProxyType[tuple[Provider, ProviderKind], SDKClient | tuple[SDKClient, ...]] = (
    MappingProxyType(
        {
            (provider, ProviderKind.EMBEDDING): SDKClient.OPENAI
            for provider in (
                p
                for p in Provider
                if p.uses_openai_api
                and p not in (Provider.AZURE, Provider.HEROKU, Provider.GROQ)
                and p.is_embedding_provider()
            )
        }
        | {
            (Provider.AZURE, ProviderKind.EMBEDDING): (SDKClient.OPENAI, SDKClient.COHERE),
            (Provider.HEROKU, ProviderKind.EMBEDDING): (SDKClient.OPENAI, SDKClient.COHERE),
        }
        | {
            (provider, ProviderKind.EMBEDDING): SDKClient.from_string(provider.variable)
            for provider in (Provider.MISTRAL, Provider.HUGGINGFACE_INFERENCE, Provider.GOOGLE)
        }
        | {
            (provider, kind): SDKClient.from_string(provider.variable)
            for provider, kind in (
                (prov, knd)
                for prov in (Provider.BEDROCK, Provider.COHERE, Provider.VOYAGE)
                for knd in (ProviderKind.EMBEDDING, ProviderKind.RERANKING)
            )
        }
        | {
            (provider, kind): SDKClient.from_string(provider.variable)
            for provider in (Provider.FASTEMBED, Provider.SENTENCE_TRANSFORMERS)
            for kind in (
                ProviderKind.EMBEDDING,
                ProviderKind.SPARSE_EMBEDDING,
                ProviderKind.RERANKING,
            )
        }
        | {(Provider.QDRANT, ProviderKind.VECTOR_STORE): SDKClient.QDRANT}
        | {(Provider.MEMORY, ProviderKind.VECTOR_STORE): SDKClient.QDRANT}
        | {
            (provider, ProviderKind.AGENT): SDKClient.OPENAI
            for provider in Provider
            if provider.uses_openai_api
            and provider != Provider.GROQ
            and provider.is_agent_provider()
        }
        | {(Provider.ANTHROPIC, ProviderKind.AGENT): SDKClient.ANTHROPIC}
        | {(Provider.AZURE, ProviderKind.AGENT): (SDKClient.OPENAI, SDKClient.ANTHROPIC)}
        | {(Provider.BEDROCK, ProviderKind.AGENT): (SDKClient.BEDROCK, SDKClient.ANTHROPIC)}
        | {(Provider.COHERE, ProviderKind.AGENT): SDKClient.COHERE}
        | {(Provider.GOOGLE, ProviderKind.AGENT): (SDKClient.GOOGLE, SDKClient.ANTHROPIC)}
        | {(Provider.GROQ, ProviderKind.AGENT): SDKClient.GROQ}
        | {(Provider.HUGGINGFACE_INFERENCE, ProviderKind.AGENT): SDKClient.HUGGINGFACE_INFERENCE}
        | {(Provider.MISTRAL, ProviderKind.AGENT): SDKClient.MISTRAL}
        | {
            (provider, ProviderKind.AGENT): SDKClient.OPENAI
            for provider in {
                p
                for p in Provider
                if p.is_agent_provider()
                and p.uses_openai_api
                and p not in (Provider.AZURE, Provider.GROQ)
            }
        }
        | {(Provider.DUCKDUCKGO, ProviderKind.DATA): SDKClient.DUCKDUCKGO}
        | {(Provider.TAVILY, ProviderKind.DATA): SDKClient.TAVILY}
    )
)
"""Mapping of providers and their kinds to SDK clients. Currently only handles embedding/sparse_embedding/reranking/vector_store kinds."""


PROVIDER_CAPABILITIES: MappingProxyType[Provider, tuple[ProviderKind, ...]] = MappingProxyType({
    Provider.ALIBABA: (ProviderKind.AGENT,),
    Provider.ANTHROPIC: (ProviderKind.AGENT,),
    Provider.AZURE: (ProviderKind.AGENT, ProviderKind.EMBEDDING),
    Provider.BEDROCK: (ProviderKind.EMBEDDING, ProviderKind.RERANKING, ProviderKind.AGENT),
    Provider.CEREBRAS: (ProviderKind.AGENT,),
    Provider.COHERE: (ProviderKind.EMBEDDING, ProviderKind.RERANKING, ProviderKind.AGENT),
    Provider.DEEPSEEK: (ProviderKind.AGENT,),
    Provider.DUCKDUCKGO: (ProviderKind.DATA,),
    Provider.FASTEMBED: (
        ProviderKind.EMBEDDING,
        ProviderKind.RERANKING,
        ProviderKind.SPARSE_EMBEDDING,
    ),
    Provider.FIREWORKS: (ProviderKind.AGENT, ProviderKind.EMBEDDING),
    Provider.GITHUB: (ProviderKind.AGENT, ProviderKind.EMBEDDING),
    Provider.GOOGLE: (ProviderKind.AGENT, ProviderKind.EMBEDDING),
    Provider.GROQ: (ProviderKind.AGENT, ProviderKind.EMBEDDING),
    Provider.HEROKU: (ProviderKind.AGENT, ProviderKind.EMBEDDING),
    Provider.HUGGINGFACE_INFERENCE: (ProviderKind.AGENT, ProviderKind.EMBEDDING),
    Provider.LITELLM: (ProviderKind.AGENT,),  # supports embedding but not implemented yet
    Provider.MISTRAL: (ProviderKind.AGENT, ProviderKind.EMBEDDING),
    Provider.MEMORY: (ProviderKind.VECTOR_STORE,),
    Provider.MOONSHOT: (ProviderKind.AGENT,),
    Provider.MORPH: (ProviderKind.EMBEDDING,),  # supports agent but not implemented
    Provider.NEBIUS: (ProviderKind.AGENT,),
    Provider.OLLAMA: (ProviderKind.AGENT, ProviderKind.EMBEDDING),
    Provider.OPENAI: (ProviderKind.AGENT, ProviderKind.EMBEDDING),
    # Provider.OUTLINES: (ProviderKind.AGENT,),  # not implemented yet
    Provider.OPENROUTER: (ProviderKind.AGENT,),  # supports embedding but not implemented yet
    Provider.OVHCLOUD: (ProviderKind.AGENT,),
    Provider.PERPLEXITY: (ProviderKind.AGENT,),
    Provider.PYDANTIC_GATEWAY: (ProviderKind.AGENT,),
    Provider.QDRANT: (ProviderKind.VECTOR_STORE,),
    Provider.SENTENCE_TRANSFORMERS: (
        ProviderKind.EMBEDDING,
        ProviderKind.RERANKING,
        ProviderKind.SPARSE_EMBEDDING,
    ),
    Provider.TAVILY: (ProviderKind.DATA,),
    Provider.TOGETHER: (ProviderKind.AGENT, ProviderKind.EMBEDDING),
    Provider.VERCEL: (ProviderKind.AGENT, ProviderKind.EMBEDDING),
    Provider.VOYAGE: (ProviderKind.EMBEDDING, ProviderKind.RERANKING),
    Provider.X_AI: (ProviderKind.AGENT,),
})
"""Mapping of providers to their capabilities (the kind of provider).

One of the big questions you might have is "why don't certain providers have reranking models available?" For example, Hugging Face Inference has some models that can do reranking, but we don't list it here. The biggest reason is the SDK support, not model availability. Most notably, the SDK we use for many providers is the OpenAI SDK, which has no reranking endpoint because OpenAI itself has no reranking models.

Eventually, we may be able to enable broader support from these providers, but for now, we only list providers that have first-class support for these capabilities in their SDKs.
"""


def get_provider_kinds(provider: LiteralProviderType) -> tuple[ProviderKind, ...]:
    """Get capabilities for a provider."""
    provider = cast(
        LiteralProviderType,
        provider if isinstance(provider, Provider) else Provider.from_string(provider),
    )
    return PROVIDER_CAPABILITIES.get(provider, (ProviderKind.DATA,))  # ty:ignore[no-matching-overload]


type LiteralProviderKind = Literal[
    ProviderKind.AGENT,
    ProviderKind.DATA,
    ProviderKind.EMBEDDING,
    ProviderKind.RERANKING,
    ProviderKind.SPARSE_EMBEDDING,
    ProviderKind.VECTOR_STORE,
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

type ProviderKindLiteral = Literal[
    "agent", "data", "embedding", "reranking", "sparse_embedding", "vector_store"
]

type ProviderLiteral = Literal[
    "alibaba",
    "anthropic",
    "azure",
    "bedrock",
    "cerebras",
    "cohere",
    "deepseek",
    "duckduckgo",
    "fastembed",
    "fireworks",
    "gateway",
    "github",
    "google",
    "groq",
    "heroku",
    "hf_inference",
    "litellm",
    "mistral",
    "memory",
    "moonshot",
    "nebius",
    "ollama",
    "openai",
    "openrouter",
    "ovhcloud",
    # "outlines",
    "perplexity",
    "pydantic_gateway",
    "qdrant",
    "sentence_transformers",
    "tavily",
    "together",
    "vercel",
    "voyage",
    "x_ai",
]

type LiteralProviderKindType = ProviderKindLiteral | LiteralProviderKind
type LiteralProviderType = ProviderLiteral | LiteralProvider


__all__ = (
    "LiteralProvider",
    "LiteralProviderKind",
    "LiteralProviderKindType",
    "LiteralProviderType",
    "Provider",
    "ProviderKind",
    "ProviderKindLiteral",
    "ProviderLiteral",
    "SDKClient",
    "get_provider_kinds",
)
