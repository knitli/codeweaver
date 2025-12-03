---
title: CLI Reference
description: Complete command-line interface reference for CodeWeaver
---

# CodeWeaver CLI Reference

CodeWeaver: Powerful code search and understanding for humans and agents.

:::note
This is a simplified CLI reference for the POC. For complete documentation including all subcommands and options, see the full CLI documentation.
:::

## Quick Start

```bash
# Index a repository
codeweaver index /path/to/repo

# Search your code
codeweaver search "authentication logic"

# Start MCP server
codeweaver server
```

## Main Commands

### `codeweaver config`

Configure CodeWeaver settings.

**Usage:**
```bash
codeweaver config
```

### `codeweaver search`

Search indexed repositories using semantic search.

**Usage:**
```bash
codeweaver search QUERY [OPTIONS]
```

**Arguments:**
- `QUERY` - Natural language search query

**Options:**
- `--repo PATH` - Repository to search (default: current directory)
- `--limit N` - Maximum number of results (default: 10)
- `--context-lines N` - Lines of context around matches (default: 3)

**Examples:**
```bash
# Basic search
codeweaver search "user authentication"

# Search specific repository
codeweaver search "api endpoints" --repo ~/projects/myapp

# Limit results
codeweaver search "database queries" --limit 5
```

### `codeweaver server`

Start the CodeWeaver MCP server for AI agent integration.

**Usage:**
```bash
codeweaver server [OPTIONS]
```

**Options:**
- `--host TEXT` - Host to bind to (default: localhost)
- `--port INT` - Port to listen on (default: 8765)
- `--repo PATH` - Repository to serve

**Example:**
```bash
codeweaver server --port 8765
```

### `codeweaver index`

Index a repository for semantic search.

**Usage:**
```bash
codeweaver index PATH [OPTIONS]
```

**Arguments:**
- `PATH` - Path to repository to index

**Options:**
- `--force` - Force reindex even if index exists
- `--incremental` - Only index changed files

**Examples:**
```bash
# Index current directory
codeweaver index .

# Force reindex
codeweaver index . --force

# Incremental update
codeweaver index . --incremental
```

### `codeweaver doctor`

Check system configuration and diagnose issues.

**Usage:**
```bash
codeweaver doctor
```

Verifies:
- Provider configurations
- API keys and credentials
- Index health
- Dependencies

### `codeweaver list`

List available providers and models.

**Subcommands:**
- `providers` - List all available providers
- `embedding` - List embedding providers
- `vector-store` - List vector store providers
- `reranking` - List reranking providers

**Examples:**
```bash
# List all providers
codeweaver list providers

# List embedding providers
codeweaver list embedding
```

### `codeweaver init`

Initialize CodeWeaver configuration.

**Subcommands:**
- `config` - Initialize configuration file
- `mcp` - Initialize MCP server configuration

**Examples:**
```bash
# Initialize config
codeweaver init config

# Initialize MCP server
codeweaver init mcp
```

### `codeweaver status`

Show status of indexed repositories.

**Usage:**
```bash
codeweaver status [PATH]
```

Shows:
- Index status
- Number of indexed files
- Last update time
- Provider configuration

## Configuration

CodeWeaver can be configured via:
1. Configuration file (`~/.codeweaver/config.yaml`)
2. Environment variables
3. Command-line options

### Configuration File

Example configuration:

```yaml
# ~/.codeweaver/config.yaml
embedding:
  provider: openai
  model: text-embedding-3-small

vector_store:
  provider: chroma
  path: ~/.codeweaver/vectors

reranking:
  provider: cohere
  model: rerank-english-v3.0

indexing:
  chunk_size: 512
  chunk_overlap: 128
```

### Environment Variables

- `CODEWEAVER_CONFIG` - Path to configuration file
- `CODEWEAVER_DATA_DIR` - Data directory
- `OPENAI_API_KEY` - OpenAI API key
- `COHERE_API_KEY` - Cohere API key
- `ANTHROPIC_API_KEY` - Anthropic API key

## Exit Codes

- `0` - Success
- `1` - General error
- `2` - Configuration error
- `3` - Index error
- `4` - Provider error

## See Also

- [Configuration Guide](/guides/configuration/)
- [Provider Setup](/guides/providers/)
- [API Reference](/api/)
