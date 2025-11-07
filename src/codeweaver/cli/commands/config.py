# sourcery skip: avoid-global-variables, name-type-suffix, no-complex-if-expressions
# sourcery skip: avoid-global-variables, no-complex-if-expressions
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Config-related CLI commands for CodeWeaver."""

from __future__ import annotations

import sys

from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import cyclopts

from cyclopts import App
from rich.console import Console
from rich.table import Table

from codeweaver.common import CODEWEAVER_PREFIX
from codeweaver.core.types.enum import BaseEnum


if TYPE_CHECKING:
    from codeweaver.config.types import CodeWeaverSettingsDict
    from codeweaver.core.types.dictview import DictView

console = Console(markup=True, emoji=True)
app = App("config", help="Manage and view your CodeWeaver config.", console=console)


class ConfigProfile(BaseEnum):
    """Configuration profiles for quick setup."""

    RECOMMENDED = "recommended"
    LOCAL_ONLY = "local-only"
    MINIMAL = "minimal"


@app.default()
def config(
    *, project_path: Annotated[Path | None, cyclopts.Parameter(name=["--project", "-p"])] = None
) -> None:
    """Manage CodeWeaver configuration."""
    from codeweaver.config.settings import get_settings_map
    from codeweaver.exceptions import CodeWeaverError

    try:
        settings = get_settings_map()
        if project_path:
            from codeweaver.config.settings import update_settings

            settings = update_settings(project_path=project_path)  # type: ignore

        _show_config(settings)

    except CodeWeaverError as e:
        console.print(f"{CODEWEAVER_PREFIX} [red]Configuration Error: {e.message}[/red]")
        if e.suggestions:
            console.print(f"{CODEWEAVER_PREFIX} [yellow]Suggestions:[/yellow]")
            for suggestion in e.suggestions:
                console.print(f"  • {suggestion}")
        sys.exit(1)


def _show_config(settings: DictView[CodeWeaverSettingsDict]) -> None:
    """Display current configuration."""
    from codeweaver.core.types.sentinel import Unset

    console.print("[bold blue]CodeWeaver Configuration[/bold blue]\n")

    table = Table(show_header=True, header_style="bold blue")
    table.add_column("Setting", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")

    # Core settings
    table.add_row("Project Path", str(settings["project_path"]))
    table.add_row("Project Name", settings["project_name"] or "auto-detected")
    table.add_row("Token Limit", str(settings["token_limit"]))
    table.add_row("Max File Size", f"{settings['max_file_size']:,} bytes")
    table.add_row("Max Results", str(settings["max_results"]))

    # Feature flags
    table.add_row(
        "Background Indexing",
        "❌"
        if settings["indexing"].get("only_index_on_command")
        and not isinstance(settings["indexing"].get("only_index_on_command"), Unset)
        else "✅",
    )
    table.add_row("Telemetry", "❌" if settings["telemetry"].get("disable_telemetry") else "✅")

    console.print(table)


def main() -> None:
    """Main entry point for config CLI."""
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
