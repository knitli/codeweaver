# sourcery skip: lambdas-should-be-short, no-complex-if-expressions
# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Base settings model for CodeWeaver using Pydantic Settings."""

from __future__ import annotations

import abc

from pydantic_settings import BaseSettings, SettingsConfigDict

from codeweaver.core.types.aliases import FilteredKeyT
from codeweaver.core.types.enum import AnonymityConversion
from codeweaver.core.types.utils import (
    clean_sentinel_from_schema,
    generate_field_title,
    generate_title,
)


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



    Subclasses can use the `from_config` class method to create instances from specific configuration files, facilitating testing and specialized setups. If a subclass is subordinate to the main `CodeWeaverSettings`, it should handle settings_customise_sources in a way that avoids conflicts -- mirroring a localized version of the logic here, but only when the main class is not available. Since users can install only parts of CodeWeaver, this is important for modularity.

    Every class has the `project_path`, `config_file`, and `user_config_dir` properties available for use in configuration; primarily for situations where `CodeWeaverSettings` is not available.
    """

    # spellchecker:on
    model_config: SettingsConfigDict = DEFAULT_BASE_SETTINGS_CONFIG

    @abc.abstractmethod
    async def _initialize(self) -> None:
        """Initialize any additional state or perform actions after settings are loaded."""

    @abc.abstractmethod
    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion] | None:
        """Define telemetry filtering for core settings."""

    @abc.abstractmethod
    async def _finalize(self) -> None:
        """Finalize settings after initialization, for any async post-processing needed."""


__all__ = ("DEFAULT_BASE_SETTINGS_CONFIG", "BaseCodeWeaverSettings")
