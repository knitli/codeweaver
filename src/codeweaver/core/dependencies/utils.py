# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Utilities for setting up dependencies."""

from __future__ import annotations

import codeweaver.core.di.container


_container_initialized = False
_settings_initialized = False


def ensure_container_initialized() -> None:
    """Ensure the DI container is initialized.

    This is necessary before importing any modules that might use dependency injection,
    to avoid circular import issues. It can be called at the top of any module that
    needs to use dependencies.
    """
    if globals()["_container_initialized"] is False:
        # just call it to initialize the container
        _ = codeweaver.core.di.container.get_container()
        globals()["_container_initialized"] = True


def _try_to_resolve_settings() -> bool:
    """Try to resolve settings from the DI container.

    This is used to check if settings have been initialized yet, without causing
    an import error if they haven't. It can be used in modules that depend on
    settings to check if they can safely import them.

    Returns:
        True if settings were successfully resolved, False otherwise.
    """
    container = codeweaver.core.di.container.get_container()
    try:
        from codeweaver.core.config.settings_type import CodeWeaverSettingsType

        container[CodeWeaverSettingsType]
    except Exception:
        return False
    else:
        return True


def ensure_settings_initialized() -> None:
    """Ensure settings are initialized in the DI container (sync version).

    This checks if settings are already initialized. If not, it raises an error
    directing the caller to use the async version or bootstrap settings properly.

    Use this in sync contexts where settings should already be initialized
    (e.g., after async bootstrap has run during application startup).

    Raises:
        RuntimeError: If settings are not initialized

    Note:
        For async contexts or initial bootstrap, use ensure_settings_initialized_async()
        instead, which properly awaits the bootstrap process.
    """
    if globals()["_container_initialized"] is False:
        ensure_container_initialized()
    if globals()["_settings_initialized"] is False:
        if not _try_to_resolve_settings():
            raise RuntimeError(
                "Settings are not initialized. Settings must be initialized from an async "
                "context using ensure_settings_initialized_async() or bootstrap_settings() "
                "before accessing them from sync code.\n\n"
                "Common causes:\n"
                "  - Importing a module that depends on settings before bootstrapping\n"
                "  - Calling settings-dependent code outside an async context\n\n"
                "Solutions:\n"
                "  - Call await ensure_settings_initialized_async() from an async function\n"
                "  - Use the server/CLI startup paths that handle bootstrap automatically"
            )
        # If _try_to_resolve_settings() returned True, settings exist in container
        globals()["_settings_initialized"] = True


async def ensure_settings_initialized_async() -> None:
    """Ensure settings are initialized in the DI container (async version).

    This should be called from async contexts to properly bootstrap settings.
    It will await the async bootstrap_settings() if needed.

    This is the preferred way to initialize settings during application startup,
    as it properly handles the async nature of the bootstrap process.

    Raises:
        Exception: If settings initialization fails
    """
    if globals()["_container_initialized"] is False:
        ensure_container_initialized()
    if globals()["_settings_initialized"] is False:
        if not _try_to_resolve_settings():
            from codeweaver.core.dependencies.core_settings import bootstrap_settings

            await bootstrap_settings()
        globals()["_settings_initialized"] = True


__all__ = (
    "ensure_container_initialized",
    "ensure_settings_initialized",
    "ensure_settings_initialized_async",
)
