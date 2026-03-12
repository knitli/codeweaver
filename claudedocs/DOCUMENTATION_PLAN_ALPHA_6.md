# CodeWeaver Alpha 6 Documentation Plan

**Status:** Finalized (Alpha 6 Release Strategy)  
**Focus:** Stability, Extensibility (DI), and Resilient Infrastructure  
**Date:** March 12, 2026

---

## 1. Executive Summary: The Alpha 6 Narrative
CodeWeaver Alpha 6 marks the transition from a "Search Tool" to a **Professional Context Management Platform**. With the DI system 100% implemented and the configuration system completely overhauled, the documentation will focus on **Industrial-Grade Context**—infrastructure that is extensible, predictable, and resilient.

### Core Value Propositions
*   **Universal Extensibility (DI):** Swapping providers is now a configuration change, not a code change.
*   **Predictable Configuration:** Pydantic-driven validation catches setup errors at boot-time.
*   **Resilient Intelligence:** A simplified fallback system ensures agents never lose context, even when cloud APIs fail.

---

## 2. Proposed Site Structure (`docs-site/src/content/docs/`)

### A. Getting Started (The 5-Minute Path)
*   **The Hero Page (`index.mdx`):** "Exquisite Context for Agents." Visual before/after.
*   **Installation & Setup:** `uv add` and `cw init`.
*   **Choosing a Profile:** Deep dive into `recommended` (VoyageAI/Qdrant) vs. `quickstart` (Local/Free).

### B. Core Concepts (The "Why")
*   **The DI Architecture (`concepts/di-system.md`):** Explaining the `@dependency_provider` pattern and why it makes CodeWeaver the most extensible tool in its class.
*   **Exquisite Context:** Hybrid search (Semantic + AST + Keyword) and how it reduces token waste by 60–80%.
*   **Language Support:** Deep AST (27 languages) vs. Heuristic (166+ languages).

### C. Guides (Workflow Focused)
*   **Resilience & Fallbacks:** Configuring the "Safety Net" with local providers (`fastembed`, `sentence-transformers`).
*   **Local-Only Operation:** Running 100% airgapped for sensitive codebases.
*   **Custom Providers:** A step-by-step guide to plugging in niche embedding or vector stores via the DI system.

### D. Reference (The Deep Dive)
*   **Configuration Schema:** Documenting the new `core_settings` and `provider_settings` hierarchy.
*   **CLI 2.0:** Updated `cw` command reference with enhanced Alpha 6 diagnostics (`cw doctor`).
*   **Provider Registry:** A full menu of the 17+ integrated providers.

---

## 3. Content Design & Scoping (The "Human" Lens)

Each page will feature a **"Context Box"** for rapid assessment:
> **TL;DR:** This module handles [Feature]. Use it when you need [Value]. It saves [X%] tokens by [Mechanism].

### Key Content Shifts
*   **From "Internal Reports" to "Operational Value":** We will distill research from `claudedocs/` into "How-to" guides.
*   **Alpha Status Transparency:** A "Living Roadmap" page linking the `di_monorepo` refactor to the upcoming Alpha 7 monorepo deployment.

---

## 4. Implementation Task List

| Priority | Task | Target Deliverable |
| :--- | :--- | :--- |
| **P0** | **Refresh Hero Page** | `index.mdx` with the Comparison Matrix. |
| **P0** | **Write DI Guide** | Explaining the `INJECTED` and `Depends` markers. |
| **P1** | **Document Config Overhaul** | Highlighting the new validation and hierarchy. |
| **P1** | **Resilience Guide** | Explaining the simplified backup system. |
| **P2** | **Roadmap to Alpha 7** | Setting expectations for the monorepo split. |

---

## 5. Strategic Alignment
This plan aligns with the **Project Constitution** (AI-First Context, Proven Patterns) and leverages the technical maturity of the `di_monorepo` branch to establish CodeWeaver as the premier context infrastructure for developers and their AI agents.
