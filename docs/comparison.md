<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# CodeWeaver Feature Comparison Chart

**Last Updated**: December 9, 2025

## Quick Reference Matrix

| Feature | CodeWeaver | Serena | Cursor | Copilot Workspace | Sourcegraph Cody | Continue.dev | Bloop | Aider |
|---------|-----------|--------|--------|-------------------|------------------|--------------|-------|-------|
| **Approach** | Semantic search | Symbol lookup (LSP) | Semantic | Semantic | Keyword | Semantic | Semantic | Repo maps |
| **Tool Count** | **1** | **20+** | N/A | N/A | N/A | N/A | N/A | N/A |
| **Prompt Overhead** | **~500 tokens** | **~16,000 tokens** | N/A | N/A | N/A | N/A | N/A | N/A |
| **Search Speed** | Moderate (embeddings) | **Very fast (LSP)** | Moderate | Server-side | Fast | Moderate | Fast | On-demand |
| **Embedding Providers** | **17** | 0 (no embeddings) | 1-2 | 1 | 0 (deprecated) | 4-5 | 1 | 0 |
| **Language Support** | **166+** | ~30 (LSP required) | ~50-100 | All (text) | All | ~165 | Unknown | ~165+ |
| **Requires Language Server** | ❌ No | ✅ Yes | ❌ No | ❌ No | ❌ No | ❌ No | ❌ No | ❌ No |
| **Symbol Precision** | ⚠️ Semantic | **✅ Exact symbols** | ⚠️ Semantic | ⚠️ Semantic | ⚠️ Keyword | ⚠️ Semantic | ⚠️ Semantic | ✅ Exact |
| **Concept Search** | **✅ Yes** | ❌ Symbols only | ✅ Yes | ✅ Yes | ⚠️ Limited | ✅ Yes | ✅ Yes | ❌ No |
| **Editing Capabilities** | ❌ No | **✅ Yes (9 tools)** | ✅ Yes | ✅ Yes | ✅ Yes | ✅ Yes | ❌ No | ✅ Yes |

**Notes**:
- **Serena tool count**: Varies by Serena's 'context' (20+ in claude-code, up to 35 total available)
- **Serena prompt overhead**: Measured with 21 active tools in claude-code context (~16,000 tokens)
- **Language counts**: CodeWeaver supports 166+ unique languages (27 with AST parsing, 139 with language-aware chunking)

**Legend**:
- ✅ **Full support/Yes**
- ⚠️ **Partial/Unclear/Limited**
- ❌ **No/Not available**
- N/A **Not applicable** (different architecture)

---

### CodeWeaver vs. Serena

| Feature | CodeWeaver | Serena | Winner |
|---------|-----------|--------|--------|
| Search approach | Semantic (embeddings) | Symbol lookup (LSP) | **Different strengths** |
| Language support | 166+ (no LSP needed) | ~30 (requires LSP) | **CodeWeaver** (breadth) |
| Search speed | Moderate (embedding lookup) | Very fast (LSP queries) | **Serena** |
| Tool count | 1 (`find_code`) | 20+ total tools | **CodeWeaver** (simplicity) |
| Prompt overhead | ~500 tokens | ~16,000 tokens | **CodeWeaver** |
| Symbol precision | Semantic match | Exact symbols | **Serena** |
| Concept search | ✅ "authentication flow" | ❌ Must know symbol name | **CodeWeaver** |
| Editing | ❌ No | ✅ Yes | **Serena** |
| Setup requirement | Vector store + embeddings | Language server (usually running) | **Serena** (simpler) |

**The Core Tradeoff**:

**Serena is better when**:
- Your agent knows the symbol name or can get the information through symbol lists
- You're working in one of the ~30 supported languages
- Speed matters (LSP is instant, embeddings take time)
- You want editing capabilities too
- You don't care about prompt token overhead

