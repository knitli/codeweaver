# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Common utilities for the registry package. Not for public use."""

from __future__ import annotations

from typing import TYPE_CHECKING, Literal, overload


if TYPE_CHECKING:
    from codeweaver.config.providers import (
        AgentProviderSettings,
        DataProviderSettings,
        EmbeddingProviderSettings,
        ProviderSettingsDict,
        RerankingProviderSettings,
        SparseEmbeddingProviderSettings,
        VectorStoreProviderSettings,
    )
    from codeweaver.core.types.dictview import DictView
    from codeweaver.providers.provider import ProviderKind


_provider_settings: DictView[ProviderSettingsDict] | None = None


def get_provider_settings() -> DictView[ProviderSettingsDict]:
    """Get the provider settings."""
    global _provider_settings
    if not _provider_settings:
        from codeweaver.config.settings import get_settings_map
        from codeweaver.core.types.dictview import DictView

        _provider_settings = DictView(get_settings_map()["provider"])
    if not _provider_settings:
        raise ValueError("Provider settings are not available.")
    return _provider_settings


def _get_sparse_config(
    embedding_settings: tuple[SparseEmbeddingProviderSettings, ...],
) -> DictView[SparseEmbeddingProviderSettings] | None:
    """Get the config for sparse config, if any."""
    from codeweaver.core.types.dictview import DictView

    return next(
        (
            DictView(setting)
            for setting in embedding_settings
            if setting.get("model_settings") and setting.get("enabled")
        ),
        None,
    )


def _get_embedding_config(
    embedding_settings: tuple[EmbeddingProviderSettings, ...],
) -> DictView[EmbeddingProviderSettings] | None:
    """Get the embedding model config."""
    from codeweaver.core.types.dictview import DictView

    return next(
        (
            DictView(setting)
            for setting in embedding_settings
            if setting.get("model_settings") and setting.get("enabled")
        ),
        None,
    )


def _get_reranking_config(
    reranking_settings: tuple[RerankingProviderSettings, ...],
) -> DictView[RerankingProviderSettings] | None:
    """Get the reranking model config."""
    from codeweaver.core.types.dictview import DictView

    return next(
        (
            DictView(setting)
            for setting in reranking_settings
            if setting.get("model_settings") and setting.get("enabled")
        ),
        None,
    )


def _get_agent_config(
    agent_settings: tuple[AgentProviderSettings, ...],
) -> DictView[AgentProviderSettings] | None:
    """Get the agent model config."""
    from codeweaver.core.types.dictview import DictView

    return next(
        (
            DictView(setting)
            for setting in agent_settings
            if setting.get("model_settings") and setting.get("enabled")
        ),
        None,
    )


@overload
def get_model_config(
    kind: Literal[ProviderKind.EMBEDDING, "embedding"],
) -> DictView[EmbeddingProviderSettings] | None: ...
@overload
def get_model_config(
    kind: Literal[ProviderKind.SPARSE_EMBEDDING, "sparse_embedding"],
) -> DictView[SparseEmbeddingProviderSettings] | None: ...
@overload
def get_model_config(
    kind: Literal[ProviderKind.RERANKING, "reranking"],
) -> DictView[RerankingProviderSettings] | None: ...
@overload
def get_model_config(
    kind: Literal[ProviderKind.AGENT, "agent"],
) -> DictView[AgentProviderSettings] | None: ...
def get_model_config(
    kind: Literal[
        ProviderKind.EMBEDDING,
        "embedding",
        ProviderKind.SPARSE_EMBEDDING,
        "sparse_embedding",
        ProviderKind.RERANKING,
        "reranking",
        ProviderKind.AGENT,
        "agent",
    ]
    | None = None,
) -> (
    DictView[AgentProviderSettings]
    | DictView[EmbeddingProviderSettings]
    | DictView[RerankingProviderSettings]
    | DictView[SparseEmbeddingProviderSettings]
    | None
):
    """Get the model settings for a specific provider kind."""
    from codeweaver.providers.provider import ProviderKind

    provider_settings = get_provider_settings()
    kind = ProviderKind.from_string(kind) if isinstance(kind, str) else kind  # type: ignore
    if kind is None:
        raise ValueError("We didn't recognize that provider kind, %s.", kind)
    match kind:
        case ProviderKind.EMBEDDING:
            return (
                _get_embedding_config(provider_settings["embedding"])
                if provider_settings["embedding"]
                else None
            )
        case ProviderKind.SPARSE_EMBEDDING:
            return (
                _get_sparse_config(provider_settings["sparse_embedding"])
                if provider_settings["sparse_embedding"]
                else None
            )
        case ProviderKind.RERANKING:
            return (
                _get_reranking_config(provider_settings["reranking"])
                if provider_settings["reranking"]
                else None
            )
        case ProviderKind.AGENT:
            return (
                _get_agent_config(provider_settings["agent"])
                if provider_settings["agent"]
                else None
            )
        case _:
            # The only other provider kind is DATA and they don't have models.
            raise ValueError("We didn't recognize that provider kind, %s.", kind)


def get_vector_store_config() -> DictView[VectorStoreProviderSettings] | None:
    """Get the vector store config, if any."""
    provider_settings = get_provider_settings()
    return next(
        (
            DictView(setting)
            for setting in provider_settings["vector_store"]
            if setting.get("enabled")
        ),
        None,
    )


def get_data_configs() -> tuple[DictView[DataProviderSettings], ...]:
    """Get all enabled data provider configs."""
    provider_settings = get_provider_settings()
    from codeweaver.core.types.dictview import DictView

    return tuple(
        DictView(setting) for setting in provider_settings["data"] if setting.get("enabled")
    )


__all__ = ("get_model_config", "get_provider_settings", "get_vector_store_config")
