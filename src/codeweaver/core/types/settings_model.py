# sourcery skip: lambdas-should-be-short
# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Base settings model for CodeWeaver using Pydantic Settings."""

from __future__ import annotations

import abc
import importlib
import logging
import os

from collections.abc import Iterator
from dataclasses import asdict
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Annotated, Any, ClassVar, Literal, Self, cast

from pydantic import BaseModel, DirectoryPath, Field, FilePath, HttpUrl, PrivateAttr, computed_field
from pydantic_core import to_json
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

from codeweaver.core.config._logging import DefaultLoggingSettings, LoggingSettingsDict
from codeweaver.core.config.telemetry import DefaultTelemetrySettings, TelemetrySettings
from codeweaver.core.exceptions import ValidationError
from codeweaver.core.types.aliases import FilteredKey, FilteredKeyT, LiteralStringT
from codeweaver.core.types.dictview import DictView
from codeweaver.core.types.enum import AnonymityConversion
from codeweaver.core.types.sentinel import UNSET, Unset
from codeweaver.core.types.utils import (
    clean_sentinel_from_schema,
    generate_field_title,
    generate_title,
)
from codeweaver.core.utils.checks import is_test_environment
from codeweaver.core.utils.filesystem import get_project_path, get_user_config_dir


if TYPE_CHECKING:
    from codeweaver.core.config.types import CodeWeaverSettingsDict


SCHEMA_VERSION = "1.2.0"


SUPPORTED_CONFIG_FILE_EXTENSIONS = MappingProxyType({
    TomlConfigSettingsSource: ".toml",
    YamlConfigSettingsSource: (".yaml", ".yml"),
    JsonConfigSettingsSource: ".json",
})

logger = logging.getLogger(__name__)

CODEWEAVER_SETTINGS_AVAILABLE = importlib.util.find_spec("codeweaver.server") is not None


def _get_user_config_dir() -> Path:
    """Get the user configuration directory for CodeWeaver."""
    return get_user_config_dir()


_BASE_TEST_PATHS = (
    "codeweaver.test.local",
    "codeweaver.test",
    ".codeweaver.test.local",
    ".codeweaver.test",
    "codeweaver/codeweaver.test.local",
    "codeweaver/codeweaver.test",
    "codeweaver/config.test.local",
    "codeweaver/config.test",
    ".codeweaver/codeweaver.test.local",
    ".codeweaver/codeweaver.test",
    ".config/codeweaver/test.local",
    ".config/codeweaver/test",
    ".config/codeweaver/config.test.local",
    ".config/codeweaver/config.test",
    ".config/codeweaver/codeweaver.test.local",
    ".config/codeweaver/codeweaver.test",
)

_BASE_PROD_PATHS = (
    "codeweaver.local",
    "codeweaver",
    ".codeweaver.local",
    ".codeweaver",
    "codeweaver/codeweaver.local",
    "codeweaver/config.local",
    "codeweaver/codeweaver",
    "codeweaver/config",
    ".codeweaver/codeweaver.local",
    ".codeweaver/config.local",
    ".codeweaver/codeweaver",
    ".codeweaver/config",
    ".config/codeweaver/codeweaver.local",
    ".config/codeweaver/codeweaver",
    ".config/codeweaver/config.local",
    ".config/codeweaver/config",
)
_USER_PROD_PATHS = (f"{_get_user_config_dir()!s}/codeweaver", f"{_get_user_config_dir()!s}/config")

_DOTENV_PATHS = (
    ".local.env",
    ".env",
    ".codeweaver.local.env",
    ".codeweaver.env",
    ".codeweaver/.local.env",
    ".codeweaver/.env",
    ".config/codeweaver/.local.env",
    ".config/codeweaver/.env",
)


def _resolve_project_path() -> Path:
    from codeweaver.core.utils import get_project_path

    return get_project_path().resolve()


