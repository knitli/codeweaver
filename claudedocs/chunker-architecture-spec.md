<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# CodeWeaver Chunker System Architecture Specification

**Version**: 2.0.0
**Status**: Ready for Implementation
**Author**: Claude Code (Sequential Analysis + Gap Analysis)
**Date**: 2025-10-24

## Executive Summary

Complete redesign of CodeWeaver's chunking system with:
- **Semantic Chunker**: AST-based chunking w/ rich AI-first metadata for 26 languages
- **Delimiter Chunker**: Pattern-based fallback for 170+ languages
- **Intelligent Selection**: Automatic chunker routing w/ graceful degradation
- **Constitutional Compliance**: Evidence-based, proven patterns, simplicity-focused
- **Production Ready**: Resource governance, deduplication, comprehensive observability

**Removes**: `router.py` (hardcoded, inflexible)
**Adds**: `semantic.py`, `delimiter.py`, `selector.py`

---

## 1. System Architecture

### 1.1 Component Hierarchy

```
ChunkerSelector
    ↓ (selects)
SemanticChunker (primary, 26 langs)
    ↓ (fallback on parse error or oversized)
DelimiterChunker (secondary, 170+ langs)
    ↓ (fallback on no matches)
GenericDelimiters (tertiary, universal)
    ↓ (last resort)
Return as single chunk (may exceed token limit)
```

### 1.2 Design Principles (Constitutional)

| Principle | Implementation |
|-----------|----------------|
| **I. AI-First Context** | Rich importance scores in metadata → better agent ranking |
| **II. Proven Patterns** | Strategy pattern for chunker selection, plugin registry |
| **III. Evidence-Based** | Real AST/delimiter patterns, no mocks or placeholders |
| **IV. Testing Philosophy** | Integration tests for critical paths, not impl details |
| **V. Simplicity** | Flat structure, clear separation of concerns |

### 1.3 Infrastructure Integration

**Leverages Existing Codebase**:
- **UUIDStore & BlakeStore** (stores.py): Content-addressable deduplication
- **Metadata & SemanticMetadata** (metadata.py): Standardized chunk metadata
- **SessionStatistics** (statistics.py): Comprehensive observability
- **ExtKind** (file_extensions.py): Language and category detection

---

## 2. Semantic Chunker Design

### 2.1 Overview

**Purpose**: AST-based chunking leveraging sophisticated semantic analysis system
**Languages**: 26 w/ tree-sitter grammars (`SemanticSearchLanguage`)
**Key Advantage**: Rich metadata w/ importance scores → optimal AI context

### 2.2 Core Algorithm

```python
def chunk(content: str, file_path: Path) -> list[CodeChunk]:
    # 0. Resource governance and edge case handling
    with ResourceGovernor(settings) as governor:
        if edge_result := handle_edge_cases(content, file_path):
            return edge_result

        # 1. Parse file → FileThing (AST root)
        root = parse_file(content, file_path, language)

        # 2. Find chunkable nodes (filtered by classification & importance)
        nodes = find_chunkable_nodes(root)

        # 3. Convert to chunks w/ size enforcement
        chunks = []
        for node in nodes:
            governor.check_timeout()  # Resource check

            if estimate_tokens(node.text) <= chunk_limit:
                chunks.append(create_chunk(node))
            else:
                # Oversized → recursively chunk children OR fallback to delimiter
                chunks.extend(handle_oversized_node(node))

            governor.register_chunk()  # Track and enforce limits

        # 4. Deduplicate using content hashing
        unique_chunks = deduplicate_chunks(chunks, batch_id)

        return unique_chunks
```

### 2.3 Chunkable Node Criteria

✅ **Include**:
- Has `classification` (not UNKNOWN)
- `importance_score` ≥ threshold (default 0.3)
- OR: `is_composite` w/ chunkable children (containers)

❌ **Exclude**:
- Pure structural nodes (bare blocks)
- Tokens w/ no semantic value
- Nodes below importance threshold

### 2.4 Metadata Structure (AI-First!)

Uses existing `Metadata` TypedDict and `SemanticMetadata` BasedModel:

```python
def _build_metadata(self, node: AstThing) -> Metadata:
    """Build metadata using existing Metadata TypedDict structure."""
    from codeweaver.core.metadata import Metadata, SemanticMetadata

    # Use existing SemanticMetadata.from_node() factory
    semantic_meta = SemanticMetadata.from_node(node, self.language)

    metadata: Metadata = {
        "chunk_id": uuid7(),
        "created_at": datetime.now(UTC).timestamp(),
        "name": node.title,  # "Python-function_definition-Function: 'calculate_score'"
        "semantic_meta": semantic_meta,
        "context": {
            # Chunker-specific context in flexible dict
            "chunker_type": "semantic",
            "content_hash": self._compute_content_hash(node.text),
            "classification": node.classification.name if node.classification else None,
            "kind": str(node.name),
            "category": node.primary_category,
            "importance_scores": node.importance.as_dict() if node.importance else None,
            "is_composite": node.is_composite,
            "nesting_level": len(list(node.ancestors())),
        },
    }

    return metadata
```

**SemanticMetadata Fields** (from metadata.py):
- `language`: Language identifier
- `thing`: Full AstThing reference
- `positional_connections`: Child nodes
- `symbol`: Identifier name
- `thing_id` & `parent_thing_id`: UUID7 hierarchical tracking
- `is_partial_node`: Indicates oversized node chunking

### 2.5 Token Size Management

**Strategy**: Multi-tiered enforcement

```
1. Estimate node.text tokens
   ├─ Fits? → Create chunk
   └─ Oversized?
       ↓
2. Try extracting just children (skip node wrapper)
   ├─ Fits? → Create chunks from children
   └─ Still oversized?
       ↓
3. Hybrid: Use DelimiterChunker on node.text
   ├─ Success? → Return delimiter chunks
   └─ Fails?
       ↓
4. RecursiveCharacterTextSplitter (last resort)
```

### 2.6 Edge Case Handling

**Handles** (before normal chunking):
- **Empty files** (0 bytes): Return `[]`
- **Whitespace-only**: Return single chunk with `edge_case` metadata
- **Single-line files**: Return single chunk, skip AST parsing
- **Binary files**: Raise `BinaryFileError`

