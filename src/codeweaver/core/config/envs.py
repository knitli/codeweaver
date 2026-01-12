# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Environment variables for codeweaver configuration."""

from __future__ import annotations

# sourcery skip:snake-case-variable-declarations
import os

from types import MappingProxyType
from typing import Literal, TypedDict, get_args

from pydantic import AnyUrl, SecretStr
from pydantic.dataclasses import asdict, dataclass

from codeweaver.core.config.loader import detect_root_package
from codeweaver.core.types import (
    DataclassSerializationMixin,
    DictView,
    EnvFormat,
    EnvVarInfo,
    LiteralProviderKindType,
    Provider,
)


@dataclass
class SettingsEnvVars(DataclassSerializationMixin):
    """Environment variables for CodeWeaver settings."""

    CODEWEAVER_LOG_LEVEL: EnvVarInfo
    """Environment variable for setting the log level."""

    CODEWEAVER_PROJECT_NAME: EnvVarInfo
    """Environment variable for setting the project name."""

    CODEWEAVER_PROJECT_PATH: EnvVarInfo
    """Environment variable for setting the project path."""

    CODEWEAVER_HOST: EnvVarInfo
    """Environment variable for setting the server host."""

    CODEWEAVER_PORT: EnvVarInfo
    """Environment variable for setting the server port."""

    CODEWEAVER_MCP_PORT: EnvVarInfo
    """Environment variable for setting the MCP server port."""

    CODEWEAVER_DEBUG: EnvVarInfo
    """Environment variable for enabling debug mode."""

    CODEWEAVER_PROFILE: EnvVarInfo
    """Environment variable for using a premade settings profile."""

    CODEWEAVER_CONFIG_FILE: EnvVarInfo
    """Environment variable for specifying a custom config file path."""

    CODEWEAVER_VECTOR_STORE_PROVIDER: EnvVarInfo
    """Environment variable for specifying the vector store to use."""

    CODEWEAVER_VECTOR_STORE_URL: EnvVarInfo
    """Environment variable for specifying the URL for the vector store."""

    CODEWEAVER_VECTOR_STORE_PORT: EnvVarInfo
    """Environment variable for specifying the port for the vector store."""

    CODEWEAVER_VECTOR_STORE_API_KEY: EnvVarInfo
    """Environment variable for specifying the API key for the vector store."""

    CODEWEAVER_SPARSE_EMBEDDING_MODEL: EnvVarInfo
    """Environment variable for specifying the sparse embedding model to use."""

    CODEWEAVER_SPARSE_EMBEDDING_PROVIDER: EnvVarInfo
    """Environment variable for specifying the sparse embedding provider to use."""

    CODEWEAVER_EMBEDDING_PROVIDER: EnvVarInfo
    """Environment variable for specifying the embedding provider to use."""

    CODEWEAVER_EMBEDDING_MODEL: EnvVarInfo
    """Environment variable for specifying the embedding model to use."""

    CODEWEAVER_EMBEDDING_API_KEY: EnvVarInfo
    """Environment variable for specifying the API key for the embedding provider."""

    CODEWEAVER_RERANKING_PROVIDER: EnvVarInfo
    """Environment variable for specifying the reranking provider to use."""

    CODEWEAVER_RERANKING_MODEL: EnvVarInfo
    """Environment variable for specifying the reranking model to use."""

    CODEWEAVER_RERANKING_API_KEY: EnvVarInfo
    """Environment variable for specifying the API key for the reranking provider."""

    CODEWEAVER_AGENT_PROVIDER: EnvVarInfo
    """Environment variable for specifying the agent provider to use."""

    CODEWEAVER_AGENT_MODEL: EnvVarInfo
    """Environment variable for specifying the agent model to use."""

    CODEWEAVER_AGENT_API_KEY: EnvVarInfo
    """Environment variable for specifying the API key for the agent provider."""

    CODEWEAVER_DATA_PROVIDERS: EnvVarInfo
    """Environment variable for specifying data providers. API keys, if required, must be set using the provider's specific environment variable, such as `TAVILY_API_KEY` for the TAVILY provider."""

    CODEWEAVER__TELEMETRY__DISABLE_TELEMETRY: EnvVarInfo
    """Environment variable to disable telemetry data collection."""

    CODEWEAVER__TELEMETRY__TOOLS_OVER_PRIVACY: EnvVarInfo
    """Environment variable to opt-in to providing more detailed search and query data for telemetry. This may include potentially identifying information that we will try to anonymize but can't garauntee complete privacy."""

    CODEWEAVER_DISABLE_BACKUP_SYSTEM: EnvVarInfo
    """Environment variable to disable CodeWeaver's failsafe/backup system. Not recommended if you want to ever use CodeWeaver offline or when a cloud provider is unreachable. The backup system uses extremely lightweight local models to provide basic functionality when your main provider is unavailable (well, it is still probably better than most alternatives)."""

    def __post_init__(self) -> None:
        """Post-initialization to validate default values."""
        self.register_values()

    @classmethod
    def from_defaults(cls) -> SettingsEnvVars:
        """Create SettingsEnvVars with built-in defaults."""
        return cls(
            CODEWEAVER_LOG_LEVEL=EnvVarInfo(
                env="CODEWEAVER_LOG_LEVEL",
                description="Set the log level for CodeWeaver (e.g., DEBUG, INFO, WARNING, ERROR).",
                is_required=False,
                is_secret=False,
                default="WARNING",
                variable_name="log_level",
                choices={"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"},
                resolver_key="logging.level",
            ),
            CODEWEAVER_PROJECT_PATH=EnvVarInfo(
                env="CODEWEAVER_PROJECT_PATH",
                description="Set the project path for CodeWeaver.",
                fmt=EnvFormat.FILEPATH,
                is_required=False,
                is_secret=False,
                variable_name="project_path",
                resolver_key="project_path",
            ),
            CODEWEAVER_PROJECT_NAME=EnvVarInfo(
                env="CODEWEAVER_PROJECT_NAME",
                description="Set the project name for CodeWeaver.",
                is_required=False,
                is_secret=False,
                variable_name="project_name",
                resolver_key="project_name",
            ),
            CODEWEAVER_HOST=EnvVarInfo(
                env="CODEWEAVER_HOST",
                description="Set the server host for CodeWeaver.",
                is_required=False,
                is_secret=False,
                default="localhost",
                variable_name="management_host",
                resolver_key="management_host",
                available_with="server",
            ),
            CODEWEAVER_PORT=EnvVarInfo(
                env="CODEWEAVER_PORT",
                description="Set the port for the codeweaver management server (information and management endpoints).",
                is_required=False,
                is_secret=False,
                fmt=EnvFormat.NUMBER,
                default="9329",
                variable_name="management_port",
                resolver_key="management_port",
                available_with="server",
            ),
            CODEWEAVER_MCP_PORT=EnvVarInfo(
                env="CODEWEAVER_MCP_PORT",
                description="Set the MCP server port for CodeWeaver if using http transport for mcp. Not required if using the default port (9328), or stdio transport.",
                is_required=False,
                is_secret=False,
                fmt=EnvFormat.NUMBER,
                default="9328",
                variable_name="mcp_port",
                resolver_key="server.run_args.port",
                available_with="server",
            ),
            CODEWEAVER_DEBUG=EnvVarInfo(
                env="CODEWEAVER_DEBUG",
                description="Enable debug mode for CodeWeaver.",
                is_required=False,
                is_secret=False,
                default="false",
                fmt=EnvFormat.BOOLEAN,
                variable_name="debug",
                choices={"true", "false"},
                resolver_key="debug",
            ),
            CODEWEAVER_PROFILE=EnvVarInfo(
                env="CODEWEAVER_PROFILE",
                description="Use a premade provider settings profile for CodeWeaver.",
                is_required=False,
                is_secret=False,
                variable_name="profile",
                choices={"recommended", "quickstart", "testing"},
                resolver_key="profile",
                available_with="providers",
            ),
            CODEWEAVER_CONFIG_FILE=EnvVarInfo(
                env="CODEWEAVER_CONFIG_FILE",
                description="Specify a custom config file path for CodeWeaver. Only needed if not using the default locations.",
                fmt=EnvFormat.FILEPATH,
                is_required=False,
                is_secret=False,
                variable_name="config_file",
                resolver_key="config_file",
            ),
            CODEWEAVER_VECTOR_STORE_PROVIDER=EnvVarInfo(
                env="CODEWEAVER_VECTOR_STORE_PROVIDER",
                description="Specify the vector store provider to use.",
                is_required=False,
                is_secret=False,
                default="qdrant",
                variable_name="provider",
                choices=_providers_for_kind("vector_store"),
                resolver_key="primary.vector_store.provider",
                available_with="providers",
            ),
            CODEWEAVER_VECTOR_STORE_URL=EnvVarInfo(
                env="CODEWEAVER_VECTOR_STORE_URL",
                description="Specify the URL for the vector store.",
                is_required=False,
                is_secret=False,
                default="http://localhost",
                variable_name="url",
                resolver_key="primary.vector_store.url",
                available_with="providers",
            ),
            CODEWEAVER_VECTOR_STORE_PORT=EnvVarInfo(
                env="CODEWEAVER_VECTOR_STORE_PORT",
                description="Specify the port for the vector store.",
                is_required=False,
                is_secret=False,
                default="6333",
                variable_name="port",
                resolver_key="primary.vector_store.port",
                available_with="providers",
            ),
            CODEWEAVER_VECTOR_STORE_API_KEY=EnvVarInfo(
                env="CODEWEAVER_VECTOR_STORE_API_KEY",
                description="Specify the API key for the vector store, if required.",
                is_required=False,
                is_secret=True,
                variable_name="api_key",
                choices=_auth_list_for_kind("vector_store"),
                resolver_key="primary.vector_store.api_key",
                available_with="providers",
            ),
            CODEWEAVER_SPARSE_EMBEDDING_MODEL=EnvVarInfo(
                env="CODEWEAVER_SPARSE_EMBEDDING_MODEL",
                description="Specify the sparse embedding model to use.",
                is_required=False,
                is_secret=False,
                default="prithivida/Splade_pp_en_v1",
                variable_name="model",
                resolver_key="primary.sparse_primary.embedding.model_name",
                available_with="providers",
            ),
            CODEWEAVER_SPARSE_EMBEDDING_PROVIDER=EnvVarInfo(
                env="CODEWEAVER_SPARSE_EMBEDDING_PROVIDER",
                description="Specify the sparse embedding provider to use.",
                is_required=False,
                is_secret=False,
                default="fastembed",
                variable_name="provider",
                choices=_providers_for_kind("sparse_embedding"),
                resolver_key="primary.sparse_embedding.provider",
                available_with="providers",
            ),
            CODEWEAVER_EMBEDDING_PROVIDER=EnvVarInfo(
                env="CODEWEAVER_EMBEDDING_PROVIDER",
                description="Specify the embedding provider to use.",
                is_required=False,
                is_secret=False,
                default="voyage",
                variable_name="provider",
                choices=_providers_for_kind("embedding"),
                resolver_key="primary.embedding.provider",
                available_with="providers",
            ),
            CODEWEAVER_EMBEDDING_MODEL=EnvVarInfo(
                env="CODEWEAVER_EMBEDDING_MODEL",
                description="Specify the embedding model to use.",
                is_required=False,
                is_secret=False,
                default="voyage-code-3",
                variable_name="model",
                resolver_key="primary.primary.embedding.model_name",
                available_with="providers",
            ),
            CODEWEAVER_EMBEDDING_API_KEY=EnvVarInfo(
                env="CODEWEAVER_EMBEDDING_API_KEY",
                description="Specify the API key for the embedding provider, if required. Note: Ollama may require an API key if using their cloud services.",
                is_required=False,
                is_secret=True,
                variable_name="api_key",
                choices=_auth_list_for_kind("embedding"),
                resolver_key="primary.embedding.api_key",
                available_with="providers",
            ),
            CODEWEAVER_RERANKING_PROVIDER=EnvVarInfo(
                env="CODEWEAVER_RERANKING_PROVIDER",
                description="Specify the reranking provider to use.",
                is_required=False,
                is_secret=False,
                default="voyage",
                variable_name="provider",
                choices=_providers_for_kind("reranking"),
                resolver_key="primary.reranking.provider",
                available_with="providers",
            ),
            CODEWEAVER_RERANKING_MODEL=EnvVarInfo(
                env="CODEWEAVER_RERANKING_MODEL",
                description="Specify the reranking model to use.",
                is_required=False,
                is_secret=False,
                default="rerank-2.5",
                variable_name="model",
                resolver_key="primary.reranking.model_name",
                available_with="providers",
            ),
            CODEWEAVER_RERANKING_API_KEY=EnvVarInfo(
                env="CODEWEAVER_RERANKING_API_KEY",
                description="Specify the API key for the reranking provider, if required.",
                is_required=False,
                is_secret=True,
                variable_name="api_key",
                choices=_auth_list_for_kind("reranking"),
                resolver_key="primary.reranking.api_key",
                available_with="providers",
            ),
            CODEWEAVER_AGENT_PROVIDER=EnvVarInfo(
                env="CODEWEAVER_AGENT_PROVIDER",
                description="Specify the agent provider to use.",
                is_required=False,
                is_secret=False,
                default="anthropic",
                variable_name="provider",
                choices=_providers_for_kind("agent"),
                resolver_key="primary.agent.provider",
                available_with="providers",
            ),
            CODEWEAVER_AGENT_MODEL=EnvVarInfo(
                env="CODEWEAVER_AGENT_MODEL",
                description="Specify the agent model to use. Provide the model name as you would to the provider directly -- check the provider's documentation.",
                is_required=False,
                is_secret=False,
                default="claude-haiku-4.5-latest",
                variable_name="model",
                resolver_key="primary.agent.model_name",
                available_with="providers",
            ),
            CODEWEAVER_AGENT_API_KEY=EnvVarInfo(
                env="CODEWEAVER_AGENT_API_KEY",
                description="Specify the API key for the agent provider, if required. Note: Ollama uses the `openai` client, which requires an API key. If you're using Ollama locally, you need to set this, but it can be to anything -- like `madeup-key`.",
                is_required=False,
                is_secret=True,
                variable_name="api_key",
                choices=_auth_list_for_kind("agent"),
                resolver_key="primary.agent.api_key",
                available_with="providers",
            ),
            CODEWEAVER_DATA_PROVIDERS=EnvVarInfo(
                env="CODEWEAVER_DATA_PROVIDERS",
                description="Specify data providers to use, separated by commas. API keys, if required, must be set using the provider's specific environment variable, such as `TAVILY_API_KEY` for the TAVILY provider.",
                is_required=False,
                is_secret=False,
                default="tavily",
                choices=_providers_for_kind("data"),
                available_with="providers",
                resolver_key="data.providers",
            ),
            CODEWEAVER__TELEMETRY__DISABLE_TELEMETRY=EnvVarInfo(
                env="CODEWEAVER__TELEMETRY__DISABLE_TELEMETRY",
                description="Disable telemetry data collection.",
                is_required=False,
                is_secret=False,
                fmt=EnvFormat.BOOLEAN,
                default="false",
                variable_name="disable_telemetry",
                choices={"true", "false"},
                resolver_key="telemetry.disable_telemetry",
            ),
            CODEWEAVER__TELEMETRY__TOOLS_OVER_PRIVACY=EnvVarInfo(
                env="CODEWEAVER__TELEMETRY__TOOLS_OVER_PRIVACY",
                description="Opt-in to potentially identifying collection of query and search result data. This is invaluable for helping us improve CodeWeaver's search capabilities. If privacy is a higher priority, do not enable this setting.",
                is_required=False,
                is_secret=False,
                fmt=EnvFormat.BOOLEAN,
                default="false",
                variable_name="tools_over_privacy",
                choices={"true", "false"},
                resolver_key="telemetry.tools_over_privacy",
            ),
            CODEWEAVER_DISABLE_BACKUP_SYSTEM=EnvVarInfo(
                env="CODEWEAVER_DISABLE_BACKUP_SYSTEM",
                description="Disable CodeWeaver's failsafe/backup system. Not recommended if you want to ever use CodeWeaver offline or when a cloud provider is unreachable. The backup system uses extremely lightweight local models to provide basic functionality when your main provider is unavailable (well, it is still probably better than most alternatives).",
                is_required=False,
                is_secret=False,
                fmt=EnvFormat.BOOLEAN,
                default="false",
                variable_name="disable_backup_system",
                choices={"true", "false"},
                resolver_key="provider.disable_backup_system",
            ),
        )

    def resolved_values(self) -> dict[str, str | None]:
        """Get resolved environment variable values."""
        mapped_self = {
            k: v for k, v in asdict(self).items() if detect_root_package() == v.available_with
        }
        return {
            key: resolved_value
            if (resolved_value := os.getenv(var_info.env)) is not None
            else var_info.default
            for key, var_info in mapped_self.items()
            if var_info.env in os.environ
        }

    def register_values(self) -> None:
        """Register the environment variables in the OS environment."""
        from codeweaver.core.config.registry import (
            create_configuration_value,
            register_configurable,
        )

        if resolved := self.resolved_values():
            for key, value in resolved.items():
                info = getattr(self, key)
                register_configurable(
                    create_configuration_value(
                        resolver_key=info.resolver_key,
                        value=value,
                        source="env",
                        tagged=info.resolver_key.startswith("primary."),
                    )
                )


