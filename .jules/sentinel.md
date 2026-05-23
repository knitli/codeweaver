<!-- SPDX-FileCopyrightText: 2026 Knitli Inc. -->
<!-- SPDX-License-Identifier: MIT OR Apache-2.0 -->
## 2026-04-21 - Unused unsafe import function removed
**Vulnerability:** Found an unused `_attempt_import` function in `src/codeweaver/server/mcp/server.py` that dynamically imports a module directly from unvalidated configuration (`import_module(mw.rsplit(".", 1)[0])`), leading to potential arbitrary code execution.
**Learning:** Functions that perform dynamic imports should not be left around in the codebase if they are unused, especially if they are designed to take unvalidated strings as input.
**Prevention:** Avoid dynamic imports based on configuration or inputs without strict whitelisting. Use tools like `semgrep` with python security rules to actively catch these patterns.

## 2026-04-22 - Arbitrary Code Execution via Unsafe AST Evaluation
**Vulnerability:** Found a critical vulnerability in `_safe_eval_type` inside `src/codeweaver/core/di/container.py` where `ast.Call` nodes were unconditionally allowed during AST-based type string evaluation using Python's `eval()`. This allowed arbitrary callable execution within the module namespace.
**Learning:** Even with an AST `NodeVisitor` ensuring restricted constructs (like disabling dunder access), unconditionally allowing `ast.Call` can be exploited to run system commands or unintended functions if an attacker controls a type annotation string.
**Prevention:** Strictly enforce a whitelist for `ast.Call` validation checking `node.func.id` to match explicitly required dependencies (e.g., `Depends`, `depends`, `Field`, `PrivateAttr`, `Tag`). Avoid open-ended evaluations by enforcing an allow-only list of node types.
