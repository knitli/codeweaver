<!--
SPDX-FileCopyrightText: 2026 Knitli Inc.

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Lazy Import System - Remediation Plan v2.0

**Created**: 2026-02-14  
**Status**: Active  
**Timeline**: 10-12 days  
**Previous Version**: v1.0 (replaced - removed Week 2 migration validation)

## Changes from v1.0

**Removed**:
- ❌ Week 2: Migration Validation Workflow (REQ-COMPAT-001)
  - Rationale: Old system never delivered desired results, equivalence validation not needed
  - Impact: Eliminates most complex/uncertain remediation work

**Added**:
- ✅ **Week 2: Core Implementation** - File discovery, AST parsing, pipeline orchestration, CLI integration
  - Rationale: Critical gaps discovered in QA review - CLI commands are placeholders
  - Impact: Required for system to actually work end-to-end

**Retained**:
- ✅ Week 1: Schema Versioning, Circuit Breaker, Validator Completion (from v1.0)
- ✅ Week 3: Polish & Documentation (from v1.0, condensed)

## Overview

### Current Status
- **Compliance**: 64% (14/22 requirements) - excluding deprecated REQ-COMPAT-001
- **Critical Gap**: CLI implementation is placeholder - cannot actually generate exports
- **Blocking Issues**: 
  - REQ-CONFIG-002: Schema versioning not enforced
  - REQ-ERROR-003: Circuit breaker not implemented
  - REQ-FUNC-001: Core pipeline missing (file discovery, AST parsing, orchestration)

### Target Status
- **Compliance**: 100% (all valid requirements)
- **Functionality**: Complete end-to-end workflow
- **Performance**: Meets all performance targets (REQ-PERF-001, REQ-PERF-002)
- **Production Ready**: All critical gaps addressed

---

## Week 1: Critical Fixes (Days 1-3)

**Goal**: Address existing implementation gaps in core components

### Day 1: Schema Versioning Enforcement

**Requirement**: REQ-CONFIG-002  
**Priority**: Critical 🔴  
**Effort**: 4-6 hours

**Current State**:
- Schema version field exists in types
- No validation on config load
- No migration logic for version changes

**Implementation**:

```python
# In tools/lazy_imports/export_manager/rules.py

CURRENT_SCHEMA_VERSION = "1.0"
SUPPORTED_VERSIONS = ["1.0"]  # Expand as we add versions

class SchemaVersionError(Exception):
    """Schema version mismatch or unsupported."""
    pass

class RuleEngine:
    def load_rules(self, rule_files: list[Path]) -> None:
        """Load rules with schema version validation."""
        for rule_file in rule_files:
            data = yaml.safe_load(rule_file.read_text())
            
            # Validate schema version
            if "schema_version" not in data:
                raise SchemaVersionError(
                    f"Missing schema_version in {rule_file}\n"
                    f"Expected: {CURRENT_SCHEMA_VERSION}"
                )
            
            version = data["schema_version"]
            if version not in SUPPORTED_VERSIONS:
                raise SchemaVersionError(
                    f"Unsupported schema version {version} in {rule_file}\n"
                    f"Supported versions: {', '.join(SUPPORTED_VERSIONS)}\n"
                    f"Current version: {CURRENT_SCHEMA_VERSION}\n\n"
                    f"You may need to:\n"
                    f"  1. Update CodeWeaver to support this version\n"
                    f"  2. Migrate the config file to {CURRENT_SCHEMA_VERSION}\n"
                    f"  3. Run: codeweaver lazy-imports migrate"
                )
            
            # If older version, migrate
            if version != CURRENT_SCHEMA_VERSION:
                data = self._migrate_schema(data, from_version=version)
            
            # Continue with rule loading...
            self._load_rules_from_data(data)
    
    def _migrate_schema(self, data: dict, from_version: str) -> dict:
        """Migrate config from old schema to current.
        
        Future: Add migration logic as schema evolves.
        Currently: No migrations needed (only one version exists).
        """
        # Placeholder for future migrations
        # e.g., if from_version == "0.9":
        #     data = self._migrate_0_9_to_1_0(data)
        return data
```

**Testing**:
- Test missing schema_version → raises SchemaVersionError
- Test unsupported version → raises with helpful message
- Test supported version → loads successfully
- Test future version migration (when we add version 1.1)

**Acceptance**:
- ✅ Clear error messages for version mismatches
- ✅ Helpful suggestions for resolution
- ✅ Migration path defined (even if not used yet)

---

### Day 2: Circuit Breaker Implementation

**Requirement**: REQ-ERROR-003  
**Priority**: Important 🟡  
**Effort**: 4-6 hours

**Current State**:
- Cache has basic corruption recovery
- No circuit breaker pattern
- Repeated failures could cause performance issues

