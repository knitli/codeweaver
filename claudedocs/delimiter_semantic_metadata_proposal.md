<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Claude Code Analysis

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Delimiter Semantic Metadata Enhancement Proposal

**Date**: 2025-01-03
**Related**: Chunker refactoring analysis
**Status**: Design proposal - ready for implementation

## Executive Summary

Delimiters are **inherently semantic** - they mark meaningful code boundaries like function definitions, class bodies, control structures, etc. Currently, the `Delimiter` NamedTuple only captures syntactic information (start/end strings).

This proposal enhances `Delimiter` to capture semantic metadata, enabling:
- **Richer chunk metadata** without AST parsing overhead
- **Language-agnostic semantic understanding** via delimiter patterns
- **Better context** for embedding and retrieval
- **Hierarchical structure detection** (functions inside classes, nested blocks)

**Key insight**: Even minimal delimiter metadata (like language + delimiter used) provides substantial context without heavyweight AST processing.

---

## Current State Analysis

### Delimiter (NamedTuple)

**Current** (src/codeweaver/_constants.py:539-542):
```python
class Delimiter(NamedTuple):
    start: str
    end: str
```

**Usage examples** from DELIMITERS mapping:
```python
# Python
Delimiter("def", "end")        # Function definition
Delimiter("class", "end")      # Class definition
Delimiter('"""', '"""')        # Docstring
Delimiter("#", "\n")           # Comment

# C/C++/Java
Delimiter("/*", "*/")          # Block comment
Delimiter("//", "\n")          # Line comment
Delimiter("{", "}")            # Code block

# Bash
Delimiter("if", "fi")          # Conditional
Delimiter("do", "done")        # Loop body
Delimiter("case", "esac")      # Case statement
```

### Semantic Information Available

Looking at the delimiter patterns, we can infer:

| Delimiter | Semantic Meaning | Structure Type |
|-----------|------------------|----------------|
| `def...end` | Function definition | Declaration |
| `class...end` | Class definition | Declaration |
| `if...fi` | Conditional block | Control flow |
| `do...done` | Loop body | Control flow |
| `{...}` | Generic block | Structure |
| `/*...*/` | Block comment | Documentation |
| `"""..."""` | Docstring/string literal | Documentation/Data |

**The delimiter itself carries semantic information!**

---

## Proposed Enhancement

### Enhanced Delimiter Model

