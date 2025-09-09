# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Application bindings for CodeWeaver. Registers tools and routes."""

from __future__ import annotations

import contextlib
import datetime
import enum
import importlib
import logging
import time

from collections.abc import Awaitable, Callable, Container
from dataclasses import is_dataclass
from functools import cache
from typing import TYPE_CHECKING, Any, cast

from fastapi.middleware import Middleware
from fastmcp import Context
from pydantic import BaseModel, PydanticUserError, TypeAdapter
from starlette.requests import Request
from starlette.responses import JSONResponse

from codeweaver._server import AppState, HealthInfo, get_health_info
from codeweaver._statistics import (
    SessionStatistics,
    get_session_statistics,
    record_timed_http_request,
)
from codeweaver._utils import is_class, is_pydantic_basemodel, is_typeadapter
from codeweaver.exceptions import CodeWeaverError
from codeweaver.language import SemanticSearchLanguage
from codeweaver.middleware.statistics import StatisticsMiddleware
from codeweaver.models.core import FindCodeResponseSummary
from codeweaver.models.intent import IntentType
from codeweaver.settings import CodeWeaverSettings, get_settings
from codeweaver.settings_types import MiddlewareOptions
from codeweaver.tools.find_code import find_code_implementation


_logger = logging.getLogger(__name__)

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


@cache
def health_info() -> HealthInfo:
    """Get the current health information."""
    return get_health_info()


# -------------------------
# Plain tool implementation
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
                if context and context.request_context and context.request_context.request_id:
                    request_id = context.request_context.request_id
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


# ===========================================================================
#  *                    Pydantic Model Management
#    We use Pydantic models extensively throughout the application.
#    When you have deeply nested models, Pydantic may not always
#    have finished building them, as it likes to do it lazily, and from the bottom up.
#    This section is a guard against that for models serving the server's http endpoints.
# ===========================================================================


def is_complete(model: BaseModel | type[BaseModel]) -> bool:
    """Check if a Pydantic model is complete."""
    return bool(
        hasattr(model, "__pydantic_complete__")
        and model.__pydantic_complete__ is not None  # type: ignore
        and model.__pydantic_complete__  # type: ignore
    )


def try_to_build_sub_models(model: Any) -> None:
    """Try to build sub-models for a Pydantic model."""
    if hasattr(model, "__dict__") and isinstance(model.__dict__, dict) and model.__dict__:
        dict_items = (
            item
            for item in model.__dict__.items()
            if not item[0].startswith("__")
            and item[1] is not None
            and not is_class(item[1])
            and "codeweaver" in item[1].__module__
        )
        for attr_name, attr_value in dict_items:
            if isinstance(attr_value, BaseModel | enum.Enum) or is_dataclass(attr_value):
                # no idea why this works, but it does -- clearly something with the namespacing, but don't know what
                _type = type(attr_value)
                _ = importlib.import_module(attr_value.__module__)._type
                if isinstance(attr_value, enum.Enum) or (
                    is_pydantic_basemodel(attr_value) and is_complete(attr_value)
                ):
                    continue
                if isinstance(attr_value, BaseModel):
                    try:
                        outcome = attr_value.model_rebuild()
                        if outcome:
                            print(
                                f"Rebuilt sub-model for {attr_name} in {model.__class__.__name__}"
                            )
                    except Exception:
                        _logger.exception("Failed to rebuild sub-model")
                        try:
                            try_to_build_sub_models(attr_value)
                        except Exception:
                            _logger.exception("Failed to build sub-models")
                elif is_dataclass(attr_value):
                    try:
                        adapted_value = TypeAdapter(attr_value)
                        outcome = adapted_value.rebuild()
                        if outcome:
                            print(
                                f"Rebuilt dataclass for {attr_name} in {model.__class__.__name__}"
                            )
                    except Exception:
                        _logger.exception("Failed to rebuild dataclass")
                        try:
                            try_to_build_sub_models(attr_value)
                        except Exception:
                            _logger.exception("Failed to build sub-models")


async def rebuild_if_needed[
    T: (BaseModel | TypeAdapter[SessionStatistics] | TypeAdapter[HealthInfo])
](model: T) -> T | None:
    """Rebuild a Pydantic model if needed."""
    # TypeAdapter has a different API from BaseModel, so we need to handle both cases.
    if (is_pydantic_basemodel(model) and model.__pydantic_complete__) or (
        is_typeadapter(model) and model.pydantic_complete
    ):
        return model
    method = "model_rebuild" if is_pydantic_basemodel(model) else "rebuild"
    rebuild_attr = getattr(model, method, None)
    if not rebuild_attr:
        raise ValueError(f"Model {model} does not have method {method}")
    with contextlib.suppress(PydanticUserError):
        if rebuild_attr():
            print(
                f"Rebuilt model for {model.__name__ if isinstance(model, type) else model.__class__.__name__}"
            )

            return model
        try:
            return try_to_build_sub_models(model)
        except Exception:
            _logger.exception("Failed to rebuild model")
            return None
    return None


