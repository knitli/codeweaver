<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# CodeWeaver Chunker Usage Guide

Comprehensive guide for using the CodeWeaver chunking system for semantic code search.

## Table of Contents

- [Overview](#overview)
- [Quick Start](#quick-start)
- [Basic Workflows](#basic-workflows)
- [Configuration](#configuration)
- [Error Handling](#error-handling)
- [Performance Optimization](#performance-optimization)
- [Parallel Processing](#parallel-processing)
- [Troubleshooting](#troubleshooting)

## Overview

CodeWeaver's chunking system provides intelligent code segmentation optimized for AI-powered semantic search. It supports two primary chunking strategies:

- **Semantic Chunking**: AST-based parsing for 26+ languages with rich metadata
- **Delimiter Chunking**: Pattern-based fallback for 170+ languages

The system automatically selects the appropriate strategy based on file language and gracefully degrades when parsing fails.

### Key Features

- ✅ AI-optimized metadata with importance scores
- ✅ Content-based deduplication
- ✅ Resource governance (timeouts, limits)
- ✅ Graceful degradation chain
- ✅ Parallel processing support
- ✅ Comprehensive edge case handling

## Quick Start

### Basic Chunking

```python
from pathlib import Path
from codeweaver.engine.chunker.selector import ChunkerSelector
from codeweaver.engine.chunker.governance import ChunkGovernor
from codeweaver.config.settings import get_settings
from codeweaver.core.discovery import DiscoveredFile

# Get settings and create governor
settings = get_settings()
governor = ChunkGovernor(settings.chunker.performance)

# Create selector
selector = ChunkerSelector(governor)

# Chunk a file
file_path = Path("src/myapp/models.py")
content = file_path.read_text()

discovered_file = DiscoveredFile(path=file_path)
chunker = selector.select_for_file(discovered_file)
chunks = chunker.chunk(content, file_path=file_path)

print(f"Generated {len(chunks)} chunks")
for i, chunk in enumerate(chunks[:3]):
    print(f"\nChunk {i+1}:")
    print(f"  Lines: {chunk.line_range.start}-{chunk.line_range.end}")
    print(f"  Length: {len(chunk.content)} chars")
    print(f"  Language: {chunk.language}")
```

### Using Specific Chunkers

```python
from codeweaver.engine.chunker.semantic import SemanticChunker
from codeweaver.core.language import SemanticSearchLanguage

# Semantic chunker for Python
semantic = SemanticChunker(governor, SemanticSearchLanguage.PYTHON)
chunks = semantic.chunk(content, file_path=file_path)
```

```python
from codeweaver.engine.chunker.delimiter import DelimiterChunker

# Delimiter chunker for JavaScript
delimiter = DelimiterChunker(governor, "javascript")
chunks = delimiter.chunk(content, file_path=file_path)
```

## Basic Workflows

### 1. Single File Chunking

```python
def chunk_single_file(file_path: Path) -> list[CodeChunk]:
    """Chunk a single file with automatic strategy selection."""
    settings = get_settings()
    governor = ChunkGovernor(settings.chunker.performance)
    selector = ChunkerSelector(governor)

    content = file_path.read_text()
    discovered_file = DiscoveredFile(path=file_path)
    chunker = selector.select_for_file(discovered_file)

    return chunker.chunk(content, file_path=file_path)
```

### 2. Batch Processing

```python
def chunk_multiple_files(file_paths: list[Path]) -> dict[Path, list[CodeChunk]]:
    """Chunk multiple files sequentially."""
    settings = get_settings()
    governor = ChunkGovernor(settings.chunker.performance)
    selector = ChunkerSelector(governor)

    results = {}
    for file_path in file_paths:
        try:
            content = file_path.read_text()
            discovered_file = DiscoveredFile(path=file_path)
            chunker = selector.select_for_file(discovered_file)
            chunks = chunker.chunk(content, file_path=file_path)
            results[file_path] = chunks
        except Exception as e:
            print(f"Failed to chunk {file_path}: {e}")
            results[file_path] = []

    return results
```

### 3. Metadata Inspection

```python
def inspect_chunk_metadata(chunks: list[CodeChunk]):
    """Inspect rich metadata from semantic chunking."""
    for chunk in chunks:
        if "semantic_meta" in chunk.metadata:
            meta = chunk.metadata["semantic_meta"]
            print(f"Symbol: {meta.get('symbol')}")
            print(f"Language: {meta.get('language')}")

        if "context" in chunk.metadata:
            ctx = chunk.metadata["context"]
            print(f"Classification: {ctx.get('classification')}")
            print(f"Kind: {ctx.get('kind')}")
            print(f"Importance: {ctx.get('importance_scores')}")
```

## Configuration

### TOML Configuration

Create or edit `codeweaver.toml`:

```toml
[chunker]
# Minimum importance score for semantic nodes (0.0-1.0)
semantic_importance_threshold = 0.3

[chunker.performance]
# Maximum file size to chunk (MB)
max_file_size_mb = 10

# Maximum time per file (seconds)
chunk_timeout_seconds = 30

# Maximum chunks per file
max_chunks_per_file = 5000

# Maximum AST nesting depth
max_ast_depth = 200

# Parse timeout (seconds)
parse_timeout_seconds = 10

# Memory limit per operation (MB)
max_memory_mb_per_operation = 100

[chunker.concurrency]
# Maximum files to process in parallel
max_parallel_files = 4

# Use process pool for parallelism (vs thread pool)
use_process_pool = true
```

### Programmatic Configuration

```python
from codeweaver.config.settings import CodeWeaverSettings, ChunkerSettings, PerformanceSettings

# Create custom settings
settings = CodeWeaverSettings(
    chunker=ChunkerSettings(
        semantic_importance_threshold=0.4,
        performance=PerformanceSettings(
            max_file_size_mb=15,
            chunk_timeout_seconds=45,
        )
    )
)

# Use custom settings
governor = ChunkGovernor(settings.chunker.performance)
```

## Error Handling

### Common Exceptions

```python
from codeweaver.engine.chunker.exceptions import (
    ParseError,
    ChunkingTimeoutError,
    BinaryFileError,
    ASTDepthExceededError,
    ChunkLimitExceededError,
    OversizedChunkError,
)

def safe_chunk(file_path: Path) -> list[CodeChunk]:
    """Chunk with comprehensive error handling."""
    try:
        chunks = chunk_single_file(file_path)
        return chunks

    except ParseError as e:
        print(f"Parse error: {e.message}")
        print(f"Suggestions: {', '.join(e.suggestions)}")
        # System will automatically fall back to delimiter chunker

    except ChunkingTimeoutError as e:
        print(f"Timeout after {e.elapsed_seconds}s (limit: {e.timeout_seconds}s)")
        print(f"File: {e.file_path}")
        # Consider excluding from indexing

    except BinaryFileError as e:
        print(f"Binary file detected: {e.file_path}")
        # Skip binary files

    except ASTDepthExceededError as e:
        print(f"AST depth {e.actual_depth} exceeds limit {e.max_depth}")
        # Generated or obfuscated code

    except ChunkLimitExceededError as e:
        print(f"Generated {e.chunk_count} chunks (limit: {e.max_chunks})")
        # File too complex

    except OversizedChunkError as e:
        print(f"Chunk {e.actual_tokens} tokens exceeds {e.max_tokens}")
        # Cannot reduce further

    return []
```

### Graceful Degradation

The system automatically degrades through these strategies:

```
1. SemanticChunker (AST-based, best quality)
   ↓ (on parse error)
2. DelimiterChunker (pattern-based, good quality)
   ↓ (on no matches)
3. Generic Delimiters (basic quality, universal)
   ↓ (last resort)
4. Single chunk (may exceed limits)
```

```python
# The selector handles degradation automatically
chunker = selector.select_for_file(discovered_file)
chunks = chunker.chunk(content, file_path=file_path)
# Will try semantic → delimiter → generic automatically
```

## Performance Optimization

### Performance Targets

Based on architecture spec §6.1:

- **Typical files** (100-1000 lines): 100-500 files/second
- **Large files** (1000-5000 lines): 50-200 files/second
- **Very large files** (5000+ lines): 10-50 files/second
- **Memory usage**: <100MB per operation

### Optimization Tips

#### 1. Adjust Importance Threshold

```python
# Lower threshold = more chunks (slower but more complete)
settings.chunker.semantic_importance_threshold = 0.2

# Higher threshold = fewer chunks (faster but may miss content)
settings.chunker.semantic_importance_threshold = 0.5
```

#### 2. Increase Timeouts for Large Files

```python
# Increase timeout for very large codebases
settings.chunker.performance.chunk_timeout_seconds = 60
settings.chunker.performance.parse_timeout_seconds = 20
```

#### 3. Use Parallel Processing

```python
from codeweaver.engine.chunker.parallel import chunk_files_parallel

# Process multiple files in parallel
files = [DiscoveredFile(path=p) for p in file_paths]
results = list(chunk_files_parallel(files, governor, max_workers=8))
```

#### 4. Profile Performance

```python
import time

start = time.perf_counter()
chunks = chunker.chunk(content, file_path=file_path)
elapsed = time.perf_counter() - start

print(f"Chunked {len(chunks)} chunks in {elapsed*1000:.2f}ms")
print(f"Rate: {len(chunks)/elapsed:.1f} chunks/second")
```

## Parallel Processing

### Thread-Based Parallel Processing

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def chunk_files_parallel_threads(file_paths: list[Path], max_workers: int = 4):
    """Chunk files in parallel using threads."""
    settings = get_settings()
    governor = ChunkGovernor(settings.chunker.performance)
    selector = ChunkerSelector(governor)

    def chunk_file(file_path: Path):
        content = file_path.read_text()
        discovered_file = DiscoveredFile(path=file_path)
        chunker = selector.select_for_file(discovered_file)
        return file_path, chunker.chunk(content, file_path=file_path)

    results = {}
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {executor.submit(chunk_file, p): p for p in file_paths}

        for future in as_completed(futures):
            try:
                file_path, chunks = future.result()
                results[file_path] = chunks
            except Exception as e:
                print(f"Error: {e}")

    return results
```

### Process-Based Parallel Processing

```python
from codeweaver.engine.chunker.parallel import chunk_files_parallel

# Built-in parallel processing (uses ProcessPoolExecutor)
files = [DiscoveredFile(path=p) for p in file_paths]
for file_path, chunks in chunk_files_parallel(files, governor, max_workers=4):
    print(f"{file_path}: {len(chunks)} chunks")
```

### Choosing Thread vs Process Pool

- **Thread Pool**: Good for I/O-bound operations, shared memory
- **Process Pool**: Better for CPU-bound chunking, bypasses GIL, isolated memory

Recommendation: Use **process pool** for large-scale chunking operations.

## Troubleshooting

### Issue: Chunking Too Slow

**Symptoms**: Processing takes longer than expected

**Solutions**:
1. Check file size - ensure files are under recommended limits
2. Increase timeout settings
3. Profile to identify bottlenecks
4. Use parallel processing
5. Adjust importance threshold to reduce chunk count

```python
# Profile slow operations
import cProfile
import pstats

profiler = cProfile.Profile()
profiler.enable()

chunks = chunker.chunk(content, file_path=file_path)

profiler.disable()
stats = pstats.Stats(profiler)
stats.sort_stats('cumulative')
stats.print_stats(20)  # Top 20 slowest functions
```

### Issue: Out of Memory

**Symptoms**: Process crashes with memory error

**Solutions**:
1. Process files in smaller batches
2. Reduce max parallel workers
3. Check for memory leaks in custom code
4. Increase system memory limits

```python
# Process in smaller batches
batch_size = 10
for i in range(0, len(file_paths), batch_size):
    batch = file_paths[i:i+batch_size]
    results = chunk_multiple_files(batch)
    # Process results before next batch
```

### Issue: Too Many/Few Chunks

**Symptoms**: Unexpected chunk count

**Solutions**:
1. Adjust semantic importance threshold
2. Check delimiter patterns for the language
3. Inspect metadata to understand chunking decisions
4. Consider file structure and complexity

```python
# Debug chunk generation
for chunk in chunks:
    ctx = chunk.metadata.get("context", {})
    print(f"Classification: {ctx.get('classification')}")
    print(f"Kind: {ctx.get('kind')}")
    print(f"Importance: {ctx.get('importance_scores')}")
```

### Issue: Parse Errors

**Symptoms**: Frequent ParseError exceptions

**Solutions**:
1. Verify file encoding (should be UTF-8)
2. Check for syntax errors in source files
3. Update tree-sitter grammars if outdated
4. System will auto-fallback to delimiter chunking

```python
# Explicitly handle parse errors
try:
    chunks = semantic_chunker.chunk(content, file_path=file_path)
except ParseError:
    # Fallback to delimiter
    delimiter_chunker = DelimiterChunker(governor, "python")
    chunks = delimiter_chunker.chunk(content, file_path=file_path)
```

### Issue: Binary File Errors

**Symptoms**: BinaryFileError raised unexpectedly

**Solutions**:
1. Update file discovery patterns to exclude binary extensions
2. Verify files are actually text-based
3. Check file encoding

```python
# Filter out binary files before chunking
def is_text_file(file_path: Path) -> bool:
    """Check if file appears to be text."""
    try:
        with open(file_path, 'rb') as f:
            chunk = f.read(1024)
            return b'\x00' not in chunk
    except Exception:
        return False

text_files = [f for f in file_paths if is_text_file(f)]
```

## Advanced Usage

### Custom Delimiter Patterns

```python
from codeweaver.engine.chunker.delimiter_model import Delimiter, DelimiterKind

# Define custom delimiters
custom_delimiters = [
    Delimiter(
        start="<!-- START -->",
        end="<!-- END -->",
        kind=DelimiterKind.BLOCK,
        priority=10,
        inclusive=True,
        take_whole_lines=True,
        nestable=False,
    )
]

# Use in chunker
delimiter_chunker = DelimiterChunker(governor, "custom")
delimiter_chunker.delimiters = custom_delimiters
```

### Batch ID Tracking

```python
# Chunks are deduplicated within batches
from codeweaver.common.utils import uuid7

batch_id = uuid7()
chunks = chunker.chunk(content, file_path=file_path)

# All chunks share same batch_id
for chunk in chunks:
    chunk.set_batch_id(batch_id)
```

### Integration with Statistics

```python
from codeweaver.common.statistics import get_session_statistics

# Statistics are tracked automatically
statistics = get_session_statistics()

# After chunking operations
for ext_kind, stats in statistics.file_operations_by_extkind.items():
    print(f"{ext_kind}: {len(stats)} operations")
```

## Best Practices

1. **Always use resource governance**: The `ChunkGovernor` prevents runaway operations
2. **Handle exceptions gracefully**: Let the system degrade automatically
3. **Monitor performance**: Track metrics for optimization opportunities
4. **Use parallel processing**: For batch operations on large codebases
5. **Configure appropriately**: Adjust settings based on your codebase characteristics
6. **Inspect metadata**: Rich metadata enables better AI understanding
7. **Test with real files**: Validate chunking quality with actual code samples

## Additional Resources

- [Architecture Specification](../claudedocs/chunker-architecture-spec.md)
- [API Reference](./api/chunker.md)
- [Performance Benchmarks](../tests/benchmark/chunker/test_performance.py)
- [Integration Tests](../tests/integration/chunker/test_e2e.py)
