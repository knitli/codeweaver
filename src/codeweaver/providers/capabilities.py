# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Metadata about provider capabilities for all provider kinds in CodeWeaver.

This module's capabilities are high-level and not specific to any model or version, focused on overall provider services. For more granular capabilities,
"""

from __future__ import annotations

import importlib

from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Literal, NamedTuple, cast

import httpx

from pydantic import ConfigDict
from pydantic.dataclasses import dataclass
from pydantic.types import PositiveInt

from codeweaver.core import (
    DATACLASS_CONFIG,
    PROVIDER_CAPABILITIES,
    DataclassSerializationMixin,
    LazyImport,
    Provider,
    ProviderKind,
    lazy_import,
)


if importlib.util.find_spec("fastembed") is not None:
    from fastembed.common.types import OnnxProvider
else:
    OnnxProvider = object

if importlib.util.find_spec("torch") is not None:
    from torch.nn import Module
else:
    Module = object
if importlib.util.find_spec("sentence-transformers") is not None:
    from sentence_transformers.model_card import SentenceTransformersModelCardData
else:
    SentenceTransformersModelCardData = object

if TYPE_CHECKING:
    from codeweaver.providers.embedding.providers.openai_factory import OpenAIEmbeddingBase
    from codeweaver.providers.types import LiteralProvider, LiteralProviderKind


VECTOR_PROVIDER_CAPABILITIES: MappingProxyType[LiteralProvider, str] = cast(
    "MappingProxyType[LiteralProvider, str]", MappingProxyType({Provider.QDRANT: "placeholder"})
)


FACTORY_IMPORT: LazyImport[OpenAIEmbeddingBase] = lazy_import(
    "codeweaver.providers.embedding.providers.openai_factory", "OpenAIEmbeddingBase"
)

type UrlString = str


@dataclass(config=ConfigDict(DATACLASS_CONFIG | {"extra": "allow"}))
class ClientOptions(DataclassSerializationMixin):
    """Essentially a schema for provider client options."""


class CohereClientOptions(ClientOptions):
    """Client options for Cohere (rerank and embeddings)."""

    api_key: str | Callable[[], str]
    base_url: str | None = None
    environment: Literal["production", "staging", "development"] = "production"
    client_name: str | None = None
    timeout: float | None = None
    httpx_client: httpx.Client | None = None
    thread_pool_executor: ThreadPoolExecutor | None = None
    log_experimental: bool = True  # disables warnings about experimental features


class QdrantClientOptions(ClientOptions):
    """Client options for Qdrant vector store provider.

    Note: `kwargs` are passed directly to the underlying httpx or grpc client.

    The instantiated client's `_client` attribute will be either an `httpx.AsyncClient` for rest.based connections, or a `grpc.aio.Channel` for grpc-based connections, which may be useful for providing custom httpx or grpc clients.
    """

    location: Literal[":memory:"] | UrlString | None = None
    url: UrlString | None = None
    port: PositiveInt | None = 6333
    grpc_port: PositiveInt | None = 6334
    https: bool | None = None
    api_key: str | None = None
    prefer_grpc: bool = False
    prefix: str | None = None
    timeout: int | None = None
    host: UrlString | None = None
    path: str | None = None
    force_disable_check_same_thread: bool = False
    grpc_options: dict[str, Any] | None = None
    auth_token_provider: Callable[[], str] | Callable[[], Awaitable[str]] | None = None
    cloud_inference: bool = False
    local_inference_batch_size: PositiveInt | None = None
    check_compatibility: bool = True
    pool_size: PositiveInt | None = None  # (httpx pool size, default 100)
    kwargs: Any = None

    def __post_init__(self) -> None:
        """Validate that either location or url is provided."""
        # Essentially, you can only provide 1 of location or url or host+port -- path is exclusive of all of them.
        if self.path:
            for attr in ("location", "url", "host", "port", "grpc_port"):
                if getattr(self, attr) is not None:
                    raise ValueError(
                        f"If 'path' is provided, '{attr}' must be None, got {getattr(self, attr)}"
                    )
        if self.url and self.host:
            self.host = None
        if self.location and self.location != ":memory:" and (self.url or self.host):
            self.url = self.url or self.location or self.host
            self.location = None
            self.host = None
        return self


class OpenAIClientOptions(ClientOptions):
    """Client options for OpenAI-based embedding providers."""

    api_key: str | Callable[[], str] | Callable[[], Awaitable[str]] | None = None
    organization: str | None = None
    project: str | None = None
    webhook_secret: str | None = None
    base_url: UrlString | None = None
    websocket_base_url: UrlString | None = None
    timeout: float | None = None
    max_retries: PositiveInt | None = None
    default_headers: Mapping[str, str] | None = None
    default_query: Mapping[str, object] | None = None
    http_client: httpx.Client | None = None
    _strict_response_validation: bool = False


class Boto3ClientOptions(ClientOptions):
    """Client options for Boto3-based providers like Bedrock."""

    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    aws_session_token: str | None = None
    region_name: str | None = None
    botocore_session: Any | None = None
    profile_name: str | None = None
    aws_account_id: str | None = None


class GoogleClientOptions(ClientOptions):
    """Client options for the GenAI Google provider."""

    api_key: str | None = None
    vertex_ai: bool = False
    credentials: Any | None = None
    project: str | None = None
    location: str | None = None
    debug_config: dict[str, Any] | None = None
    http_options: dict[str, Any] | None = None


class FastEmbedClientOptions(ClientOptions):
    """Client options for FastEmbed-based embedding providers."""

    model_name: str
    cache_dir: str | None = None
    threads: int | None = None
    providers: Sequence[OnnxProvider] | None = None
    cuda: bool = False
    device_ids: list[int] | None = None
    lazy_load: bool = True


class SentenceTransformersClientOptions(ClientOptions):
    """Client options for SentenceTransformers-based embedding providers."""

    model_name_or_path: str | None = None
    modules: Iterable[Module] | None = None
    device: str | None = None
    prompts: dict[str, str] | None = None
    default_prompt_name: str | None = None
    similarity_fn_name: Literal["cosine", "dot", "euclidean", "manhattan"] | None = None
    cache_folder: str | None = None
    trust_remote_code: bool = False
    revision: str | None = None
    local_files_only: bool = False
    token: bool | str | None = None
    use_auth_token: bool | str | None = None
    truncate_dim: int | None = None
    model_kwargs: dict[str, Any] | None = None
    tokenizer_kwargs: dict[str, Any] | None = None
    config_kwargs: dict[str, Any] | None = None
    model_card_data: SentenceTransformersModelCardData | None = None
    backend: Literal["torch", "onnx", "openvino"] = "torch"


class HFInferenceClientOptions(ClientOptions):
    """Client options for HuggingFace Inference API-based embedding providers."""

    model: str | None = None
    provider: str | None = None
    token: str | None = None
    timeout: float | None = None
    headers: dict[str, str] | None = None
    cookies: dict[str, str] | None = None
    trust_env: bool = False
    proxies: Any | None = None
    bill_to: str | None = None
    base_url: UrlString | None = None
    api_key: str | None = None


class MistralClientOptions(ClientOptions):
    """Client options for Mistral-based embedding providers."""

    api_key: str | Callable[[], str] | Callable[[], Awaitable[str]] | None = None
    server: str | None = None
    server_url: UrlString | None = None
    url_params: dict[str, str] | None = None
    async_client: httpx.AsyncClient | None = None
    retry_config: Any | None = None
    timeout_ms: int | None = None
    debug_logger: Any | None = None


class VoyageClientOptions(ClientOptions):
    """Client options for Voyage AI-based embedding and reranking providers."""

    api_key: str | None = None
    max_retries: PositiveInt = 0
    timeout: float | None = None


class Client(NamedTuple):
    """Provides information on a provider's client for a given kind (like ProviderKind.EMBEDDING), and information needed to create the client and class."""

    provider: LiteralProvider
    kind: LiteralProviderKind
    origin: Literal["codeweaver", "pydantic-ai"] = "codeweaver"
    # the following are only given for codeweaver providers
    client: LazyImport[Any] | None = None
    models_matching: tuple[str, ...] | tuple[Literal["*"]] = ("*",)
    provider_class: LazyImport[Any] | None = None
    provider_factory: LazyImport[Any] | Callable[[Any], Any] | None = None
    client_options: type[ClientOptions] | None = None


