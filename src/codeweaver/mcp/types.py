# sourcery skip: snake-case-variable-declarations
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Native type wrappers for MCP components."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, NotRequired, TypedDict

from mcp.types import ToolAnnotations


class ToolRegistrationDict(TypedDict):
    """Information about a registered tool."""

    fn: Callable[..., Any]
    name: str
    description: str
    tags: set[str]
    annotations: ToolAnnotations
    exclude_args: list[str]
    serializer: Callable[[Any], str]
    output_schema: dict[str, Any] | None
    meta: dict[str, Any]
    enabled: bool


class ToolAnnotationsDict(TypedDict, total=False):
    """Dictionary representation of ToolAnnotations."""

    title: NotRequired[str]
    """A human-readable title for the tool."""
    readOnlyHint: NotRequired[bool]
    """A hint that the tool does not modify state."""
    destructiveHint: NotRequired[bool]
    """A hint that the tool may modify state in a destructive way."""
    idempotentHint: NotRequired[bool]
    """A hint that the tool can be called multiple times without changing the result beyond the initial application."""
    openWorldHint: NotRequired[bool]
    """A hint that the tool operates in an open world context (e.g., interacting with external systems or environments)."""


__all__ = ("ToolAnnotationsDict", "ToolRegistrationDict")
