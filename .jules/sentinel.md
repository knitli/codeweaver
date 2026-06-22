<!-- SPDX-FileCopyrightText: 2026 Knitli Inc. -->
<!-- SPDX-License-Identifier: MIT OR Apache-2.0 -->
## 2026-04-21 - Unused unsafe import function removed
**Vulnerability:** Found an unused `_attempt_import` function in `src/codeweaver/server/mcp/server.py` that dynamically imports a module directly from unvalidated configuration (`import_module(mw.rsplit(".", 1)[0])`), leading to potential arbitrary code execution.
**Learning:** Functions that perform dynamic imports should not be left around in the codebase if they are unused, especially if they are designed to take unvalidated strings as input.
**Prevention:** Avoid dynamic imports based on configuration or inputs without strict whitelisting. Use tools like `semgrep` with python security rules to actively catch these patterns.
<!-- SPDX-FileCopyrightText: 2025 Knitli Inc. -->
<!-- SPDX-License-Identifier: MIT OR Apache-2.0 -->

## 2025-02-25 - Prevent Arbitrary Code Execution (ACE) in Safe AST Evaluation
**Vulnerability:** Safe AST evaluation logic for resolving dynamic type annotations in `src/codeweaver/core/di/container.py` allowed unrestricted `ast.Call` nodes. This permitted the evaluation of arbitrary callables present in the global namespace during type hint parsing (e.g., `Annotated[int, os.system('...')]`), leading to a critical Arbitrary Code Execution (ACE) vulnerability.
**Learning:** Even when builtins are restricted (e.g., overriding `__builtins__` in `eval()`), allowing function calls in an AST passed to `eval` can be extremely dangerous if the global namespace or allowed AST nodes are not strictly controlled.
**Prevention:** Implement an explicit whitelist for `ast.Call` nodes, allowing only specifically required functions (e.g., `Depends`, `depends`, `Field`, `PrivateAttr`, `Tag`). Verify that any added functions are strictly necessary for the application's functionality.
