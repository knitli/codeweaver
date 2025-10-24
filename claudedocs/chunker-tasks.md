<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Tasks: CodeWeaver Chunker System v2.0

**Input**: chunker-architecture-spec.md v2.0.0
**Prerequisites**: Complete redesign spec with semantic/delimiter/selector architecture
**Status**: Ready for implementation

## Overview

Implementing the complete chunker system redesign with:
- **SemanticChunker**: AST-based chunking for 26 languages with rich metadata
- **DelimiterChunker**: Pattern-based fallback for 170+ languages
- **ChunkerSelector**: Intelligent routing with graceful degradation
- **Removes**: `router.py` (hardcoded, inflexible)
- **Adds**: `semantic.py`, `delimiter.py`, `selector.py`

## Path Conventions
- **Source**: `src/codeweaver/engine/chunker/`
- **Tests**: `tests/unit/engine/chunker/`, `tests/integration/chunker/`
- **Fixtures**: `tests/fixtures/`

---

## Phase 1: Foundation & Test Setup

### T001: Create Test Fixtures
**File**: `tests/fixtures/` (multiple files)
**Parallel**: No (file creation)

Create comprehensive test fixtures for chunking validation:
- `sample.py`: Medium Python file with classes, functions, nested logic
- `sample.js`: JavaScript with nested functions and callbacks
- `sample.rs`: Rust with traits, impls, macros
- `sample.go`: Go with interfaces, structs, methods
- `malformed.py`: Invalid syntax for error handling tests
- `huge_function.py`: Single function exceeding token limit (>2000 tokens)
- `deep_nesting.py`: Deeply nested control structures (>200 levels)
- `empty.py`: Empty file (0 bytes)
- `single_line.py`: Single line file
- `whitespace_only.py`: File with only whitespace
- `binary_mock.txt`: File with binary content (`\x00` bytes)

**Acceptance**:
- [ ] All fixture files created with realistic content
- [ ] `huge_function.py` exceeds 2000 tokens
- [ ] `deep_nesting.py` has >200 nesting levels
- [ ] Binary file contains null bytes for detection testing

---

### T002: Enhance Exception Hierarchy
**File**: `src/codeweaver/engine/chunker/exceptions.py`
**Parallel**: Yes [P] (new file)

Implement comprehensive exception hierarchy per spec §6.3:

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

**Acceptance**:
- [ ] All exceptions inherit from `ChunkingError`
- [ ] Each exception has descriptive docstring
- [ ] Exceptions importable from `chunker.exceptions`

---

### T003: Implement ResourceGovernor
**File**: `src/codeweaver/engine/chunker/governance.py`
**Parallel**: Yes [P] (new file)

Implement resource governance per spec §6.2:

```python
class ResourceGovernor:
    """Enforces resource limits during chunking operations."""

    def __init__(self, settings: PerformanceSettings): ...
    def __enter__(self) -> Self: ...
    def __exit__(self, exc_type, exc_val, exc_tb): ...
    def check_timeout(self): ...
    def check_chunk_limit(self): ...
    def register_chunk(self): ...
```

**Key Features**:
- Context manager for resource tracking
- Timeout enforcement (default 30s per file)
- Chunk count limits (default 5000 per file)
- Raises appropriate exceptions when limits exceeded

**Acceptance**:
- [ ] Context manager protocol implemented
- [ ] `check_timeout()` raises `ChunkingTimeoutError` when exceeded
- [ ] `register_chunk()` raises `ChunkLimitExceededError` at limit
- [ ] Thread-safe (no shared mutable state)

---

### T004: Extend Configuration Settings
**File**: `src/codeweaver/config/settings.py`
**Parallel**: No (modifies existing file)

Add chunker configuration per spec §10.1:

