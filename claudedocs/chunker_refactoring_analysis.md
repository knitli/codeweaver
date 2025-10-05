<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Claude Code Analysis

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Chunker Architecture Refactoring Analysis

**Date**: 2025-01-03
**Focus**: Maintainability improvements through BaseChunker and Chunker enum hierarchy
**Status**: Feasibility assessment - RECOMMENDED

## Executive Summary

The current `ChunkMicroManager` (645 lines) and `EnhancedChunkMicroManager` (179 lines) can be refactored into a cleaner, more maintainable architecture using the existing `BaseChunker` ABC and `Chunker` enum hierarchy. This refactoring will:

- **Reduce complexity**: Single responsibility per chunker class (~100-150 lines each)
- **Improve maintainability**: Clear separation of concerns, easier testing
- **Enable extensibility**: New chunker types via plugins without modifying core
- **Natural fallback**: Automatic "sliding" down hierarchy using `Chunker.next_chunker()`

**Verdict**: ✅ **Highly Feasible** - The Chunker enum already provides the framework needed

---

## Current Architecture Problems

### 1. ChunkMicroManager - Monolithic Responsibility

**Current state** (src/codeweaver/services/chunker/base.py:139-785):
```python
class ChunkMicroManager:
    """Does EVERYTHING:
    - Strategy selection (_semantic_available, _special_splitter_available)
    - AST/semantic chunking with importance scoring
    - Langchain text splitter integration (markdown, latex, language-specific)
    - Fallback recursive text chunking
    - Chunk metadata creation and enrichment
    - Large node splitting logic
    - Context extraction
    - Gap filling
    """
```

**Issues**:
- Violates Single Responsibility Principle (SRP)
- 645 lines - too large to comprehend easily
- Tightly coupled strategy selection with execution
- Hard to test individual strategies in isolation
- Adding new chunker types requires modifying this class

### 2. EnhancedChunkMicroManager - Post-Processing Band-Aid

**Current state** (src/codeweaver/services/chunker/router.py:23-202):
```python
class EnhancedChunkMicroManager:
    """Wrapper that:
    - Delegates to ChunkMicroManager
    - Post-processes results for token budget enforcement
    - Re-splits oversized chunks
    - Handles metadata-heavy chunks separately
    """
```

**Issues**:
- Can't participate in chunking strategy - forced to post-process
- Duplicates splitting logic from ChunkMicroManager
- Wrapper pattern adds indirection without clear benefit
- Token budget should be enforced during chunking, not after

### 3. BaseChunker - Incomplete Abstraction

**Current state** (src/codeweaver/services/chunker/base.py:103-136):
```python
class BaseChunker(ABC):
    def next_chunker(self) -> ChunkMicroManager:  # ❌ Returns concrete class!
        return ChunkMicroManager(self._governor)
```

**Issues**:
- `next_chunker()` returns `ChunkMicroManager`, not another `BaseChunker`
- Breaks abstraction - forces dependency on concrete implementation
- Doesn't use the `Chunker` enum hierarchy for fallback

### 4. Unused Delimiter Framework

The `Chunker` enum provides:
- `Chunker.builtin_delimiters()` - Built-in delimiter mapping
- `Chunker.delimiters_for_language(lang)` - Language-specific delimiters
- `Chunker.register_custom_chunker(delimiter)` - User customization
- `Chunker.BUILTIN_DELIMITER` level - **Not implemented yet!**

This framework is ready but unused - no chunker implementation exists for it.

---

## Proposed Architecture

### Core Design: Chunker Hierarchy with Strategy Pattern

