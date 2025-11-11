# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Model registry for managing embedding, reranking, and sparse embedding models."""

from __future__ import annotations

import contextlib

from collections import defaultdict
from collections.abc import Iterable, MutableMapping, Sequence
from fnmatch import fnmatch
from typing import NamedTuple, cast

from pydantic import ConfigDict
from rich.console import Console

from codeweaver.common.registry.types import LiteralModelKinds
from codeweaver.core.types.aliases import LiteralStringT, ModelName
from codeweaver.core.types.models import BasedModel
from codeweaver.providers.agent import AgentModel, AgentProfile, AgentProfileSpec
from codeweaver.providers.embedding.capabilities.base import (
    EmbeddingModelCapabilities,
    SparseEmbeddingModelCapabilities,
)
from codeweaver.providers.provider import Provider
from codeweaver.providers.reranking.capabilities.base import RerankingModelCapabilities


console = Console(markup=True, emoji=True)


def _normalize_iterable[
    T: EmbeddingModelCapabilities | SparseEmbeddingModelCapabilities | RerankingModelCapabilities
](items: Iterable[T] | Sequence[T] | T) -> tuple[T, ...]:
    """Normalize an input that can be a single item, iterable, or sequence into a tuple.

    NOTE: we need to be careful here because, as it turns out, the capabilities objects are iterable themselves, which is not what we want to treat as an iterable of capabilities!
    """
    if isinstance(
        items,
        EmbeddingModelCapabilities | SparseEmbeddingModelCapabilities | RerankingModelCapabilities,
    ):
        return (cast(T, items),)
    return tuple(items)


def _normalize_model_name(name: str) -> ModelName:
    """Normalize a model name for consistent storage and lookup."""
    return ModelName(cast(LiteralStringT, name.strip().lower().replace(" ", "_").replace("-", "_")))


class ModelResult(NamedTuple):
    """Result of a model lookup in the registry for a Provider."""

    provider: Provider
    embedding: tuple[EmbeddingModelCapabilities, ...] | None = None
    sparse_embedding: tuple[SparseEmbeddingModelCapabilities, ...] | None = None
    reranking: tuple[RerankingModelCapabilities, ...] | None = None
    agent: tuple[tuple[str, AgentProfileSpec], ...] | None = None


