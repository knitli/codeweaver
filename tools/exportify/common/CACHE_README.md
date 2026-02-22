<!--
SPDX-FileCopyrightText: 2026 Knitli Inc.

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Analysis Cache Implementation

## Overview

The Analysis Cache provides persistent caching of file analysis results for the lazy import system, using SHA-256 hash-based validation to ensure cache correctness.

## Features

### ✅ Hash-Based Validation
- SHA-256 hashing of file content for cache key validation
- Automatic invalidation when file content changes
- Protection against stale cache entries

### ✅ JSON Persistence
- Atomic writes using temp file + rename pattern
- Schema versioning for cache invalidation on structure changes
- Stored at `tools/.codeweaver/exportify_cache.json`

### ✅ Circuit Breaker Pattern
- Automatically disables cache after 5 consecutive failures
- Prevents cascading failures
- Auto-reset after 300 seconds (configurable)

### ✅ Graceful Error Handling
- **FM-001**: Corrupt JSON → Auto-delete and rebuild
- **FM-008**: Repeated failures → Circuit breaker disables cache
- **FM-013**: Disk full → Warn and disable cache

### ✅ Performance Optimized
- Target: <50ms per file operation (REQ-PERF-004)
- Target: >90% hit rate across runs (REQ-PERF-002)
- In-memory cache data for fast lookups
- Chunked file reading for large files

## API

### Basic Operations

```python
from codeweaver.tools.exportify.common.cache import AnalysisCache

# Initialize cache
cache = AnalysisCache()  # Uses .codeweaver/ by default
# or
cache = AnalysisCache(cache_dir=Path("/custom/path"))

# Get cached analysis (returns None if not found/invalid)
analysis = cache.get(file_path)

# Cache analysis result
cache.set(file_path, analysis_result)

# Invalidate specific entry
cache.invalidate(file_path)

# Clear entire cache
cache.clear()

# Get statistics
stats = cache.get_statistics()
print(f"Hit rate: {stats.hit_rate:.2%}")
print(f"Total entries: {stats.total_entries}")
```

### Statistics

```python
stats = cache.get_statistics()

# Returns CacheStatistics with:
# - total_entries: int
# - valid_entries: int (files still exist)
# - invalid_entries: int (files deleted)
# - total_size_bytes: int (cache file size)
# - hit_rate: float (0.0 to 1.0)
```

### Properties

```python
# Check if cache is enabled (not disabled by circuit breaker)
if cache.is_enabled:
    ...

# Get current hit rate
print(f"Hit rate: {cache.hit_rate:.2%}")
```

## Configuration

### Schema Version
Current version: `1.0`

Increment when `AnalysisResult` structure changes to invalidate old cache entries:

```python
CACHE_SCHEMA_VERSION = "1.0"
```

### Circuit Breaker

```python
CIRCUIT_BREAKER_THRESHOLD = 5  # Failures before opening
CIRCUIT_BREAKER_TIMEOUT = 300  # Seconds before reset attempt
```

## Error Handling

### Automatic Recovery

| Error | Detection | Recovery | Impact |
|-------|-----------|----------|--------|
| Corrupt JSON | Parse error | Delete + rebuild | None (cache miss) |
| Wrong schema | Version check | Clear cache | None (cache miss) |
| File changed | Hash mismatch | Invalidate entry | None (cache miss) |
| Disk full | Write error | Disable cache | Performance degradation |
| Repeated failures | Failure counter | Circuit breaker | Performance degradation |

### No Manual Intervention Required

All errors are handled gracefully with automatic recovery. The cache never fails the build - it degrades to direct analysis when necessary.

## Implementation Details

### Serialization

The cache handles complex Python objects:

- **Path objects** → Converted to strings
- **Sets** → Converted to lists (JSON compatible)
- **Nested dataclasses** → Recursively serialized

Deserialization reconstructs the original types:

- **Strings** → Path objects
- **Lists** → Sets (for `propagates_to`, `dependencies`)
- **Dicts** → ExportNode objects

### Atomic Writes

Cache writes are atomic to prevent corruption:

```python
1. Write to temp file: exportify_cache.tmp
2. Rename to final: exportify_cache.json
```

This ensures the cache file is never partially written.

### Hash Computation

SHA-256 hashing with chunked reading for large files:

```python
hasher = hashlib.sha256()
for chunk in iter(lambda: f.read(8192), b""):
    hasher.update(chunk)
```

## Testing

See `/tmp/test_cache_basic.py` for comprehensive tests covering:

- ✅ Basic operations (get, set, invalidate, clear)
- ✅ Hash-based validation
- ✅ File modification detection
- ✅ Corruption recovery
- ✅ Circuit breaker functionality
- ✅ Statistics tracking

## Performance Characteristics

| Operation | Expected Time | Notes |
|-----------|---------------|-------|
| Cache hit | <10ms | In-memory lookup + hash validation |
| Cache miss | <50ms | Hash computation + analysis |
| Cache write | <30ms | Serialization + atomic write |
| Circuit check | <1ms | Simple counter check |

## Future Enhancements

Potential improvements (not in current scope):

1. **LRU Eviction**: Limit cache size with LRU eviction policy
2. **Compression**: GZIP compression for large cache files
3. **Metrics Export**: Prometheus metrics for monitoring
4. **TTL Support**: Time-based cache invalidation
5. **Distributed Cache**: Redis/Memcached backend option

## Dependencies

- `hashlib` (stdlib): SHA-256 hashing
- `json` (stdlib): Serialization
- `pathlib` (stdlib): Path handling
- `dataclasses` (stdlib): Serialization support
- `logging` (stdlib): Error reporting
- `time` (stdlib): Timestamps and circuit breaker

## License

See project LICENSE file.
