# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Helper functions for server configuration.

Re-exports configuration functions from core for convenience.
"""

from __future__ import annotations

from typing import TYPE_CHECKING

from codeweaver.core.config.loader import get_settings as _get_settings


if TYPE_CHECKING:
    from codeweaver.core.types import DictView
    from codeweaver.core.types.settings_model import BaseCodeWeaverSettings
    from codeweaver.server.config.settings import CodeWeaverSettingsDict


def get_settings(**kwargs) -> BaseCodeWeaverSettings:
    """Get CodeWeaver settings.

    This is a re-export of codeweaver.core.config.loader.get_settings
    for convenience when working with server configuration.

    Args:
        **kwargs: Additional arguments to pass to settings constructor

    Returns:
        The appropriate root settings instance for the current installation
    """
    return _get_settings(**kwargs)


def get_settings_map(config_file: str | None = None) -> DictView[CodeWeaverSettingsDict]:
    """Get settings as a dictionary view.

    Args:
        config_file: Optional path to configuration file

    Returns:
        Dictionary view of settings
    """
    settings = get_settings(config_file=config_file)
    return settings.view  # ty:ignore[invalid-return-type]


def update_settings(**kwargs) -> BaseCodeWeaverSettings:
    """Update settings with new values.

    Args:
        **kwargs: Settings values to update

    Returns:
        Updated settings instance
    """
    settings = get_settings()
    # Create a new settings instance with updated values
    updated_data = settings.model_dump()
    updated_data |= kwargs
    return type(settings)(**updated_data)


__all__ = ("get_settings", "get_settings_map", "update_settings")
