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

        container.resolve(CodeWeaverSettingsType)
    except Exception:
        return False
    else:
        return True


def ensure_settings_initialized() -> None:
    """Ensure settings are initialized in the DI container.

    This is necessary before importing any modules that depend on settings, to avoid
    circular import issues. It can be called at the top of any module that needs to
    use settings.
    """
    if globals()["_container_initialized"] is False:
        ensure_container_initialized()
    if globals()["_settings_initialized"] is False:
        if not _try_to_resolve_settings():
            from codeweaver.core.dependencies.core_settings import bootstrap_settings

            bootstrap_settings()
        globals()["_settings_initialized"] = True


__all__ = ("ensure_container_initialized", "ensure_settings_initialized")
