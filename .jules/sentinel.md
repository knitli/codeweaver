<!-- SPDX-FileCopyrightText: 2026 Knitli Inc. -->
<!-- SPDX-License-Identifier: MIT OR Apache-2.0 -->
## 2026-04-21 - Unused unsafe import function removed
**Vulnerability:** Found an unused `_attempt_import` function in `src/codeweaver/server/mcp/server.py` that dynamically imports a module directly from unvalidated configuration (`import_module(mw.rsplit(".", 1)[0])`), leading to potential arbitrary code execution.
**Learning:** Functions that perform dynamic imports should not be left around in the codebase if they are unused, especially if they are designed to take unvalidated strings as input.
**Prevention:** Avoid dynamic imports based on configuration or inputs without strict whitelisting. Use tools like `semgrep` with python security rules to actively catch these patterns.
## 2026-04-21 - AST Arbitrary Code Execution Prevented
**Vulnerability:** Found an Arbitrary Code Execution (ACE) vulnerability during dynamic type evaluation via safe `eval()`. The AST validation didn't restrict `ast.Call` nodes, allowing any arbitrary callable in the module's global namespace to be executed during type string resolution.
**Learning:** Even when `eval()` restricts `__builtins__` and dunder accesses, generic `ast.Call` nodes are extremely dangerous. A malicious type annotation string can still invoke arbitrary functions that are available in the module's `globalns`, resulting in arbitrary code execution.
**Prevention:** `ast.Call` nodes must be strictly whitelisted to specific, required functions like `Depends`, `depends`, `Field`, `PrivateAttr`, `Tag`, and `Parameter`. Never trust type annotations derived from external or potentially unvalidated sources. Always whitelist explicit nodes rather than simply allowing classes of node types.
