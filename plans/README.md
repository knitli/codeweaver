<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# CodeWeaver Planning Documents

This directory contains planning, architecture, and specification documents for CodeWeaver development.

## Active Planning Documents

### Dependency Injection Architecture (NEW - 2025-10-31)

**Status**: Awaiting user feedback and approval

1. **[DI_ARCHITECTURE_SUMMARY.md](./DI_ARCHITECTURE_SUMMARY.md)** (5KB)
   - Quick reference and executive summary
   - Start here for overview
   - Before/after comparisons
   - Key benefits and timeline

2. **[dependency-injection-architecture-plan.md](./dependency-injection-architecture-plan.md)** (32KB)
   - Comprehensive technical plan
   - Full architecture details
   - Risk analysis and mitigation
   - Implementation phases
   - Migration strategy

3. **[DI_ARCHITECTURE_DIAGRAMS.md](./DI_ARCHITECTURE_DIAGRAMS.md)** (15KB)
   - Visual architecture diagrams
   - Flow comparisons
   - Code examples with illustrations
   - Migration timeline visualization

**Overview**: Proposes FastAPI-inspired dependency injection to replace manual provider instantiation. Aims to reduce boilerplate by 60-70%, improve testability, and scale gracefully to 100+ providers.

**Target**: v0.2 (foundation + core migration) and v0.3 (advanced features)

---

### General Implementation

4. **[IMPLEMENTATION_PLAN.md](./IMPLEMENTATION_PLAN.md)** (14KB)
   - Overall project roadmap
   - Feature priorities
   - Release planning

---

### Feature Specifications

5. **[flexible-extension-system-spec.md](./flexible-extension-system-spec.md)** (24KB)
   - Extension and plugin system design
   - Custom provider integration
   - API extensibility

6. **[node_type_parser_implementation_spec.md](./node_type_parser_implementation_spec.md)** (43KB)
   - AST node type parsing specification
   - Language support details
   - Parser implementation guide

---

### Telemetry & Monitoring

7. **[telemetry-integration-checklist.md](./telemetry-integration-checklist.md)** (11KB)
   - Telemetry integration tasks
   - Implementation checklist
   - Testing requirements

8. **[telemetry-metrics-implementation-plan.md](./telemetry-metrics-implementation-plan.md)** (37KB)
   - Comprehensive telemetry design
   - Metrics collection strategy
   - Privacy and compliance considerations

---

## Document Status Legend

| Status | Meaning |
|--------|---------|
| ✅ **Approved** | Ready for implementation |
| 🚧 **In Progress** | Currently being implemented |
| ⏳ **Awaiting Review** | Needs user feedback/approval |
| 📋 **Draft** | Work in progress, not final |
| 📦 **Archived** | Historical reference only |

---

## How to Use These Documents

### For Contributors

1. **Starting a new feature?**
   - Check if a spec exists here first
   - Follow architectural patterns from approved specs
   - Reference DI architecture for provider-related work

2. **Implementing DI system?**
   - Start with `DI_ARCHITECTURE_SUMMARY.md` for quick overview
   - Read full plan in `dependency-injection-architecture-plan.md`
   - Use diagrams in `DI_ARCHITECTURE_DIAGRAMS.md` for reference
   - Follow phase-by-phase implementation approach

3. **Adding telemetry?**
   - Review telemetry integration checklist
   - Follow metrics implementation plan
   - Ensure privacy compliance

### For Reviewers

1. **Architecture reviews**
   - Verify alignment with specs in this directory
   - Check constitutional compliance (see `.specify/memory/constitution.md`)
   - Ensure consistency across features

2. **DI architecture review**
   - Evaluate phases and risk mitigation
   - Assess FastAPI pattern alignment
   - Verify backward compatibility plan
   - Consider scaling implications

### For Product Planning

1. **Release planning**
   - Consult `IMPLEMENTATION_PLAN.md` for roadmap
   - Review DI plan for v0.2/v0.3 scope
   - Consider dependencies between features

2. **Feature prioritization**
   - Specs here represent significant engineering investment
   - DI architecture is foundational for future expansion
   - Balance quick wins vs. long-term architecture

---

## Creating New Planning Documents

When adding new planning documents to this directory:

1. **Follow naming convention**: `kebab-case-descriptive-name.md`
2. **Include SPDX headers** (copyright and license)
3. **Add status section** at the top of the document
4. **Link to related docs** (constitution, architecture, other specs)
5. **Update this README** with a summary entry
6. **Tag with creation/update date**

### Planning Document Template

```markdown
<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Your Name <your@email.com>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Feature/Architecture Name

**Status**: Draft / Awaiting Review / Approved / In Progress  
**Created**: YYYY-MM-DD  
**Last Updated**: YYYY-MM-DD  
**Target Release**: vX.X

## Executive Summary

Brief overview of what this document covers.

## [Rest of document structure...]
```

---

## Questions?

- **Architecture questions**: See `ARCHITECTURE.md` in repository root
- **Constitutional questions**: See `.specify/memory/constitution.md`
- **Code style questions**: See `CODE_STYLE.md` in repository root
- **Contribution questions**: See `AGENTS.md` in repository root

---

## Document History

| Date | Document | Action |
|------|----------|--------|
| 2025-10-31 | DI Architecture (3 docs) | Added comprehensive DI planning |
| (earlier) | Various specs | Original planning documents |

---

**Maintenance**: This README should be updated whenever new planning documents are added or significant changes are made to existing ones.
