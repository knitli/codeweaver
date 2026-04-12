# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Indexing service for orchestrating file discovery, chunking, embedding, and storage."""

from __future__ import annotations

import asyncio
import logging
import multiprocessing
import threading

from pathlib import Path
from typing import TYPE_CHECKING, Any, Protocol

import rignore

from codeweaver.core import INJECTED, DiscoveredFile, get_blake_hash, set_relative_path
from codeweaver.core.constants import (
    FILE_BATCH_SIZE,
    MAX_INLINE_CONTENT_SIZE,
    PRIMARY_SPARSE_VECTOR_NAME,
    ZERO,
)
from codeweaver.core.discovery import compute_semantic_file_hash
from codeweaver.providers import EmbeddingRegistryDep


if TYPE_CHECKING:
    from codeweaver.core import CodeChunk
    from codeweaver.core.ui_protocol import ProgressReporter
    from codeweaver.engine.config import IndexerSettings
    from codeweaver.engine.managers.checkpoint_manager import CheckpointManager, IndexingCheckpoint
    from codeweaver.engine.managers.manifest_manager import FileManifestManager, IndexFileManifest
    from codeweaver.engine.managers.progress_tracker import IndexingProgressTracker, IndexingStats
    from codeweaver.engine.services.chunking_service import ChunkingService
    from codeweaver.engine.watcher.types import FileChange
    from codeweaver.providers import EmbeddingProvider, VectorStoreProvider


logger = logging.getLogger(__name__)


class ProgressCallback(Protocol):
    """Protocol for progress callback functions."""

    def __call__(
        self, phase: str, current: int, total: int, *, extra: dict[str, Any] | None = None
    ) -> None:
        """Report progress update."""
        ...


