<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# CodeWeaver Chunker System Architecture Specification

**Version**: 1.0.0
**Status**: Design Phase
**Author**: Claude Code (Sequential Analysis)
**Date**: 2025-10-23

## Executive Summary

Complete redesign of CodeWeaver's chunking system with:
- **Semantic Chunker**: AST-based chunking w/ rich AI-first metadata for 26 languages
- **Delimiter Chunker**: Pattern-based fallback for 170+ languages
- **Intelligent Selection**: Automatic chunker routing w/ graceful degradation
- **Constitutional Compliance**: Evidence-based, proven patterns, simplicity-focused

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
RecursiveTextSplitter (existing)
```

### 1.2 Design Principles (Constitutional)

| Principle | Implementation |
|-----------|----------------|
| **I. AI-First Context** | Rich importance scores in metadata → better agent ranking |
| **II. Proven Patterns** | Strategy pattern for chunker selection, plugin registry |
| **III. Evidence-Based** | Real AST/delimiter patterns, no mocks or placeholders |
| **IV. Testing Philosophy** | Integration tests for critical paths, not impl details |
| **V. Simplicity** | Flat structure, clear separation of concerns |

---

## 2. Semantic Chunker Design

### 2.1 Overview

**Purpose**: AST-based chunking leveraging sophisticated semantic analysis system
**Languages**: 26 w/ tree-sitter grammars (`SemanticSearchLanguage`)
**Key Advantage**: Rich metadata w/ importance scores → optimal AI context

### 2.2 Core Algorithm

```python
def chunk(content: str, file_path: Path) -> list[CodeChunk]:
    # 1. Parse file → FileThing (AST root)
    root = parse_file(content, file_path, language)

    # 2. Find chunkable nodes (filtered by classification & importance)
    nodes = find_chunkable_nodes(root)

    # 3. Convert to chunks w/ size enforcement
    chunks = []
    for node in nodes:
        if estimate_tokens(node.text) <= chunk_limit:
            chunks.append(create_chunk(node))
        else:
            # Oversized → recursively chunk children OR fallback to delimiter
            chunks.extend(handle_oversized_node(node))

    return chunks
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

```python
metadata = {
    # Human-readable ID
    "name": node.title,  # "Python-function_definition-Function: 'calculate_score'"

    # Semantic classification
    "classification": node.classification.name,  # FUNCTION, CLASS, LOOP, etc.
    "kind": node.name,  # Grammar kind: "function_definition"
    "category": node.primary_category,  # "declaration", "statement", etc.

    # Importance scoring (task-aware!)
    "importance": {
        "discovery": float,      # Finding new code
        "comprehension": float,  # Understanding logic
        "modification": float,   # Making changes
        "debugging": float,      # Finding bugs
        "documentation": float,  # Writing docs
    },

    # Structural context
    "is_composite": bool,
    "parent_kind": str | None,
    "nesting_level": int,

    # Rich semantic data
    "semantic_meta": {
        "has_explicit_rule": bool,
        "connection_count": int,
        "primary_category": str,
    }
}
```

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

### 2.6 Implementation Scaffold

