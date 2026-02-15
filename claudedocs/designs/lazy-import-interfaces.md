<!--
SPDX-FileCopyrightText: 2026 Knitli Inc.

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Lazy Import System - Interface Contracts

## Overview

This document defines the formal interfaces and data contracts between components of the lazy import system, enabling independent evolution and clear boundaries.

---

## Core Data Contracts

### Export Generation Result

**Contract**: What the Export Manager produces

```python
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class GeneratedFile:
    """A file that was generated or updated."""
    path: Path
    content: str
    exports: list[str]  # What was exported from this file
    source_modules: list[str]  # Where exports came from
    timestamp: float  # When generated
    hash: str  # Content hash for verification


@dataclass(frozen=True)
class UpdatedFile:
    """A file that was modified."""
    path: Path
    old_content: str
    new_content: str
    changes: list[str]  # Description of changes made


@dataclass(frozen=True)
class SkippedFile:
    """A file that was skipped during processing."""
    path: Path
    reason: str  # Why it was skipped


@dataclass(frozen=True)
class GenerationMetrics:
    """Metrics from export generation."""
    files_analyzed: int
    files_generated: int
    files_updated: int
    files_skipped: int
    exports_created: int
    processing_time_ms: int
    cache_hit_rate: float


@dataclass(frozen=True)
class ExportGenerationResult:
    """Complete result of export generation process."""
    generated_files: list[GeneratedFile]
    updated_files: list[UpdatedFile]
    skipped_files: list[SkippedFile]
    metrics: GenerationMetrics
    success: bool
    errors: list[str]  # Any errors encountered
```

---

### Validation Report

**Contract**: What the Validator produces

```python
@dataclass(frozen=True)
class ValidationError:
    """A validation error that must be fixed."""
    file: Path
    line: int | None
    message: str
    suggestion: str | None
    code: str  # Error code (e.g., "BROKEN_IMPORT")


@dataclass(frozen=True)
class ValidationWarning:
    """A validation warning (non-critical)."""
    file: Path
    line: int | None
    message: str
    suggestion: str | None


@dataclass(frozen=True)
class ValidationMetrics:
    """Metrics from validation."""
    files_validated: int
    imports_checked: int
    consistency_checks: int
    validation_time_ms: int


@dataclass(frozen=True)
class ValidationReport:
    """Complete validation result."""
    errors: list[ValidationError]
    warnings: list[ValidationWarning]
    metrics: ValidationMetrics
    success: bool  # True if no errors (warnings OK)
```

---

### Export Node

**Contract**: Representation of a single export in the system

```python
from enum import Enum


class PropagationLevel(str, Enum):
    """How far an export should propagate up the hierarchy."""
    NONE = "none"  # Don't propagate
    PARENT = "parent"  # Propagate to parent module only
    ROOT = "root"  # Propagate all the way to package root
    CUSTOM = "custom"  # Custom propagation (advanced)


class MemberType(str, Enum):
    """Type of Python member."""
    CLASS = "class"
    FUNCTION = "function"
    VARIABLE = "variable"
    CONSTANT = "constant"
    TYPE_ALIAS = "type_alias"


@dataclass(frozen=True)
class ExportNode:
    """A single export in the propagation graph."""
    name: str  # Symbol name
    module: str  # Fully qualified module name
    member_type: MemberType
    propagation: PropagationLevel
    source_file: Path  # Where it's defined
    line_number: int  # Line where defined
    docstring: str | None = None


@dataclass(frozen=True)
class ExportManifest:
    """Export manifest for a single module."""
    module_path: str
    own_exports: list[ExportNode]  # Defined in this module
    propagated_exports: list[ExportNode]  # From children
    all_exports: list[ExportNode]  # own + propagated

    @property
    def export_names(self) -> list[str]:
        """All export names for __all__ declaration."""
        return sorted(e.name for e in self.all_exports)
```

---

### Rule Evaluation Result

**Contract**: Result of rule evaluation

