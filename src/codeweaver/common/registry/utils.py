# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Common utilities for the registry package."""

from __future__ import annotations

from codeweaver.config.providers import ProviderSettingsDict
from codeweaver.core.types.dictview import DictView


_provider_settings: DictView[ProviderSettingsDict] | None = None


def get_provider_settings() -> DictView[ProviderSettingsDict]:
    """Get the provider settings."""
    global _provider_settings
    if not _provider_settings:
        from codeweaver.config.settings import get_settings_map

        _provider_settings = DictView(get_settings_map()["provider"])
    if not _provider_settings:
        raise ValueError("Provider settings are not available.")
    return _provider_settings
