# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""CLI dependency injection setup."""

from __future__ import annotations

from pathlib import Path

from codeweaver.cli.ui import get_display
from codeweaver.core.config.loader import get_settings
from codeweaver.core.dependencies import CodeWeaverSettingsType
from codeweaver.core.di import Container, get_container
from codeweaver.core.ui_protocol import ProgressReporter
from codeweaver.server import update_settings


def setup_cli_di(
    config_file: Path | None, project_path: Path | None, *, verbose: bool = False
) -> Container:
    """Setup the DI container for CLI commands.

    This function:
    1. Loads the settings based on CLI arguments.
    2. Configures the global container to use these settings.
    3. Configures the UI display as the progress reporter.
    """
    # 1. Load and update settings
    # We use the server's get_settings/update_settings to handle the logic
    # of combining defaults, env vars, and CLI args.
    settings = get_settings(config_file=config_file)

    if project_path:
        # update_settings returns a new settings object
        # We need to cast the result because update_settings dynamic return type
        # might confuse type checkers in this context
        settings = update_settings(project_path=project_path)  # type: ignore

    # 2. Get global container
    container = get_container()

    # 3. Override Settings
    # This ensures that any component requesting settings (via SettingsDep or CodeWeaverSettingsType)
    # receives the instance we just configured from CLI args.
    container.override(CodeWeaverSettingsType, settings)

    # 4. Override ProgressReporter
    # The CLI uses StatusDisplay for progress reporting.
    display = get_display()
    container.override(ProgressReporter, display)

    return container
