<!--
SPDX-FileCopyrightText: 2026 Knitli Inc.

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Lazy Import System - User Workflows

## Overview

This document provides step-by-step workflows for all user personas interacting with the lazy import system.

---

## Personas

### Feature Developer
**Context**: Adds new features, may not understand lazy import internals
**Goal**: Add code and make it importable without manual __all__ management
**Expertise**: Medium Python, basic Git

### System Maintainer
**Context**: Maintains lazy import system, fixes issues, manages configuration
**Goal**: Keep system healthy, debug issues, ensure quality
**Expertise**: Advanced Python, system design

### CI/CD System
**Context**: Automated validation in pipeline
**Goal**: Ensure code quality, prevent broken imports
**Expertise**: N/A (automated)

---

## Workflow 1: Adding New Module (Feature Developer)

### Scenario
Developer adds new feature module and wants it to be automatically exported.

### Pre-conditions
- Working on feature branch
- Repository is clean
- Lazy import system is configured

### Steps

**1. Create new module**
```bash
# Add new feature file
echo 'class NewFeature:
    """New feature implementation."""
    pass

def helper_function():
    """Helper for new feature."""
    pass
' > src/codeweaver/features/new_feature.py
```

**2. Generate exports**
```bash
mise run lazy-imports export generate

# Expected output:
# Analyzing files...
# ✓ src/codeweaver/features/new_feature.py (2 exports found)
#
# Generating exports...
# ✓ Generated __all__ in src/codeweaver/features/new_feature.py
#   __all__ = ("NewFeature", "helper_function")
#
# ✓ Updated src/codeweaver/features/__init__.py
#   Added: NewFeature, helper_function
#
# ✓ Updated src/codeweaver/__init__.py
#   Added: NewFeature (propagated from features)
#
# Summary:
#   Modules analyzed: 1
#   Exports generated: 2
#   Files updated: 3
#   Time: 0.3s
```

**3. Verify exports**
```bash
mise run lazy-imports validate

# Expected output:
# Validating lazy imports...
# ✓ All lazy_import() calls resolve
# ✓ All __all__ declarations consistent with _dynamic_imports
# ✓ All TYPE_CHECKING imports exist
# ✓ No broken imports found
#
# Summary:
#   Files validated: 347
#   Errors: 0
#   Warnings: 0
#   Time: 1.2s
```

**4. Test locally**
```python
# Test the imports work
python -c "from codeweaver.features import NewFeature; print('Success!')"
python -c "from codeweaver import NewFeature; print('Success!')"
```

**5. Commit changes**
```bash
git add src/codeweaver/features/
git commit -m "feat: add NewFeature module

- Implements new feature functionality
- Auto-generated exports included"
```

### Error Recovery

**Error: Export not generated**
```bash
# Debug why export wasn't created
mise run lazy-imports export debug NewFeature

# Output shows:
# Analyzing: NewFeature (src/codeweaver/features/new_feature.py)
#
# Rule evaluation:
#   ✓ [P1000] exclude-single-letter-types → SKIP (name doesn't match)
#   ✓ [P900]  include-version → SKIP (name doesn't match)
#   ✗ [P500]  default-exclude → EXCLUDE
#       Reason: No matching include rule found
#
# Final decision: EXCLUDE
# Not exported because no rule matched to include it
#
# Suggestions:
#   - Rename to match pattern (e.g., PascalCase for classes)
#   - Add custom rule in .codeweaver/rules/custom.yaml
#   - Add manual override in .codeweaver/lazy_imports.toml
```

**Solution: Add custom rule**
```yaml
# .codeweaver/rules/custom.yaml
rules:
  - name: "include-features"
    priority: 600
    match:
      module_pattern: ".*\\.features\\..*"
    action: include
    propagate: parent
```

Then regenerate:
```bash
mise run lazy-imports export generate
```

---

## Workflow 2: Debugging Missing Export (Feature Developer)

### Scenario
Developer expects a class to be exported but it's not appearing.

### Steps

**1. Check if class exists in module**
```bash
# Verify class is defined
grep -n "class MyClass" src/codeweaver/module.py
```

**2. Run debug command**
```bash
mise run lazy-imports export debug MyClass

# Output:
# Searching for: MyClass
#
# Found in: src/codeweaver/core/utils.py (line 42)
#
# Rule evaluation:
#   ✓ [P1000] exclude-single-letter-types → SKIP
#   ✓ [P700]  types-propagate-pascalcase → MATCH
#       Module: codeweaver.core.utils
#       Pattern: .*\.types(\..*)? → NO MATCH
#   ✓ [P500]  utilities-local-only → MATCH
#       Action: EXCLUDE
#       Reason: Utility modules don't propagate by default
#
# Final decision: EXCLUDE
# Reason: Matched rule "utilities-local-only" (priority 500)
#
# To include this export:
#   Option 1: Move to types module (auto-included)
#   Option 2: Add override in .codeweaver/lazy_imports.toml:
#
#     [overrides.include]
#     "codeweaver.core.utils" = ["MyClass"]
#
#   Option 3: Add custom rule for this pattern
```

