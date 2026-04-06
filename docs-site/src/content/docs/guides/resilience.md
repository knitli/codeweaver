---
title: "Resilience: The Safety Net"
---

# Resilience: The Safety Net

> **TL;DR:** This module handles Resilient Intelligence. Use it to ensure your agents never lose context, even when cloud APIs fail. It saves your workflow by automatically switching to local providers (FastEmbed/Sentence-Transformers) during outages.

CodeWeaver includes an industrial-grade "Safety Net" that protects your AI agents from cloud provider failures. Whether it's an API timeout, a rate limit, or a total service outage, CodeWeaver keeps your context pipeline flowing.

---

## How It Works: The Multi-Vector Approach

Unlike traditional search tools that rely on a single model, CodeWeaver uses a **Multi-Vector** architecture. When you index your code, the system generates both your primary cloud embeddings and a set of lightweight "backup" embeddings stored on the same data points.

### 1. Automatic Cloud Fallback
If your primary embedding provider (e.g., Voyage AI) becomes unreachable, CodeWeaver detects the failure in milliseconds. It immediately reroutes all search queries to your local backup provider (FastEmbed or Sentence-Transformers). Your agent receives relevant context without ever seeing an "API Error."

### 2. Resilient Vector Storage
If you use a cloud vector store and it fails, CodeWeaver switches to a local backup. The system maintains this backup using:
- **Regular Snapshots:** Point-in-time copies of your index.
- **Write-Ahead Logging (WAL):** A record of every change made since the last snapshot.

### 3. Interchangeable Reranking
Reranking models are interchangeable by design. If your high-precision cloud reranker fails, CodeWeaver falls back to a local reranking model to ensure your search results are still prioritized by relevance.

---

## Configuration

The Safety Net is **enabled by default** for all cloud-based profiles. You don't need to do anything to turn it on.

### Disabling the Safety Net
If you are running in a strictly resource-constrained environment or a 100% airgapped local setup, you can disable the backup system in your `codeweaver.toml`:

```toml
[provider]
disable_backup_system = true
```

> **Warning:** Disabling the backup system means CodeWeaver will stop working if your primary cloud providers are unreachable. We do not recommend this for production environments.

---

## Supported Local Providers

CodeWeaver integrates with industry-standard local embedding libraries to provide its Safety Net:

| Provider | Library | Best For |
| :--- | :--- | :--- |
| **FastEmbed** | `fastembed` | High-performance CPU-based fallback. |
| **Sentence-Transformers** | `sentence-transformers` | GPU-accelerated local search. |
| **BM25** | Built-in | Traditional keyword fallback when all else fails. |

---

## Why Resilience Matters

For AI agents, **Context is Oxygen**. If an agent loses access to its context tool (CodeWeaver), it can become confused, hallucinate, or fail to complete its task. By providing a transparent Safety Net, CodeWeaver ensures your agents remain productive regardless of cloud status.
