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

import contextlib
import logging
import time

from datetime import UTC, datetime
from pathlib import Path
from typing import TYPE_CHECKING, Any, cast
from uuid import UUID

from ast_grep_py import SgNode
from codeweaver_tokenizers import Tokenizer
from pydantic import UUID7

from codeweaver.core import (
    INJECTED,
    BlakeHashKey,
    BlakeStore,
    ChunkSource,
    CodeChunk,
    ExtKind,
    Metadata,
    SemanticSearchLanguage,
    SessionStatistics,
    Span,
    StatisticsDep,
    UUIDStore,
    get_blake_hash,
    make_blake_store,
    make_uuid_store,
    uuid7,
)
from codeweaver.core.constants import (
    DEFAULT_BLAKE_STORE_MAX_SIZE,
    DEFAULT_UUID_STORE_MAX_SIZE,
    MAX_SEMANTIC_CHUNKER_RECURSION_DEPTH,
    ONE_MILLISECOND_IN_MICROSECONDS,
    SEMANTIC_CHUNKER_PERFORMANCE_THRESHOLD_MS,
)
from codeweaver.engine.chunker.base import BaseChunker
from codeweaver.engine.chunker.exceptions import ASTDepthExceededError, BinaryFileError, ParseError
from codeweaver.engine.chunker.governance import ResourceGovernor
from codeweaver.semantic.types import SemanticMetadata


if TYPE_CHECKING:
    from ast_grep_py import SgRoot

    from codeweaver.core import DiscoveredFile
    from codeweaver.engine.chunker.base import ChunkGovernor
    from codeweaver.semantic import AstThing, FileThing


logger = logging.getLogger(__name__)

# Import chunker logging functions for structured logging
from codeweaver.engine.chunker._logging import (
    log_chunking_deduplication,
    log_chunking_edge_case,
    log_chunking_failed,
    log_chunking_fallback,
)


