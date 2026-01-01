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

import importlib
import logging
import ssl

from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    Literal,
    NamedTuple,
    NotRequired,
    Required,
    Self,
    TypedDict,
    cast,
    is_typeddict,
)

import httpx

from pydantic import (
    AnyUrl,
    ConfigDict,
    Discriminator,
    Field,
    NonNegativeInt,
    PositiveFloat,
    PositiveInt,
    SecretStr,
    Tag,
    computed_field,
    model_validator,
)
from pydantic_ai.settings import ModelSettings as AgentModelSettings
from pydantic_ai.settings import merge_model_settings
from qdrant_client.http.models.models import SparseVectorParams, VectorParams

from codeweaver.core import (
    BASEDMODEL_CONFIG,
    AnonymityConversion,
    BasedModel,
    ConfigurationError,
    DictView,
    FilteredKey,
    FilteredKeyT,
    Provider,
    ProviderLiteral,
    Unset,
    get_user_config_dir,
)


if TYPE_CHECKING:
    from codeweaver.common.registry.types import LiteralKinds


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


if importlib.util.find_spec("fastembed") is not None:
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
        return self._core_provider

    @property
    def providers(self) -> tuple[Provider, ...]:
        return self._providers


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
        host = url.host if isinstance(url, AnyUrl) else url
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
                if self.location in {"localhost", "127.0.0.1", "0.0.0.0"}
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
            and not self._is_local_url(self.url or self.host)
        ):
            # GRPC over http requires http2
            self.kwargs = (self.kwargs or {}) | {"http2": True, "http1": False}
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


class Boto3ClientOptions(ClientOptions):
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


def _discriminate_azure_embedding_client_options(v: Any) -> str:
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


# ===========================================================================
# *            Provider Settings classes
# ===========================================================================


class DataProviderSettings(BaseProviderSettings):
    """Settings for data providers."""

    other: Annotated[
        dict[str, Any] | None, Field(description="Other provider-specific settings.")
    ] = None


class EmbeddingModelSettings(TypedDict, total=False):
    """Embedding model settings. Use this class for dense (vector) models."""

    model: Required[str]
    dimension: NotRequired[PositiveInt | None]
    data_type: NotRequired[str | None]
    custom_prompt: NotRequired[str | None]
    """A custom prompt to use for the embedding model, if supported. Most models do not support custom prompts for embedding."""
    embed_options: NotRequired[dict[str, Any] | None]
    """Keyword arguments to pass to the *provider* **client's** (like `voyageai.async_client.AsyncClient`) `embed` method. These are different from `model_options`, which are passed to the model constructor itself."""
    model_options: NotRequired[dict[str, Any] | None]
    """Keyword arguments to pass to the model's constructor."""


class SparseEmbeddingModelSettings(TypedDict, total=False):
    """Sparse embedding model settings. Use this class for sparse (e.g. bag-of-words) models."""

    model: Required[str]
    embed_options: NotRequired[dict[str, Any] | None]
    """Keyword arguments to pass to the *provider* **client's** (like `sentence_transformers.SparseEncoder`) `embed` method. These are different from `model_options`, which are passed to the model constructor itself."""
    model_options: NotRequired[dict[str, Any] | None]
    """Keyword arguments to pass to the model's constructor."""
    data_type: NotRequired[Literal["float32", "float16", "int8", "binary"] | None]


class RerankingModelSettings(TypedDict, total=False):
    """Rerank model settings."""

    model: Required[str]
    custom_prompt: NotRequired[str | None]


class BedrockProviderMixin:
    """Settings for AWS provider."""

    model_arn: str
    """The ARN of the Bedrock model you want to use."""
    client_options: (
        Annotated[
            Boto3ClientOptions | None,
            Field(
                description="Client options for the Bedrock client. Note: You need to provide most of the client settings, but may do so through environment variables, AWS config files, or IAM roles if not supplied here."
            ),
        ]
        | None
    ) = None

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        return {FilteredKey("model_arn"): AnonymityConversion.HASH}


