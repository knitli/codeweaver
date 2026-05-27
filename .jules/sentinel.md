<!-- SPDX-FileCopyrightText: 2026 Knitli Inc. -->
<!-- SPDX-License-Identifier: MIT OR Apache-2.0 -->
## 2026-04-21 - Unused unsafe import function removed
**Vulnerability:** Found an unused `_attempt_import` function in `src/codeweaver/server/mcp/server.py` that dynamically imports a module directly from unvalidated configuration (`import_module(mw.rsplit(".", 1)[0])`), leading to potential arbitrary code execution.
**Learning:** Functions that perform dynamic imports should not be left around in the codebase if they are unused, especially if they are designed to take unvalidated strings as input.
**Prevention:** Avoid dynamic imports based on configuration or inputs without strict whitelisting. Use tools like `semgrep` with python security rules to actively catch these patterns.

## 2026-04-22 - ACE vulnerability via generic `ast.Call` in safe eval
**Vulnerability:** Found an Arbitrary Code Execution (ACE) vulnerability in `src/codeweaver/core/di/container.py` within `_safe_eval_type`. The function parsed type hints via `ast.parse` and validated the AST tree before evaluating it, but allowed generic `ast.Call` nodes. This permitted the execution of any callable available in the module's global namespace during the final `eval()` call.
**Learning:** Even when `eval()` is used with a restricted `__builtins__` dictionary, evaluating an AST tree constructed from user-provided or stringified type hints can lead to ACE if `ast.Call` nodes are universally permitted. The evaluation will run callables from the provided `globalns`.
**Prevention:** Strictly restrict `ast.Call` nodes by maintaining an explicit whitelist of allowed callables (e.g., `{"Depends", "depends", "Field", "PrivateAttr", "Tag"}`). Validate `node.func.id` or `node.func.attr` against this whitelist during AST tree validation.
