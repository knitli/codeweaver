<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Server Indexing Timeout Investigation

## Problem Statement
Test `test_indexing_completes_successfully` fails with:
```
AssertionError: Indexing took 763.37s, expected <120s
```

## Analysis

### Test Code Review
From `tests/integration/test_server_indexing.py:207-236`:

```python
async def test_indexing_completes_successfully(indexer: Indexer, test_project_path: Path):
    """T009: Indexing completes for small test project."""
    # Run indexing
    discovered_count = indexer.prime_index(force_reindex=True)

    # Allow time for async indexing to complete
    await asyncio.sleep(2)  # Only 2 seconds wait!

    # Check completion time
    duration = stats.elapsed_time  # THIS is the problem
    assert duration < 120, f"Indexing took {duration}s, expected <120s"
```

### Root Cause Identified

**The Issue**: `stats.elapsed_time` measures from `IndexingStats` instantiation (line 108 in indexer.py):
```python
start_time: float = time.time()  # Set at object creation
```

But `IndexingStats` is created in `Indexer.__init__()` (line 401), which happens during the pytest fixture setup, **not** when `prime_index()` is called!

**Timeline**:
1. **Test setup phase**: `Indexer.__init__()` → `IndexingStats()` created → `start_time = time.time()`
2. **Pytest runs all 350 tests before this test** (we're test #147)
3. **This test runs**: `prime_index()` → `await asyncio.sleep(2)` → check `elapsed_time`
4. **Result**: `elapsed_time` includes entire pytest session duration before this test!

### Evidence
From test output:
- Test runs at position 147 of 350 tests
- Many tests run before this one (benchmark, contract, integration tests)
- Total pytest session likely takes 120+ seconds before reaching this test
- Observed failure: 763.37 seconds = ~12.7 minutes of accumulated test runtime

### Workload Being Indexed
From test fixture (lines 30-112):
- **5 small files**: auth.py, database.py, test_auth.py, README.md, .gitignore
- **Total ~100 lines of code**
- **Expected chunks**: ~10-15 chunks
- **Realistic indexing time**: <5 seconds for this tiny project

### Why 120s Threshold is Actually Reasonable
The 120-second threshold was set for this small test project and is completely appropriate:
- Small project should index in 2-5 seconds
- 120s provides 24-60x safety margin
- The problem is NOT the threshold, it's the measurement bug

## Constitutional Compliance Review

### Evidence-Based Development ✅
- Root cause identified through code analysis
- Timeline verified against test output
- No assumptions about performance without measurement

### Testing Philosophy ✅
- Test focuses on critical user-affecting behavior (indexing completion)
- Integration test validates realistic workflow
- Issue is implementation bug, not test design flaw

## Solution Options

### Option A: Fix Timing Measurement (RECOMMENDED)
Reset `start_time` when `prime_index()` is called:

```python
def prime_index(self, *, force_reindex: bool = False) -> int:
    # Reset stats for new indexing run
    self._stats = IndexingStats()  # Already does this!
    # ... rest of method
```

**Analysis**: Line 695 already resets stats! The fixture is reusing the same indexer across tests, causing stats to accumulate.

### Option B: Fresh Indexer Per Test
Modify fixture scope from module to function:

```python
@pytest.fixture  # Remove scope="module" if present
def indexer(test_project_path: Path) -> Indexer:
    return Indexer(project_root=test_project_path, auto_initialize_providers=True)
```

### Option C: Explicit Timing Capture
Measure indexing duration directly in test:

```python
start = time.time()
discovered_count = indexer.prime_index(force_reindex=True)
await asyncio.sleep(2)
duration = time.time() - start
assert duration < 120
```

## Recommendation: Option A + Fixture Verification

### Why Option A?
1. **Most accurate**: Measures actual indexing duration
2. **Minimal change**: Code at line 695 already correct
3. **Root cause fix**: Addresses measurement bug, not symptom
4. **Constitutional alignment**: Evidence-based solution

### Implementation
Verify fixture scope and ensure stats reset works correctly.

## Performance Expectations (For Reference)

For this test workload (5 files, ~100 lines):
- **File discovery**: <100ms
- **Chunking**: <500ms (5 files * 100ms avg)
- **Embedding**: <1000ms (if providers configured)
- **Vector store**: <500ms (if configured)
- **Total expected**: <2 seconds realistic, <5 seconds conservative
- **120s threshold**: Provides 24-60x safety margin ✅

## Environment Factors (Non-Issues)
- WSL performance: Not relevant for this tiny workload
- CI variability: 120s margin handles this
- Provider availability: Test handles gracefully (no providers = skip phases)

## Conclusion
The 120-second threshold is **completely appropriate**. The failure was caused by a timing measurement bug where `stats.elapsed_time` accumulated across instances due to a Python dataclass default value evaluation timing issue.

## Root Cause: Python Dataclass Gotcha

### The Bug
In `src/codeweaver/engine/indexer.py` line 108:

```python
@dataclass
class IndexingStats:
    start_time: float = time.time()  # ❌ EVALUATED ONCE AT CLASS DEFINITION!
```

**Problem**: Default values in dataclasses are evaluated **once at class definition time**, not at instance creation time. This means:
1. Python loads the module
2. `time.time()` is called ONCE
3. ALL `IndexingStats` instances share that same timestamp forever!

### Verification
Debug script showed:
```
Before prime_index, stats object id: 125772745079648
Before prime_index, stats.start_time: 1762289754.902095
After prime_index, stats object id: 125772745152848  ← NEW OBJECT
After prime_index, stats.start_time: 1762289754.902095  ← SAME TIMESTAMP!
```

### The Fix
Use `field(default_factory=...)` to evaluate at instance creation:

```python
from dataclasses import field

@dataclass
class IndexingStats:
    start_time: float = field(default_factory=time.time)  # ✅ EVALUATED PER INSTANCE
```

## Implementation

**File Modified**: `/home/knitli/codeweaver-mcp/src/codeweaver/engine/indexer.py`

**Changes**:
1. Added `import dataclasses` (line 17)
2. Changed line 108 from `start_time: float = time.time()` to `start_time: float = dataclasses.field(default_factory=time.time)`

**Test Results**:
- `test_indexing_completes_successfully`: **PASSED** in 6.02s ✅
- All 7 tests in `test_server_indexing.py`: **PASSED** in 16.50s ✅

## Constitutional Compliance ✅

### Evidence-Based Development
- Root cause identified through systematic debugging
- Bug verified with minimal reproduction test
- Fix validated with both debug script and actual tests

### Testing Philosophy
- Test focuses on critical user-affecting behavior (indexing completion)
- Integration test validates realistic workflow
- Fix addresses root cause, not symptom

### Quality Standards
- No linting errors introduced
- All tests pass
- Code adheres to project conventions

## Performance Characteristics (Actual)

From debug script with fix:
- **Indexer creation**: 0.30s
- **Actual indexing**: 1.19s
- **Total with 2s async wait**: 3.24s
- **120s threshold**: Provides **37x safety margin** ✅

## Lessons Learned

**Python Dataclass Pitfall**: When using mutable default values or dynamic values (like timestamps), ALWAYS use `field(default_factory=...)` instead of direct assignment. This is similar to the classic "mutable default argument" gotcha but affects dataclass fields.

**Debugging Approach**: Object identity checks (`id()`) revealed that new objects were being created but shared the same timestamp, leading to the discovery of the class-level evaluation issue.