class IndexingService:
    """Orchestrates the indexing workflow.

    Responsibilities:
    - Coordinate file discovery → chunking → embedding → storage
    - Manage checkpointing at intervals
    - Update file manifest
    - Report progress
    """

    def __init__(
        self,
        chunking_service: ChunkingService,
        embedding_provider: EmbeddingProvider | None,
        sparse_provider: EmbeddingProvider | None,
        vector_store: VectorStoreProvider | None,
        settings: IndexerSettings,
        progress_reporter: ProgressReporter,
        progress_tracker: IndexingProgressTracker,
        checkpoint_manager: CheckpointManager,
        manifest_manager: FileManifestManager,
        project_path: Path,
    ):
        """Initialize indexing service with required dependencies."""
        self._chunking_service = chunking_service
        self._embedding_provider = embedding_provider
        self._sparse_provider = sparse_provider
        self._vector_store = vector_store
        self._settings = settings
        self._progress_reporter = progress_reporter
        self._progress_tracker = progress_tracker
        self._checkpoint_manager = checkpoint_manager
        self._manifest_manager = manifest_manager
        self._project_path = project_path.resolve()

        # Operational state
        self._file_manifest: IndexFileManifest | None = None
        self._current_checkpoint: IndexingCheckpoint | None = None
        self._manifest_lock = asyncio.Lock()
        self._duplicate_dense_count = ZERO
        self._duplicate_sparse_count = ZERO
        self._deleted_files: list[Path] = []

        # Concurrency control
        self._max_concurrent_batches = settings.max_concurrent_batches
        self._indexing_semaphore = asyncio.Semaphore(self._max_concurrent_batches)
        self._consumer_batch_size = self._calculate_consumer_batch_size()

    def _calculate_consumer_batch_size(self) -> int:
        """Calculate optimal consumer batch size based on available CPU cores."""
        try:
            cpu_count = multiprocessing.cpu_count()
        except NotImplementedError:
            cpu_count = 4
        # We want roughly 4-8 files per core per batch to keep overhead low
        # but throughput high. Min 10, Max 100.
        return max(10, min(100, cpu_count * 4))

    @property
    def stats(self) -> IndexingStats:
        """Get current indexing statistics."""
        return self._progress_tracker.get_stats()

    async def process_changes(self, changes: list[FileChange]) -> int:
        """Process a batch of file changes (incremental indexing)."""
        from watchfiles import Change

        # Ensure manifest is loaded
        if self._file_manifest is None:
            self._file_manifest = (
                await self._manifest_manager.load() or self._manifest_manager.create_new()
            )

        files_to_index: list[Path] = []
        files_to_delete: list[Path] = []

        for change_type, path_str in changes:
            path = Path(path_str)
            if change_type == Change.deleted:
                files_to_delete.append(path)
            else:
                files_to_index.append(path)

        # Handle deletions
        if files_to_delete:
            self._deleted_files.extend(files_to_delete)
            await self._cleanup_deleted_files()

        # Handle updates
        if files_to_index:
            await self._perform_batch_indexing(files_to_index, progress_callback=None)

        return len(files_to_index) + len(files_to_delete)

    async def index_project(
        self,
        *,
        force_reindex: bool = False,
        add_dense: bool = True,
        add_sparse: bool = True,
        progress_callback: ProgressCallback | None = None,
    ) -> int:
        """Index the project codebase.

        Args:
            force_reindex: If True, skip persistence checks and reindex everything
            add_dense: Whether to add dense embeddings
            add_sparse: Whether to add sparse embeddings
            progress_callback: Optional granular progress callback

        Returns:
            Number of files indexed
        """
        self._progress_tracker.update_phase("discovery")

        # 1. Load manifest
        if not force_reindex:
            self._file_manifest = await self._manifest_manager.load()

        if self._file_manifest is None:
            self._file_manifest = self._manifest_manager.create_new()

        # 2. Setup streaming pipeline
        # Now passing a tuple of (Path, bytes | None) to avoid redundant I/O
        queue: asyncio.Queue[tuple[Path, bytes | None] | None] = asyncio.Queue(
            maxsize=self._settings.max_queue_size
        )

        # Start workers
        discovery_task = asyncio.create_task(self._discovery_worker(queue, progress_callback))
        indexing_task = asyncio.create_task(
            self._indexing_worker(queue, self._indexing_semaphore, progress_callback)
        )

        self._progress_tracker.update_phase("indexing")

        # 3. Wait for discovery to complete
        await discovery_task

        # 4. Wait for indexing to finish consuming the queue
        await queue.join()
        await indexing_task

        # 5. Clean up deleted files (detected during discovery)
        if self._deleted_files:
            await self._cleanup_deleted_files()

        # 6. Finalize
        await self._manifest_manager.save(self._file_manifest)
        await self._checkpoint_manager.delete()  # Clear checkpoint on success

        self._progress_tracker.update_phase("complete")

        return self.stats.files_discovered

    async def _discovery_worker(
        self,
        queue: asyncio.Queue[tuple[Path, bytes | None] | None],
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        """Producer: Walks filesystem and identifies files needing indexing."""
        from queue import Queue as SyncQueue

        walker_settings = self._settings._as_settings(project_path=self._project_path)
        loop = asyncio.get_running_loop()

        # Thread-safe queue for streaming paths from discovery thread
        path_queue: SyncQueue[Path | None] = SyncQueue(maxsize=1000)

        def _walker_thread() -> None:
            """Background thread for blocking filesystem walk."""
            try:
                walker = rignore.Walker(**walker_settings)
                for p in walker:
                    if p and p.exists() and p.is_file():
                        path_queue.put(p)
            except Exception:
                logger.exception("Error in filesystem walker thread")
            finally:
                path_queue.put(None)

        # Start walker thread
        threading.Thread(target=_walker_thread, daemon=True).start()

        current_models = self._get_current_embedding_models()
        batch_size = FILE_BATCH_SIZE
        files_discovered_count = ZERO
        seen_files: set[Path] = set()
        current_batch: list[Path] = []

        while True:
            # Get next path from thread (offload the blocking get)
            path = await loop.run_in_executor(None, path_queue.get)

            if path is None:
                # End of walk - process final partial batch
                if current_batch:
                    files_discovered_count += await self._process_discovery_batch(
                        current_batch, seen_files, current_models, queue
                    )
                break

            current_batch.append(path)

            if len(current_batch) >= batch_size:
                files_discovered_count += await self._process_discovery_batch(
                    current_batch, seen_files, current_models, queue
                )
                current_batch = []

                if progress_callback:
                    # Approximation: we don't know the total files yet in streaming mode
                    # Use 0 or -1 to indicate streaming/unknown total if protocol allows,
                    # or just report current count.
                    progress_callback("discovery", files_discovered_count, 0)

            # Cooperative yield
            await asyncio.sleep(0)

        # Handle deleted files by comparing seen set with manifest
        if not self._file_manifest:
            self._file_manifest = self._manifest_manager.create_new()
        manifest_files = self._file_manifest.get_all_file_paths()
        deleted_relative = manifest_files - seen_files
        self._deleted_files = [self._project_path / rel for rel in deleted_relative]

        self.stats.files_discovered = files_discovered_count

        # Signal completion to indexing worker
        await queue.put(None)

    async def _process_discovery_batch(
        self,
        batch: list[Path],
        seen_files: set[Path],
        current_models: dict[str, str | None],
        index_queue: asyncio.Queue[tuple[Path, bytes | None] | None],
    ) -> int:
        """Process a batch of discovered files: hash, check manifest, and queue."""

        def _hash_batch(paths: list[Path]) -> list[tuple[Path, bytes]]:
            return [(p, p.read_bytes()) for p in paths]

        # Offload hashing I/O to thread
        hashed_batch = await asyncio.to_thread(_hash_batch, batch)

        queued_count = 0

        for path, content_bytes in hashed_batch:
            relative_path = set_relative_path(path, base_path=self._project_path)
            if not relative_path:
                # Pass small content through to avoid re-reading
                inline_content = (
                    content_bytes if len(content_bytes) <= MAX_INLINE_CONTENT_SIZE else None
                )
                await index_queue.put((path, inline_content))
                queued_count += 1
                continue

            seen_files.add(relative_path)
            current_hash = compute_semantic_file_hash(content_bytes, path)
            if not self._file_manifest:
                self._file_manifest = self._manifest_manager.create_new()
            needs_reindex, _ = self._file_manifest.file_needs_reindexing(
                relative_path,
                current_hash,
                current_dense_provider=current_models["dense_provider"],
                current_dense_model=current_models["dense_model"],
                current_sparse_provider=current_models["sparse_provider"],
                current_sparse_model=current_models["sparse_model"],
            )

            if needs_reindex:
                # Optimized: Pass already-read content if it's not too large
                inline_content = (
                    content_bytes if len(content_bytes) <= MAX_INLINE_CONTENT_SIZE else None
                )
                await index_queue.put((path, inline_content))
                queued_count += 1

        return queued_count

    async def _indexing_worker(
        self,
        queue: asyncio.Queue[tuple[Path, bytes | None] | None],
        semaphore: asyncio.Semaphore,
        progress_callback: ProgressCallback | None = None,
    ) -> None:
        """Consumer: Pulls files from queue and processes them in batches."""
        batch_size = self._consumer_batch_size
        current_batch: list[tuple[Path, bytes | None]] = []
        indexing_tasks = []

        while True:
            item = await queue.get()

            if item is None:
                # Sentinel received
                if current_batch:
                    # Final partial batch
                    task = asyncio.create_task(
                        self._run_guarded_index_batch(
                            current_batch, self._indexing_semaphore, progress_callback
                        )
                    )
                    indexing_tasks.append(task)

                queue.task_done()
                break

            current_batch.append(item)

            if len(current_batch) >= batch_size:
                # Process batch (under semaphore)
                task = asyncio.create_task(
                    self._run_guarded_index_batch(
                        current_batch.copy(), self._indexing_semaphore, progress_callback
                    )
                )
                indexing_tasks.append(task)
                current_batch = []

            queue.task_done()

        # Wait for all indexing tasks to complete
        if indexing_tasks:
            await asyncio.gather(*indexing_tasks)

    async def _run_guarded_index_batch(
        self,
        batch: list[tuple[Path, bytes | None]],
        semaphore: asyncio.Semaphore,
        progress_callback: ProgressCallback | None,
    ) -> None:
        """Run a single indexing batch guarded by a semaphore."""
        async with semaphore:
            await self._index_files_batch(batch, progress_callback)

    async def _perform_batch_indexing(
        self, files: list[Path], progress_callback: ProgressCallback | None
    ) -> None:
        """Process files in batches through the pipeline."""
        # Note: process_changes uses this for incremental updates from watcher.
        # It currently doesn't have the bytes, so we pass None for content.
        batch_size = 50
        tasks = []
        for i in range(0, len(files), batch_size):
            batch = [(p, None) for p in files[i : i + batch_size]]
            task = asyncio.create_task(
                self._run_guarded_index_batch(batch, self._indexing_semaphore, progress_callback)
            )
            tasks.append(task)

        if tasks:
            await asyncio.gather(*tasks)

    async def _index_files_batch(
        self, batch: list[tuple[Path, bytes | None]], progress_callback: ProgressCallback | None
    ) -> None:
        """Index a single batch of files."""

        def _collect_discovered_files() -> list[DiscoveredFile]:
            results = []
            for path, content in batch:
                if content is not None:
                    # Optimized: Use existing bytes to avoid re-reading and re-hashing
                    # Note: We still use is_path_text for safety, but it's now against memory
                    if DiscoveredFile.is_path_binary(path):
                        continue

                    df = DiscoveredFile(
                        path=path,
                        file_hash=get_blake_hash(content),
                        project_path=self._project_path,
                    )
                    results.append(df)
                else:
                    # Fallback for large files or watcher updates
                    if DiscoveredFile.is_path_text(path) and (
                        df := DiscoveredFile.from_path(path, project_path=self._project_path)
                    ):
                        results.append(df)
            return results

        discovered_files = await asyncio.to_thread(_collect_discovered_files)

        if not discovered_files:
            return

        # Clean up old chunks for files being re-indexed
        if self._vector_store:
            # OPTIMIZATION: Batch deletion of chunks for the entire file list
            await self._vector_store.delete_by_files([df.path for df in discovered_files])

        self.stats.files_processed += len(discovered_files)

        # Chunk
        all_chunks: list[CodeChunk] = []
        async for _, chunks in self._chunking_service.chunk_files(discovered_files):
            all_chunks.extend(chunks)

        self.stats.chunks_created += len(all_chunks)

        if progress_callback:
            progress_callback(
                "chunking",
                len(discovered_files),
                len(discovered_files),
                extra={"chunks_created": len(all_chunks)},
            )

        # Embed
        if self._embedding_provider or self._sparse_provider:
            await self._embed_chunks(all_chunks)

        self.stats.chunks_embedded += len(all_chunks)

        # Retrieve embedded chunks from registry
        from codeweaver.providers.embedding import get_embedding_registry

        registry = get_embedding_registry()
        updated_chunks = [
            registry[chunk.chunk_id].chunk for chunk in all_chunks if chunk.chunk_id in registry
        ] or all_chunks

        # Index
        if self._vector_store:
            await self._vector_store.upsert(updated_chunks)
            self.stats.chunks_indexed += len(updated_chunks)

        # Update manifest
        model_info = self._get_current_embedding_models()
        manifest_updates = []

        for df in discovered_files:
            rel_path = set_relative_path(df.path, base_path=self._project_path)
            if not rel_path:
                continue

            file_chunk_ids = [str(c.chunk_id) for c in updated_chunks if c.file_path == df.path]
            manifest_updates.append({
                "path": rel_path,
                "content_hash": df.file_hash,
                "chunk_ids": file_chunk_ids,
                "dense_embedding_provider": model_info["dense_provider"],
                "dense_model": model_info["dense_model"],
                "sparse_provider": model_info["sparse_provider"],
                "sparse_model": model_info["sparse_model"],
                "has_dense_embeddings": bool(self._embedding_provider),
                "has_sparse_embeddings": bool(self._sparse_provider),
            })

        if manifest_updates:
            if not self._file_manifest:
                self._file_manifest = self._manifest_manager.create_new()
            async with self._manifest_lock:
                self._file_manifest.add_files_batch(manifest_updates)

    async def _embed_chunks(self, chunks: list[CodeChunk]) -> None:
        """Generate embeddings for chunks."""
        from codeweaver.providers.embedding import get_embedding_registry

        registry = get_embedding_registry()

        if self._embedding_provider and (
            needing_dense := [
                c
                for c in chunks
                if c.chunk_id not in registry or not registry[c.chunk_id].has_dense
            ]
        ):
            await self._embedding_provider.embed_documents(needing_dense)

        if self._sparse_provider and (
            needing_sparse := [
                c
                for c in chunks
                if c.chunk_id not in registry or not registry[c.chunk_id].has_sparse
            ]
        ):
            await self._sparse_provider.embed_documents(needing_sparse)

    async def _cleanup_deleted_files(self) -> None:
        """Remove deleted files from vector store and manifest."""
        if not self._deleted_files:
            return

        rel_paths: list[Path] = [
            rel_path
            for path in self._deleted_files
            if (rel_path := set_relative_path(path, base_path=self._project_path))
        ]

        if self._vector_store and rel_paths:
            await self._vector_store.delete_by_files(rel_paths)

        if self._file_manifest:
            for rel_path in rel_paths:
                async with self._manifest_lock:
                    self._file_manifest.remove_file(rel_path)

        self._deleted_files = []

    async def reconcile_from_backup(self, backup_store: VectorStoreProvider) -> None:
        """Reconcile primary index from backup store after failover recovery.

        This handles the "Smart Promote" logic:
        1. If models match, zero-cost copy vectors.
        2. If chunks are compatible (fit in context), reuse text and re-embed.
        3. If incompatible, fall back to standard indexing (via manifest status).
        """
        if not self._vector_store:
            return

        logger.info("Starting reconciliation from backup store...")
        self._progress_tracker.update_phase("reconciliation")

        # 1. Get model information directly from vector store properties
        try:
            primary_dense = self._vector_store.dense_model
            primary_sparse = self._vector_store.sparse_model
            backup_dense = backup_store.dense_model
            backup_sparse = backup_store.sparse_model
        except Exception:
            logger.warning(
                "Could not compare collection models, assuming incompatible.", exc_info=True
            )
            # Fallback: force re-index via standard mechanism
            return

        models_match = primary_dense == backup_dense and primary_sparse == backup_sparse
        sparse_match = primary_sparse == backup_sparse

        # 2. Iterate Backup Content
        offset = None
        while True:
            # Scroll returns (points, next_offset)
            batch, offset = await backup_store.client.scroll(limit=100, offset=offset)
            if not batch:
                break

            await self._process_backup_batch(
                batch, models_match=models_match, sparse_match=sparse_match
            )

            if offset is None:
                break

        # After processing backup, run standard index pass to ensure consistency
        await self.index_project()

    async def _process_backup_batch(
        self,
        batch: list[Any],
        *,
        models_match: bool,
        sparse_match: bool = False,
        registry: EmbeddingRegistryDep = INJECTED,
    ) -> None:
        """Process a single batch of backup content for reconciliation."""
        from codeweaver.providers.embedding import get_embedding_registry

        # Extract chunks and sparse vectors from batch
        chunks, sparse_vectors = self._extract_chunks_from_batch(batch)
        if not chunks:
            return

        registry = get_embedding_registry()

        # Inject sparse vectors if available and model matches
        if sparse_match and sparse_vectors:
            self._inject_sparse_vectors(chunks, sparse_vectors, registry)

        # Index compatible chunks
        await self._index_compatible_chunks(chunks)

    def _extract_chunks_from_batch(
        self, batch: list[Any]
    ) -> tuple[list[CodeChunk], dict[str, Any]]:
        """Extract chunks and sparse vectors from batch points.

        Returns tuple of (chunks, sparse_vectors) where sparse_vectors maps
        chunk_id to sparse vector data.
        """
        chunks: list[CodeChunk] = []
        sparse_vectors: dict[str, Any] = {}

        for point in batch:
            if not hasattr(point.payload, "chunk"):
                continue

            chunk = self._deserialize_chunk(point.payload.chunk)
            chunks.append(chunk)

            # Extract sparse vector if available
            sparse_vec = self._extract_sparse_vector(point)
            if sparse_vec is not None:
                sparse_vectors[str(chunk.chunk_id)] = sparse_vec

        return chunks, sparse_vectors

    def _deserialize_chunk(self, chunk: Any) -> CodeChunk:
        """Deserialize chunk from payload if needed."""
        from codeweaver.core import CodeChunk

        return CodeChunk.model_validate(chunk) if isinstance(chunk, dict) else chunk

    def _extract_sparse_vector(self, point: Any) -> Any | None:
        """Extract sparse vector from point if available."""
        if not hasattr(point, "vector"):
            return None

        vector = point.vector
        return vector.get(PRIMARY_SPARSE_VECTOR_NAME) if isinstance(vector, dict) else None

    def _inject_sparse_vectors(
        self, chunks: list[CodeChunk], sparse_vectors: dict[str, Any], registry: Any
    ) -> None:
        """Inject sparse vectors into embedding registry.

        Converts Qdrant sparse vectors to SparseEmbedding format and registers
        them for reuse during reconciliation.
        """
        from codeweaver.core import uuid7

        migration_batch_id = uuid7()

        for i, chunk in enumerate(chunks):
            sparse_vec = sparse_vectors.get(str(chunk.chunk_id))
            if sparse_vec is None:
                continue

            try:
                self._register_sparse_embedding(chunk, sparse_vec, migration_batch_id, i, registry)
            except Exception:
                logger.debug(
                    "Failed to inject sparse vector for chunk %s", chunk.chunk_id, exc_info=True
                )

    def _register_sparse_embedding(
        self, chunk: CodeChunk, sparse_vec: Any, batch_id: Any, batch_index: int, registry: Any
    ) -> None:
        """Register a single sparse embedding in the registry."""
        from codeweaver.core import (
            ChunkEmbeddings,
            CodeWeaverSparseEmbedding,
            EmbeddingBatchInfo,
            ModelName,
        )

        # Convert Qdrant SparseVector to SparseEmbedding
        indices = getattr(sparse_vec, "indices", None) or sparse_vec.get("indices")
        values = getattr(sparse_vec, "values", None) or sparse_vec.get("values")
        sparse_emb = CodeWeaverSparseEmbedding(indices=indices, values=values)

        # Create embedding info with current sparse provider model
        model = (
            ModelName(self._sparse_provider.model_name)
            if self._sparse_provider
            else ModelName("unknown")
        )
        info = EmbeddingBatchInfo.create_sparse(
            batch_id=batch_id,
            batch_index=batch_index,
            chunk_id=chunk.chunk_id,
            model=model,
            embeddings=sparse_emb,
            dtype="float16",
        )

        # Add to registry
        if chunk.chunk_id in registry:
            registry[chunk.chunk_id] = registry[chunk.chunk_id].add(info)
        else:
            registry[chunk.chunk_id] = ChunkEmbeddings(chunk=chunk).add(info)

    async def _index_compatible_chunks(self, chunks: list[CodeChunk]) -> None:
        """Index chunks from backup store for reconciliation."""
        # Generate embeddings if providers available
        if self._embedding_provider or self._sparse_provider:
            await self._embed_chunks(chunks)

        # Upsert to vector store
        if self._vector_store:
            await self._vector_store.upsert(chunks)
            self.stats.chunks_indexed += len(chunks)

    def _get_current_embedding_models(self) -> dict[str, str | None]:
        """Helper to get model info for manifest updates."""
        return {
            "dense_provider": self._embedding_provider.name.variable
            if self._embedding_provider
            else None,
            "dense_model": str(self._embedding_provider.model_name)
            if self._embedding_provider
            else None,
            "sparse_provider": self._sparse_provider.name.variable
            if self._sparse_provider
            else None,
            "sparse_model": str(self._sparse_provider.model_name)
            if self._sparse_provider
            else None,
        }


__all__ = ("IndexingService", "ProgressCallback")