**Implementation**:

```python
# In tools/lazy_imports/common/cache.py

from dataclasses import dataclass, field
from datetime import datetime, timedelta
from enum import Enum

class CircuitState(Enum):
    """Circuit breaker states."""
    CLOSED = "closed"      # Normal operation
    OPEN = "open"          # Failures detected, reject requests
    HALF_OPEN = "half_open"  # Testing if service recovered

@dataclass
class CircuitBreaker:
    """Circuit breaker for cache operations."""
    
    failure_threshold: int = 5
    recovery_timeout: timedelta = timedelta(seconds=30)
    success_threshold: int = 2
    
    state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    failure_count: int = field(default=0, init=False)
    success_count: int = field(default=0, init=False)
    last_failure_time: datetime | None = field(default=None, init=False)
    
    def record_success(self) -> None:
        """Record successful operation."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= self.success_threshold:
                # Recovered - close circuit
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
        elif self.state == CircuitState.CLOSED:
            # Reset failure count on success
            self.failure_count = 0
    
    def record_failure(self) -> None:
        """Record failed operation."""
        self.failure_count += 1
        self.last_failure_time = datetime.now()
        
        if self.failure_count >= self.failure_threshold:
            # Open circuit
            self.state = CircuitState.OPEN
    
    def can_attempt(self) -> bool:
        """Check if operation should be attempted."""
        if self.state == CircuitState.CLOSED:
            return True
        
        if self.state == CircuitState.OPEN:
            # Check if recovery timeout elapsed
            if (self.last_failure_time and 
                datetime.now() - self.last_failure_time >= self.recovery_timeout):
                # Try half-open
                self.state = CircuitState.HALF_OPEN
                self.success_count = 0
                return True
            return False
        
        # HALF_OPEN - allow attempt
        return True

class JSONAnalysisCache:
    def __init__(self, cache_dir: Path | None = None):
        # ... existing init ...
        self.circuit_breaker = CircuitBreaker()
    
    def get(self, file_path: Path, file_hash: str) -> AnalysisResult | None:
        """Get cached analysis with circuit breaker protection."""
        if not self.circuit_breaker.can_attempt():
            # Circuit is open - skip cache
            logger.warning("Cache circuit breaker is OPEN - bypassing cache")
            return None
        
        try:
            result = self._get_from_cache(file_path, file_hash)
            self.circuit_breaker.record_success()
            return result
        except Exception as e:
            self.circuit_breaker.record_failure()
            logger.error(f"Cache get failed: {e}")
            return None
    
    def put(self, file_path: Path, file_hash: str, analysis: AnalysisResult) -> None:
        """Put analysis in cache with circuit breaker protection."""
        if not self.circuit_breaker.can_attempt():
            # Circuit is open - skip cache write
            logger.warning("Cache circuit breaker is OPEN - skipping cache write")
            return
        
        try:
            self._put_to_cache(file_path, file_hash, analysis)
            self.circuit_breaker.record_success()
        except Exception as e:
            self.circuit_breaker.record_failure()
            logger.error(f"Cache put failed: {e}")
```

**Testing**:
- Test normal operation (CLOSED state)
- Test repeated failures → OPEN state
- Test recovery timeout → HALF_OPEN state
- Test successful operations in HALF_OPEN → CLOSED
- Test circuit prevents operations when OPEN

**Acceptance**:
- ✅ Prevents cascade failures
- ✅ Automatic recovery after timeout
- ✅ Clear logging of circuit state changes
- ✅ Performance degradation instead of complete failure

---

### Day 3: Validator Completion

**Requirement**: REQ-FUNC-004  
**Priority**: Important 🟡  
**Effort**: 4-6 hours

**Current State**:
- Basic validation exists
- Missing checks for:
  - Syntax errors in lazy_import() calls
  - TYPE_CHECKING block structure
  - Import organization

**Implementation**:

