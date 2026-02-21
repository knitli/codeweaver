<!--
SPDX-FileCopyrightText: 2026 Knitli Inc.

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Lazy Import System - Remediation Plan

**Purpose:** Actionable plan to address compliance gaps and achieve production readiness
**Target Date:** 2026-03-01 (15 business days)
**Current Compliance:** 64%
**Target Compliance:** 100% (all MUST requirements)

---

## Overview

This plan addresses the 8 gaps identified in the QA compliance review, organized into 3 priority levels. Each item includes specific implementation guidance, test requirements, and acceptance criteria.

---

## Priority 1: Critical Blockers (Week 1)

These items are **production blockers** that must be completed before launch.

### 1. Migration Validation Workflow (REQ-COMPAT-001)

**Requirement:** New system SHALL produce identical output to old system
**Gap:** Migration tool exists but no validation workflow
**Effort:** 2-3 days
**Owner:** TBD

#### Implementation

**File:** `tools/lazy_imports/migration.py`

```python
def verify_migration(
    old_script: Path,
    new_config: Path,
    modules: list[Path]
) -> MigrationValidationReport:
    """Verify new system produces identical output to old.

    Process:
    1. Extract exports using old system
    2. Generate exports using new system
    3. Compare outputs module-by-module
    4. Report discrepancies
    """

    results = []
    for module in modules:
        old_exports = extract_old_exports(module)
        new_exports = generate_new_exports(module, new_config)

        match = compare_exports(old_exports, new_exports)
        results.append(match)

    return MigrationValidationReport(
        total_modules=len(modules),
        matched=sum(r.matched for r in results),
        discrepancies=[r for r in results if not r.matched],
        match_rate=sum(r.matched for r in results) / len(modules)
    )
```

**CLI Integration:**

```bash
# Add to cli.py
@app.command
def migrate(
    validate: bool = True,
    output: Path = DEFAULT_OUTPUT,
    dry_run: bool = False
) -> None:
    """Migrate from old system to new YAML rules.

    Examples:
        codeweaver lazy-imports migrate --validate
        codeweaver lazy-imports migrate --dry-run
    """
    migrator = RuleMigrator()
    result = migrator.migrate()

    if validate:
        # Run validation
        report = verify_migration(
            OLD_SCRIPT,
            output,
            get_all_modules()
        )

        if report.match_rate < 1.0:
            console.print(f"[red]Validation failed: {report.match_rate:.1%} match rate[/red]")
            for discrepancy in report.discrepancies:
                console.print(f"  {discrepancy.module}: {discrepancy.reason}")
            return

        console.print("[green]✓ Migration validated: 100% match[/green]")
```

#### Tests Required

**File:** `tools/tests/lazy_imports/test_migration.py`

```python
def test_verify_migration_perfect_match(tmp_path):
    """Should report 100% match for identical outputs."""
    # Setup old and new configs
    # Run verification
    report = verify_migration(old_script, new_config, modules)

    assert report.match_rate == 1.0
    assert len(report.discrepancies) == 0

def test_verify_migration_detects_discrepancy(tmp_path):
    """Should detect when outputs differ."""
    # Setup configs with known difference
    report = verify_migration(old_script, new_config, modules)

    assert report.match_rate < 1.0
    assert len(report.discrepancies) > 0
    assert "module.name" in report.discrepancies[0].module

def test_migration_validation_command(tmp_path, cli_runner):
    """CLI migrate --validate should run verification."""
    result = cli_runner.invoke(app, ["migrate", "--validate"])

    assert result.exit_code == 0
    assert "100% match" in result.output
```

#### Acceptance Criteria

- [ ] `verify_migration()` function implemented
- [ ] CLI `migrate --validate` command working
- [ ] Validation runs on all 347 modules in codebase
- [ ] Report shows 100% match OR documented exceptions
- [ ] Tests cover perfect match and discrepancy detection
- [ ] Documentation in MIGRATION.md updated

---

### 2. Schema Versioning Enforcement (REQ-CONFIG-002)

