# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""
CodeWeaver - Intelligent codebase context discovery.
"""

from __future__ import annotations

import contextlib
import warnings

from typing import Final


with contextlib.suppress(ImportError):
    # Google's `genai` package uses outdated pydantic features that trigger deprecation warnings with our newer pydantic version.
    from pydantic.warnings import PydanticDeprecatedSince212

    warnings.simplefilter("ignore", PydanticDeprecatedSince212)

warnings.filterwarnings(
    "ignore",
    message=r"The '(exclude|repr|frozen)' attribute.*was provided to the `Field\(\)` function",
    category=UserWarning,
    module=r"pydantic\._internal\._generate_schema",
)

warnings.filterwarnings(
    "ignore",
    message=r"You should use `.*` instead\. Deprecated since version",
    category=DeprecationWarning,
)


def get_version() -> str:
    """Get the current version of CodeWeaver.

    Because our version is dynamically generated during build/release, we try several methods to get it. If you downloaded CodeWeaver from PyPi, then the first will work, or the second if the file didn't get generated for some reason. If you're running from source, we try to get the version from git tags. If all else fails, we return "0.0.0".
    """
    try:
        from codeweaver._version import __version__
    except ImportError:
        try:
            import importlib.metadata

            __version__ = importlib.metadata.version("code-weaver")
        except importlib.metadata.PackageNotFoundError:
            try:
                import shutil
                import subprocess

                # Try to get version from git if available
                # Git commands work from any directory within a repo, so no need to specify cwd
                # The subprocess call is safe because we use the system to find the executable, not user input
                if git := shutil.which("git"):
                    git_describe = subprocess.run(  # noqa: S603
                        [git, "describe", "--tags", "--always", "--dirty"],
                        capture_output=True,
                        text=True,
                        check=False,
                    )
                    if git_describe.returncode == 0:
                        __version__ = git_describe.stdout.strip()
                    else:
                        __version__ = "0.0.0"
                else:
                    __version__ = "0.0.0"
            except Exception:
                __version__ = "0.0.0"
    return __version__


__version__: Final[str] = get_version()

# === MANAGED EXPORTS ===

# Exportify manages this section. It contains lazy-loading infrastructure
# for the package: imports and runtime declarations (__all__, __getattr__,
# __dir__). Manual edits will be overwritten by `exportify fix`.

from types import MappingProxyType
from typing import TYPE_CHECKING

from lateimport import create_late_getattr


if TYPE_CHECKING:
    from codeweaver.server.mcp.middleware.fastmcp import (
        DetailedTimingMiddleware,
        ErrorHandlingMiddleware,
        LoggingMiddleware,
        McpMiddleware,
        RateLimitingMiddleware,
        ResponseCachingMiddleware,
        RetryMiddleware,
        StructuredLoggingMiddleware,
    )
    from codeweaver.server.mcp.middleware.statistics import StatisticsMiddleware

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "DetailedTimingMiddleware": (__spec__.parent, "server.mcp.middleware.fastmcp"),
    "ErrorHandlingMiddleware": (__spec__.parent, "server.mcp.middleware.fastmcp"),
    "LoggingMiddleware": (__spec__.parent, "server.mcp.middleware.fastmcp"),
    "McpMiddleware": (__spec__.parent, "server.mcp.middleware.fastmcp"),
    "RateLimitingMiddleware": (__spec__.parent, "server.mcp.middleware.fastmcp"),
    "ResponseCachingMiddleware": (__spec__.parent, "server.mcp.middleware.fastmcp"),
    "RetryMiddleware": (__spec__.parent, "server.mcp.middleware.fastmcp"),
    "StatisticsMiddleware": (__spec__.parent, "server.mcp.middleware.statistics"),
    "StructuredLoggingMiddleware": (__spec__.parent, "server.mcp.middleware.fastmcp"),
})

__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    "DetailedTimingMiddleware",
    "ErrorHandlingMiddleware",
    "LoggingMiddleware",
    "McpMiddleware",
    "RateLimitingMiddleware",
    "ResponseCachingMiddleware",
    "RetryMiddleware",
    "StatisticsMiddleware",
    "StructuredLoggingMiddleware",
)


def __dir__() -> list[str]:
    """List available attributes for the package."""
    return list(__all__)
