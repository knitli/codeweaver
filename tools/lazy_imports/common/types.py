#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Core type definitions for the lazy import system.

This module defines all the data structures, enums, and types used throughout
the lazy import system, following the interface contracts specified in
.specify/designs/lazy-import-interfaces.md.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum
from pathlib import Path


# Enumerations


class PropagationLevel(StrEnum):
    """How far an export should propagate up the package hierarchy."""

    NONE = "none"  # Don't propagate
    PARENT = "parent"  # Propagate to parent module only
    ROOT = "root"  # Propagate all the way to package root
    CUSTOM = "custom"  # Custom propagation (advanced, future)


class RuleAction(StrEnum):
    """Action to take for an export."""

    INCLUDE = "include"
    EXCLUDE = "exclude"
    NO_DECISION = "no_decision"  # No rule matched


class MemberType(StrEnum):
    """Type of Python member."""

    CLASS = "class"
    FUNCTION = "function"
    VARIABLE = "variable"
    CONSTANT = "constant"
    TYPE_ALIAS = "type_alias"
    IMPORTED = "imported"  # For imported symbols
    UNKNOWN = "unknown"


class SymbolProvenance(StrEnum):
    """Where a symbol comes from."""

    DEFINED_HERE = "defined_here"  # Defined in the current file
    IMPORTED = "imported"  # Imported from another module
    ALIAS_IMPORTED = "alias_imported"  # Imported with an alias (import X as Y)
    UNKNOWN = "unknown"


@dataclass(frozen=True)
class SourceLocation:
    """Location in a source file."""

    line: int
    column: int | None = None


# Discovery Phase Types


@dataclass(frozen=True)
class DetectedSymbol:
    """A raw symbol found in a source file (Discovery Phase)."""

    name: str
    provenance: SymbolProvenance
    location: SourceLocation
    member_type: MemberType

    # Critical Context
    is_private: bool
    original_source: str | None  # If imported, where from? "codeweaver.utils"
    original_name: str | None  # If aliased, what was the original name?
    docstring: str | None = None
    metadata: dict[str, object] = field(default_factory=dict)


# Decision Phase Types


@dataclass(frozen=True)
class ExportDecision:
    """The result of applying rules to a symbol (Decision Phase)."""

    module_path: str  # Context of decision
    action: RuleAction
    export_name: str  # Usually symbol.name, but rules could rename it
    propagation: PropagationLevel
    priority: int  # Traceable priority for conflict resolution
    reason: str  # "Matched rule: PublicVariable"
    source_symbol: DetectedSymbol  # logic trace back


# Graph/Generation Phase Types


@dataclass(frozen=True)
class LazyExport:
    """A finalized export entry for __init__.py generation (Graph Phase)."""

    public_name: str  # Name in __all__
    target_module: str  # "codeweaver.core.utils" (absolute)
    target_object: str  # "some_function"
    is_type_only: bool  # Goes in TYPE_CHECKING only?

    def __hash__(self):
        """Hash based on public_name, target_module, and target_object for use in sets/dicts."""
        return hash((self.public_name, self.target_module, self.target_object))


@dataclass(frozen=True)
class ExportManifest:
    """Export manifest for a single module.

    Contains all exports for a module: both its own exports and those
    propagated from child modules.
    """

    module_path: str
    own_exports: list[LazyExport]  # Defined in this module
    propagated_exports: list[LazyExport]  # From children
    all_exports: list[LazyExport]  # own + propagated

    @property
    def export_names(self) -> list[str]:
        """All export names for __all__ declaration (sorted by export_sort_key)."""
        # Note: all_exports should be pre-sorted by PropagationGraph.build_manifests(),
        # but we sort defensively to handle manually-constructed manifests (e.g., tests)
        import textcase

        def _sort_key(name: str) -> tuple[int, str]:
            """SCREAMING_SNAKE (0) → PascalCase (1) → snake_case (2), then alphabetically."""
            if textcase.constant.match(name):
                return (0, name.lower())
            return (1, name.lower()) if textcase.pascal.match(name) else (2, name.lower())

        names = [e.public_name for e in self.all_exports]
        return sorted(names, key=_sort_key)


# Rule System Types


@dataclass(frozen=True)
class RuleMatchCriteria:
    """Criteria for matching exports."""

    name_exact: str | None = None
    name_pattern: str | None = None  # Regex
    module_exact: str | None = None
    module_pattern: str | None = None  # Regex
    member_type: MemberType | None = None
    provenance: SymbolProvenance | None = None  # NEW: Match on symbol provenance
    any_of: list[RuleMatchCriteria] | None = None  # OR conditions
    all_of: list[RuleMatchCriteria] | None = None  # AND conditions


@dataclass(frozen=True)
class Rule:
    """A rule for export decisions.

    Rules are evaluated in priority order (higher = first).
    When multiple rules match, the highest priority wins.
    For same priority, alphabetically first rule name wins.
    """

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

        # Validate action is a valid RuleAction
        if not isinstance(self.action, RuleAction):
            try:
                # Try to convert string to RuleAction
                object.__setattr__(self, "action", RuleAction(self.action))
            except (ValueError, KeyError) as e:
                raise ValueError(
                    f"Invalid action: {self.action!r}. Must be one of: {[a.value for a in RuleAction]}"
                ) from e

        # Validate propagate is a valid PropagationLevel if provided
        if self.propagate is not None and not isinstance(self.propagate, PropagationLevel):
            try:
                # Try to convert string to PropagationLevel
                object.__setattr__(self, "propagate", PropagationLevel(self.propagate))
            except (ValueError, KeyError) as e:
                raise ValueError(
                    f"Invalid propagation level: {self.propagate!r}. Must be one of: {[p.value for p in PropagationLevel]}"
                ) from e


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


# Generation Results


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


# Validation Results


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


# Cache Types


@dataclass(frozen=True)
class AnalysisResult:
    """Cached analysis of a Python file."""

    symbols: list[DetectedSymbol]
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


@dataclass(frozen=True)
class CacheStatistics:
    """Cache statistics."""

    total_entries: int
    valid_entries: int
    invalid_entries: int
    total_size_bytes: int
    hit_rate: float


# Coordinator Result


@dataclass(frozen=True)
class CoordinatedResult:
    """Result from coordinator."""

    export_result: ExportGenerationResult
    validation_result: ValidationReport
    overall_success: bool
    total_time_ms: int


# Configuration Types


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


# Import Resolution


@dataclass(frozen=True)
class ImportResolution:
    """Result of import resolution."""

    module: str
    obj: str
    exists: bool
    path: Path | None
    error: str | None = None


# Consistency Issue


@dataclass(frozen=True)
class ConsistencyIssue:
    """Issue found during consistency checking."""

    severity: str  # "error", "warning", "info"
    location: Path
    message: str
    line: int | None = None


# Call Error


@dataclass(frozen=True)
class CallError:
    """Error in a lazy_import() call."""

    file: Path
    line: int
    module: str
    obj: str
    error: str