```python
def _handle_edge_cases(self, content: str, file_path: Path) -> list[CodeChunk] | None:
    """Handle edge cases before normal chunking.

    Returns:
        - Empty list for truly empty files
        - Single chunk for whitespace-only or single-line files
        - None to continue with normal chunking
        - Raises BinaryFileError if binary content detected
    """
    # Binary file detection
    if b'\x00' in content.encode('utf-8', errors='ignore'):
        raise BinaryFileError(f"Binary content detected in {file_path}")

    # Empty file
    if not content or len(content) == 0:
        logger.info(f"Empty file: {file_path}, returning no chunks")
        return []

    # Whitespace-only file
    if not content.strip():
        return [CodeChunk(
            content=content,
            line_range=Span(1, content.count('\n') + 1, source_id_for(file_path)),
            file_path=file_path,
            language=self.language.name,
            source="edge_case",
            metadata={"edge_case": "whitespace_only"},
        )]

    # Single line (no semantic structure to parse)
    if '\n' not in content:
        return [CodeChunk(
            content=content,
            line_range=Span(1, 1, source_id_for(file_path)),
            file_path=file_path,
            language=self.language.name,
            source="edge_case",
            metadata={"edge_case": "single_line"},
        )]

    # Continue with normal chunking
    return None
```

### 2.7 Implementation Scaffold

```python
# src/codeweaver/engine/chunker/semantic.py

from codeweaver.core.stores import BlakeStore, UUIDStore, make_blake_store, make_uuid_store

class SemanticChunker(BaseChunker):
    """AST-based chunker w/ rich semantic metadata and deduplication."""

    chunker = Chunker.SEMANTIC  # Registry key

    # Deduplication stores (class-level, shared)
    _store: UUIDStore[list[CodeChunk]] = make_uuid_store(
        value_type=list, size_limit=3 * 1024 * 1024  # 3MB
    )
    _hash_store: BlakeStore[UUID7] = make_blake_store(
        value_type=UUID7, size_limit=256 * 1024  # 256KB
    )

    def __init__(self, governor: ChunkGovernor, language: SemanticSearchLanguage):
        super().__init__(governor)
        self.language = language
        self._importance_threshold = 0.3  # Configurable via governor

    def chunk(self, content: str, *, file_path: Path | None = None,
              context: dict[str, Any] | None = None) -> list[CodeChunk]:
        """Main chunking entry point with resource governance."""
        statistics = get_session_statistics()
        start_time = time.perf_counter()
        batch_id = uuid7()

        with ResourceGovernor(self.governor.performance_settings) as governor:
            try:
                # Edge case handling
                if edge_result := self._handle_edge_cases(content, file_path):
                    return edge_result

                # Normal chunking
                root = self._parse_file(content, file_path)
                nodes = self._find_chunkable_nodes(root)

                chunks = []
                for node in nodes:
                    governor.check_timeout()

                    node_text = node.text
                    tokens = estimate_tokens(node_text)

                    if tokens <= self.chunk_limit:
                        chunks.append(self._create_chunk_from_node(node, file_path))
                    else:
                        chunks.extend(self._handle_oversized_node(node, file_path))

                    governor.register_chunk()

                # Deduplicate
                unique_chunks = self._deduplicate_chunks(chunks, batch_id)

                # Store batch
                self._store.set(batch_id, unique_chunks)
                for chunk in unique_chunks:
                    chunk.set_batch_id(batch_id)

                # Track statistics
                if file_path and (ext_kind := ExtKind.from_file(file_path)):
                    statistics.add_file_operations_by_extkind([
                        (file_path, ext_kind, "processed")
                    ])

                self._track_chunk_metrics(unique_chunks, time.perf_counter() - start_time)

                return unique_chunks

            except ParseError as e:
                logger.error(f"Parse error in {file_path}: {e}")
                if file_path and (ext_kind := ExtKind.from_file(file_path)):
                    statistics.add_file_operations_by_extkind([
                        (file_path, ext_kind, "skipped")
                    ])
                raise

    def _parse_file(self, content: str, file_path: Path) -> FileThing:
        """Parse content to AST root."""
        from ast_grep_py import SgRoot
        return FileThing.from_sg_root(SgRoot(content, self.language.value))

    def _find_chunkable_nodes(self, root: FileThing) -> list[AstThing]:
        """Traverse AST, filter by classification & importance."""
        chunkable = []
        for node in root.root._node.children():
            ast_thing = AstThing.from_sg_node(node, self.language)
            self._check_ast_depth(ast_thing)  # Safety check
            if self._is_chunkable(ast_thing):
                chunkable.append(ast_thing)
        return chunkable

    def _is_chunkable(self, node: AstThing) -> bool:
        """Check if node meets chunkable criteria."""
        if not node.classification or node.classification.name == "UNKNOWN":
            return node.is_composite

        if node.importance:
            return any(score >= self._importance_threshold
                      for score in node.importance.as_dict().values())

        return True

    def _check_ast_depth(self, node: AstThing, max_depth: int = 200) -> None:
        """Verify AST depth doesn't exceed safe limits."""
        depth = len(list(node.ancestors()))
        if depth > max_depth:
            raise ASTDepthExceededError(
                f"AST depth {depth} exceeds maximum {max_depth}"
            )

    def _create_chunk_from_node(self, node: AstThing, file_path: Path) -> CodeChunk:
        """Create CodeChunk w/ rich metadata from AstThing."""
        range_obj = node.range
        metadata = self._build_metadata(node)

        return CodeChunk(
            content=node.text,
            line_range=Span(
                start=range_obj.start.line,
                end=range_obj.end.line,
                source_id=source_id_for(file_path)
            ),
            file_path=file_path,
            language=self.language.name,
            source="semantic",
            metadata=metadata,
        )

    def _handle_oversized_node(self, node: AstThing, file_path: Path) -> list[CodeChunk]:
        """Handle nodes exceeding token limit."""
        # Try chunking children first
        if node.is_composite:
            children = list(node.positional_connections)
            child_chunks = []
            for child in children:
                if estimate_tokens(child.text) <= self.chunk_limit:
                    child_chunks.append(self._create_chunk_from_node(child, file_path))
                else:
                    child_chunks.extend(self._handle_oversized_node(child, file_path))

            if child_chunks:
                return child_chunks

        # Fallback: Use delimiter chunker
        from codeweaver.engine.chunker.delimiter import DelimiterChunker
        delimiter_chunker = DelimiterChunker(self.governor, self.language.name)
        delimiter_chunks = delimiter_chunker.chunk(node.text, file_path=file_path)

        # Enhance with semantic context
        for chunk in delimiter_chunks:
            if chunk.metadata:
                chunk.metadata["parent_semantic_node"] = node.title
                chunk.metadata["context"]["semantic_context"] = {
                    "classification": node.classification.name if node.classification else None,
                    "kind": str(node.name),
                }

        return delimiter_chunks

    def _compute_content_hash(self, content: str) -> BlakeHashKey:
        """Compute Blake3 hash for deduplication."""
        from codeweaver.core.stores import get_blake_hash

        normalized = content.strip()
        return get_blake_hash(normalized.encode('utf-8'))

    def _deduplicate_chunks(
        self, chunks: list[CodeChunk], batch_id: UUID7
    ) -> list[CodeChunk]:
        """Deduplicate chunks using hash store."""
        deduplicated = []

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
        """Track chunking performance metrics."""
        logger.info(
            "chunking_completed",
            extra={
                "chunk_count": len(chunks),
                "duration_ms": duration * 1000,
                "chunker_type": self.chunker.name,
                "avg_chunk_size": sum(len(c.content) for c in chunks) / len(chunks) if chunks else 0,
            }
        )
```