class ModelRegistry(BasedModel):
    """Registry for managing available embedding, reranking, and sparse embedding models."""

    model_config = BasedModel.model_config | ConfigDict(
        arbitrary_types_allowed=True, validate_assignment=True, defer_build=True
    )

    def __init__(self) -> None:
        """Initialize the model registry."""
        # provider -> (model_name -> capabilities)
        self._embedding_capabilities: MutableMapping[
            Provider, MutableMapping[ModelName, tuple[EmbeddingModelCapabilities, ...]]
        ] = defaultdict(dict)
        self._sparse_embedding_capabilities: MutableMapping[
            Provider, MutableMapping[ModelName, tuple[SparseEmbeddingModelCapabilities, ...]]
        ] = defaultdict(dict)
        self._reranking_capabilities: MutableMapping[
            Provider, MutableMapping[ModelName, tuple[RerankingModelCapabilities, ...]]
        ] = defaultdict(dict)

        # provider -> list[(model_glob, AgentProfileSpec)] for agent profiles
        self._agent_profiles: MutableMapping[Provider, list[tuple[str, AgentProfileSpec]]] = (
            defaultdict(list)
        )

        # flag to allow one-time default population by caller
        self._populated_defaults: bool = False

        # Register builtin models on initialization
        self._register_builtin_models()
        self._populated_defaults = True

    def _register_builtin_embedding_models(self) -> None:
        """Register built-in embedding models."""
        from codeweaver.providers.embedding.capabilities import (
            load_default_capabilities,
            load_sparse_capabilities,
        )

        for cap in load_default_capabilities():
            self.register_embedding_capabilities(cap, replace=False)
        for cap in load_sparse_capabilities():
            self.register_sparse_embedding_capabilities(cap, replace=False)

    def _register_builtin_reranking_models(self) -> None:
        from codeweaver.providers.reranking.capabilities import load_default_capabilities

        for cap in load_default_capabilities():
            self.register_reranking_capabilities(cap, replace=False)

    def _register_builtin_models(self) -> None:
        self._register_builtin_embedding_models()
        self._register_builtin_reranking_models()

    def _register_capabilities[
        Capabilities: EmbeddingModelCapabilities
        | RerankingModelCapabilities
        | SparseEmbeddingModelCapabilities
    ](
        self,
        capabilities: Capabilities,
        registry: MutableMapping[Provider, MutableMapping[ModelName, tuple[Capabilities, ...]]],
        *,
        replace: bool,
    ) -> None:
        """Helper to sort and register capabilities into the given registry."""
        prov_map = registry[capabilities.provider]
        model_name = _normalize_model_name(capabilities.name)
        if replace or model_name not in prov_map:
            prov_map[model_name] = (capabilities,)
        elif prov_map.get(model_name) and capabilities not in prov_map[model_name]:
            prov_map[model_name] += (capabilities,)
        else:
            prov_map[model_name] = (capabilities,)

    # ---------- Embedding capabilities ----------
    def register_embedding_capabilities(
        self, capabilities: EmbeddingModelCapabilities, *, replace: bool = True
    ) -> None:
        """Register one or more embedding model capabilities.

        Adds embedding model capability metadata to the registry, replacing
        existing entries for the same model name and provider if `replace` is True.

        Args:
            capabilities: A single EmbeddingModelCapabilities or a sequence of them to register.
            replace: Whether to replace existing capabilities for the same model name and provider.
        """
        self._register_capabilities(capabilities, self._embedding_capabilities, replace=replace)

    def get_embedding_capabilities(
        self, provider: Provider, name: str
    ) -> tuple[EmbeddingModelCapabilities, ...] | None:
        """Get embedding capabilities for a specific provider and model name."""
        prov_map = self._embedding_capabilities.get(provider)
        return (
            prov_map.get(ModelName(cast(LiteralStringT, _normalize_model_name(name))))
            if prov_map
            else None
        )

    def list_embedding_models(
        self, provider: Provider | None = None
    ) -> tuple[EmbeddingModelCapabilities, ...]:
        """List all embedding models for a specific provider or all providers."""
        if provider is None:
            return tuple(
                cap
                for prov_map in self._embedding_capabilities.values()
                for cap in prov_map.values()
            )  # type: ignore
        return tuple(self._embedding_capabilities.get(provider, {}).values())  # type: ignore

    # ---------- Sparse embedding capabilities ----------
    def register_sparse_embedding_capabilities(
        self, capabilities: SparseEmbeddingModelCapabilities, *, replace: bool = True
    ) -> None:
        """Register one or more sparse embedding model capabilities."""
        self._register_capabilities(
            capabilities, self._sparse_embedding_capabilities, replace=replace
        )

    def get_sparse_embedding_capabilities(
        self, provider: Provider, name: str
    ) -> tuple[SparseEmbeddingModelCapabilities, ...] | None:
        """Get sparse embedding capabilities for a specific provider and model name."""
        prov_map = self._sparse_embedding_capabilities.get(provider)
        return (
            prov_map.get(ModelName(cast(LiteralStringT, _normalize_model_name(name))))
            if prov_map
            else None
        )

    def list_sparse_embedding_models(
        self, provider: Provider | None = None
    ) -> tuple[SparseEmbeddingModelCapabilities, ...]:
        """List all sparse embedding models for a specific provider or all providers."""
        if provider is None:
            return tuple(
                cap
                for prov_map in self._sparse_embedding_capabilities.values()
                for cap_tuple in prov_map.values()
                for cap in cap_tuple
            )
        prov_map = self._sparse_embedding_capabilities.get(provider, {})
        return tuple(cap for cap_tuple in prov_map.values() for cap in cap_tuple)

    # ---------- Reranking capabilities ----------
    def register_reranking_capabilities(
        self, capabilities: RerankingModelCapabilities, *, replace: bool = True
    ) -> None:
        """Register one or more reranking model capabilities."""
        self._register_capabilities(capabilities, self._reranking_capabilities, replace=replace)

    def get_reranking_capabilities(
        self, provider: Provider, name: str
    ) -> tuple[RerankingModelCapabilities, ...] | None:
        """Get reranking capabilities for a specific provider and model name."""
        prov_map = self._reranking_capabilities.get(provider)
        return (
            prov_map.get(ModelName(cast(LiteralStringT, _normalize_model_name(name))))
            if prov_map
            else None
        )

    def list_reranking_models(
        self, provider: Provider | None = None
    ) -> tuple[RerankingModelCapabilities, ...]:
        """List all reranking models for a specific provider or all providers."""
        if provider is None:
            return tuple(
                cap
                for prov_map in self._reranking_capabilities.values()
                for cap_tuple in prov_map.values()
                for cap in cap_tuple
            )
        prov_map = self._reranking_capabilities.get(provider, {})
        return tuple(cap for cap_tuple in prov_map.values() for cap in cap_tuple)

    # ---------- Agentic model profiles (pydantic-ai) ----------
    def register_agent_profile(
        self,
        provider: Provider,
        model_glob: str,
        profile: AgentProfileSpec,
        *,
        replace: bool = True,
    ) -> None:
        """Register an agent profile for a specific provider and model glob."""
        rules = self._agent_profiles.setdefault(provider, [])
        if replace:
            rules[:] = [(g, p) for (g, p) in rules if g != model_glob]
        rules.append((model_glob, profile))

    def resolve_agent_profile(self, provider: Provider, model_name: str) -> AgentProfile | None:
        """Resolve the agent profile for a specific model name."""
        rules = self._agent_profiles.get(provider) or []
        name = model_name.strip()
        return next(
            (
                spec(name) if callable(spec) else spec
                for glob, spec in rules
                if glob == name or fnmatch(name, glob)
            ),
            None,
        )

    def _register_builtin_agent_profiles(self) -> None:
        """Register built-in agent profiles."""
        from codeweaver.providers.agent import KnownAgentModelName, infer_model

        model_names = KnownAgentModelName.__value__.__dict__["__args__"][:-1]
        for model_name in model_names:
            with contextlib.suppress(ValueError, AttributeError, ImportError):
                model_profile: AgentModel = infer_model(model_name)
                # These are `KnownAgentModelName`, which are just strings like: "provider:model"
                provider = Provider.from_string(
                    model_profile.profile.split(":")[1]  # type: ignore
                    if len(model_profile.profile.split(":")) > 1  # type: ignore
                    else model_profile.profile  # type: ignore
                )
                if not provider:
                    console.print(
                        f"[yellow]Warning:[/yellow] Could not infer provider for model '{model_name}' with profile '{model_profile.profile}'. Skipping registration."  # type: ignore
                    )
                else:
                    self.register_agent_profile(provider, model_name, model_profile, replace=False)  # type: ignore

    # ---------- Population helpers ----------
    def mark_defaults_populated(self) -> None:
        """Mark the default capabilities as populated."""
        self._populated_defaults = True

    def defaults_populated(self) -> bool:
        """Check if the default capabilities have been populated."""
        return self._populated_defaults

    def is_empty(self) -> bool:
        """Check if the registry is empty."""
        return not any(self._embedding_capabilities.values()) and not any(
            self._agent_profiles.values()
        )

    def models_for_provider(self, provider: Provider) -> ModelResult:
        """Get all models registered for a specific provider."""
        embedding_models = self.list_embedding_models(provider)
        sparse_embedding_models = self.list_sparse_embedding_models(provider)
        reranking_models = self.list_reranking_models(provider)
        agent_profiles = self._agent_profiles.get(provider)
        return ModelResult(
            provider=provider,
            embedding=embedding_models or None,
            sparse_embedding=sparse_embedding_models or None,
            reranking=reranking_models or None,
            agent=tuple(agent_profiles) if agent_profiles else None,
        )

    def configured_models_for_kind(
        self, kind: LiteralModelKinds
    ) -> (
        tuple[EmbeddingModelCapabilities, ...]
        | tuple[RerankingModelCapabilities, ...]
        | tuple[SparseEmbeddingModelCapabilities, ...]
        | EmbeddingModelCapabilities
        | RerankingModelCapabilities
        | SparseEmbeddingModelCapabilities
        | AgentProfile
        | None
    ):
        """Get all configured models for a specific kind."""
        from codeweaver.common.registry.provider import get_provider_config_for
        from codeweaver.providers.provider import ProviderKind

        kind = kind if isinstance(kind, ProviderKind) else ProviderKind.from_string(kind)
        if settings := get_provider_config_for(kind):
            provider = settings["provider"]
            # Extract model from nested model_settings structure
            model_settings = settings.get("model_settings")
            if not model_settings:
                return None
            model_name = model_settings.get("model")
            if not model_name:
                return None
            if kind == ProviderKind.EMBEDDING:
                return self.get_embedding_capabilities(provider, model_name)  # type: ignore
            if kind == ProviderKind.SPARSE_EMBEDDING:
                return self.get_sparse_embedding_capabilities(provider, model_name)  # type: ignore
            if kind == ProviderKind.RERANKING:
                return self.get_reranking_capabilities(provider, model_name)  # type: ignore
            if kind == ProviderKind.AGENT and (
                profile := self.resolve_agent_profile(provider, model_name)
            ):
                return profile
        return None

    def _telemetry_keys(self) -> None:
        return None


_registry: ModelRegistry | None = None


def get_model_registry() -> ModelRegistry:
    """Get or create the global model registry instance."""
    global _registry
    if _registry is None:
        _registry = ModelRegistry()
    return _registry


__all__ = ("ModelRegistry", "get_model_registry")
