# SPDX-CopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
# SPDX-License-Identifier: MIT OR Apache-2.0
#
# Docstrings taken from Pydantic AI where applicable.
# SPDX-FileCopyrightText: 2025 Pydantic Services Inc.
# SPDX-License-Identifier: MIT
"""Settings objects for agent model constructors.

NOTE: As with other function config modules, the corresponding provider (i.e. anthropic for `AnthropicAgentModelConfig`), refers to the *SDK client* that uses these settings -- not necessarily the model provider or the service provider (i.e. AWS for Bedrock). For example: `BedrockAgentModelConfig` refers to settings used by the Bedrock SDK client, which may be used to access models from multiple service providers, while for Anthropic's Claude models with AWS Bedrock, the agent model config is `AnthropicAgentModelConfig`, because Anthropic's native client is being used, even though the service provider is AWS.

It might seem complicated, but we've simplified it at the top provider-level settings by differentiating by both provider and SDK client where necessary, so for the example above, there is a `AnthropicBedrockAgentProviderSettings` class for using Anthropic's Claude models via AWS Bedrock where the `agent_config` field's type is `AnthropicAgentModelConfig`, and a `BedrockAgentProviderSettings` class for using other models via Bedrock where the `agent_config` field's type is `BedrockAgentModelConfig`.

*Not all settings in a model are necessarily supported by every model or every SDK*. These are `pydantic_ai` types, and that library takes a little bit of a different approach to configuration than we do. I'm not sure we'd do it differently though because it quickly becomes a complex problem space given the number of providers, models, and SDKs and the speed at which new models and features are released. When in doubt, refer to the SDK documentation and model card/docs for the specific model you're using to verify which settings are supported.

Each ModelConfig inherits from the base `AgentModelConfig` (which is actually `pydantic_ai.models.ModelSettings`) and adds additional fields for settings that are specific to that provider's SDK. Generally you can be certain that the SDK will support the namespaced fields (e.g. `anthropic_thinking` or `bedrock_guardrail_config` -- not necessarily for every model), but for the general fields inherited from `AgentModelConfig`, it's a good idea to check the SDK documentation for the specific model you're using to verify that the setting is supported. The `AgentModelConfig` fields are common settings found across providers (like `temperature` and `max_tokens`), but not every provider supports every setting, and some providers have unique settings that aren't shared by others, which is why we have provider-specific ModelConfig classes that inherit from the base `AgentModelConfig`. If two fields are similar, use the namespaced field. For example, if you're using Anthropic's SDK, use `anthropic_thinking` instead of a hypothetical `thinking` field that might be added to the base `AgentModelConfig` in the future, even if other providers eventually support a similar setting. This way you can be sure that the setting is supported by the SDK you're using, and you won't run into issues with your settings not being applied.
"""

from __future__ import annotations

import re

from collections.abc import Iterable, Mapping
from typing import TYPE_CHECKING, Annotated, Any, Literal, Required, TypedDict

from pydantic import Discriminator, Field, Tag
from pydantic_ai.models import ModelSettings as AgentModelConfig

from codeweaver.core.types import LiteralStringT
from codeweaver.core.utils import has_package


# This is a bit verbose, but it makes type checkers happy regardless of which packages are installed. This is entirely for IDE and type checker convenience; at runtime, only the relevant classes will be used.

if TYPE_CHECKING and has_package("anthropic"):
    from pydantic_ai.models.anthropic import AnthropicModelSettings as AnthropicAgentModelConfig