**Requirement:** Configuration files SHALL include schema version with enforcement
**Gap:** Version field exists but not validated
**Effort:** 1-2 days
**Owner:** TBD

#### Implementation

**File:** `tools/lazy_imports/export_manager/rules.py`

```python
# Constants
SUPPORTED_SCHEMA_VERSIONS = ["1.0", "1.1"]
CURRENT_SCHEMA_VERSION = "1.1"
MINIMUM_SCHEMA_VERSION = "1.0"

class UnsupportedSchemaVersion(Exception):
    """Raised when schema version is not supported."""
    pass

def load_rules(rule_file: Path) -> list[Rule]:
    """Load rules from YAML file with schema validation.

    Raises:
        UnsupportedSchemaVersion: If schema version unsupported
    """
    with rule_file.open() as f:
        data = yaml.safe_load(f)

    schema_version = data.get("schema_version")

    if not schema_version:
        raise ValueError(
            f"Missing schema_version in {rule_file}\n"
            f"Add: schema_version: \"{CURRENT_SCHEMA_VERSION}\""
        )

    if schema_version not in SUPPORTED_SCHEMA_VERSIONS:
        raise UnsupportedSchemaVersion(
            f"Unsupported schema version: {schema_version}\n"
            f"File: {rule_file}\n"
            f"Supported versions: {', '.join(SUPPORTED_SCHEMA_VERSIONS)}\n\n"
            f"This file uses schema version {schema_version} which is no longer supported.\n"
            f"Please migrate to version {CURRENT_SCHEMA_VERSION}.\n\n"
            f"Migration command:\n"
            f"  codeweaver lazy-imports migrate-schema {rule_file}"
        )

    # Proceed with rule loading...
```

**Migration Tool:**

```python
@app.command
def migrate_schema(
    rule_file: Path,
    target_version: str = CURRENT_SCHEMA_VERSION
) -> None:
    """Migrate rule file to newer schema version.

    Examples:
        codeweaver lazy-imports migrate-schema rules.yaml
        codeweaver lazy-imports migrate-schema rules.yaml --target-version 1.1
    """
    migrator = SchemaMigrator()
    result = migrator.migrate(rule_file, target_version)

    if result.success:
        console.print(f"[green]✓ Migrated {rule_file} to version {target_version}[/green]")
    else:
        console.print(f"[red]✗ Migration failed: {result.error}[/red]")
```

#### Tests Required

**File:** `tools/tests/lazy_imports/test_rules.py`

```python
def test_load_rules_validates_schema_version(tmp_path):
    """Should validate schema version on load."""
    rule_file = tmp_path / "rules.yaml"
    rule_file.write_text("""
schema_version: "1.0"
rules:
  - name: test
    priority: 500
    action: include
""")

    rules = load_rules(rule_file)
    assert len(rules) > 0

def test_load_rules_rejects_unsupported_version(tmp_path):
    """Should reject unsupported schema version."""
    rule_file = tmp_path / "rules.yaml"
    rule_file.write_text("""
schema_version: "99.0"
rules: []
""")

    with pytest.raises(UnsupportedSchemaVersion) as exc:
        load_rules(rule_file)

    assert "99.0" in str(exc.value)
    assert "Supported versions:" in str(exc.value)

def test_load_rules_requires_schema_version(tmp_path):
    """Should require schema_version field."""
    rule_file = tmp_path / "rules.yaml"
    rule_file.write_text("rules: []")

    with pytest.raises(ValueError) as exc:
        load_rules(rule_file)

    assert "schema_version" in str(exc.value)

def test_schema_migration_command(tmp_path, cli_runner):
    """Should migrate schema version."""
    rule_file = tmp_path / "rules.yaml"
    rule_file.write_text('schema_version: "1.0"\\nrules: []')

    result = cli_runner.invoke(app, ["migrate-schema", str(rule_file)])

    assert result.exit_code == 0
    assert "Migrated" in result.output
```

#### Acceptance Criteria

