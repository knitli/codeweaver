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
from codeweaver.core import CODEWEAVER_PREFIX
from codeweaver.core.di import get_container
from codeweaver.core.ui_protocol import ProgressReporter
from codeweaver.core.utils.environment import detect_root_package


if TYPE_CHECKING:
    from rich.console import Console

    from codeweaver.cli.ui.status_display import StatusDisplay

ROOT_PACKAGE = detect_root_package()

display: StatusDisplay = get_display()
console: Console = display.console
app = App(
    "codeweaver",
    help="CodeWeaver: Powerful code search and understanding for humans and agents.",
    default_parameter=Parameter(negative=()),
    version=__version__,
    console=console,
)
# command availability depends on what codeweaver packages are installed
# if server; everything is available, and then progressively less from there
if ROOT_PACKAGE == "server":
    app.command("codeweaver.cli.commands.init:app", name="init")
    app.command("codeweaver.cli.commands.doctor:app", name="doctor")
    app.command("codeweaver.cli.commands.search:app", name="search")
    app.command("codeweaver.cli.commands.server:app", name="server")
    app.command("codeweaver.cli.commands.start:app", name="start")
    app.command("codeweaver.cli.commands.stop:app", name="stop")
    app.command("codeweaver.cli.commands.status:app", name="status")
    # these are scaffolded for future implementation
    # app.command("codeweaver.cli.commands.context:app", name="context", alias="prep")
if ROOT_PACKAGE in ("engine", "server"):
    app.command("codeweaver.cli.commands.index:app", name="index")
if ROOT_PACKAGE in ("provider", "engine", "server"):
    app.command("codeweaver.cli.commands.list:app", name="list", alias="ls")

app.command("codeweaver.cli.commands.config:app", name="config")


def _handle_keyboard_interrupt():
    console.print(
        f"\n{CODEWEAVER_PREFIX} [yellow]⚠️ We got a keyboard interrupt signal...⚠️[/yellow]"
    )
    console.print(f"{CODEWEAVER_PREFIX} [yellow]Thanks for using CodeWeaver![/yellow]")
    console.print(
        f"{CODEWEAVER_PREFIX} [yellow]If you like CodeWeaver, please take a second to give us a star on GitHub! 🌟[/yellow] [cyan]https://github.com/knitli/codeweaver [/cyan] \n"
    )
    console.print()
    console.print("[dim]If you have feedback, please open an issue or discussion:[/dim]")
    console.print("  [dim]issues: https://github.com/knitli/codeweaver/issues[/dim]")
    console.print("  [dim]discussions: https://github.com/knitli/codeweaver/discussions[/dim]")


def main() -> None:
    """Main CLI entry point."""
    import asyncio
    from codeweaver.core.dependencies import bootstrap_settings

    # Bootstrap settings and initialize DI container
    # This must happen before any commands are executed
    async def _init_di():
        """Initialize dependency injection container with settings."""
        # Bootstrap settings - this registers them in the DI container
        await bootstrap_settings()
        # Override DI to use StatusDisplay instead of default RichConsoleProgressReporter
        get_container().override(ProgressReporter, display)

    # Run async initialization
    try:
        asyncio.run(_init_di())
    except Exception as e:
        console.print(f"{CODEWEAVER_PREFIX} [bold red]Failed to initialize: {e}[/bold red]")
        console.print("\n[red]Traceback:[/red]")
        console.print_exception(max_frames=10)
        sys.exit(1)

    try:
        app()
    except KeyboardInterrupt:
        _handle_keyboard_interrupt()
    except Exception as e:
        console.print(f"{CODEWEAVER_PREFIX} [bold red]Fatal error: {e}[/bold red]")
        console.print("\n[red]Traceback:[/red]")
        console.print_exception(max_frames=10)
        sys.exit(1)


if __name__ == "__main__":
    main()


__all__ = ("app", "main")