```python
# In tools/lazy_imports/validator/validator.py

class LazyImportValidator:
    def validate_file(self, file_path: Path) -> ValidationResult:
        """Validate a single file comprehensively."""
        errors = []
        warnings = []
        
        try:
            content = file_path.read_text()
            tree = ast.parse(content)
        except SyntaxError as e:
            return ValidationResult(
                errors=[ValidationError(
                    file=file_path,
                    line=e.lineno,
                    message=f"Syntax error: {e.msg}",
                    suggestion="Fix syntax before validation",
                    code="SYNTAX_ERROR"
                )],
                warnings=[],
                success=False
            )
        
        # Check 1: Validate lazy_import() calls
        errors.extend(self._check_lazy_import_calls(file_path, tree))
        
        # Check 2: Validate TYPE_CHECKING structure
        warnings.extend(self._check_type_checking_blocks(file_path, tree))
        
        # Check 3: Validate __all__ matches imports
        all_errors, all_warnings = self._check_all_declaration(file_path, tree)
        errors.extend(all_errors)
        warnings.extend(all_warnings)
        
        # Check 4: Validate import organization
        warnings.extend(self._check_import_organization(file_path, tree))
        
        return ValidationResult(
            errors=errors,
            warnings=warnings,
            success=len(errors) == 0
        )
    
    def _check_lazy_import_calls(
        self, 
        file_path: Path, 
        tree: ast.Module
    ) -> list[ValidationError]:
        """Check lazy_import() calls are well-formed."""
        errors = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if (isinstance(node.func, ast.Name) and 
                    node.func.id == "lazy_import"):
                    # Validate call signature
                    if len(node.args) < 2:
                        errors.append(ValidationError(
                            file=file_path,
                            line=node.lineno,
                            message="lazy_import() requires at least 2 arguments (module, name)",
                            suggestion="lazy_import('module.path', 'SymbolName')",
                            code="INVALID_LAZY_IMPORT"
                        ))
                    
                    # Check arguments are string literals
                    for i, arg in enumerate(node.args[:2]):
                        if not isinstance(arg, ast.Constant) or not isinstance(arg.value, str):
                            errors.append(ValidationError(
                                file=file_path,
                                line=node.lineno,
                                message=f"lazy_import() argument {i+1} must be a string literal",
                                suggestion="Use string literals, not variables or expressions",
                                code="NON_LITERAL_LAZY_IMPORT"
                            ))
        
        return errors
    
    def _check_type_checking_blocks(
        self,
        file_path: Path,
        tree: ast.Module
    ) -> list[ValidationWarning]:
        """Check TYPE_CHECKING blocks are properly structured."""
        warnings = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.If):
                # Check if this is a TYPE_CHECKING block
                if (isinstance(node.test, ast.Name) and 
                    node.test.id == "TYPE_CHECKING"):
                    # Validate only imports in block
                    for stmt in node.body:
                        if not isinstance(stmt, (ast.Import, ast.ImportFrom)):
                            warnings.append(ValidationWarning(
                                file=file_path,
                                line=stmt.lineno,
                                message="TYPE_CHECKING block should only contain imports",
                                suggestion="Move non-import statements outside the block"
                            ))
        
        return warnings
    
    def _check_all_declaration(
        self,
        file_path: Path,
        tree: ast.Module
    ) -> tuple[list[ValidationError], list[ValidationWarning]]:
        """Check __all__ declaration matches actual exports."""
        errors = []
        warnings = []
        
        # Find __all__ declaration
        all_names = None
        for node in tree.body:
            if isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name) and target.id == "__all__":
                        # Extract names from list
                        if isinstance(node.value, (ast.List, ast.Tuple)):
                            all_names = [
                                elt.value for elt in node.value.elts
                                if isinstance(elt, ast.Constant) and isinstance(elt.value, str)
                            ]
        
        if all_names is None:
            warnings.append(ValidationWarning(
                file=file_path,
                line=None,
                message="Missing __all__ declaration",
                suggestion="Add __all__ to explicitly define public API"
            ))
            return errors, warnings
        
        # Check that all names in __all__ are defined or imported
        defined_names = self._get_defined_names(tree)
        imported_names = self._get_imported_names(tree)
        available_names = defined_names | imported_names
        
        for name in all_names:
            if name not in available_names:
                errors.append(ValidationError(
                    file=file_path,
                    line=None,
                    message=f"'{name}' in __all__ but not defined or imported",
                    suggestion=f"Either define/import '{name}' or remove from __all__",
                    code="UNDEFINED_IN_ALL"
                ))
        
        return errors, warnings
    
    def _check_import_organization(
        self,
        file_path: Path,
        tree: ast.Module
    ) -> list[ValidationWarning]:
        """Check imports are organized properly."""
        warnings = []
        
        # Imports should be at top of file (after docstring and __future__)
        found_non_import = False
        for node in tree.body:
            if isinstance(node, (ast.Import, ast.ImportFrom)):
                if found_non_import:
                    # Special case: allow if TYPE_CHECKING
                    if not (isinstance(node, ast.ImportFrom) and 
                           isinstance(getattr(node, 'parent_if', None), ast.If)):
                        warnings.append(ValidationWarning(
                            file=file_path,
                            line=node.lineno,
                            message="Import statement after non-import code",
                            suggestion="Move imports to top of file"
                        ))
            elif not isinstance(node, ast.Expr):  # Skip docstrings
                found_non_import = True
        
        return warnings
```

