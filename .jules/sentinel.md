<!-- SPDX-FileCopyrightText: 2026 Knitli Inc. -->
<!-- SPDX-License-Identifier: MIT OR Apache-2.0 -->
## 2026-04-21 - Unused unsafe import function removed
**Vulnerability:** Found an unused `_attempt_import` function in `src/codeweaver/server/mcp/server.py` that dynamically imports a module directly from unvalidated configuration (`import_module(mw.rsplit(".", 1)[0])`), leading to potential arbitrary code execution.
**Learning:** Functions that perform dynamic imports should not be left around in the codebase if they are unused, especially if they are designed to take unvalidated strings as input.
**Prevention:** Avoid dynamic imports based on configuration or inputs without strict whitelisting. Use tools like `semgrep` with python security rules to actively catch these patterns.

## 2026-04-21 - Restrict ast.Call in AST parsing for eval
**Vulnerability:** Found a vulnerability in `_safe_eval_type` in `src/codeweaver/core/di/container.py` where allowing generic `ast.Call` nodes during AST validation before an `eval()` call could lead to Arbitrary Code Execution (ACE) if an attacker injects a malicious function call (e.g., `__import__('os').system('...')` though `__import__` was handled via dunder exclusion, other calls could still pass if their dependencies are met or via other tricks).
**Learning:** When validating AST trees for dynamic type evaluation using `eval()`, allowing generic `ast.Call` nodes introduces a critical Arbitrary Code Execution (ACE) vulnerability, as it permits execution of any callable in the module's global namespace.
**Prevention:** `ast.Call` nodes must be strictly whitelisted to specific, required functions (e.g., `Depends`, `Field`, `depends`, `PrivateAttr`) to prevent ACE.