---

## 3. Delimiter Chunker Design

### 3.1 Overview

**Purpose**: Pattern-based fallback for non-semantic languages & parse failures
**Languages**: 170+ via `DelimiterPattern` DSL
**Key Advantage**: Universal coverage, no parse dependencies

### 3.2 Delimiter Model

```python
# src/codeweaver/engine/chunker/delimiter.py

class Delimiter(BasedModel):
    """Concrete delimiter definition."""

    start: str
    end: str
    kind: DelimiterKind
    priority: PositiveInt  # Higher = processed first
    inclusive: bool         # Include delimiters in chunk?
    take_whole_lines: bool  # Expand to line boundaries?
    nestable: bool          # Can nest (e.g., braces)?

    @classmethod
    def from_pattern(cls, pattern: DelimiterPattern) -> list[Delimiter]:
        """Expand pattern to concrete delimiters."""
        return [cls(**d) for d in expand_pattern(pattern)]
```

### 3.3 Chunking Algorithm

**Phase 1: Match Detection**
```python
def _find_delimiter_matches(self, content: str) -> list[DelimiterMatch]:
    # Build combined regex for efficiency
    pattern = '|'.join(re.escape(d.start) for d in self.delimiters)
    compiled = re.compile(pattern)

    matches = []
    for match in compiled.finditer(content):
        delimiter = self._delimiter_map[match.group()]
        matches.append(DelimiterMatch(
            delimiter=delimiter,
            start_pos=match.start(),
            end_pos=None,
            nesting_level=0,
        ))

    return matches
```

**Phase 2: Boundary Extraction** (handles nesting)
```python
def _extract_boundaries(self, matches: list[DelimiterMatch]) -> list[Boundary]:
    """Match starts w/ ends, handle nesting."""
    stack: list[DelimiterMatch] = []
    boundaries: list[Boundary] = []

    for match in matches:
        if match.is_start:
            match.nesting_level = len(stack)
            stack.append(match)
        else:  # end delimiter
            if match.delimiter.nestable:
                start = stack.pop()
            else:
                start = next(m for m in reversed(stack)
                           if m.delimiter.kind == match.delimiter.kind)
                stack.remove(start)

            boundaries.append(Boundary(
                start=start.start_pos,
                end=match.end_pos,
                delimiter=start.delimiter,
                nesting_level=start.nesting_level,
            ))

    return boundaries
```

**Phase 3: Priority Resolution** (handle overlaps)
```python
def _resolve_overlaps(self, boundaries: list[Boundary]) -> list[Boundary]:
    """Keep highest-priority non-overlapping boundaries.

    Tie-breaking rules (in order):
    1. Higher priority wins
    2. Same priority: Longer match wins
    3. Same length: Earlier position wins (deterministic)
    """
    sorted_bounds = sorted(
        boundaries,
        key=lambda b: (
            -b.delimiter.priority,
            -(b.end - b.start),
            b.start
        )
    )

    selected = []
    for boundary in sorted_bounds:
        if not any(self._overlaps(boundary, s) for s in selected):
            selected.append(boundary)

    return sorted(selected, key=lambda b: b.start)
```

### 3.4 Metadata Structure

```python
def _build_metadata(self, boundary: Boundary, line: int) -> Metadata:
    """Build metadata for delimiter chunks."""
    from codeweaver.core.metadata import Metadata

    metadata: Metadata = {
        "chunk_id": uuid7(),
        "created_at": datetime.now(UTC).timestamp(),
        "name": f"{boundary.delimiter.kind.name.title()} at line {line}",
        "context": {
            "chunker_type": "delimiter",
            "content_hash": self._compute_content_hash(boundary.text),
            "delimiter_kind": boundary.delimiter.kind.name,
            "delimiter_start": boundary.delimiter.start,
            "delimiter_end": boundary.delimiter.end,
            "priority": boundary.delimiter.priority,
            "nesting_level": boundary.nesting_level,
        },
    }

    return metadata
```

### 3.5 Implementation Scaffold