```python
class PerformanceSettings(BasedModel):
    max_file_size_mb: PositiveInt = 10
    chunk_timeout_seconds: PositiveInt = 30
    parse_timeout_seconds: PositiveInt = 10
    max_chunks_per_file: PositiveInt = 5000
    max_memory_mb_per_operation: PositiveInt = 100
    max_ast_depth: PositiveInt = 200

class ConcurrencySettings(BasedModel):
    max_parallel_files: PositiveInt = 4
    use_process_pool: bool = True

class ChunkerSettings(BasedModel):
    semantic_importance_threshold: float = 0.3
    custom_delimiters: dict[str, list[DelimiterPattern]] = Field(default_factory=dict)
    prefer_semantic: bool = True
    force_delimiter_for_languages: list[str] = Field(default_factory=list)
    enable_hybrid_chunking: bool = True
    performance: PerformanceSettings = Field(default_factory=PerformanceSettings)
    concurrency: ConcurrencySettings = Field(default_factory=ConcurrencySettings)
```

**Acceptance**:
- [ ] All settings use pydantic validation
- [ ] Default values match spec requirements
- [ ] Settings loadable from TOML config
- [ ] Settings accessible via `get_settings().chunker`

---

## Phase 2: Tests First (TDD) ⚠️ MUST COMPLETE BEFORE PHASE 3

### T005 [P]: Semantic Chunker - Basic Functionality Tests
**File**: `tests/unit/engine/chunker/test_semantic_basic.py`
**Parallel**: Yes [P] (new test file)

Write comprehensive tests for semantic chunker basic operations:

1. **test_semantic_chunks_python_file()**:
   - Load `sample.py` fixture
   - Verify chunk count matches expected structure
   - Assert metadata contains classification (FUNCTION, CLASS, etc.)
   - Verify chunk content matches original code sections

2. **test_semantic_chunks_javascript_file()**:
   - Load `sample.js` fixture
   - Verify JavaScript AST parsing works
   - Assert proper nested function handling

3. **test_semantic_chunks_rust_file()**:
   - Load `sample.rs` fixture
   - Verify Rust trait/impl chunking

**Acceptance**:
- [ ] All tests written and FAIL (no implementation yet)
- [ ] Tests verify chunk count, metadata, content integrity
- [ ] Tests use real fixtures from T001

---

### T006 [P]: Semantic Chunker - Edge Cases Tests
**File**: `tests/unit/engine/chunker/test_semantic_edge_cases.py`
**Parallel**: Yes [P] (new test file)

Write tests for all edge cases per spec §2.6:

1. **test_empty_file()**:
   - Input: `empty.py` (0 bytes)
   - Expected: Return `[]`

2. **test_whitespace_only_file()**:
   - Input: `whitespace_only.py`
   - Expected: Single chunk with `edge_case: whitespace_only` metadata

3. **test_single_line_file()**:
   - Input: `single_line.py`
   - Expected: Single chunk with `edge_case: single_line` metadata

4. **test_binary_file_detection()**:
   - Input: `binary_mock.txt`
   - Expected: Raise `BinaryFileError`

**Acceptance**:
- [ ] All edge case tests written and FAIL
- [ ] Binary detection test expects exception
- [ ] Edge case metadata properly specified

---

### T007 [P]: Semantic Chunker - Oversized Node Tests
**File**: `tests/unit/engine/chunker/test_semantic_oversized.py`
**Parallel**: Yes [P] (new test file)

Write tests for oversized node handling per spec §2.5:

1. **test_oversized_node_fallback_to_delimiter()**:
   - Input: `huge_function.py` (>2000 tokens)
   - Expected: Multiple chunks, all under token limit
   - Verify: Chunks have `parent_semantic_node` in metadata

2. **test_oversized_node_recursive_children()**:
   - Input: Class with large methods
   - Expected: Children chunked individually
   - Verify: Each chunk under limit

3. **test_all_strategies_fail_uses_text_splitter()**:
   - Input: Huge indivisible text block
   - Expected: Falls back to `RecursiveTextSplitter`
   - Verify: Metadata contains fallback indication

**Acceptance**:
- [ ] Tests verify token limits enforced
- [ ] Tests check fallback chain triggers correctly
- [ ] All tests FAIL (implementation pending)

---

### T008 [P]: Semantic Chunker - Error Handling Tests
**File**: `tests/unit/engine/chunker/test_semantic_errors.py`
**Parallel**: Yes [P] (new test file)

Write tests for error conditions:

1. **test_parse_error_raises()**:
   - Input: `malformed.py`
   - Expected: Raise `ParseError`