**Option 1: Rich Delimiter (Recommended)**
```python
from enum import Enum
from typing import Literal

class DelimiterKind(str, Enum):
    """Semantic category of delimiter."""
    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    INTERFACE = "interface"
    STRUCT = "struct"
    ENUM = "enum"
    NAMESPACE = "namespace"
    MODULE = "module"

    # Control flow
    CONDITIONAL = "conditional"  # if, switch, case
    LOOP = "loop"                # for, while, do
    TRY_CATCH = "try_catch"

    # Documentation
    COMMENT_LINE = "comment_line"
    COMMENT_BLOCK = "comment_block"
    DOCSTRING = "docstring"

    # Structural
    BLOCK = "block"              # Generic {}
    ARRAY = "array"              # []
    TUPLE = "tuple"              # ()

    # Data
    STRING = "string"
    TEMPLATE = "template"

    # Meta
    ANNOTATION = "annotation"
    DECORATOR = "decorator"
    PRAGMA = "pragma"

    # Unknown
    UNKNOWN = "unknown"


class Delimiter(NamedTuple):
    """Delimiter with semantic metadata.

    Attributes:
        start: Opening delimiter string
        end: Closing delimiter string
        kind: Semantic category (optional, inferred if not provided)
        description: Human-readable description (optional)
        nestable: Whether this delimiter can nest inside itself (optional, default True)
        priority: Matching priority (optional, higher = try first)
    """
    start: str
    end: str
    kind: DelimiterKind | None = None
    description: str | None = None
    nestable: bool = True
    priority: int = 0
    language: LiteralStringT | None = None

    def infer_kind(self) -> DelimiterKind:
        """Infer semantic kind from delimiter strings if not explicitly set."""
        if self.kind:
            return self.kind

        # Pattern-based inference
        start_lower = self.start.lower()

        # Declarations
        if start_lower in ("def", "function", "fn"):
            return DelimiterKind.FUNCTION
        if start_lower in ("class", "struct", "type"):
            return DelimiterKind.CLASS if "class" in start_lower else DelimiterKind.STRUCT
        if start_lower in ("interface", "trait", "protocol"):
            return DelimiterKind.INTERFACE
        if start_lower in ("module", "namespace", "package"):
            return DelimiterKind.MODULE
        if start_lower in ("enum",):
            return DelimiterKind.ENUM

        # Control flow
        if start_lower in ("if", "else", "elif", "unless", "switch", "case", "select"):
            return DelimiterKind.CONDITIONAL
        if start_lower in ("for", "while", "do", "until", "loop", "foreach"):
            return DelimiterKind.LOOP
        if start_lower in ("try", "catch", "except", "finally"):
            return DelimiterKind.TRY_CATCH

        # Comments/docs
        if start_lower.startswith("//") or start_lower in ("#", "%", "--"):
            return DelimiterKind.COMMENT_LINE
        if start_lower.startswith("/*") or start_lower in ("(*", "{-", "#|", "#="):
            return DelimiterKind.COMMENT_BLOCK
        if start_lower in ('"""', "'''", "@doc"):
            return DelimiterKind.DOCSTRING

        # Structural
        if self.start == "{" and self.end == "}":
            return DelimiterKind.BLOCK
        if self.start == "[" and self.end == "]":
            return DelimiterKind.ARRAY
        if self.start == "(" and self.end == ")":
            return DelimiterKind.TUPLE

        # Data
        if self.start in ('"', "'", "`") and self.start == self.end:
            return DelimiterKind.STRING
        if self.start in ("<", "<%", "{{") and self.end in (">", "%>", "}}"):
            return DelimiterKind.TEMPLATE

        # Meta
        if start_lower in ("@", "#["):
            return DelimiterKind.ANNOTATION

        return DelimiterKind.UNKNOWN
```

**Option 2: Minimal Enhancement (Simpler, still useful)**
```python
class Delimiter(NamedTuple):
    """Delimiter with optional semantic hint."""
    start: str
    end: str
    semantic_hint: str | None = None  # e.g., "function", "class", "comment"

    # Later can attach full metadata in chunk creation:
    # chunk.metadata["delimiter_info"] = {
    #     "start": delimiter.start,
    #     "end": delimiter.end,
    #     "hint": delimiter.semantic_hint,
    #     "language": language
    # }
