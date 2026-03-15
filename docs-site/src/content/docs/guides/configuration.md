---
title: "Configuration Architecture"
---

# Configuration Architecture

> **TL;DR:** CodeWeaver Alpha 6 features a completely overhauled configuration system powered by Pydantic. Use it to define your providers, server settings, and performance limits. It catches setup errors at boot-time, ensuring your agent always has a reliable foundation.

The configuration system is hierarchical, predictable, and strictly validated. Whether you use environment variables, a `.env` file, or a `codeweaver.toml`, the system ensures your settings are consistent before the application starts.

---

## The Configuration Hierarchy

CodeWeaver uses a nested structure to organize settings. The top-level `CodeWeaverSettings` model contains several logical sections:

### 1. Core Settings
Shared across all installations (Core, Provider, Engine, and Server).
- `logging`: Log levels and formats.
- `telemetry`: Privacy-preserving usage reporting.
- `project_path`: The root of your codebase.

### 2. Provider Settings (`[provider]`)
This is where you define the "brains" of CodeWeaver.
- `embedding`: Primary and query embedding models.
- `sparse_embedding`: Models for hybrid search.
- `reranking`: The final "judge" that ranks the most relevant snippets.
- `vector_store`: Where your embeddings are stored (e.g., Qdrant).
- `agent`: Configuration for the Context Agent (e.g., Anthropic Claude).

### 3. Server Settings
Specific to the CodeWeaver daemon and MCP integration.
- `mcp_server`: HTTP and Stdio transport settings.
- `management_port`: Port for health checks and metrics (default: 9329).
- `uvicorn`: Web server tuning.

---

## Validation & Reliability

CodeWeaver Alpha 6 uses **Pydantic V2** to enforce strict validation. This means:

1.  **Boot-time Failure:** If you provide an invalid URL or a missing API key, CodeWeaver will fail immediately with a clear error message instead of crashing later during a search.
2.  **Type Safety:** Numbers, booleans, and nested objects are automatically converted and validated.
3.  **Discriminator Support:** The system automatically picks the correct configuration schema based on your `provider` name (e.g., if you set `provider = "voyage"`, it expects Voyage-specific options).

---

## Profiles: The Fast Track

Instead of configuring every provider manually, you can use a **Profile**. Profiles are pre-configured bundles that balance cost, quality, and performance.

| Profile | Best For | Requirement |
| :--- | :--- | :--- |
| **`recommended`** | Production use, high precision. | Voyage AI API Key. |
| **`quickstart`** | Local development, testing. | No API keys (FastEmbed/Local Qdrant). |
| **`testing`** | CI/CD, unit tests. | In-memory storage. |

You can activate a profile during initialization:
```bash
cw init --profile recommended
```

---

## Precedence Order

When the same setting is defined in multiple places, CodeWeaver follows this priority:

1.  **Environment Variables** (e.g., `CODEWEAVER_LOGGING__LEVEL=DEBUG`)
2.  **Explicit `init` arguments**
3.  **Local `.env` files**
4.  **Project-level `codeweaver.toml`**
5.  **User-level config** (e.g., `~/.config/codeweaver/config.toml`)
6.  **Defaults**
