# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""The indexer service for managing and querying indexed data."""
# import contextlib

# with contextlib.suppress(ImportError):
# from watchfiles import watch
# TODO: register with providers registry

from __future__ import annotations

import asyncio
import contextlib
import logging
import time

from collections.abc import Callable, Sequence
from pathlib import Path
from time import sleep
from typing import TYPE_CHECKING, Annotated, Any, ClassVar, Unpack, cast, overload

import rignore
import watchfiles

from pydantic import Field, PrivateAttr
from pydantic.dataclasses import dataclass
from watchfiles.main import Change, FileChange

from codeweaver.config.types import CodeWeaverSettingsDict, IndexerSettingsDict, RignoreSettings
from codeweaver.core.discovery import DiscoveredFile
from codeweaver.core.file_extensions import (
    CODE_FILES_EXTENSIONS,
    CONFIG_FILE_LANGUAGES,
    DEFAULT_EXCLUDED_DIRS,
    DEFAULT_EXCLUDED_EXTENSIONS,
    DOC_FILES_EXTENSIONS,
)
from codeweaver.core.language import ConfigLanguage, SemanticSearchLanguage
from codeweaver.core.stores import BlakeStore
from codeweaver.core.types.dictview import DictView
from codeweaver.core.types.models import BasedModel
from codeweaver.exceptions import ConfigurationError


logger = logging.getLogger(__name__)

if TYPE_CHECKING:
    from typing import Any

    from codeweaver.core.chunks import CodeChunk
    from codeweaver.providers.embedding.providers.base import EmbeddingProvider


def _get_settings_map() -> DictView[CodeWeaverSettingsDict]:
    """Stub function to get settings map. Replace with actual implementation."""
    from codeweaver.config.settings import get_settings_map

    return get_settings_map()


def _get_indexer_settings() -> DictView[IndexerSettingsDict]:
    """Retrieve indexer settings from the global settings map."""
    return DictView(_get_settings_map()["indexing"])


def _get_embedding_instance(*, sparse: bool = False) -> EmbeddingProvider[Any] | None:
    """Stub function to get embedding provider instance."""
    from codeweaver.common.registry import get_provider_registry

    registry = get_provider_registry()
    if provider := registry.get_embedding_provider(sparse=sparse):
        if sparse:
            return registry.get_sparse_embedding_provider_instance(
                provider=provider, singleton=True
            )
        return registry.get_embedding_provider_instance(provider=provider, singleton=True)
    return None


def _get_reranking_instance() -> Any | None:
    """Stub function to get reranking provider instance."""
    from codeweaver.common.registry import get_provider_registry

    registry = get_provider_registry()
    if provider := registry.get_reranking_provider():
        return registry.get_reranking_provider_instance(provider=provider, singleton=True)
    return None


def _get_vector_store_instance() -> Any | None:
    """Stub function to get vector store provider instance."""
    from codeweaver.common.registry import get_provider_registry

    registry = get_provider_registry()
    if provider := registry.get_vector_store_provider():
        return registry.get_vector_store_provider_instance(provider=provider, singleton=True)
    return None


@dataclass
class IndexingStats:
    """Statistics tracking for indexing progress."""

    files_discovered: int = 0
    files_processed: int = 0
    chunks_created: int = 0
    chunks_embedded: int = 0
    chunks_indexed: int = 0
    start_time: float = time.time()
    files_with_errors: ClassVar[
        Annotated[
            list[Path],
            Field(description="""List of file paths that encountered errors during indexing."""),
        ]
    ] = []

    @property
    def elapsed_time(self) -> float:
        """Calculate elapsed time since indexing started."""
        return time.time() - self.start_time

    @property
    def processing_rate(self) -> float:
        """Files processed per second."""
        if self.elapsed_time == 0:
            return 0.0
        return self.files_processed / self.elapsed_time


