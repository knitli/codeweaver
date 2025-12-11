# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Provider enum and related functionality.

The `Provider` enum defines the available providers across the CodeWeaver project,
and includes methods for validating providers, checking capabilities, and retrieving
provider-specific settings.

A companion enum, `ProviderKind`, categorizes providers by their capabilities,
such as `embedding`, `sparse_embedding`, `reranking`, `vector_store`, `agent`, and `data`.

The `Provider` enum also includes methods for retrieving some provider-specific information, such as environment variables used by the provider's client that are not part of CodeWeaver's settings.
"""

# ===========================================================================
# *     PROVIDER ENUM - main provider enum for all CodeWeaver providers
# ===========================================================================
from __future__ import annotations

import contextlib
import os

from typing import NotRequired, TypedDict, cast, is_typeddict

from codeweaver.core.types.enum import BaseEnum
from codeweaver.core.types.env import EnvVarInfo as ProviderEnvVarInfo
from codeweaver.exceptions import ConfigurationError


class ProviderEnvVars(TypedDict, total=False):
    """Provides information about environment variables used by a provider's client that are not part of CodeWeaver's settings.

    You can optionally use these to configure the provider's client, or you can use the equivalent CodeWeaver environment variables or settings.

    Each setting is a tuple of the form `(env_var_name, description)`, where `env_var_name` is the name of the environment variable and `description` is a brief description of what it does or the expected format.
    """

    note: NotRequired[str]
    api_key: NotRequired[ProviderEnvVarInfo]
    host: NotRequired[ProviderEnvVarInfo]
    """URL or hostname of the provider's API endpoint."""
    endpoint: NotRequired[ProviderEnvVarInfo]
    """A customer-specific endpoint hostname for the provider's API."""
    log_level: NotRequired[ProviderEnvVarInfo]
    tls_cert_path: NotRequired[ProviderEnvVarInfo]
    tls_key_path: NotRequired[ProviderEnvVarInfo]
    tls_on_off: NotRequired[ProviderEnvVarInfo]
    tls_version: NotRequired[ProviderEnvVarInfo]
    config_path: NotRequired[ProviderEnvVarInfo]
    region: NotRequired[ProviderEnvVarInfo]
    account_id: NotRequired[ProviderEnvVarInfo]

    port: NotRequired[ProviderEnvVarInfo]
    path: NotRequired[ProviderEnvVarInfo]
    oauth: NotRequired[ProviderEnvVarInfo]

    other: NotRequired[dict[str, ProviderEnvVarInfo]]


