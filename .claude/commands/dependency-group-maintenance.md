---
name: dependency-group-maintenance
description: Workflow command scaffold for dependency-group-maintenance in codeweaver.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /dependency-group-maintenance

Use this workflow when working on **dependency-group-maintenance** in `codeweaver`.

## Goal

Add, remove, or reorganize dependency groups (such as 'dev', 'test', 'lint', 'build') in the project configuration.

## Common Files

- `pyproject.toml`
- `uv.lock`
- `packages/codeweaver-daemon/pyproject.toml`
- `packages/codeweaver-tokenizers/pyproject.toml`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Edit pyproject.toml to update [dependency-groups] or equivalent sections.
- Edit workspace member pyproject.toml files if group changes affect them.
- Update uv.lock to reflect group changes.
- Document or communicate the new group structure if needed.

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.