else:
    type AnthropicCacheType = bool | Literal["5m", "1h"]

    class AnthropicAgentModelConfig(AgentModelConfig, total=False):
        """Simplified settings used for AnthropicModelSettings when Anthropic is not installed, used for an Anthropic model request."""

        anthropic_metadata: Mapping[Literal["_user_id"], str] | None
        """An object describing metadata about the request.

        Contains `user_id`, an external identifier for the user who is associated with the request.
        """

        anthropic_thinking: Required[
            Mapping[Literal["enabled", "budget_tokens"], int | Literal["enabled"]]
            | Mapping[Literal["type"], Literal["disabled"]]
        ]
        """Determine whether the model should generate a thinking block.

        See [the Anthropic docs](https://docs.anthropic.com/en/docs/build-with-claude/extended-thinking) for more information.
        """

        anthropic_cache_tool_definitions: AnthropicCacheType | None
        """Whether to add `cache_control` to the last tool definition.

        When enabled, the last tool in the `tools` array will have `cache_control` set,
        allowing Anthropic to cache tool definitions and reduce costs.
        If `True`, uses TTL='5m'. You can also specify '5m' or '1h' directly.
        TTL is automatically omitted for Bedrock, as it does not support explicit TTL.
        See https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching for more information.
        """

        anthropic_cache_instructions: AnthropicCacheType | None
        """Whether to add `cache_control` to the last system prompt block.

        When enabled, the last system prompt will have `cache_control` set,
        allowing Anthropic to cache system instructions and reduce costs.
        If `True`, uses TTL='5m'. You can also specify '5m' or '1h' directly.
        TTL is automatically omitted for Bedrock, as it does not support explicit TTL.
        See https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching for more information.
        """

        anthropic_cache_messages: AnthropicCacheType | None
        """Convenience setting to enable caching for the last user message.

        When enabled, this automatically adds a cache point to the last content block
        in the final user message, which is useful for caching conversation history
        or context in multi-turn conversations.
        If `True`, uses TTL='5m'. You can also specify '5m' or '1h' directly.
        TTL is automatically omitted for Bedrock, as it does not support explicit TTL.

        Note: Uses 1 of Anthropic's 4 available cache points per request. Any additional CachePoint
        markers in messages will be automatically limited to respect the 4-cache-point maximum.
        See https://docs.anthropic.com/en/docs/build-with-claude/prompt-caching for more information.
        """

        anthropic_container: (
            Mapping[
                Literal["id", "skills"],
                str
                | list[
                    Iterable[
                        Mapping[
                            Literal["skill_id", "type", "version"],
                            str | Literal["anthropic", "custom"],
                        ]
                    ]
                ],
            ]
            | None
        )
        """Container configuration for multi-turn conversations.

        By default, if previous messages contain a container_id (from a prior response),
        it will be reused automatically.

        Set to `False` to force a fresh container (ignore any `container_id` from history).
        Set to a dict (e.g. `{'id': 'container_xxx'}`) to explicitly specify a container.
        """


if TYPE_CHECKING and has_package("boto3") and has_package("mypy_boto3_bedrock_runtime"):
    from pydantic_ai.models.bedrock import BedrockModelSettings as BedrockAgentModelConfig
else:

    class BedrockAgentModelConfig(AgentModelConfig, total=False):
        """Settings for Bedrock models.

        See [the Bedrock Converse API docs](https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html#API_runtime_Converse_RequestSyntax) for a full list.
        See [the boto3 implementation](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/bedrock-runtime/client/converse.html) of the Bedrock Converse API.
        """

        bedrock_guardrail_config: Mapping[str, Any] | None
        """Content moderation and safety settings for Bedrock API requests.

        See more about it on <https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_GuardrailConfiguration.html>.
        """
        bedrock_performance_configuration: Mapping[str, Any] | None
        """Performance optimization settings for model inference.

        See more about it on <https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_PerformanceConfiguration.html>.
        """
        bedrock_request_metadata: Mapping[str, str] | None
        """Additional metadata to attach to Bedrock API requests.

        See more about it on <https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_Converse.html#API_runtime_Converse_RequestSyntax>.
        """
        bedrock_additional_model_response_fields_paths: list[str] | None
        """JSON paths to extract additional fields from model responses.

        See more about it on <https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters.html>.
        """
        bedrock_prompt_variables: Mapping[str, Any] | None
        """Variables for substitution into prompt templates.

        See more about it on <https://docs.aws.amazon.com/bedrock/latest/APIReference/API_runtime_PromptVariableValues.html>.
        """
        bedrock_additional_model_requests_fields: Mapping[str, Any] | None
        """Additional model-specific parameters to include in requests.

        See more about it on <https://docs.aws.amazon.com/bedrock/latest/userguide/model-parameters.html>.
        """
        bedrock_cache_tool_definitions: bool | None
        """Whether to add a cache point after the last tool definition.

        When enabled, the last tool in the `tools` array will include a `cachePoint`, allowing Bedrock to cache tool
        definitions and reduce costs for compatible models.
        See https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-caching.html for more information.
        """
        bedrock_cache_instructions: bool | None
        """Whether to add a cache point after the system prompt blocks.

        When enabled, an extra `cachePoint` is appended to the system prompt so Bedrock can cache system instructions.
        See https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-caching.html for more information.
        """
        bedrock_cache_messages: bool | None
        """Convenience setting to enable caching for the last user message.

        When enabled, this automatically adds a cache point to the last content block
        in the final user message, which is useful for caching conversation history
        or context in multi-turn conversations.

        Note: Uses 1 of Bedrock's 4 available cache points per request. Any additional CachePoint
        markers in messages will be automatically limited to respect the 4-cache-point maximum.
        See https://docs.aws.amazon.com/bedrock/latest/userguide/prompt-caching.html for more information.
        """
        bedrock_service_tier: Literal["reserved", "priority", "default", "flex"] | None
        """Setting for optimizing performance and cost

        See more about it on <https://docs.aws.amazon.com/bedrock/latest/userguide/service-tiers-inference.html>.
        """


