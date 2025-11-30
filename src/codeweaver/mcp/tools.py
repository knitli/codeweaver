"""Tool definitions for CodeWeaver's MCP interface."""

from __future__ import annotations

from collections.abc import Callable
from textwrap import dedent
from typing import Any, TypedDict

from fastmcp import FastMCP
from fastmcp.client.transports import FastMCPTransport
from fastmcp.tools import Tool
from mcp.types import ToolAnnotations

from codeweaver.agent_api.find_code.types import FindCodeResponseSummary
from codeweaver.common.utils.lazy_importer import lazy_import
from codeweaver.core.types import DictView
from codeweaver.mcp.types import ToolRegistrationDict
from codeweaver.mcp.user_agent import find_code_tool


USER_AGENT_TAGS = {"user", "external"}

CONTEXT_AGENT_TAGS = {"context", "internal", "data"}


class ToolCollectionDict(TypedDict):
    """Collection of CodeWeaver MCP tool definitions."""

    find_code: Tool
    # Bulk tool caller is being tested and isn't used in release versions yet. We will probably change the signature for find_code to allow multiple queries at once instead.
    call_tool_bulk: Callable[[FastMCP[Any]], Tool]


def get_bulk_tool(server: FastMCP[Any]) -> Tool:
    """Lazily import and return the bulk tool definition."""
    bulk_tool_cls = lazy_import("fastmcp.contrib.bulk_tool_caller", "BulkToolCaller")
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
            exclude_args=registration_info.get("exclude_args", []),
            serializer=registration_info.get("serializer"),
            output_schema=registration_info.get("output_schema", None),
            meta=registration_info.get("meta", {}),
            enabled=registration_info.get("enabled", True),
        )
    )


TOOL_DEFINITIONS: DictView[ToolCollectionDict] = DictView(
    ToolCollectionDict(
        find_code=Tool.from_function(
            **ToolRegistrationDict(
                fn=find_code_tool,
                name="find_code",
                description=dedent("""
        CodeWeaver's `find_code` tool is an advanced code search function that leverages context and task-aware semantic search to identify and retrieve relevant code snippets from a codebase using natural language queries. `find_code` uses advanced sparse and dense embedding models, and reranking models to provide the best possible results, which are continuously updated. `find_code` is purpose-built to assist AI coding agents with getting exactly the information they need for any coding or repository task.

        # Using `find_code`

        **One Required Argument:**
            - query: Provide a natural language query describing what you are looking for.

        **Optional Arguments:**
            - intent: Specify an intent to help narrow down the search results. Choose from: `understand`, `implement`, `debug`, `optimize`, `test`, `configure`, `document`.
            - token_limit: Set a maximum number of tokens to return (default is 30000).
            - focus_languages: Filter results by programming language(s). A list of languages using their common names (like "python", "javascript", etc.). CodeWeaver supports over 160 programming languages.

        RETURNS:
            A detailed summary of ranked matches and metadata. Including:
            - matches: A list of code or documentation snippets *in ranked order by relevance* to the query. Each match includes:
                - content: An object representing the code or documentation snippet or its syntax tree representation. These objects carry substantial metadata about the snippet depending on how it was retrieved. Metadata may include: language, size, importance, symbol, semantic role and relationships to other code snippets and symbols.
                - file: The file and associated metadata where the snippet was found.
                - span: A span object indicating the exact location of the snippet within the file.
                - relevance_score: A numerical score indicating how relevant the snippet is to the query, normalized between 0 and 1.

        """),
                enabled=True,
                exclude_args=["context"],
                tags={"user", "external"},
                annotations=ToolAnnotations(
                    title="Find Code Tool",
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


def register_tool(app: FastMCP[Any], tool: Tool) -> FastMCP[Any]:
    """Register all CodeWeaver tools with the application."""
    _ = app.add_tool(tool)
    return app


__all__ = ("TOOL_DEFINITIONS", "register_tool")
