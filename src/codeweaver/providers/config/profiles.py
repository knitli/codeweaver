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

from dataclasses import asdict
from importlib import util
from importlib.util import find_spec
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, overload

from pydantic import AnyHttpUrl
from pydantic_ai.settings import ModelSettings as AgentModelSettings

from codeweaver.core import (
    BaseDataclassEnum,
    BaseEnumData,
    ModelName,
    Provider,
    generate_collection_name,
    get_user_data_dir,
)
from codeweaver.core.utils import has_package, uuid7
from codeweaver.providers.config import (
    AgentProviderSettingsType,
    DataProviderSettingsType,
    EmbeddingProviderSettingsType,
    RerankingProviderSettingsType,
    SparseEmbeddingProviderSettingsType,
)
from codeweaver.providers.config.agent import AnthropicAgentModelConfig
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
    AnthropicAgentProviderSettings,
    CollectionConfig,
    DuckDuckGoProviderSettings,
    EmbeddingProviderSettings,
    QdrantVectorStoreProviderSettings,
    RerankingProviderSettings,
    SparseEmbeddingProviderSettings,
    TavilyProviderSettings,
)
from codeweaver.providers.config.providers import AsymmetricEmbeddingProviderSettings


if TYPE_CHECKING:
    from codeweaver.providers.config.providers import ProviderSettingsDict


# Check if FastEmbed is available
HAS_FASTEMBED = find_spec("fastembed") is not None or find_spec("fastembed-gpu") is not None

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


def _default_collection_options(
    *, project_path: Path | None = None, project_name: str | None = None
) -> CollectionConfig:
    """Default collection configuration for Qdrant.

    Vector config is deferred - will be set from embedding config at runtime.
    """
    return CollectionConfig(
        collection_name=generate_collection_name(
            project_name=project_name, project_path=project_path
        ),
        vectors_config=None,  # Will be set from embedding config at runtime
        sparse_vectors_config=None,  # Will be set from sparse embedding config at runtime
    )


def _get_vector_client_options(
    vector_deployment: Literal["cloud", "local"], *, url: AnyHttpUrl | None = None
) -> QdrantClientOptions:
    if vector_deployment != "cloud":
        return _default_local_vector_client_options()
    if url is None:
        # Provide placeholder for cloud deployment - will need to be configured before use
        from pydantic import AnyHttpUrl

        url = AnyHttpUrl("https://qdrant.example.com")  # Placeholder URL
    return _default_remote_vector_client_options(url)