class AzureProviderMixin:
    """Provider settings for Azure.

    You need to provide these settings if you are using Azure for either Cohere *embedding or reranking models* or OpenAI *embedding* models. You need to provide these for agentic models too, but not with this class (well, we'll probably try to make it work if you do, but no garauntees).

    **For OpenAI embedding models:**
    **We only support the "**next-generation** Azure OpenAI API." Currently, you need to opt into this API in your Azure settings. We didn't want to start supporting the old API knowing it's going away.

    Note that we don't currently support using Azure's SDKs directly for embedding or reranking models. Instead, we use the OpenAI or Cohere clients configured to use Azure endpoints.

    For agent models:
    We support both OpenAI APIs for agentic models because our support comes from `pydantic_ai`, which supports both, it also implements the Azure SDK for agents.
    """

    azure_resource_name: Annotated[
        str,
        Field(
            description="The name of your Azure resource. This is used to identify your resource in Azure."
        ),
    ]

    model_deployment: Annotated[
        str,
        Field(
            description="The deployment name of the model you want to use. This is *different* from the model name in `model_settings`, which is the name of the model itself (`text-embedding-3-small`). You need to create a deployment in your Azure OpenAI resource for each model you want to use, and provide the deployment name here."
        ),
    ]

    endpoint: Annotated[
        str | None,
        Field(
            description='The endpoint for your Azure resource. This is used to send requests to your resource. Only provide the endpoint, not the full URL. For example, if your endpoint is `https://your-cool-resource.<region_name>.inference.ai.azure.com/v1`, you would only provide "your-cool-resource" here.'
        ),
    ] = None

    region_name: Annotated[
        str | None,
        Field(
            description="The region name for your Azure resource. This is used to identify the region your resource is in. For example, `eastus` or `westus2`."
        ),
    ] = None

    api_key: Annotated[
        SecretStr | None,
        Field(
            description="Your Azure API key. If not provided, we'll assume you have your Azure credentials configured in another way, such as environment variables."
        ),
    ] = None

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        return {
            FilteredKey("azure_resource_name"): AnonymityConversion.HASH,
            FilteredKey("model_deployment"): AnonymityConversion.HASH,
            FilteredKey("endpoint"): AnonymityConversion.HASH,
            FilteredKey("region_name"): AnonymityConversion.HASH,
            FilteredKey("api_key"): AnonymityConversion.BOOLEAN,
        }


class FastembedProviderMixin:
    """Special settings for Fastembed-GPU provider.

    These settings only apply if you are using a Fastembed provider, installed the `codeweaver[fastembed-gpu]` or `codeweaver[full-gpu]` extra, have a CUDA-capable GPU, and have properly installed and configured the ONNX GPU runtime (see ONNX docs).

    You can provide these settings with your CodeWeaver embedding provider settings, or rerank provider settings. If you're using fastembed-gpu for both, we'll assume you are using the same settings for both if we find one of them.

    Important: You cannot have both `fastembed` and `fastembed-gpu` installed at the same time. They conflict with each other. Make sure to uninstall `fastembed` if you want to use `fastembed-gpu`.
    """

    cuda: NotRequired[bool | None]
    """Whether to use CUDA (if available). If `None`, will auto-detect. We'll generally assume you want to use CUDA if it's available unless you provide a `False` value here."""
    device_ids: NotRequired[list[int] | None]
    """List of GPU device IDs to use. If `None`, we will try to detect available GPUs using `nvidia-smi` if we can find it. We recommend specifying them because our checks aren't perfect."""


# ===========================================================================
# *            Vector Store Provider Settings
# ===========================================================================


class VectorConfig(TypedDict, total=False):
    """Configuration for individual vector types in a collection."""

    dense: VectorParams | None
    sparse: SparseVectorParams | None


class CollectionConfig(TypedDict, total=False):
    """Common collection configuration for vector store providers."""

    collection_name: NotRequired[str | None]
    """Collection name override. Defaults to a unique name based on the project name."""
    dense_vector_name: NotRequired[str]
    """Named vector for dense embeddings. Defaults to 'dense'."""
    sparse_vector_name: NotRequired[str]
    """Named vector for sparse embeddings. Defaults to 'sparse'."""
    vector_config: NotRequired[VectorConfig | None]
    """Configuration for individual vector types in the collection."""


