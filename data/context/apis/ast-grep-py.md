<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# ast-grep-py API Research Report

*Expert API Analyst Research - Foundation for CodeWeaver Semantic Search Integration*

## Summary

**Feature Name**: ast-grep-py Integration for Semantic Codebase Analysis  
**Feature Description**: Python bindings for ast-grep, enabling high-performance AST-based semantic search, code analysis, and transformation across 25+ programming languages  
**Feature Goal**: Replace text-based indexing with intelligent semantic indexing using Abstract Syntax Tree patterns for more accurate and contextual code discovery

**Primary External Surface(s)**: 
- `SgRoot` class (parsing entry point)
- `SgNode` class (AST node manipulation and search)
- `Edit` class (code transformation operations)
- `Config`/`Rule` types (search configuration)

**Integration Confidence**: High - Well-documented Python API with proven performance characteristics, extensive language support, and clear integration path with existing CodeWeaver language detection system

## Core Types

| Name | Kind | Definition | Role |
|------|------|------------|------|
| `SgRoot` | Class | AST parsing entry point | Parses source code into searchable AST representation |
| `SgNode` | Class | AST node with search/traversal methods | Primary interface for semantic search and code analysis |
| `Edit` | Class | Text modification descriptor | Represents code transformations with position and content |
| `Rule` | TypedDict | Search pattern configuration | Defines atomic, relational, and composite search rules |
| `Config` | TypedDict | Complete rule configuration | Mirrors ast-grep's YAML rule structure |
| `Pattern` | TypedDict | Context-aware pattern matching | Advanced pattern with selector and context |
| `Range` | Class | Source code position range | Tracks start/end positions for nodes and edits |

## Signatures

### Core Parser Classes

>NOTE!: CodeWeaver has serializable versions of each of these types, any codeweaver implementation should use those types and not the native ast_grep_py types.  CodeWeaver's versions are in `src/codeweaver/_ast_grep.py`

**Class: SgRoot**
```python
class SgRoot:
    def __init__(self, src: str, language: str) -> None: ...
    def root(self) -> SgNode: ...
    def filename(self) -> str: ...  # Returns "anonymous" for string parsing
```
- **Import Path**: `from ast_grep_py import SgRoot`
- **Concrete Path**: Available via PyPI package `ast-grep-py`
- **Params**: 
  - `src: str` (required) - Source code string to parse
  - `language: str` (required) - Language identifier (matches SemanticSearchLanguage enum values)
- **Returns**: Initialized SgRoot instance containing parsed AST
- **Errors**: Parsing errors if language unsupported or syntax invalid
- **Notes**: Thread-safe, supports async parsing via `parseAsync()` in Node.js bindings

**Type Information**: Language parameter should match CodeWeaver's `SemanticSearchLanguage` enum values: "python", "javascript", "typescript", "rust", "go", etc.

### Core Search and Manipulation Classes

**Class: SgNode**
```python
class SgNode:
    # Node Inspection
    def range(self) -> Range: ...
    def is_leaf(self) -> bool: ...
    def is_named(self) -> bool: ...
    def is_named_leaf(self) -> bool: ...
    def kind(self) -> str: ...
    def text(self) -> str: ...

    # Search Methods (overloaded)
    @overload
    def find(self, **kwargs: Unpack[Rule]) -> Optional[SgNode]: ...
    @overload
    def find_all(self, **kwargs: Unpack[Rule]) -> List[SgNode]: ...
    @overload
    def find(self, config: Config) -> Optional[SgNode]: ...
    @overload
    def find_all(self, config: Config) -> List[SgNode]: ...

    # Meta Variable Access
    def get_match(self, meta_var: str) -> Optional[SgNode]: ...
    def get_multiple_matches(self, meta_var: str) -> List[SgNode]: ...
    def __getitem__(self, meta_var: str) -> SgNode: ...  # Raises KeyError if not found

    # Tree Traversal
    def get_root(self) -> SgRoot: ...
    def field(self, name: str) -> Optional[SgNode]: ...
    def parent(self) -> Optional[SgNode]: ...
    def child(self, nth: int) -> Optional[SgNode]: ...
    def children(self) -> List[SgNode]: ...
    def ancestors(self) -> List[SgNode]: ...
    def next(self) -> Optional[SgNode]: ...
    def next_all(self) -> List[SgNode]: ...
    def prev(self) -> Optional[SgNode]: ...
    def prev_all(self) -> List[SgNode]: ...

    # Search Refinement
    def matches(self, **rule: Unpack[Rule]) -> bool: ...
    def inside(self, **rule: Unpack[Rule]) -> bool: ...
    def has(self, **rule: Unpack[Rule]) -> bool: ...
    def precedes(self, **rule: Unpack[Rule]) -> bool: ...
    def follows(self, **rule: Unpack[Rule]) -> bool: ...

    # Code Editing
    def replace(self, new_text: str) -> Edit: ...
    def commit_edits(self, edits: List[Edit]) -> str: ...
```