- [ ] `load_rules()` validates schema version
- [ ] Unsupported versions rejected with actionable error
- [ ] Error message shows supported versions and migration command
- [ ] `migrate-schema` command implemented
- [ ] Tests cover validation, rejection, and migration
- [ ] Documentation updated with version policy

---

### 3. Cache Circuit Breaker (REQ-ERROR-003)

**Requirement:** System SHALL open circuit breaker after 3 consecutive failures
**Gap:** Not implemented
**Effort:** 1 day
**Owner:** TBD

#### Implementation

**File:** `tools/lazy_imports/common/cache.py`

```python
class JSONAnalysisCache:
    """Cache with circuit breaker pattern."""

    CIRCUIT_BREAKER_THRESHOLD = 3

    def __init__(self, cache_dir: Path | None = None) -> None:
        self._cache_dir = cache_dir or Path(".codeweaver/cache")
        self._cache: dict[Path, dict] = {}

        # Circuit breaker state
        self._consecutive_failures = 0
        self._circuit_open = False

        self._load_from_disk()

    def get(self, file_path: Path, file_hash: str):
        """Get cached analysis with circuit breaker."""
        # If circuit open, bypass cache
        if self._circuit_open:
            return None

        try:
            result = self._get_internal(file_path, file_hash)
            self._on_success()
            return result
        except Exception as e:
            self._on_failure(e)
            return None

    def put(self, file_path: Path, file_hash: str, analysis) -> None:
        """Store in cache with circuit breaker."""
        if self._circuit_open:
            # Log but don't fail
            logger.warning("Cache circuit open, skipping write")
            return

        try:
            self._put_internal(file_path, file_hash, analysis)
            self._on_success()
        except Exception as e:
            self._on_failure(e)

    def _on_success(self) -> None:
        """Reset failure counter on success."""
        if self._consecutive_failures > 0:
            self._consecutive_failures = 0
            if self._circuit_open:
                logger.info("Cache circuit closed, resuming normal operation")
                self._circuit_open = False

    def _on_failure(self, error: Exception) -> None:
        """Track failures and open circuit if threshold exceeded."""
        self._consecutive_failures += 1

        logger.warning(
            f"Cache operation failed ({self._consecutive_failures}/{self.CIRCUIT_BREAKER_THRESHOLD}): {error}"
        )

        if self._consecutive_failures >= self.CIRCUIT_BREAKER_THRESHOLD:
            if not self._circuit_open:
                logger.warning(
                    f"Cache circuit opened after {self._consecutive_failures} failures. "
                    f"Bypassing cache for remaining operations. "
                    f"Circuit will reset on next run."
                )
                self._circuit_open = True
```

#### Tests Required

**File:** `tools/tests/lazy_imports/test_cache.py`

```python
def test_circuit_breaker_opens_after_threshold(temp_cache_dir, monkeypatch):
    """Should open circuit after 3 consecutive failures."""
    cache = JSONAnalysisCache(cache_dir=temp_cache_dir)

    # Mock _get_internal to always fail
    def failing_get(*args):
        raise RuntimeError("Cache failure")

    monkeypatch.setattr(cache, "_get_internal", failing_get)

    # First 2 failures - circuit remains closed
    cache.get(Path("test1.py"), "hash1")
    assert not cache._circuit_open

    cache.get(Path("test2.py"), "hash2")
    assert not cache._circuit_open

    # 3rd failure - circuit opens
    cache.get(Path("test3.py"), "hash3")
    assert cache._circuit_open

def test_circuit_breaker_bypasses_on_open(temp_cache_dir):
    """Should bypass cache when circuit is open."""
    cache = JSONAnalysisCache(cache_dir=temp_cache_dir)
    cache._circuit_open = True

    # Should return None immediately without attempting cache access
    result = cache.get(Path("test.py"), "hash")
    assert result is None

def test_circuit_breaker_resets_on_success(temp_cache_dir, monkeypatch):
    """Should reset failure counter on successful operation."""
    cache = JSONAnalysisCache(cache_dir=temp_cache_dir)
    cache._consecutive_failures = 2

    # Successful operation
    cache.put(Path("test.py"), "hash", mock_analysis)

    assert cache._consecutive_failures == 0
    assert not cache._circuit_open
```

