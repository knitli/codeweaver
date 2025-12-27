# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Metadata about provider capabilities for all provider kinds in CodeWeaver.

This module's capabilities are high-level and not specific to any model or version, focused on overall provider services. For more granular capabilities,
"""

from __future__ import annotations

from collections.abc import Callable
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Literal, NamedTuple, cast

from codeweaver.core import LazyImport, lazy_import
from codeweaver.core.types.provider import PROVIDER_CAPABILITIES, Provider, ProviderKind


if TYPE_CHECKING:
    from codeweaver.providers.embedding.providers.openai_factory import OpenAIEmbeddingBase
    from codeweaver.providers.types import LiteralProvider, LiteralProviderKind


VECTOR_PROVIDER_CAPABILITIES: MappingProxyType[LiteralProvider, str] = cast(
    "MappingProxyType[LiteralProvider, str]", MappingProxyType({Provider.QDRANT: "placeholder"})
)


FACTORY_IMPORT: LazyImport[OpenAIEmbeddingBase] = lazy_import(
    "codeweaver.providers.embedding.providers.openai_factory", "OpenAIEmbeddingBase"
)


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
            ),
            Client(
                provider=Provider.BEDROCK,
                kind=ProviderKind.RERANKING,
                origin="codeweaver",
                client=lazy_import("boto3", "client"),  # bedrock-runtime
                provider_class=lazy_import(
                    "codeweaver.providers.reranking.providers.bedrock", "BedrockRerankingProvider"
                ),
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
            ),
            Client(
                provider=Provider.COHERE,
                kind=ProviderKind.RERANKING,
                origin="codeweaver",
                client=lazy_import("cohere", "AsyncClientV2"),
                provider_class=lazy_import(
                    "codeweaver.providers.reranking.providers.cohere", "CohereRerankingProvider"
                ),
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
            ),
            Client(
                provider=Provider.FASTEMBED,
                kind=ProviderKind.SPARSE_EMBEDDING,
                origin="codeweaver",
                client=lazy_import("fastembed", "SparseTextEmbedding"),
                provider_class=lazy_import(
                    "codeweaver.providers.embedding.providers.fastembed", "FastEmbedSparseProvider"
                ),
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
            ),
            Client(
                provider=Provider.VOYAGE,
                kind=ProviderKind.RERANKING,
                origin="codeweaver",
                client=lazy_import("voyageai.client_async", "AsyncClient"),
                provider_class=lazy_import(
                    "codeweaver.providers.reranking.providers.voyage", "VoyageRerankingProvider"
                ),
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
