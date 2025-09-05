# sourcery skip: avoid-global-variables
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Main FastMCP server implementation for CodeWeaver."""

from __future__ import annotations

import asyncio

from types import FunctionType
from typing import TYPE_CHECKING, Any

from fastmcp import Context, FastMCP
from pydantic import TypeAdapter
from typing_extensions import TypeIs

from codeweaver import __version__ as version
from codeweaver._server import (
    Feature,
    HealthInfo,
    HealthStatus,
    get_health_info,
    get_state,
    get_statistics,
    initialize_app,
)
from codeweaver._server import get_settings as get_app_settings
from codeweaver._statistics import SessionStatistics
from codeweaver.exceptions import CodeWeaverError
from codeweaver.models.core import FindCodeResponseSummary
from codeweaver.tools.find_code import find_code_implementation


if TYPE_CHECKING:
    from codeweaver._server import AppState
    from codeweaver.language import SemanticSearchLanguage
    from codeweaver.models.intent import IntentType


def is_fastmcp_instance(app: Any) -> TypeIs[FastMCP[AppState]]:
    """Validate if the given app is an instance of FastMCP."""
    return isinstance(app, FastMCP)


# Create FastMCP application
app, run_method = asyncio.run(initialize_app())  # type: ignore  # the types are just below :arrow_lower_left:
if not is_fastmcp_instance(app):
    raise TypeError("Expected app to be an instance of FastMCP")
run_method: FunctionType


@app.tool(tags={"user", "external", "code"})
async def find_code(
    query: str,
    intent: IntentType | None = None,
    *,
    token_limit: int = 10000,
    include_tests: bool = False,
    focus_languages: tuple[SemanticSearchLanguage, ...] | None = None,
    context: Context | None = None,
) -> FindCodeResponseSummary:
    """Intelligently discover and retrieve relevant codebase context.

    Phase 1 implementation provides basic file discovery and keyword-based search.
    Future phases will add semantic embeddings and AI-powered intent analysis.

    Args:
        query: Natural language description of the information you need
        intent: An optional hint about the type of information you need based on the user's task to you. One of "understand", "implement", "debug", "optimize", "test", "configure", or "document".
        include_tests: Whether to include test files in results
        focus_languages: Limit search to specific programming languages
        context: FastMCP context (injected automatically)

    Returns:
        Structured response with relevant code matches and metadata

    Examples:
        query="authentication middleware setup"
        query="database connection pooling configuration"
        query="user registration validation logic"
    """
    statistics = get_statistics()
    settings = get_app_settings()
    try:
        # Execute the find_code implementation
        response = await find_code_implementation(
            query=query,
            settings=settings,
            intent=intent,
            token_limit=token_limit,
            include_tests=include_tests,
            focus_languages=focus_languages,
            statistics=statistics,
        )

        # Record successful request
        if statistics:
            statistics.add_successful_request()

    except CodeWeaverError:
        if statistics:
            statistics.log_request_from_context(context, successful=False)
        raise
    except Exception as e:
        if statistics:
            statistics.log_request_from_context(context, successful=False)

        from codeweaver.exceptions import QueryError

        raise QueryError(
            f"Unexpected error in `find_code`: {e!s}",
            suggestions=["Try a simpler query", "Check server logs for details"],
        ) from e
    else:
        return response


@app.custom_route("/stats", methods=["GET"], tags={"system", "stats"}, include_in_schema=True)  # type: ignore
async def stats_info() -> bytes:
    """Get the current statistics information."""
    statistics = get_statistics()
    return TypeAdapter(statistics).dump_json(statistics, indent=2)  # pyright: ignore[reportUnknownMemberType, reportReturnType,reportOptionalMemberAccess]  # we establish it exists down in the initialization


@app.custom_route("/settings", methods=["GET"], tags={"system", "settings"}, include_in_schema=True)  # type: ignore
async def settings_info() -> bytes:
    """Get the current settings information."""
    return get_state().settings.model_dump_json(indent=2)  # pyright: ignore[reportReturnType,reportOptionalMemberAccess]  # we establish it exists down in the initialization


@app.custom_route("/version", methods=["GET"], tags={"system", "version"}, include_in_schema=True)  # type: ignore
async def version_info() -> bytes:
    """Get the current version information."""
    return f"CodeWeaver version: {version}".encode()


@app.custom_route("/health", methods=["GET"], tags={"system", "health"}, include_in_schema=True)  # type: ignore
async def health() -> bytes:
    """Health check endpoint for monitoring server status.

    Returns:
        Health status information with statistics
    """
    if health := get_health_info():
        # Return existing health info if available
        dumped_health: bytes = TypeAdapter(health).dump_json(health, indent=2)  # type: ignore
        return dumped_health
    unhealthy_status: HealthInfo = HealthInfo(
        status=HealthStatus.UNHEALTHY,
        version=version,
        features=(Feature._UNKNOWN,),  # pyright: ignore[reportPrivateUsage]
    )
    return TypeAdapter(unhealthy_status).dump_json(unhealthy_status, indent=2)  # type: ignore


def is_health_instance(health_info: Any) -> TypeIs[HealthInfo]:
    """Check if the provided health_info is a valid HealthInfo instance."""
    return isinstance(health_info, HealthInfo) and health_info.status in HealthStatus


def is_appstate_instance(state: Any) -> TypeIs[AppState]:
    """Check if the provided state is a valid AppState instance."""
    return isinstance(state, AppState)


def is_statistics_instance(statistics: Any) -> TypeIs[SessionStatistics]:
    """Check if the provided statistics is a valid Statistics instance."""
    return isinstance(statistics, SessionStatistics)


if __name__ == "__main__":
    # Main entry point for MCP
    asyncio.run(run_method(app))  # type: ignore
    asyncio.run(app.run_http_async())
    if not is_appstate_instance(get_state()):
        raise TypeError("Expected get_state() to be an instance of AppState")
    if not is_health_instance(get_health_info()):
        raise TypeError("Expected get_health_info() to be an instance of HealthInfo")
    if not is_statistics_instance(get_statistics()):
        raise TypeError("Expected get_statistics() to be an instance of SessionStatistics")
