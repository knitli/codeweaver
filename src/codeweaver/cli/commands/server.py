# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""CodeWeaver MCP server command-line interface."""

from pathlib import Path
from typing import Annotated, Literal

import cyclopts

from cyclopts import App
from pydantic import FilePath

from codeweaver.cli.ui import CLIErrorHandler, StatusDisplay, get_display
from codeweaver.exceptions import CodeWeaverError


_display: StatusDisplay = get_display()
app = App("server", help="Start CodeWeaver MCP server.")


async def _run_server(
    config_file: Annotated[FilePath | None, cyclopts.Parameter(name=["--config", "-c"])] = None,
    project_path: Annotated[Path | None, cyclopts.Parameter(name=["--project", "-p"])] = None,
    host: str = "127.0.0.1",
    port: int = 9328,
    transport: Annotated[
        Literal["streamable-http", "stdio"],
        cyclopts.Parameter(
            name=["--transport", "-t"],
            help="Transport type for MCP communication (streamable-http or stdio)",
        ),
    ] = "streamable-http",
    *,
    debug: bool = False,
    verbose: bool = False,
) -> None:
    from codeweaver.main import run

    # Only print startup message in verbose/debug mode
    if verbose or debug:
        display = StatusDisplay()
        display.print_info("Starting CodeWeaver MCP server...")
    return await run(
        config_file=config_file,
        project_path=project_path,
        host=host,
        port=port,
        transport=transport,
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
    transport: Annotated[
        Literal["streamable-http", "stdio"],
        cyclopts.Parameter(
            name=["--transport", "-t"],
            help="Transport type for MCP communication (streamable-http or stdio)",
        ),
    ] = "streamable-http",
    verbose: Annotated[
        bool,
        cyclopts.Parameter(name=["--verbose", "-v"], help="Enable verbose logging with timestamps"),
    ] = False,
    debug: Annotated[
        bool, cyclopts.Parameter(name=["--debug", "-d"], help="Enable debug logging")
    ] = False,
) -> None:
    """Start CodeWeaver MCP server."""
    display = StatusDisplay()
    error_handler = CLIErrorHandler(display, verbose=verbose, debug=debug)

    try:
        await _run_server(
            config_file=config_file,
            project_path=project_path,
            host=host,
            port=port,
            transport=transport,
            debug=debug,
            verbose=verbose,
        )

    except CodeWeaverError as e:
        error_handler.handle_error(e, "Server startup", exit_code=1)

    except KeyboardInterrupt:
        # Clean shutdown message handled in server shutdown
        pass

    except Exception as e:
        error_handler.handle_error(e, "Server", exit_code=1)


def main() -> None:
    """Entry point for the CodeWeaver server CLI."""
    display = StatusDisplay()
    error_handler = CLIErrorHandler(display, verbose=True, debug=True)

    try:
        app()
    except Exception as e:
        error_handler.handle_error(e, "CLI", exit_code=1)


if __name__ == "__main__":
    main()

__all__ = ("app", "server")
