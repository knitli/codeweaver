<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Phase 1: Data Model

**Feature**: CodeWeaver v0.1 Release
**Date**: 2025-10-27
**Based On**: Feature specification entities (spec.md § Data Models)

## Entity Overview

All entities are Pydantic BaseModels with strict type validation, following constitutional requirements for type system discipline.

### Core Data Flow

```
DiscoveredFile → CodeChunk → Embeddings → VectorStore → CodeMatch → FindCodeResponseSummary
     ↓              ↓             ↓            ↓             ↓              ↓
  Filtering    Chunking     Embedding     Indexing     Searching      Response
```

## Entity Definitions

### 1. CodeChunk (Core Building Block)

**Module**: `codeweaver.core.chunks`
**Purpose**: Represents a semantic unit of code (function, class, method, or text block)

**Fields**:
```python
content: str                                    # Code content (raw text)
line_range: Span                               # (start_line, end_line) in source
file_path: Path | None                         # Source file absolute path
language: SemanticSearchLanguage | str | None  # Language identifier
source: ChunkSource                            # TEXT_BLOCK | FILE | AST_NODE
ext_kind: ExtKind | None                       # File extension metadata
timestamp: float                               # Unix timestamp (creation/modification)
chunk_id: UUID7                                # Unique chunk identifier
parent_id: UUID7 | None                        # Parent chunk (e.g., file chunk ID)
metadata: Metadata | None                      # Additional key-value metadata
chunk_name: str | None                         # Fully qualified name (e.g., "auth.py:UserAuth.validate")
embeddings: dict | None                        # {"dense": [...], "sparse": {...}}
```

**Validation Rules**:
- `line_range.start <= line_range.end`
- `content` must not be empty string
- `chunk_id` is UUID7 (timestamp-sortable)
- `embeddings` only populated after embedding generation
- `chunk_name` format: "{filename}:{qualified_name}" for AST nodes

**State Transitions**:
```
Created (no embeddings) → Embedded (has embeddings) → Indexed (in vector store)
```

**Related Entities**: DiscoveredFile (parent), Span, Metadata

---

### 2. DiscoveredFile

**Module**: `codeweaver.middleware.filtering` (from IndexerSettings)
**Purpose**: Represents a discovered file during indexing with metadata

**Fields**:
```python
path: Path                                     # Absolute file path
language: SemanticSearchLanguage | str         # Detected language
size_bytes: int                                # File size
last_modified: float                           # Unix timestamp
ext_kind: ExtKind                              # Extension classification
is_test: bool                                  # Test file indicator
```

**Validation Rules**:
- `path` must exist and be readable
- `size_bytes >= 0`
- `language` auto-detected from extension or content

**Derivation**: Created by `rignore` file walker + language detection

**Related Entities**: CodeChunk (children), ExtKind, SemanticSearchLanguage

---

### 3. CodeMatch

**Module**: `codeweaver.agent_api.models`
**Purpose**: Individual search result with relevance scoring

**Fields**:
```python
file: DiscoveredFile                           # File information
content: CodeChunk                             # The matching code chunk
span: Span                                     # Line numbers (start, end)
relevance_score: float                         # [0.0-1.0] weighted score
match_type: CodeMatchType                      # SEMANTIC | SYNTACTIC | KEYWORD | FILE_PATTERN
related_symbols: tuple[str, ...]               # Related functions/classes
```

**Validation Rules**:
- `0.0 <= relevance_score <= 1.0`
- `span` must match `content.line_range`
- `file.path` must match `content.file_path`

**Scoring Calculation**:
```python
relevance_score = (
    rerank_score * 0.5 +                       # Reranker score (VoyageAI)
    dense_similarity * 0.3 +                   # Dense vector similarity
    sparse_similarity * 0.1 +                  # Sparse vector similarity
    semantic_weight * 0.1                      # ImportanceScores adjustment
)
```

**Related Entities**: DiscoveredFile, CodeChunk, Span, CodeMatchType

---

### 4. FindCodeResponseSummary

**Module**: `codeweaver.agent_api.models`
**Purpose**: Complete response from `find_code` tool

