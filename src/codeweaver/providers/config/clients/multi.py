# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Client options for providers that can be used with multiple categories (e.g. embedding, reranking)."""

from __future__ import annotations

import contextlib

from collections.abc import Awaitable, Callable, Hashable, Iterable, Mapping, Sequence
from concurrent.futures import ThreadPoolExecutor
from typing import Annotated, Any, ClassVar, Literal, Self, TypedDict, cast

import httpx

from pydantic import (
    AnyUrl,
    Discriminator,
    Field,
    PositiveFloat,
    PositiveInt,
    SecretStr,
    Tag,
    model_validator,
)

from codeweaver.core.constants import DEFAULT_EMBEDDING_TIMEOUT, ONNX_CUDA_PROVIDER
from codeweaver.core.types import (
    AnonymityConversion,
    FilteredKey,
    FilteredKeyT,
    LiteralProviderType,
    Provider,
)
from codeweaver.core.utils import TypeIs, deep_merge_dicts, has_package
from codeweaver.providers.config.clients.base import ClientOptions
from codeweaver.providers.config.clients.utils import (
    AzureOptions,
    discriminate_embedding_clients,
    try_for_azure_endpoint,
    try_for_heroku_endpoint,
)


if has_package("google"):
    from google.auth.credentials import Credentials as GoogleCredentials
else:
    GoogleCredentials = Any

if has_package("fastembed") or has_package("fastembed_gpu"):
    try:
        from fastembed.common.types import OnnxProvider
    except ImportError:
        OnnxProvider = Any  # type: ignore[assignment, misc]
else:
    OnnxProvider = Any  # type: ignore[assignment, misc]

if has_package("torch"):
    try:
        from torch.nn import Module
    except ImportError:
        Module = Any  # type: ignore[assignment, misc]
else:
    Module = Any  # type: ignore[assignment, misc]
if has_package("sentence_transformers"):
    # SentenceTransformerModelCardData contains these forward references:
    # - eval_results_dict: dict[SentenceEvaluator, dict[str, Any]] | None
    # - model: SentenceTransformer | None
    # So if the configured settings are SentenceTransformersClientOptions
    # Then we need to have these in the namespace for pydantic to resolve
    from sentence_transformers import SentenceTransformer as SentenceTransformer
    from sentence_transformers.evaluation import SentenceEvaluator as SentenceEvaluator
    from sentence_transformers.model_card import (
        SentenceTransformerModelCardData as SentenceTransformerModelCardData,
    )


class CohereClientOptions(ClientOptions):
    """Client options for Cohere (rerank and embeddings)."""

    _core_provider: ClassVar[Literal[Provider.COHERE]] = Provider.COHERE
    _providers: ClassVar[tuple[Provider, ...]] = (Provider.COHERE, Provider.AZURE, Provider.HEROKU)

    tag: Literal["cohere"] = "cohere"
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

    def computed_base_url(self, provider: LiteralProviderType) -> str | None:
        """Return the default base URL for the Cohere client based on the provider."""
        provider = provider if isinstance(provider, Provider) else Provider.from_string(provider)  # ty:ignore[invalid-assignment]
        if base_url := {
            Provider.COHERE: "https://api.cohere.com",
            Provider.AZURE: try_for_azure_endpoint(
                AzureOptions(api_key=self.api_key, endpoint=str(self.base_url)), cohere=True
            ),
            Provider.HEROKU: try_for_heroku_endpoint(self.model_dump(), cohere=True),
        }.get(provider):
            if not self.base_url:
                self.base_url = AnyUrl(base_url)
            return base_url
        return None