2. **test_ast_depth_exceeded_error()**:
   - Input: `deep_nesting.py` (>200 levels)
   - Expected: Raise `ASTDepthExceededError`

3. **test_timeout_exceeded()**:
   - Mock slow parsing operation
   - Expected: Raise `ChunkingTimeoutError`

4. **test_chunk_limit_exceeded()**:
   - Generate file producing >5000 chunks
   - Expected: Raise `ChunkLimitExceededError`

**Acceptance**:
- [ ] All error tests written
- [ ] Tests verify correct exception types raised
- [ ] Tests validate error messages are descriptive

---

### T009 [P]: Semantic Chunker - Deduplication Tests
**File**: `tests/unit/engine/chunker/test_semantic_dedup.py`
**Parallel**: Yes [P] (new test file)

Write tests for content deduplication per spec §2.7:

1. **test_duplicate_functions_deduplicated()**:
   - Input: File with duplicate function definitions
   - Expected: Only one chunk for duplicate content
   - Verify: Hash store tracks content hashes

2. **test_unique_chunks_preserved()**:
   - Input: File with similar but different functions
   - Expected: All unique chunks preserved

3. **test_batch_id_tracking()**:
   - Verify: All chunks in batch have same `batch_id`
   - Verify: Chunks stored in `UUIDStore` by batch

**Acceptance**:
- [ ] Deduplication tests written and FAIL
- [ ] Tests verify hash-based deduplication
- [ ] Batch ID tracking validated

---

### T010 [P]: Delimiter Chunker - Basic Tests
**File**: `tests/unit/engine/chunker/test_delimiter_basic.py`
**Parallel**: Yes [P] (new test file)

Write tests for delimiter chunker per spec §3:

1. **test_delimiter_chunks_javascript_nested()**:
   - Input: JavaScript with nested functions
   - Expected: Chunks respect function boundaries
   - Verify: Nesting levels tracked in metadata

2. **test_delimiter_priority_resolution()**:
   - Input: Code with overlapping delimiters
   - Expected: Higher priority delimiter wins
   - Verify: Only non-overlapping boundaries selected

3. **test_delimiter_chunks_python()**:
   - Input: Python code with class/function delimiters
   - Expected: Proper boundary detection

**Acceptance**:
- [ ] All delimiter tests written and FAIL
- [ ] Tests verify nesting handling
- [ ] Priority resolution validated

---

### T011 [P]: Delimiter Chunker - Edge Cases Tests
**File**: `tests/unit/engine/chunker/test_delimiter_edge_cases.py`
**Parallel**: Yes [P] (new test file)

Write delimiter-specific edge case tests:

1. **test_no_delimiters_match_uses_generic()**:
   - Input: File with no recognizable delimiters
   - Expected: Falls back to generic patterns (braces, newlines)

2. **test_inclusive_vs_exclusive_delimiters()**:
   - Verify: Inclusive delimiters include markers in chunks
   - Verify: Exclusive delimiters strip markers

3. **test_take_whole_lines_expansion()**:
   - Verify: Chunks expanded to line boundaries when configured

**Acceptance**:
- [ ] Edge case tests written and FAIL
- [ ] Generic fallback behavior tested
- [ ] Delimiter configuration options validated

---

### T012 [P]: Chunker Selector Tests
**File**: `tests/unit/engine/chunker/test_selector.py`
**Parallel**: Yes [P] (new test file)

Write tests for intelligent chunker selection per spec §4:

1. **test_selector_chooses_semantic_for_python()**:
   - Input: Python file
   - Expected: Returns `SemanticChunker` instance

2. **test_selector_falls_back_to_delimiter_for_unknown()**:
   - Input: `.xyz` file (unsupported language)
   - Expected: Returns `DelimiterChunker`

3. **test_selector_handles_parse_error_gracefully()**:
   - Input: Malformed Python file
   - Expected: Falls back to delimiter chunker
   - Verify: Warning logged

4. **test_selector_creates_fresh_instances()**:
   - Call selector twice for same file
   - Verify: Returns different instances (no reuse)

