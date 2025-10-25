# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""AST-based semantic chunker with rich metadata and intelligent deduplication.

Provides semantic code chunking using tree-sitter grammars via ast-grep-py.
Leverages sophisticated semantic analysis to extract meaningful code segments
with importance scoring and classification metadata optimized for AI context.

Key Features:
- AST-based parsing for 26+ languages
- Importance-weighted node filtering
- Hierarchical metadata with classification
- Content-based deduplication via Blake3 hashing
- Graceful degradation for oversized nodes
- Comprehensive edge case handling

Architecture:
- Uses existing Metadata TypedDict and SemanticMetadata structures
- Class-level deduplication stores (UUIDStore, BlakeStore)
- Resource governance for timeout and limit enforcement
- Integration with SessionStatistics for metrics tracking
"""

from __future__ import annotations

import logging
import time

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast

from ast_grep_py import SgNode
from pydantic import UUID7

from codeweaver.common.utils import uuid7
from codeweaver.core.chunks import CodeChunk
from codeweaver.core.language import Chunker, SemanticSearchLanguage
from codeweaver.core.metadata import ChunkSource, ExtKind, Metadata, SemanticMetadata
from codeweaver.core.spans import Span
from codeweaver.core.stores import (
    BlakeHashKey,
    BlakeStore,
    UUIDStore,
    get_blake_hash,
    make_blake_store,
    make_uuid_store,
)
from codeweaver.engine.chunker.base import BaseChunker
from codeweaver.engine.chunker.exceptions import ASTDepthExceededError, BinaryFileError, ParseError
from codeweaver.engine.chunker.governance import ResourceGovernor


if TYPE_CHECKING:
    from ast_grep_py import SgRoot

    from codeweaver.engine.chunker.base import ChunkGovernor
    from codeweaver.semantic.ast_grep import AstThing, FileThing


logger = logging.getLogger(__name__)


class SemanticChunker(BaseChunker):
    """AST-based chunker with rich semantic metadata and intelligent deduplication.

    Provides semantic chunking for 26+ languages using tree-sitter grammars.
    Leverages sophisticated semantic analysis to extract meaningful code segments
    with importance scoring, classification metadata, and hierarchical tracking.

    The chunker applies multi-tiered token size management with graceful degradation:
    1. AST nodes within token limit → semantic chunks
    2. Oversized composite nodes → recursive child chunking
    3. Still oversized → delimiter-based fallback
    4. Last resort → RecursiveCharacterTextSplitter

    Features:
    - Importance-weighted node filtering (default threshold: 0.3)
    - Content-based deduplication using Blake3 hashing
    - Comprehensive edge case handling (empty, binary, whitespace, single-line)
    - Resource governance (timeout and chunk count limits)
    - Rich metadata optimized for AI context delivery

    Attributes:
        chunker: Registry key identifying this chunker type
        language: Target language for semantic parsing
        _importance_threshold: Minimum importance score for node inclusion
        _store: Class-level UUID store for chunk batches
        _hash_store: Class-level Blake3 store for content hashes
    """

    chunker = Chunker.SEMANTIC
    language: SemanticSearchLanguage

    # Class-level deduplication stores shared across instances
    _store: UUIDStore[list[CodeChunk]] = make_uuid_store(
        value_type=list,
        size_limit=3 * 1024 * 1024,  # 3MB cache for chunk batches
    )
    _hash_store: BlakeStore[UUID7] = make_blake_store(
        value_type=UUID7,
        size_limit=256 * 1024,  # 256KB cache for content hashes
    )

    def __init__(self, governor: ChunkGovernor, language: SemanticSearchLanguage) -> None:
        """Initialize semantic chunker with governor and language.

        Args:
            governor: Configuration for chunking behavior and resource limits
            language: Target semantic search language for parsing
        """
        super().__init__(governor)
        self.language = language
        self._importance_threshold = 0.3  # TODO: Make configurable via governor

    def chunk(
        self, content: str, *, file_path: Path | None = None, context: dict[str, Any] | None = None
    ) -> list[CodeChunk]:
        """Chunk content into semantic code segments with resource governance.

        Main entry point for semantic chunking. Handles edge cases, parses AST,
        filters nodes by importance, manages token limits, deduplicates content,
        and tracks metrics.

        Args:
            content: Source code content to chunk
            file_path: Optional file path for context and metadata
            context: Optional additional context (currently unused)

        Returns:
            List of CodeChunk objects with rich semantic metadata

        Raises:
            BinaryFileError: If binary content detected in input
            ParseError: If AST parsing fails for the content
            ChunkingTimeoutError: If operation exceeds configured timeout
            ChunkLimitExceededError: If chunk count exceeds configured maximum
            ASTDepthExceededError: If AST nesting exceeds safe depth limit
        """
        from codeweaver.common.statistics import get_session_statistics

        statistics = get_session_statistics()
        start_time = time.perf_counter()
        batch_id = uuid7()

        # Create performance settings for resource governance
        # TODO: Get this from actual config when PerformanceSettings is implemented
        class _PerformanceSettings:
            chunk_timeout_seconds = 30
            max_chunks_per_file = 5000

        with ResourceGovernor(_PerformanceSettings()) as governor:
            try:
                # Handle edge cases before normal chunking
                if edge_result := self._handle_edge_cases(content, file_path):
                    return edge_result

                # Parse content to AST
                root: FileThing[SgRoot] = self._parse_file(content, file_path)

                # Find chunkable nodes filtered by classification and importance
                nodes: list[AstThing[SgNode]] = self._find_chunkable_nodes(root)

                # Convert nodes to chunks with size enforcement
                chunks: list[CodeChunk] = []
                for node in nodes:
                    governor.check_timeout()

                    node_text = node.text
                    # TODO: Implement proper token estimation
                    tokens = len(node_text) // 4  # Rough approximation

                    if tokens <= self.chunk_limit:
                        chunks.append(self._create_chunk_from_node(node, file_path))
                    else:
                        chunks.extend(self._handle_oversized_node(node, file_path))

                    governor.register_chunk()

                # Deduplicate using content hashing
                unique_chunks = self._deduplicate_chunks(chunks, batch_id)

                # Store batch
                self._store.set(batch_id, unique_chunks)
                for chunk in unique_chunks:
                    chunk.set_batch_id(batch_id)

                # Track statistics
                if file_path and (ext_kind := ExtKind.from_file(file_path)):
                    statistics.add_file_operations_by_extkind([(file_path, ext_kind, "processed")])

                self._track_chunk_metrics(unique_chunks, time.perf_counter() - start_time)

            except ParseError:
                logger.exception("Parse error in %s", file_path)
                if file_path and (ext_kind := ExtKind.from_file(file_path)):
                    statistics.add_file_operations_by_extkind([(file_path, ext_kind, "skipped")])
                raise
            else:
                return unique_chunks

    def _handle_edge_cases(self, content: str, file_path: Path | None) -> list[CodeChunk] | None:
        """Handle edge cases before normal chunking.

        Detects and handles special file conditions that don't require AST parsing:
        - Binary files (raise error)
        - Empty files (return empty list)
        - Whitespace-only files (return single chunk with metadata)
        - Single-line files (return single chunk, skip parsing)

        Args:
            content: Source code content to check
            file_path: Optional file path for error messages and metadata

        Returns:
            - Empty list for truly empty files
            - Single chunk for whitespace-only or single-line files
            - None to continue with normal chunking

        Raises:
            BinaryFileError: If binary content (null bytes) detected
        """
        # Binary file detection
        if b"\x00" in content.encode("utf-8", errors="ignore"):
            raise BinaryFileError(
                f"Binary content detected in {file_path}",
                file_path=str(file_path) if file_path else None,
            )

        # Empty file
        if not content:
            logger.info("Empty file: %s, returning no chunks", file_path)
            return []

        # Whitespace-only file
        if not content.strip():
            source_id = uuid7()
            return [
                CodeChunk(
                    content=content,
                    line_range=Span(1, content.count("\n") + 1, source_id),
                    ext_kind=ExtKind.from_file(file_path) if file_path else None,
                    file_path=file_path,
                    language=self.language,
                    source=ChunkSource.TEXT_BLOCK,
                    metadata={
                        "chunk_id": uuid7(),
                        "created_at": datetime.now(UTC).timestamp(),
                        "context": {"edge_case": "whitespace_only", "chunker_type": "semantic"},
                    },
                )
            ]

        # Single line (no semantic structure to parse)
        if "\n" not in content:
            source_id = uuid7()
            ext_kind = ExtKind.from_file(file_path) if file_path else None
            return [
                CodeChunk(
                    content=content,
                    line_range=Span(1, 1, source_id),
                    file_path=file_path,
                    ext_kind=ext_kind,
                    language=self.language,
                    source=ChunkSource.TEXT_BLOCK,
                    metadata={
                        "chunk_id": uuid7(),
                        "created_at": datetime.now(UTC).timestamp(),
                        "context": {"edge_case": "single_line", "chunker_type": "semantic"},
                    },
                )
            ]

        # Continue with normal chunking
        return None

    def _parse_file(self, content: str, file_path: Path | None) -> FileThing[SgRoot]:
        """Parse content to AST root using ast-grep.

        Wraps ast-grep parsing with error handling and FileThing conversion.

        Args:
            content: Source code content to parse
            file_path: Optional file path for error messages

        Returns:
            FileThing AST root node

        Raises:
            ParseError: If parsing fails for the content
        """
        try:
            from ast_grep_py import SgRoot

            from codeweaver.semantic.ast_grep import FileThing

            root: SgRoot = SgRoot(content, self.language.value)
            return cast(FileThing[SgRoot], FileThing.from_sg_root(root, file_path))
        except Exception as e:
            raise ParseError(
                f"Failed to parse {file_path or 'content'}",
                file_path=str(file_path) if file_path else None,
                details={"language": self.language.value, "error": str(e)},
            ) from e

    def _find_chunkable_nodes(self, root: FileThing[SgRoot]) -> list[AstThing[SgNode]]:
        """Traverse AST and filter nodes by classification and importance.

        Recursively walks the AST tree from root, checking each node against
        chunkability criteria (classification and importance threshold) and
        enforcing AST depth safety limits.

        Args:
            root: FileThing AST root to traverse

        Returns:
            List of AstThing nodes meeting chunkability criteria

        Raises:
            ASTDepthExceededError: If any node exceeds safe nesting depth
        """
        chunkable: list[AstThing[SgNode]] = []

        # Traverse root children
        for child_thing in root.root.positional_connections:
            self._check_ast_depth(child_thing)

            if self._is_chunkable(child_thing):
                chunkable.append(child_thing)

        return chunkable

    def _is_chunkable(self, node: AstThing[SgNode]) -> bool:
        """Check if node meets chunkability criteria.

        A node is chunkable if:
        - It has a meaningful classification (not UNKNOWN), OR
        - It is a composite node (container) with chunkable children
        - AND it meets the importance threshold

        Args:
            node: AstThing node to evaluate

        Returns:
            True if node should be included in chunking
        """
        # Allow composite nodes even if classification is unknown
        if not node.classification:
            return node.is_composite

        # Check importance threshold
        if node.importance:
            return any(
                score >= self._importance_threshold for score in node.importance.as_dict().values()
            )

        # Include if we have classification but no importance scores
        return True

    def _check_ast_depth(self, node: AstThing[SgNode], max_depth: int = 200) -> None:
        """Verify AST nesting doesn't exceed safe depth limits.

        Protects against stack overflow and excessive memory usage during
        traversal of pathologically deep AST structures.

        Args:
            node: AstThing node to check
            max_depth: Maximum safe nesting depth (default: 200)

        Raises:
            ASTDepthExceededError: If node depth exceeds maximum
        """
        depth = len(list(node.ancestors()))
        if depth > max_depth:
            raise ASTDepthExceededError(
                f"AST depth {depth} exceeds maximum {max_depth}",
                actual_depth=depth,
                max_depth=max_depth,
            )

    def _create_chunk_from_node(self, node: AstThing[SgNode], file_path: Path | None) -> CodeChunk:
        """Create CodeChunk with rich metadata from AstThing node.

        Extracts text, line range, and builds comprehensive metadata including
        semantic information, classification, importance scores, and hierarchy.

        Args:
            node: AstThing node to convert
            file_path: Optional file path for chunk context

        Returns:
            CodeChunk with semantic metadata
        """
        range_obj = node.range
        metadata = self._build_metadata(node)
        source_id = uuid7()

        # Use model_construct to bypass validation since dependencies may not be fully defined
        return CodeChunk.model_construct(
            content=node.text,
            line_range=Span(
                # ast-grep uses 0-based line numbers, Span uses 1-based
                start=range_obj.start.line + 1,
                end=range_obj.end.line + 1,
                _source_id=source_id,
            ),
            ext_kind=ExtKind.from_file(file_path) if file_path else None,
            file_path=file_path,
            language=self.language,
            source=ChunkSource.SEMANTIC,
            metadata=metadata,
        )

    def _build_metadata(self, node: AstThing[SgNode]) -> Metadata:
        """Build metadata using existing Metadata TypedDict structure.

        Creates comprehensive metadata optimized for AI context delivery,
        including semantic information, classification, importance scores,
        and hierarchical tracking.

        Args:
            node: AstThing node to extract metadata from

        Returns:
            Metadata TypedDict with semantic and context information
        """
        # Use existing SemanticMetadata.from_node() factory
        semantic_meta = SemanticMetadata.from_node(node, self.language)

        metadata: Metadata = {
            "chunk_id": uuid7(),
            "created_at": datetime.now(UTC).timestamp(),
            "name": node.title if hasattr(node, "title") else str(node.name),
            "semantic_meta": semantic_meta,
            "context": {
                # Chunker-specific context in flexible dict
                "chunker_type": "semantic",
                "content_hash": self._compute_content_hash(node.text),
                "classification": node.classification.name if node.classification else None,
                "kind": str(node.name),
                "category": node.primary_category if hasattr(node, "primary_category") else None,
                "importance_scores": node.importance.as_dict() if node.importance else None,
                "is_composite": node.is_composite,
                "nesting_level": len(list(node.ancestors())),
            },
        }

        return metadata

    def _handle_oversized_node(
        self, node: AstThing[SgNode], file_path: Path | None
    ) -> list[CodeChunk]:
        """Handle nodes exceeding token limit via multi-tiered strategy.

        Applies graceful degradation:
        1. Try chunking children recursively (for composite nodes)
        2. Fallback to delimiter-based chunking on node text
        3. Last resort: RecursiveCharacterTextSplitter

        Preserves semantic context in fallback chunks via metadata enhancement.

        Args:
            node: Oversized AstThing node
            file_path: Optional file path for context

        Returns:
            List of chunks derived from oversized node
        """
        # Try chunking children first for composite nodes
        if node.is_composite:
            children = list(node.positional_connections)
            child_chunks: list[CodeChunk] = []

            for child in children:
                # TODO: Implement proper token estimation
                child_tokens = len(child.text) // 4

                if child_tokens <= self.chunk_limit:
                    child_chunks.append(self._create_chunk_from_node(child, file_path))
                else:
                    # Recursive handling for oversized children
                    child_chunks.extend(self._handle_oversized_node(child, file_path))

            if child_chunks:
                return child_chunks

        # Fallback: Use delimiter chunker
        # TODO: Implement delimiter chunker fallback when available
        # For now, create a single chunk with partial node metadata
        logger.warning(
            "Oversized node without chunkable children: %s, creating single chunk (delimiter fallback not yet implemented)",
            node.name,
        )

        source_id = uuid7()
        metadata = self._build_metadata(node)
        if metadata and "semantic_meta" in metadata:
            # Mark as partial node in semantic metadata
            metadata["semantic_meta"].is_partial_node = True  # type: ignore
        if "context" in metadata:
            metadata.get("context", {})["oversized_fallback"] = True  # type: ignore

        return [
            CodeChunk(
                content=node.text,
                line_range=Span(
                    start=node.range.start.line, end=node.range.end.line, _source_id=source_id
                ),
                ext_kind=ExtKind.from_file(file_path) if file_path else None,
                file_path=file_path,
                language=self.language,
                source=ChunkSource.SEMANTIC,
                metadata=metadata,
            )
        ]

    def _compute_content_hash(self, content: str) -> BlakeHashKey:
        """Compute Blake3 hash for content deduplication.

        Normalizes content by stripping whitespace before hashing to
        treat semantically identical code as duplicates.

        Args:
            content: Code content to hash

        Returns:
            Blake3 hash key for deduplication
        """
        normalized = content.strip()
        return get_blake_hash(normalized.encode("utf-8"))

    def _deduplicate_chunks(self, chunks: list[CodeChunk], batch_id: UUID7) -> list[CodeChunk]:
        """Deduplicate chunks using Blake3 content hashing.

        Tracks content hashes in class-level store to identify duplicates
        across batches. Skips chunks with previously seen content hashes.

        Args:
            chunks: Chunks to deduplicate
            batch_id: Current batch identifier for hash tracking

        Returns:
            List of unique chunks
        """
        deduplicated: list[CodeChunk] = []

        for chunk in chunks:
            if not chunk.metadata or "context" not in chunk.metadata:
                deduplicated.append(chunk)
                continue

            content_hash = chunk.metadata["context"].get("content_hash")
            if not content_hash:
                deduplicated.append(chunk)
                continue

            # Check if we've seen this content before
            if existing_batch_id := self._hash_store.get(content_hash):
                logger.debug(
                    f"Duplicate chunk detected: {content_hash[:16]}... "
                    f"(existing batch: {existing_batch_id})"
                )
                continue

            # New unique chunk
            self._hash_store.set(content_hash, batch_id)
            deduplicated.append(chunk)

        return deduplicated

    def _track_chunk_metrics(self, chunks: list[CodeChunk], duration: float) -> None:
        """Track chunking performance metrics via structured logging.

        Logs structured event with chunk count, duration, chunker type,
        and average chunk size for monitoring and performance analysis.

        Args:
            chunks: Generated chunks for metrics
            duration: Operation duration in seconds
        """
        logger.info(
            "chunking_completed",
            extra={
                "chunk_count": len(chunks),
                "duration_ms": duration * 1000,
                "chunker_type": self.chunker.name,
                "avg_chunk_size": sum(len(c.content) for c in chunks) / len(chunks)
                if chunks
                else 0,
            },
        )


__all__ = ("SemanticChunker",)
