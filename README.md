<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

<div align="center">

<picture>
  <source media="(prefers-color-scheme: dark)" srcset="docs/assets/codeweaver-reverse.webp">
  <source media="(prefers-color-scheme: light)" srcset="docs/assets/codeweaver-primary.webp">
  <img alt="CodeWeaver logo" src="docs/assets/codeweaver-primary.webp" height="150px" width="150px">
</picture>

# CodeWeaver

### Semantic code search for Claude, Gemini, ChatGPT — across 166+ languages

[![Python Version][badge_python]][link_python]
[![License][badge_license]][link_license]
[![Alpha Release][badge_release]][link_release]
[![MCP Compatible][badge_mcp]][link_mcp]

[Installation][nav_install] •
[Features][nav_features] •
[Comparison][nav_comparison]

</div>

---

## What It Does

**CodeWeaver gives Claude and other AI agents precise context from your codebase.** Not keyword grep. Not whole-file dumps. Actual structural understanding through hybrid semantic search.

You, or Claude, or your intern, can ask questions like:
- *"Where do we handle OAuth tokens?"*
- *"Find all API endpoint definitions"*
- *"Show me error handling in the payment flow"*

CodeWeaver returns the exact functions, classes, and code blocks — even in unfamiliar languages or massive repositories.

**Example:**
```
Without CodeWeaver:
  Claude: "Let me search for 'auth'... here are 50 files mentioning authentication"
  Result: Generic code, wrong context, wasted tokens

With CodeWeaver:
  You: "Where do we validate OAuth tokens?"
  Claude gets: The exact 3 functions across 2 files, with surrounding context
  Result: Precise answers, focused context, actual understanding
```

> ⚠️ **Alpha Release**: This works, but it's early. [Use it, break it, help shape it][issues].

---

## How CodeWeaver Stacks Up

### Quick Reference Matrix

| Feature | CodeWeaver | Serena | Cursor | Copilot Workspace | Sourcegraph Cody | Continue.dev | Bloop | Aider |
|---------|-----------|--------|--------|-------------------|------------------|--------------|-------|-------|
| **Approach** | Semantic search | Symbol lookup (LSP) | Semantic | Semantic | Keyword | Semantic | Semantic | Repo maps |
| **Tool Count** | **1** | **20+** | N/A | N/A | N/A | N/A | N/A | N/A |
| **Prompt Overhead** | **~500 tokens** | **~16,000 tokens** | N/A | N/A | N/A | N/A | N/A | N/A |
| **Search Speed** | Moderate (embeddings) | **Very fast (LSP)** | Moderate | Server-side | Fast | Moderate | Fast | On-demand |
| **Embedding Providers** | **17** | 0 (no embeddings) | 1-2 | 1 | 0 (deprecated) | 4-5 | 1 | 0 |
| **Language Support** | **166+** | ~30 (LSP required) | ~50-100 | All (text) | All | ~165 | Unknown | ~165+ |
| **Requires Language Server** | ❌ No | ✅ Yes | ❌ No | ❌ No | ❌ No | ❌ No | ❌ No | ❌ No |
| **Symbol Precision** | ⚠️ Semantic match | **✅ Exact symbols** | ⚠️ Semantic | ⚠️ Semantic | ⚠️ Keyword | ⚠️ Semantic | ⚠️ Semantic | ✅ Exact |
| **Concept Search** | **✅ Yes** | ❌ Symbols only | ✅ Yes | ✅ Yes | ⚠️ Limited | ✅ Yes | ✅ Yes | ❌ No |
| **Editing Capabilities** | ❌ No | **✅ Yes (9 tools)** | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes | ❌ No | ✅ Yes |

**Notes**:
- **Serena tool count**: Varies by context (20+ in claude-code, up to 35 total available)
- **Serena prompt overhead**: Measured with 21 active tools in claude-code context (~16,000 tokens)
- **Language counts**: CodeWeaver supports 166+ unique languages (27 with AST parsing, 139 with intelligent delimiter-based chunking)

📊 [See detailed competitive analysis →][competitive_analysis]

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

> **📝 Note**: `cw init` defaults to CodeWeaver's `recommended` profile:
> - 🔑 [Voyage AI API key][voyage_ai] (generous free tier)
> - 🗄️ [Qdrant instance][qdrant] (cloud or local, both free options)
>
> **Want full offline?** Use `cw init --profile quickstart` for local-only operation.

🐳 **Prefer Docker?** [See Docker setup guide →][docker_guide]

### MCP Configuration

To watch and handle your files, CodeWeaver always runs an HTTP server. You can connect to that or use your typical `stdio` setup:

`cw init` adds CodeWeaver to your project's `.mcp.json`:
```json
{
  "mcpServers": {
    "codeweaver": {
      "type": "stdio",
      "cmd": "uv",
      "args": ["run", "codeweaver", "server"],
      "env": {"VOYAGE_API_KEY": "your-key-here"}
    }
  }
}
```

**or with http:**
```json
{
  "mcpServers": {
    "codeweaver": {
      "type": "http",
      "url": "http://127.0.0.1:9328"
    }
  }
}
```

---

## ✨ Features

<table>
<tr>
<td width="50%">

### 🔍 Smart Search
- **Hybrid search** (sparse + dense vectors)
- **AST-level understanding** (27 languages)
- **Semantic relationships**
- **Language-aware chunking** (166+ languages)

</td>
<td width="50%">

### 🌐 Language Support
- **27 languages** with full AST/semantic parsing
- **166+ languages** with language-aware chunking
- **Cross-language normalization**
- **Family heuristics** for smart fallback

</td>
</tr>
<tr>
<td>

### 🔄 Resilient & Offline
- **Full offline operation** with local models
- **Automatic failover** to backup vector store
- **Works airgapped** (no cloud required)
- **Graceful degradation** with health monitoring

</td>
<td>

### 🔌 Provider Flexibility
- **17 embedding providers**
- **50+ embedding models**
- **Sparse & dense** embedding model support
- **5 reranking providers**
- [See full provider list →][providers_list]

</td>
</tr>
<tr>
<td>

### ⚙️ Configuration
- **~15 config sources** (TOML/YAML/JSON/ENV)
- **Cloud secret stores** (AWS/Azure/GCP)
- **Hierarchical merging**
- **Profiles** for common setups

</td>
<td>

### 🛠️ Developer Experience
- **Live indexing** with file watching
- **Move detection** (no re-indexing duplicates)
- **Full CLI** (`cw` / `codeweaver`)
- **Health & metrics** endpoints

</td>
</tr>
</table>

---

## 💭 Philosophy

### The Bigger Picture

I started building CodeWeaver because I believe AI agents need better context infrastructure. Right now:

- Agents re-read the same huge files repeatedly
- They get shallow, text-based context instead of structural understanding
- They are mostly given tools built for humans, not for how they actually work
- You don't control what context they see or how they get it

CodeWeaver addresses this with one focused capability: structural + semantic code understanding that you control and can deploy however you want.

**Is this solving a big problem?** We think so. But we're in alpha; we're probably not there yet. We also need real-world usage to prove it. That's where you come in. Use it, make it better. Worst case -- it's a good tool, best case -- you get better results and cut costs on AI.

📖 [Read the detailed rationale →][why_codeweaver]

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
[competitive_analysis]: <src/codeweaver/docs/comparison.md> "See how CodeWeaver stacks up"
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
[nav_comparison]: <#-quick-reference-matrix> "How CodeWeaver Compares"
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
