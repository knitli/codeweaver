# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Prebuilt settings profiles for CodeWeaver quick setup.

A few important things to note about profiles (or any provider settings):
- Most providers are *not* available with the default installation of CodeWeaver. CodeWeaver has multiple install paths that include different sets of providers. The `recommended` install flag (`pip install codeweaver[recommended]`) includes *most* of the providers available in CodeWeaver, but not all.
The `full` or `full-gpu` install flags (`pip install codeweaver[full]` or `pip install codeweaver[full-gpu]`) include *all* providers, and all optional dependencies, such as auth providers and GPU support (for the gpu flag).
The recommended flag gives you access to:
    - All current vector, agent and data providers
    - All embedding and reranking providers except for Sentence Transformers (because these install paths are aligned with pydantic-ai's default dependencies, and Sentence Transformers is not a default dependency of pydantic-ai).
- A-la-Carte installations: You can also use the `required-core` install flag (`pip install codeweaver[required-core]`) to install only the core dependencies of CodeWeaver, and then add individual providers using their own install flags (all prefixed with `provider-`), like:
    `pip install codeweaver[required-core,provider-openai,provider-qdrant]`

"""

import contextlib

from importlib import util
from typing import Literal, overload

from pydantic import AnyHttpUrl

from codeweaver.common.utils.git import get_project_path
from codeweaver.common.utils.utils import get_user_config_dir
from codeweaver.config.providers import (
    AgentModelSettings,
    AgentProviderSettings,
    DataProviderSettings,
    EmbeddingModelSettings,
    EmbeddingProviderSettings,
    MemoryConfig,
    ProviderSettingsDict,
    QdrantConfig,
    RerankingModelSettings,
    RerankingProviderSettings,
    SparseEmbeddingModelSettings,
    SparseEmbeddingProviderSettings,
    VectorStoreProviderSettings,
)
from codeweaver.core.stores import get_blake_hash


def _default_local_vector_config() -> QdrantConfig:
    """Default local vector store configuration for Qdrant."""
    return QdrantConfig(prefer_grpc=True, url="http://localhost:6334")


def _default_remote_vector_config(url: AnyHttpUrl) -> QdrantConfig:
    """Default remote vector store configuration for Qdrant."""
    return QdrantConfig(prefer_grpc=True, url=str(url))


def _get_vector_config(
    vector_deployment: Literal["cloud", "local"], *, url: AnyHttpUrl | None = None
) -> QdrantConfig:
    if vector_deployment != "cloud":
        return _default_local_vector_config()
    if url is None:
        raise ValueError("You must provide a URL for cloud vector store deployment.")
    return _default_remote_vector_config(url)


@overload
def get_profile(
    profile: Literal["recommended", "quickstart", "backup"],
    vector_deployment: Literal["local"],
    *,
    url: AnyHttpUrl | None = None,
) -> ProviderSettingsDict: ...
@overload
def get_profile(
    profile: Literal["recommended", "quickstart", "backup"],
    vector_deployment: Literal["cloud"],
    *,
    url: AnyHttpUrl,
) -> ProviderSettingsDict: ...
def get_profile(
    profile: Literal["recommended", "quickstart", "backup"],
    vector_deployment: Literal["cloud", "local"],
    *,
    url: AnyHttpUrl | None = None,
) -> ProviderSettingsDict:
    """Get the default provider settings profile.

    Args:
        profile: The profile name, either "recommended" or "quickstart".
        vector_deployment: The vector store deployment type, either "cloud" or "local".
        url: The URL for the vector store if using cloud deployment.

    Returns:
        The provider settings dictionary for the specified profile.
    """
    if profile == "backup":
        return _backup_profile()
    if profile == "recommended":
        return _recommended_default(vector_deployment, url=url)
    if profile == "quickstart":
        return _quickstart_default(vector_deployment, url=url)
    raise ValueError(f"Unknown profile: {profile}")


def _vector_client_opts(*, remote: bool) -> dict[str, object]:
    """Get vector client options based on deployment type."""
    if remote:
        grpc = None
        with contextlib.suppress(ImportError):
            import grpc
        if compression := getattr(grpc, "Compression", None):
            compression = compression.Gzip
        return {"grpc_compression": compression}
    return {}


def _recommended_default(
    vector_deployment: Literal["cloud", "local"], *, url: AnyHttpUrl | None = None
) -> ProviderSettingsDict:
    """Recommended default settings profile.

    This profile leans towards high-quality providers, but without excessive cost or setup. Voyage AI used for embeddings and reranking, which has a generous free tier and class-leading performance. Qdrant can be deployed locally for free or as a cloud service with a generous free tier. Anthropic Claude Haiku is used for agents, which has a strong balance of cost and performance.
    """
    from codeweaver.providers.provider import Provider

    return ProviderSettingsDict(
        embedding=(
            EmbeddingProviderSettings(
                model_settings=EmbeddingModelSettings(model="voyage-code-3"),
                provider=Provider.VOYAGE,
                enabled=True,
            ),
        ),
        reranking=(
            RerankingProviderSettings(
                provider=Provider.VOYAGE,
                enabled=True,
                model_settings=RerankingModelSettings(model="voyage-rerank-2.5"),
            ),
        ),
        agent=(
            AgentProviderSettings(
                provider=Provider.ANTHROPIC,
                enabled=True,
                model="claude-haiku-4.5",
                model_settings=AgentModelSettings(),
            ),
        ),
        data=(
            DataProviderSettings(provider=Provider.TAVILY, enabled=True),
            DataProviderSettings(provider=Provider.DUCKDUCKGO, enabled=True),
        ),
        vector_store=VectorStoreProviderSettings(
            provider=Provider.QDRANT,
            enabled=True,
            provider_settings=_get_vector_config(vector_deployment, url=url),
        ),
    )


HAS_ST = util.find_spec("sentence_transformers") is not None


def _quickstart_default(
    vector_deployment: Literal["local", "cloud"], *, url: AnyHttpUrl | None = None
) -> ProviderSettingsDict:
    """Quickstart default settings profile.

    This profile uses free-tier or open-source providers to allow for immediate use without cost.
    """
    from codeweaver.providers.provider import Provider

    return ProviderSettingsDict(
        embedding=(
            EmbeddingProviderSettings(
                model_settings=EmbeddingModelSettings(
                    model="ibm-granite/granite-embedding-small-english-r2"
                    if HAS_ST
                    else "Alibaba-NLP/gte-modernbert-base"
                ),
                provider=Provider.SENTENCE_TRANSFORMERS if HAS_ST else Provider.FASTEMBED,
                enabled=True,
            ),
        ),
        sparse_embedding=(
            SparseEmbeddingProviderSettings(
                provider=Provider.SENTENCE_TRANSFORMERS if HAS_ST else Provider.FASTEMBED,
                enabled=True,
                model_settings=SparseEmbeddingModelSettings(
                    model="opensearch/openensearch-neural-sparse-encoding-doc-v3-gte"
                    if HAS_ST
                    else "prithivida/Splade_PP_en_v1"
                ),
            ),
        ),
        reranking=(
            RerankingProviderSettings(
                provider=Provider.SENTENCE_TRANSFORMERS if HAS_ST else Provider.FASTEMBED,
                enabled=True,
                model_settings=RerankingModelSettings(
                    model="BAAI/bge-reranking-v2-m3"
                    if HAS_ST
                    else "jinaai/jina-reranking-v2-base-multilingual"
                ),
            ),
        ),
        agent=(
            AgentProviderSettings(
                provider=Provider.ANTHROPIC,
                enabled=True,
                model="claude-haiku-4.5",
                model_settings=AgentModelSettings(),
            ),
        ),
        data=(
            DataProviderSettings(provider=Provider.TAVILY, enabled=True),
            DataProviderSettings(provider=Provider.DUCKDUCKGO, enabled=True),
        ),
        vector_store=VectorStoreProviderSettings(
            provider=Provider.QDRANT,
            enabled=True,
            provider_settings=_get_vector_config(vector_deployment, url=url),
        ),
    )


def _backup_profile() -> ProviderSettingsDict:
    from codeweaver.providers.provider import Provider

    return ProviderSettingsDict(
        **(
            _quickstart_default("local")
            | {
                "embedding": EmbeddingProviderSettings(
                    provider=Provider.SENTENCE_TRANSFORMERS if HAS_ST else Provider.FASTEMBED,
                    enabled=True,
                    model_settings=EmbeddingModelSettings(
                        model="BAAI/ibm-granite/granite-embedding-small-english-r2"
                        if HAS_ST
                        else "Alibaba-NLP/gte-modernbert-base",
                        dimension=384 if HAS_ST else 768,
                        data_type="int8",
                    ),
                )
            }
            | {
                "vector_store": VectorStoreProviderSettings(
                    provider=Provider.MEMORY,
                    enabled=True,
                    provider_settings=MemoryConfig(
                        persist_path=get_user_config_dir() / "vectors/backup",
                        collection_name=f"{get_project_path().name}-{get_blake_hash(str(get_project_path()).encode('utf-8'))[:8]}-backup",
                    ),
                )
            }
        )
    )


__all__ = ("get_profile",)