**Fields**:
```python
matches: list[CodeMatch]                       # Ranked results
summary: str                                   # High-level explanation (max 1000 chars)
query_intent: IntentType | None                # Detected or specified intent
total_matches: int                             # Candidates before ranking
total_results: int                             # Results in response
token_count: int                               # Actual tokens used
execution_time_ms: float                       # Total processing time
search_strategy: tuple[SearchStrategy, ...]    # HYBRID_SEARCH, SEMANTIC_RERANK, etc.
languages_found: tuple[str, ...]               # Languages in results
```

**Validation Rules**:
- `len(matches) == total_results`
- `total_results <= total_matches`
- `0 < len(summary) <= 1000`
- `execution_time_ms >= 0`

**Business Logic**:
- `summary` generated from top 3 matches (file paths + brief description)
- `query_intent` from heuristic analysis or user-provided parameter
- `search_strategy` reflects actual execution path (with fallbacks)

**Related Entities**: CodeMatch, IntentType, SearchStrategy

---

### 5. IntentType (Enum)

**Module**: `codeweaver.agent_api.intent`
**Purpose**: Classify user/agent search intent

**Values**:
```python
UNDERSTAND = "understand"      # Understand codebase structure
IMPLEMENT = "implement"        # Implement new features
DEBUG = "debug"                # Debug issues and errors
OPTIMIZE = "optimize"          # Optimize performance
TEST = "test"                  # Write or modify tests
CONFIGURE = "configure"        # Update configuration
DOCUMENT = "document"          # Write or update documentation
```

**Extensibility**:
- Designed for future additions (FR-028)
- `find_code` accepts `IntentType | str` for forward compatibility
- Unknown values handled gracefully (default to None)

**Usage**: Adjusts semantic weighting in ranking algorithm (see ImportanceScores)

**Related Entities**: QueryIntent, ImportanceScores, AgentTask

---

### 6. QueryIntent

**Module**: `codeweaver.agent_api.intent`
**Purpose**: Analyzed query intent with confidence scoring

**Fields**:
```python
intent_type: IntentType                        # Classified intent
confidence: float                              # [0.0-1.0] confidence score
reasoning: str                                 # Why this intent detected
focus_areas: tuple[str, ...]                   # Specific focus (e.g., ["authentication", "middleware"])
complexity_level: QueryComplexity              # SIMPLE | MODERATE | COMPLEX
```

**Validation Rules**:
- `0.0 <= confidence <= 1.0`
- `reasoning` must be non-empty
- `len(focus_areas) >= 0`

**Heuristic Detection Rules**:
- UNDERSTAND: "how does", "what is", "explain"
- IMPLEMENT: "add", "create", "build", "implement"
- DEBUG: "why", "error", "crash", "bug", "exception"
- OPTIMIZE: "slow", "performance", "faster", "optimize"
- TEST: "test", "testing", "spec", "should"
- CONFIGURE: "config", "settings", "setup"
- DOCUMENT: "document", "docs", "readme"

**Related Entities**: IntentType, QueryComplexity, IntentResult

---

### 7. ImportanceScores

**Module**: `codeweaver.semantic.classifications`
**Purpose**: Multi-dimensional importance scoring for AI contexts

**Fields**:
```python
discovery: float                               # [0.0-1.0] Finding relevant code
comprehension: float                           # [0.0-1.0] Understanding behavior
modification: float                            # [0.0-1.0] Safe editing points
debugging: float                               # [0.0-1.0] Tracing execution
documentation: float                           # [0.0-1.0] Explaining code
```

**Validation Rules**:
- All fields: `0.0 <= value <= 1.0`
- Sum not required to equal 1.0 (independent dimensions)

**Usage in Ranking**:
```python
# Apply IntentType weighting
if intent == IntentType.UNDERSTAND:
    score_adjustment = importance.comprehension * 1.5
elif intent == IntentType.DEBUG:
    score_adjustment = importance.debugging * 1.4
elif intent == IntentType.IMPLEMENT:
    score_adjustment = (importance.discovery + importance.modification) * 1.3
```

**Related Entities**: SemanticClass, AgentTask, IntentType

---

### 8. SemanticClass (Enum)

**Module**: `codeweaver.semantic.classifications`
**Purpose**: Language-agnostic semantic categories for AST nodes

**Tiers** (20+ classifications):

**Tier 1 - Primary Definitions**:
- DEFINITION_CALLABLE: Functions, methods, procedures
- DEFINITION_TYPE: Classes, structs, interfaces, enums
- DEFINITION_DATA: Variables, constants, fields
- DEFINITION_TEST: Test functions, test classes