```
BaseChunker (ABC)
├─ SemanticChunker (Chunker.SEMANTIC)
│  ├─ Uses ast-grep for semantic analysis
│  ├─ Importance scoring and categorization
│  ├─ Rich semantic metadata
│  └─ Fallback: next_chunker() → LangchainSpecialChunker
│
├─ UserDelimiterChunker (Chunker.USER_DELIMITER)
│  ├─ Uses custom registered delimiters
│  ├─ Respects user configuration
│  └─ Fallback: next_chunker() → LangchainSpecialChunker
│
├─ LangchainSpecialChunker (Chunker.LANGCHAIN_SPECIAL)
│  ├─ Markdown with headers (ExperimentalMarkdownSyntaxSplitter)
│  ├─ LaTeX specialized splitting
│  ├─ Language-specific recursive splitters
│  └─ Fallback: next_chunker() → BuiltinDelimiterChunker
│
├─ BuiltinDelimiterChunker (Chunker.BUILTIN_DELIMITER) [NEW]
│  ├─ Uses Chunker.builtin_delimiters()
│  ├─ Start-end delimiter matching
│  └─ Fallback: next_chunker() → RecursiveTextChunker
│
└─ RecursiveTextChunker (Chunker.LANGCHAIN_RECURSIVE)
   ├─ Final fallback - always succeeds
   ├─ Language-agnostic recursive splitting
   └─ Fallback: None (bottom of hierarchy)
```

### Key Components

#### 1. BaseChunker (Enhanced)

```python
class BaseChunker(ABC):
    """Base class for all chunkers."""

    chunker: Chunker  # Each subclass declares its level
    _governor: ChunkGovernor

    def __init__(self, governor: ChunkGovernor):
        self._governor = governor

    @abstractmethod
    def chunk(
        self,
        content: str,
        *,
        file_path: Path | None = None,
        context: dict[str, Any] | None = None
    ) -> list[CodeChunk]:
        """Chunk content. Return empty list if can't handle (triggers fallback)."""

    def next_chunker(self) -> BaseChunker | None:
        """Get next chunker in fallback hierarchy."""
        next_level = self.chunker.next_chunker()
        if next_level is None:
            return None
        return chunker_registry[next_level](self._governor)

    def chunk_with_fallback(self, content: str, **kwargs) -> list[CodeChunk]:
        """Chunk with automatic fallback on failure or empty result."""
        try:
            chunks = self.chunk(content, **kwargs)
            if chunks:
                return chunks
        except Exception as e:
            logger.debug(f"{self.__class__.__name__} failed: {e}")

        # Automatic fallback
        if next_chunker := self.next_chunker():
            return next_chunker.chunk_with_fallback(content, **kwargs)
        return []
```

#### 2. Chunker Registry (Strategy Mapping)

```python
chunker_registry: dict[Chunker, type[BaseChunker]] = {
    Chunker.SEMANTIC: SemanticChunker,
    Chunker.USER_DELIMITER: UserDelimiterChunker,
    Chunker.LANGCHAIN_SPECIAL: LangchainSpecialChunker,
    Chunker.BUILTIN_DELIMITER: BuiltinDelimiterChunker,
    Chunker.LANGCHAIN_RECURSIVE: RecursiveTextChunker,
}

def select_chunker(file: DiscoveredFile, governor: ChunkGovernor) -> BaseChunker:
    """Select best chunker for file based on language and availability."""
    language = file.ext_kind.language

    # Try from highest (SEMANTIC) to lowest (LANGCHAIN_RECURSIVE)
    for chunker_level in reversed(Chunker):
        if language in chunker_level.supported_languages:
            return chunker_registry[chunker_level](governor)

    # Final fallback
    return RecursiveTextChunker(governor)
```

#### 3. ChunkValidator (Extracted from EnhancedChunkMicroManager)

```python
class ChunkValidator:
    """Validates and enforces token budgets on chunks.

    Separate concern from chunking strategy - handles technical constraints.
    """

    def __init__(self, governor: ChunkGovernor):
        self.governor = governor

    def validate_and_fix(self, chunks: list[CodeChunk]) -> list[CodeChunk]:
        """Enforce token budget, split oversized chunks, handle metadata."""
        validated = []
        for chunk in chunks:
            if self._is_valid_size(chunk):
                validated.append(chunk)
            else:
                # Try metadata stripping first, then re-split
                validated.extend(self._fix_oversized(chunk))
        return validated

    def _is_valid_size(self, chunk: CodeChunk) -> bool:
        """Check if chunk fits within token budget."""
        token_count = estimate_tokens(chunk.serialize_for_embedding())
        effective_limit = int(self.governor.chunk_limit * (1 - SAFETY_MARGIN))
        return token_count <= effective_limit

    def _fix_oversized(self, chunk: CodeChunk) -> list[CodeChunk]:
        """Fix oversized chunk - strip metadata or re-split."""
        # Implementation from EnhancedChunkMicroManager._enforce_budget_on_chunks
        ...
```

