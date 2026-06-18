<!-- SPDX-FileCopyrightText: 2026 Knitli Inc. -->
<!-- SPDX-License-Identifier: MIT OR Apache-2.0 -->
## 2026-04-21 - Unused unsafe import function removed
**Vulnerability:** Found an unused `_attempt_import` function in `src/codeweaver/server/mcp/server.py` that dynamically imports a module directly from unvalidated configuration (`import_module(mw.rsplit(".", 1)[0])`), leading to potential arbitrary code execution.
**Learning:** Functions that perform dynamic imports should not be left around in the codebase if they are unused, especially if they are designed to take unvalidated strings as input.
**Prevention:** Avoid dynamic imports based on configuration or inputs without strict whitelisting. Use tools like `semgrep` with python security rules to actively catch these patterns.

## 2026-04-21 - Arbitrary code execution vulnerability in type string evaluation
**Vulnerability:** Found a critical vulnerability in `_safe_eval_type` inside `src/codeweaver/core/di/container.py` where the AST validator did not restrict `ast.Call` nodes. This could allow for arbitrary code execution during `eval()` since any callable in the global namespace could be executed if present in a type string annotation.
**Learning:** When using `eval()` in restricted environments, it is crucial to meticulously validate all AST nodes to prevent executing unwanted code. Even with restricted built-ins, allowing generic function calls via `ast.Call` defeats the purpose of the security boundary.
**Prevention:** Always restrict `ast.Call` nodes to a strict whitelist of explicitly required functions (like `Depends`, `Field`, `Parameter`) when validating AST trees for dynamic type evaluation.