if TYPE_CHECKING and has_package("openai"):
    from pydantic_ai.models.cerebras import CerebrasModelSettings as CerebrasAgentModelConfig

else:

    class CerebrasAgentModelConfig(AgentModelConfig, total=False):
        """Simplified settings object for CerebrasModelSettings when OpenAI is not installed."""

        cerebras_disable_reasoning: bool | None
        """Disable reasoning for the model.

        This setting is only supported on reasoning models, currently: `zai-glm-4.6` and `gpt-oss-120b`.

        See [the Cerebras docs](https://inference-docs.cerebras.ai/resources/openai#passing-non-standard-parameters) for more details.
        """


class CohereAgentModelConfig(AgentModelConfig, total=False):
    """Settings for a Cohere model request."""


if TYPE_CHECKING and has_package("google"):
    from pydantic_ai.models.google import GoogleModelSettings as GoogleAgentModelConfig
else:

    class GoogleAgentModelConfig(AgentModelConfig, total=False):
        """Simplified settings object for GoogleModelSettings when Google is not installed."""

    google_safety_settings: (
        list[Mapping[Literal["category", "method", "threshold"], LiteralStringT]] | None
    )
    """The safety settings to use for the model.

    See <https://ai.google.dev/gemini-api/docs/safety-settings> for more information.
    """

    google_thinking_config: (
        Mapping[
            Literal["include_thoughts", "thinking_budget", "thinking_level"],
            bool | int | Literal["THINKING_LEVEL_UNSPECIFIED", "LOW", "MEDIUM", "HIGH"],
        ]
        | None
    )
    """The thinking configuration to use for the model.

    See <https://ai.google.dev/gemini-api/docs/thinking> for more information.
    """

    google_labels: dict[str, str] | None
    """User-defined metadata to break down billed charges. Only supported by the Vertex AI API.

    See the [Gemini API docs](https://cloud.google.com/vertex-ai/generative-ai/docs/multimodal/add-labels-to-api-calls) for use cases and limitations.
    """

    google_video_resolution: (
        Literal[
            "MEDIA_RESOLUTION_UNSPECIFIED",
            "MEDIA_RESOLUTION_LOW",
            "MEDIA_RESOLUTION_MEDIUM",
            "MEDIA_RESOLUTION_HIGH",
        ]
        | None
    )
    """The video resolution to use for the model.

    See <https://ai.google.dev/api/generate-content#MediaResolution> for more information.
    """

    google_cached_content: str | None
    """The name of the cached content to use for the model.

    See <https://ai.google.dev/gemini-api/docs/caching> for more information.
    """

if TYPE_CHECKING and has_package("groq"):
    from pydantic_ai.models.groq import GroqModelSettings as GroqAgentModelConfig
else:

    class GroqAgentModelConfig(AgentModelConfig, total=False):
        """Simplified settings object for GroqModelSettings when Groq is not installed; settings for a Groq model request."""

        groq_reasoning_format: Literal["hidden", "raw", "parsed"] | None
        """The format of the reasoning output.

        See [the Groq docs](https://console.groq.com/docs/reasoning#reasoning-format) for more details.
        """


if TYPE_CHECKING and has_package("huggingface_hub"):
    from pydantic_ai.models.huggingface import (
        HuggingFaceModelSettings as HuggingFaceAgentModelConfig,
    )
else:

    class HuggingFaceAgentModelConfig(AgentModelConfig, total=False):
        """Simplified settings object for HuggingFaceModelSettings when HuggingFace is not installed; settings for a Hugging Face model request."""


if TYPE_CHECKING and has_package("mistralai"):
    from pydantic_ai.models.mistral import MistralModelSettings as MistralAgentModelConfig
else:

    class MistralAgentModelConfig(AgentModelConfig, total=False):
        """Simplified settings object for MistralModelSettings when Mistral is not installed; settings for a Mistral model request."""


