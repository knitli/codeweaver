<!-- SPDX-FileCopyrightText: 2026 Knitli Inc. -->
<!-- SPDX-License-Identifier: MIT OR Apache-2.0 -->
## 2026-04-21 - Unused unsafe import function removed
**Vulnerability:** Found an unused `_attempt_import` function in `src/codeweaver/server/mcp/server.py` that dynamically imports a module directly from unvalidated configuration (`import_module(mw.rsplit(".", 1)[0])`), leading to potential arbitrary code execution.
**Learning:** Functions that perform dynamic imports should not be left around in the codebase if they are unused, especially if they are designed to take unvalidated strings as input.
**Prevention:** Avoid dynamic imports based on configuration or inputs without strict whitelisting. Use tools like `semgrep` with python security rules to actively catch these patterns.

## 2026-04-21 - Arbitrary Code Execution in dynamic type evaluation
**Vulnerability:** Found an Arbitrary Code Execution (ACE) vulnerability in `src/codeweaver/core/di/container.py` during dynamic type evaluation. Generic `ast.Call` nodes were allowed when evaluating string type annotations with `ast.parse` and `eval()`, which permitted execution of any callable in the module's global namespace.
**Learning:** Permitting generic `ast.Call` nodes in abstract syntax trees before evaluating them is dangerous because it provides an entrypoint to execute code during type resolution.
**Prevention:** Strictly whitelist allowed functions (e.g. `Depends`, `Field`, `Tag`, etc.) when traversing `ast.Call` nodes before calling `eval()`.