```python
from enum import Enum


class RuleAction(str, Enum):
    """Action to take for an export."""
    INCLUDE = "include"
    EXCLUDE = "exclude"
    NO_DECISION = "no_decision"  # No rule matched


@dataclass(frozen=True)
class RuleMatch:
    """A rule that matched an export."""
    rule_name: str
    priority: int
    action: RuleAction
    propagation: PropagationLevel | None
    reason: str  # Why this rule matched


@dataclass(frozen=True)
class RuleEvaluationResult:
    """Result of evaluating rules for an export."""
    action: RuleAction
    matched_rule: RuleMatch | None
    propagation: PropagationLevel | None
    all_matches: list[RuleMatch]  # All rules that matched
```

---

### Cache Entry

**Contract**: Cached analysis data

```python
@dataclass(frozen=True)
class AnalysisResult:
    """Cached analysis of a Python file."""
    exports: list[ExportNode]
    imports: list[str]  # Import statements
    file_hash: str  # SHA-256 of file content
    analysis_timestamp: float
    schema_version: str  # For cache invalidation


@dataclass(frozen=True)
class CacheEntry:
    """A single cache entry."""
    file_path: Path
    file_hash: str
    analysis: AnalysisResult
    created_at: float
    accessed_at: float
```

---

## Component Interfaces

### Export Manager Interface

```python
from typing import Protocol


class ExportManager(Protocol):
    """Interface for export management."""

    def generate_all(self) -> ExportGenerationResult:
        """Generate all exports for the project."""
        ...

    def generate_module(self, module_path: str) -> ExportGenerationResult:
        """Generate exports for a specific module."""
        ...

    def check_up_to_date(self) -> bool:
        """Check if all generated files are up to date."""
        ...

    def get_manifest(self, module_path: str) -> ExportManifest:
        """Get export manifest for a module."""
        ...

    def should_export(
        self,
        name: str,
        module: str,
        member_type: MemberType
    ) -> tuple[bool, PropagationLevel | None]:
        """Check if a symbol should be exported."""
        ...
```

---

### Validator Interface

```python
class LazyImportValidator(Protocol):
    """Interface for lazy import validation."""

    def validate_all(self) -> ValidationReport:
        """Validate all lazy imports in project."""
        ...

    def validate_file(self, file_path: Path) -> ValidationReport:
        """Validate a specific file."""
        ...

    def validate_calls(self, files: list[Path]) -> list[ValidationError]:
        """Validate all lazy_import() calls."""
        ...

    def check_package(self, init_file: Path) -> list[ValidationError | ValidationWarning]:
        """Check package __init__.py consistency."""
        ...

    def fix_broken_imports(
        self,
        *,
        dry_run: bool = False
    ) -> list[Path]:
        """Fix broken imports (returns modified files)."""
        ...
```

---

### Rule Engine Interface

```python
class RuleEngine(Protocol):
    """Interface for rule evaluation."""

    def evaluate(
        self,
        name: str,
        module: str,
        member_type: MemberType
    ) -> RuleEvaluationResult:
        """Evaluate rules for an export candidate."""
        ...

    def load_rules(self, rule_files: list[Path]) -> None:
        """Load rules from files."""
        ...

    def validate_rules(self) -> list[ValidationError]:
        """Validate all loaded rules."""
        ...

    def get_rule_by_name(self, name: str) -> Rule | None:
        """Get a specific rule."""
        ...
```

---

### Propagation Graph Interface

```python
class PropagationGraph(Protocol):
    """Interface for propagation graph."""

    def add_export(self, export: ExportNode) -> None:
        """Add an export to the graph."""
        ...

    def build_manifests(self) -> dict[str, ExportManifest]:
        """Build export manifests for all modules."""
        ...

    def get_propagation_path(
        self,
        export: ExportNode
    ) -> list[str]:
        """Get the propagation path for an export."""
        ...

    def detect_cycles(self) -> list[list[str]]:
        """Detect circular propagation."""
        ...
```

---

### Analysis Cache Interface