#### 4. Example: SemanticChunker

```python
class SemanticChunker(BaseChunker):
    """Semantic chunking using ast-grep with importance scoring."""

    chunker = Chunker.SEMANTIC

    def chunk(
        self,
        content: str,
        *,
        file_path: Path | None = None,
        context: dict[str, Any] | None = None
    ) -> list[CodeChunk]:
        """Chunk using AST analysis with semantic metadata."""
        if not file_path:
            return []  # Trigger fallback

        # Detect language from file_path
        ext_kind = ExtKind.from_path(file_path)
        language = ext_kind.language

        if not isinstance(language, SemanticSearchLanguage):
            return []  # Not supported, trigger fallback

        try:
            from ast_grep_py import SgRoot
            root = SgRoot(content, str(language))
            ast_node = AstNode.from_sg_node(root.root(), language)

            # Extract semantic chunks with importance scoring
            chunks = self._extract_semantic_chunks(ast_node, content, file_path)
            return chunks

        except Exception as e:
            logger.debug(f"AST parsing failed for {file_path}: {e}")
            return []  # Trigger fallback

    def _extract_semantic_chunks(self, root, content, file_path) -> list[CodeChunk]:
        """Core semantic extraction logic - moved from ChunkMicroManager."""
        # Implementation from ChunkMicroManager._extract_semantic_chunks
        ...
```

#### 5. Example: BuiltinDelimiterChunker (NEW)

```python
class BuiltinDelimiterChunker(BaseChunker):
    """Delimiter-based chunking using built-in delimiter definitions."""

    chunker = Chunker.BUILTIN_DELIMITER

    def chunk(
        self,
        content: str,
        *,
        file_path: Path | None = None,
        context: dict[str, Any] | None = None
    ) -> list[CodeChunk]:
        """Chunk using start-end delimiter pairs."""
        if not file_path:
            return []

        ext_kind = ExtKind.from_path(file_path)
        language = ext_kind.language

        # Get delimiters for this language
        delimiters = Chunker.delimiters_for_language(language)
        if not delimiters:
            return []  # No delimiters defined, trigger fallback

        try:
            chunks = self._chunk_with_delimiters(content, delimiters, file_path)
            return chunks
        except Exception as e:
            logger.debug(f"Delimiter chunking failed: {e}")
            return []

    def _chunk_with_delimiters(
        self,
        content: str,
        delimiters: tuple[Delimiter, ...],
        file_path: Path
    ) -> list[CodeChunk]:
        """Split content using delimiter pairs (start/end markers)."""
        # NEW IMPLEMENTATION - uses Delimiter.start and Delimiter.end
        # This is the missing piece in the current architecture
        ...
```

---

## Benefits Analysis

### Maintainability ⭐⭐⭐⭐⭐

**Single Responsibility Principle**:
- Each chunker: ~100-150 lines, ONE strategy
- ChunkValidator: ~80 lines, token budget only
- SemanticChunker: AST logic only
- LangchainSpecialChunker: Langchain integration only

**Open/Closed Principle**:
- Add new chunker: implement BaseChunker, register in chunker_registry
- No modification to existing chunkers required
- Plugin system possible: users register custom chunkers

