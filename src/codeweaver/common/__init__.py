"""Infrastructure package for CodeWeaver. Infrastructure includes cross-cutting concerns such as logging, statistics, utilities. The types module defines types used throughout the infrastructure package, but is not cross-cutting itself."""

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


__all__ = (
    "CallHookTimingDict",
    "FileStatistics",
    "HttpRequestsDict",
    "Identifier",
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
    "get_session_statistics",
    "log_to_client_or_fallback",
    "record_timed_http_request",
    "setup_logger",
    "timed_http",
)
