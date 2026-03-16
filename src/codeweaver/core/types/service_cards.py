# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Mappings of provider types for various purposes (e.g. to clients, classes, etc.).

This module is an internal implementation detail. You shouldn't use it directly. It supplies the raw data used in the `Provider` and `SDKClient` and `ProviderCategory` enum classes (`codeweaver.core.types.provider`). Use those classes instead.

To allow for lazy loading and prevent circular imports, we put the mappings in this separate module and wrapped in functions. To avoid circular dependencies and initialization order issues, we require callers to pass in themselves (`ProviderCategory`, `Provider`, or `SDKClient`) either as a class or instance.
"""
# TODO: Is this in the right place? It's here because the it feeds data for methods in `Provider` and `SDKClient`, but it extends well beyond just being a 'type' module. But if we moved it out, we'd have to import it into types, which is not a great solution either; we could remove the methods from `Provider` and `SDKClient`, but that's a larger refactor...

from __future__ import annotations

import asyncio
import re

from collections import defaultdict
from collections.abc import Coroutine
from functools import cache
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Literal, NamedTuple, cast, overload

from beartype.typing import Callable
from lateimport import LateImport, lateimport

from codeweaver.core.utils import has_package


if TYPE_CHECKING:
    from codeweaver.core.types.provider import (
        LiteralProvider,  # Members of Provider
        LiteralProviderCategory,  # Members of ProviderCategory
        Provider,
        ProviderCategory,
        SDKClient,
    )

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


type ProviderCategoryLiteralString = Literal[
    "agent", "data", "embedding", "reranking", "sparse_embedding", "vector_store"
]

type ProviderLiteralString = Literal[
    "alibaba",
    "anthropic",
    "azure",
    "bedrock",
    "cerebras",
    "cohere",
    "deepseek",
    "duckduckgo",
    "exa",
    "fastembed",
    "fireworks",
    "gateway",
    "github",
    "google",
    "groq",
    "heroku",
    "hf_inference",
    "litellm",
    "memory",
    "mistral",
    "moonshot",
    "morph",
    "nebius",
    "ollama",
    "openai",
    "openrouter",
    "ovhcloud",
    "perplexity",
    "qdrant",
    "sambanova",
    "sentence_transformers",
    "tavily",
    "together",
    "vercel",
    "voyage",
    "x_ai",
    # "outlines",
]

type SDKClientLiteralString = Literal[
    "anthropic",
    "bedrock",
    "cohere",
    "duckduckgo",
    "exa",
    "fastembed",
    "gateway",
    "google",
    "groq",
    "hf_inference",
    "mistral",
    "openai",
    "qdrant",
    "sentence_transformers",
    "tavily",
    "voyage",
    "x_ai",
]


def _all_provider_gen() -> set[ProviderLiteralString]:
    """Generate the set of all provider literals.

    Returns:
        A set of all provider literals as strings.
    """
    # we only need to maintain the ProviderLiteralString union this way.
    return set(ProviderLiteralString.__value__.__args__)


def _never_use_other_api() -> set[ProviderLiteralString]:
    """These are providers that (at least in CodeWeaver) never use any API other than their own SDK/client.

    This does not mean that others *don't* also use their API, just that they themselves never use anything else. It also does not mean any *models* associated with these providers aren't also available on other APIs. A `provider` is who you pay, not the client/API, or models.
    """
    return set(SDKClientLiteralString.__value__.__args__) - {"bedrock"}


def _never_use_openai_api() -> set[ProviderLiteralString]:
    """Get the set of providers that never use the OpenAI API.

    Returns:
        A set of provider literals that never use the OpenAI API.
    """
    return {"bedrock", "memory"} | _never_use_other_api()


def _sometimes_use_openai_api() -> set[ProviderLiteralString]:
    return {"azure", "heroku", "google", "groq"}


def _local_only_providers() -> set[ProviderLiteralString]:
    """Get the set of local-only providers.

    Returns:
        A set of provider literals that are local-only.
    """
    return {"fastembed", "sentence_transformers", "memory"}


def _sometimes_local_providers() -> set[ProviderLiteralString]:
    """Get the set of sometimes-local providers.

    Returns:
        A set of provider literals that are sometimes local.
    """
    return {"ollama", "qdrant"}


@cache
def _always_use_openai_api() -> set[ProviderLiteralString]:
    """These are providers that (at least in CodeWeaver) do not always use the OpenAI API.

    This means that they have their own SDK/client, and may also use other APIs.

    It also does not mean any *models* associated with these providers aren't also available on the OpenAI API. A `provider` is who you pay, not the client/API, or models.
    """
    return _all_provider_gen() - _never_use_openai_api() - _sometimes_use_openai_api()


def get_openai_providers() -> set[ProviderLiteralString]:
    """Get the set of OpenAI-related providers.

    Returns:
        A set of provider strings that use the OpenAI API.
    """
    return _sometimes_use_openai_api() | _always_use_openai_api()


def get_provider_literals() -> set[ProviderLiteralString]:
    """Get the set of all provider literals.

    Returns:
        A set of all provider literals as strings.
    """
    return _all_provider_gen()


def get_local_only_providers() -> set[ProviderLiteralString]:
    """Get the set of local-only providers.

    Returns:
        A set of provider strings that are local-only.
    """
    return _local_only_providers()


def get_sometimes_local_providers() -> set[ProviderLiteralString]:
    """Get the set of sometimes-local providers.

    Returns:
        A set of provider strings that are sometimes local.
    """
    return _sometimes_local_providers()


def get_sometimes_local_provider_members(
    provider_cls: type[Provider],
) -> set[ProviderLiteralString]:
    """Get the set of sometimes-local provider members.

    Args:
        provider_cls: The `Provider` class to get members from.

    Returns:
        A set of `Provider` members that are sometimes local.
    """
    return {provider_cls.from_string(p) for p in get_sometimes_local_providers()}


def get_openai_provider_members(provider_cls: type[Provider]) -> set[ProviderLiteralString]:
    """Get the set of OpenAI-related provider members.

    Args:
        provider_cls: The `Provider` class to get members from.

    Returns:
        A set of `Provider` members that use the OpenAI API.
    """
    return {provider_cls.from_string(p) for p in get_openai_providers()}


def get_local_only_provider_members(provider_cls: type[Provider]) -> set[ProviderLiteralString]:
    """Get the set of local-only provider members.

    Args:
        provider_cls: The `Provider` class to get members from.

    Returns:
        A set of `Provider` members that are local-only.
    """
    return {provider_cls.from_string(p) for p in _local_only_providers()}


# exclusivity groups
# Groups of providers that are mutually exclusive in some way.


def _data_providers():
    return {"duckduckgo", "exa", "tavily"}


def _vector_providers():
    return {"memory", "qdrant"}


def _sparse_providers():
    return _local_only_providers() - _non_model_providers()


def _non_model_providers():
    return _data_providers() | _vector_providers()


def _non_agent_providers():
    return {"voyage"} | _local_only_providers() | _non_model_providers()


def _agent_providers():
    return _all_provider_gen() - _non_agent_providers()


def _agent_only_providers():
    return {
        "alibaba",
        "cerebras",
        "deepseek",
        "gateway",
        "litellm",
        "moonshot",
        "nebius",
        "openrouter",
        "ovhcloud",
        "perplexity",
        "sambanova",
        "x_ai",
    }


def _openai_agent_providers():
    return get_openai_providers() - {"groq"}


def _openai_embedding_providers():
    return get_openai_providers() - _agent_only_providers() - {"google"}


def _embedding_providers():
    return _all_provider_gen() - _non_model_providers() - _agent_only_providers()


def _reranking_providers():
    return (_local_only_providers() - _non_model_providers()) | {"bedrock", "cohere", "voyage"}


def _trifecta_providers():
    return _all_provider_gen() & (
        _reranking_providers() & _embedding_providers() & _agent_providers()
    )


class ServiceMetadata(NamedTuple):
    """Optional metadata for services requiring special handling.

    Used for multi-client scenarios (e.g., Azure supporting both OpenAI and Anthropic)
    or cases requiring custom instantiation logic.
    """

    discriminator: tuple[Literal["model", "client"], str | re.Pattern] | None = None
    """For multi-client providers, determines which card to use.

    Format: (discriminator_category, discriminator_value)

    - ("model", "claude"): Use this card if model name starts with "claude"
    - ("client", "openai"): Use this card if client preference is "openai"

    Example: Azure agent can use Anthropic (for Claude models) or OpenAI (default).
    """

    client_handler: (
        Callable[[Any, ServiceCard, ...], Any]
        | Callable[[Any, ServiceCard, ...], Coroutine[Any, Any, Any]]
        | None
    ) = None
    """Custom instantiation handler for the SDK client.

    The function receives the client class (resolved from client_cls), the service card instance,
    and any args/kwargs needed for instantiation. It returns the instantiated client.
    The function may be sync or async.
    """

    provider_handler: (
        Callable[[Any, ServiceCard, ...], Any]
        | Callable[[Any, ServiceCard, ...], Coroutine[Any, Any, Any]]
        | None
    ) = None
    """Custom instantiation handler for the provider wrapper.

    The function receives the provider class (resolved from provider_cls), the service card instance,
    and any args/kwargs needed for instantiation. It returns the instantiated provider.
    The function may be sync or async.
    """


class ServiceCard(NamedTuple):
    """Service card representing a provider-category-client combination.

    A ServiceCard maps a provider-category pair to the actual provider class and
    client class needed to instantiate that service. For example:
    - (cohere, reranking) → (CohereRerankingProvider, AsyncClientV2)

    For multi-client scenarios (Azure, Bedrock, etc.), multiple cards exist
    with different metadata.discriminator values to select the right one.
    """

    provider: LiteralProvider
    """The provider (the service you pay for, e.g., 'openai', 'cohere')."""

    category: LiteralProviderCategory
    """The category of service (e.g., 'embedding', 'agent', 'reranking')."""

    provider_cls: LateImport[Any]
    """The provider class (e.g., CohereProvider, OpenAIEmbeddingProvider).

    This is the class that wraps the client and implements the CodeWeaver
    provider interface for this service type. (or pydantic AI interface for agents)
    """

    client_cls: LateImport[Any]
    """The SDK client class (e.g., AsyncCohereV2, AsyncOpenAI, Mistral).

    This is the actual SDK client from the provider's library that will be
    instantiated to make API calls.
    """

    client: SDKClientLiteralString

    metadata: ServiceMetadata | None = None
    """Optional metadata for multi-client scenarios or special handling.

    Most cards have metadata=None. Only needed for:
    - Multi-client providers (Azure, Bedrock) - uses discriminator
    - Custom instantiation logic - uses handler
    """

    def _default_agent_handler(self, *args: Any, **kwargs: Any) -> Any:
        """All agents require a slight difference in handling to construct the provider."""
        if self.category != "agent":
            raise ValueError("Default agent handler can only be used for agent category.")
        provider_cls = self.provider_cls._resolve()
        client_key = (
            f"{self.client}_client"
            if self.client not in {"hf_inference", "x_ai"}
            else f"{self.client.replace('_inference', '').replace('_', '')}_client"
        )
        if kwargs.get("client"):
            kwargs[client_key] = kwargs.pop("client")
        else:
            kwargs[client_key] = self.create_instance(
                "client", *args, **kwargs.get("client_options", {})
            )
        if self.metadata and self.metadata.provider_handler:
            return self.metadata.provider_handler(provider_cls, self, *args, **kwargs)
        return provider_cls(*args, **kwargs)

    def has_multiple(self) -> bool:
        """Check if this service card is part of a multi-client scenario."""
        return self.metadata is not None and self.metadata.discriminator is not None

    def evaluate(self, model_name: str | None = None, client_preference: str | None = None) -> bool:
        """Evaluate if this service card matches the given model name or client preference.

        Used in multi-client scenarios to determine if this card should be selected
        based on the discriminator.

        Args:
            model_name: The model name to check against the discriminator (if category is "model").
            client_preference: The client preference to check against the discriminator (if category is "client").

        Returns:
            True if this card matches the discriminator criteria, False otherwise.
        """
        if not self.has_multiple():
            return True  # No discriminator, always matches

        disc_category = self.discriminator_category
        disc_value = self.discriminator

        if disc_category == "model" and model_name is not None:
            if isinstance(disc_value, re.Pattern):
                return bool(disc_value.match(model_name))
            return model_name.startswith(disc_value)

        if disc_category == "client" and client_preference is not None:
            return client_preference == disc_value

        return False  # No match if required info not provided

    @property
    def is_only_client(self) -> bool:
        """Check if this card is the only client for its provider-category."""
        return not self.has_multiple()

    @property
    def discriminator_category(self) -> Literal["model", "client"] | None:
        """Get the discriminator category if this card has a discriminator."""
        if self.metadata and self.metadata.discriminator:
            return self.metadata.discriminator[0]
        return None

    @property
    def discriminator(self) -> str | re.Pattern | None:
        """Get the discriminator value if this card has a discriminator."""
        if self.metadata and self.metadata.discriminator:
            return self.metadata.discriminator[1]
        return None

    def _apply_handler(
        self, target: Literal["client", "provider"], *args: Any, **kwargs: Any
    ) -> Any:
        """Apply the custom handler if it exists, otherwise return None.

        This is used to get the actual client or provider instance when a card has a custom handler defined.
        """
        if not self.metadata:
            return None

        handler = (
            self.metadata.client_handler if target == "client" else self.metadata.provider_handler
        )
        if not handler and self.category == "agent" and target == "provider":
            return self._default_agent_handler(*args, **kwargs)
        if not handler:
            return None

        import_cls = self.client_cls if target == "client" else self.provider_cls
        return handler(import_cls._resolve(), self, *args, **kwargs)

    def create_instance(
        self, target: Literal["client", "provider"], *args: Any, **kwargs: Any
    ) -> Any:
        """Create an instance of the client or provider using the handler if it exists, otherwise standard instantiation.

        This is a convenience method that abstracts away the logic of checking for a handler and applying it, versus just instantiating the client or provider in the standard way. The caller can simply call `card.create_instance()` and get the correct instance based on the card's configuration.

        Args:
            target: Whether to create a "client" or "provider" instance.
            *args: Positional arguments to pass to the handler function if it exists.
            **kwargs: Keyword arguments to pass to the handler function if it exists.

        Returns:
            An instance of the client or provider as defined by this service card.
        """
        try:
            target_cls = (
                self.client_cls._resolve() if target == "client" else self.provider_cls._resolve()
            )
        except (ImportError, AttributeError, KeyError):
            raise ValueError(
                f"Failed to resolve {target} class for provider {self.provider} and category {self.category}."
            ) from None

        result = self._apply_handler(target, *args, **kwargs)
        if result is None:
            result = target_cls(*args, **kwargs)

        return result

    async def create_instance_async(
        self, target: Literal["client", "provider"], *args: Any, **kwargs: Any
    ) -> Any:
        """Asynchronously create an instance, awaiting if the handler or constructor is async."""
        result = self.create_instance(target, *args, **kwargs)
        return await result if asyncio.iscoroutine(result) else result


@overload
def service_card_factory(
    provider: ProviderLiteralString,
    category: ProviderCategoryLiteralString,
    provider_cls: LateImport[Any],
    client_cls: LateImport[Any],
    client: SDKClientLiteralString,
) -> ServiceCard: ...


@overload
def service_card_factory(
    provider: ProviderLiteralString,
    category: ProviderCategoryLiteralString,
    provider_cls: LateImport[Any],
    client_cls: LateImport[Any],
    client: SDKClientLiteralString,
    *,
    metadata: ServiceMetadata,
) -> ServiceCard: ...


def service_card_factory(
    provider: ProviderLiteralString,
    category: ProviderCategoryLiteralString,
    provider_cls: LateImport[Any],
    client_cls: LateImport[Any],
    client: SDKClientLiteralString,
    *,
    metadata: ServiceMetadata | None = None,
) -> ServiceCard:
    """Factory function to create a ServiceCard with proper type checking.

    Simplified factory that creates ServiceCards with 4 core fields and
    optional metadata for special cases.

    Args:
        provider: The provider (the service you pay for).
        category: The category of service (embedding, agent, etc.).
        provider_cls: The provider class (e.g., CohereProvider).
        client_cls: The client class (e.g., AsyncCohereV2).
        metadata: Optional metadata for multi-client scenarios or special handling.

    Returns:
        A ServiceCard instance.

    Examples:
        Simple case (most providers):
        >>> service_card_factory(
        ...     "openai",
        ...     "embedding",
        ...     lateimport("codeweaver.providers.embedding", "OpenAIEmbeddingProvider"),
        ...     lateimport("openai", "AsyncOpenAI"),
        ...     client="openai",
        ... )

        Multi-client with discriminator:
        >>> service_card_factory(
        ...     "azure",
        ...     "agent",
        ...     lateimport("pydantic_ai.providers.anthropic", "AnthropicProvider"),
        ...     lateimport("anthropic", "AsyncAnthropicFoundry"),
        ...     "anthropic",
        ...     metadata=ServiceMetadata(discriminator=("model", "claude")),
        ... )

        Custom handler:
        >>> service_card_factory(
        ...     "bedrock",
        ...     "embedding",
        ...     lateimport("codeweaver.providers.embedding", "BedrockEmbeddingProvider"),
        ...     lateimport("boto3", "client"),
        ...     "bedrock",
        ...     metadata=ServiceMetadata(handler=("client", bedrock_client_factory)),
        ... )
    """
    return ServiceCard(
        provider=provider,
        category=category,
        provider_cls=provider_cls,
        client_cls=client_cls,
        client=client,
        metadata=metadata,
    )


# ===========================================================================
# *                    Registry Validation
# ===========================================================================


def _validate_registry(cards: tuple[ServiceCard, ...]) -> None:
    """Validate the service card registry for consistency.

    Logs warnings for suspicious patterns but doesn't raise exceptions.
    This helps catch configuration issues without blocking imports.

    Validation checks:
    - Duplicate cards (same provider-category-discriminator)
    - Multi-client scenarios with inconsistent discriminator patterns
    - Missing default fallback cards for multi-client providers

    Args:
        cards: The complete tuple of service cards to validate.
    """
    import logging

    from collections import defaultdict

    logger = logging.getLogger(__name__)

    seen: set[tuple[ProviderLiteralString, ProviderCategoryLiteralString, str | None]] = set()
    multi_client: defaultdict[
        tuple[ProviderLiteralString, ProviderCategoryLiteralString], list[ServiceCard]
    ] = defaultdict(list)

    for card in cards:
        # Track multi-client scenarios
        key = (card.provider, card.category)
        multi_client[key].append(card)

        # Check for exact duplicates
        disc = (
            card.metadata.discriminator[1]
            if card.metadata and card.metadata.discriminator
            else None
        )
        full_key = (card.provider, card.category, disc)

        if full_key in seen:
            logger.warning("Duplicate service card detected: %s", full_key)
        seen.add(full_key)

    # Validate multi-client discriminator logic
    for (provider, category), card_list in multi_client.items():
        if len(card_list) > 1:
            has_default = any(
                c.metadata is None or c.metadata.discriminator is None for c in card_list
            )
            has_discriminators = any(c.metadata and c.metadata.discriminator for c in card_list)

            if has_discriminators and not has_default:
                logger.warning(
                    "Multi-client %s-%s has discriminators but no default fallback. "
                    "Consider adding a card with metadata=None for the default case.",
                    provider,
                    category,
                )

            if not has_discriminators:
                logger.warning(
                    "Multi-client %s-%s has multiple cards but no discriminators. "
                    "Selection will be non-deterministic (first match wins).",
                    provider,
                    category,
                )


# ===========================================================================
# *                    Service Card Registry
# ===========================================================================

_anthropic_model_discriminator = (
    "model",
    re.compile(r".*(claude|opus|sonnet|haiku).*", re.IGNORECASE),
)


@cache
def _build_service_card_registry() -> tuple[ServiceCard, ...]:
    """Build the complete registry of service cards.

    Returns immutable tuple for caching and thread safety.
    All provider-category-client mappings are defined through this registry.

    The registry is built from pattern-specific builder functions that handle
    common scenarios (OpenAI API, native SDKs, local providers, multi-client).

    Returns:
        Immutable tuple of all service cards.
    """
    cards: list[ServiceCard] = []

    # Build cards for each category
    cards.extend(_build_openai_api_cards())
    cards.extend(_build_native_sdk_cards())
    cards.extend(_build_local_provider_cards())
    cards.extend(_build_pydantic_gateway_provider_cards())
    cards.extend(_build_multi_client_cards())
    cards.extend(_build_data_provider_cards())
    cards.extend(_build_vector_store_cards())

    registry = tuple(cards)
    _validate_registry(registry)
    return registry


def _get_pydantic_ai_cls_module(provider_name: str) -> str:
    """Get the module name for a given provider in the pydantic_ai.providers namespace.

    This is needed to correctly import provider classes for the service cards, especially for providers that have different naming conventions between the provider literal and the module name.

    Args:
        provider_name: The provider literal string (e.g., "hf_inference", "moonshot").

    Returns:
        The module name to use for importing the provider class.
    """
    if provider_name == "hf_inference":
        return "huggingface"
    return "moonshotai" if provider_name == "moonshot" else provider_name


def _get_pydantic_ai_provider_cls(provider_name: str) -> LateImport[Any]:
    """Get the LateImport for the provider class in the pydantic_ai.providers namespace.

    This uses the provider name to determine the correct module and class name to import for the provider. It handles special cases where the provider literal does not directly match the module or class name.

    Args:
        provider_name: The provider literal string (e.g., "hf_inference", "moonshot").

    Returns:
        A LateImport for the provider class.
    """
    module_name = _get_pydantic_ai_cls_module(provider_name)
    class_name = f"{module_name.title().replace('_', '')}Provider"
    if module_name in {"moonshotai", "openai", "litellm", "huggingface", "ovhcloud"}:
        class_name = (
            class_name
            .replace("ai", "AI")
            .replace("llm", "LLM")
            .replace("face", "Face")
            .replace("Ovhcloud", "OVHcloud")
        )  # the c is lowercase ... for some reason, I guess to distinguish the acronym from "cloud"?
    return lateimport(f"pydantic_ai.providers.{module_name}", class_name)


# Builder function stubs - will implement next
def _build_openai_api_cards() -> list[ServiceCard]:
    """Build service cards for OpenAI API-compatible providers.

    These providers use the OpenAI SDK (AsyncOpenAI) but may connect to different endpoints.
    Includes ~15 providers that implement the OpenAI-compatible API.

    Excludes: Azure, Heroku, Google, Groq (multi-client or special handling)
    """
    agent_cards = [
        service_card_factory(
            provider=provider,
            category="agent",
            provider_cls=_get_pydantic_ai_provider_cls(provider),
            client_cls=lateimport("openai", "AsyncOpenAI"),
            client="openai",
        )
        for provider in _openai_agent_providers()
    ]

    embedding_cards = [
        service_card_factory(
            provider=provider,
            category="embedding",
            provider_cls=lateimport(
                "codeweaver.providers.embedding.providers.openai_factory", "get_provider_class"
            ),
            client_cls=lateimport("openai", "AsyncOpenAI"),
            client="openai",
        )
        for provider in _openai_embedding_providers()
    ]

    return agent_cards + embedding_cards


def _build_native_sdk_cards() -> list[ServiceCard]:
    """Build service cards for providers with their own native SDKs.

    These providers have their own SDK client libraries (not OpenAI-compatible).
    Includes: Mistral, Cohere, Voyage, Anthropic, Google, HuggingFace, Gateway.
    """
    return [
        # Mistral
        service_card_factory(
            "mistral",
            "agent",
            _get_pydantic_ai_provider_cls("mistral"),
            lateimport("mistralai", "Mistral"),
            "mistral",
        ),
        service_card_factory(
            "mistral",
            "embedding",
            lateimport(
                "codeweaver.providers.embedding.providers.mistral", "MistralEmbeddingProvider"
            ),
            lateimport("mistralai", "Mistral"),
            "mistral",
        ),
        # Cohere - agent, embedding, reranking
        service_card_factory(
            "cohere",
            "agent",
            _get_pydantic_ai_provider_cls("cohere"),
            lateimport("cohere", "AsyncClientV2"),
            "cohere",
        ),
        service_card_factory(
            "cohere",
            "embedding",
            lateimport(
                "codeweaver.providers.embedding.providers.cohere", "CohereEmbeddingProvider"
            ),
            lateimport("cohere", "AsyncClientV2"),
            "cohere",
        ),
        service_card_factory(
            "cohere",
            "reranking",
            lateimport(
                "codeweaver.providers.reranking.providers.cohere", "CohereRerankingProvider"
            ),
            lateimport("cohere", "AsyncClientV2"),
            "cohere",
        ),
        # Voyage - embedding and reranking
        service_card_factory(
            "voyage",
            "embedding",
            lateimport(
                "codeweaver.providers.embedding.providers.voyage", "VoyageEmbeddingProvider"
            ),
            lateimport("voyageai", "VoyageAI"),
            "voyage",
        ),
        service_card_factory(
            "voyage",
            "reranking",
            lateimport(
                "codeweaver.providers.reranking.providers.voyage", "VoyageRerankingProvider"
            ),
            lateimport("voyageai", "VoyageAI"),
            "voyage",
        ),
        # Anthropic - agent only (non-Azure/Bedrock/Google)
        service_card_factory(
            "anthropic",
            "agent",
            _get_pydantic_ai_provider_cls("anthropic"),
            lateimport("anthropic", "AsyncAnthropic"),
            "anthropic",
        ),
        # Google - agent and embedding
        service_card_factory(
            "google",
            "agent",
            _get_pydantic_ai_provider_cls("google"),
            lateimport("google.genai", "Client"),
            "google",
        ),
        service_card_factory(
            "google",
            "embedding",
            lateimport(
                "codeweaver.providers.embedding.providers.google", "GoogleEmbeddingProvider"
            ),
            lateimport("google.genai", "Client"),
            "google",
        ),
        # HuggingFace Inference - agent and embedding
        service_card_factory(
            "hf_inference",
            "agent",
            _get_pydantic_ai_provider_cls("hf_inference"),
            lateimport("huggingface_hub", "AsyncInferenceClient"),
            "hf_inference",
        ),
        service_card_factory(
            "hf_inference",
            "embedding",
            lateimport(
                "codeweaver.providers.embedding.providers.huggingface",
                "HuggingFaceEmbeddingProvider",
            ),
            lateimport("huggingface_hub", "AsyncInferenceClient"),
            "hf_inference",
        ),
        service_card_factory(
            "x_ai",
            "agent",
            _get_pydantic_ai_provider_cls("xai"),
            lateimport("xai_sdk", "AsyncClient"),
            "x_ai",
        ),
    ]


async def _start_instance_in_thread(
    cls: type[Any], card: ServiceCard, *args: Any, **kwargs: Any
) -> Any:
    """Helper function to start an instance in a separate thread for sync handlers."""
    return await asyncio.to_thread(cls, *args, **kwargs)


async def _start_cross_encoder_in_thread(
    get_cls_fn: Any, card: ServiceCard, *args: Any, **kwargs: Any
) -> Any:
    """Handler for fastembed cross encoder: call factory to get class, then instantiate.

    The cross encoder service card uses `get_cross_encoder` (a factory function) as
    client_cls. This handler first calls the factory (with no args) to get the
    enhanced TextCrossEncoder class, then instantiates it with the provided kwargs.

    Empty list values (e.g. device_ids=[]) are removed from kwargs to avoid
    IndexError in fastembed's OnnxTextCrossEncoder when it tries device_ids[0].
    """
    cls = get_cls_fn()  # get_cross_encoder() -> type[TextCrossEncoder]
    # Filter out empty list values that would cause IndexError in fastembed
    filtered_kwargs = {k: v for k, v in kwargs.items() if not (isinstance(v, list) and len(v) == 0)}
    return await asyncio.to_thread(cls, *args, **filtered_kwargs)


def _build_local_provider_cards() -> list[ServiceCard]:
    """Build service cards for local-only providers (Fastembed, Sentence Transformers).

    These providers run entirely locally without external API calls.
    Both support embedding, sparse embedding, and reranking.
    """
    return [
        service_card_factory(
            "fastembed",
            "embedding",
            lateimport(
                "codeweaver.providers.embedding.providers.fastembed", "FastEmbedEmbeddingProvider"
            ),
            lateimport("codeweaver.providers.embedding.fastembed_extensions", "get_text_embedder"),
            "fastembed",
            metadata=ServiceMetadata(client_handler=_start_instance_in_thread),
        ),
        service_card_factory(
            "fastembed",
            "sparse_embedding",
            lateimport(
                "codeweaver.providers.embedding.providers.fastembed", "FastEmbedSparseProvider"
            ),
            lateimport(
                "codeweaver.providers.embedding.fastembed_extensions", "get_sparse_embedder"
            ),
            "fastembed",
            metadata=ServiceMetadata(client_handler=_start_instance_in_thread),
        ),
        service_card_factory(
            "fastembed",
            "reranking",
            lateimport(
                "codeweaver.providers.reranking.providers.fastembed", "FastEmbedRerankingProvider"
            ),
            lateimport("codeweaver.providers.embedding.fastembed_extensions", "get_cross_encoder"),
            "fastembed",
            metadata=ServiceMetadata(client_handler=_start_cross_encoder_in_thread),
        ),
        # Sentence Transformers - embedding, sparse_embedding, reranking
        service_card_factory(
            "sentence_transformers",
            "embedding",
            lateimport(
                "codeweaver.providers.embedding.providers.sentence_transformers",
                "SentenceTransformersEmbeddingProvider",
            ),
            lateimport("sentence_transformers", "SentenceTransformer"),
            "sentence_transformers",
            metadata=ServiceMetadata(client_handler=_start_instance_in_thread),
        ),
        service_card_factory(
            "sentence_transformers",
            "sparse_embedding",
            lateimport(
                "codeweaver.providers.embedding.providers.sentence_transformers",
                "SentenceTransformersSparseEmbeddingProvider",
            ),
            lateimport("sentence_transformers", "SparseEncoder"),
            "sentence_transformers",
            metadata=ServiceMetadata(client_handler=_start_instance_in_thread),
        ),
        service_card_factory(
            "sentence_transformers",
            "reranking",
            lateimport(
                "codeweaver.providers.reranking.providers.sentence_transformers",
                "SentenceTransformersRerankingProvider",
            ),
            lateimport("sentence_transformers", "CrossEncoder"),
            "sentence_transformers",
            metadata=ServiceMetadata(client_handler=_start_instance_in_thread),
        ),
    ]


def _build_multi_client_cards() -> list[ServiceCard]:
    """Build service cards for multi-client providers (Azure, Bedrock, Heroku, Groq).

    These providers can use multiple different SDK clients depending on context:
    - Model-based discrimination: Select client based on model name
    - Client-based discrimination: Select based on explicit client preference

    Each multi-client scenario should have:
    - One or more cards with discriminators for specific cases
    - One card without discriminator as the default fallback
    """
    anthropic_provider = _get_pydantic_ai_provider_cls("anthropic")
    return [
        service_card_factory(
            "azure",
            "agent",
            anthropic_provider,
            lateimport("anthropic", "AsyncAnthropicFoundry"),
            "anthropic",
            metadata=ServiceMetadata(discriminator=("model", _anthropic_model_discriminator)),
        ),
        service_card_factory(
            "azure",
            "agent",
            _get_pydantic_ai_provider_cls("azure"),
            lateimport("openai", "AsyncOpenAI"),
            "openai",
        ),
        # Azure - Embedding (OpenAI or Cohere)
        # Use Cohere for Cohere models
        service_card_factory(
            "azure",
            "embedding",
            lateimport(
                "codeweaver.providers.embedding.providers.cohere", "CohereEmbeddingProvider"
            ),
            lateimport("cohere", "AsyncClientV2"),
            "cohere",
            metadata=ServiceMetadata(
                discriminator=(
                    "model",
                    # currently only embed-v4 but assuming 5 will follow the pattern
                    re.compile(r"^embed-(english-|multilingual-|v[45]).*", re.IGNORECASE),
                )
            ),
        ),
        # Use OpenAI by default
        service_card_factory(
            "azure",
            "embedding",
            lateimport(
                "codeweaver.providers.embedding.providers.openai_factory", "get_provider_class"
            ),
            lateimport("openai", "AsyncOpenAI"),
            "openai",
        ),
        # Bedrock - Agent (Bedrock or Anthropic based on model)
        # Use Anthropic client for Claude models on Bedrock
        service_card_factory(
            "bedrock",
            "agent",
            anthropic_provider,
            lateimport("anthropic", "AsyncAnthropicBedrock"),
            "anthropic",
            metadata=ServiceMetadata(discriminator=("model", _anthropic_model_discriminator)),
        ),
        # Use Bedrock client for other models (default)
        service_card_factory(
            "bedrock",
            "agent",
            lateimport("pydantic_ai.providers.bedrock", "BedrockProvider"),
            lateimport("boto3", "client"),
            "bedrock",
            metadata=ServiceMetadata(
                client_handler=lambda client, card, *args, **kwargs: client(
                    "bedrock-runtime", *args, **kwargs
                )
            ),
        ),
        # Bedrock - Embedding and Reranking (only bedrock client)
        service_card_factory(
            "bedrock",
            "embedding",
            lateimport(
                "codeweaver.providers.embedding.providers.bedrock", "BedrockEmbeddingProvider"
            ),
            lateimport("boto3", "client"),
            "bedrock",
            metadata=ServiceMetadata(
                client_handler=lambda client, card, *args, **kwargs: client(
                    "bedrock-runtime", *args, **kwargs
                )
            ),
        ),
        service_card_factory(
            "bedrock",
            "reranking",
            lateimport(
                "codeweaver.providers.reranking.providers.bedrock", "BedrockRerankingProvider"
            ),
            lateimport("boto3", "client"),
            "bedrock",
            metadata=ServiceMetadata(
                client_handler=lambda client, card, *args, **kwargs: client(
                    "bedrock-agent-runtime", *args, **kwargs
                )
            ),
        ),
        # Heroku - Agent and Embedding (OpenAI or Cohere)
        # Note: Heroku uses same client for both agent and embedding per provider
        # Cohere client
        service_card_factory(
            "heroku",
            "agent",
            _get_pydantic_ai_provider_cls("cohere"),
            lateimport("cohere", "AsyncClientV2"),
            "cohere",
            metadata=ServiceMetadata(discriminator=("model", "cohere")),
        ),
        # OpenAI client (default)
        service_card_factory(
            "heroku",
            "agent",
            _get_pydantic_ai_provider_cls("heroku"),
            lateimport("openai", "AsyncOpenAI"),
            "openai",
        ),
        # Cohere embedding
        service_card_factory(
            "heroku",
            "embedding",
            lateimport(
                "codeweaver.providers.embedding.providers.cohere", "CohereEmbeddingProvider"
            ),
            lateimport("cohere", "AsyncClientV2"),
            "cohere",
            metadata=ServiceMetadata(discriminator=("model", "cohere-embed")),
        ),
        # OpenAI embedding (default)
        service_card_factory(
            "heroku",
            "embedding",
            lateimport(
                "codeweaver.providers.embedding.providers.openai_factory", "get_provider_class"
            ),
            lateimport("openai", "AsyncOpenAI"),
            "openai",
        ),
        # Groq - Special case: agent uses Groq client, embedding uses OpenAI client
        service_card_factory(
            "groq",
            "agent",
            _get_pydantic_ai_provider_cls("groq"),
            lateimport("groq", "AsyncGroq"),
            "groq",
        ),
        service_card_factory(
            "groq",
            "embedding",
            lateimport(
                "codeweaver.providers.embedding.providers.openai_factory", "get_provider_class"
            ),
            lateimport("openai", "AsyncOpenAI"),
            "openai",
        ),
        # Pydantic Gateway - agent only
        service_card_factory(
            "gateway",
            "agent",
            lateimport("pydantic_ai.providers.gateway", "gateway_provider"),
            lateimport("pydantic_ai.providers.gateway", "gateway_provider"),
            "gateway",
            metadata=ServiceMetadata(
                provider_handler=lambda provider_cls, card, upstream_provider, **kwargs: (
                    provider_cls(upstream_provider=upstream_provider, **kwargs)
                )
            ),
        ),
    ]


def _build_pydantic_gateway_provider_cards() -> list[ServiceCard]:
    """Build service cards for Pydantic Gateway provider.

    Pydantic Gateway is a special provider that routes requests to various LLMs.
    It uses its own client for both agent and embedding services.
    """
    return [
        service_card_factory(
            "gateway",
            "agent",
            lateimport("pydantic_ai.providers.gateway", "gateway_provider"),
            lateimport("pydantic_ai.providers.gateway", "gateway_provider"),
            "gateway",
            metadata=ServiceMetadata(
                provider_handler=lambda provider_cls, card, upstream_provider, **kwargs: (
                    provider_cls(upstream_provider=upstream_provider, **kwargs)
                )
            ),
        )
    ]


def _build_data_provider_cards() -> list[ServiceCard]:
    """Build service cards for data providers (Tavily, DuckDuckGo).

    Data providers are used for web search and data retrieval.
    """
    return [
        service_card_factory(
            "tavily",
            "data",
            lateimport("codeweaver.providers.data.tavily", "tavily_search_tool"),
            lateimport("tavily", "AsyncTavilyClient"),
            "tavily",
            metadata=ServiceMetadata(
                # provider_cls is tavily_search_tool; called with (client, **extra_kwargs)
                provider_handler=lambda provider_cls, card, client=None, **kwargs: provider_cls(
                    client
                )
            ),
        ),
        service_card_factory(
            "duckduckgo",
            "data",
            lateimport("codeweaver.providers.data.duckduckgo", "duckduckgo_search_tool"),
            lateimport("ddgs.ddgs", "DDGS"),
            "duckduckgo",
            metadata=ServiceMetadata(
                # provider_cls is duckduckgo_search_tool; called with (client, **extra_kwargs)
                provider_handler=lambda provider_cls, card, client=None, **kwargs: provider_cls(
                    client, max_results=15
                )
            ),
        ),
        service_card_factory(
            "exa",
            "data",
            lateimport("codeweaver.providers.data.exa", "ExaToolset"),
            lateimport("exa_py", "AsyncExa"),
            "exa",
        ),
    ]


def _build_vector_store_cards() -> list[ServiceCard]:
    """Build service cards for vector store providers (Qdrant, Memory).

    Vector stores are used for storing and querying embeddings.
    Both use AsyncQdrantClient, but Memory is in-memory with JSON persistence.
    """
    return [
        service_card_factory(
            "qdrant",
            "vector_store",
            lateimport("codeweaver.providers.vector_stores.qdrant", "QdrantVectorStoreProvider"),
            lateimport("qdrant_client", "AsyncQdrantClient"),
            "qdrant",
        ),
        service_card_factory(
            "memory",
            "vector_store",
            lateimport("codeweaver.providers.vector_stores.inmemory", "MemoryVectorStoreProvider"),
            lateimport("qdrant_client", "AsyncQdrantClient"),
            "qdrant",
        ),
    ]


# ===========================================================================
# *                    Query Interface - Helper Functions
# ===========================================================================


def _match_discriminator(
    card: ServiceCard, model_hint: str | None = None, client_preference: str | None = None
) -> bool:
    """Check if a service card matches the given model or client discriminator.

    Args:
        card: The service card to check.
        model_hint: Optional model name to match against model discriminators.
        client_preference: Optional client name to match against client discriminators.

    Returns:
        True if the card matches the discriminator, False otherwise.
        Cards without discriminators always return True (they're defaults).
    """
    if not card.metadata or not card.metadata.discriminator:
        return True  # Default card (no discriminator)
    if isinstance(card.metadata.discriminator, tuple):
        disc_category, disc_value = card.metadata.discriminator
    elif isinstance(card.metadata.discriminator, re.Pattern) and (
        model_hint and (match := card.metadata.discriminator.match(model_hint))
    ):
        disc_category, disc_value = "model", match.group(1)
    elif (
        isinstance(card.metadata.discriminator, re.Pattern)
        and client_preference
        and (match := card.metadata.discriminator.match(client_preference))
    ):
        disc_category, disc_value = "client", match.group(1)
    elif isinstance(card.metadata.discriminator, re.Pattern):
        # If it's a regex but no hint provided, we can't match
        return False
    if disc_category == "model" and model_hint:
        # Model discriminator: check if model name starts with discriminator value
        return model_hint.lower().startswith(cast(str, disc_value).lower())

    if disc_category == "client" and client_preference:
        # Client discriminator: exact match
        return client_preference.lower() == cast(str, disc_value).lower()

    return False


# ===========================================================================
# *                    Query Interface - Main Functions
# ===========================================================================


@cache
def get_service_cards(
    *,
    provider: ProviderLiteralString | set[ProviderLiteralString] | None = None,
    category: ProviderCategoryLiteralString | set[ProviderCategoryLiteralString] | None = None,
    client: SDKClientLiteralString | set[SDKClientLiteralString] | None = None,
) -> tuple[ServiceCard, ...]:
    """Query service cards by any combination of filters.

    This is the primary query function for finding service cards.
    All filters are optional and can be combined.

    Args:
        provider: Filter by provider name (e.g., "openai", "cohere").
        category: Filter by service category (e.g., "embedding", "agent").
        client: Filter by SDK client name (e.g., "openai", "anthropic").

    Returns:
        Tuple of matching service cards (may be empty).

    Examples:
        Get all OpenAI cards:
        >>> get_service_cards(provider="openai")

        Get all embedding providers:
        >>> get_service_cards(category="embedding")

        Get providers using OpenAI client:
        >>> get_service_cards(client="openai")

        Get specific provider-category combination:
        >>> get_service_cards(provider="azure", category="agent")
    """
    registry = _build_service_card_registry()
    prov_filter: set[ProviderLiteralString] = (
        provider if isinstance(provider, set) else ({provider} if provider is not None else set())
    )
    category_filter: set[ProviderCategoryLiteralString] = (
        category if isinstance(category, set) else ({category} if category is not None else set())
    )
    client_filter: set[SDKClientLiteralString] = (
        client if isinstance(client, set) else ({client} if client is not None else set())
    )
    if prov_filter or category_filter or client_filter:
        return tuple(
            sorted(
                (
                    c
                    for c in registry
                    if (not prov_filter or c.provider in prov_filter)
                    and (not category_filter or c.category in category_filter)
                    and (not client_filter or c.client in client_filter)
                ),
                key=lambda c: (c.provider, c.category, c.client),
            )
        )
    return registry


@cache
def get_service_card(
    provider: ProviderLiteralString,
    category: ProviderCategoryLiteralString,
    *,
    client_preference: str | None = None,
    model_hint: str | None = None,
) -> ServiceCard | None:
    """Get single service card for exact provider-category match with discriminator support.

    For multi-client providers (Azure, Bedrock, Heroku), this function uses
    discriminators to select the appropriate card:
    - model_hint: Selects based on model name (e.g., "claude-3" → Anthropic client)
    - client_preference: Selects based on explicit client preference

    If no discriminators match, returns the default card (one without discriminator).

    Args:
        provider: The provider name (e.g., "azure", "openai").
        category: The service category (e.g., "agent", "embedding").
        client_preference: Optional client preference for multi-client providers.
        model_hint: Optional model name hint for model-based discrimination.

    Returns:
        ServiceCard if found, None if provider-category combination doesn't exist.

    Examples:
        Simple case:
        >>> get_service_card("openai", "embedding")
        ServiceCard(provider='openai', category='embedding', ...)

        Multi-client with model hint:
        >>> get_service_card("azure", "agent", model_hint="claude-3-opus")
        ServiceCard(...client_cls=AsyncAnthropicFoundry...)

        Multi-client with client preference:
        >>> get_service_card("heroku", "embedding", client_preference="cohere")
        ServiceCard(...client_cls=AsyncClientV2...)
    """
    cards = get_service_cards(provider=provider, category=category)

    if not cards:
        return None

    if len(cards) == 1:
        return cards[0]

    # Multiple cards exist - use discriminators to select
    # First, try discriminators with hints
    if model_hint or client_preference:
        for card in cards:
            if (
                _match_discriminator(
                    card, model_hint=model_hint, client_preference=client_preference
                )
                and card.metadata
                and card.metadata.discriminator
            ):
                # This card has a discriminator that matched
                return card

    # Fall back to default card (no discriminator)
    for card in cards:
        if not card.metadata or not card.metadata.discriminator:
            return card

    # If no default exists, return first card
    return cards[0]


@cache
def get_provider_clients(
    provider: ProviderLiteralString,
) -> dict[ProviderCategoryLiteralString, tuple[SDKClientLiteralString, ...]]:
    """Get all SDK client options for a provider, grouped by service category.

    Useful for discovering what clients a provider supports for each service type.

    Args:
        provider: The provider name (e.g., "azure", "openai").

    Returns:
        Dictionary mapping service categories to tuples of SDK client names.
        Empty dict if provider not found.

    Examples:
        >>> get_provider_clients("azure")
        {
            'agent': ('openai', 'anthropic'),
            'embedding': ('openai', 'cohere')
        }

        >>> get_provider_clients("openai")
        {
            'agent': ('openai',),
            'embedding': ('openai',)
        }
    """
    cards = get_service_cards(provider=provider)

    result: dict[ProviderCategoryLiteralString, set[SDKClientLiteralString]] = defaultdict(set)
    for card in cards:
        result[card.category] |= {card.client}

    return {k: tuple(sorted(v)) for k, v in result.items() if v}


@cache
def get_provider_capabilities_map(
    provider_cls: type[Provider],
) -> MappingProxyType[Provider, tuple[ProviderCategoryLiteralString, ...]]:
    """Get the mapping of provider capabilities.

    The map is from `Provider` to their supported `ProviderCategory`s as strings.

    Args:
        provider: The `Provider` class to get capabilities for.

    Returns:
        A mapping of `Provider` to their supported `ProviderCategory`s as strings.
    """
    cards = get_service_cards()
    mapping = defaultdict(set)
    for card in cards:
        mapping[provider_cls.from_string(card.provider)].add(card.category)
    return MappingProxyType({
        prov: tuple(sorted(categories)) for prov, categories in mapping.items()
    })


@cache
def get_categories(provider: LiteralProvider) -> tuple[ProviderCategoryLiteralString, ...]:
    """Get the supported provider categories for a given provider, returned as strings.

    Args:
        provider_instance: The `Provider` instance to get categories for.

    Returns:
        A tuple of supported `ProviderCategory`s as strings.
    """
    return get_provider_capabilities_map(provider_cls=type(provider)).get(provider, ())


@cache
def get_providers_for_category(category: LiteralProviderCategory) -> set[LiteralProvider]:
    """Get all providers that support a given provider category.

    Args:
        category: The `ProviderCategory` to get providers for.

    Returns:
        A set of `Provider` members that support the given category.
    """
    mapping = get_provider_capabilities_map(type(category)._provider_cls())
    return {provider for provider, categories in mapping.items() if category.variable in categories}


@cache
def get_sdk_client_map(
    client_cls: type[SDKClient],
) -> MappingProxyType[
    tuple[ProviderLiteralString, ProviderCategoryLiteralString], SDKClient | tuple[SDKClient, ...]
]:
    """Get the mapping of SDK clients.

    The map is from `(Provider, ProviderCategory)` to their `SDKClient` class.

    Args:
        client_cls: The `SDKClient` class to get the mapping for.

    Returns:
        A mapping of `(Provider, ProviderCategory)` to their `SDKClient` class(es).
    """
    cards = get_service_cards()
    return MappingProxyType({
        (c.provider, c.category): client_cls.from_string(c.client) for c in cards
    })


@cache
def get_sdk_client(
    client_cls: type[SDKClient], provider: LiteralProvider, category: LiteralProviderCategory
) -> SDKClient | tuple[SDKClient, ...] | None:
    """Get the SDK client for a given provider and category.

    Args:
        client_cls: The `SDKClient` class to get the client for.
        provider: The `Provider` to get the client for as a string.
        category: The `ProviderCategory` to get the client for as a string.

    Returns:
        The `SDKClient` class or tuple of classes for the given provider and category, or None if not found.
    """
    return get_sdk_client_map(client_cls).get((provider, category))


@cache
def get_provider_category_sdk_clients_for_provider(
    client_cls: type[SDKClient], provider: Provider
) -> dict[ProviderCategory, tuple[SDKClient, ...] | SDKClient]:
    """Get all SDK clients for a given provider.

    Args:
        client_cls: The `SDKClient` class to get the clients for.
        provider: The `Provider` to get the clients for as a string.
    """
    provider_category_cls = client_cls._any_category()
    return {
        provider_category_cls.from_string(category): client
        for (p, category), client in get_sdk_client_map(client_cls).items()
        if p == provider.variable
    }


# ===========================================================================
# *                        Public Exports
# ===========================================================================

__all__ = (
    "ProviderCategoryLiteralString",
    "ProviderLiteralString",
    "SDKClientLiteralString",
    "ServiceCard",
    "ServiceMetadata",
    "get_categories",
    "get_local_only_provider_members",
    "get_local_only_providers",
    "get_openai_provider_members",
    "get_openai_providers",
    "get_provider_capabilities_map",
    "get_provider_category_sdk_clients_for_provider",
    "get_provider_clients",
    "get_provider_literals",
    "get_providers_for_category",
    "get_sdk_client",
    "get_sdk_client_map",
    "get_service_card",
    "get_service_cards",
    "get_sometimes_local_provider_members",
    "get_sometimes_local_providers",
    "service_card_factory",
)
