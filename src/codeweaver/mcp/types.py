# sourcery skip: snake-case-variable-declarations
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Native type wrappers for MCP components."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, NotRequired, Required, TypedDict

from mcp.types import ToolAnnotations


class ToolRegistrationDict(TypedDict, total=False):
    """Information about a registered tool."""

    fn: Required[Callable[..., Any]]
    name: NotRequired[str | None]
    description: NotRequired[str | None]
    tags: NotRequired[set[str] | None]
    annotations: NotRequired[ToolAnnotations | None]
    exclude_args: NotRequired[list[str] | None]
    serializer: NotRequired[Callable[[Any], str] | None]
    output_schema: NotRequired[dict[str, Any] | None]
    meta: NotRequired[dict[str, Any] | None]
    enabled: NotRequired[bool | None]


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