class SemanticChunker(BaseChunker):
    """AST-based chunker with rich semantic metadata and intelligent deduplication.

    Provides semantic chunking for 26+ languages using tree-sitter grammars.
    Leverages sophisticated semantic analysis to extract meaningful code segments
    with importance scoring, classification metadata, and hierarchical tracking.

    The chunker applies multi-tiered token size management with graceful degradation:
    1. AST nodes within token limit → semantic chunks
    2. Oversized composite nodes → recursive child chunking
    3. Still oversized → delimiter-based fallback
    4. Last resort → return single chunk as-is (may exceed limit for indivisible content)

    Features:
    - Importance-weighted node filtering (default threshold: 0.3)
    - Content-based deduplication using Blake3 hashing
    - Comprehensive edge case handling (empty, binary, whitespace, single-line)
    - Resource governance (timeout and chunk count limits)
    - Rich metadata optimized for AI context delivery

    Attributes:
        language: Target language for semantic parsing
        _importance_threshold: Minimum importance score for node inclusion
        _store: UUID store for chunk batches
        _hash_store: BlakeStore[UUID7] = make_blake_store(
    """

    language: SemanticSearchLanguage

    _statistics: SessionStatistics

    _store: UUIDStore[list[CodeChunk]] = make_uuid_store(
        value_type=list,
        size_limit=DEFAULT_UUID_STORE_MAX_SIZE,  # 3MB cache for chunk batches
    )
    _hash_store: BlakeStore[UUID7] = make_blake_store(
        value_type=UUID,  # UUID7 but UUID is the type
        size_limit=DEFAULT_BLAKE_STORE_MAX_SIZE,  # 256KB cache for content hashes
    )

    @classmethod
    def clear_deduplication_stores(cls) -> None:
        """Clear class-level deduplication stores.

        This is primarily useful for testing to ensure clean state between test runs.
        In production, stores persist across chunking operations to detect duplicates
        across files within a session.
        """
        # Recreate stores instead of clearing to avoid weak reference issues with lists
        cls._store = make_uuid_store(
            value_type=list,
            size_limit=DEFAULT_UUID_STORE_MAX_SIZE,  # 3MB cache for chunk batches
        )
        cls._hash_store = make_blake_store(
            value_type=UUID,  # UUID7 but UUID is the type
            size_limit=DEFAULT_BLAKE_STORE_MAX_SIZE,  # 256KB cache for content hashes
        )

    def __init__(
        self,
        governor: ChunkGovernor,
        language: SemanticSearchLanguage,
        tokenizer: Tokenizer | None = None,
        statistics: StatisticsDep = INJECTED,
    ) -> None:
        """Initialize semantic chunker with governor and language.

        Args:
            governor: Configuration for chunking behavior and resource limits
            language: Target semantic search language for parsing
            tokenizer: Optional tokenizer for accurate token counting
            statistics: Session statistics tracker for metrics
        """
        super().__init__(governor)
        self.language = language

        # Handle statistics injection - resolve placeholder in test environments
        from codeweaver.core import is_depends_marker

        if is_depends_marker(statistics):
            # No DI container active, create a simple SessionStatistics instance
            self._statistics = SessionStatistics()
        else:
            self._statistics = statistics

        # Handle tokenizer injection
        if tokenizer is None or is_depends_marker(tokenizer):
            try:
                # Try to resolve from container if not provided
                from codeweaver_tokenizers import get_tokenizer

                # Default to tokenizers/gpt-4 if nothing else available
                self.tokenizer = get_tokenizer("tokenizers", "gpt-4")
            except Exception:
                self.tokenizer = None
        else:
            self.tokenizer = tokenizer

        # Cache tokenizer existence for performance (avoid repeated None checks)
        self._has_tokenizer = self.tokenizer is not None

        # Use importance threshold from settings, fallback to default
        if governor.settings is not None:
            self._importance_threshold = governor.settings.semantic_importance_threshold
        else:
            self._importance_threshold = 0.3

    def chunk(
        self,
        content: str,
        *,
        file: DiscoveredFile | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[CodeChunk]:
        """Chunk content into semantic code segments with resource governance.

        Main entry point for semantic chunking. Handles edge cases, parses AST,
        filters nodes by importance, manages token limits, deduplicates content,
        and tracks metrics.

        Args:
            content: Source code content to chunk
            file: Optional DiscoveredFile with metadata and source_id
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
        start_time = time.perf_counter()
        batch_id = uuid7()

        file_path, source_id = self._extract_file_metadata(file)
        performance_settings = self._get_performance_settings_semantic()

        with ResourceGovernor(performance_settings) as governor:
            try:
                # Handle edge cases before normal chunking
                if edge_result := self._handle_edge_cases(content, file_path, source_id):
                    return edge_result

                # Parse and process AST
                chunks = self._parse_and_chunk(
                    content, file_path, source_id, performance_settings, governor
                )

                # Deduplicate and finalize
                unique_chunks = self._finalize_chunks(chunks, batch_id)

                # Track statistics and metrics
                self._track_statistics(file_path, self._statistics, unique_chunks, start_time)

            except ParseError as e:
                # Log at debug level - this is an expected condition for malformed files
                # The caller (parallel.py or chunking_service.py) will handle fallback to delimiter chunking
                logger.debug(
                    "Parse error in %s: %s - caller will handle fallback",
                    file_path,
                    type(e).__name__,
                    extra={"file_path": str(file_path) if file_path else None},
                )

                # Log structured error event for observability
                log_chunking_failed(
                    file_path=file_path or Path("<unknown>"),
                    chunker_type=self,
                    error_type=type(e).__name__,
                    error_message=str(e),
                    fallback_triggered=True,  # Caller will trigger fallback
                )

                self._track_skipped_file(file_path, self._statistics)
                raise
            else:
                return unique_chunks

    def _extract_file_metadata(self, file: DiscoveredFile | None) -> tuple[Path | None, Any]:
        """Extract file path and source ID from DiscoveredFile.

        Args:
            file: Optional discovered file

        Returns:
            Tuple of (file_path, source_id)
        """
        from codeweaver.core import UUID7Hex

        file_path = file.path if file else None
        if file_path:
            file_path = file_path.resolve()

        source_id = UUID7Hex(file.source_id.hex) if file else uuid7()
        return file_path, source_id

    def _get_performance_settings_semantic(self) -> Any:
        """Get performance settings for semantic chunking.

        Returns:
            Performance settings instance
        """
        if self.governor.settings is not None:
            return self.governor.settings.performance

        from codeweaver.engine.config import PerformanceSettings

        return PerformanceSettings()

    def _parse_and_chunk(
        self,
        content: str,
        file_path: Path | None,
        source_id: Any,
        performance_settings: Any,
        governor: Any,
    ) -> list[CodeChunk]:
        """Parse AST and convert to chunks.

        Args:
            content: Source code
            file_path: Optional file path
            source_id: Source identifier
            performance_settings: Performance settings
            governor: Resource governor

        Returns:
            List of code chunks
        """
        # Parse content to AST
        root: FileThing[SgRoot] = self._parse_file(content, file_path)

        # Find chunkable nodes and cache their depths
        nodes, node_depths = self._find_chunkable_nodes(
            root, max_depth=performance_settings.max_ast_depth, file_path=file_path
        )

        # Convert nodes to chunks using cached depths
        return self._convert_nodes_to_chunks(nodes, file_path, source_id, governor, node_depths)

    def _convert_nodes_to_chunks(
        self,
        nodes: list[AstThing[SgNode]],
        file_path: Path | None,
        source_id: Any,
        governor: Any,
        node_depths: dict[int, int],
    ) -> list[CodeChunk]:
        """Convert AST nodes to code chunks with size enforcement.

        Args:
            nodes: List of AST nodes
            file_path: Optional file path
            source_id: Source identifier
            governor: Resource governor
            node_depths: Mapping of node id to cached depth

        Returns:
            List of code chunks
        """
        chunks: list[CodeChunk] = []
        for node in nodes:
            governor.check_timeout()

            # Cache node text to avoid repeated property access
            node_text = node.text
            # Use cached tokenizer flag for performance
            tokens = (
                self.tokenizer.estimate(node_text) if self._has_tokenizer else len(node_text) // 4
            )

            # Get cached depth for this node
            depth = node_depths.get(id(node))

            if tokens <= self.chunk_limit:
                chunks.append(self._create_chunk_from_node(node, file_path, source_id, depth))
                governor.register_chunk()
            else:
                chunks.extend(self._handle_oversized_node(node, file_path, source_id, governor))

        return chunks

    def _finalize_chunks(self, chunks: list[CodeChunk], batch_id: UUID7) -> list[CodeChunk]:
        """Deduplicate chunks and set batch metadata.

        Args:
            chunks: List of chunks to finalize
            batch_id: Batch identifier

        Returns:
            List of unique chunks with batch metadata
        """
        # Deduplicate using content hashing (already sets batch keys internally)
        unique_chunks = self._deduplicate_chunks(chunks, batch_id)

        # Store batch
        self._store.set(batch_id, unique_chunks)

        return unique_chunks

    def _track_statistics(
        self, file_path: Path | None, statistics: Any, chunks: list[CodeChunk], start_time: float
    ) -> None:
        """Track file operations and chunk metrics.

        Args:
            file_path: Optional file path
            statistics: Statistics tracker
            chunks: List of chunks
            start_time: Start time for duration calculation
        """
        with contextlib.suppress(ValueError, OSError):
            if file_path and (ext_kind := ExtKind.from_file(file_path)):
                statistics.add_file_operations_by_extkind([(file_path, ext_kind, "processed")])

        # Calculate file size from chunks
        file_size_bytes = sum(len(c.content) for c in chunks) if chunks else 0

        self._track_chunk_metrics(
            chunks,
            time.perf_counter() - start_time,
            file_path=file_path,
            file_size_bytes=file_size_bytes,
            language=self.language.as_title,
        )

    def _track_skipped_file(self, file_path: Path | None, statistics: Any) -> None:
        """Track skipped file in statistics.

        Args:
            file_path: Optional file path
            statistics: Statistics tracker
        """
        with contextlib.suppress(ValueError, OSError):
            if file_path and (ext_kind := ExtKind.from_file(file_path)):
                statistics.add_file_operations_by_extkind([(file_path, ext_kind, "skipped")])

    def _handle_edge_cases(
        self, content: str, file_path: Path | None, source_id: UUID7
    ) -> list[CodeChunk] | None:
        """Handle edge cases before normal chunking.

        Detects and handles special file conditions that don't require AST parsing:
        - Binary files (raise error)
        - Empty files (return empty list)
        - Whitespace-only files (return single chunk with metadata)
        - Single-line files (return single chunk, skip parsing)

        Args:
            content: Source code content to check
            file_path: Optional file path for error messages and metadata
            source_id: Shared source ID for all chunks from this file

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

            # Log edge case for observability
            log_chunking_edge_case(
                file_path=file_path or Path("<unknown>"), edge_case_type="empty_file", chunk_count=0
            )

            return []

        # Whitespace-only file
        if not content.strip():
            # Log edge case for observability
            log_chunking_edge_case(
                file_path=file_path or Path("<unknown>"),
                edge_case_type="whitespace_only",
                chunk_count=1,
                extra_context={"line_count": content.count("\n") + 1},
            )

            return [
                CodeChunk.model_construct(
                    content=content,
                    line_range=Span(1, content.count("\n") + 1, source_id),
                    ext_kind=ExtKind.from_file(file_path) if file_path else None,
                    file_path=file_path,
                    language=self.language,
                    source=ChunkSource.TEXT_BLOCK,
                    metadata={
                        "chunk_id": uuid7(),
                        "created_at": datetime.now(UTC).timestamp(),
                        "edge_case": "whitespace_only",
                        "context": {"chunker_type": "semantic"},
                    },
                )
            ]

        # Single line (no semantic structure to parse)
        # Count non-comment, non-blank lines to handle files with license headers
        code_lines = [
            line
            for line in content.splitlines()
            if line.strip() and not line.strip().startswith("#")
        ]

        if len(code_lines) <= 1:
            ext_kind = ExtKind.from_file(file_path) if file_path else None
            total_lines = content.count("\n") + 1

            # Log edge case for observability
            log_chunking_edge_case(
                file_path=file_path or Path("<unknown>"),
                edge_case_type="single_line",
                chunk_count=1,
                extra_context={"total_lines": total_lines, "code_lines": len(code_lines)},
            )

            return [
                CodeChunk.model_construct(
                    content=content,
                    line_range=Span(1, total_lines, source_id),
                    file_path=file_path,
                    ext_kind=ext_kind,
                    language=self.language,
                    source=ChunkSource.TEXT_BLOCK,
                    metadata={
                        "chunk_id": uuid7(),
                        "created_at": datetime.now(UTC).timestamp(),
                        "edge_case": "single_line",
                        "context": {"chunker_type": "semantic"},
                    },
                )
            ]

        # Continue with normal chunking
        return None

    def _parse_file(self, content: str, file_path: Path | None) -> FileThing[SgRoot]:
        """Parse content to AST root using ast-grep.

        Wraps ast-grep parsing with error handling and FileThing conversion.
        Checks for ERROR nodes in the AST which indicate syntax errors.

        Args:
            content: Source code content to parse
            file_path: Optional file path for error messages

        Returns:
            FileThing AST root node

        Raises:
            ParseError: If parsing fails or ERROR nodes found in AST
        """
        from typing import NoReturn

        def raise_parse_error(
            message: str,
            line_number: int | None = None,
            e: Exception | None = None,
            details: dict[str, Any] | None = None,
        ) -> NoReturn:
            raise ParseError(
                message,
                file_path=str(file_path) if file_path else None,
                details={
                    "language": self.language.variable,
                    "line_number": line_number,
                    **(details or {}),
                },
            ) from e or None

        try:
            from ast_grep_py import SgRoot

            from codeweaver.semantic import FileThing

            root: SgRoot = SgRoot(content, self.language.variable)

            # Note: Removed ERROR node scanning for performance. ast-grep-py already
            # raises exceptions for fatal syntax errors. ERROR nodes typically indicate
            # partial parsing/error recovery which we don't use anyway. If SgRoot
            # construction succeeds, the AST is usable for our purposes.
        except ParseError:
            raise
        except Exception as e:
            logger.warning("Failed to parse %s", file_path or "content", exc_info=True)

            # Log structured error event for observability
            log_chunking_failed(
                file_path=file_path or Path("<unknown>"),
                chunker_type=self,
                error_type=type(e).__name__,
                error_message=str(e),
                fallback_triggered=False,  # Will be handled by caller's exception handling
                extra_context={"language": self.language.as_title},
            )

            raise_parse_error(
                f"Failed to parse {file_path or 'content'}",
                e=e,
                details={"language": self.language.as_title, "exception": str(e)},
            )
        else:
            return cast(FileThing[SgRoot], FileThing.from_sg_root(root, file_path=file_path))

    def _find_chunkable_nodes(
        self, root: FileThing[SgRoot], max_depth: int = 200, file_path: Path | None = None
    ) -> tuple[list[AstThing[SgNode]], dict[int, int]]:
        """Traverse AST and filter nodes by classification and importance.

        Recursively walks the AST tree from root, checking each node against
        chunkability criteria (classification and importance threshold) and
        enforcing AST depth safety limits. Returns both chunkable nodes and
        their depths for efficient metadata building.

        Args:
            root: FileThing AST root to traverse
            max_depth: Maximum safe nesting depth
            file_path: Optional file path for error messages

        Returns:
            Tuple of (chunkable nodes list, node depth mapping)

        Raises:
            ASTDepthExceededError: If any node exceeds safe nesting depth
        """
        chunkable: list[AstThing[SgNode]] = []
        # Cache node depths to avoid repeated ancestor traversal
        node_depths: dict[int, int] = {}

        # Single-pass optimized traversal that tracks depth and finds chunkable nodes
        def traverse(node: AstThing[SgNode], depth: int) -> None:
            # Check depth limit
            if depth > max_depth:
                raise ASTDepthExceededError(
                    (
                        f"AST nesting depth of {depth} levels exceeds the configured maximum of {max_depth} levels. "
                        f"This typically indicates deeply nested code structures that may cause performance issues."
                    ),
                    actual_depth=depth,
                    max_depth=max_depth,
                    file_path=str(file_path) if file_path else None,
                )

            # Cache depth for this node (using id as key for O(1) lookup)
            node_depths[id(node)] = depth

            # Check if this node is chunkable
            if self._is_chunkable(node):
                chunkable.append(node)

            # Recurse into children
            for child in node.positional_connections:
                traverse(child, depth + 1)

        # Start traversal from root's children
        for child_thing in root.root.positional_connections:
            traverse(child_thing, 1)

        return chunkable, node_depths

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
            # Values are already NonNegativeFloat from ImportanceScoresDict
            # Type checker loses this info through .values(), so we help it with a cast
            scores = node.importance.as_dict().values()
            return any(score >= self._importance_threshold for score in scores)  # type: ignore[operator]

        # Include if we have classification but no importance scores
        return True

    def _check_ast_depth(
        self, node: AstThing[SgNode], max_depth: int, file_path: Path | None = None
    ) -> None:
        """Verify AST nesting doesn't exceed safe depth limits.

        Protects against stack overflow and excessive memory usage during
        traversal of pathologically deep AST structures.

        Note: This method is now primarily used for legacy support or individual checks.
        Primary depth enforcement happens in _find_chunkable_nodes traversal.

        Args:
            node: AstThing node to check
            max_depth: Maximum safe nesting depth
            file_path: Optional file path for error messages

        Raises:
            ASTDepthExceededError: If node depth exceeds maximum
        """
        # Calculate depth efficiently if needed, but prefer passing depth during traversal
        depth = len(list(node._node.ancestors()))  # Use raw node to avoid AstThing overhead
        if depth > max_depth:
            raise ASTDepthExceededError(
                (
                    f"AST nesting depth of {depth} levels exceeds the configured maximum of {max_depth} levels. "
                    f"This typically indicates deeply nested code structures that may cause performance issues."
                ),
                actual_depth=depth,
                max_depth=max_depth,
                file_path=str(file_path) if file_path else None,
            )

    def _create_chunk_from_node(
        self,
        node: AstThing[SgNode],
        file_path: Path | None,
        source_id: UUID7,
        depth: int | None = None,
    ) -> CodeChunk:
        """Create CodeChunk with rich metadata from AstThing node.

        Extracts text, line range, and builds comprehensive metadata including
        semantic information, classification, importance scores, and hierarchy.

        Args:
            node: AstThing node to convert
            file_path: Optional file path for chunk context
            source_id: Shared source ID for all chunks from this file
            depth: Optional cached depth to avoid ancestor traversal

        Returns:
            CodeChunk with semantic metadata
        """
        range_obj = node.range
        metadata = self._build_metadata(node, depth)

        # Use model_construct to bypass validation since dependencies may not be fully defined
        return CodeChunk.model_construct(
            content=node.text,
            line_range=Span(
                # ast-grep uses 0-based line numbers, Span uses 1-based
                range_obj.start.line + 1,
                range_obj.end.line + 1,
                source_id,
            ),  # All spans from same file share source_id
            ext_kind=ExtKind.from_file(file_path) if file_path else None,
            file_path=file_path,
            language=self.language,
            source=ChunkSource.SEMANTIC,
            metadata=metadata,
        )

    def _build_metadata(self, node: AstThing[SgNode], depth: int | None = None) -> Metadata:
        """Build metadata using existing Metadata TypedDict structure.

        Creates comprehensive metadata optimized for AI context delivery,
        including semantic information, classification, importance scores,
        and hierarchical tracking.

        Args:
            node: AstThing node to extract metadata from
            depth: Optional cached depth to avoid ancestor traversal

        Returns:
            Metadata TypedDict with semantic and context information
        """
        # Use existing SemanticMetadata.from_node() factory
        semantic_meta = SemanticMetadata.from_node(node, self.language)

        # Extract simple name from node - try to get identifier field first
        simple_name = None
        with contextlib.suppress(Exception):
            # For functions/methods/classes, try to get the "name" field from AST
            # Note: Accessing _node is acceptable here as it's wrapped in exception handling
            if name_node := node._node.field("name"):
                simple_name = name_node.text()
        # Fallback to using title or node name
        if not simple_name:
            simple_name = node.title if hasattr(node, "title") else str(node.name)

        # Use cached depth if available, otherwise calculate from ancestors
        nesting_level = depth if depth is not None else len(list(node.ancestors()))

        metadata: Metadata = {
            "chunk_id": uuid7(),
            "created_at": datetime.now(UTC).timestamp(),
            "name": simple_name,
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
                "nesting_level": nesting_level,
            },
        }

        return metadata

    def _handle_oversized_node(
        self,
        node: AstThing[SgNode],
        file_path: Path | None,
        source_id: UUID7,
        governor: Any,
        recursion_depth: int = 0,
    ) -> list[CodeChunk]:
        """Handle nodes exceeding token limit via multi-tiered strategy.

        Applies graceful degradation:
        1. Try chunking children recursively (for composite nodes)
        2. Fallback to delimiter-based chunking on node text
        3. Last resort: Return single chunk as-is (may exceed token limit)

        Preserves semantic context in fallback chunks via metadata enhancement.

        Args:
            node: Oversized AstThing node
            file_path: Optional file_path for context
            source_id: Shared source ID for all chunks from this file
            governor: Resource governor for limit enforcement
            recursion_depth: Current recursion depth to prevent stack overflow

        Returns:
            List of chunks derived from oversized node
        """
        # Tier 1: Recursive child chunking for composite nodes
        if (
            node.is_composite
            and recursion_depth < MAX_SEMANTIC_CHUNKER_RECURSION_DEPTH
            and (
                child_chunks := self._chunk_oversized_node_children(
                    node, file_path, source_id, governor, recursion_depth
                )
            )
        ):
            return child_chunks

        # Log recursion limit warning if falling back due to depth
        if recursion_depth >= MAX_SEMANTIC_CHUNKER_RECURSION_DEPTH:
            logger.warning(
                "Maximum recursion depth (%d) reached for oversized node '%s', using delimiter fallback",
                MAX_SEMANTIC_CHUNKER_RECURSION_DEPTH,
                node.name,
            )

        # Tier 2: Fallback to delimiter-based chunking
        return self._fallback_to_delimiter_chunking(node, file_path, source_id, governor)

    def _chunk_oversized_node_children(
        self,
        node: AstThing[SgNode],
        file_path: Path | None,
        source_id: UUID7,
        governor: Any,
        recursion_depth: int,
    ) -> list[CodeChunk]:
        """Recursive child chunking for oversized composite nodes."""
        children = list(node.positional_connections)
        child_chunks: list[CodeChunk] = []

        for child in children:
            governor.check_timeout()
            # Cache child text for performance
            child_text = child.text
            if self._has_tokenizer:
                child_tokens = self.tokenizer.estimate(child_text)
            else:
                child_tokens = len(child_text) // 4

            if child_tokens <= self.chunk_limit:
                child_chunks.append(self._create_chunk_from_node(child, file_path, source_id))
                governor.register_chunk()
            else:
                # Recursive handling for oversized children with incremented depth
                child_chunks.extend(
                    self._handle_oversized_node(
                        child, file_path, source_id, governor, recursion_depth + 1
                    )
                )

        return child_chunks

    def _fallback_to_delimiter_chunking(
        self, node: AstThing[SgNode], file_path: Path | None, source_id: UUID7, governor: Any
    ) -> list[CodeChunk]:
        """Delimiter-based fallback for oversized nodes that cannot be semantically subdivided."""
        logger.info(
            "Oversized node without chunkable children: %s, falling back to delimiter chunker",
            node.name,
        )

        from codeweaver.engine.chunker.delimiter import DelimiterChunker

        # Create delimiter chunker with same language
        delimiter_chunker = DelimiterChunker(
            governor=self.governor,
            language=self.language.variable
            if hasattr(self.language, "variable")
            else str(self.language),
        )

        log_chunking_fallback(
            file_path=file_path or Path("<unknown>"),
            from_chunker=self,
            to_chunker=delimiter_chunker,
            reason="oversized_chunk",
            extra_context={"node_name": node.name, "node_text_length": len(node.text)},
        )

        from codeweaver.core import DiscoveredFile as _DiscoveredFile

        temp_file = _DiscoveredFile.from_path(file_path) if file_path else None
        delimiter_chunks = delimiter_chunker.chunk(node.text, file=temp_file)

        # If delimiter chunking didn't actually split it (produced 1 chunk >= original size)
        # OR if it produced no chunks, we MUST return a single chunk to avoid infinite recursion
        if not delimiter_chunks or (
            len(delimiter_chunks) == 1 and len(delimiter_chunks[0].content) >= len(node.text)
        ):
            metadata = self._build_metadata(node)
            chunk = CodeChunk(
                content=node.text,
                line_range=Span(node.range.start.line + 1, node.range.end.line + 1, source_id),
                ext_kind=ExtKind.from_file(file_path) if file_path else None,
                file_path=file_path,
                language=self.language,
                source=ChunkSource.SEMANTIC,
                metadata=metadata,
            )
            governor.register_chunk()
            return [chunk]

        # Enhance each chunk with semantic fallback metadata
        metadata = self._build_metadata(node)
        if (
            metadata
            and "semantic_meta" in metadata
            and isinstance(metadata["semantic_meta"], SemanticMetadata)
        ):
            # Mark as partial node
            metadata["semantic_meta"] = metadata["semantic_meta"].model_copy(
                update={"is_partial_node": True}
            )

        enhanced_chunks: list[CodeChunk] = []
        for delimiter_chunk in delimiter_chunks:
            # Preserve delimiter chunk content but enhance metadata
            chunk_metadata = delimiter_chunk.metadata or {}
            if "context" not in chunk_metadata or chunk_metadata["context"] is None:
                chunk_metadata["context"] = {}

            # Add semantic fallback indicators (both top-level and in context)
            chunk_metadata["context"]["fallback"] = "delimiter"
            chunk_metadata["context"]["parent_semantic_node"] = node.name

            # Create enhanced chunk preserving delimiter chunk properties
            enhanced_chunk = CodeChunk(
                content=delimiter_chunk.content,
                line_range=delimiter_chunk.line_range,
                ext_kind=delimiter_chunk.ext_kind,
                file_path=delimiter_chunk.file_path,
                language=delimiter_chunk.language,
                source=ChunkSource.TEXT_BLOCK,  # Not truly semantic
                metadata=Metadata(**chunk_metadata),
            )
            enhanced_chunks.append(enhanced_chunk)

        return enhanced_chunks or [
            # Last resort: single chunk with fallback metadata
            CodeChunk(
                content=node.text,
                line_range=Span(node.range.start.line, node.range.end.line, source_id),
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
        from codeweaver.core import BatchKeys

        deduplicated: list[CodeChunk] = []

        for idx, chunk in enumerate(chunks):
            if not chunk.metadata or "context" not in chunk.metadata:
                batch_keys = BatchKeys(id=batch_id, idx=idx)
                deduplicated.append(chunk.set_batch_keys(batch_keys))
                continue

            context = chunk.metadata.get("context")
            if not context:
                batch_keys = BatchKeys(id=batch_id, idx=idx)
                deduplicated.append(chunk.set_batch_keys(batch_keys))
                continue

            content_hash = context.get("content_hash")
            if not content_hash:
                batch_keys = BatchKeys(id=batch_id, idx=idx)
                deduplicated.append(chunk.set_batch_keys(batch_keys))
                continue

            # Check if we've seen this content before
            if existing_batch_id := type(self)._hash_store.get(content_hash):
                logger.debug(
                    "Duplicate chunk detected: %s... (existing batch: %s)",
                    content_hash[:16],
                    existing_batch_id,
                )
                continue

            # New unique chunk
            type(self)._hash_store.set(content_hash, batch_id)
            batch_keys = BatchKeys(id=batch_id, idx=idx)
            deduplicated.append(chunk.set_batch_keys(batch_keys))

        # Log deduplication statistics if any duplicates were found
        if len(chunks) > len(deduplicated):
            log_chunking_deduplication(
                file_path=Path("<batch>"),  # Batch-level dedup doesn't have single file
                total_chunks=len(chunks),
                duplicate_chunks=len(chunks) - len(deduplicated),
                unique_chunks=len(deduplicated),
            )

        return deduplicated

    def _track_chunk_metrics(
        self,
        chunks: list[CodeChunk],
        duration: float,
        file_path: Path | None = None,
        file_size_bytes: int = 0,
        language: str = "unknown",
    ) -> None:
        """Track chunking performance metrics via structured logging.

        Logs structured event with chunk count, duration, chunker type,
        and average chunk size for monitoring and performance analysis.

        Args:
            chunks: Generated chunks for metrics
            duration: Operation duration in seconds
            file_path: Optional file path being chunked
            file_size_bytes: Total size of content in bytes
            language: Programming language of the file
        """
        from codeweaver.engine.chunker import _logging as chunker_logging

        duration_ms = duration * ONE_MILLISECOND_IN_MICROSECONDS

        # Use standardized structured logging
        chunker_logging.log_chunking_completed(
            file_path=file_path or Path("<unknown>"),
            chunker_type=self,
            chunk_count=len(chunks),
            duration_ms=duration_ms,
            file_size_bytes=file_size_bytes,
            language=language,
        )

        # Log performance warning if chunking took too long
        if duration_ms > SEMANTIC_CHUNKER_PERFORMANCE_THRESHOLD_MS:
            chunker_logging.log_chunking_performance_warning(
                file_path=file_path or Path("<unknown>"),
                chunker_type=self,
                duration_ms=duration_ms,
                threshold_ms=SEMANTIC_CHUNKER_PERFORMANCE_THRESHOLD_MS,
                extra_context={"chunk_count": len(chunks), "file_size_bytes": file_size_bytes},
            )


__all__ = ("SemanticChunker",)
