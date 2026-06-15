<!-- SPDX-FileCopyrightText: 2026 Knitli Inc. -->
<!-- SPDX-License-Identifier: MIT OR Apache-2.0 -->
## 2026-04-21 - Unused unsafe import function removed
**Vulnerability:** Found an unused `_attempt_import` function in `src/codeweaver/server/mcp/server.py` that dynamically imports a module directly from unvalidated configuration (`import_module(mw.rsplit(".", 1)[0])`), leading to potential arbitrary code execution.
**Learning:** Functions that perform dynamic imports should not be left around in the codebase if they are unused, especially if they are designed to take unvalidated strings as input.
**Prevention:** Avoid dynamic imports based on configuration or inputs without strict whitelisting. Use tools like `semgrep` with python security rules to actively catch these patterns.
## 2026-04-22 - Arbitrary Code Execution via unvalidated ast.Call in eval()
**Vulnerability:** Found a critical Arbitrary Code Execution (ACE) vulnerability in `src/codeweaver/core/di/container.py` where type hints evaluated dynamically via `eval()` allowed generic `ast.Call` nodes. This permitted execution of any callable in the module's global namespace.
**Learning:** When validating AST trees for dynamic type evaluation using `eval()`, allowing generic `ast.Call` nodes introduces severe ACE risks. Attackers can potentially execute unintended functions present in the environment.
**Prevention:** Strictly whitelist allowable function names inside `ast.Call` nodes (e.g., `Depends`, `depends`, `Field`, `PrivateAttr`, `Tag`, `Parameter`) before passing the tree to `eval()`.
