<!--
SPDX-FileCopyrightText: 2026 Knitli Inc.

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Missing Components - Lazy Import System

**Assessment Date**: 2026-02-14  
**Purpose**: Identify all missing components needed for complete implementation

## Executive Summary

The lazy import system has **most core components implemented**, but **lacks the integration layer** that connects them into a working end-to-end system.

**Status**: 
- ✅ Data models and types (100%)
- ✅ Rule engine and propagation graph (100%)
- ✅ Cache system (100%)
- ✅ Code generator (100%)
- ✅ Validator (100%)
- ✅ Migration tool (100%)
- ❌ File discovery and AST parsing (0%)
- ❌ Pipeline orchestration (0%)
- ❌ CLI integration (30% - structure exists, implementation missing)

## What Exists (Complete)

### 1. Core Data Models ✅
**Location**: `tools/lazy_imports/common/types.py`  
**Status**: Complete (800 lines)  
**Components**:
- PropagationLevel, RuleAction, MemberType enums
- ExportNode, ExportManifest data structures
- Rule system types (Rule, RuleMatchCriteria, RuleEvaluationResult)
- Generation results (GeneratedFile, UpdatedFile, GenerationMetrics)
- Validation results (ValidationError, ValidationWarning, ValidationReport)
- Cache types (AnalysisResult, CacheEntry, CacheStatistics)

### 2. Rule Engine ✅
**Location**: `tools/lazy_imports/export_manager/rules.py`  
**Status**: Complete and tested (146/146 tests pass)  
**Capabilities**:
- YAML rule loading with schema validation
- Priority-based rule evaluation
- Pattern matching (regex, exact, member type)
- Module-level overrides
- Comprehensive test coverage

### 3. Propagation Graph ✅
**Location**: `tools/lazy_imports/export_manager/graph.py`  
**Status**: Complete and tested  
**Capabilities**:
- Bottom-up export propagation
- Parent/Root propagation levels
- Export manifest generation
- Module hierarchy management
- Tested with all propagation scenarios

### 4. JSON Analysis Cache ✅
**Location**: `tools/lazy_imports/common/cache.py`  
**Status**: Complete (needs circuit breaker - see remediation)  
**Capabilities**:
- SHA-256 hash-based caching
- File-based persistence
- Cache invalidation
- Statistics tracking
- Corruption recovery

### 5. Code Generator ✅
**Location**: `tools/lazy_imports/export_manager/generator.py`  
**Status**: Complete (600+ lines, fully implemented)  
**Capabilities**:
- Sentinel-based manual code preservation
- TYPE_CHECKING import generation
- Sorted __all__ declarations
- Atomic writes with backup/rollback
- Syntax validation
- Import organization (absolute/relative)

### 6. Validator ✅
**Location**: `tools/lazy_imports/validator/validator.py`  
**Status**: Complete (needs expansion - see remediation)  
**Capabilities**:
- Import validation
- Consistency checking
- Syntax error detection
- File-level validation
- Multi-file validation reports

### 7. Auto-Fixer ✅
**Location**: `tools/lazy_imports/validator/fixer.py`  
**Status**: Complete (needs expansion - see remediation)  
**Capabilities**:
- Basic auto-fix capability
- Dry-run mode
- Backup creation

### 8. Migration Tool ✅
**Location**: `tools/lazy_imports/migration.py`  
**Status**: Complete (600+ lines, fully implemented)  
**Capabilities**:
- Extract rules from old hardcoded system
- Generate YAML configuration
- Module override extraction
- Equivalence verification
- Migration report generation

## What's Missing (Critical Gaps)

### 1. File Discovery Service ❌
**Status**: Not implemented  
**Required for**: `analyze` and `generate` commands  
**Purpose**: Walk source tree and find Python files to process

**Needed Functionality**:
```python
class FileDiscovery:
    """Discover Python files in source tree."""
    
    def discover_python_files(
        self, 
        root: Path,
        *,
        respect_gitignore: bool = True,
        include_patterns: list[str] | None = None,
        exclude_patterns: list[str] | None = None
    ) -> list[Path]:
        """Find all Python files in directory tree.
        
        Features needed:
        - Recursive directory walking
        - .gitignore respect
        - Pattern filtering (include/exclude)
        - __pycache__ exclusion
        - .py file detection
        """
```

**Implementation Approach**:
- Use `pathlib.Path.rglob()` for directory walking
- Use `gitignore-parser` or similar for .gitignore support
- Pattern matching with `fnmatch` or `re`
- Return list of discovered file paths

**Estimated Effort**: 2-3 hours (150-200 lines)

### 2. AST Parser Service ❌
**Status**: Not implemented  
**Required for**: `analyze` and `generate` commands  
**Purpose**: Parse Python files and extract symbol definitions

