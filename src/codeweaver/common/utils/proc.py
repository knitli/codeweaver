# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Multiprocessing and process utilities."""

from __future__ import annotations

from functools import cache


@cache
def asyncio_or_uvloop() -> object:
    """Set uvloop as the event loop policy if available and appropriate."""
    import platform
    import sys

    from importlib.util import find_spec

    if (
        sys.platform not in {"win32", "cygwin", "wasi", "ios"}
        and platform.python_implementation() == "CPython"
        and find_spec("uvloop") is not None
    ):
        import uvloop

        return uvloop
    import asyncio

    return asyncio


__all__ = ("asyncio_or_uvloop",)
