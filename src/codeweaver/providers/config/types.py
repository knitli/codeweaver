"""Shared types for providers configurations."""

import ssl

from collections.abc import Callable, Mapping
from typing import Any, Literal, NotRequired, TypedDict

import httpx

from pydantic import NonNegativeInt, PositiveInt


class HttpxClientParams(TypedDict, total=False):
    """Parameters for configuring an httpx client."""

    auth: NotRequired[httpx._types.AuthTypes]
    params: NotRequired[httpx._types.QueryParamTypes]
    headers: NotRequired[httpx._types.HeaderTypes]
    cookies: NotRequired[httpx._types.CookieTypes]
    verify: NotRequired[bool | ssl.SSLContext | str]
    cert: NotRequired[httpx._types.CertTypes]
    http1: NotRequired[bool]
    http2: NotRequired[bool]
    proxy: NotRequired[httpx._types.ProxyTypes]
    mounts: NotRequired[Mapping[str, httpx._transports.AsyncBaseTransport]]
    timeout: NotRequired[httpx._types.TimeoutTypes]
    follow_redirects: NotRequired[bool]
    limits: NotRequired[httpx.Limits]
    max_redirects: NotRequired[NonNegativeInt]
    event_hooks: NotRequired[Mapping[str, list[Callable[..., Any]]]]
    base_url: NotRequired[httpx.URL | str]
    transport: NotRequired[httpx._transports.AsyncBaseTransport]
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
