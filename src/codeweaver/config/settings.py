# sourcery skip: name-type-suffix, no-complex-if-expressions
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# We need to override our generic models with specific types, and type overrides for narrower values is a good thing.
# pyright: reportIncompatibleMethodOverride=false,reportIncompatibleVariableOverride=false
"""Unified configuration system for CodeWeaver.

Provides a centralized settings system using pydantic-settings with
clear precedence hierarchy and validation.
"""

from __future__ import annotations

import contextlib
import inspect
import logging
import os

from collections.abc import Callable
from importlib import util
from pathlib import Path
from typing import Annotated, Any, Literal, Self, Unpack, cast

from fastmcp.server.middleware import Middleware
from fastmcp.server.server import DuplicateBehavior
from fastmcp.tools.tool import Tool
from mcp.server.auth.settings import AuthSettings
from pydantic import (
    DirectoryPath,
    Field,
    FilePath,
    ImportString,
    PositiveInt,
    PrivateAttr,
    ValidationError,
    computed_field,
    field_validator,
)
from pydantic.fields import ComputedFieldInfo, FieldInfo
from pydantic_core import from_json
from pydantic_settings import (
    AWSSecretsManagerSettingsSource,
    AzureKeyVaultSettingsSource,
    BaseSettings,
    DotEnvSettingsSource,
    EnvSettingsSource,
    GoogleSecretManagerSettingsSource,
    JsonConfigSettingsSource,
    PydanticBaseSettingsSource,
    SecretsSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
    YamlConfigSettingsSource,
)

from codeweaver.common.utils.lazy_importer import lazy_import
from codeweaver.common.utils.utils import get_user_config_dir
from codeweaver.config.chunker import ChunkerSettings, DefaultChunkerSettings
from codeweaver.config.indexer import DefaultIndexerSettings, IndexerSettings
from codeweaver.config.logging import DefaultLoggingSettings, LoggingSettings
from codeweaver.config.mcp import CodeWeaverMCPConfig, MCPServerConfig
from codeweaver.config.middleware import (
    AVAILABLE_MIDDLEWARE,
    DefaultMiddlewareSettings,
    MiddlewareOptions,
)
from codeweaver.config.providers import AllDefaultProviderSettings, ProviderSettings
from codeweaver.config.server_defaults import (
    DefaultEndpointSettings,
    DefaultFastMcpServerSettings,
    DefaultUvicornSettings,
)
from codeweaver.config.telemetry import DefaultTelemetrySettings, TelemetrySettings
from codeweaver.config.types import (
    CodeWeaverSettingsDict,
    EndpointSettingsDict,
    UvicornServerSettings,
)
from codeweaver.core.types.aliases import FilteredKeyT
from codeweaver.core.types.dictview import DictView
from codeweaver.core.types.enum import AnonymityConversion
from codeweaver.core.types.models import BasedModel
from codeweaver.core.types.sentinel import UNSET, Unset


logger = logging.getLogger(__name__)


def _determine_setting(
    field_name: str, field_info: FieldInfo, obj: BaseSettings | BasedModel
) -> Any:
    """Determine the correct value for a setting field that was Unset."""
    if (
        isinstance(field_info.default, Unset)
        and hasattr(obj, "_defaults")
        and (defaults := obj._defaults() if callable(obj._defaults) else obj._defaults)  # type: ignore
        and (value := defaults.get(field_name))  # type: ignore
    ):
        return value  # type: ignore
    if (
        (annotation := field_info.annotation)
        and hasattr(annotation, "__args__")
        and (args := annotation.__args__)
        and (other_sources := tuple(arg for arg in args if arg is not Unset and arg is not None))
        and (other := other_sources[0])
    ):
        # Don't return class references - return None instead
        # This prevents TypedDict classes from being returned as values
        return None if inspect.isclass(other) else other
    return None


def _process_nested_value(value: Any) -> Any:
    """Process a nested value, ensuring all fields are set."""
    if isinstance(value, BaseSettings | BasedModel):
        return ensure_set_fields(value)
    if isinstance(value, list):
        return [
            ensure_set_fields(item) if isinstance(item, BaseSettings | BasedModel) else item
            for item in value
        ]
    if isinstance(value, dict):
        return {
            key: ensure_set_fields(item) if isinstance(item, BaseSettings | BasedModel) else item
            for key, item in value.items()
        }  # type: ignore
    return value


def _should_set_field(value: Any, field_type: Any) -> bool:
    """Check if a None value should be set for a field based on its type annotation."""
    if value is not None:
        return True
    if not field_type:
        return True
    args = getattr(field_type, "__args__", None)
    return type(None) in args if args else True


