<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# CodeWeaver Feature Comparison Chart

**Last Updated**: November 17, 2025

## Quick Reference Matrix

| Feature | CodeWeaver | Cursor | Copilot Workspace | Sourcegraph Cody | Continue.dev | Bloop | Aider |
|---------|-----------|--------|-------------------|------------------|--------------|-------|-------|
| **Embedding Providers** | **20+** | 1-2 | 1 | 0 (deprecated) | 4-5 | 1 | 0 (no embeddings) |
| **Embedding Models** | **50+** | 1-2 | 1 | 0 | 5-10 | 1 | 0 |
| **Code-Specific Models** | ✅ Yes | ❌ No | ❌ No | N/A | ✅ Yes | ⚠️ Unclear | N/A |
| **Hybrid Search** | **✅ Dense+Sparse** | ❌ Dense only | ❌ Dense only | ❌ Keyword only | ✅ Dense+Keyword | ⚠️ Dense+Regex | N/A |
| **AST Semantic Parsing** | ✅ 26 langs | ⚠️ Unclear | ❌ No | ⚠️ Unclear | ✅ Tree-sitter | ⚠️ Unclear | ✅ Tree-sitter |
| **Fallback Chunking** | **✅ 170+ langs** | ⚠️ Unclear | ✅ All | ⚠️ Unclear | ⚠️ Basic | ⚠️ Unclear | ✅ ctags |
| **Total Language Support** | **170+** | ~50-100 | All (text) | All | ~165 | Unknown | ~165+ |
| **Indexing Speed** | **3.2s (77k LOC)** | ⚠️ Unclear | Server-side | ⚠️ Unclear | ⚠️ Unclear | "Fast" | N/A |
| **Live File Watching** | **✅ Instant** | ✅ Likely | ❌ No | ⚠️ Unclear | ✅ Yes | ⚠️ Unclear | ❌ No |
| **Deduplication** | **✅ Move detect** | ❌ No | ❌ No | ❌ No | ❌ No | ❌ No | N/A |
| **Local Deployment** | **✅ Full** | ⚠️ Experimental | ❌ No | ✅ Enterprise | ✅ Yes | ✅ Yes | ✅ Yes |
| **Cloud Deployment** | ✅ Yes | ✅ Default | ✅ Only | ✅ Yes | ⚠️ Hybrid | ❌ No | ❌ No |
| **Airgapped Support** | **✅ Full** | ❌ No | ❌ No | ✅ Enterprise | ✅ Yes | ✅ Yes | ✅ Yes |
| **Portable (IDE-agnostic)** | **✅ MCP** | ❌ Cursor only | ❌ Cloud only | ⚠️ IDE-tied | ❌ IDE-tied | ⚠️ Desktop app | ✅ CLI |
| **Intelligent Failover** | **✅ Yes** | ❌ No | ❌ No | ❌ No | ❌ No | ❌ No | N/A |
| **Reranking Support** | ✅ 5 providers, 20+ models | ❌ No | ❌ No | ❌ No | ✅ Multiple | ❌ No | N/A |
| **Cross-Language Normalization** | **✅ Yes** | ❌ No | ❌ No | ❌ No | ❌ No | ❌ No | ❌ No |

**Legend**:
- ✅ **Full support/Yes**
- ⚠️ **Partial/Unclear/Limited**
- ❌ **No/Not available**
- N/A **Not applicable** (different architecture)

---

## Detailed Feature Breakdown

### 1. Embedding Flexibility

| Solution | Providers | Models | Customization | Code-Specific |
|----------|-----------|--------|---------------|---------------|
| **CodeWeaver** | **20+** (Voyage, OpenAI, Cohere, Mistral, HuggingFace, Azure, AWS Bedrock, Google, Sentence Transformers, FastEmbed, etc.) | **50+** configured | **✅ Plugin architecture** | ✅ Voyage Code-2, Mistral Codestral |
| Cursor | OpenAI, Custom | 1-2 | ❌ Limited | ❌ General-purpose |
| Copilot Workspace | Microsoft/OpenAI | 1 | ❌ None | ❌ General-purpose |
| Sourcegraph Cody | None (deprecated embeddings) | 0 | N/A | N/A |
| Continue.dev | Transformers.js, Ollama, Voyage, OpenAI, HuggingFace | 5-10 | ⚠️ Config-based | ✅ Voyage Code support |
| Bloop | Local (unspecified) | 1 | ❌ None | ⚠️ Unknown |
| Aider | None (uses repo maps) | 0 | N/A | N/A |

