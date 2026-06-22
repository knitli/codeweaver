<!-- SPDX-FileCopyrightText: 2026 Knitli Inc. -->
<!-- SPDX-License-Identifier: MIT OR Apache-2.0 -->
## 2026-04-21 - Unused unsafe import function removed
**Vulnerability:** Found an unused `_attempt_import` function in `src/codeweaver/server/mcp/server.py` that dynamically imports a module directly from unvalidated configuration (`import_module(mw.rsplit(".", 1)[0])`), leading to potential arbitrary code execution.
**Learning:** Functions that perform dynamic imports should not be left around in the codebase if they are unused, especially if they are designed to take unvalidated strings as input.
**Prevention:** Avoid dynamic imports based on configuration or inputs without strict whitelisting. Use tools like `semgrep` with python security rules to actively catch these patterns.

## 2026-04-21 - ACE vulnerability in eval during AST validation
**Vulnerability:** A critical Arbitrary Code Execution (ACE) vulnerability was found in `src/codeweaver/core/di/container.py` during type resolution string evaluation (`_safe_eval_type`). The `TypeValidator` broadly allowed generic `ast.Call` nodes before calling `eval()` on type strings, permitting the execution of any callable mapped in the `globalns` parameter.
**Learning:** Even when using a restrictive AST check before executing `eval()`, implicitly allowing generic `ast.Call` nodes effectively bypasses the restricted sandbox by allowing any accessible function to be invoked during evaluation.
**Prevention:** Strictly whitelist allowed function names (e.g. `Depends`, `Field`, `Tag`) when validating `ast.Call` nodes in type strings before calling `eval()`, preventing any unauthorized code execution.