```

**Recommendation**: Start with **Option 2** (minimal), evolve to **Option 1** (rich) if needed.

---

## Usage in BuiltinDelimiterChunker

### Chunk Creation with Delimiter Metadata

```python
class BuiltinDelimiterChunker(BaseChunker):
    """Delimiter-based chunking with semantic metadata."""

    chunker = Chunker.BUILTIN_DELIMITER

    def chunk(
        self,
        content: str,
        *,
        file_path: Path | None = None,
        context: dict[str, Any] | None = None
    ) -> list[CodeChunk]:
        """Chunk using delimiters with semantic metadata."""
        if not file_path:
            return []

        ext_kind = ExtKind.from_path(file_path)
        language = ext_kind.language

        # Get delimiters for language
        delimiters = Chunker.delimiters_for_language(language)
        if not delimiters:
            return []

        try:
            chunks = self._chunk_with_delimiters(
                content, delimiters, file_path, language
            )
            return chunks
        except Exception as e:
            logger.debug(f"Delimiter chunking failed: {e}")
            return []

    def _chunk_with_delimiters(
        self,
        content: str,
        delimiters: tuple[Delimiter, ...],
        file_path: Path,
        language: str
    ) -> list[CodeChunk]:
        """Split content using delimiters and attach semantic metadata."""
        chunks: list[CodeChunk] = []

        # Sort delimiters by priority (if using Option 1)
        # For Option 2, just use order from DELIMITERS mapping

        # Find all delimiter matches in content
        matches = self._find_delimiter_matches(content, delimiters)

        # Create chunks with semantic metadata
        for match in matches:
            delimiter = match.delimiter
            start_line = match.start_line
            end_line = match.end_line
            chunk_content = match.content

            # Create rich metadata from delimiter
            metadata: Metadata = {
                "chunk_id": uuid7(),
                "created_at": datetime.now(UTC).timestamp(),
                "name": self._generate_chunk_name(delimiter, chunk_content),
                "semantic_meta": self._create_delimiter_semantic_meta(
                    delimiter, language, start_line, end_line
                ),
                "tags": (language, delimiter.semantic_hint or delimiter.start),
                "context": {
                    "delimiter": {
                        "start": delimiter.start,
                        "end": delimiter.end,
                        "kind": delimiter.semantic_hint,
                    },
                    "language": language,
                },
            }

            chunk = self._create_chunk_from_parts(
                content=chunk_content,
                start_line=start_line,
                end_line=end_line,
                file_path=file_path,
                metadata=metadata,
                chunk_type=ChunkType.DELIMITER_BOUNDED,  # New chunk type
            )
            chunks.append(chunk)

        return chunks

    def _create_delimiter_semantic_meta(
        self,
        delimiter: Delimiter,
        language: str,
        start_line: int,
        end_line: int
    ) -> dict[str, Any]:
        """Create semantic metadata from delimiter information."""

        # Option 1 (Rich): Use inferred kind
        if hasattr(delimiter, 'infer_kind'):
            kind = delimiter.infer_kind()

        # Option 2 (Minimal): Use hint or infer from delimiter string
        else:
            kind = delimiter.semantic_hint or self._infer_kind_from_delimiter(delimiter)

        return {
            "chunker_type": "delimiter",
            "delimiter_start": delimiter.start,
            "delimiter_end": delimiter.end,
            "semantic_kind": str(kind),
            "language": language,
            "line_range": (start_line, end_line),
            "is_declaration": kind in {
                "function", "class", "interface", "struct", "enum", "module"
            },
            "is_control_flow": kind in {
                "conditional", "loop", "try_catch"
            },
            "is_documentation": kind in {
                "comment_line", "comment_block", "docstring"
            },
        }

    def _generate_chunk_name(self, delimiter: Delimiter, content: str) -> str:
        """Generate human-readable name from delimiter and content."""

        # Try to extract identifier after delimiter
        # e.g., "def my_function" → "my_function"
        lines = content.strip().split("\n")
        first_line = lines[0] if lines else ""

        # Remove delimiter start from first line
        if first_line.startswith(delimiter.start):
            identifier_part = first_line[len(delimiter.start):].strip()

            # Extract first word (likely the identifier)
            identifier = identifier_part.split()[0] if identifier_part else None

            if identifier:
                kind = delimiter.semantic_hint or "block"
                return f"{kind}: {identifier}"

        # Fallback: use delimiter as name
        return f"{delimiter.start}...{delimiter.end} block"
```

---

## Enhanced DELIMITERS Mapping

### Migration Path

**Phase 1: Backward-compatible addition (Option 2)**

```python
# Can keep existing Delimiter as-is, add optional semantic_hint
# Old code still works:
Delimiter("def", "end")  # semantic_hint=None

