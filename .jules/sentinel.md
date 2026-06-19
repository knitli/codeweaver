<!-- SPDX-FileCopyrightText: 2026 Knitli Inc. -->
<!-- SPDX-License-Identifier: MIT OR Apache-2.0 -->
## 2026-04-21 - Unused unsafe import function removed
**Vulnerability:** Found an unused `_attempt_import` function in `src/codeweaver/server/mcp/server.py` that dynamically imports a module directly from unvalidated configuration (`import_module(mw.rsplit(".", 1)[0])`), leading to potential arbitrary code execution.
**Learning:** Functions that perform dynamic imports should not be left around in the codebase if they are unused, especially if they are designed to take unvalidated strings as input.
**Prevention:** Avoid dynamic imports based on configuration or inputs without strict whitelisting. Use tools like `semgrep` with python security rules to actively catch these patterns.
## 2026-04-22 - Restricting ast.Call to Prevent Arbitrary Code Execution during Type String Eval
**Vulnerability:** The AST validation logic in `_safe_eval_type` (`src/codeweaver/core/di/container.py`) permitted generic `ast.Call` nodes. Since the subsequent evaluation used `eval()` with the module's global namespace, this allowed for Arbitrary Code Execution (ACE) if an attacker could inject an arbitrary function call into a string-based type annotation.
**Learning:** Even when limiting builtins, evaluating strings as code (`eval`) with access to an entire module's namespace is inherently risky. `ast.Call` nodes must be strictly constrained.
**Prevention:** Whitelist `ast.Call` nodes specifically to the required subset of safe, metadata-constructing functions (e.g., `Depends`, `Field`, `Parameter`). Never allow unrestrained function calls when dynamically resolving type annotations.
