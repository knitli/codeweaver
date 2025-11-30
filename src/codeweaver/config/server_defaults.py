# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Default server-related settings for CodeWeaver."""

from __future__ import annotations

import logging

from codeweaver.config.types import (
    EndpointSettingsDict,
    FastMcpHttpRunArgs,
    FastMcpServerSettingsDict,
    UvicornServerSettings,
)


logger = logging.getLogger(__name__)

# NOTE: Default provider settings are in `codeweaver.config.providers`

DefaultFastMcpServerSettings = FastMcpServerSettingsDict(
    auth=None,
    on_duplicate_tools="replace",
    on_duplicate_resources="replace",
    on_duplicate_prompts="replace",
    resource_prefix_format="path",
)
DefaultEndpointSettings = EndpointSettingsDict(
    enable_settings=True, enable_version=True, enable_state=True
)

DefaultUvicornSettings = UvicornServerSettings.codeweaver_management_defaults()

DefaultUvicornSettingsForMcp = UvicornServerSettings.codeweaver_mcp_defaults()

DefaultFastMcpHttpRunArgs = FastMcpHttpRunArgs(
    transport="streamable-http",
    host="127.0.0.1",
    port=9328,
    log_level="warning",
    path="/mcp/",
    uvicorn_config=DefaultUvicornSettingsForMcp,
    middleware=[],
)

__all__ = (
    "DefaultEndpointSettings",
    "DefaultFastMcpHttpRunArgs",
    "DefaultFastMcpServerSettings",
    "DefaultUvicornSettings",
    "DefaultUvicornSettingsForMcp",
)
