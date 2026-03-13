# Exquisite Context

> **TL;DR:** This page explains the "Exquisite Context" philosophy. Use it to understand how CodeWeaver's Hybrid Search (Semantic + AST + Keyword) provides high-precision snippets. It saves 60–80% of token costs by eliminating irrelevant code from your agent's context.

AI agents often fail because they receive too much noise. When you provide a whole file for a single-function fix, you waste tokens, increase costs, and confuse the model. CodeWeaver solves this by delivering **Exquisite Context**—the exact structural and semantic matches an agent needs to perform its task.

---

## The 60–80% Context Reduction

Traditional search tools often return thousands of tokens of irrelevant code. CodeWeaver uses a multi-signal approach to filter out the noise, typically reducing the context size by **60–80%** while maintaining over **90% relevance.**

### Why It Matters
- **Lower Costs:** Fewer tokens mean smaller bills from LLM providers.
- **Higher Accuracy:** Agents are less likely to hallucinate when focused on specific, relevant code.
- **Faster Responses:** Smaller prompts result in faster processing and response times.

---

## The Hybrid Search Pipeline

CodeWeaver doesn't just look for keywords. It combines three distinct signals into a single, unified search result:

### 1. Semantic Search (Dense Embeddings)
Captures the **intent** of your query. If you search for "user login," semantic search finds code related to authentication, even if the word "login" isn't in the file.

### 2. Keyword Search (Sparse Embeddings)
Captures the **specifics**. Sparse embeddings act like a high-performance keyword index (BM25), ensuring that exact matches for function names, variable names, and error codes are never missed.

### 3. Structural Analysis (AST)
Captures the **hierarchy**. CodeWeaver understands that a function belongs to a class, and that class belongs to a module. By leveraging Abstract Syntax Trees (AST) for 27 languages, CodeWeaver identifies logical boundaries and relationships that simple text search ignores.

---

## How It Works: Unified Ranking

When you perform a search, CodeWeaver executes these signals in parallel. The results are then combined using **Reciprocal Rank Fusion (RRF)** and weighted based on your configuration.

1.  **Retrieve:** Query dense and sparse vectors simultaneously.
2.  **Analyze:** Apply AST-aware filters to ensure code snippets are logical and complete.
3.  **Rank:** Use RRF to normalize scores across different signal types.
4.  **Rerank (Optional):** Use a dedicated reranking model (like Voyage AI or Cohere) to perform a final "sanity check" on the top results.

---

## Span-Based Precision

Unlike tools that return arbitrary "chunks" of text, CodeWeaver uses an immutable **Span-Based Architecture**. Each search result is a precise coordinate (file, line, column) that accurately represents the code's location in your project. This allows agents to understand exactly where to apply their changes without guesswork.

---

## Summary: Curation over Collection

"Exquisite Context" is about **curation**, not just collection. By providing AI agents with high-precision, structurally-aware snippets, CodeWeaver enables them to work deeper, faster, and more reliably in complex codebases.
