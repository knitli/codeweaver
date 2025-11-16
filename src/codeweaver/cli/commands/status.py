# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Status command for viewing CodeWeaver runtime status.

Displays real-time operational information including indexing progress,
failover status, and active operations.
"""

from __future__ import annotations

import time

from typing import Any

import httpx

from cyclopts import App
from pydantic_core import from_json
from rich.table import Table

from codeweaver.config.settings import get_settings
from codeweaver.ui import StatusDisplay


app = App("status", help="Show CodeWeaver runtime status.")


@app.default
def status(*, verbose: bool = False, watch: bool = False, watch_interval: int = 5) -> None:
    """Show CodeWeaver runtime status.

    Args:
        verbose: Show detailed status information
        watch: Continuously watch status (refresh every watch_interval seconds)
        watch_interval: Seconds between updates in watch mode (default: 5)
    """
    display = StatusDisplay()

    if watch:
        _watch_status(display, verbose, watch_interval)
    else:
        _show_status_once(display, verbose)


def _show_status_once(display: StatusDisplay, *, verbose: bool) -> None:
    """Show status one time."""
    display.print_command_header("status", "CodeWeaver Runtime Status")

    settings = get_settings()
    server_url = f"http://{settings.server.host}:{settings.server.port}"

    status_data = _query_server_status(server_url)

    if status_data is None:
        _display_server_offline(display, server_url)
    else:
        _display_full_status(display, status_data, verbose)


def _watch_status(display: StatusDisplay, *, verbose: bool, interval: int) -> None:
    """Continuously watch and display status."""
    display.print_command_header("status", "CodeWeaver Runtime Status (Watch Mode)")
    display.print_info(f"Refreshing every {interval} seconds. Press Ctrl+C to exit.")

    settings = get_settings()
    server_url = f"http://{settings.server.host}:{settings.server.port}"

    try:
        while True:
            # Clear screen and redisplay
            display.console.clear()
            display.print_command_header("status", "CodeWeaver Runtime Status (Watch Mode)")
            display.print_info(
                f"Refreshing every {interval} seconds. Press Ctrl+C to exit.", prefix="⏱️"
            )

            status_data = _query_server_status(server_url)

            if status_data is None:
                _display_server_offline(display, server_url)
            else:
                _display_full_status(display, status_data, verbose)

            time.sleep(interval)
    except KeyboardInterrupt:
        display.print_info("Watch mode stopped.", prefix="✋")


def _query_server_status(server_url: str) -> dict[str, Any] | None:
    """Query the server /status endpoint.

    Args:
        server_url: Base URL of the server

    Returns:
        Status data dict if server is running, None if offline
    """
    try:
        with httpx.Client(timeout=5.0) as client:
            response = client.get(f"{server_url}/status")
            response.raise_for_status()
            return from_json(response.content)  # type: ignore[no-any-return]
    except (httpx.ConnectError, httpx.TimeoutException):
        return None
    except httpx.HTTPStatusError:
        return None
    except Exception:
        return None


def _display_server_offline(display: StatusDisplay, server_url: str) -> None:
    """Display server offline message."""
    display.print_section("Server Status")
    display.print_error(f"Server offline at {server_url}")
    display.print_info(
        "The CodeWeaver server is not running. Commands like 'index' and 'search' can still work without the server."
    )
    display.print_info("To start the server, run: codeweaver server start")


def _display_full_status(
    display: StatusDisplay, status_data: dict[str, Any], *, verbose: bool
) -> None:
    """Display full status information.

    Args:
        display: StatusDisplay instance
        status_data: Status data from server
        verbose: Show detailed information
    """
    # Server uptime
    display.print_section("Server Status")
    uptime = status_data.get("uptime_seconds", 0)
    display.print_success(f"Server online - Uptime: {_format_duration(uptime)}")
    if verbose:
        display.print_info(f"Timestamp: {status_data.get('timestamp', 'unknown')}")

    # Indexing status
    if "indexing" in status_data:
        _display_indexing_status(display, status_data["indexing"], verbose)

    # Failover status
    if "failover" in status_data:
        _display_failover_status(display, status_data["failover"], verbose)

    # Statistics summary
    if "statistics" in status_data and verbose:
        _display_statistics(display, status_data["statistics"])


def _display_indexing_status(
    display: StatusDisplay, indexing_data: dict[str, Any], *, verbose: bool
) -> None:
    """Display indexing status section."""
    display.print_section("Indexing Status")

    if indexing_data.get("active", False):
        display.print_info("Indexing: ACTIVE", prefix="🔄")

        # Create progress table
        table = Table(title="Indexing Progress", show_header=True, header_style="bold cyan")
        table.add_column("Metric", style="dim")
        table.add_column("Value", justify="right")

        table.add_row("Files Discovered", str(indexing_data.get("files_discovered", 0)))
        table.add_row("Files Processed", str(indexing_data.get("files_processed", 0)))
        table.add_row("Chunks Created", str(indexing_data.get("chunks_created", 0)))
        table.add_row("Chunks Embedded", str(indexing_data.get("chunks_embedded", 0)))
        table.add_row("Chunks Indexed", str(indexing_data.get("chunks_indexed", 0)))

        if verbose:
            elapsed = indexing_data.get("elapsed_time_seconds", 0)
            rate = indexing_data.get("processing_rate", 0)
            errors = indexing_data.get("errors", 0)

            table.add_row("Elapsed Time", _format_duration(elapsed))
            table.add_row("Processing Rate", f"{rate:.2f} files/sec")
            table.add_row("Errors", str(errors))

        display.print_table(table)
    else:
        display.print_info("Indexing: IDLE", prefix="💤")


def _display_failover_status(
    display: StatusDisplay, failover_data: dict[str, Any], *, verbose: bool
) -> None:
    """Display failover status section."""
    display.print_section("Failover Status")

    enabled = failover_data.get("enabled", False)

    if not enabled:
        display.print_info("Failover: DISABLED", prefix="❌")
        return

    active = failover_data.get("active", False)
    active_store = failover_data.get("active_store_type", "primary")

    if active:
        display.print_warning(f"Failover: ACTIVE - Using {active_store} store")

        # Create failover details table
        table = Table(title="Failover Details", show_header=True, header_style="bold yellow")
        table.add_column("Metric", style="dim")
        table.add_column("Value", justify="right")

        table.add_row("Active Store", active_store)
        table.add_row("Failover Count", str(failover_data.get("failover_count", 0)))

        total_time = failover_data.get("total_failover_time_seconds", 0)
        table.add_row("Total Failover Time", _format_duration(total_time))

        if last_failover := failover_data.get("last_failover_time"):
            table.add_row("Last Failover", last_failover)

        if verbose:
            table.add_row("Backup Syncs", str(failover_data.get("backup_syncs_completed", 0)))
            table.add_row("Chunks in Failover", str(failover_data.get("chunks_in_failover", 0)))

            if circuit_state := failover_data.get("primary_circuit_breaker_state"):
                table.add_row("Primary Circuit Breaker", circuit_state)

        display.print_table(table)
    else:
        display.print_success(f"Failover: ENABLED - Using {active_store} store")

        if verbose and failover_data.get("failover_count", 0) > 0:
            display.print_info(
                f"Total failovers: {failover_data.get('failover_count', 0)} "
                f"(Total time: {_format_duration(failover_data.get('total_failover_time_seconds', 0))})"
            )


def _display_statistics(display: StatusDisplay, stats_data: dict[str, Any]) -> None:
    """Display session statistics section."""
    display.print_section("Session Statistics")

    table = Table(title="Request Summary", show_header=True, header_style="bold cyan")
    table.add_column("Metric", style="dim")
    table.add_column("Count", justify="right")

    table.add_row("Total Requests", str(stats_data.get("total_requests", 0)))
    table.add_row("Successful Requests", str(stats_data.get("successful_requests", 0)))
    table.add_row("Failed Requests", str(stats_data.get("failed_requests", 0)))

    display.print_table(table)


def _format_duration(seconds: float) -> str:
    """Format duration in seconds to human-readable string.

    Args:
        seconds: Duration in seconds

    Returns:
        Formatted duration string (e.g., "1h 23m 45s")
    """
    if seconds < 60:
        return f"{int(seconds)}s"

    minutes = int(seconds // 60)
    remaining_seconds = int(seconds % 60)

    if minutes < 60:
        return f"{minutes}m {remaining_seconds}s"

    hours = minutes // 60
    remaining_minutes = minutes % 60

    return f"{hours}h {remaining_minutes}m {remaining_seconds}s"