class DefaultFilter(watchfiles.DefaultFilter):
    """A default filter that ignores common unwanted files and directories."""

    def __init__(
        self,
        *,
        ignore_dirs: Sequence[str | Path] = cast(Sequence[str], DEFAULT_EXCLUDED_DIRS),
        ignore_entity_patterns: Sequence[str] | None = None,
        ignore_paths: Sequence[str | Path] | None = None,
    ) -> None:
        """A default filter that ignores common unwanted files and directories."""
        super().__init__(
            ignore_dirs=ignore_dirs,  # type: ignore
            ignore_entity_patterns=ignore_entity_patterns,
            ignore_paths=ignore_paths,
        )


class ExtensionFilter(DefaultFilter):
    """Filter files by extension on top of the default directory/path ignores."""

    def __init__(
        self,
        extensions: Sequence[str],
        ignore_paths: Sequence[str | Path] = cast(Sequence[str], set(DEFAULT_EXCLUDED_DIRS)),
    ) -> None:
        """Initialize the extension filter.

        Args:
            extensions: Extensions (with dot) to include.
            ignore_paths: Additional paths/directories to exclude.
        """
        self._ignore_paths = ignore_paths
        self.extensions: tuple[str, ...] = (
            extensions if isinstance(extensions, tuple) else tuple(extensions)
        )
        self.__slots__ = (*super().__slots__, "extensions")
        super().__init__()

    def __call__(self, change: Change, path: str) -> bool:
        """Return True when path ends with allowed extensions and passes base filter."""
        return path.endswith(self.extensions) and super().__call__(change, path)


class DefaultExtensionFilter(ExtensionFilter):
    """Filter with a default excluded extension set augmented by provided ones."""

    def __init__(
        self,
        extensions: Sequence[str] = cast(Sequence[str], DEFAULT_EXCLUDED_EXTENSIONS),
        ignore_paths: Sequence[str | Path] = cast(Sequence[str], set(DEFAULT_EXCLUDED_DIRS)),
    ) -> None:
        """Initialize the default extension filter with sensible defaults."""
        self._ignore_paths = ignore_paths
        self.extensions: tuple[str, ...] = (
            extensions if isinstance(extensions, tuple) else tuple(extensions)
        )
        self.__slots__ = (*super().__slots__, "extensions", "_ignore_paths")
        super().__init__(extensions=extensions, ignore_paths=ignore_paths)

    def __call__(self, change: Change, path: str) -> bool:
        """Return True when path ends with allowed extensions and passes base filter."""
        return path.endswith(self.extensions) and super().__call__(change, path)


CodeFilter = DefaultExtensionFilter(
    tuple(pair.ext for pair in CODE_FILES_EXTENSIONS if pair.language not in CONFIG_FILE_LANGUAGES)
    + tuple(SemanticSearchLanguage.code_extensions())
)

ConfigFilter = DefaultExtensionFilter(
    cast(
        Sequence[str],
        {pair.ext for pair in CODE_FILES_EXTENSIONS if pair.language in CONFIG_FILE_LANGUAGES}
        | set(iter(ConfigLanguage.all_extensions())),
    )
)

DocsFilter = DefaultExtensionFilter(tuple(pair.ext for pair in DOC_FILES_EXTENSIONS))


