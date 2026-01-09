# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Root settings for core-only CodeWeaver installation.

This module provides the root settings class when only the core package
is installed (logging and telemetry configuration only).
"""

from __future__ import annotations

from typing import Annotated

from pydantic import Field

from codeweaver.core.config._logging import LoggingSettingsDict
from codeweaver.core.config.telemetry import TelemetrySettings
from codeweaver.core.types.aliases import FilteredKey, FilteredKeyT
from codeweaver.core.types.enum import AnonymityConversion
from codeweaver.core.types.sentinel import UNSET, Unset
from codeweaver.core.types.settings_model import BaseCodeWeaverSettings


class CodeWeaverCoreSettings(BaseCodeWeaverSettings):
    """Root settings wrapper for core-only installation.

    When only the core package is installed, this provides configuration
    for logging and telemetry only. All other CodeWeaver functionality
    requires additional packages (providers, engine, server).

    Configuration structure:
        ```toml
        [logging]
        level = "INFO"

        [telemetry]
        enabled = true
        ```
    """

    model_config = BaseCodeWeaverSettings.model_config | {
        "title": "CodeWeaver Core Settings",
        "description": "Core settings for CodeWeaver (logging and telemetry only).",
    }

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

    def _initialize(self) -> None:
        """Initialize core settings - nothing special needed."""

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion] | None:
        """Define telemetry filtering for core settings."""
        return {
            FilteredKey("project_path"): AnonymityConversion.HASH,
            FilteredKey("user_config_dir"): AnonymityConversion.HASH,
            FilteredKey("config_file"): AnonymityConversion.HASH,
        }


__all__ = ("CodeWeaverCoreSettings",)
