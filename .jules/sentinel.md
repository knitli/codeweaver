<!-- SPDX-FileCopyrightText: 2026 Knitli Inc. -->
<!-- SPDX-License-Identifier: MIT OR Apache-2.0 -->
## 2026-04-21 - Unused unsafe import function removed
**Vulnerability:** Found an unused `_attempt_import` function in `src/codeweaver/server/mcp/server.py` that dynamically imports a module directly from unvalidated configuration (`import_module(mw.rsplit(".", 1)[0])`), leading to potential arbitrary code execution.
**Learning:** Functions that perform dynamic imports should not be left around in the codebase if they are unused, especially if they are designed to take unvalidated strings as input.
**Prevention:** Avoid dynamic imports based on configuration or inputs without strict whitelisting. Use tools like `semgrep` with python security rules to actively catch these patterns.

## 2026-06-03 - Restrict ast.Call during safe evaluation to prevent Arbitrary Code Execution
**Vulnerability:** Arbitrary Code Execution (ACE) via unrestricted `ast.Call` nodes during AST validation for type evaluation using `eval()` in `src/codeweaver/core/di/container.py`.
**Learning:** Permitting generic `ast.Call` nodes in restricted evaluation environments allows execution of any callable in the module's global namespace, breaking the sandbox.
**Prevention:** Strictly whitelist allowed function calls (e.g., `Depends`, `Field`, `Tag`) when validating AST trees for safe evaluation.
