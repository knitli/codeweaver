# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Settings initialization and related dependencies."""

from __future__ import annotations

from codeweaver.core.di.container import get_container


_ = get_container()  # ensure container is initialized before any other imports

import asyncio
import os

from pathlib import Path
from typing import Annotated

from anyio import Path as AsyncPath

from codeweaver.core.config.settings_type import CodeWeaverSettingsType
from codeweaver.core.config.types import CodeWeaverSettingsDict
from codeweaver.core.di.dependency import INJECTED, depends
from codeweaver.core.di.utils import dependency_provider
from codeweaver.core.types.dictview import DictView


def _resolve_config_file() -> Path | None:
    """Resolve the configuration file path.

    Checks for the CODEWEAVER_CONFIG_FILE environment variable first,
    then falls back to standard config locations.

    Returns:
        The resolved config file path, or None if not found.
    """
    if (declared_env := os.getenv("CODEWEAVER_CONFIG_FILE")) is not None:
        return Path(declared_env)
    return None


@dependency_provider(CodeWeaverSettingsType, scope="singleton", tags=["settings"])
async def bootstrap_settings(config_file: Path | None = None) -> CodeWeaverSettingsType:
    """Bootstrap global settings as DI root.

    Auto-detects the appropriate settings class based on installed packages
    (server, engine, provider, or core) and returns it as BaseCodeWeaverSettings.

    This is the DI system's entry point - settings are created once at startup
    and all other providers can inject them via:
        settings: BaseCodeWeaverSettings = INJECTED

    Returns:
        The appropriate settings instance for the current installation
    """
    from codeweaver.core.config.core_settings import get_possible_config_paths
    from codeweaver.core.config.loader import get_settings_async

    loop = asyncio.get_running_loop()
    await asyncio.sleep(0)
    async_config = (
        AsyncPath(str(config_file))
        if config_file
        else AsyncPath(env)
        if (env := os.environ.get("CODEWEAVER_CONFIG_FILE")) is not None
        else None
    )
    if (
        async_config
        and await async_config.exists()
        and Path(str(async_config)) in await loop.to_thread(get_possible_config_paths)
    ):
        # let pydantic_settings handle loading from the file if it's in a standard location
        async_config = None

    settings = await get_settings_async(
        config_file=await async_config.resolve()
        if async_config and await async_config.exists()
        else None
    )
    # we'll use asyncio.sleep(0) to yield control back to the event loop between each step of initialization
    await asyncio.sleep(0)
    await settings._initialize()
    await asyncio.sleep(0)
    await settings._finalize()
    await asyncio.sleep(0)
    return settings


type SettingsDep = Annotated[CodeWeaverSettingsType, depends(scope="singleton", tags={"settings"})]


@dependency_provider(DictView[CodeWeaverSettingsDict])
def _get_settings_map(settings: SettingsDep = INJECTED) -> DictView[CodeWeaverSettingsDict]:
    """Marker for providing a DictView of the current settings."""
    from codeweaver.core.types.dictview import DictView

    return DictView(settings.model_dump())


type SettingsMapDep = Annotated[
    DictView[CodeWeaverSettingsDict], depends(_get_settings_map, use_cache=False, scope="request")
]


# re-export CodeWeaverSettingsType for type annotations in other modules
__all__ = ("CodeWeaverSettingsType", "SettingsDep", "SettingsMapDep", "bootstrap_settings")