```python
class AnalysisCache(Protocol):
    """Interface for analysis caching."""

    def get(
        self,
        file_path: Path,
        file_hash: str
    ) -> AnalysisResult | None:
        """Get cached analysis if valid."""
        ...

    def put(
        self,
        file_path: Path,
        file_hash: str,
        analysis: AnalysisResult
    ) -> None:
        """Store analysis in cache."""
        ...

    def invalidate(self, file_path: Path) -> None:
        """Invalidate cache for a file."""
        ...

    def clear(self) -> None:
        """Clear entire cache."""
        ...

    def get_stats(self) -> CacheStatistics:
        """Get cache statistics."""
        ...


@dataclass(frozen=True)
class CacheStatistics:
    """Cache statistics."""
    total_entries: int
    valid_entries: int
    invalid_entries: int
    total_size_bytes: int
    hit_rate: float
```

---

### File System Interface

```python
class FileSystem(Protocol):
    """Abstraction for file system operations."""

    def read_file(self, path: Path) -> str:
        """Read file contents."""
        ...

    def write_file(self, path: Path, content: str) -> None:
        """Write file contents (atomic)."""
        ...

    def list_files(self, pattern: str, root: Path | None = None) -> list[Path]:
        """List files matching pattern."""
        ...

    def file_exists(self, path: Path) -> bool:
        """Check if file exists."""
        ...

    def file_hash(self, path: Path) -> str:
        """Get SHA-256 hash of file."""
        ...
```

---

## Coordinator Interface

```python
@dataclass(frozen=True)
class CoordinatedResult:
    """Result from coordinator."""
    export_result: ExportGenerationResult
    validation_result: ValidationReport
    overall_success: bool
    total_time_ms: int


class LazyImportCoordinator(Protocol):
    """Coordinates export management and validation."""

    def regenerate_and_validate(self) -> CoordinatedResult:
        """Complete workflow: regenerate then validate."""
        ...

    def check_only(self) -> ValidationReport:
        """Only validate, don't regenerate."""
        ...

    def generate_only(self) -> ExportGenerationResult:
        """Only generate, don't validate."""
        ...

    def fix_all(self, *, dry_run: bool = False) -> CoordinatedResult:
        """Generate, validate, and fix issues."""
        ...
```

---

## Configuration Contracts

### Rule Definition

```python
@dataclass(frozen=True)
class RuleMatchCriteria:
    """Criteria for matching exports."""
    name_exact: str | None = None
    name_pattern: str | None = None  # Regex
    module_exact: str | None = None
    module_pattern: str | None = None  # Regex
    member_type: MemberType | None = None


@dataclass(frozen=True)
class Rule:
    """A rule for export decisions."""
    name: str  # Unique rule name
    priority: int  # 0-1000, higher = evaluated first
    description: str  # Human-readable description
    match: RuleMatchCriteria
    action: RuleAction
    propagate: PropagationLevel | None = None

    def __post_init__(self):
        """Validate rule."""
        if not 0 <= self.priority <= 1000:
            raise ValueError(f"Priority must be 0-1000, got {self.priority}")

        if not self.name:
            raise ValueError("Rule name required")
```

---

### Configuration

```python
@dataclass(frozen=True)
class LazyImportConfig:
    """Configuration for lazy import system."""
    enabled: bool
    strict_mode: bool
    cache_enabled: bool
    rule_files: list[Path]
    overrides_include: dict[str, list[str]]  # module -> names
    overrides_exclude: dict[str, list[str]]  # module -> names
    schema_version: str


@dataclass(frozen=True)
class ValidationConfig:
    """Configuration for validation."""
    check_lazy_import_calls: bool
    check_package_consistency: bool
    check_broken_imports: bool
    check_type_checking_imports: bool
    strict_mode: bool
    ignore_patterns: list[str]
    auto_fix_enabled: bool
    dry_run_by_default: bool
    backup_before_fix: bool
```

---

## Event System (Optional Future Enhancement)