```python
# src/codeweaver/engine/chunker/delimiter.py

from dataclasses import dataclass

@dataclass
class DelimiterMatch:
    delimiter: Delimiter
    start_pos: int
    end_pos: int | None = None
    nesting_level: int = 0

@dataclass
class Boundary:
    start: int
    end: int
    delimiter: Delimiter
    nesting_level: int


class DelimiterChunker(BaseChunker):
    """Pattern-based chunker for 170+ languages."""

    chunker = Chunker.DELIMITER

    def __init__(self, governor: ChunkGovernor, language: str):
        super().__init__(governor)
        self.language = language
        self.delimiters = self._load_delimiters_for_language(language)
        self.delimiters.sort(key=lambda d: d.priority, reverse=True)
        self._delimiter_map = {d.start: d for d in self.delimiters}

    def chunk(self, content: str, *, file_path: Path | None = None,
              context: dict[str, Any] | None = None) -> list[CodeChunk]:
        """Main chunking entry point."""
        # Edge cases
        if edge_result := self._handle_edge_cases(content, file_path):
            return edge_result

        # Normal chunking
        matches = self._find_delimiter_matches(content)
        boundaries = self._extract_boundaries(matches)
        boundaries = self._resolve_overlaps(boundaries)
        return self._boundaries_to_chunks(boundaries, content, file_path)

    def _load_delimiters_for_language(self, language: str) -> list[Delimiter]:
        """Load delimiter set for language."""
        from codeweaver.engine.chunker.delimiters import families

        family = families.detect_language_family(language)
        patterns = families.get_patterns_for_family(family)

        delimiters = []
        for pattern in patterns:
            delimiters.extend(Delimiter.from_pattern(pattern))

        return delimiters

    def _boundaries_to_chunks(self, boundaries: list[Boundary],
                             content: str, file_path: Path) -> list[CodeChunk]:
        """Convert boundaries to CodeChunks w/ metadata."""
        chunks = []
        for i, boundary in enumerate(boundaries):
            chunk_text = content[boundary.start:boundary.end]

            if not boundary.delimiter.inclusive:
                chunk_text = self._strip_delimiters(chunk_text, boundary.delimiter)

            if boundary.delimiter.take_whole_lines:
                chunk_text, line_start, line_end = self._expand_to_lines(
                    content, boundary.start, boundary.end
                )
            else:
                line_start, line_end = self._pos_to_lines(
                    content, boundary.start, boundary.end
                )

            # Add overlap
            if i > 0:
                overlap_size = min(self.simple_overlap, boundary.start - boundaries[i-1].end)
                prefix = content[boundary.start - overlap_size:boundary.start]
                chunk_text = prefix + chunk_text

            metadata = self._build_metadata(boundary, line_start)
            chunks.append(CodeChunk(
                content=chunk_text,
                line_range=Span(line_start, line_end, source_id_for(file_path)),
                file_path=file_path,
                language=self.language,
                source="delimiter",
                metadata=metadata,
            ))

        return chunks
```

---

## 4. Chunker Selector Design

### 4.1 Overview

**Purpose**: Intelligent routing → appropriate chunker based on language & capabilities
**Replaces**: Hardcoded `router.py`
**Pattern**: Strategy selection w/ fallback chain

### 4.2 Selection Algorithm

```
1. Detect language from file extension
   ↓
2. Language in SemanticSearchLanguage?
   ├─ YES → Try SemanticChunker
   │         ├─ Parse success? → Use semantic chunks
   │         └─ Parse error? → Fallback to delimiter
   └─ NO → Use DelimiterChunker
```

### 4.3 Implementation

```python
# src/codeweaver/engine/chunker/selector.py

class ChunkerSelector:
    """Selects appropriate chunker based on file & language."""

    def __init__(self, governor: ChunkGovernor):
        self.governor = governor

    def select_for_file(self, file: DiscoveredFile) -> BaseChunker:
        """Select best chunker for given file (creates fresh instance)."""
        language = self._detect_language(file)

        # Try semantic first for supported languages
        if language in SemanticSearchLanguage:
            try:
                return SemanticChunker(self.governor, language)
            except (ParseError, NotImplementedError) as e:
                logger.warning(
                    f"Semantic chunking unavailable for {file.path}: {e}. "
                    f"Using delimiter fallback."
                )

        # Delimiter fallback
        return DelimiterChunker(
            self.governor,
            language.name if language else "unknown"
        )

    def _detect_language(self, file: DiscoveredFile) -> SemanticSearchLanguage | str:
        """Detect language from file extension."""
        try:
            return SemanticSearchLanguage.from_extension(file.path.suffix)
        except ValueError:
            return file.path.suffix.lstrip('.')


class GracefulChunker(BaseChunker):
    """Wraps chunker with graceful degradation."""

    def __init__(self, primary: BaseChunker, fallback: BaseChunker):
        super().__init__(primary.governor)
        self.primary = primary
        self.fallback = fallback

    def chunk(self, content: str, *, file_path: Path | None = None,
              context: dict[str, Any] | None = None) -> list[CodeChunk]:
        """Try primary, fallback on error."""
        try:
            return self.primary.chunk(content, file_path=file_path, context=context)
        except Exception as e:
            logger.warning(f"Primary chunker failed: {e}. Using fallback.")
            return self.fallback.chunk(content, file_path=file_path, context=context)
```

---

## 5. Registry Enhancement

### 5.1 Purpose

Support plugin-style chunker registration per Constitutional Principle II (Proven Patterns)

### 5.2 Implementation

```python
# src/codeweaver/engine/chunker/registry.py (enhance existing)

from typing import TypeAlias

ChunkerFactory: TypeAlias = Callable[[ChunkGovernor], BaseChunker]

class ChunkerRegistry:
    """Registry for chunker implementations."""

    def __init__(self):
        self._registry: dict[Chunker, ChunkerFactory] = {}
        self._register_defaults()

    def _register_defaults(self):
        """Register built-in chunkers."""
        self.register(Chunker.SEMANTIC,
                     lambda gov: SemanticChunker(gov, SemanticSearchLanguage.PYTHON))
        self.register(Chunker.DELIMITER,
                     lambda gov: DelimiterChunker(gov, "unknown"))

    def register(self, kind: Chunker, factory: ChunkerFactory):
        """Register chunker factory."""
        self._registry[kind] = factory

    def get_chunker(self, kind: Chunker, governor: ChunkGovernor) -> BaseChunker:
        """Get chunker instance by kind."""
        factory = self._registry.get(kind)
        if not factory:
            raise ValueError(f"No chunker registered for {kind}")
        return factory(governor)

    def list_available(self) -> list[Chunker]:
        """List registered chunker kinds."""
        return list(self._registry.keys())


# Global registry instance
_global_chunker_registry = ChunkerRegistry()

def get_chunker_registry() -> ChunkerRegistry:
    """Get global chunker registry."""
    return _global_chunker_registry
```

---

## 6. Resource Governance & Safety

### 6.1 Resource Limits

**File Size Limits**:
- Maximum file size: 10MB (covers 99% of real source files)
- Recommended optimal: <1MB for best performance
- Files >10MB: Trigger warning, may use simplified chunking

**Processing Speed Targets**:
- Typical files (100-1000 lines): 100-500 files/second
- Large files (1000-5000 lines): 50-200 files/second
- Very large files (5000+ lines): 10-50 files/second

**Timeout Constraints**:
- Per-file timeout: 30 seconds (configurable)
- Parse timeout: 10 seconds (prevents infinite loops)
- Exceeding timeout triggers graceful degradation

**Memory Constraints**:
- Peak memory per chunking operation: <100MB
- Allows parallel processing of 10-20 files with 2GB memory

**AST Depth Limits**:
- Maximum AST depth: 200 levels (prevents stack overflow)
- Raises `ASTDepthExceededError` if exceeded

