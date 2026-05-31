<!-- SPDX-FileCopyrightText: 2026 Knitli Inc. -->
<!-- SPDX-License-Identifier: MIT OR Apache-2.0 -->
## 2026-04-21 - Unused unsafe import function removed
**Vulnerability:** Found an unused `_attempt_import` function in `src/codeweaver/server/mcp/server.py` that dynamically imports a module directly from unvalidated configuration (`import_module(mw.rsplit(".", 1)[0])`), leading to potential arbitrary code execution.
**Learning:** Functions that perform dynamic imports should not be left around in the codebase if they are unused, especially if they are designed to take unvalidated strings as input.
**Prevention:** Avoid dynamic imports based on configuration or inputs without strict whitelisting. Use tools like `semgrep` with python security rules to actively catch these patterns.

## 2026-04-22 - Prevent Arbitrary Code Execution in dynamic type evaluation
**Vulnerability:** The `Container._safe_eval_type` method evaluates string representations of type annotations using an AST validation approach. It previously allowed generic `ast.Call` nodes to exist without verifying the underlying function being called.
**Learning:** Allowing generic `ast.Call` nodes in type validators evaluating user or external inputs introduces a critical Arbitrary Code Execution (ACE) vulnerability, because it permits executing any function accessible in the module's global namespace or `__builtins__` during the eval phase.
**Prevention:** `ast.Call` nodes must be strictly whitelisted to the specific set of expected functions (like `Depends`, `depends`, `Field`, `PrivateAttr`, `Tag`, `Parameter`, `cast`, `length`, `uuid7`). Use rigorous AST node restriction and do not allow unbounded execution of methods when parsing types from string evaluation mechanisms.