```python
# src/codeweaver/engine/chunker/semantic.py

class SemanticChunker(BaseChunker):
    """AST-based chunker w/ rich semantic metadata."""

    chunker = Chunker.SEMANTIC  # Registry key

    def __init__(self, governor: ChunkGovernor, language: SemanticSearchLanguage):
        super().__init__(governor)
        self.language = language
        self._importance_threshold = 0.3  # Configurable via governor

    def chunk(self, content: str, *, file_path: Path | None = None,
              context: dict[str, Any] | None = None) -> list[CodeChunk]:
        """Main chunking entry point."""
        # Implementation per 2.2 algorithm
        ...

    def _parse_file(self, content: str, file_path: Path) -> FileThing:
        """Parse content to AST root."""
        from ast_grep_py import SgRoot
        return FileThing.from_sg_root(SgRoot(content, self.language.value))

    def _find_chunkable_nodes(self, root: FileThing) -> list[AstThing]:
        """Traverse AST, filter by classification & importance."""
        chunkable = []
        for node in root.root._node.children():  # Direct access to sg_node
            ast_thing = AstThing.from_sg_node(node, self.language)
            if self._is_chunkable(ast_thing):
                chunkable.append(ast_thing)
        return chunkable

    def _is_chunkable(self, node: AstThing) -> bool:
        """Check if node meets chunkable criteria."""
        if not node.classification or node.classification.name == "UNKNOWN":
            return node.is_composite  # Include containers even w/o classification

        if node.importance:
            return any(score >= self._importance_threshold
                      for score in node.importance.as_dict().values())

        return True  # Default include if has classification

    def _nodes_to_chunks(self, nodes: list[AstThing], file_path: Path) -> list[CodeChunk]:
        """Convert AstThings to CodeChunks w/ size management."""
        chunks = []
        for node in nodes:
            node_text = node.text
            tokens = estimate_tokens(node_text)

            if tokens <= self.chunk_limit:
                chunks.append(self._create_chunk_from_node(node, file_path))
            else:
                chunks.extend(self._handle_oversized_node(node, file_path))

        return chunks

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
            ext_kind=self.chunker,
            metadata=metadata,
        )

    def _build_metadata(self, node: AstThing) -> Metadata:
        """Build rich AI-first metadata from AST node."""
        importance_dict = (
            node.importance.as_dict() if node.importance
            else None
        )

        return {
            "name": node.title,
            "classification": node.classification.name if node.classification else None,
            "kind": str(node.name),
            "category": node.primary_category,
            "importance": importance_dict,
            "is_composite": node.is_composite,
            "parent_kind": node.parent.name if node.parent else None,
            "nesting_level": len(list(node.ancestors())),
            "semantic_meta": {
                "has_explicit_rule": node.has_explicit_rule,
                "connection_count": len(list(node.positional_connections)),
            }
        }

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
                    # Recursive oversized handling
                    child_chunks.extend(self._handle_oversized_node(child, file_path))

            if child_chunks:
                return child_chunks

        # Fallback: Use delimiter chunker on this node's text
        from codeweaver.engine.chunker.delimiter import DelimiterChunker
        delimiter_chunker = DelimiterChunker(self.governor, self.language.name)
        return delimiter_chunker.chunk(node.text, file_path=file_path)
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
            end_pos=None,  # Filled in phase 2
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
            # Find matching start (LIFO for nestable, specific for non-nestable)
            if match.delimiter.nestable:
                start = stack.pop()
            else:
                start = next(m for m in reversed(stack)
                           if m.delimiter.kind == match.delimiter.kind)
                stack.remove(start)

            # Create boundary
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
    """Keep highest-priority non-overlapping boundaries."""
    # Sort by priority (high → low), then position
    sorted_bounds = sorted(boundaries,
                          key=lambda b: (-b.delimiter.priority, b.start))

    selected = []
    for boundary in sorted_bounds:
        # Check if overlaps with already-selected boundaries
        if not any(self._overlaps(boundary, s) for s in selected):
            selected.append(boundary)

    return sorted(selected, key=lambda b: b.start)  # Re-sort by position
```

### 3.4 Metadata Structure

