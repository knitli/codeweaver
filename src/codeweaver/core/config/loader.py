# sourcery skip: lambdas-should-be-short
# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Configuration loader with automatic package detection.

This module provides utilities for automatically loading the appropriate
root settings class based on which CodeWeaver packages are installed.
"""

from __future__ import annotations

import asyncio
import logging

from pathlib import Path

from anyio import Path as AsyncPath

from codeweaver.core.config.settings_type import CodeWeaverSettingsType


logger = logging.getLogger(__name__)


async def get_settings_async(
    config_file: AsyncPath | None = None, **kwargs
) -> CodeWeaverSettingsType:
    """Async version of get_settings for use in async contexts."""
    from codeweaver.core.config.settings_type import _core_settings_module

    match _core_settings_module:
        case "server":
            from codeweaver.server.config.settings import CodeWeaverSettings

            return await asyncio.to_thread(
                lambda: (
                    CodeWeaverSettings.from_config(path=Path(str(config_file)))
                    if config_file
                    else CodeWeaverSettings(**kwargs)
                )
            )
        case "engine":
            from codeweaver.engine.config.root_settings import CodeWeaverEngineSettings

            return await asyncio.to_thread(
                lambda: (
                    CodeWeaverEngineSettings.from_config(path=Path(str(config_file)))
                    if config_file
                    else CodeWeaverEngineSettings(**kwargs)
                )
            )
        case "providers":
            from codeweaver.providers.config.root_settings import CodeWeaverProviderSettings

            return await asyncio.to_thread(
                lambda: (
                    CodeWeaverProviderSettings.from_config(path=Path(str(config_file)))
                    if config_file
                    else CodeWeaverProviderSettings(**kwargs)
                )
            )
        case "core":
            from codeweaver.core.config.core_settings import CodeWeaverCoreSettings

            return await asyncio.to_thread(
                lambda: (
                    CodeWeaverCoreSettings.from_config(path=Path(str(config_file)))
                    if config_file
                    else CodeWeaverCoreSettings(**kwargs)
                )
            )
        case _:
            raise ImportError(f"Unsupported package detected: {_core_settings_module}")


def get_settings(config_file: Path | None = None, **kwargs) -> CodeWeaverSettingsType:
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
        settings = get_settings(config_file="/path/to/config.toml")
        ```
    """
    from codeweaver.core.config.settings_type import _core_settings_module

    package = _core_settings_module
    match package:
        case "server":
            from codeweaver.server.config.settings import CodeWeaverSettings

            return (
                CodeWeaverSettings.from_config(path=config_file)
                if config_file
                else CodeWeaverSettings(**kwargs)
            )

        case "engine":
            from codeweaver.engine.config.root_settings import CodeWeaverEngineSettings

            return (
                CodeWeaverEngineSettings.from_config(path=config_file)
                if config_file
                else CodeWeaverEngineSettings(**kwargs)
            )

        case "provider":
            from codeweaver.providers.config.root_settings import CodeWeaverProviderSettings

            return (
                CodeWeaverProviderSettings.from_config(path=config_file)
                if config_file
                else CodeWeaverProviderSettings(**kwargs)
            )

        case "core":
            from codeweaver.core.config.core_settings import CodeWeaverCoreSettings

            return (
                CodeWeaverCoreSettings.from_config(path=config_file)
                if config_file
                else CodeWeaverCoreSettings(**kwargs)
            )

        case _:
            raise ImportError(f"Unsupported package detected: {package}")


__all__ = ("CodeWeaverSettingsType", "get_settings", "get_settings_async")