class OpenAIClientOptions(ClientOptions):
    """Client options for OpenAI-based embedding providers."""

    _core_provider: ClassVar[Literal[Provider.OPENAI]] = Provider.OPENAI
    _providers: ClassVar[tuple[Provider, ...]] = tuple(
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

    def computed_base_url(self, provider: LiteralProviderType) -> str | None:
        """Return the default base URL for the OpenAI client based on the provider."""
        if self.base_url:
            return str(self.base_url)
        provider = provider if isinstance(provider, Provider) else Provider.from_string(provider)  # ty:ignore[invalid-assignment]
        return {
            Provider.OPENAI: "https://api.openai.com/v1",
            Provider.AZURE: try_for_azure_endpoint(
                AzureOptions(api_key=self.api_key, endpoint=str(self.base_url))
            ),
            Provider.HEROKU: try_for_heroku_endpoint(self.model_dump()),
            Provider.GROQ: "https://api.groq.com/openai/v1",
            Provider.MORPH: "https://api.morphllm.com/v1",
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

    _core_provider: ClassVar[Literal[Provider.BEDROCK]] = Provider.BEDROCK
    _providers: ClassVar[tuple[Provider, ...]] = (Provider.BEDROCK,)

    tag: Literal["bedrock"] = "bedrock"
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

    _core_provider: ClassVar[Literal[Provider.GOOGLE]] = Provider.GOOGLE
    _providers: ClassVar[tuple[Provider, ...]] = (Provider.GOOGLE,)

    api_key: SecretStr | None = None
    vertex_ai: bool = False
    credentials: GoogleCredentials | None = None
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

    _core_provider: ClassVar[Literal[Provider.FASTEMBED]] = Provider.FASTEMBED
    _providers: ClassVar[tuple[Provider, ...]] = (Provider.FASTEMBED,)

    tag: Literal["fastembed"] = "fastembed"
    model_name: str
    cache_dir: str | None = None
    threads: int | None = None
    onnx_providers: Annotated[
        Sequence[OnnxProvider] | None,
        Field(alias="providers", serialization_alias="providers"),
    ] = None
    cuda: bool | None = None
    device_ids: list[int] | None = None
    lazy_load: bool = True

    @model_validator(mode="after")
    def _resolve_device_settings(self) -> Self:
        """Resolve device settings for FastEmbed client options."""
        from codeweaver.core import effective_cpu_count

        cpu_count = effective_cpu_count()
        updates: dict[str, Any] = {"threads": self.threads or cpu_count}
        if self.cuda is False:
            updates["device_ids"] = []
            return self.model_copy(update=updates)
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
        updates["cuda"] = cuda
        updates["device_ids"] = device_ids
        if cuda and (not self.onnx_providers or ONNX_CUDA_PROVIDER not in self.onnx_providers):
            updates["onnx_providers"] = [ONNX_CUDA_PROVIDER, *(self.onnx_providers or [])]
        return self.model_copy(update=updates)

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        return {FilteredKey("cache_dir"): AnonymityConversion.HASH}


class SentenceTransformersModelOptions(TypedDict, total=False):
    """Options for SentenceTransformers models."""

    dtype: Literal["float", "float16", "bfloat16", "auto"] | None
    attn_implementation: Literal["flash_attention_2", "spda", "eager"] | None
    provider: OnnxProvider | None
    """Onnx Provider if Onnx backend used."""
    file_name: str | None
    """Specific file name to load for onnx or openvino models."""
    export: bool | None
    """Whether to export the model to onnx/openvino format."""


def _is_str_dict(d: Any) -> TypeIs[dict[str, Any]]:
    """Check if the given object is a dictionary with string keys."""
    return isinstance(d, dict) and all(isinstance(k, str) for k in d if k)


def _is_hashable_dict(d: Any) -> TypeIs[dict[Hashable, Any]]:
    """Check if the given object is a dictionary with hashable keys."""
    return isinstance(d, dict) and all(isinstance(k, Hashable) for k in d if k)


class SentenceTransformersClientOptions(ClientOptions):
    """Client options for SentenceTransformers-based embedding providers."""

    _core_provider: ClassVar[Literal[Provider.SENTENCE_TRANSFORMERS]] = (
        Provider.SENTENCE_TRANSFORMERS
    )
    _providers: ClassVar[tuple[Provider, ...]] = (Provider.SENTENCE_TRANSFORMERS,)

    tag: Literal["sentence_transformers"] = "sentence_transformers"
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
    """Auth token for private/non-public models."""
    truncate_dim: int | None = None
    model_kwargs: SentenceTransformersModelOptions | None = None
    tokenizer_kwargs: dict[str, Any] | None = None
    config_kwargs: dict[str, Any] | None = None
    model_card_data: SentenceTransformerModelCardData | None = None
    backend: Literal["torch", "onnx", "openvino"] = "torch"

    def __init__(self, **data: Any) -> None:
        """Initialize the SentenceTransformers client options."""
        model_name = data.get("model_name_or_path") or ""
        data = data or {}
        default_kwargs = self.default_kwargs_for_model(model=model_name) or {}
        if not _is_hashable_dict(default_kwargs):
            raise TypeError(
                "Expected data and default_kwargs to be dicts with appropriate key types."
            )
        merged_data = deep_merge_dicts(default_kwargs, cast(dict[Hashable, Any], data))
        if not _is_str_dict(merged_data):
            raise TypeError("Expected merged data to be a dict with string keys.")
        super().__init__(**merged_data)

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        return {
            FilteredKey("cache_folder"): AnonymityConversion.HASH,
            FilteredKey("model_name_or_path"): AnonymityConversion.HASH,
        }

    def _is_dense_model(self) -> bool:
        """Determine if the model is a dense model based on its name."""
        return (
            False
            if self.capabilities  # ty:ignore[unresolved-attribute]
            and "sparse" in self.capabilities.__class__.__name__.lower()  # ty:ignore[unresolved-attribute]
            else not self.model_name_or_path
            or not any(
                key
                for key in ("sparse", "splade", "bm-25", "bm25", "attentions")
                if key in str(self.model_name_or_path.lower())
            )
        )

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
                    "dtype": "float16"
                    if "dtype" not in (self.model_kwargs or {})
                    else (self.model_kwargs or {}).get("dtype")
                },
            )
        if has_package("flash_attention_2"):
            object.__setattr__(
                self,
                "model_kwargs",
                (self.model_kwargs or {})
                | {
                    "attn_implementation": "flash_attention_2"
                    if "attn_implementation" not in (self.model_kwargs or {})
                    else (self.model_kwargs or {}).get("attn_implementation")
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
        float16 = {"model_kwargs": {"dtype": "float16"}}
        if "alibaba" in model.lower() and "gte-reranker-modernbert-base" in model.lower():
            extra = {"tokenizer_kwargs": {"padding": True}}
        if "qwen3" in model.lower():
            extra = {
                "instruction": "Use provided search results of codebase data to retrieve relevant Documents that answer the Query.",
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


class HuggingFaceClientOptions(ClientOptions):
    """Client options for HuggingFace Inference API-based embedding providers."""

    _core_provider: ClassVar[Literal[Provider.HUGGINGFACE_INFERENCE]] = (
        Provider.HUGGINGFACE_INFERENCE
    )
    _providers: ClassVar[tuple[Provider, ...]] = (Provider.HUGGINGFACE_INFERENCE,)

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

    _core_provider: ClassVar[Literal[Provider.MISTRAL]] = Provider.MISTRAL
    _providers: ClassVar[tuple[Provider, ...]] = (Provider.MISTRAL,)

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

    _core_provider: ClassVar[Literal[Provider.VOYAGE]] = Provider.VOYAGE
    _providers: ClassVar[tuple[Provider, ...]] = (Provider.VOYAGE,)

    tag: Literal["voyage"] = "voyage"
    api_key: SecretStr | None = None
    max_retries: PositiveInt = 0  # we handle retries ourself
    timeout: PositiveFloat | None = DEFAULT_EMBEDDING_TIMEOUT

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        return {FilteredKey("api_key"): AnonymityConversion.BOOLEAN}


# Rebuild Pydantic models to resolve forward references after all imports complete
# This is necessary because SentenceTransformerModelCardData contains SentenceEvaluator references
if (
    has_package("sentence_transformers") is not None
    and not SentenceTransformersClientOptions.__pydantic_complete__
):
    # we can rebuild lazily later if this fails
    with contextlib.suppress(Exception):
        SentenceTransformersClientOptions.model_rebuild()


# ===========================================================================
# *                    Client Discriminators
# ===========================================================================

type GeneralRerankingClientOptionsType = Annotated[
    Annotated[BedrockClientOptions, Tag(Provider.BEDROCK.variable)]
    | Annotated[CohereClientOptions, Tag(Provider.COHERE.variable)]
    | Annotated[FastEmbedClientOptions, Tag(Provider.FASTEMBED.variable)]
    | Annotated[SentenceTransformersClientOptions, Tag(Provider.SENTENCE_TRANSFORMERS.variable)]
    | Annotated[VoyageClientOptions, Tag(Provider.VOYAGE.variable)],
    Field(description="Reranking client options type.", discriminator="tag"),
]


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
    Annotated[BedrockClientOptions, Tag(Provider.BEDROCK.variable)]
    | Annotated[CohereClientOptions, Tag(Provider.COHERE.variable)]
    | Annotated[FastEmbedClientOptions, Tag(Provider.FASTEMBED.variable)]
    | Annotated[GoogleClientOptions, Tag(Provider.GOOGLE.variable)]
    | Annotated[HuggingFaceClientOptions, Tag(Provider.HUGGINGFACE_INFERENCE.variable)]
    | Annotated[MistralClientOptions, Tag(Provider.MISTRAL.variable)]
    | Annotated[OpenAIClientOptions, Tag(Provider.OPENAI.variable)]
    | Annotated[SentenceTransformersClientOptions, Tag(Provider.SENTENCE_TRANSFORMERS.variable)]
    | Annotated[VoyageClientOptions, Tag(Provider.VOYAGE.variable)],
    Field(
        description="Embedding client options type.",
        discriminator=Discriminator(discriminate_embedding_clients),
    ),
]


__all__ = (
    "BedrockClientOptions",
    "CohereClientOptions",
    "FastEmbedClientOptions",
    "GeneralEmbeddingClientOptionsType",
    "GeneralRerankingClientOptionsType",
    "GoogleClientOptions",
    "HuggingFaceClientOptions",
    "MistralClientOptions",
    "OpenAIClientOptions",
    "SentenceTransformersClientOptions",
    "SentenceTransformersModelOptions",
    "VoyageClientOptions",
    "discriminate_azure_embedding_client_options",
)
