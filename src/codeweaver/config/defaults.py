# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Default provider settings for CodeWeaver."""

from __future__ import annotations

import logging

from importlib import util
from typing import NamedTuple

from codeweaver.config.chunker import ChunkerSettings
from codeweaver.config.indexing import IndexerSettings
from codeweaver.config.middleware import (
    ErrorHandlingMiddlewareSettings,
    LoggingMiddlewareSettings,
    MiddlewareOptions,
    RateLimitingMiddlewareSettings,
    RetryMiddlewareSettings,
)
from codeweaver.config.providers import (
    AgentModelSettings,
    AgentProviderSettings,
    DataProviderSettings,
    EmbeddingModelSettings,
    EmbeddingProviderSettings,
    QdrantConfig,
    RerankingModelSettings,
    RerankingProviderSettings,
    SparseEmbeddingModelSettings,
    SparseEmbeddingProviderSettings,
    VectorStoreProviderSettings,
)
from codeweaver.config.telemetry import TelemetrySettings
from codeweaver.config.types import (
    ChunkerSettingsDict,
    EndpointSettingsDict,
    FastMcpServerSettingsDict,
    IndexerSettingsDict,
    TelemetrySettingsDict,
    UvicornServerSettings,
    UvicornServerSettingsDict,
)
from codeweaver.providers.provider import Provider


logger = logging.getLogger(__name__)


DefaultDataProviderSettings = (
    DataProviderSettings(provider=Provider.TAVILY, enabled=False, api_key=None, other=None),
    # DuckDuckGo
    DataProviderSettings(provider=Provider.DUCKDUCKGO, enabled=True, api_key=None, other=None),
)


class DeterminedDefaults(NamedTuple):
    """Tuple for determined default embedding settings."""

    provider: Provider
    model: str
    enabled: bool


def _get_default_embedding_settings() -> DeterminedDefaults:
    """Determine the default embedding provider, model, and enabled status based on available libraries."""
    for lib in (
        "voyageai",
        "mistral",
        "google",
        "fastembed_gpu",
        "fastembed",
        "sentence_transformers",
    ):
        if util.find_spec(lib) is not None:
            # all three of the top defaults are extremely capable
            if lib == "voyageai":
                return DeterminedDefaults(
                    provider=Provider.VOYAGE, model="voyage:voyage-code-3", enabled=True
                )
            if lib == "mistral":
                return DeterminedDefaults(
                    provider=Provider.MISTRAL, model="mistral:codestral-embed", enabled=True
                )
            if lib == "google":
                return DeterminedDefaults(
                    provider=Provider.GOOGLE, model="google/gemini-embedding-001", enabled=True
                )
            if lib in {"fastembed_gpu", "fastembed"}:
                return DeterminedDefaults(
                    # showing its age but it's still a solid lightweight option
                    provider=Provider.FASTEMBED,
                    model="fastembed:BAAI/bge-small-en-v1.5",
                    enabled=True,
                )
            if lib == "sentence_transformers":
                return DeterminedDefaults(
                    provider=Provider.SENTENCE_TRANSFORMERS,
                    # embedding-small-english-r2 is *very lightweight* and quite capable with a good context window (8192 tokens)
                    model="sentence-transformers:ibm-granite/granite-embedding-small-english-r2",
                    enabled=True,
                )
    logger.warning(
        "No default embedding provider libraries found. Embedding functionality will be disabled unless explicitly set in your config or environment variables."
    )
    return DeterminedDefaults(provider=Provider.NOT_SET, model="NONE", enabled=False)


_embedding_defaults = _get_default_embedding_settings()

DefaultEmbeddingProviderSettings = (
    EmbeddingProviderSettings(
        provider=_embedding_defaults.provider,
        enabled=_embedding_defaults.enabled,
        model_settings=EmbeddingModelSettings(model=_embedding_defaults.model),
    ),
)


def _get_default_sparse_embedding_settings() -> DeterminedDefaults:
    """Determine the default sparse embedding provider, model, and enabled status based on available libraries."""
    for lib in ("sentence_transformers", "fastembed_gpu", "fastembed"):
        if util.find_spec(lib) is not None:
            if lib == "sentence_transformers":
                return DeterminedDefaults(
                    provider=Provider.SENTENCE_TRANSFORMERS,
                    model="opensearch:opensearch-neural-sparse-encoding-doc-v3-gte",
                    enabled=True,
                )
            if lib in {"fastembed_gpu", "fastembed"}:
                return DeterminedDefaults(
                    provider=Provider.FASTEMBED, model="prithivida/Splade_PP_en_v2", enabled=True
                )
    # Sentence-Transformers and Fastembed are the *only* sparse embedding options we support
    logger.warning(
        "No sparse embedding provider libraries found. Sparse embedding functionality disabled."
    )
    return DeterminedDefaults(provider=Provider.NOT_SET, model="NONE", enabled=False)


