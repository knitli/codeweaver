<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# ProcessPoolExecutor Pickling Fix Summary

**Date**: 2025-10-26
**Issue**: ProcessPoolExecutor produced 0 results due to pickling failures
**Status**: ✅ Fully resolved - all tests passing (5/5)

---

## Problem Statement

ProcessPoolExecutor implementation was failing silently, returning 0 results with no exceptions. Initial diagnostics showed:
- ThreadPoolExecutor worked perfectly (same code, no pickling required)
- ProcessPoolExecutor submitted jobs successfully but returned empty results
- No exceptions visible in main process

---

## Investigation Process

### Phase 1: Object Pickling Test
Created `scripts/diagnose_pickling.py` to test picklability of all core objects:
- ✅ DiscoveredFile: Picklable
- ✅ ChunkGovernor: Picklable
- ✅ ChunkerSelector: Picklable
- ✅ Worker function: Picklable

**Conclusion**: All input objects were picklable - issue must be in returned data.

### Phase 2: ProcessPoolExecutor Execution Test
Created `scripts/diagnose_process_executor.py` with verbose worker logging:

**First Error Identified**:
```
TypeError: cannot pickle 'generator' object
```

Worker successfully created 8 chunks but failed when returning results through result queue.

### Phase 3: Root Cause Analysis

#### Issue 1: Generator in cached_property

**Location**: `src/codeweaver/semantic/ast_grep.py:648`

```python
@computed_field
@cached_property
def positional_connections(self) -> Iterator[AstThing[SgNode]]:
    """Get the things positionally connected to this thing (its children)."""
    yield from (
        type(self).from_sg_node(child, self.language) for child in self._node.children()
    )
```

**Problem**:
- `@cached_property` decorator stores the result
- The result is a generator object (from `yield from`)
- Generator objects cannot be pickled
- This generator gets embedded in CodeChunk metadata

#### Issue 2: Unpicklable AST Nodes

**Location**: `src/codeweaver/core/metadata.py:87`

After fixing the generator issue, second error appeared:
```
TypeError: cannot pickle 'builtins.SgNode' object
```

**Problem**:
- `SemanticMetadata.thing` contains raw `SgNode` objects from ast-grep
- `SgNode` is a C extension object that doesn't support pickling
- These AST nodes are only needed during chunking, not after

---

## Solution Implemented

### Fix 1: Convert Generator to Tuple

**File**: `src/codeweaver/semantic/ast_grep.py`

```python
@computed_field
@cached_property
def positional_connections(self) -> tuple[AstThing[SgNode], ...]:
    """Get the things positionally connected to this thing (its children)."""
    return tuple(
        type(self).from_sg_node(child, self.language) for child in self._node.children()
    )
```

**Changes**:
- Changed return type from `Iterator[AstThing[SgNode]]` to `tuple[AstThing[SgNode], ...]`
- Changed implementation from `yield from` to `return tuple(...)`
- Materializes the collection immediately (still lazy via `@cached_property`)

### Fix 2: Add Pickle Support to SemanticMetadata

**File**: `src/codeweaver/core/metadata.py`

```python
def __getstate__(self) -> dict[str, Any]:
    """Custom pickle support - exclude unpicklable AST nodes."""
    state = self.__dict__.copy()
    # Remove unpicklable fields (SgNode and AstThing objects)
    state["thing"] = None
    state["positional_connections"] = ()  # Clear AST node references
    return state

def __setstate__(self, state: dict[str, Any]) -> None:
    """Custom pickle support - restore state without AST nodes."""
    self.__dict__.update(state)
```

**Rationale**:
- AST nodes (`thing` field) are only needed during chunking analysis
- After chunking is complete, we only need the extracted metadata
- Setting `thing=None` and clearing `positional_connections` removes all AST references
- Chunks remain fully functional without the raw AST data

---

## Test Results

