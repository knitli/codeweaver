---
title: "Choosing a Profile"
---

# Choosing a Profile

> **TL;DR:** CodeWeaver Alpha 6 uses Profiles to simplify setup. Use `recommended` for production-grade search (Voyage AI) or `quickstart` for a free, local-only experience (FastEmbed). Profiles save you from manual configuration by bundling optimized provider settings.

CodeWeaver offers three primary profiles to meet different cost, performance, and privacy requirements. You can select a profile during initialization with `cw init --profile <name>`.

---

## Profile Comparison

| Feature | `recommended` | `quickstart` | `testing` |
| :--- | :--- | :--- | :--- |
| **Best For** | Production, High Precision | Local Dev, Privacy | CI/CD, Unit Tests |
| **Cloud/Local** | Hybrid (Cloud + Local) | 100% Local | 100% In-Memory |
| **Embedding** | Voyage AI (Cloud) | FastEmbed (Local) | FastEmbed (Local) |
| **Vector Store** | Qdrant (Local/Cloud) | Qdrant (Local) | In-Memory |
| **Reranking** | Voyage AI (Cloud) | FastEmbed (Local) | None |
| **Cost** | API Usage Fees | **Free** | **Free** |
| **Search Quality** | **Exquisite** | Good | Minimal |
| **API Keys** | Required (Voyage AI) | **None** | **None** |

---

## 1. The `recommended` Profile
This is our flagship configuration designed for professional AI agents. It leverages **Voyage AI**'s state-of-the-art code embedding models.

- **Why choose it:** You need the highest possible search precision to prevent agent hallucinations.
- **Requirement:** A Voyage AI API key (`VOYAGE_API_KEY`).
- **Resilience:** Includes the automatic "Safety Net" (FastEmbed) for cloud outages.

## 2. The `quickstart` Profile
Perfect for individual developers or teams working on sensitive, airgapped codebases.

- **Why choose it:** You want a completely free experience with no external API dependencies, or you need to keep 100% of your code on your machine.
- **Mechanism:** Uses `fastembed` and `sentence-transformers` to run models directly on your CPU/GPU.
- **Search Quality:** Highly capable, though slightly less precise than specialized cloud models.

## 3. The `testing` Profile
Designed for automated testing and continuous integration.

- **Why choose it:** You need a volatile, high-speed environment for unit or integration tests that doesn't persist data to disk.
- **Mechanism:** Uses an in-memory vector store and the lightest weight models available.

---

## Switching Profiles

You can switch profiles at any time by re-running the initialization command. Note that switching profiles may require you to re-index your codebase if the embedding dimensions change.

```bash
# Switch to the free local profile
cw init --profile quickstart --force

# Re-index to use the new local models
cw index --force
```

---

## Which one should I use?

- **"I'm building a professional tool for my team."** → Use `recommended`.
- **"I just want to try CodeWeaver for free."** → Use `quickstart`.
- **"I'm running this on my laptop with no internet."** → Use `quickstart`.
- **"I'm writing a test suite for my CodeWeaver plugin."** → Use `testing`.