class MemoryConfig(TypedDict, total=False):
    """Configuration for in-memory vector store provider."""

    persist_path: NotRequired[Path]
    f"""Path for JSON persistence file. Defaults to {get_user_config_dir()}/codeweaver/vectors/[your_project_name]_vector_store.json."""
    auto_persist: NotRequired[bool]
    """Automatically save after operations. Defaults to True."""
    persist_interval: NotRequired[PositiveInt | None]
    """Periodic persist interval in seconds. Defaults to 300 (5 minutes). Set to None to disable periodic persistence."""


class QdrantProviderMixin:
    collection: CollectionConfig | None = None
    in_memory_config: MemoryConfig | None = None

    def _telemetry_handler(self, _serialized_self: dict[str, Any], /) -> dict[str, Any]:
        """Custom telemetry handler to avoid logging sensitive collection names or paths."""
        if (collection := _serialized_self.get("collection")) and (
            collection_name := collection.get("collection_name")
        ):
            return {
                "collection": {
                    "collection_name": AnonymityConversion.HASH.filtered(collection_name)
                }
            }
        return {}


class VectorStoreProviderSettings(BaseProviderSettings):
    """Settings for vector store provider selection and configuration."""

    batch_size: Annotated[
        PositiveInt | None,
        Field(description="Batch size for bulk upsert operations. Defaults to 64."),
    ] = 64


# we don't need to add client_options here because it's easy to resolve
class QdrantVectorStoreProviderSettings(QdrantProviderMixin, VectorStoreProviderSettings):
    """Qdrant-specific settings for the Qdrant and Memory providers. Qdrant is the only currently supported vector store, but others may be added in the future."""

    client_options: Annotated[
        QdrantClientOptions | None, Field(description="Client options for the provider's client.")
    ] = None

    @model_validator(mode="after")
    def _ensure_consistent_config(self) -> Self:
        """Ensure consistent config for Qdrant and Memory providers."""
        if not self._client_options:
            self.client_options = QdrantClientOptions(
                location=":memory:" if self.provider == Provider.MEMORY else None,
                host="localhost" if self.provider == Provider.QDRANT else None,
            )
        if self.provider == Provider.MEMORY:
            # we'll resolve the project name later if the user didn't provide a path
            self.in_memory_config = MemoryConfig(auto_persist=True, persist_interval=300) | (
                self.in_memory_config or {}
            )
        # we'll handle collection config later too -- when models are getting instantiated it's much less painful to wait until the dust settles for inter-model dependencies
        return self


class EmbeddingProviderSettings(BaseProviderSettings):
    """Settings for (dense) embedding models. It validates that the model and provider settings are compatible and complete, reconciling environment variables and config file settings as needed."""

    model_settings: EmbeddingModelSettings
    """Settings for the embedding model(s)."""
    client_options: Annotated[
        GeneralEmbeddingClientOptionsType | None,
        Field(description="Client options for the provider's client.", discriminator="tag"),
    ] = None


class AzureEmbeddingProviderSettings(AzureProviderMixin, EmbeddingProviderSettings):
    """Provider settings for Azure embedding models (Cohere or OpenAI)."""

    client_options: Annotated[
        Annotated[CohereClientOptions, Tag(Provider.COHERE.variable)]
        | Annotated[OpenAIClientOptions, Tag(Provider.OPENAI.variable)]
        | None,
        Field(
            description="Client options for the provider's client.",
            discriminator=Discriminator(_discriminate_azure_embedding_client_options),
        ),
    ] = None


class BedrockEmbeddingProviderSettings(BedrockProviderMixin, EmbeddingProviderSettings):
    """Provider settings for Bedrock embedding models."""

    client_options: Annotated[
        Boto3ClientOptions | None, Field(description="Client options for the provider's client.")
    ] = None


class FastembedEmbeddingProviderSettings(FastembedProviderMixin, EmbeddingProviderSettings):
    """Provider settings for Fastembed embedding models."""

    client_options: Annotated[
        FastEmbedClientOptions | None,
        Field(description="Client options for the provider's client."),
    ] = None


