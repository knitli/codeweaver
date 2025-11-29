# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Application bindings for CodeWeaver. Registers tools and routes."""

from __future__ import annotations

import logging

from collections.abc import Container
from functools import cache
from typing import TYPE_CHECKING, Any, cast

from fastmcp.server.middleware.middleware import Middleware
from pydantic import BaseModel, TypeAdapter

from codeweaver.common.statistics import SessionStatistics, get_session_statistics
from codeweaver.config.middleware import MiddlewareOptions
from codeweaver.config.settings import CodeWeaverSettingsDict, get_settings_map
from codeweaver.core.types.dictview import DictView
from codeweaver.middleware.statistics import StatisticsMiddleware


_logger = logging.getLogger(__name__)

type PydanticType = type[BaseModel | TypeAdapter[Any]] | BaseModel | TypeAdapter[Any]

if TYPE_CHECKING:
    from fastmcp import FastMCP

    from codeweaver.server import AppState


@cache
def statistics() -> SessionStatistics:
    """Get the current session statistics."""
    return get_session_statistics()


@cache
def settings() -> DictView[CodeWeaverSettingsDict]:
    """Get the current settings."""
    return get_settings_map()


def setup_middleware(
    middleware: Container[type[Middleware]], middleware_settings: MiddlewareOptions
) -> set[Middleware]:
    """Setup middleware for the application."""
    # Convert container to set for modification
    result: set[Middleware] = set()

    # Apply middleware settings
    # ty gets very confused here, so we ignore most issues
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


# -------------------------
# Registration entrypoint
# -------------------------
async def register_app_bindings(
    app: FastMCP[AppState], middleware: set[Middleware], middleware_settings: MiddlewareOptions
) -> tuple[FastMCP[AppState], set[Middleware]]:
    """Register application bindings for tools and routes."""
    middleware = setup_middleware(
        cast(Container[type[Middleware]], middleware), middleware_settings
    )
    middleware.add(
        StatisticsMiddleware(
            statistics=statistics(),
            logger=cast(dict, middleware_settings.get("logging", {})).get(  # type: ignore[unknown-attribute]
                "logger", logging.getLogger(__name__)
            ),
            log_level=cast(dict, middleware_settings.get("logging", {})).get("log_level", 30),  # type: ignore[unknown-attribute]
        )
    )
    return app, middleware


__all__ = ("register_app_bindings",)