def get_possible_config_paths(
    project_path: Path | None = None, *, for_test: bool = False
) -> tuple[Path, ...]:
    """Get possible configuration file paths for CodeWeaverSettings."""
    resolved_project_path = (
        project_path if project_path and project_path.exists() else _resolve_project_path()
    )
    if for_test:
        return (
            tuple(project_path / path for path in _BASE_TEST_PATHS)
            if project_path
            else tuple(resolved_project_path / path for path in _BASE_TEST_PATHS)
        )
    return (
        *(
            (project_path / path for path in _BASE_PROD_PATHS)
            if project_path
            else (resolved_project_path / path for path in _BASE_PROD_PATHS)
        ),
        *(Path(path) for path in _USER_PROD_PATHS),
    )


def get_config_locations(
    settings_cls: type[BaseSettings], *, for_test: bool = False
) -> tuple[PydanticBaseSettingsSource, ...]:
    """Get standard configuration file locations for CodeWeaverSettings.

    Also ensures that the user configuration directories exist with correct permissions.
    """
    user_config_dir = _get_user_config_dir().resolve()
    secrets_dir = user_config_dir / "secrets"
    user_config_dir.mkdir(parents=True, exist_ok=True)
    user_config_dir.chmod(0o700)
    secrets_dir.mkdir(parents=True, exist_ok=True)
    secrets_dir.chmod(0o700)

    def to_sources(config_path: str) -> Iterator[PydanticBaseSettingsSource]:
        for source_cls, ext in SUPPORTED_CONFIG_FILE_EXTENSIONS.items():
            if isinstance(ext, tuple):
                yield from (source_cls(settings_cls, f"{config_path}{e}") for e in ext)
            else:
                yield source_cls(settings_cls, f"{config_path}{ext}")

    return tuple(
        source
        for path in get_possible_config_paths(for_test=for_test)
        for source in to_sources(str(path))
    )


def get_dotenv_locations(settings_cls: type[BaseSettings]) -> tuple[DotEnvSettingsSource, ...]:
    """Get standard dotenv file locations for CodeWeaverSettings."""
    return tuple(
        DotEnvSettingsSource(settings_cls, path, env_ignore_empty=True) for path in _DOTENV_PATHS
    )


def aws_secret_store_configured(
    settings_cls: type[BaseSettings],
) -> Literal[False] | AWSSecretsManagerSettingsSource:
    """Check if AWS Secrets Manager is configured for use as a settings source."""
    if any(env for env in os.environ if env.startswith("AWS_SECRETS_MANAGER")):
        return AWSSecretsManagerSettingsSource(
            settings_cls,
            os.environ.get("AWS_SECRETS_MANAGER_SECRET_ID", ""),
            os.environ.get("AWS_SECRETS_MANAGER_REGION", ""),
            os.environ.get("AWS_SECRETS_MANAGER_ENDPOINT_URL", ""),
        )
    return False


def azure_key_vault_configured(
    settings_cls: type[BaseSettings],
) -> Literal[False] | AzureKeyVaultSettingsSource:
    """Check if Azure Key Vault is configured for use as a settings source."""
    if any(
        env for env in os.environ if env.startswith("AZURE_KEY_VAULT")
    ) and importlib.util.find_spec("azure.identity"):
        try:
            from azure.identity import DefaultAzureCredential  # type: ignore

        except ImportError:
            logger.warning("Azure SDK not installed, skipping Azure Key Vault settings.")
            return False
        else:
            return AzureKeyVaultSettingsSource(
                settings_cls,
                os.environ.get("AZURE_KEY_VAULT_URL", ""),
                DefaultAzureCredential(),  # type: ignore
            )
    return False