class IgnoreFilter[Walker: rignore.Walker](watchfiles.DefaultFilter):
    """
    A filter that uses rignore to exclude files based on .gitignore and other rules.

    `IgnoreFilter` can be initialized with either:
    - An `rignore.Walker` instance, which is a pre-configured walker that
      applies ignore rules.
    - A `base_path` and `settings` dictionary to create a new `rignore.Walker`.

    The filter checks if a file should be included based on the rules defined
    in the walker. It caches results to avoid redundant checks for previously
    seen paths.
    """

    _walker: Walker
    _allowed: ClassVar[set[Path]] = set()
    _allowed_complete: bool = False

    @overload
    def __init__(self, *, base_path: None, settings: None, walker: rignore.Walker) -> None: ...
    @overload
    def __init__(
        self, *, base_path: Path, walker: None = None, **settings: Unpack[RignoreSettings]
    ) -> None: ...
    def __init__(  # type: ignore
        self,
        *,
        base_path: Path | None = None,
        walker: Walker | None = None,
        settings: RignoreSettings | None = None,
    ) -> None:
        """Initialize the IgnoreFilter with either rignore settings or a pre-configured walker."""
        self.__slots__ = (*super().__slots__, "_walker", "_allowed_complete", "_allowed")
        if not walker and not (settings and base_path):
            self = type(self).from_settings()
            return
        if walker and settings:
            # favor walker if both are provided
            logger.warning("Both settings and walker provided; using walker.")
        if walker:
            self._walker = walker
        else:
            if settings is None:
                raise ValueError("You must provide either settings or a walker.")
            if base_path is None:
                raise ValueError("Base path must be provided if walker is not.")
            if (
                (filter_present := settings.pop("filter", None))
                and callable(filter_present)
                and settings.get("should_exclude_entry") is None
            ) or not callable(settings.get("should_exclude_entry")):
                settings |= {"should_exclude_entry": filter_present}  # type: ignore
            self._walker = rignore.walk(path=base_path, **cast(dict[str, Any], settings))  # type: ignore
        super().__init__()

    def __call__(self, change: Change, path: str) -> bool:
        """Determine if a file should be included based on rignore rules."""
        p = Path(path)
        match change:
            case Change.deleted:
                return self._walkable(p, is_new=False, delete=True)
            case Change.added:
                return self._walkable(p, is_new=True, delete=False)
            case Change.modified:
                return self._walkable(p, is_new=False, delete=False)

    def _walkable(self, path: Path, *, is_new: bool = False, delete: bool = False) -> bool:
        """Check if a path is walkable (not ignored) using the rignore walker.

        Stores previously seen paths to avoid redundant checks.

        This method still returns True for deleted files to allow cleanup of indexed data.
        """
        if self._allowed_complete and (not is_new or path in self._allowed):
            if delete and path in self._allowed:
                self._allowed.remove(path)
                return True
            return False if delete else path in self._allowed
        if delete:
            with contextlib.suppress(KeyError):
                self._allowed.remove(path)
                return True
            # It's either not in allowed or it doesn't matter because we're deleting
            return False
        try:
            for p in self._walker:
                # it's a set, so we add regardless of whether it's already there
                self._allowed.add(p)
                if p and p.samefile(str(path)):
                    return True
        except StopIteration:
            self._allowed_complete = True
        return False

    @classmethod
    def from_settings(
        cls, settings: DictView[CodeWeaverSettingsDict] | None = None
    ) -> IgnoreFilter[rignore.Walker]:
        """Create an IgnoreFilter instance from settings."""
        # we actually need the full object here
        from codeweaver.config.settings import get_settings, get_settings_map

        settings_map = settings or get_settings_map()
        index_settings = get_settings().indexing
        if not index_settings.inc_exc_set:
            _ = asyncio.run(index_settings.set_inc_exc(get_settings().project_path))
        indexing = index_settings.to_settings()
        return cls(
            base_path=settings_map["project_path"], settings=None, walker=rignore.walk(**indexing)
        )

    @property
    def walker(self) -> rignore.Walker:
        """Return the underlying rignore walker used by this filter."""
        return self._walker