# New code benefits from hints:
Delimiter("def", "end", "function")
Delimiter("class", "end", "class")
Delimiter("if", "fi", "conditional")
Delimiter("/*", "*/", "comment_block")
```

**Phase 2: Rich metadata (Option 1)**

```python
# Explicit semantic kinds
Delimiter("def", "end", kind=DelimiterKind.FUNCTION, description="Function definition")
Delimiter("class", "end", kind=DelimiterKind.CLASS, description="Class definition")
Delimiter("{", "}", kind=DelimiterKind.BLOCK, nestable=True, priority=10)

# Or use inference (no kind specified, inferred from start/end)
Delimiter("def", "end")  # Automatically infers DelimiterKind.FUNCTION
```

### Example Enhanced DELIMITERS

```python
# Python with semantic hints (Option 2 - Minimal)
"python": (
    Delimiter('"""', '"""', "docstring"),
    Delimiter("'''", "'''", "docstring"),
    Delimiter("def", "end", "function"),
    Delimiter("class", "end", "class"),
    Delimiter("#", "\n", "comment_line"),
    *GENERIC_CODE_DELIMITERS,
)

# Or with rich metadata (Option 1)
"python": (
    Delimiter('"""', '"""', kind=DelimiterKind.DOCSTRING, description="Python docstring"),
    Delimiter("def", "end", kind=DelimiterKind.FUNCTION, description="Function definition"),
    Delimiter("class", "end", kind=DelimiterKind.CLASS, description="Class definition"),
    Delimiter("#", "\n", kind=DelimiterKind.COMMENT_LINE, nestable=False),
    *GENERIC_CODE_DELIMITERS,
)