- **Import Path**: `from ast_grep_py import SgNode`
- **Concrete Path**: Returned by `SgRoot.root()` and search methods
- **Key Methods**:
  - `find(pattern="print($A)")` - Single pattern search with meta-variable capture
  - `find_all(kind="function_definition")` - Multiple node search by AST node type
  - `node["A"].text()` - Direct meta-variable access (preferred over get_match for type safety)
- **Returns**: Various - nodes, text, boolean matches, position ranges
- **Errors**: `KeyError` for missing meta-variables, `None` for failed searches
- **Notes**: All search operations are performed in Rust for optimal performance, minimizing Python-Rust FFI calls

**Class: Edit**
```python
class Edit:
    start_pos: int      # Start byte position in source
    end_pos: int        # End byte position in source  
    inserted_text: str  # Replacement text content
```

- **Import Path**: `from ast_grep_py import Edit`
- **Concrete Path**: Generated by `SgNode.replace()` method
- **Usage**: Immutable edit descriptors that can be batched and applied via `commit_edits()`
- **Notes**: Positions are byte-based, not character-based; supports batching multiple edits for atomic updates

## Type Graph

```
SgRoot --> parses --> source_code: str + language: str
SgRoot --> produces --> SgNode (root)

SgNode --> searches --> SgNode[] (results)
SgNode --> contains --> meta_variables: Dict[str, SgNode]
SgNode --> navigates --> parent: SgNode | None
SgNode --> navigates --> children: List[SgNode]
SgNode --> transforms --> Edit (via replace())

Edit --> contains --> position: (start_pos, end_pos)
Edit --> contains --> content: inserted_text
Edit[] --> applies_to --> SgNode (via commit_edits())

Rule --> configures --> atomic_rules: pattern | kind | regex
Rule --> configures --> relational_rules: inside | has | precedes | follows
Rule --> configures --> composite_rules: all | any | not

Config --> extends --> Rule
Config --> adds --> constraints: Dict[str, Mapping]
Config --> adds --> transforms: Dict[str, Mapping]
```

## Request/Response Schemas

### Basic Search Workflow

**Parse and Search Request**:
```python
# 1. Initialize parser
root = SgRoot("print('hello world')", "python")
node = root.root()

# 2. Pattern-based search
result = node.find(pattern="print($A)")
if result:
    captured_text = result["A"].text()  # 'hello world'
```

**Advanced Search Configuration**:
```python
# Using Config object for complex searches
config = {
    "rule": {
        "pattern": "print($A)",
    },
    "constraints": {
        "A": {"regex": "hello"}
    }
}
result = node.find(config)
```

### Batch File Processing

