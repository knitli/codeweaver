---
title: daemon
description: API reference for daemon
---

# daemon

Shared daemon utilities for CodeWeaver.

Provides common functionality for starting and health-checking the CodeWeaver daemon
from both the CLI start command and the stdio server proxy.

## Functions

## `check_daemon_health(management_host: str = '127.0.0.1', management_port: int = 9329, timeout_at: float = 5.0) -> bool`

Check if the CodeWeaver daemon is healthy.

Args:
    management_host: Host of management server
    management_port: Port of management server
    timeout_at: Request timeout in seconds (default 5s to handle cold starts)

Returns:
    True if daemon is healthy, False otherwise


## `spawn_daemon_process(config_file: Path | None = None, project: Path | None = None, management_host: str | None = None, management_port: int | None = None, mcp_host: str | None = None, mcp_port: int | None = None) -> bool`

Spawn the CodeWeaver daemon as a detached background process.

Args:
    config_file: Optional configuration file path
    project: Optional project directory path (also used as working directory)
    management_host: Host for management server
    management_port: Port for management server
    mcp_host: Host for MCP HTTP server
    mcp_port: Port for MCP HTTP server

Returns:
    True if daemon was spawned successfully, False otherwise.


## `start_daemon_if_needed(management_host: str = '127.0.0.1', management_port: int = 9329, max_wait_seconds: float = 30.0, check_interval: float = 0.5, config_file: Path | None = None, project: Path | None = None, mcp_host: str | None = None, mcp_port: int | None = None) -> bool`

Start the CodeWeaver daemon if not already running, and wait for it to be healthy.

Args:
    management_host: Host of management server
    management_port: Port of management server
    max_wait_seconds: Maximum time to wait for daemon to become healthy
    check_interval: Interval between health checks
    config_file: Optional configuration file path
    project: Optional project directory path
    mcp_host: Host for MCP HTTP server
    mcp_port: Port for MCP HTTP server

Returns:
    True if daemon is running (either was already running or successfully started),
    False if daemon could not be started or failed to become healthy.


## `request_daemon_shutdown(management_host: str = '127.0.0.1', management_port: int = 9329, timeout_at: float = 10.0) -> bool`

Request daemon shutdown via management server endpoint.

Args:
    management_host: Host of management server
    management_port: Port of management server
    timeout_at: Request timeout in seconds

Returns:
    True if shutdown was requested successfully, False otherwise.


## `wait_for_daemon_shutdown(management_host: str = '127.0.0.1', management_port: int = 9329, max_wait_seconds: float = 30.0, check_interval: float = 0.5) -> bool`

Wait for daemon to complete shutdown.

Args:
    management_host: Host of management server
    management_port: Port of management server
    max_wait_seconds: Maximum time to wait for shutdown
    check_interval: Interval between health checks

Returns:
    True if daemon shut down within timeout, False otherwise.