def ensure_set_fields(obj: BaseSettings | BasedModel) -> BaseSettings | BasedModel:
    """Ensure all fields in a pydantic model are set, replacing Unset with None where applicable."""
    for field_name in type(obj).model_fields:
        value = getattr(obj, field_name)

        if not isinstance(value, Unset):
            setattr(obj, field_name, _process_nested_value(value))
            continue

        # Handle Unset values
        field_info = type(obj).model_fields[field_name]
        new_value = _determine_setting(field_name, field_info, obj)

        # Handle class references - instantiate if it's a BaseSettings/BasedModel subclass
        if inspect.isclass(new_value) and issubclass(new_value, BaseSettings | BasedModel):
            new_value = ensure_set_fields(new_value())

        # Check if None is acceptable for this field
        field_type = field_info.annotation
        if not _should_set_field(new_value, field_type):
            continue

        setattr(obj, field_name, new_value)

    return obj


class FastMcpServerSettings(BasedModel):
    """Settings for the FastMCP server.

    These settings don't represent the complete set of FastMCP server settings, but the ones users can configure. The remaining settings, if changed, could break functionality or cause unexpected behavior.
    """

    transport: Annotated[
        Literal["stdio", "http", "streamable-http"] | None,
        Field(
            description="""Transport protocol to use for the FastMCP server. Stdio is for local use and cannot support concurrent requests. HTTP (streamable HTTP) can be used for local or remote use and supports concurrent requests. Unlike many MCP servers, CodeWeaver **defaults to http**."""
        ),
    ] = "http"
    host: Annotated[str | None, Field(description="""Host address for the FastMCP server.""")] = (
        "127.0.0.1"
    )
    port: Annotated[
        PositiveInt | None,
        Field(description="""Port number for the FastMCP server. Default is 9328 ('WEAV')"""),
    ] = 9328

    auth: Annotated[AuthSettings | None, Field(description="""OAuth provider configuration""")] = (
        None
    )
    on_duplicate_tools: DuplicateBehavior | None = None
    on_duplicate_resources: DuplicateBehavior | None = None
    on_duplicate_prompts: DuplicateBehavior | None = None
    resource_prefix_format: Literal["protocol", "path"] | None = None
    # these are each "middleware", "tools", and "dependencies" for FastMCP. But we prefix them with "additional_" to make it clear these are *in addition to* the ones we provide by default.
    additional_middleware: Annotated[
        list[ImportString[Middleware]] | None,
        Field(
            description="""Additional middleware to add to the FastMCP server. Values should be full path import strings, like `codeweaver.middleware.statistics.StatisticsMiddleware`.""",
            validation_alias="middleware",
            serialization_alias="middleware",
        ),
    ] = None
    additional_tools: Annotated[
        list[ImportString[Any]] | None,
        Field(
            description="""Additional tools to add to the FastMCP server. Values can be either full path import strings, like `codeweaver.agent_api.git.GitTool`, or just the tool name, like `GitTool`.""",
            validation_alias="tools",
            serialization_alias="tools",
        ),
    ] = None

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        from codeweaver.core.types import AnonymityConversion, FilteredKey

        return {
            FilteredKey("auth"): AnonymityConversion.BOOLEAN,
            FilteredKey("host"): AnonymityConversion.BOOLEAN,
            FilteredKey("port"): AnonymityConversion.BOOLEAN,
            FilteredKey("additional_middleware"): AnonymityConversion.COUNT,
            FilteredKey("additional_tools"): AnonymityConversion.COUNT,
        }

    @staticmethod
    def _attempt_import(suspected_path: str) -> Any | None:
        """Attempt to import a class or callable."""
        module_path, class_name = suspected_path.rsplit(".", 1)
        with contextlib.suppress(ImportError, AttributeError):
            module = __import__(module_path, fromlist=[class_name])
            cls = getattr(module, class_name, None)
            if cls and (inspect.isclass(cls) or callable(cls)):
                return cls
        return None

    @staticmethod
    def _dotted_name(obj: Any) -> str | None:
        """Return a stable 'module.qualname' for a class/callable/instance when possible."""
        with contextlib.suppress(ImportError, AttributeError):
            if inspect.isclass(obj) or inspect.isfunction(obj) or inspect.ismethod(obj):
                module = getattr(obj, "__module__", None)
                qual = getattr(obj, "__qualname__", None)
                if module and qual:
                    return f"{module}.{qual}"
            # Instance -> use its class
            cls_obj = getattr(obj, "__class__", None)
            module = getattr(cls_obj, "__module__", None)
            qual = getattr(cls_obj, "__qualname__", None)
            if module and qual:
                return f"{module}.{qual}"
        return None

    @classmethod
    def _callable_to_path(cls, value: Any, field: Literal["middleware", "tools"]) -> str | None:
        """Normalize middleware inputs (class/instance/callable/str) into 'module.qualname' strings."""
        if not value:
            return None
        if isinstance(value, str) and field == "tools":
            return value
        # Strings
        if isinstance(value, str) and field == "middleware":
            # If it matches a known middleware class name, expand to dotted path
            for mw in AVAILABLE_MIDDLEWARE:
                if value in (mw.__name__, mw.__qualname__, str(mw)):
                    return f"{mw.__module__}.{mw.__qualname__}"
            # If dotted import path, keep as-is
            return value
        # Known class/instance/callable
        if (isinstance(value, Middleware | Tool) or inspect.isclass(value) or callable(value)) and (
            dotted := cls._dotted_name(value)
        ):
            return dotted
        return None

    @classmethod
    @field_validator("additional_middleware", mode="before")
    def _validate_additional_middleware(cls, value: Any) -> list[str] | None:
        """Validate and normalize additional middleware inputs."""
        if value is None or isinstance(value, Unset):
            return None
        if isinstance(value, str | bytes | bytearray):
            try:
                value = from_json(value)
            except Exception:
                value = [value]
        return [s for s in (cls._callable_to_path(v, "middleware") for v in value) if s]

    @classmethod
    @field_validator("additional_tools", mode="before")
    def _validate_additional_tools(cls, value: Any) -> list[str] | None:
        """Validate and normalize additional tool inputs."""
        if value is None or isinstance(value, Unset):
            return None
        if isinstance(value, str | bytes | bytearray):
            try:
                value = from_json(value)
            except Exception:
                value = [value]
        return [s for s in (cls._callable_to_path(v, "tools") for v in value) if s]


