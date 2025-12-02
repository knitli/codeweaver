# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Shared daemon utilities for CodeWeaver.

Provides common functionality for starting and health-checking the CodeWeaver daemon
from both the CLI start command and the stdio server proxy.
"""

from __future__ import annotations

import asyncio
import logging
import shutil
import subprocess
import sys

from pathlib import Path
from typing import Any


logger = logging.getLogger(__name__)


async def check_daemon_health(
    management_host: str = "127.0.0.1",
    management_port: int = 9329,
    timeout: float = 2.0,
) -> bool:
    """Check if the CodeWeaver daemon is healthy.

    Args:
        management_host: Host of management server
        management_port: Port of management server
        timeout: Request timeout in seconds

    Returns:
        True if daemon is healthy, False otherwise
    """
    try:
        import httpx
    except ImportError:
        return False

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"http://{management_host}:{management_port}/health",
                timeout=timeout,
            )
            return response.status_code == 200
    except Exception:
        return False


def spawn_daemon_process(
    *,
    config_file: Path | None = None,
    project: Path | None = None,
    management_host: str = "127.0.0.1",
    management_port: int = 9329,
    mcp_host: str | None = None,
    mcp_port: int | None = None,
) -> bool:
    """Spawn the CodeWeaver daemon as a detached background process.

    Args:
        config_file: Optional configuration file path
        project: Optional project directory path (also used as working directory)
        management_host: Host for management server
        management_port: Port for management server
        mcp_host: Host for MCP HTTP server
        mcp_port: Port for MCP HTTP server

    Returns:
        True if daemon was spawned successfully, False otherwise.
    """
    # Find the codeweaver executable
    cw_cmd = shutil.which("cw") or shutil.which("codeweaver")
    if not cw_cmd:
        # Try using python -m codeweaver
        cw_cmd = sys.executable
        cw_args = ["-m", "codeweaver", "start", "--foreground"]
    else:
        cw_args = ["start", "--foreground"]

    # Add optional arguments
    if config_file:
        cw_args.extend(["--config-file", str(config_file)])
    if project:
        cw_args.extend(["--project", str(project)])
    if management_host != "127.0.0.1":
        cw_args.extend(["--management-host", management_host])
    if management_port != 9329:
        cw_args.extend(["--management-port", str(management_port)])
    if mcp_host:
        cw_args.extend(["--mcp-host", mcp_host])
    if mcp_port:
        cw_args.extend(["--mcp-port", str(mcp_port)])

    # Determine working directory for the daemon
    working_dir = project.resolve() if project else None

    try:
        # Start daemon as detached subprocess
        # Use CREATE_NEW_PROCESS_GROUP on Windows, start_new_session on Unix
        kwargs: dict[str, Any] = {
            "stdout": subprocess.DEVNULL,
            "stderr": subprocess.DEVNULL,
            "stdin": subprocess.DEVNULL,
        }
        if working_dir:
            kwargs["cwd"] = working_dir
        if sys.platform == "win32":
            kwargs["creationflags"] = subprocess.CREATE_NEW_PROCESS_GROUP  # type: ignore[attr-defined]
        else:
            kwargs["start_new_session"] = True

        subprocess.Popen([cw_cmd, *cw_args], **kwargs)
        return True

    except Exception as e:
        logger.error("Failed to spawn daemon: %s", e)
        return False


async def start_daemon_if_needed(
    management_host: str = "127.0.0.1",
    management_port: int = 9329,
    max_wait_seconds: float = 30.0,
    check_interval: float = 0.5,
    config_file: Path | None = None,
    project: Path | None = None,
    mcp_host: str | None = None,
    mcp_port: int | None = None,
) -> bool:
    """Start the CodeWeaver daemon if not already running, and wait for it to be healthy.

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
    """
    # First check if already running
    if await check_daemon_health(management_host, management_port):
        logger.debug("Daemon already running at %s:%d", management_host, management_port)
        return True

    logger.info("Starting CodeWeaver daemon...")

    # Spawn the daemon
    if not spawn_daemon_process(
        config_file=config_file,
        project=project,
        management_host=management_host,
        management_port=management_port,
        mcp_host=mcp_host,
        mcp_port=mcp_port,
    ):
        return False

    # Wait for daemon to become healthy
    elapsed = 0.0
    while elapsed < max_wait_seconds:
        await asyncio.sleep(check_interval)
        elapsed += check_interval

        if await check_daemon_health(management_host, management_port):
            logger.info("Daemon started successfully")
            return True

    logger.warning("Daemon did not become healthy within %s seconds", max_wait_seconds)
    return False
