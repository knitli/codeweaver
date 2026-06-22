<!-- SPDX-FileCopyrightText: 2026 Knitli Inc. -->
<!-- SPDX-License-Identifier: MIT OR Apache-2.0 -->
## 2026-04-21 - Unused unsafe import function removed
**Vulnerability:** Found an unused `_attempt_import` function in `src/codeweaver/server/mcp/server.py` that dynamically imports a module directly from unvalidated configuration (`import_module(mw.rsplit(".", 1)[0])`), leading to potential arbitrary code execution.
**Learning:** Functions that perform dynamic imports should not be left around in the codebase if they are unused, especially if they are designed to take unvalidated strings as input.
**Prevention:** Avoid dynamic imports based on configuration or inputs without strict whitelisting. Use tools like `semgrep` with python security rules to actively catch these patterns.
## 2026-06-04 - Arbitrary Code Execution in AST eval
**Vulnerability:** Found that when validating AST trees for dynamic type evaluation using `eval()`, allowing generic `ast.Call` nodes introduced an Arbitrary Code Execution (ACE) vulnerability, permitting the execution of any callable in the module's global namespace.
**Learning:** `ast.Call` nodes in type annotations (e.g., inside `Annotated[]`) must be strictly validated. Merely allowing `ast.Call` as a node type is insufficient if `eval()` is subsequently called, as it can execute unintended functions.
**Prevention:** Strictly whitelist allowed functions in `ast.Call` nodes (e.g., `Depends`, `depends`, `Field`, `PrivateAttr`, `Tag`, `Parameter`) by checking the node's function name before permitting the node in the AST validation step.
