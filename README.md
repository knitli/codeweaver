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

[![Python Version][badge_python]][link_python]
[![License][badge_license]][link_license]
[![Alpha Release][badge_release]][link_release]
[![MCP Compatible][badge_mcp]][link_mcp]

[Installation][nav_install] •
[Features][nav_features] •
[How It Works][nav_how_it_works] •
[Documentation][nav_docs] •
[Contributing][nav_contributing]

</div>

---

## 🎯 What is CodeWeaver?

**CodeWeaver gives both humans and AI a deep, structural understanding of your project** — not just text search, but real context: symbols, blocks, relationships, intent. [MCP][mcp] is just the delivery mechanism; CodeWeaver is the capability.

**If you want AI that actually knows your code instead of guessing, this is the foundation.**

> ⚠️ **Alpha Release**: CodeWeaver is in active development. [Use it, break it, shape it, help make it better][issues].

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

📖 [Read the detailed rationale →][why_codeweaver]

---

## 🚀 Getting Started

### Quick Install

Using the [CLI](#cli) with [uv][uv_tool]:

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
> - 🔑 [Voyage AI API key][voyage_ai] (generous free tier)
> - 🗄️ [Qdrant instance][qdrant] (cloud or local, generous free tier for cloud, free local)

🐳 **Prefer Docker?** [See Docker setup guide →][docker_guide]

### MCP Configuration

CodeWeaver uses **stdio transport by default**, which proxies to the HTTP backend daemon. First start the daemon with `codeweaver start`, then MCP clients can connect via stdio.

`cw init` will add CodeWeaver to your project's `.mcp.json`:

```json "with stdio (default):"
{
  "mcpServers": {
    "codeweaver": {
      "type": "stdio",
      "cmd": "uv",
      "args": ["run", "codeweaver", "server"],
      "env": {"SOME_API_KEY_FOR_PROVIDERS": "value"}
    }
  }
}
```

```json "with http (direct connection):"
{
  "mcpServers": {
    "codeweaver": {
      "type": "http",
      "url": "http://127.0.0.1:9328/mcp"
    }
  }
}

```

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
- [See full provider list →][providers_list]

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

CodeWeaver combines [AST][wiki_ast]-level understanding, semantic relationships, and hybrid embeddings (sparse + dense) to deliver both contextual and literal understanding of your codebase.

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
cw start     # Start daemon in background (or --foreground)
cw stop      # Stop the daemon
cw server    # Run the MCP server (stdio by default)
cw doctor    # Full setup diagnostic
cw index     # Run indexing without server
cw init      # Set up MCP + config
cw list      # List providers, models, capabilities
cw status    # Live server status, health, index state
cw search    # Test the search engine
cw config    # View resolved configuration
```

#### Running as a System Service

Install CodeWeaver to start automatically on login:

```bash
cw init service          # Install and enable (systemd/launchd)
cw init service --uninstall  # Remove the service
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

The [`enhancement`][enhancement_label] issues describe detailed plans. Short version:

- 📚 **Way better docs** – comprehensive guides and tutorials
- 🤖 **AI-powered context curation** – agents identify purpose and intent
- 🔧 **Data provider integration** – Tavily, DuckDuckGo, Context7, and more
- 💉 **True DI system** – replace existing registry
- 🕸️ **Advanced orchestration** – integrate `pydantic-graph`

### What Will Stay: **One Tool**

**One tool**. We give AI agents one simple tool: `find_code`.

Agents just need to explain what they need. No complex schemas. No novella-length prompts.

---

## 📚 Documentation

### For Users
- 🐳 [Docker Setup Notes][docker_notes]
- 🚀 [Getting Started Guide][nav_install]

### For Developers
- 🏗️ [Overall Architecture][architecture]
- 🔍 [find_code API][api_find_code]
- 📐 [find_code Architecture][arch_find_code]

### Product Philosophy
- 💭 [Product Decisions][product_decisions] – transparency matters
- 🤔 [Why CodeWeaver?][why_codeweaver] – detailed rationale

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

You'll need to agree to our [Contributor License Agreement][cla].

### Found a Bug?

🐛 [Report it here][issues] – include as much detail as possible!

---

## 🔗 Links

### Project
- 📦 **Repository**: [github.com/knitli/codeweaver][repo]
- 🐛 **Issues**: [Report bugs & request features][issues]
- 📋 **Changelog**: [View release history][changelog]
<!-- - 📖 **Documentation**: https://dev.knitli.com/codeweaver (in progress) -->

### Company
- 🏢 **Knitli**: [knitli.com][knitli_site]
- ✍️ **Blog**: [blog.knitli.com][knitli_blog]
- 🐦 **X/Twitter**: [@knitli_inc][knitli_x]
- 💼 **LinkedIn**: [company/knitli][knitli_linkedin]
- 💻 **GitHub**: [@knitli][knitli_github]

### Support the Project

We're a [one-person company][bashandbone] at the moment... and make no money... if you like CodeWeaver and want to keep it going, please consider **[sponsoring me][sponsor]** 😄

---

## 📦 Package Info

- **Python package**: `code-weaver` 👈❗ **note the hyphen**
- **CLI commands**: `cw` / `codeweaver`
- **Python requirement**: ≥3.12 (tested on 3.12, 3.13, 3.14)
- **Entry point**: `codeweaver.cli.app:main`

---

## 📄 License

Licensed under **MIT OR Apache 2.0** — you choose! Some vendored code is Apache 2.0 only and some is MIT only. Everything is permissively licensed.

The project follows the [REUSE specification][reuse_spec]. Every file has detailed licensing information, and we regularly generate a [software bill of materials][sbom].

---

## 📊 Telemetry

The default includes **very anonymized telemetry** to improve CodeWeaver. [See the implementation][telemetry_impl] or read [the README][telemetry_readme].

**Opt out**: `export CODEWEAVER__TELEMETRY__DISABLE_TELEMETRY=true`

**Opt in to detailed feedback** (helps us improve): `export CODEWEAVER__TELEMETRY__TOOLS_OVER_PRIVACY=true`

📋 [See our privacy policy][privacy_policy]

---

## ⚠️ API Stability

> **Warning**: The API *will change*. Our priority right now is giving you and your coding agent an awesome tool.
>
> To deliver on that, we can't get locked into API contracts while we're in alpha. We also want you to be able to extend and build on CodeWeaver — once we get to stable releases.

---

<div align="center">

**Built with ❤️ by [Knitli][knitli_site]**

[⬆ Back to top][nav_top]

</div>

<!-- Badges -->

[badge_license]: <https://img.shields.io/badge/license-MIT%20OR%20Apache--2.0-green.svg> "License Badge"
[badge_mcp]: <https://img.shields.io/badge/MCP-compatible-purple.svg> "MCP Compatible Badge"
[badge_python]: <https://img.shields.io/badge/python-3.12%2B-blue.svg> "Python Version Badge"
[badge_release]: <https://img.shields.io/badge/release-alpha%201-orange.svg> "Release Badge"

<!-- Other links -->

[api_find_code]: <src/codeweaver/agent_api/find_code/README.md> "find_code API Documentation"
[arch_find_code]: <src/codeweaver/agent_api/find_code/ARCHITECTURE.md> "find_code Architecture"
[architecture]: <ARCHITECTURE.md> "Overall Architecture"
[bashandbone]: <https://github.com/bashandbone> "Adam Poulemanos' GitHub Profile"
[changelog]: <https://github.com/knitli/codeweaver/blob/main/CHANGELOG.md> "Changelog"
[cla]: <CONTRIBUTORS_LICENSE_AGREEMENT.md> "Contributor License Agreement"
[cli_guide]: <docs/CLI.md> "Command Line Reference"
[config_schema]: <schema/codeweaver.schema.json> "The CodeWeaver Config Schema"
[docker_guide]: <DOCKER.md> "Docker Setup Guide"
[docker_notes]: <docs/docker/DOCKER_BUILD_NOTES.md> "Docker Build Notes"
[enhancement_label]: <https://github.com/knitli/codeweaver/labels/enhancement> "Enhancement Issues"
[issues]: <https://github.com/knitli/codeweaver/issues> "Report an Issue"
[knitli_blog]: <https://blog.knitli.com> "Knitli Blog"
[knitli_github]: <https://github.com/knitli> "Knitli GitHub Organization"
[knitli_linkedin]: <https://linkedin.com/company/knitli> "Knitli LinkedIn"
[knitli_site]: <https://knitli.com> "Knitli Website"
[knitli_x]: <https://x.com/knitli_inc> "Knitli X/Twitter"
[link_license]: <LICENSE> "License File"
[link_mcp]: <https://modelcontextprotocol.io> "Model Context Protocol Website"
[link_python]: <https://www.python.org/downloads/> "Python Downloads"
[link_release]: <https://github.com/knitli/codeweaver/releases> "CodeWeaver Releases"
[mcp]: <https://modelcontextprotocol.io> "Learn About the Model Context Protocol"
[nav_contributing]: <#-contributing> "Contributing Section"
[nav_docs]: <#-documentation> "Documentation Section"
[nav_features]: <#-features> "Features Section"
[nav_how_it_works]: <#-how-it-works> "How It Works Section"
[nav_install]: <#-getting-started> "Installation Section"
[nav_top]: <#codeweaver> "Back to Top"
[privacy_policy]: <PRIVACY_POLICY.md> "Privacy Policy"
[product_decisions]: <PRODUCT.md> "Product Decisions"
[providers_list]: <overrides/partials/providers.md> "Full Provider List"
[qdrant]: <https://qdrant.tech> "Qdrant Website"
[repo]: <https://github.com/knitli/codeweaver> "CodeWeaver Repository"
[reuse_spec]: <https://reuse.software> "REUSE Specification"
[sbom]: <sbom.spdx> "Software Bill of Materials"
[sponsor]: <https://github.com/sponsors/knitli> "Sponsor Knitli"
[telemetry_impl]: <src/codeweaver/common/telemetry/> "Telemetry Implementation"
[telemetry_readme]: <src/codeweaver/common/telemetry/README.md> "Telemetry README"
[uv_tool]: <https://astral.sh/uv> "uv Package Manager"
[voyage_ai]: <http://voyage.ai> "Voyage AI Website"
[why_codeweaver]: <docs/WHY.md> "Why CodeWeaver"
[wiki_ast]: <https://en.wikipedia.org/wiki/Abstract_syntax_tree> "About Abstract Syntax Trees"
