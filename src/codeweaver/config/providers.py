# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""TypedDict classes for provider settings.

Provides configuration settings for all supported providers, including embedding models, reranking models, and agent models.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated, Any, NotRequired, Required, TypedDict

from pydantic import Field, PositiveInt, SecretStr
from pydantic_ai.settings import ModelSettings as AgentModelSettings

from codeweaver.config.types import BaseProviderSettings
from codeweaver.core.types import DictView


if TYPE_CHECKING:
    pass


# ===========================================================================
# *            Provider Settings classes
# ===========================================================================


class DataProviderSettings(BaseProviderSettings):
    """Settings for data providers."""


# TODO: Standardize field names
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


class RerankingModelSettings(TypedDict, total=False):
    """Rerank model settings."""

    model: Required[str]
    custom_prompt: NotRequired[str | None]
    rerank_options: NotRequired[dict[str, Any] | None]
    """Keyword arguments to pass to the *provider* **client's** (like `voyageai.async_client.AsyncClient`) `rerank` method."""
    client_options: NotRequired[dict[str, Any] | None]
    """Keyword arguments to pass to the *provider* **client's** (like `voyageai.async_client.AsyncClient`) constructor."""
    model_options: NotRequired[dict[str, Any] | None]
    """Keyword arguments to pass to the model's constructor."""


class AWSProviderSettings(TypedDict, total=False):
    """Settings for AWS provider.

    You need to provide these settings if you are using Bedrock, and you need to provide them for each Bedrock model you use. It might be repetitive, but a lot of people have different credentials for different models/services.
    """

    region_name: Required[str]
    model_arn: Required[str]
    aws_access_key_id: NotRequired[SecretStr | None]
    """Optional AWS access key ID. If not provided, we'll assume you have you have your AWS credentials configured in another way, such as environment variables, AWS config files, or IAM roles."""
    aws_secret_access_key: NotRequired[SecretStr | None]
    """Optional AWS secret access key. If not provided, we'll assume you have you have your AWS credentials configured in another way, such as environment variables, AWS config files, or IAM roles."""
    aws_session_token: NotRequired[SecretStr | None]
    """Optional AWS session token. If not provided, we'll assume you have you have your AWS credentials configured in another way, such as environment variables, AWS config files, or IAM roles."""


class AzureCohereProviderSettings(TypedDict, total=False):
    """Provider settings for Azure Cohere.

    You need to provide these settings if you are using Azure Cohere, and you need to provide them for each Azure Cohere model you use.
    They're **all required**. They're marked `NotRequired` in the TypedDict because you can also provide them by environment variables, but you must provide them one way or another.
    """

    model_deployment: NotRequired[str]
    """The deployment name of the model you want to use. Important: While the OpenAI API uses the model name to identify the model, you must separately provide a codeweaver-compatible name for the model, as well as your Azure resource name here. We're open to PRs if you want to add a parser for model names that can extract the deployment name from them."""
    api_key: NotRequired[SecretStr | None]
    """Your Azure API key. If not provided, we'll assume you have your Azure credentials configured in another way, such as environment variables."""
    azure_resource_name: NotRequired[str]
    """The name of your Azure resource. This is used to identify your resource in Azure."""
    azure_endpoint: NotRequired[str]
    """The endpoint for your Azure resource. This is used to send requests to your resource. Only provide the endpoint, not the full URL. For example, if your endpoint is `https://your-cool-resource.<region_name>.inference.ai.azure.com/v1`, you would only provide "your-cool-resource" here."""
    region_name: NotRequired[str]
    """The Azure region where your resource is located. This is used to route requests to the correct regional endpoint."""


class AzureOpenAIProviderSettings(TypedDict, total=False):
    """Provider settings for Azure OpenAI.

    You need to provide these settings if you are using Azure OpenAI, and you need to provide them for each Azure OpenAI model you use.

    **For embedding models:**
    **We only support the "**next-generation** Azure OpenAI API." Currently, you need to opt into this API in your Azure settings. We didn't want to start supporting the old API knowing it's going away.

    For agent models:
    We support both APIs for agentic models because our support comes from `pydantic_ai`, which supports both.
    """

    azure_resource_name: NotRequired[str]
    """The name of your Azure resource. This is used to identify your resource in Azure."""
    model_deployment: NotRequired[str]
    """The deployment name of the model you want to use. Important: While the OpenAI API uses the model name to identify the model, you must separately provide a codeweaver-compatible name for the model, as well as your Azure resource name here. We're open to PRs if you want to add a parser for model names that can extract the deployment name from them."""
    endpoint: NotRequired[str | None]
    """The endpoint for your Azure resource. This is used to send requests to your resource. Only provide the endpoint, not the full URL. For example, if your endpoint is `https://your-cool-resource.<region_name>.inference.ai.azure.com/v1`, you would only provide "your-cool-resource" here."""
    region_name: NotRequired[str]
    """The Azure region where your resource is located. This is used to route requests to the correct regional endpoint."""
    api_key: NotRequired[SecretStr | None]
    """Your Azure API key. If not provided, we'll assume you have your Azure credentials configured in another way, such as environment variables."""


class FastembedGPUProviderSettings(TypedDict, total=False):
    """Special settings for Fastembed-GPU provider.

    These settings only apply if you are using a Fastembed provider, installed the `codeweaver-mcp[provider-fastembed-gpu]` extra, have a CUDA-capable GPU, and have properly installed and configured the ONNX GPU runtime.
    You can provide these settings with your CodeWeaver embedding provider settings, or rerank provider settings. If you're using fastembed-gpu for both, we'll assume you are using the same settings for both if we find one of them.
    """

    cuda: NotRequired[bool | None]
    """Whether to use CUDA (if available). If `None`, will auto-detect. We'll generally assume you want to use CUDA if it's available unless you provide a `False` value here."""
    provider_settings: NotRequired[list[int] | None]
    """List of GPU device IDs to use. If `None`, we will try to detect available GPUs using `nvidia-smi` if we can find it. We recommend specifying them because our checks aren't perfect."""