**Tier 2 - Behavioral Contracts**:
- BOUNDARY_MODULE: Imports, exports, package declarations
- BOUNDARY_ERROR: Try-catch, error handling, exceptions
- BOUNDARY_RESOURCE: File I/O, network, database connections
- DOCUMENTATION_STRUCTURED: Docstrings, JSDoc, JavaDoc

**Tier 3 - Control Flow**:
- FLOW_BRANCHING: If-else, switch-case, pattern matching
- FLOW_ITERATION: For, while, map, reduce
- FLOW_CONTROL: Break, continue, return, yield
- FLOW_ASYNC: Async/await, promises, coroutines

**Tier 4 - Operations**:
- OPERATION_INVOCATION: Function calls, method calls
- OPERATION_DATA: Assignments, data transformations
- OPERATION_OPERATOR: Arithmetic, logical, bitwise operators
- EXPRESSION_ANONYMOUS: Lambdas, closures, arrow functions

**Tier 5 - Syntax**:
- SYNTAX_KEYWORD: Language keywords (if, for, class, etc.)
- SYNTAX_IDENTIFIER: Variable names, function names
- SYNTAX_LITERAL: String, number, boolean literals
- SYNTAX_ANNOTATION: Type hints, decorators, attributes
- SYNTAX_PUNCTUATION: Braces, parentheses, semicolons

**Importance Mapping**:
Each SemanticClass has an ImportanceScores profile (e.g., DEFINITION_TYPE has high discovery=0.95)

**Related Entities**: ImportanceScores, AgentTask

---

### 9. AgentTask (Enum)

**Module**: `codeweaver.semantic.classifications`
**Purpose**: Predefined task contexts with importance weight profiles

**Values**:
```python
DEBUG = "debug"
DEFAULT = "default"
DOCUMENT = "document"
IMPLEMENT = "implement"
LOCAL_EDIT = "local_edit"
REFACTOR = "refactor"
REVIEW = "review"
SEARCH = "search"
TEST = "test"
```

**Weight Profiles Example** (DEBUG):
```python
{
    "discovery": 0.2,
    "comprehension": 0.3,
    "modification": 0.1,
    "debugging": 0.35,      # Highest for DEBUG task
    "documentation": 0.05
}
```

**Usage**: Provides context-specific weighting when IntentType is not specified

**Related Entities**: ImportanceScores, IntentType

---

### 10. Span (Type Alias)

**Module**: `codeweaver.core.chunks`
**Purpose**: Line range representation

**Definition**:
```python
Span = tuple[int, int]  # (start_line, end_line) - 1-indexed, inclusive
```

**Validation Rules**:
- `start_line >= 1`
- `end_line >= start_line`
- Both integers

**Usage**: Represents line ranges in source files for chunks and matches

---

### 11. SemanticSearchLanguage (Enum)

**Module**: `codeweaver.language`
**Purpose**: Supported programming languages for semantic search

**Values**: 20+ languages including:
- Python, JavaScript, TypeScript, Java, Rust, Go, C, C++, C#, Swift, Kotlin
- Ruby, PHP, Scala, Haskell, Lua, R, Perl, Shell, SQL, HTML, CSS, Markdown

**Detection**: From file extension or content analysis

**Related Entities**: DiscoveredFile, CodeChunk

---

### 12. ChunkSource (Enum)

**Module**: `codeweaver.core.chunks`
**Purpose**: Origin of code chunk

**Values**:
```python
TEXT_BLOCK = "text_block"  # Text-based chunking (fallback)
FILE = "file"              # Whole file chunk
AST_NODE = "ast_node"      # AST-based syntactic unit
```

**Usage**: Indicates chunking strategy used (AST preferred, text fallback)

---

### 13. CodeMatchType (Enum)

**Module**: `codeweaver.agent_api.models`
**Purpose**: Type of match found

**Values**:
```python
SEMANTIC = "semantic"      # Semantic similarity via embeddings
SYNTACTIC = "syntactic"    # AST pattern match
KEYWORD = "keyword"        # Keyword/text match
FILE_PATTERN = "file_pattern"  # File path/name match
```

**Usage**: Indicates primary matching mechanism for result

---

### 14. SearchStrategy (Enum)

