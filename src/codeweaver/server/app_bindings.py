# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Application bindings for CodeWeaver. Registers tools and routes."""

from __future__ import annotations

import contextlib
import logging

from collections.abc import Container
from functools import cache
from typing import TYPE_CHECKING, Any, cast

from fastmcp import Context
from fastmcp.server.middleware.middleware import Middleware
from fastmcp.tools import Tool
from mcp.shared.context import RequestContext
from mcp.shared.session import BaseSession
from mcp.types import ToolAnnotations
from pydantic import BaseModel, TypeAdapter
from pydantic_core import to_json
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from codeweaver.agent_api.find_code import find_code
from codeweaver.agent_api.find_code.intent import IntentType
from codeweaver.agent_api.find_code.types import FindCodeResponseSummary
from codeweaver.common.statistics import SessionStatistics, get_session_statistics, timed_http
from codeweaver.config.middleware import MiddlewareOptions
from codeweaver.config.settings import CodeWeaverSettingsDict, get_settings_map
from codeweaver.core.language import SemanticSearchLanguage
from codeweaver.core.types.dictview import DictView
from codeweaver.middleware.statistics import StatisticsMiddleware
from codeweaver.server.server import AppState, HealthInfo, get_health_info


_logger = logging.getLogger(__name__)

type PydanticType = type[BaseModel | TypeAdapter[Any]] | BaseModel | TypeAdapter[Any]

if TYPE_CHECKING:
    from fastmcp import FastMCP


@cache
def statistics() -> SessionStatistics:
    """Get the current session statistics."""
    return get_session_statistics()


@cache
def settings() -> DictView[CodeWeaverSettingsDict]:
    """Get the current settings."""
    return get_settings_map()


def health_info() -> HealthInfo:
    """Get the current health information."""
    return get_health_info()