@overload
def _get_profile(
    profile: Literal["recommended", "quickstart", "testing"],
    vector_deployment: Literal["local"],
    *,
    url: AnyHttpUrl | None = None,
    project_name: str | None = None,
    project_path: Path | None = None,
) -> ProviderSettingsDict: ...
@overload
def _get_profile(
    profile: Literal["recommended", "quickstart", "testing"],
    vector_deployment: Literal["cloud"],
    *,
    url: AnyHttpUrl,
    project_name: str | None = None,
    project_path: Path | None = None,
) -> ProviderSettingsDict: ...
def _get_profile(
    profile: Literal["recommended", "quickstart", "testing"],
    vector_deployment: Literal["cloud", "local"],
    *,
    project_name: str | None = None,
    project_path: Path | None = None,
    url: AnyHttpUrl | None = None,
) -> ProviderSettingsDict:
    """Get the default provider settings profile.

    Args:
        profile: The profile name, either "recommended" or "quickstart".
        vector_deployment: The vector store deployment type, either "cloud" or "local".
        url: The URL for the vector store if using cloud deployment.
        project_name: The name of the project, used for generating collection names.
        project_path: The path to the project, used for generating collection names.

    Returns:
        The provider settings dictionary for the specified profile.
    """
    if profile == "testing":
        return _testing_profile()
    if profile == "recommended":
        return _recommended_default(
            vector_deployment, url=url, project_name=project_name, project_path=project_path
        )
    if profile == "quickstart":
        return _quickstart_default(
            vector_deployment, url=url, project_name=project_name, project_path=project_path
        )
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
    vector_deployment: Literal["cloud", "local"],
    *,
    url: AnyHttpUrl | None = None,
    project_name: str | None = None,
    project_path: Path | None = None,
) -> ProviderSettingsDict:
    """Recommended default settings profile.

    This profile leans towards high-quality providers, but without excessive cost or setup. It uses Voyage AI for embeddings and rerankings, which has a generous free tier and class-leading performance. Qdrant can be deployed locally for free or as a cloud service with a generous free tier. Anthropic Claude Haiku is used for agents, which has a strong balance of cost and performance.
    """
    from codeweaver.core import Provider
    from codeweaver.providers.config.providers import ProviderSettingsDict

    return ProviderSettingsDict(
        embedding=(
            AsymmetricEmbeddingProviderSettings(
                embed_provider=EmbeddingProviderSettings(
                    model_name=ModelName("voyage-4-large"),
                    embedding_config=VoyageEmbeddingConfig(model_name=ModelName("voyage-4-large")),
                    provider=Provider.VOYAGE,
                ),
                query_provider=EmbeddingProviderSettings(
                    model_name=ModelName("voyage-4-nano"),
                    provider=Provider.SENTENCE_TRANSFORMERS,
                    embedding_config=SentenceTransformersEmbeddingConfig(
                        model_name=ModelName("voyage-4-nano")
                    ),
                ),
            ),
        ),
        sparse_embedding=(
            SparseEmbeddingProviderSettings(
                provider=Provider.FASTEMBED,
                # Splade is a strong sparse embedding model that works well for code search
                # Splade models are slow to generate embeddings, but lightning fast at inference time
                # This version comes without license complications associated with `naver`'s versions
                # There is a v2 available, but not yet supported by FastEmbed
                model_name=ModelName("prithivida/Splade_PP_en_v1"),
                sparse_embedding_config=FastEmbedSparseEmbeddingConfig(
                    model_name=ModelName("prithivida/Splade_PP_en_v1")
                ),
            ),
        ),
        reranking=(
            RerankingProviderSettings(
                provider=Provider.VOYAGE,
                model_name=ModelName("voyage-rerank-2.5"),
                reranking_config=VoyageRerankingConfig(model_name=ModelName("voyage-rerank-2.5")),
            ),
        ),
        agent=(
            AnthropicAgentProviderSettings(
                provider=Provider.ANTHROPIC,
                model_name="claude-haiku-4.5",
                model_options=AnthropicAgentModelConfig(
                    anthropic_metadata={"_user_id": f"cw-recommended-{uuid7().hex}"},
                    model_name="claude-haiku-4.5",
                    max_tokens=20_000,
                    temperature=0.2,
                    top_p=1.0,
                ),
            ),
        ),
        data=(
            (TavilyProviderSettings(provider=Provider.TAVILY),)
            if Provider.TAVILY.has_env_auth() and has_package("tavily")
            else (DuckDuckGoProviderSettings(provider=Provider.DUCKDUCKGO),)
        ),
        vector_store=(
            QdrantVectorStoreProviderSettings(
                provider=Provider.QDRANT,
                client_options=_get_vector_client_options(vector_deployment, url=url),
                collection=_default_collection_options(),
            ),
        ),
    )


def _quickstart_default(
    vector_deployment: Literal["local", "cloud"],
    *,
    url: AnyHttpUrl | None = None,
    project_name: str | None = None,
    project_path: Path | None = None,
) -> ProviderSettingsDict:
    """Quickstart default settings profile.

    This profile uses free-tier or open-source providers to allow for immediate use without cost.
    """
    from codeweaver.core import Provider
    from codeweaver.providers.config.providers import ProviderSettingsDict

    embedding_model = (
        ModelName("voyageai/voyage-4-nano") if HAS_ST else ModelName("BAAI/bge-small-en-v1.5")
    )
    sparse_model = (
        ModelName("opensearch/opensearch-neural-sparse-encoding-doc-v3-gte")
        if HAS_ST
        else ModelName("prithivida/Splade_PP_en_v1")
    )
    reranking_model = ModelName("jinaai/jina-reranker-v1-en-")

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
                model_name="claude-haiku-4.5",
                model_options=AgentModelSettings(),
            ),
        ),
        data=(
            TavilyProviderSettings(provider=Provider.TAVILY)
            if has_package("tavily") and Provider.TAVILY.has_env_auth()
            else DuckDuckGoProviderSettings(provider=Provider.DUCKDUCKGO),
        ),
        vector_store=(
            QdrantVectorStoreProviderSettings(
                provider=Provider.QDRANT,
                client_options=_get_vector_client_options(vector_deployment, url=url),
                collection=_default_collection_options(),
            ),
        ),
    )