**Module**: `codeweaver.agent_api.models`
**Purpose**: Search execution strategies

**Values**:
```python
HYBRID_SEARCH = "hybrid_search"              # Dense + sparse vectors
SEMANTIC_RERANK = "semantic_rerank"          # Reranker applied
SPARSE_ONLY = "sparse_only"                  # Fallback (API down)
DENSE_ONLY = "dense_only"                    # Legacy/future
KEYWORD_FALLBACK = "keyword_fallback"        # Last resort
```

**Usage**: Tracks actual search execution path (for debugging and monitoring)

---

## Relationships

### One-to-Many
- **DiscoveredFile → CodeChunk**: One file produces multiple chunks
- **FindCodeResponseSummary → CodeMatch**: One response contains multiple matches

### One-to-One
- **CodeMatch → CodeChunk**: Each match references one chunk
- **CodeMatch → DiscoveredFile**: Each match references one file

### Many-to-Many
- **SemanticClass ↔ ImportanceScores**: Each class has importance scores, scores apply to multiple classes

### Enumerations
- **IntentType**: Used by QueryIntent, FindCodeResponseSummary
- **AgentTask**: Used by ranking algorithm, alternative to IntentType
- **SemanticClass**: Applied to CodeChunk during AST analysis

---

## Data Validation Patterns

All entities follow constitutional type system discipline:

### Pydantic Validation
```python
from pydantic import BaseModel, Field, field_validator

class CodeChunk(BaseModel):
    content: str = Field(min_length=1)
    line_range: Span
    chunk_id: UUID7 = Field(default_factory=uuid7)

    @field_validator("line_range")
    @classmethod
    def validate_line_range(cls, v: Span) -> Span:
        start, end = v
        if start < 1 or end < start:
            raise ValueError(f"Invalid line range: {v}")
        return v
```

### Immutability
Most entities use `frozen=True` for immutability (constitutional requirement):
```python
class CodeMatch(BaseModel, frozen=True):
    # ... fields ...
```

### Type Safety
Strict typing with no `dict[str, Any]` (constitutional requirement):
```python
# ✅ Correct
metadata: Metadata | None

# ❌ Wrong (violates constitution)
metadata: dict[str, Any] | None
```

---

## State Machines

### CodeChunk Lifecycle
```
[Created] → [Embedded] → [Indexed] → [Matched] → [Returned]
   ↓            ↓            ↓           ↓           ↓
no_emb     has_emb      in_vector   in_results  in_response
```

### Search Query Flow
```
[Query] → [Intent Analysis] → [Embedding] → [Retrieval] → [Reranking] → [Response]
   ↓              ↓                ↓              ↓             ↓             ↓
  str      QueryIntent      embeddings    candidates   ranked_matches  Summary
```

---

## Performance Considerations

### Chunk Size Limits
- Target: 200-800 tokens per chunk
- Hard limit: 4000 tokens (FR-039)
- Truncate if exceeded, log warning

### Embedding Batch Sizes
- Max 100 chunks per VoyageAI API request
- Max 10 concurrent requests (FR-039)

### Memory Limits
- Max 2GB resident set size per indexing session (FR-039)
- Use generators for large file processing
- Stream results, don't load all in memory

---

## Serialization Formats

### JSON (API Responses)
All Pydantic models serialize to JSON via `.model_dump_json()`:
```python
response = FindCodeResponseSummary(...)
json_str = response.model_dump_json(indent=2)
```

### TOML (Configuration)
Settings use `pydantic-settings` with TOML support:
```toml
[codeweaver]
project_path = "/path/to/codebase"
max_chunk_size = 800

[embedding]
provider = "voyageai"
model = "voyage-code-3"
```

---

## Testing Requirements

### Contract Tests
Each entity requires contract tests validating:
1. Field types and constraints
2. Validation rules (e.g., line_range constraints)
3. Serialization round-trip (JSON, TOML)
4. State transitions (if applicable)

### Integration Tests
Entity relationships validated in integration tests:
- DiscoveredFile → CodeChunk creation
- CodeChunk → CodeMatch transformation
- QueryIntent → ranking adjustment

---

**Phase 1 Data Model Status**: ✅ COMPLETE
**Entities Documented**: 14 core entities + enums
**Validation**: Pydantic-based, constitution-compliant
**Next**: Generate API contracts (contracts/ directory)
