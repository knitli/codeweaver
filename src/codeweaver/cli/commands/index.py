# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""CodeWeaver indexing command-line interface."""

import sys

from pathlib import Path
from typing import Annotated

import cyclopts

from cyclopts import App
from pydantic import FilePath
from rich.console import Console

from codeweaver.common import CODEWEAVER_PREFIX
from codeweaver.exceptions import CodeWeaverError


console = Console(markup=True, emoji=True)
app = App(
    "index", default_command="index", help="Index codebase for semantic search.", console=console
)


@app.command
def index(
    *,
    config_file: Annotated[FilePath | None, cyclopts.Parameter(name=["--config", "-c"])] = None,
    project_path: Annotated[Path | None, cyclopts.Parameter(name=["--project", "-p"])] = None,
    force_reindex: Annotated[
        bool, cyclopts.Parameter(name=["--force", "-f"], help="Force full reindex")
    ] = False,
) -> None:
    """Index codebase for semantic search with progress indicators.

    Args:
        config_file: Optional path to CodeWeaver configuration file
        project_path: Optional path to project root directory
        force_reindex: If True, skip persistence checks and reindex everything
    """
    from codeweaver.config.settings import get_settings
    from codeweaver.engine.indexer import Indexer
    from codeweaver.engine.progress import IndexingProgressTracker

    try:
        # Load settings
        console.print(f"{CODEWEAVER_PREFIX} [blue]Loading configuration...[/blue]")
        settings = get_settings(config_file=config_file)

        # Override project path if provided
        if project_path:
            from codeweaver.config.settings import update_settings

            settings = update_settings(**{**settings.model_dump(), "project_path": project_path})

        # Create indexer with progress tracking
        console.print(f"{CODEWEAVER_PREFIX} [blue]Initializing indexer...[/blue]")
        indexer = Indexer.from_settings(settings=None)

        # Create progress tracker
        progress_tracker = IndexingProgressTracker(console=console)

        # Perform indexing with progress indicators
        console.print(f"{CODEWEAVER_PREFIX} [green]Starting indexing process...[/green]")

        indexer.prime_index(
            force_reindex=force_reindex, progress_callback=progress_tracker.update
        )

        # Display final summary
        stats = indexer.stats
        console.print()
        console.print(f"{CODEWEAVER_PREFIX} [green bold]Indexing Complete![/green bold]")
        console.print()
        console.print(f"  Files processed: [cyan]{stats.files_processed}[/cyan]")
        console.print(f"  Chunks created: [cyan]{stats.chunks_created}[/cyan]")
        console.print(f"  Chunks indexed: [cyan]{stats.chunks_indexed}[/cyan]")
        console.print(f"  Processing rate: [cyan]{stats.processing_rate:.2f}[/cyan] files/sec")
        console.print(f"  Time elapsed: [cyan]{stats.elapsed_time:.2f}[/cyan] seconds")

        if stats.total_errors > 0:
            console.print(f"  [yellow]Files with errors: {stats.total_errors}[/yellow]")

        sys.exit(0)

    except CodeWeaverError as e:
        console.print_exception(show_locals=True)
        if e.suggestions:
            console.print(f"{CODEWEAVER_PREFIX} [yellow]Suggestions:[/yellow]")
            for suggestion in e.suggestions:
                console.print(f"  • {suggestion}")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print(f"\n{CODEWEAVER_PREFIX} [yellow]Indexing cancelled by user[/yellow]")
        sys.exit(130)
    except Exception:
        console.print_exception(show_locals=True, word_wrap=True)
        sys.exit(1)


def main() -> None:
    """Entry point for the CodeWeaver index CLI."""
    try:
        app()
    except Exception:
        console.print_exception(show_locals=True)
        sys.exit(1)


if __name__ == "__main__":
    main()

__all__ = ("app", "index")
