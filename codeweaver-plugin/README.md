<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# CodeWeaver Claude Code Plugin

**Exquisite Context for AI Agents** — One-command installation of CodeWeaver's semantic code search MCP server.

## Quick Install

```bash
/plugin install codeweaver@knitli
```

That's it! CodeWeaver is now available in your Claude Code session.

## What You Get

- **Hybrid Search**: Semantic + AST + keyword search for precise code discovery
- **166+ Languages**: Language-aware chunking and understanding
- **27 Languages with AST**: Deep semantic analysis for major languages
- **Automatic Indexing**: Background indexing with file watching
- **Zero Configuration**: Works out of the box with sensible defaults

## How It Works

Once installed, CodeWeaver runs as an MCP server that Claude can query to find relevant code in your project. It combines:

1. **Semantic Search**: Understanding what code *means*, not just what it says
2. **AST Analysis**: Structural understanding of code organization
3. **Keyword Matching**: Traditional search when appropriate
4. **Intelligent Ranking**: RRF (Reciprocal Rank Fusion) for best results

## Usage

CodeWeaver automatically indexes your project on first use. Claude can then search your codebase with natural language queries:

- "Where do we handle authentication?"
- "Find the database connection logic"
- "Show me error handling code"
- "Where is the user validation implemented?"

## Storage

CodeWeaver stores its index and cache in `${CLAUDE_PLUGIN_DATA}/codeweaver`, which persists across plugin updates.

## Configuration

For advanced configuration (custom embedding providers, vector stores, etc.), see the [main CodeWeaver documentation](https://github.com/knitli/codeweaver).

Default configuration uses:
- **Embedding Provider**: Voyage AI (requires API key) with automatic fallback to local FastEmbed
- **Vector Store**: Qdrant (in-memory mode, no Docker required)
- **Chunking**: Language-aware with semantic boundaries

## Requirements

- Python 3.12 or later
- [uv](https://astral.sh/uv) package manager (bundled with plugin)

## Support

- **Documentation**: https://github.com/knitli/codeweaver
- **Issues**: https://github.com/knitli/codeweaver/issues
- **Discord**: Coming soon

## Privacy

CodeWeaver respects your privacy:
- Code stays local by default (optional cloud embeddings)
- Telemetry is privacy-focused and opt-out
- See [Privacy Policy](https://github.com/knitli/codeweaver/blob/main/PRIVACY_POLICY.md)

## License

MIT OR Apache-2.0

Built with ❤️ by [Knitli](https://knitli.com)
