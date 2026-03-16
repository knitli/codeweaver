---
title: "The Roadmap to Alpha 7"
---

# The Roadmap to Alpha 7

> **TL;DR:** This page handles Alpha Status Transparency. Use it to understand where CodeWeaver is heading. It saves you from surprises by outlining the upcoming transition to a high-performance monorepo structure.

CodeWeaver Alpha 6 marks the stabilization of our core infrastructure. With the Dependency Injection (DI) system and configuration overhaul complete, we are now preparing for the next major milestone: **The Monorepo Split.**

---

## Current Status: Alpha 6 (Stability)

Alpha 6 is about **Industrial-Grade Context**. We have replaced fragmented registries with a unified, FastAPI-inspired DI system. This ensures that CodeWeaver is no longer just a "search tool," but a professional infrastructure component for AI agents.

**Key Achievements in Alpha 6:**
- **100% DI Integration:** Every service is now registered and injected via the `@dependency_provider` system.
- **Config Validation:** Pydantic-driven settings catch errors before they reach your agents.
- **Resilient Pipeline:** Automatic local fallbacks ensure 100% context availability.

---

## The Next Step: Alpha 7 (Extensibility)

The primary goal of Alpha 7 is the **Monorepo Split**. We are reorganizing the codebase into independent, selectively installable packages.

### 1. Package Separation
Currently, CodeWeaver is a single large package. In Alpha 7, it will be split into:
- `codeweaver-core`: The base infrastructure, DI container, and logging.
- `codeweaver-providers`: Embedding, vector store, and agent integrations.
- `codeweaver-engine`: The indexing and search logic.
- `codeweaver-server`: The MCP and Management server components.

### 2. Selective Installation
The monorepo structure allows you to install only what you need. If you are building a custom search engine, you might only install `core` and `engine`. If you only need MCP connectivity, you might only install `core` and `server`.

### 3. "Pulling the Bandaid" Refactor
Alpha 7 completes the architectural cleanup started in Alpha 6. We are removing the last remnants of legacy registries and hardcoded imports, ensuring that each package is truly independent and "monorepo-safe."

---

## Beyond Alpha 7: The Vision

Our long-term goal is to establish CodeWeaver as the **Universal Context Layer** for AI.

- **Alpha 8:** Enhanced cloud orchestration and distributed indexing.
- **Alpha 9:** Multi-tenant support and advanced access controls.
- **Beta 1:** API stability and performance-at-scale guarantees.

We are building CodeWeaver in the open, and we welcome feedback from the community as we transition into this new high-performance architecture.
