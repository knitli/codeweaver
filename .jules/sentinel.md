<!-- SPDX-FileCopyrightText: 2026 Knitli Inc. -->
<!-- SPDX-License-Identifier: MIT OR Apache-2.0 -->
## 2026-04-21 - Unused unsafe import function removed
**Vulnerability:** Found an unused `_attempt_import` function in `src/codeweaver/server/mcp/server.py` that dynamically imports a module directly from unvalidated configuration (`import_module(mw.rsplit(".", 1)[0])`), leading to potential arbitrary code execution.
**Learning:** Functions that perform dynamic imports should not be left around in the codebase if they are unused, especially if they are designed to take unvalidated strings as input.
**Prevention:** Avoid dynamic imports based on configuration or inputs without strict whitelisting. Use tools like `semgrep` with python security rules to actively catch these patterns.

## 2026-04-22 - Arbitrary Code Execution (ACE) via unvalidated ast.Call nodes
**Vulnerability:** Found that the AST validation for safe type evaluation `_safe_eval_type` in `src/codeweaver/core/di/container.py` allowed generic `ast.Call` nodes. This permitted the evaluation of arbitrary function calls within type hint strings, leading to a critical Arbitrary Code Execution (ACE) vulnerability.
**Learning:** Permitting generic `ast.Call` nodes during AST-based validation for dynamic evaluation bypasses the intended safety restrictions, as any callable in the global namespace can be executed.
**Prevention:** `ast.Call` nodes must be strictly evaluated and whitelisted to only allow specific, required functions (e.g., `Depends`, `depends`, `Field`, `PrivateAttr`, `Tag`, `Parameter`) using custom visitor methods like `visit_Call`.