**CodeWeaver is better when**:
- **You** want to search. CodeWeaver provides you with the same tool it gives to agents.
- You/Your Agent are searching by concept: "where do we handle retries?"
- You're in an unusual language (COBOL, Fortran, legacy codebases)
- You don't have a language server running
- You care about context efficiency (16k vs 500 tokens per turn)
- You want ONE simple tool instead of choosing among 20+

**Real Talk**: Symbol lookup solves ~90% of code navigation needs. Serena is fast, precise, and proven. CodeWeaver targets the remaining 10% where semantic understanding matters, plus the long tail of languages LSP doesn't cover.

> [!TIP]
> **They're complementary**
>
> Use both. If you're not concerned about prompt overhead, use Serena for "find function X" and its excellent editing capabilities, and use CodeWeaver for "find where we handle edge cases in authentication."

## Detailed Feature Breakdown

### 1. Embedding Flexibility

| Solution | Providers | Models | Customization | Code-Specific |
|----------|-----------|--------|---------------|---------------|
| **CodeWeaver** | **17** (Voyage, OpenAI, Cohere, Mistral, HuggingFace, Azure, AWS Bedrock, Google, Sentence Transformers, FastEmbed, etc.) | **50+** configured | **✅ Plugin architecture** | ✅ Voyage Code-3, Mistral Codestral |
| Cursor | OpenAI, Custom | 1-2 | ❌ Limited | ⚠️ Unknown |
| Copilot Workspace | Microsoft/OpenAI | 1 | ❌ None | ⚠️ Unknown |
| Sourcegraph Cody | None (deprecated embeddings) | 0 | N/A | N/A |
| Continue.dev | Transformers.js, Ollama, Voyage, OpenAI, HuggingFace | 5-10 | ⚠️ Config-based | ✅ Voyage Code support |
| Bloop | Local (unspecified) | 1 | ❌ None | ⚠️ Unknown |
| Aider | None (uses repo maps) | 0 | N/A | N/A |

**CodeWeaver Advantage**: **4-10x more provider options** than any one else.

---

### 2. Search Capabilities

| Solution | Dense Embeddings | Sparse Embeddings | Hybrid Method | Reranking |
|----------|-----------------|-------------------|---------------|-----------|
| **CodeWeaver** | ✅ Yes | **✅ BM25/SPLADE** | **✅ Default** | ✅ 5 providers |
| Cursor | ✅ Yes | ❌ No | ❌ Dense only | ❌ No |
| Copilot Workspace | ✅ Yes | ❌ No | ❌ Dense only | ❌ No |
| Sourcegraph Cody | ❌ Deprecated | ❌ No | ⚠️ Keyword search | ❌ No |
| Continue.dev | ✅ Yes | ⚠️ Keyword (not true sparse) | ⚠️ Combined | ✅ Multiple options |
| Bloop | ✅ Yes | ⚠️ Regex (not sparse) | ⚠️ Combined | ❌ No |
| Aider | N/A | N/A | N/A (graph ranking) | N/A |

**Industry Context**:
- Hybrid search (dense + sparse) is industry best practice for code search
- Voyage Code-3 with hybrid search shows **14.52% improvement** vs using Voyage Code-3 alone
- **Only CodeWeaver** offers true hybrid search (both vector types with ranked results)

---

### 3. Language Support

| Solution | AST Parsing | Languages (AST) | Fallback Method | Total Languages |
|----------|-------------|----------------|-----------------|-----------------|
| **CodeWeaver** | ✅ Tree-sitter | **27** | **✅ Language-aware chunking (family patterns)** | **166+** |
| Cursor | ⚠️ Unspecified | ⚠️ Unknown | ⚠️ Unknown | ~50-100 (est.) |
| Copilot Workspace | ❌ Language-agnostic | N/A | Text-based | All (basic) |
| Sourcegraph Cody | ⚠️ Unspecified | ⚠️ Unknown | Keyword indexing | All |
| Continue.dev | ✅ Tree-sitter | ~165 | ⚠️ Top-level only | ~165 |
| Bloop | ⚠️ Unspecified | ⚠️ Unknown | ⚠️ Unknown | Unknown |
| Aider | ✅ Tree-sitter | ~165 | ✅ ctags | ~165+ |

