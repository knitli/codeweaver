# SPDX-FileCopyrightText: 2026 Knitli Inc.
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

from dataclasses import dataclass
from importlib import util
from importlib.util import find_spec
from pathlib import Path
from typing import TYPE_CHECKING, Any, Literal, overload

from packaging.version import parse as parse_version
from pydantic import AnyHttpUrl

from codeweaver.core import (
    BaseDataclassEnum,
    BaseEnumData,
    ModelName,
    Provider,
    generate_collection_name,
    get_user_data_dir,
)
from codeweaver.core.constants import (
    BACKUP_EMBEDDING_MODEL_FALLBACK,
    RECOMMENDED_CLOUD_CONTEXT_AGENT_MODEL_BARE,
    RECOMMENDED_CLOUD_EMBEDDING_MODEL,
    RECOMMENDED_CLOUD_RERANKING_MODEL,
    RECOMMENDED_QUERY_EMBEDDING_MODEL,
    RECOMMENDED_SPARSE_EMBEDDING_MODEL,
    ULTRALIGHT_EMBEDDING_MODEL,
    ULTRALIGHT_RERANKING_MODEL,
    ULTRALIGHT_SPARSE_EMBEDDING_MODEL,
)
from codeweaver.core.types import AnonymityConversion, FilteredKeyT
from codeweaver.core.types.dataclasses import DataclassSerializationMixin
from codeweaver.core.utils import has_package, uuid7
from codeweaver.providers.config import (
    AgentProviderSettingsType,
    DataProviderSettingsType,
    EmbeddingProviderSettingsType,
    RerankingProviderSettingsType,
    SparseEmbeddingProviderSettingsType,
)
from codeweaver.providers.config.categories import (
    AnthropicAgentProviderSettings,
    AsymmetricEmbeddingProviderSettings,
    DuckDuckGoProviderSettings,
    EmbeddingProviderSettings,
    FastEmbedSparseEmbeddingProviderSettings,
    QdrantVectorStoreProviderSettings,
    RerankingProviderSettings,
    SparseEmbeddingProviderSettings,
    TavilyProviderSettings,
)
from codeweaver.providers.config.clients import QdrantClientOptions
from codeweaver.providers.config.sdk import (
    CollectionConfig,
    FastEmbedEmbeddingConfig,
    FastEmbedSparseEmbeddingConfig,
    SentenceTransformersEmbeddingConfig,
    SentenceTransformersSparseEmbeddingConfig,
    VoyageEmbeddingConfig,
)
from codeweaver.providers.config.sdk.agent import AnthropicAgentModelConfig


if TYPE_CHECKING:
    from codeweaver.providers.config.providers import ProviderSettingsDict
HAS_FASTEMBED = find_spec("fastembed") is not None or find_spec("fastembed-gpu") is not None
from codeweaver.providers.config.sdk import (
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
        vectors_config=None,
        sparse_vectors_config=None,
    )


