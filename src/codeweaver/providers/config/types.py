# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Shared types for providers configurations."""

import ssl

from collections.abc import Callable, Mapping
from typing import TYPE_CHECKING, Any, Literal, NotRequired, TypedDict

from pydantic import NonNegativeInt, PositiveInt


if TYPE_CHECKING:
    pass


# Mirror types to avoid httpx dependency at module initialization
# These will accept httpx types at runtime but don't require httpx import
class HttpxClientParams(TypedDict, total=False):
    """Parameters for configuring an httpx client.

    Note: Type annotations use Any to avoid httpx import at initialization.
    At runtime, these accept the corresponding httpx types.
    """

    auth: NotRequired[Any]  # httpx._types.AuthTypes
    params: NotRequired[Any]  # httpx._types.QueryParamTypes
    headers: NotRequired[Any]  # httpx._types.HeaderTypes
    cookies: NotRequired[Any]  # httpx._types.CookieTypes
    verify: NotRequired[bool | ssl.SSLContext | str]
    cert: NotRequired[Any]  # httpx._types.CertTypes
    http1: NotRequired[bool]
    http2: NotRequired[bool]
    proxy: NotRequired[Any]  # httpx._types.ProxyTypes
    mounts: NotRequired[Mapping[str, Any]]  # Mapping[str, httpx._transports.AsyncBaseTransport]
    timeout: NotRequired[Any]  # httpx._types.TimeoutTypes
    follow_redirects: NotRequired[bool]
    limits: NotRequired[Any]  # httpx.Limits
    max_redirects: NotRequired[NonNegativeInt]
    event_hooks: NotRequired[Mapping[str, list[Callable[..., Any]]]]
    base_url: NotRequired[Any | str]  # httpx.URL | str
    transport: NotRequired[Any]  # httpx._transports.AsyncBaseTransport
    trust_env: NotRequired[bool]
    default_encoding: NotRequired[
        Literal["utf-8", "utf-16", "utf-32"]
        | Callable[[bytes], Literal["utf-8", "utf-16", "utf-32"]]
    ]


class CohereRequestOptionsDict(TypedDict, total=False):
    """Additional request options for the Cohere API."""

    timeout_in_seconds: NotRequired[PositiveInt]
    """Timeout for the request in seconds."""

    max_retries: NotRequired[PositiveInt]
    """Number of retries for the request in case of failure."""

    additional_headers: NotRequired[dict[str, Any]]
    """Additional headers to include in the request."""

    additional_query_parameters: NotRequired[dict[str, Any]]
    """Additional query parameters to include in the request."""


__all__ = ("CohereRequestOptionsDict", "HttpxClientParams")