**Acceptance**:
- [ ] Selector routing tests written and FAIL
- [ ] Fallback behavior validated
- [ ] Instance isolation verified

---

### T013 [P]: Integration Tests - End-to-End
**File**: `tests/integration/chunker/test_e2e.py`
**Parallel**: Yes [P] (new test file)

Write integration tests for complete chunking workflows:

1. **test_e2e_real_python_file()**:
   - Input: Real `sample.py` fixture
   - Expected: Valid chunks, all under token limit
   - Verify: Metadata complete, line ranges valid

2. **test_e2e_multiple_files_parallel()**:
   - Input: Multiple fixtures (Python, JavaScript, Rust)
   - Process in parallel using process pool
   - Verify: All complete successfully, no state contamination

3. **test_e2e_degradation_chain()**:
   - Input: Malformed file
   - Expected: Full degradation chain executes
   - Verify: Eventually produces chunks via fallback

**Acceptance**:
- [ ] End-to-end tests written and FAIL
- [ ] Multi-file parallel processing tested
- [ ] Degradation chain validated

---

### T014 [P]: Resource Governance Tests
**File**: `tests/unit/engine/chunker/test_governance.py`
**Parallel**: Yes [P] (new test file)

Write tests for resource limits enforcement:

1. **test_timeout_enforcement()**:
   - Mock slow operation exceeding timeout
   - Verify: `ChunkingTimeoutError` raised

2. **test_chunk_limit_enforcement()**:
   - Generate operation producing >5000 chunks
   - Verify: `ChunkLimitExceededError` raised

3. **test_governor_context_manager()**:
   - Verify: Resources cleaned up on exit
   - Test both success and error exit paths

**Acceptance**:
- [ ] Governance tests written and FAIL
- [ ] Timeout and limit enforcement validated
- [ ] Context manager protocol tested

---

## Phase 3: Core Implementation (ONLY after all tests are failing)

### T015: Implement Delimiter Model
**File**: `src/codeweaver/engine/chunker/delimiter_model.py`
**Parallel**: Yes [P] (new file)

Implement `Delimiter` and supporting models per spec §3.2:

```python
class Delimiter(BasedModel):
    """Concrete delimiter definition."""
    start: str
    end: str
    kind: DelimiterKind
    priority: PositiveInt
    inclusive: bool
    take_whole_lines: bool
    nestable: bool

    @classmethod
    def from_pattern(cls, pattern: DelimiterPattern) -> list[Delimiter]: ...
```

Also implement:
- `DelimiterMatch` dataclass
- `Boundary` dataclass
- Helper functions for pattern expansion

**Acceptance**:
- [ ] `Delimiter` model validates all fields
- [ ] `from_pattern()` correctly expands patterns
- [ ] Dataclasses properly typed with type hints
- [ ] Tests T010-T011 start passing for models

---

### T016: Implement DelimiterChunker Core
**File**: `src/codeweaver/engine/chunker/delimiter.py`
**Parallel**: No (depends on T015)

Implement `DelimiterChunker` per spec §3.3-3.5:

Key methods:
- `chunk()`: Main entry point with edge case handling
- `_find_delimiter_matches()`: Regex-based match detection
- `_extract_boundaries()`: Match starts with ends, handle nesting
- `_resolve_overlaps()`: Priority-based overlap resolution
- `_boundaries_to_chunks()`: Convert boundaries to `CodeChunk` objects
- `_build_metadata()`: Create delimiter chunk metadata
- `_load_delimiters_for_language()`: Load delimiter patterns

**Acceptance**:
- [ ] All spec algorithms implemented correctly
- [ ] Nesting handled for nestable delimiters
- [ ] Priority resolution works per tie-breaking rules
- [ ] Tests T010-T011 pass completely

---

### T017: Implement SemanticChunker - Core Structure
**File**: `src/codeweaver/engine/chunker/semantic.py`
**Parallel**: No (depends on T003 ResourceGovernor)

Implement `SemanticChunker` skeleton and basic methods per spec §2.7:

