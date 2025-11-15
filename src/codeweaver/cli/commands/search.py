"""CodeWeaver CLI - Search Command."""

# sourcery skip: avoid-global-variables, no-complex-if-expressions
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
from __future__ import annotations

import logging
import sys

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, Literal

import cyclopts

from cyclopts import App
from rich import print as rich_print
from rich.table import Table

from codeweaver.agent_api.find_code.intent import IntentType
from codeweaver.agent_api.find_code.types import CodeMatch, FindCodeResponseSummary
from codeweaver.config.settings import get_settings_map
from codeweaver.exceptions import CodeWeaverError
from codeweaver.ui import CLIErrorHandler, StatusDisplay


if TYPE_CHECKING:
    from codeweaver.config.settings import CodeWeaverSettings
    from codeweaver.config.types import CodeWeaverSettingsDict
    from codeweaver.core.types.dictview import DictView


logger = logging.getLogger(__name__)
app = App(help="Search codebase from command line.")


async def _index_exists(settings: dict[str, Any] | CodeWeaverSettings) -> bool:
    """Check if an index exists for this project.

    Args:
        settings: Settings dictionary or CodeWeaverSettings object

    Returns:
        True if a valid index exists with indexed files
    """
    try:
        from codeweaver.common.utils.utils import get_user_config_dir
        from codeweaver.config.indexer import IndexerSettings
        from codeweaver.engine.indexer.manifest import FileManifestManager

        # Get project path
        if isinstance(settings, dict):
            project_path = settings.get("project_path")
        else:
            project_path = settings.project_path

        if not project_path:
            return False

        # Get manifest directory (same logic as indexer)
        if isinstance(settings, dict):
            indexer_config = settings.get("indexer", {})
            cache_dir = (
                indexer_config.get("cache_dir") if isinstance(indexer_config, dict) else None
            )
        else:
            cache_dir = (
                settings.indexer.cache_dir
                if isinstance(settings.indexer, IndexerSettings)
                else None
            )

        manifest_dir = (
            cache_dir / "manifests" if cache_dir else get_user_config_dir() / ".indexes/manifests"
        )

        # Check manifest
        manifest_manager = FileManifestManager(Path(project_path), manifest_dir)
        manifest = manifest_manager.load()

    except Exception as e:
        logger.debug("Error checking index existence: %s", e)
        return False
    else:
        # Index exists if manifest has files
        return manifest is not None and manifest.total_files > 0


async def _run_search_indexing(
    settings: CodeWeaverSettings | DictView[CodeWeaverSettingsDict],
) -> None:
    """Run indexing for search command (standalone, no server).

    Args:
        settings: Settings object containing configuration

    Raises:
        Exception: On indexing failure
    """
    from codeweaver.core.types.dictview import DictView
    from codeweaver.engine.indexer import Indexer

    display = StatusDisplay()
    display.print_warning("No index found. Indexing project...")

    try:
        # Convert to DictView if needed (same as index.py pattern)
        settings_view = (
            settings if isinstance(settings, DictView) else DictView(settings.model_dump())
        )

        # Create and run indexer
        indexer = await Indexer.from_settings_async(settings=settings_view)
        await indexer.prime_index(force_reindex=False)

        # Show quick summary
        stats = indexer.stats
        display.print_success(
            f"Indexing complete! ({stats.files_processed} files, {stats.chunks_indexed} chunks)"
        )

    except Exception as e:
        display.print_warning(f"Indexing failed: {e}")
        display.print_warning("Attempting search anyway...")
        # Don't exit - let search try anyway in case there's a partial index


