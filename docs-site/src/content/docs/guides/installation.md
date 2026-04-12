---
title: "Installation and Setup"
---

# Installation & Setup

> **TL;DR:** This guide handles the initial installation and configuration of CodeWeaver. Use it to set up your environment and prepare your codebase for AI agent interaction. It saves time by providing a streamlined path from empty directory to "Exquisite Context."

CodeWeaver transforms your codebase into a structured, semantic search engine for AI agents. This guide walks you through the 5-minute setup process to get CodeWeaver running on your machine.

---

## 1. Prerequisites

Before installing CodeWeaver, ensure you have the following:

- **Python 3.12 or 3.13:** CodeWeaver leverages modern Python features.
- **`uv` Package Manager:** We recommend [uv](https://astral.sh/uv) for fast, reliable dependency management.
- **A Codebase:** Any local directory containing source code or documentation.

---

## 2. Install CodeWeaver

Add CodeWeaver to your project using `uv`. This ensures that CodeWeaver and its dependencies are isolated and manageable.

```bash
# Add CodeWeaver as a development dependency
uv add --dev code-weaver
```

---

## 3. Initialize Your Project

The `cw init` command sets up your configuration and prepares your repository for indexing. You must choose a **Profile** during initialization.

### Option A: The Recommended Setup (Cloud + Local)
Best for production use and high-precision search. It requires a [Voyage AI API Key](https://voyage.ai).

```bash
cw init --profile recommended
```

### Option B: The Quickstart Setup (100% Local)
Best for privacy and offline development. It requires no API keys and runs entirely on your machine.

```bash
cw init --profile quickstart
```

---

## 4. Configure Your Environment

If you chose the `recommended` profile, you must provide your API keys. CodeWeaver reads these from your environment or a `.env` file in your project root.

```bash
# Example .env file
VOYAGE_API_KEY="your-voyage-key-here"
ANTHROPIC_API_KEY="your-anthropic-key-here"  # Required for the Context Agent
```

---

## 5. Start the Services

CodeWeaver runs as a background daemon that manages indexing and serves the MCP (Model Context Protocol) interface.

### Start the Daemon
This command starts the background indexer and the management server.

```bash
cw start
```

### Verify the Installation
Run the diagnostic tool to ensure everything is configured correctly.

```bash
cw doctor
```

---

## 6. Next Steps

Now that CodeWeaver is running, you can:

- **Index your code:** Run `cw index` to build your first search index.
- **Search manually:** Use `cw search "your query"` to test the results.
- **Connect an Agent:** Add CodeWeaver to your `.mcp.json` to give Claude or other agents exquisite context.

For a deeper dive into how to customize your setup, see the [Configuration Architecture](./configuration.md) guide.