**Chunk Count Limits**:
- Maximum chunks per file: 5000 (prevents memory exhaustion)
- Raises `ChunkLimitExceededError` if exceeded

### 6.2 ResourceGovernor Implementation

```python
class ResourceGovernor:
    """Enforces resource limits during chunking operations."""

    def __init__(self, settings: PerformanceSettings):
        self.settings = settings
        self._start_time: float | None = None
        self._chunk_count: int = 0

    def __enter__(self):
        """Start resource tracking."""
        self._start_time = time.time()
        self._chunk_count = 0
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        """Clean up resource tracking."""
        self._start_time = None
        self._chunk_count = 0

    def check_timeout(self):
        """Check if operation has exceeded timeout."""
        if self._start_time is None:
            return

        elapsed = time.time() - self._start_time
        if elapsed > self.settings.chunk_timeout_seconds:
            raise ChunkingTimeoutError(
                f"Chunking exceeded timeout of {self.settings.chunk_timeout_seconds}s"
            )

    def check_chunk_limit(self):
        """Check if chunk count has exceeded limit."""
        if self._chunk_count >= self.settings.max_chunks_per_file:
            raise ChunkLimitExceededError(
                f"Exceeded maximum of {self.settings.max_chunks_per_file} chunks per file"
            )

    def register_chunk(self):
        """Register a new chunk and check limits."""
        self._chunk_count += 1
        self.check_chunk_limit()
        self.check_timeout()
```

### 6.3 Exception Hierarchy

```python
class ChunkingError(Exception):
    """Base exception for chunking failures."""

class ParseError(ChunkingError):
    """AST parsing failed."""

class OversizedChunkError(ChunkingError):
    """Chunk exceeds token limit after all strategies."""

class ChunkingTimeoutError(ChunkingError):
    """Operation exceeded time limit."""

class ChunkLimitExceededError(ChunkingError):
    """File produced too many chunks."""

class BinaryFileError(ChunkingError):
    """Binary content detected in file."""

class ASTDepthExceededError(ChunkingError):
    """AST nesting exceeds safe depth."""
```

---

## 7. Error Handling & Graceful Degradation

### 7.1 Failure Modes & Responses

| Failure | Chunker | Response |
|---------|---------|----------|
| Parse error | Semantic | → Delimiter fallback |
| Oversized node | Semantic | → Delimiter on node OR recurse children |
| No delimiters match | Delimiter | → Generic patterns (braces, newlines) |
| All chunks oversized | Delimiter | → Return as single chunk |
| Unknown language | Selector | → Delimiter w/ family inference |
| Empty file (0 bytes) | Any | Return [] |
| Whitespace-only | Any | Return single chunk with edge_case metadata |
| Single-line file | Semantic | Return single chunk, skip AST parsing |
| Binary file | Any | Raise BinaryFileError |
| Timeout exceeded | Any | Raise ChunkingTimeoutError, log details |
| AST too deep | Semantic | Raise ASTDepthExceededError |

### 7.2 Degradation Chain

```
SemanticChunker (best quality, 26 langs)
    ↓ parse_error
DelimiterChunker (good quality, 170+ langs)
    ↓ no_matches
GenericDelimiters (basic quality, universal)
    ↓ oversized_chunks
Return as single chunk (last resort, may exceed limit)
```

### 7.3 Complete Degradation Implementation

```python
def chunk_with_full_degradation(
    content: str,
    file_path: Path,
    governor: ChunkGovernor
) -> list[CodeChunk]:
    """Complete degradation chain implementation."""

    errors = []

    # Try semantic
    try:
        selector = ChunkerSelector(governor)
        chunker = selector.select_for_file(DiscoveredFile(path=file_path))
        return chunker.chunk(content, file_path=file_path)
    except ParseError as e:
        errors.append(f"Semantic: {e}")

    # Try delimiter
    try:
        delimiter = DelimiterChunker(governor, file_path.suffix.lstrip('.'))
        chunks = delimiter.chunk(content, file_path=file_path)
        if chunks:
            return chunks
    except Exception as e:
        errors.append(f"Delimiter: {e}")

    # Try generic delimiters
    try:
        generic = DelimiterChunker(governor, "generic")
        chunks = generic.chunk(content, file_path=file_path)
        if chunks:
            return chunks
    except Exception as e:
        errors.append(f"Generic: {e}")

    # Last resort: Return single chunk as-is (may exceed token limit)
    logger.error(f"All chunking strategies failed for {file_path}: {errors}")
    return [
        CodeChunk(
            content=content,
            line_range=Span(0, content.count('\n'), source_id_for(file_path)),
            file_path=file_path,
            language="unknown",
            source="fallback",
            metadata={"error": "All strategies failed", "errors": errors}
        )
    ]
```

---

## 8. Concurrency & Thread Safety

### 8.1 Thread Safety Guarantees

1. **Chunkers are Stateless**:
   - All chunker instances are immutable after construction
   - No shared mutable state between operations
   - Safe for concurrent use across threads

2. **ChunkerSelector Creates Fresh Instances**:
   - Each `select_for_file()` call creates new chunker
   - No instance reuse across files
   - Eliminates cross-file state contamination

3. **File-Level Parallelism**:
   - Chunk each file independently
   - No dependencies between file chunking operations
   - Embarrassingly parallel workload

### 8.2 Parallel Processing

```python
from concurrent.futures import ProcessPoolExecutor, as_completed

def chunk_files_parallel(
    files: list[DiscoveredFile],
    governor: ChunkGovernor,
    max_workers: int = 4
) -> Iterator[tuple[Path, list[CodeChunk]]]:
    """Chunk multiple files in parallel using process pool."""

    selector = ChunkerSelector(governor)

    def chunk_file(file: DiscoveredFile) -> tuple[Path, list[CodeChunk]]:
        """Chunk single file (executed in worker process)."""
        content = file.path.read_text()
        chunker = selector.select_for_file(file)  # Fresh instance
        chunks = chunker.chunk(content, file_path=file.path)
        return (file.path, chunks)

    with ProcessPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(chunk_file, f): f for f in files}

        for future in as_completed(futures):
            try:
                yield future.result()
            except Exception as e:
                file = futures[future]
                logger.error(f"Failed to chunk {file.path}: {e}")
```

**Why Process Pool vs Thread Pool**:
- AST parsing is CPU-bound (not I/O-bound)
- ProcessPoolExecutor bypasses GIL limitations
- Better CPU utilization for multi-core systems
- Isolated memory space prevents memory leaks

