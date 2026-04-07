<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

---
name: dependency-formatting-standardization
description: Workflow command scaffold for dependency-formatting-standardization in codeweaver.
allowed_tools: ["Bash", "Read", "Write", "Grep", "Glob"]
---

# /dependency-formatting-standardization

Use this workflow when working on **dependency-formatting-standardization** in `codeweaver`.

## Goal

Apply formatting tools to pyproject.toml files across the workspace for consistency (e.g., alphabetizing, section reordering).

## Common Files

- `pyproject.toml`
- `packages/codeweaver-daemon/pyproject.toml`
- `packages/codeweaver-tokenizers/pyproject.toml`

## Suggested Sequence

1. Understand the current state and failure mode before editing.
2. Make the smallest coherent change that satisfies the workflow goal.
3. Run the most relevant verification for touched files.
4. Summarize what changed and what still needs review.

## Typical Commit Signals

- Run a formatter (e.g., tombi) on pyproject.toml files.
- Commit the reformatted files (no semantic change).

## Notes

- Treat this as a scaffold, not a hard-coded script.
- Update the command if the workflow evolves materially.