```python
metadata = {
    "name": f"{delimiter.kind.name.title()} at line {start_line}",
    "delimiter_kind": delimiter.kind.name,
    "delimiter_start": delimiter.start,
    "delimiter_end": delimiter.end,
    "priority": delimiter.priority,
    "nesting_level": boundary.nesting_level,
    "inclusive": delimiter.inclusive,
}
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
        # Sort by priority descending
        self.delimiters.sort(key=lambda d: d.priority, reverse=True)
        self._delimiter_map = {d.start: d for d in self.delimiters}

    def chunk(self, content: str, *, file_path: Path | None = None,
              context: dict[str, Any] | None = None) -> list[CodeChunk]:
        """Main chunking entry point."""
        # Implementation per 3.3 algorithm
        matches = self._find_delimiter_matches(content)
        boundaries = self._extract_boundaries(matches)
        boundaries = self._resolve_overlaps(boundaries)
        return self._boundaries_to_chunks(boundaries, content, file_path)

    def _load_delimiters_for_language(self, language: str) -> list[Delimiter]:
        """Load delimiter set for language."""
        from codeweaver.engine.chunker.delimiters import families

        # Try language-specific patterns first
        family = families.detect_language_family(language)
        patterns = families.get_patterns_for_family(family)

        # Expand patterns to concrete delimiters
        delimiters = []
        for pattern in patterns:
            delimiters.extend(Delimiter.from_pattern(pattern))

        return delimiters

    def _find_delimiter_matches(self, content: str) -> list[DelimiterMatch]:
        """Find all delimiter occurrences. (See 3.3 Phase 1)"""
        ...

    def _extract_boundaries(self, matches: list[DelimiterMatch]) -> list[Boundary]:
        """Match starts with ends, handle nesting. (See 3.3 Phase 2)"""
        ...

    def _resolve_overlaps(self, boundaries: list[Boundary]) -> list[Boundary]:
        """Keep highest-priority non-overlapping boundaries. (See 3.3 Phase 3)"""
        ...

    def _boundaries_to_chunks(self, boundaries: list[Boundary],
                             content: str, file_path: Path) -> list[CodeChunk]:
        """Convert boundaries to CodeChunks w/ metadata."""
        chunks = []
        for i, boundary in enumerate(boundaries):
            # Extract text
            chunk_text = content[boundary.start:boundary.end]

            # Apply delimiter properties
            if not boundary.delimiter.inclusive:
                # Strip delimiter markers
                chunk_text = self._strip_delimiters(chunk_text, boundary.delimiter)

            if boundary.delimiter.take_whole_lines:
                # Expand to line boundaries
                chunk_text, line_start, line_end = self._expand_to_lines(
                    content, boundary.start, boundary.end
                )
            else:
                line_start, line_end = self._pos_to_lines(content, boundary.start, boundary.end)

            # Add overlap with adjacent chunks
            if i > 0:
                overlap_size = min(self.simple_overlap, boundary.start - boundaries[i-1].end)
                prefix = content[boundary.start - overlap_size:boundary.start]
                chunk_text = prefix + chunk_text

            # Create chunk
            metadata = self._build_metadata(boundary, line_start)
            chunks.append(CodeChunk(
                content=chunk_text,
                line_range=Span(line_start, line_end, source_id_for(file_path)),
                file_path=file_path,
                language=self.language,
                source="delimiter",
                ext_kind=self.chunker,
                metadata=metadata,
            ))

        return chunks

    def _build_metadata(self, boundary: Boundary, line: int) -> Metadata:
        """Build basic metadata from delimiter boundary."""
        return {
            "name": f"{boundary.delimiter.kind.name.title()} at line {line}",
            "delimiter_kind": boundary.delimiter.kind.name,
            "delimiter_start": boundary.delimiter.start,
            "delimiter_end": boundary.delimiter.end,
            "priority": boundary.delimiter.priority,
            "nesting_level": boundary.nesting_level,
        }
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
        """Select best chunker for given file."""
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
        return DelimiterChunker(self.governor, language.name if language else "unknown")

    def _detect_language(self, file: DiscoveredFile) -> SemanticSearchLanguage | str:
        """Detect language from file extension."""
        try:
            return SemanticSearchLanguage.from_extension(file.path.suffix)
        except ValueError:
            # Unknown extension, return as string for delimiter inference
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

## 6. Integration Patterns

### 6.1 Hybrid Chunking

**Use Case**: Semantic finds oversized node → use delimiter for fine-grained splitting

```python
# In SemanticChunker._handle_oversized_node():

def _handle_oversized_node(self, node: AstThing, file_path: Path) -> list[CodeChunk]:
    """Hybrid approach: semantic → delimiter for oversized."""

    # Try children first (pure semantic)
    if node.is_composite:
        child_chunks = self._try_chunk_children(node, file_path)
        if child_chunks:
            return child_chunks

    # Fallback: delimiter chunking on node text
    delimiter_chunker = DelimiterChunker(self.governor, self.language.name)
    delimiter_chunks = delimiter_chunker.chunk(node.text, file_path=file_path)

    # Enhance delimiter chunks w/ semantic context
    for chunk in delimiter_chunks:
        chunk.metadata["parent_semantic_node"] = node.title
        chunk.metadata["semantic_context"] = {
            "classification": node.classification.name if node.classification else None,
            "kind": str(node.name),
        }

    return delimiter_chunks
