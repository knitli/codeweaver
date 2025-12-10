<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Chunker Structured Logging Integration Plan

## Executive Summary

Integrate the existing `_logging.py` module into the chunker subsystem to provide comprehensive observability for chunking operations. Currently, the chunker has ad-hoc logging scattered throughout - this plan consolidates it into a structured, consistent, and observable system.

## Current State Analysis

### What Exists
- ✅ `src/codeweaver/engine/chunker/_logging.py` - Complete implementation with 8 event types
- ⚠️ Ad-hoc logging in semantic.py, delimiter.py, parallel.py
- ⚠️ One structured log call exists: `_track_chunk_metrics()` in [semantic.py:874](../src/codeweaver/engine/chunker/semantic.py#L874)
- ❌ No logging for fallbacks, edge cases, performance issues, resource limits, deduplication

### Observability Gaps

| Event Type | Current | Impact | Fix Location |
|------------|---------|---------|--------------|
| **chunking_completed** | Ad-hoc in semantic.py:874 | Incomplete metrics | Standardize across both chunkers |
| **chunking_failed** | Ad-hoc error logs | No structured error tracking | Add to exception handlers |
| **chunking_fallback** | Not logged | Blind to semantic→delimiter fallback | parallel.py:90, semantic.py:730 |
| **chunking_edge_case** | Not logged | Don't know edge case frequency | semantic.py:380, 396, 424 |
| **chunking_performance_warning** | Not logged | No slow operation alerts | Add threshold checks |
| **chunking_resource_limit** | Not logged | Timeout/limit violations invisible | governance.py integration |
| **chunking_deduplication** | Not logged | Unknown dedup effectiveness | semantic.py:849-862 |

## Integration Strategy

### Phase 1: Replace Existing Structured Logging (Low Risk)
**Goal**: Replace the one existing structured log with standardized version

**File**: `src/codeweaver/engine/chunker/semantic.py`

**Changes**:
```python
# BEFORE (line 864-884):
def _track_chunk_metrics(self, chunks: list[CodeChunk], duration: float) -> None:
    logger.info(
        "chunking_completed",
        extra={
            "chunk_count": len(chunks),
            "duration_ms": duration * 1000,
            "chunker_type": "semantic",
            "avg_chunk_size": sum(len(c.content) for c in chunks) / len(chunks) if chunks else 0,
        },
    )

# AFTER:
from codeweaver.engine.chunker import _logging as chunker_logging

def _track_chunk_metrics(
    self,
    chunks: list[CodeChunk],
    duration: float,
    file_path: Path | None = None,
    file_size_bytes: int = 0,
    language: str = "unknown"
) -> None:
    chunker_logging.log_chunking_completed(
        file_path=file_path or Path("<unknown>"),
        chunker_type=self,
        chunk_count=len(chunks),
        duration_ms=duration * 1000,
        file_size_bytes=file_size_bytes,
        language=language,
    )
```

**Impact**: Minimal - replaces existing structured log with standardized version

---

### Phase 2: Add Edge Case Logging (Low Risk)
**Goal**: Make edge case handling visible

**File**: `src/codeweaver/engine/chunker/semantic.py`

**Locations**:
1. **Empty file** - [semantic.py:380](../src/codeweaver/engine/chunker/semantic.py#L380)
2. **Whitespace only** - [semantic.py:396](../src/codeweaver/engine/chunker/semantic.py#L396)
3. **Single line** - [semantic.py:424](../src/codeweaver/engine/chunker/semantic.py#L424)

**Example Change** (line 380):
```python
# BEFORE:
if not content:
    logger.info("Empty file: %s, returning no chunks", file_path)
    return []

# AFTER:
if not content:
    chunker_logging.log_chunking_edge_case(
        file_path=file_path,
        edge_case_type="empty_file",
        chunk_count=0,
    )
    return []
```

**Impact**: Enables tracking of how often edge cases occur without changing behavior

---

### Phase 3: Add Fallback Logging (Medium Value)
**Goal**: Track when semantic chunking fails and delimiter fallback is used

**Files**:
1. `src/codeweaver/engine/chunker/parallel.py` - [line 90](../src/codeweaver/engine/chunker/parallel.py#L90)
2. `src/codeweaver/engine/chunker/semantic.py` - [line 730](../src/codeweaver/engine/chunker/semantic.py#L730)

**Example Change 1** - parallel.py (external fallback):
```python
# BEFORE (line 90-105):
# Graceful fallback to delimiter chunking for parse errors
except ParseError as e:
    # ... existing code ...
    fallback_chunker = DelimiterChunker(governor, language=language)
    chunks = fallback_chunker.chunk(content, file=file)

# AFTER:
except ParseError as e:
    # Create delimiter chunker as fallback
    fallback_chunker = DelimiterChunker(governor, language=language)

    # Log fallback event
    chunker_logging.log_chunking_fallback(
        file_path=file.path,
        from_chunker=chunker,  # SemanticChunker instance
        to_chunker=fallback_chunker,
        reason="parse_error",
        extra_context={"error": str(e)},
    )

    chunks = fallback_chunker.chunk(content, file=file)
```

**Example Change 2** - semantic.py (internal fallback):
```python
# BEFORE (line 724-730):
# Fallback: Use delimiter chunker to split oversized node text
logger.info(
    "Oversized node without chunkable children: %s, falling back to delimiter chunker",
    node.name,
)

# AFTER:
# Fallback: Use delimiter chunker to split oversized node text
from codeweaver.engine.chunker.delimiter import DelimiterChunker
delimiter_chunker = DelimiterChunker(self.governor)

chunker_logging.log_chunking_fallback(
    file_path=Path("<unknown>"),  # node chunking doesn't have file context
    from_chunker=self,
    to_chunker=delimiter_chunker,
    reason="oversized_chunk",
    extra_context={"node_name": node.name},
)
```

**Impact**: **HIGH VALUE** - Reveals when semantic parsing is struggling, helps tune importance thresholds

---

### Phase 4: Add Deduplication Logging (Medium Value)
**Goal**: Track deduplication effectiveness

**File**: `src/codeweaver/engine/chunker/semantic.py`

**Location**: [line 849-862](../src/codeweaver/engine/chunker/semantic.py#L849-L862) - After deduplication loop

**Change**:
```python
# AFTER the deduplicated list is built (line 862):
def _deduplicate_chunks(self, chunks: list[CodeChunk]) -> list[CodeChunk]:
    """Deduplicate chunks based on content hash."""
    # ... existing dedup logic ...

    # Log deduplication statistics
    if len(chunks) > len(deduplicated):
        chunker_logging.log_chunking_deduplication(
            file_path=Path("<batch>"),  # batch-level dedup doesn't have single file
            total_chunks=len(chunks),
            duplicate_chunks=len(chunks) - len(deduplicated),
            unique_chunks=len(deduplicated),
        )

    return deduplicated
```

**Impact**: Shows how effective deduplication is across codebase

---

### Phase 5: Add Error Logging (High Value)
**Goal**: Structured error tracking for debugging

**File**: `src/codeweaver/engine/chunker/semantic.py`

**Location**: [line 502-505](../src/codeweaver/engine/chunker/semantic.py#L502-L505) - Exception handler

**Change**:
```python
# BEFORE (line 502-505):
except Exception as e:
    logger.warning("Failed to parse %s", file_path or "content", exc_info=True)
    raise_parse_error(
        f"Failed to parse {file_path or 'content'}",
        original_error=e,
        file_path=file_path,
    )

# AFTER:
except Exception as e:
    chunker_logging.log_chunking_failed(
        file_path=file_path or Path("<unknown>"),
        chunker_type=self,
        error_type=type(e).__name__,
        error_message=str(e),
        fallback_triggered=False,  # Will be triggered by caller
    )
    raise_parse_error(
        f"Failed to parse {file_path or 'content'}",
        original_error=e,
        file_path=file_path,
    )
```

**Impact**: Better error tracking and debugging

---

### Phase 6: Add Performance Warning Logging (Medium Value)
**Goal**: Alert on slow chunking operations

**Files**: Both `semantic.py` and `delimiter.py`

**Location**: At end of chunking operations, after duration calculation

**Change**:
```python
# Add to both chunkers after chunking completes:
PERFORMANCE_THRESHOLD_MS = 1000  # 1 second

if duration_ms > PERFORMANCE_THRESHOLD_MS:
    chunker_logging.log_chunking_performance_warning(
        file_path=file_path,
        chunker_type=self,
        duration_ms=duration_ms,
        threshold_ms=PERFORMANCE_THRESHOLD_MS,
        extra_context={"file_size_bytes": file_size_bytes},
    )
```

**Impact**: Identify performance bottlenecks in production

---

### Phase 7: Add Resource Limit Logging (High Value)
**Goal**: Track timeout and limit violations

**File**: `src/codeweaver/engine/chunker/governance.py`

**Locations**:
1. Timeout check failures
2. Chunk limit exceeded

**Change Example**:
```python
# In ResourceGovernor.check_timeout():
def check_timeout(self) -> None:
    if self.is_timeout():
        from codeweaver.engine.chunker import _logging as chunker_logging

        chunker_logging.log_chunking_resource_limit(
            file_path=Path("<governed>"),
            limit_type="timeout",
            limit_value=self._settings.chunk_timeout_seconds,
            actual_value=(datetime.now(UTC) - self._start_time).total_seconds(),
        )

        raise ChunkingTimeoutError(...)
```

**Impact**: **CRITICAL** - Understand resource pressure and tune limits

---

## Implementation Sequence

### Recommended Order (by value/risk ratio):
1. ✅ **Phase 1** - Replace existing (low risk, alignment)
2. ✅ **Phase 7** - Resource limits (high value, critical visibility)
3. ✅ **Phase 3** - Fallback logging (high value, debugging gold)
4. ✅ **Phase 5** - Error logging (high value, debugging)
5. ✅ **Phase 2** - Edge cases (low risk, completeness)
6. ✅ **Phase 4** - Deduplication (medium value, optimization insight)
7. ✅ **Phase 6** - Performance warnings (medium value, nice-to-have)

### Alternative: Quick Win Sequence (fastest value):
1. **Phase 3** - Fallback logging (immediately reveals when semantic fails)
2. **Phase 7** - Resource limits (immediately shows resource pressure)
3. **Phase 5** - Error logging (better debugging)
4. Rest as needed

## Testing Strategy

### Unit Tests
Add tests to verify logging calls are made:
```python
def test_fallback_logging(mocker):
    """Verify fallback events are logged."""
    mock_log = mocker.patch("codeweaver.engine.chunker._logging.log_chunking_fallback")

    # Trigger fallback scenario
    chunker = SemanticChunker(...)
    # ... trigger parse error ...

    assert mock_log.called
    assert mock_log.call_args[1]["reason"] == "parse_error"
```

### Integration Tests
Verify structured logs appear in output:
```python
def test_structured_logging_output(caplog):
    """Verify structured logging produces correct extra fields."""
    with caplog.at_level(logging.INFO):
        chunker = SemanticChunker(...)
        chunks = chunker.chunk(content, file=file)

    # Find chunking_completed log
    records = [r for r in caplog.records if r.extra.get("event") == "chunking_completed"]
    assert len(records) == 1
    assert records[0].extra["chunk_count"] == expected_count
```

## Migration Checklist

- [ ] Phase 1: Update `_track_chunk_metrics()` in semantic.py
- [ ] Phase 1: Add same to delimiter.py (create equivalent method)
- [ ] Phase 2: Add edge case logging (3 locations in semantic.py)
- [ ] Phase 3: Add fallback logging in parallel.py
- [ ] Phase 3: Add fallback logging in semantic.py (oversized nodes)
- [ ] Phase 4: Add deduplication logging in semantic.py
- [ ] Phase 5: Add error logging in semantic.py exception handlers
- [ ] Phase 6: Add performance warnings (both chunkers)
- [ ] Phase 7: Add resource limit logging in governance.py
- [ ] Add unit tests for each logging call
- [ ] Add integration tests for structured log output
- [ ] Update documentation to reference new observability
- [ ] Add example queries for log analysis (e.g., Splunk/ELK queries)

## Expected Benefits

### Debugging
- See exactly when and why semantic chunking fails
- Track which files cause timeouts or resource issues
- Identify performance bottlenecks per file

### Optimization
- Measure deduplication effectiveness
- Tune importance thresholds based on fallback frequency
- Adjust resource limits based on actual usage

### Production Monitoring
- Alert on increasing fallback rates (code quality degradation?)
- Track edge case frequency changes
- Monitor chunking performance trends

### Metrics Dashboard Potential
```
Chunking Health Dashboard:
- Success rate: semantic vs delimiter
- Fallback frequency by language
- Average chunking duration
- Resource limit hit rate
- Deduplication effectiveness
- Edge case distribution
```

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Performance overhead from logging | Low | Logging is already present, just restructuring |
| Log volume increase | Medium | Use appropriate log levels (DEBUG for edge cases) |
| Breaking existing log parsers | Low | Existing logs are mostly ad-hoc, not parsed |
| Missing file_path context | Low | Use `Path("<unknown>")` fallback for safety |

## Questions to Answer

1. **Log Level Strategy**: Should edge cases be DEBUG or INFO?
   - Recommendation: DEBUG (happens frequently, low signal)

2. **Performance Threshold**: What's acceptable chunking time?
   - Recommendation: Start with 1000ms, tune based on data

3. **Dedup Logging**: Per-file or per-batch?
   - Current: Per-batch (dedup happens at batch level)

4. **Resource Limit Logging**: Include stack traces?
   - Recommendation: Yes for timeouts, helps debug slow code paths

## Future Enhancements

### Post-Integration Improvements
1. **Metrics Export**: Send structured logs to metrics system (Prometheus, etc.)
2. **Alerting**: Set up alerts for high fallback rates or resource exhaustion
3. **Performance Profiling**: Correlate logs with AST depth, file size
4. **Language Analysis**: Track success rates per programming language

### Potential New Events
- `chunking_cache_hit` - Track cache effectiveness (future)
- `chunking_batch_start/end` - Track batch operations
- `chunking_parallel_coordination` - Track parallel chunking orchestration

## References

- Architecture Spec §9.3 (referenced in [_logging.py:9](../src/codeweaver/engine/chunker/_logging.py#L9))
- Current ad-hoc logging: [semantic.py](../src/codeweaver/engine/chunker/semantic.py), [delimiter.py](../src/codeweaver/engine/chunker/delimiter.py), [parallel.py](../src/codeweaver/engine/chunker/parallel.py)
- Resource governance: [governance.py](../src/codeweaver/engine/chunker/governance.py)