def _testing_profile(
    *, use_local: bool = False, project_name: str | None = None, project_path: Path | None = None
) -> ProviderSettingsDict:
    """Backup profile for local development with backup vector store.

    Exposed through the CLI as the "testing" profile. We choose the lightest models available for either FastEmbed or Sentence Transformers, depending on availability.

    Together this set of models can run entirely locally, with very low resource usage, making them ideal for development, testing, and as CodeWeaver's fallback profile.

    Args:
        use_local: Whether to use a local Qdrant vector store instead of in-memory.
        project_name: The name of the project, used for generating collection names.
        project_path: The path to the project, used for generating collection names.
    """
    from codeweaver.core import Provider
    from codeweaver.providers.config.providers import ProviderSettingsDict

    # NOTE: qdrant/bm25 doesn't require FASTEMBED -- FastEmbed can generate with it, but so can the qdrant_client itself
    # We lose true sparse embeddings with bm25, but it's a good lightweight backup option
    embedding_model = "minishlab/potion-base-8M" if HAS_ST else "jinaai/jina-embeddings-v2-small-en"
    reranking_model = "jinaai/jina-reranker-v1-tiny-en"
    default_collection = _default_collection_options(
        project_name=project_name, project_path=project_path
    )

    backup_settings = _quickstart_default("local") | {
        "sparse_embedding": SparseEmbeddingProviderSettings(
            provider=Provider.FASTEMBED,
            model_name=ModelName("qdrant/bm25"),
            sparse_embedding_config=FastEmbedSparseEmbeddingConfig(
                model_name=ModelName("qdrant/bm25")
            ),
        ),
        # For the dense embeddings, we essentially choose the lightest available model
        # potion-base-8M is a static embedding model, which loses some quality, but is extremely light weight and virtually instant
        "embedding": EmbeddingProviderSettings(
            provider=Provider.SENTENCE_TRANSFORMERS if HAS_ST else Provider.FASTEMBED,
            model_name=ModelName(embedding_model),
            embedding_config=(
                SentenceTransformersEmbeddingConfig(model_name=ModelName(embedding_model))
                if HAS_ST
                else FastEmbedEmbeddingConfig(model_name=ModelName(embedding_model))
            ),
        ),
    }

    backup_settings["reranking"] = (
        RerankingProviderSettings(
            provider=Provider.FASTEMBED if HAS_FASTEMBED else Provider.SENTENCE_TRANSFORMERS,
            model_name=ModelName(reranking_model),
            reranking_config=(
                FastEmbedRerankingConfig(model_name=ModelName(reranking_model))
                if HAS_FASTEMBED
                else SentenceTransformersRerankingConfig(model_name=ModelName(reranking_model))
            ),
        ),
    )
    if use_local:
        backup_settings["vector_store"] = (
            QdrantVectorStoreProviderSettings(
                provider=Provider.QDRANT,
                collection=default_collection,
                client_options=_default_local_vector_client_options(),
            ),
        )
    else:
        backup_settings["vector_store"] = QdrantVectorStoreProviderSettings(
            provider=Provider.QDRANT,
            client_options=QdrantClientOptions(
                path=str(get_user_data_dir() / f"backup-{project_name}")
            ),
            collection=default_collection,
        )

    return ProviderSettingsDict(**backup_settings)


class ProviderConfigProfile(BaseEnumData):
    """Dataclass wrapper for provider settings profiles.

    This is a frozen dataclass for use with BaseDataclassEnum.
    """

    vector_store: tuple[QdrantVectorStoreProviderSettings, ...] | None
    embedding: tuple[EmbeddingProviderSettingsType, ...] | None
    sparse_embedding: tuple[SparseEmbeddingProviderSettingsType, ...] | None
    reranking: tuple[RerankingProviderSettingsType, ...] | None
    agent: tuple[AgentProviderSettingsType, ...] | None
    data: tuple[DataProviderSettingsType, ...] | None

    def __init__(
        self, provider_settings: ProviderSettingsDict | None = None, *args: Any, **kwargs: Any
    ) -> None:
        """Initialize ProviderConfigProfile with provider settings.

        Args:
            provider_settings: Dictionary containing provider settings
            *args: Additional positional args passed to BaseEnumData
            **kwargs: Additional keyword args passed to BaseEnumData
        """
        provider_settings = provider_settings or ProviderSettingsDict()

        object.__setattr__(self, "vector_store", provider_settings.get("vector_store"))
        object.__setattr__(self, "embedding", provider_settings.get("embedding"))
        object.__setattr__(self, "sparse_embedding", provider_settings.get("sparse_embedding"))
        object.__setattr__(self, "reranking", provider_settings.get("reranking"))
        object.__setattr__(self, "agent", provider_settings.get("agent"))
        object.__setattr__(self, "data", provider_settings.get("data"))
        super().__init__(*args, **kwargs)

    def _telemetry_keys(self) -> None:
        return None

    def _register_self(self, name: str) -> None:
        from codeweaver.core.di.container import get_container

        container = get_container()
        container.register(
            type(self), lambda: self, singleton=True, tags=frozenset({name, "profile"})
        )

    def __and__(self, other: ProviderConfigProfile) -> ProviderConfigProfile:
        """Combine two provider config profiles."""
        from codeweaver.providers.config.providers import ProviderSettingsDict

        return ProviderConfigProfile(
            ProviderSettingsDict(
                vector_store=(*(self.vector_store or ()), *(other.vector_store or ())),
                embedding=(*(self.embedding or ()), *(other.embedding or ())),
                sparse_embedding=(*(self.sparse_embedding or ()), *(other.sparse_embedding or ())),
                reranking=(*(self.reranking or ()), *(other.reranking or ())),
                agent=(*(self.agent or ()), *(other.agent or ())),
                data=(*(self.data or ()), *(other.data or ())),
            ),
            self._aliases or (),  # ty:ignore[unresolved-attribute]
            self._description or "",  # ty:ignore[unresolved-attribute]
        )


