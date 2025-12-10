# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

# sourcery skip: no-complex-if-expressions
"""Tools, Resources, and Prompts exposed to users and Users' Agents. Currently there's only one: `find_code` and we don't plan to change that soon."""

from __future__ import annotations

import contextlib
import logging

from typing import Any, cast

from fastmcp.server.context import Context
from mcp.server.session import ServerSession
from mcp.shared.context import RequestContext
from starlette.requests import Request

from codeweaver.agent_api.find_code import find_code
from codeweaver.agent_api.find_code.intent import IntentType
from codeweaver.agent_api.find_code.types import FindCodeResponseSummary
from codeweaver.common.utils import lazy_import
from codeweaver.core.language import SemanticSearchLanguage


_logger = logging.getLogger(__name__)


# -------------------------
# * `find_code` tool definition
#
# * This is the function that gets called when an MCP agent invokes the `find_code` tool. The mcp Tool definition is in `codeweaver.mcp.tools`. This find_code_tool wraps the actual `find_code`, which is defined in `codeweaver.agent_api.find_code`.
# -------------------------
async def find_code_tool(
    query: str,
    intent: IntentType | None = None,
    *,
    token_limit: int = 30000,
    focus_languages: tuple[SemanticSearchLanguage | str, ...] | None = None,
    context: Context,
) -> FindCodeResponseSummary:
    """CodeWeaver's `find_code` tool is an advanced code search function that leverages context and task-aware semantic search to identify and retrieve relevant code snippets from a codebase using natural language queries. `find_code` uses advanced sparse and dense embedding models, and reranking models to provide the best possible results. It is purpose-built for AI coding agents to assist with code understanding, implementation, debugging, optimization, testing, configuration, and documentation tasks.

    To use it, provide a natural language query describing what you are looking for. You can optionally specify an intent to help narrow down the search results. You can also set a token limit to control the size of the response, and filter results by programming language.

    Args:
        query: Natural language search query
        intent: Optional search intent. One of `understand`, `implement`, `debug`, `optimize`, `test`, `configure`, `document`
        token_limit: Maximum tokens to return (default: 30000)
        focus_languages: Optional language filter
        context: MCP context for request tracking

    Returns:
        FindCodeResponseSummary with ranked matches and metadata

    Raises:
        QueryError: If search fails unexpectedly
    """
    try:
        # Call the real find_code implementation
        # Convert focus_languages from SemanticSearchLanguage to str tuple
        focus_langs = (
            tuple(
                lang.variable if hasattr(lang, "variable") else str(lang)
                for lang in focus_languages
            )
            if focus_languages
            else None
        )
        statistics = lazy_import("codeweaver.common.statistics", "get_session_statistics")

        # Set context on failover manager for notifications
        from codeweaver.server.server import get_state

        state = get_state()
        if state.failover_manager and context:
            state.failover_manager.set_context(context)

        response = await find_code(
            query=query,
            intent=intent,
            token_limit=token_limit,
            focus_languages=cast(tuple[str, ...], focus_langs),
            max_results=30,  # Default from find_code signature
        )

        with contextlib.suppress(RuntimeError):
            # try to get request id from context for logging and stats.
            # Context is only available when called via MCP and will raise ValueError otherwise.
            # Track successful request in statistics
            if (
                context
                and hasattr(context, "request_context")
                and (request_context := context.request_context)  # type: ignore
            ):
                request_context: RequestContext[ServerSession, Any, Request]
                request_id = request_context.request_id
                statistics().add_successful_request(request_id)

        # Add failover metadata if failover manager exists
        if state.failover_manager:
            failover_metadata = {
                "failover": {
                    "enabled": state.failover_manager.backup_enabled,
                    "active": state.failover_manager.is_failover_active,
                    "active_store_type": "backup"
                    if state.failover_manager.is_failover_active
                    else "primary",
                }
            }
            # Set metadata on response
            response = response.model_copy(update={"metadata": failover_metadata})

    except Exception as e:
        # Track failed request
        if context:
            statistics().log_request_from_context(context, successful=False)

        # Log the error
        _logger.exception("find_code failed")

        # Import here to avoid circular dependency
        from codeweaver.exceptions import QueryError

        raise QueryError(
            f"Unexpected error in find_code: {e!s}",
            suggestions=["Try a simpler query", "Check server logs for details"],
        ) from e

    else:
        return response


__all__ = ("find_code_tool",)