# C++ with priority and nesting control
"cpp": (
    Delimiter("/*", "*/", kind=DelimiterKind.COMMENT_BLOCK, priority=100, nestable=False),
    Delimiter("//", "\n", kind=DelimiterKind.COMMENT_LINE, priority=100, nestable=False),
    Delimiter("{", "}", kind=DelimiterKind.BLOCK, priority=10, nestable=True),
    Delimiter("(", ")", kind=DelimiterKind.TUPLE, priority=5, nestable=True),
    Delimiter("[", "]", kind=DelimiterKind.ARRAY, priority=5, nestable=True),
)
```

---

## Benefits Analysis

### 1. Richer Chunk Metadata ⭐⭐⭐⭐⭐

**Before** (no delimiter metadata):
```python
chunk.metadata = {
    "name": "code_block_1",
    "tags": ("python",),
}
```

**After** (with delimiter metadata):
```python
chunk.metadata = {
    "name": "function: calculate_total",
    "tags": ("python", "function"),
    "semantic_meta": {
        "chunker_type": "delimiter",
        "delimiter_start": "def",
        "delimiter_end": "end",
        "semantic_kind": "function",
        "is_declaration": True,
        "language": "python",
    },
    "context": {
        "delimiter": {"start": "def", "end": "end", "kind": "function"},
        "language": "python",
    },
}
```

### 2. Better Embeddings & Retrieval ⭐⭐⭐⭐⭐

**Context provided to embedding model**:
```
Language: python
Chunk type: function definition
Delimiter: def...end
Content: [actual code]
```

This context helps the embedding model understand:
- **Structural role**: "This is a function, not a class or comment"
- **Language-specific**: "Python function syntax"
- **Semantic boundaries**: "Complete function definition"

**Retrieval improvements**:
- Query: "find all class definitions" → filter by `semantic_kind: "class"`
- Query: "find docstrings" → filter by `semantic_kind: "docstring"`
- Query: "find control flow logic" → filter by `is_control_flow: True`

### 3. Language-Agnostic Semantic Understanding ⭐⭐⭐⭐

**Without AST parsing**, delimiter metadata provides:
- Structure type (function, class, block, comment)
- Hierarchy hints (nestable blocks suggest structure depth)
- Documentation vs code distinction (comments, docstrings)

**Especially useful for**:
- Languages without AST support (SemanticSearchLanguage coverage gaps)
- Config files with structured syntax (YAML, TOML, INI)
- Domain-specific languages (DSLs)
- Template languages (Jinja, Handlebars, ERB)

### 4. Hierarchical Structure Detection ⭐⭐⭐⭐

**Nesting awareness**:
```python
# Detect nested structures
chunks = [
    Chunk("class User", delimiter="class...end", level=1),
    Chunk("def __init__", delimiter="def...end", level=2, parent="class User"),
    Chunk("def save", delimiter="def...end", level=2, parent="class User"),
]
```

**Benefits**:
- Reconstruct code hierarchy without full AST
- Better context for nested code blocks
- Parent-child relationships for retrieval

### 5. Minimal Implementation Cost ⭐⭐⭐⭐⭐

**Option 2 (Minimal)**:
- Change `Delimiter` NamedTuple: +1 optional field
- Update DELIMITERS mapping: ~200 delimiter definitions, add hints
- Modify chunk creation: +10-20 lines for metadata attachment
- **Total effort**: ~2-3 hours

**Option 1 (Rich)**:
- Implement `DelimiterKind` enum: ~100 lines
- Enhanced `Delimiter` with inference: ~50 lines
- Update DELIMITERS mapping: explicit kinds for important delimiters
- Enhanced chunk creation: ~50 lines
- **Total effort**: ~1 day

---

## Implementation Recommendations

### Phase 1: Minimal Enhancement (Option 2) ✅ Start Here

**Steps**:
1. Modify `Delimiter` NamedTuple in `_constants.py`:
   ```python
   class Delimiter(NamedTuple):
       start: str
       end: str
       semantic_hint: str | None = None
   ```

2. Update key delimiter definitions in DELIMITERS:
   ```python
   # Focus on high-value semantic hints first
   - Function/method delimiters: "function"
   - Class/struct delimiters: "class" or "struct"
   - Comment delimiters: "comment_line" or "comment_block"
   - Control flow: "conditional", "loop", "try_catch"
   ```

3. Implement `BuiltinDelimiterChunker` with metadata attachment

4. Test with Python, JavaScript, C++ (cover major patterns)

**Estimated effort**: 3-4 hours

### Phase 2: Rich Metadata (Option 1) - Future Enhancement

**When to implement**:
- After BuiltinDelimiterChunker is working with minimal metadata
- If advanced filtering/retrieval features are needed
- If priority-based delimiter matching becomes important
- If nesting analysis is required

**Benefits over Phase 1**:
- Type-safe semantic kinds (enum vs strings)
- Automatic kind inference (less manual annotation)
- Priority-based matching (resolve ambiguities)
- Nesting control (prevent incorrect matches)

**Estimated effort**: 1 day

### Phase 3: Hierarchical Structure Detection - Advanced

**Capabilities**:
- Build parent-child relationships between chunks
- Detect nesting levels (classes containing methods, etc.)
- Reconstruct code structure graph
- Context-aware retrieval (find all methods of class X)

**Estimated effort**: 2-3 days

---

## Migration & Testing Strategy

### Backward Compatibility

**Option 2 (Minimal)** is fully backward compatible:
```python
# Old code continues to work
old_delimiter = Delimiter("def", "end")  # semantic_hint defaults to None

# New code gets benefits
new_delimiter = Delimiter("def", "end", "function")
```

**Option 1 (Rich)** requires migration but provides clear path:
```python
# Auto-migration script can infer kinds
for lang, delimiters in DELIMITERS.items():
    for old_delim in delimiters:
        if len(old_delim) == 2:  # Old format
            # Create new delimiter with inference
            new_delim = Delimiter(old_delim.start, old_delim.end)
            # kind will be auto-inferred via infer_kind()
