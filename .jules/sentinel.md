<!-- SPDX-FileCopyrightText: 2026 Knitli Inc. -->
<!-- SPDX-License-Identifier: MIT OR Apache-2.0 -->
## 2026-04-21 - Unused unsafe import function removed
**Vulnerability:** Found an unused `_attempt_import` function in `src/codeweaver/server/mcp/server.py` that dynamically imports a module directly from unvalidated configuration (`import_module(mw.rsplit(".", 1)[0])`), leading to potential arbitrary code execution.
**Learning:** Functions that perform dynamic imports should not be left around in the codebase if they are unused, especially if they are designed to take unvalidated strings as input.
**Prevention:** Avoid dynamic imports based on configuration or inputs without strict whitelisting. Use tools like `semgrep` with python security rules to actively catch these patterns.
## 2026-04-22 - Unrestricted AST Call nodes in _safe_eval_type
**Vulnerability:** Found `ast.Call` included in the allowed nodes list of `_safe_eval_type` in `src/codeweaver/core/di/container.py` without validation, which introduces a critical Arbitrary Code Execution (ACE) vulnerability as it permits execution of any callable in the module's global namespace via `eval()`.
**Learning:** Permitting generic `ast.Call` nodes when parsing untrusted or complex type strings dynamically evaluated via `eval()` can lead to ACE if the type string references available functions in the global scope.
**Prevention:** Always restrict `ast.Call` nodes to a strict whitelist of explicitly required, known-safe functions (e.g., `Depends`, `Field`) when utilizing AST validation prior to dynamic evaluation.
