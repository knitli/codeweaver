<!-- SPDX-FileCopyrightText: 2026 Knitli Inc. -->
<!-- SPDX-License-Identifier: MIT OR Apache-2.0 -->
## 2026-04-21 - Unused unsafe import function removed
**Vulnerability:** Found an unused `_attempt_import` function in `src/codeweaver/server/mcp/server.py` that dynamically imports a module directly from unvalidated configuration (`import_module(mw.rsplit(".", 1)[0])`), leading to potential arbitrary code execution.
**Learning:** Functions that perform dynamic imports should not be left around in the codebase if they are unused, especially if they are designed to take unvalidated strings as input.
**Prevention:** Avoid dynamic imports based on configuration or inputs without strict whitelisting. Use tools like `semgrep` with python security rules to actively catch these patterns.

## 2026-04-21 - Restrict arbitrary Call nodes in AST dynamic evaluation
**Vulnerability:** The type validation logic using `ast.parse(type_str, mode="eval")` allowed generic `ast.Call` nodes to pass. Even though standard Python literal types were blocked, any accessible callable within the execution environment's scope could be arbitrarily executed, leading to a critical Arbitrary Code Execution (ACE) vulnerability during type resolution.
**Learning:** Permitting generic `ast.Call` nodes in type validation allows unauthorized function execution. Allowed AST nodes must be restricted to their expected forms and specific callable identifiers (e.g., `Depends`, `Field`) must be hardcoded or whitelisted.
**Prevention:** Explicitly restrict allowed callables in the `TypeValidator` to a predefined whitelist instead of broadly allowing the `ast.Call` class. Implement rigorous AST node visitation checks that explicitly validate both `node.func.id` and `node.func.attr`.
