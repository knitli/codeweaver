<!-- SPDX-FileCopyrightText: 2026 Knitli Inc. -->
<!-- SPDX-License-Identifier: MIT OR Apache-2.0 -->
## 2026-04-21 - Unused unsafe import function removed
**Vulnerability:** Found an unused `_attempt_import` function in `src/codeweaver/server/mcp/server.py` that dynamically imports a module directly from unvalidated configuration (`import_module(mw.rsplit(".", 1)[0])`), leading to potential arbitrary code execution.
**Learning:** Functions that perform dynamic imports should not be left around in the codebase if they are unused, especially if they are designed to take unvalidated strings as input.
**Prevention:** Avoid dynamic imports based on configuration or inputs without strict whitelisting. Use tools like `semgrep` with python security rules to actively catch these patterns.
## 2025-02-14 - Arbitrary Code Execution (ACE) via AST Call Evaluation
**Vulnerability:** Allowed arbitrary `ast.Call` nodes in type annotation evaluation strings, potentially leading to arbitrary code execution if user input or malicious type strings are evaluated.
**Learning:** `eval()` inherently supports execution even within restricted builtins environments. By allowing generic `ast.Call` nodes when traversing AST for type annotation resolution, the system accidentally permitted invocation of any callable residing in the target global namespace.
**Prevention:** Strictly limited the `ast.Call` nodes to a tightly controlled whitelist of known safe functions used directly within type annotations (`Depends`, `depends`, `Field`, `PrivateAttr`, `Tag`). Any unexpected callables during AST inspection will correctly raise a `TypeError` before `eval()` executes.
