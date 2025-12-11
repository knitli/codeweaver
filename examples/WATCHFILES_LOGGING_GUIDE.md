<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Watchfiles Logging Integration Guide

Complete guide to capturing and controlling logging output from `watchfiles` in CodeWeaver.

## Overview

The `WatchfilesLogManager` class provides comprehensive integration between `watchfiles` logging and CodeWeaver's existing logging infrastructure, featuring:

- **Pattern-based filtering** using `SerializableLoggingFilter`
- **Rich handler support** for beautiful console output
- **FastMCP context routing** for structured client logging
- **Dynamic configuration** with runtime updates
- **Multiple output modes** (Rich, plain text, or FastMCP)

## Quick Start

### Basic Usage

```python
from codeweaver.engine.indexer import FileWatcher
import logging

# Enable watchfiles logging with default settings
watcher = FileWatcher(
    '/path/to/watch',
    capture_watchfiles_output=True,  # Enable logging capture
)
```

### Debug Mode

```python
# Capture all watchfiles debug output
watcher = FileWatcher(
    '/path/to/watch',
    capture_watchfiles_output=True,
    watchfiles_log_level=logging.DEBUG,  # Show everything
)
```

### Quiet Mode

```python
# Only show errors
watcher = FileWatcher(
    '/path/to/watch',
    capture_watchfiles_output=True,
    watchfiles_log_level=logging.ERROR,  # Errors only
)
```

## Pattern-Based Filtering

### Include Pattern

Only show logs matching a regex pattern:

```python
watcher = FileWatcher(
    '/path/to/watch',
    capture_watchfiles_output=True,
    watchfiles_include_pattern=r'file|change|add',
)
```

### Exclude Pattern

Hide logs matching a pattern:

```python
watcher = FileWatcher(
    '/path/to/watch',
    capture_watchfiles_output=True,
    watchfiles_exclude_pattern=r'\.git/|node_modules/|__pycache__/',
)
```

### Combined Filtering

```python
watcher = FileWatcher(
    '/path/to/watch',
    capture_watchfiles_output=True,
    watchfiles_include_pattern=r'\.(py|js|ts)$',  # Only code files
    watchfiles_exclude_pattern=r'test|spec',       # Exclude tests
)
```

## FastMCP Integration

Route watchfiles logs to FastMCP client for structured logging:

```python
from fastmcp import Context

async def watch_with_context(context: Context):
    watcher = FileWatcher(
        '/path/to/watch',
        capture_watchfiles_output=True,
        context=context,              # Provide FastMCP context
        route_logs_to_context=True,   # Enable routing
    )
    await watcher.run()
```

Logs will appear in the FastMCP client with structured data:

```json
{
  "msg": "File change detected",
  "extra": {
    "logger": "watchfiles",
    "level": "INFO",
    "module": "main",
    "function": "watch",
    "line": 123
  }
}
```

## Dynamic Configuration

Update logging configuration at runtime:

```python
# Start with minimal logging
watcher = FileWatcher(
    '/path/to/watch',
    capture_watchfiles_output=True,
    watchfiles_log_level=logging.WARNING,
)

# Later, enable debug mode
watcher.update_logging(level=logging.DEBUG)

# Add filtering
watcher.update_logging(
    include_pattern=r'\.py$',
    exclude_pattern=r'__pycache__',
)

# Update FastMCP context
watcher.update_logging(context=new_context)
```

## Output Formats

### Rich Output (Default)

Beautiful, colored console output:

```python
watcher = FileWatcher(
    '/path/to/watch',
    capture_watchfiles_output=True,
    watchfiles_use_rich=True,  # Default
)
```

### Plain Text Output

Standard text format for scripts or log files:

```python
watcher = FileWatcher(
    '/path/to/watch',
    capture_watchfiles_output=True,
    watchfiles_use_rich=False,
)
```

## Standalone Usage

Use `WatchfilesLogManager` independently:

```python
from codeweaver.engine.indexer import WatchfilesLogManager
import logging

# Create manager
log_manager = WatchfilesLogManager(
    log_level=logging.INFO,
    use_rich=True,
    include_pattern=r'file',
    exclude_pattern=r'permission',
)

# Now all watchfiles operations use this config
```

## Advanced Features

### Compiled Regex Patterns

```python
import re

pattern = re.compile(
    r'(?:file|directory).*(?:added|modified|deleted)',
    re.IGNORECASE
)

watcher = FileWatcher(
    '/path/to/watch',
    capture_watchfiles_output=True,
    watchfiles_include_pattern=pattern,
)
```

### Multiple Watchers

Each watcher can have different logging configuration:

```python
# Source code - verbose
watcher_src = FileWatcher(
    '/path/to/src',
    capture_watchfiles_output=True,
    watchfiles_log_level=logging.DEBUG,
)

# Docs - minimal
watcher_docs = FileWatcher(
    '/path/to/docs',
    capture_watchfiles_output=True,
    watchfiles_log_level=logging.WARNING,
)

await asyncio.gather(
    watcher_src.run(),
    watcher_docs.run(),
)
```