**CodeWeaver Advantages**:
1. **Language-aware chunking for 166+ languages** (not just line-based fallback)
2. **Cross-language AST normalization** (unique in market)
3. **Language family intelligence** in chunker

---

### 4. Real-Time Updates & Indexing

| Solution | Incremental Updates | File Watching | Move Detection |
|----------|---------------------|---------------|----------------|
| **CodeWeaver** | **✅ Live** | **✅ Continuous** | **✅ Dedup on move** |
| Cursor | ✅ Likely | ✅ Likely | ❌ No |
| Copilot Workspace | ⚠️ Server-managed | ❌ Client-side | ❌ No |
| Sourcegraph Cody | ✅ Yes | ⚠️ Unclear | ❌ No |
| Continue.dev | ✅ Yes | ✅ Yes | ❌ No |
| Bloop | ⚠️ Unclear | ⚠️ Unclear | ❌ No |
| Aider | ❌ On-demand only | ❌ No | N/A |

**CodeWeaver's Real-Time Capabilities**:
- **Live file watching**: Detects changes as they happen
- **Incremental updates**: Only re-indexes changed files
- **Move detection**: Recognizes when files are moved/renamed without re-embedding
- **Continuous operation**: No manual re-indexing required

---

### 5. Deployment Models

| Solution | Local | Cloud | Offline/Airgapped | Portable | Failover |
|----------|-------|-------|-------------------|----------|----------|
| **CodeWeaver** | **✅ Full** | **✅ Full** | **✅ Full** | **✅ MCP** | **✅ Intelligent backup** |
| Cursor | ⚠️ Experimental (ChromaDB) | ✅ Default | ❌ Requires internet | ❌ IDE-locked | ❌ No |
| Copilot Workspace | ❌ Cloud-only | ✅ Only option | ❌ Requires GitHub/Azure | ❌ Cloud service | ❌ No |
| Sourcegraph Cody | ✅ Enterprise | ✅ Yes | ✅ Enterprise | ⚠️ IDE-integrated | ❌ No |
| Continue.dev | ✅ Yes (local models) | ⚠️ Hybrid | ✅ Via Ollama | ❌ IDE-locked | ❌ No |
| Bloop | ✅ Yes | ❌ No | ✅ Yes | ⚠️ Desktop app | ❌ No |
| Aider | ✅ Yes | ❌ No | ✅ Yes | ✅ CLI | N/A |

**Airgapped Deployment Leaders**:
1. Tabnine Enterprise (fully airgapped)
2. **CodeWeaver** (local providers + failover)
3. Sourcegraph Cody Enterprise
4. Continue.dev (via Ollama)

**CodeWeaver's Intelligent Failover**:
- Primary vector store (Qdrant) fails → auto-switch to in-memory store with lightweight models
- Maintains live file watching during failover
- Seamless handover when primary recovers
- **Zero functionality loss** (slightly reduced search quality only)

---

### 6. Integration & Portability

| Solution | Architecture | IDE Support | MCP Protocol | Extensibility |
|----------|--------------|-------------|--------------|---------------|
| **CodeWeaver** | **MCP Server** | **Any MCP client** | **✅ Native** | **✅ Plugin providers** |
| Cursor | Integrated IDE | Cursor only | ⚠️ Can use MCP servers | ❌ Limited |
| Copilot Workspace | Cloud service | Web-based | ⚠️ Can integrate | ❌ None |
| Sourcegraph Cody | IDE extension + backend | VS Code, JetBrains | ⚠️ Potential | ⚠️ Config-based |
| Continue.dev | IDE extension | VS Code, JetBrains | ⚠️ Potential | ⚠️ Config-based |
| Bloop | Desktop app | Standalone | ❌ No | ❌ Limited |
| Aider | CLI tool | Terminal | ❌ No | ⚠️ Limited |

