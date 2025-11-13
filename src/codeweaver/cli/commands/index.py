# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""CodeWeaver indexing command-line interface."""

from __future__ import annotations

import asyncio
import sys

from pathlib import Path
from typing import Annotated

import cyclopts
import httpx

from cyclopts import App
from pydantic import FilePath
from rich.console import Console

from codeweaver.common import CODEWEAVER_PREFIX
from codeweaver.exceptions import CodeWeaverError


console = Console(markup=True, emoji=True)
app = App("index", help="Index codebase for semantic search.", console=console)


def _check_server_health() -> bool:
    """Check if CodeWeaver server is running.

    Returns:
        True if server is running and healthy
    """
    try:
        response = httpx.get("http://localhost:9328/health/", timeout=2.0)
    except (httpx.ConnectError, httpx.TimeoutException):
        return False
    else:
        return response.status_code == 200


def _trigger_server_reindex(*, force: bool) -> bool:
    """Trigger re-index on running server.

    Args:
        force: If True, force full re-index

    Returns:
        True if re-index was successfully triggered
    """
    # For v0.1, we don't have an admin endpoint yet
    # The server auto-indexes on startup, so just inform user
    # TODO: Add admin endpoint in future for manual re-index trigger
    return False


@app.default
async def index(
    *,
    config_file: Annotated[FilePath | None, cyclopts.Parameter(name=["--config", "-c"])] = None,
    project_path: Annotated[Path | None, cyclopts.Parameter(name=["--project", "-p"])] = None,
    force_reindex: Annotated[
        bool, cyclopts.Parameter(name=["--force", "-f"], help="Force full reindex")
    ] = False,
    standalone: Annotated[
        bool, cyclopts.Parameter(name=["--standalone", "-s"], help="Run indexing without server")
    ] = False,
    clear: Annotated[
        bool,
        cyclopts.Parameter(
            name=["--clear"],
            help="Clear vector store and checkpoints before indexing (requires confirmation)",
        ),
    ] = False,
    yes: Annotated[
        bool,
        cyclopts.Parameter(
            name=["--yes", "-y"], help="Skip confirmation prompts (use with --clear)"
        ),
    ] = False,
) -> None:
    """Index or re-index a codebase.

    By default, checks if server is running and informs user about auto-indexing.
    Use --standalone to run indexing without server.

    Examples:
        codeweaver index                  # Check server status
        codeweaver index --force          # Force full re-index in standalone mode
        codeweaver index --standalone     # Standalone indexing
        codeweaver index --clear          # Clear vector store and re-index (with confirmation)
        codeweaver index --clear --yes    # Clear and re-index without confirmation

    Args:
        config_file: Optional path to CodeWeaver configuration file
        project_path: Optional path to project root directory
        force_reindex: If True, skip persistence checks and reindex everything
        standalone: If True, run indexing without checking for server
        clear: If True, clear vector store and checkpoints before indexing
        yes: If True, skip confirmation prompts
    """
    from codeweaver.config.settings import get_settings
    from codeweaver.engine.indexer import Indexer, IndexingProgressTracker

    # Handle --clear flag
    if clear:
        if not yes:
            console.print(
                f"{CODEWEAVER_PREFIX} [yellow bold]⚠ Warning: Destructive Operation[/yellow bold]\n"
            )
            console.print("This will [red]permanently delete[/red]:")
            console.print("  • Vector store collection and all indexed data")
            console.print("  • All indexing checkpoints")
            console.print("  • File manifest state\n")

            response = console.input(
                "[yellow]Are you sure you want to continue? (yes/no):[/yellow] "
            )
            if response.lower() not in ["yes", "y"]:
                console.print(f"{CODEWEAVER_PREFIX} [blue]Operation cancelled[/blue]")
                sys.exit(0)

        # Perform the clear operation
        try:
            console.print(f"{CODEWEAVER_PREFIX} [blue]Loading configuration...[/blue]")
            settings = get_settings(config_file=config_file)

            if project_path:
                from codeweaver.config.settings import update_settings

                settings = update_settings(**{
                    **settings.model_dump(),
                    "project_path": project_path,
                })

            console.print(
                f"{CODEWEAVER_PREFIX} [yellow]Clearing vector store and checkpoints...[/yellow]"
            )

            # Clear vector store
            from codeweaver.common.registry.provider import get_provider_registry
            from codeweaver.config.providers import ProviderSettings, VectorStoreProviderSettings

            registry = get_provider_registry()
            store = registry.create_provider("vector_store")  # type: ignore
            if (
                (provider_settings := settings.provider)
                and isinstance(provider_settings, ProviderSettings)
                and (vector_settings := provider_settings.vector_store)
                and isinstance(vector_settings, VectorStoreProviderSettings)
            ):
                collection_name = vector_settings.get("provider_settings", {}).get(
                    "collection_name", "codeweaver_vectors"
                )
            await_result = await store.delete_collection(collection_name)

            if await_result:
                console.print("  ✓ [green]Vector store collection deleted[/green]")
            else:
                console.print("  • [dim]Vector store collection did not exist[/dim]")

            # Clear checkpoints and manifest
            from codeweaver.engine.indexer.checkpoint import CheckpointManager
            from codeweaver.engine.indexer.manifest import FileManifestManager

            checkpoint_mgr = CheckpointManager(
                project_path=settings.project_path, checkpoint_dir=settings.indexing.cache_dir
            )
            checkpoint_mgr.delete()
            console.print("  ✓ [green]Checkpoints cleared[/green]")

            manifest = FileManifestManager(
                project_path=settings.project_path, manifest_dir=settings.indexing.cache_dir
            )
            manifest.delete()
            console.print("  ✓ [green]File manifest cleared[/green]")

            console.print(f"{CODEWEAVER_PREFIX} [green]Clear operation complete[/green]\n")

            # Continue to reindex after clearing
            force_reindex = True

        except Exception as e:
            console.print(f"{CODEWEAVER_PREFIX} [red]Error during clear operation:[/red] {e}")
            console.print_exception(show_locals=True)
            sys.exit(1)

    # Check if server is running (unless --standalone)
    if not standalone:
        if _check_server_health():
            console.print(f"{CODEWEAVER_PREFIX} [bold green]✓ Server is running[/bold green]\n")
            console.print(
                "[yellow]Info:[/yellow] The CodeWeaver server automatically indexes your codebase"
            )
            console.print("  • Initial indexing runs on server startup")
            console.print("  • File watcher monitors for changes in real-time")
            console.print("\n[cyan]To check indexing status:[/cyan]")
            console.print("  curl http://localhost:9328/health/ | jq '.indexing'")
            console.print("\n[dim]Tip: Use --standalone to run indexing without the server[/dim]")
            return
        console.print(f"{CODEWEAVER_PREFIX} [yellow]⚠ Server not running[/yellow]")
        console.print("[blue]Info:[/blue] Running standalone indexing")
        console.print(
            "[dim]Tip: Start server with 'codeweaver server' for automatic indexing[/dim]\n"
        )

    # Standalone indexing (current implementation)
    try:
        # Load settings
        console.print(f"{CODEWEAVER_PREFIX} [blue]Loading configuration...[/blue]")
        settings = get_settings(config_file=config_file)

        # Override project path if provided
        if project_path:
            from codeweaver.config.settings import update_settings

            settings = update_settings(**{**settings.model_dump(), "project_path": project_path})  # type: ignore

        # Create indexer with progress tracking
        console.print(f"{CODEWEAVER_PREFIX} [blue]Initializing indexer...[/blue]")
        indexer = Indexer.from_settings(settings=None)

        # Create progress tracker
        progress_tracker = IndexingProgressTracker(console=console)

        # Perform indexing with progress indicators
        console.print(f"{CODEWEAVER_PREFIX} [green]Starting indexing process...[/green]")

        _ = asyncio.run(
            indexer.prime_index(
                force_reindex=force_reindex,
                progress_callback=lambda stats, phase: progress_tracker.update(stats, phase),
            )
        )

        # Display final summary
        stats = indexer.stats
        console.print()
        console.print(f"{CODEWEAVER_PREFIX} [green bold]Indexing Complete![/green bold]")
        console.print()
        console.print(f"  Files processed: [cyan]{stats.files_processed}[/cyan]")
        console.print(f"  Chunks created: [cyan]{stats.chunks_created}[/cyan]")
        console.print(f"  Chunks indexed: [cyan]{stats.chunks_indexed}[/cyan]")
        console.print(f"  Processing rate: [cyan]{stats.processing_rate():.2f}[/cyan] files/sec")
        console.print(f"  Time elapsed: [cyan]{stats.elapsed_time():.2f}[/cyan] seconds")

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
