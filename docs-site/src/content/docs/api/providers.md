---
title: "Provider Registry"
---

# Provider Registry

> **TL;DR:** CodeWeaver Alpha 6 supports **17+ embedding providers** and multiple vector stores. Use this registry to find the right "brains" for your project. It saves you from vendor lock-in by providing a unified interface for the industry's best models.

CodeWeaver's DI-driven architecture allows it to integrate with a wide range of cloud and local providers. Below is a comprehensive list of currently supported integrations.

---

## Embedding Providers (Dense & Sparse)

These providers generate the mathematical representations of your code used for semantic search.

| Provider | Type | Best For | Requirement |
| :--- | :--- | :--- | :--- |
| **Voyage AI** | Cloud | State-of-the-art code embeddings. | `VOYAGE_API_KEY` |
| **OpenAI** | Cloud | Industry standard, wide model selection. | `OPENAI_API_KEY` |
| **Cohere** | Cloud | High-performance multilingual models. | `COHERE_API_KEY` |
| **Anthropic** | Cloud | Context Agent integration. | `ANTHROPIC_API_KEY` |
| **Mistral AI** | Cloud | Efficient, high-quality open models. | `MISTRAL_API_KEY` |
| **AWS Bedrock** | Cloud | Enterprise-grade hosted models. | AWS Credentials |
| **Google GenAI** | Cloud | Gemini-integrated embeddings. | `GOOGLE_API_KEY` |
| **HuggingFace** | Cloud/Local | Access to thousands of open-source models. | Optional API Key |
| **FastEmbed** | Local | High-speed, local-only CPU inference. | None (Local) |
| **Sentence-Transformers** | Local | Deep, local-only GPU/CPU search. | None (Local) |

---

## Vector Store Providers

These providers store your embeddings and perform the actual similarity search.

| Provider | Type | Best For | Requirement |
| :--- | :--- | :--- | :--- |
| **Qdrant (Local)** | Local | High-performance, persistent local search. | None (Local) |
| **Qdrant (Cloud)** | Cloud | Scalable, managed vector storage. | Qdrant Cloud URL/Key |
| **In-Memory** | Local | Ephemeral storage for tests and small projects. | None (Local) |

---

## Reranking Providers

Rerankers perform a second, deeper analysis of search results to ensure the most relevant code is at the top.

| Provider | Type | Best For |
| :--- | :--- | :--- |
| **Voyage AI** | Cloud | Specialized code reranking. |
| **Cohere** | Cloud | Industry-standard reranking precision. |
| **FastEmbed** | Local | Fast, local-only reranking. |
| **Sentence-Transformers** | Local | Flexible local reranking models. |

---

## Data Source Providers

Optional integrations for pulling in external context during a search.

| Provider | Type | Use Case |
| :--- | :--- | :--- |
| **Tavily** | Cloud | AI-optimized web search. |
| **Exa** | Cloud | Neural search for the web. |
| **DuckDuckGo** | Cloud | Free, privacy-focused web search. |

---

## Adding More Providers

Don't see your favorite provider? CodeWeaver's DI system makes it easy to add your own. See the [Custom Providers](/guides/custom-providers/) guide to learn how to extend the registry.
