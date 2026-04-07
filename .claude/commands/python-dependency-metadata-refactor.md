<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

---
name: python-dependency-metadata-refactor
description: Workflow command scaffold for python-dependency-metadata-refactor in codeweaver.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /python-dependency-metadata-refactor

Use this workflow when working on **python-dependency-metadata-refactor** in `codeweaver`.

## Goal

Refactor or reorganize Python project dependencies, extras, or metadata structure across a monorepo workspace.

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

- Edit root pyproject.toml to change [project.dependencies], [project.optional-dependencies], or [tool.*] sections.
- Edit workspace member pyproject.toml files (e.g., packages/codeweaver-daemon/pyproject.toml, packages/codeweaver-tokenizers/pyproject.toml) to synchronize or update dependency metadata.
- Update uv.lock to reflect the new dependency resolution.
- Verify by building wheels or running dependency-related commands.
- Optionally, add or update related tests to verify import behavior or dependency isolation.

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.
