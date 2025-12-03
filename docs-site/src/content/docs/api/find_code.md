---
title: find_code
description: API reference for find_code
---

# find_code

# Implementation of the find_code tool.

CodeWeaver differentiates between *internal* and *external* tools. External tools -- and there is only one, this one, the **`find_code`** tool -- are exposed to the user and user's AI agents. `find_code` is intentionally very simple. This module contains the back-end, execution-side, of the `find_code` tool. The entry-point exposed to users and agents is in `codeweaver.mcp.user_agent`.

## How it Works

You, or your AI agents, simply ask a question, explain what you are trying to do or what you need information for, and CodeWeaver will answer it.

For example, your agent might say:
    > Note: The main parameters for `find_code` that are exposed to users and agents are `query`, `intent`, and `focus_languages`. There's also `token_limit`, but that's self-explanatory.
    ```
    ```

`find_code` is different from other MCP tools in that it:
    1) Is intentionally designed to reduce "*cognitive load*"[^1] on *agents*. Put simply, AI agents have "great minds and terrible hands." `find_code` aims to bridge that gap between intellect and action. The explosion of MCP tools has also increased the cognitive load on agents -- when there are 100 tools, which one do you use? It's a hard task for a human, and harder for an AI. `find_code` aims to be a simple, universal tool that can be used in many situations.
    2) `find_code`, and all of CodeWeaver, is entirely designed to *narrow context*. AI agents are very prone to "*context poisoning*" and "*context overload*". In even small codebases, this can happen very quickly -- often before the agent even gets to the point of using a tool. `find_code` intentionally filters and shields the user's agent from unnecessary context, and only provides the context that is relevant to the query. This is a key part of CodeWeaver's design philosophy.
    3) It's context-aware. `find_code` understands the context of your project, the files, the languages, and the structure. It uses this context to provide relevant results.

    [^1]: AI agents don't experience 'cognitive load' in the human sense, but we use the term here metaphorically. Practically speaking, two things actually happen: 1) Context 'poisoning' -- the agent's context gets filled with irrelevant information that steers it away from the results you want, 2) The agent, which really doesn't 'think' in the human sense, can't tell what tool to use, so it often picks the wrong one -- tool use is more of a side effect of their training to generate language.

## Architecture

The find_code package is organized into focused modules:

- **conversion.py**: Converts SearchResult objects to CodeMatch responses
- **filters.py**: Post-search filtering (test files, language focus)
- **pipeline.py**: Query embedding and vector search orchestration
- **scoring.py**: Score calculation, reranking, and semantic weighting

This modular structure makes it easy to:
- Add new filtering strategies
- Extend scoring mechanisms
- Integrate new search providers
- Test individual components in isolation

## Philosophy: Agent UX

The design of `find_code` is heavily influenced by the concept of *Agent User Experience (Agent UX)*. Just as traditional UX focuses on making software intuitive and efficient for human users, Agent UX aims to optimize how AI agents interact with tools and systems. When we ask agents to use a tool with a human API, we need to consider how the agent will perceive and utilize that tool. `find_code` is designed to be as straightforward and effective as possible for AI agents, minimizing the complexity they have to deal with.