def _providers_for_kind(kind: LiteralProviderKindType) -> set[str]:

    return {provider.variable for provider in Provider if provider.has_capability(kind)}


def _providers_for_kind_requiring_auth(kind: LiteralProviderKindType) -> set[str]:

    return {
        provider.variable
        for provider in Provider
        if provider.has_capability(kind) and provider.requires_auth
    }


def as_cloud_string(provider_name: str) -> str:
    return f"{provider_name} (cloud only)"


def _auth_list_for_kind(kind: LiteralProviderKindType) -> set[str]:
    return set(
        _providers_for_kind_requiring_auth(kind)
        | {as_cloud_string(p) for p in _maybe_requiring_auth(kind) if p}
    )


def _maybe_requiring_auth(kind: LiteralProviderKindType) -> set[str]:

    return {
        provider.variable
        for provider in Provider
        if provider.has_capability(kind) and provider.is_cloud_provider
    }


def environment_variables() -> DictView[SettingsEnvVars]:  # ty:ignore[invalid-type-arguments]
    """Get environment variables for CodeWeaver settings."""
    return DictView(asdict(SettingsEnvVars))


type ProviderField = Literal["embedding", "reranking", "sparse_embedding", "vector_store"]
type ProviderKey = Literal["provider", "model", "api_key", "url", "host", "port"]


