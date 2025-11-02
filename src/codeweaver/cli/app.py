# sourcery skip: avoid-global-variables, no-complex-if-expressions
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""CLI application for CodeWeaver using cyclopts."""

from __future__ import annotations

import sys

from collections.abc import Sequence
from pathlib import Path
from typing import Annotated, Literal

import cyclopts

from pydantic import FilePath
from rich import print as rich_print
from rich.console import Console
from rich.table import Table

from codeweaver.agent_api import CodeMatch, FindCodeResponseSummary, IntentType  #  find_code
from codeweaver.common import CODEWEAVER_PREFIX
from codeweaver.common.utils import LazyImport, lazy_import
from codeweaver.config.settings import CodeWeaverSettingsDict
from codeweaver.core.types.dictview import DictView
from codeweaver.exceptions import CodeWeaverError


# Lazy import for performance
get_settings_map: LazyImport[DictView[CodeWeaverSettingsDict]] = lazy_import(
    "codeweaver.config", "get_settings_map"
)

# Initialize console for rich output
console = Console(markup=True, emoji=True)

# Create the main CLI application
app = cyclopts.App(
    name="codeweaver",
    help="CodeWeaver: A tool that gives AI agents exactly what you need them to have.",
)


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


@app.command
async def search(
    query: str,
    *,
    intent: IntentType | None = None,
    limit: int = 10,
    include_tests: bool = True,
    project_path: Annotated[Path | None, cyclopts.Parameter(name=["--project", "-p"])] = None,
    output_format: Literal["json", "table", "markdown"] = "table",
) -> None:
    """Search codebase from command line (using stub during refactor)."""
    try:
        settings = get_settings_map()
        if project_path:
            from codeweaver.config.settings import update_settings

            settings = update_settings(project_path=project_path)  # type: ignore

        console.print(f"{CODEWEAVER_PREFIX} [blue]Searching in: {settings['project_path']}[/blue]")
        console.print(f"{CODEWEAVER_PREFIX} [blue]Query: {query}[/blue]")

        # Use stub find_code_tool during refactor
        from codeweaver.server.app_bindings import find_code_tool

        response = await find_code_tool(
            query=query,
            intent=intent,
            token_limit=settings.get("token_limit", 10000),
            include_tests=include_tests,
            focus_languages=None,
            context=None,
        )

        # Limit results for CLI display
        limited_matches = response.matches[:limit]

        # Output results in requested format
        if output_format == "json":
            rich_print(response.model_dump_json(indent=2))

        elif output_format == "table":
            _display_table_results(query, response, limited_matches)

        elif output_format == "markdown":
            _display_markdown_results(query, response, limited_matches)

    except CodeWeaverError as e:
        console.print(f"[red]Error: {e.message}[/red]")
        if e.suggestions:
            console.print("[yellow]Suggestions:[/yellow]")
            for suggestion in e.suggestions:
                console.print(f"  • {suggestion}")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
        sys.exit(1)


@app.command
async def config(
    *,
    show: bool = False,
    project_path: Annotated[Path | None, cyclopts.Parameter(name=["--project", "-p"])] = None,
) -> None:
    """Manage CodeWeaver configuration."""
    try:
        settings = get_settings_map()
        if project_path:
            from codeweaver.config.settings import update_settings

            settings = update_settings(project_path=project_path)  # type: ignore

        if show:
            _show_config(settings)
        else:
            console.print("Use --show to display configuration")

    except CodeWeaverError as e:
        console.print(f"[red]Configuration Error: {e.message}[/red]")
        if e.suggestions:
            console.print("[yellow]Suggestions:[/yellow]")
            for suggestion in e.suggestions:
                console.print(f"  • {suggestion}")
        sys.exit(1)


def _display_table_results(
    query: str, response: FindCodeResponseSummary, matches: Sequence[CodeMatch]
) -> None:
    """Display search results as a table using serialize_for_cli."""
    console.print(f"\n[bold green]Search Results for: '{query}'[/bold green]")

    # Use the built-in CLI summary from FindCodeResponseSummary
    summary_table = response.assemble_cli_summary()
    console.print(summary_table)

    # If there are matches, display them in a detailed table
    if matches:
        _display_match_details(matches)
    else:
        console.print("\n[yellow]No matches found[/yellow]")


def _display_match_details(matches: Sequence[CodeMatch]) -> None:
    console.print("\n[bold blue]Match Details:[/bold blue]\n")

    table = Table(show_header=True, header_style="bold blue")
    table.add_column("File", style="cyan", no_wrap=True, min_width=30)
    table.add_column("Language", style="green", min_width=10)
    table.add_column("Score", style="yellow", justify="right", min_width=8)
    table.add_column("Lines", style="magenta", justify="center", min_width=10)
    table.add_column("Preview", style="white", min_width=40, max_width=60)

    for match in matches:
        # Use serialize_for_cli to get structured data
        match_data = match.serialize_for_cli()

        preview = match.content.content  # serialize_for_cli truncates content for preview
        if not preview.strip():
            preview = "<no content>"
        else:
            table.add_row(
                str(match_data.get("file", {}).get("path", "unknown")),
                str(match_data.get("file", {}).get("ext_kind", {}).get("language", "unknown")),
                f"{match.relevance_score:.2f}",
                f"{match.span!s}",
                preview,
            )

    console.print(table)


def _display_markdown_results(
    query: str, response: FindCodeResponseSummary, matches: Sequence[CodeMatch]
) -> None:
    """Display search results as markdown using serialize_for_cli."""
    console.print(f"# Search Results for: '{query}'\n")
    console.print(f"Found {response.total_matches} matches in {response.execution_time_ms:.1f}ms\n")

    if not matches:
        console.print("*No matches found*")
        return

    for i, match in enumerate(matches, 1):
        # Use serialize_for_cli to get structured data
        match_data = match.serialize_for_cli()

        file_path = match_data.get("file", {}).get("path", "unknown")
        language = match_data.get("file", {}).get("ext_kind", {}).get("language", "unknown")

        console.print(f"## {i}. {file_path}")
        console.print(
            f"**Language:** {language} | **Score:** {match.relevance_score:.2f} | {match.span!s}"
        )
        console.print(f"```{language}")
        console.print(str(match.content) if match.content else "")
        console.print("```\n")


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
    table.add_row("Telemetry", "✅" if settings["enable_telemetry"] else "❌")

    console.print(table)


def main() -> None:
    """Main CLI entry point."""
    try:
        app()
    except KeyboardInterrupt:
        console.print("\n[yellow]Operation cancelled by user[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"[red]Fatal error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()


__all__ = ["app", "main"]