**Performance-Optimized File Processing**:
```python
# Recommended pattern for large codebases
from ast_grep_py import SgRoot
import asyncio
from pathlib import Path

async def process_files_batch(file_paths: List[Path], language: str):
    """Process multiple files in parallel using async parsing"""
    tasks = []
    for file_path in file_paths:
        content = file_path.read_text()
        # Use parseAsync equivalent or thread pool for parallel processing
        task = asyncio.create_task(analyze_file(content, language))
        tasks.append(task)
    
    results = await asyncio.gather(*tasks)
    return results

def analyze_file(content: str, language: str) -> List[dict]:
    """Single file analysis with semantic search"""
    root = SgRoot(content, language)
    node = root.root()
    
    # Find all function definitions
    functions = node.find_all(kind="function_definition")
    
    results = []
    for func in functions:
        results.append({
            "name": func.field("name").text() if func.field("name") else "anonymous",
            "start": func.range().start_pos,
            "end": func.range().end_pos,
            "text": func.text()
        })
    return results
```

### Code Transformation Workflow

**Edit Generation and Application**:
```python
# 1. Find target nodes
root = SgRoot("console.log('debug info')", "javascript")
node = root.root()
console_calls = node.find_all(pattern="console.log($MSG)")

# 2. Generate edits
edits = []
for call in console_calls:
    edit = call.replace("logger.debug($MSG)")
    edits.append(edit)

# 3. Apply all edits atomically
new_source = node.commit_edits(edits)
# Result: "logger.debug('debug info')"
```

## Implementation Patterns

### Integration with CodeWeaver Language System

**Language Detection Integration**:
```python
# Leverage existing SemanticSearchLanguage enum
from codeweaver.language import SemanticSearchLanguage
from ast_grep_py import SgRoot

def create_semantic_parser(file_path: Path) -> Optional[SgRoot]:
    """Create ast-grep parser using CodeWeaver language detection"""
    
    # Use existing extension mapping
    ext = file_path.suffix.lstrip('.')
    language = SemanticSearchLanguage.lang_from_ext(ext)
    
    if not language:
        return None
        
    # Map to ast-grep language identifier
    ast_grep_lang = language.value  # e.g., "python", "javascript"
    content = file_path.read_text()
    
    return SgRoot(content, ast_grep_lang)
```


### Performance Optimization Patterns

**Efficient Batch Processing**:
```python
def process_large_codebase(root_path: Path, max_workers: int = 4) -> List[Dict]:
    """Optimized processing for large codebases"""
    from concurrent.futures import ThreadPoolExecutor
    import threading
    
    # Collect all supported files
    file_tasks = []
    for lang in SemanticSearchLanguage.members():
        if lang.extensions:
            for ext in lang.extensions:
                pattern = f"**/*.{ext}"
                files = list(root_path.glob(pattern))
                file_tasks.extend([(f, lang.value) for f in files])
    
    # Process in parallel threads (ast-grep parsing is CPU-bound)
    results = []
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {
            executor.submit(analyze_single_file, file_path, language): (file_path, language)
            for file_path, language in file_tasks
        }
        
        for future in concurrent.futures.as_completed(futures):
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                file_path, language = futures[future]
                print(f"Error processing {file_path}: {e}")
                continue
                
    return results

def analyze_single_file(file_path: Path, language: str) -> Dict[str, Any]:
    """Single-threaded file analysis optimized for performance"""
    content = file_path.read_text()
    root = SgRoot(content, language)
    node = root.root()
    
    # Use find_all for better performance than manual traversal
    # This minimizes Python-Rust FFI calls
    functions = node.find_all(kind="function_definition")
    classes = node.find_all(kind="class_definition")
    imports = node.find_all(kind="import_statement")
    
    return {
        "file_path": str(file_path),
        "language": language,
        "metrics": {
            "function_count": len(functions),
            "class_count": len(classes),
            "import_count": len(imports),
            "total_lines": content.count('\n') + 1
        },
        "semantic_elements": [
            {
                "type": "function",
                "name": f.field("name").text() if f.field("name") else "anonymous",
                "range": (f.range().start_pos, f.range().end_pos)
            }
            for f in functions
        ]
    }
```

## Differences vs Project Requirements

### Alignment Strengths

1. **Performance Requirements**: ast-grep-py's Rust implementation with multi-core processing perfectly aligns with CodeWeaver's need for high-performance codebase analysis.

2. **Language Support**: Supports 25+ languages matching CodeWeaver's `SemanticSearchLanguage` enum, enabling comprehensive polyglot codebase analysis.