**3. Apply fix**
```toml
# .codeweaver/lazy_imports.toml
[overrides.include]
"codeweaver.core.utils" = ["MyClass"]
```

**4. Regenerate and verify**
```bash
mise run lazy-imports export generate
mise run lazy-imports validate
```

---

## Workflow 3: System Migration (System Maintainer)

### Scenario
Migrating from old lazy import system to new system.

### Pre-conditions
- Old system (validate-lazy-imports.py) is working
- Backup of current state exists
- Test suite is passing

### Steps

**1. Create baseline**
```bash
# Capture current state
git add -A
git commit -m "chore: baseline before lazy import migration"

# Run old system and capture output
python mise-tasks/validate-lazy-imports.py > old-system-baseline.txt

# Create backup
cp exports_config.json exports_config.json.backup
```

**2. Run migration tool**
```bash
mise run lazy-imports migrate

# Output:
# Lazy Import System Migration
# ============================
#
# Analyzing old configuration...
# ✓ Found exports_config.json with 67 manual exclusions
# ✓ Analyzed 102 lines of hardcoded rules
#
# Generating new configuration...
# ✓ Created .codeweaver/lazy_imports.toml
# ✓ Generated 15 YAML rules from code logic
# ✓ Migrated 67 manual exclusions to overrides
# ✓ Created .codeweaver/rules/core.yaml
# ✓ Created .codeweaver/rules/providers.yaml
#
# Backup created:
# ✓ exports_config.json → exports_config.json.pre-v0.9.0
#
# Migration complete!
#
# Next steps:
#   1. Review generated config in .codeweaver/
#   2. Run validation: mise run lazy-imports --validate-migration
#   3. Test thoroughly before committing
```

**3. Validate migration**
```bash
mise run lazy-imports --validate-migration

# Output:
# Migration Validation
# ===================
#
# Running old system... Done (28.5s)
# Running new system... Done (2.8s)
#
# Comparing 347 modules:
#   ✓ 345/347 modules match exactly (99.4%)
#   ⚠ 2 differences found
#
# Differences:
#
# 1. codeweaver.core.types
#    Old: ["TypeA", "TypeB", "TypeC"]
#    New: ["TypeA", "TypeC"]
#    Missing: ["TypeB"]
#    Cause: Rule [P600] "capabilities-exclude-constants" excluded TypeB
#
#    Review: TypeB is actually a constant, exclusion is correct
#    Action: Approve difference
#
# 2. codeweaver.utils
#    Old: ["utilX", "utilY"]
#    New: ["utilX", "utilY", "utilZ"]
#    Extra: ["utilZ"]
#    Cause: Rule [P700] "include-get-functions" included utilZ
#
#    Review: utilZ is a valid get_ function, inclusion is correct
#    Action: Approve difference
#
# Migration quality: GOOD (99.4% match, differences are improvements)
#
# To approve these differences:
#   mise run lazy-imports approve-migration-diff
```

**4. Test thoroughly**
```bash
# Run full test suite
mise run test

# Test imports manually
python -c "import codeweaver; print(dir(codeweaver))"

# Performance check
mise run benchmark-lazy-imports

# Output:
# Performance: 2.8s (old: 28.5s) ✓ 10.2x faster
# Cache hit rate: 94% ✓
# Memory: 145MB peak ✓
```

**5. Commit migration**
```bash
git add .codeweaver/
git add exports_config.json.pre-v0.9.0
git commit -m "chore: migrate to new lazy import system

- Migrated from validate-lazy-imports.py to declarative system
- Generated rules from hardcoded logic
- 10x performance improvement (28.5s → 2.8s)
- 99.4% output equivalence (2 improvements)
- Old config backed up for rollback if needed"
```

### Rollback Procedure

If migration causes issues:

```bash
# Restore old config
cp exports_config.json.pre-v0.9.0 exports_config.json

# Remove new config
rm -rf .codeweaver/

# Use old system (fallback)
python mise-tasks/validate-lazy-imports.py --fix

# Report issue
gh issue create --title "Migration regression" --body "..."
```

---

## Workflow 4: CI/CD Validation (Automated)

### Scenario
CI pipeline validates lazy imports on every PR.

