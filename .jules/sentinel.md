<!-- SPDX-FileCopyrightText: 2026 Knitli Inc. -->
<!-- SPDX-License-Identifier: MIT OR Apache-2.0 -->
## 2026-04-21 - Unused unsafe import function removed
**Vulnerability:** Found an unused `_attempt_import` function in `src/codeweaver/server/mcp/server.py` that dynamically imports a module directly from unvalidated configuration (`import_module(mw.rsplit(".", 1)[0])`), leading to potential arbitrary code execution.
**Learning:** Functions that perform dynamic imports should not be left around in the codebase if they are unused, especially if they are designed to take unvalidated strings as input.
**Prevention:** Avoid dynamic imports based on configuration or inputs without strict whitelisting. Use tools like `semgrep` with python security rules to actively catch these patterns.

## 2025-05-18 - Restrict AST calls to prevent ACE in type hints
**Vulnerability:** Discovered that dynamic type evaluation in `src/codeweaver/core/di/container.py` using safe AST traversal allowed generic `ast.Call` nodes, enabling Arbitrary Code Execution (ACE) via the module's global namespace.
**Learning:** Permitting arbitrary functions to be called during AST evaluation of unvalidated or dynamic strings can lead to ACE vulnerabilities even when standard Python `eval` limitations are partially enforced.
**Prevention:** Strictly whitelist allowed functions (e.g., `Depends`, `Field`, `Parameter`) when validating AST trees and explicitly reject any `ast.Call` nodes executing unrecognized functions.
