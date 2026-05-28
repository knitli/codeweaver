<!-- SPDX-FileCopyrightText: 2026 Knitli Inc. -->
<!-- SPDX-License-Identifier: MIT OR Apache-2.0 -->
## 2026-04-21 - Unused unsafe import function removed
**Vulnerability:** Found an unused `_attempt_import` function in `src/codeweaver/server/mcp/server.py` that dynamically imports a module directly from unvalidated configuration (`import_module(mw.rsplit(".", 1)[0])`), leading to potential arbitrary code execution.
**Learning:** Functions that perform dynamic imports should not be left around in the codebase if they are unused, especially if they are designed to take unvalidated strings as input.
**Prevention:** Avoid dynamic imports based on configuration or inputs without strict whitelisting. Use tools like `semgrep` with python security rules to actively catch these patterns.

## 2026-05-28 - [Arbitrary Code Execution in AST Validation]
**Vulnerability:** Found a vulnerability in `src/codeweaver/core/di/container.py` where generic `ast.Call` nodes were permitted during AST validation for string type resolution, which is later passed to `eval`. This permitted the execution of any callable in the restricted eval's global namespace, posing an Arbitrary Code Execution (ACE) risk.
**Learning:** Permitting generic `ast.Call` in validation nodes that precede `eval()` without validating the actual function being called defeats the purpose of the sandbox.
**Prevention:** Strictly whitelist all callable names and restrict the nodes to direct function calls when traversing ASTs for safe `eval` validation.