### Configuration

```yaml
# .github/workflows/ci.yml

name: CI

on:
  pull_request:
  push:
    branches: [main]

jobs:
  lazy-imports:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v3

      - name: Setup
        run: mise install

      - name: Validate Lazy Imports
        run: mise run lazy-imports validate --strict

      - name: Check Exports Up-to-Date
        run: |
          mise run lazy-imports export check
          # Fails if __init__.py files need updating

      - name: Comment on PR (if failures)
        if: failure()
        uses: actions/github-script@v6
        with:
          script: |
            github.rest.issues.createComment({
              issue_number: context.issue.number,
              owner: context.repo.owner,
              repo: context.repo.repo,
              body: '❌ Lazy import validation failed. Run `mise run lazy-imports export generate` locally.'
            })
```

### Developer Experience

**When PR passes**:
```
✅ All checks passed
   ✓ Lazy import validation
   ✓ Exports up-to-date
```

**When exports out of date**:
```
❌ Lazy import validation failed

Exports need updating:
  - src/codeweaver/features/__init__.py (2 exports missing)
  - src/codeweaver/utils/__init__.py (1 export extra)

Fix locally:
  mise run lazy-imports export generate
  git add .
  git commit --amend --no-edit
  git push --force-with-lease
```

**When broken import detected**:
```
❌ Lazy import validation failed

Broken imports found:
  src/codeweaver/core/__init__.py:15
    lazy_import("codeweaver.old.module", "OldClass")
    Error: Module 'codeweaver.old.module' not found

Fix locally:
  # Option 1: Auto-fix
  mise run lazy-imports validate fix

  # Option 2: Manual fix
  # Remove the lazy_import() call from __init__.py
```

---

## Workflow 5: Adding Custom Rule (System Maintainer)

### Scenario
Need to add project-specific export rule.

### Steps

**1. Identify pattern**
```bash
# Find exports that need special handling
mise run lazy-imports export generate --dry-run | grep "EXCLUDE"

# Example output:
# EXCLUDE: internal_helper (codeweaver.utils.internal)
# EXCLUDE: _private_func (codeweaver.core.private)
```

**2. Create custom rule**
```yaml
# .codeweaver/rules/custom.yaml

schema_version: "1.0"

rules:
  - name: "exclude-internal-helpers"
    priority: 550
    description: "Don't export internal_* helpers"
    match:
      name_pattern: "^internal_"
    action: exclude

  - name: "exclude-private-functions"
    priority: 540
    description: "Don't export functions starting with _"
    match:
      name_pattern: "^_"
      member_type: "function"
    action: exclude
```

**3. Add to configuration**
```toml
# .codeweaver/lazy_imports.toml

[rules]
rule_files = [
    ".codeweaver/rules/core.yaml",
    ".codeweaver/rules/providers.yaml",
    ".codeweaver/rules/custom.yaml",  # Add custom rules
]
```

**4. Validate and test**
```bash
# Validate configuration
mise run lazy-imports validate-config

# Output:
# ✓ Configuration valid
# ✓ All rule files found
# ✓ Schema validation passed
# ✓ No duplicate rule names
# ✓ Priority ranges valid

# Test with dry-run
mise run lazy-imports export generate --dry-run

# Apply if looks good
mise run lazy-imports export generate
```

**5. Document the rule**
```markdown
# .codeweaver/rules/README.md

## Custom Rules

### exclude-internal-helpers (Priority 550)
- **Pattern**: `^internal_`
- **Action**: Exclude
- **Reason**: Internal helper functions should not be exported
- **Examples**: `internal_parse()`, `internal_validate()`
```

---

## Workflow 6: Performance Investigation (System Maintainer)

### Scenario
Lazy import processing is slower than expected.

### Steps

**1. Run performance profile**
```bash
mise run lazy-imports export generate --profile

# Output:
# Performance Profile
# ==================
#
# Total time: 8.5s (expected <5s) ⚠️
#
# Breakdown:
#   File discovery: 0.3s (3.5%)
#   File parsing: 2.1s (24.7%)
#   Rule evaluation: 4.8s (56.5%) ⚠️ SLOW
#   Graph building: 0.8s (9.4%)
#   Code generation: 0.5s (5.9%)
#
# Cache statistics:
#   Hit rate: 45% (expected >90%) ⚠️ LOW
#   Hits: 156
#   Misses: 191
#
# Slow rules (>100ms):
#   [P650] complex-pattern-match: 2.1s (43.8% of rule time)
#   [P480] module-hierarchy-check: 1.8s (37.5% of rule time)
#
# Recommendations:
#   1. Optimize regex in complex-pattern-match rule
#   2. Cache module hierarchy checks
#   3. Investigate low cache hit rate
```