#### Acceptance Criteria

- [ ] Circuit breaker pattern implemented in cache
- [ ] Opens after 3 consecutive failures
- [ ] Bypasses cache when open
- [ ] Resets on next successful operation
- [ ] Logs warnings appropriately
- [ ] Tests cover all scenarios

---

### 4. Complete Validator Implementation (REQ-VALID-001, REQ-VALID-002)

**Requirements:**
- REQ-VALID-001: Detect broken lazy_import() calls
- REQ-VALID-002: Validate package consistency

**Gap:** Validator structure exists but incomplete
**Effort:** 3-4 days
**Owner:** TBD

#### Implementation

**File:** `tools/lazy_imports/validator/validator.py`

```python
class LazyImportValidator:
    """Comprehensive lazy import validation."""

    def validate_project(self, project_root: Path) -> ValidationReport:
        """Run all validations on project.

        Checks:
        1. All lazy_import() calls resolve
        2. __all__ matches _dynamic_imports
        3. TYPE_CHECKING imports exist
        4. No circular dependencies
        """
        errors = []
        warnings = []

        # Find all Python files
        files = list(project_root.rglob("*.py"))

        # Validate each file
        for file in files:
            # Check lazy_import calls
            call_issues = self.resolver.validate_calls(file)
            errors.extend(call_issues)

            # Check package consistency
            if file.name == "__init__.py":
                consistency_issues = self.consistency_checker.check_package(file)
                errors.extend(e for e in consistency_issues if e.severity == "error")
                warnings.extend(w for w in consistency_issues if w.severity == "warning")

        return ValidationReport(
            errors=errors,
            warnings=warnings,
            metrics=self._compute_metrics(files, errors, warnings),
            success=len(errors) == 0
        )
```

**File:** `tools/lazy_imports/validator/resolver.py`

```python
class ImportResolver:
    """Resolve and validate import statements."""

    def validate_calls(self, file: Path) -> list[ValidationError]:
        """Validate all lazy_import() calls in file."""
        errors = []

        # Parse file
        tree = ast.parse(file.read_text(), str(file))

        # Find lazy_import calls
        for node in ast.walk(tree):
            if isinstance(node, ast.Call):
                if self._is_lazy_import_call(node):
                    error = self._validate_lazy_import(node, file)
                    if error:
                        errors.append(error)

        return errors

    def _validate_lazy_import(self, node: ast.Call, file: Path) -> ValidationError | None:
        """Validate a single lazy_import() call."""
        # Extract arguments
        if len(node.args) < 2:
            return ValidationError(
                file=file,
                line=node.lineno,
                message="lazy_import() requires 2 arguments: (module, name)",
                code="LAZY_IMPORT_ARGS"
            )

        module_arg = node.args[0]
        name_arg = node.args[1]

        # Validate module exists
        if isinstance(module_arg, ast.Constant):
            module = module_arg.value
            if not self._module_exists(module):
                return ValidationError(
                    file=file,
                    line=node.lineno,
                    message=f"Module not found: {module}",
                    suggestion=f"Check if module '{module}' is installed or spelled correctly",
                    code="MODULE_NOT_FOUND"
                )

        # Validate name is importable
        if isinstance(name_arg, ast.Constant):
            name = name_arg.value
            if not self._name_importable(module, name):
                return ValidationError(
                    file=file,
                    line=node.lineno,
                    message=f"Cannot import '{name}' from '{module}'",
                    suggestion=f"Check if '{name}' is exported from '{module}'",
                    code="NAME_NOT_IMPORTABLE"
                )

        return None
```

**File:** `tools/lazy_imports/validator/consistency.py`

