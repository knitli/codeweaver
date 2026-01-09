# sourcery skip: lambdas-should-be-short, no-complex-if-expressions
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Prebuilt settings profiles for CodeWeaver quick setup.

A few important things to note about profiles (or any provider settings):
- Most providers are *not* available with the default installation of CodeWeaver. CodeWeaver has multiple install paths that include different sets of providers. The `recommended` install flag (`pip install code-weaver[recommended]`) includes *most* of the providers available in CodeWeaver, but not all.
The `full` or `full-gpu` install flags (`pip install code-weaver[full]` or `pip install code-weaver[full-gpu]`) include *all* providers, and all optional dependencies, such as auth providers and GPU support (for the gpu flag).
The recommended flag gives you access to:
    - All current vector, agent and data providers
    - All embedding and reranking providers except for Sentence Transformers (because these install paths are aligned with pydantic-ai's default dependencies, and Sentence Transformers is not a default dependency of pydantic-ai).
- A-la-Carte installations: You can also use the `required-core` install flag (`pip install code-weaver[required-core]`) to install only the core dependencies of CodeWeaver, and then add individual providers using their own install flags, like:
    `pip install code-weaver[required-core,openai,qdrant]`

"""

from __future__ import annotations

import contextlib
import os

from importlib import util
from pathlib import Path
from typing import Any, Literal, overload

from pydantic import AnyHttpUrl
from pydantic.dataclasses import as_dict
from pydantic_ai.settings import ModelSettings as AgentModelSettings

from codeweaver.core import BaseDataclassEnum, Provider
from codeweaver.core.utils.filesystem import get_user_data_dir
from codeweaver.providers.config.clients import QdrantClientOptions
from codeweaver.providers.config.embedding import (
    FastEmbedEmbeddingConfig,
    FastEmbedSparseEmbeddingConfig,
    SentenceTransformersEmbeddingConfig,
    SentenceTransformersSparseEmbeddingConfig,
    VoyageEmbeddingConfig,
)
from codeweaver.providers.config.kinds import (
    AgentProviderSettings,
    DataProviderSettings,
    EmbeddingProviderSettings,
    MemoryConfig,
    QdrantVectorStoreProviderSettings,
    RerankingProviderSettings,
    SparseEmbeddingProviderSettings,
)
from codeweaver.providers.config.providers import ProviderSettingsDict
from codeweaver.providers.config.reranking import (
    FastEmbedRerankingConfig,
    SentenceTransformersRerankingConfig,
    VoyageRerankingConfig,
)


def _default_local_vector_client_options() -> QdrantClientOptions:
    """Default local vector store configuration for Qdrant."""
    return QdrantClientOptions(prefer_grpc=False, host="localhost", port=6333)


def _default_remote_vector_client_options(url: AnyHttpUrl) -> QdrantClientOptions:
    """Default remote vector store configuration for Qdrant."""
    return QdrantClientOptions(prefer_grpc=False, url=url)


def _get_vector_client_options(
    vector_deployment: Literal["cloud", "local"], *, url: AnyHttpUrl | None = None
) -> QdrantClientOptions:
    if vector_deployment != "cloud":
        return _default_local_vector_client_options()
    if url is None:
        raise ValueError("You must provide a URL for cloud vector store deployment.")
    return _default_remote_vector_client_options(url)


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


HAS_ST = util.find_spec("sentence_transformers") is not None


def _recommended_default(
    vector_deployment: Literal["cloud", "local"], *, url: AnyHttpUrl | None = None
) -> ProviderSettingsDict:
    """Recommended default settings profile.

    This profile leans towards high-quality providers, but without excessive cost or setup. It uses Voyage AI for embeddings and rerankings, which has a generous free tier and class-leading performance. Qdrant can be deployed locally for free or as a cloud service with a generous free tier. Anthropic Claude Haiku is used for agents, which has a strong balance of cost and performance.
    """
    from codeweaver.core import Provider

    return ProviderSettingsDict(
        embedding=(
            EmbeddingProviderSettings(
                model_name="voyage-code-3",
                embedding_config=VoyageEmbeddingConfig(model_name="voyage-code-3"),
                provider=Provider.VOYAGE,
            ),
        ),
        sparse_embedding=(
            SparseEmbeddingProviderSettings(
                provider=Provider.FASTEMBED,
                # Splade is a strong sparse embedding model that works well for code search
                # Splade models are slow to generate embeddings, but lightning fast at inference time
                # This version comes without license complications associated with `naver`'s versions
                # There is a v2 available, but not yet supported by FastEmbed
                model_name="prithivida/Splade_PP_en_v1",
                sparse_embedding_config=FastEmbedSparseEmbeddingConfig(
                    model_name="prithivida/Splade_PP_en_v1"
                ),
            ),
        ),
        reranking=(
            RerankingProviderSettings(
                provider=Provider.VOYAGE,
                model_name="voyage-rerank-2.5",
                reranking_config=VoyageRerankingConfig(model_name="voyage-rerank-2.5"),
            ),
        ),
        agent=(
            AgentProviderSettings(
                provider=Provider.ANTHROPIC,
                model="claude-haiku-4.5",
                model_options=AgentModelSettings(),
            ),
        ),
        data=(
            DataProviderSettings(provider=Provider.TAVILY),
            DataProviderSettings(provider=Provider.DUCKDUCKGO),
        ),
        vector_store=QdrantVectorStoreProviderSettings(
            provider=Provider.QDRANT,
            client_options=_get_vector_client_options(vector_deployment, url=url),
        ),
    )


def _quickstart_default(
    vector_deployment: Literal["local", "cloud"], *, url: AnyHttpUrl | None = None
) -> ProviderSettingsDict:
    """Quickstart default settings profile.

    This profile uses free-tier or open-source providers to allow for immediate use without cost.
    """
    from codeweaver.core import Provider

    embedding_model = (
        "ibm-granite/granite-embedding-small-english-r2" if HAS_ST else "BAAI/bge-small-en-v1.5"
    )
    sparse_model = (
        "opensearch/opensearch-neural-sparse-encoding-doc-v3-gte"
        if HAS_ST
        else "prithivida/Splade_PP_en_v1"
    )
    reranking_model = (
        "BAAI/bge-reranking-v2-m3" if HAS_ST else "jinaai/jina-reranking-v2-base-multilingual"
    )

    return ProviderSettingsDict(
        embedding=(
            EmbeddingProviderSettings(
                model_name=embedding_model,
                embedding_config=(
                    SentenceTransformersEmbeddingConfig(model_name=embedding_model)
                    if HAS_ST
                    else FastEmbedEmbeddingConfig(model_name=embedding_model)
                ),
                provider=(Provider.SENTENCE_TRANSFORMERS if HAS_ST else Provider.FASTEMBED),
            ),
        ),
        sparse_embedding=(
            SparseEmbeddingProviderSettings(
                provider=(Provider.SENTENCE_TRANSFORMERS if HAS_ST else Provider.FASTEMBED),
                model_name=sparse_model,
                sparse_embedding_config=(
                    SentenceTransformersSparseEmbeddingConfig(model_name=sparse_model)
                    if HAS_ST
                    else FastEmbedSparseEmbeddingConfig(model_name=sparse_model)
                ),
            ),
        ),
        reranking=(
            RerankingProviderSettings(
                provider=(Provider.SENTENCE_TRANSFORMERS if HAS_ST else Provider.FASTEMBED),
                model_name=reranking_model,
                reranking_config=(
                    SentenceTransformersRerankingConfig(model_name=reranking_model)
                    if HAS_ST
                    else FastEmbedRerankingConfig(model_name=reranking_model)
                ),
            ),
        ),
        agent=(
            AgentProviderSettings(
                provider=Provider.ANTHROPIC,
                model="claude-haiku-4.5",
                model_options=AgentModelSettings(),
            ),
        ),
        data=(
            DataProviderSettings(provider=Provider.TAVILY),
            DataProviderSettings(provider=Provider.DUCKDUCKGO),
        ),
        vector_store=QdrantVectorStoreProviderSettings(
            provider=Provider.QDRANT,
            client_options=_get_vector_client_options(vector_deployment, url=url),
        ),
    )


def _backup_profile() -> ProviderSettingsDict:
    """Backup profile for local development with backup vector store.

    Exposed through the CLI as the "testing" profile. We choose the lightest models available for either FastEmbed or Sentence Transformers, depending on availability.

    Together this set of models can run entirely locally, with very low resource usage, making them ideal for development, testing, and as CodeWeaver's fallback profile.
    """
    from codeweaver.core import Provider

    # NOTE: qdrant/bm25 doesn't require FASTEMBED -- FastEmbed can generate with it, but so can the qdrant_client itself
    # We lose true sparse embeddings with bm25, but it's a good lightweight backup option
    embedding_model = "minishlab/potion-base-8M" if HAS_ST else "BAAI/bge-small-en-v1.5"
    reranking_model = (
        "cross-encoder/ms-marco-TinyBERT-L2-v2" if HAS_ST else "jinaai/jina-reranker-v1-tiny-en"
    )

    backup_settings = _quickstart_default("local") | {
        "sparse_embedding": SparseEmbeddingProviderSettings(
            provider=Provider.FASTEMBED,
            model_name="qdrant/bm25",
            sparse_embedding_config=FastEmbedSparseEmbeddingConfig(model_name="qdrant/bm25"),
        ),
        # For the dense embeddings, we essentially choose the lightest available model
        # potion-base-8M is a static embedding model, which again loses some quality, but is extremely light weight and virtually instant
        "embedding": EmbeddingProviderSettings(
            provider=Provider.SENTENCE_TRANSFORMERS if HAS_ST else Provider.FASTEMBED,
            model_name=embedding_model,
            embedding_config=(
                SentenceTransformersEmbeddingConfig(model_name=embedding_model)
                if HAS_ST
                else FastEmbedEmbeddingConfig(model_name=embedding_model)
            ),
        ),
    }

    backup_settings["reranking"] = (
        RerankingProviderSettings(
            provider=Provider.SENTENCE_TRANSFORMERS if HAS_ST else Provider.FASTEMBED,
            model_name=reranking_model,
            reranking_config=(
                SentenceTransformersRerankingConfig(model_name=reranking_model)
                if HAS_ST
                else FastEmbedRerankingConfig(model_name=reranking_model)
            ),
        ),
    )

    backup_settings["vector_store"] = QdrantVectorStoreProviderSettings(
        provider=Provider.MEMORY,
        in_memory_config=MemoryConfig(
            persist_path=Path(f"{get_user_data_dir()}/vectors/backup"), auto_persist=True
        ),
        client_options=_default_local_vector_client_options(),
    )

    return ProviderSettingsDict(**backup_settings)


class ProviderConfigProfile(BaseDataclassEnum):
    """Dataclass wrapper for provider settings profiles."""

    _profile: ProviderSettingsDict

    def __init__(self, profile: ProviderSettingsDict, *args: Any, **kwargs: Any):
        """Initialize the provider config profile."""
        object.__setattr__(self, "_profile", profile)
        super().__init__(*args, **kwargs)

    def __and__(self, other: ProviderConfigProfile) -> ProviderConfigProfile:
        """Combine two provider config profiles."""
        args = (*(self._aliases or ()), self._description or "")  # ty:ignore[unresolved-attribute]
        return ProviderConfigProfile(
            ProviderSettingsDict(
                vector_store=(
                    *(self._profile["vector_store"] or ()),
                    *(other._profile["vector_store"] or ()),
                ),
                embedding=(
                    *(self._profile["embedding"] or ()),
                    *(other._profile["embedding"] or ()),
                ),
                sparse_embedding=(
                    *(self._profile["sparse_embedding"] or ()),
                    *(other._profile["sparse_embedding"] or ()),
                ),
                reranking=(
                    *(self._profile["reranking"] or ()),
                    *(other._profile["reranking"] or ()),
                ),
                agent=(*(self._profile["agent"] or ()), *(other._profile["agent"] or ())),
                data=(*(self._profile["data"] or ()), *(other._profile["data"] or ())),
            ),
            *args,
        )  # ty:ignore[unresolved-attribute]


class ProviderProfile(ProviderConfigProfile, BaseDataclassEnum):
    """Prebuilt provider settings profiles for quick setup."""

    RECOMMENDED = ProviderConfigProfile(
        get_profile("recommended", vector_deployment="local"),
        ("recommended",),
        "Recommended provider settings profile with high-quality providers. Uses Voyage AI for embeddings and rerankings, FastEmbed for sparse (local) embeddings, and local Qdrant for vector storage.",
    )
    QUICKSTART = ProviderConfigProfile(
        get_profile("quickstart", vector_deployment="local"),
        ("quickstart", "local", "free", "open-source"),
        "Quickstart provider settings profile. Entirely local and free. Uses open-source models for sparse and dense embeddings and rerankings, and local Qdrant for vector storage.",
    )
    TESTING = ProviderConfigProfile(
        get_profile("backup", vector_deployment="local"),
        ("testing", "backup", "development", "lightweight", "dev"),
        "Optimized for testing and local development. Uses the lightest weight local models available, and an in-memory vector store with on-disk persistence. This profile is also used as CodeWeaver's backup when cloud providers are unavailable, ensuring reliable operation regardless of external service status with minimal resource usage.",
    )
    TESTING_DB = ProviderConfigProfile(
        {
            **get_profile("backup", vector_deployment="local"),
            "vector_store": QdrantVectorStoreProviderSettings(
                provider=Provider.QDRANT, client_options=_default_local_vector_client_options()
            ),
        },
        ("testing-db", "backup-db", "development-db", "lightweight-db", "dev-db"),
        "Testing profile with on-disk vector database. Similar to the testing profile, but uses a normal on-disk Qdrant vector store instead of an in-memory store. This allows for larger datasets and more persistent storage while still using lightweight local models for embeddings and rerankings.",
    )

    def as_settings_dict(self) -> ProviderSettingsDict:
        """Get the provider settings as a dictionary."""
        profile = (
            self
            if self in {ProviderProfile.TESTING, ProviderProfile.TESTING_DB}
            or os.environ.get("CODEWEAVER__BACKUP_DISABLED")
            else (self._profile | ProviderProfile.TESTING._profile)
        )
        return as_dict(profile._profile)


__all__ = ("ProviderConfigProfile", "ProviderProfile")
