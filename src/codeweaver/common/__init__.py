# pyright: reportUnsupportedDunderAll=none
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Infrastructure package for CodeWeaver. Infrastructure includes cross-cutting concerns such as logging, statistics, utilities. The types module defines types used throughout the infrastructure package, but is not cross-cutting itself."""

from importlib import import_module
from types import MappingProxyType
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    # Import everything for IDE and type checker support
    # These imports are never executed at runtime, only during type checking
    from codeweaver.common.logging import log_to_client_or_fallback, setup_logger
    from codeweaver.common.statistics import (
        FileStatistics,
        Identifier,
        SessionStatistics,
        TimingStatistics,
        TokenCategory,
        TokenCounter,
        add_failed_request,
        add_successful_request,
        get_session_statistics,
        record_timed_http_request,
        timed_http,
    )
    from codeweaver.common.types import (
        CallHookTimingDict,
        HttpRequestsDict,
        McpComponentRequests,
        McpComponentTimingDict,
        McpOperationRequests,
        McpTimingDict,
        ResourceUri,
        TimingStatisticsDict,
        ToolOrPromptName,
    )
    from codeweaver.common.utils import (
        LazyImport,
        ensure_iterable,
        estimate_tokens,
        file_is_binary,
        get_git_branch,
        get_git_revision,
        get_possible_env_vars,
        get_project_path,
        has_package,
        in_codeweaver_clone,
        is_class,
        is_debug,
        is_git_dir,
        is_pydantic_basemodel,
        is_test_environment,
        is_typeadapter,
        lazy_import,
        normalize_ext,
        rpartial,
        sanitize_unicode,
        set_relative_path,
        try_git_rev_parse,
        uuid7,
    )


_MARKUP_TAG = "bold dark_orange"

CODEWEAVER_PREFIX = f"[{_MARKUP_TAG}]CodeWeaver[/{_MARKUP_TAG}]"

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "CallHookTimingDict": (__spec__.parent, "types"),
    "FileStatistics": (__spec__.parent, "statistics"),
    "HttpRequestsDict": (__spec__.parent, "types"),
    "Identifier": (__spec__.parent, "statistics"),
    "LazyImport": (__spec__.parent, "utils"),
    "McpComponentRequests": (__spec__.parent, "types"),
    "McpComponentTimingDict": (__spec__.parent, "types"),
    "McpOperationRequests": (__spec__.parent, "types"),
    "McpTimingDict": (__spec__.parent, "types"),
    "ResourceUri": (__spec__.parent, "types"),
    "SessionStatistics": (__spec__.parent, "statistics"),
    "TimingStatistics": (__spec__.parent, "statistics"),
    "TimingStatisticsDict": (__spec__.parent, "types"),
    "TokenCategory": (__spec__.parent, "statistics"),
    "TokenCounter": (__spec__.parent, "statistics"),
    "ToolOrPromptName": (__spec__.parent, "types"),
    "add_failed_request": (__spec__.parent, "statistics"),
    "add_successful_request": (__spec__.parent, "statistics"),
    "ensure_iterable": (__spec__.parent, "utils"),
    "estimate_tokens": (__spec__.parent, "utils"),
    "file_is_binary": (__spec__.parent, "utils"),
    "get_git_branch": (__spec__.parent, "utils"),
    "get_git_revision": (__spec__.parent, "utils"),
    "get_possible_env_vars": (__spec__.parent, "utils"),
    "get_project_path": (__spec__.parent, "utils"),
    "get_session_statistics": (__spec__.parent, "statistics"),
    "get_user_config_dir": (__spec__.parent, "utils"),
    "has_package": (__spec__.parent, "utils"),
    "in_codeweaver_clone": (__spec__.parent, "utils"),
    "is_class": (__spec__.parent, "utils"),
    "is_debug": (__spec__.parent, "utils"),
    "is_git_dir": (__spec__.parent, "utils"),
    "is_pydantic_basemodel": (__spec__.parent, "utils"),
    "is_test_environment": (__spec__.parent, "utils"),
    "is_typeadapter": (__spec__.parent, "utils"),
    "lazy_import": (__spec__.parent, "utils"),
    "log_to_client_or_fallback": (__spec__.parent, "logging"),
    "normalize_ext": (__spec__.parent, "utils"),
    "record_timed_http_request": (__spec__.parent, "statistics"),
    "rpartial": (__spec__.parent, "utils"),
    "sanitize_unicode": (__spec__.parent, "utils"),
    "set_relative_path": (__spec__.parent, "utils"),
    "setup_logger": (__spec__.parent, "logging"),
    "timed_http": (__spec__.parent, "statistics"),
    "try_git_rev_parse": (__spec__.parent, "utils"),
    "uuid7": (__spec__.parent, "utils"),
})
"""Dynamically import submodules and classes for the common package.

Maps class/function/type names to their respective module paths for lazy loading.
"""


def __getattr__(name: str) -> object:
    """Dynamically import submodules and classes for the semantic package."""
    if name in _dynamic_imports:
        module_name, submodule_name = _dynamic_imports[name]
        module = import_module(f"{module_name}.{submodule_name}")
        result = getattr(module, name)
        globals()[name] = result  # Cache in globals for future access
        return result
    if globals().get(name) is not None:
        return globals()[name]
    raise AttributeError(f"module {__name__} has no attribute {name}")


__all__ = (
    "CODEWEAVER_PREFIX",
    "CallHookTimingDict",
    "FileStatistics",
    "HttpRequestsDict",
    "Identifier",
    "LazyImport",
    "McpComponentRequests",
    "McpComponentTimingDict",
    "McpOperationRequests",
    "McpTimingDict",
    "ResourceUri",
    "SessionStatistics",
    "TimingStatistics",
    "TimingStatisticsDict",
    "TokenCategory",
    "TokenCounter",
    "ToolOrPromptName",
    "add_failed_request",
    "add_successful_request",
    "ensure_iterable",
    "estimate_tokens",
    "file_is_binary",
    "get_git_branch",
    "get_git_revision",
    "get_possible_env_vars",
    "get_project_path",
    "get_session_statistics",
    "get_user_config_dir",
    "has_package",
    "in_codeweaver_clone",
    "is_class",
    "is_debug",
    "is_git_dir",
    "is_pydantic_basemodel",
    "is_test_environment",
    "is_typeadapter",
    "lazy_import",
    "log_to_client_or_fallback",
    "normalize_ext",
    "record_timed_http_request",
    "rpartial",
    "sanitize_unicode",
    "set_relative_path",
    "setup_logger",
    "timed_http",
    "try_git_rev_parse",
    "uuid7",
)


def __dir__() -> list[str]:
    """List available attributes for the semantic package."""
    return list(__all__)