def google_secret_manager_configured(
    settings_cls: type[BaseSettings],
) -> Literal[False] | GoogleSecretManagerSettingsSource:
    """Check if Google Secret Manager is configured for use as a settings source."""
    if any(
        env for env in os.environ if env.startswith("GOOGLE_SECRET_MANAGER")
    ) and importlib.util.find_spec("google.auth"):
        try:
            from google.auth import default  # type: ignore

        except ImportError:
            logger.warning(
                "Google Cloud SDK not installed, skipping Google Secret Manager settings."
            )
            return False
        else:
            return GoogleSecretManagerSettingsSource(
                settings_cls,
                default()[0],  # type: ignore
                os.environ.get("GOOGLE_SECRET_MANAGER_PROJECT_ID", ""),
            )
    return False


DEFAULT_BASE_SETTINGS_CONFIG = SettingsConfigDict(
    case_sensitive=False,
    cli_kebab_case=True,
    extra="allow",  # Allow extra fields in the configuration for plugins/extensions
    field_title_generator=generate_field_title,
    model_title_generator=generate_title,
    serialize_by_alias=True,
    validate_by_alias=True,
    validate_by_name=True,
    json_schema_extra=clean_sentinel_from_schema,
    nested_model_default_partial_update=True,
    from_attributes=True,
    env_ignore_empty=True,
    env_nested_delimiter="__",
    env_nested_max_split=-1,
    env_prefix="CODEWEAVER_",  # environment variables will be prefixed with CODEWEAVER_ for top-level fields
    # keep secrets in user config dir
    str_strip_whitespace=True,
    title="CodeWeaver Settings",
    use_attribute_docstrings=True,
    use_enum_values=True,
    validate_assignment=True,
    populate_by_name=True,
)