@app.default
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
    from codeweaver.exceptions import ConfigurationError

    display = StatusDisplay()
    error_handler = CLIErrorHandler(display, verbose=False, debug=False)

    try:
        settings = get_settings_map()
        if project_path:
            from codeweaver.config.settings import update_settings

            settings = update_settings(project_path=project_path)  # type: ignore

        # Check if index exists, auto-index if needed
        if not await _index_exists(settings):
            from codeweaver.config.settings import get_settings

            settings_obj = get_settings()
            await _run_search_indexing(settings_obj)
            # Reload settings after indexing
            settings = get_settings_map()

        display.print_info(f"Searching in: {settings['project_path']}")
        display.print_info(f"Query: {query}")
        display.console.print()

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

        # Check for error status in response
        if response.status.lower() == "error":
            display.console.print()
            display.print_error(f"Configuration Error: {response.summary}")
            display.console.print()

            # Check if error is about missing embedding providers
            if "embedding providers" in response.summary.lower():
                display.console.print("[yellow]To fix this:[/yellow]")
                display.console.print(
                    "  [yellow]•[/yellow] Set VOYAGE_API_KEY environment variable for cloud embeddings"
                )
                display.console.print(
                    "  [yellow]•[/yellow] Or install local provider: pip install codeweaver-mcp[provider-fastembed]"
                )
                display.console.print("  [yellow]•[/yellow] Or configure fastembed in .codeweaver.toml")
                display.console.print(
                    "  [yellow]•[/yellow] See docs: https://github.com/knitli/codeweaver-mcp#configuration"
                )
            display.console.print()
            sys.exit(1)

        # Limit results for CLI display
        limited_matches = response.matches[:limit]

        # Output results in requested format
        if output_format == "json":
            rich_print(response.model_dump_json(indent=2))

        elif output_format == "table":
            _display_table_results(query, response, limited_matches, display)

        elif output_format == "markdown":
            _display_markdown_results(query, response, limited_matches, display)

    except ConfigurationError as e:
        error_handler.handle_error(e, "Search configuration", exit_code=1)
    except CodeWeaverError as e:
        error_handler.handle_error(e, "Search", exit_code=1)
    except Exception as e:
        error_handler.handle_error(e, "Search", exit_code=1)


def _display_table_results(
    query: str, response: FindCodeResponseSummary, matches: Sequence[CodeMatch], display: StatusDisplay
) -> None:
    """Display search results as a table using serialize_for_cli."""
    display.console.print()
    display.console.print(f"[bold green]Search Results for: '{query}'[/bold green]")

    # Use the built-in CLI summary from FindCodeResponseSummary
    summary_table = response.assemble_cli_summary()
    display.print_table(summary_table)

    # If there are matches, display them in a detailed table
    if matches:
        _display_match_details(matches, display)
    else:
        display.console.print("\n[yellow]No matches found[/yellow]")


def _display_match_details(matches: Sequence[CodeMatch], display: StatusDisplay) -> None:
    display.console.print("\n[bold blue]Match Details:[/bold blue]\n")

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

    display.print_table(table)


def _display_markdown_results(
    query: str, response: FindCodeResponseSummary, matches: Sequence[CodeMatch], display: StatusDisplay
) -> None:
    """Display search results as markdown using serialize_for_cli."""
    display.console.print(f"# Search Results for: '{query}'\n")
    display.console.print(
        f"Found {response.total_matches} matches in {response.execution_time_ms:.1f}ms\n"
    )

    if not matches:
        display.console.print("*No matches found*")
        return

    for i, match in enumerate(matches, 1):
        # Use serialize_for_cli to get structured data
        match_data = match.serialize_for_cli()

        file_path = match_data.get("file", {}).get("path", "unknown")
        language = match_data.get("file", {}).get("ext_kind", {}).get("language", "unknown")

        display.console.print(f"## {i}. {file_path}")
        display.console.print(
            f"**Language:** {language} | **Score:** {match.relevance_score:.2f} | {match.span!s}"
        )
        display.console.print(f"```{language}")
        display.console.print(str(match.content) if match.content else "")
        display.console.print("```\n")


def main() -> None:
    """Entry point for the search CLI command."""
    display = StatusDisplay()
    error_handler = CLIErrorHandler(display, verbose=True, debug=True)

    try:
        app()
    except Exception as e:
        error_handler.handle_error(e, "Search CLI", exit_code=1)


if __name__ == "__main__":
    main()

__all__ = ("app", "search")