```python
class ConsistencyChecker:
    """Check package __init__.py consistency."""

    def check_package(self, init_file: Path) -> list[ConsistencyIssue]:
        """Validate package __init__.py consistency."""
        issues = []

        # Parse file
        content = init_file.read_text()
        tree = ast.parse(content, str(init_file))

        # Extract __all__
        all_names = self._extract_all(tree)

        # Extract _dynamic_imports
        dynamic_imports = self._extract_dynamic_imports(tree)

        # Check consistency
        if set(all_names) != set(dynamic_imports.keys()):
            missing_in_all = set(dynamic_imports.keys()) - set(all_names)
            missing_in_dynamic = set(all_names) - set(dynamic_imports.keys())

            if missing_in_all:
                issues.append(ConsistencyIssue(
                    file=init_file,
                    line=0,
                    severity="error",
                    message=f"Names in _dynamic_imports but not __all__: {missing_in_all}",
                    code="MISSING_IN_ALL"
                ))

            if missing_in_dynamic:
                issues.append(ConsistencyIssue(
                    file=init_file,
                    line=0,
                    severity="error",
                    message=f"Names in __all__ but not _dynamic_imports: {missing_in_dynamic}",
                    code="MISSING_IN_DYNAMIC"
                ))

        # Check TYPE_CHECKING imports
        type_checking_imports = self._extract_type_checking_imports(tree)
        for name in all_names:
            if name not in type_checking_imports:
                issues.append(ConsistencyIssue(
                    file=init_file,
                    line=0,
                    severity="warning",
                    message=f"Missing TYPE_CHECKING import for: {name}",
                    code="MISSING_TYPE_IMPORT"
                ))

        return issues
```

#### Tests Required

**File:** `tools/tests/lazy_imports/test_validator.py`

```python
def test_validate_broken_lazy_import(tmp_path):
    """Should detect broken lazy_import() call."""
    test_file = tmp_path / "test.py"
    test_file.write_text('''
lazy_import("nonexistent.module", "Class")
''')

    validator = LazyImportValidator(tmp_path)
    errors = validator.resolver.validate_calls(test_file)

    assert len(errors) == 1
    assert "nonexistent.module" in errors[0].message
    assert errors[0].code == "MODULE_NOT_FOUND"

def test_validate_package_consistency(tmp_path):
    """Should detect __all__ and _dynamic_imports mismatch."""
    init_file = tmp_path / "__init__.py"
    init_file.write_text('''
__all__ = ["Foo", "Bar"]

_dynamic_imports = {
    "Foo": ("module", "Foo"),
    # Missing Bar!
}
''')

    checker = ConsistencyChecker(tmp_path)
    issues = checker.check_package(init_file)

    assert len(issues) > 0
    assert any("Bar" in issue.message for issue in issues)

def test_validator_full_project(tmp_path):
    """Should validate entire project."""
    # Create test project structure
    create_test_project(tmp_path)

    validator = LazyImportValidator(tmp_path)
    report = validator.validate_project(tmp_path)

    assert report.success or len(report.errors) > 0
    assert report.metrics.files_validated > 0
```

#### Acceptance Criteria

- [ ] `ImportResolver.validate_calls()` detects broken imports
- [ ] `ConsistencyChecker.check_package()` validates consistency
- [ ] `LazyImportValidator.validate_project()` runs full validation
- [ ] Error messages include file, line, message, suggestion
- [ ] Tests cover broken imports and consistency issues
- [ ] CLI `validate` command uses validator

---

## Priority 2: Important (Week 2)

### 5. Define Backward Compatibility Timeline (REQ-COMPAT-002)

**Effort:** 1 day
**Owner:** TBD

#### Deliverables

**File:** `tools/lazy_imports/MIGRATION.md`

```markdown
## Backward Compatibility Timeline

### Version 0.9.0 (Current)
- New YAML-based system is default
- Old system available with `--legacy` flag
- Both systems tested in CI

### Version 0.10.0 (Q2 2026)
- Old system deprecated with warning
- Warning shown on every use
- Still functional but not recommended

### Version 0.11.0 (Q3 2026)
- Old system removed
- Migration required
- Breaking change

### Migration Support

Users have 2 full release cycles (6+ months) to migrate.

**Migration command:**
```bash
codeweaver lazy-imports migrate --validate
```

**Rollback:**
If migration fails, rollback by:
1. Delete `.codeweaver/lazy_import_rules.yaml`
2. Restore `exports_config.json.pre-v0.9.0`
3. Use `--legacy` flag until migration resolved
```