```python
class SemanticChunker(BaseChunker):
    chunker = Chunker.SEMANTIC

    # Class-level deduplication stores
    _store: UUIDStore[list[CodeChunk]] = make_uuid_store(...)
    _hash_store: BlakeStore[UUID7] = make_blake_store(...)

    def __init__(self, governor: ChunkGovernor, language: SemanticSearchLanguage): ...
    def chunk(self, content: str, *, file_path: Path | None = None, ...) -> list[CodeChunk]: ...
    def _parse_file(self, content: str, file_path: Path) -> FileThing: ...
```

**Acceptance**:
- [ ] Skeleton implemented with all method signatures
- [ ] Deduplication stores initialized correctly
- [ ] `_parse_file()` wraps ast-grep parsing
- [ ] Basic structure tests pass

---

### T018: Implement SemanticChunker - Edge Case Handling
**File**: `src/codeweaver/engine/chunker/semantic.py`
**Parallel**: No (continues T017)

Implement `_handle_edge_cases()` method per spec §2.6:

```python
def _handle_edge_cases(self, content: str, file_path: Path) -> list[CodeChunk] | None:
    # Binary detection
    # Empty file handling
    # Whitespace-only handling
    # Single-line handling
    # Returns None to continue normal chunking
```

**Acceptance**:
- [ ] Binary file detection works (raises `BinaryFileError`)
- [ ] Empty files return `[]`
- [ ] Whitespace/single-line return appropriate chunks
- [ ] Tests T006 pass completely

---

### T019: Implement SemanticChunker - Node Finding
**File**: `src/codeweaver/engine/chunker/semantic.py`
**Parallel**: No (continues T018)

Implement node traversal and filtering per spec §2.3:

```python
def _find_chunkable_nodes(self, root: FileThing) -> list[AstThing]:
    # Traverse AST
    # Filter by classification and importance
    # Check AST depth limits

def _is_chunkable(self, node: AstThing) -> bool:
    # Classification check
    # Importance threshold check
    # Composite node handling

def _check_ast_depth(self, node: AstThing, max_depth: int = 200) -> None:
    # Verify depth limits
    # Raise ASTDepthExceededError if exceeded
```

**Acceptance**:
- [ ] Nodes filtered by importance threshold (default 0.3)
- [ ] Composite nodes properly identified
- [ ] AST depth limits enforced
- [ ] Tests T008 pass for depth errors

---

### T020: Implement SemanticChunker - Metadata Building
**File**: `src/codeweaver/engine/chunker/semantic.py`
**Parallel**: No (continues T019)

Implement metadata construction per spec §2.4:

```python
def _build_metadata(self, node: AstThing) -> Metadata:
    # Use existing SemanticMetadata.from_node()
    # Build Metadata TypedDict structure
    # Include chunker-specific context
    # Add importance scores, classification, etc.
```

**Acceptance**:
- [ ] Uses existing `Metadata` TypedDict structure
- [ ] Leverages `SemanticMetadata.from_node()` factory
- [ ] Includes all required context fields
- [ ] Tests T005 pass for metadata validation

---

### T021: Implement SemanticChunker - Chunk Creation
**File**: `src/codeweaver/engine/chunker/semantic.py`
**Parallel**: No (continues T020)

Implement chunk creation from AST nodes:

```python
def _create_chunk_from_node(self, node: AstThing, file_path: Path) -> CodeChunk:
    # Extract text and line range
    # Build metadata
    # Create CodeChunk instance
    # Set source="semantic"
```

**Acceptance**:
- [ ] Chunks correctly map line ranges
- [ ] Content matches node text exactly
- [ ] Metadata populated correctly
- [ ] Tests T005 pass for basic chunking

---

### T022: Implement SemanticChunker - Oversized Node Handling
**File**: `src/codeweaver/engine/chunker/semantic.py`
**Parallel**: No (continues T021)

Implement oversized node handling per spec §2.5:

```python
def _handle_oversized_node(self, node: AstThing, file_path: Path) -> list[CodeChunk]:
    # Try chunking children first
    # If composite: recursively chunk children
    # Fallback: Use DelimiterChunker on node.text
    # Enhance chunks with semantic context
    # Last resort: RecursiveTextSplitter
```

**Acceptance**:
- [ ] Children chunked recursively when possible
- [ ] Fallback to delimiter chunker works
- [ ] Semantic context preserved in metadata
- [ ] Tests T007 pass completely

