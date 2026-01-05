"""Configuration loader with automatic package detection.

This module provides utilities for automatically loading the appropriate
root settings class based on which CodeWeaver packages are installed.
"""

from __future__ import annotations

import importlib.util
import logging
from typing import TYPE_CHECKING, Literal

if TYPE_CHECKING:
    from codeweaver.core.types.settings_model import BaseCodeWeaverSettings


logger = logging.getLogger(__name__)


def detect_root_package() -> Literal["server", "engine", "provider", "core"]:
    """Detect which package should be root based on what's installed.

    Priority (highest to lowest):
    1. code-weaver-server (full installation)
    2. code-weaver-engine (indexing/chunking only)
    3. code-weaver-providers (providers only)
    4. core (minimal - logging/telemetry only)

    Returns:
        The package type that should serve as root settings
    """
    # Check in priority order - highest level package wins
    if importlib.util.find_spec("codeweaver.server") is not None:
        logger.debug("Detected server package - using CodeWeaverSettings")
        return "server"

    if importlib.util.find_spec("codeweaver.engine") is not None:
        logger.debug("Detected engine package - using CodeWeaverEngineSettings")
        return "engine"

    if importlib.util.find_spec("codeweaver.providers") is not None:
        logger.debug("Detected providers package - using CodeWeaverProviderSettings")
        return "provider"

    logger.debug("Only core package detected - using CodeWeaverCoreSettings")
    return "core"


def get_settings(**kwargs) -> BaseCodeWeaverSettings:
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
        settings = get_settings(project_path="/path/to/project")
        ```
    """
    package = detect_root_package()

    match package:
        case "server":
            from codeweaver.server.config.settings import CodeWeaverSettings

            return CodeWeaverSettings(**kwargs)

        case "engine":
            from codeweaver.engine.config.root_settings import CodeWeaverEngineSettings

            return CodeWeaverEngineSettings(**kwargs)

        case "provider":
            from codeweaver.providers.config.root_settings import CodeWeaverProviderSettings

            return CodeWeaverProviderSettings(**kwargs)

        case "core":
            from codeweaver.core.config.core_settings import CodeWeaverCoreSettings

            return CodeWeaverCoreSettings(**kwargs)


__all__ = ("detect_root_package", "get_settings")