class SetProviderEnvVarsDict(TypedDict):
    """Dictionary of provider environment variables."""

    provider: Provider | None
    model: str | None
    api_key: SecretStr | None
    url: AnyUrl | None
    host: str | None
    port: int | None


def get_provider_vars() -> MappingProxyType[ProviderField, SetProviderEnvVarsDict]:
    """Get all environment variable names related to providers."""
    provider_keys = get_args(ProviderKey)
    env_vars = {
        var_info.env
        for var_info in environment_variables().values()
        if any(
            k
            for k in provider_keys
            if k.upper() in var_info.env
            and not any(x for x in {"AGENT", "DATA"} if x in var_info.env)
        )
    }
    env_map: dict[ProviderField, SetProviderEnvVarsDict] = dict.fromkeys(  # ty: ignore[invalid-assignment]
        ("embedding", "reranking", "sparse_embedding", "vector_store"), None
    )
    for env_var in env_vars:
        kind = next(k for k in provider_keys if k.upper() in env_var)
        if env_map[kind] is None:
            env_map[kind] = {}  # ty: ignore[invalid-assignment]
        if value := os.environ.get(env_var):
            if "API_KEY" in env_var:
                env_map[kind]["api_key"] = SecretStr(value)
            elif env_var.endswith("PROVIDER"):
                from codeweaver.core import Provider

                env_map[kind]["provider"] = Provider.from_string(value)
            elif "PORT" in env_var:
                env_map[kind]["port"] = int(value)
            elif "URL" in env_var:
                env_map[kind]["url"] = AnyUrl(value)
            else:
                env_map[kind][next(k for k in provider_keys if k.upper() in env_var.lower())] = (
                    value
                )
    return MappingProxyType(env_map)


__all__ = (
    "SettingsEnvVars",
    "environment_variables",
    "get_provider_vars",
    "get_skeleton_provider_dict",
)