**CodeWeaver Advantage**: **4-10x more provider options** than any competitor

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
- Hybrid search (dense + sparse) is industry best practice
- Voyage Code-2 with hybrid search shows **14.52% improvement** vs dense-only
- Only **CodeWeaver and Continue.dev** offer true hybrid search

---

### 3. Language Support

| Solution | AST Parsing | Languages (AST) | Fallback Method | Total Languages |
|----------|-------------|----------------|-----------------|-----------------|
| **CodeWeaver** | ✅ Tree-sitter | **26** | **✅ Intelligent delimiters (language family patterns)** | **170+** |
| Cursor | ⚠️ Unspecified | ⚠️ Unknown | ⚠️ Unknown | ~50-100 (est.) |
| Copilot Workspace | ❌ Language-agnostic | N/A | Text-based | All (basic) |
| Sourcegraph Cody | ⚠️ Unspecified | ⚠️ Unknown | Keyword indexing | All |
| Continue.dev | ✅ Tree-sitter | ~165 | ⚠️ Top-level only | ~165 |
| Bloop | ⚠️ Unspecified | ⚠️ Unknown | ⚠️ Unknown | Unknown |
| Aider | ✅ Tree-sitter | ~165 | ✅ ctags | ~165+ |

**CodeWeaver Advantages**:
1. **Semantic-like chunking for 170+ languages** (not just line-based fallback)
2. **Cross-language AST normalization** (unique in market)
3. **Language family intelligence** in delimiter chunker

---

### 4. Performance & Real-Time Updates

| Solution | Indexing Speed | Incremental Updates | File Watching | Move Detection |
|----------|---------------|---------------------|---------------|----------------|
| **CodeWeaver** | **3.2s for 77k LOC** (index) <br> ~5s total (remote embed) <br> ~20s total (local embed) | **✅ Instant** | **✅ Live** | **✅ Dedup on move** |
| Cursor | ⚠️ Unclear | ✅ Likely | ✅ Likely | ❌ No |
| Copilot Workspace | Server-side | ⚠️ Server-managed | ❌ Client-side | ❌ No |
| Sourcegraph Cody | ⚠️ Unclear | ✅ Yes | ⚠️ Unclear | ❌ No |
| Continue.dev | ⚠️ Unclear | ✅ Yes | ✅ Yes | ❌ No |
| Bloop | "Fast" (Rust, Tantivy, Qdrant) | ⚠️ Unclear | ⚠️ Unclear | ❌ No |
| Aider | N/A (on-demand) | ❌ No | ❌ No | N/A |

**Benchmark Context** (Visual Studio C++ indexing):
- Gears of War: 6.5min → 2.5min (2.5x speedup)
- Unreal Engine 5: 2.5min → 1min (2.7x speedup)
- Chromium: 31min → 5min (6x speedup)

**CodeWeaver's sub-5s total time** for mid-size repos is competitive with industry leaders

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

**Airgapped Deployment Leaders** (Enterprise 2024):
1. Tabnine Enterprise (fully airgapped)
2. **CodeWeaver** (local providers + failover)
3. Sourcegraph Cody Enterprise
4. Continue.dev (via Ollama)

**CodeWeaver's Intelligent Failover**:
- Primary vector store (Qdrant) fails → auto-switch to in-memory store
- Maintains live file watching during failover
- Seamless handover when primary recovers
- **Zero functionality loss** (only slightly degraded results)

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
| Embedding models | 50+ models, 20+ providers | 1-2 models | **CodeWeaver** |
| Hybrid search | ✅ Dense + Sparse | ❌ Dense only | **CodeWeaver** |
| Privacy | ✅ Local option, airgapped | ⚠️ Sends to cloud (experimental local) | **CodeWeaver** |
| IDE integration | Via MCP | Native, deep | **Cursor** |
| Portability | ✅ Any MCP client | ❌ Cursor only | **CodeWeaver** |
| Ease of use | Requires MCP client | Built-in | **Cursor** |

