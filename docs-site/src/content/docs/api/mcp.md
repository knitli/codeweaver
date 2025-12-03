---
title: mcp
description: API reference for mcp
---

# mcp

FastMCP Server Creation and Lifespan Management for CodeWeaver.

## Which Find_Code Tool?

There are *three* symbols named "find_code" in CodeWeaver, two in this package:
- `find_code_tool`: The actual implementation function of the tool. This version is really a wrapper around the real `find_code` function defined in `codeweaver.agent_api.find_code`. `find_code_tool` is defined here in `codeweaver.mcp.user_agent` because it's the part exposed as an MCP tool for user's agents to call.
- `find_code_tool_definition`: The MCP `Tool` definition for the `find_code` tool. This is defined in `codeweaver.mcp.tools` as part of the `TOOL_DEFINITIONS` dictionary. This is what gets registered with the MCP server.
- `find_code`: The actual implementation function of the `find_code` logic, defined in `codeweaver.agent_api.find_code`. This is the core logic that does the code searching. If a user uses the `search` command in CodeWeaver's CLI, this `find_code` function is what gets called under the hood.

## Functions