class SparseEmbeddingProviderSettings(BaseProviderSettings):
    """Settings for sparse embedding models."""

    model_settings: SparseEmbeddingModelSettings
    """Settings for the sparse embedding model."""
    client_options: Annotated[
        SentenceTransformersClientOptions | None,
        Field(description="Client options for the provider's client."),
    ] = None


class FastembedSparseEmbeddingProviderSettings(
    FastembedProviderMixin, SparseEmbeddingProviderSettings
):
    """Provider settings for Fastembed sparse embedding models."""

    client_options: Annotated[
        FastEmbedClientOptions | None,
        Field(description="Client options for the provider's client."),
    ] = None


class RerankingProviderSettings(BaseProviderSettings):
    """Settings for re-ranking models."""

    model_settings: RerankingModelSettings
    """Settings for the re-ranking model(s)."""
    top_n: PositiveInt | None = None
    client_options: (
        Annotated[
            GeneralRerankingClientOptionsType,
            Field(description="Client options for the provider's client."),
        ]
        | None
    ) = None


class FastembedRerankingProviderSettings(FastembedProviderMixin, RerankingProviderSettings):
    """Provider settings for Fastembed reranking models."""

    client_options: Annotated[
        FastEmbedClientOptions | None,
        Field(description="Client options for the provider's client."),
    ] = None


class BedrockRerankingProviderSettings(BedrockProviderMixin, RerankingProviderSettings):
    """Provider settings for Bedrock reranking models."""

    client_options: Annotated[
        Boto3ClientOptions | None, Field(description="Client options for the provider's client.")
    ] = None


# Agent model settings are imported/defined from `pydantic_ai`

type ModelString = Annotated[
    str,
    Field(
        description="""The model string, as it appears in `pydantic_ai.models.KnownModelName`."""
    ),
]


# we also don't need to add it here because pydantic-ai handles the client
class AgentProviderSettings(BaseProviderSettings):
    """Settings for agent models."""

    model: Required[ModelString]
    model_settings: Required[AgentModelSettings | None]
    """Settings for the agent model(s)."""


# ===========================================================================
# *                    Settings Discriminators
# ===========================================================================

type SpecialEmbeddingProviderSettingsType = Annotated[
    Annotated[AzureEmbeddingProviderSettings, Tag(Provider.AZURE.variable)],
    Annotated(BedrockEmbeddingProviderSettings, Tag(Provider.BEDROCK.variable)),
    Annotated(FastembedEmbeddingProviderSettings, Tag(Provider.FASTEMBED.variable)),
    Field(description="Special embedding provider settings type.", discriminator="tag"),
]


def _discriminate_embedding_provider(v: Any) -> str:
    """Identify the embedding provider settings type for discriminator field."""
    return (
        tag
        if (tag := (v["tag"] if isinstance(v, dict) else v.tag))
        in {Provider.AZURE.variable, Provider.BEDROCK.variable, Provider.FASTEMBED.variable}
        else "none"
    )


type EmbeddingProviderSettingsType = Annotated[
    Annotated[EmbeddingProviderSettings, Tag("none")] | SpecialEmbeddingProviderSettingsType,
    Field(
        description="Embedding provider settings type.",
        discriminator=Discriminator(_discriminate_embedding_provider),
    ),
]


type SparseEmbeddingProviderSettingsType = Annotated[
    Annotated[SparseEmbeddingProviderSettings, Tag(Provider.SENTENCE_TRANSFORMERS.variable)]
    | Annotated[FastembedSparseEmbeddingProviderSettings, Tag(Provider.FASTEMBED.variable)],
    Field(description="Sparse embedding provider settings type.", discriminator="tag"),
]


def _discriminate_reranking_provider(v: Any) -> str:
    """Identify the reranking provider settings type for discriminator field."""
    return (
        tag
        if (tag := (v["tag"] if isinstance(v, dict) else v.tag))
        in {Provider.FASTEMBED.variable, Provider.BEDROCK.variable}
        else "none"
    )


