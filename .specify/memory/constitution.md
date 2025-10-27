<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->
<!--
Sync Impact Report - Constitution Update:
- Version change: 1.0.0 → 2.0.0 (NEW)
- Constitution created from project practices analysis
- Principles derived from AGENTS.md and CODE_STYLE.md
- Added AI-First Development, Proven Patterns, Evidence-Based Development, Testing Philosophy, and Simplicity principles
- Added Architecture Standards and Development Workflow sections
- Added comprehensive governance framework
- Templates requiring updates: ✅ updated/validated
- Follow-up TODOs: None - constitution complete and self-contained
-->

# CodeWeaver Constitution

## Core Principles

### I. AI-First Context
Deliver precise codebase context for plain language agent requests. Every feature must enhance the ability of AI agents to understand and work with code through "exquisite context." Design APIs, documentation, and tooling with AI consumption as the primary interface, not an afterthought.

**Rationale**: CodeWeaver's mission is to bridge the gap between human expectations and AI agent capabilities, making AI-first design essential for success.

### II. Proven Patterns
Leverage established abstractions and ecosystem alignment over reinvention. Channel proven architectural patterns from FastAPI, pydantic ecosystem, and established open source projects. Use familiar interfaces that reduce learning curve and increase adoption.

**Rationale**: Established patterns reduce development risk, accelerate onboarding, and provide battle-tested solutions to common problems.

### III. Evidence-Based Development (NON-NEGOTIABLE)
All technical decisions must be supported by verifiable evidence: documentation, testing, metrics, or reproducible demonstrations. No workarounds, mock implementations, or placeholder code without explicit user authorization. "No code beats bad code."

**Rationale**: Evidence-based development ensures reliability, maintainability, and prevents technical debt from accumulating.

### IV. Testing Philosophy
Effectiveness over coverage. Focus on critical behavior affecting user experience, realistic integration scenarios, and input/output validation. Integration testing preferred over unit testing. One solid, realistic test beats ten implementation detail tests.

**Rationale**: Testing should validate real-world usage patterns and prevent user-affecting bugs, not just achieve coverage metrics.

### V. Simplicity Through Architecture
Transform complexity into clarity. Use simple modularity with extensible yet intuitive design where purpose should be obvious. Implement flat structure grouping related modules in packages while avoiding unnecessary nesting.

**Rationale**: Simplicity enables maintainability, reduces bugs, and makes the codebase accessible to contributors.

## Architecture Standards

### Plugin Architecture Requirements
All major system components (embedding, reranking, vector-stores, services) must implement protocol-based interfaces and register with the associated registry in `_registry.py`. Components must be discoverable at runtime and support dynamic instantiation with health monitoring.

### Type System Discipline
Strict typing. Use `TypedDict`, `Protocol`, `NamedTuple`, `enum.Enum` for structured data. Avoid generic types like `dict[str, Any]` when structure is known. All public functions require type annotations.

### Configuration Management
Hierarchical configuration via `pydantic-settings` with environment variables and TOML support. All settings must be documentable and validateable. No hardcoded values in implementation code.

## Development Workflow

### Code Review Gates
- Evidence-based justification for architectural decisions
- Type system compliance verification
- Integration test coverage for critical paths
- Documentation updates for public interfaces

### Quality Standards
- Google docstring convention written in plain language with active voice
- 100-character line length limit
- Modern Python typing (>=3.12) with latest syntax patterns
- Ruff auto-formatting and linting compliance

### Red Flag Protocol
When APIs behave unexpectedly, files aren't where expected, or code contradicts documentation:
1. Stop current work immediately
2. Review understanding and plans systematically
3. Research using available tools and agents
4. Ask user for clarification if still unclear
5. Never create workarounds without explicit authorization

## Governance

This constitution supersedes all other development practices. All code reviews, feature planning, and technical decisions must verify compliance with these principles.

**Amendment Process**: Constitution changes require documentation of rationale, impact analysis, and migration plan for affected code. Version bumps follow semantic versioning (MAJOR for principle changes, MINOR for new sections, PATCH for clarifications).

**Enforcement**: Use AGENTS.md for runtime development guidance. All team members must validate architectural decisions against these principles before implementation.

**Complexity Justification**: Any deviation from these principles must be documented with specific rationale and simpler alternatives considered. Technical debt must be explicitly tracked and addressed.

**Version**: 2.0.1 | **Ratified**: 2025-09-23 | **Last Amended**: 2025-10-18