**MCP Protocol Context** (launched Nov 2024):
- Adopted by: Visual Studio (GA), Cursor, Claude Code, Replit, Codeium, Sourcegraph
- Growing ecosystem of MCP servers for code search, databases, deployment
- **CodeWeaver is MCP-native**, not retrofitted

---

## Head-to-Head Comparisons

### CodeWeaver vs. Cursor IDE

| Feature | CodeWeaver | Cursor | Winner |
|---------|-----------|--------|--------|
| Embedding models | 50+ models, 17 providers | 1-2 models | **CodeWeaver** |
| Hybrid search | ✅ Dense + Sparse | ❌ Dense only | **CodeWeaver** |
| Privacy | ✅ Local option, airgapped | ⚠️ Sends to cloud (experimental local) | **CodeWeaver** |
| IDE integration | Via MCP | Native, deep | **Cursor** |
| Portability | ✅ Any MCP client | ❌ Cursor only | **CodeWeaver** |
| Ease of use | Requires MCP client | Built-in | **Cursor** |

**Best for**:
- **CodeWeaver**: Teams needing customization, privacy, multi-IDE support
- **Cursor**: Individual developers wanting seamless IDE experience

> [!TIP]
> CodeWeaver can make Cursor better, giving it richer context through MCP.

---

### CodeWeaver vs. Continue.dev

| Feature | CodeWeaver | Continue.dev | Winner |
|---------|-----------|--------------|--------|
| Embedding providers | 17 | 7 | **CodeWeaver** |
| Embedding models | 50+ | 5-10 | **CodeWeaver** |
| Hybrid search | ✅ Dense + Sparse | ⚠️ Dense + Keyword | **CodeWeaver** |
| Language support | 166+ (language-aware) | ~165 (AST + basic fallback) | **CodeWeaver** |
| Portability | ✅ MCP (any client) | ❌ VS Code/JetBrains only | **CodeWeaver** |
| Reranking | 5 providers, 20+ models | Multiple options | **Tie** |
| IDE integration | Via MCP | Native extension | **Continue.dev** |
| Configuration | ⚠️ Requires setup | Config file | **Continue.dev** |

**Best for**:
- **CodeWeaver**: Multi-IDE teams, advanced customization, MCP ecosystem
- **Continue.dev**: VS Code/JetBrains users wanting embedding flexibility with native integration

> [!NOTE]
> You can use CodeWeaver **with** Continue.dev or any other MCP client.

---

### CodeWeaver vs. Sourcegraph Cody

| Feature | CodeWeaver | Sourcegraph Cody | Winner |
|---------|-----------|------------------|--------|
| Search method | Semantic (embeddings) | Keyword (deprecated embeddings) | **Different philosophies** |
| Scale | Mid-large repos | Massive repos (1M+ LOC) | **Cody** (proven at scale) |
| Customization | 17 embedding providers | N/A (uses keyword search) | **CodeWeaver** |
| Enterprise features | Airgapped, local | Enterprise-proven, airgapped | **Tie** |
| Repository understanding | Semantic chunks | Full-text + structural | **Different approaches** |

**Best for**:
- **CodeWeaver**: Teams wanting semantic search with embedding customization
- **Sourcegraph Cody**: Enterprises with massive monorepos needing proven scalability

---

### CodeWeaver vs. Aider

| Feature | CodeWeaver | Aider | Winner |
|---------|-----------|-------|--------|
| Approach | Semantic embeddings | Repository maps (graph ranking) | **Different purposes** |
| Use case | Interactive search | LLM context generation | **Different purposes** |
| Portability | MCP server | CLI | **Tie** |
| Deployment | Local/cloud/airgapped | Local only | **CodeWeaver** (flexibility) |
| Simplicity | Requires vector store | Lightweight | **Aider** |