type SpecialRerankingProviderSettingsType = Annotated[
    Annotated[FastembedRerankingProviderSettings, Tag(Provider.FASTEMBED.variable)]
    | Annotated[BedrockRerankingProviderSettings, Tag(Provider.BEDROCK.variable)],
    Field(description="Special reranking provider settings type.", discriminator="tag"),
]

type RerankingProviderSettingsType = Annotated[
    Annotated[RerankingProviderSettings, Tag("none")] | SpecialRerankingProviderSettingsType,
    Field(
        description="Reranking provider settings type.",
        discriminator=Discriminator(_discriminate_reranking_provider),
    ),
]

# ===========================================================================
# *                    More TypedDict versions of Models
# ===========================================================================


class ProviderSettingsDict(TypedDict, total=False):
    """A dictionary representation of provider settings."""

    data: NotRequired[tuple[DataProviderSettings, ...] | None]
    # we currently only support one each of embedding, reranking and vector store providers
    # but we use tuples to allow for future expansion for some less common use cases
    embedding: NotRequired[
        tuple[EmbeddingProviderSettingsType, ...] | EmbeddingProviderSettingsType | None
    ]
    # rerank is probably the priority for multiple providers in the future, because they're vector agnostic, so you could have fallback providers, or use different ones for different tasks
    sparse_embedding: NotRequired[
        tuple[SparseEmbeddingProviderSettingsType, ...] | SparseEmbeddingProviderSettingsType | None
    ]
    reranking: NotRequired[
        tuple[RerankingProviderSettingsType, ...] | RerankingProviderSettingsType | None
    ]

    vector_store: NotRequired[
        tuple[VectorStoreProviderSettings, ...] | VectorStoreProviderSettings | None
    ]
    agent: NotRequired[tuple[AgentProviderSettings, ...] | AgentProviderSettings | None]


type ProviderSettingsView = DictView[ProviderSettingsDict]


def merge_agent_model_settings(
    base: AgentModelSettings | None, override: AgentModelSettings | None
) -> AgentModelSettings | None:
    """A convenience re-export of `merge_model_settings` for agent model settings."""
    return merge_model_settings(base, override)


DefaultDataProviderSettings = (
    DataProviderSettings(provider=Provider.TAVILY, enabled=False, api_key=None, other=None),
    # DuckDuckGo
    DataProviderSettings(provider=Provider.DUCKDUCKGO, enabled=True, api_key=None, other=None),
)


class DeterminedDefaults(NamedTuple):
    """Tuple for determined default embedding settings."""

    provider: Provider
    model: str
    enabled: bool


def _get_default_embedding_settings() -> DeterminedDefaults:
    """Determine the default embedding provider, model, and enabled status based on available libraries."""
    for lib in (
        "voyageai",
        "mistral",
        "google",
        "fastembed_gpu",
        "fastembed",
        "sentence_transformers",
    ):
        if importlib.util.find_spec(lib) is not None:
            # all three of the top defaults are extremely capable
            if lib == "voyageai":
                return DeterminedDefaults(
                    provider=Provider.VOYAGE, model="voyage-code-3", enabled=True
                )
            if lib == "mistral":
                return DeterminedDefaults(
                    provider=Provider.MISTRAL, model="codestral-embed", enabled=True
                )
            if lib == "google":
                return DeterminedDefaults(
                    provider=Provider.GOOGLE, model="gemini-embedding-001", enabled=True
                )
            if lib in {"fastembed_gpu", "fastembed"}:
                return DeterminedDefaults(
                    provider=Provider.FASTEMBED, model="BAAI/bge-small-en-v1.5", enabled=True
                )
            if lib == "sentence_transformers":
                return DeterminedDefaults(
                    provider=Provider.SENTENCE_TRANSFORMERS,
                    # embedding-small-english-r2 is *very lightweight* and quite capable with a good context window (8192 tokens)
                    model="ibm-granite/granite-embedding-small-english-r2",
                    enabled=True,
                )
    logger.warning(
        "No default embedding provider libraries found. Embedding functionality will be disabled unless explicitly set in your config or environment variables."
    )
    return DeterminedDefaults(provider=Provider.NOT_SET, model="NONE", enabled=False)


_embedding_defaults = _get_default_embedding_settings()