class ProviderProfile(ProviderConfigProfile, BaseDataclassEnum):
    """Prebuilt provider settings profiles for quick setup."""

    RECOMMENDED = (
        _get_profile("recommended", vector_deployment="local"),
        ("recommended",),
        "Recommended provider settings profile with high-quality providers. Uses Voyage AI for embeddings and rerankings, FastEmbed for sparse (local) embeddings, and local Qdrant for vector storage.",
    )
    RECOMMENDED_CLOUD = (
        _recommended_default(vector_deployment="cloud"),
        ("recommended-cloud",),
        "Recommended provider settings profile with high-quality providers and cloud vector store. Uses Voyage AI for embeddings and rerankings, FastEmbed for sparse (local) embeddings, and cloud Qdrant for vector storage.",
    )
    QUICKSTART = (
        _get_profile("quickstart", vector_deployment="local"),
        ("quickstart", "local", "free", "open-source"),
        "Quickstart provider settings profile. Entirely local and free. Uses open-source models for sparse and dense embeddings and rerankings, and local Qdrant for vector storage.",
    )
    TESTING = (
        _get_profile("testing", vector_deployment="local"),
        ("testing", "development", "lightweight", "dev"),
        "Optimized for testing and local development. Uses the lightest weight local models available, and an in-memory vector store with on-disk persistence. This profile is also used as CodeWeaver's backup when cloud providers are unavailable, ensuring reliable operation regardless of external service status with minimal resource usage.",
    )
    TESTING_DB = (
        {
            **_get_profile("testing", vector_deployment="local"),
            "vector_store": (
                QdrantVectorStoreProviderSettings(
                    collection=_default_collection_options(),
                    provider=Provider.QDRANT,
                    client_options=_default_local_vector_client_options(),
                ),
            ),
        },
        ("testing-db", "backup-db", "development-db", "lightweight-db", "dev-db"),
        "Testing profile with on-disk vector database. Similar to the testing profile, but uses a normal on-disk Qdrant vector store instead of an in-memory store. This allows for larger datasets and more persistent storage while still using lightweight local models for embeddings and rerankings.",
    )

    @classmethod
    def _get_profile(
        cls, name: str, vector_deployment: Literal["cloud", "local"] = "local"
    ) -> ProviderConfigProfile:
        """Get a provider profile by name.

        Args:
            name: The name of the profile.
            vector_deployment: The vector store deployment type, either "cloud" or "local".

        Returns:
            The provider config profile.

        Raises:
            ValueError: If the profile name is unknown.
        """
        for profile in cls:
            if name in (alias.lower() for alias in (profile._aliases or ())):  # type: ignore[unresolved-attribute]
                return profile
        provider = ProviderProfile.from_string(name)
        if provider in {ProviderProfile.RECOMMENDED, ProviderProfile.RECOMMENDED_CLOUD}:
            return (
                ProviderProfile.RECOMMENDED_CLOUD
                if vector_deployment == "cloud"
                else ProviderProfile.RECOMMENDED
            )
        return provider

    def as_provider_settings(self) -> ProviderSettingsDict:
        """Get the provider settings as a dictionary."""
        from codeweaver.providers.config.providers import ProviderSettingsDict

        return ProviderSettingsDict(**{
            k: v for k, v in asdict(self.value).items() if k not in {"aliases", "description"}
        })


__all__ = ("ProviderConfigProfile", "ProviderProfile")