# ===========================================================================
# *            Vector Store Provider Settings
# ===========================================================================


class QdrantConfig(TypedDict, total=False):
    """Configuration for Qdrant vector store provider."""

    url: NotRequired[str | None]
    """Qdrant server URL. Defaults to http://localhost:6333 if not specified."""
    api_key: NotRequired[SecretStr | None]
    """API key for authentication (required for remote instances)."""
    collection_name: NotRequired[str | None]
    """Collection name override. Defaults to project name if not specified."""
    prefer_grpc: NotRequired[bool]
    """Use gRPC instead of HTTP. Defaults to False."""
    batch_size: NotRequired[PositiveInt]
    """Batch size for bulk upsert operations. Defaults to 64."""
    dense_vector_name: NotRequired[str]
    """Named vector for dense embeddings. Defaults to 'dense'."""
    sparse_vector_name: NotRequired[str]
    """Named vector for sparse embeddings. Defaults to 'sparse'."""
    client_options: NotRequired[dict[str, Any] | None]
    """Additional keyword arguments to pass to the Qdrant client."""


class MemoryConfig(TypedDict, total=False):
    """Configuration for in-memory vector store provider."""

    persist_path: NotRequired[str]
    """Path for JSON persistence file. Defaults to {system_user_config}/codeweaver/{project_name}_vector_store.json."""
    auto_persist: NotRequired[bool]
    """Automatically save after operations. Defaults to True."""
    persist_interval: NotRequired[PositiveInt]
    """Periodic persist interval in seconds. Defaults to 300 (5 minutes)."""
    collection_name: NotRequired[str]
    """Collection name override. Defaults to project name if not specified."""


type ProviderSpecificSettings = (
    FastembedGPUProviderSettings
    | AWSProviderSettings
    | AzureOpenAIProviderSettings
    | AzureCohereProviderSettings
)


class EmbeddingProviderSettings(BaseProviderSettings):
    """Settings for (dense) embedding models. It validates that the model and provider settings are compatible and complete, reconciling environment variables and config file settings as needed."""

    model_settings: Required[EmbeddingModelSettings]
    """Settings for the embedding model(s)."""
    provider_settings: NotRequired[ProviderSpecificSettings | None]
    """Settings for specific providers, if any. Some providers have special settings that are required for them to work properly, but you may provide them by environment variables as well as in your config, or both."""


class SparseEmbeddingProviderSettings(BaseProviderSettings):
    """Settings for sparse embedding models."""

    model_settings: Required[SparseEmbeddingModelSettings]
    """Settings for the sparse embedding model(s)."""
    provider_settings: NotRequired[ProviderSpecificSettings | None]


class RerankingProviderSettings(BaseProviderSettings):
    """Settings for re-ranking models."""

    model_settings: Required[RerankingModelSettings]
    """Settings for the re-ranking model(s)."""
    provider_settings: NotRequired[ProviderSpecificSettings | None]
    top_n: NotRequired[PositiveInt | None]


class VectorStoreProviderSettings(BaseProviderSettings, total=False):
    """Settings for vector store provider selection and configuration."""

    """Vector store provider: Provider.QDRANT or Provider.MEMORY. Defaults to Provider.QDRANT."""
    provider_settings: Required[QdrantConfig | MemoryConfig]


# Agent model settings are imported/defined from `pydantic_ai`

type ModelString = Annotated[
    str,
    Field(
        description="""The model string, as it appears in `pydantic_ai.models.KnownModelName`."""
    ),
]


class AgentProviderSettings(BaseProviderSettings):
    """Settings for agent models."""

    model: Required[ModelString | None]
    model_settings: Required[AgentModelSettings | None]
    """Settings for the agent model(s)."""


# ===========================================================================
# *                    More TypedDict versions of Models
# ===========================================================================


class ProviderSettingsDict(TypedDict, total=False):
    """A dictionary representation of provider settings."""

    data: NotRequired[tuple[DataProviderSettings, ...] | None]
    # we currently only support one each of embedding, reranking and vector store providers
    # but we use tuples to allow for future expansion for some less common use cases
    embedding: NotRequired[tuple[EmbeddingProviderSettings, ...] | None]
    # rerank is probably the priority for multiple providers in the future, because they're vector agnostic, so you could have fallback providers, or use different ones for different tasks
    sparse_embedding: NotRequired[tuple[SparseEmbeddingProviderSettings, ...] | None]
    reranking: NotRequired[tuple[RerankingProviderSettings, ...] | None]
    vector: NotRequired[tuple[VectorStoreProviderSettings, ...] | None]
    agent: NotRequired[tuple[AgentProviderSettings, ...] | None]


type ProviderSettingsView = DictView[ProviderSettingsDict]

__all__ = (
    "AWSProviderSettings",
    "AgentProviderSettings",
    "AzureCohereProviderSettings",
    "AzureOpenAIProviderSettings",
    "DataProviderSettings",
    "EmbeddingModelSettings",
    "EmbeddingProviderSettings",
    "FastembedGPUProviderSettings",
    "MemoryConfig",
    "ModelString",
    "ProviderSettingsDict",
    "ProviderSettingsView",
    "ProviderSpecificSettings",
    "QdrantConfig",
    "RerankingModelSettings",
    "RerankingProviderSettings",
    "SparseEmbeddingModelSettings",
    "VectorStoreProviderSettings",
)
