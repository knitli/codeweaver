# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""CodeWeaver CLI - Search Command."""

# sourcery skip: avoid-global-variables, no-complex-if-expressions
from __future__ import annotations

import logging
import sys

from collections.abc import Sequence
from pathlib import Path
from typing import Annotated, Literal

import cyclopts

from cyclopts import App
from pydantic import FilePath
from rich.table import Table

from codeweaver.cli.dependencies import setup_cli_di
from codeweaver.cli.ui import (
    CLIErrorHandler,
    StatusDisplay,
    get_display,
    handle_keyboard_interrupt_gracefully,
)
from codeweaver.core import CodeWeaverError
from codeweaver.core.config.loader import CodeWeaverSettingsType
from codeweaver.server.agent_api.search import (
    CodeMatch,
    FindCodeResponseSummary,
    IntentType,
    find_code,
)


_display: StatusDisplay = get_display()
logger = logging.getLogger(__name__)
app = App(help="Search your codebase from the command line.")


@app.default
async def search(
    query: str,
    *,
    intent: IntentType | None = None,
    limit: int = 10,
    project_path: Annotated[Path | None, cyclopts.Parameter(name=["--project", "-p"])] = None,
    config_file: Annotated[
        FilePath | None,
        cyclopts.Parameter(
            name=["--config-file", "-c"], help="Path to a specific config file to use"
        ),
    ] = None,
    output_format: Literal["json", "table", "markdown"] = "table",
    verbose: Annotated[
        bool,
        cyclopts.Parameter(name=["--verbose", "-v"], help="Enable verbose logging with timestamps"),
    ] = False,
    debug: Annotated[
        bool, cyclopts.Parameter(name=["--debug", "-d"], help="Enable debug logging")
    ] = False,
) -> None:
    """Search your codebase from the command line with plain language."""
    from codeweaver.core import ConfigurationError

    display = _display
    error_handler = CLIErrorHandler(display, verbose=verbose, debug=debug)

    try:
        # Setup DI Container
        container = setup_cli_di(config_file, project_path, verbose=verbose)

        # Resolve Settings
        settings = await container.resolve(CodeWeaverSettingsType)

        display.print_info(f"Searching in: {settings.project_path}")
        display.print_info(f"Query: {query}")
        display.print_info("")  # Empty line for spacing

        # Resolve Providers
        # We explicitly resolve this because find_code expects a dictionary-like object (ProviderDict),
        # but if we don't pass it, the default value is the INJECTED marker, which doesn't behave like a dict.

        response = await find_code(
            query=query,
            intent=intent,
            token_limit=settings.token_limit or 30000,
            focus_languages=None,
            context=None,
        )

        # Check for error status in response
        if response.status.lower() == "error":
            display.print_info("")  # Empty line for spacing
            display.print_error(f"Configuration Error: {response.summary}")
            display.print_info("")  # Empty line for spacing

            # Check if error is about missing embedding providers
            if "embedding providers" in response.summary.lower():
                display.print_warning("To fix this:")
                display.print_info(
                    "  • Set VOYAGE_API_KEY environment variable for cloud embeddings"
                )
                display.print_info(
                    "  • Or use a local embedding provider in your config, `fastembed` is in the default install."
                )
                display.print_info(
                    "  • You can use the `cw init` command to set up a config file. Use `cw init --config-only` to just create the config with the recommended profile, or for a quickstart, local-only, profile: `cw init --profile quickstart`."
                )
                display.print_info("")  # Empty line for spacing
            sys.exit(1)

        # Limit results for CLI display
        limited_matches = response.matches[:limit]

        # Output results in requested format
        if output_format == "json":
            # JSON output uses console.print for proper formatting
            display.console.print(response.model_dump_json(indent=2))

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
    query: str,
    response: FindCodeResponseSummary,
    matches: Sequence[CodeMatch],
    display: StatusDisplay,
) -> None:
    """Display search results as a table using serialize_for_cli."""
    display.print_info("")  # Empty line for spacing
    display.print_success(f"Search Results for: '{query}'")

    # Use the built-in CLI summary from FindCodeResponseSummary
    summary_table = response.assemble_cli_summary()
    display.print_table(summary_table)

    # If there are matches, display them in a detailed table
    if matches:
        _display_match_details(matches, display)
    else:
        display.print_warning("No matches found")


def _display_match_details(matches: Sequence[CodeMatch], display: StatusDisplay) -> None:
    display.print_info("")  # Empty line for spacing
    display.print_info("Match Details:")
    display.print_info("")  # Empty line for spacing

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
                str(match_data.get("file", {}).get("ext_category", {}).get("language", "unknown")),
                f"{match.relevance_score:.2f}",
                f"{match.span!s}",
                preview,
            )

    display.print_table(table)


def _display_markdown_results(
    query: str,
    response: FindCodeResponseSummary,
    matches: Sequence[CodeMatch],
    display: StatusDisplay,
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
        language = match_data.get("file", {}).get("ext_category", {}).get("language", "unknown")

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

    with handle_keyboard_interrupt_gracefully():
        try:
            app()
        except Exception as e:
            error_handler.handle_error(e, "Search CLI", exit_code=1)


if __name__ == "__main__":
    main()

__all__ = ()