**Testing**:
- Test each validation check independently
- Test combination of errors and warnings
- Test empty files, minimal files, complex files
- Test auto-fix integration (validator finds issues → fixer fixes them)

**Acceptance**:
- ✅ Comprehensive validation coverage
- ✅ Clear error messages with suggestions
- ✅ Distinguishes errors (blockers) from warnings (improvements)
- ✅ Integrates with auto-fix workflow

---

## Week 2: Core Implementation (Days 4-8)

**Goal**: Implement missing components to make system actually work

### Day 4: File Discovery Service

**Requirement**: REQ-FUNC-001 (part 1)  
**Priority**: Critical 🔴  
**Effort**: 3-4 hours

**Implementation**:

```python
# New file: tools/lazy_imports/discovery/file_discovery.py

from pathlib import Path
from typing import Pattern
import re
import fnmatch

class FileDiscovery:
    """Discover Python files in source tree."""
    
    def __init__(self, *, respect_gitignore: bool = True):
        self.respect_gitignore = respect_gitignore
        self._gitignore_patterns: list[Pattern] = []
    
    def discover_python_files(
        self,
        root: Path,
        *,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None
    ) -> list[Path]:
        """Find all Python files in directory tree.
        
        Args:
            root: Root directory to search
            include_patterns: Glob patterns to include (e.g., ["*.py"])
            exclude_patterns: Glob patterns to exclude (e.g., ["*_test.py"])
        
        Returns:
            Sorted list of Python file paths
        """
        if self.respect_gitignore:
            self._load_gitignore(root)
        
        python_files = []
        
        for py_file in root.rglob("*.py"):
            # Skip __pycache__
            if "__pycache__" in py_file.parts:
                continue
            
            # Skip if gitignored
            if self.respect_gitignore and self._is_ignored(py_file, root):
                continue
            
            # Apply include patterns
            if include_patterns and not any(
                fnmatch.fnmatch(py_file.name, pattern) 
                for pattern in include_patterns
            ):
                continue
            
            # Apply exclude patterns
            if exclude_patterns and any(
                fnmatch.fnmatch(py_file.name, pattern)
                for pattern in exclude_patterns
            ):
                continue
            
            python_files.append(py_file)
        
        return sorted(python_files)
    
    def _load_gitignore(self, root: Path) -> None:
        """Load .gitignore patterns."""
        gitignore_file = root / ".gitignore"
        if not gitignore_file.exists():
            return
        
        patterns = []
        for line in gitignore_file.read_text().splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            
            # Convert gitignore pattern to regex
            # Simplified - could use gitignore-parser library for full support
            pattern = line.replace(".", r"\\.").replace("*", ".*")
            patterns.append(re.compile(pattern))
        
        self._gitignore_patterns = patterns
    
    def _is_ignored(self, path: Path, root: Path) -> bool:
        """Check if path matches any gitignore pattern."""
        relative = path.relative_to(root)
        relative_str = str(relative)
        
        return any(
            pattern.match(relative_str)
            for pattern in self._gitignore_patterns
        )
```

**Testing**:
- Test finds all .py files in tree
- Test respects .gitignore
- Test excludes __pycache__
- Test include/exclude patterns
- Test empty directories
- Test nested structures

**Files**: 
- `tools/lazy_imports/discovery/__init__.py`
- `tools/lazy_imports/discovery/file_discovery.py`
- `tools/tests/lazy_imports/test_discovery.py`

---

### Days 5-6: AST Parser + Export Extractor

**Requirement**: REQ-FUNC-001 (part 2)  
**Priority**: Critical 🔴  
**Effort**: 8-12 hours

**Implementation**:

