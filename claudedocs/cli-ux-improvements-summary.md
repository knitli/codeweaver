<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# CLI UX Improvements Summary

## Overview

This document summarizes the CLI user experience improvements made to the Option A service architecture implementation plan based on UX analysis.

## Key Changes

### 1. Background Services Management

**New Commands:**
- `cw start` - Start background services (indexing, file watching, telemetry, management server)
- `cw stop` - Stop background services gracefully

**Rationale:**
- Simple, intuitive interface ("start/stop CodeWeaver")
- Common pattern in server software (postgres, redis, nginx)
- Clear separation from MCP server concerns

### 2. MCP Server Command (Unchanged Name, Enhanced Behavior)

**Command:** `cw server [options]`

**New Behavior:**
- Automatically starts background services if not running
- `--no-auto-start` flag to disable auto-start (advanced use)
- Clear console output indicating service status

**Rationale:**
- Maintains backward compatibility
- Provides smart defaults (most users don't need manual service management)
- Explicit control available when needed

### 3. Enhanced Status Command

**Command:** `cw status [options]`

**New Flags:**
- `--services` - Show only background services status
- `--index` - Show only index status (current behavior)
- (no flags) - Comprehensive status (all systems)

**Rationale:**
- Single command for all observability needs
- Progressive disclosure (detailed when needed)
- Consistent with existing `--watch` flag

## What Was Removed from Original Plan

### ❌ Removed: `cw start` / `cw serve` shortcuts

**Original proposal:**
- `cw start` → shortcut for stdio server
- `cw serve` → shortcut for HTTP server

**Why removed:**
- Confusing distinction between "start" and "serve"
- Namespace pollution at top level
- stdio clients launch server automatically (no manual start needed)
- HTTP users can type `cw server` (minimal friction)

### ❌ Removed: `cw server start` / `cw server stop`

**Original proposal:**
- Make `server` a command group with `start` and `stop` subcommands

**Why removed:**
- Breaking change (current `cw server` behavior)
- Inconsistent with other direct commands (`index`, `search`)
- `stop` implementation incomplete (TODO comment)
- Server stop better handled by process managers (systemd, docker)

### ❌ Removed: Incomplete `server stop` feature

**Original proposal:**
- `cw server stop` via pidfile management

**Why removed:**
- Marked as TODO in plan (incomplete)
- Cross-platform pidfile complexity
- Production uses systemd/docker/etc (not direct CLI)
- False promise to users (command exists but doesn't work)

## Final CLI Structure

```bash
# Background services
cw start                          # Start services
cw stop                           # Stop services

# MCP server
cw server                         # Start MCP server (auto-starts services)
cw server --no-auto-start         # Start MCP only (advanced)
cw server --transport stdio       # Specify transport
cw server --transport streamable-http

# Manual operations
cw index                          # Manual indexing
cw search <query>                 # CLI search

# Observability
cw status                         # Comprehensive status
cw status --services              # Services-only
cw status --index                 # Index-only
cw status --watch                 # Continuous monitoring

# Existing commands (unchanged)
cw config
cw doctor
cw init
cw list / ls
```

## User Workflows

### Quick Start (Most Common)

```bash
# User just wants to start CodeWeaver
cw server

# Output:
# [dim]Background services not running, starting...[/dim]
# [green]✓[/green] Background services started
# [green]Starting MCP server on 127.0.0.1:9328[/green]
# [dim]Management server: http://127.0.0.1:9329[/dim]
```

### Explicit Service Management (Advanced)

```bash
# Start services separately
cw start

# Later, start MCP server
cw server --no-auto-start
```

### Status Monitoring

```bash
# Check everything
cw status

# Check just background services
cw status --services

# Continuous monitoring
cw status --watch
```

### Shutdown

```bash
# Stop background services (also stops dependent MCP servers)
cw stop
```

## Help Text Example

```
$ cw --help

CodeWeaver: Powerful code search for humans and agents

Commands:
  start      Start background services (indexing, file watching, telemetry)
  stop       Stop background services
  server     Start MCP server (auto-starts services if needed)
  index      Manual indexing operations
  search     Search codebase from command line
  status     Show system status (services, indexing, health)
  config     Manage configuration
  doctor     Validate setup
  init       Initialize configuration
  list, ls   List available resources
```

## Benefits

### 1. Simplicity
- ✅ Minimal commands for common workflows
- ✅ Smart defaults reduce cognitive load
- ✅ Clear, intuitive naming

### 2. Backward Compatibility
- ✅ `cw server` still works (no breaking changes)
- ✅ Existing documentation remains valid
- ✅ Deployment scripts unchanged

### 3. Discoverability
- ✅ Help text clearly explains each command
- ✅ No confusing overlapping commands
- ✅ Progressive disclosure (simple → advanced)

### 4. Architecture Alignment
- ✅ Reflects actual system architecture (services + MCP layer)
- ✅ Clear separation of concerns
- ✅ Room for future expansion

## Implementation Notes

### Auto-Start Mechanism

```python
@cyclopts.command
def server(..., no_auto_start: bool = False):
    """Start CodeWeaver MCP server."""

    if not no_auto_start:
        if not asyncio.run(is_services_running()):
            console.print("[dim]Background services not running, starting...[/dim]")
            # Start services in background thread
            start_services_in_background()
            console.print("[green]✓[/green] Background services started")
```

### Service Detection

Services running status detected via management server health endpoint:
- Management server runs on port 9329 (always HTTP)
- Health check: `GET http://127.0.0.1:9329/health`
- Returns 200 OK if services running

### Graceful Shutdown

Services shutdown via management server API:
- Shutdown endpoint: `POST http://127.0.0.1:9329/shutdown`
- Triggers graceful shutdown of all background services
- MCP servers depending on services will also stop

## Migration from Original Plan

### Code Changes

**Remove:**
- `server_app = cyclopts.App("server")` (command group)
- `@server_app.command def start()` (subcommand)
- `@server_app.command def stop()` (incomplete feature)
- Top-level `start` and `serve` convenience commands

**Add:**
- `cli/commands/services.py` with `start()` and `stop()` commands
- `--no-auto-start` flag to `server()` command
- Auto-start logic in `server()` command
- Enhanced `status()` command with filtering flags

### Documentation Changes

**Update:**
- README Quick Start section
- CLI Commands reference
- MCP client configuration examples (stdio args)
- Help text and docstrings

**Add:**
- Background services management section
- Auto-start behavior explanation
- Relationship between `index` and background indexing

## Future Considerations

### If Moving to Separate-Process Architecture

Current design supports evolution:
- `cw start` already manages background services independently
- `cw server` already treats services as external dependency
- Clean migration path: services become actual separate process

### Additional Commands (Future)

Possible future additions without breaking current structure:
- `cw restart` - Restart background services
- `cw reload` - Reload configuration without full restart
- `cw logs` - Stream service logs
- `cw health` - Detailed health diagnostics

## Conclusion

The revised CLI structure:
- **Maintains simplicity** for common workflows
- **Preserves backward compatibility** with existing usage
- **Reflects architecture** accurately (services + MCP)
- **Provides clear boundaries** between different concerns
- **Enables future expansion** without breaking changes

Users get:
- One command to start CodeWeaver: `cw server`
- Clear control when needed: `cw start`, `cw stop`
- Comprehensive observability: `cw status`
- No confusing overlaps or incomplete features
