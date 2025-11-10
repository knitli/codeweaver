<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Task Completion Checklist

When completing any development task, follow this checklist to ensure quality and compliance.

## Before Starting Work

1. **Understand Requirements**
   - Read the Project Constitution (`.specify/memory/constitution.md`)
   - Verify alignment with AI-First Context principle
   - Check for evidence-based justification requirements

2. **Check Project Status**
   ```bash
   git status              # Check current branch and changes
   git branch              # Verify on feature branch (NOT main/master)
   ```

3. **Ensure Clean Environment**
   ```bash
   mise run sync          # Sync dependencies
   mise run activate      # Activate virtual environment
   ```

## During Development

1. **Follow Code Style**
   - Line length: 100 characters
   - Google-style docstrings (active voice, present tense)
   - Modern Python >=3.12 typing syntax
   - Use project base classes (`BasedModel`, `BaseEnum`, etc.)

2. **Type Safety**
   - Add type hints to all public functions
   - Use structured types (`TypedDict`, `NamedTuple`, `BaseModel`)
   - Avoid generic `dict[str, Any]` when structure is known

3. **Testing**
   - Focus on user-affecting behavior (not implementation details)
   - Prefer integration tests over unit tests
   - Add appropriate pytest markers to new tests
   - Run tests frequently: `mise run test`

## After Code Changes

### 1. Run Automatic Fixes
```bash
mise run fix            # Auto-fix formatting and linting issues
```

This command runs:
- `ruff format` - Auto-format Python code
- `ruff check --fix --unsafe-fixes` - Fix linting issues
- Format YAML/JSON/TOML files
- Apply ruff pattern fixes

### 2. Run Quality Checks
```bash
mise run check          # Type checking and validation
mise run lint           # Linting verification
```

**If checks fail**: Fix issues before proceeding. Do NOT disable tests or skip validation.

### 3. Run Tests
```bash
mise run test           # Run all tests
# OR for specific coverage:
mise run test-cov       # With coverage report
```

**If tests fail**: Investigate and fix root cause. Do NOT comment out failing tests.

### 4. Verify Build
```bash
mise run build          # Ensure package builds successfully
```

## Before Committing

### 1. Run Pre-Commit Checks
```bash
mise run pre-commit     # Comprehensive pre-commit validation
```

This runs:
- `hk fix` - Fix all fixable issues
- `hk check` - Validate all checks pass
- Auto-stages fixed files

### 2. Review Changes
```bash
git diff                # Review all changes
git status              # Verify staged files
```

### 3. Commit with Meaningful Message
```bash
git add .
git commit -m "Brief summary of changes

Detailed explanation if needed:
- What changed and why
- Any breaking changes
- References to issues/PRs"
```

**Commit Message Standards**:
- First line: Brief summary (50-72 chars)
- Use imperative mood: "Add feature" not "Added feature"
- Reference issues: "Fix #123: ..."
- Include rationale for complex changes

## Constitutional Compliance Checklist

Before finalizing any task, verify:

- [ ] **AI-First Context**: Does this enhance AI agent understanding?
- [ ] **Proven Patterns**: Using pydantic ecosystem patterns?
- [ ] **Evidence-Based**: All decisions backed by verifiable evidence?
- [ ] **Testing Philosophy**: Tests focus on user-affecting behavior?
- [ ] **Simplicity**: Code is as simple as possible, purpose is obvious?

## Red Flags - Stop and Investigate

If you encounter any of these, STOP and investigate:

- APIs behave unexpectedly
- Files aren't where documentation says they should be
- Code contradicts documentation
- Need to create workarounds or mock implementations
- Tests consistently fail without clear cause

**Red Flag Protocol**:
1. Stop current work
2. Review understanding systematically
3. Research using available tools
4. Ask for clarification if unclear
5. Never create workarounds without explicit authorization

## Quality Standards Verification

### Type Safety
- [ ] All public functions have type annotations
- [ ] Using modern Python >=3.12 syntax
- [ ] No `dict[str, Any]` where structure is known
- [ ] Project base classes used appropriately

### Code Quality
- [ ] Line length ≤100 characters
- [ ] Google-style docstrings with active voice
- [ ] No f-strings in logging statements
- [ ] Specific exception types (no bare `except:`)
- [ ] Boolean parameters are keyword-only

### Testing
- [ ] New tests have appropriate pytest markers
- [ ] Tests cover critical user-affecting behavior
- [ ] Integration tests for component interactions
- [ ] No disabled or commented-out tests

### Documentation
- [ ] Public APIs have clear docstrings
- [ ] Complex logic has explanatory comments
- [ ] README/docs updated if public interface changed

## Final Verification

```bash
# Run complete CI pipeline locally
mise run ci
```

This runs the full suite:
1. `mise run check` - Type checking
2. `mise run lint` - Linting
3. `mise run format` - Format verification
4. `mise run test-cov` - Tests with coverage
5. `mise run build` - Package build

**All steps must pass before considering task complete.**

## Clean Up

After task completion:

```bash
# Remove any temporary files or debug outputs
rm -rf temp_* debug_* *.log

# Clean build artifacts if needed
mise run clean
```

## Push and PR

```bash
# Push to feature branch
git push -u origin feature/branch-name

# Create PR using GitHub CLI (if available)
gh pr create --title "Title" --body "Description"
```

**PR Description Should Include**:
- Summary of changes
- Rationale and context
- Testing performed
- Breaking changes (if any)
- Related issues/PRs