class Provider(BaseEnum):
    """Enumeration of available providers."""

    VOYAGE = "voyage"
    FASTEMBED = "fastembed"

    QDRANT = "qdrant"
    MEMORY = "memory"

    ANTHROPIC = "anthropic"
    BEDROCK = "bedrock"
    COHERE = "cohere"
    GOOGLE = "google"
    X_AI = "x-ai"
    HUGGINGFACE_INFERENCE = "hf-inference"
    SENTENCE_TRANSFORMERS = "sentence-transformers"
    MISTRAL = "mistral"
    OPENAI = "openai"

    # OpenAI Compatible with OpenAIModel
    AZURE = "azure"  # supports rerank, but not w/ OpenAI API
    CEREBRAS = "cerebras"
    DEEPSEEK = "deepseek"
    FIREWORKS = "fireworks"
    GITHUB = "github"
    GROQ = "groq"  # yes, it's different from Grok...
    HEROKU = "heroku"
    LITELLM = "litellm"
    MOONSHOT = "moonshot"
    OLLAMA = "ollama"  # supports rerank, but not w/ OpenAI API
    OPENROUTER = "openrouter"
    PERPLEXITY = "perplexity"
    TOGETHER = "together"
    VERCEL = "vercel"

    DUCKDUCKGO = "duckduckgo"
    TAVILY = "tavily"

    NOT_SET = "not_set"

    @classmethod
    def validate(cls, value: str) -> BaseEnum:
        """Validate provider-specific settings."""
        with contextlib.suppress(AttributeError, KeyError, ValueError):
            if value_in_self := cls.from_string(value.strip()):
                return value_in_self
        raise ConfigurationError(f"Invalid provider: {value}")

    @property
    def other_env_vars(  # noqa: C901
        self,
    ) -> tuple[ProviderEnvVars, ...] | None:
        """Get the environment variables used by the provider's client that are not part of CodeWeaver's settings."""
        from codeweaver.core.types.env import EnvFormat

        httpx_env_vars = {
            "http_proxy": ProviderEnvVarInfo(
                env="HTTPS_PROXY", description="HTTP proxy for requests"
            ),
            "ssl_cert_file": ProviderEnvVarInfo(
                env="SSL_CERT_FILE", description="Path to the SSL certificate file for requests"
            ),
        }
        match self:
            case Provider.QDRANT:
                return (
                    ProviderEnvVars(
                        note="Qdrant supports setting **all** configuration options using environment variables. Like with CodeWeaver, nested variables are separated by double underscores (`__`). For all options, see [the Qdrant documentation](https://qdrant.tech/documentation/guides/configuration/)",
                        log_level=ProviderEnvVarInfo(
                            env="QDRANT__LOG_LEVEL",
                            description="Log level for Qdrant service",
                            choices={"DEBUG", "INFO", "WARNING", "ERROR"},
                        ),
                        api_key=ProviderEnvVarInfo(
                            env="QDRANT__SERVICE__API_KEY",
                            is_secret=True,
                            description="API key for Qdrant service",
                        ),
                        tls_on_off=ProviderEnvVarInfo(
                            env="QDRANT__SERVICE__ENABLE_TLS",
                            description="Enable TLS for Qdrant service, expects truthy or false value (e.g. 1 for on, 0 for off).",
                            fmt=EnvFormat.BOOLEAN,
                            choices={"true", "false"},
                        ),
                        tls_cert_path=ProviderEnvVarInfo(
                            env="QDRANT__TLS__CERT",
                            description="Path to the TLS certificate file for Qdrant service. Only needed if using a self-signed certificate. If you're using qdrant-cloud, you don't need this.",
                            fmt=EnvFormat.FILEPATH,
                        ),
                        host=ProviderEnvVarInfo(
                            env="QDRANT__SERVICE__HOST",
                            description="Hostname of the Qdrant service; do not use for URLs with schemes (e.g. 'http://')",
                        ),
                        port=ProviderEnvVarInfo(
                            env="QDRANT__SERVICE__HTTP_PORT",
                            description="Port number for the Qdrant service",
                        ),
                    ),
                )
            case Provider.VOYAGE:
                return (
                    ProviderEnvVars(
                        api_key=ProviderEnvVarInfo(
                            env="VOYAGE_API_KEY",
                            is_secret=True,
                            description="API key for Voyage service",
                        ),
                        **httpx_env_vars,
                    ),
                )
            case Provider.AZURE:
                # Azure has env vars by model provider, so we return a tuple of them.
                return (
                    ProviderEnvVars(
                        note="These variables are for the Azure OpenAI service. (OpenAI models on Azure)",
                        api_key=ProviderEnvVarInfo(
                            env="AZURE_OPENAI_API_KEY",
                            is_secret=True,
                            description="API key for Azure OpenAI service (OpenAI models on Azure)",
                        ),
                        endpoint=ProviderEnvVarInfo(
                            env="AZURE_OPENAI_ENDPOINT",
                            description="Endpoint for Azure OpenAI service (OpenAI models on Azure)",
                        ),
                        region=ProviderEnvVarInfo(
                            env="AZURE_OPENAI_REGION",
                            description="Region for Azure OpenAI service (OpenAI models on Azure)",
                        ),
                        **httpx_env_vars,
                    ),
                    ProviderEnvVars(
                        note="These variables are for the Azure Cohere service.",
                        api_key=ProviderEnvVarInfo(
                            env="AZURE_COHERE_API_KEY",
                            is_secret=True,
                            description="API key for Azure Cohere service (cohere models on Azure)",
                        ),
                        endpoint=ProviderEnvVarInfo(
                            env="AZURE_COHERE_ENDPOINT",
                            description="Endpoint for Azure Cohere service (cohere models on Azure)",
                        ),
                        region=ProviderEnvVarInfo(
                            env="AZURE_COHERE_REGION", description="Region for Azure Cohere service"
                        ),
                        **httpx_env_vars,
                    ),
                    cast(ProviderEnvVars, *type(self).OPENAI.other_env_vars),
                )
            case Provider.VERCEL:
                return (
                    ProviderEnvVars(
                        note="You may also use the OpenAI-compatible environment variables with Vercel, since it uses the OpenAI client.",
                        api_key=ProviderEnvVarInfo(
                            env="AI_GATEWAY_API_KEY",
                            is_secret=True,
                            description="API key for Vercel service",
                        ),
                        other=httpx_env_vars,
                    ),
                    ProviderEnvVars(
                        api_key=ProviderEnvVarInfo(
                            env="VERCEL_OIDC_TOKEN",
                            is_secret=True,
                            description="OIDC token for Vercel service",
                        )
                    ),
                    cast(ProviderEnvVars, *type(self).OPENAI.other_env_vars),
                )
            case Provider.TOGETHER:
                return (
                    ProviderEnvVars(
                        note="These variables are for the Together service.",
                        api_key=ProviderEnvVarInfo(
                            env="TOGETHER_API_KEY",
                            is_secret=True,
                            description="API key for Together service",
                        ),
                        other=httpx_env_vars,
                    ),
                    cast(ProviderEnvVars, *type(self).OPENAI.other_env_vars),
                )
            case Provider.HEROKU:
                return (
                    ProviderEnvVars(
                        note="These variables are for the Heroku service.",
                        api_key=ProviderEnvVarInfo(
                            env="INFERENCE_KEY",
                            is_secret=True,
                            description="API key for Heroku service",
                        ),
                        host=ProviderEnvVarInfo(
                            env="INFERENCE_URL", description="Host URL for Heroku service"
                        ),
                        other={
                            "model_id": ProviderEnvVarInfo(
                                env="INFERENCE_MODEL_ID", description="Model ID for Heroku service"
                            ),
                            **httpx_env_vars,
                        },
                    ),
                    cast(ProviderEnvVars, *type(self).OPENAI.other_env_vars),
                )
            case Provider.DEEPSEEK:
                return (
                    ProviderEnvVars(
                        note="These variables are for the DeepSeek service.",
                        api_key=ProviderEnvVarInfo(
                            env="DEEPSEEK_API_KEY",
                            is_secret=True,
                            description="API key for DeepSeek service",
                        ),
                        other=httpx_env_vars,
                    ),
                    cast(ProviderEnvVars, *type(self).OPENAI.other_env_vars),
                )
            case (
                Provider.OPENAI
                | Provider.FIREWORKS
                | Provider.GITHUB
                | Provider.X_AI
                | Provider.GROQ
                | Provider.MOONSHOT
                | Provider.OLLAMA
                | Provider.OPENROUTER
                | Provider.PERPLEXITY
                | Provider.CEREBRAS
            ):
                return (
                    ProviderEnvVars(
                        note="These variables are for any OpenAI-compatible service, including OpenAI itself, Azure OpenAI, and others -- any provider that we use the OpenAI client to connect to.",
                        api_key=ProviderEnvVarInfo(
                            env="OPENAI_API_KEY",
                            description="API key for OpenAI-compatible services (not necessarily an API key *for* OpenAI). The OpenAI client also requires an API key, even if you don't actually need one for your provider (like local Ollama). So provide a dummy key if needed.",
                            is_secret=True,
                        ),
                        log_level=ProviderEnvVarInfo(
                            env="OPENAI_LOG",
                            description="One of: 'debug', 'info', 'warning', 'error'",
                            choices={"debug", "info", "warning", "error"},
                        ),
                        other=httpx_env_vars,
                    ),
                )
            case Provider.HUGGINGFACE_INFERENCE:
                return (
                    ProviderEnvVars(
                        note="Hugging Face allows for setting many configuration options by environment variable. See [the Hugging Face documentation](https://huggingface.co/docs/huggingface_hub/package_reference/environment_variables) for more details.",
                        api_key=ProviderEnvVarInfo(
                            env="HF_TOKEN", description="API key/token for Hugging Face service"
                        ),
                        log_level=ProviderEnvVarInfo(
                            env="HF_HUB_VERBOSITY",
                            description="Log level for Hugging Face Hub client",
                            choices={"debug", "info", "warning", "error", "critical"},
                        ),
                        other=httpx_env_vars,
                    ),
                )
            case Provider.BEDROCK:
                return (
                    (
                        ProviderEnvVars(
                            note="AWS allows for setting many configuration options by environment variable. See [the AWS documentation](https://boto3.amazonaws.com/v1/documentation/api/latest/guide/configuration.html#using-environment-variables) for more details. Because AWS has multiple authentication methods, and ways to configure settings, we don't provide them here. We'd just confuse people. Unlike other providers, we also don't check for AWS's environment variables, we just assume you're authorized to do what you need to do.",
                            region=ProviderEnvVarInfo(
                                env="AWS_REGION",
                                description="AWS region for Bedrock service",
                                variable_name="region",
                            ),
                            account_id=ProviderEnvVarInfo(
                                env="AWS_ACCOUNT_ID",
                                description="AWS Account ID for Bedrock service",
                                variable_name="aws_account_id",
                            ),
                            api_key=ProviderEnvVarInfo(
                                env="AWS_SECRET_ACCESS_KEY",
                                description="AWS Secret Access Key for Bedrock service",
                                is_secret=True,
                                variable_name="aws_secret_access_key",
                            ),
                            other={
                                "aws_access_key_id": ProviderEnvVarInfo(
                                    env="AWS_ACCESS_KEY_ID",
                                    description="AWS Access Key ID for Bedrock service",
                                    is_secret=True,
                                    variable_name="aws_access_key_id",
                                )
                            },
                        )
                    ),
                )
            case Provider.COHERE:
                return (
                    ProviderEnvVars(
                        api_key=ProviderEnvVarInfo(
                            env="COHERE_API_KEY", description="Your Cohere API Key"
                        ),
                        host=ProviderEnvVarInfo(
                            env="CO_API_URL", description="Host URL for Cohere service"
                        ),
                        other=httpx_env_vars,
                    ),
                )
            case Provider.TAVILY:
                return (
                    ProviderEnvVars(
                        api_key=ProviderEnvVarInfo(
                            env="TAVILY_API_KEY", description="Your Tavily API Key"
                        ),
                        other=httpx_env_vars,
                    ),
                )
            case Provider.GOOGLE:
                return (
                    ProviderEnvVars(
                        api_key=ProviderEnvVarInfo(
                            env="GEMINI_API_KEY", description="Your Google Gemini API Key"
                        ),
                        other=httpx_env_vars,
                    ),
                    ProviderEnvVars(
                        api_key=ProviderEnvVarInfo(
                            env="GOOGLE_API_KEY", description="Your Google API Key"
                        )
                    ),
                )
            case Provider.MISTRAL:
                return (
                    ProviderEnvVars(
                        api_key=ProviderEnvVarInfo(
                            env="MISTRAL_API_KEY", description="Your Mistral API Key"
                        ),
                        other=httpx_env_vars,
                    ),
                )
            case _:
                return None

    @property
    def api_key_env_vars(self) -> tuple[str, ...] | None:
        """Get the environment variable names used for API keys by the provider's client that are not part of CodeWeaver's settings."""
        if envs := self.other_env_vars:
            return tuple(env["api_key"].env for env in envs if "api_key" in env)
        return None

    @property
    def always_local(self) -> bool:
        """Check if the provider is a local provider."""
        return self in {Provider.FASTEMBED, Provider.SENTENCE_TRANSFORMERS, Provider.MEMORY}

    @property
    def is_local_provider(self) -> bool:
        """Check if the provider can be used as a local provider."""
        return self.always_local or self in {Provider.OLLAMA, Provider.QDRANT}

    @property
    def is_cloud_provider(self) -> bool:
        """Check if the provider is a cloud provider."""
        return not self.always_local

    @property
    def always_cloud(self) -> bool:
        """Check if the provider is always a cloud provider."""
        return not self.is_local_provider

    @property
    def is_huggingface_model_provider(self) -> bool:
        """Check if the provider is a Hugging Face model provider."""
        return self in {
            Provider.CEREBRAS,
            Provider.FASTEMBED,
            Provider.FIREWORKS,
            Provider.GROQ,
            Provider.HUGGINGFACE_INFERENCE,
            Provider.LITELLM,
            Provider.OLLAMA,
            Provider.SENTENCE_TRANSFORMERS,
            Provider.TOGETHER,
        }

    @property
    def requires_auth(self) -> bool:
        """Check if the provider requires authentication."""
        return self not in {
            # Qdrant may not require auth -- we check for API key presence elsewhere
            Provider.FASTEMBED,
            Provider.MEMORY,
            Provider.DUCKDUCKGO,
            Provider.SENTENCE_TRANSFORMERS,
            # Ollama does for cloud, but generally people associate it as local
            Provider.OLLAMA,
        }

    @property
    def uses_openai_api(self) -> bool:
        """Check if the provider uses the OpenAI API."""
        return self in {
            Provider.AZURE,
            Provider.CEREBRAS,
            Provider.DEEPSEEK,
            Provider.FIREWORKS,
            Provider.GITHUB,
            Provider.GROQ,
            Provider.HEROKU,
            Provider.LITELLM,
            Provider.MOONSHOT,
            Provider.OLLAMA,
            Provider.OPENAI,
            Provider.OPENROUTER,
            Provider.PERPLEXITY,
            Provider.TOGETHER,
            Provider.VERCEL,
            Provider.X_AI,
        }

    @staticmethod
    def _flatten_envvars(env_vars: ProviderEnvVars) -> list[ProviderEnvVarInfo]:
        """Flatten a ProviderEnvVars TypedDict into a list of ProviderEnvVarInfo tuples."""
        found_vars: list[ProviderEnvVarInfo] = []
        for key, value in env_vars.items():
            if key not in ("note", "other") and isinstance(value, ProviderEnvVarInfo):
                found_vars.append(value)
            elif key == "other" and isinstance(value, dict) and value:
                found_vars.extend(iter(value.values()))
        return found_vars

    @classmethod
    def all_envs(cls) -> tuple[tuple[Provider, ProviderEnvVarInfo], ...]:
        """Get all environment variables used by all providers."""
        found_vars: list[tuple[Provider, ProviderEnvVarInfo]] = []
        for p in cls:
            if (v := p.other_env_vars) is not None and is_typeddict(v):
                # singleton
                found_vars.extend((p, var_info) for var_info in cls._flatten_envvars(v))
            if isinstance(v, tuple):
                for env_vars_dict in v:
                    if is_typeddict(env_vars_dict):
                        found_vars.extend(
                            (p, var_info) for var_info in cls._flatten_envvars(env_vars_dict)
                        )
        return tuple(found_vars)

    def is_embedding_provider(self) -> bool:
        """Check if the provider is an embedding provider."""
        from codeweaver.providers.capabilities import get_provider_kinds
        from codeweaver.providers.types import LiteralProvider

        return any(
            kind == ProviderKind.EMBEDDING
            for kind in get_provider_kinds(cast(LiteralProvider, self))
        )

    def is_sparse_provider(self) -> bool:
        """Check if the provider is a sparse embedding provider."""
        from codeweaver.providers.capabilities import get_provider_kinds
        from codeweaver.providers.types import LiteralProvider

        return ProviderKind.SPARSE_EMBEDDING in get_provider_kinds(cast(LiteralProvider, self))

    def is_reranking_provider(self) -> bool:
        """Check if the provider is a reranking provider."""
        from codeweaver.providers.capabilities import get_provider_kinds
        from codeweaver.providers.types import LiteralProvider

        return ProviderKind.RERANKING in get_provider_kinds(cast(LiteralProvider, self))

    def is_agent_provider(self) -> bool:
        """Check if the provider is an agent model provider."""
        from codeweaver.providers.capabilities import get_provider_kinds
        from codeweaver.providers.types import LiteralProvider

        return ProviderKind.AGENT in get_provider_kinds(cast(LiteralProvider, self))

    def is_data_provider(self) -> bool:
        """Check if the provider is a data provider."""
        from codeweaver.providers.capabilities import get_provider_kinds
        from codeweaver.providers.types import LiteralProvider

        return ProviderKind.DATA in get_provider_kinds(cast(LiteralProvider, self))

    def get_env_api_key(self) -> str | None:
        """Get the API key from environment variables, if set."""
        if env_vars := self.api_key_env_vars:
            for env_var in env_vars:
                if api_key := os.getenv(env_var):
                    return api_key
        return None

    @property
    def has_env_auth(self) -> bool:
        """Check if API key or TLS certs are set for the provider."""
        if self.other_env_vars:
            auth_vars = ("api_key", "tls_cert_path", "tls_key_path")
            for env_info in self.other_env_vars:
                for var in auth_vars:
                    if (env_var := env_info.get(var)) and (env := env_var.env) and os.getenv(env):
                        return True
        return False


class ProviderKind(BaseEnum):
    """Enumeration of available provider kinds."""

    DATA = "data"
    """Provider for data retrieval and processing (e.g. Tavily)"""
    EMBEDDING = "embedding"
    """Provider for text embedding (e.g. Voyage)"""
    SPARSE_EMBEDDING = "sparse_embedding"
    """Provider for sparse text embedding (traditional indexed search, more-or-less).

    Sparse embeddings tend to be fast and lightweight. We only support local providers (currently Fastembed and Sentence Transformers).
    While vector embeddings are more powerful and flexible, sparse embeddings can be a force multiplier that improves overall results when used in combination with vector embeddings.
    Our default vectorstore, Qdrant, supports storing multiple vectors on a "point", which allows you to combine sparse and dense embeddings in a single search.
    """
    RERANKING = "reranking"
    """Provider for re-ranking (e.g. Voyage)"""
    VECTOR_STORE = "vector-store"
    """Provider for vector storage (e.g. Qdrant)"""
    AGENT = "agent"
    """Provider for agents (e.g. OpenAI or Anthropic)"""

    UNSET = "unset"
    """A setting to identify when a `ProviderKind` is not set or configured."""


__all__ = ("Provider", "ProviderEnvVars", "ProviderKind")