```python
# New file: tools/lazy_imports/analysis/ast_parser.py

import ast
from pathlib import Path
from dataclasses import dataclass

from tools.lazy_imports.common.types import (
    ExportNode, MemberType, PropagationLevel, AnalysisResult
)
from tools.lazy_imports.export_manager.rules import RuleEngine

@dataclass
class ParsedSymbol:
    """A symbol extracted from AST."""
    name: str
    member_type: MemberType
    line_number: int
    docstring: str | None
    
class ASTParser:
    """Parse Python files and extract exports."""
    
    def __init__(self, rule_engine: RuleEngine):
        self.rule_engine = rule_engine
    
    def parse_file(self, file_path: Path, module_path: str) -> AnalysisResult:
        """Parse a Python file and extract exports.
        
        Args:
            file_path: Path to Python file
            module_path: Module path (e.g., "codeweaver.core.types")
        
        Returns:
            AnalysisResult with exports and metadata
        """
        import hashlib
        import time
        
        # Read and hash file
        content = file_path.read_text()
        file_hash = hashlib.sha256(content.encode()).hexdigest()
        
        try:
            tree = ast.parse(content)
        except SyntaxError as e:
            # Return empty result with error
            return AnalysisResult(
                exports=[],
                imports=[],
                file_hash=file_hash,
                analysis_timestamp=time.time(),
                schema_version="1.0"
            )
        
        # Extract symbols
        symbols = self._extract_symbols(tree, file_path)
        
        # Convert to ExportNodes with rule evaluation
        exports = []
        for symbol in symbols:
            # Evaluate rules to determine propagation
            result = self.rule_engine.evaluate(
                symbol.name,
                module_path,
                symbol.member_type
            )
            
            # Skip if excluded
            if result.action == RuleAction.EXCLUDE:
                continue
            
            # Create ExportNode
            export = ExportNode(
                name=symbol.name,
                module=module_path,
                member_type=symbol.member_type,
                propagation=result.propagation or PropagationLevel.PARENT,
                source_file=file_path,
                line_number=symbol.line_number,
                defined_in=module_path,
                docstring=symbol.docstring
            )
            exports.append(export)
        
        # Extract imports
        imports = self._extract_imports(tree)
        
        return AnalysisResult(
            exports=exports,
            imports=imports,
            file_hash=file_hash,
            analysis_timestamp=time.time(),
            schema_version="1.0"
        )
    
    def _extract_symbols(self, tree: ast.Module, file_path: Path) -> list[ParsedSymbol]:
        """Extract all exportable symbols from AST."""
        symbols = []
        
        for node in tree.body:
            # Classes
            if isinstance(node, ast.ClassDef):
                symbols.append(ParsedSymbol(
                    name=node.name,
                    member_type=MemberType.CLASS,
                    line_number=node.lineno,
                    docstring=ast.get_docstring(node)
                ))
            
            # Functions (top-level only)
            elif isinstance(node, ast.FunctionDef):
                symbols.append(ParsedSymbol(
                    name=node.name,
                    member_type=MemberType.FUNCTION,
                    line_number=node.lineno,
                    docstring=ast.get_docstring(node)
                ))
            
            # Variables and constants
            elif isinstance(node, ast.Assign):
                for target in node.targets:
                    if isinstance(target, ast.Name):
                        # Determine if constant (SCREAMING_SNAKE_CASE)
                        import re
                        is_constant = bool(re.match(r"^[A-Z][A-Z0-9_]*$", target.id))
                        
                        # Check for TypeAlias annotation
                        is_type_alias = False
                        if isinstance(node, ast.AnnAssign):
                            if isinstance(node.annotation, ast.Name):
                                is_type_alias = node.annotation.id == "TypeAlias"
                        
                        member_type = (
                            MemberType.TYPE_ALIAS if is_type_alias
                            else MemberType.CONSTANT if is_constant
                            else MemberType.VARIABLE
                        )
                        
                        symbols.append(ParsedSymbol(
                            name=target.id,
                            member_type=member_type,
                            line_number=node.lineno,
                            docstring=None
                        ))
        
        return symbols
    
    def _extract_imports(self, tree: ast.Module) -> list[str]:
        """Extract import statements as strings."""
        imports = []
        
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    imports.append(f"import {alias.name}")
            
            elif isinstance(node, ast.ImportFrom):
                module = node.module or ""
                for alias in node.names:
                    imports.append(f"from {module} import {alias.name}")
        
        return imports
```

**Testing**:
- Test each symbol type extraction (class, function, variable, constant, type alias)
- Test docstring extraction
- Test line number accuracy
- Test syntax error handling
- Test import extraction
- Test rule engine integration
- Test cache integration

**Files**:
- `tools/lazy_imports/analysis/__init__.py`
- `tools/lazy_imports/analysis/ast_parser.py`
- `tools/tests/lazy_imports/test_ast_parser.py` (20-30 tests)

---

### Days 7-8: Pipeline Orchestrator

**Requirement**: REQ-FUNC-001 (part 3)  
**Priority**: Critical 🔴  
**Effort**: 6-8 hours

**Implementation**:

