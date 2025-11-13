# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""CodeWeaver indexing command-line interface."""

from __future__ import annotations

import sys

from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import cyclopts
import httpx

from cyclopts import App
from pydantic import FilePath
from rich.console import Console

from codeweaver.common import CODEWEAVER_PREFIX
from codeweaver.common.utils.git import get_project_path
from codeweaver.common.utils.utils import get_user_config_dir
from codeweaver.core.types.dictview import DictView
from codeweaver.exceptions import CodeWeaverError


if TYPE_CHECKING:
    from codeweaver.config.settings import CodeWeaverSettings
    from codeweaver.config.types import CodeWeaverSettingsDict
    from codeweaver.engine.indexer.checkpoint import CheckpointManager


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


def _load_and_configure_settings(
    config_file: FilePath | None, project_path: Path | None
) -> tuple[CodeWeaverSettings, Path]:
    """Load settings and determine project path.

    Args:
        config_file: Optional path to configuration file
        project_path: Optional path to project root

    Returns:
        Tuple of (CodeWeaverSettings, resolved project path)
    """
    from codeweaver.config.settings import get_settings, update_settings

    settings = get_settings(config_file=config_file)

    if project_path:
        settings = update_settings(**{**settings.model_dump(), "project_path": project_path})

    resolved_path = (
        project_path or settings.project_path
        if isinstance(settings.project_path, Path)
        else get_project_path()
    )

    return settings, resolved_path


def _derive_collection_name(
    settings: CodeWeaverSettings, project_path: Path, checkpoint_mgr: CheckpointManager
) -> str:
    """Derive collection name from settings or checkpoint.

    Args:
        settings: Settings object containing configuration
        project_path: Path to project root
        checkpoint_mgr: Checkpoint manager instance

    Returns:
        Derived collection name string
    """
    from codeweaver.config.providers import ProviderSettings
    from codeweaver.core.stores import get_blake_hash

    # Default collection name
    collection_name = f"{
        settings.project_name if isinstance(settings.project_name, str) else project_path.name
    }-{get_blake_hash(str(project_path).encode('utf-8'))[:8]}"

    # Check checkpoint file
    if checkpoint_file := checkpoint_mgr.checkpoint_file:
        return checkpoint_file.stem.replace("checkpoint_", "")

    # Check provider settings
    if (
        (provider_settings := settings.provider)
        and isinstance(provider_settings, ProviderSettings)
        and (vector_settings := provider_settings.vector_store)
        and vector_settings is not None
        and (vector_provider_config := vector_settings.get("provider_settings"))
    ):
        collection_name = vector_provider_config.get(
            "collection_name",
            settings.project_name if isinstance(settings.project_name, str) else project_path.name,
        )

    return collection_name


async def _perform_clear_operation(
    settings: CodeWeaverSettings, project_path: Path, *, yes: bool
) -> None:
    """Clear vector store and checkpoints.

    Args:
        settings: Settings object containing configuration
        project_path: Path to project root
        yes: If True, skip confirmation prompt

    Raises:
        SystemExit: If user cancels operation or error occurs
    """
    from codeweaver.common.registry.provider import get_provider_registry
    from codeweaver.config.indexing import IndexerSettings
    from codeweaver.engine.indexer.checkpoint import CheckpointManager
    from codeweaver.engine.indexer.manifest import FileManifestManager

    if not yes:
        console.print(
            f"{CODEWEAVER_PREFIX} [yellow bold]⚠ Warning: Destructive Operation[/yellow bold]\n"
        )
        console.print("This will [red]permanently delete[/red]:")
        console.print("  • Vector store collection and all indexed data")
        console.print("  • All indexing checkpoints")
        console.print("  • File manifest state\n")

        response = console.input("[yellow]Are you sure you want to continue? (yes/no):[/yellow] ")
        if response.lower() not in ["yes", "y"]:
            console.print(f"{CODEWEAVER_PREFIX} [blue]Operation cancelled[/blue]")
            sys.exit(0)

    try:
        console.print(
            f"{CODEWEAVER_PREFIX} [yellow]Clearing vector store and checkpoints...[/yellow]"
        )

        # Setup paths and managers
        indexes_dir = (
            settings.indexing.cache_dir
            if isinstance(settings.indexing, IndexerSettings)
            else get_user_config_dir() / ".indexes"
        )

        checkpoint_mgr = CheckpointManager(
            project_path=project_path, checkpoint_dir=indexes_dir / "checkpoints"
        )
        manifest = FileManifestManager(
            project_path=project_path, manifest_dir=indexes_dir / "manifests"
        )

        # Derive collection name
        collection_name = _derive_collection_name(settings, project_path, checkpoint_mgr)

        # Clear vector store
        from codeweaver.config.providers import ProviderSettings

        registry = get_provider_registry()
        provider = registry.get_provider_enum_for("vector_store")

        # Extract provider settings from config
        provider_config: dict[str, object] = {}
        if (
            (provider_settings := settings.provider)
            and isinstance(provider_settings, ProviderSettings)
            and (vector_settings := provider_settings.vector_store)
            and vector_settings is not None
            and (vector_provider_config := vector_settings.get("provider_settings"))
        ):
            # Copy provider_settings (url, collection_name, etc.)
            provider_config = dict(vector_provider_config)
            # Add api_key from parent level if present
            if api_key := vector_settings.get("api_key"):
                provider_config["api_key"] = api_key

        store = registry.create_provider(provider, "vector_store", config=provider_config)  # type: ignore

        await store._initialize()
        await_result = await store.delete_collection(collection_name)

        if await_result:
            console.print(f"  ✓ [green]Vector store collection, {collection_name} deleted[/green]")
        else:
            console.print(
                f"  • [dim]Vector store collection, {collection_name} did not exist[/dim]"
            )

        # Clear checkpoints and manifests
        checkpoint_mgr.delete()
        console.print("  ✓ [green]Checkpoints cleared[/green]")
        manifest.delete()
        console.print("  ✓ [green]File manifest cleared[/green]")

        console.print(f"{CODEWEAVER_PREFIX} [green]Clear operation complete[/green]\n")

    except Exception as e:
        console.print(f"{CODEWEAVER_PREFIX} [red]Error during clear operation:[/red] {e}")
        console.print_exception(show_locals=True)
        sys.exit(1)


