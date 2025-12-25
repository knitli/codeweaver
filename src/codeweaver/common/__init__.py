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
    from codeweaver.common._logging import log_to_client_or_fallback, setup_logger
    from codeweaver.common.http_pool import (
        HttpClientPool,
        PoolLimits,
        PoolTimeouts,
        get_http_pool,
        reset_http_pool,
        reset_http_pool_sync,
    )
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


_MARKUP_TAG = "bold dark_orange"

CODEWEAVER_PREFIX = f"[{_MARKUP_TAG}]CodeWeaver[/{_MARKUP_TAG}]"

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "CallHookTimingDict": (__spec__.parent, "types"),
    "FileStatistics": (__spec__.parent, "statistics"),
    "HttpClientPool": (__spec__.parent, "http_pool"),
    "HttpRequestsDict": (__spec__.parent, "types"),
    "Identifier": (__spec__.parent, "statistics"),
    "McpComponentRequests": (__spec__.parent, "types"),
    "McpComponentTimingDict": (__spec__.parent, "types"),
    "McpOperationRequests": (__spec__.parent, "types"),
    "McpTimingDict": (__spec__.parent, "types"),
    "PoolLimits": (__spec__.parent, "http_pool"),
    "PoolTimeouts": (__spec__.parent, "http_pool"),
    "ResourceUri": (__spec__.parent, "types"),
    "SessionStatistics": (__spec__.parent, "statistics"),
    "TimingStatistics": (__spec__.parent, "statistics"),
    "TimingStatisticsDict": (__spec__.parent, "types"),
    "TokenCategory": (__spec__.parent, "statistics"),
    "TokenCounter": (__spec__.parent, "statistics"),
    "ToolOrPromptName": (__spec__.parent, "types"),
    "add_failed_request": (__spec__.parent, "statistics"),
    "add_successful_request": (__spec__.parent, "statistics"),

    "get_http_pool": (__spec__.parent, "http_pool"),
    "get_session_statistics": (__spec__.parent, "statistics"),
    "log_to_client_or_fallback": (__spec__.parent, "_logging"),
    "record_timed_http_request": (__spec__.parent, "statistics"),
    "reset_http_pool": (__spec__.parent, "http_pool"),
    "reset_http_pool_sync": (__spec__.parent, "http_pool"),
    "setup_logger": (__spec__.parent, "_logging"),
    "timed_http": (__spec__.parent, "statistics"),
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
    "HttpClientPool",
    "HttpRequestsDict",
    "Identifier",
    "McpComponentRequests",
    "McpComponentTimingDict",
    "McpOperationRequests",
    "McpTimingDict",
    "PoolLimits",
    "PoolTimeouts",
    "ResourceUri",
    "SessionStatistics",
    "TimingStatistics",
    "TimingStatisticsDict",
    "TokenCategory",
    "TokenCounter",
    "ToolOrPromptName",
    "add_failed_request",
    "add_successful_request",
    "get_http_pool",
    "get_session_statistics",
    "log_to_client_or_fallback",
    "record_timed_http_request",
    "reset_http_pool",
    "reset_http_pool_sync",
    "setup_logger",
    "timed_http",
)


def __dir__() -> list[str]:
    """List available attributes for the semantic package."""
    return list(__all__)
