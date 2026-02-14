# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Vector Store Client Options."""

from __future__ import annotations

import logging

from collections.abc import Awaitable, Callable, Sequence
from typing import Any, Literal, NotRequired, Self, TypedDict, cast

from pydantic import (
    AnyUrl,
    ConfigDict,
    Field,
    PositiveFloat,
    PositiveInt,
    SecretStr,
    model_validator,
)

from codeweaver.core.constants import LOCALHOST_INDICATORS, LOCALHOST_URL, QDRANT_MEMORY_LOCATION
from codeweaver.core.exceptions import ConfigurationError
from codeweaver.core.types import AnonymityConversion, FilteredKey, FilteredKeyT
from codeweaver.core.types.provider import Provider
from codeweaver.providers.config.clients.base import ClientOptions
from codeweaver.providers.config.types import HttpxClientParams


logger = logging.getLogger(__name__)


class GrpcParams(TypedDict, total=False):
    """Parameters for configuring a grpc channel."""

    root_certificates: NotRequired[bytes]
    """PEM encoded root certificates as bytes."""
    private_key: NotRequired[bytes]
    """PEM encoded private key as bytes."""
    certificate_chain: NotRequired[bytes]
    """PEM encoded certificate chain as bytes."""
    metadata: NotRequired[Sequence[tuple[str, str]]]
    """Metadata to be sent with each request."""
    options: NotRequired[dict[str, Any]]
    """A mapping of channel options. See grpc documentation for details. Note: max_send_message_length and max_receive_message_length can't be set here because qdrant_client will override them (always -1)."""