---

### T023: Implement SemanticChunker - Deduplication
**File**: `src/codeweaver/engine/chunker/semantic.py`
**Parallel**: No (continues T022)

Implement content deduplication per spec §2.7:

```python
def _compute_content_hash(self, content: str) -> BlakeHashKey:
    # Normalize content (strip whitespace)
    # Compute Blake3 hash

def _deduplicate_chunks(self, chunks: list[CodeChunk], batch_id: UUID7) -> list[CodeChunk]:
    # Check hash store for duplicates
    # Skip duplicate chunks
    # Store new unique chunks in hash store
```

**Acceptance**:
- [ ] Hash computation uses Blake3 from existing stores
- [ ] Duplicate chunks filtered correctly
- [ ] Hash store updated with new chunks
- [ ] Tests T009 pass completely

---

### T024: Implement SemanticChunker - Statistics Tracking
**File**: `src/codeweaver/engine/chunker/semantic.py`
**Parallel**: No (continues T023)

Integrate with `SessionStatistics` per spec §9.1:

```python
def _track_chunk_metrics(self, chunks: list[CodeChunk], duration: float) -> None:
    # Log structured events
    # Track chunk count, duration, avg size
    # Use SessionStatistics for file operations
```

**Acceptance**:
- [ ] Structured logging implemented
- [ ] SessionStatistics integration works
- [ ] Metrics include all required fields
- [ ] Success and error events logged correctly

---

### T025: Implement ChunkerSelector
**File**: `src/codeweaver/engine/chunker/selector.py`
**Parallel**: Yes [P] (new file, depends on T016, T024)

Implement intelligent chunker selection per spec §4:

```python
class ChunkerSelector:
    def __init__(self, governor: ChunkGovernor): ...
    def select_for_file(self, file: DiscoveredFile) -> BaseChunker: ...
    def _detect_language(self, file: DiscoveredFile) -> SemanticSearchLanguage | str: ...

class GracefulChunker(BaseChunker):
    def __init__(self, primary: BaseChunker, fallback: BaseChunker): ...
    def chunk(self, content: str, *, file_path: Path | None = None, ...) -> list[CodeChunk]: ...
```

**Acceptance**:
- [ ] Language detection from file extensions
- [ ] Semantic preferred for supported languages
- [ ] Graceful fallback to delimiter on errors
- [ ] Fresh instances created per file
- [ ] Tests T012 pass completely

---

### T026: Implement Degradation Chain
**File**: `src/codeweaver/engine/chunker/degradation.py`
**Parallel**: Yes [P] (new file)

Implement complete degradation chain per spec §7:

```python
def chunk_with_full_degradation(
    content: str,
    file_path: Path,
    governor: ChunkGovernor
) -> list[CodeChunk]:
    # Try semantic
    # Try delimiter
    # Try generic delimiters
    # Last resort: RecursiveTextSplitter
    # Track all errors
```

**Acceptance**:
- [ ] All fallback levels implemented
- [ ] Error tracking at each level
- [ ] Always produces chunks (even if crude)
- [ ] Tests T013 pass for degradation chain

---

### T027: Enhance ChunkerRegistry
**File**: `src/codeweaver/engine/chunker/registry.py`
**Parallel**: No (modifies existing file)

Enhance registry with plugin support per spec §5:

```python
ChunkerFactory: TypeAlias = Callable[[ChunkGovernor], BaseChunker]

class ChunkerRegistry:
    def _register_defaults(self): ...
    def register(self, kind: Chunker, factory: ChunkerFactory): ...
    def get_chunker(self, kind: Chunker, governor: ChunkGovernor) -> BaseChunker: ...
    def list_available(self) -> list[Chunker]: ...
```

**Acceptance**:
- [ ] Factory pattern implemented
- [ ] Default chunkers registered
- [ ] Plugin registration API works
- [ ] Registry accessible via `get_chunker_registry()`

---

## Phase 4: Integration & Parallelization

### T028: Implement Parallel Processing
**File**: `src/codeweaver/engine/chunker/parallel.py`
**Parallel**: Yes [P] (new file)

