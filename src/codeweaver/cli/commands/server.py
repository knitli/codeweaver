# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""CodeWeaver MCP server command-line interface."""

import sys

from pathlib import Path
from typing import Annotated

import cyclopts

from cyclopts import App
from pydantic import FilePath
from rich.console import Console

from codeweaver.common import CODEWEAVER_PREFIX
from codeweaver.exceptions import CodeWeaverError


console = Console(markup=True, emoji=True)
app = App("server", help="Start CodeWeaver MCP server.", console=console)


async def _run_server(
    config_file: Annotated[FilePath | None, cyclopts.Parameter(name=["--config", "-c"])] = None,
    project_path: Annotated[Path | None, cyclopts.Parameter(name=["--project", "-p"])] = None,
    host: str = "127.0.0.1",
    port: int = 9328,
    *,
    debug: bool = False,
    verbose: bool = False,
) -> None:
    from codeweaver.main import run

    # Only print startup message in verbose/debug mode
    if verbose or debug:
        console.print(f"{CODEWEAVER_PREFIX} [blue]Starting CodeWeaver MCP server...[/blue]")
    return await run(
        config_file=config_file,
        project_path=project_path,
        host=host,
        port=port,
        debug=debug,
        verbose=verbose,
    )


@app.default
async def server(
    *,
    config_file: Annotated[FilePath | None, cyclopts.Parameter(name=["--config", "-c"])] = None,
    project_path: Annotated[Path | None, cyclopts.Parameter(name=["--project", "-p"])] = None,
    host: str = "127.0.0.1",
    port: int = 9328,
    verbose: Annotated[
        bool,
        cyclopts.Parameter(name=["--verbose", "-v"], help="Enable verbose logging with timestamps"),
    ] = False,
    debug: Annotated[
        bool, cyclopts.Parameter(name=["--debug", "-d"], help="Enable debug logging")
    ] = False,
) -> None:
    """Start CodeWeaver MCP server."""
    try:
        await _run_server(
            config_file=config_file,
            project_path=project_path,
            host=host,
            port=port,
            debug=debug,
            verbose=verbose,
        )

    except CodeWeaverError as e:
        # When we're exiting due to an error, show full details regardless of verbosity
        console.print(
            f"\n{CODEWEAVER_PREFIX} [bold red]✗ Server failed to start[/bold red]\n", style="bold"
        )
        console.print(f"[red]Error:[/red] {e}\n")

        # Show details if available
        if hasattr(e, "details") and e.details:
            console.print("[yellow]Details:[/yellow]")
            import json

            console.print(json.dumps(e.details, indent=2))
            console.print()

        # Show suggestions if available
        if e.suggestions:
            console.print("[yellow]Suggestions:[/yellow]")
            for suggestion in e.suggestions:
                console.print(f"  • {suggestion}")
            console.print()

        # Show full traceback in verbose/debug mode
        if verbose or debug:
            console.print("[dim]Full traceback:[/dim]")
            console.print_exception(show_locals=True)

        sys.exit(1)

    except KeyboardInterrupt:
        # Clean shutdown message handled in server shutdown
        pass

    except Exception as e:
        # When we're exiting due to an unexpected error, always show full details
        console.print(
            f"\n{CODEWEAVER_PREFIX} [bold red]✗ Server crashed unexpectedly[/bold red]\n",
            style="bold",
        )
        console.print(f"[red]Error:[/red] {type(e).__name__}: {e}\n")
        console.print("[yellow]Full traceback:[/yellow]")
        console.print_exception(show_locals=True, word_wrap=True)
        console.print("\n[dim]Tip: Please report this error with the traceback above[/dim]\n")
        sys.exit(1)


def main() -> None:
    """Entry point for the CodeWeaver server CLI."""
    try:
        app()
    except Exception:
        console.print_exception(show_locals=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

__all__ = ("app", "server")
