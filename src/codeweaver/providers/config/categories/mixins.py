"""Mixin classes for specific providers."""

from __future__ import annotations

from typing import Annotated

from pydantic import Field, SecretStr

from codeweaver.core.types import AnonymityConversion, FilteredKey, FilteredKeyT
from codeweaver.providers.config.clients.multi import AzureOptions


class BedrockProviderMixin:
    """Settings for AWS provider."""

    model_arn: str

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
            description="The deployment name of the model you want to use. This is *different* from the model name in `model_options`, which is the name of the model itself (`text-embedding-3-small`). You need to create a deployment in your Azure OpenAI resource for each model you want to use, and provide the deployment name here."
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

    def as_azure_options(self) -> AzureOptions:
        """Return the settings as an AzureOptions TypedDict."""
        return AzureOptions(
            model_deployment=self.model_deployment,
            endpoint=self.endpoint,
            region_name=self.region_name,
            api_key=self.api_key,
        )


class FastEmbedProviderMixin:
    """Special settings for FastEmbed-GPU provider.

    These settings only apply if you are using a FastEmbed provider, installed the `codeweaver[fastembed-gpu]` or `codeweaver[full-gpu]` extra, have a CUDA-capable GPU, and have properly installed and configured the ONNX GPU runtime (see ONNX docs).

    You can provide these settings with your CodeWeaver embedding provider settings, or rerank provider settings. If you're using fastembed-gpu for both, we'll assume you are using the same settings for both if we find one of them.

    Important: You cannot have both `fastembed` and `fastembed-gpu` installed at the same time. They conflict with each other. Make sure to uninstall `fastembed` if you want to use `fastembed-gpu`.
    """

    cuda: bool | None = None
    "Whether to use CUDA (if available). If `None`, will auto-detect. We'll generally assume you want to use CUDA if it's available unless you provide a `False` value here."
    device_ids: list[int] | None = None
    "List of GPU device IDs to use. If `None`, we will try to detect available GPUs using `nvidia-smi` if we can find it. We recommend specifying them because our checks aren't perfect."


__all__ = ("AzureProviderMixin", "BedrockProviderMixin", "FastEmbedProviderMixin")