class Indexer(BasedModel):
    """Main indexer class. Wraps a DiscoveredFilestore and chunkers."""

    _store: BlakeStore[DiscoveredFile] = PrivateAttr()
    _parsers: Annotated[Sequence[Callable[[Path], Any]], PrivateAttr(default_factory=list)]
    _walker: rignore.Walker | None = PrivateAttr(default=None)

    def __init__(
        self,
        walker: rignore.Walker | None = None,
        store: BlakeStore[DiscoveredFile] | None = None,
        chunking_service: Any | None = None,  # ChunkingService type
        *,
        auto_initialize_providers: bool = True,
    ) -> None:
        """Initialize the Indexer with optional pipeline components.

        Args:
            walker: rignore walker for file discovery
            store: Store for discovered file metadata
            chunking_service: Service for chunking files (optional)
            auto_initialize_providers: Auto-initialize providers from global registry
        """
        self._parsers = []
        self._store = store or BlakeStore[DiscoveredFile](_value_type=DiscoveredFile)
        self._walker = walker
        self._chunking_service = chunking_service
        self._stats = IndexingStats()

        # Pipeline provider Fields (initialized below or lazily)
        self._embedding_provider: Any | None = None
        self._sparse_provider: Any | None = None
        self._vector_store: Any | None = None

        if auto_initialize_providers:
            self._initialize_providers()

    def _initialize_providers(self) -> None:
        """Initialize pipeline providers from global registry."""
        try:
            try:
                self._embedding_provider = _get_embedding_instance(sparse=False)
                logger.info(
                    "Initialized embedding provider: %s", type(self._embedding_provider).__name__
                )
            except Exception as e:
                logger.warning("No embedding provider configured: %s", e)
                self._embedding_provider = None

            try:
                self._sparse_provider = _get_embedding_instance(sparse=True)
                logger.info("Initialized sparse provider: %s", type(self._sparse_provider).__name__)
            except Exception as e:
                logger.debug("No sparse embedding provider configured: %s", e)
                self._sparse_provider = None

            if not self._embedding_provider and not self._sparse_provider:
                logger.warning("No embedding providers configured")
                raise ConfigurationError("No embedding providers configured")

            try:
                self._vector_store = _get_vector_store_instance()
                logger.info("Initialized vector store: %s", type(self._vector_store).__name__)
            except Exception as e:
                logger.warning("No vector store configured: %s", e)
                self._vector_store = None

        except ImportError:
            logger.warning("Provider registry not available, providers not initialized")

    async def _index_file(self, path: Path) -> None:
        """Execute full pipeline for a single file: discover → chunk → embed → index.

        Args:
            path: Path to the file to index
        """
        try:
            # 1. Discover and store file metadata
            discovered_file = DiscoveredFile.from_path(path)
            if not discovered_file or not discovered_file.is_text:
                logger.debug("Skipping non-text file: %s", path)
                return

            self._store.set(discovered_file.file_hash, discovered_file)
            self._stats.files_discovered += 1
            logger.debug("Discovered file: %s (%s bytes)", path, discovered_file.size)

            # 2. Chunk via ChunkingService (if available)
            if not self._chunking_service:
                logger.warning("No chunking service configured, skipping file: %s", path)
                return

            chunks = self._chunking_service.chunk_file(discovered_file)
            self._stats.chunks_created += len(chunks)
            logger.debug("Created %d chunks from %s", len(chunks), path)

            # 3. Embed chunks (if embedding providers available)
            if self._embedding_provider or self._sparse_provider:
                await self._embed_chunks(chunks)
                self._stats.chunks_embedded += len(chunks)
            else:
                logger.warning(
                    "No embedding providers configured, skipping embedding for: %s", path
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
                logger.debug("Indexed %d chunks to vector store from %s", len(updated_chunks), path)
            else:
                logger.warning("No vector store configured, skipping indexing for: %s", path)

            self._stats.files_processed += 1
            logger.info("Successfully processed file: %s (%d chunks)", path, len(chunks))

        except Exception:
            logger.exception("Failed to index file %s", path)
            self._stats.files_with_errors.append(path)

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
        except Exception:
            logger.exception("Failed to delete file %s", path)

    async def index(self, change: FileChange) -> None:
        """Index a single file based on a watchfiles change event.

        Enhanced version that executes full pipeline: file → chunks → embeddings → vector store.
        Handles added, modified, and deleted file events.
        """
        try:
            change_type, path_str = change
        except Exception:
            logger.exception("Invalid FileChange tuple received: %r", change)
            return

        path = Path(path_str)

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
    def prime_index(self, *, force_reindex: bool = False) -> int:
        """Perform an initial indexing pass using the configured rignore walker.

        Enhanced version with persistence support and batch processing.

        Args:
            force_reindex: If True, skip persistence checks and reindex everything

        Returns:
            Number of files indexed
        """
        if not self._walker:
            logger.warning("No walker configured, cannot prime index")
            return 0

        # Try to restore from persistence (unless force_reindex)
        if not force_reindex:
            try:
                # TODO: Implement persistence methods in next phase
                # asyncio.run(self.initialize_from_vector_store())
                # if not self._store.is_empty:
                #     logger.info("Restored index from vector store")
                #     return len(self._store)
                pass
            except Exception as e:
                logger.debug("Could not restore from persistence: %s", e)

        # Reset stats for new indexing run
        self._stats = IndexingStats()

        # Collect files to index
        files_to_index: list[Path] = []
        try:
            with contextlib.suppress(StopIteration):
                files_to_index.extend(p for p in self._walker if p and p.is_file())
        except Exception:
            logger.exception("Failure during file discovery")
            return 0

        if not files_to_index:
            logger.info("No files found to index")
            return 0

        logger.info("Discovered %d files to index", len(files_to_index))
        self._stats.files_discovered = len(files_to_index)

        # Index files in batch (synchronous wrapper for async pipeline)
        try:
            asyncio.run(self._index_files_batch(files_to_index))
        except Exception:
            logger.exception("Failure during batch indexing")

        logger.info(
            "Indexing complete: %d files processed, %d chunks created, %d indexed, %d errors in %.2fs (%.2f files/sec)",
            self._stats.files_processed,
            self._stats.chunks_created,
            self._stats.chunks_indexed,
            len(self._stats.files_with_errors),
            self._stats.elapsed_time,
            self._stats.processing_rate,
        )

        return self._stats.files_processed

    async def _index_files_batch(self, files: list[Path]) -> None:
        """Index multiple files in batch using the chunking service.

        Args:
            files: List of file paths to index
        """
        if not files:
            return

        if not self._chunking_service:
            logger.warning("No chunking service configured, cannot batch index files")
            return

        # Convert paths to DiscoveredFile objects
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

        if not discovered_files:
            logger.info("No valid files to index in batch")
            return

        # Chunk files using ChunkingService (handles parallelization)
        all_chunks: list[CodeChunk] = []
        for file_path, chunks in self._chunking_service.chunk_files(discovered_files):
            all_chunks.extend(chunks)
            self._stats.chunks_created += len(chunks)
            logger.debug("Chunked %s: %d chunks", file_path, len(chunks))

        if not all_chunks:
            logger.info("No chunks created from files")
            return

        logger.info("Created %d chunks from %d files", len(all_chunks), len(discovered_files))

        # Embed in batches of 100 chunks
        batch_size = 100
        for i in range(0, len(all_chunks), batch_size):
            batch = all_chunks[i : i + batch_size]
            try:
                await self._embed_chunks(batch)
                self._stats.chunks_embedded += len(batch)
                logger.debug("Embedded batch %d-%d (%d chunks)", i, i + len(batch), len(batch))
            except Exception:
                logger.exception("Failed to embed batch %d-%d", i, i + len(batch))

        # Retrieve updated chunks from registry
        from codeweaver.providers.embedding.registry import get_embedding_registry

        registry = get_embedding_registry()
        updated_chunks = [
            registry[chunk.chunk_id].chunk for chunk in all_chunks if chunk.chunk_id in registry
        ]

        # If no chunks were embedded, use original chunks
        if not updated_chunks:
            logger.warning("No chunks were embedded, using original chunks")
            updated_chunks = all_chunks

        # Index to vector store
        if self._vector_store:
            try:
                await self._vector_store.upsert(updated_chunks)
                self._stats.chunks_indexed = len(updated_chunks)
                logger.info("Indexed %d chunks to vector store", len(updated_chunks))
            except Exception:
                logger.exception("Failed to index to vector store")
        else:
            logger.warning("No vector store configured, skipping indexing")

        self._stats.files_processed = len(discovered_files)

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

    def save_checkpoint(self, checkpoint_path: Path | None = None) -> None:
        """Save indexing state to checkpoint file.

        TODO: Implement in T008
        - Save to index_settings["checkpoint_file"]
        - Include files_discovered, files_processed, chunks stats
        - Include error list and timestamp

        Args:
            checkpoint_path: Optional custom checkpoint file path
        """
        logger.debug("Checkpoint save not yet implemented")

    def load_checkpoint(self, _checkpoint_path: Path | None = None) -> bool:
        """Load indexing state from checkpoint file.

        TODO: Implement in T008
        - argument primarily for testing, we use the configured path in production
        - Load from index_settings["checkpoint_file"]
        - Verify settings hash matches current config
        - Skip if checkpoint >24 hours old

        Args:
            _checkpoint_path: Optional custom checkpoint file path

        Returns:
            True if checkpoint was loaded successfully
        """
        logger.debug("Checkpoint load not yet implemented")
        return False

    @property
    def is_empty(self) -> bool:
        """Check if the indexer is empty."""
        return len(self._store) == 0


class FileWatcher:
    """Main file watcher class. Wraps watchfiles.awatch."""

    _indexer: Indexer

    def __init__(
        self,
        *paths: str | Path,
        handler: Callable[[set[FileChange]], Any] | None = None,
        file_filter: watchfiles.BaseFilter | None = None,
        walker: rignore.Walker | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the FileWatcher with a path and an optional filter."""
        # If an IgnoreFilter is provided, extract its rignore walker for initial indexing.
        if walker is None and isinstance(file_filter, IgnoreFilter):
            walker = file_filter.walker
        self._indexer = Indexer(walker=walker)
        ff = cast(watchfiles.BaseFilter | None, file_filter)
        self.file_filter = ff
        self.paths = paths
        self.handler = handler or self._default_handler
        watch_kwargs: dict[str, Any] = (
            {
                # Keep a child process alive; do NOT perform indexing in the child process
                # so that state remains in the main process.
                "target": Indexer.keep_alive,
                "target_type": "function",
                "callback": self._default_handler,
                "watch_filter": ff,
                "grace_period": 20,
                "debounce": 200_000,  # milliseconds - we want to avoid rapid re-indexing but not let things go stale, either.
                "step": 15_000,  # milliseconds -- how long to wait for more changes before yielding on changes
                "ignore_permission_denied": True,
            }
            | kwargs
        )
        watch_kwargs["recursive"] = True  # we always want recursive watching
        try:
            # Perform a one-time initial indexing pass if we have a walker
            if initial_count := self._indexer.prime_index():
                logger.info("Initial indexing complete: %d files indexed", initial_count)
            self.watcher = watchfiles.arun_process(*self.paths, **watch_kwargs)
        except Exception:
            logger.exception("Something happened...")
            raise

    async def _default_handler(self, changes: set[FileChange]) -> None:
        """Default may be a strong characterization -- 'placeholder' handler."""
        for change in changes:
            logger.info("File change detected.", extra={"change": change})
            await self._indexer.index(change)

    async def run(self) -> int:
        """Run the file watcher until cancelled. Returns the reload count from arun_process."""
        return await self.watcher  # type: ignore[no-any-return]


__all__ = (
    "CodeFilter",
    "ConfigFilter",
    "DefaultFilter",
    "DocsFilter",
    "ExtensionFilter",
    "FileWatcher",
    "IgnoreFilter",
    "Indexer",
)