**Best for**:
- **CodeWeaver**: Interactive code search and discovery
- **Aider**: Terminal-based AI pair programming context

> [!TIP]
> CodeWeaver can make Aider better, giving it richer context through MCP.

---

## CodeWeaver's Unique Differentiators

### ✅ Only CodeWeaver Has ALL of These:

1. **17 embedding providers, 50+ models** (2-10x more than any competitor)
2. **True hybrid search** (dense + sparse embeddings by default)
3. **166+ language support** with language-aware chunking (not just AST + line breaks)
4. **Intelligent failover** (backup vector store with live file tracking)
5. **Cross-language AST normalization** (unique in market)
6. **Full offline/airgapped** capability with local providers
7. **MCP-native architecture** (portable, works with any MCP client)
8. **Move detection & deduplication** (doesn't re-embed moved files)

---

## Use Case Recommendations

| Scenario | Recommended Solution | Why |
|----------|---------------------|-----|
| **Individual dev, wants simplicity** | Cursor, Continue.dev | Native IDE integration, easy setup |
| **Enterprise, airgapped environment** | **CodeWeaver**, Sourcegraph Cody Enterprise | No external API calls, full offline capability |
| **Multi-IDE team** | **CodeWeaver** | MCP protocol and CLI works with any client |
| **Massive repos (>1M LOC)** | Sourcegraph Cody | Proven scalability at enterprise scale |
| **Terminal-based workflow** | Aider, ripgrep | CLI-first tools |
| **GitHub-centric team** | Copilot Workspace | Native GitHub integration (issues, PRs, comments) |
| **Custom embedding models** | **CodeWeaver**, Continue.dev | Provider flexibility |
| **Need hybrid search (dense + sparse)** | **CodeWeaver**, Continue.dev | Only solutions with true hybrid search |
| **Multi-language projects** | **CodeWeaver** | Cross-language AST normalization |
| **Privacy-first, local-only** | **CodeWeaver**, Bloop, Aider | No cloud dependencies |
| **Want MCP ecosystem** | **CodeWeaver** | Native MCP server, not retrofitted |

---

## Market Position Summary

```
High Customization (Embedding Models)
         ▲
         │
         │                              ● CodeWeaver ⭐
         │                                (MCP Server)
         │
         │                      ● Continue.dev
         │                        (IDE Extension)
         │
    ─────┼───────────────────────────── Portability
         │
         │
         │
         │  ● Cursor  ● Copilot    ● Bloop
         │    (Cloud)    (Cloud)     (Desktop)
         │
         ▼
Low Customization (1-2 Models)
```

**CodeWeaver's Position**:
- **Top tier** for embedding customization (16+ providers)
- **High portability** via MCP protocol and CLI (not IDE-locked)
- **Unique combination** of flexibility + portability + airgapped capability

---

## Conclusion

### Where CodeWeaver Leads

1. Embedding provider diversity (17 vs 1-7)
2. Hybrid search (dense + sparse by default)
3. Language support breadth (166+ with language-aware chunking)
4. Deployment flexibility (local/cloud/airgapped with failover)
5. Portability (MCP-native, not IDE-locked)

### Consider Alternatives When...

- You want deep native IDE integration → Cursor, Continue.dev
- You need proven scale for massive repos → Sourcegraph Cody
- You prefer simplicity over customization → Cursor, Bloop

### CodeWeaver is Best For...

- Teams requiring embedding customization or wanting to tailor search and model selection
- Multi-IDE environments
- Privacy-sensitive/airgapped deployments
- Anyone using MCP tools regularly
- People using multiple AI clients (like Claude + Copilot)
- Multi-language projects benefiting from cross-language search
- Teams working with less-common languages, or maintaining legacy codebases who want modern support

---

**Last Updated**: December 9, 2025