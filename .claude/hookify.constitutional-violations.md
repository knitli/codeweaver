---
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

name: constitutional-violations
enabled: true
event: file
conditions:
  - field: new_text
    operator: regex_match
    pattern: (TODO|FIXME|NotImplementedError|raise NotImplementedError|mock|stub|placeholder|fake_data|// not implemented|\.\.\.|pass\s*#\s*(todo|fixme|not impl))|eval\(
---

⚠️ **Constitutional Principle III violation detected**

You may be adding code that violates the Project Constitution (Evidence-Based Development). 

**Constitutional Principle III states:**
> "No code beats bad code. Fix underlying issues, don't use placeholders. All code must be production-ready."

**Violations detected:**
- ❌ TODO/FIXME comments for core functionality
- ❌ NotImplementedError or similar stub implementations
- ❌ Mock objects or fake data in actual code
- ❌ Placeholder comments like "..." or "pass"
- ❌ Eval or dangerous patterns

**Constitutional requirements:**
- ✅ All generated code must be production-ready, not scaffolding
- ✅ Never leave TODO for core functionality or implementations
- ✅ No mock objects, fake data, or stub implementations
- ✅ Every function must work as specified, not throw NotImplementedError
- ✅ Complete implementations, not partial code

**Exceptions:**
- If the user explicitly requested that you leave something unfinished or marked TODO, follow their direction. 
- If you are unsure, ask the user for clarification on how to leave the implementation.
- When you are executing a development plan and the code requires later phases to be completed before returning to finish.

**What to do:**
1. **Complete the implementation fully** - Don't leave TODOs in code
2. **Implement properly** - Write real code, not stubs
3. **Ask for clarification** - If requirements unclear, ask the user
4. **Fix underlying issues** - Address root causes, not symptoms
5. **Before ending a task or project** - Review the work and ensure there are no placeholders or TODOs left -- address them or seek user direction.

**The Constitution is non-negotiable** - All work must comply with these principles. Please revise this code before continuing.

Reference: `.specify/memory/constitution.md` (v2.0.1) - Principle III: Evidence-Based Development
