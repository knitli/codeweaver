<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->
<!--
mcp-name: com.knitli/codeweaver
-->
# CodeWeaver

![codeweaver logo](docs/assets/codeweaver-primary.svg "CodeWeaver by Knitli)
---
by Knitli

> *Alpha Release 1*
---
**CodeWeaver is the missing abstraction layer between AI and your code.**

It gives both humans and AI a deep, structural understanding of your project — not just text search, but real context: symbols, blocks, relationships, intent. [MCP][mcp] is just the delivery mechanism; CodeWeaver is the capability.

If you want AI that actually knows your code instead of guessing, this is the foundation.

---

## **Why CodeWeaver exists**

**The problems:**
* **Poor Context = Poor Results** - Agents are better at generating new code than finding and understanding existing structure
* **Massive Inefficiency** - Agents read the same huge files repeatedly, carrying bloated context with every tool call (50%+ waste is common)
* **Wrong Abstraction** - Agents get handed complex tools built for humans, not tools built for how agents actually work
* **No Ownership** - Existing solutions are locked into specific IDEs or MCP clients; you can't deploy them how you want

The result: shallow, inconsistent, fragile context. And you don't control it.

**CodeWeaver's approach:**
* One focused capability: structural + semantic code understanding
* Hybrid search built for code, not text
* Works offline, airgapped, or degraded
* Deploy it however you want
* One great tool instead of 30 mediocre ones

[Read the detailed rationale →][WHY]

---

## **Getting Started**

Using the [CLI](#cli):

In your project:
```bash
uv add --prerelease allow --dev codeweaver
# or poetry: 

cw init
cw doctor
```

You're ready, but you can customize *just about everything if you want to*.

---

## **How It Works**

CodeWeaver mixes [AST][wiki_ask]-level understanding, semantic relationships, and hybrid embeddings (sparse + dense) to deliver contextual and literal understanding of your codebase.

**The goal: give AI the fragments it *should* see, not whatever it can grab.**

### **Language Support**

* **AST/Semantic Hybrid Search:** 26 languages
* **Context-Aware Chunking:** 136+ languages
  Uses language family heuristics to intelligently chunk (like "this is a Lisp-style form", "this looks like a function block", etc.)

### **Search & Context**

* Hybrid (sparse + dense) search is always available — offline, airgapped; no problem.
* Vector store and embedding provider health monitoring with automatic fallback to lightweight, local models
* Performs better than generic MCP search because it's built for structure, not text

### **Indexing & Watching**

* Live indexing with stable, fast file watching
* Low CPU overhead (background tasks run at low process priority)
* Index stays warm as you edit

### **CLI**

Both `cw` and `codeweaver` work.

* `server` - run the server
* `doctor` – full setup diagnostic and troubleshooting
* `index` – run indexing without the server
* `init` – set up MCP + CodeWeaver config (or each separately with `mcp` and `config` subcommands)
* `list` - list available providers, models, and similar capabilities
* `status` – live server status, provider health, index state
* `search` – same engine AI uses; works with or without server
* `config` – view final resolved config (hierarchical, merged, secrets-aware)

Full CLI Guide [available here][cli_guide]

### **Configuration**

* ~15 config sources (TOML/YAML/JSON, env, workspace overrides, secrets, etc.)
* Default config is `codeweaver.toml` in your project. Use `cw init config` to generate.
* Cloud secret stores supported (AWS/Azure/GCP)
* Priority-based hierarchical merging
* [Schema][config_schema]

Full guide coming soon. 

### **Server & Programmatic Access**

* Health endpoint (`/health/`)
* Metrics (`/metrics/`)
* Versioning info (`/version/`)
* Settings view (`/settings/`)
* Full state dump for external tooling or debugging
* Docker image for painless setup

### **Resilient Fallback**

If your embedding provider dies, or Qdrant crashes, or your laptop goes offline:

* CodeWeaver detects the failure
* Automatically falls back to a separate hybrid (dense + sparse) vector index with lightweight local models
* Still includes reranking for quality results
* Keeps serving context without you doing anything

Your degraded mode is better than most tools' primary mode (which often lack sparse vectors or reranking entirely).

### **The MCP layer is thin**

It's not "MCP as product." MCP is just the pipe AI drinks from.

---

## **Current Status & Stability (Alpha)**

> [!IMPORTANT]
> Codeweaver **is in alpha**. *Use* it, *break* it, *shape* it, *help make it better*. [Report issues][report].


### **Stability Snapshot** -- Strong Core; Prickly Edges

| Area                                      | Status                 | Notes                                              |
| ----------------------------------------- | ---------------------- | -------------------------------------------------- |
| **Live indexing & file watching**         | ⭐⭐⭐⭐           | Runs continuously; reliable
| **Ast-Based Chunking**                  | ⭐⭐⭐⭐           | Full semantic/AST for 26 languages.                |
| **Context-aware chunking**                | ⭐⭐⭐⭐         | 136+ languages. Heuristic AST-lite. Usually right. |
| **Provider integration**                  | ⭐⭐⭐             | Voyage/FastEmbed reliable. Others: ¯\_(ツ)_/¯       |
| **Automatic fallback (offline/degraded)** | ⭐⭐⭐            | Seamless switch to local hybrid backup search.        |
| **CLI (cw / codeweaver)**                 | ⭐⭐⭐⭐            | Core commands fully wired and tested.              |
| **Docker build**                          | ⭐⭐⭐             | Skip local Qdrant setup entirely.
| **MCP interface**                         | ⭐⭐⭐             | Core ops reliable; some edge-case weirdness.       |
| **HTTP endpoints**                        | ⭐⭐⭐              | Health, metrics, state, versions. Stable.          |

*(Legend: ⭐⭐⭐⭐ = solid, ⭐⭐⭐ = works with some quirks, ⭐⭐ = experimental, ⭐ = chaos gremlin)*

---

## **Roadmap**

The `enhancement` issues describe plans in detail; the short version:

- Way better docs.
- Integrate AI agents into the context delivery pipeline to identify purpose and intent and curate results
- Integrate data providers and tools for *internal* agents to use to provide better, more accurate context (Tavily and DuckDuckGo scaffolded; we'd like to add Context7 and others)
- Replace the existing registry system with a true DI injection system.
- Integrate `pydantic-graph` for advanced orchestration of context delivery.

### What Will Stay: One Tool

**One tool**. We give AI agents one simple tool: `find_code`.

Agents just need to explain what they need. No complex schemas. No pages long prompts and tool instructions.

We would never read a novella-length document to learn how to use a basic coding tool; AI agents shouldn't either.
---

# **Documentation**

### **For Users**
- [Docker Setup Notes](docs/docker/DOCKER_BUILD_NOTES.md) - Docker build troubleshooting and using pre-built images

### **For Developers**
- [Overall architecture](ARCHITECTURE.md)
- [find_code API](src/codeweaver/agent_api/find_code/README.md) - Core search API documentation
- [find_code Architecture](src/codeweaver/agent_api/find_code/ARCHITECTURE.md) - Detailed architecture and extension points

### **For Anyone**

We think transparency is important, so here's our product decisions:

- [product decisions](PRODUCT.md)

<!-- More comprehensive documentation is in progress at https://dev.knitli.com/codeweaver -->

---

# **Contributing**

PRs, issues, weird edge cases, feature requests — all welcome.
This is still early, and the best time to help shape the direction.

You will need to agree to our [CLA](CONTRIBUTORS_LICENSE_AGREEMENT.md)

---

## Links

**Project**:
- Repository: https://github.com/knitli/codeweaver
- Issues: https://github.com/knitli/codeweaver/issues
<!-- Documentation: https://dev.knitli.com/codeweaver (in progress) -->
- Changelog: https://github.com/knitli/codeweaver/blob/main/CHANGELOG.md

**Company**:
- Knitli: https://knitli.com
- Blog: https://blog.knitli.com
- X/Twitter: https://x.com/knitli_inc
- LinkedIn: https://linkedin.com/company/knitli
- GitHub: https://github.com/knitli

We're a [one-person company](@bashandbone) at the moment... and make no money... if you like CodeWeaver, and want to keep it going, please consider sponsoring me 😄

**Package Info**:
- Python package: `codeweaver`
- CLI command: `codeweaver`
- Python requirement: ≥3.12 (tested on 3.12, 3.13, 3.14)
- Entry point: `codeweaver.cli.app:main`

---

## License

Licensed under MIT **or** Apache 2.0. You choose.  Some vendored code is Apache 2.0 only and some is MIT only. Everything is permissively licensed.

The project follows the [reuse specification](https://reuse.software). Every file has detailed licensing information, and we regularly generate a [software bill of materials](sbom.spdx)

---
## Telemetry

The default includes very anonymized telemetry. It will only be used to improve CodeWeaver. [You can see the implementation for yourself](src/codeweaver/common/telemetry/) or read [the README](src/codeweaver/common/telemetry/README.md). Opt out by exporting `CODEWEAVER__TELEMETRY__DISABLE_TELEMETRY=true`

If you want to be awesome and let us collect information on queries and results, you can *opt in* with `CODEWEAVER__TELEMETRY__TOOLS_OVER_PRIVACY=true`. That will give us the information we need to really make your queries better.

[See our privacy policy](PRIVACY_POLICY.md)

---
## API

> [!WARNING]
> The API *will change*. Our priority right now is giving your and your coding agent and awesome tool.
> To deliver on that, we can't get locked into API contracts while we're in alpha.
> We also want you to be able to extend and build on CodeWeaver -- once we get to stable releases.


[cli_guide]: <docs/CLI.md> "Command Line Reference"
[config_schema]: <schema/codeweaver.schema.json> "The CodeWeaver Config Schema"
[mcp]: <https://modelcontextprotocol.io> "Learn About the Model Context Protocol"
[report]: <https://github.com/knitli/codeweaver/issues> "Report an Issue"
[wiki_ask]: <https://https://en.wikipedia.org/wiki/Abstract_syntax_tree> "About Abstract Syntax Trees"
[WHY]: <docs/WHY.md> "Why I built CodeWeaver"