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
import os

from collections.abc import Awaitable, Callable, Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import Annotated, Any, Literal, NotRequired, Required, Self, TypedDict

import httpx

from pydantic import (
    AnyUrl,
    ConfigDict,
    Discriminator,
    Field,
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
    LiteralProviderType,
    Provider,
    ProviderLiteral,
)
from codeweaver.providers.config.types import HttpxClientParams


logger = logging.getLogger(__name__)


# Note: Previously we had a _ensure_qdrant_model_rebuilt() function here to handle
# httpx forward references, but we've simplified QdrantClientOptions.advanced_http_options to use
# dict[str, Any] instead of HttpxClientParams to avoid the forward reference issue.
# The actual type validation is deferred to the qdrant_client library.


# ===========================================================================
# *                           Client Options
# ===========================================================================


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
        """Initialize the ClientOptions."""
        from codeweaver.core.di import get_container

        try:
            container = get_container()
            container.register(type(self), lambda: self)
        except Exception as e:
            # Log if DI not available (monorepo compatibility)
            logger.debug(
                "Dependency injection container not available, skipping registration of ClientOptions: %s",
                e,
            )
        # Remove backup-related parameters if present (for backward compatibility)
        data.pop("_as_backup", None)

        object.__setattr__(self, "_core_provider", data.pop("_core_provider", Provider.NOT_SET))
        object.__setattr__(self, "_providers", data.pop("_providers", ()))
        super().__init__(**data)

    @model_validator(mode="before")
    @classmethod
    def _handle_env_vars(cls, values: dict[str, Any]) -> dict[str, Any]:
        """Handle environment variables before initialization."""
        env_vars = cls.assemble_env_vars()
        if values and not isinstance(values, dict):
            values = values.model_dump()
        return env_vars | values

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

    @classmethod
    def _client_env_vars(cls) -> dict[str, tuple[str, ...] | dict[str, Any]]:
        """Return a dictionary of environment variables for the client options, mapping client variable names to the environment variable name."""
        # Access _core_provider from class __dict__ to avoid pydantic descriptor issues
        core_provider = cls.__dict__.get("_core_provider", Provider.NOT_SET)
        if core_provider == Provider.NOT_SET:
            # Fallback to parent class if not set in current class
            for base in cls.__mro__[1:]:
                if "_core_provider" in base.__dict__:
                    core_provider = base.__dict__["_core_provider"]
                    break
        env_vars = core_provider.all_envs_for_client(core_provider.variable)  # ty:ignore[invalid-argument-type]
        mapped_vars = {}
        fields = tuple(cls.model_fields)
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

    @classmethod
    def _handle_env_tuple(cls, var_name: str, env_var_names: tuple[str, ...]) -> dict[str, Any]:
        if var_name not in cls.model_fields:
            return {}
        if value := next(
            (os.getenv(env_var) for env_var in env_var_names if os.getenv(env_var)), None
        ):
            return {var_name: value}
        return {}

    @classmethod
    def _handle_env_dict(cls, var_name: str, env_var_names: dict[str, Any]) -> dict[str, Any]:
        if var_name not in cls.model_fields:
            return {}
        for client_var, env_var in env_var_names.items():
            if (value := os.getenv(env_var)) and client_var == var_name:
                return {var_name: value}
        return {}

    @classmethod
    def assemble_env_vars(cls) -> dict[str, Any]:
        """Apply environment variables to the client options."""
        env_vars = cls._client_env_vars()
        response_map: dict[str, Any] = {}
        for var_name, env_var_names in env_vars.items():
            if var_name not in cls.model_fields:
                continue
            if isinstance(env_var_names, tuple):
                response_map |= cls._handle_env_tuple(var_name, env_var_names)
                continue
            # it's a dictionary
            response_map |= cls._handle_env_dict(var_name, env_var_names)
        return response_map if response_map and response_map.values() else {}


