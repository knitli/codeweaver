<!-- SPDX-FileCopyrightText: 2026 Knitli Inc. -->
<!-- SPDX-License-Identifier: MIT OR Apache-2.0 -->
## 2026-04-21 - Unused unsafe import function removed
**Vulnerability:** Found an unused `_attempt_import` function in `src/codeweaver/server/mcp/server.py` that dynamically imports a module directly from unvalidated configuration (`import_module(mw.rsplit(".", 1)[0])`), leading to potential arbitrary code execution.
**Learning:** Functions that perform dynamic imports should not be left around in the codebase if they are unused, especially if they are designed to take unvalidated strings as input.
**Prevention:** Avoid dynamic imports based on configuration or inputs without strict whitelisting. Use tools like `semgrep` with python security rules to actively catch these patterns.

## 2025-02-25 - Arbitrary code execution in AST eval
**Vulnerability:** Found a lack of whitelisting for `ast.Call` nodes in type annotation resolution logic within `TypeValidator` (at `src/codeweaver/core/di/container.py`). This allowed any arbitrary function within the module's global namespace to be called during `eval()`, potentially leading to Arbitrary Code Execution (ACE).
**Learning:** Permitting generic `ast.Call` nodes inside restricted Abstract Syntax Tree parsing environments drastically increases the attack surface, allowing escape from restricted evaluation constraints.
**Prevention:** Strictly limit `ast.Call` nodes to specifically required functions (e.g., `Depends`, `depends`, `Field`, `PrivateAttr`, `Tag`, `Parameter`) when validating trees meant for dynamic type evaluation.