if TYPE_CHECKING and has_package("openai"):
    from pydantic_ai.models.openai import OpenAIChatModelSettings as OpenAIAgentModelConfig
    from pydantic_ai.models.openrouter import OpenRouterModelSettings as OpenRouterAgentModelConfig
    from pydantic_ai.models.openrouter import (
        OpenRouterProviderConfig as OpenRouterAgentProviderConfig,
    )
else:

    class OpenRouterAgentProviderConfig(TypedDict, total=False):
        """Represents the 'Provider' object from the OpenRouter API."""

        order: list[LiteralStringT]
        """List of provider slugs to try in order (e.g. ["anthropic", "openai"]). [See details](https://openrouter.ai/docs/features/provider-routing#ordering-specific-providers)"""

        allow_fallbacks: bool
        """Whether to allow backup providers when the primary is unavailable. [See details](https://openrouter.ai/docs/features/provider-routing#disabling-fallbacks)"""

        require_parameters: bool
        """Only use providers that support all parameters in your request."""

        data_collection: Literal["allow", "deny"]
        """Control whether to use providers that may store data. [See details](https://openrouter.ai/docs/features/provider-routing#requiring-providers-to-comply-with-data-policies)"""

        zdr: bool
        """Restrict routing to only ZDR (Zero Data Retention) endpoints. [See details](https://openrouter.ai/docs/features/provider-routing#zero-data-retention-enforcement)"""

        only: list[LiteralStringT]
        """List of provider slugs to allow for this request. [See details](https://openrouter.ai/docs/features/provider-routing#allowing-only-specific-providers)"""

        ignore: list[str]
        """List of provider slugs to skip for this request. [See details](https://openrouter.ai/docs/features/provider-routing#ignoring-providers)"""

        quantizations: list[
            Literal["int4", "int8", "fp4", "fp6", "fp8", "fp16", "bf16", "fp32", "unknown"]
        ]
        """List of quantization levels to filter by (e.g. ["int4", "int8"]). [See details](https://openrouter.ai/docs/features/provider-routing#quantization)"""

        sort: Literal["price", "throughput", "latency"]
        """Sort providers by price or throughput. (e.g. "price" or "throughput"). [See details](https://openrouter.ai/docs/features/provider-routing#provider-sorting)"""

        max_price: Mapping[Literal["prompt", "completion", "image", "audio", "request"], int]
        """The maximum pricing you want to pay for this request. [See details](https://openrouter.ai/docs/features/provider-routing#max-price). USD price per million tokens for prompt and completion."""

    class OpenRouterAgentModelConfig(AgentModelConfig, total=False):
        """Settings for an OpenRouter model request."""

        openrouter_models: list[str]
        """A list of fallback models.

        These models will be tried, in order, if the main model returns an error. [See details](https://openrouter.ai/docs/features/model-routing#the-models-parameter)
        """

        openrouter_provider: OpenRouterAgentProviderConfig
        """OpenRouter routes requests to the best available providers for your model. By default, requests are load balanced across the top providers to maximize uptime.

        You can customize how your requests are routed using the provider object. [See more](https://openrouter.ai/docs/features/provider-routing)"""

        openrouter_preset: str
        """Presets allow you to separate your LLM configuration from your code.

        Create and manage presets through the OpenRouter web application to control provider routing, model selection, system prompts, and other parameters, then reference them in OpenRouter API requests. [See more](https://openrouter.ai/docs/features/presets)"""

        openrouter_transforms: list[Literal["middle-out"]]
        """To help with prompts that exceed the maximum context size of a model.

        Transforms work by removing or truncating messages from the middle of the prompt, until the prompt fits within the model's context window. [See more](https://openrouter.ai/docs/features/message-transforms)
        """

        openrouter_reasoning: Mapping[
            Literal["effort", "max_tokens", "exclude", "enabled"],
            Literal["low", "medium", "high"] | int | bool,
        ]
        """To control the reasoning tokens in the request.

        The reasoning config object consolidates settings for controlling reasoning strength across different models. [See more](https://openrouter.ai/docs/use-cases/reasoning-tokens)
        """

        openrouter_usage: Mapping[Literal["include"], bool]
        """To control the usage of the model.

        The usage config object consolidates settings for enabling detailed usage information. [See more](https://openrouter.ai/docs/use-cases/usage-accounting)
        """

    class OpenAIAgentModelConfig(AgentModelConfig, total=False):
        """Settings used for an OpenAI model request."""

        openai_reasoning_effort: Literal["none", "minimal", "low", "medium", "high", "xhigh"]
        """Constrains effort on reasoning for [reasoning models](https://platform.openai.com/docs/guides/reasoning).

        Currently supported values are `low`, `medium`, and `high`. Reducing reasoning effort can
        result in faster responses and fewer tokens used on reasoning in a response.
        """

        openai_logprobs: bool
        """Include log probabilities in the response.

        For Chat models, these will be included in `ModelResponse.provider_details['logprobs']`.
        For Responses models, these will be included in the response output parts `TextPart.provider_details['logprobs']`.
        """

        openai_top_logprobs: int
        """Include log probabilities of the top n tokens in the response."""

        openai_user: str
        """A unique identifier representing the end-user, which can help OpenAI monitor and detect abuse.

        See [OpenAI's safety best practices](https://platform.openai.com/docs/guides/safety-best-practices#end-user-ids) for more details.
        """

        openai_service_tier: Literal["auto", "default", "flex", "priority"]
        """The service tier to use for the model request.

        Currently supported values are `auto`, `default`, `flex`, and `priority`.
        For more information, see [OpenAI's service tiers documentation](https://platform.openai.com/docs/api-reference/chat/object#chat/object-service_tier).
        """

        openai_prediction: Mapping[
            Literal["content", "type"],
            str
            | Iterable[
                Mapping[Literal["text", "type"], str | Literal["text"]] | Literal["content"]
            ],
        ]
        """Enables [predictive outputs](https://platform.openai.com/docs/guides/predicted-outputs).

        This feature is currently only supported for some OpenAI models.
        """

        openai_prompt_cache_key: str
        """Used by OpenAI to cache responses for similar requests to optimize your cache hit rates.

        See the [OpenAI Prompt Caching documentation](https://platform.openai.com/docs/guides/prompt-caching#how-it-works) for more information.
        """

        openai_prompt_cache_retention: Literal["in-memory", "24h"]
        """The retention policy for the prompt cache. Set to 24h to enable extended prompt caching, which keeps cached prefixes active for longer, up to a maximum of 24 hours.

        See the [OpenAI Prompt Caching documentation](https://platform.openai.com/docs/guides/prompt-caching#how-it-works) for more information.
        """


