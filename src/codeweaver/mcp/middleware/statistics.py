# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# sourcery skip: avoid-single-character-names-variables

# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Statistics middleware for FastMCP."""

from __future__ import annotations

import logging
import time

from collections.abc import Sequence
from typing import Any, cast, overload, override

from fastmcp.prompts import Prompt
from fastmcp.resources import Resource, ResourceTemplate
from fastmcp.server.middleware import CallNext
from fastmcp.server.middleware import MiddlewareContext as McpMiddlewareContext
from fastmcp.server.middleware.middleware import Middleware as McpMiddleware
from fastmcp.tools.tool import Tool, ToolResult
from mcp.server.lowlevel.helper_types import ReadResourceContents
from mcp.types import (
    CallToolRequestParams,
    GetPromptRequestParams,
    GetPromptResult,
    ListPromptsRequest,
    ListResourcesRequest,
    ListResourceTemplatesRequest,
    ListToolsRequest,
    ReadResourceRequestParams,
)
from pydantic import AnyUrl
from typing_extensions import TypeIs

from codeweaver.common.statistics import (
    McpOperationRequests,
    SessionStatistics,
    TimingStatistics,
    get_session_statistics,
)
from codeweaver.common.types import TimingStatisticsDict
from codeweaver.exceptions import ProviderError


