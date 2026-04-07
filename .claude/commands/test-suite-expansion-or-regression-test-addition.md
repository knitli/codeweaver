---
name: test-suite-expansion-or-regression-test-addition
description: Workflow command scaffold for test-suite-expansion-or-regression-test-addition in codeweaver.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /test-suite-expansion-or-regression-test-addition

Use this workflow when working on **test-suite-expansion-or-regression-test-addition** in `codeweaver`.

## Goal

Add new regression or smoke tests to verify import, dependency, or installation behavior, especially for optional dependencies.

## Common Files

- `tests/unit/test_lazy_imports.py`
- `tests/unit/test_install_smoke.py`
- `pyproject.toml`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Create or update test files under tests/unit/ (e.g., test_lazy_imports.py, test_install_smoke.py) to add new checks.
- Optionally update pyproject.toml to register new pytest markers or test config.
- Verify tests pass locally and in CI.

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.