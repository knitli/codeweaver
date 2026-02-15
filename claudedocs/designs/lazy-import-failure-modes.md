<!--
SPDX-FileCopyrightText: 2026 Knitli Inc.

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Lazy Import System - Failure Mode Analysis

## Overview

This document catalogs all failure modes for the lazy import system, specifying detection strategies, recovery approaches, user impact, and exit behaviors.

---

## Failure Mode Catalog

### FM-001: Corrupt JSON Cache

**Component**: Analysis Cache
**Failure**: JSON cache file is corrupted (truncated write, disk error, invalid JSON)

**Detection**:
- JSON parse error during cache.get()
- Hash mismatch (file exists but wrong hash)
- Invalid data structure after parsing

**Recovery**:
```python
def analyze_file(self, path: Path) -> Analysis:
    try:
        cached = self.cache.get(path, hash_file(path))
        if cached:
            self.cache_failures = 0  # Reset on success
            return cached
    except (JSONDecodeError, CacheCorruptionError) as e:
        logger.warning(
            f"Cache corruption detected for {path}: {e}\n"
            f"Deleting corrupt entry and re-analyzing"
        )
        self.cache.invalidate(path)
        self.cache_failures += 1
        # Fall through to direct analysis

    return self._analyze_directly(path)
```

**User Impact**:
- Warning logged
- Performance degradation (one file analyzed without cache)
- No functional impact

