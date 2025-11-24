"""Environment variables for codeweaver configuration."""

# sourcery skip:snake-case-variable-declarations
from typing import Literal, TypedDict

from codeweaver.core.types.dictview import DictView
from codeweaver.core.types.models import EnvFormat, EnvVarInfo


class SettingsEnvVars(TypedDict):
    """Environment variables for CodeWeaver settings."""

    CODEWEAVER_LOG_LEVEL: EnvVarInfo
    """Environment variable for setting the log level."""

    CODEWEAVER_PROJECT_PATH: EnvVarInfo
    """Environment variable for setting the project path."""

    CODEWEAVER_HOST: EnvVarInfo
    """Environment variable for setting the server host."""

    CODEWEAVER_PORT: EnvVarInfo
    """Environment variable for setting the server port."""

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

    CODEWEAVER__TELEMETRY__DISABLE_TELEMETRY: EnvVarInfo
    """Environment variable to disable telemetry data collection."""

    CODEWEAVER__TELEMETRY__TOOLS_OVER_PRIVACY: EnvVarInfo
    """Environment variable to opt-in to """


def _providers_for_kind(
    kind: Literal["embedding", "reranking", "sparse_embedding", "agent", "data", "vector_store"],
) -> set[str]:
    from codeweaver.providers.capabilities import PROVIDER_CAPABILITIES
    from codeweaver.providers.provider import ProviderKind

    kind = ProviderKind.from_string(kind)
    return {provider.variable for provider, caps in PROVIDER_CAPABILITIES.items() if kind in caps}


def _providers_for_kind_requiring_auth(
    kind: Literal["embedding", "reranking", "sparse_embedding", "agent", "data", "vector_store"],
) -> set[str]:
    from codeweaver.providers.capabilities import PROVIDER_CAPABILITIES
    from codeweaver.providers.provider import ProviderKind

    kind = ProviderKind.from_string(kind)
    return {
        provider.variable
        for provider, caps in PROVIDER_CAPABILITIES.items()
        if kind in caps and provider.requires_auth
    }


def as_cloud_string(provider_name: str) -> str:
    return f"{provider_name} (cloud only)"


def _auth_list_for_kind(
    kind: Literal["embedding", "reranking", "sparse_embedding", "agent", "data", "vector_store"],
) -> set[str]:
    return set(
        _providers_for_kind_requiring_auth(kind)
        | {as_cloud_string(p) for p in _maybe_requiring_auth(kind) if p}
    )


def _maybe_requiring_auth(
    kind: Literal["embedding", "reranking", "sparse_embedding", "agent", "data", "vector_store"],
) -> set[str]:
    from codeweaver.providers.capabilities import PROVIDER_CAPABILITIES
    from codeweaver.providers.provider import ProviderKind

    kind = ProviderKind.from_string(kind)
    return {
        provider.variable
        for provider, caps in PROVIDER_CAPABILITIES.items()
        if kind in caps and provider.is_cloud_provider and provider.is_local_provider
    }