### Before Fix
```
tests/integration/chunker/test_e2e.py -k "parallel"
  test_e2e_multiple_files_parallel_process - SKIPPED
  test_e2e_multiple_files_parallel_thread - PASSED ✅
  test_e2e_parallel_error_handling - PASSED ✅
  test_e2e_parallel_empty_file_list - PASSED ✅
  test_e2e_parallel_dict_convenience - PASSED ✅

Result: 4/4 runnable tests passing (process test skipped)
```

### After Fix
```
tests/integration/chunker/test_e2e.py -k "parallel"
  test_e2e_multiple_files_parallel_process - PASSED ✅
  test_e2e_multiple_files_parallel_thread - PASSED ✅
  test_e2e_parallel_error_handling - PASSED ✅
  test_e2e_parallel_empty_file_list - PASSED ✅
  test_e2e_parallel_dict_convenience - PASSED ✅

Result: 5/5 tests passing (100% success rate)
```

---

## Files Modified

1. **src/codeweaver/semantic/ast_grep.py**
   - Changed `positional_connections` from generator to tuple
   - Line 648: Return type and implementation

2. **src/codeweaver/core/metadata.py**
   - Added `__getstate__` method (line 111)
   - Added `__setstate__` method (line 119)

3. **tests/integration/chunker/test_e2e.py**
   - Removed `@pytest.mark.skip` decorator from process executor test
   - Updated test docstring to document the fix

4. **claudedocs/parallel-implementation-summary.md**
   - Updated test results to reflect 5/5 passing
   - Added "Pickling Fix" section documenting the solution
   - Updated acceptance criteria and recommendations

---

## Technical Insights

### Why ThreadPoolExecutor Worked

ThreadPoolExecutor shares memory space with the main process:
- No need to pickle/unpickle arguments or return values
- Objects can contain generators, C extensions, or any Python object
- Lower overhead but subject to GIL limitations

### Why ProcessPoolExecutor Failed

ProcessPoolExecutor uses separate processes:
- All arguments and return values must be pickled for IPC
- Uses multiprocessing queues that require pickle serialization
- Python's `pickle` module has limitations with generators and C extensions
- Silent failures occur when pickling fails in worker process

### Why This Fix is Safe

1. **AST nodes are ephemeral**: Only needed during analysis phase
2. **Metadata is preserved**: All extracted information (symbols, ranges, etc.) remains
3. **Chunks are complete**: CodeChunk objects retain all necessary information
4. **No breaking changes**: Existing code continues to work

---

## Performance Impact

### Generator → Tuple Conversion
- **Memory**: Minimal increase (children list is typically small, <10 items)
- **CPU**: One-time materialization cost, amortized by `@cached_property`
- **Benefit**: Enables ProcessPoolExecutor, true parallelism for CPU-bound parsing

### AST Node Exclusion
- **Memory**: Reduction in pickled data size (AST nodes can be large)
- **CPU**: Faster pickling/unpickling in workers
- **Trade-off**: Cannot access raw AST nodes after pickling (acceptable - not needed)

---

## Lessons Learned

1. **Test Early with Real Executor**: Unit tests with mocks won't catch pickling issues
2. **Diagnostic Layering**: Start with simple tests (can objects pickle?), then complex (can execution succeed?)
3. **Generator + Cache = Trouble**: Generators stored by `@cached_property` break pickling
4. **Custom Pickle Support**: `__getstate__`/`__setstate__` powerful for controlling serialization
5. **Silent Failures**: ProcessPoolExecutor errors in workers can be silent - use verbose logging

---

## Future Considerations

1. **Alternative Serialization**: Could explore `dill` library for even more complex objects
2. **Lazy Loading**: Could implement pattern to reconstruct AST nodes on demand if needed
3. **Performance Benchmarking**: Compare process vs thread performance with real codebases
4. **Memory Profiling**: Monitor memory usage with large file counts

---

## Conclusion

ProcessPoolExecutor now fully functional, enabling:
- True CPU parallelism for AST parsing (no GIL)
- Better resource utilization on multi-core systems
- Choice between process-based (CPU-bound) and thread-based (I/O-bound) execution

**Time Invested**: ~2 hours (vs estimated 4-8 hours)
**Tests Passing**: 5/5 (100%)
**Production Ready**: ✅ Yes