**2. Investigate cache issues**
```bash
# Check cache validity
mise run lazy-imports cache stats

# Output:
# Cache Statistics
# ===============
#
# Total entries: 347
# Invalid entries: 128 (36.9%) ⚠️
# Reason: Schema version mismatch (old: 0.9, current: 1.0)
#
# Recommendation:
#   Clear cache: mise run lazy-imports cache clear
#   Rebuild: mise run lazy-imports export generate
```

**3. Clear cache and rebuild**
```bash
mise run lazy-imports cache clear
mise run lazy-imports export generate

# Output:
# First run: 6.2s (rebuilding cache)
# Second run: 2.1s (cache hit rate: 96%) ✓
```

**4. Optimize slow rule**
```yaml
# Before (slow):
- name: "complex-pattern-match"
  match:
    name_pattern: "^(Get|Set|Create|Update|Delete)[A-Z][a-zA-Z0-9]*$"

# After (optimized):
- name: "crud-operations"
  match:
    name_pattern: "^(Get|Set|Create|Update|Delete)[A-Z]\\w+$"
    # Simpler pattern, using \\w+ instead of [a-zA-Z0-9]*
```

---

## Workflow 7: Emergency Rollback (System Maintainer)

### Scenario
New system causes production issues, need immediate rollback.

### Steps

**1. Identify issue**
```bash
# Check what's broken
mise run lazy-imports validate

# Output shows errors
```

**2. Quick rollback**
```bash
# Restore old configuration
cp exports_config.json.pre-v0.9.0 exports_config.json

# Remove new system config
mv .codeweaver .codeweaver.broken

# Use old system
python mise-tasks/validate-lazy-imports.py --fix

# Verify
python mise-tasks/validate-lazy-imports.py
```

**3. Emergency commit**
```bash
git add exports_config.json
git add .codeweaver.broken
git commit -m "ROLLBACK: revert to old lazy import system

Issue: [describe issue]
Needs investigation before re-attempting migration"

git push
```

**4. Post-mortem**
```markdown
# .codeweaver.broken/ROLLBACK_NOTES.md

## Rollback Reason
[Describe what went wrong]

## Investigation Needed
- [ ] Reproduce issue locally
- [ ] Identify root cause
- [ ] Create fix
- [ ] Test thoroughly
- [ ] Document prevention

## Re-migration Checklist
- [ ] Issue fixed
- [ ] Tests added
- [ ] Validation passes 100%
- [ ] Staged rollout plan
```

---

## Integration Modes

### Mode 1: Pre-commit Hook (Automatic)

```bash
# .git/hooks/pre-commit
#!/bin/bash

mise run lazy-imports export generate --quiet

# Stage updated files
git add **/__init__.py

# Validation
if ! mise run lazy-imports validate --quiet; then
    echo "❌ Lazy import validation failed"
    echo "Run: mise run lazy-imports validate fix"
    exit 1
fi
```

**Developer experience**: Transparent, zero manual work

### Mode 2: Manual (Developer Responsibility)

```bash
# Developer workflow
git add src/codeweaver/new_module.py
mise run lazy-imports export generate
git add **/__init__.py
git commit -m "feat: add new module"
```

**Developer experience**: Explicit, clear what's happening

### Mode 3: CI-Enforced (Strict)

```yaml
# CI checks but doesn't auto-fix
- run: mise run lazy-imports export check
  # Fails if exports need updating
```

**Developer experience**: Fails PR if exports not updated locally

---

## Workflow Summary Matrix

| Workflow | Actor | Frequency | Automation | Critical? |
|----------|-------|-----------|------------|-----------|
| Adding Module | Developer | Daily | Optional hook | No |
| Debugging Export | Developer | Weekly | None | No |
| System Migration | Maintainer | Once | Tooling | Yes |
| CI Validation | CI/CD | Every PR | Full | Yes |
| Custom Rules | Maintainer | Monthly | None | No |
| Performance Fix | Maintainer | As needed | Tooling | No |
| Emergency Rollback | Maintainer | Rare | Manual | Yes |

---

## Success Metrics

**Feature Developer**:
- ✅ Can add module and generate exports in <30 seconds
- ✅ Clear error messages when something goes wrong
- ✅ Self-service debugging with `export debug` command

**System Maintainer**:
- ✅ Migration completes with >95% equivalence
- ✅ Performance targets met (10x faster)
- ✅ Clear rollback procedure if needed

**CI/CD**:
- ✅ Validation completes in <5 seconds
- ✅ Clear failure messages for developers
- ✅ Automated without manual intervention
