---
name: dependency-group-refactor-and-lock-update
description: Workflow command scaffold for dependency-group-refactor-and-lock-update in codeweaver.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /dependency-group-refactor-and-lock-update

Use this workflow when working on **dependency-group-refactor-and-lock-update** in `codeweaver`.

## Goal

Refactor dependency groups or extras in pyproject.toml and update the lockfile to match new dependency structure.

## Common Files

- `pyproject.toml`
- `uv.lock`
- `packages/*/pyproject.toml`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Edit pyproject.toml (root and/or packages/*/pyproject.toml) to change dependency groups, extras, or dynamic metadata.
- Update uv.lock to reflect new dependency structure.
- Optionally update related test markers or comments.

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.