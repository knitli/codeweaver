# `codeweaver init` Command Test Report

**Test Date**: 2025-11-07
**Tester**: Quality Engineer (Claude)
**Status**: ❌ CRITICAL FAILURES - Command Cannot Execute

## Executive Summary

The `codeweaver init` command has **multiple critical blocking issues** that prevent it from running at all. The command cannot be executed in any variation due to import errors and missing dependencies.

**Critical Severity**: 🔴 P0 - Complete failure, no workaround available
**Impact**: 100% of init command functionality is broken
**Recommendation**: Fix import errors before any further testing

---

## Critical Blocking Issues

### Issue 1: Invalid fastmcp imports ❌ BLOCKER

**Location**: `src/codeweaver/cli/commands/init.py:24`

```python
from fastmcp import claude_code, claude_desktop, cursor, gemini_cli, mcp_json
```

**Error**:
```
ImportError: cannot import name 'claude_code' from 'fastmcp'
```

**Root Cause**: These modules do not exist in the fastmcp package. The actual fastmcp exports are:
```python
['Client', 'Context', 'FastMCP', 'Settings', '__all__',
 'client', 'exceptions', 'fastmcp', 'mcp_config', 'prompts',
 'resources', 'server', 'settings', 'tools', 'utilities', 'warnings']
```

**Impact**: Command cannot be imported at all, making ALL init functionality unavailable.

**Evidence**:
```bash
$ uv run codeweaver init --help
Fatal error: Cannot import module 'codeweaver.cli.commands.init' from 'codeweaver.cli.commands.init:app'
```

---

### Issue 2: Missing config wizard function ❌ BLOCKER

**Location**: `src/codeweaver/cli/commands/init.py:82-94`

```python
from codeweaver.cli.commands.config import init as config_init_wizard
# ...
config_init_wizard(output=config_path, force=False)
```

**Error**:
```
ImportError: cannot import name 'init' from 'codeweaver.cli.commands.config'
```

**Root Cause**: The `config.py` module does not export an `init` function. Available exports:
```python
__all__ = ("app", "main")
```

**Impact**: Even if the fastmcp import is fixed, the `_create_codeweaver_config()` function would fail when called.

---

## Test Plan (Cannot Execute)

The following test variations **cannot be executed** until blocking issues are resolved:

### Planned Tests

#### Basic Commands
- [ ] `codeweaver init --help`
- [ ] `codeweaver init config --help`
- [ ] `codeweaver init mcp --help`

#### Default Behavior
- [ ] `codeweaver init` (should do both config and mcp)
- [ ] Verify `.codeweaver.toml` created
- [ ] Verify MCP config created at correct location

#### Flag Variations
- [ ] `codeweaver init --quick`
- [ ] `codeweaver init --config-only`
- [ ] `codeweaver init --mcp-only`
- [ ] `codeweaver init --force`

#### Client Variations
- [ ] `codeweaver init --client claude_code`
- [ ] `codeweaver init --client claude_desktop`
- [ ] `codeweaver init --client cursor`
- [ ] `codeweaver init --client vscode`
- [ ] `codeweaver init --client mcpjson`
- [ ] `codeweaver init --client gemini_cli`

#### Transport Variations
- [ ] `codeweaver init --transport streamable-http`
- [ ] `codeweaver init --transport stdio`

#### Config Level Variations
- [ ] `codeweaver init --config-level project`
- [ ] `codeweaver init --config-level user`

#### Subcommands
- [ ] `codeweaver init config`
- [ ] `codeweaver init mcp`
- [ ] `codeweaver init mcp --output print`
- [ ] `codeweaver init mcp --output copy` (requires pyperclip)

---

## Architecture Analysis

### Expected File Locations

Based on code analysis in `_get_client_config_path()`:

**Project-level configs**:
- Claude Code: `.claude/mcp.json`
- Cursor: `.cursor/mcp.json`
- VSCode: `.vscode/mcp.json`
- Gemini CLI: `.gemini/mcp.json`
- Generic MCP: `.mcp.json`

**User-level configs**:
- Claude Code (Linux): `~/.config/claude-code/mcp.json`
- Claude Desktop (Linux): `~/.config/Claude/claude_desktop_config.json`
- Generic MCP: `~/.config/codeweaver/mcp.json`

**Unsupported combinations**:
- Cursor: No user-level config (project only)
- Gemini CLI: No user-level config (project only)
- Claude Desktop: No project-level config (user only)

### Transport Logic

**stdio transport** (line 569-579):
- Creates `StdioCodeWeaverConfig`
- Default command: `"codeweaver server --transport stdio"`
- Spawns per-session server instance
- No background indexing

**streamable-http transport** (line 580-590):
- Creates `CodeWeaverMCPConfig`
- Default URL: `127.0.0.1:9328`
- Connects to running server
- Enables background indexing

---

## Code Quality Issues (Beyond Blocking Bugs)

### Design Issues

1. **Unused client_modules dict** (line 37-43):
   - Dict maps client names to fastmcp modules
   - Never actually used in code
   - Modules don't exist anyway

2. **Missing quick mode implementation** (line 88-92):
   - Comment says "will be implemented by the config wizard's quick mode"
   - But config wizard doesn't exist
   - Flag is accepted but does nothing

