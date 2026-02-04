# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Mappings of provider types for various purposes (e.g. to clients, classes, etc.).

This module is an internal implementation detail. You shouldn't use it directly. It supplies the raw data used in the `Provider` and `SDKClient` and `ProviderKind` enum classes (`codeweaver.core.types.provider`). Use those classes instead.

To allow for lazy loading and prevent circular imports, we put the mappings in this separate module and wrapped in functions. To avoid circular dependencies and initialization order issues, we require callers to pass in themselves (`ProviderKind`, `Provider`, or `SDKClient`) either as a class or instance.
"""

from __future__ import annotations

from functools import cache
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Literal, NamedTuple, TypedDict, overload

from beartype.typing import Callable

from codeweaver.core.utils import LazyImport, has_package
from codeweaver.core.utils.lazy_importer import lazy_import


if TYPE_CHECKING:
    from codeweaver.core.types.provider import (
        LiteralProvider,  # Members of Provider
        LiteralProviderKind,  # Members of ProviderKind
        Provider,
        ProviderKind,
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


type ProviderKindLiteral = Literal[
    "agent", "data", "embedding", "reranking", "sparse_embedding", "vector_store"
]

type ProviderLiteral = Literal[
    "alibaba",
    "anthropic",
    "azure",
    "bedrock",
    "cerebras",
    "cohere",
    "deepseek",
    "duckduckgo",
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
    "nebius",
    "ollama",
    "openai",
    "openrouter",
    "ovhcloud",
    "perplexity",
    "qdrant",
    "sentence_transformers",
    "tavily",
    "together",
    "vercel",
    "voyage",
    "x_ai",
    # "outlines",
]

type LiteralSDKClient = Literal[
    "anthropic",
    "bedrock",
    "cohere",
    "duckduckgo",
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
]

type ProviderImportMapType = dict[ProviderLiteral, LazyImport[Any]]


class VectorStoreImportDict(TypedDict):
    """A typed dict for mapping vector store providers to their import paths."""

    qdrant: LazyImport[Any]
    memory: LazyImport[Any]


class KindImportDict(TypedDict, total=False):
    """A typed dict for mapping provider kinds to their import paths."""

    agent: LazyImport[Any]
    data: LazyImport[Any]
    embedding: LazyImport[Any]
    reranking: LazyImport[Any]
    sparse_embedding: LazyImport[Any]
    vector_store: VectorStoreImportDict


class KindProviderDict(TypedDict, total=False):
    """A typed dict for mapping provider kinds to providers."""

    agent: ProviderImportMapType
    data: ProviderImportMapType
    embedding: ProviderImportMapType
    reranking: ProviderImportMapType
    sparse_embedding: ProviderImportMapType
    vector_store: VectorStoreImportDict


class SDKClientMap(TypedDict):
    client: KindProviderDict
    cls: KindImportDict


# ===========================================================================
# *                       Provider Groups
# ===========================================================================
# section provides the canonical sets of provider groups used in the Provider class' methods.


@cache
def _all_provider_gen() -> set[ProviderLiteral]:
    """Generate the set of all provider literals.

    Returns:
        A set of all provider literals as strings.
    """
    # we only need to maintain the ProviderLiteral union this way.
    return set(ProviderLiteral.__args__)  # ty:ignore[unresolved-attribute]


@cache
def _never_use_other_api() -> set[ProviderLiteral]:
    """These are providers that (at least in CodeWeaver) never use any API other than their own SDK/client.

    This does not mean that others *don't* also use their API, just that they themselves never use anything else. It also does not mean any *models* associated with these providers aren't also available on other APIs. A `provider` is who you pay, not the client/API, or models.
    """
    return {
        "anthropic",
        "cohere",
        "duckduckgo",
        "fastembed",
        "gateway",
        "hf_inference",
        "mistral",
        "openai",
        "qdrant",
        "sentence_transformers",
        "tavily",
        "voyage",
    }


@cache
def _never_use_openai_api() -> set[ProviderLiteral]:
    """These are providers that (at least in CodeWeaver) never use the OpenAI API.

    This does not mean that others *don't* also use their API, just that they themselves never use it. It also does not mean any *models* associated with these providers aren't also available on the OpenAI API. A `provider` is who you pay, not the client/API, or models.

    ...unless you don't pay anyone, then it's the client (like sentence_transformers).
    """
    return ((_all_provider_gen() - {"openai"}) & _never_use_other_api()) | {"bedrock", "memory"}


def _sometimes_use_openai_api() -> set[ProviderLiteral]:
    """These are providers that (at least in CodeWeaver) sometimes use the OpenAI API.

    This means that they have their own SDK/client, but can also use the OpenAI API.

    It also does not mean any *models* associated with these providers aren't also available on the OpenAI API. A `provider` is who you pay, not the client/API, or models.
    """
    return _all_provider_gen() - _never_use_openai_api()


@cache
def _always_use_openai_api() -> set[ProviderLiteral]:
    """These are providers that (at least in CodeWeaver) do not always use the OpenAI API.

    This means that they have their own SDK/client, and may also use other APIs.

    It also does not mean any *models* associated with these providers aren't also available on the OpenAI API. A `provider` is who you pay, not the client/API, or models.
    """
    return _sometimes_use_openai_api() - {"azure", "heroku", "google", "groq"}


_LOCAL_ONLY_PROVIDERS: set[ProviderLiteral] = {
    "fastembed",  # not strictly true but for our purposes it is
    "sentence_transformers",
    "memory",
}

_SOMETIMES_LOCAL_PROVIDERS: set[ProviderLiteral] = {"ollama", "qdrant"}


def _get_openai_providers() -> set[ProviderLiteral]:
    """Get the set of OpenAI-related providers.

    Returns:
        A set of provider strings that use the OpenAI API.
    """
    return _sometimes_use_openai_api()


def get_openai_provider_members(provider_cls: type[Provider]) -> set[LiteralProvider]:
    """Get the set of OpenAI-related provider members.

    Args:
        provider_cls: The `Provider` class to get members from.

    Returns:
        A set of `Provider` members that use the OpenAI API.
    """
    return {provider_cls.from_string(p) for p in _get_openai_providers()}


def get_local_only_provider_members(provider_cls: type[Provider]) -> set[LiteralProvider]:
    """Get the set of local-only provider members.

    Args:
        provider_cls: The `Provider` class to get members from.

    Returns:
        A set of `Provider` members that are local-only.
    """
    return {provider_cls.from_string(p) for p in _LOCAL_ONLY_PROVIDERS}


# ===========================================================================
# *                       Provider Maps
# ===========================================================================


@overload
def _get_provider_capabilities_map(
    provider_cls: type[Provider], provider_instance: Provider
) -> tuple[ProviderKindLiteral, ...]: ...
@overload
def _get_provider_capabilities_map(
    provider_cls: type[Provider],
) -> MappingProxyType[Provider, tuple[ProviderKindLiteral, ...]]: ...
def _get_provider_capabilities_map(
    provider_cls: type[Provider], provider_instance: LiteralProvider | None = None
) -> tuple[ProviderKind, ...] | MappingProxyType[Provider, tuple[ProviderKindLiteral, ...]]:
    """Get the mapping of provider capabilities.

    Args:
        provider_instance: The `Provider` class or instance to get capabilities for.

    Returns:
        A mapping of `Provider` to their supported `ProviderKind`s.
    """
    _provider_capabilities: MappingProxyType[Provider, tuple[ProviderKindLiteral, ...]] = (
        MappingProxyType({
            provider_cls.ALIBABA: ("agent",),
            provider_cls.ANTHROPIC: ("agent",),
            provider_cls.AZURE: ("agent", "embedding"),
            provider_cls.BEDROCK: ("embedding", "reranking", "agent"),
            provider_cls.CEREBRAS: ("agent",),
            provider_cls.COHERE: ("embedding", "reranking", "agent"),
            provider_cls.DEEPSEEK: ("agent",),
            provider_cls.DUCKDUCKGO: ("data",),
            provider_cls.FASTEMBED: ("embedding", "reranking", "sparse_embedding"),
            provider_cls.FIREWORKS: ("agent", "embedding"),
            provider_cls.GITHUB: ("agent", "embedding"),
            provider_cls.GOOGLE: ("agent", "embedding"),
            provider_cls.GROQ: ("agent", "embedding"),
            provider_cls.HEROKU: ("agent", "embedding"),
            provider_cls.HUGGINGFACE_INFERENCE: ("agent", "embedding"),
            provider_cls.LITELLM: ("agent",),  # supports embedding but not implemented yet
            provider_cls.MISTRAL: ("agent", "embedding"),
            provider_cls.MEMORY: ("vector_store",),
            provider_cls.MOONSHOT: ("agent",),
            provider_cls.MORPH: ("embedding",),  # supports agent but not implemented
            provider_cls.NEBIUS: ("agent",),
            provider_cls.OLLAMA: ("agent", "embedding"),
            provider_cls.OPENAI: ("agent", "embedding"),
            # provider_cls.OUTLINES: ("agent",),  # not implemented yet
            provider_cls.OPENROUTER: ("agent",),  # supports embedding but not implemented yet
            provider_cls.OVHCLOUD: ("agent",),
            provider_cls.PERPLEXITY: ("agent",),
            provider_cls.PYDANTIC_GATEWAY: ("agent",),
            provider_cls.QDRANT: ("vector_store",),
            provider_cls.SENTENCE_TRANSFORMERS: ("embedding", "reranking", "sparse_embedding"),
            provider_cls.TAVILY: ("data",),
            provider_cls.TOGETHER: ("agent", "embedding"),
            provider_cls.VERCEL: ("agent", "embedding"),
            provider_cls.VOYAGE: ("embedding", "reranking"),
            provider_cls.X_AI: ("agent",),
        })
    )

    if provider_instance is None:
        return _provider_capabilities
    return (
        _provider_capabilities[provider_instance] if provider_instance != Provider.NOT_SET else ()
    )


@cache
def get_provider_capabilities_map(
    provider: type[Provider],
) -> MappingProxyType[Provider, tuple[ProviderKindLiteral, ...]]:
    """Get the mapping of provider capabilities.

    The map is from `Provider` to their supported `ProviderKind`s as strings.

    Args:
        provider: The `Provider` class to get capabilities for.

    Returns:
        A mapping of `Provider` to their supported `ProviderKind`s as strings.
    """
    return _get_provider_capabilities_map(provider)


@cache
def get_provider_kinds(provider: LiteralProvider) -> tuple[ProviderKindLiteral, ...]:
    """Get the supported provider kinds for a given provider, returned as strings.

    Args:
        provider_instance: The `Provider` instance to get kinds for.

    Returns:
        A tuple of supported `ProviderKind`s as strings.
    """
    return _get_provider_capabilities_map(provider_cls=type(provider), provider_instance=provider)


@cache
def get_providers_for_kind(kind: LiteralProviderKind) -> set[ProviderLiteral]:
    """Get all providers that support a given provider kind.

    Args:
        kind: The `ProviderKind` to get providers for.

    Returns:
        A set of `Provider` members that support the given kind.
    """
    mapping = _get_provider_capabilities_map(type(kind)._provider_cls())
    return {provider for provider, kinds in mapping.items() if kind.variable in kinds}


# ===========================================================================
# *                    Provider -> SDKClient mapping
# ===========================================================================


# Kind given, provider is None, return all providers-client mappings for that kind
@overload
def _get_sdk_client_map[ProviderMember: None, Kind: ProviderKindLiteral](
    client_cls: type[SDKClient], *, provider: None = None, kind: Kind
) -> dict[Provider, SDKClient | tuple[SDKClient, ...]]: ...


# Provider and kind given, return specific client or tuple of clients, or None
# this is the only overload that can return None if there are no entries for the given provider-kind pair
@overload
def _get_sdk_client_map[ProviderMember: ProviderLiteral, Kind: ProviderKindLiteral](
    client_cls: type[SDKClient], provider: ProviderMember, kind: Kind
) -> SDKClient | tuple[SDKClient, ...] | None: ...


# provider given, kind is None, return all clients and kinds for that provider
@overload
def _get_sdk_client_map[ProviderMember: ProviderLiteral, Kind: None](
    client_cls: type[SDKClient], provider: ProviderMember, kind: None = None
) -> dict[ProviderKind, tuple[SDKClient, ...] | SDKClient]: ...


# provider and kind are None, return full map
@overload
def _get_sdk_client_map[ProviderMember: None, Kind: None](
    client_cls: type[SDKClient], provider: None = None, kind: None = None
) -> SDKClient | tuple[SDKClient, ...]: ...


def _get_sdk_client_map[ProviderMember: ProviderLiteral, Kind: ProviderKindLiteral](
    client_cls: type[SDKClient], provider: ProviderMember | None = None, kind: Kind | None = None
) -> (
    MappingProxyType[tuple[ProviderLiteral, ProviderKindLiteral], SDKClient | tuple[SDKClient, ...]]
    | SDKClient
    | tuple[SDKClient, ...]
    | dict[ProviderKind, tuple[SDKClient, ...] | SDKClient]
    | dict[Provider, SDKClient | tuple[SDKClient, ...]]
    | None
):
    """Get the mapping of SDK clients.

    Args:
        provider: The `Provider` to get the clients for.
        kind: The `ProviderKind` to get the clients for.

    Returns:
        A mapping of `(Provider, ProviderKind)` to their `SDKClient` class.
    """
    sdkclient_cls = client_cls
    provider_cls = type(sdkclient_cls._any_provider())
    providerkind_cls = provider_cls._kind_cls()

    _sdk_client_map: MappingProxyType[tuple[ProviderMember, Kind], type[SDKClient]] = (
        MappingProxyType(
            {
                (provider, providerkind_cls.EMBEDDING): sdkclient_cls.OPENAI
                for provider in (
                    p
                    for p in provider_cls
                    if p.uses_openai_api
                    and p not in (provider_cls.AZURE, provider_cls.HEROKU, provider_cls.GROQ)
                    and p.is_embedding_provider()
                )
            }
            | {
                (provider_cls.AZURE, providerkind_cls.EMBEDDING): (
                    sdkclient_cls.OPENAI,
                    sdkclient_cls.COHERE,
                ),
                (provider_cls.HEROKU, providerkind_cls.EMBEDDING): (
                    sdkclient_cls.OPENAI,
                    sdkclient_cls.COHERE,
                ),
            }
            | {
                (provider, providerkind_cls.EMBEDDING): sdkclient_cls.from_string(provider.variable)
                for provider in (
                    provider_cls.MISTRAL,
                    provider_cls.HUGGINGFACE_INFERENCE,
                    provider_cls.GOOGLE,
                )
            }
            | {
                (provider, kind): sdkclient_cls.from_string(provider.variable)
                for provider, kind in (
                    (prov, knd)
                    for prov in (provider_cls.BEDROCK, provider_cls.COHERE, provider_cls.VOYAGE)
                    for knd in (providerkind_cls.EMBEDDING, providerkind_cls.RERANKING)
                )
            }
            | {
                (provider, kind): sdkclient_cls.from_string(provider.variable)
                for provider in (provider_cls.FASTEMBED, provider_cls.SENTENCE_TRANSFORMERS)
                for kind in (
                    providerkind_cls.EMBEDDING,
                    providerkind_cls.SPARSE_EMBEDDING,
                    providerkind_cls.RERANKING,
                )
            }
            | {(provider_cls.QDRANT, providerkind_cls.VECTOR_STORE): sdkclient_cls.QDRANT}
            | {(provider_cls.MEMORY, providerkind_cls.VECTOR_STORE): sdkclient_cls.QDRANT}
            | {
                (provider, providerkind_cls.AGENT): sdkclient_cls.OPENAI
                for provider in provider_cls
                if provider.uses_openai_api
                and provider != provider_cls.GROQ
                and provider.is_agent_provider()
            }
            | {(provider_cls.ANTHROPIC, providerkind_cls.AGENT): sdkclient_cls.ANTHROPIC}
            | {
                (provider_cls.AZURE, providerkind_cls.AGENT): (
                    sdkclient_cls.OPENAI,
                    sdkclient_cls.ANTHROPIC,
                )
            }
            | {
                (provider_cls.BEDROCK, providerkind_cls.AGENT): (
                    sdkclient_cls.BEDROCK,
                    sdkclient_cls.ANTHROPIC,
                )
            }
            | {(provider_cls.COHERE, providerkind_cls.AGENT): sdkclient_cls.COHERE}
            | {
                (provider_cls.GOOGLE, providerkind_cls.AGENT): (
                    sdkclient_cls.GOOGLE,
                    sdkclient_cls.ANTHROPIC,
                )
            }
            | {(provider_cls.GROQ, providerkind_cls.AGENT): sdkclient_cls.GROQ}
            | {
                (
                    provider_cls.HUGGINGFACE_INFERENCE,
                    providerkind_cls.AGENT,
                ): sdkclient_cls.HUGGINGFACE_INFERENCE
            }
            | {(provider_cls.MISTRAL, providerkind_cls.AGENT): sdkclient_cls.MISTRAL}
            | {
                (provider, providerkind_cls.AGENT): sdkclient_cls.OPENAI
                for provider in {
                    p
                    for p in provider_cls
                    if p.is_agent_provider()
                    and p.uses_openai_api
                    and p not in (provider_cls.AZURE, provider_cls.GROQ)
                }
            }
            | {(provider_cls.DUCKDUCKGO, providerkind_cls.DATA): sdkclient_cls.DUCKDUCKGO}
            | {(provider_cls.TAVILY, providerkind_cls.DATA): sdkclient_cls.TAVILY}
        )
    )
    if provider and kind:
        return _sdk_client_map.get((
            provider_cls.from_string(provider),
            providerkind_cls.from_string(kind),
        ))
    if provider and not kind:
        return {
            knd: client
            for (prov, knd), client in _sdk_client_map.items()
            if prov == provider_cls.from_string(provider)
        }
    if kind and not provider:
        return {
            prov: client
            for (prov, knd), client in _sdk_client_map.items()
            if knd == providerkind_cls.from_string(kind)
        }
    return _sdk_client_map


@cache
def get_sdk_client_map(
    client_cls: type[SDKClient],
) -> MappingProxyType[
    tuple[ProviderLiteral, ProviderKindLiteral], SDKClient | tuple[SDKClient, ...]
]:
    """Get the mapping of SDK clients.

    The map is from `(Provider, ProviderKind)` to their `SDKClient` class.

    Args:
        client_cls: The `SDKClient` class to get the mapping for.

    Returns:
        A mapping of `(Provider, ProviderKind)` to their `SDKClient` class(es).
    """
    return _get_sdk_client_map(client_cls)  # ty:ignore[invalid-return-type]


@cache
def get_sdk_client(
    client_cls: type[SDKClient], provider: LiteralProvider, kind: LiteralProviderKind
) -> SDKClient | tuple[SDKClient, ...] | None:
    """Get the SDK client for a given provider and kind.

    Args:
        client_cls: The `SDKClient` class to get the client for.
        provider: The `Provider` to get the client for as a string.
        kind: The `ProviderKind` to get the client for as a string.

    Returns:
        The `SDKClient` class or tuple of classes for the given provider and kind, or None if not found.
    """
    return _get_sdk_client_map(client_cls, provider=provider, kind=kind)  # ty:ignore[no-matching-overload]


@cache
def get_provider_sdk_clients_for_kind(
    client_cls: type[SDKClient], kind: LiteralProviderKind
) -> dict[Provider, SDKClient | tuple[SDKClient, ...]]:
    """Get all SDK clients for a given provider kind.

    Args:
        client_cls: The `SDKClient` class to get the clients for.
        kind: The `ProviderKind` to get the clients for as a string.
    """
    return _get_sdk_client_map(client_cls, kind=kind)


@cache
def get_provider_kind_sdk_clients_for_provider(
    client_cls: type[SDKClient], provider: Provider
) -> dict[ProviderKind, tuple[SDKClient, ...] | SDKClient]:
    """Get all SDK clients for a given provider.

    Args:
        client_cls: The `SDKClient` class to get the clients for.
        provider: The `Provider` to get the clients for as a string.
    """
    return _get_sdk_client_map(client_cls, provider)


# ===========================================================================
# *               SDKClient -> Actual Client Import
# ===========================================================================
class ServiceCard(NamedTuple):
    """A service card representing a provider-kind-client mapping."""

    provider: ProviderLiteral
    """The provider (the service you pay for)."""
    kind: ProviderKindLiteral
    """The kind of service (embedding, agent, etc.)."""
    provider_cls: LazyImport[Any]
    """The provider class (e.g. CohereProvider)."""
    client_cls: LazyImport[Any]
    """The client class (e.g. AsyncCohereV2)."""
    has_multiple: bool
    """Whether this service has multiple possible provider_cls or client_cls options."""
    requires_special_handling: bool
    """Whether this service requires special handling when instantiating the provider or client."""
    discriminator_kind: Literal["model", "client"] | None
    """For providers that can use more than one provider_cls or client_cls, the discriminator indicates which to use based on context. Only used if `has_multiple` is True."""
    discriminator_value: str | None
    """The value to match against the discriminator_kind to select this service card. Only used if `has_multiple` is True."""
    handler_kind: Literal["client", "provider"] | None
    """If requires_special_handling is True, indicates whether the special handling is for the client or provider."""
    handler_function: Callable[..., Any] | None
    """If requires_special_handling is True, the function to call to handle special instantiation."""


@overload
def service_card_factory(
    provider: ProviderLiteral,
    kind: ProviderKindLiteral,
    provider_cls: LazyImport[Any],
    client_cls: LazyImport[Any],
    *,
    has_multiple: Literal[True],
    requires_special_handling: Literal[True],
    discriminator_kind: Literal["model", "client"],
    discriminator_value: str,
    handler_kind: Literal["client", "provider"],
    handler_function: Callable[..., Any],
) -> ServiceCard: ...
@overload
def service_card_factory(
    provider: ProviderLiteral,
    kind: ProviderKindLiteral,
    provider_cls: LazyImport[Any],
    client_cls: LazyImport[Any],
    *,
    has_multiple: Literal[True],
    requires_special_handling: Literal[True],
    handler_kind: Literal["client", "provider"],
    handler_function: Callable[..., Any],
) -> ServiceCard: ...
@overload
def service_card_factory(
    provider: ProviderLiteral,
    kind: ProviderKindLiteral,
    provider_cls: LazyImport[Any],
    client_cls: LazyImport[Any],
    *,
    has_multiple: Literal[True],
    discriminator_kind: Literal["model", "client"],
    discriminator_value: str,
) -> ServiceCard: ...
@overload
def service_card_factory(
    provider: ProviderLiteral,
    kind: ProviderKindLiteral,
    provider_cls: LazyImport[Any],
    client_cls: LazyImport[Any],
    *,
    has_multiple: bool = False,
    discriminator_kind: Literal["model", "client"] | None = None,
    discriminator_value: str | None = None,
    handler_kind: Literal["client", "provider"] | None = None,
    handler_function: Callable[..., Any] | None = None,
) -> ServiceCard: ...
def service_card_factory(
    provider: ProviderLiteral,
    kind: ProviderKindLiteral,
    provider_cls: LazyImport[Any],
    client_cls: LazyImport[Any],
    *,
    has_multiple: bool = False,
    requires_special_handling: bool = False,
    discriminator_kind: Literal["model", "client"] | None = None,
    discriminator_value: str | None = None,
    handler_kind: Literal["client", "provider"] | None = None,
    handler_function: Callable[..., Any] | None = None,
) -> ServiceCard:
    """Factory function to create a ServiceCard with proper type checking.

    Args:
        provider: The provider (the service you pay for).
        kind: The kind of service (embedding, agent, etc.).
        provider_cls: The provider class (e.g. CohereProvider).
        client_cls: The client class (e.g. AsyncCohereV2).

        has_multiple: Whether this service has multiple possible provider_cls or client_cls options.
        requires_special_handling: Whether this service requires special handling when instantiating the provider or client.
        discriminator_kind: For providers that can use more than one provider_cls or client_cls, the discriminator indicates which to use based on context. Only used if `has_multiple` is True.
        discriminator_value: The value to match against the discriminator_kind to select this service card. Only used if `has_multiple` is True.
        handler_kind: If requires_special_handling is True, indicates whether the special handling is for the client or provider.
        handler_function: If requires_special_handling is True, the function to call to handle special instantiation.

    Returns:
        A ServiceCard instance.
    """
    return ServiceCard(
        provider=provider,
        kind=kind,
        provider_cls=provider_cls,
        client_cls=client_cls,
        has_multiple=has_multiple,
        requires_special_handling=requires_special_handling,
        discriminator_kind=discriminator_kind,
        discriminator_value=discriminator_value,
        handler_kind=handler_kind,
        handler_function=handler_function,
    )


def get_sdk_client_map(sdk_client: LiteralSDKClient) -> LazyImport[Any]:
    """Get the actual SDK client class for a given SDK client literal.

    Args:
        sdk_client: The `SDKClient` literal to get the class for.

    Returns:
        The actual SDK client class.
    """
    _client_mapping: MappingProxyType[LiteralSDKClient, SDKClientMap] = MappingProxyType({
        "anthropic": SDKClientMap(
            client=KindProviderDict(
                agent={
                    "anthropic": lazy_import("anthropic", "AsyncAnthropic"),
                    "azure": lazy_import("anthropic", "AsyncAnthropicFoundry"),
                    "bedrock": lazy_import("anthropic", "AsyncAnthropicBedrock"),
                    "google": lazy_import("anthropic", "AsyncAnthropicVertex"),
                }
            ),
            cls=KindImportDict(
                agent=lazy_import("pydantic_ai.providers.anthropic", "AnthropicProvider")
            ),
        ),
        "bedrock": SDKClientMap(
            client=KindProviderDict(
                agent={"bedrock": lazy_import("boto3", "client")},
                embedding={"bedrock": lazy_import("boto3", "client")},
                reranking={"bedrock": lazy_import("boto3", "client")},
            ),
            cls=KindImportDict(
                agent=lazy_import("pydantic_ai.providers.bedrock", "BedrockProvider"),
                embedding=lazy_import(
                    "codeweaver.providers.embedding.providers", "BedrockEmbeddingProvider"
                ),
                reranking=lazy_import(
                    "codeweaver.providers.reranking.providers", "BedrockRerankingProvider"
                ),
            ),
        ),
        "cohere": SDKClientMap(
            client=KindProviderDict(
                agent={"cohere": lazy_import("cohere", "AsyncClientV2")},
                embedding={"cohere": lazy_import("cohere", "AsyncClientV2")},
                reranking={"cohere": lazy_import("cohere", "AsyncClientV2")},
            ),
            cls=KindImportDict(
                agent=lazy_import("pydantic_ai.providers.cohere", "CohereProvider"),
                embedding=lazy_import(
                    "codeweaver.providers.embedding.providers", "CohereEmbeddingProvider"
                ),
                reranking=lazy_import(
                    "codeweaver.providers.reranking.providers", "CohereRerankingProvider"
                ),
            ),
        ),
        "duckduckgo": SDKClientMap(
            client=KindProviderDict(data={"duckduckgo": lazy_import("ddgs.ddgs", "DDGS")}),
            cls=KindImportDict(
                data=lazy_import("pydantic_ai.common_tools.duckduckgo", "DuckDuckGoSearchTool")
            ),
        ),
        "fastembed": SDKClientMap(
            client=KindProviderDict(
                embedding={
                    "fastembed": lazy_import(
                        "codeweaver.providers.embedding.fastembed_extensions", "get_text_embedder"
                    )
                },
                sparse_embedding={
                    "fastembed": lazy_import(
                        "codeweaver.providers.embedding.fastembed_extensions", "get_sparse_embedder"
                    )
                },
                reranking={
                    "fastembed": lazy_import("fastembed.rerank.cross_encoder", "TextCrossEncoder")
                },
            ),
            cls=KindImportDict(
                embedding=lazy_import(
                    "codeweaver.providers.embedding.providers.fastembed",
                    "FastEmbedEmbeddingProvider",
                ),
                sparse_embedding=lazy_import(
                    "codeweaver.providers.embedding.providers.fastembed",
                    "FastEmbedSparseEmbeddingProvider",
                ),
                reranking=lazy_import(
                    "codeweaver.providers.reranking.providers.fastembed",
                    "FastEmbedRerankingProvider",
                ),
            ),
        ),
        "gateway": SDKClientMap(
            client=KindProviderDict(
                agent={"gateway": lazy_import("pydantic_ai.providers.gateway", "gateway_provider")}
            ),
            cls=KindImportDict(
                agent=lazy_import("pydantic_ai.providers.gateway", "gateway_provider")
            ),
        ),
        "google": SDKClientMap(
            client=KindProviderDict(
                agent={"google": lazy_import("google.genai", "Client")},
                embedding={"google": lazy_import("google.genai", "Client")},
            ),
            cls=KindImportDict(
                agent=lazy_import("pydantic_ai.providers.google", "GoogleProvider"),
                embedding=lazy_import(
                    "codeweaver.providers.embedding.providers.google", "GoogleEmbeddingProvider"
                ),
            ),
        ),
        "groq": SDKClientMap(
            client=KindProviderDict(
                agent={"groq": lazy_import("groq", "AsyncGroq")},
                embedding={"groq": lazy_import("openai", "AsyncOpenAI")},
            ),
            cls=KindImportDict(
                agent=lazy_import("pydantic_ai.providers.groq", "GroqProvider"),
                embedding=lazy_import(
                    "codeweaver.providers.embedding.providers.openai_factory.OpenAIEmbeddingBase",
                    "get_provider_class",
                ),
            ),
        ),
        "hf_inference": SDKClientMap(
            client=KindProviderDict(
                agent={"hf_inference": lazy_import("huggingface_hub", "AsyncInferenceClient")},
                embedding={"hf_inference": lazy_import("huggingface_hub", "AsyncInferenceClient")},
            ),
            cls=KindImportDict(
                agent=lazy_import("pydantic_ai.providers.huggingface", "HuggingFaceProvider"),
                embedding=lazy_import(
                    "codeweaver.providers.embedding.providers.hf_inference",
                    "HFInferenceEmbeddingProvider",
                ),
            ),
        ),
        "mistral": SDKClientMap(
            client=KindProviderDict(
                agent={"mistral": lazy_import("mistralai", "Mistral")},
                embedding={"mistral": lazy_import("mistralai", "Mistral")},
            ),
            cls=KindImportDict(
                agent=lazy_import("pydantic_ai.providers.mistral", "MistralProvider"),
                embedding=lazy_import(
                    "codeweaver.providers.embedding.providers.mistral", "MistralEmbeddingProvider"
                ),
            ),
        ),
        "openai": SDKClientMap(
            client=KindProviderDict(
                agent={"openai": lazy_import("openai", "AsyncOpenAI")},
                embedding={"openai": lazy_import("openai", "AsyncOpenAI")},
            ),
            cls=KindImportDict(
                agent=lazy_import("pydantic_ai.providers.openai", "OpenAIProvider"),
                embedding=lazy_import(
                    "codeweaver.providers.embedding.providers.openai_factory.OpenAIEmbeddingBase",
                    "get_provider_class",
                ),
            ),
        ),
        "qdrant": SDKClientMap(
            client=KindProviderDict(
                vector_store=VectorStoreImportDict(
                    qdrant=lazy_import("qdrant_client", "AsyncQdrantClient"),
                    memory=lazy_import("qdrant_client", "AsyncQdrantClient"),
                )
            ),
            cls=KindImportDict(
                vector_store=VectorStoreImportDict(
                    qdrant=lazy_import(
                        "codeweaver.providers.vector_store.providers.qdrant",
                        "QdrantVectorStoreProvider",
                    ),
                    memory=lazy_import(
                        "codeweaver.providers.vector_store.providers.inmemory",
                        "MemoryVectorStoreProvider",
                    ),
                )
            ),
        ),
        "tavily": SDKClientMap(
            client=KindProviderDict(data={"tavily": lazy_import("tavily", "AsyncTavilyClient")}),
            cls=KindImportDict(
                data=lazy_import("pydantic_ai.common_tools.tavily", "TavilySearchTool")
            ),
        ),
        "sentence_transformers": SDKClientMap(
            client=KindProviderDict(
                embedding={
                    "sentence_transformers": lazy_import(
                        "sentence_transformers", "SentenceTransformer"
                    )
                },
                sparse_embedding={
                    "sentence_transformers": lazy_import("sentence_transformers", "SparseEncoder")
                },
                reranking={
                    "sentence_transformers": lazy_import("sentence_transformers", "CrossEncoder")
                },
            ),
            cls=KindImportDict(
                embedding=lazy_import(
                    "codeweaver.providers.embedding.providers.sentence_transformers",
                    "SentenceTransformersEmbeddingProvider",
                ),
                sparse_embedding=lazy_import(
                    "codeweaver.providers.embedding.providers.sentence_transformers",
                    "SentenceTransformersSparseEmbeddingProvider",
                ),
                reranking=lazy_import(
                    "codeweaver.providers.reranking.providers.sentence_transformers",
                    "SentenceTransformersRerankingProvider",
                ),
            ),
        ),
        "voyage": SDKClientMap(
            client=KindProviderDict(
                embedding={"voyage": lazy_import("voyageai", "VoyageAI")},
                reranking={"voyage": lazy_import("voyageai", "VoyageAI")},
            ),
            cls=KindImportDict(
                embedding=lazy_import(
                    "codeweaver.providers.embedding.providers.voyage", "VoyageEmbeddingProvider"
                ),
                reranking=lazy_import(
                    "codeweaver.providers.reranking.providers.voyage", "VoyageRerankingProvider"
                ),
            ),
        ),
    })

    return _client_mapping[sdk_client]


__all__ = (
    "ProviderKindLiteral",
    "ProviderLiteral",
    "get_local_only_provider_members",
    "get_openai_provider_members",
    "get_provider_capabilities_map",
    "get_provider_kind_sdk_clients_for_provider",
    "get_provider_kinds",
    "get_provider_sdk_clients_for_kind",
    "get_sdk_client",
    "get_sdk_client_map",
)
