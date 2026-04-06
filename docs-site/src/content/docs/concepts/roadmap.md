---
title: "Roadmap"
---

# Roadmap

> **TL;DR:** This page outlines where CodeWeaver is heading. It saves you from surprises by providing transparency on upcoming changes and the path to 1.0.

CodeWeaver has completed a major infrastructure overhaul. With the Dependency Injection (DI) system and configuration rewrite complete, we are now preparing for the next milestones: **the Monorepo Split** and **Context Agent integration**.

---

## Current Status: 0.1.0 (Stable Foundation)

The 0.1.x series represents **Industrial-Grade Context**. We have replaced fragmented registries with a unified, FastAPI-inspired DI system. CodeWeaver is no longer just a "search tool" — it is a professional infrastructure component for AI agents.

**Key Achievements:**
- **100% DI Integration:** Every service is now registered and injected via the `@dependency_provider` system.
- **Config Validation:** Pydantic-driven settings catch errors before they reach your agents.
- **Resilient Pipeline:** Automatic local fallbacks ensure 100% context availability.

---

## Next: 0.2.0 (Extensibility)

The primary goal of 0.2.0 is the **Monorepo Split**. We are reorganizing the codebase into independent, selectively installable packages.

### 1. Package Separation
Currently, CodeWeaver is a single large package. In 0.2.0, it will be split into:
- `codeweaver-core`: The base infrastructure, DI container, and logging.
- `codeweaver-providers`: Embedding, vector store, and agent integrations.
- `codeweaver-engine`: The indexing and search logic.
- `codeweaver-server`: The MCP and Management server components.

### 2. Selective Installation
The monorepo structure allows you to install only what you need. If you are building a custom search engine, you might only install `core` and `engine`. If you only need MCP connectivity, you might only install `core` and `server`.

### 3. Legacy Cleanup
0.2.0 completes the architectural cleanup. We are removing the last remnants of legacy registries and hardcoded imports, ensuring that each package is truly independent and "monorepo-safe."

---

## The Path to 1.0

Our long-term goal is to establish CodeWeaver as the **Universal Context Layer** for AI.

- **0.3.0:** Context Agent integration and agentic pipeline orchestration.
- **0.4.0:** Enhanced cloud orchestration and distributed indexing.
- **1.0.0:** API stability guarantees, performance-at-scale, and production hardening.

We are building CodeWeaver in the open, and we welcome feedback from the community as we move toward a stable 1.0 release.
