---
title: CLI Reference
description: Complete command-line interface reference for CodeWeaver
---

# CodeWeaver CLI Reference

The `cw` command (alias for `codeweaver`) is your primary interface for managing CodeWeaver. It provides tools for initialization, indexing, searching, and diagnostics.

:::note
CodeWeaver includes `cw doctor` for deep diagnostics and `cw init --profile` for rapid setup.
:::

## Core Workflow

```bash
# 1. Initialize with a profile
cw init --profile recommended

# 2. Start the background daemon
cw start

# 3. Search your codebase
cw search "authentication middleware"
```

---

## Main Commands

### `cw init`
Initialize your CodeWeaver configuration.

**Usage:**
```bash
cw init [OPTIONS]
```

**Options:**
- `--profile [recommended|quickstart|testing]` - Choose a premade provider profile.
- `--force` - Overwrite existing configuration.

**Example:**
```bash
cw init --profile recommended
```

---

### `cw doctor`
Check system configuration and diagnose issues. This is the first command you should run if something isn't working.

**Usage:**
```bash
cw doctor
```

**What it checks:**
- **Provider Connectivity:** Verifies API keys and cloud service reachability.
- **Index Health:** Checks for corrupted or outdated search indexes.
- **DI Container:** Validates that all required services are correctly registered.
- **Environment:** Checks Python version, project paths, and disk space.

---

### `cw search`
Search indexed repositories using hybrid (Semantic + AST + Keyword) search.

**Usage:**
```bash
cw search QUERY [OPTIONS]
```

**Arguments:**
- `QUERY` - Your natural language search query.

**Options:**
- `--repo PATH` - Repository to search (default: current directory).
- `--limit N` - Maximum number of results.
- `--context-lines N` - Lines of context around each match.

---

### `cw start` / `cw stop`
Manage the CodeWeaver background daemon.

**Usage:**
```bash
cw start [OPTIONS]
cw stop
```

**Options:**
- `--foreground` - Run in the current terminal instead of the background.
- `--project PATH` - Start services for a specific project.

---

### `cw status`
Show the status of the current project, including indexing progress and active providers.

**Usage:**
```bash
cw status
```

---

## Configuration

CodeWeaver uses `codeweaver.toml` as its primary configuration format.

### File Locations (Priority Order)
1. **Project Root:** `./codeweaver.toml`
2. **User Config:** `~/.config/codeweaver/config.toml`
3. **Environment:** `CODEWEAVER_CONFIG_FILE`

### Environment Variables
- `CODEWEAVER_PROJECT_PATH` - Override the current project path.
- `VOYAGE_API_KEY` - API key for Voyage AI.
- `ANTHROPIC_API_KEY` - API key for the Context Agent.

---

## Exit Codes
- `0` - Success.
- `1` - General error.
- `2` - Configuration/Validation error.
- `3` - Index/Storage error.
- `4` - Provider/API error.
