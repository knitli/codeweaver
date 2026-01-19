# sourcery skip: lambdas-should-be-short
# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Root settings for core-only CodeWeaver installation.

This module provides the root settings class when only the core package
is installed (logging and telemetry configuration only).
"""

from __future__ import annotations

from typing import Any

from codeweaver.core.types.settings_model import BaseCodeWeaverSettings


SCHEMA_VERSION = "1.2.0"


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

    def _initialize(self, **kwargs: Any) -> dict[str, Any]:
        """Initialize core settings - nothing special needed."""
        return kwargs


__all__ = ("CodeWeaverCoreSettings",)
