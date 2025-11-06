"""CodeWeaver CLI - Search Command."""

# sourcery skip: avoid-global-variables, no-complex-if-expressions
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
from __future__ import annotations

import sys

from collections.abc import Sequence
from pathlib import Path
from typing import Annotated, Literal

import cyclopts

from cyclopts import App
from rich import print as rich_print
from rich.console import Console
from rich.table import Table

from codeweaver.agent_api.find_code.intent import IntentType
from codeweaver.agent_api.find_code.types import CodeMatch, FindCodeResponseSummary
from codeweaver.common import CODEWEAVER_PREFIX
from codeweaver.config.settings import get_settings_map
from codeweaver.exceptions import CodeWeaverError


console = Console(markup=True, emoji=True)
app = App(
    "search", default_command="search", help="Search codebase from command line.", console=console
)


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
    """Search your codebase from the command line with plain language."""
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
        console.print(f"{CODEWEAVER_PREFIX} [red]Error: {e.message}[/red]")
        if e.suggestions:
            console.print(f"{CODEWEAVER_PREFIX} [yellow]Suggestions:[/yellow]")
            for suggestion in e.suggestions:
                console.print(f"  • {suggestion}")
        sys.exit(1)
    except Exception as e:
        console.print(f"{CODEWEAVER_PREFIX} [red]Unexpected error: {e}[/red]")
        sys.exit(1)


def _display_table_results(
    query: str, response: FindCodeResponseSummary, matches: Sequence[CodeMatch]
) -> None:
    """Display search results as a table using serialize_for_cli."""
    console.print(f"\n{CODEWEAVER_PREFIX} [bold green]Search Results for: '{query}'[/bold green]")

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
    console.print(f"{CODEWEAVER_PREFIX} # Search Results for: '{query}'\n")
    console.print(
        f"{CODEWEAVER_PREFIX} Found {response.total_matches} matches in {response.execution_time_ms:.1f}ms\n"
    )

    if not matches:
        console.print(f"{CODEWEAVER_PREFIX} *No matches found*")
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


def main() -> None:
    """Entry point for the search CLI command."""
    try:
        app()
    except Exception as e:
        console.print(f"{CODEWEAVER_PREFIX} [red]Unexpected error: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    main()

__all__ = ("app", "search")
