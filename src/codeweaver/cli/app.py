# sourcery skip: avoid-global-variables
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""CLI application for CodeWeaver using cyclopts."""

from __future__ import annotations

import asyncio
import sys

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Literal

import cyclopts

from pydantic_core import to_json
from rich import print as rich_print
from rich.console import Console
from rich.table import Table

from codeweaver.exceptions import CodeWeaverError
from codeweaver.settings import CodeWeaverSettings, get_settings
from codeweaver.tools.find_code import find_code_implementation


if TYPE_CHECKING:
    from codeweaver.models.core import CodeMatch, FindCodeResponseSummary
    from codeweaver.models.intent import IntentType


# Initialize console for rich output
console = Console(markup=True, emoji=True)

# Create the main CLI application
app = cyclopts.App(
    name="codeweaver",
    help="CodeWeaver: A tool that gives AI agents exactly what you need them to have.",
)


@app.command
async def server(
    *,
    config_file: Annotated[Path | None, cyclopts.Parameter(name=["--config", "-c"])] = None,
    project_path: Annotated[Path | None, cyclopts.Parameter(name=["--project", "-p"])] = None,
    host: str = "localhost",
    port: int = 9328,
    debug: bool = False,
) -> None:
    """Start CodeWeaver MCP server."""
    try:
        from codeweaver.main import app as mcp_app
        from codeweaver.main import run_method

        # Load settings with overrides
        settings = get_settings(config_file) if config_file else get_settings()
        if project_path:
            settings.project_path = project_path

        console.print("[green]Starting CodeWeaver MCP server...[/green]")
        console.print(f"[blue]Project: {settings.project_path}[/blue]")
        console.print(f"[blue]Server: http://{host}:{port}[/blue]")
        await asyncio.run(run_method(mcp_app))  # type: ignore
        await asyncio.run(mcp_app.run_http_async(host=host, port=port, debug=debug))  # type: ignore

    except CodeWeaverError as e:
        console.print(f"[red]Error: {e.message}[/red]")
        if e.suggestions:
            console.print("[yellow]Suggestions:[/yellow]")
            for suggestion in e.suggestions:
                console.print(f"  • {suggestion}")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("[yellow]Server stopped by user[/yellow]")
    except Exception as e:
        console.print(f"[red]Unexpected error: {e}[/red]")
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
    """Search codebase from command line (Phase 1: local only)."""
    try:
        # Load settings with overrides
        settings = get_settings()
        if project_path:
            settings.project_path = project_path

        console.print(f"[blue]Searching in: {settings.project_path}[/blue]")
        console.print(f"[blue]Query: {query}[/blue]")

        # Execute search
        response = await find_code_implementation(
            query=query,
            settings=settings,
            intent=intent,
            token_limit=settings.token_limit,
            include_tests=include_tests,
        )

        # Limit results for CLI display
        limited_matches = response.matches[:limit]

        # Output results in requested format
        if output_format == "json":
            # Create a simplified version for JSON output
            output = {
                "query": query,
                "summary": response.summary,
                "total_matches": response.total_matches,
                "matches": [
                    {
                        "file_path": str(match.file.path),
                        "language": match.file.ext_kind.language,
                        "relevance_score": match.relevance_score,
                        "line_range": match.span,
                        "content": (
                            f"{match.content[:200]}..."
                            if len(match.content) > 200
                            else match.content
                        ),
                    }
                    for match in limited_matches
                ],
            }
            rich_print(to_json(output, indent=2))

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
    validate: bool = False,
    project_path: Annotated[Path | None, cyclopts.Parameter(name=["--project", "-p"])] = None,
) -> None:
    """Manage CodeWeaver configuration."""
    try:
        settings = get_settings()
        if project_path:
            settings.project_path = project_path

        if show:
            _show_config(settings)
        elif validate:
            _validate_config(settings)
        else:
            console.print("Use --show to display configuration or --validate to check settings")

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
    """Display search results as a table."""
    console.print(f"\n[bold green]Search Results for: '{query}'[/bold green]")
    console.print(
        f"[dim]Found {response.total_matches} matches in {response.execution_time_ms:.1f}ms[/dim]\n"
    )

    if not matches:
        console.print("[yellow]No matches found[/yellow]")
        return

    table = Table(show_header=True, header_style="bold blue")
    table.add_column("File", style="cyan", no_wrap=True, min_width=30)
    table.add_column("Language", style="green", min_width=10)
    table.add_column("Score", style="yellow", justify="right", min_width=8)
    table.add_column("Lines", style="magenta", justify="center", min_width=10)
    table.add_column("Preview", style="white", min_width=40, max_width=60)

    for match in matches:
        preview = (
            match.content[:100].replace("\n", " ") + "..."
            if len(match.content) > 100
            else match.content.replace("\n", " ")
        )

        table.add_row(
            str(match.file.path),
            str(match.file.ext_kind.language) or "unknown",
            f"{match.relevance_score:.2f}",
            f"{match.span!s}",
            preview,
        )

    console.print(table)


def _display_markdown_results(
    query: str, response: FindCodeResponseSummary, matches: Sequence[CodeMatch]
) -> None:
    """Display search results as markdown."""
    console.print(f"# Search Results for: '{query}'\n")
    console.print(f"Found {response.total_matches} matches in {response.execution_time_ms:.1f}ms\n")

    if not matches:
        console.print("*No matches found*")
        return

    for i, match in enumerate(matches, 1):
        console.print(f"## {i}. {match.file.path}")
        console.print(
            f"**Language:** {match.file.ext_kind.language or 'unknown'} | **Score:** {match.relevance_score:.2f} | {match.span!s}"
        )
        console.print(f"```{match.file.ext_kind.language or ''}")
        console.print(f"{match.content[:300]}..." if len(match.content) > 300 else match.content)
        console.print("```\n")


def _show_config(settings: CodeWeaverSettings) -> None:
    """Display current configuration."""
    console.print("[bold blue]CodeWeaver Configuration[/bold blue]\n")

    table = Table(show_header=True, header_style="bold blue")
    table.add_column("Setting", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")

    # Core settings
    table.add_row("Project Path", str(settings.project_path))
    table.add_row("Project Name", settings.project_name or "auto-detected")
    table.add_row("Token Limit", str(settings.token_limit))
    table.add_row("Max File Size", f"{settings.max_file_size:,} bytes")
    table.add_row("Max Results", str(settings.max_results))

    # Feature flags
    table.add_row("Background Indexing", "✅" if settings.enable_background_indexing else "❌")
    table.add_row("Telemetry", "✅" if settings.enable_telemetry else "❌")
    table.add_row("AI Intent Analysis", "✅" if settings.enable_ai_intent_analysis else "❌")

    console.print(table)


def _validate_config(settings: CodeWeaverSettings) -> None:
    """Validate current configuration."""
    console.print("[bold blue]Validating Configuration...[/bold blue]\n")

    issues: list[str] = []

    # Check project path
    if not settings.project_path.exists():
        issues.append(f"Project path does not exist: {settings.project_path}")
    elif not settings.project_path.is_dir():
        issues.append(f"Project path is not a directory: {settings.project_path}")

    # Check token limits
    if settings.token_limit > 500_000:  # 500k tokens
        issues.append(
            "Token limit is very high and may cause performance issues or set your wallet on fire."
        )

    # Check file size limits
    if settings.max_file_size > 50_000_000:  # 50MB
        issues.append("Max file size is very large and may cause memory issues")

    if issues:
        console.print("[red]Configuration Issues Found:[/red]")
        for issue in issues:
            console.print(f"  ⚠️  {issue}")
        console.print()
    else:
        console.print("[green]✅ Configuration is valid[/green]\n")


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