# -------------------------
# * `find_code` tool entrypoint
# -------------------------
async def find_code_tool(
    query: str,
    intent: IntentType | None = None,
    *,
    token_limit: int = 10000,
    include_tests: bool = False,
    focus_languages: tuple[SemanticSearchLanguage, ...] | None = None,
    context: Context | None = None,
) -> FindCodeResponseSummary:
    """Use CodeWeaver to find code in the codebase.

    Args:
        query: Natural language search query
        intent: Optional search intent (if None, will be detected)
        token_limit: Maximum tokens to return (default: 10000)
        include_tests: Whether to include test files in results
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
            tuple(lang.value if hasattr(lang, "value") else str(lang) for lang in focus_languages)
            if focus_languages
            else None
        )

        response = await find_code(
            query=query,
            intent=intent,
            token_limit=token_limit,
            include_tests=include_tests,
            focus_languages=focus_langs,
            max_results=50,  # Default from find_code signature
        )

        with contextlib.suppress(ValueError):
            # try to get request id from context for logging and stats.
            # Context is only available when called via MCP and will raise ValueError otherwise.
            # Track successful request in statistics
            if (
                context
                and hasattr(context, "request_context")
                and (request_context := context.request_context)  # type: ignore
            ):
                request_context: RequestContext[BaseSession[Any, Any, Any, Any, Any], Any, Any]
                request_id = request_context.request_id
                statistics().add_successful_request(request_id)

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


# -------------------------
# Plain route handlers
# -------------------------
@timed_http("statistics")
async def stats_info(_request: Request) -> PlainTextResponse:
    """Return current session statistics as JSON."""
    global statistics
    stats: SessionStatistics = statistics()
    try:
        return PlainTextResponse(content=stats.report(), media_type="application/json")
    except Exception as e:
        _logger.exception("Failed to serialize session statistics")
        return PlainTextResponse(
            content=to_json({"error": f"Failed to serialize session statistics: {e}"}),
            status_code=500,
            media_type="application/json",
        )


@timed_http("settings")
async def settings_info(_request: Request) -> PlainTextResponse:
    """Return current settings as JSON."""
    settings_view: DictView[CodeWeaverSettingsDict] = settings()
    try:
        return PlainTextResponse(
            content=to_json(dict(settings_view.items())), media_type="application/json"
        )
    except Exception as e:
        _logger.exception("Failed to serialize settings")
        return PlainTextResponse(
            content=to_json({"error": f"Failed to serialize settings: {e}"}),
            status_code=500,
            media_type="application/json",
        )


@timed_http("version")
async def version_info(_request: Request) -> PlainTextResponse:
    """Return current version information as JSON."""
    from codeweaver import __version__

    try:
        return PlainTextResponse(
            content=to_json({"version": __version__}), media_type="application/json"
        )
    except Exception as e:
        _logger.exception("Failed to serialize version information")
        return PlainTextResponse(
            content=to_json({"error": f"Failed to serialize version information: {e}"}),
            status_code=500,
            media_type="application/json",
        )


@timed_http("state")
async def state_info(_request: Request) -> PlainTextResponse:
    """Return the complete application state as JSON."""
    from codeweaver.server.server import get_state

    state = get_state()
    return PlainTextResponse(content=state.dump_json(), media_type="application/json")


@timed_http("health")
async def health(_request: Request) -> PlainTextResponse:
    """Return enhanced health information as JSON (FR-010-Enhanced).

    Provides comprehensive system health including:
    - Overall status (healthy/degraded/unhealthy)
    - Indexing progress and state
    - Service health for all providers
    - Statistics on indexed content and queries
    """
    from codeweaver.server.server import get_state

    try:
        state = get_state()
        if state.health_service is None:
            _logger.warning("Health service not initialized, returning basic health info")
            # Fallback to basic health if service not initialized
            info = health_info()
            return PlainTextResponse(content=info.report(), media_type="application/json")
        # Get health response from health Service
        if state.health_service:
            health_response = await state.health_service.get_health_response()
            return PlainTextResponse(
                content=health_response.model_dump_json(), media_type="application/json"
            )
    except Exception:
        _logger.exception("Failed to get health status")
        # Return unhealthy status on error

        from codeweaver.server.health_models import (
            EmbeddingProviderServiceInfo,
            HealthResponse,
            IndexingInfo,
            IndexingProgressInfo,
            RerankingServiceInfo,
            ServicesInfo,
            SparseEmbeddingServiceInfo,
            StatisticsInfo,
            VectorStoreServiceInfo,
        )

        error_response = HealthResponse.create_with_current_timestamp(
            status="unhealthy",
            uptime_seconds=0,
            indexing=IndexingInfo(
                state="error",
                last_indexed=None,
                progress=IndexingProgressInfo(
                    files_discovered=0,
                    files_processed=0,
                    chunks_created=0,
                    errors=0,
                    current_file=None,
                    start_time=None,
                    estimated_completion=None,
                ),
            ),
            services=ServicesInfo(
                vector_store=VectorStoreServiceInfo(status="down", latency_ms=0),
                embedding_provider=EmbeddingProviderServiceInfo(
                    status="down", model="unknown", latency_ms=0, circuit_breaker_state="open"
                ),
                sparse_embedding=SparseEmbeddingServiceInfo(status="down", provider="unknown"),
                reranking=RerankingServiceInfo(status="down", model="unknown", latency_ms=0),
            ),
            statistics=StatisticsInfo(
                total_chunks_indexed=0,
                total_files_indexed=0,
                languages_indexed=[],
                index_size_mb=0,
                queries_processed=0,
                avg_query_latency_ms=0,
            ),
        )
        return PlainTextResponse(
            content=error_response.model_dump_json(), status_code=503, media_type="application/json"
        )
    raise RuntimeError("Unreachable code in health endpoint")


def setup_middleware(
    middleware: Container[type[Middleware]], middleware_settings: MiddlewareOptions
) -> set[Middleware]:
    """Setup middleware for the application."""
    # Convert container to set for modification
    result: set[Middleware] = set()

    # Apply middleware settings
    # pyright gets very confused here, so we ignore most issues
    for mw in middleware:  # type: ignore
        mw: type[Middleware]  # type: ignore
        match mw.__name__:  # type: ignore[reportUnknownMemberType, reportUnknownArgumentType, reportAttributeAccessIssue]
            case "ErrorHandlingMiddleware":
                instance = mw(**middleware_settings.get("error_handling", {}))  # type: ignore[reportCallIssue]
            case "RetryMiddleware":
                instance = mw(**middleware_settings.get("retry", {}))  # type: ignore[reportCallIssue]
            case "RateLimitingMiddleware":
                instance = mw(**middleware_settings.get("rate_limiting", {}))  # type: ignore[reportCallIssue]
            case "LoggingMiddleware" | "StructuredLoggingMiddleware":
                instance = mw(**middleware_settings.get("logging", {}))  # type: ignore[reportCallIssue]
            case _:
                if any_settings := middleware_settings.get(mw.__name__.lower()):  # type: ignore[reportUnknownMemberType, reportUnknownArgumentType, reportAttributeAccessIssue]
                    instance = mw(**any_settings)  # type: ignore[reportCallIssue, reportUnknownVariableType]
                else:
                    instance = mw()  # type: ignore[reportCallIssue, reportUnknownVariableType]
        result.add(instance)
    return result


def register_tool(app: FastMCP[AppState]) -> FastMCP[AppState]:
    """Register the find_code tool with the application."""
    app.add_tool(
        Tool.from_function(
            find_code_tool,
            name="find_code",
            description="""Find code in the codebase using semantic search and intelligent analysis.""",
            enabled=True,
            exclude_args=["context"],
            tags={"user", "external", "code-context"},
            annotations=ToolAnnotations(
                title="find_code",
                readOnlyHint=True,
                destructiveHint=False,
                idempotentHint=True,
                openWorldHint=True,
            ),
            output_schema=FindCodeResponseSummary.get_schema(),
            serializer=FindCodeResponseSummary.model_dump_json,
        )  # type: ignore
    )
    return app


# -------------------------
# Registration entrypoint
# -------------------------
async def register_app_bindings(
    app: FastMCP[AppState], middleware: set[Middleware], middleware_settings: MiddlewareOptions
) -> tuple[FastMCP[AppState], set[Middleware]]:
    """Register application bindings for tools and routes."""
    from codeweaver.config.server_defaults import DefaultEndpointSettings
    from codeweaver.config.settings import get_settings_map
    from codeweaver.core.types.sentinel import Unset

    if (endpoint_settings := get_settings_map().get("endpoints")) and isinstance(
        endpoint_settings, Unset
    ):
        endpoint_settings = DefaultEndpointSettings
    elif endpoint_settings:
        endpoint_settings = DefaultEndpointSettings | endpoint_settings
    else:
        endpoint_settings = DefaultEndpointSettings
    # Routes
    if endpoint_settings.get("enable_state", True):
        app.custom_route("/state", methods=["GET"], name="state", include_in_schema=True)(
            state_info
        )  # type: ignore[arg-type]
    if endpoint_settings.get("enable_stats", True):
        app.custom_route("/stats", methods=["GET"], name="stats", include_in_schema=True)(
            stats_info
        )  # type: ignore[arg-type]
    if endpoint_settings.get("enable_settings", True):
        app.custom_route("/settings", methods=["GET"], name="settings", include_in_schema=True)(
            settings_info
        )  # type: ignore[arg-type]
    if endpoint_settings.get("enable_version", True):
        app.custom_route("/version", methods=["GET"], name="version", include_in_schema=True)(
            version_info
        )  # type: ignore[arg-type]
    if endpoint_settings.get("enable_health", True):
        app.custom_route("/health", methods=["GET"], name="health", include_in_schema=True)(health)  # type: ignore[arg-type]
    # todo: add status endpoint (more what I'm doing right now/progress than health)

    middleware = setup_middleware(
        cast(Container[type[Middleware]], middleware), middleware_settings
    )
    middleware.add(
        StatisticsMiddleware(
            statistics=statistics(),
            logger=cast(dict, middleware_settings.get("logging", {})).get(  # type: ignore[unknown-attribute]
                "logger", logging.getLogger(__name__)
            ),
            log_level=cast(dict, middleware_settings.get("logging", {})).get("log_level", 20),  # type: ignore[unknown-attribute]
        )
    )
    return app, middleware


__all__ = ("find_code_tool", "register_app_bindings", "register_tool")
