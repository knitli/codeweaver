<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->
<!--
mcp-name: com.knitli/codeweaver
-->
<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/codeweaver-reverse.webp">
  <source media="(prefers-color-scheme: light)" srcset="docs/assets/codeweaver-primary.webp">
  <img alt="CodeWeaver logo" src="docs/assets/codeweaver-primary.webp" height="150px" width="150px">
</picture>


# CodeWeaver

### The missing abstraction layer between AI and your code

[![Python Version](https://img.shields.io/badge/python-3.12%2B-blue.svg)](https://www.python.org/downloads/)
[![License](https://img.shields.io/badge/license-MIT%20OR%20Apache--2.0-green.svg)](LICENSE)
[![Alpha Release](https://img.shields.io/badge/release-alpha%201-orange.svg)](https://github.com/knitli/codeweaver/releases)
[![MCP Compatible](https://img.shields.io/badge/MCP-compatible-purple.svg)](https://modelcontextprotocol.io)

[Installation](#-getting-started) •
[Features](#-features) •
[How It Works](#-how-it-works) •
[Documentation](#-documentation) •
[Contributing](#-contributing)

</div>

---

## 🎯 What is CodeWeaver?

**CodeWeaver gives both humans and AI a deep, structural understanding of your project** — not just text search, but real context: symbols, blocks, relationships, intent. [MCP][mcp] is just the delivery mechanism; CodeWeaver is the capability.

**If you want AI that actually knows your code instead of guessing, this is the foundation.**

> ⚠️ **Alpha Release**: CodeWeaver is in active development. [Use it, break it, shape it, help make it better][report].

---

## 🔍 Why CodeWeaver Exists

### The Problems

| Problem | Impact |
|---------|--------|
| 🔴 **Poor Context = Poor Results** | Agents are better at generating new code than understanding existing structure |
| 💸 **Massive Inefficiency** | Agents read the same huge files repeatedly (50%+ context waste is common) |
| 🔧 **Wrong Abstraction** | Tools built for humans, not for how agents actually work |
| 🔒 **No Ownership** | Existing solutions locked into specific IDEs or agent clients like Claude Code |

**The result**: Shallow, inconsistent, fragile context. And you don't control it.

### CodeWeaver's Approach

✅ **One focused capability**: Structural + semantic code understanding
✅ **Hybrid search built for code**, not text
✅ **Works offline, airgapped, or degraded**
✅ **Deploy it however you want**
✅ **One great tool instead of 30 mediocre ones**

📖 [Read the detailed rationale →][WHY]

---

## 🚀 Getting Started

### Quick Install

Using the [CLI](#cli) with [uv](https://astral.sh/uv):

```bash
# Add CodeWeaver to your project
uv add --prerelease allow --dev code-weaver

# Initialize config and MCP setup
cw init

# Verify setup
cw doctor

# Start the server
cw server
```

> **📝 Note**: `cw init` defaults to CodeWeaver's `recommended` profile, which requires:
> - 🔑 [Voyage AI API key](http://voyage.ai) (generous free tier)
> - 🗄️ [Qdrant instance](https://qdrant.tech) (cloud or local, generous free tier for cloud, free local)

🐳 **Prefer Docker?** [See Docker setup guide →](DOCKER.md)

### MCP Configuration

`cw init` will add CodeWeaver to your project's `.mcp.json`:

```json
{
  "mcpServers": {
    "codeweaver": {
      "type": "http",
      "url": "http://127.0.0.1:9328/mcp"
    }
  }
}
```

> **💡 Why HTTP?** Unlike most MCP servers, CodeWeaver defaults to `streamable-http` transport for a more predictable, smoother experience.

> ⚠️ **Warning**: While `stdio` transport is technically possible, it's **untested** and may cause issues due to complex background orchestration. Use at your own risk!

---

## ✨ Features

<table>
<tr>
<td width="50%">

### 🧠 Smart Search
- **Hybrid search** (sparse + dense)
- **AST-level understanding**
- **Semantic relationships**
- **Context-aware chunking**

</td>
<td width="50%">

### 🌐 Language Support
- **26 languages** with full AST/semantic
- **166+ languages** with intelligent chunking
- **Family heuristics** for smart parsing

</td>
</tr>
<tr>
<td>

### 🔄 Resilient & Offline
- **Automatic fallback** to local models
- **Works offline/airgapped**
- **Health monitoring** with graceful degradation
- **Better degraded than others' primary mode**

</td>
<td>

### ⚙️ Flexible Configuration
- **~15 config sources** (TOML/YAML/JSON)
- **Cloud secret stores** (AWS/Azure/GCP)
- **Hierarchical merging**
- **Environment overrides**

</td>
</tr>
<tr>
<td>

### 🔌 Provider Support
- **Multiple embedding providers**
- **Sparse & dense models**
- **Reranking support**
- [See full provider list →](overrides/partials/providers.md)

</td>
<td>

### 🛠️ Developer Experience
- **Live indexing** with file watching
- **Low CPU overhead**
- **Full CLI** (`cw` / `codeweaver`)
- **Health, metrics, status endpoints**

</td>
</tr>
</table>

---

## 🏗️ How It Works

CodeWeaver combines [AST][wiki_ask]-level understanding, semantic relationships, and hybrid embeddings (sparse + dense) to deliver both contextual and literal understanding of your codebase.

**The goal: give AI the fragments it *should* see, not whatever it can grab.**

### Architecture Highlights

```text
┌─────────────────────────────────────────────────────────┐
│                    Your Codebase                        │
└────────────────┬────────────────────────────────────────┘
                 │
                 ▼
        ┌────────────────┐
        │  Live Indexing  │ ← AST parsing + semantic analysis
        └────────┬───────┘
                 │
                 ▼
    ┌────────────────────────┐
    │   Hybrid Vector Store   │ ← Sparse + Dense embeddings
    └────────┬───────────────┘
             │
             ▼
    ┌─────────────────┐
    │  Reranking Layer │ ← Relevance optimization (heuristic and reranking model)
    └────────┬────────┘
             │
             ▼
    ┌──────────────────┐
    │   MCP Interface   │ ← Simple "find_code" tool (`find_code("authentication api")`)
    └────────┬─────────┘
             │
             ▼
       ┌─────────┐
       │   AI    │
       └─────────┘
```

### CLI Commands

```bash
cw server    # Run the MCP server
cw doctor    # Full setup diagnostic
cw index     # Run indexing without server
cw init      # Set up MCP + config
cw list      # List providers, models, capabilities
cw status    # Live server status, health, index state
cw search    # Test the search engine
cw config    # View resolved configuration
```

📖 [Full CLI Guide →][cli_guide]


---

## 📊 Current Status (Alpha)

### Stability Snapshot: Strong Core, Prickly Edges

| Component | Status | Notes |
|-----------|--------|-------|
| 🔄 **Live indexing & file watching** | ⭐⭐⭐⭐ | Runs continuously; reliable |
| 🌳 **AST-based chunking** | ⭐⭐⭐⭐ | Full semantic/AST for 26 languages |
| 📝 **Context-aware chunking** | ⭐⭐⭐⭐ | 166+ languages, heuristic AST-lite |
| 🔌 **Provider integration** | ⭐⭐⭐ | Voyage/FastEmbed reliable, others vary |
| 🛡️ **Automatic fallback** | ⭐⭐⭐ | Seamless offline/degraded mode |
| 💻 **CLI** | ⭐⭐⭐⭐ | Core commands fully wired and tested |
| 🐳 **Docker build** | ⭐⭐⭐ | Skip local Qdrant setup entirely |
| 🔗 **MCP interface** | ⭐⭐⭐ | Core ops reliable, some edge cases |
| 🌐 **HTTP endpoints** | ⭐⭐⭐ | Health, metrics, state, versions stable |

_Legend: ⭐⭐⭐⭐ = solid | ⭐⭐⭐ = works with quirks | ⭐⭐ = experimental | ⭐ = chaos gremlin_

---

## 🗺️ Roadmap

The [`enhancement`](https://github.com/knitli/codeweaver/labels/enhancement) issues describe detailed plans. Short version:

- 📚 **Way better docs** – comprehensive guides and tutorials
- 🤖 **AI-powered context curation** – agents identify purpose and intent
- 🔧 **Data provider integration** – Tavily, DuckDuckGo, Context7, and more
- 💉 **True DI system** – replace existing registry
- 🕸️ **Advanced orchestration** – integrate `pydantic-graph`

### What Will Stay: One Tool

**One tool**. We give AI agents one simple tool: `find_code`.

Agents just need to explain what they need. No complex schemas. No novella-length prompts.

---

## 📚 Documentation

### For Users
- 🐳 [Docker Setup Notes](docs/docker/DOCKER_BUILD_NOTES.md)
- 🚀 [Getting Started Guide](#-getting-started)

### For Developers
- 🏗️ [Overall Architecture](ARCHITECTURE.md)
- 🔍 [find_code API](src/codeweaver/agent_api/find_code/README.md)
- 📐 [find_code Architecture](src/codeweaver/agent_api/find_code/ARCHITECTURE.md)

### Product Philosophy
- 💭 [Product Decisions](PRODUCT.md) – transparency matters
- 🤔 [Why CodeWeaver?](docs/WHY.md) – detailed rationale

<!-- Comprehensive documentation coming soon at https://dev.knitli.com/codeweaver -->

---

## 🤝 Contributing

**PRs, issues, weird edge cases, feature requests — all welcome!**

This is still early, and the best time to help shape the direction.

### How to Contribute

1. 🍴 Fork the repository
2. 🌿 Create a feature branch
3. ✨ Make your changes
4. ✅ Add tests if applicable
5. 📝 Update documentation
6. 🚀 Submit a PR

You'll need to agree to our [Contributor License Agreement](CONTRIBUTORS_LICENSE_AGREEMENT.md).

### Found a Bug?

🐛 [Report it here][report] – include as much detail as possible!

---

## 🔗 Links

### Project
- 📦 **Repository**: [github.com/knitli/codeweaver](https://github.com/knitli/codeweaver)
- 🐛 **Issues**: [Report bugs & request features](https://github.com/knitli/codeweaver/issues)
- 📋 **Changelog**: [View release history](https://github.com/knitli/codeweaver/blob/main/CHANGELOG.md)
<!-- - 📖 **Documentation**: https://dev.knitli.com/codeweaver (in progress) -->

### Company
- 🏢 **Knitli**: [knitli.com](https://knitli.com)
- ✍️ **Blog**: [blog.knitli.com](https://blog.knitli.com)
- 🐦 **X/Twitter**: [@knitli_inc](https://x.com/knitli_inc)
- 💼 **LinkedIn**: [company/knitli](https://linkedin.com/company/knitli)
- 💻 **GitHub**: [@knitli](https://github.com/knitli)

### Support the Project

We're a [one-person company](https://github.com/bashandbone) at the moment... and make no money... if you like CodeWeaver and want to keep it going, please consider **[sponsoring me](https://github.com/sponsors/knitli)** 😄

---

## 📦 Package Info

- **Python package**: `codeweaver`
- **CLI commands**: `cw` / `codeweaver`
- **Python requirement**: ≥3.12 (tested on 3.12, 3.13, 3.14)
- **Entry point**: `codeweaver.cli.app:main`

---

## 📄 License

Licensed under **MIT OR Apache 2.0** — you choose! Some vendored code is Apache 2.0 only and some is MIT only. Everything is permissively licensed.

The project follows the [REUSE specification](https://reuse.software). Every file has detailed licensing information, and we regularly generate a [software bill of materials](sbom.spdx).

---

## 📊 Telemetry

The default includes **very anonymized telemetry** to improve CodeWeaver. [See the implementation](src/codeweaver/common/telemetry/) or read [the README](src/codeweaver/common/telemetry/README.md).

**Opt out**: `export CODEWEAVER__TELEMETRY__DISABLE_TELEMETRY=true`

**Opt in to detailed feedback** (helps us improve): `export CODEWEAVER__TELEMETRY__TOOLS_OVER_PRIVACY=true`

📋 [See our privacy policy](PRIVACY_POLICY.md)

---

## ⚠️ API Stability

> **Warning**: The API *will change*. Our priority right now is giving you and your coding agent an awesome tool.
>
> To deliver on that, we can't get locked into API contracts while we're in alpha. We also want you to be able to extend and build on CodeWeaver — once we get to stable releases.

---

<div align="center">

**Built with ❤️ by [Knitli](https://knitli.com)**

[⬆ Back to top](#codeweaver)

</div>

[cli_guide]: <docs/CLI.md> "Command Line Reference"
[config_schema]: <schema/codeweaver.schema.json> "The CodeWeaver Config Schema"
[mcp]: <https://modelcontextprotocol.io> "Learn About the Model Context Protocol"
[report]: <https://github.com/knitli/codeweaver/issues> "Report an Issue"
[wiki_ask]: <https://en.wikipedia.org/wiki/Abstract_syntax_tree> "About Abstract Syntax Trees"
[WHY]: <docs/WHY.md> "Why I built CodeWeaver"