**Needed Functionality**:
```python
class ASTParser:
    """Parse Python files and extract exports."""
    
    def parse_file(self, file_path: Path) -> ParseResult:
        """Parse a Python file and extract exports.
        
        Must extract:
        - Classes (with docstrings, line numbers)
        - Functions (top-level only)
        - Variables (module-level)
        - Constants (SCREAMING_SNAKE_CASE detection)
        - Type aliases (TypeAlias annotation detection)
        
        Returns:
            ParseResult with:
            - List of exported symbols
            - Import statements
            - File metadata (hash, timestamp)
            - Syntax errors if any
        """
    
    def extract_exports(self, tree: ast.Module, file_path: Path) -> list[ExportNode]:
        """Convert AST nodes to ExportNode objects.
        
        For each symbol:
        - Determine member_type (CLASS, FUNCTION, VARIABLE, etc.)
        - Extract docstring
        - Get line number
        - Determine defined_in module path
        - Set initial propagation (from rules)
        """
```

**Implementation Details**:
- Use `ast.parse()` to parse Python source
- Walk AST with `ast.NodeVisitor` or `ast.walk()`
- Extract:
  - Classes: `ast.ClassDef` nodes
  - Functions: `ast.FunctionDef` nodes (top-level only)
  - Variables: `ast.Assign` with `ast.Name` targets
  - Constants: Variables matching `^[A-Z][A-Z0-9_]*$`
  - Type aliases: Assignments with `TypeAlias` annotation
- Get docstrings using `ast.get_docstring()`
- Get line numbers from `node.lineno`

**Estimated Effort**: 4-6 hours (300-400 lines)

### 3. Export Extractor ❌
**Status**: Not implemented (part of AST Parser)  
**Required for**: Converting AST nodes to ExportNode objects  
**Purpose**: Bridge between AST and our data model

**Needed Functionality**:
```python
class ExportExtractor:
    """Extract ExportNode objects from AST."""
    
    def __init__(self, rule_engine: RuleEngine):
        self.rule_engine = rule_engine
    
    def extract_from_ast(
        self,
        tree: ast.Module,
        file_path: Path,
        module_path: str
    ) -> list[ExportNode]:
        """Convert AST to ExportNode objects.
        
        For each symbol:
        1. Determine member_type
        2. Extract metadata (docstring, line number)
        3. Apply rule engine to determine propagation
        4. Create ExportNode
        """
```

**Implementation Details**:
- Integrate with AST Parser
- Use RuleEngine to determine initial propagation level
- Create ExportNode objects with all required fields
- Handle special cases (constants, type aliases)

**Estimated Effort**: 2-3 hours (150-200 lines, integrated with AST Parser)

### 4. Pipeline Orchestrator ❌
**Status**: Not implemented  
**Required for**: Coordinating the full workflow  
**Purpose**: Tie all components together into working system

**Needed Functionality**:
```python
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
        self.file_discovery = FileDiscovery()
        self.ast_parser = ASTParser(rule_engine)
        self.generator = CodeGenerator(output_dir)
    
    def run(
        self,
        source_root: Path,
        *,
        dry_run: bool = False
    ) -> ExportGenerationResult:
        """Execute full pipeline.
        
        Steps:
        1. Discover Python files
        2. For each file:
           a. Check cache
           b. Parse if needed
           c. Extract exports
           d. Store in cache
        3. Build propagation graph
        4. Generate manifests
        5. Generate code
        6. Write files (if not dry_run)
        7. Return results
        """
```

**Implementation Details**:
- Coordinate all services
- Handle errors at each stage
- Progress reporting
- Cache management
- Metrics collection
- Dry-run support

**Estimated Effort**: 4-6 hours (250-350 lines)

### 5. CLI Integration ❌
**Status**: Partially implemented (structure exists, calls missing)  
**Required for**: User interaction  
**Purpose**: Connect CLI commands to pipeline

**What Exists**:
- ✅ CLI structure (`cli.py` with cyclopts)
- ✅ Command definitions (analyze, generate, validate, migrate, etc.)
- ✅ Output formatting helpers
- ✅ Result printing functions

**What's Missing**:
```python
# In cli.py analyze() command:
def analyze(...):
    # REPLACE this placeholder:
    _print_warning("Note: This is sample data - full implementation pending")
    
    # WITH this implementation:
    from tools.lazy_imports.pipeline import Pipeline
    
    # Create pipeline
    pipeline = Pipeline(
        rule_engine=RuleEngine(),
        cache=JSONAnalysisCache(),
        output_dir=Path.cwd()
    )
    
    # Run analysis
    result = pipeline.run(source_root, dry_run=True)
    
    # Display statistics
    _print_generation_results(result)

# In cli.py generate() command:
def generate(...):
    # REPLACE the TODO and placeholder with actual pipeline execution
    pipeline = Pipeline(...)
    result = pipeline.run(source_root, dry_run=dry_run)
    
    if result.success:
        _print_success(f"Generated {result.metrics.files_generated} files")
        _print_generation_results(result)
    else:
        _print_error("Generation failed")
        for error in result.errors:
            _print_error(error)
```

