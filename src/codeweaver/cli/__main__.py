# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""CodeWeaver CLI entrypoint.

Commands are registered and lazy-loaded from here.
"""

from __future__ import annotations

import sys

from cyclopts import App
from rich.console import Console

from codeweaver import __version__
from codeweaver.common import CODEWEAVER_PREFIX


console = Console(markup=True, emoji=True)
app = App(
    "codeweaver",
    help="CodeWeaver: Powerful code search and understanding for humans and agents.",
    version=__version__,
    console=console,
)
app.command(
    "codeweaver.cli.commands.config:main",
    name="config",
    help="Manage your CodeWeaver configuration.",
)
app.command("codeweaver.cli.commands.server:main", name="server", help="Run the CodeWeaver server.")
app.command("codeweaver.cli.commands.search:main", name="search", help="Search your codebase.")
app.command(
    "codeweaver.cli.commands.index:main",
    name="index",
    help="Check the status of your codebase index.",
)
app.command(
    "codeweaver.cli.commands.doctor:main", name="doctor", help="Diagnose and fix common issues."
)
app.command(
    "codeweaver.cli.commands.list:main",
    name="list",
    alias="ls",
    help="List available providers, models, and more.",
)

# these are scaffolded for future implementation
# app.command("codeweaver.cli.commands.context:main", name="context", alias="prep")
# app.command("codeweaver.cli.commands.init:main", name="init", alias="initialize")


def main() -> None:
    """Main CLI entry point."""
    try:
        app()
    except KeyboardInterrupt:
        console.print(f"\n{CODEWEAVER_PREFIX} [yellow]Operation cancelled by user[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"{CODEWEAVER_PREFIX} [red]Fatal error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()


__all__ = ("app", "main")
