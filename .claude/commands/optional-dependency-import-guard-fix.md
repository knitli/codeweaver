---
name: optional-dependency-import-guard-fix
description: Workflow command scaffold for optional-dependency-import-guard-fix in codeweaver.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /optional-dependency-import-guard-fix

Use this workflow when working on **optional-dependency-import-guard-fix** in `codeweaver`.

## Goal

Fix runtime or test failures caused by missing optional dependencies by guarding imports and providing fallbacks (e.g., TYPE_CHECKING, Any).

## Common Files

- `src/codeweaver/providers/config/clients/multi.py`
- `src/codeweaver/providers/config/categories/embedding.py`
- `src/codeweaver/providers/config/categories/sparse_embedding.py`
- `pyproject.toml`
- `tests/unit/test_lazy_imports.py`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Identify files where optional dependency imports are not properly guarded.
- Update those files to wrap imports in has_package checks, TYPE_CHECKING, or try/except ImportError blocks, providing fallback types (Any) as needed.
- Update pyproject.toml to suppress type checker warnings for intentional fallbacks.
- Verify test suite passes in both full and minimal dependency environments.

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.