<!-- SPDX-FileCopyrightText: 2026 Knitli Inc. -->
<!-- SPDX-License-Identifier: MIT OR Apache-2.0 -->
## 2026-04-21 - Unused unsafe import function removed
**Vulnerability:** Found an unused `_attempt_import` function in `src/codeweaver/server/mcp/server.py` that dynamically imports a module directly from unvalidated configuration (`import_module(mw.rsplit(".", 1)[0])`), leading to potential arbitrary code execution.
**Learning:** Functions that perform dynamic imports should not be left around in the codebase if they are unused, especially if they are designed to take unvalidated strings as input.
**Prevention:** Avoid dynamic imports based on configuration or inputs without strict whitelisting. Use tools like `semgrep` with python security rules to actively catch these patterns.

## 2026-06-09 - Arbitrary Code Execution via unrestricted ast.Call in eval()
**Vulnerability:** Found a vulnerability in `src/codeweaver/core/di/container.py` where `eval()` was used to evaluate dynamic type strings. While an AST validator checked for safe nodes, it allowed unrestricted `ast.Call` nodes, meaning any function available in the global namespace or builtins could be executed during dependency injection resolution.
**Learning:** Even when using a restricted `eval()` environment with a filtered globals dict and AST validation, permitting generic `ast.Call` execution still allows for severe security holes (Arbitrary Code Execution) if an attacker can manipulate the input strings (type hints).
**Prevention:** Strictly whitelist allowed functions in AST validation (like `Depends`, `Field`, etc.) when evaluating type annotations, and never allow generic `ast.Call` nodes.
