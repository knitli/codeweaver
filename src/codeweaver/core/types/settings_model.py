"""Base settings model for CodeWeaver using Pydantic Settings."""

import abc
import importlib
import logging
import os

from collections.abc import Iterator
from pathlib import Path
from types import MappingProxyType
from typing import Annotated, Any, Literal, Self, cast

from beartype.typing import ClassVar
from pydantic import DirectoryPath, Field, FilePath, PrivateAttr, computed_field
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

from codeweaver.core import get_project_path
from codeweaver.core.types.aliases import FilteredKey, FilteredKeyT, LiteralStringT
from codeweaver.core.types.enum import AnonymityConversion
from codeweaver.core.types.sentinel import UNSET, Unset
from codeweaver.core.types.utils import (
    clean_sentinel_from_schema,
    generate_field_title,
    generate_title,
)
from codeweaver.core.utils import get_user_config_dir, get_user_data_dir, is_test_environment


SUPPORTED_CONFIG_FILE_EXTENSIONS = MappingProxyType({
    TomlConfigSettingsSource: ".toml",
    YamlConfigSettingsSource: (".yaml", ".yml"),
    JsonConfigSettingsSource: ".json",
})

logger = logging.getLogger(__name__)

CODEWEAVER_SETTINGS_AVAILABLE = importlib.util.find_spec("codeweaver.server") is not None


def get_config_locations(
    settings_cls: type[BaseSettings], user_config_dir: Path, *, for_test: bool
) -> tuple[PydanticBaseSettingsSource, ...]:
    """Get standard configuration file locations for CodeWeaverSettings.

    Also ensures that the user configuration directories exist with correct permissions.
    """
    user_config_dir = user_config_dir
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

    if for_test:
        return tuple(
            pth
            for path in (
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
            for pth in to_sources(path)
        )
    return tuple(
        pth
        for path in (
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
            f"{user_config_dir!s}/codeweaver",
            f"{user_config_dir!s}/config",
        )
        for pth in to_sources(path)
    )


def get_dotenv_locations(settings_cls: type[BaseSettings]) -> tuple[DotEnvSettingsSource, ...]:
    """Get standard dotenv file locations for CodeWeaverSettings."""
    return tuple(
        DotEnvSettingsSource(settings_cls, path, env_ignore_empty=True)
        for path in (
            ".local.env",
            ".env",
            ".codeweaver.local.env",
            ".codeweaver.env",
            ".codeweaver/.local.env",
            ".codeweaver/.env",
            ".config/codeweaver/.local.env",
            ".config/codeweaver/.env",
        )
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

    user_config_dir: Annotated[
        DirectoryPath,
        Field(
            description="Path to the user configuration directory",
            default_factory=get_user_config_dir,
            exclude=CODEWEAVER_SETTINGS_AVAILABLE,
            init=False,
        ),
    ]

    user_data_dir: Annotated[
        DirectoryPath,
        Field(
            description="Path to the user data directory",
            default_factory=get_user_data_dir,
            exclude=CODEWEAVER_SETTINGS_AVAILABLE,
            init=False,
        ),
    ]

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
        user_config_dir: DirectoryPath | Unset = UNSET,
        user_data_dir: DirectoryPath | Unset = UNSET,
        **data: Any,
    ) -> None:
        """Initialize the BaseCodeWeaverSettings instance."""
        if config_file is not UNSET:
            self = type(self).from_config(
                cast(Path, config_file),
                project_path=cast(Path | None, project_path if project_path is not UNSET else None),
                **data,
            )
        for key in type(self).model_fields:
            if key not in data or key not in {"project_path", "config_file", "user_config_dir"}:
                self._unset_fields.add(key)
        if project_path is UNSET:
            project_path = get_project_path()
        if config_file is UNSET:
            config_file = None  # ty:ignore[invalid-assignment]
        object.__setattr__(self, "user_config_dir", get_user_config_dir())
        object.__setattr__(self, "project_path", project_path)
        object.__setattr__(self, "config_file", config_file)
        self._initialize()
        super().__init__(**data)

    @abc.abstractmethod
    def _initialize(self) -> None:
        """Optional initialization logic for subclasses.

        This method is called during the class's `__init__` method to allow subclasses to perform any necessary setup after the base initialization but before the instance is fully constructed.
        """

    @abc.abstractmethod
    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion] | None:
        """Get telemetry keys for the dataclass."""
        raise NotImplementedError("Subclasses must implement _telemetry_keys method.")

    def _telemetry_handler(self, _serialized_self: dict[str, Any], /) -> dict[str, Any]:
        """An optional handler for subclasses to modify telemetry serialization. By default, it returns an empty dict.

        We use any returned keys as overrides for the serialized_self.
        """
        return {}

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
            return get_config_locations(settings_cls, user_config_dir, for_test=True)
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
            *get_config_locations(settings_cls, user_config_dir, for_test=False),
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


__all__ = (
    "DEFAULT_BASE_SETTINGS_CONFIG",
    "BaseCodeWeaverSettings",
    "get_config_locations",
    "get_dotenv_locations",
)
