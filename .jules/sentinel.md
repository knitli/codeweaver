<!-- SPDX-FileCopyrightText: 2026 Knitli Inc. -->
<!-- SPDX-License-Identifier: MIT OR Apache-2.0 -->
## 2026-04-21 - Unused unsafe import function removed
**Vulnerability:** Found an unused `_attempt_import` function in `src/codeweaver/server/mcp/server.py` that dynamically imports a module directly from unvalidated configuration (`import_module(mw.rsplit(".", 1)[0])`), leading to potential arbitrary code execution.
**Learning:** Functions that perform dynamic imports should not be left around in the codebase if they are unused, especially if they are designed to take unvalidated strings as input.
**Prevention:** Avoid dynamic imports based on configuration or inputs without strict whitelisting. Use tools like `semgrep` with python security rules to actively catch these patterns.
## 2026-04-22 - Arbitrary Code Execution via unvalidated ast.Call in Type Resolution
**Vulnerability:** Found an Arbitrary Code Execution (ACE) vulnerability in `src/codeweaver/core/di/container.py` during dynamic type evaluation via `eval()`. The `TypeValidator` allowed generic `ast.Call` nodes without checking the underlying function being executed, enabling the execution of any callable in the restricted environment's global namespace or provided builtins.
**Learning:** Even when `eval()` is executed with restricted globals and `__builtins__`, allowing `ast.Call` to execute arbitrary functions present in the namespace can lead to unintended code execution.
**Prevention:** Strictly validate and whitelist any `ast.Call` nodes when building restricted execution environments to ensure only explicitly trusted functions (e.g., `Depends`, `Field`) are evaluated.