Implement parallel chunking per spec §8.2:

```python
def chunk_files_parallel(
    files: list[DiscoveredFile],
    governor: ChunkGovernor,
    max_workers: int = 4
) -> Iterator[tuple[Path, list[CodeChunk]]]:
    # Use ProcessPoolExecutor for CPU-bound work
    # Chunk each file independently
    # Handle errors gracefully
```

**Acceptance**:
- [ ] Uses `ProcessPoolExecutor` (not threads)
- [ ] Errors logged but don't stop processing
- [ ] Returns iterator for memory efficiency
- [ ] Tests T013 pass for parallel processing

---

### T029: Remove Legacy router.py
**File**: `src/codeweaver/engine/chunker/router.py`
**Parallel**: No (deletion)

Remove old router and create compatibility shim per spec §13:

Steps:
1. Create deprecation shim in `router.py` (temporary)
2. Update all imports to use new selector
3. Delete original router implementation
4. Add deprecation warnings

**Acceptance**:
- [ ] Old router code deleted
- [ ] Deprecation shim redirects to selector
- [ ] All imports updated to new system
- [ ] Deprecation warnings logged

---

## Phase 5: Polish & Documentation

### T030 [P]: Add Structured Logging
**File**: `src/codeweaver/engine/chunker/logging.py`
**Parallel**: Yes [P] (new file)

Implement structured logging utilities per spec §9.3:

- Success events: `chunking_completed`
- Error events: `chunking_failed`
- Edge case events: `chunking_edge_case`
- All events include required context fields

**Acceptance**:
- [ ] Logging utilities importable
- [ ] All event types supported
- [ ] Structured logging format consistent
- [ ] Integration with existing logging config

---

### T031 [P]: Performance Profiling
**File**: `tests/benchmark/chunker/test_performance.py`
**Parallel**: Yes [P] (new test file)

Create performance benchmarks per spec §6.1:

- Typical files (100-1000 lines): 100-500 files/second
- Large files (1000-5000 lines): 50-200 files/second
- Very large files (5000+ lines): 10-50 files/second
- Memory usage < 100MB per operation

**Acceptance**:
- [ ] Benchmarks for all file size categories
- [ ] Performance targets documented
- [ ] Memory profiling included
- [ ] Results logged for regression tracking

---

### T032 [P]: Update Module Docstrings
**File**: Multiple chunker module files
**Parallel**: Yes [P] (documentation)

Add comprehensive docstrings to all chunker modules:

- `semantic.py`: AST-based chunking overview
- `delimiter.py`: Pattern-based chunking overview
- `selector.py`: Intelligent routing overview
- `governance.py`: Resource management overview
- `exceptions.py`: Exception hierarchy documentation

**Acceptance**:
- [ ] All modules have module-level docstrings
- [ ] Public APIs documented with examples
- [ ] Cross-references to spec sections included

---

### T033 [P]: Create Usage Examples
**File**: `docs/chunker_usage.md`
**Parallel**: Yes [P] (new documentation)

Create comprehensive usage guide:

- Basic chunking workflow
- Configuration examples
- Error handling patterns
- Performance optimization tips
- Parallel processing examples

**Acceptance**:
- [ ] All common use cases documented
- [ ] Code examples tested and working
- [ ] Configuration options explained
- [ ] Troubleshooting section included

---

### T034: Integration Testing with Real Codebases
**File**: `tests/integration/chunker/test_real_codebases.py`
**Parallel**: No (final validation)

Test chunker system against real codebases:

- Clone sample repos (Python, JavaScript, Rust, Go)
- Chunk all files
- Verify no failures
- Check performance meets targets
- Validate chunk quality

**Acceptance**:
- [ ] Test against 4+ language codebases
- [ ] All files chunk successfully
- [ ] Performance within acceptable ranges
- [ ] No resource limit violations

---

## Dependencies

