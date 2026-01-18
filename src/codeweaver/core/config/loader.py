# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Configuration loader with automatic package detection.

This module provides utilities for automatically loading the appropriate
root settings class based on which CodeWeaver packages are installed.
"""

from __future__ import annotations

import logging

from typing import TYPE_CHECKING

from codeweaver.core.utils.environment import detect_root_package


if TYPE_CHECKING:
    from codeweaver.core.types.settings_model import BaseCodeWeaverSettings


logger = logging.getLogger(__name__)


def get_settings(**kwargs) -> BaseCodeWeaverSettings:
    """Auto-load the appropriate root settings based on installation.

    This function detects which CodeWeaver packages are installed and
    loads the corresponding root settings class. This allows the same
    code to work across different installation configurations.

    Args:
        **kwargs: Additional arguments to pass to settings constructor

    Returns:
        The appropriate root settings instance for the current installation

    Raises:
        ImportError: If the detected package's settings module cannot be imported

    Examples:
        ```python
        # Works with any installation
        settings = get_settings()
        await settings.finalize()

        # With custom config
        settings = get_settings(project_path="/path/to/project")
        ```
    """
    package = detect_root_package()

    match package:
        case "server":
            from codeweaver.server.config.settings import CodeWeaverSettings

            return CodeWeaverSettings(**kwargs)

        case "engine":
            from codeweaver.engine.config.root_settings import CodeWeaverEngineSettings

            return CodeWeaverEngineSettings(**kwargs)

        case "provider":
            from codeweaver.providers.config.root_settings import CodeWeaverProviderSettings

            return CodeWeaverProviderSettings(**kwargs)

        case "core":
            from codeweaver.core.config.core_settings import CodeWeaverCoreSettings

            return CodeWeaverCoreSettings(**kwargs)

        case _:
            raise ImportError(f"Unsupported package detected: {package}")


__all__ = ("get_settings",)