class StatisticsMiddleware(McpMiddleware):
    """Middleware to track request statistics and performance metrics."""

    def __init__(
        self,
        statistics: SessionStatistics | None = None,
        logger: logging.Logger | None = None,
        log_level: int = logging.WARNING,
    ) -> None:
        """Initialize statistics middleware.

        Args:
            statistics: Statistics instance to use for tracking
            logger: Logger instance to use for logging
            log_level: Logging level to use
        """
        self.statistics = statistics or get_session_statistics()
        self.timing_statistics = self.statistics.timing_statistics
        self.logger = logger or logging.getLogger(__name__)
        self.log_level = log_level or logging.WARNING
        self._we_are_not_none()

    def _stats_is_stats(self, statistics: Any) -> TypeIs[SessionStatistics]:
        return isinstance(statistics, SessionStatistics)

    def _timing_stats_is_stats(self, timing: Any) -> TypeIs[TimingStatistics]:
        return isinstance(timing, TimingStatistics)

    def _we_are_not_none(self) -> None:
        """Ensure that all required statistics are present."""
        if not self.statistics:
            raise ProviderError("Failed to initialize statistics middleware provider.")
        if not self.timing_statistics:
            raise ProviderError("Failed to initialize timing statistics.")

    # Trust me, I tried to define this with generics, but it was a nightmare. I blame the fastmcp types (but it's probably me).
    @overload
    async def _time_operation(
        self,
        context: McpMiddlewareContext[CallToolRequestParams],
        call_next: CallNext[CallToolRequestParams, ToolResult],
        operation_name: str,
        tool_or_resource_name: str,
    ) -> ToolResult: ...
    @overload
    async def _time_operation(
        self,
        context: McpMiddlewareContext[ReadResourceRequestParams],
        call_next: CallNext[ReadResourceRequestParams, Sequence[ReadResourceContents]],
        operation_name: str,
        tool_or_resource_name: AnyUrl,
    ) -> Sequence[ReadResourceContents]: ...
    @overload
    async def _time_operation(
        self,
        context: McpMiddlewareContext[GetPromptRequestParams],
        call_next: CallNext[GetPromptRequestParams, GetPromptResult],
        operation_name: str,
        tool_or_resource_name: str,
    ) -> GetPromptResult: ...
    @overload
    async def _time_operation(
        self,
        context: McpMiddlewareContext[ListResourcesRequest],
        call_next: CallNext[ListResourcesRequest, list[Resource]],
        operation_name: str,
        tool_or_resource_name: None = None,
    ) -> list[Resource]: ...
    @overload
    async def _time_operation(
        self,
        context: McpMiddlewareContext[ListResourceTemplatesRequest],
        call_next: CallNext[ListResourceTemplatesRequest, list[ResourceTemplate]],
        operation_name: str,
        tool_or_resource_name: None = None,
    ) -> list[ResourceTemplate]: ...
    @overload
    async def _time_operation(
        self,
        context: McpMiddlewareContext[ListPromptsRequest],
        call_next: CallNext[ListPromptsRequest, list[Prompt]],
        operation_name: str,
        tool_or_resource_name: None = None,
    ) -> list[Prompt]: ...
    @overload
    async def _time_operation(
        self,
        context: McpMiddlewareContext[ListToolsRequest],
        call_next: CallNext[ListToolsRequest, list[Tool]],
        operation_name: str,
        tool_or_resource_name: None = None,
    ) -> list[Tool]: ...
    async def _time_operation(
        self,
        context: McpMiddlewareContext[Any],
        call_next: CallNext[Any, Any],
        operation_name: str,
        tool_or_resource_name: str | AnyUrl | None = None,
    ) -> Any:
        """Helper method to time any operation."""
        if not self._stats_is_stats(self.statistics) or not self._timing_stats_is_stats(
            self.timing_statistics
        ):
            raise ProviderError("Statistics middleware is not properly initialized.")
        start_time = time.perf_counter()
        request_id = (
            context.fastmcp_context.request_id if context and context.fastmcp_context else None
        )

        try:
            result = await call_next(context)
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.statistics.add_successful_request(request_id=request_id)
            self.timing_statistics.update(
                cast(McpOperationRequests, operation_name),
                duration_ms,
                tool_or_resource_name=tool_or_resource_name,
            )

        except Exception:
            duration_ms = (time.perf_counter() - start_time) * 1000
            self.statistics.add_failed_request(request_id=request_id)
            self.logger.warning(
                "Operation in %s failed after %.2fms",
                operation_name,
                duration_ms,
                extra={"failed_operation": operation_name, "duration_ms": duration_ms},
                exc_info=True,
            )
            raise
        else:
            return result

    async def on_call_tool(
        self,
        context: McpMiddlewareContext[CallToolRequestParams],
        call_next: CallNext[CallToolRequestParams, ToolResult],
    ) -> ToolResult:
        """Handle incoming requests and track statistics."""
        return await self._time_operation(
            context, call_next, "on_call_tool_requests", context.message.name
        )

    @override
    async def on_read_resource(
        self,
        context: McpMiddlewareContext[ReadResourceRequestParams],
        call_next: CallNext[ReadResourceRequestParams, Sequence[ReadResourceContents]],
    ) -> Sequence[ReadResourceContents]:
        """Handle resource read requests and track statistics."""
        return await self._time_operation(
            context, call_next, "on_read_resource_requests", context.message.uri
        )

    async def on_get_prompt(
        self,
        context: McpMiddlewareContext[GetPromptRequestParams],
        call_next: CallNext[GetPromptRequestParams, GetPromptResult],
    ) -> GetPromptResult:
        """Handle prompt retrieval requests and track statistics."""
        return await self._time_operation(
            context, call_next, "on_get_prompt_requests", context.message.name
        )

    async def on_list_tools(
        self,
        context: McpMiddlewareContext[ListToolsRequest],
        call_next: CallNext[ListToolsRequest, list[Tool]],
    ) -> list[Tool]:
        """Handle tool listing requests and track statistics."""
        return await self._time_operation(context, call_next, "on_list_tools_requests")

    async def on_list_resources(
        self,
        context: McpMiddlewareContext[ListResourcesRequest],
        call_next: CallNext[ListResourcesRequest, list[Resource]],
    ) -> list[Resource]:
        """Handle resource listing requests and track statistics."""
        return await self._time_operation(context, call_next, "on_list_resources_requests")

    async def on_list_resource_templates(
        self,
        context: McpMiddlewareContext[ListResourceTemplatesRequest],
        call_next: CallNext[ListResourceTemplatesRequest, list[ResourceTemplate]],
    ) -> list[ResourceTemplate]:
        """Handle resource template listing requests and track statistics."""
        return await self._time_operation(context, call_next, "on_list_resource_templates_requests")

    async def on_list_prompts(
        self,
        context: McpMiddlewareContext[ListPromptsRequest],
        call_next: CallNext[ListPromptsRequest, list[Prompt]],
    ) -> list[Prompt]:
        """Handle prompt listing requests and track statistics."""
        return await self._time_operation(context, call_next, "on_list_prompts_requests")

    def get_statistics(self) -> SessionStatistics:
        """Get current statistics.

        Returns:
            Current session statistics
        """
        return self.statistics

    def get_timing_statistics(self) -> TimingStatisticsDict:
        """Get current timing statistics.

        Returns:
            Current timing statistics
        """
        if not self.timing_statistics:
            raise ProviderError("Timing statistics not initialized.")
        return self.timing_statistics.timing_summary

    def reset_statistics(self) -> None:
        """Reset all statistics to initial state."""
        self.statistics.reset()


__all__ = ("StatisticsMiddleware",)
