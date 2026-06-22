<!-- SPDX-FileCopyrightText: 2026 Knitli Inc. -->
<!-- SPDX-License-Identifier: MIT OR Apache-2.0 -->
## 2026-04-21 - Unused unsafe import function removed
**Vulnerability:** Found an unused `_attempt_import` function in `src/codeweaver/server/mcp/server.py` that dynamically imports a module directly from unvalidated configuration (`import_module(mw.rsplit(".", 1)[0])`), leading to potential arbitrary code execution.
**Learning:** Functions that perform dynamic imports should not be left around in the codebase if they are unused, especially if they are designed to take unvalidated strings as input.
**Prevention:** Avoid dynamic imports based on configuration or inputs without strict whitelisting. Use tools like `semgrep` with python security rules to actively catch these patterns.
## 2026-04-21 - Restrict arbitrary code execution in AST evaluation
**Vulnerability:** The AST evaluation mechanism in `src/codeweaver/core/di/container.py` (`_safe_eval_type`) permitted arbitrary callable nodes. Because it used `eval()` on the parsed AST tree, an attacker could inject arbitrary functions available in the global namespace (e.g. `eval("evil()")`).
**Learning:** Even when builtins are restricted in `eval()`, if an attacker controls the AST tree generation and generic `ast.Call` nodes are permitted, they can execute any function present in the module's global namespace.
**Prevention:** Always restrict callable nodes (`ast.Call`) to an explicit whitelist of safe functions instead of merely relying on an allowed node type list.