**Estimated Effort**: 2-3 hours (updating CLI commands)

## Implementation Dependencies

```
File Discovery (no dependencies)
    ↓
AST Parser (needs: RuleEngine for propagation)
    ↓
Pipeline Orchestrator (needs: all above + CodeGenerator + Cache)
    ↓
CLI Integration (needs: Pipeline)
```

## Total Effort Estimate

| Component | Effort | Lines of Code |
|-----------|--------|---------------|
| File Discovery | 2-3 hours | 150-200 |
| AST Parser + Extractor | 6-9 hours | 450-600 |
| Pipeline Orchestrator | 4-6 hours | 250-350 |
| CLI Integration | 2-3 hours | 100-150 |
| **Total** | **14-21 hours** | **950-1,300** |

**Testing overhead**: Add 30-50% for comprehensive tests → **Total: 18-32 hours**

## Risk Assessment

### Low Risk ✅
- File discovery (standard library operations)
- CLI integration (structure exists, just fill in calls)

### Medium Risk ⚠️
- AST parsing (complex but well-documented)
- Pipeline orchestration (many moving parts)

### High Risk 🚨
- None identified (all components are independent and testable)

## Success Criteria

### For File Discovery
- ✅ Finds all .py files in source tree
- ✅ Respects .gitignore
- ✅ Excludes __pycache__ directories
- ✅ Supports include/exclude patterns
- ✅ Returns sorted, deduplicated list

### For AST Parser
- ✅ Parses valid Python files without errors
- ✅ Extracts all symbol types (class, function, variable, constant, type alias)
- ✅ Gets accurate line numbers and docstrings
- ✅ Handles syntax errors gracefully
- ✅ Works with cache system

### For Pipeline
- ✅ Runs full workflow end-to-end
- ✅ Uses cache effectively (>90% hit rate on second run)
- ✅ Handles errors at each stage
- ✅ Reports accurate metrics
- ✅ Supports dry-run mode

### For CLI Integration
- ✅ `analyze` command shows real statistics
- ✅ `generate` command creates __init__.py files
- ✅ Both commands use the same pipeline
- ✅ Error messages are clear and actionable

## Validation Plan

### Unit Tests
- File discovery: 10-15 test cases
- AST parser: 20-30 test cases (one per symbol type + edge cases)
- Pipeline: 15-20 test cases (full workflow + error scenarios)

### Integration Tests
- End-to-end: Analyze → Generate → Validate cycle
- Cache effectiveness: First run vs second run
- Error recovery: Syntax errors, missing files, etc.

### Acceptance Tests
- Real codebase: Run on CodeWeaver itself
- Performance: <5s for 500 modules (REQ-PERF-001)
- Cache hit rate: >90% (REQ-PERF-002)

## Next Steps

1. **Immediate**: Implement File Discovery service (2-3 hours)
2. **Next**: Implement AST Parser + Extractor (6-9 hours)
3. **Then**: Implement Pipeline Orchestrator (4-6 hours)
4. **Finally**: Integrate with CLI (2-3 hours)
5. **Validate**: Run comprehensive test suite and acceptance tests

## Appendix: Example Workflow

### Current (Broken)
```bash
$ codeweaver lazy-imports analyze
# Shows hardcoded sample data ❌
```

### Target (Working)
```bash
$ codeweaver lazy-imports analyze
ℹ Analyzing export patterns...

Files analyzed: 347
Modules processed: 52
Exports found: 1,245
  - Classes: 423
  - Functions: 687
  - Constants: 89
  - Type Aliases: 46

Top exporters:
  codeweaver.core.types: 87 exports (45 own, 42 propagated)
  codeweaver.providers: 134 exports (23 own, 111 propagated)
  codeweaver: 298 exports (5 own, 293 propagated)

Cache hit rate: 94.2%
Processing time: 2.3s

✓ Analysis complete
```

### Example Generate Flow
```bash
$ codeweaver lazy-imports generate
ℹ Generating exports...
ℹ Loading export rules...
✓ Loaded rules from .codeweaver/lazy_import_rules.yaml
ℹ Building export propagation graph...
ℹ Analyzing codebase in src...

Files analyzed: 347
Files generated: 52
Files updated: 12
Files skipped: 283 (cached)
Exports created: 1,245
Processing time: 3.1s
Cache hit rate: 81.6%

✓ Export generation completed successfully
```