CLIENT_MAP: MappingProxyType[LiteralProvider, tuple[Client, ...]] = cast(
    "MappingProxyType[LiteralProvider, tuple[Client, ...]]",
    MappingProxyType({
        Provider.QDRANT: (
            Client(
                provider=Provider.QDRANT,
                kind=ProviderKind.VECTOR_STORE,
                client=lazy_import("qdrant_client", "AsyncQdrantClient"),
                provider_class=lazy_import(
                    "codeweaver.providers.vector_stores.qdrant", "QdrantVectorStoreProvider"
                ),
                client_options=QdrantClientOptions,
            ),
        ),
        Provider.MEMORY: (
            Client(
                provider=Provider.MEMORY,  # ty:ignore[invalid-argument-type]
                kind=ProviderKind.VECTOR_STORE,
                client=lazy_import("qdrant_client", "AsyncQdrantClient"),
                provider_class=lazy_import(
                    "codeweaver.providers.vector_stores.inmemory", "MemoryVectorStoreProvider"
                ),
                client_options=QdrantClientOptions,
            ),
        ),
        Provider.ANTHROPIC: (
            Client(provider=Provider.ANTHROPIC, kind=ProviderKind.AGENT, origin="pydantic-ai"),
        ),
        Provider.AZURE: (
            Client(provider=Provider.AZURE, kind=ProviderKind.AGENT, origin="pydantic-ai"),
            Client(
                provider=Provider.AZURE,
                kind=ProviderKind.EMBEDDING,
                origin="codeweaver",
                models_matching=("text-embedding*",),
                client=lazy_import("openai", "AsyncOpenAI"),
                provider_class=FACTORY_IMPORT,
                provider_factory=lambda *args, **kwargs: FACTORY_IMPORT.get_provider_class(  # type: ignore
                    *args, **kwargs
                ),
                client_options=OpenAIClientOptions,
            ),
            Client(
                provider=Provider.AZURE,
                kind=ProviderKind.EMBEDDING,
                origin="codeweaver",
                models_matching=("embed-*-v3.0", "embed-v4.0"),
                client=lazy_import("cohere", "AsyncClientV2"),
                provider_class=lazy_import(
                    "codeweaver.providers.embedding.providers.cohere", "CohereEmbeddingProvider"
                ),
                client_options=CohereClientOptions,
            ),
        ),
        Provider.BEDROCK: (
            Client(provider=Provider.BEDROCK, kind=ProviderKind.AGENT, origin="pydantic-ai"),
            Client(
                provider=Provider.BEDROCK,
                kind=ProviderKind.EMBEDDING,
                origin="codeweaver",
                client=lazy_import("boto3", "client"),  # bedrock-runtime
                provider_class=lazy_import(
                    "codeweaver.providers.embedding.providers.bedrock", "BedrockEmbeddingProvider"
                ),
                client_options=Boto3ClientOptions,
            ),
            Client(
                provider=Provider.BEDROCK,
                kind=ProviderKind.RERANKING,
                origin="codeweaver",
                client=lazy_import("boto3", "client"),  # bedrock-runtime
                provider_class=lazy_import(
                    "codeweaver.providers.reranking.providers.bedrock", "BedrockRerankingProvider"
                ),
                client_options=Boto3ClientOptions,
            ),
        ),
        Provider.CEREBRAS: (
            Client(provider=Provider.CEREBRAS, kind=ProviderKind.AGENT, origin="pydantic-ai"),
            Client(
                provider=Provider.CEREBRAS,
                kind=ProviderKind.EMBEDDING,
                origin="codeweaver",
                client=lazy_import("openai", "AsyncOpenAI"),
                provider_class=FACTORY_IMPORT,
                provider_factory=lambda *args, **kwargs: FACTORY_IMPORT.get_provider_class(
                    *args, **kwargs
                ),
                client_options=OpenAIClientOptions,
            ),
        ),
        Provider.COHERE: (
            Client(provider=Provider.COHERE, kind=ProviderKind.AGENT, origin="pydantic-ai"),
            Client(
                provider=Provider.COHERE,
                kind=ProviderKind.EMBEDDING,
                origin="codeweaver",
                client=lazy_import("cohere", "AsyncClientV2"),
                provider_class=lazy_import(
                    "codeweaver.providers.embedding.providers.cohere", "CohereEmbeddingProvider"
                ),
                client_options=CohereClientOptions,
            ),
            Client(
                provider=Provider.COHERE,
                kind=ProviderKind.RERANKING,
                origin="codeweaver",
                client=lazy_import("cohere", "AsyncClientV2"),
                provider_class=lazy_import(
                    "codeweaver.providers.reranking.providers.cohere", "CohereRerankingProvider"
                ),
                client_options=CohereClientOptions,
            ),
        ),
        Provider.DEEPSEEK: (
            Client(provider=Provider.DEEPSEEK, kind=ProviderKind.AGENT, origin="pydantic-ai"),
        ),
        Provider.DUCKDUCKGO: (
            Client(provider=Provider.DUCKDUCKGO, kind=ProviderKind.DATA, origin="pydantic-ai"),
        ),
        Provider.FASTEMBED: (
            Client(
                provider=Provider.FASTEMBED,
                kind=ProviderKind.EMBEDDING,
                origin="codeweaver",
                client=lazy_import(
                    "codeweaver.providers.embedding.fastembed_extensions", "get_text_embedder"
                ),
                provider_class=lazy_import(
                    "codeweaver.providers.embedding.providers.fastembed",
                    "FastEmbedEmbeddingProvider",
                ),
                client_options=FastEmbedClientOptions,
            ),
            Client(
                provider=Provider.FASTEMBED,
                kind=ProviderKind.SPARSE_EMBEDDING,
                origin="codeweaver",
                client=lazy_import("fastembed", "SparseTextEmbedding"),
                provider_class=lazy_import(
                    "codeweaver.providers.embedding.providers.fastembed", "FastEmbedSparseProvider"
                ),
                client_options=FastEmbedClientOptions,
            ),
            Client(
                provider=Provider.FASTEMBED,
                kind=ProviderKind.RERANKING,
                origin="codeweaver",
                client=lazy_import("fastembed.rerank.cross_encoder", "TextCrossEncoder"),
                provider_class=lazy_import(
                    "codeweaver.providers.reranking.providers.fastembed",
                    "FastEmbedRerankingProvider",
                ),
                client_options=FastEmbedClientOptions,
            ),
        ),
        Provider.FIREWORKS: (
            Client(provider=Provider.FIREWORKS, kind=ProviderKind.AGENT, origin="pydantic-ai"),
            Client(
                provider=Provider.FIREWORKS,
                kind=ProviderKind.EMBEDDING,
                origin="codeweaver",
                client=lazy_import("openai", "AsyncOpenAI"),
                provider_class=FACTORY_IMPORT,
                provider_factory=lambda *args, **kwargs: FACTORY_IMPORT.get_provider_class(
                    *args, **kwargs
                ),
                client_options=OpenAIClientOptions,
            ),
        ),
        Provider.GITHUB: (
            Client(provider=Provider.GITHUB, kind=ProviderKind.AGENT, origin="pydantic-ai"),
            Client(
                provider=Provider.GITHUB,
                kind=ProviderKind.EMBEDDING,
                origin="codeweaver",
                client=lazy_import("openai", "AsyncOpenAI"),
                provider_class=FACTORY_IMPORT,
                provider_factory=lambda *args, **kwargs: FACTORY_IMPORT.get_provider_class(
                    *args, **kwargs
                ),
                client_options=OpenAIClientOptions,
            ),
        ),
        Provider.GOOGLE: (
            Client(provider=Provider.GOOGLE, kind=ProviderKind.AGENT, origin="pydantic-ai"),
            Client(
                provider=Provider.GOOGLE,
                kind=ProviderKind.EMBEDDING,
                origin="codeweaver",
                client=lazy_import("google.genai", "Client"),
                provider_class=lazy_import(
                    "codeweaver.providers.embedding.providers.google", "GoogleEmbeddingProvider"
                ),
                client_options=GoogleClientOptions,
            ),
        ),
        Provider.GROQ: (
            Client(provider=Provider.GROQ, kind=ProviderKind.AGENT, origin="pydantic-ai"),
            Client(
                provider=Provider.GROQ,
                kind=ProviderKind.EMBEDDING,
                origin="codeweaver",
                client=lazy_import("openai", "AsyncOpenAI"),
                provider_class=FACTORY_IMPORT,
                provider_factory=lambda *args, **kwargs: FACTORY_IMPORT.get_provider_class(
                    *args, **kwargs
                ),
                client_options=OpenAIClientOptions,
            ),
        ),
        Provider.HEROKU: (
            Client(provider=Provider.HEROKU, kind=ProviderKind.AGENT, origin="pydantic-ai"),
            Client(
                provider=Provider.HEROKU,
                kind=ProviderKind.EMBEDDING,
                origin="codeweaver",
                client=lazy_import("openai", "AsyncOpenAI"),
                provider_class=FACTORY_IMPORT,
                provider_factory=lambda *args, **kwargs: FACTORY_IMPORT.get_provider_class(
                    *args, **kwargs
                ),
                client_options=OpenAIClientOptions,
            ),
        ),
        Provider.HUGGINGFACE_INFERENCE: (
            Client(
                provider=Provider.HUGGINGFACE_INFERENCE,
                kind=ProviderKind.AGENT,
                origin="pydantic-ai",
            ),
            Client(
                provider=Provider.HUGGINGFACE_INFERENCE,
                kind=ProviderKind.EMBEDDING,
                origin="codeweaver",
                client=lazy_import("huggingface_hub", "AsyncInferenceClient"),
                provider_class=lazy_import(
                    "codeweaver.providers.embedding.providers.huggingface_inference",
                    "HuggingFaceEmbeddingProvider",
                ),
                client_options=HFInferenceClientOptions,
            ),
        ),
        Provider.LITELLM: (
            Client(provider=Provider.LITELLM, kind=ProviderKind.AGENT, origin="pydantic-ai"),
        ),  # Not implemented yet for embedding/reranking
        Provider.MISTRAL: (
            Client(provider=Provider.MISTRAL, kind=ProviderKind.AGENT, origin="pydantic-ai"),
            Client(
                provider=Provider.MISTRAL,
                kind=ProviderKind.EMBEDDING,
                origin="codeweaver",
                client=lazy_import("mistralai", "Mistral"),
                provider_class=lazy_import(
                    "codeweaver.providers.embedding.providers.mistral", "MistralEmbeddingProvider"
                ),
                client_options=MistralClientOptions,
            ),
        ),
        Provider.MOONSHOT: (
            Client(provider=Provider.MOONSHOT, kind=ProviderKind.AGENT, origin="pydantic-ai"),
        ),
        Provider.OLLAMA: (
            Client(provider=Provider.OLLAMA, kind=ProviderKind.AGENT, origin="pydantic-ai"),
            Client(
                provider=Provider.OLLAMA,
                kind=ProviderKind.EMBEDDING,
                origin="codeweaver",
                client=lazy_import("openai", "AsyncOpenAI"),
                provider_class=FACTORY_IMPORT,
                provider_factory=lambda *args, **kwargs: FACTORY_IMPORT.get_provider_class(
                    *args, **kwargs
                ),
                client_options=OpenAIClientOptions,
            ),
        ),
        Provider.OPENAI: (
            Client(provider=Provider.OPENAI, kind=ProviderKind.AGENT, origin="pydantic-ai"),
            Client(
                provider=Provider.OPENAI,
                kind=ProviderKind.EMBEDDING,
                origin="codeweaver",
                client=lazy_import("openai", "AsyncOpenAI"),
                provider_class=FACTORY_IMPORT,
                provider_factory=lambda *args, **kwargs: FACTORY_IMPORT.get_provider_class(
                    *args, **kwargs
                ),
                client_options=OpenAIClientOptions,
            ),
        ),
        Provider.OPENROUTER: (
            Client(provider=Provider.OPENROUTER, kind=ProviderKind.AGENT, origin="pydantic-ai"),
        ),
        Provider.PERPLEXITY: (
            Client(provider=Provider.PERPLEXITY, kind=ProviderKind.AGENT, origin="pydantic-ai"),
        ),
        Provider.SENTENCE_TRANSFORMERS: (
            Client(
                provider=Provider.SENTENCE_TRANSFORMERS,
                kind=ProviderKind.EMBEDDING,
                origin="codeweaver",
                client=lazy_import("sentence_transformers", "SentenceTransformer"),
                provider_class=lazy_import(
                    "codeweaver.providers.embedding.providers.sentence_transformers",
                    "SentenceTransformersEmbeddingProvider",
                ),
                client_options=SentenceTransformersClientOptions,
            ),
            Client(
                provider=Provider.SENTENCE_TRANSFORMERS,
                kind=ProviderKind.SPARSE_EMBEDDING,
                origin="codeweaver",
                client=lazy_import("sentence_transformers", "SparseEncoder"),
                provider_class=lazy_import(
                    "codeweaver.providers.embedding.providers.sentence_transformers",
                    "SentenceTransformersSparseProvider",
                ),
                client_options=SentenceTransformersClientOptions,
            ),
            Client(
                provider=Provider.SENTENCE_TRANSFORMERS,
                kind=ProviderKind.RERANKING,
                origin="codeweaver",
                client=lazy_import("sentence_transformers", "CrossEncoder"),
                provider_class=lazy_import(
                    "codeweaver.providers.reranking.providers.sentence_transformers",
                    "SentenceTransformersRerankingProvider",
                ),
                client_options=SentenceTransformersClientOptions,
            ),
        ),
        Provider.TAVILY: (
            Client(provider=Provider.TAVILY, kind=ProviderKind.DATA, origin="pydantic-ai"),
        ),
        Provider.TOGETHER: (
            Client(provider=Provider.TOGETHER, kind=ProviderKind.AGENT, origin="pydantic-ai"),
            Client(
                provider=Provider.TOGETHER,
                kind=ProviderKind.EMBEDDING,
                origin="codeweaver",
                client=lazy_import("openai", "AsyncOpenAI"),
                provider_class=FACTORY_IMPORT,
                provider_factory=lambda *args, **kwargs: FACTORY_IMPORT.get_provider_class(
                    *args, **kwargs
                ),
                client_options=OpenAIClientOptions,
            ),
        ),
        Provider.VERCEL: (
            Client(provider=Provider.VERCEL, kind=ProviderKind.AGENT, origin="pydantic-ai"),
            Client(
                provider=Provider.VERCEL,
                kind=ProviderKind.EMBEDDING,
                origin="codeweaver",
                client=lazy_import("openai", "AsyncOpenAI"),
                provider_class=FACTORY_IMPORT,
                provider_factory=lambda *args, **kwargs: FACTORY_IMPORT.get_provider_class(
                    *args, **kwargs
                ),
                client_options=OpenAIClientOptions,
            ),
        ),
        Provider.VOYAGE: (
            Client(
                provider=Provider.VOYAGE,
                kind=ProviderKind.EMBEDDING,
                origin="codeweaver",
                client=lazy_import("voyageai.client_async", "AsyncClient"),
                provider_class=lazy_import(
                    "codeweaver.providers.embedding.providers.voyage", "VoyageEmbeddingProvider"
                ),
                client_options=VoyageClientOptions,
            ),
            Client(
                provider=Provider.VOYAGE,
                kind=ProviderKind.RERANKING,
                origin="codeweaver",
                client=lazy_import("voyageai.client_async", "AsyncClient"),
                provider_class=lazy_import(
                    "codeweaver.providers.reranking.providers.voyage", "VoyageRerankingProvider"
                ),
                client_options=VoyageClientOptions,
            ),
        ),
        Provider.X_AI: (
            Client(provider=Provider.X_AI, kind=ProviderKind.AGENT, origin="pydantic-ai"),
        ),
    }),
)


def get_client_map(provider: LiteralProvider) -> tuple[Client, ...]:
    """Get the full client map as a flat tuple."""
    return CLIENT_MAP.get(provider, ())


__all__ = ("CLIENT_MAP", "PROVIDER_CAPABILITIES", "VECTOR_PROVIDER_CAPABILITIES")