```

### 6.2 Parse Failure Recovery

```python
def chunk_with_recovery(content: str, file_path: Path,
                       governor: ChunkGovernor) -> list[CodeChunk]:
    """Attempt semantic, fallback to delimiter on parse error."""

    selector = ChunkerSelector(governor)
    language = SemanticSearchLanguage.from_extension(file_path.suffix)

    try:
        # Try semantic
        semantic = SemanticChunker(governor, language)
        return semantic.chunk(content, file_path=file_path)
    except ParseError as e:
        logger.info(f"Parse failed for {file_path}, using delimiter: {e}")
        # Fallback
        delimiter = DelimiterChunker(governor, language.name)
        return delimiter.chunk(content, file_path=file_path)
```

### 6.3 Mixed Content Files

**Example**: Markdown w/ code blocks

```python
def chunk_mixed_content(content: str, file_path: Path,
                       governor: ChunkGovernor) -> list[CodeChunk]:
    """Handle files with mixed content (e.g., markdown + code)."""

    # Use delimiter for outer structure (markdown sections)
    markdown_chunker = DelimiterChunker(governor, "markdown")
    sections = markdown_chunker.chunk(content, file_path=file_path)

    enhanced_chunks = []
    for section in sections:
        # Detect code blocks within section
        code_blocks = extract_code_blocks(section.content)

        if code_blocks:
            # Chunk code blocks semantically
            for block in code_blocks:
                lang = detect_code_block_language(block)
                if lang in SemanticSearchLanguage:
                    semantic = SemanticChunker(governor, lang)
                    enhanced_chunks.extend(semantic.chunk(block.content))
        else:
            # Keep markdown section as-is
            enhanced_chunks.append(section)

    return enhanced_chunks
```

---

## 7. Error Handling & Graceful Degradation

### 7.1 Failure Modes & Responses

| Failure | Chunker | Response |
|---------|---------|----------|
| Parse error | Semantic | → Delimiter fallback |
| Oversized node | Semantic | → Delimiter on node OR recurse children |
| No delimiters match | Delimiter | → Generic patterns (braces, newlines) |
| All chunks oversized | Delimiter | → RecursiveTextSplitter |
| Unknown language | Selector | → Delimiter w/ family inference |

### 7.2 Degradation Chain

```
SemanticChunker (best quality, 26 langs)
    ↓ parse_error
DelimiterChunker (good quality, 170+ langs)
    ↓ no_matches
GenericDelimiters (basic quality, universal)
    ↓ oversized_chunks
RecursiveTextSplitter (last resort, crude)
```

### 7.3 Error Handling Code

```python
class ChunkingError(Exception):
    """Base exception for chunking failures."""

class ParseError(ChunkingError):
    """AST parsing failed."""

class OversizedChunkError(ChunkingError):
    """Chunk exceeds token limit after all strategies."""


def chunk_with_full_degradation(content: str, file_path: Path,
                                governor: ChunkGovernor) -> list[CodeChunk]:
    """Complete degradation chain implementation."""

    errors = []

    # Try semantic
    try:
        selector = ChunkerSelector(governor)
        chunker = selector.select_for_file(DiscoveredFile(path=file_path))
        return chunker.chunk(content, file_path=file_path)
    except ParseError as e:
        errors.append(f"Semantic: {e}")
        # Continue to delimiter

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

    # Last resort: RecursiveTextSplitter
    logger.error(f"All chunking strategies failed for {file_path}: {errors}")
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=int(governor.chunk_limit * 0.9),
        chunk_overlap=governor.simple_overlap,
        length_function=estimate_tokens,
    )
    text_parts = splitter.split_text(content)
    return [
        CodeChunk(
            content=part,
            line_range=Span(0, part.count('\n'), source_id_for(file_path)),
            file_path=file_path,
            language="unknown",
            source="fallback",
            ext_kind=Chunker.UNKNOWN,
            metadata={"error": "All strategies failed", "errors": errors}
        )
        for part in text_parts
    ]
