# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""
Models and TypedDict classes for provider and AI (embedding, sparse embedding, reranking, agent) model settings.

The overall pattern:
    - Each potential provider client (the actual client class, e.g., OpenAIClient) has a corresponding ClientOptions class (e.g., OpenAIClientOptions).
    - There is a baseline provider settings model, `BaseProviderSettings`. Each provider type (embedding, data, vector store, etc.) has a corresponding settings model that extends `BaseProviderSettings` (e.g., `EmbeddingProviderSettings`). These are mostly almost identical, but the class distinctions make identification easier and improves clarity.
    - Certain providers with unique settings requirements can define a mixin class that provides the additional required settings. Note that these should not overlap with the client options for the provider.
    - A series of discriminators help with identifying the correct client options and provider settings classes based on the provider and other settings.
"""

from __future__ import annotations

import contextlib
import importlib
import logging
import os
import ssl

from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import Annotated, Any, Literal, NotRequired, Required, Self, TypedDict

import httpx

from pydantic import (
    AnyUrl,
    BaseModel,
    ConfigDict,
    Discriminator,
    Field,
    NonNegativeInt,
    PositiveFloat,
    PositiveInt,
    SecretStr,
    Tag,
    model_validator,
)

from codeweaver.core import (
    BASEDMODEL_CONFIG,
    AnonymityConversion,
    BasedModel,
    ConfigurationError,
    FilteredKey,
    FilteredKeyT,
    Provider,
    ProviderLiteral,
)


logger = logging.getLogger(__name__)

# ===========================================================================
# *                           Client Options
# ===========================================================================


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


if (
    importlib.util.find_spec("fastembed") is not None
    or importlib.util.find_spec("fastembed-gpu") is not None
):
    from fastembed.common.types import OnnxProvider
else:
    OnnxProvider = object

if importlib.util.find_spec("torch") is not None:
    from torch.nn import Module
else:
    Module = object
if importlib.util.find_spec("sentence-transformers") is not None:
    from sentence_transformers.model_card import SentenceTransformerModelCardData
else:
    SentenceTransformerModelCardData = object


class ClientOptions(BasedModel):
    """A base class for provider client options.

    Client options are specific to the underlying SDK client that's used. They are not
    necessarily the same as the *provider*. The provider is who you pay, while the client
    if what you use to connect. For the most part, this is intuitive but there are some
    exceptions. The biggest exception is Azure, which does not have its own provider class,
    because it instead uses either Cohere or OpenAI providers. You're connecting to and paying Azure,
    but using the correct provider class for what you're trying to do.

    The standard way to pass client options to a provider is with the `as_settings()` method, which provides a kwargs dictionary.
    """

    model_config = BASEDMODEL_CONFIG | ConfigDict(frozen=True, from_attributes=True)
    _core_provider: Annotated[
        Provider,
        Field(
            exclude=True,
            init=False,
            description="The provider most associated with this options class. For example, OpenAI for OpenAIClientOptions, or Cohere for CohereClientOptions, even though both can be used with multiple providers. This value should be a provider that the client is *always* used with.",
        ),
    ]
    _providers: Annotated[
        tuple[Provider, ...],
        Field(
            exclude=True,
            init=False,
            description="Providers this client options class can apply to.",
        ),
    ]

    def __init__(self, **data: Any) -> None:
        """Initialize the client options and apply environment variables."""
        for key, value in data.items():
            if key in type(self).model_fields and value:
                object.__setattr__(self, key, value)
        self.apply_env_vars()
        super().__init__(**data)

    @staticmethod
    def _filter_values(value: Any) -> Any:
        if isinstance(value, SecretStr):
            return value.get_secret_value()
        return str(value) if isinstance(value, AnyUrl) else value

    def as_settings(self) -> dict[str, Any]:
        """Return the client options as a dictionary suitable for passing as settings to the client constructor."""
        settings = self.model_dump(exclude={"_core_provider", "_providers"})
        return {k: self._filter_values(v) for k, v in settings.items()}

    @property
    def core_provider(self) -> Provider:
        """Return the core provider this client options class is most associated with."""
        return self._core_provider

    @property
    def providers(self) -> tuple[Provider, ...]:
        """Return the providers this client options class can apply to."""
        return self._providers

    def client_env_vars(self) -> dict[str, tuple[str, ...] | dict[str, Any]]:
        """Return a dictionary of environment variables for the client options, mapping client variable names to the environment variable name."""
        env_vars = self._core_provider.all_envs_for_client(self._core_provider.variable)  # ty:ignore[invalid-argument-type]
        mapped_vars = {}
        fields = tuple(type(self).model_fields)
        for env_var in env_vars:
            variables = env_var.variables if "variables" in env_var._asdict() else ()
            if (
                (
                    var_name := env_var.variable_name
                    if "variable_name" in env_var._asdict()
                    else None
                )
                and variables
                and (
                    client_var := next(
                        (var.variable for var in variables if var.dest == "client"), None
                    )
                )
            ):
                mapped_vars[var_name] = {client_var.variable: env_var.env}
            elif var_name and var_name in fields:
                mapped_vars[var_name] = (
                    (env_var.env,)
                    if var_name not in mapped_vars
                    else (mapped_vars[var_name] + (env_var.env,))
                )
            elif variables:
                for var in variables:
                    if var.dest == "client" and var.variable in fields:
                        mapped_vars[var.variable] = (
                            (env_var.env,)
                            if var.variable not in mapped_vars
                            else (mapped_vars[var.variable] + (env_var.env,))
                        )
        return mapped_vars

    def _handle_env_tuple(self, var_name: str, env_var_names: tuple[str, ...]) -> None:
        if value := next(
            (os.getenv(env_name) for env_name in env_var_names if os.getenv(env_name)), None
        ):
            if (
                var_name in type(self).model_fields
                and not (existing_value := getattr(self, var_name, None))
            ) or (existing_value and existing_value == value):
                object.__setattr__(self, var_name, value)
                return
            if var_name in type(self).model_fields and existing_value:
                if (
                    isinstance(existing_value, SecretStr)
                    and existing_value.get_secret_value() == value
                ):
                    return
                logger.warning(
                    "Environment variable %s is set but client option %s already has a different value; skipping environment variable.",
                    env_var_names,
                    var_name,
                )

    def _handle_env_dict(self, var_name: str, env_var_names: dict[str, Any]) -> None:
        if var_name not in type(self).model_fields:
            return
        existing_value = getattr(self, var_name, None) or {}
        env_vars = {k: os.getenv(v) for k, v in env_var_names.items() if os.getenv(v) is not None}
        if not existing_value and env_vars:
            object.__setattr__(self, var_name, env_vars)
            return
        if isinstance(existing_value, dict):
            object.__setattr__(self, var_name, existing_value | env_vars)
            return
        if isinstance(existing_value, BaseModel | tuple):
            with contextlib.suppress(AttributeError, ValueError, TypeError):
                object.__setattr__(
                    self,
                    var_name,
                    existing_value.model_dump() | env_vars
                    if isinstance(existing_value, BaseModel)
                    else existing_value._asdict() | env_vars,
                )
                return

    def apply_env_vars(self) -> None:
        """Apply environment variables to the client options."""
        env_vars = self.client_env_vars()
        for var_name, env_var_names in env_vars.items():
            if var_name not in type(self).model_fields:
                continue
            if isinstance(env_var_names, tuple):
                self._handle_env_tuple(var_name, env_var_names)
                continue
            # it's a dictionary
            self._handle_env_dict(var_name, env_var_names)


class CohereClientOptions(ClientOptions):
    """Client options for Cohere (rerank and embeddings)."""

    _core_provider: Provider = Provider.COHERE
    _providers: tuple[Provider, ...] = (Provider.COHERE, Provider.AZURE, Provider.HEROKU)

    api_key: (
        Annotated[
            SecretStr | Callable[[], str],
            Field(description="Cohere API key.", default_factory=SecretStr),
        ]
        | None
    ) = None
    base_url: Annotated[AnyUrl, Field(description="Base URL for the Cohere API.")] | None = None
    environment: Literal["production", "staging", "development"] = "production"
    client_name: str | None = "codeweaver_cohere_client"
    timeout: PositiveFloat | None = None
    httpx_client: httpx.Client | None = None
    thread_pool_executor: ThreadPoolExecutor | None = None
    log_experimental: bool = True  # disables warnings about experimental features

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        return {
            FilteredKey("api_key"): AnonymityConversion.BOOLEAN,
            FilteredKey("base_url"): AnonymityConversion.BOOLEAN,
            FilteredKey("client_name"): AnonymityConversion.HASH,
            FilteredKey("httpx_client"): AnonymityConversion.BOOLEAN,
        }


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
    grpc_options: dict[str, Any] | None = None
    auth_token_provider: (
        Callable[[], SecretStr | str] | Callable[[], Awaitable[SecretStr | str]] | None
    ) = None
    cloud_inference: bool = False
    local_inference_batch_size: PositiveInt | None = None
    check_compatibility: bool = True
    pool_size: PositiveInt | None = None  # (httpx pool size, default 100)
    kwargs: HttpxClientParams | GrpcParams | None = None

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

    def _handle_cloud(self) -> None:
        pass

    def _to_nones(self, attrs: Sequence[str]) -> None:
        for attr in attrs:
            setattr(self, attr, False if attr == "https" else None)

    @staticmethod
    def _is_local_url(url: str | AnyUrl) -> bool:
        """Determine if a URL is local."""
        host = (url.host if isinstance(url, AnyUrl) else url) or ""
        return any(local in host for local in ("localhost", "127.0.0.1", "0.0.0.0"))  # noqa: S104

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
            self.url = AnyUrl(url="http://127.0.0.1")
            self.https = False
            return
        if ":memory:" in url_like_settings:
            self.location = ":memory:"
            self._to_nones(["url", "host", "https", "path"])
            return
        if self.path:
            self._to_nones(["location", "url", "host", "https"])
            return
        # we've already handled `:memory`
        if self.location:
            self.url = (
                self.url or None
                if self.location in {"localhost", "127.0.0.1", "0.0.0.0"}  # noqa: S104
                else AnyUrl(self.location)
            )
            self.host = self.host or None if self.url else self.location
            self._to_nones(["location", "path"])
        self._resolve_host_and_url()

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
        self._handle_cloud()
        if (
            (self.url or self.host)
            and self.prefer_grpc
            and not self._is_local_url(self.url or self.host or "")
        ):
            # GRPC over http requires http2
            self.kwargs = HttpxClientParams(
                **((self.kwargs or {}) | {"http2": True, "http1": False})
            )
        if self.url and not self._is_local_url(self.url) and self.https is None:
            self.https = True
            if self.url.scheme == "http":
                self.url = AnyUrl(url=str(self.url).replace("http://", "https://", 1))
        return self


class OpenAIClientOptions(ClientOptions):
    """Client options for OpenAI-based embedding providers."""

    _core_provider: Provider = Provider.OPENAI
    _providers: tuple[Provider, ...] = tuple(
        provider for provider in Provider if provider.uses_openai_api
    )

    api_key: (
        SecretStr | Callable[[], str | SecretStr] | Callable[[], Awaitable[str | SecretStr]] | None
    ) = None
    organization: str | None = None
    project: str | None = None
    webhook_secret: SecretStr | None = None
    base_url: AnyUrl | None = None
    websocket_base_url: AnyUrl | None = None
    timeout: PositiveFloat | None = None
    max_retries: PositiveInt | None = None
    default_headers: Mapping[str, str] | None = None
    default_query: Mapping[str, object] | None = None
    http_client: httpx.Client | None = None
    _strict_response_validation: bool = False

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        return {
            FilteredKey(name): AnonymityConversion.BOOLEAN
            for name in (
                "api_key",
                "webhook_secret",
                "http_client",
                "default_headers",
                "default_query",
            )
        } | {
            FilteredKey(name): AnonymityConversion.HASH
            for name in ("organization", "project", "base_url", "websocket_base_url")
        }


class BedrockClientOptions(ClientOptions):
    """Client options for Boto3-based providers like Bedrock. Most of these are required but can be configured in other ways, such as environment variables or AWS config files."""

    _core_provider: Provider = Provider.BEDROCK
    _providers: tuple[Provider, ...] = (Provider.BEDROCK,)

    aws_access_key_id: str | None = None
    aws_secret_access_key: SecretStr | None = None
    aws_session_token: SecretStr | None = None
    region_name: str | None = None
    profile_name: str | None = None
    aws_account_id: str | None = None
    botocore_session: Any | None = None

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        return {FilteredKey("aws_secret_access_key"): AnonymityConversion.BOOLEAN} | {
            FilteredKey(name): AnonymityConversion.HASH
            for name in (
                "aws_access_key_id",
                "aws_session_token",
                "region_name",
                "profile_name",
                "aws_account_id",
            )
        }


class GoogleClientOptions(ClientOptions):
    """Client options for the GenAI Google provider."""

    _core_provider: Provider = Provider.GOOGLE
    _providers: tuple[Provider, ...] = (Provider.GOOGLE,)

    api_key: SecretStr | None = None
    vertex_ai: bool = False
    credentials: Any | None = None
    project: str | None = None
    location: str | None = None
    debug_config: dict[str, Any] | None = None
    http_options: dict[str, Any] | None = None

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        return {
            FilteredKey(name): AnonymityConversion.BOOLEAN
            for name in ("api_key", "location", "http_options", "credentials")
        } | {FilteredKey("project"): AnonymityConversion.HASH}


class FastEmbedClientOptions(ClientOptions):
    """Client options for FastEmbed-based embedding providers."""

    _core_provider: Provider = Provider.FASTEMBED
    _providers: tuple[Provider, ...] = (Provider.FASTEMBED,)

    model_name: str
    cache_dir: str | None = None
    threads: int | None = None
    providers: Sequence[OnnxProvider] | None = None
    cuda: bool = False
    device_ids: list[int] | None = None
    lazy_load: bool = True

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        return {FilteredKey("cache_dir"): AnonymityConversion.HASH}


class SentenceTransformersClientOptions(ClientOptions):
    """Client options for SentenceTransformers-based embedding providers."""

    _core_provider: Provider = Provider.SENTENCE_TRANSFORMERS
    _providers: tuple[Provider, ...] = (Provider.SENTENCE_TRANSFORMERS,)

    model_name_or_path: str | None = None
    modules: Iterable[Module] | None = None
    device: str | None = None
    prompts: dict[str, str] | None = None
    default_prompt_name: str | None = None
    similarity_fn_name: Literal["cosine", "dot", "euclidean", "manhattan"] | None = None
    cache_folder: str | None = None
    trust_remote_code: bool = False
    revision: str | None = None
    local_files_only: bool = False
    token: bool | SecretStr | None = None
    use_auth_token: bool | SecretStr | None = None
    truncate_dim: int | None = None
    model_kwargs: dict[str, Any] | None = None
    tokenizer_kwargs: dict[str, Any] | None = None
    config_kwargs: dict[str, Any] | None = None
    model_card_data: SentenceTransformerModelCardData | None = None
    backend: Literal["torch", "onnx", "openvino"] = "torch"

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        return {
            FilteredKey("cache_folder"): AnonymityConversion.HASH,
            FilteredKey("model_name_or_path"): AnonymityConversion.HASH,
        }


class HFInferenceClientOptions(ClientOptions):
    """Client options for HuggingFace Inference API-based embedding providers."""

    _core_provider: Provider = Provider.HUGGINGFACE_INFERENCE
    _providers: tuple[Provider, ...] = (Provider.HUGGINGFACE_INFERENCE,)

    model: str | None = None
    provider: str | None = None
    token: SecretStr | None = None
    timeout: PositiveFloat | None = None
    headers: dict[str, str] | None = None
    cookies: dict[str, str] | None = None
    trust_env: bool = False
    proxies: Any | None = None
    bill_to: str | None = None
    base_url: AnyUrl | None = None
    api_key: SecretStr | None = None

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        return {
            FilteredKey(name): AnonymityConversion.BOOLEAN
            for name in ("token", "api_key", "headers", "cookies", "proxies")
        } | {
            FilteredKey("base_url"): AnonymityConversion.HASH,
            FilteredKey("bill_to"): AnonymityConversion.HASH,
        }


class MistralClientOptions(ClientOptions):
    """Client options for Mistral-based embedding providers."""

    _core_provider: Provider = Provider.MISTRAL
    _providers: tuple[Provider, ...] = (Provider.MISTRAL,)

    api_key: (
        SecretStr | Callable[[], str | SecretStr] | Callable[[], Awaitable[str | SecretStr]] | None
    ) = None
    server: str | None = None
    server_url: AnyUrl | None = None
    url_params: dict[str, str] | None = None
    async_client: httpx.AsyncClient | None = None
    retry_config: Any | None = None
    timeout_ms: PositiveInt | None = None
    debug_logger: Any | None = None

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        return {
            FilteredKey("api_key"): AnonymityConversion.BOOLEAN,
            FilteredKey("server"): AnonymityConversion.HASH,
            FilteredKey("server_url"): AnonymityConversion.HASH,
            FilteredKey("url_params"): AnonymityConversion.HASH,
            FilteredKey("async_client"): AnonymityConversion.BOOLEAN,
        }


class VoyageClientOptions(ClientOptions):
    """Client options for Voyage AI-based embedding and reranking providers."""

    _core_provider: Provider = Provider.VOYAGE
    _providers: tuple[Provider, ...] = (Provider.VOYAGE,)

    api_key: SecretStr | None = None
    max_retries: PositiveInt = 0
    timeout: PositiveFloat | None = None

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        return {FilteredKey("api_key"): AnonymityConversion.BOOLEAN}


class FastEmbedClientOptions(ClientOptions):
    """Client options for FastEmbed-based embedding providers."""

    _core_provider: Provider = Provider.FASTEMBED
    _providers: tuple[Provider, ...] = (Provider.FASTEMBED,)

    model_name: str
    cache_dir: str | None = None
    cuda: bool = False
    device_ids: list[int] | None = None


# We chose TypedDicts originally for speed. They can be substantially faster than Pydantic models (according to Pydantic: https://docs.pydantic.dev/2.12/concepts/performance/#use-typeddict-over-nested-models) But we lose a lot of benefits of Pydantic models.

# ===========================================================================
# *            Provider Connection and Rate Limit Settings
# ===========================================================================


class ConnectionRateLimitConfig(BasedModel):
    """Settings for connection rate limiting."""

    max_requests_per_second: PositiveInt | None
    burst_capacity: PositiveInt | None
    backoff_multiplier: PositiveFloat | None
    max_retries: PositiveInt | None


class ConnectionConfiguration(BasedModel):
    """Settings for connection configuration. You probably don't need to set these unless you're doing something special."""

    headers: Annotated[
        dict[str, str] | None, Field(description="HTTP headers to include in requests.")
    ] = None
    rate_limits: Annotated[
        ConnectionRateLimitConfig | None,
        Field(description="Rate limit configuration for the connection."),
    ] = None
    httpx_config: Annotated[
        HttpxClientParams | None,
        Field(
            description="You may optionally provide custom client parameters for the httpx client. CodeWeaver will use your parameters when it constructs its http client pool. You probably don't need this unless you need to handle unique auth or similar requirements."
        ),
    ] = None

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        return {
            FilteredKey("headers"): AnonymityConversion.BOOLEAN,
            FilteredKey("httpx_config"): AnonymityConversion.BOOLEAN,
        }


class BaseProviderSettings(BasedModel):
    """Base settings for all providers."""

    provider: Provider
    connection: ConnectionConfiguration | None = None
    tag: ProviderLiteral = Field(
        default_factory=lambda data: (
            data.get("provider").variable if isinstance(data, dict) else data.provider.variable
        ),
        exclude=True,
        init=False,
        description="Discriminator tag for the provider.",
    )

    def _telemetry_keys(self) -> None:
        return None


class BaseProviderSettingsDict(TypedDict, total=False):
    """Base settings for all providers. Represents `BaseProviderSettings` in a TypedDict form."""

    provider: Required[Provider]
    connection: NotRequired[ConnectionConfiguration | None]


# ===========================================================================
# *                    Client Discriminators
# ===========================================================================

type GeneralRerankingClientOptionsType = Annotated[
    Annotated[SentenceTransformersClientOptions, Tag(Provider.SENTENCE_TRANSFORMERS.variable)]
    | Annotated[CohereClientOptions, Tag(Provider.COHERE.variable)]
    | Annotated[VoyageClientOptions, Tag(Provider.VOYAGE.variable)],
    Field(description="Reranking client options type.", discriminator="tag"),
]


def _discriminate_embedding_clients(v: Any) -> str:
    """Identify the provider-specific settings type for discriminator field."""
    return v["tag"] if isinstance(v, dict) else v.tag


def discriminate_azure_embedding_client_options(v: Any) -> str:
    """Identify the Azure embedding provider settings type for discriminator field."""
    model_settings = v["model_settings"] if isinstance(v, dict) else v.model_settings
    model = (
        model_settings.get("model") if isinstance(model_settings, dict) else model_settings.model
    )
    if model in ("text-embedding-3-small", "text-embedding-3-large"):
        return "openai"
    return "cohere"


type GeneralEmbeddingClientOptionsType = Annotated[
    Annotated[SentenceTransformersClientOptions, Tag(Provider.SENTENCE_TRANSFORMERS.variable)]
    | Annotated[CohereClientOptions, Tag(Provider.COHERE.variable)]
    | Annotated[OpenAIClientOptions, Tag(Provider.OPENAI.variable)]
    | Annotated[GoogleClientOptions, Tag(Provider.GOOGLE.variable)]
    | Annotated[HFInferenceClientOptions, Tag(Provider.HUGGINGFACE_INFERENCE.variable)]
    | Annotated[MistralClientOptions, Tag(Provider.MISTRAL.variable)]
    | Annotated[VoyageClientOptions, Tag(Provider.VOYAGE.variable)],
    Field(
        description="Embedding client options type.",
        discriminator=Discriminator(_discriminate_embedding_clients),
    ),
]

__all__ = (
    "BaseProviderSettings",
    "BaseProviderSettingsDict",
    "BedrockClientOptions",
    "ClientOptions",
    "CohereClientOptions",
    "ConnectionConfiguration",
    "ConnectionRateLimitConfig",
    "FastEmbedClientOptions",
    "GeneralEmbeddingClientOptionsType",
    "GeneralRerankingClientOptionsType",
    "GoogleClientOptions",
    "GrpcParams",
    "HFInferenceClientOptions",
    "HttpxClientParams",
    "MistralClientOptions",
    "OpenAIClientOptions",
    "QdrantClientOptions",
    "SentenceTransformersClientOptions",
    "VoyageClientOptions",
    "discriminate_azure_embedding_client_options",
)
