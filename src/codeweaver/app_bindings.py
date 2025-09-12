# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Application bindings for CodeWeaver. Registers tools and routes."""

from __future__ import annotations

import contextlib
import datetime
import logging

from collections.abc import Container
from functools import cache
from typing import TYPE_CHECKING, Any, cast

from fastapi.middleware import Middleware
from fastmcp import Context
from fastmcp.tools import Tool
from mcp.types import ToolAnnotations
from pydantic import BaseModel, TypeAdapter
from pydantic_core import to_json
from starlette.requests import Request
from starlette.responses import PlainTextResponse

from codeweaver._server import AppState, HealthInfo, get_health_info
from codeweaver._statistics import SessionStatistics, get_session_statistics, timed_http
from codeweaver.exceptions import CodeWeaverError
from codeweaver.language import SemanticSearchLanguage
from codeweaver.middleware.statistics import StatisticsMiddleware
from codeweaver.models.core import FindCodeResponseSummary
from codeweaver.models.intent import IntentType
from codeweaver.settings import CodeWeaverSettings, get_settings
from codeweaver.settings_types import MiddlewareOptions
from codeweaver.tools.find_code import find_code_implementation


_logger = logging.getLogger(__name__)

type PydanticType = type[BaseModel | TypeAdapter[Any]] | BaseModel | TypeAdapter[Any]

if TYPE_CHECKING:
    from fastmcp import FastMCP


@cache
def statistics() -> SessionStatistics:
    """Get the current session statistics."""
    return get_session_statistics()


@cache
def settings() -> CodeWeaverSettings:
    """Get the current settings."""
    return get_settings()


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
    """Use CodeWeaver to find_code in the codebase."""
    try:
        response = await find_code_implementation(
            query=query,
            settings=settings(),
            intent=intent,
            token_limit=token_limit,
            include_tests=include_tests,
            focus_languages=focus_languages,
            statistics=statistics(),
        )
        if statistics:
            request_id = datetime.datetime.now(datetime.UTC).isoformat()
            with contextlib.suppress(ValueError, AttributeError):
                if context and context.request_context and context.request_context.request_id:  # type: ignore
                    request_id = context.request_context.request_id  # type: ignore
            cast(SessionStatistics, statistics).add_successful_request(request_id)
    except CodeWeaverError:
        if statistics:
            cast(SessionStatistics, statistics).log_request_from_context(context, successful=False)
        raise
    except Exception as e:
        if statistics:
            cast(SessionStatistics, statistics).log_request_from_context(context, successful=False)
        from codeweaver.exceptions import QueryError

        raise QueryError(
            f"Unexpected error in `find_code`: {e!s}",
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
    settings_model: CodeWeaverSettings = settings()
    try:
        return PlainTextResponse(
            content=settings_model.model_dump_json(), media_type="application/json"
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
    from codeweaver import __version__ as version

    return PlainTextResponse(content=to_json({"version": version}), media_type="application/json")


@timed_http("health")
async def health(_request: Request) -> PlainTextResponse:
    """Return current health information as JSON."""
    info = health_info()
    try:
        return PlainTextResponse(content=info.report(), media_type="application/json")
    except Exception as e:
        _logger.exception("Failed to update health status")
        return PlainTextResponse(
            content=to_json({"error": f"Failed to update health status: {e}"}),
            status_code=500,
            media_type="application/json",
        )


def setup_middleware(
    middleware: Container[type[Middleware]], middleware_settings: MiddlewareOptions
) -> Container[Middleware]:
    """Setup middleware for the application."""
    # Apply middleware settings
    # pyright gets very confused here, so we ignore most issues
    for mw in middleware:  # type: ignore
        mw: type[Middleware]  # type: ignore
        match mw.__name__:  # type: ignore[reportUnknownMemberType, reportUnknownArgumentType, reportAttributeAccessIssue]
            case "ErrorHandlingMiddleware":
                mw = mw(**middleware_settings.get("error_handling", {}))  # type: ignore[reportCallIssue]
            case "RetryMiddleware":
                mw = mw(**middleware_settings.get("retry", {}))  # type: ignore[reportCallIssue]
            case "RateLimitingMiddleware":
                mw = mw(**middleware_settings.get("rate_limiting", {}))  # type: ignore[reportCallIssue]
            case "LoggingMiddleware" | "StructuredLoggingMiddleware":
                mw = mw(**middleware_settings.get("logging", {}))  # type: ignore[reportCallIssue]
            case _:  # pyright: ignore[reportUnknownVariableType]
                if any_settings := middleware_settings.get(mw.__name__.lower()):  # type: ignore[reportUnknownMemberType, reportUnknownArgumentType, reportAttributeAccessIssue]
                    mw = mw(**any_settings)  # type: ignore[reportCallIssue, reportUnknownVariableType]
                else:
                    mw = mw()  # type: ignore[reportCallIssue, reportUnknownVariableType]
        mw: Middleware
    return middleware  # pyright: ignore[reportReturnType]


def register_tool(app: FastMCP[AppState]) -> FastMCP[AppState]:
    """Register the find_code tool with the application."""
    app.add_tool(
        Tool.from_function(
            find_code_tool,
            name="find_code",
            description="Find code in the codebase",
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
    # Routes
    app.custom_route("/stats", methods=["GET"], name="stats", include_in_schema=True)(stats_info)  # type: ignore[arg-type]
    app.custom_route("/settings", methods=["GET"], name="settings", include_in_schema=True)(  # pyright: ignore[reportUnknownMemberType]
        settings_info
    )  # type: ignore[arg-type]
    app.custom_route("/version", methods=["GET"], name="version", include_in_schema=True)(  # pyright: ignore[reportUnknownMemberType]
        version_info
    )  # type: ignore[arg-type]
    app.custom_route("/health", methods=["GET"], name="health", include_in_schema=True)(health)  # type: ignore[arg-type]
    # todo: add status endpoint (more what I'm doing right now/progress than health)

    middleware = setup_middleware(
        cast(Container[type[Middleware]], middleware), middleware_settings
    )  # pyright: ignore[reportAssignmentType]
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