```python
# New file: tools/lazy_imports/pipeline.py

from pathlib import Path
from dataclasses import dataclass, field
import time
import logging

from tools.lazy_imports.common.types import (
    ExportGenerationResult, GeneratedFile, UpdatedFile, SkippedFile,
    GenerationMetrics
)
from tools.lazy_imports.common.cache import JSONAnalysisCache
from tools.lazy_imports.export_manager.rules import RuleEngine
from tools.lazy_imports.export_manager.graph import PropagationGraph
from tools.lazy_imports.export_manager.generator import CodeGenerator
from tools.lazy_imports.discovery.file_discovery import FileDiscovery
from tools.lazy_imports.analysis.ast_parser import ASTParser

logger = logging.getLogger(__name__)

@dataclass
class PipelineStats:
    """Statistics from pipeline execution."""
    files_discovered: int = 0
    files_analyzed: int = 0
    cache_hits: int = 0
    cache_misses: int = 0
    exports_extracted: int = 0
    manifests_generated: int = 0
    files_written: int = 0
    errors: list[str] = field(default_factory=list)

class Pipeline:
    """Orchestrate the export generation pipeline."""
    
    def __init__(
        self,
        rule_engine: RuleEngine,
        cache: JSONAnalysisCache,
        output_dir: Path
    ):
        self.rule_engine = rule_engine
        self.cache = cache
        self.output_dir = output_dir
        
        # Components
        self.file_discovery = FileDiscovery()
        self.ast_parser = ASTParser(rule_engine)
        self.generator = CodeGenerator(output_dir)
        self.graph = PropagationGraph(rule_engine)
        
        # Stats
        self.stats = PipelineStats()
    
    def run(
        self,
        source_root: Path,
        *,
        dry_run: bool = False,
        module: Path | None = None
    ) -> ExportGenerationResult:
        """Execute full pipeline.
        
        Args:
            source_root: Root directory to process
            dry_run: If True, don't write files
            module: If specified, only process this module
        
        Returns:
            ExportGenerationResult with complete results
        """
        start_time = time.time()
        
        # Step 1: Discover files
        logger.info(f"Discovering Python files in {source_root}")
        search_root = module if module else source_root
        python_files = self.file_discovery.discover_python_files(search_root)
        self.stats.files_discovered = len(python_files)
        logger.info(f"Found {len(python_files)} Python files")
        
        # Step 2: Analyze files and build graph
        logger.info("Analyzing files and building propagation graph")
        for file_path in python_files:
            self._process_file(file_path, source_root)
        
        # Step 3: Get manifests from graph
        logger.info("Generating export manifests")
        manifests = self.graph.get_all_manifests()
        self.stats.manifests_generated = len(manifests)
        
        # Step 4: Generate code
        logger.info(f"Generating code for {len(manifests)} modules")
        generated_files = []
        updated_files = []
        skipped_files = []
        
        for manifest in manifests:
            try:
                code = self.generator.generate(manifest)
                
                if not dry_run:
                    self.generator.write_file(manifest.module_path, code)
                    self.stats.files_written += 1
                
                # Determine if file was created or updated
                target = self.generator._get_target_path(manifest.module_path)
                if target.exists():
                    updated_files.append(UpdatedFile(
                        path=target,
                        old_content="",  # Would need to read for full diff
                        new_content=code.content,
                        changes=[f"Updated {len(manifest.all_exports)} exports"]
                    ))
                else:
                    generated_files.append(GeneratedFile(
                        path=target,
                        content=code.content,
                        exports=manifest.export_names,
                        source_modules=[e.defined_in for e in manifest.all_exports],
                        timestamp=time.time(),
                        hash=code.hash
                    ))
                
            except Exception as e:
                logger.error(f"Failed to generate {manifest.module_path}: {e}")
                self.stats.errors.append(f"{manifest.module_path}: {e}")
        
        # Calculate metrics
        processing_time_ms = int((time.time() - start_time) * 1000)
        cache_hit_rate = (
            self.stats.cache_hits / (self.stats.cache_hits + self.stats.cache_misses)
            if (self.stats.cache_hits + self.stats.cache_misses) > 0
            else 0.0
        )
        
        metrics = GenerationMetrics(
            files_analyzed=self.stats.files_analyzed,
            files_generated=len(generated_files),
            files_updated=len(updated_files),
            files_skipped=len(skipped_files),
            exports_created=self.stats.exports_extracted,
            processing_time_ms=processing_time_ms,
            cache_hit_rate=cache_hit_rate
        )
        
        return ExportGenerationResult(
            generated_files=generated_files,
            updated_files=updated_files,
            skipped_files=skipped_files,
            metrics=metrics,
            success=len(self.stats.errors) == 0,
            errors=self.stats.errors
        )
    
    def _process_file(self, file_path: Path, source_root: Path) -> None:
        """Process a single file (with caching)."""
        import hashlib
        
        # Calculate module path
        relative = file_path.relative_to(source_root)
        # Remove .py and convert to module path
        parts = list(relative.parts[:-1])  # Remove filename
        if relative.stem != "__init__":
            parts.append(relative.stem)
        module_path = ".".join(parts) if parts else "root"
        
        # Check cache
        content = file_path.read_text()
        file_hash = hashlib.sha256(content.encode()).hexdigest()
        
        cached = self.cache.get(file_path, file_hash)
        if cached:
            # Use cached analysis
            self.stats.cache_hits += 1
            analysis = cached
        else:
            # Parse file
            self.stats.cache_misses += 1
            self.stats.files_analyzed += 1
            
            analysis = self.ast_parser.parse_file(file_path, module_path)
            
            # Cache result
            self.cache.put(file_path, file_hash, analysis)
        
        # Add to graph
        self.graph.add_module(module_path)
        for export in analysis.exports:
            self.graph.add_export(module_path, export)
            self.stats.exports_extracted += 1
```

