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
app = App("server", default_command="server", help="Start CodeWeaver MCP server.", console=console)


async def _run_server(
    config_file: Annotated[FilePath | None, cyclopts.Parameter(name=["--config", "-c"])] = None,
    project_path: Annotated[Path | None, cyclopts.Parameter(name=["--project", "-p"])] = None,
    host: str = "127.0.0.1",
    port: int = 9328,
    *,
    debug: bool = False,
) -> None:
    from codeweaver.main import run

    console.print(f"{CODEWEAVER_PREFIX} [blue]Starting CodeWeaver MCP server...[/blue]")
    return await run(config_file=config_file, project_path=project_path, host=host, port=port)


@app.command
async def server(
    *,
    config_file: Annotated[FilePath | None, cyclopts.Parameter(name=["--config", "-c"])] = None,
    project_path: Annotated[Path | None, cyclopts.Parameter(name=["--project", "-p"])] = None,
    host: str = "127.0.0.1",
    port: int = 9328,
    debug: bool = False,
) -> None:
    """Start CodeWeaver MCP server."""
    try:
        await _run_server(
            config_file=config_file, project_path=project_path, host=host, port=port, debug=debug
        )

    except CodeWeaverError as e:
        console.print_exception(show_locals=True)
        if e.suggestions:
            console.print(f"{CODEWEAVER_PREFIX} [yellow]Suggestions:[/yellow]")
            for suggestion in e.suggestions:
                console.print(f"  • {suggestion}")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print_exception(show_locals=False, word_wrap=True)
    except Exception:
        console.print_exception(show_locals=True, word_wrap=True)
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