3. **Inconsistent parameter naming**:
   - `interactive` parameter in `config()` command is unused (line 103)
   - Always defaults to True but never checked

### Error Handling Gaps

1. **Missing validation**:
   - No check if server is running for streamable-http transport
   - No validation of host:port reachability
   - No check if command exists for stdio transport

2. **Backup logic issue**:
   - Creates backups but never uses return value (line 350: `_ = _backup_config(config_path)`)
   - No cleanup of old backups
   - No max backup limit

---

## Required Fixes (Priority Order)

### P0 - Critical Blockers

1. **Fix fastmcp imports**:
   - Remove invalid imports: `claude_code, claude_desktop, cursor, gemini_cli, mcp_json`
   - Remove unused `client_modules` dict
   - Find correct way to reference these clients (if needed)

2. **Implement or remove config wizard**:
   - Either implement `init()` function in `config.py`
   - OR remove the call and implement inline config creation
   - OR document that config must be created manually first

### P1 - High Priority

3. **Implement quick mode**:
   - Actually use the `--quick` flag
   - Provide sensible defaults without prompting

4. **Add validation**:
   - Check server connectivity for streamable-http
   - Validate command existence for stdio
   - Verify directory permissions before writing

### P2 - Medium Priority

5. **Clean up unused code**:
   - Remove unused `interactive` parameter
   - Use backup path or remove the return value
   - Remove dead code paths

---

## Testing Prerequisites

Before ANY testing can proceed:

1. ✅ Fix `fastmcp` import errors
2. ✅ Implement or remove config wizard call
3. ✅ Verify command can be imported: `from codeweaver.cli.commands.init import app`
4. ✅ Verify command shows help: `uv run codeweaver init --help`

---

## Dependencies Analysis

### Required Python Packages
- ✅ cyclopts - Present (CLI framework)
- ✅ httpx - Present (HTTP client)
- ✅ fastmcp - Present (but wrong imports used)
- ✅ pydantic-core - Present (JSON handling)
- ✅ rich - Present (console output)
- ❓ pyperclip - Optional (for --output copy)

### Internal Dependencies
- ✅ `codeweaver.common.utils.utils.get_user_config_dir`
- ❌ `codeweaver.cli.commands.config.init` - DOES NOT EXIST
- ✅ `codeweaver.config.mcp` - Models exist
- ✅ `codeweaver.config.settings` - Functions exist

---

## Recommendations

### Immediate Actions

1. **Remove invalid imports**: The fastmcp modules don't exist
2. **Implement config creation**: Either:
   - Add `init()` function to `config.py` that creates `.codeweaver.toml`
   - OR implement inline in `init.py` using `pydantic-settings`
   - OR use a template file approach

### Design Improvements

1. **Split responsibilities**:
   - `init config` should handle `.codeweaver.toml` creation only
   - `init mcp` should handle MCP client configs only
   - Default `init` calls both in sequence

2. **Add validation**:
   - Test server connectivity before writing config
   - Verify command availability for stdio
   - Check write permissions

3. **Improve UX**:
   - Show actual config being written
   - Provide examples for manual editing
   - Add `--dry-run` flag to preview without writing

### Documentation Needs

1. Create examples directory with sample configs
2. Document all client types and their requirements
3. Provide troubleshooting guide
4. Add architecture notes explaining HTTP vs stdio choice

---

## Appendix: Error Output

```bash
$ uv run codeweaver init --help
[2mBytecode compiled [1m22924 files[0m [2min 2.50s[0m[0m

[1;38;5;208mCodeWeaver[0m [31mFatal error: Cannot import module [0m[31m'codeweaver.cli.commands.init'[0m[31m from[0m
[31m'codeweaver.cli.commands.init:app'[0m
```

```python
$ uv run python -c "from codeweaver.cli.commands.init import app"
Traceback (most recent call last):
  File "<string>", line 1, in <module>
    from codeweaver.cli.commands.init import app; print(app)
    ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^
  File "/home/knitli/codeweaver-mcp/src/codeweaver/cli/commands/init.py", line 24, in <module>
    from fastmcp import claude_code, claude_desktop, cursor, gemini_cli, mcp_json
ImportError: cannot import name 'claude_code' from 'fastmcp'
```

---

## Test Status Summary

| Category | Planned | Executed | Passed | Failed | Blocked |
|----------|---------|----------|--------|--------|---------|
| Help Commands | 3 | 0 | 0 | 0 | 3 |
| Default Behavior | 3 | 0 | 0 | 0 | 3 |
| Flag Variations | 4 | 0 | 0 | 0 | 4 |
| Client Variations | 6 | 0 | 0 | 0 | 6 |
| Transport Variations | 2 | 0 | 0 | 0 | 2 |
| Config Level | 2 | 0 | 0 | 0 | 2 |
| Subcommands | 3 | 0 | 0 | 0 | 3 |
| **TOTAL** | **23** | **0** | **0** | **0** | **23** |

**Coverage**: 0% (cannot execute any tests)
**Blocker Rate**: 100% (all tests blocked by import errors)

---

## Next Steps

1. **Developer**: Fix the two critical import errors
2. **QA**: Re-run this test suite once imports are fixed
3. **Developer**: Address validation and UX issues
4. **QA**: Perform full integration testing with actual MCP clients
