<!-- SPDX-FileCopyrightText: 2026 Knitli Inc. -->
<!-- SPDX-License-Identifier: MIT OR Apache-2.0 -->
## 2026-04-21 - Unused unsafe import function removed
**Vulnerability:** Found an unused `_attempt_import` function in `src/codeweaver/server/mcp/server.py` that dynamically imports a module directly from unvalidated configuration (`import_module(mw.rsplit(".", 1)[0])`), leading to potential arbitrary code execution.
**Learning:** Functions that perform dynamic imports should not be left around in the codebase if they are unused, especially if they are designed to take unvalidated strings as input.
**Prevention:** Avoid dynamic imports based on configuration or inputs without strict whitelisting. Use tools like `semgrep` with python security rules to actively catch these patterns.
## 2026-04-21 - Replaced dangerous eval() with custom safe AST evaluator
**Vulnerability:** The Dependency Injection container `_safe_eval_type` function used `eval()` to resolve type strings. While wrapped in an AST validator, the use of `eval` with user-controllable strings (like type annotations) is a significant code injection risk and correctly triggered an `S307` static analysis warning.
**Learning:** `eval` shouldn't be used even when seemingly sandboxed with `{"__builtins__": safe_builtins}` and AST validation. Pydantic's `eval_type_lenient` is also not an alternative as it similarly relies on `eval` internally. The safest approach is to recursively resolve allowed AST nodes via `ast.parse` and a custom Python-side node evaluator, avoiding execution engines completely.
**Prevention:** Avoid `eval` for type resolution or any string parsing tasks entirely. Enforce static analysis checks (like Bandit or Ruff's `S` rules) and ensure exceptions are not added manually (e.g. `noqa: S307`) without strict scrutiny.