DefaultEmbeddingProviderSettings = EmbeddingProviderSettings(
    provider=_embedding_defaults.provider,
    enabled=_embedding_defaults.enabled,
    model_settings=EmbeddingModelSettings(model=_embedding_defaults.model),
)


def _get_default_sparse_embedding_settings() -> DeterminedDefaults:
    """Determine the default sparse embedding provider, model, and enabled status based on available libraries."""
    for lib in ("sentence_transformers", "fastembed_gpu", "fastembed"):
        if importlib.util.find_spec(lib) is not None:
            if lib == "sentence_transformers":
                return DeterminedDefaults(
                    provider=Provider.SENTENCE_TRANSFORMERS,
                    model="opensearch/opensearch-neural-sparse-encoding-doc-v3-gte",
                    enabled=True,
                )
            if lib in {"fastembed_gpu", "fastembed"}:
                return DeterminedDefaults(
                    provider=Provider.FASTEMBED, model="prithivida/Splade_PP_en_v1", enabled=True
                )
    # qdrant_client has built-in BM25 support
    # if FastEmbed isn't available, we will use that automatically
    return DeterminedDefaults(provider=Provider.FASTEMBED, model="qdrant/bm25", enabled=True)


_sparse_embedding_defaults = _get_default_sparse_embedding_settings()

DefaultSparseEmbeddingProviderSettings = SparseEmbeddingProviderSettings(
    provider=_sparse_embedding_defaults.provider,
    enabled=_sparse_embedding_defaults.enabled,
    model_settings=SparseEmbeddingModelSettings(model=_sparse_embedding_defaults.model),
)


def _get_default_reranking_settings() -> DeterminedDefaults:
    """Determine the default reranking provider, model, and enabled status based on available libraries."""
    for lib in ("voyageai", "fastembed_gpu", "fastembed", "sentence_transformers"):
        if importlib.util.find_spec(lib) is not None:
            if lib == "voyageai":
                return DeterminedDefaults(
                    provider=Provider.VOYAGE, model="voyage:rerank-2.5", enabled=True
                )
            if lib in {"fastembed_gpu", "fastembed"}:
                return DeterminedDefaults(
                    provider=Provider.FASTEMBED,
                    model="fastembed:jinaai/jina-reranking-v2-base-multilingual",
                    enabled=True,
                )
            if lib == "sentence_transformers":
                return DeterminedDefaults(
                    provider=Provider.SENTENCE_TRANSFORMERS,
                    # on the heavier side for what we aim for as a default but very capable
                    model="sentence-transformers:BAAI/bge-reranking-v2-m3",
                    enabled=True,
                )
    logger.warning(
        "No default reranking provider libraries found. Reranking functionality will be disabled unless explicitly set in your config or environment variables."
    )
    return DeterminedDefaults(provider=Provider.NOT_SET, model="NONE", enabled=False)


_reranking_defaults = _get_default_reranking_settings()

DefaultRerankingProviderSettings = RerankingProviderSettings(
    provider=_reranking_defaults.provider,
    enabled=_reranking_defaults.enabled,
    model_settings=RerankingModelSettings(model=_reranking_defaults.model),
)

HAS_ANTHROPIC = (
    importlib.util.find_spec("anthropic") or importlib.util.find_spec("code_agent_sdk")
) is not None
DefaultAgentProviderSettings = AgentProviderSettings(
    provider=Provider.ANTHROPIC,
    enabled=HAS_ANTHROPIC,
    model="claude-haiku-4.5-latest",
    model_settings=AgentModelSettings(),
)


DefaultVectorStoreProviderSettings = VectorStoreProviderSettings(
    provider=Provider.QDRANT, enabled=True, provider_settings=QdrantConfig()
)

type ProviderField = Literal[
    "data", "embedding", "sparse_embedding", "reranking", "vector_store", "agent"
]


class ProviderNameMap(TypedDict):
    """Configured providers by kind."""

    data: tuple[Provider, ...] | None
    embedding: Provider | tuple[Provider, ...] | None
    sparse_embedding: Provider | tuple[Provider, ...] | None
    reranking: Provider | tuple[Provider, ...] | None
    vector_store: Provider | tuple[Provider, ...] | None
    agent: Provider | tuple[Provider, ...] | None


