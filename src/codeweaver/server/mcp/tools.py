# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Tool definitions for CodeWeaver's MCP interface."""

from __future__ import annotations

from collections.abc import Callable
from typing import Any, TypedDict

from fastmcp import FastMCP
from fastmcp.client.transports import FastMCPTransport
from fastmcp.tools import Tool
from lateimport import lateimport
from mcp.types import ToolAnnotations

from codeweaver.core import DictView
from codeweaver.core.constants import (
    CONTEXT_AGENT_TAGS,
    FIND_CODE_DESCRIPTION,
    FIND_CODE_TITLE,
    USER_AGENT_TAGS,
)
from codeweaver.server.agent_api import FindCodeResponseSummary
from codeweaver.server.mcp.types import ToolRegistrationDict
from codeweaver.server.mcp.user_agent import find_code_tool


class ContextAgentToolkit(TypedDict):
    """Context agent search tool definition."""

    search_tool: Tool
    call_tool_bulk: Callable[[FastMCP[Any]], Tool]


class ToolCollectionDict(TypedDict):
    """Collection of CodeWeaver MCP tool definitions."""

    find_code: Tool
    # Bulk tool caller is being tested and isn't used in release versions yet. We will probably change the signature for find_code to allow multiple queries at once instead.
    call_tool_bulk: Callable[[FastMCP[Any]], Tool]


def get_bulk_tool(server: FastMCP[Any]) -> Tool:
    """Lazily import and return the bulk tool definition."""
    bulk_tool_cls = lateimport("fastmcp.contrib.bulk_tool_caller", "BulkToolCaller")
    bulk_tool_instance = bulk_tool_cls()
    bulk_tool_instance.connection = FastMCPTransport(mcp=server)
    bulk_tool_name = "call_tool_bulk"
    # We need to do a little work around because the default behavior of BulkToolCaller's registration registers all of its tools, and we just want one -- call_tool_bulk (the other tool is call_bulk_tools -- which we don't need because we only have one tool.)
    bulk_tool = getattr(bulk_tool_instance, bulk_tool_name)
    registration_info = getattr(bulk_tool, "_mcp_tool_registration", {})
    return Tool.from_function(
        **ToolRegistrationDict(
            fn=bulk_tool,
            name=registration_info.get("name", bulk_tool_name),
            description=registration_info.get("description", "Bulk tool caller"),
            tags={"bulk", *CONTEXT_AGENT_TAGS},
            annotations=registration_info.get("annotations", ToolAnnotations()),
            serializer=registration_info.get("serializer"),
            output_schema=registration_info.get("output_schema", None),
            meta=registration_info.get("meta", {}),
        )
    )


TOOL_DEFINITIONS: DictView[ToolCollectionDict] = DictView(
    ToolCollectionDict(
        find_code=Tool.from_function(
            **ToolRegistrationDict(
                fn=find_code_tool,
                name="find_code",
                description=FIND_CODE_DESCRIPTION,
                tags=USER_AGENT_TAGS | {"find_code"},
                annotations=ToolAnnotations(
                    title=FIND_CODE_TITLE,
                    readOnlyHint=True,
                    destructiveHint=False,
                    idempotentHint=True,
                    openWorldHint=True,
                ),
                output_schema=FindCodeResponseSummary.get_schema(),
                serializer=FindCodeResponseSummary.model_dump_json,
            )
        ),
        call_tool_bulk=lambda server: get_bulk_tool(server),
    )
)

find_code_tool_definition: Tool = TOOL_DEFINITIONS["find_code"]


def register_tool(app: FastMCP[Any], tool: Tool) -> FastMCP[Any]:
    """Register all CodeWeaver tools with the application."""
    _ = app.add_tool(tool)
    return app


__all__ = (
    "TOOL_DEFINITIONS",
    "ContextAgentToolkit",
    "ToolCollectionDict",
    "get_bulk_tool",
    "register_tool",
)