```
Phase 1 (Foundation):
  T001 → T005-T014 (tests need fixtures)
  T002 → T008 (error tests need exceptions)
  T003 → T014, T017 (governance needed by tests and semantic)
  T004 → all (settings needed throughout)

Phase 2 (Tests):
  T005-T014 can all run in parallel [P]
  All must FAIL before Phase 3 starts

Phase 3 (Implementation):
  T015 → T016 (delimiter model before chunker)
  T003 → T017 (governor before semantic)
  T017 → T018 → T019 → T020 → T021 → T022 → T023 → T024 (semantic sequence)
  T016, T024 → T025 (selector needs both chunkers)
  T025 → T026 (degradation needs selector)
  T026 → T027 (registry enhancement last)

Phase 4 (Integration):
  T027 → T028 (parallel needs registry)
  T028 → T029 (remove router after parallel works)

Phase 5 (Polish):
  T030, T031, T032, T033 can all run in parallel [P]
  All Phase 3-4 → T034 (final integration test)
```

## Parallel Execution Examples

### Tests Phase (T005-T014)
All test files can be created in parallel:

```bash
# Launch all test creation tasks together
Task: "Write semantic chunker basic tests in tests/unit/engine/chunker/test_semantic_basic.py"
Task: "Write semantic edge case tests in tests/unit/engine/chunker/test_semantic_edge_cases.py"
Task: "Write semantic oversized tests in tests/unit/engine/chunker/test_semantic_oversized.py"
Task: "Write semantic error tests in tests/unit/engine/chunker/test_semantic_errors.py"
Task: "Write semantic dedup tests in tests/unit/engine/chunker/test_semantic_dedup.py"
Task: "Write delimiter basic tests in tests/unit/engine/chunker/test_delimiter_basic.py"
Task: "Write delimiter edge case tests in tests/unit/engine/chunker/test_delimiter_edge_cases.py"
Task: "Write selector tests in tests/unit/engine/chunker/test_selector.py"
Task: "Write integration E2E tests in tests/integration/chunker/test_e2e.py"
Task: "Write governance tests in tests/unit/engine/chunker/test_governance.py"
```

### Polish Phase (T030-T033)
Documentation and profiling in parallel:

```bash
# Launch all polish tasks together
Task: "Add structured logging utilities in src/codeweaver/engine/chunker/logging.py"
Task: "Create performance benchmarks in tests/benchmark/chunker/test_performance.py"
Task: "Update module docstrings in all chunker modules"
Task: "Create usage guide in docs/chunker_usage.md"
```

## Validation Checklist

Before marking complete:

- [ ] All semantic chunker edge cases handled (empty, binary, single-line, whitespace)
- [ ] All delimiter patterns tested with nesting and priority resolution
- [ ] Selector correctly routes to semantic/delimiter based on language
- [ ] Resource limits enforced (timeout, chunk count, AST depth)
- [ ] Deduplication working with hash store
- [ ] Degradation chain tested end-to-end
- [ ] Parallel processing tested with real files
- [ ] All tests passing (unit, integration, E2E)
- [ ] Performance benchmarks within targets
- [ ] Documentation complete and accurate
- [ ] Legacy router.py removed
- [ ] No regression in existing functionality

## Notes

- **TDD Critical**: Phase 2 tests must FAIL before Phase 3 implementation begins
- **No [P] for Sequential Work**: Semantic chunker tasks T017-T024 must run in order
- **Thread Safety**: All chunkers are stateless, safe for parallel use
- **Resource Limits**: Always use `ResourceGovernor` context manager
- **Commit Frequency**: Commit after each task completion
- **Test Fixtures**: Reuse across all test phases (created once in T001)

---

## Summary

**Total Tasks**: 34
**Parallel Tasks**: 16 ([P] marked)
**Sequential Tasks**: 18 (dependencies or same-file edits)

**Critical Path**:
T001 → T002-T004 → T005-T014 (tests) → T015-T027 (implementation) → T028-T029 (integration) → T030-T034 (polish)

**Estimated Effort**:
- Phase 1 (Foundation): 4-6 hours
- Phase 2 (Tests): 6-8 hours (parallelizable)
- Phase 3 (Implementation): 16-20 hours
- Phase 4 (Integration): 4-6 hours
- Phase 5 (Polish): 4-6 hours
- **Total**: 34-46 hours

**Implementation Ready**: All tasks have clear acceptance criteria and can be completed independently by an LLM without additional context.