#### Tests Required

```python
def test_legacy_mode_still_works():
    """Legacy mode should work until v0.11.0."""
    result = cli_runner.invoke(app, ["--legacy", "generate"])
    assert result.exit_code == 0

def test_deprecation_warning_shown():
    """Should show deprecation warning in v0.10.0."""
    result = cli_runner.invoke(app, ["--legacy", "generate"])
    assert "deprecated" in result.output.lower()
```

#### Acceptance Criteria

- [ ] MIGRATION.md documents timeline
- [ ] `--legacy` flag implemented
- [ ] Deprecation warnings added
- [ ] Tests verify legacy mode works
- [ ] Version milestones documented

---

### 6. Enhance Error Messages (REQ-ERROR-001)

**Effort:** 2 days
**Owner:** TBD

#### Implementation

**File:** `tools/lazy_imports/export_manager/rules.py`

```python
def load_rules(rule_file: Path) -> list[Rule]:
    """Load rules with actionable error messages."""
    try:
        with rule_file.open() as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        # Enhanced YAML error
        raise ValueError(
            f"❌ Error loading rules from {rule_file}\\n\\n"
            f"Line {e.problem_mark.line}: {e.problem}\\n"
            f"{e.problem_mark.get_snippet()}\\n\\n"
            f"Suggestions:\\n"
            f"- Check for missing quotes, colons, or indentation\\n"
            f"- Validate YAML at: https://www.yamllint.com/\\n"
            f"- Restore from backup: {rule_file}.bak"
        ) from e

    # Schema validation with helpful errors
    try:
        validate_schema(data)
    except SchemaValidationError as e:
        raise ValueError(
            f"❌ Schema validation failed for {rule_file}\\n\\n"
            f"Error: {e.message}\\n"
            f"Field: {e.field_path}\\n\\n"
            f"Expected: {e.expected}\\n"
            f"Got: {e.actual}\\n\\n"
            f"Fix: {e.suggestion}"
        ) from e
```

#### Tests Required

```python
def test_yaml_error_shows_line_number(tmp_path):
    """YAML errors should show line number."""
    rule_file = tmp_path / "rules.yaml"
    rule_file.write_text('name: "unclosed')

    with pytest.raises(ValueError) as exc:
        load_rules(rule_file)

    assert "Line" in str(exc.value)
    assert "unclosed" in str(exc.value)
    assert "Suggestions:" in str(exc.value)
```

#### Acceptance Criteria

- [ ] Error messages include file, line, and context
- [ ] Suggestions provided for common mistakes
- [ ] YAML errors show snippet
- [ ] Schema errors show expected vs actual
- [ ] Tests verify error format

---

## Priority 3: Nice-to-Have (Week 2)

### 7. Add Debug Mode (REQ-UX-001)

**Effort:** 2 days
**Owner:** TBD

#### Implementation

```python
@app.command
def debug(
    symbol: str,
    module: str | None = None
) -> None:
    """Debug rule evaluation for a symbol.

    Shows:
    - All rules evaluated in priority order
    - Match/skip decision for each rule
    - Final decision and propagation
    - Where export will appear

    Examples:
        codeweaver lazy-imports debug MyClass --module codeweaver.core.types
    """
    engine = RuleEngine()
    engine.load_rules_from_config()

    console.print(f"\\nEvaluating export: [bold]{symbol}[/bold]", end="")
    if module:
        console.print(f" ([cyan]{module}[/cyan])")
    console.print()

    console.print("\\n[bold]Rule evaluation order:[/bold]")

    # Show all rules in priority order
    for rule in engine.rules:
        result = engine._evaluate_single_rule(rule, symbol, module or "unknown")

        if result.matched:
            console.print(f"  ✓ MATCH [P{rule.priority}] {rule.name} → {result.action}")
            console.print(f"       Reason: {result.reason}")
            if result.propagation:
                console.print(f"       Propagate: {result.propagation}")
        else:
            console.print(f"  ✓ SKIP [P{rule.priority}] {rule.name}")

    # Show final decision
    final = engine.evaluate(symbol, module or "unknown", MemberType.CLASS)
    console.print(f"\\n[bold]Final decision:[/bold] {final.action}")
    if final.propagation:
        console.print(f"Will propagate to: {', '.join(get_propagation_targets(module, final.propagation))}")
```

