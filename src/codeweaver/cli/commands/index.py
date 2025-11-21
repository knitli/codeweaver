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

from cyclopts import App
from pydantic import FilePath

from codeweaver.cli.ui import CLIErrorHandler, IndexingProgress, StatusDisplay, get_display
from codeweaver.common.utils.git import get_project_path
from codeweaver.common.utils.utils import get_user_config_dir
from codeweaver.config.types import CodeWeaverSettingsDict
from codeweaver.core.types.dictview import DictView
from codeweaver.exceptions import CodeWeaverError


if TYPE_CHECKING:
    from codeweaver.config.settings import CodeWeaverSettings
    from codeweaver.config.types import CodeWeaverSettingsDict
    from codeweaver.engine.indexer.checkpoint import CheckpointManager

_display: StatusDisplay = get_display()

app = App("index", help="Index codebase for semantic search.", console=_display.console)


async def _check_server_health() -> bool:
    """Check if CodeWeaver server is running.

    Returns:
        True if server is running and healthy
    """
    import httpx

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{_get_url()}/health", timeout=2.0)
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
        settings = update_settings(
            **CodeWeaverSettingsDict(**(settings.model_dump() | {"project_path": project_path}))  # type: ignore
        )

    new_settings = get_settings()

    resolved_path = (
        project_path or new_settings.project_path
        if isinstance(new_settings.project_path, Path)
        else get_project_path()
    )

    return new_settings, resolved_path


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
    from codeweaver.common.utils.utils import generate_collection_name
    from codeweaver.config.providers import ProviderSettings

    # Default collection name
    collection_name = generate_collection_name()

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
        collection_name = vector_provider_config.get("collection_name", collection_name)

    return collection_name