3. **FastMCP Integration**: API design allows seamless integration with FastMCP's tool architecture and Context injection patterns.

4. **Pydantic Compatibility**: Type-safe API design works well with pydantic models and validation throughout CodeWeaver's architecture.

5. **Semantic Understanding**: AST-based analysis provides the "semantic" intelligence CodeWeaver needs beyond simple text matching.

### Integration Recommendations

1. **Language Detection Bridge**: 
   - **Current**: CodeWeaver's `SemanticSearchLanguage` enum provides file extension mapping
   - **Integration**: Use enum values directly as language identifiers for `SgRoot(src, language)`
   - **Enhancement**: Add validation to ensure ast-grep supports detected languages

2. **Indexing Pipeline Enhancement**:
   - **Current**: Planned text-based chunking and embedding
   - **Enhancement**: Use ast-grep to extract semantic chunks (functions, classes, modules) rather than arbitrary text chunks
   - **Benefit**: More meaningful context units for vector storage and retrieval

3. **Config-Aware Processing**:
   - **Current**: `LanguageConfigFile` maps languages to config files and dependency paths
   - **Integration**: Use ast-grep to parse config files and extract actual dependency information
   - **Enhancement**: Semantic understanding of project structure beyond file system analysis

4. **Performance Integration**:
   - **Current**: Individual file processing planned
   - **Enhancement**: Leverage ast-grep's multi-core batch processing via threading
   - **Pattern**: Use `ThreadPoolExecutor` for CPU-bound AST parsing tasks

### Gap Analysis

**Missing Capabilities**:
1. **File System Walking**: ast-grep-py doesn't include file discovery - CodeWeaver needs to integrate with `watchfiles` and `rignore` for file system operations
2. **Vector Embedding Integration**: ast-grep provides semantic structure but doesn't generate embeddings - needs integration with Voyage AI
3. **Configuration Management**: ast-grep-py is purely parsing/analysis - needs integration with pydantic-settings for configuration

**CodeWeaver-Specific Adaptations Needed**:
1. **Intent Analysis**: Map user queries to appropriate ast-grep search patterns
2. **Result Ranking**: Combine ast-grep results with vector similarity for relevance ranking  
3. **Context Assembly**: Use ast-grep's semantic understanding to build better context for LLM consumption
4. **Incremental Updates**: Handle file changes detected by watchfiles through targeted ast-grep re-analysis

**Architectural Considerations**:
1. **Memory Management**: Large codebases may require streaming/chunked processing of ast-grep results
2. **Error Handling**: Graceful degradation when ast-grep parsing fails (unsupported syntax, etc.)
3. **Caching Strategy**: Cache parsed ASTs for frequently accessed files, invalidate on file changes

## Sources

[ast-grep Python API Documentation | ast-grep](https://ast-grep.github.io/guide/api-usage/py-api.html) | official | latest | reliability: 5
[ast-grep API Reference | ast-grep](https://ast-grep.github.io/reference/api.html) | official | latest | reliability: 5  
[ast-grep Performance Guide | ast-grep](https://ast-grep.github.io/guide/api-usage/performance-tip.html) | official | latest | reliability: 5
[ast-grep PyPI Package](https://pypi.org/project/ast-grep-py/) | official | 0.28.0+ | reliability: 5
[ast-grep GitHub Repository](https://github.com/ast-grep/ast-grep) | official | latest | reliability: 5
[ast-grep Language Support](https://ast-grep.github.io/reference/languages.html) | official | latest | reliability: 5
[Context7 ast-grep Documentation](https://ast-grep.github.io/) | official | latest | reliability: 5
[Web Search Results: ast-grep-py performance characteristics](web-search) | mixed | 2024 | reliability: 4

---

*This research report provides the technical foundation needed for integrating ast-grep-py into CodeWeaver's semantic search architecture. All API patterns and integration recommendations are designed to work seamlessly with CodeWeaver's FastMCP, pydantic-graph, and existing language detection systems while providing significant performance and semantic understanding improvements over text-based indexing approaches.*