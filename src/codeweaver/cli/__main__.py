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

from pathlib import Path


# NOTE: google.genai emits a pydantic deprecation warning during module import
# (before our code runs). To suppress it, set: PYTHONWARNINGS='ignore::pydantic.warnings.PydanticDeprecatedSince212'
# We suppress runtime warnings here, but import-time warnings occur too early to catch.
with contextlib.suppress(Exception):
    from pydantic.warnings import PydanticDeprecatedSince212

    warnings.simplefilter("ignore", PydanticDeprecatedSince212)

from typing import TYPE_CHECKING, NoReturn

from cyclopts import App, Parameter

from codeweaver import __version__
from codeweaver.cli.ui import get_display
from codeweaver.core.di.container import (
    get_container,  # ensure we're pulling in the container module
)
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
    from codeweaver.core.utils import get_codeweaver_prefix

    prefix = get_codeweaver_prefix()
    console.print(f"\n{prefix} [yellow]⚠️ We got a keyboard interrupt signal...⚠️[/yellow]")
    console.print(f"{prefix} [yellow]Thanks for using CodeWeaver![/yellow]")
    console.print(
        f"{prefix} [yellow]If you like CodeWeaver, please take a second to give us a star on GitHub! 🌟[/yellow] [cyan]https://github.com/knitli/codeweaver [/cyan] \n"
    )
    console.print()
    console.print("[dim]If you have feedback, please open an issue or discussion:[/dim]")
    console.print("  [dim]issues: https://github.com/knitli/codeweaver/issues[/dim]")
    console.print("  [dim]discussions: https://github.com/knitli/codeweaver/discussions[/dim]")


async def _init_di(config_path: str | None = None) -> None:
    """Initialize dependency injection container with settings."""
    from codeweaver.core.dependencies import bootstrap_settings

    # Bootstrap settings - this registers them in the DI container
    await bootstrap_settings(config_file=Path(config_path) if config_path else None)
    # Override DI to use StatusDisplay instead of default RichConsoleProgressReporter
    get_container().override(ProgressReporter, display)


def _print_error_message(message: str, e: Exception) -> NoReturn:
    from codeweaver.core.utils import get_codeweaver_prefix

    prefix = get_codeweaver_prefix()
    console.print(f"{prefix} {message}{e}")
    console.print("\n[red]Traceback:[/red]")
    console.print_exception(max_frames=10)
    raise SystemExit(1) from e


async def _config_in_args(args: list[str]) -> str | None:
    """Check if a --config argument is provided in the CLI args."""
    return next(
        (
            (arg.split("=", 1)[1] if "=" in arg else args[i + 1] if i + 1 < len(args) else None)
            for i, arg in enumerate(args)
            if arg.startswith(("--config", "-c"))
        ),
        None,
    )


async def _async_main() -> None:
    """Async main CLI entry point with DI initialization."""
    try:
        await _init_di(config_path=await _config_in_args(sys.argv))
    except Exception as e:
        _print_error_message(" [bold red]Fatal error during DI initialization: ", e)
    try:
        app()
    except KeyboardInterrupt:
        _handle_keyboard_interrupt()
    except Exception as e:
        _print_error_message(" [bold red]Fatal error: ", e)


def main() -> None:
    """Main CLI entry point (sync wrapper for async logic)."""
    from codeweaver.core.utils.procs import asyncio_or_uvloop

    loop = asyncio_or_uvloop()
    loop.run(_async_main())


if __name__ == "__main__":
    from codeweaver.core.utils import get_codeweaver_prefix

    prefix = get_codeweaver_prefix()
    console.print(f"{prefix} Starting CodeWeaver CLI...", style="dim")
    try:
        main()
        console.print("Settings initialized.", style="dim")
    except Exception as e:
        try:
            _print_error_message(" [bold red]Fatal error during startup: ", e)
        except Exception:
            sys.exit(1)


__all__ = ("app", "main")