_ = ProviderSettings.model_rebuild()


def _resolve_config_file() -> FilePath | None:
    """Resolve the configuration file path from environment variable, if set."""
    if (
        (env_var := os.environ.get("CODEWEAVER_CONFIG_FILE"))
        and (env_config := Path(env_var))
        and env_config.exists()
        and env_config.is_file()
    ):
        return env_config
    return None


class CodeWeaverSettings(BaseSettings):
    """Main configuration model following pydantic-settings patterns.

    Configuration precedence (highest to lowest):
    1. Environment variables (CODEWEAVER_*)
    2. Local config (codeweaver.local.toml (or .yaml, .yml, .json) in current directory)
    3. Project config (codeweaver.toml (or .yaml, .yml, .json) in project root)
    4. User config (~/codeweaver.toml (or .yaml, .yml, .json))
    5. Global config (/etc/codeweaver.toml (or .yaml, .yml, .json))
    6. Defaults

    # TODO: flatten the config structure. It's a bit too much when using env vars for nested models, particularly for provider settings.
    """

    model_config = SettingsConfigDict(
        case_sensitive=False,
        cli_kebab_case=True,
        extra="allow",  # Allow extra fields in the configuration for plugins/extensions
        field_title_generator=cast(
            Callable[[str, FieldInfo | ComputedFieldInfo], str],
            BasedModel.model_config["field_title_generator"],  # type: ignore
        ),
        nested_model_default_partial_update=True,
        from_attributes=True,
        env_ignore_empty=True,
        env_nested_delimiter="__",
        env_nested_max_split=-1,
        env_prefix="CODEWEAVER_",  # environment variables will be prefixed with CODEWEAVER_
        # keep secrets in user config dir
        str_strip_whitespace=True,
        title="CodeWeaver Settings",
        use_attribute_docstrings=True,
        use_enum_values=True,
        validate_assignment=True,
        populate_by_name=True,
        # spellchecker:off
        # NOTE: Config sources are set in `settings_customise_sources` method below
        # spellchecker:on
    )

    # Core settings
    project_path: Annotated[
        DirectoryPath | Unset,
        Field(
            description="""Root path of the codebase to analyze. CodeWeaver will try to detect the project root automatically if you don't provide one.""",
            validate_default=False,
        ),
    ] = UNSET

    project_name: Annotated[
        str | Unset,
        Field(
            description="""Project name (auto-detected from directory if None)""",
            validate_default=False,
        ),
    ] = UNSET

    provider: Annotated[
        ProviderSettings | Unset,
        Field(
            description="""Provider and model configurations for agents, data, embedding, reranking, sparse embedding, and vector store providers. Will default to default profile if not provided.""",
            validate_default=False,
        ),
    ] = UNSET

    config_file: Annotated[
        FilePath | None,
        Field(description="""Path to the configuration file, if any""", exclude=True),
    ] = _resolve_config_file()

    # Performance settings
    token_limit: Annotated[
        PositiveInt | Unset,
        Field(description="""Maximum tokens per response""", validate_default=False),
    ] = UNSET
    max_file_size: Annotated[
        PositiveInt | Unset,
        Field(description="""Maximum file size to process in bytes""", validate_default=False),
    ] = UNSET
    max_results: Annotated[
        PositiveInt | Unset,
        Field(
            description="""Maximum code matches to return. Because CodeWeaver primarily indexes ast-nodes, a page can return multiple matches per file, so this is not the same as the number of files returned. This is the maximum number of code matches returned in a single response.""",
            validate_default=False,
        ),
    ] = UNSET
    server: Annotated[
        FastMcpServerSettings | Unset,
        Field(
            description="""Optionally customize FastMCP server settings.""", validate_default=False
        ),
    ] = UNSET

    logging: Annotated[
        LoggingSettings | Unset,
        Field(description="""Logging configuration""", validate_default=False),
    ] = UNSET

    middleware: Annotated[
        MiddlewareOptions | Unset,
        Field(description="""Middleware settings""", validate_default=False),
    ] = UNSET

    indexer: Annotated[
        IndexerSettings | Unset,
        Field(description="""File filtering settings""", validate_default=False),
    ] = UNSET

    chunker: Annotated[
        ChunkerSettings | Unset,
        Field(description="""Chunker system configuration""", validate_default=False),
    ] = UNSET

    endpoints: Annotated[
        EndpointSettingsDict | Unset,
        Field(description="""Endpoint settings""", validate_default=False),
    ] = UNSET

    uvicorn: Annotated[
        UvicornServerSettings | Unset,
        Field(description="""Settings for the Uvicorn server""", validate_default=False),
    ] = UNSET

    telemetry: Annotated[
        TelemetrySettings | Unset,
        Field(description="""Telemetry configuration""", validate_default=False),
    ] = UNSET

    default_mcp_config: Annotated[
        MCPServerConfig | Unset,
        Field(
            description="""Default MCP server configuration for mcp clients. Setting this makes it quick and easy to add codeweaver to any mcp.json file using `codeweaver init`. Defaults to a streamable-http CodeWeaver server at `http://127.0.0.1:9328`. We strongly recommend using streamable-http instead of stdio for a better experience.""",
            validate_default=False,
        ),
    ] = UNSET

    __version__: Annotated[
        str,
        Field(
            description="""Schema version for CodeWeaver settings""",
            pattern=r"\d{1,2}\.\d{1,3}\.\d{1,3}",
        ),
    ] = "1.0.0"

    _map: Annotated[DictView[CodeWeaverSettingsDict] | None, PrivateAttr()] = None

    _unset_fields: Annotated[
        set[str], Field(description="Set of fields that were unset", exclude=True)
    ] = set()

    def model_post_init(self, __context: Any, /) -> None:
        """Post-initialization validation."""
        self._unset_fields = {
            field for field in type(self).model_fields if getattr(self, field) is Unset
        }
        self.project_path = (
            lazy_import("codeweaver.common.utils", "get_project_path")()
            if isinstance(self.project_path, Unset)
            else self.project_path
        )  # type: ignore
        self.project_name = (
            cast(DirectoryPath, self.project_path).name  # type: ignore
            if isinstance(self.project_name, Unset)
            else self.project_name  # type: ignore
        )
        self.provider = (
            ProviderSettings.model_validate(AllDefaultProviderSettings)
            if isinstance(self.provider, Unset) or self.provider is None
            else self.provider
        )
        # Serena uses 17,000 tokens *each turn*, so I feel like 30,000 is a reasonable default limit. We'll strive to keep it well under that.
        self.token_limit = 30_000 if isinstance(self.token_limit, Unset) else self.token_limit
        self.max_file_size = (
            1 * 1024 * 1024 if isinstance(self.max_file_size, Unset) else self.max_file_size
        )
        self.max_results = 75 if isinstance(self.max_results, Unset) else self.max_results
        self.server = (
            FastMcpServerSettings.model_validate(DefaultFastMcpServerSettings)
            if isinstance(self.server, Unset)
            else self.server
        )
        self.middleware = (
            DefaultMiddlewareSettings if isinstance(self.middleware, Unset) else self.middleware
        )
        self.logging = DefaultLoggingSettings if isinstance(self.logging, Unset) else self.logging
        # by default, IndexerSettings has `rignore_options` UNSET, but that needs to be deferred until after CodeWeaverSettings is initialized
        self.indexer = IndexerSettings() if isinstance(self.indexer, Unset) else self.indexer
        self.chunker = ChunkerSettings() if isinstance(self.chunker, Unset) else self.chunker
        self.telemetry = (
            TelemetrySettings._default()  # type: ignore
            if isinstance(self.telemetry, Unset)
            else self.telemetry
        )
        self.uvicorn = (
            UvicornServerSettings.model_validate(DefaultUvicornSettings)
            if isinstance(self.uvicorn, Unset)
            else self.uvicorn
        )
        self.endpoints = (
            DefaultEndpointSettings
            if isinstance(self.endpoints, Unset) or self.endpoints is None
            else DefaultEndpointSettings | self.endpoints
        )
        self.default_mcp_config = (
            CodeWeaverMCPConfig()
            if isinstance(self.default_mcp_config, Unset)
            else self.default_mcp_config
        )
        if not type(self).__pydantic_complete__:
            result = type(self).model_rebuild()
            logger.debug("Rebuilt CodeWeaverSettings during post-init, result: %s", result)
        if type(self).__pydantic_complete__:
            # Ensure all nested Unset values are replaced with defaults
            self = cast(CodeWeaverSettings, ensure_set_fields(self))
            # Exclude computed fields to prevent circular dependency during initialization
            # Computed fields like IndexingSettings.cache_dir may call get_settings()
            self._map = cast(
                DictView[CodeWeaverSettingsDict],
                DictView(self.model_dump(mode="python", exclude_computed_fields=True)),
            )
            globals()["_mapped_settings"] = self._map

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        from codeweaver.core.types import AnonymityConversion, FilteredKey

        return {
            FilteredKey("project_path"): AnonymityConversion.HASH,
            FilteredKey("project_name"): AnonymityConversion.BOOLEAN,
            FilteredKey("config_file"): AnonymityConversion.HASH,
        }

    @classmethod
    def _defaults(cls) -> CodeWeaverSettingsDict:
        """Get a default settings dictionary."""
        from codeweaver.common.utils import get_project_path

        path = get_project_path()
        return CodeWeaverSettingsDict(
            project_path=path or Path.cwd(),
            project_name=path.name,
            provider=AllDefaultProviderSettings,
            token_limit=30_000,
            max_file_size=1 * 1024 * 1024,
            max_results=75,
            server=DefaultFastMcpServerSettings,
            indexer=DefaultIndexerSettings,
            chunker=DefaultChunkerSettings,
            telemetry=DefaultTelemetrySettings,
            uvicorn=DefaultUvicornSettings,
            endpoints=DefaultEndpointSettings,
        )

    @classmethod
    def from_config(cls, path: FilePath, **kwargs: Unpack[CodeWeaverSettingsDict]) -> Self:
        """Create a CodeWeaverSettings instance from a configuration file.

        This is a convenience method for creating a settings instance from a specific config file. By default, CodeWeaverSettings will look for configuration files in standard locations (like codeweaver.toml in the project root). This method allows you to specify a particular config file to load settings from, primarily for testing or special use cases.
        """
        extension = path.suffix.lower()
        match extension:
            case ".json":
                cls.model_config["json_file"] = path
            case ".toml":
                cls.model_config["toml_file"] = path
            case ".yaml" | ".yml":
                cls.model_config["yaml_file"] = path
            case _:
                raise ValueError(f"Unsupported configuration file format: {extension}")
        from codeweaver.common.utils import get_project_path

        return cls(project_path=get_project_path(), **{**kwargs, "config_file": path})  # type: ignore

    @computed_field
    def project_root(self) -> Path:
        """Get the project root directory. Alias for `project_path`."""
        if isinstance(self.project_path, Unset):
            from codeweaver.common.utils.git import get_project_path

            self.project_path = get_project_path()
        return self.project_path.resolve()

    @classmethod  # spellchecker:off
    def settings_customise_sources(  # noqa: C901
        # spellchecker:on
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Customize the sources of settings for a specific settings class.

        Configuration precedence (highest to lowest):
        1. init_settings - Direct initialization arguments
        2. env_settings - Environment variables (CODEWEAVER_*)
        3. dotenv_settings - .env files:
            - .local.env,
            - .env
            - .codeweaver.local.env
            - .codeweaver.env
            - .codeweaver/.local.env
            - .codeweaver/.env
        4. In order of .toml, .yaml/.yml, .json files:
            - codeweaver.local.{toml,yaml,yml,json}
            - codeweaver.{toml,yaml,yml,json}
            - .codeweaver.local.{toml,yaml,yml,json}
            - .codeweaver.{toml,yaml,yml,json}
            - .codeweaver/codeweaver.local.{toml,yaml,yml,json}
            - .codeweaver/codeweaver.{toml,yaml,yml,json}
            - SYSTEM_USER_CONFIG_DIR/codeweaver/codeweaver.{toml,yaml,yml,json}
        5. file_secret_settings - Secret files SYSTEM_USER_CONFIG_DIR/codeweaver/secrets/
           (see https://docs.pydantic.dev/latest/concepts/pydantic_settings/#secrets for more info)
        6. If available and configured:
            - AWS Secrets Manager
            - Azure Key Vault
            - Google Secret Manager
        """
        config_files: list[PydanticBaseSettingsSource] = []
        user_config_dir = get_user_config_dir()
        secrets_dir = user_config_dir / "secrets"
        if not user_config_dir.exists():
            user_config_dir.mkdir(parents=True, exist_ok=True)
            user_config_dir.chmod(0o700)
        if not secrets_dir.exists():
            secrets_dir.mkdir(parents=True, exist_ok=True)
            secrets_dir.chmod(0o700)
        locations: list[str] = [
            "codeweaver.local",
            "codeweaver",
            ".codeweaver.local",
            ".codeweaver",
            ".codeweaver/codeweaver.local",
            ".codeweaver/codeweaver",
            f"{user_config_dir!s}/codeweaver",
        ]
        for _class in (
            TomlConfigSettingsSource,
            YamlConfigSettingsSource,
            JsonConfigSettingsSource,
        ):
            for loc in locations:
                ext = _class.__name__.split("ConfigSettingsSource")[0].lower()
                config_files.append(_class(settings_cls, Path(f"{loc}.{ext}")))
                if ext == "yaml":
                    config_files.append(_class(settings_cls, Path(f"{loc}.yml")))
        other_sources: list[PydanticBaseSettingsSource] = []
        if any(env for env in os.environ if env.startswith("AWS_SECRETS_MANAGER")):
            other_sources.append(
                AWSSecretsManagerSettingsSource(
                    settings_cls,
                    os.environ.get("AWS_SECRETS_MANAGER_SECRET_ID", ""),
                    os.environ.get("AWS_SECRETS_MANAGER_REGION", ""),
                    os.environ.get("AWS_SECRETS_MANAGER_ENDPOINT_URL", ""),
                )
            )
        if any(env for env in os.environ if env.startswith("AZURE_KEY_VAULT")) and util.find_spec(
            "azure.identity"
        ):
            try:
                from azure.identity import DefaultAzureCredential  # type: ignore

            except ImportError:
                logger.warning("Azure SDK not installed, skipping Azure Key Vault settings.")
            else:
                other_sources.append(
                    AzureKeyVaultSettingsSource(
                        settings_cls,
                        os.environ.get("AZURE_KEY_VAULT_URL", ""),
                        DefaultAzureCredential(),  # type: ignore
                    )
                )
        if any(
            env for env in os.environ if env.startswith("GOOGLE_SECRET_MANAGER")
        ) and util.find_spec("google.auth"):
            try:
                from google.auth import default  # type: ignore

            except ImportError:
                logger.warning(
                    "Google Cloud SDK not installed, skipping Google Secret Manager settings."
                )
            else:
                other_sources.append(
                    GoogleSecretManagerSettingsSource(
                        settings_cls,
                        default()[0],  # type: ignore
                        os.environ.get("GOOGLE_SECRET_MANAGER_PROJECT_ID", ""),
                    )
                )
        return (
            init_settings,
            EnvSettingsSource(
                settings_cls,
                env_prefix="CODEWEAVER_",
                case_sensitive=False,
                env_nested_delimiter="__",
                env_parse_enums=True,
                env_ignore_empty=True,
            ),
            DotEnvSettingsSource(
                settings_cls,
                env_file=(
                    ".local.env",
                    ".env",
                    ".codeweaver.local.env",
                    ".codeweaver.env",
                    ".codeweaver/.local.env",
                    ".codeweaver/.env",
                ),
                env_ignore_empty=True,
            ),
            *config_files,
            SecretsSettingsSource(
                settings_cls=settings_cls,
                secrets_dir=f"{user_config_dir}/secrets",
                env_ignore_empty=True,
            ),
            *other_sources,
        )

    def _update_settings(self, **kwargs: Unpack[CodeWeaverSettingsDict]) -> Self:
        """Update settings, validating a new CodeWeaverSettings instance and updating the global instance."""
        try:
            self.__init__(**kwargs)  # type: ignore # Unpack doesn't extend to nested dicts
        except ValidationError:
            logger.exception(
                "`CodeWeaverSettings` received invalid settings for an update. The settings failed to validate. We did not update the settings."
            )
            return self
        # The global _settings doesn't need updated because its reference didn't change
        # But we do need to update the global _mapped_settings because it's a copy
        # And other modules are using references to that copy
        globals()["_mapped_settings"] = self.view  # this recreates self._map as well
        return self

    @classmethod
    def reload(cls) -> Self:
        """Reloads settings from configuration sources.

        You can use this method to refresh the settings instance, re-reading configuration files and environment variables. This is useful if you expect configuration to change at runtime and want to apply those changes without restarting the application.
        """
        instance = globals().get("_settings")
        if instance is None:
            return cls()
        instance.__init__()
        return instance

    @property
    def view(self) -> DictView[CodeWeaverSettingsDict]:
        """Get a read-only mapping view of the settings."""
        if self._map is None or not self._map:
            try:
                self._map = DictView(self.model_dump(exclude_computed_fields=True))  # type: ignore
            except Exception:
                logger.exception("Failed to create settings map view")
                _ = type(self).model_rebuild()
                self._map = DictView(self.model_dump())  # type: ignore
        if not self._map:
            raise TypeError("Settings map view is not a valid DictView[CodeWeaverSettingsDict]")
        if unset_fields := tuple(
            field for field in type(self).model_fields if getattr(self, field) is Unset
        ):
            logger.warning("Some fields in CodeWeaverSettings are still unset: %s", unset_fields)
            self._unset_fields |= set(unset_fields)
            self = ensure_set_fields(self)
            self._map = DictView(self.model_dump(exclude_computed_fields=True))  # type: ignore
        return self._map  # type: ignore

    @classmethod
    def generate_default_config(cls, path: Path) -> None:
        """Generate a default configuration file at the specified path.

        The file format is determined by the file extension (.toml, .yaml/.yml, .json).
        """
        default_settings = cls()
        data = cls._to_serializable(default_settings, path=path)
        cls._write_config_file(path, data)

    @staticmethod
    def _to_serializable(
        obj: CodeWeaverSettings, path: Path | None = None, **override_kwargs: Any
    ) -> Any:
        """Convert an object to a serializable form."""
        from codeweaver.common.utils.git import get_project_path

        kwargs = {
            "indent": 4,
            "exclude_unset": True,
            "by_alias": True,
            "exclude_defaults": True,
            "round_trip": True,
            "exclude_computed_fields": True,
            "mode": "python",
        } | override_kwargs
        as_obj = obj.model_dump(**kwargs)  # type: ignore
        config_file = (
            path
            or obj.config_file
            or (
                obj.project_path
                if isinstance(obj.project_path, Path)
                else get_project_path() or Path.cwd()
            )
            / Path("codeweaver.toml")
        )
        extension = config_file.suffix.lower()
        match extension:
            case ".json":
                from pydantic_core import to_json

                data = to_json(
                    as_obj,
                    **{
                        k: v
                        for k, v in kwargs.items()
                        if k not in {"exclude_unset", "exclude_defaults", "exclude_computed_fields"}
                    },  # type: ignore
                ).decode("utf-8")
            case ".toml":
                import tomli_w

                data = tomli_w.dumps(as_obj)
            case ".yaml" | ".yml":
                import yaml

                data = yaml.dump(obj.model_dump())
            case _:
                raise ValueError(f"Unsupported configuration file format: {extension}")
        return data

    @staticmethod
    def _write_config_file(path: Path, data: str) -> None:
        """Write configuration data to a file."""
        path.parent.mkdir(parents=True, exist_ok=True)
        _ = path.write_text(data, encoding="utf-8")

    def save_to_file(self, path: Path | None = None) -> None:
        """Save the current settings to a configuration file.

        The file format is determined by the file extension (.toml, .yaml/.yml, .json).
        """
        path = path or self.config_file
        if path is None and isinstance(self.project_path, Path):
            path = self.project_path / "codeweaver.toml"
        if path is None:
            raise ValueError("No path provided to save configuration file.")
        extension = path.suffix.lower()
        # Use mode='json' to serialize Path objects to strings (needed for TOML/YAML)
        # model_dump kwargs (indent is NOT a valid model_dump parameter)
        dump_kwargs = {
            "exclude_unset": True,
            "by_alias": True,
            "exclude_defaults": True,
            "round_trip": True,
            "exclude_computed_fields": True,
            "mode": "json",  # Changed from "python" to handle Path serialization
            "exclude_none": True,  # Exclude None values for TOML compatibility
        }
        # JSON serialization kwargs (includes indent for to_json)
        json_kwargs = {"indent": 4, "round_trip": True}
        as_obj = self.model_dump(**dump_kwargs)  # type: ignore
        data: str
        match extension:
            case ".json":
                from pydantic_core import to_json

                data = to_json(as_obj, **json_kwargs).decode("utf-8")  # type: ignore
            case ".toml":
                import tomli_w

                data = tomli_w.dumps(as_obj)
            case ".yaml" | ".yml":
                import yaml

                data = yaml.dump(self.model_dump())
            case _:
                raise ValueError(f"Unsupported configuration file format: {extension}")
        _ = path.write_text(data, encoding="utf-8")


# Global settings instance
_settings: CodeWeaverSettings | None = None
"""The global settings instance. Use `get_settings()` to access it."""

_mapped_settings: DictView[CodeWeaverSettingsDict] | None = None
"""An immutable mapping view of the global settings instance. Use `get_settings_map()` to access it."""


def get_settings(config_file: FilePath | None = None) -> CodeWeaverSettings:
    """Get the global settings instance.

    This should not be your first choice for getting settings. For most needs, you should. Use get_settings_map() to get a read-only mapping view of the settings. This map is a *live view*, meaning it will update if the settings are updated.

    If you **really** need to get the mutable settings instance, you can use this function. It will create the global instance if it doesn't exist, optionally loading from a configuration file (like, codeweaver.toml) if you provide a path.
    """
    global _settings
    # Ensure chunker models are rebuilt before creating settings
    if not ChunkerSettings.__pydantic_complete__:
        ChunkerSettings._ensure_models_rebuilt()  # type: ignore

    # Rebuild CodeWeaverSettings if needed before instantiation
    if not CodeWeaverSettings.__pydantic_complete__:
        _ = CodeWeaverSettings.model_rebuild()
    if config_file and config_file.exists():
        _settings = CodeWeaverSettings(config_file=config_file)
    if _settings is None or isinstance(_settings, Unset):
        _settings = CodeWeaverSettings()  # type: ignore

    if isinstance(_settings.project_path, Unset):
        from codeweaver.common.utils import get_project_path

        _settings.project_path = get_project_path()
    if isinstance(_settings.project_name, Unset):
        _settings.project_name = _settings.project_path.name
    return _settings


def update_settings(**kwargs: CodeWeaverSettingsDict) -> DictView[CodeWeaverSettingsDict]:
    """Update the global settings instance.

    Returns a read-only mapping view of the updated settings.
    """
    global _settings
    if _settings is None:
        try:
            _settings = get_settings()
        except Exception:
            logger.exception("Failed to get settings: ")
            _ = CodeWeaverSettings.model_rebuild()
            _settings = get_settings()
    _settings = _settings._update_settings(**kwargs)  # type: ignore
    return _settings.view


def get_settings_map() -> DictView[CodeWeaverSettingsDict]:
    """Get a read-only mapping view of the global settings instance.

    Almost nothing in CodeWeaver should need to modify settings at runtime,
    so instead we distribute a live, read-only view of the global settings. It's thread-safe and will update if the settings are changed.
    """
    global _mapped_settings
    global _settings
    try:
        settings = _settings or get_settings()
    except Exception:
        logger.exception("Failed to get settings: ")
        _ = CodeWeaverSettings.model_rebuild()
        settings = get_settings()
    if _mapped_settings is None or _mapped_settings != settings.view:
        _mapped_settings = settings.view or (
            _mapped_settings or DictView(settings.model_dump(round_trip=True))
        )  # type: ignore
    if not _mapped_settings:
        raise TypeError("Mapped settings is not a valid DictView[CodeWeaverSettingsDict]")
    return _mapped_settings


def reset_settings() -> None:
    """Reload settings from configuration sources."""
    global _settings
    global _mapped_settings
    _settings = None
    _mapped_settings = None  # the mapping will be regenerated on next access


__all__ = (
    "CodeWeaverSettings",
    "FastMcpServerSettings",
    "get_settings",
    "get_settings_map",
    "reset_settings",
    "update_settings",
)
