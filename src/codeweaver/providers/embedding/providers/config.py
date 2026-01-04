from __future__ import annotations

from typing import Literal, LiteralString, NotRequired, Required, TypedDict

from codeweaver.core import BasedModel


BEDROCK_DEFAULTS = {"cohere*": {}}


class BedrockEmbeddingRequestParams(TypedDict, total=False):
    """Parameters for Bedrock embedding requests."""

    model_id: Required[str]
    """The model ID to use for generating embeddings. The value for this depends on the model, your account, and other factors. [See the Bedrock docs](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/bedrock-runtime/client/invoke_model.html) for more information. tl;dr **use the model ARN if you aren't sure.**"""
    trace: NotRequired[Literal["ENABLED", "DISABLED", "ENABLED_FULL"]]
    """Whether to enable tracing for the requests made to Bedrock. Defaults to "DISABLED"."""
    guardrail_identifier: NotRequired[str]
    """The guardrail identifier to use for the request. This is used to enforce safety and compliance policies. We'll default to null/None. If you need this, you'll know."""
    guardrail_version: NotRequired[str]
    """The guardrail version to use for the request, if using guardrails."""
    performance_config_latency: NotRequired[Literal["standard", "optimized"]]
    """The performance configuration for latency. Can be "standard" or "optimized". Defaults to "standard"."""


class BedrockTitanV2ConfigDict(TypedDict, total=False):
    """Configuration options specific to the Bedrock Titan V2 embedding model."""

    dimensions: NotRequired[Literal[256, 512, 1024]]
    """Number of dimensions for the embeddings. Can be 256, 512, or 1024. Defaults to 1024."""
    embedding_types: NotRequired[Literal["float", "binary"]]


class BedrockCohereConfigDict(TypedDict, total=False):
    """Configuration options specific to Bedrock Cohere embedding models."""

    truncate: NotRequired[Literal["NONE", "START", "END"]]
    """Truncation strategy for inputs that exceed the model's maximum context length. Can be "NONE", "START", or "END". Defaults to "NONE"."""
    embedding_types: NotRequired[Literal["float", "int8", "uint8", "binary", "ubinary"]]


class BedrockEmbeddingConfigDict(BasedModel):
    """Configuration options for Bedrock embedding models."""

    model_name: Required[
        Literal[
            "amazon.titan-embed-text-v2:0",
            "cohere.embed-english-v3.0",
            "cohere.embed-multilingual-v3.0",
        ]
        | LiteralString
    ]
    """The Bedrock embedding model to use. Can be one of the predefined models or a custom model identifier. Note that this isn't the AWS `model_id` (usually its ARN) - that's specified in the embedding request params."""

    model: NotRequired[BedrockTitanV2ConfigDict | BedrockCohereConfigDict]
    """Model-specific embedding configuration options."""

    embedding: NotRequired[BedrockEmbeddingRequestParams]
    """Parameters for the embedding request to Bedrock."""


class FastembedEmbeddingConfigDict(BasedModel):
    """Configuration options for Fastembed embedding models."""

    model_name: Required[str]
    """The Fastembed model name to use for embeddings."""

    model_version: NotRequired[str]
    """The version of the Fastembed model to use. Defaults to the latest version available."""

    additional_options: NotRequired[dict[str, str]]
    """Additional model-specific options for Fastembed embeddings."""