**Best for**:
- **CodeWeaver**: Teams needing customization, privacy, multi-IDE support
- **Cursor**: Individual developers wanting seamless IDE experience

---

### CodeWeaver vs. Continue.dev

| Feature | CodeWeaver | Continue.dev | Winner |
|---------|-----------|--------------|--------|
| Embedding providers | 20+ | 4-5 | **CodeWeaver** |
| Embedding models | 50+ | 5-10 | **CodeWeaver** |
| Hybrid search | ✅ Dense + Sparse | ⚠️ Dense + Keyword | **CodeWeaver** |
| Language support | 170+ (semantic-like) | ~165 (AST + basic fallback) | **CodeWeaver** |
| Portability | ✅ MCP (any client) | ❌ VS Code/JetBrains only | **CodeWeaver** |
| Reranking | 5 providers, 20+ models | Multiple options | **Tie** |
| IDE integration | Via MCP | Native extension | **Continue.dev** |
| Configuration | ⚠️ Requires setup | Config file | **Continue.dev** |

**Best for**:
- **CodeWeaver**: Multi-IDE teams, advanced customization, MCP ecosystem
- **Continue.dev**: VS Code/JetBrains users wanting embedding flexibility with native integration

---

### CodeWeaver vs. Sourcegraph Cody

| Feature | CodeWeaver | Sourcegraph Cody | Winner |
|---------|-----------|------------------|--------|
| Search method | Semantic (embeddings) | Keyword (deprecated embeddings) | **Different philosophies** |
| Scale | Mid-large repos | Massive repos (1M+ LOC) | **Cody** (for scale) |
| Customization | 20+ embedding providers | N/A (uses keyword search) | **CodeWeaver** |
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

---

## CodeWeaver's Unique Differentiators

### ✅ Only CodeWeaver Has ALL of These:

1. **20+ embedding providers, 50+ models** (4-10x more than any competitor)
2. **True hybrid search** (dense + sparse embeddings by default)
3. **170+ language support** with semantic-like chunking (not just AST + line breaks)
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
| **Multi-IDE team** | **CodeWeaver** | MCP protocol works with any client |
| **Massive repos (>1M LOC)** | Sourcegraph Cody | Proven scalability, keyword search scales better |
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
         │  ● CodeWeaver ⭐
         │    (MCP Server)
         │
         │           ● Continue.dev
         │             (IDE Extension)
         │
    ─────┼─────────────────────────────
         │
         │  ● Aider          ● Bloop
         │    (CLI)            (Desktop)
         │
         │  ● Cursor       ● Copilot
         │    (Cloud)        (Cloud)
         │
         ▼
Low Customization (1-2 Models)
```

**CodeWeaver's Position**:
- **Top tier** for embedding customization (20+ providers)
- **High portability** via MCP protocol (not IDE-locked)
- **Unique combination** of flexibility + portability + airgapped capability

---

## Conclusion

**CodeWeaver leads in**:
1. Embedding provider diversity (20+ vs 1-5)
2. Hybrid search (dense + sparse by default)
3. Language support breadth (170+ with semantic-like chunking)
4. Deployment flexibility (local/cloud/airgapped with failover)
5. Portability (MCP-native, not IDE-locked)

**Consider alternatives if**:
- You want deep native IDE integration → Cursor, Continue.dev
- You need proven scale for massive repos → Sourcegraph Cody
- You prefer simplicity over customization → Cursor, Bloop

**CodeWeaver is best for**:
- Teams requiring embedding customization
- Multi-IDE environments
- Privacy-sensitive/airgapped deployments
- MCP ecosystem participants
- Multi-language projects benefiting from cross-language search

---

**Last Updated**: November 17, 2025
**Source**: CodeWeaver Competitive Analysis Research
