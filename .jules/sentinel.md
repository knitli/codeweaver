<!-- SPDX-FileCopyrightText: 2026 Knitli Inc. -->
<!-- SPDX-License-Identifier: MIT OR Apache-2.0 -->
## 2026-04-21 - Unused unsafe import function removed
**Vulnerability:** Found an unused `_attempt_import` function in `src/codeweaver/server/mcp/server.py` that dynamically imports a module directly from unvalidated configuration (`import_module(mw.rsplit(".", 1)[0])`), leading to potential arbitrary code execution.
**Learning:** Functions that perform dynamic imports should not be left around in the codebase if they are unused, especially if they are designed to take unvalidated strings as input.
**Prevention:** Avoid dynamic imports based on configuration or inputs without strict whitelisting. Use tools like `semgrep` with python security rules to actively catch these patterns.
## 2026-06-06 - Prevented Arbitrary Code Execution in AST Evaluation
**Vulnerability:** Found a vulnerability in `src/codeweaver/core/di/container.py` where `ast.Call` nodes were allowed without any whitelisting during dynamic type evaluation via `ast.parse(type_str, mode="eval")`. This could lead to Arbitrary Code Execution (ACE) if an attacker can control the type string being evaluated, as any callable in the module's global namespace could be executed.
**Learning:** When validating AST trees for dynamic type evaluation using `eval()`, allowing generic `ast.Call` nodes is dangerous. It permits execution of any callable in the module's global namespace.
**Prevention:** `ast.Call` nodes must be strictly whitelisted to specific, required functions (e.g., `Depends`, `depends`, `Field`, `PrivateAttr`, `Tag`, `Parameter`) when validating an AST before evaluating it.