_matcher_re: re.Pattern = re.compile(
    r"^(?P<provider>anthropic|bedrock|cerebras|cohere|google|groq|huggingface|mistral|openai|openrouter)_.*"
)


def _discriminate_agent_model_configs(v: Any) -> str:
    keys = list(v)
    if keys and (
        next_match := next((m if (m := _matcher_re.match(key)) else None for key in keys), None)
    ):
        return next_match.group("provider")
    return "agent"


type AgentModelConfigT = Annotated[
    Annotated[AgentModelConfig, Tag("agent")]
    | Annotated[AnthropicAgentModelConfig, Tag("anthropic")]
    | Annotated[BedrockAgentModelConfig, Tag("bedrock")]
    | Annotated[CerebrasAgentModelConfig, Tag("cerebras")]
    | Annotated[CohereAgentModelConfig, Tag("cohere")]
    | Annotated[GoogleAgentModelConfig, Tag("google")]
    | Annotated[GroqAgentModelConfig, Tag("groq")]
    | Annotated[HuggingFaceAgentModelConfig, Tag("huggingface")]
    | Annotated[MistralAgentModelConfig, Tag("mistral")]
    | Annotated[OpenAIAgentModelConfig, Tag("openai")]
    | Annotated[OpenRouterAgentModelConfig, Tag("openrouter")],
    Field(discriminator=Discriminator(_discriminate_agent_model_configs)),
]
# NOTE: This discriminated union is *usually* not necessary, as each provider's top-level settings
# class will specify the correct AgentModelConfig type for that provider. However, it can be
# useful in cases where the provider is not known ahead of time, such as in dynamic loading
# scenarios with custom providers.


__all__ = (
    "AgentModelConfig",
    "AgentModelConfigT",
    "AnthropicAgentModelConfig",
    "BedrockAgentModelConfig",
    "CerebrasAgentModelConfig",
    "CohereAgentModelConfig",
    "GoogleAgentModelConfig",
    "GroqAgentModelConfig",
    "HuggingFaceAgentModelConfig",
    "MistralAgentModelConfig",
    "OpenAIAgentModelConfig",
    "OpenRouterAgentModelConfig",
    "OpenRouterAgentProviderConfig",
)
