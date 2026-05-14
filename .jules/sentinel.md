<!-- SPDX-FileCopyrightText: 2026 Knitli Inc. -->
<!-- SPDX-License-Identifier: MIT OR Apache-2.0 -->
## 2026-04-21 - Unused unsafe import function removed
**Vulnerability:** Found an unused `_attempt_import` function in `src/codeweaver/server/mcp/server.py` that dynamically imports a module directly from unvalidated configuration (`import_module(mw.rsplit(".", 1)[0])`), leading to potential arbitrary code execution.
**Learning:** Functions that perform dynamic imports should not be left around in the codebase if they are unused, especially if they are designed to take unvalidated strings as input.
**Prevention:** Avoid dynamic imports based on configuration or inputs without strict whitelisting. Use tools like `semgrep` with python security rules to actively catch these patterns.

## 2026-04-21 - Arbitrary Code Execution in Type Resolution Eval
**Vulnerability:** Found an arbitrary code execution vulnerability in `src/codeweaver/core/di/container.py` during type resolution. The AST validator `_safe_eval_type` permitted any `ast.Call` nodes to be executed through `eval()` within the provided `globalns` environment.
**Learning:** AST whitelisting must strictly validate the identifier names being called. Validating the node type alone is insufficient to prevent evaluating functions injected via dynamic namespaces.
**Prevention:** Explicitly whitelist permitted identifier names inside `ast.Call` validations to ensure that only expected dependency injection annotations (`Depends`, `depends`, `Field`, `PrivateAttr`) are instantiated.