async def time_http_response(
    request: Request, call_next: Callable[[Request], Awaitable[JSONResponse]]
) -> JSONResponse:
    """Time the response of a request."""
    start_time = time.perf_counter()
    response = await call_next(request)
    duration = time.perf_counter() - start_time
    record_timed_http_request(request_name, duration)
    return response


# -------------------------
# Plain route handlers
# -------------------------
async def stats_info(_request: Request) -> JSONResponse:
    """Return current session statistics as JSON."""
    global statistics
    stats: SessionStatistics = statistics()
    stats_model: TypeAdapter[SessionStatistics] = TypeAdapter(stats)
    if final_model := await rebuild_if_needed(stats_model):
        return JSONResponse(content=final_model.dump_json(stats), media_type="application/json")
    return JSONResponse(
        content={"error": "We ran into an error -- statistics unavailable."},
        status_code=500,
        media_type="application/json",
    )


async def settings_info(_request: Request) -> JSONResponse:
    """Return current settings as JSON."""
    settings_model: CodeWeaverSettings = settings()
    if final_model := await rebuild_if_needed(settings_model):
        return JSONResponse(content=final_model.model_dump_json(), media_type="application/json")
    return JSONResponse(
        content={"error": "We ran into an error -- settings unavailable."},
        status_code=500,
        media_type="application/json",
    )


async def version_info(_request: Request) -> JSONResponse:
    """Return current version information as JSON."""
    from codeweaver import __version__ as version

    return JSONResponse(content={"version": version}, media_type="application/json")


async def health(_request: Request) -> JSONResponse:
    """Return current health information as JSON."""
    info = health_info()
    health_model: TypeAdapter[HealthInfo] = TypeAdapter(info)
    if final_model := await rebuild_if_needed(health_model):
        return JSONResponse(content=final_model.dump_json(info), media_type="application/json")
    unhealthy = info.update_status("unhealthy", "failed to build the health model; health unknown")
    try:
        return JSONResponse(
            content=TypeAdapter(HealthInfo).dump_json(unhealthy, indent=2),
            media_type="application/json",
        )
    except Exception as e:
        _logger.exception("Failed to update health status")
        try:
            return JSONResponse(
                content={"error": f"Failed to update health status: {e}"},
                status_code=500,
                media_type="application/json",
            )
        except Exception as e:
            _logger.exception("Failed to update health status")
            return JSONResponse(
                content={"error": f"Failed to update health status: {e}"},
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
            case _:
                if any_settings := middleware_settings.get(mw.__name__.lower()):  # type: ignore[reportUnknownMemberType, reportUnknownArgumentType, reportAttributeAccessIssue]
                    mw = mw(**any_settings)  # type: ignore[reportCallIssue, reportUnknownVariableType]
                else:
                    mw = mw()  # type: ignore[reportCallIssue, reportUnknownVariableType]
        mw: Middleware
    return middleware  # pyright: ignore[reportReturnType]


@cache
async def get_schema() -> dict[str, Any]:
    """Get the schema for the application."""
    from codeweaver._data_structures import DiscoveredFile, Span
    from codeweaver.language import SemanticSearchLanguage
    from codeweaver.models.core import CodeMatch

    _ = (
        Span,
        DiscoveredFile,
        SemanticSearchLanguage,
    )  # ensure these are imported for schema generation
    codematch_model = CodeMatch
    if (
        await rebuild_if_needed(codematch_model)  # pyright: ignore[reportArgumentType]
        and (final_model := await rebuild_if_needed(FindCodeResponseSummary))  # pyright: ignore[reportArgumentType]
        and (schema := final_model.model_json_schema())
    ):  # type: ignore
        return schema
    raise RuntimeError("Failed to build schema for FindCodeResponseSummary")


# -------------------------
# Registration entrypoint
# -------------------------
def register_app_bindings(
    app: FastMCP[AppState], middleware: set[Middleware], middleware_settings: MiddlewareOptions
) -> tuple[FastMCP[AppState], set[Middleware]]:
    """Register application bindings for tools and routes."""
    # Routes
    app.custom_route("/stats", methods=["GET"], include_in_schema=True)(stats_info)  # type: ignore[arg-type]
    app.custom_route("/settings", methods=["GET"], include_in_schema=True)(settings_info)  # type: ignore[arg-type]
    app.custom_route("/version", methods=["GET"], include_in_schema=True)(version_info)  # type: ignore[arg-type]
    app.custom_route("/health", methods=["GET"], include_in_schema=True)(health)  # type: ignore[arg-type]

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


__all__ = ("find_code_tool", "register_app_bindings")
