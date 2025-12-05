# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Default server-related settings for CodeWeaver."""

from __future__ import annotations

import logging

from functools import cache
from pathlib import Path
from typing import Literal, overload

from codeweaver.common.utils.utils import get_user_config_dir
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

_USER_CONFIG_DIR = get_user_config_dir()

_test_config_file_locations = [
    "codeweaver.test.local",
    ".codeweaver.test.local",
    "codeweaver/codeweaver.test.local",
    "codeweaver/config.test.local",
    ".codeweaver/codeweaver.test.local",
    ".codeweaver/config.test.local",
    ".config/codeweaver/test.local",
    "codeweaver.test",
    ".codeweaver.test",
    "codeweaver/codeweaver.test",
    "codeweaver/config.test",
    ".codeweaver/codeweaver.test",
    ".codeweaver/config.test",
    ".config/codeweaver/test",
]

_config_file_locations = [
    "codeweaver.local",
    ".codeweaver.local",
    "codeweaver/codeweaver.local",
    "codeweaver/config.local",
    ".codeweaver/codeweaver.local",
    ".codeweaver/config.local",
    ".config/codeweaver/codeweaver.local",
    ".config/codeweaver/config.local",
    "codeweaver",
    ".codeweaver",
    "codeweaver/codeweaver",
    "codeweaver/config",
    ".codeweaver/codeweaver",
    ".codeweaver/config",
    ".config/codeweaver/codeweaver",
    ".config/codeweaver/config",
    f"{_USER_CONFIG_DIR!s}/codeweaver",
    f"{_USER_CONFIG_DIR!s}/config",
]

CODEWEAVER_TEST_CONFIG_FILE_LOCATIONS = tuple(
    f"{location}.{ext}"
    for location in _test_config_file_locations
    for ext in ("toml", "yaml", "yml", "json")
)

CODEWEAVER_CONFIG_FILE_LOCATIONS = tuple(
    f"{location}.{ext}"
    for location in _config_file_locations
    for ext in ("toml", "yaml", "yml", "json")
)


@overload
def get_config_file_locations(
    *, for_test: bool = False, must_exist: bool = False, as_path: Literal[True] = True
) -> tuple[Path, ...]: ...
@overload
def get_config_file_locations(
    *, for_test: bool = False, must_exist: bool = False, as_path: Literal[False]
) -> tuple[str, ...]: ...
@cache
def get_config_file_locations(
    *, for_test: bool = False, must_exist: bool = False, as_path: bool = True
) -> tuple[Path, ...] | tuple[str, ...]:
    """Get the list of config file locations."""
    locations = (
        CODEWEAVER_TEST_CONFIG_FILE_LOCATIONS if for_test else CODEWEAVER_CONFIG_FILE_LOCATIONS
    )
    if must_exist:
        if as_path:
            return tuple(Path(location) for location in locations if Path(location).exists())
        return tuple(location for location in locations if Path(location).exists())
    if as_path:
        return tuple(Path(location) for location in locations)
    return tuple(locations)


__all__ = (
    "DefaultEndpointSettings",
    "DefaultFastMcpHttpRunArgs",
    "DefaultFastMcpServerSettings",
    "DefaultUvicornSettings",
    "DefaultUvicornSettingsForMcp",
)