**Testing**:
- Test full pipeline end-to-end
- Test cache integration (first run vs second run)
- Test error handling at each stage
- Test dry-run mode
- Test module filtering
- Test statistics collection

**Files**:
- `tools/lazy_imports/pipeline.py`
- `tools/tests/lazy_imports/test_pipeline.py` (15-20 tests)

---

### Day 8 (continued): CLI Integration

**Requirement**: REQ-FUNC-001 (part 4)  
**Priority**: Critical 🔴  
**Effort**: 2-3 hours

**Implementation**: Update CLI commands to use pipeline

```python
# In tools/lazy_imports/cli.py

@app.command
def analyze(...):
    """Analyze export patterns across the codebase."""
    from tools.lazy_imports.pipeline import Pipeline
    from tools.lazy_imports.export_manager.rules import RuleEngine
    from tools.lazy_imports.common.cache import JSONAnalysisCache
    
    _print_info("Analyzing export patterns...")
    console.print()
    
    # Create pipeline
    rules = RuleEngine()
    rules_path = Path(".codeweaver/lazy_import_rules.yaml")
    if rules_path.exists():
        rules.load_rules([rules_path])
    
    cache = JSONAnalysisCache()
    pipeline = Pipeline(rules, cache, Path.cwd())
    
    # Run analysis (dry-run mode)
    result = pipeline.run(Path("src"), dry_run=True)
    
    # Display results based on format
    if format == "table":
        # ... create table from result.metrics ...
        pass
    elif format == "json":
        # ... output JSON ...
        pass
    else:  # report
        # ... detailed report ...
        pass

@app.command
def generate(...):
    """Generate __init__.py files from export manifests."""
    from tools.lazy_imports.pipeline import Pipeline
    from tools.lazy_imports.export_manager.rules import RuleEngine
    from tools.lazy_imports.common.cache import JSONAnalysisCache
    
    _print_info("Generating exports...")
    console.print()
    
    # Load rules
    rules = RuleEngine()
    rules_path = Path(".codeweaver/lazy_import_rules.yaml")
    if rules_path.exists():
        rules.load_rules([rules_path])
        _print_success(f"Loaded rules from {rules_path}")
    else:
        _print_warning("No rules file found - using defaults")
    
    # Create and run pipeline
    cache = JSONAnalysisCache()
    pipeline = Pipeline(rules, cache, Path.cwd())
    
    result = pipeline.run(
        module or Path("src"),
        dry_run=dry_run
    )
    
    # Display results
    _print_generation_results(result)
    
    if not result.success:
        raise SystemExit(1)
```

**Testing**:
- Integration test: CLI → Pipeline → Output
- Test both analyze and generate commands
- Test with real codebase
- Verify performance targets (REQ-PERF-001, REQ-PERF-002)

---

## Week 3: Polish & Documentation (Days 9-10)

**Goal**: Final touches and documentation

### Day 9: Auto-Fix Completion

**Requirement**: REQ-FUNC-005  
**Priority**: Nice-to-have 🟢  
**Effort**: 3-4 hours

**Expand auto-fix capability to handle more scenarios**:
- Missing imports
- Incorrect __all__ declarations
- TYPE_CHECKING block reorganization
- Import sorting

**Files**: `tools/lazy_imports/validator/fixer.py`

---

### Day 10: Documentation & Final Validation

**Priority**: Important 🟡  
**Effort**: 4-6 hours

**Tasks**:
1. Update README with new implementation
2. Add usage examples
3. Document CLI commands
4. Create troubleshooting guide
5. Final acceptance testing on real codebase
6. Performance validation (REQ-PERF-001, REQ-PERF-002)

**Acceptance Tests**:
```bash
# Test on CodeWeaver itself
$ codeweaver lazy-imports generate --dry-run
# Should complete in <5s for ~500 modules

# Second run should use cache
$ codeweaver lazy-imports generate --dry-run
# Cache hit rate should be >90%

# Validate output
$ codeweaver lazy-imports validate
# Should find no errors
```

---

## Summary & Timeline

### Week-by-Week Breakdown

**Week 1: Critical Fixes (3 days)**
- Day 1: Schema versioning
- Day 2: Circuit breaker
- Day 3: Validator completion