```

---

## 8. Testing Strategy

### 8.1 Philosophy (Constitutional Principle IV)

**Focus**: Integration tests for critical user-affecting behavior
**Avoid**: Implementation detail tests, 100% coverage for its own sake

### 8.2 Critical Test Cases

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

    assert len(chunks) == 2  # function + class
    assert chunks[0].metadata["classification"] == "FUNCTION"
    assert chunks[1].metadata["classification"] == "CLASS"
    assert "importance" in chunks[0].metadata

def test_semantic_oversized_node_fallback():
    """Verify oversized nodes trigger delimiter fallback."""
    large_function = "def huge():\n" + "    x = 1\n" * 10000  # Way over limit
    governor = ChunkGovernor(capabilities=(mock_embedding_caps,))
    chunker = SemanticChunker(governor, SemanticSearchLanguage.PYTHON)
    chunks = chunker.chunk(large_function, file_path=Path("test.py"))

    assert len(chunks) > 1  # Should be split
    assert all(estimate_tokens(c.content) <= governor.chunk_limit for c in chunks)

def test_semantic_parse_error_raises():
    """Verify parse errors are raised (not silently caught)."""
    invalid_python = "def broken("
    governor = ChunkGovernor(capabilities=(mock_embedding_caps,))
    chunker = SemanticChunker(governor, SemanticSearchLanguage.PYTHON)

    with pytest.raises(ParseError):
        chunker.chunk(invalid_python, file_path=Path("test.py"))
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

    # Should prioritize function boundaries over if blocks
    assert any("function" in c.metadata.get("delimiter_kind", "") for c in chunks)
    # Verify nesting levels tracked
    assert any(c.metadata.get("nesting_level", 0) > 0 for c in chunks)

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
    chunker = DelimiterChunker(governor, "python")  # Deliberately wrong lang for test
    chunks = chunker.chunk(content, file_path=Path("test.py"))

    # CLASS (priority 70) should beat COMMENT (priority 55)
    kinds = [c.metadata["delimiter_kind"] for c in chunks]
    assert "CLASS" in kinds or "BLOCK" in kinds
    assert kinds.count("COMMENT") < kinds.count("CLASS") + kinds.count("FUNCTION")
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

    # Assertions
    assert len(chunks) > 0
    assert all(c.content.strip() for c in chunks)  # No empty
    assert all(estimate_tokens(c.content) <= governor.chunk_limit for c in chunks)
    assert all(c.metadata for c in chunks)  # Has metadata
    assert all(c.line_range.start <= c.line_range.end for c in chunks)  # Valid ranges
```

### 8.3 Test Fixtures

Create `tests/fixtures/` with:
- `sample.py` - Medium Python file (classes, functions, nested logic)
- `sample.js` - JavaScript with nested functions and callbacks
- `sample.rs` - Rust with traits, impls, macros
- `sample.go` - Go with interfaces, structs, methods
- `malformed.py` - Invalid syntax for error handling tests
- `huge_function.py` - Single function > token limit

---

## 9. Implementation Checklist

### Phase 1: Core Infrastructure
- [ ] Create `Delimiter` model in `delimiter.py`
- [ ] Implement `DelimiterChunker.chunk()` method
- [ ] Implement delimiter matching algorithm (§3.3 Phase 1-2)
- [ ] Implement priority resolution (§3.3 Phase 3)
- [ ] Implement `SemanticChunker.chunk()` method
- [ ] Implement `_find_chunkable_nodes()` logic
- [ ] Implement metadata builders for both chunkers

### Phase 2: Selection & Integration
- [ ] Create `ChunkerSelector` in `selector.py`
- [ ] Implement selection algorithm (§4.2)
- [ ] Create `GracefulChunker` wrapper
- [ ] Enhance `ChunkerRegistry` (§5.2)
- [ ] Implement hybrid chunking pattern (§6.1)
- [ ] Remove `router.py` entirely

### Phase 3: Error Handling
- [ ] Implement degradation chain (§7.2)
- [ ] Add `ChunkingError` exception hierarchy
- [ ] Add comprehensive logging
- [ ] Implement parse error recovery

### Phase 4: Testing
- [ ] Create test fixtures (§8.3)
- [ ] Write semantic chunker tests (§8.2)
- [ ] Write delimiter chunker tests (§8.2)
- [ ] Write selector tests (§8.2)
- [ ] Write E2E integration tests (§8.2)