**DRY (Don't Repeat Yourself)**:
- Common logic extracted to BaseChunker.chunk_with_fallback()
- Metadata creation utilities shared across chunkers
- Validation logic centralized in ChunkValidator

**Testability**:
- Each chunker independently testable
- Mock governor for unit tests
- Test fallback behavior in isolation
- Compare outputs between chunker implementations

### Flexibility ⭐⭐⭐⭐⭐

**Natural Fallback**:
```python
# Automatic sliding down hierarchy
semantic_chunker.chunk_with_fallback(content)
  → SemanticChunker tries
  → Fails/empty → next_chunker() → LangchainSpecialChunker
  → Fails/empty → next_chunker() → BuiltinDelimiterChunker
  → Fails/empty → next_chunker() → RecursiveTextChunker
  → Always succeeds (final fallback)
```

**Configuration-Driven**:
- Strategy selection based on language support
- No hardcoded if-else chains
- Chunker enum defines hierarchy, not code

**Extensibility**:
- Users can implement custom BaseChunker subclasses
- Register via chunker_registry or plugin system
- Custom delimiters via Chunker.register_custom_chunker()

### Correctness ⭐⭐⭐⭐

**Type Safety**:
- Chunker enum enforces hierarchy
- BaseChunker protocol ensures consistency
- Impossible to skip fallback levels

**Clear Contracts**:
- Empty list = "can't handle, try next"
- Exception = "failed, try next"
- Non-empty list = "success, use these chunks"

**Language Support**:
- Explicit per chunker via Chunker.supported_languages
- Automatic filtering in select_chunker()

### Code Reduction ⭐⭐⭐⭐

**Before**:
- ChunkMicroManager: 645 lines
- EnhancedChunkMicroManager: 179 lines
- **Total**: 824 lines

**After**:
- BaseChunker (enhanced): ~50 lines
- SemanticChunker: ~150 lines
- LangchainSpecialChunker: ~120 lines
- BuiltinDelimiterChunker: ~80 lines (NEW)
- RecursiveTextChunker: ~50 lines
- ChunkValidator: ~80 lines
- chunker_registry + select_chunker: ~20 lines
- **Total**: ~550 lines

**Savings**: ~270 lines (33% reduction) with MORE functionality (delimiter chunker added)

---

## Migration Path

### Phase 1: Parallel Implementation

1. **Create new chunker classes** alongside existing code:
   - Implement SemanticChunker (extract from ChunkMicroManager._chunk_with_ast)
   - Implement LangchainSpecialChunker (extract from ChunkMicroManager._chunk_with_langchain)
   - Implement RecursiveTextChunker (extract from ChunkMicroManager._chunk_fallback)
   - Implement BuiltinDelimiterChunker (NEW - use Chunker.delimiters_for_language)

2. **Create ChunkValidator** (extract from EnhancedChunkMicroManager):
   - Move _enforce_budget_on_chunks logic
   - Move _tokens_for_chunk calculation
   - Move _resplit_chunk logic

3. **Add chunker_registry and select_chunker utilities**

4. **Keep old ChunkMicroManager** for comparison testing

### Phase 2: Integration Testing

1. **Create comparison tests**:
   - Run old ChunkMicroManager vs new chunker hierarchy
   - Compare chunk outputs for equivalence
   - Ensure no regressions in chunk quality

2. **Validate new BuiltinDelimiterChunker**:
   - Test delimiter matching logic
   - Ensure proper fallback when no delimiters found
   - Validate against languages with built-in delimiters

3. **Performance testing**:
   - Compare chunking speed old vs new
   - Validate token budget enforcement
   - Test with large files (>10K lines)

### Phase 3: Switch Over

1. **Update router.py** to use new architecture:
   ```python
   class ChunkRouter:
       def route_file(self, file: DiscoveredFile, content: str) -> list[CodeChunk]:
           chunker = select_chunker(file, self.governor)
           chunks = chunker.chunk_with_fallback(content, file_path=file.path)
           validator = ChunkValidator(self.governor)
           return validator.validate_and_fix(chunks)
   ```

2. **Update tests** to use new classes

3. **Update documentation** to reflect new architecture

### Phase 4: Cleanup

1. **Remove old implementations**:
   - Delete ChunkMicroManager (after validation)
   - Delete EnhancedChunkMicroManager (replaced by ChunkValidator)

2. **Update BaseChunker.next_chunker()** signature:
   - Change return type from `ChunkMicroManager` to `BaseChunker | None`
   - Update docstrings

3. **Documentation**:
   - Update architecture docs
   - Add plugin guide for custom chunkers
   - Document delimiter configuration

---

## Risk Assessment

### Low Risk ✅

**Reasons**:
- Parallel implementation allows gradual migration
- Existing tests provide regression detection
- Chunker enum framework already exists and is well-designed
- Core logic (AST parsing, langchain) unchanged - just reorganized
- Fallback mechanism identical to current behavior

**Mitigation**:
- Comprehensive comparison testing old vs new
- Feature flag to switch between implementations
- Gradual rollout with monitoring

### Medium Effort 🟡

**Estimated effort**:
- Phase 1 (Parallel implementation): 2-3 days
- Phase 2 (Testing & validation): 1-2 days
- Phase 3 (Switch over): 1 day
- Phase 4 (Cleanup): 0.5 days
- **Total**: 4.5-6.5 days

**Complexity**:
- Mostly code movement, not new logic
- BuiltinDelimiterChunker is the only NEW implementation
- Testing is the most time-consuming part

---

## Recommendations

### ✅ Proceed with Refactoring

**Justification**:
1. **Significant maintainability improvement** - worth the effort
2. **Chunker enum framework already exists** - foundation is solid
3. **Clear migration path** - can be done incrementally
4. **Enables future extensions** - delimiter chunker, custom plugins
5. **Reduces code size** - 33% reduction with more features

### Priority Order

1. **High Priority**: Implement BaseChunker hierarchy (Phases 1-2)
   - Immediate maintainability gains
   - Enables BuiltinDelimiterChunker implementation
   - Prepares for plugin system

2. **Medium Priority**: Implement BuiltinDelimiterChunker (Phase 2)
   - Utilizes unused Chunker.delimiters_for_language() framework
   - Fills gap in chunker hierarchy
   - Improves chunking for delimiter-based formats

3. **Low Priority**: Complete cleanup (Phase 4)
   - Remove old code once validated
   - Can be deferred if needed

### Next Steps

1. **Review this analysis** with team for alignment
2. **Create feature branch** for refactoring
3. **Start Phase 1** - implement SemanticChunker first (largest, most complex)
4. **Iterative validation** - test each chunker as implemented
5. **Documentation** - update as you go, not at the end

---

## Appendix: Code Structure

### File Organization

```
src/codeweaver/services/chunker/
├── base.py              # BaseChunker, ChunkGovernor, ChunkValidator
├── registry.py          # chunker_registry, select_chunker()
├── semantic.py          # SemanticChunker
├── langchain_special.py # LangchainSpecialChunker
├── delimiter.py         # BuiltinDelimiterChunker, UserDelimiterChunker
├── recursive.py         # RecursiveTextChunker
└── router.py            # ChunkRouter (simplified)
```

### Dependency Graph

```
ChunkRouter
  └─ select_chunker() → BaseChunker subclass
       └─ chunker.chunk_with_fallback()
            ├─ Try current chunker
            └─ Fallback to next_chunker() if needed
  └─ ChunkValidator.validate_and_fix()
       ├─ Check token budgets
       └─ Re-split if needed
```

### Interface Stability

**Public API remains stable**:
- ChunkRouter.route_file() signature unchanged
- CodeChunk structure unchanged
- Governor configuration unchanged

**Internal refactoring**:
- ChunkMicroManager → multiple BaseChunker subclasses
- EnhancedChunkMicroManager → ChunkValidator
- Strategy selection → chunker_registry + Chunker enum

---

## Conclusion

The refactoring is **highly feasible** and **strongly recommended**. The `Chunker` enum already provides the perfect framework for this architecture - we just need to implement the missing pieces (chunker classes, validator) and connect them together.

The maintainability gains alone justify the effort:
- 645-line monolith → 5 focused classes (~100-150 lines each)
- Clear separation of concerns
- Extensible plugin system ready
- Natural fallback behavior

The migration path is low-risk due to parallel implementation and comprehensive testing strategy.

**Recommendation**: ✅ **Proceed with refactoring** - start with Phase 1
