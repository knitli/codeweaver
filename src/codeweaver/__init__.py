# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""
CodeWeaver - Intelligent codebase context discovery.
"""

from __future__ import annotations

# Suppress pydantic deprecation warnings from third-party dependencies
# This must be at the very top before any imports
import contextlib
import warnings

from types import MappingProxyType
from typing import TYPE_CHECKING, Final


with contextlib.suppress(ImportError):
    # Google's `genai` package uses outdated pydantic features that trigger deprecation warnings with our newer pydantic version.
    from pydantic.warnings import PydanticDeprecatedSince212

    warnings.simplefilter("ignore", PydanticDeprecatedSince212)

# Suppress Pydantic 2.12+ UnsupportedFieldAttributeWarning
# This warning is triggered when Field(exclude=True) is used in Annotated type aliases
# See: https://github.com/wandb/wandb/issues/10662
# The warning is cosmetic - the fields still work correctly, the exclude parameter is just ignored
warnings.filterwarnings(
    "ignore",
    message=r"The '(exclude|repr|frozen)' attribute.*was provided to the `Field\(\)` function",
    category=UserWarning,
    module=r"pydantic\._internal\._generate_schema",
)

# Suppress OpenTelemetry deprecation warnings from dependencies
# These are from opentelemetry internal API changes that dependencies haven't updated yet
warnings.filterwarnings(
    "ignore",
    message=r"You should use `.*` instead\. Deprecated since version",
    category=DeprecationWarning,
)

from codeweaver.core import create_lazy_getattr


def get_version() -> str:
    """Get the current version of CodeWeaver.

    Because our version is dynamically generated during build/release, we try several methods to get it. If you downloaded CodeWeaver from PyPi, then the first will work, or the second if the file didn't get generated for some reason. If you're running from source, we try to get the version from git tags. If all else fails, we return "0.0.0".
    """
    try:
        from codeweaver._version import __version__
    except ImportError:
        try:
            import importlib.metadata

            __version__ = importlib.metadata.version("codeweaver")
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


if TYPE_CHECKING:
    from codeweaver_daemon import (
        check_daemon_health,
        request_daemon_shutdown,
        spawn_daemon_process,
        start_daemon_if_needed,
        wait_for_daemon_shutdown,
    )
    from codeweaver_tokenizers import TiktokenTokenizer, Tokenizer, Tokenizers


_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "TiktokenTokenizer": ("codeweaver_tokenizers", "TiktokenTokenizer"),
    "Tokenizer": ("codeweaver_tokenizers", "Tokenizer"),
    "Tokenizers": ("codeweaver_tokenizers", "Tokenizers"),
    "spawn_daemon_process": ("codeweaver_daemon", "spawn_daemon_process"),
    "check_daemon_health": ("codeweaver_daemon", "check_daemon_health"),
    "request_daemon_shutdown": ("codeweaver_daemon", "request_daemon_shutdown"),
    "start_daemon_if_needed": ("codeweaver_daemon", "start_daemon_if_needed"),
    "wait_for_daemon_shutdown": ("codeweaver_daemon", "wait_for_daemon_shutdown"),
})

__getattr__ = create_lazy_getattr(_dynamic_imports, globals(), __name__)


__all__ = (
    "TiktokenTokenizer",
    "Tokenizer",
    "Tokenizers",
    "__version__",
    "check_daemon_health",
    "request_daemon_shutdown",
    "spawn_daemon_process",
    "start_daemon_if_needed",
    "wait_for_daemon_shutdown",
)


def __dir__() -> list[str]:
    return list(__all__)
