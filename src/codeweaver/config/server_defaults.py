# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Default server-related settings for CodeWeaver."""

from __future__ import annotations

import logging

from codeweaver.config.types import (
    EndpointSettingsDict,
    FastMcpServerSettingsDict,
    UvicornServerSettings,
    UvicornServerSettingsDict,
)


logger = logging.getLogger(__name__)

# NOTE: Default provider settings are in `codeweaver.config.providers`


DefaultFastMcpServerSettings = FastMcpServerSettingsDict(
    transport="http",
    auth=None,
    on_duplicate_tools="replace",
    on_duplicate_resources="replace",
    on_duplicate_prompts="replace",
    resource_prefix_format="path",
    middleware=[],
    tools=[],
)
DefaultEndpointSettings = EndpointSettingsDict(
    enable_health=True,
    enable_metrics=True,
    enable_settings=True,
    enable_version=True,
    enable_state=True,
)  # type: ignore

DefaultUvicornSettings = UvicornServerSettingsDict(
    UvicornServerSettings().model_dump(exclude_none=True, exclude_computed_fields=True)  # type: ignore
)

__all__ = ("DefaultEndpointSettings", "DefaultFastMcpServerSettings", "DefaultUvicornSettings")
