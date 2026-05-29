<!-- SPDX-FileCopyrightText: 2026 Knitli Inc. -->
<!-- SPDX-License-Identifier: MIT OR Apache-2.0 -->
## 2026-04-21 - Unused unsafe import function removed
**Vulnerability:** Found an unused `_attempt_import` function in `src/codeweaver/server/mcp/server.py` that dynamically imports a module directly from unvalidated configuration (`import_module(mw.rsplit(".", 1)[0])`), leading to potential arbitrary code execution.
**Learning:** Functions that perform dynamic imports should not be left around in the codebase if they are unused, especially if they are designed to take unvalidated strings as input.
**Prevention:** Avoid dynamic imports based on configuration or inputs without strict whitelisting. Use tools like `semgrep` with python security rules to actively catch these patterns.

## 2026-04-21 - AST Validation Arbitrary Code Execution
**Vulnerability:** The `TypeValidator` class in `src/codeweaver/core/di/container.py` evaluated type strings using `ast.parse` and allowed generic `ast.Call` nodes. This permitted the execution of any callable in the module's global namespace, introducing a critical Arbitrary Code Execution (ACE) vulnerability during dependency injection.
**Learning:** Even when performing restricted evaluation or AST validation, allowing generic `ast.Call` nodes provides a pathway for arbitrary code execution because the evaluator needs to call the function to resolve the type.
**Prevention:** To prevent ACE in dynamic type evaluation, `ast.Call` nodes must be strictly limited via a whitelist to only specific, required functions (like `Depends`, `Field`, etc.). Use a custom `visit_Call` method in `ast.NodeVisitor` subclasses to enforce this whitelist.