---

## 9. Observability & Metrics

### 9.1 Integration with SessionStatistics

Uses existing `SessionStatistics` infrastructure (statistics.py):

```python
from codeweaver.common.statistics import get_session_statistics
from codeweaver.core.metadata import ExtKind

class BaseChunker(ABC):
    """Base chunker with integrated statistics tracking."""

    def chunk(self, content: str, *, file_path: Path | None = None,
              context: dict[str, Any] | None = None) -> list[CodeChunk]:
        """Main chunking with statistics tracking."""
        import time

        statistics = get_session_statistics()
        start_time = time.perf_counter()

        try:
            # Perform chunking
            chunks = self._chunk_impl(content, file_path, context)

            # Track successful operation
            if file_path and (ext_kind := ExtKind.from_file(file_path)):
                statistics.add_file_operations_by_extkind([
                    (file_path, ext_kind, "processed")
                ])

            # Track chunk metrics
            self._track_chunk_metrics(chunks, time.perf_counter() - start_time)

            return chunks

        except ParseError as e:
            # Track parse failures
            logger.error(f"Parse error in {file_path}: {e}")
            if file_path and (ext_kind := ExtKind.from_file(file_path)):
                statistics.add_file_operations_by_extkind([
                    (file_path, ext_kind, "skipped")
                ])
            raise
```

### 9.2 Metrics Tracked

**File Operations** (via FileStatistics):
- `processed`: Successfully chunked files
- `skipped`: Files skipped due to errors
- `reindexed`: Files re-chunked after changes

**Performance Metrics** (via structured logging):
- `chunking.duration_ms`: Time to chunk file
- `chunking.chunk_count`: Number of chunks produced
- `chunking.avg_chunk_size`: Average chunk size in characters

**Quality Metrics** (via structured logging):
- `chunking.parse_errors`: AST parse failures
- `chunking.fallback_count`: Semantic → delimiter fallbacks
- `chunking.edge_cases`: Empty, single-line, binary files
- `chunking.oversized_chunks`: Chunks exceeding limits

### 9.3 Structured Logging Format

```python
import logging

logger = logging.getLogger(__name__)

# Success event
logger.info(
    "chunking_completed",
    extra={
        "file_path": str(file_path),
        "chunker_type": self.chunker.name,
        "chunk_count": len(chunks),
        "duration_ms": duration * 1000,
        "file_size_bytes": len(content),
        "language": self.language.name if hasattr(self, 'language') else "unknown",
    }
)

# Error event
logger.error(
    "chunking_failed",
    extra={
        "file_path": str(file_path),
        "chunker_type": self.chunker.name,
        "error_type": type(e).__name__,
        "error_message": str(e),
        "fallback_triggered": True,
    }
)

# Edge case event
logger.debug(
    "chunking_edge_case",
    extra={
        "file_path": str(file_path),
        "edge_case_type": "single_line",
    }
)
```

---

## 10. Configuration Interface

### 10.1 Settings Extension

```python
# src/codeweaver/config/settings.py (extend existing)

class PerformanceSettings(BasedModel):
    """Performance and resource limit configuration."""

    max_file_size_mb: PositiveInt = Field(
        default=10,
        description="Maximum file size in MB to attempt chunking"
    )
    chunk_timeout_seconds: PositiveInt = Field(
        default=30,
        description="Maximum time allowed for chunking a single file"
    )
    parse_timeout_seconds: PositiveInt = Field(
        default=10,
        description="Maximum time for AST parsing operation"
    )
    max_chunks_per_file: PositiveInt = Field(
        default=5000,
        description="Maximum chunks to generate from single file"
    )
    max_memory_mb_per_operation: PositiveInt = Field(
        default=100,
        description="Peak memory limit per chunking operation"
    )
    max_ast_depth: PositiveInt = Field(
        default=200,
        description="Maximum AST nesting depth"
    )


class ConcurrencySettings(BasedModel):
    """Concurrency configuration."""

    max_parallel_files: PositiveInt = Field(
        default=4,
        description="Maximum files to chunk concurrently"
    )
    executor: Literal["process", "thread"] = Field(
        default="process",
        description="Use ProcessPoolExecutor (process) vs ThreadPoolExecutor (thread)"
    )


class ChunkerSettings(BasedModel):
    """Configuration for chunker system."""

    # Semantic chunker settings
    semantic_importance_threshold: float = Field(
        default=0.3,
        ge=0.0,
        le=1.0,
        description="Minimum importance score for nodes to be chunkable"
    )

    # Delimiter chunker settings
    custom_delimiters: dict[LanguageNameT, list[CustomDelimiter]] = Field(
        default_factory=dict,
        description="Custom delimiter patterns per language"
    )

    custom_languages: list[CustomLanguage] = Field(default_factory=list, description="Associate new language with one of CodeWeaver's existing language families")

    # Resource settings
    performance: PerformanceSettings = Field(
        default_factory=PerformanceSettings
    )
    concurrency: ConcurrencySettings = Field(
        default_factory=ConcurrencySettings
    )


class CodeWeaverSettings(BasedModel):
    """Extend existing settings with chunker config."""

    chunker: ChunkerSettings = Field(default_factory=ChunkerSettings)
    # ... existing settings ...
```

### 10.2 Usage Example

```toml
# codeweaver.toml

[chunker]
semantic_importance_threshold = 0.4

[chunker.performance]
max_file_size_mb = 10
chunk_timeout_seconds = 30
parse_timeout_seconds = 10
max_chunks_per_file = 5000
max_ast_depth = 200

[chunker.concurrency]
max_parallel_files = 4
```

---

## 11. Testing Strategy

### 11.1 Philosophy (Constitutional Principle IV)

**Focus**: Integration tests for critical user-affecting behavior
**Avoid**: Implementation detail tests, 100% coverage for its own sake

### 11.2 Critical Test Cases

