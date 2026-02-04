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
from typing import TYPE_CHECKING, cast, overload


if TYPE_CHECKING:
    from codeweaver.core.types.provider import (
        LiteralProvider,  # Members of Provider
        LiteralProviderKind,  # Members of ProviderKind
        Provider,
        ProviderKind,
        ProviderKindLiteral,  # ProviderKind as string
        ProviderLiteral,  # Provider as string
        SDKClient,
    )


def _get_openai_providers() -> set[ProviderLiteral]:
    """Get the set of OpenAI-related providers.

    Returns:
        A set of provider strings that use the OpenAI API.
    """
    return cast(
        set[ProviderLiteral],
        {
            "alibaba",
            "azure",
            "cerebras",
            "deepseek",
            "fireworks",
            "github",
            "groq",
            "heroku",
            "litellm",
            "moonshot",
            "morph",
            "nebius",
            "ollama",
            "openai",
            "openrouter",
            "ovhcloud",
            "perplexity",
            "sambanova",
            "together",
            "vercel",
            "x_ai",
        },
    )


def _get_openai_provider_members(provider_cls: type[Provider]) -> set[LiteralProvider]:
    """Get the set of OpenAI-related provider members.

    Args:
        provider_cls: The `Provider` class to get members from.

    Returns:
        A set of `Provider` members that use the OpenAI API.
    """
    return cast(
        set[LiteralProvider], {provider_cls.from_string(p) for p in _get_openai_providers()}
    )


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
    Provider = provider_cls  # noqa: N806
    _provider_capabilities: MappingProxyType[Provider, tuple[ProviderKindLiteral, ...]] = (
        MappingProxyType({
            Provider.ALIBABA: ("agent",),
            Provider.ANTHROPIC: ("agent",),
            Provider.AZURE: ("agent", "embedding"),
            Provider.BEDROCK: ("embedding", "reranking", "agent"),
            Provider.CEREBRAS: ("agent",),
            Provider.COHERE: ("embedding", "reranking", "agent"),
            Provider.DEEPSEEK: ("agent",),
            Provider.DUCKDUCKGO: ("data",),
            Provider.FASTEMBED: ("embedding", "reranking", "sparse_embedding"),
            Provider.FIREWORKS: ("agent", "embedding"),
            Provider.GITHUB: ("agent", "embedding"),
            Provider.GOOGLE: ("agent", "embedding"),
            Provider.GROQ: ("agent", "embedding"),
            Provider.HEROKU: ("agent", "embedding"),
            Provider.HUGGINGFACE_INFERENCE: ("agent", "embedding"),
            Provider.LITELLM: ("agent",),  # supports embedding but not implemented yet
            Provider.MISTRAL: ("agent", "embedding"),
            Provider.MEMORY: ("vector_store",),
            Provider.MOONSHOT: ("agent",),
            Provider.MORPH: ("embedding",),  # supports agent but not implemented
            Provider.NEBIUS: ("agent",),
            Provider.OLLAMA: ("agent", "embedding"),
            Provider.OPENAI: ("agent", "embedding"),
            # Provider.OUTLINES: ("agent",),  # not implemented yet
            Provider.OPENROUTER: ("agent",),  # supports embedding but not implemented yet
            Provider.OVHCLOUD: ("agent",),
            Provider.PERPLEXITY: ("agent",),
            Provider.PYDANTIC_GATEWAY: ("agent",),
            Provider.QDRANT: ("vector_store",),
            Provider.SENTENCE_TRANSFORMERS: ("embedding", "reranking", "sparse_embedding"),
            Provider.TAVILY: ("data",),
            Provider.TOGETHER: ("agent", "embedding"),
            Provider.VERCEL: ("agent", "embedding"),
            Provider.VOYAGE: ("embedding", "reranking"),
            Provider.X_AI: ("agent",),
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
def get_providers_for_kind(kind: ProviderKindLiteral) -> set[LiteralProvider]:
    """Get all providers that support a given provider kind.

    Args:
        kind: The `ProviderKind` to get providers for.

    Returns:
        A set of `Provider` members that support the given kind.
    """
    mapping = _get_provider_capabilities_map(type(kind)._provider_cls())
    return {provider for provider, kinds in mapping.items() if kind.variable in kinds}


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
    SDKClient = client_cls  # noqa: N806
    Provider = type(SDKClient._any_provider())  # noqa: N806
    ProviderKind = Provider._kind_cls()  # noqa: N806

    _sdk_client_map: MappingProxyType[tuple[ProviderMember, Kind], type[SDKClient]] = (
        MappingProxyType(
            {
                (provider, ProviderKind.EMBEDDING): SDKClient.OPENAI
                for provider in (
                    p
                    for p in Provider
                    if p.uses_openai_api
                    and p not in (Provider.AZURE, Provider.HEROKU, Provider.GROQ)
                    and p.is_embedding_provider()
                )
            }
            | {
                (Provider.AZURE, ProviderKind.EMBEDDING): (SDKClient.OPENAI, SDKClient.COHERE),
                (Provider.HEROKU, ProviderKind.EMBEDDING): (SDKClient.OPENAI, SDKClient.COHERE),
            }
            | {
                (provider, ProviderKind.EMBEDDING): SDKClient.from_string(provider.variable)
                for provider in (Provider.MISTRAL, Provider.HUGGINGFACE_INFERENCE, Provider.GOOGLE)
            }
            | {
                (provider, kind): SDKClient.from_string(provider.variable)
                for provider, kind in (
                    (prov, knd)
                    for prov in (Provider.BEDROCK, Provider.COHERE, Provider.VOYAGE)
                    for knd in (ProviderKind.EMBEDDING, ProviderKind.RERANKING)
                )
            }
            | {
                (provider, kind): SDKClient.from_string(provider.variable)
                for provider in (Provider.FASTEMBED, Provider.SENTENCE_TRANSFORMERS)
                for kind in (
                    ProviderKind.EMBEDDING,
                    ProviderKind.SPARSE_EMBEDDING,
                    ProviderKind.RERANKING,
                )
            }
            | {(Provider.QDRANT, ProviderKind.VECTOR_STORE): SDKClient.QDRANT}
            | {(Provider.MEMORY, ProviderKind.VECTOR_STORE): SDKClient.QDRANT}
            | {
                (provider, ProviderKind.AGENT): SDKClient.OPENAI
                for provider in Provider
                if provider.uses_openai_api
                and provider != Provider.GROQ
                and provider.is_agent_provider()
            }
            | {(Provider.ANTHROPIC, ProviderKind.AGENT): SDKClient.ANTHROPIC}
            | {(Provider.AZURE, ProviderKind.AGENT): (SDKClient.OPENAI, SDKClient.ANTHROPIC)}
            | {(Provider.BEDROCK, ProviderKind.AGENT): (SDKClient.BEDROCK, SDKClient.ANTHROPIC)}
            | {(Provider.COHERE, ProviderKind.AGENT): SDKClient.COHERE}
            | {(Provider.GOOGLE, ProviderKind.AGENT): (SDKClient.GOOGLE, SDKClient.ANTHROPIC)}
            | {(Provider.GROQ, ProviderKind.AGENT): SDKClient.GROQ}
            | {
                (
                    Provider.HUGGINGFACE_INFERENCE,
                    ProviderKind.AGENT,
                ): SDKClient.HUGGINGFACE_INFERENCE
            }
            | {(Provider.MISTRAL, ProviderKind.AGENT): SDKClient.MISTRAL}
            | {
                (provider, ProviderKind.AGENT): SDKClient.OPENAI
                for provider in {
                    p
                    for p in Provider
                    if p.is_agent_provider()
                    and p.uses_openai_api
                    and p not in (Provider.AZURE, Provider.GROQ)
                }
            }
            | {(Provider.DUCKDUCKGO, ProviderKind.DATA): SDKClient.DUCKDUCKGO}
            | {(Provider.TAVILY, ProviderKind.DATA): SDKClient.TAVILY}
        )
    )
    if provider and kind:
        return _sdk_client_map.get((Provider.from_string(provider), ProviderKind.from_string(kind)))
    if provider and not kind:
        return {
            knd: client
            for (prov, knd), client in _sdk_client_map.items()
            if prov == Provider.from_string(provider)
        }
    if kind and not provider:
        return {
            prov: client
            for (prov, knd), client in _sdk_client_map.items()
            if knd == ProviderKind.from_string(kind)
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
    return _get_sdk_client_map(client_cls, kind=kind)  # ty:ignore[no-matching-overload]


@cache
def get_provider_kind_sdk_clients_for_provider(
    client_cls: type[SDKClient], provider: Provider
) -> dict[ProviderKind, tuple[SDKClient, ...] | SDKClient]:
    """Get all SDK clients for a given provider.

    Args:
        client_cls: The `SDKClient` class to get the clients for.
        provider: The `Provider` to get the clients for as a string.
    """
    return _get_sdk_client_map(client_cls, provider)  # ty:ignore[no-matching-overload]


__all__ = (
    "get_provider_capabilities_map",
    "get_provider_kind_sdk_clients_for_provider",
    "get_provider_kinds",
    "get_provider_sdk_clients_for_kind",
    "get_sdk_client",
    "get_sdk_client_map",
)