class ProviderSettings(BasedModel):
    """Settings for provider configuration."""

    data: Annotated[
        tuple[DataProviderSettings, ...] | DataProviderSettings | Unset,
        Field(description="""Data provider configuration"""),
    ] = DefaultDataProviderSettings

    embedding: Annotated[
        tuple[EmbeddingProviderSettings, ...] | EmbeddingProviderSettings | Unset,
        Field(
            description="""Embedding provider configuration.

            We will only use the first provider you configure here. We may add support for multiple embedding providers in the future.
            """
        ),
    ] = DefaultEmbeddingProviderSettings

    sparse_embedding: Annotated[
        tuple[SparseEmbeddingProviderSettings, ...] | SparseEmbeddingProviderSettings | Unset,
        Field(
            description="""Sparse embedding provider configuration.

            We will only use the first provider you configure here. We may add support for multiple sparse embedding providers in the future."""
        ),
    ] = DefaultSparseEmbeddingProviderSettings

    reranking: Annotated[
        tuple[RerankingProviderSettings, ...] | RerankingProviderSettings | Unset,
        Field(
            description="""Reranking provider configuration.

            We will only use the first provider you configure here. We may add support for multiple reranking providers in the future."""
        ),
    ] = DefaultRerankingProviderSettings

    vector_store: Annotated[
        tuple[VectorStoreProviderSettings, ...] | VectorStoreProviderSettings | Unset,
        Field(
            description="""Vector store provider configuration (Qdrant or in-memory), defaults to a local Qdrant instance."""
        ),
    ] = DefaultVectorStoreProviderSettings

    agent: Annotated[
        tuple[AgentProviderSettings, ...] | AgentProviderSettings | Unset,
        Field(description="""Agent provider configuration"""),
    ] = DefaultAgentProviderSettings

    def _reconcile_env_vars(self) -> ProviderSettings:
        """Reconcile provider settings with environment variables, if any."""
        from codeweaver.config.profiles import get_skeleton_provider_settings

        serialized_self = self.model_dump()
        skeleton = get_skeleton_provider_settings()
        for key, value in serialized_self.items():
            if skeleton_value := skeleton.get(key):
                if value is Unset:
                    serialized_self[key] = (skeleton_value,)
                else:
                    value = value[0] if isinstance(value, tuple) else value
                    new_value = value.copy() | skeleton_value
                    serialized_self[key] = (new_value,)
        return self.model_copy(update=serialized_self)

    @model_validator(mode="after")
    def validate_and_normalize_providers(self) -> ProviderSettings:
        """Validate and normalize provider settings after initialization."""
        for key in "vector_store", "embedding", "sparse_embedding", "reranking", "agent":
            value = getattr(self, key)
            if value is not Unset and not isinstance(value, tuple):
                setattr(self, key, (value,))
        return self._reconcile_env_vars()

    def _telemetry_keys(self) -> None:
        return None

    def has_setting(self, setting_name: ProviderField | LiteralKinds) -> bool:
        """Check if a specific provider setting is configured.

        Args:
            setting_name: The name of the setting or ProviderKind to check.
        """
        from codeweaver.core.types.provider import ProviderKind

        setting = (
            setting_name
            if setting_name
            in {"data", "embedding", "sparse_embedding", "reranking", "vector_store", "agent"}
            else cast(ProviderKind, setting_name).variable
        )
        return getattr(self, setting) is not Unset  # type: ignore

    @computed_field
    @property
    def providers(self) -> frozenset[Provider]:
        """Get a set of configured providers."""
        return frozenset({
            p
            for prov in self.provider_name_map.values()
            if prov
            for p in (prov if isinstance(prov, tuple) else (prov,))
        })  # type: ignore

    @property
    def _field_names(self) -> tuple[ProviderField, ...]:
        """Get the field names for provider settings."""
        return ("data", "embedding", "sparse_embedding", "reranking", "vector_store", "agent")

    @property
    def provider_configs(self) -> dict[ProviderField, tuple[BaseProviderSettings, ...] | None]:
        """Get a summary of configured provider settings by kind."""
        configs: dict[ProviderField, tuple[BaseProviderSettings, ...] | None] = {}
        for field in self._field_names:
            setting = self.settings_for_kind(field)
            if setting is None or setting is Unset:
                continue
            # Normalize to tuple form
            configs[field] = setting if isinstance(setting, tuple) else (setting,)  # ty:ignore[invalid-assignment]
        return configs or None  # type: ignore[return-value]

    @property
    def provider_name_map(self) -> ProviderNameMap:
        """Get a summary of configured providers by kind."""
        provider_data: dict[ProviderField, Provider | tuple[Provider, ...] | None] = {
            field_name: (
                tuple(s.provider for s in setting if setting and is_typeddict(s))  # type: ignore
                if isinstance(setting, tuple)
                else (setting["provider"] if setting else None)
            )
            for field_name, setting in self.provider_configs.items()
        }

        return ProviderNameMap(**provider_data)  # type: ignore

    def get_provider_settings(
        self, provider: Provider
    ) -> BaseProviderSettings | tuple[BaseProviderSettings, ...] | None:
        """Get the settings for a specific provider."""
        if provider == Provider.NOT_SET:
            return None

        # Collect all fields containing this provider in a single pass
        matching_fields = []
        for field_name, config_value in self.provider_configs.items():
            if isinstance(config_value, tuple):
                if any(cfg.get("provider") == provider for cfg in config_value):
                    matching_fields.append(field_name)
            elif isinstance(config_value, dict) and config_value.get("provider") == provider:
                matching_fields.append(field_name)

        if not matching_fields:
            return None

        # Retrieve and flatten settings for matching fields
        all_settings: list[BaseProviderSettings] = []
        for field in matching_fields:
            if setting := self.settings_for_kind(field):
                if isinstance(setting, tuple):
                    all_settings.extend(setting)  # ty:ignore[invalid-argument-type]
                else:
                    all_settings.append(setting)

        return (
            all_settings[0]
            if len(all_settings) == 1
            else tuple(all_settings)
            if all_settings
            else None
        )

    def has_auth_configured(self, provider: Provider) -> bool:
        """Check if API key or TLS certs are set for the provider through settings or environment."""
        if not (settings := self.get_provider_settings(provider)):
            return False
        settings = settings if isinstance(settings, tuple) else (settings,)
        return next(
            (True for setting in settings if isinstance(setting.get("api_key"), SecretStr)),
            provider.has_env_auth,
        )

    def settings_for_kind(
        self, kind: ProviderField | LiteralKinds
    ) -> BaseProviderSettings | tuple[BaseProviderSettings, ...] | None:
        """Get the settings for a specific provider kind.

        Args:
            kind: The kind of provider or ProviderKind to get settings for.
        """
        from codeweaver.core.types.provider import ProviderKind

        setting_field = (
            kind
            if kind
            in {"data", "embedding", "sparse_embedding", "reranking", "vector_store", "agent"}
            else cast(ProviderKind, kind).variable
        )
        setting = getattr(self, setting_field, None)  # type: ignore
        return None if setting is Unset else setting  # type: ignore


AllDefaultProviderSettings = ProviderSettingsDict(
    data=DefaultDataProviderSettings,
    embedding=DefaultEmbeddingProviderSettings,
    sparse_embedding=DefaultSparseEmbeddingProviderSettings,
    reranking=DefaultRerankingProviderSettings,
    agent=DefaultAgentProviderSettings,
)


__all__ = (
    "AgentProviderSettings",
    "AllDefaultProviderSettings",
    "ConnectionConfiguration",
    "ConnectionRateLimitConfig",
    "DataProviderSettings",
    "EmbeddingModelSettings",
    "EmbeddingProviderSettings",
    "MemoryConfig",
    "ModelString",
    "ProviderSettings",
    "ProviderSettingsDict",
    "ProviderSettingsDict",
    "ProviderSettingsView",
    "RerankingModelSettings",
    "RerankingProviderSettings",
    "SparseEmbeddingModelSettings",
)