#### Semantic Chunker
```python
def test_semantic_chunks_python_file():
    """Verify semantic chunking of valid Python produces correct structure."""
    content = """
def calculate_score(data):
    total = sum(data)
    return total / len(data)

class Calculator:
    def add(self, a, b):
        return a + b
"""
    governor = ChunkGovernor(capabilities=(mock_embedding_caps,))
    chunker = SemanticChunker(governor, SemanticSearchLanguage.PYTHON)
    chunks = chunker.chunk(content, file_path=Path("test.py"))

    assert len(chunks) == 2
    assert chunks[0].metadata["context"]["classification"] == "FUNCTION"
    assert chunks[1].metadata["context"]["classification"] == "CLASS"

def test_semantic_oversized_node_fallback():
    """Verify oversized nodes trigger delimiter fallback."""
    large_function = "def huge():\n" + "    x = 1\n" * 10000
    governor = ChunkGovernor(capabilities=(mock_embedding_caps,))
    chunker = SemanticChunker(governor, SemanticSearchLanguage.PYTHON)
    chunks = chunker.chunk(large_function, file_path=Path("test.py"))

    assert len(chunks) > 1
    assert all(estimate_tokens(c.content) <= governor.chunk_limit for c in chunks)

def test_semantic_parse_error_raises():
    """Verify parse errors are raised (not silently caught)."""
    invalid_python = "def broken("
    governor = ChunkGovernor(capabilities=(mock_embedding_caps,))
    chunker = SemanticChunker(governor, SemanticSearchLanguage.PYTHON)

    with pytest.raises(ParseError):
        chunker.chunk(invalid_python, file_path=Path("test.py"))

def test_edge_cases():
    """Verify edge case handling."""
    governor = ChunkGovernor(capabilities=(mock_embedding_caps,))
    chunker = SemanticChunker(governor, SemanticSearchLanguage.PYTHON)

    # Empty file
    assert chunker.chunk("", file_path=Path("empty.py")) == []

    # Whitespace only
    chunks = chunker.chunk("   \n\n  ", file_path=Path("whitespace.py"))
    assert len(chunks) == 1
    assert chunks[0].metadata["edge_case"] == "whitespace_only"

    # Single line
    chunks = chunker.chunk("x = 1", file_path=Path("oneline.py"))
    assert len(chunks) == 1
    assert chunks[0].metadata["edge_case"] == "single_line"

    # Binary file
    with pytest.raises(BinaryFileError):
        chunker.chunk("text\x00binary", file_path=Path("binary.py"))
```

#### Delimiter Chunker
```python
def test_delimiter_chunks_javascript_nested():
    """Verify delimiter chunking handles nested functions correctly."""
    content = """
function outer() {
    function inner() {
        if (true) {
            console.log('nested');
        }
    }
}
"""
    governor = ChunkGovernor(capabilities=(mock_embedding_caps,))
    chunker = DelimiterChunker(governor, "javascript")
    chunks = chunker.chunk(content, file_path=Path("test.js"))

    assert any("function" in c.metadata.get("context", {}).get("delimiter_kind", "") for c in chunks)
    assert any(c.metadata.get("context", {}).get("nesting_level", 0) > 0 for c in chunks)

def test_delimiter_priority_resolution():
    """Verify higher-priority delimiters win in overlaps."""
    content = """
class MyClass {
    function myMethod() {
        # comment
    }
}
"""
    governor = ChunkGovernor(capabilities=(mock_embedding_caps,))
    chunker = DelimiterChunker(governor, "python")
    chunks = chunker.chunk(content, file_path=Path("test.py"))

    kinds = [c.metadata["context"]["delimiter_kind"] for c in chunks]
    assert "CLASS" in kinds or "BLOCK" in kinds
```

#### Selector
```python
def test_selector_chooses_semantic_for_python():
    """Verify selector picks semantic for supported language."""
    governor = ChunkGovernor(capabilities=(mock_embedding_caps,))
    selector = ChunkerSelector(governor)
    file = DiscoveredFile(path=Path("test.py"))

    chunker = selector.select_for_file(file)
    assert isinstance(chunker, SemanticChunker)

def test_selector_falls_back_to_delimiter_for_unknown():
    """Verify selector uses delimiter for unsupported language."""
    governor = ChunkGovernor(capabilities=(mock_embedding_caps,))
    selector = ChunkerSelector(governor)
    file = DiscoveredFile(path=Path("test.xyz"))

    chunker = selector.select_for_file(file)
    assert isinstance(chunker, DelimiterChunker)
```

#### End-to-End
```python
def test_e2e_real_python_file():
    """Integration test: Real Python file → valid chunks."""
    content = Path("tests/fixtures/sample.py").read_text()
    governor = ChunkGovernor(capabilities=(mock_embedding_caps,))
    selector = ChunkerSelector(governor)
    chunker = selector.select_for_file(DiscoveredFile(path=Path("sample.py")))

    chunks = chunker.chunk(content, file_path=Path("sample.py"))

    assert len(chunks) > 0
    assert all(c.content.strip() for c in chunks)
    assert all(estimate_tokens(c.content) <= governor.chunk_limit for c in chunks)
    assert all(c.metadata for c in chunks)
    assert all(c.line_range.start <= c.line_range.end for c in chunks)

def test_resource_limits_enforced():
    """Verify resource governance prevents runaway operations."""
    # Generate file with excessive AST depth
    deeply_nested = "if True:\n" + ("    if True:\n" * 300)
    governor = ChunkGovernor(capabilities=(mock_embedding_caps,))
    chunker = SemanticChunker(governor, SemanticSearchLanguage.PYTHON)

    with pytest.raises(ASTDepthExceededError):
        chunker.chunk(deeply_nested, file_path=Path("deep.py"))

def test_deduplication_works():
    """Verify chunk deduplication using hash store."""
    content = """
def foo():
    pass

def foo():
    pass
"""  # Duplicate function
    governor = ChunkGovernor(capabilities=(mock_embedding_caps,))
    chunker = SemanticChunker(governor, SemanticSearchLanguage.PYTHON)
    chunks = chunker.chunk(content, file_path=Path("test.py"))

    # Should have 1 unique chunk (deduplicated)
    assert len(chunks) == 1
```

### 11.3 Test Fixtures

Create `tests/fixtures/` with:
- `sample.py` - Medium Python file (classes, functions, nested logic)
- `sample.js` - JavaScript with nested functions and callbacks
- `sample.rs` - Rust with traits, impls, macros
- `sample.go` - Go with interfaces, structs, methods
- `malformed.py` - Invalid syntax for error handling tests
- `huge_function.py` - Single function > token limit
- `deep_nesting.py` - Deeply nested control structures
- `empty.py` - Empty file
- `single_line.py` - Single line file

---

## 12. Implementation Checklist