**Week 2: Core Implementation (5 days)**
- Day 4: File discovery
- Days 5-6: AST parser + extractor
- Days 7-8: Pipeline orchestrator + CLI integration

**Week 3: Polish (2 days)**
- Day 9: Auto-fix expansion
- Day 10: Documentation & validation

**Total**: 10 working days

### Effort Summary

| Component | Days | LOC | Tests |
|-----------|------|-----|-------|
| Schema versioning | 0.5 | 50 | 5 |
| Circuit breaker | 0.5 | 100 | 8 |
| Validator completion | 1 | 200 | 15 |
| File discovery | 0.5 | 150 | 10 |
| AST parser | 2 | 400 | 25 |
| Pipeline orchestrator | 1.5 | 300 | 20 |
| CLI integration | 0.5 | 100 | 5 |
| Auto-fix expansion | 0.5 | 150 | 10 |
| Documentation | 1 | - | - |
| **Total** | **8 days** | **1,450** | **98** |

**Buffer**: 2 days for unexpected issues, additional testing, refinement

### Success Metrics

**Functionality**:
- ✅ All CLI commands work end-to-end
- ✅ Can analyze any Python codebase
- ✅ Generates valid __init__.py files
- ✅ Validates generated files successfully

**Performance (REQ-PERF-001, REQ-PERF-002)**:
- ✅ <5s processing time for 500 modules
- ✅ >90% cache hit rate on second run
- ✅ No performance degradation under normal load

**Quality**:
- ✅ 100% test pass rate
- ✅ No critical errors in real-world usage
- ✅ Clear error messages and suggestions
- ✅ Comprehensive documentation

**Compliance**:
- ✅ 100% of valid requirements met
- ✅ All critical gaps addressed
- ✅ Production-ready quality

---

## Risk Mitigation

### Technical Risks

**AST Parsing Complexity** 🟡
- *Risk*: Edge cases in Python AST handling
- *Mitigation*: Comprehensive test suite covering Python 3.9-3.13 syntax
- *Fallback*: Graceful degradation - skip unparsable files with warning

**Performance Targets** 🟡
- *Risk*: May not meet <5s target for large codebases
- *Mitigation*: Aggressive caching, parallel processing if needed
- *Fallback*: Document performance characteristics, optimize in v2.0

**Cache Corruption** 🟢
- *Risk*: Circuit breaker might trigger too often
- *Mitigation*: Tunable thresholds, clear logging
- *Fallback*: Can disable circuit breaker via config

### Schedule Risks

**Optimistic Estimates** 🟡
- *Risk*: Implementation takes longer than estimated
- *Mitigation*: 2-day buffer included, can defer auto-fix expansion
- *Fallback*: Focus on core functionality, defer nice-to-haves

**Testing Overhead** 🟡
- *Risk*: More tests needed than estimated
- *Mitigation*: Write tests alongside implementation
- *Fallback*: Focus on critical path testing first

---

## Appendix: Test Plan

### Unit Tests (98 total)

**Week 1 Components** (28 tests):
- Schema versioning: 5 tests
- Circuit breaker: 8 tests
- Validator: 15 tests

**Week 2 Components** (60 tests):
- File discovery: 10 tests
- AST parser: 25 tests
- Pipeline: 20 tests
- CLI: 5 tests

**Week 3 Components** (10 tests):
- Auto-fix: 10 tests

### Integration Tests (15 tests)

- Full pipeline workflow (5 tests)
- Cache integration (3 tests)
- Error recovery (4 tests)
- Performance benchmarks (3 tests)

### Acceptance Tests (5 scenarios)

1. Generate exports for CodeWeaver codebase
2. Validate all generated files
3. Performance: <5s for 500 modules
4. Cache: >90% hit rate on second run
5. End-to-end: analyze → generate → validate

---

## Approval & Next Steps

### Prerequisites for Starting

- ✅ User approval of this plan
- ✅ Week 2 removal confirmed (old system deprecated)
- ✅ Timeline acceptable (10-12 days)

### Implementation Sequence

1. **Immediate**: Day 1 (Schema versioning)
2. **This week**: Days 1-5 (Critical fixes + core implementation start)
3. **Next week**: Days 6-10 (Complete core + polish)

### Definition of Done

- All code implemented and tested
- 100% test pass rate
- Documentation complete
- Acceptance tests pass on real codebase
- Performance targets met
- User approval for production use

### Communication Plan

- Daily progress updates
- Blockers escalated immediately
- Demo after Week 1 (critical fixes)
- Demo after Week 2 (working end-to-end)
- Final review before production

---

**Status**: PENDING USER APPROVAL  
**Author**: Claude (AI Assistant)  
**Review Date**: 2026-02-14  
**Version**: 2.0
