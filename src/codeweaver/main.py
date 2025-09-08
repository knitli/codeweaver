# sourcery skip: avoid-global-variables
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Main FastMCP server entrypoint for CodeWeaver with linear bootstrap."""

from __future__ import annotations

import asyncio
import logging

from typing import TYPE_CHECKING

from codeweaver._server import build_app
from codeweaver.app_bindings import register_app_bindings


if TYPE_CHECKING:
    from fastmcp import FastMCP

    from codeweaver._server import AppState


async def start_server(
    app: "FastMCP[AppState]", *, host: str = "127.0.0.1", port: int = 9328
) -> None:  # noqa: UP037
    """Start CodeWeaver's FastMCP server."""
    await app.run_http_async(host=host, port=port)


async def run() -> None:
    """Run the CodeWeaver server."""
    app = build_app()
    register_app_bindings(app)
    await start_server(app)


if __name__ == "__main__":
    try:
        asyncio.run(run())
    except Exception as e:
        logging.getLogger(__name__).exception("Failed to start CodeWeaver server: ")
        raise RuntimeError("Failed to start CodeWeaver server.") from e
