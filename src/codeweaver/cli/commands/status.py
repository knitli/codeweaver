# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Status command for viewing CodeWeaver runtime status.

Displays real-time operational information including indexing progress,
failover status, and active operations.
"""

from __future__ import annotations

import asyncio

from typing import Any

from cyclopts import App
from pydantic_core import from_json
from rich.table import Table

from codeweaver.cli.ui import CLIErrorHandler, StatusDisplay, get_display


_display: StatusDisplay = get_display()
app = App("status", help="Show CodeWeaver runtime status.")


def get_url() -> str:
    """Get the MCP server URL from settings (http transport)."""
    from codeweaver.config.settings import get_settings_map

    settings_map = get_settings_map()
    host = settings_map["server"]["host"] or "127.0.0.1"
    port = settings_map["server"]["port"] or "9328"  # WEAV
    return f"http://{host}:{port}"


def get_management_url() -> str:
    """Get the management server URL from settings."""
    from codeweaver.config.settings import get_settings_map

    settings_map = get_settings_map()
    mgmt_host = settings_map["server"].get("management_host", "127.0.0.1")
    mgmt_port = settings_map["server"].get("management_port", 9329)
    return f"http://{mgmt_host}:{mgmt_port}"


@app.default
async def status(*, verbose: bool = False, watch: bool = False, watch_interval: int = 5) -> None:
    """Show CodeWeaver runtime status.

    Args:
        verbose: Show detailed status information
        watch: Continuously watch status (refresh every watch_interval seconds)
        watch_interval: Seconds between updates in watch mode (default: 5)
    """
    display = _display

    if watch:
        await _watch_status(display, verbose=verbose, interval=watch_interval)
    else:
        await _show_status_once(display, verbose=verbose)


async def _show_status_once(display: StatusDisplay, *, verbose: bool) -> None:
    """Show status one time."""
    display.print_command_header("status", "CodeWeaver Runtime Status")
    server_url = get_url()
    management_url = get_management_url()

    status_data = await _query_server_status(server_url)
    management_healthy = await _query_management_health(management_url)

    # Display management server status first
    _display_management_status(display, management_url, healthy=management_healthy)

    # Then display MCP server status
    if status_data is None:
        _display_server_offline(display, server_url)
    else:
        _display_full_status(display, status_data, verbose=verbose)


async def _watch_status(display: StatusDisplay, *, verbose: bool, interval: int) -> None:
    """Continuously watch and display status."""
    display.print_command_header("status", "CodeWeaver Runtime Status (Watch Mode)")
    display.print_info(f"Refreshing every {interval} seconds. Press Ctrl+C to exit.")
    server_url = get_url()
    management_url = get_management_url()

    try:
        while True:
            # Clear screen and redisplay
            display.console.clear()
            display.print_command_header("status", "CodeWeaver Runtime Status (Watch Mode)")
            display.print_info(
                f"Refreshing every {interval} seconds. Press Ctrl+C to exit.", prefix="⏱️"
            )

            status_data = await _query_server_status(server_url)
            management_healthy = await _query_management_health(management_url)

            # Display management server status first
            _display_management_status(display, management_url, healthy=management_healthy)

            # Then display MCP server status
            if status_data is None:
                _display_server_offline(display, server_url)
            else:
                _display_full_status(display, status_data, verbose=verbose)

            await asyncio.sleep(interval)
    except KeyboardInterrupt:
        display.print_info("Watch mode stopped.", prefix="✋")


async def _query_server_status(server_url: str) -> dict[str, Any] | None:
    """Query the server /status endpoint.

    Args:
        server_url: Base URL of the server

    Returns:
        Status data dict if server is running, None if offline
    """
    import httpx

    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            response = await client.get(f"{server_url}/status")
            response.raise_for_status()
            return from_json(response.content)  # type: ignore[no-any-return]
    except (httpx.ConnectError, httpx.TimeoutException):
        return None
    except httpx.HTTPStatusError:
        return None
    except Exception:
        return None


async def _query_management_health(management_url: str) -> bool:
    """Query the management server /health endpoint.

    Args:
        management_url: Base URL of the management server

    Returns:
        True if management server is running and healthy, False otherwise
    """
    import httpx

    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            response = await client.get(f"{management_url}/health")
            return response.status_code == 200
    except Exception:
        return False


def _display_management_status(
    display: StatusDisplay, management_url: str, *, healthy: bool
) -> None:
    """Display management server status.

    Args:
        display: StatusDisplay instance
        management_url: Management server URL
        healthy: Whether management server is healthy
    """
    display.print_section("Background Services")
    if healthy:
        display.print_success("Background services running")
        display.print_info(f"Management server: {management_url}", prefix="🌐")
    else:
        display.print_warning("Background services not running")
        display.print_info("To start background services: 'cw start'")


def _display_server_offline(display: StatusDisplay, server_url: str) -> None:
    """Display server offline message."""
    display.print_section("MCP Server Status")
    display.print_error(f"MCP server offline at {server_url}")
    display.print_info(
        "The CodeWeaver server is not running. Commands like 'index' and 'search' can still work without the server."
    )
    display.print_info("To start the server, run: 'cw server'")


def _display_full_status(
    display: StatusDisplay, status_data: dict[str, Any], *, verbose: bool
) -> None:
    """Display full status information.

    Args:
        display: StatusDisplay instance
        status_data: Status data from server
        verbose: Show detailed information
    """
    # MCP server uptime
    display.print_section("MCP Server Status")
    uptime = status_data.get("uptime_seconds", 0)
    display.print_success(f"MCP server online - Uptime: {_format_duration(uptime)}")
    if verbose:
        display.print_info(f"Timestamp: {status_data.get('timestamp', 'unknown')}")

    # Indexing status
    if "indexing" in status_data:
        _display_indexing_status(display, status_data["indexing"], verbose=verbose)

    # Failover status
    if "failover" in status_data:
        _display_failover_status(display, status_data["failover"], verbose=verbose)

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
            table = _report_indexing_timing(indexing_data, table)
        display.print_table(table)
    else:
        display.print_info("Indexing: IDLE", prefix="💤")


def _report_indexing_timing(indexing_data, table) -> Table:
    elapsed = indexing_data.get("elapsed_time_seconds", 0)
    rate = indexing_data.get("processing_rate", 0)
    errors = indexing_data.get("errors", 0)

    table.add_row("Elapsed Time", _format_duration(elapsed))
    table.add_row("Processing Rate", f"{rate:.2f} files/sec")
    table.add_row("Errors", str(errors))
    return table


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
        _generate_failover_details_table(display, active_store, failover_data, verbose=verbose)
    else:
        display.print_success(f"Failover: ENABLED - Using {active_store} store")

        if verbose and failover_data.get("failover_count", 0) > 0:
            display.print_info(
                f"Total failovers: {failover_data.get('failover_count', 0)} "
                f"(Total time: {_format_duration(failover_data.get('total_failover_time_seconds', 0))})"
            )


def _generate_failover_details_table(
    display: StatusDisplay, active_store: str, failover_data: dict[str, Any], *, verbose: bool
) -> None:
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

    hours, remaining_minutes = divmod(minutes, 60)
    return f"{hours}h {remaining_minutes}m {remaining_seconds}s"


if __name__ == "__main__":
    display = _display
    error_handler = CLIErrorHandler(display, verbose=True, debug=True)
    try:
        app()
    except Exception as e:
        error_handler.handle_error(e, "Status command", exit_code=1)
