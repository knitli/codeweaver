# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""LiteLLM embedding provider information.

LiteLLM presents a difficult case, as it supports a wide range of providers itself, and each provider may have multiple models with different capabilities and using different APIs.

From an authentication standpoint, you need to use the client's authentication environment variables, e.g., for OpenAI models, you need to set OPENAI_API_KEY.

To keep things manageable, for now, we only support OpenAI-compatible models and endpoints via LiteLLM. Unlike other providers that only expose OpenAI models through the OpenAI API, LiteLLM actually supports a broad range of models through the OpenAI-compatible API. All models must be prefixed with "openai/" to tell LiteLLM to use the OpenAI-compatible endpoint.
"""

# ===========================================================================
# todo              This is not yet implemented!
#        It needs to get integrated, tested, and documented.
# ===========================================================================

from typing import Literal

from pydantic import FutureDate

from codeweaver.core import BasedModel, LiteralStringT
from codeweaver.core.types import FROZEN_BASEDMODEL_CONFIG
from codeweaver.providers.provider import Provider


class LiteLLMModelSpec(BasedModel):
    """Specification for a LiteLLM embedding model."""

    model_config = FROZEN_BASEDMODEL_CONFIG

    code_interpreter_cost_per_session: float | None = None
    """The cost per session for using the code interpreter with this model."""
    computer_use_input_cost_per_1k_tokens: float | None = None
    """The cost per 1,000 input tokens for using the computer with this model."""
    computer_use_output_cost_per_1k_tokens: float | None = None
    """The cost per 1,000 output tokens for using the computer with this model."""
    deprecation_date: FutureDate | None = None
    """The date when this model will be deprecated, if applicable."""
    file_search_cost_per_1k_calls: float | None = None
    """The cost per 1,000 calls for file search with this model."""
    file_search_cost_per_gb_per_day: float | None = None
    """The cost per GB per day for file search with this model."""
    input_cost_per_audio_token: float | None = None
    """The cost per audio token for input with this model."""
    lite_llm_provider: LiteralStringT | None = None
    """The LiteLLM provider for this model."""
    max_input_tokens: int | None = None
    """The maximum number of input tokens for this model."""
    max_output_tokens: int | None = None
    """The maximum number of output tokens for this model."""
    max_tokens: int | None = None
    """Deprecated. Use `max_input_tokens` and `max_output_tokens` instead."""
    mode: (
        Literal[
            "chat",
            "completion",
            "embedding",
            "image_generation",
            "audio_transcription",
            "audio_speech",
            "moderation",
            "rerank",
        ]
        | None
    ) = None
    output_cost_per_reasoning_token: float | None = None
    """The cost per reasoning token for output with this model."""
    output_cost_per_token: float | None = None
    """The cost per output token for this model."""
    search_context_cost_per_query: None = None
    """The cost per query for search context with this model."""
    supported_regions: (
        list[Literal["global", "us-west-2", "us-west-1", "ap-southeast-1", "ap-northeast-1"]] | None
    ) = None
    """The regions where this model is supported."""
    supports_audio_input: bool | None = None
    """Whether this model supports audio input."""
    supports_audio_output: bool | None = None
    """Whether this model supports audio output."""
    supports_function_calling: bool | None = None
    """Whether this model supports function calling."""
    supports_parallel_function_calling: bool | None = None
    """Whether this model supports parallel function calling."""
    supports_prompt_caching: bool | None = None
    """Whether this model supports prompt caching."""
    supports_reasoning: bool | None = None
    """Whether this model supports reasoning."""
    supports_response_schema: bool | None = None
    """Whether this model supports response schema."""
    supports_system_messages: bool | None = None
    """Whether this model supports system messages."""
    supports_vision: bool | None = None
    """Whether this model supports vision."""
    supports_web_search: bool | None = None
    """Whether this model supports web search."""
    vector_store_cost_per_gb_per_day: float | None = None
    """The cost per GB per day for vector store with this model."""


LITELLM_OPENAI_PROVIDERS: dict[Provider | LiteralStringT, tuple[LiteralStringT, ...]] = {
    Provider.OPENAI: ("text-embedding-3-small", "text-embedding-3-large"),
    Provider.COHERE: ("cohere/embed-english-v3.0", "cohere/embed-multilingual-v3.0"),
    "Nvidia_NIM": (  # NVIDIA_NIM_API_KEY & NVIDIA_NIM_API_BASE
        "nvidia_nim/NV-Embed-QA",
        "nvidia_nim/nvidia/nv-embed-v1",
        "nvidia_nim/nvidia/nv-embedqa-mistral-7b-v2",
        "nvidia_nim/nvidia/nv-embedqa-e5-v5",
        "nvidia_nim/nvidia/embed-qa-4",
        "nvidia_nim/nvidia/llama-3.2-nv-embedqa-1b-v1",
        "nvidia_nim/nvidia/llama-3.2-nv-embedqa-1b-v2",
        "nvidia_nim/snowflake/arctic-embed-l",
        "nvidia_nim/baai/bge-m3",
    ),
    Provider.HUGGINGFACE_INFERENCE: (  # HUGGINGFACE_API_KEY
        "huggingface/microsoft/codebert-base",
        "huggingface/hf-embedding-model",
    ),
    Provider.MISTRAL: ("mistral/mistral-embed",),
    Provider.GOOGLE: ("gemini/text-embedding-004",),
    Provider.VOYAGE: (
        "voyage/voyage-3-large",
        "voyage/voyage-3.5",
        "voyage/voyage-code-3",
        "voyage/voyage-3.5-lite",
    ),
}