def _handle_server_status(*, standalone: bool) -> bool:
    """Check server status and inform user.

    Args:
        standalone: If True, skip server check

    Returns:
        True if should proceed with standalone indexing, False to exit
    """
    if standalone:
        return True

    if _check_server_health():
        return _check_and_print_server_status()
    _print_server_status(
        " [yellow]⚠ Server not running[/yellow]",
        "[blue]Info:[/blue] Running standalone indexing",
        "[dim]Tip: Start server with 'codeweaver server' for automatic indexing[/dim]\n",
    )
    return True


def _check_and_print_server_status():
    _print_server_status(
        " [bold green]✓ Server is running[/bold green]\n",
        "[yellow]Info:[/yellow] The CodeWeaver server automatically indexes your codebase",
        "  • Initial indexing runs on server startup",
    )
    console.print("  • File watcher monitors for changes in real-time")
    console.print("\n[cyan]To check indexing status:[/cyan]")
    console.print("  curl http://localhost:9328/health/ | jq '.indexing'")
    console.print("\n[dim]Tip: Use --standalone to run indexing without the server[/dim]")
    return False


def _print_server_status(running_msg: str, mode: str, info: str) -> None:
    console.print(f"{CODEWEAVER_PREFIX}{running_msg}")
    console.print(mode)
    console.print(info)


async def _run_standalone_indexing(
    settings: CodeWeaverSettings | DictView[CodeWeaverSettingsDict], *, force_reindex: bool
) -> None:
    """Run standalone indexing operation.

    Args:
        settings: Settings object containing configuration
        force_reindex: If True, force full reindex

    Raises:
        SystemExit: On completion or error
    """
    from codeweaver.engine.indexer import Indexer, IndexingProgressTracker

    console.print(f"{CODEWEAVER_PREFIX} [blue]Initializing indexer...[/blue]")
    indexer = await Indexer.from_settings_async(
        settings=settings if isinstance(settings, DictView) else DictView(settings.model_dump())
    )

    progress_tracker = IndexingProgressTracker(console=console)

    console.print(f"{CODEWEAVER_PREFIX} [green]Starting indexing process...[/green]")

    _ = await indexer.prime_index(
        force_reindex=force_reindex,
        progress_callback=lambda stats, phase: progress_tracker.update(stats, phase),
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
    # Handle --clear flag
    if clear:
        console.print(f"{CODEWEAVER_PREFIX} [blue]Loading configuration...[/blue]")
        settings, resolved_path = _load_and_configure_settings(config_file, project_path)
        await _perform_clear_operation(settings, resolved_path, yes=yes)
        force_reindex = True  # Continue to reindex after clearing

    # Check server status and decide whether to proceed
    if not _handle_server_status(standalone=standalone):
        return  # Server is running, exit early

    # Standalone indexing
    try:
        console.print(f"{CODEWEAVER_PREFIX} [blue]Loading configuration...[/blue]")
        settings, _ = _load_and_configure_settings(config_file, project_path)
        await _run_standalone_indexing(settings, force_reindex=force_reindex)

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
