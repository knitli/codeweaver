---
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

title: main
description: API reference for main
---

# main

Main FastMCP server entrypoint for CodeWeaver with linear bootstrap.

## Classes

## class `UvicornAccessLogFilter(logging.Filter)`

Filter that blocks uvicorn access log messages.

### Methods

#### `filter(self, record: logging.LogRecord) -> bool`

Return False for uvicorn access logs to block them.


## Functions

## `get_stdio_server(config_file: FilePath | None = None, project_path: Path | None = None, host: str | None = None, port: int | None = None) -> FastMCP`

Get a FastMCP stdio server setup for CodeWeaver.

Args:
    config_file: Optional path to configuration file.
    project_path: Optional path to project directory.
    host: Optional host for the server. This is the host/port for the *codeweaver http mcp server* that the stdio client will be proxied to. **You only need this if you're not connecting to a default setting or not connecting to what is in your config file**.
    port: Optional port for the server. This is the host/port for the *codeweaver http mcp server* that the stdio client will be proxied to. **You only need this if you're not connecting to a default setting or not connecting to what is in your config file**.

Returns:
    Configured FastMCP stdio server instance (not yet running).


## `run(config_file: FilePath | None = None, project_path: Path | None = None, host: str = '127.0.0.1', port: int = 9328, transport: Literal['stdio', 'streamable-http'] = 'stdio', verbose: bool = False, debug: bool = False) -> None`

Run the CodeWeaver server with appropriate transport.

This is the main entry point for starting CodeWeaver's MCP server.

Transport modes:
- stdio (default): stdio proxy that forwards to the daemon's HTTP backend.
  The daemon is started automatically if not already running.
- streamable-http: Full server with background services, MCP HTTP server,
  and management server

For manual daemon control, use `codeweaver start` and `codeweaver stop`.

Args:
    config_file: Optional configuration file path
    project_path: Optional project directory path
    host: Host of HTTP backend to proxy to (stdio) or bind to (http)
    port: Port of HTTP backend to proxy to (stdio) or bind to (http)
    transport: Transport protocol (stdio or streamable-http)
    verbose: Enable verbose logging
    debug: Enable debug logging

