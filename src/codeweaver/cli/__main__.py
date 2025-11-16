# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""CodeWeaver CLI entrypoint.

Commands are registered and lazy-loaded from here.
"""

from __future__ import annotations

import contextlib
import sys
import warnings


# NOTE: google.genai emits a pydantic deprecation warning during module import
# (before our code runs). To suppress it, set: PYTHONWARNINGS='ignore::pydantic.warnings.PydanticDeprecatedSince212'
# We suppress runtime warnings here, but import-time warnings occur too early to catch.
with contextlib.suppress(Exception):
    from pydantic.warnings import PydanticDeprecatedSince212

    warnings.simplefilter("ignore", PydanticDeprecatedSince212)

from typing import TYPE_CHECKING

from cyclopts import App, Parameter

from codeweaver import __version__
from codeweaver.cli.ui import get_display
from codeweaver.common import CODEWEAVER_PREFIX


if TYPE_CHECKING:
    from rich.console import Console

    from codeweaver.cli.ui.status_display import StatusDisplay

display: StatusDisplay = get_display()
console: Console = display.console
app = App(
    "codeweaver",
    help="CodeWeaver: Powerful code search and understanding for humans and agents.",
    default_parameter=Parameter(negative=()),
    version=__version__,
    console=console,
)
app.command("codeweaver.cli.commands.config:app", name="config")
app.command("codeweaver.cli.commands.server:app", name="server")
app.command("codeweaver.cli.commands.search:app", name="search")
app.command("codeweaver.cli.commands.index:app", name="index")
app.command("codeweaver.cli.commands.doctor:app", name="doctor")
app.command("codeweaver.cli.commands.list:app", name="list", alias="ls")
app.command("codeweaver.cli.commands.init:app", name="init")
app.command("codeweaver.cli.commands.status:app", name="status")

# these are scaffolded for future implementation
# app.command("codeweaver.cli.commands.context:app", name="context", alias="prep")


def main() -> None:
    """Main CLI entry point."""
    try:
        app()
    except KeyboardInterrupt:
        console.print(
            f"\n{CODEWEAVER_PREFIX} [yellow]⚠️ We got a keyboard interrupt signal...⚠️[/yellow]"
        )
        from rich.prompt import Confirm

        if Confirm.ask(
            f"\n{CODEWEAVER_PREFIX} [bold cyan]Do you want to exit CodeWeaver?[/bold cyan] \n ... or did your cat walk across your keyboard? 🐈 [dim]([bold]Tip:[/bold] any key but 'n' will exit)[/dim]",
            console=console,
            default=True,
            choices=["y", "n"],
        ):
            sys.exit(0)
    except Exception as e:
        console.print(f"{CODEWEAVER_PREFIX} [bold red]Fatal error: {e}[/bold red]")
        console.print("\n[red]Traceback:[/red]")
        console.print_exception(max_frames=10)
        sys.exit(1)


if __name__ == "__main__":
    main()


__all__ = ("app", "main")