async def _perform_clear_operation(
    settings: CodeWeaverSettings, project_path: Path, *, yes: bool, display: StatusDisplay
) -> None:
    """Clear vector store and checkpoints.

    Args:
        settings: Settings object containing configuration
        project_path: Path to project root
        yes: If True, skip confirmation prompt
        display: StatusDisplay for output

    Raises:
        CodeWeaverError: If operation fails
    """
    from codeweaver.common.registry.provider import get_provider_registry
    from codeweaver.config.indexer import IndexerSettings
    from codeweaver.engine.indexer.checkpoint import CheckpointManager
    from codeweaver.engine.indexer.manifest import FileManifestManager

    if not yes:
        display.print_warning("⚠ Warning: Destructive Operation")
        display.console.print()
        display.console.print("This will [red]permanently delete[/red]:")
        display.console.print("  • Vector store collection and all indexed data")
        display.console.print("  • All indexing checkpoints")
        display.console.print("  • File manifest state")
        display.console.print()

        response = display.console.input(
            "[yellow]Are you sure you want to continue? (yes/no):[/yellow] "
        )
        if response.lower() not in ["yes", "y"]:
            display.print_info("Operation cancelled")
            sys.exit(0)

    display.print_info("Clearing vector store and checkpoints...")

    # Setup paths and managers
    indexes_dir = (
        settings.indexer.cache_dir
        if isinstance(settings.indexer, IndexerSettings)
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
    from codeweaver.core.types import Unset

    registry = get_provider_registry()
    provider = registry.get_provider_enum_for("vector_store")

    # Extract provider settings from config
    provider_config: dict[str, object] = {}
    if (
        (provider_settings := settings.provider)
        and isinstance(provider_settings, ProviderSettings)
        and (
            vector_settings := provider_settings.vector_store[0]
            if isinstance(provider_settings.vector_store, tuple)
            else provider_settings.vector_store
        )
        and vector_settings is not Unset
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
        display.print_success(f"Vector store collection '{collection_name}' deleted")
    else:
        display.print_info(f"Vector store collection '{collection_name}' did not exist")

    # Clear checkpoints and manifests
    checkpoint_mgr.delete()
    display.print_success("Checkpoints cleared")
    manifest.delete()
    display.print_success("File manifest cleared")

    display.print_success("Clear operation complete")
    display.console.print()


async def _handle_server_status(*, standalone: bool, display: StatusDisplay) -> bool:
    """Check server status and inform user.

    Args:
        standalone: If True, skip server check
        display: StatusDisplay for output

    Returns:
        True if should proceed with standalone indexing, False to exit
    """
    if standalone:
        return True

    if await _check_server_health():
        return _check_and_print_server_status(display)
    display.print_warning("Server not running")
    display.print_info("Running standalone indexing")
    display.console.print("[dim]Tip: Start server with 'cw server' for automatic indexing[/dim]")
    display.console.print()
    return True


def _get_url():
    from codeweaver.config.settings import get_settings_map

    settings_map = get_settings_map()
    host = settings_map.get("server.host", "localhost")
    port = settings_map.get("server.port", 9328)
    return f"http://{host}:{port}"


def _check_and_print_server_status(display: StatusDisplay):
    display.console.print()
    display.print_success(
        "Good news: Server is running. Your **codebase is indexed automatically**!"
    )
    display.console.print()
    display.print_info("The CodeWeaver server automatically indexes your codebase")
    display.console.print(
        "  • Initial indexing runs on server startup if the index is missing or incomplete."
    )
    display.console.print(
        "  • CodeWeaver indexes most codebases in under a minute (meaning discovering, parsing, and chunking files), but the biggest factor is your choice of embedding provider. If you're generating embeddings locally, go get lunch if you want to wait until it's done. 🍔"
    )
    display.console.print(
        "  • While CodeWeaver runs, it continuously monitors your codebase for changes and updates the index in real-time. It also picks up changes when the server restarts."
    )
    display.console.print()
    display.console.print("[cyan]To check indexing status:[/cyan]")
    display.console.print()
    display.console.print("   run: 'cw status'")
    display.console.print(f"  curl {_get_url()}/health | jq '.indexer'")
    display.console.print()
    display.console.print(
        "[dim]Tip: Use --standalone to run indexing without running the server.[/dim]"
    )
    return False


async def _run_standalone_indexing(
    settings: CodeWeaverSettings | DictView[CodeWeaverSettingsDict],
    *,
    force_reindex: bool,
    display: StatusDisplay,
) -> None:
    """Run standalone indexing operation.

    Args:
        settings: Settings object containing configuration
        force_reindex: If True, force full reindex
        display: StatusDisplay for output

    Raises:
        CodeWeaverError: If indexing fails
    """
    from typing import Any

    from codeweaver.engine.indexer import Indexer

    display.print_info("Initializing indexer...")
    indexer = await Indexer.from_settings_async(
        settings=settings if isinstance(settings, DictView) else DictView(settings.model_dump())
    )

    # Create progress tracker with the new unified interface
    progress_tracker = IndexingProgress(console=display.console)

    # Create callback that maps to the new IndexingProgress methods
    def progress_callback(
        phase: str,
        current: int,
        total: int,
        *,
        extra: dict[str, Any] | None = None,
    ) -> None:
        if phase == "discovery":
            progress_tracker.update_discovery(current, total)
        elif phase == "chunking":
            chunks_created = extra.get("chunks_created", 0) if extra else 0
            progress_tracker.update_chunking(current, total, chunks_created)
        elif phase == "embedding":
            progress_tracker.update_embedding(current, total)
        elif phase == "indexing":
            progress_tracker.update_indexing(current, total)

    display.print_success("Starting indexing process...")

    with progress_tracker:
        _ = await indexer.prime_index(
            force_reindex=force_reindex,
            progress_callback=progress_callback,
        )
        progress_tracker.complete()

    # Display final summary
    stats = indexer.stats
    display.console.print()
    display.print_success("Indexing Complete!")
    display.console.print()
    display.console.print(f"  Files processed: [cyan]{stats.files_processed}[/cyan]")
    display.console.print(f"  Chunks created: [cyan]{stats.chunks_created}[/cyan]")
    display.console.print(f"  Chunks indexed: [cyan]{stats.chunks_indexed}[/cyan]")
    display.console.print(
        f"  Processing rate: [cyan]{stats.processing_rate():.2f}[/cyan] files/sec"
    )
    display.console.print(f"  Time elapsed: [cyan]{stats.elapsed_time():.2f}[/cyan] seconds")

    if stats.total_errors > 0:
        display.console.print(f"  [yellow]Files with errors: {stats.total_errors}[/yellow]")

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
        cw index                  # Check server status
        cw index --force          # Force full re-index in standalone mode
        cw index --standalone     # Standalone indexing
        cw index --clear          # Clear vector store and re-index (with confirmation)
        cw index --clear --yes    # Clear and re-index without confirmation

    Args:
        config_file: Optional path to CodeWeaver configuration file
        project_path: Optional path to project root directory
        force_reindex: If True, skip persistence checks and reindex everything
        standalone: If True, run indexing without checking for server
        clear: If True, clear vector store and checkpoints before indexing
        yes: If True, skip confirmation prompts
    """
    display = _display or get_display()
    error_handler = CLIErrorHandler(display, verbose=False, debug=False)

    try:
        # Handle --clear flag
        if clear:
            display.print_info("Loading configuration...")
            settings, resolved_path = _load_and_configure_settings(config_file, project_path)
            await _perform_clear_operation(settings, resolved_path, yes=yes, display=display)
            force_reindex = True  # Continue to reindex after clearing

        # Check server status and decide whether to proceed
        if not await _handle_server_status(standalone=standalone, display=display):
            return  # Server is running, exit early

        # Standalone indexing
        display.print_info("Loading configuration...")
        settings, _ = _load_and_configure_settings(config_file, project_path)
        await _run_standalone_indexing(settings, force_reindex=force_reindex, display=display)

    except CodeWeaverError as e:
        error_handler.handle_error(e, "Indexing", exit_code=1)

    except KeyboardInterrupt:
        display.console.print()
        display.print_warning("Indexing cancelled by user")
        sys.exit(130)

    except Exception as e:
        error_handler.handle_error(e, "Indexing", exit_code=1)


def main() -> None:
    """Entry point for the CodeWeaver index CLI."""
    display = StatusDisplay()
    error_handler = CLIErrorHandler(display, verbose=True, debug=True)

    try:
        app()
    except Exception as e:
        error_handler.handle_error(e, "Index Command", exit_code=1)


if __name__ == "__main__":
    main()

__all__ = ("app", "index")