# spellchecker:off
class BaseCodeWeaverSettings(BaseSettings):
    """
    Base settings model for CodeWeaver with privacy-preserving telemetry serialization.

    This class extends `pydantic_settings.BaseSettings` to provide a foundation for CodeWeaver's configuration management.

    As with all CodeWeaver base models, it mandates all subclasses implement the `_telemetry_keys` method to specify how sensitive data should be handled during telemetry serialization. This makes it each class's responsibility to define which fields are safe for telemetry and how they should be anonymized or excluded. Classes can implement a `_telemetry_handler` method for finer control over the telemetry serialization process.

    The class also includes an implementation of BaseSettings's `settings_customise_sources` method to define a comprehensive and prioritized configuration source hierarchy, including support for environment variables, dotenv files, multiple configuration file formats in a dozen or so locations, and secret management services.

    Subclasses can use the `from_config` class method to create instances from specific configuration files, facilitating testing and specialized setups. If a subclass is subordinate to the main `CodeWeaverSettings`, it should handle settings_customise_sources in a way that avoids conflicts -- mirroring a localized version of the logic here, but only when the main class is not available. Since users can install only parts of CodeWeaver, this is important for modularity.

    Every class has the `project_path`, `config_file`, and `user_config_dir` properties available for use in configuration; primarily for situations where `CodeWeaverSettings` is not available.
    """

    # spellchecker:on
    model_config: SettingsConfigDict = DEFAULT_BASE_SETTINGS_CONFIG

    project_path: Annotated[
        DirectoryPath,
        Field(
            description="Path to the project root directory",
            init=False,
            exclude=CODEWEAVER_SETTINGS_AVAILABLE,
            repr=True,
        ),
    ]

    project_name: Annotated[
        str,
        Field(
            description="Name of the project. Derived from the project directory name if not provided.",
            init=False,
            exclude=CODEWEAVER_SETTINGS_AVAILABLE,
            repr=True,
        ),
    ]

    config_file: Annotated[
        FilePath | None,
        Field(
            description="Path to the configuration file used to load settings",
            exclude=True,
            init=False,
            repr=True,
        ),
    ]

    logging: Annotated[
        LoggingSettingsDict | Unset,
        Field(
            default=UNSET,
            description="Logging configuration for CodeWeaver",
            validate_default=False,
        ),
    ] = UNSET

    telemetry: Annotated[
        TelemetrySettings | Unset,
        Field(
            default=UNSET,
            description="Telemetry configuration for CodeWeaver",
            validate_default=False,
        ),
    ] = UNSET

    __version__: Annotated[
        str,
        Field(
            description="""Schema version for CodeWeaver settings""",
            pattern=r"\d{1,2}\.\d{1,3}\.\d{1,3}",
            alias="schema_version",
        ),
    ] = SCHEMA_VERSION

    schema_: HttpUrl = Field(
        description="URL to the CodeWeaver settings schema",
        default_factory=lambda data: HttpUrl(
            f"https://raw.githubusercontent.com/knitli/codeweaver/main/schema/v{data.get('__version__', data.get('schema_version')) or SCHEMA_VERSION}/codeweaver.schema.json"
        ),
    )

    _unset_fields: set[str] = PrivateAttr(default_factory=set)
    """Fields that were left unset during initialization."""

    _resolution_complete: bool = PrivateAttr(default=False)
    """Whether config resolution has been completed."""

    _env_prefix: ClassVar[str] = "CODEWEAVER_"

    def __init__(
        self,
        project_path: DirectoryPath | Unset = UNSET,
        project_name: str | Unset = UNSET,
        config_file: FilePath | Unset = UNSET,
        logging: LoggingSettingsDict | Unset = UNSET,
        telemetry: TelemetrySettings | Unset = UNSET,
        **data: Any,
    ) -> None:
        """Initialize the BaseCodeWeaverSettings instance."""
        if config_file is not UNSET and config_file.exists():
            self = type(self).from_config(
                cast(Path, config_file),
                project_path=cast(Path | None, project_path if project_path is not UNSET else None),
                **data,
            )
        for key in type(self).model_fields:
            if data.get(key) is UNSET or locals().get(key) is UNSET:
                self._unset_fields.add(key)
        if project_path is UNSET:
            project_path = Path(
                os.getenv("CODEWEAVER_PROJECT_PATH", data.get("project_path", get_project_path()))
            )
        if config_file is UNSET:
            config_file = None  # ty:ignore[invalid-assignment]
        if logging is UNSET:
            logging = data.get("logging", DefaultLoggingSettings)
        if telemetry is UNSET:
            telemetry = data.get("telemetry", TelemetrySettings(**DefaultTelemetrySettings))  # ty:ignore[invalid-argument-type]
        if project_name is UNSET:
            project_name = data.get(
                "project_name", os.getenv("CODEWEAVER_PROJECT_NAME", project_path.name)
            )
        data |= {
            "logging": logging,
            "telemetry": telemetry,
            "project_path": project_path,
            "config_file": config_file,
            "project_name": project_name,
        }
        data = self._initialize(**data)
        super().__init__(**data)
        if not type(self).__pydantic_complete__:
            type(self).model_rebuild()

    @abc.abstractmethod
    def _initialize(self, **kwargs: Any) -> dict[str, Any]:
        """Optional initialization logic for subclasses.

        This method is called during the class's `__init__` method to allow subclasses to perform any necessary setup after the base initialization but before the instance is fully constructed.It must return the finalized kwargs dictionary to be passed to the superclass `__init__`.
        """

    @staticmethod
    def _resolve_default_and_provided(defaults: dict[str, Any], provided: Any) -> dict[str, Any]:
        """Resolve the final configuration by merging defaults with provided values. Do not use for primitives (str, int, float, bool)."""
        if provided is UNSET or not provided:
            return defaults
        if isinstance(provided, dict):
            return BaseCodeWeaverSettings._deep_merge(defaults, provided)
        if isinstance(provided, BaseModel):
            return BaseCodeWeaverSettings._deep_merge(defaults, provided.model_dump())
        # NamedTuple
        if isinstance(provided, tuple):
            return BaseCodeWeaverSettings._deep_merge(defaults, provided._asdict())
        # dataclass
        if hasattr(provided, "__dataclass_fields__"):
            return BaseCodeWeaverSettings._deep_merge(defaults, asdict(provided))
        return defaults

    @staticmethod
    def _deep_merge(dict1: dict[str, Any], dict2: dict[str, Any]) -> dict[str, Any]:
        """Recursively merge two dictionaries."""
        result = dict1.copy()
        for key, value in dict2.items():
            if key in result and isinstance(result[key], dict) and isinstance(value, dict):
                result[key] = BaseCodeWeaverSettings._deep_merge(result[key], value)
            else:
                result[key] = value
        return result

    def _telemetry_handler(self, _serialized_self: dict[str, Any], /) -> dict[str, Any]:
        """An optional handler for subclasses to modify telemetry serialization. By default, it returns an empty dict.

        We use any returned keys as overrides for the serialized_self.
        """
        return {}

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion] | None:
        """Define telemetry filtering for core settings."""
        return {
            FilteredKey("project_path"): AnonymityConversion.HASH,
            FilteredKey("project_name"): AnonymityConversion.HASH,
            FilteredKey("config_file"): AnonymityConversion.HASH,
        }

    def serialize_for_telemetry(self) -> dict[str, Any]:
        """Serialize the model for telemetry output, filtering sensitive keys."""
        from codeweaver.core.types.enum import AnonymityConversion

        excludes: set[str] = set()
        default_group: dict[FilteredKeyT, Any] = {}
        if telemetry_keys := (self._telemetry_keys() or {}):
            excludes = {
                str(key)
                for key, conversion in telemetry_keys.items()
                if conversion == AnonymityConversion.FORBIDDEN
            }
            default_group = {
                key: conversion.filtered(getattr(self, str(key), None))
                for key, conversion in telemetry_keys.items()
                if conversion != AnonymityConversion.FORBIDDEN
            }
        data = self.model_dump(round_trip=True, exclude_none=True, exclude=excludes)
        filtered_group: dict[str, Any] = self._telemetry_handler(data)
        return {
            key: (
                # First priority: handler override
                filtered_group[key]
                if key in filtered_group
                # Second priority: filtered conversion from telemetry_keys
                else default_group.get(FilteredKey(cast(LiteralStringT, key)), value)
            )
            for key, value in data.items()
        } | {"unset_fields": list(self._unset_fields)}

    def _update_settings(self, **kwargs: Any) -> Self:
        """Update settings, validating a new CodeWeaverSettings instance and updating the global instance."""
        try:
            self.__init__(**kwargs)  # type: ignore # Unpack doesn't extend to nested dicts
        except ValidationError:
            logger.warning(
                "`CodeWeaverSettings` received invalid settings for an update. The settings failed to validate. We did not update the settings."
            )
            return self
        self._resolution_complete = False
        return self

    @staticmethod
    def _to_serializable(
        obj: BaseCodeWeaverSettings, path: Path | None = None, **override_kwargs: Any
    ) -> Any:
        """Convert an object to a serializable form."""
        from codeweaver.core import get_project_path

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
        path = (  # ty:ignore[invalid-assignment]
            path
            if path and path is not Unset
            else self.config_file
            if self.config_file is not UNSET
            else None
        )
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
            "exclude": {"config_file", "default_mcp_config"},
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

    async def finalize(self) -> Self:
        """Finalize settings with config resolution.

        This should be called after all configs are loaded but before
        the application starts. It resolves all interdependencies between
        configuration objects.

        Returns:
            Self for chaining

        Note:
            This method is idempotent - calling it multiple times is safe.
            It will only perform resolution once.
        """
        if self._resolution_complete:
            return self

        try:
            from codeweaver.core.config.resolver import resolve_all_configs

            # Trigger config resolution across all registered components
            await resolve_all_configs()

            self._resolution_complete = True
        except ImportError:
            # Config resolution not available (minimal core install)
            logger.debug("Config resolution module not available - skipping")
        except Exception as e:
            logger.warning("Config resolution failed: %s", e)

        return self

    @classmethod
    def generate_default_config(cls, path: Path) -> None:
        """Generate a default configuration file at the specified path.

        The file format is determined by the file extension (.toml, .yaml/.yml, .json).
        """
        default_settings = cls()
        data = cls._to_serializable(default_settings, path=path)
        cls._write_config_file(path, data)

    @classmethod
    def from_config(cls, path: FilePath, project_path: Path | None = None, **kwargs: Any) -> Self:
        """Create a CodeWeaverSettings instance from a configuration file.

        This is a convenience method for creating a settings instance from a specific config file. By default, CodeWeaverSettings will look for configuration files in standard locations (like codeweaver.toml in the project root -- see `get_config_locations`). This method allows you to specify a particular config file to load settings from, primarily for testing or special use cases.
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
        return (
            cls(project_path=project_path, **{**kwargs, "config_file": path})  # ty:ignore[invalid-argument-type]
            if project_path
            else cls(**{**kwargs, "config_file": path})  # ty:ignore[invalid-argument-type]
        )  # ty:ignore[invalid-argument-type]

    @computed_field
    @property
    def project_root(self) -> Path:
        """Get the project root directory. Alias for `project_path`."""
        if isinstance(self.project_path, Unset):
            from codeweaver.core import get_project_path

            self.project_path = get_project_path()
        return self.project_path.resolve()

    @classmethod
    def _base_settings_sources(
        cls, settings_cls: type[BaseSettings]
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Get the base settings sources for subclasses to build upon.

        This method provides a standard set of configuration sources for CodeWeaver settings classes. Subclasses can extend or modify this list as needed, but this base implementation ensures a consistent configuration hierarchy across all settings classes.
        """
        user_config_dir = get_user_config_dir()
        if is_test_environment():
            return get_config_locations(settings_cls, for_test=True)
        config_sources: list[PydanticBaseSettingsSource | None] = [
            EnvSettingsSource(
                settings_cls,
                env_prefix=cls._env_prefix,
                case_sensitive=False,
                env_nested_delimiter="__",
                env_parse_enums=True,
                env_ignore_empty=True,
            ),
            *get_dotenv_locations(settings_cls),
            *get_config_locations(settings_cls, for_test=False),
            aws_secret_store_configured(settings_cls) or None,
            azure_key_vault_configured(settings_cls) or None,
            google_secret_manager_configured(settings_cls) or None,
            SecretsSettingsSource(
                settings_cls=settings_cls,
                secrets_dir=f"{user_config_dir}/secrets",
                env_ignore_empty=True,
            ),
        ]
        return tuple(source for source in config_sources if source is not None)

    # spellchecker:off
    @classmethod
    def settings_customise_sources(
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Customize settings sources for CodeWeaverSettings and subclasses.

        This method defines the configuration source hierarchy for CodeWeaver settings classes. It prioritizes environment variables, dotenv files, multiple configuration file formats in various locations, and secret management services. Subclasses can override this method to modify the source order or add additional sources as needed.
        """
        return cls._base_settings_sources(settings_cls)

    # spellchecker:on

    @classmethod
    def python_json_schema(cls) -> dict[str, Any]:
        """Get the JSON validation schema for the settings model as a string."""
        return cls.model_json_schema(by_alias=True)

    @classmethod
    def json_schema(cls) -> bytes:
        """Get the JSON validation schema for the settings model.

        Note: For build-time schema generation, use scripts/build/generate-schema.py instead.
        This method is kept for runtime introspection and testing purposes.
        """
        return to_json(cls.python_json_schema(), indent=2).replace(b"schema_", b"$schema")

    @property
    def view(self) -> DictView[CodeWeaverSettingsDict]:
        """Get a read-only mapping view of the settings."""
        if self._map is None:
            self._map = DictView(self.model_dump(exclude_computed_fields=True))  # type: ignore
        return self._map  # type: ignore


__all__ = (
    "DEFAULT_BASE_SETTINGS_CONFIG",
    "BaseCodeWeaverSettings",
    "get_config_locations",
    "get_dotenv_locations",
    "get_possible_config_paths",
)