### Phase 5: Documentation
- [ ] Update module docstrings
- [ ] Add usage examples to README
- [ ] Document configuration options
- [ ] Create troubleshooting guide

---

## 10. Configuration Interface

### 10.1 Settings Extension

```python
# src/codeweaver/config/settings.py (extend existing)

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
    custom_delimiters: dict[str, list[DelimiterPattern]] = Field(
        default_factory=dict,
        description="Custom delimiter patterns per language"
    )

    # Selector settings
    prefer_semantic: bool = Field(
        default=True,
        description="Prefer semantic chunking when available"
    )

    force_delimiter_for_languages: list[str] = Field(
        default_factory=list,
        description="Languages to always use delimiter chunking for"
    )

    # Degradation settings
    enable_hybrid_chunking: bool = Field(
        default=True,
        description="Allow semantic to fallback to delimiter for oversized nodes"
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
prefer_semantic = true
enable_hybrid_chunking = true

force_delimiter_for_languages = ["latex", "markdown"]

[chunker.custom_delimiters.latex]
# Add custom LaTeX delimiters
# (Currently supported via patterns.py, but extensible here)
```

---

## 11. Performance Considerations

### 11.1 Optimization Strategies

| Component | Strategy | Expected Impact |
|-----------|----------|----------------|
| Delimiter matching | Combined regex (§3.3 Phase 1) | 10-50x faster vs individual |
| AST parsing | Cache parsed trees per file | Avoid re-parse on retry |
| Metadata building | Lazy evaluation | Only compute when accessed |
| Token estimation | Cache per chunk | Avoid repeated counting |

### 11.2 Memory Management

- Use generators for large file processing
- WeakValueDictionary for source ID registry (already exists)
- Stream chunks to vector store vs accumulating in memory

### 11.3 Profiling Points

```python
# Add telemetry hooks
with telemetry.timing("semantic_chunking"):
    chunks = semantic.chunk(content)

telemetry.counter("chunk_count", len(chunks))
telemetry.histogram("chunk_size_tokens", [estimate_tokens(c.content) for c in chunks])
```

---

## 12. Migration Path

### 12.1 Deprecation Strategy

1. **Phase 1** (v0.1.0): Implement new system alongside router.py
2. **Phase 2** (v0.2.0): Add deprecation warning to router.py usage
3. **Phase 3** (v0.3.0): Remove router.py entirely

### 12.2 Compatibility Shims

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

## 13. Future Enhancements

### 13.1 Task-Aware Chunking

**Concept**: Use importance scores with task context for dynamic chunk selection

```python
def chunk_for_task(content: str, file_path: Path,
                  task: AgentTask, governor: ChunkGovernor) -> list[CodeChunk]:
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

### 13.2 Adaptive Chunk Sizing

**Concept**: Dynamically adjust chunk size based on content density

```python
def adaptive_chunk_limit(node: AstThing, base_limit: int) -> int:
    """Adjust limit based on node complexity."""
    complexity = node.importance.comprehension  # Higher = more complex

    if complexity > 0.8:
        return int(base_limit * 0.7)  # Smaller chunks for complex code
    elif complexity < 0.3:
        return int(base_limit * 1.3)  # Larger chunks for simple code
    else:
        return base_limit
```

### 13.3 Cross-Chunk Context

**Concept**: Include parent/sibling context in chunk metadata

```python
metadata["context"] = {
    "parent_summary": parent_node.text[:200],  # First 200 chars of parent
    "previous_sibling": prev_sibling.title if prev_sibling else None,
    "next_sibling": next_sibling.title if next_sibling else None,
}
```

---

## 14. Conclusion

This specification provides a complete, evidence-based design for CodeWeaver's chunking system that:

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

✅ **Enables Future Growth**:
- Task-aware chunking with importance weighting
- Adaptive sizing based on complexity
- Cross-chunk context for better AI understanding

**Next Steps**: Begin Phase 1 implementation per §9 checklist.

---

**Document Version**: 1.0.0
**Last Updated**: 2025-10-23
**Status**: Ready for Implementation Review