### Environment-Based Configuration

```python
import os
import sys
import logging

debug_mode = os.getenv('DEBUG', '').lower() == 'true'
log_level = logging.DEBUG if debug_mode else logging.WARNING
use_rich = sys.stdout.isatty()

watcher = FileWatcher(
    '/path/to/watch',
    capture_watchfiles_output=True,
    watchfiles_log_level=log_level,
    watchfiles_use_rich=use_rich,
)
```

## Architecture

### Component Hierarchy

```
FileWatcher
  └─> WatchfilesLogManager
      ├─> SerializableLoggingFilter (pattern filtering)
      ├─> setup_logger (Rich handler)
      └─> ContextHandler (FastMCP routing)
```

### Log Flow

1. **Watchfiles** generates log records
2. **SerializableLoggingFilter** applies include/exclude patterns
3. **Handler** routes to:
   - **Rich handler** → Beautiful console output
   - **ContextHandler** → FastMCP client
   - **StreamHandler** → Plain text output

### Integration Points

- `SerializableLoggingFilter` from `codeweaver.config._logging`
- `setup_logger` from `codeweaver.common._logging`
- `log_to_client_or_fallback` for FastMCP routing
- Standard Python `logging` module

## API Reference

### FileWatcher Parameters

```python
FileWatcher(
    *paths: str | Path,                           # Paths to watch
    capture_watchfiles_output: bool = False,      # Enable logging
    watchfiles_log_level: int = logging.WARNING,  # Log level
    watchfiles_use_rich: bool = True,             # Rich formatting
    watchfiles_include_pattern: str | Pattern | None = None,
    watchfiles_exclude_pattern: str | Pattern | None = None,
    context: Context | None = None,               # FastMCP context
    route_logs_to_context: bool = True,           # Enable routing
    # ... other parameters
)
```

### WatchfilesLogManager Parameters

```python
WatchfilesLogManager(
    log_level: int = logging.WARNING,
    use_rich: bool = True,
    include_pattern: str | Pattern | None = None,
    exclude_pattern: str | Pattern | None = None,
    context: Context | None = None,
    route_to_context: bool = True,
)
```

### Methods

#### FileWatcher.update_logging()

```python
watcher.update_logging(
    level: int | None = None,
    include_pattern: str | Pattern | None = None,
    exclude_pattern: str | Pattern | None = None,
    context: Context | None = None,
)
```

#### WatchfilesLogManager Methods

```python
log_manager.set_level(level: int)
log_manager.add_filter(include_pattern=..., exclude_pattern=...)
log_manager.clear_filters()
log_manager.update_context(context: Context | None)
```

## Performance Considerations

1. **Pattern Complexity**: Complex regex patterns may impact performance
2. **Log Volume**: Debug mode generates significant output
3. **Context Routing**: Async routing adds minimal overhead
4. **Rich Formatting**: Slightly slower than plain text

## Best Practices

### 1. Start Quiet, Go Verbose

```python
# Production: minimal logging
watcher = FileWatcher(..., watchfiles_log_level=logging.ERROR)

# Development: verbose logging
watcher = FileWatcher(..., watchfiles_log_level=logging.DEBUG)
```

### 2. Use Patterns for Large Projects

```python
# Filter to relevant files only
watcher = FileWatcher(
    ...,
    watchfiles_include_pattern=r'\.(py|js|ts)$',
    watchfiles_exclude_pattern=r'node_modules/|\.git/',
)
```

### 3. Route to FastMCP in Tools

```python
@mcp.tool()
async def watch_directory(path: str):
    context = mcp.get_context()
    watcher = FileWatcher(
        path,
        context=context,
        route_logs_to_context=True,
    )
    # Logs appear in MCP client
```

### 4. Use Rich in Development

```python
# Rich for humans
watcher = FileWatcher(..., watchfiles_use_rich=True)

# Plain text for log files
watcher = FileWatcher(..., watchfiles_use_rich=False)
```

## Troubleshooting

### Logs Not Appearing

1. Check `capture_watchfiles_output=True`
2. Verify log level is appropriate
3. Check filters aren't too restrictive

### Too Much Output

1. Increase log level (INFO → WARNING → ERROR)
2. Add exclude patterns
3. Use more specific include patterns

### Rich Formatting Issues

1. Check terminal supports ANSI colors
2. Disable Rich in non-TTY environments
3. Use `watchfiles_use_rich=False`

## Examples

See `examples/watchfiles_logging_examples.py` for complete working examples including:

- Basic capture
- Debug logging
- Pattern filtering
- FastMCP integration
- Dynamic updates
- Multiple watchers
- Custom handlers
- And more...

## Related Documentation

- [Python logging docs](https://docs.python.org/3/library/logging.html)
- [Rich logging docs](https://rich.readthedocs.io/en/stable/logging.html)
- [watchfiles docs](https://watchfiles.helpmanual.io/)
- CodeWeaver logging: `src/codeweaver/common/_logging.py`
- Configuration: `src/codeweaver/config/_logging.py`
