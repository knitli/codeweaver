<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Why CodeWeaver Exists

I had **four motivations for creating CodeWeaver**:

## 1. Poor Context = Poor Results

AI agents do a poor job using existing code and APIs because they're much better at generating new code than finding and understanding your codebase's structure and patterns.

When agents don't have proper structural understanding, they:
- Miss relevant code that exists elsewhere in your project
- Fail to follow established patterns and conventions
- Generate solutions that duplicate existing functionality
- Struggle to understand the relationships between components
- Need to spend more time and tokens *understanding* than *doing*

The root issue: agents need **structural and semantic understanding** tailored to their tasks, not just keyword matching.

## 2. Ownership and Freedom

The *context delivery* tools available to agents aren't great. Most rely on simple keyword search -- literally `grep` or `ripgrep`.

There are some better implementations out there, but most are integrated into MCP clients (Claude Code, Roo, Continue) or IDEs (Cursor). They aren't yours to deploy and use how you want, with the models, providers, clients, and IDEs you want to use.

**Want to:**
- Use your preferred IDE (VIM, Emacs, VS Code, whatever)?
- Switch between different AI agent, embedding (sparse/dense and reranking) providers? 
- Deploy to your infrastructure?
- Customize how context is indexed and retrieved?
- Work offline or in airgapped environments?

With most tools, you can't. CodeWeaver gives you that freedom.

## 3. Cost

Coding agents are *very* inefficient. If you have watched them stumble around your codebase reading the same huge files over and over again, you know this. They carry all that context with them for every tool call.

CodeWeaver's overall goal is to stop that cycle -- give agents exactly what they need from the start. Cut context -- and cost -- by **50%+**.

**The inefficiency compounds:**
- Agents read entire files when they need a single function
- They re-read the same files across multiple tool calls
- They carry massive context windows that drive up token costs
- Even well-meaning MCP tools contribute: several popular MCP servers have **15,000+ tokens in prompt overhead** -- all the prompts they supply **every single message** to tell an agent about their available tools and how to use them

CodeWeaver takes a different approach:
- Returns only the relevant code fragments
- Indexes once, serves efficiently
- Minimal MCP protocol overhead (less than 1,000 tokens)
- Smart caching and reuse

## 4. Agent-First Tools

Most MCP tools are literally just human tools and APIs with an MCP interface. AI agents are purpose-trained to *generate language*, and you've handed them a complex, many-faceted tool that can be used in many different ways, and said "figure it out."

The harder, and better course, is to give AI agents tools *built for them*. Tools that allow them to do what they do best (generate code), and minimize their need to do things they aren't great at.

**Example:**
- **Human tools**: Choose from 30 different search options, configure parameters, combine tools, parse results
- **Agent-first tools**: "Find code related to authentication" → get exactly what you need

I don't want to read a novella to figure out how to use a coding tool. But we ask agents to do exactly that every time we give them a complex tool with extensive documentation.

**CodeWeaver's philosophy:**
- Simple interface: `find_code(description)`
- Smart defaults that work
- Optional refinement when needed
- Let the tool handle complexity, not the agent

---

## The Result Without CodeWeaver

Models get random snippets. The indexing falls behind. Offline mode is a coin toss.
Context is shallow, inconsistent, and fragile.

## CodeWeaver's Path

* **One focused capability:** structural + semantic code understanding using layered hybrid (sparse + dense) search
* **One surface for AI (MCP)** and **one surface for humans (CLI/TUI)**
* **Hybrid search built for code first** - understands code structure, not just text
* **Resilient design:** maintains a separate lightweight hybrid vector index that automatically kicks in when your primary providers fail. Your fallback is better than most tools' primary mode.
* **Your infrastructure:** deploy however you want, wherever you want

It's not trying to give AI all the tools.
It gives AI one *great* tool.

---

## The Technical Bet

CodeWeaver bets that **context quality matters more than context quantity**.

Instead of giving agents every possible tool and letting them figure it out, we give them:
- Deep structural understanding of your codebase
- Semantic relationships between components
- Intent-aware search that understands what they're trying to accomplish
- Reliable fallback that works even when everything else fails

This makes agents more effective with less effort, lower cost, and better results.
