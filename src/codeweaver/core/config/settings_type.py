"""Sets the globals settings type for the codeweaver based on package resolution."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any

from codeweaver.core.utils.environment import detect_root_package


_core_settings_module = detect_root_package()

if TYPE_CHECKING and _core_settings_module == "server":
    from codeweaver.server.config.settings import CodeWeaverSettings

    type CodeWeaverSettingsType = CodeWeaverSettings
elif TYPE_CHECKING and _core_settings_module == "engine":
    from codeweaver.engine.config.root_settings import CodeWeaverEngineSettings

    type CodeWeaverSettingsType = CodeWeaverEngineSettings
elif TYPE_CHECKING and _core_settings_module == "providers":
    from codeweaver.providers.config.root_settings import CodeWeaverProviderSettings

    type CodeWeaverSettingsType = CodeWeaverProviderSettings
elif TYPE_CHECKING:
    from codeweaver.core.config.core_settings import CodeWeaverCoreSettings

    type CodeWeaverSettingsType = CodeWeaverCoreSettings
else:
    type CodeWeaverSettingsType = Any


__all__ = ("CodeWeaverSettingsType",)
