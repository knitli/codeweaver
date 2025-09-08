# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

from __future__ import annotations

from typing import TYPE_CHECKING

from pydantic import TypeAdapter

if TYPE_CHECKING:
    from fastmcp import FastMCP
    from codeweaver._server import AppState
    from codeweaver.language import SemanticSearchLanguage
    from codeweaver.models.core import FindCodeResponseSummary
    from codeweaver.models.intent import IntentType


# -------------------------
# Plain tool implementation
# -------------------------
async def find_code_tool(
    query: str,
    intent: "IntentType | None" = None,
    *,
    token_limit: int = 10000,
    include_tests: bool = False,
    focus_languages: "tuple[SemanticSearchLanguage, ...] | None" = None,
    context=None,
) -> "FindCodeResponseSummary":
    from codeweaver.tools.find_code import find_code_implementation
    from codeweaver._statistics import get_session_statistics
    from codeweaver.settings import get_settings
    from codeweaver.exceptions import CodeWeaverError
    from codeweaver.models.core import FindCodeResponseSummary  # noqa: F401

    statistics = get_session_statistics()
    settings = get_settings()

    try:
        response = await find_code_implementation(
            query=query,
            settings=settings,
            intent=intent,
            token_limit=token_limit,
            include_tests=include_tests,
            focus_languages=focus_languages,
            statistics=statistics,
        )
        if statistics:
            statistics.add_successful_request()
        return response
    except CodeWeaverError:
        if statistics:
            statistics.log_request_from_context(context, successful=False)
        raise
    except Exception as e:  # wrap unexpected errors as QueryError to preserve prior behavior
        if statistics:
            statistics.log_request_from_context(context, successful=False)
        from codeweaver.exceptions import QueryError

        raise QueryError(
            f"Unexpected error in `find_code`: {e!s}",
            suggestions=["Try a simpler query", "Check server logs for details"],
        ) from e


# -------------------------
# Plain route handlers
# -------------------------
async def stats_info() -> bytes:
    from codeweaver._statistics import get_session_statistics

    statistics = get_session_statistics()
    return TypeAdapter(type(statistics)).dump_json(statistics, indent=2)  # type: ignore[arg-type]


async def settings_info() -> bytes:
    from codeweaver.settings import get_settings

    return get_settings().model_dump_json(indent=2).encode()


async def version_info() -> bytes:
    from codeweaver import __version__ as version

    return f"CodeWeaver version: {version}".encode()


async def health() -> bytes:
    from codeweaver._server import HealthInfo, HealthStatus, get_health_info

    if (h := get_health_info()):
        return TypeAdapter(HealthInfo).dump_json(h, indent=2)
    unhealthy = HealthInfo(status=HealthStatus.UNHEALTHY)
    return TypeAdapter(HealthInfo).dump_json(unhealthy, indent=2)


# -------------------------
# Registration entrypoint
# -------------------------
def register_app_bindings(app: "FastMCP[AppState]") -> None:
    # Tools
    app.tool(tags={"user", "external", "code"})(find_code_tool)

    # Routes
    app.custom_route("/stats", methods=["GET"], tags={"system", "stats"}, include_in_schema=True)(stats_info)  # type: ignore[arg-type]
    app.custom_route("/settings", methods=["GET"], tags={"system", "settings"}, include_in_schema=True)(settings_info)  # type: ignore[arg-type]
    app.custom_route("/version", methods=["GET"], tags={"system", "version"}, include_in_schema=True)(version_info)  # type: ignore[arg-type]
    app.custom_route("/health", methods=["GET"], tags={"system", "health"}, include_in_schema=True)(health)  # type: ignore[arg-type]