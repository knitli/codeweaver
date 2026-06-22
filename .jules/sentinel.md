<!-- SPDX-FileCopyrightText: 2026 Knitli Inc. -->
<!-- SPDX-License-Identifier: MIT OR Apache-2.0 -->
## 2026-04-21 - Unused unsafe import function removed
**Vulnerability:** Found an unused `_attempt_import` function in `src/codeweaver/server/mcp/server.py` that dynamically imports a module directly from unvalidated configuration (`import_module(mw.rsplit(".", 1)[0])`), leading to potential arbitrary code execution.
**Learning:** Functions that perform dynamic imports should not be left around in the codebase if they are unused, especially if they are designed to take unvalidated strings as input.
**Prevention:** Avoid dynamic imports based on configuration or inputs without strict whitelisting. Use tools like `semgrep` with python security rules to actively catch these patterns.

## 2026-04-21 - Arbitrary code execution via ast.Call in type string evaluation
**Vulnerability:** Found that `_safe_eval_type` in `src/codeweaver/core/di/container.py` used an AST validator that allowed `ast.Call` nodes to execute any available callable in the evaluation namespace. By crafting a type annotation string like `"os.system('echo pwned')"` (provided `os` is injected or imported), an attacker could achieve arbitrary code execution because the validated string was subsequently evaluated with `eval()`.
**Learning:** Even when AST validation correctly rejects `__` dunder accesses and restricts allowed node types, allowing generic `ast.Call` nodes remains dangerous if the execution environment contains potent functions or objects. Whitelisting specific functions (like `Depends`) inside the `ast.Call` validator is required to prevent bypasses.
**Prevention:** Explicitly restrict function calls (`ast.Call`) in custom `eval` AST validators to only known, safe operations. Ensure any code dynamically evaluating parsed input never permits generic execution.