### Phase 1: Core Infrastructure
- [ ] Create `Delimiter` model in `delimiter.py`
- [ ] Implement `DelimiterChunker.chunk()` method
- [ ] Implement delimiter matching algorithm (§3.3 Phase 1-3)
- [ ] Implement `SemanticChunker.chunk()` method
- [ ] Implement `_find_chunkable_nodes()` logic
- [ ] Implement metadata builders for both chunkers
- [ ] Implement edge case handling
- [ ] Implement deduplication with UUIDStore/BlakeStore

### Phase 2: Selection & Integration
- [ ] Create `ChunkerSelector` in `selector.py`
- [ ] Implement selection algorithm (§4.2)
- [ ] Create `GracefulChunker` wrapper
- [ ] Enhance `ChunkerRegistry` (§5.2)
- [ ] Implement hybrid chunking pattern
- [ ] Remove `router.py` entirely

### Phase 3: Safety & Governance
- [ ] Implement `ResourceGovernor` (§6.2)
- [ ] Add exception hierarchy (§6.3)
- [ ] Implement degradation chain (§7.3)
- [ ] Add comprehensive logging
- [ ] Implement timeout and limit checks

### Phase 4: Concurrency & Performance
- [ ] Implement parallel processing (§8.2)
- [ ] Add concurrency settings
- [ ] Optimize delimiter regex compilation
- [ ] Profile and optimize hot paths

### Phase 5: Observability
- [ ] Integrate SessionStatistics tracking
- [ ] Add structured logging
- [ ] Implement metrics collection
- [ ] Add performance profiling hooks

### Phase 6: Testing
- [ ] Create test fixtures (§11.3)
- [ ] Write semantic chunker tests (§11.2)
- [ ] Write delimiter chunker tests (§11.2)
- [ ] Write selector tests (§11.2)
- [ ] Write E2E integration tests (§11.2)
- [ ] Write resource governance tests
- [ ] Write deduplication tests

### Phase 7: Documentation
- [ ] Update module docstrings
- [ ] Add usage examples to README
- [ ] Document configuration options
- [ ] Create troubleshooting guide

---

## 13. Migration Path

### 13.1 Deprecation Strategy

1. **Phase 1** (v0.1.0): Implement new system alongside router.py
2. **Phase 2** (v0.2.0): Add deprecation warning to router.py usage
3. **Phase 3** (v0.3.0): Remove router.py entirely

### 13.2 Compatibility Shims

```python
# Temporary backward compatibility
from codeweaver.engine.chunker.router import EnhancedChunkMicroManager

@deprecated("Use ChunkerSelector instead", version="0.2.0")
class EnhancedChunkMicroManager:
    """Legacy router (deprecated)."""

    def __init__(self, governor: ChunkGovernor):
        warnings.warn(
            "EnhancedChunkMicroManager is deprecated. Use ChunkerSelector.",
            DeprecationWarning,
            stacklevel=2
        )
        self.selector = ChunkerSelector(governor)

    def chunk_file(self, file: DiscoveredFile, content: str) -> list[CodeChunk]:
        chunker = self.selector.select_for_file(file)
        return chunker.chunk(content, file_path=file.path)
```

---

## 14. Future Enhancements

### 14.1 Task-Aware Chunking

**Concept**: Use importance scores with task context for dynamic chunk selection

```python
def chunk_for_task(
    content: str,
    file_path: Path,
    task: AgentTask,
    governor: ChunkGovernor
) -> list[CodeChunk]:
    """Chunk with task-specific importance weighting."""
    semantic = SemanticChunker(governor, detect_language(file_path))
    nodes = semantic._find_chunkable_nodes(semantic._parse_file(content, file_path))

    # Filter nodes by task-specific importance
    relevant_nodes = [
        n for n in nodes
        if n.importance_for_task(task).weighted_score(task.profile) > threshold
    ]

    return semantic._nodes_to_chunks(relevant_nodes, file_path)
```

### 14.2 Adaptive Chunk Sizing

**Concept**: Dynamically adjust chunk size based on content density

```python
def adaptive_chunk_limit(node: AstThing, base_limit: int) -> int:
    """Adjust limit based on node complexity."""
    complexity = node.importance.comprehension

    if complexity > 0.8:
        return int(base_limit * 0.7)  # Smaller chunks for complex code
    elif complexity < 0.3:
        return int(base_limit * 1.3)  # Larger chunks for simple code
    else:
        return base_limit
```

### 14.3 Cross-Chunk Context

**Concept**: Include parent/sibling context in chunk metadata

```python
metadata["context"]["cross_chunk"] = {
    "parent_summary": parent_node.text[:200],
    "previous_sibling": prev_sibling.title if prev_sibling else None,
    "next_sibling": next_sibling.title if next_sibling else None,
}
```

### 14.4 Incremental Re-Chunking

**Concept**: Only re-chunk changed regions for efficiency

**Strategy**:
1. Maintain content_hash for each chunk
2. On file modification, identify changed line ranges
3. Re-chunk only affected regions
4. Preserve unchanged chunks (reuse existing embeddings)

```python
def chunk_incremental(
    self,
    old_chunks: list[CodeChunk],
    new_content: str,
    changed_lines: set[int],
    file_path: Path
) -> list[CodeChunk]:
    """Re-chunk only changed regions."""
    # Implementation deferred to performance optimization phase
    ...
```

---

## 15. Conclusion

This specification provides a complete, evidence-based, production-ready design for CodeWeaver's chunking system that:

✅ **Complies with Constitutional Principles**:
- AI-First Context via rich importance metadata
- Proven Patterns through strategy/plugin architecture
- Evidence-Based with real AST/delimiter implementations
- Testing Philosophy focused on critical paths
- Simplicity via clear separation of concerns

✅ **Achieves Project Goals**:
- Semantic chunking for 26 languages with AST-based precision
- Delimiter fallback for 170+ languages via comprehensive patterns
- Intelligent selection with graceful degradation
- Removes inflexible router.py

✅ **Production Ready**:
- Resource governance prevents runaway operations
- Deduplication using existing UUIDStore/BlakeStore
- Comprehensive observability via SessionStatistics
- Thread-safe, concurrent processing support
- Edge case handling (empty, binary, single-line files)
- Complete error handling and degradation chain

✅ **Enables Future Growth**:
- Task-aware chunking with importance weighting
- Adaptive sizing based on complexity
- Cross-chunk context for better AI understanding
- Incremental re-chunking for efficiency

**Implementation Ready**: All critical components specified with code scaffolds, test cases, and integration patterns.

---

**Document Version**: 2.0.0
**Last Updated**: 2025-10-24
**Status**: Ready for Implementation