#### Acceptance Criteria

- [ ] `debug` command shows rule evaluation trace
- [ ] All rules shown in priority order
- [ ] Match/skip clearly indicated
- [ ] Final decision and propagation displayed
- [ ] Tests verify debug output format

---

### 8. Add Progress Indication (REQ-UX-002)

**Effort:** 1 day
**Owner:** TBD

#### Implementation

```python
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

def generate_exports(modules: list[Path]) -> ExportGenerationResult:
    """Generate exports with progress bar."""

    if len(modules) > 50:
        # Show progress for large operations
        with Progress(
            SpinnerColumn(),
            TextColumn("[progress.description]{task.description}"),
            BarColumn(),
            TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
            TextColumn("({task.completed}/{task.total})"),
            TextColumn("[cyan]{task.fields[speed]}[/cyan]"),
        ) as progress:
            task = progress.add_task(
                "Processing modules...",
                total=len(modules),
                speed="0 files/s"
            )

            start_time = time.time()
            for i, module in enumerate(modules):
                process_module(module)

                # Update progress
                elapsed = time.time() - start_time
                speed = (i + 1) / elapsed if elapsed > 0 else 0
                progress.update(
                    task,
                    advance=1,
                    speed=f"{speed:.1f} files/s"
                )
    else:
        # No progress bar for small operations
        for module in modules:
            process_module(module)
```

#### Acceptance Criteria

- [ ] Progress bar shown for >50 files
- [ ] Shows files/second and ETA
- [ ] No progress bar for small operations
- [ ] Tests verify progress updates

---

## Success Metrics

### Week 1 (P1)
- [ ] All 4 P1 items completed
- [ ] Tests passing for all P1 features
- [ ] Migration validation shows 100% match
- [ ] Circuit breaker working
- [ ] Validator functional

### Week 2 (P2/P3)
- [ ] Backward compat timeline documented
- [ ] Error messages enhanced
- [ ] Debug mode working
- [ ] Progress bars implemented

### Final (Production Ready)
- [ ] All MUST requirements met (100%)
- [ ] Test coverage >80%
- [ ] All tests passing
- [ ] Documentation complete
- [ ] Real codebase validation passing

---

## Risk Mitigation

### Risk: Migration validation fails

**Mitigation:**
- Start with small sample (10 modules)
- Identify patterns in discrepancies
- Fix issues incrementally
- Expand to full codebase

### Risk: Performance regression

**Mitigation:**
- Run benchmarks after each change
- Profile if performance degrades
- Optimize hot paths
- Keep performance tests in CI

### Risk: Breaking changes in validator

**Mitigation:**
- Start with warnings, not errors
- Provide auto-fix for common issues
- Document migration path
- Give users control with flags

---

## Tracking

**Progress Dashboard:**
```
P1 (Critical): ░░░░░░░░ 0/4 complete
P2 (Important): ░░░░░░░░ 0/2 complete
P3 (Nice-to-Have): ░░░░░░░░ 0/2 complete

Overall: ░░░░░░░░░░ 0/8 complete (0%)
```

Update this file as work progresses.

---

## Notes

- This plan assumes 1 developer working full-time
- Estimates include implementation, testing, and documentation
- Items can be parallelized if multiple developers available
- Critical items (P1) must be done sequentially due to dependencies

---

**Last Updated:** 2026-02-14
**Status:** Ready to begin