def environment_variables() -> DictView[SettingsEnvVars]:
    """Get environment variables for CodeWeaver settings."""
    return DictView(
        SettingsEnvVars(
            CODEWEAVER_LOG_LEVEL=EnvVarInfo(
                env="CODEWEAVER_LOG_LEVEL",
                description="Set the log level for CodeWeaver (e.g., DEBUG, INFO, WARNING, ERROR).",
                is_required=False,
                is_secret=False,
                default="WARNING",
                variable_name="log_level",
                choices={"DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"},
            ),
            CODEWEAVER_PROJECT_PATH=EnvVarInfo(
                env="CODEWEAVER_PROJECT_PATH",
                description="Set the project path for CodeWeaver.",
                fmt=EnvFormat.FILEPATH,
                is_required=False,
                is_secret=False,
                variable_name="project_path",
            ),
            CODEWEAVER_HOST=EnvVarInfo(
                env="CODEWEAVER_HOST",
                description="Set the server host for CodeWeaver.",
                is_required=False,
                is_secret=False,
                default="localhost",
                variable_name="host",
            ),
            CODEWEAVER_PORT=EnvVarInfo(
                env="CODEWEAVER_PORT",
                description="Set the server port for CodeWeaver.",
                is_required=False,
                is_secret=False,
                fmt=EnvFormat.NUMBER,
                default="9328",
                variable_name="port",
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
            ),
            CODEWEAVER_PROFILE=EnvVarInfo(
                env="CODEWEAVER_PROFILE",
                description="Use a premade settings profile for CodeWeaver.",
                is_required=False,
                is_secret=False,
                variable_name="profile",
                choices={"recommended", "quickstart", "testing"},
            ),
            CODEWEAVER_CONFIG_FILE=EnvVarInfo(
                env="CODEWEAVER_CONFIG_FILE",
                description="Specify a custom config file path for CodeWeaver. Only needed if not using the default locations.",
                fmt=EnvFormat.FILEPATH,
                is_required=False,
                is_secret=False,
                variable_name="config_file",
            ),
            CODEWEAVER_VECTOR_STORE_PROVIDER=EnvVarInfo(
                env="CODEWEAVER_VECTOR_STORE_PROVIDER",
                description="Specify the vector store provider to use.",
                is_required=False,
                is_secret=False,
                default="qdrant",
                variable_name="provider",
                choices=_providers_for_kind("vector_store"),
            ),
            CODEWEAVER_VECTOR_STORE_URL=EnvVarInfo(
                env="CODEWEAVER_VECTOR_STORE_URL",
                description="Specify the URL for the vector store.",
                is_required=False,
                is_secret=False,
                default="http://localhost",
                variable_name="url",
            ),
            CODEWEAVER_VECTOR_STORE_PORT=EnvVarInfo(
                env="CODEWEAVER_VECTOR_STORE_PORT",
                description="Specify the port for the vector store.",
                is_required=False,
                is_secret=False,
                default="6333",
                variable_name="port",
            ),
            CODEWEAVER_VECTOR_STORE_API_KEY=EnvVarInfo(
                env="CODEWEAVER_VECTOR_STORE_API_KEY",
                description="Specify the API key for the vector store, if required.",
                is_required=False,
                is_secret=True,
                variable_name="api_key",
                choices=_auth_list_for_kind("vector_store"),
            ),
            CODEWEAVER_SPARSE_EMBEDDING_MODEL=EnvVarInfo(
                env="CODEWEAVER_SPARSE_EMBEDDING_MODEL",
                description="Specify the sparse embedding model to use.",
                is_required=False,
                is_secret=False,
                default="prithivida/Splade_pp_en_v1",
                variable_name="model",
            ),
            CODEWEAVER_SPARSE_EMBEDDING_PROVIDER=EnvVarInfo(
                env="CODEWEAVER_SPARSE_EMBEDDING_PROVIDER",
                description="Specify the sparse embedding provider to use.",
                is_required=False,
                is_secret=False,
                default="fastembed",
                variable_name="provider",
                choices=_providers_for_kind("sparse_embedding"),
            ),
            CODEWEAVER_EMBEDDING_PROVIDER=EnvVarInfo(
                env="CODEWEAVER_EMBEDDING_PROVIDER",
                description="Specify the embedding provider to use.",
                is_required=False,
                is_secret=False,
                default="voyage",
                variable_name="provider",
                choices=_providers_for_kind("embedding"),
            ),
            CODEWEAVER_EMBEDDING_MODEL=EnvVarInfo(
                env="CODEWEAVER_EMBEDDING_MODEL",
                description="Specify the embedding model to use.",
                is_required=False,
                is_secret=False,
                default="voyage-code-3",
                variable_name="model",
            ),
            CODEWEAVER_EMBEDDING_API_KEY=EnvVarInfo(
                env="CODEWEAVER_EMBEDDING_API_KEY",
                description="Specify the API key for the embedding provider, if required. Note: {', '.join([p for p in _providers_for_kind('embedding') if p.])}",
                is_required=False,
                is_secret=True,
                variable_name="api_key",
                choices=_auth_list_for_kind("embedding"),
            ),
            CODEWEAVER_RERANKING_PROVIDER=EnvVarInfo(
                env="CODEWEAVER_RERANKING_PROVIDER",
                description="Specify the reranking provider to use.",
                is_required=False,
                is_secret=False,
                default="voyage",
                variable_name="provider",
                choices=_providers_for_kind("reranking"),
            ),
            CODEWEAVER_RERANKING_MODEL=EnvVarInfo(
                env="CODEWEAVER_RERANKING_MODEL",
                description="Specify the reranking model to use.",
                is_required=False,
                is_secret=False,
                default="rerank-2.5",
                variable_name="model",
            ),
            CODEWEAVER_RERANKING_API_KEY=EnvVarInfo(
                env="CODEWEAVER_RERANKING_API_KEY",
                description="Specify the API key for the reranking provider, if required.",
                is_required=False,
                is_secret=True,
                variable_name="api_key",
                choices=_auth_list_for_kind("reranking"),
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
            ),
        )
    )


__all__ = ("SettingsEnvVars", "environment_variables")
