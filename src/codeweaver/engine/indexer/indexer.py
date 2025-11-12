# sourcery skip: no-complex-if-expressions
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""The indexer service for managing and querying indexed data.

The indexer orchestrates file discovery, chunking, embedding generation, and storage
in vector databases. It supports checkpointing for resuming interrupted indexing
operations, and integrates with CodeWeaver's provider registry for embedding and
vector store services.

It is the backend service that powers CodeWeaver's code search and retrieval capabilities.
"""
# TODO: register with providers registry

from __future__ import annotations

import asyncio
import contextlib
import dataclasses
import logging
import signal
import time

from collections.abc import Callable
from pathlib import Path
from time import sleep
from typing import TYPE_CHECKING, Annotated, Any, ClassVar, TypedDict, cast

import rignore

from pydantic import DirectoryPath, Field, NonNegativeFloat, NonNegativeInt, PrivateAttr
from pydantic.dataclasses import dataclass
from watchfiles.main import Change

from codeweaver.common.logging import log_to_client_or_fallback
from codeweaver.common.utils.git import set_relative_path
from codeweaver.config.chunker import ChunkerSettings
from codeweaver.core.discovery import DiscoveredFile
from codeweaver.core.language import ConfigLanguage, SemanticSearchLanguage
from codeweaver.core.stores import BlakeStore, get_blake_hash, make_blake_store
from codeweaver.core.types.dictview import DictView
from codeweaver.core.types.models import BasedModel
from codeweaver.core.types.sentinel import Unset
from codeweaver.engine.chunking_service import ChunkingService
from codeweaver.engine.indexer.checkpoint import CheckpointManager, IndexingCheckpoint
from codeweaver.engine.indexer.manifest import FileManifestManager, IndexFileManifest
from codeweaver.engine.watcher.types import FileChange


logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from typing import Any

    from codeweaver.config.providers import (
        EmbeddingProviderSettings,
        SparseEmbeddingProviderSettings,
        VectorStoreProviderSettings,
    )
    from codeweaver.config.types import CodeWeaverSettingsDict
    from codeweaver.core.chunks import CodeChunk
    from codeweaver.providers.embedding.providers.base import EmbeddingProvider


class UserProviderSelectionDict(TypedDict):
    """User-selected provider configuration dictionary."""

    embedding: DictView[EmbeddingProviderSettings[Any]] | None
    sparse_embedding: DictView[SparseEmbeddingProviderSettings[Any]] | None
    vector_store: DictView[VectorStoreProviderSettings] | None


_user_config: None | UserProviderSelectionDict = None


def _get_user_provider_config() -> UserProviderSelectionDict:
    from codeweaver.common.registry.provider import get_provider_config_for
    from codeweaver.providers.provider import ProviderKind

    global _user_config
    if _user_config is None:
        _user_config = UserProviderSelectionDict(
            embedding=get_provider_config_for(ProviderKind.EMBEDDING),
            sparse_embedding=get_provider_config_for(ProviderKind.SPARSE_EMBEDDING),
            vector_store=get_provider_config_for(ProviderKind.VECTOR_STORE),
        )
    return _user_config


def _get_embedding_instance(*, sparse: bool = False) -> EmbeddingProvider[Any] | None:
    """Get embedding provider instance using new registry API."""
    from codeweaver.common.registry import get_provider_registry

    kind = "sparse_embedding" if sparse else "embedding"
    registry = get_provider_registry()

    if provider_enum := registry.get_provider_enum_for(kind):
        return registry.get_provider_instance(provider_enum, kind, singleton=True)
    return None


def _get_vector_store_instance() -> Any | None:
    """Get vector store provider instance using new registry API."""
    from codeweaver.common.registry import get_provider_registry

    registry = get_provider_registry()
    if provider_enum := registry.get_provider_enum_for("vector_store"):
        return registry.get_provider_instance(provider_enum, "vector_store", singleton=True)
    return None


def _get_chunking_service() -> ChunkingService:
    """Stub function to get chunking service instance."""
    # TODO: This should probably come from the services registry but that's not fully implemented yet
    from codeweaver.config.settings import get_settings
    from codeweaver.engine.chunker import ChunkGovernor
    from codeweaver.engine.chunking_service import ChunkingService

    chunk_settings = get_settings().chunker
    governor = ChunkGovernor.from_settings(
        ChunkerSettings() if isinstance(chunk_settings, Unset) else chunk_settings
    )
    return ChunkingService(governor=governor)


@dataclass
class IndexingStats:
    """Statistics tracking for indexing progress."""

    files_discovered: int = 0
    files_processed: int = 0
    chunks_created: int = 0
    chunks_embedded: int = 0
    chunks_indexed: int = 0
    start_time: float = dataclasses.field(default_factory=time.time)
    files_with_errors: ClassVar[
        Annotated[
            list[Path],
            Field(description="""List of file paths that encountered errors during indexing."""),
        ]
    ] = []

    def elapsed_time(self) -> float:
        """Calculate elapsed time since indexing started."""
        return time.time() - self.start_time

    def processing_rate(self) -> float:
        """Files processed per second."""
        if self.elapsed_time() == 0:
            return 0.0
        return self.files_processed / self.elapsed_time()

    @property
    def total_errors(self) -> int:
        """Total number of files with errors."""
        return len(self.files_with_errors)

    @property
    def total_files_discovered(self) -> int:
        """Total files discovered (alias for files_discovered)."""
        return self.files_discovered


class Indexer(BasedModel):
    """Main indexer class. Wraps a DiscoveredFilestore and chunkers."""

    _store: Annotated[BlakeStore[DiscoveredFile] | None, PrivateAttr()] = None
    _walker: Annotated[rignore.Walker | None, PrivateAttr()] = None
    _project_root: Annotated[DirectoryPath | None, PrivateAttr()] = None
    _checkpoint_manager: Annotated[CheckpointManager | None, PrivateAttr()] = None
    _checkpoint: Annotated[IndexingCheckpoint | None, PrivateAttr()] = None
    _manifest_manager: Annotated[FileManifestManager | None, PrivateAttr()] = None
    _file_manifest: Annotated[IndexFileManifest | None, PrivateAttr()] = None
    _manifest_lock: Annotated[asyncio.Lock | None, PrivateAttr()] = None
    _deleted_files: Annotated[list[Path], PrivateAttr()] = PrivateAttr(default_factory=list)
    _last_checkpoint_time: Annotated[NonNegativeFloat, PrivateAttr()] = 0.0
    _files_since_checkpoint: Annotated[NonNegativeInt, PrivateAttr()] = 0

    def __init__(
        self,
        walker: rignore.Walker | None = None,
        store: BlakeStore[DiscoveredFile] | None = None,
        chunking_service: Any | None = None,  # ChunkingService type
        *,
        auto_initialize_providers: bool = True,
        project_path: Path | None = None,
        project_root: Path | None = None,
    ) -> None:
        """Initialize the Indexer with optional pipeline components.

        Args:
            walker: rignore walker for file discovery
            store: Store for discovered file metadata
            chunking_service: Service for chunking files (optional)
            auto_initialize_providers: Auto-initialize providers from global registry
            project_path: Project path for checkpoint management (preferred)
            project_root: Alias for project_path (deprecated, use project_path)
        """
        from codeweaver.common.utils.git import get_project_path

        # Support both project_path and project_root for backward compatibility
        if project_root is not None and project_path is None:
            project_path = project_root

        # Auto-create walker if project_path is provided but walker is not
        if walker is None and project_path is not None:
            walker = rignore.Walker(project_path)
            logger.debug("Auto-created walker for project_path: %s", project_path)
        from codeweaver.core.discovery import DiscoveredFile

        self._store = store or make_blake_store(value_type=DiscoveredFile)
        self._walker = walker
        self._project_root = project_path
        self._chunking_service = chunking_service or _get_chunking_service()
        self._stats = IndexingStats()

        # Pipeline provider Fields (initialized lazily on first use)
        self._embedding_provider: Any | None = None
        self._sparse_provider: Any | None = None
        self._vector_store: Any | None = None
        self._providers_initialized: bool = False

        # Initialize checkpoint manager
        if project_path and not isinstance(project_path, Unset):
            self._checkpoint_manager = CheckpointManager(project_path=project_path)
        else:
            from codeweaver.config.settings import get_settings

            self._checkpoint_manager = CheckpointManager(
                project_path=cast(
                    Path,
                    get_project_path()
                    if isinstance(get_settings().project_path, Unset)
                    else get_settings().project_path,
                )
            )

        self._checkpoint = None
        self._last_checkpoint_time = time.time()
        self._files_since_checkpoint = 0
        self._shutdown_requested = False
        self._original_sigterm_handler = None
        self._original_sigint_handler = None

        # Initialize file manifest manager
        if project_path and not isinstance(project_path, Unset):
            self._manifest_manager = FileManifestManager(project_path=project_path)
        else:
            from codeweaver.config.settings import get_settings

            self._manifest_manager = FileManifestManager(
                project_path=cast(
                    Path,
                    get_project_path()
                    if isinstance(get_settings().project_path, Unset)
                    else get_settings().project_path,
                )
            )
        self._file_manifest = None
        self._manifest_lock = None  # Initialize as None, created lazily in async context

        # Note: Provider initialization is now deferred to first async operation
        # auto_initialize_providers parameter is deprecated but kept for compatibility
        if auto_initialize_providers:
            logger.debug(
                "auto_initialize_providers=True: providers will be initialized on first async operation"
            )

        # Register signal handlers for graceful shutdown
        self._register_signal_handlers()

        logger.info("Indexer initialized")
        logger.info("Using project path: %s", self._checkpoint_manager.project_path)
        logger.debug("Providers will be initialized lazily on first use")

    def _register_signal_handlers(self) -> None:
        """Register signal handlers for graceful shutdown with checkpoint saving."""

        def handle_shutdown_signal(signum: int, frame: Any) -> None:
            """Handle shutdown signal by saving checkpoint and exiting gracefully."""
            signal_name = signal.Signals(signum).name
            logger.info("Received %s signal, saving checkpoint and shutting down...", signal_name)
            self._shutdown_requested = True

            # Save final checkpoint
            try:
                self.save_checkpoint()
                logger.info("Checkpoint saved successfully before shutdown")
            except Exception:
                logger.exception("Failed to save checkpoint during shutdown")

            # Call original handler if it existed
            if signum == signal.SIGTERM and self._original_sigterm_handler:
                if callable(self._original_sigterm_handler):
                    self._original_sigterm_handler(signum, frame)
            elif (
                signum == signal.SIGINT
                and self._original_sigint_handler
                and callable(self._original_sigint_handler)
            ):
                self._original_sigint_handler(signum, frame)

        # Store original handlers and install new ones
        try:
            self._original_sigterm_handler = signal.signal(signal.SIGTERM, handle_shutdown_signal)
            self._original_sigint_handler = signal.signal(signal.SIGINT, handle_shutdown_signal)
            logger.debug("Signal handlers registered for graceful shutdown")
        except (ValueError, OSError) as e:
            # Signal handling may not be available in all contexts (e.g., threads)
            logger.debug("Could not register signal handlers: %s", e)

    def _cleanup_signal_handlers(self) -> None:
        """Restore original signal handlers."""
        try:
            if self._original_sigterm_handler is not None:
                _ = signal.signal(signal.SIGTERM, self._original_sigterm_handler)
            if self._original_sigint_handler is not None:
                _ = signal.signal(signal.SIGINT, self._original_sigint_handler)
            logger.debug("Signal handlers restored")
        except (ValueError, OSError) as e:
            logger.debug("Could not restore signal handlers: %s", e)

    async def _initialize_providers_async(self) -> None:
        """Initialize pipeline providers asynchronously from global registry.

        This is idempotent and can be safely called multiple times.
        Providers that fail to initialize will be set to None with appropriate logging.
        """
        if self._providers_initialized:
            return

        # Initialize embedding provider (dense)
        try:
            self._embedding_provider = _get_embedding_instance(sparse=False)
            logger.info(
                "Initialized embedding provider: %s", type(self._embedding_provider).__name__
            )
        except Exception as e:
            logger.warning("Could not initialize embedding provider: %s", e)
            self._embedding_provider = None

        # Initialize sparse embedding provider
        try:
            self._sparse_provider = _get_embedding_instance(sparse=True)
            logger.info("Initialized sparse provider: %s", type(self._sparse_provider).__name__)
        except Exception as e:
            logger.debug("Could not initialize sparse embedding provider: %s", e)
            self._sparse_provider = None

        # Warn if no embedding providers available
        if not self._embedding_provider and not self._sparse_provider:
            logger.warning(
                "⚠️  No embedding providers initialized - indexing will proceed without embeddings"
            )

        # Initialize vector store (async operation)
        try:
            self._vector_store = _get_vector_store_instance()
            if self._vector_store:
                # Initialize the vector store client (now we can use native await)
                await self._vector_store._initialize()
            logger.info("Initialized vector store: %s", type(self._vector_store).__name__)
        except Exception as e:
            logger.warning("Could not initialize vector store: %s", e)
            self._vector_store = None

        # Ensure chunking service is initialized
        self._chunking_service = self._chunking_service or _get_chunking_service()

        self._providers_initialized = True

    async def _index_file(self, path: Path, context: Any = None) -> None:
        """Execute full pipeline for a single file: discover → chunk → embed → index.

        Args:
            path: Path to the file to index
            context: Optional FastMCP context for structured logging
        """
        # Ensure manifest lock is initialized in async context
        if self._manifest_lock is None:
            self._manifest_lock = asyncio.Lock()

        try:
            # 1. Discover and store file metadata
            discovered_file = DiscoveredFile.from_path(path)
            if not discovered_file or not discovered_file.is_text:
                logger.debug("Skipping non-text file: %s", path)
                return

            self._store.set(discovered_file.file_hash, discovered_file)
            self._stats.files_discovered += 1

            await log_to_client_or_fallback(
                context,
                "debug",
                {
                    "msg": "File discovered",
                    "extra": {
                        "phase": "discovery",
                        "file_path": str(path),
                        "file_size": discovered_file.size,
                        "file_language": discovered_file.ext_kind.language.as_variable
                        if discovered_file.ext_kind
                        and isinstance(
                            discovered_file.ext_kind.language,
                            SemanticSearchLanguage | ConfigLanguage,
                        )
                        else str(discovered_file.ext_kind.language)
                        if discovered_file.ext_kind
                        else "unknown",
                        "total_discovered": self._stats.files_discovered,
                    },
                },
            )

            # 2. Chunk via ChunkingService (if available)
            if not self._chunking_service:
                logger.warning("No chunking service configured, skipping file: %s", path)
                return

            chunks = self._chunking_service.chunk_file(discovered_file)
            self._stats.chunks_created += len(chunks)

            await log_to_client_or_fallback(
                context,
                "debug",
                {
                    "msg": "File chunked",
                    "extra": {
                        "phase": "chunking",
                        "file_path": str(path),
                        "chunks_created": len(chunks),
                        "total_chunks": self._stats.chunks_created,
                    },
                },
            )

            # 3. Embed chunks (if embedding providers available)
            if self._embedding_provider or self._sparse_provider:
                await self._embed_chunks(chunks)
                self._stats.chunks_embedded += len(chunks)

                await log_to_client_or_fallback(
                    context,
                    "debug",
                    {
                        "msg": "Chunks embedded",
                        "extra": {
                            "phase": "embedding",
                            "file_path": str(path),
                            "chunks_embedded": len(chunks),
                            "total_embedded": self._stats.chunks_embedded,
                            "dense_provider": type(self._embedding_provider).__name__
                            if self._embedding_provider
                            else None,
                            "sparse_provider": type(self._sparse_provider).__name__
                            if self._sparse_provider
                            else None,
                        },
                    },
                )
            else:
                await log_to_client_or_fallback(
                    context,
                    "warning",
                    {
                        "msg": "No embedding providers configured",
                        "extra": {
                            "phase": "embedding",
                            "file_path": str(path),
                            "action": "skipped",
                        },
                    },
                )

            # 4. Retrieve updated chunks from registry (single source of truth!)
            from codeweaver.providers.embedding.registry import get_embedding_registry

            registry = get_embedding_registry()
            updated_chunks = [
                registry[chunk.chunk_id].chunk for chunk in chunks if chunk.chunk_id in registry
            ]

            # If no chunks were embedded, use original chunks
            if not updated_chunks:
                logger.debug("No embedded chunks, using original chunks for: %s", path)
                updated_chunks = chunks

            # 5. Index to vector store (if available)
            if self._vector_store:
                await self._vector_store.upsert(updated_chunks)
                self._stats.chunks_indexed += len(updated_chunks)

                await log_to_client_or_fallback(
                    context,
                    "debug",
                    {
                        "msg": "Chunks indexed to vector store",
                        "extra": {
                            "phase": "storage",
                            "file_path": str(path),
                            "chunks_indexed": len(updated_chunks),
                            "total_indexed": self._stats.chunks_indexed,
                            "vector_store": type(self._vector_store).__name__,
                        },
                    },
                )
            else:
                await log_to_client_or_fallback(
                    context,
                    "warning",
                    {
                        "msg": "No vector store configured",
                        "extra": {"phase": "storage", "file_path": str(path), "action": "skipped"},
                    },
                )

            self._stats.files_processed += 1

            # 6. Update file manifest with successful indexing
            # Only update if all critical operations succeeded and we have chunks
            if self._file_manifest and updated_chunks and self._manifest_lock:
                chunk_ids = [str(chunk.chunk_id) for chunk in updated_chunks]
                if relative_path := set_relative_path(path):
                    try:
                        async with self._manifest_lock:
                            self._file_manifest.add_file(
                                path=relative_path,
                                content_hash=discovered_file.file_hash,
                                chunk_ids=chunk_ids,
                            )
                        logger.debug(
                            "Updated manifest for file: %s (%d chunks)",
                            relative_path,
                            len(chunk_ids),
                        )
                    except ValueError as e:
                        logger.warning("Failed to add file to manifest: %s - %s", relative_path, e)

            await log_to_client_or_fallback(
                context,
                "info",
                {
                    "msg": "File processing complete",
                    "extra": {
                        "file_path": str(path),
                        "chunks_created": len(chunks),
                        "files_processed": self._stats.files_processed,
                        "total_files": self._stats.files_discovered,
                        "progress_pct": round(
                            (self._stats.files_processed / self._stats.files_discovered * 100), 1
                        )
                        if self._stats.files_discovered > 0
                        else 0,
                    },
                },
            )

        except Exception as e:
            logger.exception("Failed to index file %s", path)
            self._stats.files_with_errors.append(path)

            await log_to_client_or_fallback(
                context,
                "error",
                {
                    "msg": "File indexing failed",
                    "extra": {
                        "file_path": str(path),
                        "error": str(e),
                        "error_type": type(e).__name__,
                        "total_errors": len(self._stats.files_with_errors),
                    },
                },
            )

    def _telemetry_keys(self) -> None:
        return None

    async def _embed_chunks(self, chunks: list[Any]) -> None:
        """Embed chunks with both dense and sparse providers.

        Args:
            chunks: List of CodeChunk objects to embed
        """
        if not chunks:
            return

        # Dense embeddings
        if self._embedding_provider:
            try:
                await self._embedding_provider.embed_documents(chunks)
                logger.debug("Generated dense embeddings for %d chunks", len(chunks))
            except Exception:
                logger.exception("Dense embedding failed")

        # Sparse embeddings
        if self._sparse_provider:
            try:
                await self._sparse_provider.embed_documents(chunks)
                logger.debug("Generated sparse embeddings for %d chunks", len(chunks))
            except Exception:
                logger.exception("Sparse embedding failed")

    async def _delete_file(self, path: Path) -> None:
        """Remove file from store and vector store.

        Args:
            path: Path to the file to remove
        """
        # Ensure manifest lock is initialized in async context
        if self._manifest_lock is None:
            self._manifest_lock = asyncio.Lock()

        try:
            if removed := self._remove_path(path):
                logger.debug("Removed %d entries from store for: %s", removed, path)

            # Remove from vector store
            if self._vector_store:
                try:
                    await self._vector_store.delete_by_file(path)
                    logger.debug("Removed chunks from vector store for: %s", path)
                except Exception:
                    logger.exception("Failed to remove from vector store")

            # Remove from file manifest (use relative path)
            if (
                self._file_manifest
                and self._manifest_lock
                and (relative_path := set_relative_path(path))
            ):
                try:
                    async with self._manifest_lock:
                        entry = self._file_manifest.remove_file(relative_path)
                    if entry:
                        logger.debug(
                            "Removed file from manifest: %s (%d chunks)",
                            relative_path,
                            entry["chunk_count"],
                        )
                except ValueError as e:
                    logger.warning("Failed to remove file from manifest: %s - %s", relative_path, e)
        except Exception:
            logger.exception("Failed to delete file %s", path)

    async def _cleanup_deleted_files(self) -> None:
        """Clean up files that were deleted from the repository.

        Removes chunks from vector store and entries from manifest.
        """
        if not self._deleted_files:
            return

        logger.info("Cleaning up %d deleted files", len(self._deleted_files))

        for path in self._deleted_files:
            await self._delete_file(path)

        self._deleted_files.clear()
        logger.info("Deleted file cleanup complete")

    async def index(self, change: FileChange) -> None:
        """Index a single file based on a watchfiles change event.

        Enhanced version that executes full pipeline: file → chunks → embeddings → vector store.
        Handles added, modified, and deleted file events.
        """
        try:
            change_type, raw_path = change
        except Exception:
            logger.exception("Invalid FileChange tuple received: %r", change)
            return

        path = Path(raw_path)

        match change_type:
            case Change.added | Change.modified:
                # Skip non-files quickly
                if not path.exists() or not path.is_file():
                    return
                # Execute full pipeline
                await self._index_file(path)

            case Change.deleted:
                # Remove from store and vector store
                await self._delete_file(path)

            case _:
                logger.debug("Unhandled change type %s for %s", change_type, path)

    # ---- public helpers ----
    def _load_file_manifest(self) -> bool:
        """Load file manifest for incremental indexing.

        Returns:
            True if manifest was loaded successfully
        """
        if not self._manifest_manager:
            logger.debug("No manifest manager configured")
            return False

        if manifest := self._manifest_manager.load():
            # Validate that loaded manifest matches current project path
            if manifest.project_path.resolve() != self._manifest_manager.project_path.resolve():
                logger.warning(
                    "Loaded manifest project path mismatch (expected %s, got %s). Creating new manifest.",
                    self._manifest_manager.project_path,
                    manifest.project_path,
                )
                self._file_manifest = self._manifest_manager.create_new()
                return False

            self._file_manifest = manifest
            logger.info(
                "File manifest loaded: %d files, %d chunks",
                manifest.total_files,
                manifest.total_chunks,
            )
            return True
        # Create new manifest
        self._file_manifest = self._manifest_manager.create_new()
        logger.info("Created new file manifest")
        return False

    def _save_file_manifest(self) -> bool:
        """Save current file manifest to disk.

        Returns:
            True if save was successful, False otherwise
        """
        if not self._manifest_manager or not self._file_manifest:
            logger.warning("No manifest manager or manifest to save")
            return False

        return self._manifest_manager.save(self._file_manifest)

    def _try_restore_from_checkpoint(self, *, force_reindex: bool) -> bool:
        """Attempt to restore indexing state from checkpoint.

        Args:
            force_reindex: If True, skip restoration

        Returns:
            True if successfully restored, False otherwise
        """
        if force_reindex:
            return False

        try:
            if self.load_checkpoint():
                logger.info("Resuming from checkpoint")
                return True
        except Exception as e:
            logger.debug("Could not restore from persistence: %s", e)
        return False

    def _discover_files_to_index(self) -> list[Path]:
        """Discover files to index using the configured walker.

        With incremental indexing, only returns files that are new or modified.

        Returns:
            List of file paths to index
        """
        if not self._walker:
            logger.warning("No walker configured, cannot prime index")
            return []

        all_files: list[Path] = []
        try:
            with contextlib.suppress(StopIteration):
                all_files.extend(p for p in self._walker if p and p.is_file())
        except Exception:
            logger.exception("Failure during file discovery")
            return []

        if not all_files:
            logger.info("No files found to index")
            return []

        # If no manifest, index all files
        if not self._file_manifest:
            logger.info("No file manifest - will index all %d discovered files", len(all_files))
            self._stats.files_discovered = len(all_files)
            return all_files

        # Filter to only new or modified files
        files_to_index: list[Path] = []
        unchanged_count = 0

        for path in all_files:
            try:
                # Compute current hash (path is absolute from walker)
                current_hash = get_blake_hash(path.read_bytes())

                # Convert to relative path for manifest lookup
                relative_path = set_relative_path(path)
                if not relative_path:
                    # If can't convert to relative, treat as new file
                    files_to_index.append(path)
                    continue

                try:
                    # Check if file is new or changed
                    if self._file_manifest.file_changed(relative_path, current_hash):
                        files_to_index.append(path)
                    else:
                        unchanged_count += 1
                except ValueError as e:
                    # Invalid path in manifest operations
                    logger.warning("Invalid path %s: %s, will index it", relative_path, e)
                    files_to_index.append(path)
            except Exception:
                logger.exception("Error checking file %s, will index it", path)
                files_to_index.append(path)

        # Detect deleted files (in manifest but not on disk)
        # Convert all discovered files to relative paths for comparison
        manifest_files = self._file_manifest.get_all_file_paths()
        all_files_relative = {set_relative_path(p) for p in all_files if set_relative_path(p)}
        deleted_files = manifest_files - all_files_relative

        if deleted_files:
            logger.info("Detected %d deleted files to clean up", len(deleted_files))
            # Schedule cleanup (will be done in separate phase)
            # Convert relative paths from manifest to absolute paths for cleanup
            if self._project_root:
                self._deleted_files = [self._project_root / rel_path for rel_path in deleted_files]
            else:
                logger.warning("No project root set, cannot resolve deleted file paths")
                self._deleted_files = []

        logger.info(
            "Incremental indexing: %d new/modified, %d unchanged, %d deleted",
            len(files_to_index),
            unchanged_count,
            len(deleted_files) if deleted_files else 0,
        )

        self._stats.files_discovered = len(files_to_index)
        return files_to_index

    async def _perform_batch_indexing_async(
        self,
        files_to_index: list[Path],
        progress_callback: Callable[[IndexingStats, str | None], None] | None,
    ) -> None:
        """Execute batch indexing for discovered files.

        Args:
            files_to_index: List of files to process
            progress_callback: Optional progress reporting callback
        """
        try:
            await self._index_files_batch(files_to_index, progress_callback)
        except Exception:
            logger.exception("Failure during batch indexing")

    def _finalize_indexing(self) -> None:
        """Log final statistics, save checkpoint and manifest, and cleanup."""
        logger.info(
            "Indexing complete: %d files processed, %d chunks created, %d indexed, %d errors in %.2fs (%.2f files/sec)",
            self._stats.files_processed,
            self._stats.chunks_created,
            self._stats.chunks_indexed,
            len(self._stats.files_with_errors),
            self._stats.elapsed_time(),
            self._stats.processing_rate(),
        )

        # Save file manifest
        self._save_file_manifest()

        # Save final checkpoint
        self.save_checkpoint()
        logger.info("Final checkpoint saved")

        # Clean up checkpoint file on successful completion
        if self._checkpoint_manager and len(self._stats.files_with_errors) == 0:
            self._checkpoint_manager.delete()
            logger.info("Checkpoint file deleted after successful completion")

    async def prime_index(
        self,
        *,
        force_reindex: bool = False,
        progress_callback: Callable[[IndexingStats, str | None], None] | None = None,
    ) -> int:
        """Perform an initial indexing pass using the configured rignore walker.

        Enhanced version with persistence support, incremental indexing, and batch processing.

        Args:
            force_reindex: If True, skip persistence checks and reindex everything
            progress_callback: Optional callback to report progress (receives stats and phase)

        Returns:
            Number of files indexed
        """
        # Initialize providers asynchronously (idempotent)
        await self._initialize_providers_async()

        # Load file manifest for incremental indexing (unless force_reindex)
        if not force_reindex:
            self._load_file_manifest()
        else:
            # Force reindex - create new manifest
            if self._manifest_manager:
                self._file_manifest = self._manifest_manager.create_new()
                logger.info("Force reindex - created new file manifest")

        # Try to restore from checkpoint (unless force_reindex)
        if self._try_restore_from_checkpoint(force_reindex=force_reindex):
            # Note: In current version, we still reindex discovered files
            # Full resumption would require storing processed file list in checkpoint
            pass

        # Reset stats for new indexing run
        self._stats = IndexingStats()
        self._deleted_files = []

        # Discover files to index (with incremental filtering if manifest exists)
        files_to_index = self._discover_files_to_index()

        # Clean up deleted files first (before indexing new/modified files)
        if self._deleted_files:
            try:
                await self._cleanup_deleted_files()
            except Exception:
                logger.exception("Failed to clean up deleted files")

        if not files_to_index:
            logger.info("No files to index (all up to date)")
            self._finalize_indexing()
            return 0

        # Report discovery phase complete
        if progress_callback:
            progress_callback(self._stats, "discovery")

        # Index files in batch
        await self._perform_batch_indexing_async(files_to_index, progress_callback)

        # Finalize and report
        self._finalize_indexing()

        return self._stats.files_processed

    @classmethod
    def from_settings(cls, settings: DictView[CodeWeaverSettingsDict] | None = None) -> Indexer:
        """Create an Indexer instance from settings (sync version).

        Note: This method cannot set inc_exc patterns asynchronously.
        Use from_settings_async() for proper async initialization, or
        manually configure the walker's inc_exc patterns after creation.

        Args:
            settings: Optional settings dictionary view

        Returns:
            Configured Indexer instance (may need async initialization via prime_index)
        """
        from codeweaver.config.indexing import DefaultIndexerSettings, IndexerSettings
        from codeweaver.config.settings import get_settings_map

        settings_map = settings or get_settings_map()
        indexing_data = settings_map["indexing"]

        # Handle different types of indexing_data
        if isinstance(indexing_data, Unset):
            index_settings = IndexerSettings.model_validate(DefaultIndexerSettings)
        elif isinstance(indexing_data, IndexerSettings):
            # Use the existing IndexerSettings instance directly
            index_settings = indexing_data
        else:
            # If it's a dict or something else, try to validate it
            index_settings = IndexerSettings.model_validate(
                DefaultIndexerSettings | indexing_data
                if isinstance(indexing_data, dict)
                else DefaultIndexerSettings
            )

        # Note: inc_exc setting is skipped in sync version
        # The walker will be created with default settings
        # For proper inc_exc patterns, use from_settings_async()
        if not index_settings.inc_exc_set:
            logger.debug(
                "inc_exc patterns not set (async operation required). "
                "Use from_settings_async() for full initialization."
            )

        walker = rignore.Walker(
            **(index_settings.to_settings())  # type: ignore
        )
        return cls(walker=walker, project_path=settings_map["project_path"])

    @classmethod
    async def from_settings_async(
        cls, settings: DictView[CodeWeaverSettingsDict] | None = None
    ) -> Indexer:
        """Create an Indexer instance from settings with full async initialization.

        This method properly awaits all async operations including inc_exc pattern setting.
        Recommended over from_settings() for production use.

        Args:
            settings: Optional settings dictionary view

        Returns:
            Fully initialized Indexer instance
        """
        from codeweaver.common.utils.git import get_project_path
        from codeweaver.config.indexing import DefaultIndexerSettings, IndexerSettings
        from codeweaver.config.settings import get_settings_map

        settings_map = settings or get_settings_map()
        indexing_data = settings_map["indexing"]

        # Handle different types of indexing_data
        if isinstance(indexing_data, Unset):
            index_settings = IndexerSettings.model_validate(DefaultIndexerSettings)
        elif isinstance(indexing_data, IndexerSettings):
            # Use the existing IndexerSettings instance directly
            index_settings = indexing_data
        else:
            # If it's a dict or something else, try to validate it
            index_settings = IndexerSettings.model_validate(
                DefaultIndexerSettings | indexing_data
                if isinstance(indexing_data, dict)
                else DefaultIndexerSettings
            )

        # Properly await inc_exc initialization
        if not index_settings.inc_exc_set:
            project_path_value = (
                get_project_path()
                if isinstance(settings_map["project_path"], Unset)
                else settings_map["project_path"]
            )
            await index_settings.set_inc_exc(project_path_value)
            logger.debug("inc_exc patterns initialized for project: %s", project_path_value)

        walker = rignore.Walker(
            **(index_settings.to_settings())  # type: ignore
        )
        indexer = cls(walker=walker, project_path=settings_map["project_path"])

        # Initialize providers asynchronously
        await indexer._initialize_providers_async()

        return indexer

    def _discover_files_for_batch(self, files: list[Path]) -> list[DiscoveredFile]:
        """Convert file paths to DiscoveredFile objects.

        Args:
            files: List of file paths to discover

        Returns:
            List of valid DiscoveredFile objects
        """
        discovered_files: list[DiscoveredFile] = []
        for path in files:
            try:
                discovered_file = DiscoveredFile.from_path(path)
                if discovered_file and discovered_file.is_text:
                    discovered_files.append(discovered_file)
                    self._store.set(discovered_file.file_hash, discovered_file)
            except Exception:
                logger.exception("Failed to discover file %s", path)
                self._stats.files_with_errors.append(path)
        return discovered_files

    def _chunk_discovered_files(self, discovered_files: list[DiscoveredFile]) -> list[CodeChunk]:
        """Chunk discovered files using the chunking service.

        Args:
            discovered_files: List of discovered files to chunk

        Returns:
            List of code chunks created from the files
        """
        if not self._chunking_service:
            self._chunking_service = _get_chunking_service()
        all_chunks: list[CodeChunk] = []
        for file_path, chunks in self._chunking_service.chunk_files(discovered_files):
            all_chunks.extend(chunks)
            self._stats.chunks_created += len(chunks)
            logger.debug("Chunked %s: %d chunks", file_path, len(chunks))
        return all_chunks

    async def _embed_chunks_in_batches(
        self, chunks: list[CodeChunk], batch_size: int = 100
    ) -> None:
        """Embed chunks in batches.

        Args:
            chunks: List of chunks to embed
            batch_size: Number of chunks per batch
        """
        for i in range(0, len(chunks), batch_size):
            batch = chunks[i : i + batch_size]
            try:
                await self._embed_chunks(batch)
                self._stats.chunks_embedded += len(batch)
                logger.debug("Embedded batch %d-%d (%d chunks)", i, i + len(batch), len(batch))
            except Exception:
                logger.exception("Failed to embed batch %d-%d", i, i + len(batch))

    def _retrieve_embedded_chunks(self, chunks: list[CodeChunk]) -> list[CodeChunk]:
        """Retrieve embedded chunks from registry, falling back to originals if needed.

        Args:
            chunks: Original chunks to look up in registry

        Returns:
            Updated chunks from registry, or original chunks if none found
        """
        from codeweaver.providers.embedding.registry import get_embedding_registry

        registry = get_embedding_registry()
        updated_chunks = [
            registry[chunk.chunk_id].chunk for chunk in chunks if chunk.chunk_id in registry
        ]

        if not updated_chunks:
            logger.warning("No chunks were embedded, using original chunks")
            return chunks
        return updated_chunks

    async def _index_chunks_to_store(self, chunks: list[CodeChunk]) -> None:
        """Index chunks to the vector store.

        Args:
            chunks: List of chunks to index
        """
        if not self._vector_store:
            logger.warning("No vector store configured, skipping indexing")
            return

        try:
            await self._vector_store.upsert(chunks)
            self._stats.chunks_indexed = len(chunks)
            logger.info("Indexed %d chunks to vector store", len(chunks))
        except Exception:
            logger.exception("Failed to index to vector store")

    async def _phase_embed_and_index(
        self,
        all_chunks: list[CodeChunk],
        progress_callback: Callable[[IndexingStats, str | None], None] | None,
        context: Any,
    ) -> None:
        """Execute embedding and indexing phases if providers are initialized."""
        if not (self._embedding_provider or self._sparse_provider or self._vector_store):
            await log_to_client_or_fallback(
                context,
                "debug",
                {
                    "msg": "Skipping embedding and indexing phases",
                    "extra": {"reason": "no_providers_initialized"},
                },
            )
            return

        # Phase 3: Embed chunks in batches
        await log_to_client_or_fallback(
            context,
            "info",
            {
                "msg": "Starting embedding phase",
                "extra": {
                    "phase": "embedding",
                    "chunks_to_embed": len(all_chunks),
                    "dense_provider": type(self._embedding_provider).__name__
                    if self._embedding_provider
                    else None,
                    "sparse_provider": type(self._sparse_provider).__name__
                    if self._sparse_provider
                    else None,
                },
            },
        )

        await self._embed_chunks_in_batches(all_chunks)

        await log_to_client_or_fallback(
            context,
            "info",
            {
                "msg": "Embedding complete",
                "extra": {"phase": "embedding", "chunks_embedded": self._stats.chunks_embedded},
            },
        )

        if progress_callback:
            progress_callback(self._stats, "embedding")

        # Phase 4: Retrieve embedded chunks from registry
        updated_chunks = self._retrieve_embedded_chunks(all_chunks)

        # Phase 5: Index to vector store
        await log_to_client_or_fallback(
            context,
            "info",
            {
                "msg": "Starting vector store indexing",
                "extra": {
                    "phase": "storage",
                    "chunks_to_index": len(updated_chunks),
                    "vector_store": type(self._vector_store).__name__
                    if self._vector_store
                    else None,
                },
            },
        )

        await self._index_chunks_to_store(updated_chunks)

        await log_to_client_or_fallback(
            context,
            "info",
            {
                "msg": "Vector store indexing complete",
                "extra": {"phase": "storage", "chunks_indexed": self._stats.chunks_indexed},
            },
        )

        if progress_callback:
            progress_callback(self._stats, "indexing")

    async def _phase_discovery(
        self,
        files: list[Path],
        progress_callback: Callable[[IndexingStats, str | None], None] | None,
        context: Any,
    ) -> list[DiscoveredFile]:
        """Execute discovery phase and return discovered files."""
        await log_to_client_or_fallback(
            context,
            "info",
            {
                "msg": "Starting batch indexing",
                "extra": {
                    "phase": "discovery",
                    "batch_size": len(files),
                    "total_discovered": self._stats.files_discovered,
                },
            },
        )

        discovered_files = self._discover_files_for_batch(files)

        if progress_callback:
            progress_callback(self._stats, "discovery")

        return discovered_files

    async def _phase_chunking(
        self,
        discovered_files: list[DiscoveredFile],
        progress_callback: Callable[[IndexingStats, str | None], None] | None,
        context: Any,
    ) -> list[CodeChunk]:
        """Execute chunking phase and return chunks."""
        await log_to_client_or_fallback(
            context,
            "info",
            {
                "msg": "Discovery complete, starting chunking",
                "extra": {
                    "phase": "chunking",
                    "files_discovered": len(discovered_files),
                    "languages": list({
                        (
                            f.ext_kind.language.value
                            if hasattr(f.ext_kind.language, "value")
                            else str(f.ext_kind.language)
                        )
                        for f in discovered_files
                        if f.ext_kind
                    }),
                },
            },
        )

        all_chunks = self._chunk_discovered_files(discovered_files)

        await log_to_client_or_fallback(
            context,
            "info",
            {
                "msg": "Chunking complete",
                "extra": {
                    "phase": "chunking",
                    "chunks_created": len(all_chunks),
                    "files_chunked": len(discovered_files),
                    "avg_chunks_per_file": round(len(all_chunks) / len(discovered_files), 1),
                },
            },
        )

        if progress_callback:
            progress_callback(self._stats, "chunking")

        return all_chunks

    async def _index_files_batch(
        self,
        files: list[Path],
        progress_callback: Callable[[IndexingStats, str | None], None] | None = None,
        context: Any = None,
    ) -> None:
        """Index multiple files in batch using the chunking service.

        Args:
            files: List of file paths to index
            progress_callback: Optional callback to report progress (receives stats and phase)
            context: Optional FastMCP context for structured logging
        """
        if not files:
            return

        # Check for shutdown request
        if self._shutdown_requested:
            await log_to_client_or_fallback(
                context,
                "info",
                {
                    "msg": "Shutdown requested",
                    "extra": {"action": "stopping_batch_indexing", "files_remaining": len(files)},
                },
            )
            return

        if not self._chunking_service:
            await log_to_client_or_fallback(
                context,
                "warning",
                {
                    "msg": "No chunking service configured",
                    "extra": {"action": "cannot_batch_index", "files_count": len(files)},
                },
            )
            return

        # Phase 1: Discover files
        discovered_files = await self._phase_discovery(files, progress_callback, context)
        if not discovered_files:
            await log_to_client_or_fallback(
                context,
                "info",
                {
                    "msg": "No valid files to index",
                    "extra": {"phase": "discovery", "files_attempted": len(files)},
                },
            )
            return

        # Phase 2: Chunk files
        all_chunks = await self._phase_chunking(discovered_files, progress_callback, context)
        if not all_chunks:
            await log_to_client_or_fallback(
                context,
                "info",
                {
                    "msg": "No chunks created",
                    "extra": {"phase": "chunking", "files_processed": len(discovered_files)},
                },
            )
            return

        # Phase 3-5: Embed and index
        await self._phase_embed_and_index(all_chunks, progress_callback, context)

        # Update stats with successful file count
        self._stats.files_processed += len(discovered_files)
        self._files_since_checkpoint += len(discovered_files)

        # Save checkpoint if threshold reached
        if self._should_checkpoint():
            self.save_checkpoint()
            logger.info(
                "Checkpoint saved at %d/%d files processed",
                self._stats.files_processed,
                self._stats.files_discovered,
            )

    def _should_checkpoint(self) -> bool:
        """Check if checkpoint should be saved based on frequency criteria.

        Returns:
            True if checkpoint should be saved (every 100 files or every 5 minutes)
        """
        # Check file count threshold
        if self._files_since_checkpoint >= 100:
            return True

        # Check time threshold (300 seconds = 5 minutes)
        elapsed_time = time.time() - self._last_checkpoint_time
        return elapsed_time >= 300

    @property
    def stats(self) -> IndexingStats:
        """Get current indexing statistics."""
        return self._stats

    # ---- internal helpers ----
    def _remove_path(self, path: Path) -> int:
        """Remove any entries in the store that match the given path. Returns number removed."""
        to_delete: list[Any] = []
        for key, discovered_file in list(self._store.items()):
            try:
                if discovered_file.path.samefile(path):
                    to_delete.append(key)
            except Exception:
                # defensive: malformed entry shouldn't break cleanup
                logger.exception("Error checking stored item for deletion")
                continue
        for key in to_delete:
            self._store.delete(key)
        return len(to_delete)

    @staticmethod
    def keep_alive(alive_time: float = 5000) -> None:
        """A long-lived no-op function suitable as the run target for arun_process.

        We keep the child process alive so arun_process can signal and restart it,
        but all indexing happens in the callback on the main process.
        """
        try:
            while True:
                sleep(alive_time)
        except KeyboardInterrupt:
            # allow graceful stop
            return

    # ---- Persistence methods (stubs for T007-T008) ----

    async def initialize_from_vector_store(self) -> None:
        """Query vector store for indexed files on cold start.

        TODO: Implement in T007/T008
        - Query vector store for all indexed chunks
        - Reconstruct file metadata store from chunk payloads
        - Populate self._store with DiscoveredFile objects
        """
        logger.debug("Persistence from vector store not yet implemented")

    def save_state(self, state_path: Path) -> None:
        """Save current indexer state to a file."""

    def save_checkpoint(self, checkpoint_path: DirectoryPath | None = None) -> None:
        """Save indexing state to checkpoint file.

        Saves current indexing progress including:
        - Files discovered/processed/indexed counts
        - Chunks created/embedded/indexed counts
        - Error list with file paths
        - Settings hash for invalidation detection
        - File manifest status for incremental indexing

        Args:
            checkpoint_path: Optional custom checkpoint file path (primarily for testing)
        """
        if not self._checkpoint_manager:
            logger.warning("No checkpoint manager configured")
            return

        # Compute settings hash

        settings_hash = self._checkpoint_manager.compute_settings_hash(
            self._checkpoint_manager.get_relevant_settings()
        )

        # Create or update checkpoint
        if not self._checkpoint:
            self._checkpoint = IndexingCheckpoint(
                project_path=self._checkpoint_manager.get_relevant_settings()["project_path"],
                settings_hash=settings_hash,
            )

        # Update checkpoint with current stats
        self._checkpoint.files_discovered = self._stats.files_discovered
        self._checkpoint.files_embedding_complete = self._stats.files_processed
        self._checkpoint.files_indexed = self._stats.files_processed
        self._checkpoint.chunks_created = self._stats.chunks_created
        self._checkpoint.chunks_embedded = self._stats.chunks_embedded
        self._checkpoint.chunks_indexed = self._stats.chunks_indexed
        self._checkpoint.files_with_errors = [str(p) for p in self._stats.files_with_errors]
        self._checkpoint.settings_hash = settings_hash

        # Update manifest info
        if self._file_manifest:
            self._checkpoint.has_file_manifest = True
            self._checkpoint.manifest_file_count = self._file_manifest.total_files
        else:
            self._checkpoint.has_file_manifest = False
            self._checkpoint.manifest_file_count = 0

        # Save to disk
        self._checkpoint_manager.save(self._checkpoint)
        self._last_checkpoint_time = time.time()
        self._files_since_checkpoint = 0

    def _construct_checkpoint_fingerprint(self) -> str:
        """Construct a fingerprint hash of current settings for checkpoint validation."""
        if not self._checkpoint_manager:
            raise RuntimeError("No checkpoint manager configured")
        return self._checkpoint_manager.compute_settings_hash(
            self._checkpoint_manager.get_relevant_settings()
        )

    def load_checkpoint(self, _checkpoint_path: Path | None = None) -> bool:
        """Load indexing state from checkpoint file.

        Loads checkpoint if available and valid:
        - Verifies settings hash matches current config
        - Skips if checkpoint >24 hours old
        - Restores stats for progress tracking

        Args:
            _checkpoint_path: Optional custom checkpoint file path (primarily for testing)

        Returns:
            True if checkpoint was loaded successfully and is valid for resumption
        """
        if not self._checkpoint_manager:
            logger.warning("No checkpoint manager configured")
            return False

        # Load checkpoint from disk
        checkpoint = self._checkpoint_manager.load()
        if not checkpoint:
            return False

        current_settings_hash = self._construct_checkpoint_fingerprint()

        if not self._checkpoint_manager.should_resume(
            checkpoint, current_settings_hash, max_age_hours=24
        ):
            logger.info("Checkpoint cannot be used for resumption, will reindex from scratch")
            return False

        # Restore stats from checkpoint
        self._stats.files_discovered = checkpoint.files_discovered
        self._stats.files_processed = checkpoint.files_embedding_complete
        self._stats.chunks_created = checkpoint.chunks_created
        self._stats.chunks_embedded = checkpoint.chunks_embedded
        self._stats.chunks_indexed = checkpoint.chunks_indexed
        type(self._stats).files_with_errors = [Path(p) for p in checkpoint.files_with_errors]

        self._checkpoint = checkpoint
        logger.info(
            "Checkpoint loaded successfully: %d/%d files processed, %d chunks created",
            checkpoint.files_embedding_complete,
            checkpoint.files_discovered,
            checkpoint.chunks_created,
        )
        return True


__all__ = ("Indexer",)