_sparse_embedding_defaults = _get_default_sparse_embedding_settings()

DefaultSparseEmbeddingProviderSettings = (
    SparseEmbeddingProviderSettings(
        provider=_sparse_embedding_defaults.provider,
        enabled=_sparse_embedding_defaults.enabled,
        model_settings=SparseEmbeddingModelSettings(model=_sparse_embedding_defaults.model),
    ),
)


def _get_default_reranking_settings() -> DeterminedDefaults:
    """Determine the default reranking provider, model, and enabled status based on available libraries."""
    for lib in ("voyageai", "fastembed_gpu", "fastembed", "sentence_transformers"):
        if util.find_spec(lib) is not None:
            if lib == "voyageai":
                return DeterminedDefaults(
                    provider=Provider.VOYAGE, model="voyage:rerank-2.5", enabled=True
                )
            if lib in {"fastembed_gpu", "fastembed"}:
                return DeterminedDefaults(
                    provider=Provider.FASTEMBED,
                    model="fastembed:jinaai/jina-reranking-v2-base-multilingual",
                    enabled=True,
                )
            if lib == "sentence_transformers":
                return DeterminedDefaults(
                    provider=Provider.SENTENCE_TRANSFORMERS,
                    # on the heavier side for what we aim for as a default but very capable
                    model="sentence-transformers:BAAI/bge-reranking-v2-m3",
                    enabled=True,
                )
    logger.warning(
        "No default reranking provider libraries found. Reranking functionality will be disabled unless explicitly set in your config or environment variables."
    )
    return DeterminedDefaults(provider=Provider.NOT_SET, model="NONE", enabled=False)


_reranking_defaults = _get_default_reranking_settings()

DefaultRerankingProviderSettings = (
    RerankingProviderSettings(
        provider=_reranking_defaults.provider,
        enabled=_reranking_defaults.enabled,
        model_settings=RerankingModelSettings(model=_reranking_defaults.model),
    ),
)

HAS_ANTHROPIC = util.find_spec("anthropic") is not None
DefaultAgentProviderSettings = (
    AgentProviderSettings(
        provider=Provider.ANTHROPIC,
        enabled=HAS_ANTHROPIC,
        model="claude-sonnet-4-latest",
        model_settings=AgentModelSettings(),
    ),
)

DefaultMiddlewareSettings = MiddlewareOptions(
    error_handling=ErrorHandlingMiddlewareSettings(
        include_traceback=True, error_callback=None, transform_errors=False
    ),
    retry=RetryMiddlewareSettings(
        max_retries=5, base_delay=1.0, max_delay=60.0, backoff_multiplier=2.0
    ),
    logging=LoggingMiddlewareSettings(log_level=20, include_payloads=False),
    rate_limiting=RateLimitingMiddlewareSettings(
        max_requests_per_second=75, get_client_id=None, burst_capacity=150, global_limit=True
    ),
)

DefaultVectorStoreProviderSettings = (
    VectorStoreProviderSettings(
        provider=Provider.QDRANT, enabled=True, provider_settings=QdrantConfig()
    ),
)

DefaultFastMcpServerSettings = FastMcpServerSettingsDict(
    transport="http",
    auth=None,
    on_duplicate_tools="warn",
    on_duplicate_resources="warn",
    on_duplicate_prompts="warn",
    resource_prefix_format="path",
    middleware=[],
    tools=[],
)
DefaultEndpointSettings = EndpointSettingsDict(
    enable_health=True, enable_metrics=True, enable_settings=True, enable_version=True
)  # type: ignore
DefaultIndexerSettings = IndexerSettingsDict(IndexerSettings().model_dump(exclude_none=True))  # type: ignore
DefaultChunkerSettings = ChunkerSettingsDict(ChunkerSettings().model_dump(exclude_none=True))  # type: ignore
DefaultTelemetrySettings = TelemetrySettingsDict(TelemetrySettings().model_dump(exclude_none=True))  # type: ignore
DefaultUvicornSettings = UvicornServerSettingsDict(
    UvicornServerSettings().model_dump(exclude_none=True)  # type: ignore
)

__all__ = (
    "DefaultAgentProviderSettings",
    "DefaultChunkerSettings",
    "DefaultDataProviderSettings",
    "DefaultEmbeddingProviderSettings",
    "DefaultEndpointSettings",
    "DefaultFastMcpServerSettings",
    "DefaultIndexerSettings",
    "DefaultMiddlewareSettings",
    "DefaultRerankingProviderSettings",
    "DefaultSparseEmbeddingProviderSettings",
    "DefaultTelemetrySettings",
    "DefaultUvicornSettings",
    "DefaultVectorStoreProviderSettings",
)