```python
from typing import Callable
from enum import Enum


class EventType(str, Enum):
    """Event types."""
    EXPORTS_GENERATED = "exports_generated"
    VALIDATION_COMPLETE = "validation_complete"
    ERROR_OCCURRED = "error_occurred"
    CACHE_INVALIDATED = "cache_invalidated"


@dataclass(frozen=True)
class Event:
    """Base event."""
    type: EventType
    timestamp: float
    data: dict[str, any]


class EventBus(Protocol):
    """Event bus for decoupled communication."""

    def publish(self, event: Event) -> None:
        """Publish an event."""
        ...

    def subscribe(
        self,
        event_type: EventType,
        handler: Callable[[Event], None]
    ) -> None:
        """Subscribe to events."""
        ...

    def unsubscribe(
        self,
        event_type: EventType,
        handler: Callable[[Event], None]
    ) -> None:
        """Unsubscribe from events."""
        ...
```

---

## Usage Examples

### Using Export Manager

```python
from codeweaver.tools.lazy_imports import ExportManager

# Create manager
manager = ExportManager()

# Generate all exports
result = manager.generate_all()

print(f"Generated {result.metrics.exports_created} exports")
print(f"Updated {result.metrics.files_updated} files")
print(f"Time: {result.metrics.processing_time_ms}ms")

# Check if exports are up to date
if not manager.check_up_to_date():
    print("Exports need updating!")

# Get manifest for specific module
manifest = manager.get_manifest("codeweaver.core.types")
print(f"Exports: {manifest.export_names}")
```

### Using Validator

```python
from codeweaver.tools.lazy_imports import LazyImportValidator

# Create validator
validator = LazyImportValidator()

# Validate all
report = validator.validate_all()

if not report.success:
    for error in report.errors:
        print(f"❌ {error.file}:{error.line} - {error.message}")

    # Auto-fix if needed
    fixed_files = validator.fix_broken_imports(dry_run=False)
    print(f"Fixed {len(fixed_files)} files")
```

### Using Coordinator

```python
from codeweaver.tools.lazy_imports import LazyImportCoordinator

# Create coordinator
coordinator = LazyImportCoordinator()

# Full workflow
result = coordinator.regenerate_and_validate()

if result.overall_success:
    print(f"✅ Success! {result.total_time_ms}ms")
else:
    print(f"❌ Failures:")
    for error in result.validation_result.errors:
        print(f"  - {error.message}")
```

---

## Dependency Injection

### Using Protocols for Testing

```python
# Production implementation
class RealFileSystem:
    """Real file system implementation."""

    def read_file(self, path: Path) -> str:
        return path.read_text()

    def write_file(self, path: Path, content: str) -> None:
        path.write_text(content)

# Test implementation
class FakeFileSystem:
    """Fake file system for testing."""

    def __init__(self):
        self.files: dict[Path, str] = {}

    def read_file(self, path: Path) -> str:
        if path not in self.files:
            raise FileNotFoundError(path)
        return self.files[path]

    def write_file(self, path: Path, content: str) -> None:
        self.files[path] = content

# Usage
def test_export_generation():
    fs = FakeFileSystem()
    fs.write_file(Path("test.py"), "class Foo: pass")

    manager = ExportManager(filesystem=fs)
    result = manager.generate_all()

    assert result.success
```

---

## Versioning Strategy

### Schema Versioning

All contracts include schema_version to enable evolution:

```python
# Version 1.0
@dataclass(frozen=True)
class ExportGenerationResult:
    schema_version: str = "1.0"
    # ... fields

# Version 1.1 (added new field)
@dataclass(frozen=True)
class ExportGenerationResult:
    schema_version: str = "1.1"
    # ... original fields
    performance_hints: list[str] = field(default_factory=list)  # New field
```

### Backward Compatibility

```python
def from_dict(data: dict) -> ExportGenerationResult:
    """Load from dict with version handling."""
    version = data.get("schema_version", "1.0")

    if version == "1.0":
        # Upgrade to 1.1
        data["performance_hints"] = []
        data["schema_version"] = "1.1"

    return ExportGenerationResult(**data)
```

---

## Summary

All interfaces are:
- ✅ Well-defined with Protocol types
- ✅ Versioned for evolution
- ✅ Testable with dependency injection
- ✅ Documented with examples
- ✅ Type-safe with frozen dataclasses

This enables:
- Independent evolution of components
- Clear testing boundaries
- Flexible implementations
- Long-term maintainability
