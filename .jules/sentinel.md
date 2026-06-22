<!-- SPDX-FileCopyrightText: 2026 Knitli Inc. -->
<!-- SPDX-License-Identifier: MIT OR Apache-2.0 -->
## 2026-04-21 - Unused unsafe import function removed
**Vulnerability:** Found an unused `_attempt_import` function in `src/codeweaver/server/mcp/server.py` that dynamically imports a module directly from unvalidated configuration (`import_module(mw.rsplit(".", 1)[0])`), leading to potential arbitrary code execution.
**Learning:** Functions that perform dynamic imports should not be left around in the codebase if they are unused, especially if they are designed to take unvalidated strings as input.
**Prevention:** Avoid dynamic imports based on configuration or inputs without strict whitelisting. Use tools like `semgrep` with python security rules to actively catch these patterns.

## 2026-04-22 - Arbitrary Code Execution (ACE) risk in type hint evaluation
**Vulnerability:** Found `ast.Call` nodes generically allowed in `_safe_eval_type` within `src/codeweaver/core/di/container.py`, meaning any arbitrary function callable in the namespace (like OS commands via `os.system` if imported) could be executed through malicious type strings parsed by `eval()`.
**Learning:** Even constrained restricted environments for `eval` cannot effectively sandbox `ast.Call` if `eval` dynamically evaluates parsed generic attributes.
**Prevention:** Always use an explicit whitelist matching exact function names (like `Depends`, `Field`, `Parameter`, etc.) rather than allowing all `ast.Call` structures to prevent unwanted arbitrary code execution during type resolution.