```

### Testing Approach

**Unit tests**:
1. Test delimiter matching for each language
2. Test semantic metadata creation
3. Test kind inference (Option 1)
4. Test chunk name generation

**Integration tests**:
1. Compare delimiter chunking output with AST chunking (for overlap validation)
2. Test embedding quality with vs without metadata
3. Test retrieval accuracy improvements

**Performance tests**:
1. Benchmark delimiter matching speed
2. Compare with AST chunking overhead
3. Validate delimiter chunking is faster for supported languages

---

## Example: Python Function Chunking

### Input Code
```python
def calculate_total(items, tax_rate=0.1):
    """Calculate total price with tax.

    Args:
        items: List of items with prices
        tax_rate: Tax rate (default 0.1)

    Returns:
        Total price including tax
    """
    subtotal = sum(item.price for item in items)
    tax = subtotal * tax_rate
    return subtotal + tax
```

### Chunking Result with Delimiter Metadata

**Chunk 1: Function definition**
```python
CodeChunk(
    content="def calculate_total(items, tax_rate=0.1):\n    ...\n    return subtotal + tax",
    line_range=Span(1, 11),
    chunk_type=ChunkType.DELIMITER_BOUNDED,
    language="python",
    metadata={
        "chunk_id": "...",
        "created_at": 1234567890.0,
        "name": "function: calculate_total",
        "semantic_meta": {
            "chunker_type": "delimiter",
            "delimiter_start": "def",
            "delimiter_end": "end",  # Inferred from indentation/next def
            "semantic_kind": "function",
            "is_declaration": True,
            "language": "python",
            "line_range": (1, 11),
        },
        "tags": ("python", "function"),
        "context": {
            "delimiter": {"start": "def", "end": "end", "kind": "function"},
            "language": "python",
        },
    }
)
```

**Chunk 2: Docstring** (if nested chunking enabled)
```python
CodeChunk(
    content='"""Calculate total price with tax.\n    ...\n    """',
    line_range=Span(2, 9),
    chunk_type=ChunkType.DELIMITER_BOUNDED,
    language="python",
    metadata={
        "name": "docstring: calculate_total",
        "semantic_meta": {
            "chunker_type": "delimiter",
            "delimiter_start": '"""',
            "delimiter_end": '"""',
            "semantic_kind": "docstring",
            "is_documentation": True,
            "parent_chunk": "function: calculate_total",
        },
        "tags": ("python", "docstring"),
    }
)
```

### Comparison: No Metadata vs With Metadata

**Embedding context without metadata**:
```
[python code chunk]
def calculate_total(items, tax_rate=0.1):
    subtotal = sum(item.price for item in items)
    ...
```

**Embedding context with metadata**:
```
[python function definition: calculate_total]
Language: python
Chunk type: function
Delimiter: def...end
Semantic kind: function declaration

def calculate_total(items, tax_rate=0.1):
    subtotal = sum(item.price for item in items)
    ...
```

**Result**: Better semantic understanding for embedding and retrieval.

---

## Conclusion

### Recommendation: ✅ Implement Phase 1 (Minimal Enhancement)

**Justification**:
1. **Low effort, high value**: 3-4 hours for significant metadata improvements
2. **Backward compatible**: No breaking changes to existing code
3. **Immediate benefits**: Better embeddings, retrieval, and context
4. **Foundation for future**: Easy to extend to Option 1 (rich) later
5. **Complements AST chunking**: Provides semantic info for non-AST languages

### Implementation Priority

1. **High**: Implement Option 2 (minimal) during BuiltinDelimiterChunker development
2. **Medium**: Enhance to Option 1 (rich) if advanced features needed
3. **Low**: Hierarchical structure detection (Phase 3) - only if required for specific use cases

### Next Steps

1. Update `Delimiter` NamedTuple with `semantic_hint` field
2. Annotate high-value delimiters in DELIMITERS mapping (functions, classes, comments)
3. Implement metadata attachment in `BuiltinDelimiterChunker._chunk_with_delimiters()`
4. Add unit tests for delimiter metadata creation
5. Validate embedding quality improvements

**Recommendation**: ✅ **Proceed with Phase 1** - implement alongside chunker refactoring