class CohereClientOptions(ClientOptions):
    """Client options for Cohere (rerank and embeddings)."""

    _core_provider: Provider = Provider.COHERE
    _providers: tuple[Provider, ...] = (Provider.COHERE, Provider.AZURE, Provider.HEROKU)

    api_key: (
        Annotated[SecretStr | Callable[[], str], Field(description="Cohere API key.")] | None
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

    def is_local_on_disk(self) -> bool:
        """Check if the Qdrant client is configured for local on-disk storage."""
        return bool(
            self.path is not None
            or (self.url and self._is_local_url(self.url))
            or (self.host and self._is_local_url(self.host))
        )

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

        # Connection parameters
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

        # Authentication
        if self.api_key is not None:
            params["api_key"] = self.api_key
        if self.auth_token_provider is not None:
            params["auth_token_provider"] = self.auth_token_provider

        # Preferences
        params["prefer_grpc"] = self.prefer_grpc
        if self.prefix is not None:
            params["prefix"] = self.prefix
        if self.timeout is not None:
            params["timeout"] = self.timeout

        # Advanced options
        params["force_disable_check_same_thread"] = self.force_disable_check_same_thread
        if self.grpc_options is not None:
            params["grpc_options"] = self.grpc_options
        params["cloud_inference"] = self.cloud_inference
        if self.local_inference_batch_size is not None:
            params["local_inference_batch_size"] = self.local_inference_batch_size
        params["check_compatibility"] = self.check_compatibility
        if self.pool_size is not None:
            params["pool_size"] = self.pool_size

        # Advanced HTTP options (power users)
        if self.advanced_http_options is not None:
            # These are passed through to httpx.AsyncClient
            params["kwargs"] = self.advanced_http_options

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
            self.advanced_http_options = HttpxClientParams(
                **((self.advanced_http_options or {}) | {"http2": True, "http1": False})
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

    def __init__(self, **data: Any) -> None:
        """Initialize the OpenAI client options."""
        object.__setattr__(
            self, "_strict_response_validation", data.pop("_strict_response_validation", False)
        )
        super().__init__(**data)

    def default_base_url(self, provider: LiteralProviderType) -> str | None:
        """Return the default base URL for the OpenAI client based on the provider."""
        provider = provider if isinstance(provider, Provider) else Provider.from_string(provider)  # ty:ignore[invalid-assignment]
        return {
            Provider.OPENAI: "https://api.openai.com/v1",
            Provider.AZURE: None,
            Provider.GROQ: "https://api.groq.com/openai/v1",
            Provider.OLLAMA: "http://localhost:11434/v1",
            Provider.TOGETHER: "https://api.together.xyz/v1",
        }.get(provider)

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
    cuda: bool | None = None
    device_ids: list[int] | None = None
    lazy_load: bool = True

    @model_validator(mode="after")
    def _resolve_device_settings(self) -> Self:
        """Resolve device settings for FastEmbed client options."""
        from codeweaver.core import effective_cpu_count

        cpu_count = effective_cpu_count()
        object.__setattr__(self, "threads", self.threads or cpu_count)
        if self.cuda is False:
            object.__setattr__(self, "device_ids", [])
            return self
        from codeweaver.providers.optimize import decide_fastembed_runtime

        decision = decide_fastembed_runtime(
            explicit_cuda=self.cuda, explicit_device_ids=self.device_ids
        )
        if isinstance(decision, tuple) and len(decision) == 2:
            cuda = bool(decision[0])
            device_ids = decision[1]
        elif decision == "gpu":
            cuda = True
            device_ids = [0]
        else:
            cuda = False
            device_ids = []
        object.__setattr__(self, "cuda", cuda)
        object.__setattr__(self, "device_ids", device_ids)
        if cuda and (not self.providers or "CUDAExecutionProvider" not in self.providers):
            object.__setattr__(
                self, "providers", ["CUDAExecutionProvider", *(self.providers or [])]
            )
        return self

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
    trust_remote_code: bool = True
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

    def __model_post_init__(self) -> None:
        """Post-initialization adjustments for specific models."""
        if (
            model_name_or_path := self.model_name_or_path
        ) and "qwen3" in model_name_or_path.lower():
            object.__setattr__(
                self,
                "model_kwargs",
                (self.model_kwargs or {})
                | {
                    "torch_dtype": "float16"
                    if "torch_dtype" not in (self.model_kwargs or {})
                    else self.model_kwargs.get("torch_dtype")
                },
            )
            if importlib.util.find_spec("flash_attention_2") is not None:
                object.__setattr__(
                    self,
                    "model_kwargs",
                    (self.model_kwargs or {})
                    | {
                        "attention_implementation": "flash_attention_2"
                        if "attention_implementation" not in (self.model_kwargs or {})
                        else self.model_kwargs.get("attention_implementation")
                    },
                )

    def default_kwargs_for_model(
        self, *, model: str | None = None, query: bool = False
    ) -> dict[str, Any]:
        """Get default client arguments for a specific model."""
        model = model or self.model_name_or_path
        if not model:
            return {}
        extra: dict[str, Any] = {}
        float16 = {"model_kwargs": {"torch_dtype": "torch.float16"}}
        if "qwen3" in model.lower():
            extra = {
                "instruction": "Use provided search results to of codebase data to retrieve relevant Documents that answer the Query.",
                "tokenizer_kwargs": {"padding_side": "left"},
                **float16,
            }
        if "bge" in model.lower() and "m3" not in model.lower() and query:
            extra = {
                "prompt_name": "query",
                "prompts": {
                    "query": {"text": "Represent this sentence for searching relevant passages:"}
                },
                **float16,
            }
        if "snowflake" in model.lower() and "v2.0" in model.lower():
            extra = {"prompt_name": "query"}  # only for query embeddings
        if "intfloat" in model.lower() and "instruct" not in model.lower():
            extra = {"prompt_name": "query"} if query else {"prompt_name": "document"}
        if "jina" in model.lower() and "v2" not in model.lower():
            if "v4" in model.lower():
                extra = (
                    {"prompt_name": "query", "task": "code"}
                    if query
                    else {"task": "code", "prompt_name": "passage"}
                )
            else:
                extra = (
                    {"task": "retrieval.query", "prompt_name": "query"}
                    if query
                    else {"task": "retrieval.passage"}
                )
        if "nomic" in model.lower():
            extra = {"tokenizer_kwargs": {"padding": True}}
        return {
            "model_name_or_path": model,
            "normalize_embeddings": True,
            "trust_remote_code": True,
            **extra,
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