**Exit Behavior**: Continue (don't fail build)

**Prevention**:
- Atomic writes with temp file + rename
- Checksum validation
- Regular cache validation

---

### FM-002: Invalid Rule YAML

**Component**: Rule Loader
**Failure**: YAML syntax error or schema validation failure

**Detection**:
- YAML parser raises exception
- JSON schema validation fails
- Required fields missing

**Error Message**:
```
❌ Error loading rules from .codeweaver/rules/custom.yaml

Line 15: Invalid YAML syntax
  13 | - name: "my-rule"
  14 |   match:
  15 |     name_pattern: "^Foo  # <-- Missing closing quote
  16 |   action: include

Suggestions:
- Check for missing quotes, colons, or indentation
- Validate YAML at: https://www.yamllint.com/
- Restore from backup: .codeweaver/rules/custom.yaml.bak

Exit code: 1
```

**Recovery**: None (fail fast)

**User Impact**:
- Build fails immediately
- Clear error message with line number
- Actionable suggestions

**Exit Behavior**: Exit code 1

**Prevention**:
- Schema validation before loading
- Validation command: `mise run lazy-imports validate-config`
- Editor integration (LSP for YAML validation)

---

### FM-003: Rule File Not Found

**Component**: Rule Loader
**Failure**: Referenced rule file doesn't exist

**Detection**:
- File path in config doesn't exist
- Checked at startup

**Error Message**:
```
❌ Error: Rule file not found
  File: .codeweaver/rules/custom.yaml
  Referenced in: .codeweaver/lazy_imports.toml

Suggestions:
- Create the file: touch .codeweaver/rules/custom.yaml
- Remove reference from config
- Check file path spelling

Exit code: 1
```

**Recovery**: Configurable
```toml
[rules]
missing_file_behavior = "error"  # or "warn" or "create_default"
```

**User Impact**:
- Build fails (error mode)
- Warning logged (warn mode)
- Default file created (create_default mode)

**Exit Behavior**: Depends on config (default: error)

---

### FM-004: Circular Propagation

**Component**: Propagation Graph
**Failure**: Rules create circular propagation path

**Detection**:
- Cycle detection during graph building
- Tarjan's algorithm or similar

**Error Message**:
```
❌ Error: Circular propagation detected

Cycle path:
  codeweaver.core.utils
  → codeweaver.core.types
  → codeweaver.core.utils

This indicates conflicting propagation rules.

Suggestions:
- Review rules affecting these modules
- Ensure propagation is strictly hierarchical
- Use `mise run lazy-imports export debug <symbol>` to trace propagation

Exit code: 1
```

**Recovery**: None (fail fast)

**User Impact**:
- Build fails
- Clear cycle path shown
- Debug suggestions provided

**Exit Behavior**: Exit code 1

**Prevention**:
- Propagation must follow module hierarchy
- Rules validated to prevent cycles

---

### FM-005: Cache Write Failure

**Component**: Analysis Cache
**Failure**: Cannot write cache file (disk full, permissions, etc.)

**Detection**:
- IOError during cache.put()
- Disk space check

**Recovery**:
```python
def put(self, key: str, value: Analysis):
    try:
        # Atomic write
        temp_file = self._get_temp_path(key)
        temp_file.write_text(json.dumps(value.to_dict()))
        temp_file.rename(self._get_cache_path(key))
    except IOError as e:
        logger.warning(
            f"Cache write failed for {key}: {e}\n"
            f"Continuing without cache for this file"
        )
        # Don't fail, just proceed without caching
```

**User Impact**:
- Warning logged
- Performance degradation (no caching)
- No functional impact

**Exit Behavior**: Continue (warn only)

---

### FM-006: Broken Import in lazy_import() Call

**Component**: Import Validator
**Failure**: lazy_import() references non-existent module or object

**Detection**:
- AST analysis of lazy_import() calls
- Attempt to resolve import
- Check module existence

**Error Message**:
```
❌ Error: Broken lazy import detected

File: src/codeweaver/core/__init__.py
Line: 15
Call: lazy_import("codeweaver.old.module", "OldClass")
Issue: Module 'codeweaver.old.module' not found

Suggestions:
- Remove the lazy_import() call if module was deleted
- Fix module path if it was moved
- Run: mise run lazy-imports validate fix --dry-run

Exit code: 1 (strict mode) or 0 (permissive mode)
```

**Recovery**: Auto-fix available
```bash
mise run lazy-imports validate fix
# Removes broken imports automatically
```

**User Impact**:
- Validation fails (strict mode)
- Warning only (permissive mode)
- Auto-fix available

**Exit Behavior**: Depends on strictness setting

---

### FM-007: Hash Collision

**Component**: Analysis Cache
**Failure**: Different files produce same hash

**Detection**:
- Extremely rare (SHA-256 collision)
- File content mismatch after cache hit

**Recovery**:
```python
def get(self, path: Path, file_hash: str) -> Analysis | None:
    cached = self._load_from_disk(path)

    if cached and cached.hash == file_hash:
        # Additional verification: check file size
        if cached.file_size == path.stat().st_size:
            return cached.analysis

    # Hash match but content differs (collision)
    logger.error(f"Hash collision detected for {path}!")
    self.invalidate(path)
    return None
```

**User Impact**:
- Error logged
- Cache invalidated
- Re-analysis performed

**Exit Behavior**: Continue (automatic recovery)

**Mitigation**:
- Use strong hash (SHA-256)
- Include file size in cache key
- Statistical impossibility in practice

---

### FM-008: Excessive Cache Failures (Circuit Breaker)

**Component**: Analysis Cache
**Failure**: Multiple consecutive cache failures

**Detection**:
- Counter tracks failures
- Circuit opens after threshold (3 failures)

**Recovery**:
```python
class CachedAnalyzer:
    def __init__(self):
        self.cache_failures = 0
        self.cache_circuit_open = False
        self.circuit_threshold = 3

    def analyze_file(self, path: Path) -> Analysis:
        if not self.cache_circuit_open:
            try:
                cached = self.cache.get(path, hash_file(path))
                if cached:
                    self.cache_failures = 0
                    return cached
            except CacheError:
                self.cache_failures += 1
                if self.cache_failures >= self.circuit_threshold:
                    logger.warning(
                        f"Cache circuit opened after {self.cache_failures} failures\n"
                        f"Bypassing cache for remaining operations"
                    )
                    self.cache_circuit_open = True

        # Fallback: analyze without cache
        return self._analyze_directly(path)
```

**User Impact**:
- Warning logged once
- Performance degradation (no caching)
- Build continues successfully

**Exit Behavior**: Continue (automatic fallback)

**Reset**: Circuit resets on next run

---

### FM-009: Priority Collision

**Component**: Rule Engine
**Failure**: Multiple rules with same priority match same export

**Detection**:
- During rule evaluation
- Multiple matches at same priority level

**Resolution**:
- Lexicographic ordering on rule name
- Deterministic and documented

**Behavior**:
```python
def resolve_conflict(matches: list[RuleMatch]) -> RuleMatch:
    """Resolve conflicts: priority desc, then name asc."""
    return sorted(
        matches,
        key=lambda m: (-m.rule.priority, m.rule.name)
    )[0]
```

**User Impact**: None (automatic resolution)

**Exit Behavior**: Continue (no error)

**Prevention**: Document tie-breaking in rule writing guide

---

### FM-010: Invalid Regex Pattern

**Component**: Rule Engine
**Failure**: Rule contains invalid regex pattern

**Detection**:
- Regex compilation during rule loading
- Schema validation

**Error Message**:
```
❌ Error in rule: "match-complex-pattern"
  File: .codeweaver/rules/custom.yaml
  Line: 10

Invalid regex pattern: "^[A-Z("
  Error: unbalanced parenthesis at position 5

Suggestions:
- Test regex at: https://regex101.com/
- Escape special characters: ( ) [ ] { } . * + ?
- Check for balanced brackets

Exit code: 1
```

**Recovery**: None (fail fast)

**User Impact**:
- Build fails
- Clear error with pattern shown
- Position of error indicated

**Exit Behavior**: Exit code 1

**Prevention**:
- Regex validation during schema check
- Common pattern library provided

---

### FM-011: Unsupported Schema Version

**Component**: Configuration Loader
**Failure**: Config file uses unsupported schema version

**Detection**:
- Version check during config load
- Compared against supported versions

**Error Message**:
```
❌ Error: Unsupported schema version

File: .codeweaver/rules/core.yaml
Schema version: "99.0"
Supported versions: 1.0, 1.1

Suggestions:
- Upgrade codeweaver to support this schema
- Migrate config to supported version
- Use migration tool: mise run lazy-imports migrate-config

Exit code: 1
```

**Recovery**: Migration tool available
```bash
mise run lazy-imports migrate-config --from 99.0 --to 1.1
```

**User Impact**:
- Build fails
- Clear upgrade path shown
- Migration tool provided

**Exit Behavior**: Exit code 1

---

### FM-012: Duplicate Export Names

**Component**: Propagation Graph
**Failure**: Same export name from different source modules

**Detection**:
- During graph building
- Multiple sources for same name

**Behavior**: Deduplication with warning
```python
def add_export(self, export: ExportNode):
    if export.name in self.exports:
        existing = self.exports[export.name]
        if existing.source_module != export.source_module:
            logger.warning(
                f"Duplicate export: {export.name}\n"
                f"  Source 1: {existing.source_module}\n"
                f"  Source 2: {export.source_module}\n"
                f"  Using: {existing.source_module} (first occurrence)"
            )
            return  # Keep first occurrence

    self.exports[export.name] = export
```

**User Impact**:
- Warning logged
- First occurrence wins
- Build continues

**Exit Behavior**: Continue (warn only)

**Prevention**: Review warnings, adjust rules if needed

---

### FM-013: Inconsistent __all__ and _dynamic_imports

**Component**: Consistency Checker
**Failure**: __all__ doesn't match _dynamic_imports

**Detection**:
- AST comparison during validation
- Set difference calculation

**Error Message**:
```
⚠️  Warning: Inconsistency in src/codeweaver/core/__init__.py

__all__ contains:
  ["Foo", "Bar", "Baz"]

_dynamic_imports contains:
  ["Foo", "Bar"]

Missing from _dynamic_imports: ["Baz"]

Suggestions:
- Run: mise run lazy-imports export generate
- Or manually update _dynamic_imports

Exit code: 0 (warning) or 1 (strict mode)
```

**Recovery**: Auto-fix available
```bash
mise run lazy-imports validate fix
```

**User Impact**:
- Warning in permissive mode
- Error in strict mode
- Auto-fix available

**Exit Behavior**: Depends on strictness

---

### FM-014: Memory Exhaustion

**Component**: Entire System
**Failure**: Processing requires more memory than available

**Detection**:
- Memory monitoring
- Large file/module count

**Recovery**:
```python
class MemoryAwareProcessor:
    def __init__(self):
        self.memory_threshold = 400 * 1024 * 1024  # 400MB

    def process_all(self):
        if self._get_memory_usage() > self.memory_threshold:
            logger.warning(
                "High memory usage detected, enabling memory-saving mode"
            )
            # Enable incremental processing
            return self._process_incrementally()

        return self._process_normally()

    def _process_incrementally(self):
        """Process in smaller batches to reduce memory usage."""
        results = []
        for batch in self._create_batches():
            results.append(self._process_batch(batch))
            gc.collect()  # Force garbage collection

        return self._merge_results(results)
```

**User Impact**:
- Automatic fallback to incremental processing
- Slightly slower but completes successfully
- Warning logged

**Exit Behavior**: Continue (automatic adaptation)

---

### FM-015: File System Permissions

**Component**: File Operations
**Failure**: Cannot read source file or write generated file

**Detection**:
- IOError during file operations
- Permission checks

**Error Message**:
```
❌ Error: Permission denied

Cannot read: src/codeweaver/core/types.py
  Permissions: ---------
  Required: r--r--r--

Suggestions:
- Check file permissions: ls -l
- Fix with: chmod +r src/codeweaver/core/types.py
- Verify user has read access

Exit code: 1
```

**Recovery**: None (fail fast)

**User Impact**:
- Build fails
- Clear error message
- Fix suggestions

**Exit Behavior**: Exit code 1

---

## Failure Mode Decision Matrix

| Failure Mode | Severity | Detection | Recovery | Exit Code |
|--------------|----------|-----------|----------|-----------|
| FM-001: Corrupt Cache | Low | Exception | Auto-fix | 0 |
| FM-002: Invalid YAML | High | Parser | None | 1 |
| FM-003: Missing Rule File | Medium | File check | Configurable | 0 or 1 |
| FM-004: Circular Propagation | High | Cycle detection | None | 1 |
| FM-005: Cache Write Fail | Low | Exception | Bypass cache | 0 |
| FM-006: Broken Import | High | Validation | Auto-fix | 0 or 1 |
| FM-007: Hash Collision | Low | Verification | Auto-fix | 0 |
| FM-008: Cache Failures | Medium | Counter | Circuit breaker | 0 |
| FM-009: Priority Collision | None | Multi-match | Deterministic | 0 |
| FM-010: Invalid Regex | High | Compilation | None | 1 |
| FM-011: Unsupported Schema | High | Version check | Migration | 1 |
| FM-012: Duplicate Exports | Low | Dedup | First wins | 0 |
| FM-013: Inconsistent Data | Medium | Comparison | Auto-fix | 0 or 1 |
| FM-014: Memory Exhaustion | Medium | Monitoring | Incremental | 0 |
| FM-015: Permissions | High | File ops | None | 1 |

---

## Error Handling Patterns

### Pattern 1: Fail Fast
Used for: Configuration errors, invalid input

```python
def load_config(path: Path) -> Config:
    """Load and validate configuration (fail fast)."""
    if not path.exists():
        raise ConfigNotFoundError(f"Config file not found: {path}")

    try:
        content = path.read_text()
        data = yaml.safe_load(content)
    except yaml.YAMLError as e:
        raise ConfigSyntaxError(f"Invalid YAML in {path}: {e}")

    # Validate against schema
    validate_schema(data)  # Raises SchemaValidationError

    return Config.from_dict(data)
```

### Pattern 2: Graceful Degradation
Used for: Cache failures, non-critical errors

```python
def get_analysis(path: Path) -> Analysis:
    """Get analysis with cache fallback."""
    try:
        cached = self.cache.get(path)
        if cached:
            return cached
    except CacheError as e:
        logger.warning(f"Cache error: {e}, using fallback")
        # Continue without cache

    # Fallback: analyze directly
    return self._analyze_directly(path)
```

### Pattern 3: Circuit Breaker
Used for: Repeated failures, resource issues

```python
class CircuitBreaker:
    def __init__(self, threshold=3, timeout=60):
        self.failures = 0
        self.threshold = threshold
        self.timeout = timeout
        self.opened_at = None

    def call(self, func, *args, **kwargs):
        # Check if circuit is open
        if self.is_open():
            if self.should_attempt_reset():
                self.half_open()
            else:
                raise CircuitOpenError("Circuit breaker is open")

        try:
            result = func(*args, **kwargs)
            self.on_success()
            return result
        except Exception as e:
            self.on_failure()
            raise

    def is_open(self):
        return self.failures >= self.threshold

    def should_attempt_reset(self):
        if not self.opened_at:
            return False
        return (time.time() - self.opened_at) > self.timeout

    def on_success(self):
        self.failures = 0
        self.opened_at = None

    def on_failure(self):
        self.failures += 1
        if self.is_open() and not self.opened_at:
            self.opened_at = time.time()
            logger.warning("Circuit breaker opened")
```

### Pattern 4: Retry with Backoff
Used for: Transient failures, network issues

```python
def retry_with_backoff(
    func,
    max_attempts=3,
    initial_delay=1.0,
    backoff_factor=2.0
):
    """Retry function with exponential backoff."""
    delay = initial_delay

    for attempt in range(max_attempts):
        try:
            return func()
        except TransientError as e:
            if attempt == max_attempts - 1:
                raise  # Last attempt, re-raise

            logger.warning(
                f"Attempt {attempt + 1} failed: {e}\n"
                f"Retrying in {delay}s..."
            )
            time.sleep(delay)
            delay *= backoff_factor

    raise MaxRetriesExceeded()
```

---

## Testing Failure Modes

### Failure Mode Tests

```python
# tests/integration/test_error_handling.py

class TestFailureModes:
    """Test suite for failure mode handling."""

    def test_corrupt_cache_recovery(self):
        """FM-001: Should recover from corrupt cache."""
        # Corrupt cache file
        cache_file = Path(".codeweaver/cache/test.json")
        cache_file.write_text("{invalid")

        # Should recover gracefully
        processor = LazyImportProcessor()
        result = processor.process_all()

        assert result.success
        assert "Cache corruption detected" in caplog.text

    def test_invalid_yaml_error(self):
        """FM-002: Should fail fast on invalid YAML."""
        write_file(".codeweaver/rules/bad.yaml", "name: 'unclosed")

        with pytest.raises(ConfigSyntaxError) as exc:
            load_rules()

        assert "Invalid YAML" in str(exc.value)

    def test_circular_propagation_detection(self):
        """FM-004: Should detect circular propagation."""
        rules = create_circular_rules()

        with pytest.raises(PropagationCycleError) as exc:
            graph = PropagationGraph(rules)
            graph.build()

        assert "Circular propagation" in str(exc.value)

    def test_cache_circuit_breaker(self):
        """FM-008: Should open circuit after failures."""
        cache = FailingCache(fail_count=5)
        processor = LazyImportProcessor(cache=cache)

        result = processor.process_all()

        assert result.success
        assert "Circuit breaker opened" in caplog.text
```

---

## Observability

### Error Metrics

```python
@dataclass
class ErrorMetrics:
    """Track error occurrences."""
    cache_corruptions: int = 0
    validation_errors: int = 0
    config_errors: int = 0
    circuit_breaker_opens: int = 0

    def report(self):
        """Generate error report."""
        return {
            "cache_corruptions": self.cache_corruptions,
            "validation_errors": self.validation_errors,
            "config_errors": self.config_errors,
            "circuit_opens": self.circuit_breaker_opens,
        }
```

### Error Logging

```python
# Structured error logging
logger.error(
    "Failure detected",
    extra={
        "failure_mode": "FM-001",
        "component": "cache",
        "severity": "low",
        "recovery": "auto",
        "file_path": str(path),
    }
)
```

---

## Summary

All failure modes documented with:
- ✅ Clear detection strategy
- ✅ Defined recovery approach
- ✅ User impact assessment
- ✅ Exit behavior specification
- ✅ Prevention measures
- ✅ Test coverage plan

This ensures robust error handling and graceful degradation across the system.