class QdrantClientOptions(ClientOptions):
    """Client options for Qdrant vector store provider.

    Note: `kwargs` are passed directly to the underlying httpx or grpc client.

    The instantiated client's `_client` attribute will be either an `httpx.AsyncClient` for rest.based connections, or a `grpc.aio.Channel` for grpc-based connections, which may be useful for providing custom httpx or grpc clients.
    """

    # we need to manipulate values on this one, so we'll leave it mutable
    model_config = ClientOptions.model_config | ConfigDict(frozen=False)

    _core_provider: Provider = Provider.QDRANT
    _providers: tuple[Provider, ...] = (Provider.QDRANT, Provider.MEMORY)

    location: Literal[":memory:"] | AnyUrl | None = None
    url: AnyUrl | Literal[":memory:"] | None = None
    port: PositiveInt | None = 6333
    grpc_port: PositiveInt | None = 6334
    https: bool | None = None
    api_key: str | None = None
    prefer_grpc: bool = False
    prefix: str | None = None
    timeout: PositiveFloat | None = None
    host: AnyUrl | str | None = None
    path: str | None = None
    force_disable_check_same_thread: bool = False
    grpc_options: GrpcParams | None = None
    auth_token_provider: (
        Callable[[], SecretStr | str] | Callable[[], Awaitable[SecretStr | str]] | None
    ) = None
    cloud_inference: bool = False
    local_inference_batch_size: PositiveInt | None = None
    check_compatibility: bool = True
    pool_size: PositiveInt | None = None  # (httpx pool size, default 100)

    # Advanced options (escape hatches for power users)
    advanced_http_options: dict[str, Any] | None = Field(
        default=None,
        description="Advanced httpx.AsyncClient parameters for power users. "
        "Common options are available as explicit fields above. "
        "Use this for specialized httpx configuration (custom auth, headers, proxies, etc.). "
        "See httpx documentation for available options.",
    )

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        # Location isn't sensitive because after `finalize_settings` it will only be `:memory:` or None
        return {
            FilteredKey(name): AnonymityConversion.BOOLEAN
            for name in ("api_key", "auth_token_provider")
        } | {FilteredKey(name): AnonymityConversion.HASH for name in ("url", "host", "path")}

    def _handle_cloud_inference(self) -> None:
        """Adjust settings for cloud inference if enabled."""
        if not self.cloud_inference:
            return
        if not self.url or (
            (self.url and not self.url.host.endswith(".cloud.qdrant.io"))
            or (self.host and not self.host.host.endswith(".cloud.qdrant.io"))
        ):
            logger.warning(
                "Cloud inference can only be enabled for Qdrant cloud endpoints. Disabling cloud_inference."
            )
            self.cloud_inference = False
            return
        logger.warning(
            "We haven't tested CodeWeaver with Qdrant Cloud inference yet. It may not work as expected. If you proceed, please report any issues you encounter to help us improve support."
        )

    def _to_nones(self, attrs: Sequence[str]) -> None:
        for attr in attrs:
            setattr(self, attr, False if attr == "https" else None)

    @staticmethod
    def _is_local_url(url: str | AnyUrl) -> bool:
        """Determine if a URL is local."""
        host = (url.host if isinstance(url, AnyUrl) else url) or ""
        return any(local in host for local in LOCALHOST_INDICATORS)

    def _resolve_host_and_url(self) -> None:
        """Resolve host and url settings to avoid conflicts."""
        if not self.host or not self.url:
            return
        if self.url.host == (self.host if isinstance(self.host, str) else self.host.host) or (
            self._is_local_url(self.url) and self._is_local_url(self.host)
        ):
            self.host = None
            return
        if not self._is_local_url(self.url):
            self.host = None
            return
        if not self._is_local_url(self.host):
            self.url = None
            return
        # at this point, we can raise:
        raise ConfigurationError(
            "Conflicting Qdrant client options: both `host` and `url` are set, and they aren't the same.",
            suggestions=["Set only one of `host` or `url` to avoid conflicts."],
        )

    def _normalize_settings(self) -> None:
        """Normalize settings for Qdrant client options.

        The goal here is to ensure that only one of `location`, `url`, `host`, or `path` is set, as required by the Qdrant client.
        """
        if not (url_like_settings := (self.url, self.host, self.location, self.path)):
            self.url = AnyUrl(url=LOCALHOST_URL)
            self.https = False
            return
        if ":memory:" in url_like_settings:
            self.location = QDRANT_MEMORY_LOCATION
            self._to_nones(["url", "host", "https", "path"])
            return
        if self.path:
            self._to_nones(["location", "url", "host", "https"])
            return
        # we've already handled `:memory`
        if self.location:
            self.url = (
                self.url or None if self.location in LOCALHOST_INDICATORS else AnyUrl(self.location)
            )
            self.host = self.host or None if self.url else self.location
            self._to_nones(["location", "path"])
        self._resolve_host_and_url()

    def is_local_on_disk(self) -> bool:
        """Check if the Qdrant client is configured for local on-disk storage."""
        return bool(
            self.path is not None
            or (self.url and self._is_local_url(self.url))
            or (self.host and self._is_local_url(self.host))
        )

    def _add_connection_params(self, params: dict[str, Any]) -> None:
        """Add connection-related parameters to params dict."""
        if self.location is not None:
            params["location"] = self.location
        if self.url is not None:
            params["url"] = str(self.url) if isinstance(self.url, AnyUrl) else self.url
        if self.host is not None:
            params["host"] = str(self.host) if isinstance(self.host, AnyUrl) else self.host
        if self.path is not None:
            params["path"] = self.path
        if self.port is not None:
            params["port"] = self.port
        if self.grpc_port is not None:
            params["grpc_port"] = self.grpc_port
        if self.https is not None:
            params["https"] = self.https

    def _add_auth_params(self, params: dict[str, Any]) -> None:
        """Add authentication parameters to params dict."""
        if self.api_key is not None:
            params["api_key"] = self.api_key
        if self.auth_token_provider is not None:
            params["auth_token_provider"] = self.auth_token_provider

    def _add_preference_params(self, params: dict[str, Any]) -> None:
        """Add preference parameters to params dict."""
        params["prefer_grpc"] = self.prefer_grpc
        if self.prefix is not None:
            params["prefix"] = self.prefix
        if self.timeout is not None:
            params["timeout"] = self.timeout

    def _add_advanced_params(self, params: dict[str, Any]) -> None:
        """Add advanced configuration parameters to params dict."""
        params["force_disable_check_same_thread"] = self.force_disable_check_same_thread
        if self.grpc_options is not None:
            params["grpc_options"] = self.grpc_options
        params["cloud_inference"] = self.cloud_inference
        if self.local_inference_batch_size is not None:
            params["local_inference_batch_size"] = self.local_inference_batch_size
        params["check_compatibility"] = self.check_compatibility
        if self.pool_size is not None:
            params["pool_size"] = self.pool_size

    def _add_http_params(self, params: dict[str, Any]) -> None:
        """Add advanced HTTP options to params dict."""
        if self.advanced_http_options is not None:
            # These are passed through to httpx.AsyncClient
            params["kwargs"] = self.advanced_http_options

    def to_qdrant_params(self) -> dict[str, Any]:
        """Convert client options to qdrant_client constructor parameters.

        Maps CodeWeaver's simplified interface to qdrant_client's expected format.
        Handles both common cases (explicit fields) and advanced cases (escape hatches).

        Returns:
            Dictionary suitable for passing to AsyncQdrantClient constructor

        Example:
            >>> options = QdrantClientOptions(
            ...     url="https://qdrant.example.com", api_key="secret-key", timeout=30.0
            ... )
            >>> params = options.to_qdrant_params()
            >>> client = AsyncQdrantClient(**params)
        """
        params: dict[str, Any] = {}

        self._add_connection_params(params)
        self._add_auth_params(params)
        self._add_preference_params(params)
        self._add_advanced_params(params)
        self._add_http_params(params)

        return params

    @model_validator(mode="after")
    def finalize_settings(self) -> Self:
        """Validate that either location or url is provided.

        This is actually less of a true validator and more of a guard against common foot-guns with the `qdrant_client`.

        Quick version: `qdrant_client` offers `location`, `path`, `url`, and `host` settings but resolves them in a way that's not super intuitive. It errors if more than one is set, but doesn't provide any overrides to help you avoid that situation -- despite the fact that it will ignore other settings of path or location is set...

        I'll give them the benefit of the doubt on the missing overrides and assume there're no overrides or better handling because of limitations imposed by their minimum python version. Clearly though, I should probably take a stab at a PR to improve this in qdrant-client itself when I get a few extra cycles. I understand that maintaining backward compatibility is important, and I know folks like to keep things explicit, but I think there's room for improvement here.

        Instead, we assume you're trying to provide reasonable parameters, and like many people, might set both `location` and `url`, or `location` and `host`/`port`, etc. The overall strategy is to look for non-default options first. If multiple are found, we prioritize them in this order: `location`, `path`, `url`, `host` (well, the last two get some nuanced handling). The others are nulled out.
        """
        self._normalize_settings()
        self._handle_cloud_inference()
        if (
            (self.url or self.host)
            and self.prefer_grpc
            and not self._is_local_url(self.url or self.host or "")
        ):
            # GRPC over http requires http2
            self.advanced_http_options = cast(
                dict[str, Any],
                HttpxClientParams(
                    **((self.advanced_http_options or {}) | {"http2": True, "http1": False})
                ),
            )
        if self.url and not self._is_local_url(self.url) and self.https is None:
            self.https = True
            if self.url.scheme == "http":
                self.url = AnyUrl(url=str(self.url).replace("http://", "https://", 1))
        return self


__all__ = ("QdrantClientOptions",)