def _get_vector_client_options(
    vector_deployment: Literal["cloud", "local"], *, url: AnyHttpUrl | None = None
) -> QdrantClientOptions:
    if vector_deployment != "cloud":
        return _default_local_vector_client_options()
    if url is None:
        from pydantic import AnyHttpUrl

        url = AnyHttpUrl("https://qdrant.example.com")
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
                    model_name=ModelName(RECOMMENDED_CLOUD_EMBEDDING_MODEL),
                    embedding_config=VoyageEmbeddingConfig(
                        model_name=ModelName(RECOMMENDED_CLOUD_EMBEDDING_MODEL)
                    ),
                    provider=Provider.VOYAGE,
                ),
                query_provider=EmbeddingProviderSettings(
                    model_name=ModelName(RECOMMENDED_QUERY_EMBEDDING_MODEL),
                    provider=Provider.SENTENCE_TRANSFORMERS,
                    embedding_config=SentenceTransformersEmbeddingConfig(
                        model_name=ModelName(RECOMMENDED_QUERY_EMBEDDING_MODEL)
                    ),
                ),
            ),
        ),
        sparse_embedding=(
            FastEmbedSparseEmbeddingProviderSettings(
                provider=Provider.FASTEMBED,
                model_name=ModelName(RECOMMENDED_SPARSE_EMBEDDING_MODEL),
                sparse_embedding_config=FastEmbedSparseEmbeddingConfig(
                    model_name=ModelName(RECOMMENDED_SPARSE_EMBEDDING_MODEL)
                ),
            ),
        ),
        reranking=(
            RerankingProviderSettings(
                provider=Provider.VOYAGE,
                model_name=ModelName(RECOMMENDED_CLOUD_RERANKING_MODEL),
                reranking_config=VoyageRerankingConfig(
                    model_name=ModelName(RECOMMENDED_CLOUD_RERANKING_MODEL)
                ),
            ),
        ),
        agent=(
            AnthropicAgentProviderSettings(
                provider=Provider.ANTHROPIC,
                model_name=RECOMMENDED_CLOUD_CONTEXT_AGENT_MODEL_BARE,
                agent_config=AnthropicAgentModelConfig(
                    anthropic_metadata={"_user_id": f"cw-recommended-{uuid7().hex}"},
                    anthropic_thinking={"type": "disabled"},
                    model_name=RECOMMENDED_CLOUD_CONTEXT_AGENT_MODEL_BARE,
                    max_tokens=20000,
                    temperature=0.2,
                    top_p=1.0,
                ),
            ),
        ),
        data=(TavilyProviderSettings(provider=Provider.TAVILY),)
        if Provider.TAVILY.has_env_auth and has_package("tavily")
        else (DuckDuckGoProviderSettings(provider=Provider.DUCKDUCKGO),),
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
    reranking_model = ModelName(ULTRALIGHT_RERANKING_MODEL)
    return ProviderSettingsDict(
        embedding=(
            EmbeddingProviderSettings(
                model_name=embedding_model,
                embedding_config=SentenceTransformersEmbeddingConfig(model_name=embedding_model)
                if HAS_ST
                else FastEmbedEmbeddingConfig(model_name=embedding_model),
                provider=Provider.SENTENCE_TRANSFORMERS if HAS_ST else Provider.FASTEMBED,
            ),
        ),
        sparse_embedding=(
            (
                SparseEmbeddingProviderSettings
                if HAS_ST
                else FastEmbedSparseEmbeddingProviderSettings
            )(
                provider=Provider.SENTENCE_TRANSFORMERS if HAS_ST else Provider.FASTEMBED,  # ty:ignore[invalid-argument-type]
                model_name=sparse_model,
                sparse_embedding_config=SentenceTransformersSparseEmbeddingConfig(
                    model_name=sparse_model
                )
                if HAS_ST
                else FastEmbedSparseEmbeddingConfig(model_name=sparse_model),
            ),
        ),
        reranking=(
            RerankingProviderSettings(
                provider=Provider.SENTENCE_TRANSFORMERS if HAS_ST else Provider.FASTEMBED,
                model_name=reranking_model,
                reranking_config=SentenceTransformersRerankingConfig(model_name=reranking_model)
                if HAS_ST
                else FastEmbedRerankingConfig(model_name=reranking_model),
            ),
        ),
        agent=(
            AnthropicAgentProviderSettings(
                provider=Provider.ANTHROPIC,
                model_name=RECOMMENDED_CLOUD_CONTEXT_AGENT_MODEL_BARE,
                agent_config=AnthropicAgentModelConfig(anthropic_thinking={"type": "disabled"}),
            ),
        ),
        data=(
            TavilyProviderSettings(provider=Provider.TAVILY)
            if has_package("tavily") and Provider.TAVILY.has_env_auth
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

    embedding_model = ULTRALIGHT_EMBEDDING_MODEL if HAS_ST else BACKUP_EMBEDDING_MODEL_FALLBACK
    reranking_model = ULTRALIGHT_RERANKING_MODEL
    default_collection = _default_collection_options(
        project_name=project_name, project_path=project_path
    )
    backup_settings = _quickstart_default("local") | {
        "sparse_embedding": FastEmbedSparseEmbeddingProviderSettings(
            provider=Provider.FASTEMBED,
            model_name=ModelName(ULTRALIGHT_SPARSE_EMBEDDING_MODEL),
            sparse_embedding_config=FastEmbedSparseEmbeddingConfig(
                model_name=ModelName(ULTRALIGHT_SPARSE_EMBEDDING_MODEL)
            ),
        ),
        "embedding": EmbeddingProviderSettings(
            provider=Provider.SENTENCE_TRANSFORMERS if HAS_ST else Provider.FASTEMBED,
            model_name=ModelName(embedding_model),
            embedding_config=SentenceTransformersEmbeddingConfig(
                model_name=ModelName(embedding_model)
            )
            if HAS_ST
            else FastEmbedEmbeddingConfig(model_name=ModelName(embedding_model)),
        ),
    }
    backup_settings["reranking"] = (
        RerankingProviderSettings(
            provider=Provider.FASTEMBED if HAS_FASTEMBED else Provider.SENTENCE_TRANSFORMERS,
            model_name=ModelName(reranking_model),
            reranking_config=FastEmbedRerankingConfig(model_name=ModelName(reranking_model))
            if HAS_FASTEMBED
            else SentenceTransformersRerankingConfig(model_name=ModelName(reranking_model)),
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


@dataclass(frozen=True)
class VersionedProfile(DataclassSerializationMixin):
    """Profile configuration with version tracking for compatibility management.

    Tracks the CodeWeaver version associated with each profile configuration,
    enabling semantic versioning-based compatibility checks between profile
    versions and collection metadata versions.

    Version Compatibility:
        - Major version must match for compatibility (e.g., 0.x.x with 0.y.z)
        - Minor and patch versions can differ (backward compatible)
        - Changelog tracks profile evolution across versions

    Integration with Collections:
        When a collection is created, it stores:
        - profile_name: The name of this profile
        - profile_version: The CodeWeaver version when profile was applied
        - This enables compatibility validation on collection reuse

    Attributes:
        name: Unique identifier for the profile (e.g., "recommended", "quickstart")
        version: CodeWeaver version string following semantic versioning (e.g., "0.1.0a6")
        embedding_config: The embedding provider configuration for this profile
        changelog: Historical record of profile changes across versions
    """

    name: str
    "Unique identifier for this profile configuration."
    version: str
    "CodeWeaver version when this profile was defined, following semantic versioning."
    embedding_config: EmbeddingProviderSettingsType | AsymmetricEmbeddingProviderSettings
    "Embedding provider configuration for this profile."
    changelog: tuple[str, ...]
    "Chronological record of profile changes, newest entries first."

    def __init__(
        self,
        name: str,
        version: str,
        embedding_config: EmbeddingProviderSettingsType | AsymmetricEmbeddingProviderSettings,
        changelog: tuple[str, ...] | list[str],
        **kwargs: Any,
    ) -> None:
        """Initialize a versioned profile.

        Args:
            name: Profile identifier
            version: CodeWeaver version string
            embedding_config: Embedding configuration
            changelog: List or tuple of changelog entries
        """
        object.__setattr__(self, "name", name)
        object.__setattr__(self, "version", version)
        object.__setattr__(self, "embedding_config", embedding_config)
        object.__setattr__(
            self, "changelog", tuple(changelog) if isinstance(changelog, list) else changelog
        )
        cleaned_kwargs = {k: v for k, v in kwargs.items() if k in {"aliases", "description"}} or {}
        super().__init__(**cleaned_kwargs)

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion] | None:
        """Define telemetry anonymization rules."""
        return None

    @classmethod
    def is_compatible_with(cls, profile_version: str, collection_version: str) -> bool:
        """Check if profile version is compatible with collection version.

        Uses semantic versioning rules where major versions must match for
        compatibility. Minor and patch version differences are acceptable as
        they represent backward-compatible changes.

        Args:
            profile_version: Version string of the profile (e.g., "0.1.0a6")
            collection_version: Version string from collection metadata

        Returns:
            True if versions are compatible (same major version), False otherwise

        Examples:
            >>> VersionedProfile.is_compatible_with("0.1.0", "0.2.5")
            True  # Same major version (0)
            >>> VersionedProfile.is_compatible_with("0.1.0", "1.0.0")
            False  # Different major versions
            >>> VersionedProfile.is_compatible_with("0.1.0a6", "0.1.0")
            True  # Pre-release compatible with same major.minor
        """
        try:
            pv = parse_version(profile_version)
            cv = parse_version(collection_version)
            profile_major = pv.release[0] if pv.release else 0
            collection_major = cv.release[0] if cv.release else 0
        except Exception:
            return False
        else:
            return profile_major == collection_major

    def get_changelog_for_version(self, target_version: str) -> list[str]:
        """Get changelog entries relevant to upgrading to target version.

        Filters changelog entries that apply when migrating from this profile's
        version to the target version. Useful for displaying migration guidance.

        Args:
            target_version: Version string to migrate to

        Returns:
            List of relevant changelog entries, newest first
        """
        try:
            current = parse_version(self.version)
            target = parse_version(target_version)
            if target > current:
                return list(self.changelog)
        except Exception:
            return list(self.changelog)
        else:
            return []

    def validate_against_collection(
        self, collection_profile_name: str | None, collection_profile_version: str | None
    ) -> tuple[bool, str | None]:
        """Validate this profile can be used with an existing collection.

        Checks both profile name matching and version compatibility to determine
        if this profile can safely be used with a collection created under different
        profile/version settings.

        Args:
            collection_profile_name: Profile name stored in collection metadata
            collection_profile_version: Profile version stored in collection metadata

        Returns:
            Tuple of (is_valid, error_message). error_message is None if valid.

        Examples:
            >>> profile = VersionedProfile("recommended", "0.1.0", config, [])
            >>> profile.validate_against_collection("recommended", "0.1.5")
            (True, None)
            >>> profile.validate_against_collection("quickstart", "0.1.0")
            (False, "Profile name mismatch: ...")
            >>> profile.validate_against_collection("recommended", "1.0.0")
            (False, "Incompatible versions: ...")
        """
        if not collection_profile_name or not collection_profile_version:
            return (True, None)
        if collection_profile_name != self.name:
            return (
                False,
                f"Profile name mismatch: collection uses '{collection_profile_name}' but current profile is '{self.name}'. Consider re-indexing with the correct profile or switching to '{collection_profile_name}'.",
            )
        if not self.is_compatible_with(self.version, collection_profile_version):
            return (
                False,
                f"Incompatible versions: collection created with version '{collection_profile_version}' but current version is '{self.version}'. Major version mismatch requires re-indexing. See changelog for breaking changes.",
            )
        return (True, None)


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
        if isinstance(provider_settings, ProviderConfigProfile):
            # Called by Python's Enum metaclass with the already-created instance as value.
            # Copy all fields directly from the existing instance and return.
            object.__setattr__(self, "vector_store", provider_settings.vector_store)
            object.__setattr__(self, "embedding", provider_settings.embedding)
            object.__setattr__(self, "sparse_embedding", provider_settings.sparse_embedding)
            object.__setattr__(self, "reranking", provider_settings.reranking)
            object.__setattr__(self, "agent", provider_settings.agent)
            object.__setattr__(self, "data", provider_settings.data)
            object.__setattr__(self, "aliases", getattr(provider_settings, "aliases", ()))
            object.__setattr__(self, "description", getattr(provider_settings, "description", None))
            return
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
            self.aliases if hasattr(self, "aliases") else (),
            self.description or "",
        )


class ProviderProfile(ProviderConfigProfile, BaseDataclassEnum):
    """Prebuilt provider settings profiles for quick setup."""

    RECOMMENDED = ProviderConfigProfile(
        _get_profile("recommended", vector_deployment="local"),
        ("recommended",),
        "Recommended provider settings profile with high-quality providers. Uses Voyage AI for embeddings and rerankings, FastEmbed for sparse (local) embeddings, and local Qdrant for vector storage.",
    )
    RECOMMENDED_CLOUD = ProviderConfigProfile(
        _recommended_default(vector_deployment="cloud"),
        ("recommended-cloud",),
        "Recommended provider settings profile with high-quality providers and cloud vector store. Uses Voyage AI for embeddings and rerankings, FastEmbed for sparse (local) embeddings, and cloud Qdrant for vector storage.",
    )
    QUICKSTART = ProviderConfigProfile(
        _get_profile("quickstart", vector_deployment="local"),
        ("quickstart", "local", "free", "open-source"),
        "Quickstart provider settings profile. Entirely local and free. Uses open-source models for sparse and dense embeddings and rerankings, and local Qdrant for vector storage.",
    )
    TESTING = ProviderConfigProfile(
        _get_profile("testing", vector_deployment="local"),
        ("testing", "development", "lightweight", "dev"),
        "Optimized for testing and local development. Uses the lightest weight local models available, and an in-memory vector store with on-disk persistence. This profile is also used as CodeWeaver's backup when cloud providers are unavailable, ensuring reliable operation regardless of external service status with minimal resource usage.",
    )
    TESTING_DB = ProviderConfigProfile(
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
            if name in (
                alias.lower() for alias in (profile.aliases if hasattr(profile, "aliases") else ())
            ):
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

        _fields = ("embedding", "sparse_embedding", "reranking", "vector_store", "agent", "data")
        return ProviderSettingsDict(**{
            k: v for k in _fields if (v := getattr(self, k, None)) is not None
        })


__all__ = (
    "HAS_FASTEMBED",
    "HAS_ST",
    "ProviderConfigProfile",
    "ProviderProfile",
    "VersionedProfile",
)
