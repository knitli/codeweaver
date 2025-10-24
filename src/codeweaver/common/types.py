"""Types for CodeWeaver infrastructure package."""

from __future__ import annotations

from typing import Literal, TypedDict

from pydantic import AnyUrl, NonNegativeFloat


# ===========================================================================
# *             Statistics Aliases and TypedDicts
# ===========================================================================

type ToolOrPromptName = str
type ResourceUri = AnyUrl

type McpComponentRequests = Literal[
    "on_call_tool_requests", "on_read_resource_requests", "on_get_prompt_requests"
]
type McpOperationRequests = Literal[
    "on_call_tool_requests",
    "on_read_resource_requests",
    "on_get_prompt_requests",
    "on_list_tools_requests",
    "on_list_resources_requests",
    "on_list_resource_templates_requests",
    "on_list_prompts_requests",
]


class McpTimingDict(TypedDict):
    """Typed dictionary for MCP timing statistics."""

    combined: NonNegativeFloat
    by_component: dict[ToolOrPromptName | ResourceUri, NonNegativeFloat]


class McpComponentTimingDict(TypedDict):
    """Typed dictionary for MCP component timing statistics."""

    on_call_tool_requests: McpTimingDict
    on_read_resource_requests: McpTimingDict
    on_get_prompt_requests: McpTimingDict


class HttpRequestsDict(TypedDict):
    """Typed dictionary for HTTP request timing statistics."""

    version: NonNegativeFloat
    health: NonNegativeFloat
    state: NonNegativeFloat
    statistics: NonNegativeFloat
    settings: NonNegativeFloat


class CallHookTimingDict(TypedDict):
    """Typed dictionary for MCP timing statistics."""

    on_call_tool_requests: McpTimingDict
    on_read_resource_requests: McpTimingDict
    on_get_prompt_requests: McpTimingDict
    on_list_tools_requests: NonNegativeFloat
    on_list_resources_requests: NonNegativeFloat
    on_list_resource_templates_requests: NonNegativeFloat
    on_list_prompts_requests: NonNegativeFloat
    http_requests: HttpRequestsDict


class TimingStatisticsDict(TypedDict):
    """Typed dictionary for MCP timing statistics."""

    averages: CallHookTimingDict
    counts: CallHookTimingDict
    lows: CallHookTimingDict
    medians: CallHookTimingDict
    highs: CallHookTimingDict


type RequestKind = Literal[
    "on_call_tool",
    "on_read_resource",
    "on_get_prompt",
    "on_list_tools",
    "on_list_resources",
    "on_list_resource_templates",
    "on_list_prompts",
    "http_requests",
]

type OperationsKey = Literal["indexed", "retrieved", "processed", "reindexed", "skipped"]
type SummaryKey = Literal["total_operations", "unique_files"]
type CategoryKey = Literal["code", "config", "docs", "other"]


__all__ = (
    "CallHookTimingDict",
    "CategoryKey",
    "HttpRequestsDict",
    "McpComponentRequests",
    "McpComponentTimingDict",
    "McpOperationRequests",
    "McpTimingDict",
    "OperationsKey",
    "RequestKind",
    "ResourceUri",
    "SummaryKey",
    "TimingStatisticsDict",
    "ToolOrPromptName",
)
