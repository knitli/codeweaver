# Fix Proposal: `codeweaver init` Command

**Target**: Make the command minimally functional
**Priority**: P0 Critical Blocker
**Estimated Effort**: 2-4 hours

---

## Problem Statement

The `codeweaver init` command has two critical import errors that prevent it from executing at all:

1. **Invalid fastmcp imports**: Attempting to import non-existent modules
2. **Missing config wizard**: Calling a function that doesn't exist

---

## Minimal Fix: Remove Unused Code

### Fix 1: Remove Invalid fastmcp Imports

**File**: `src/codeweaver/cli/commands/init.py`

**Lines to remove**: 24, 37-43

```python
# REMOVE these lines:
from fastmcp import claude_code, claude_desktop, cursor, gemini_cli, mcp_json

client_modules = {
    "claude_code": claude_code,
    "claude_desktop": claude_desktop,
    "cursor": cursor,
    "mcpjson": mcp_json,
    "gemini_cli": gemini_cli,
}
```

**Justification**:
- These imports are never used in the code
- The `client_modules` dict is never referenced
- The modules don't exist in fastmcp anyway

**Risk**: None - dead code removal

---

### Fix 2: Implement Config Creation (Option A - Simplest)

**File**: `src/codeweaver/cli/commands/init.py`

**Replace function**: `_create_codeweaver_config()` (lines 72-96)

```python
def _create_codeweaver_config(project_path: Path, *, quick: bool = False) -> Path:
    """Create CodeWeaver configuration file.

    Args:
        project_path: Path to project directory
        quick: Use recommended defaults without prompting

    Returns:
        Path to created configuration file
    """
    from codeweaver.config.settings import CodeWeaverSettings

    config_path = project_path / ".codeweaver.toml"

    # Create default settings
    settings = CodeWeaverSettings(project_path=project_path)

    # Write to TOML file
    import tomli_w
    config_path.write_text(
        tomli_w.dumps(settings.model_dump(exclude_none=True, mode='json')),
        encoding='utf-8'
    )

    return config_path
```

**Required dependency check**:
```bash
# Check if tomli-w is available
uv run python -c "import tomli_w"
```

If not available, add to pyproject.toml or use alternative:

**Alternative: JSON format** (if TOML writer not available):
```python
def _create_codeweaver_config(project_path: Path, *, quick: bool = False) -> Path:
    """Create CodeWeaver configuration file.

    Args:
        project_path: Path to project directory
        quick: Use recommended defaults without prompting

    Returns:
        Path to created configuration file
    """
    from codeweaver.config.settings import CodeWeaverSettings
    import json

    config_path = project_path / ".codeweaver.json"

    # Create default settings
    settings = CodeWeaverSettings(project_path=project_path)

    # Write to JSON file
    config_path.write_text(
        json.dumps(settings.model_dump(exclude_none=True, mode='json'), indent=2),
        encoding='utf-8'
    )

    return config_path
```

**Justification**:
- Simplest working implementation
- Uses existing settings models
- No external wizard needed
- Can be enhanced later

**Risk**: Low - straightforward implementation

---

### Fix 3: Remove Unused Parameters

**File**: `src/codeweaver/cli/commands/init.py`

**Line 103**: Remove unused `interactive` parameter

```python
# BEFORE
def config(
    *,
    project: Annotated[Path | None, cyclopts.Parameter(name=["--project", "-p"])] = None,
    interactive: Annotated[bool, cyclopts.Parameter(name=["--interactive", "-i"])] = True,  # UNUSED
    quick: Annotated[bool, cyclopts.Parameter(name=["--quick", "-q"])] = False,
    force: Annotated[bool, cyclopts.Parameter(name=["--force", "-f"])] = False,
) -> None:

# AFTER
def config(
    *,
    project: Annotated[Path | None, cyclopts.Parameter(name=["--project", "-p"])] = None,
    quick: Annotated[bool, cyclopts.Parameter(name=["--quick", "-q"])] = False,
    force: Annotated[bool, cyclopts.Parameter(name=["--force", "-f"])] = False,
) -> None:
```

**Justification**: Parameter is never used, removes confusion

**Risk**: None - parameter not used anywhere

---

## Testing After Fix

### Verification Steps

1. **Import test**:
```bash
uv run python -c "from codeweaver.cli.commands.init import app; print('SUCCESS')"
```

2. **Help test**:
```bash
uv run codeweaver init --help
```

3. **Config-only test**:
```bash
cd /tmp/test-project
uv run codeweaver init --config-only
ls -la .codeweaver.*  # Should show config file
```

4. **MCP-only test**:
```bash
cd /tmp/test-project
uv run codeweaver init --mcp-only --client mcpjson
ls -la .mcp.json  # Should show MCP config
cat .mcp.json  # Should show valid JSON
```

5. **Full init test**:
```bash
cd /tmp/test-project
uv run codeweaver init --quick --client claude_code
ls -la .codeweaver.* .claude/mcp.json
```

### Expected Results

- ✅ All imports succeed
- ✅ Help text displays
- ✅ Config file created with valid structure
- ✅ MCP config created at correct location
- ✅ No errors or exceptions

---

## Complete Patch

Here's the complete minimal fix as a unified diff:

```diff
--- a/src/codeweaver/cli/commands/init.py
+++ b/src/codeweaver/cli/commands/init.py
@@ -21,22 +21,6 @@ from typing import TYPE_CHECKING, Annotated, Any, Literal
 import cyclopts
 import httpx

-from fastmcp import claude_code, claude_desktop, cursor, gemini_cli, mcp_json
 from pydantic_core import from_json as from_json
 from pydantic_core import to_json as to_json
 from rich.console import Console
@@ -36,13 +20,6 @@ if TYPE_CHECKING:
     from codeweaver.config.mcp import CodeWeaverMCPConfig, StdioCodeWeaverConfig


-client_modules = {
-    "claude_code": claude_code,
-    "claude_desktop": claude_desktop,
-    "cursor": cursor,
-    "mcpjson": mcp_json,
-    "gemini_cli": gemini_cli,
-}
-
 console = Console(markup=True, emoji=True)

 # Create cyclopts app at module level
@@ -79,18 +56,18 @@ def _create_codeweaver_config(project_path: Path, *, quick: bool = False) -> Pa
     Returns:
         Path to created configuration file
     """
-    from codeweaver.cli.commands.config import init as config_init_wizard
+    from codeweaver.config.settings import CodeWeaverSettings
+    import json

-    # Use existing config wizard
-    config_path = project_path / ".codeweaver.toml"
+    config_path = project_path / ".codeweaver.json"

-    if quick:
-        # Use recommended default profile
-        console.print("[cyan]Creating configuration with recommended defaults...[/cyan]")
-        # For quick mode, we'll use the config wizard with default answers
-        # This will be implemented by the config wizard's quick mode
+    # Create default settings
+    settings = CodeWeaverSettings(project_path=project_path)

-    # Call the existing config wizard
-    config_init_wizard(output=config_path, force=False)
+    # Write to JSON file
+    config_path.write_text(
+        json.dumps(settings.model_dump(exclude_none=True, mode='json'), indent=2),
+        encoding='utf-8'
+    )

     return config_path

@@ -101,7 +78,6 @@ def config(
     *,
     project: Annotated[Path | None, cyclopts.Parameter(name=["--project", "-p"])] = None,
-    interactive: Annotated[bool, cyclopts.Parameter(name=["--interactive", "-i"])] = True,
     quick: Annotated[bool, cyclopts.Parameter(name=["--quick", "-q"])] = False,
     force: Annotated[bool, cyclopts.Parameter(name=["--force", "-f"])] = False,
 ) -> None:
```

---

## Implementation Order

1. **Remove fastmcp imports** (30 seconds)
   - Delete line 24
   - Delete lines 37-43

2. **Replace config creation** (5 minutes)
   - Replace `_create_codeweaver_config()` function
   - Test import: `from codeweaver.config.settings import CodeWeaverSettings`

3. **Remove unused parameter** (30 seconds)
   - Delete `interactive` parameter from `config()` function

4. **Test** (10 minutes)
   - Run verification steps
   - Create test project
   - Verify files created

**Total time**: ~20 minutes

---

## Future Enhancements (Not in Minimal Fix)

### P1 - High Priority
- Add interactive prompts for config values
- Implement proper TOML support (if tomli-w available)
- Add validation before writing configs
- Add `--dry-run` flag

### P2 - Medium Priority
- Add config templates/profiles
- Implement quick mode properly
- Add server connectivity check for HTTP transport
- Better error messages

### P3 - Low Priority
- Add examples directory
- Interactive config wizard with rich prompts
- Config migration utilities
- Backup management

---

## Dependencies Verification

Check if these are available before implementing:

```bash
# Required for settings
uv run python -c "from codeweaver.config.settings import CodeWeaverSettings; print('OK')"

# Optional for TOML (if preferred over JSON)
uv run python -c "import tomli_w; print('OK')" 2>/dev/null || echo "Not available - use JSON"

# Required for JSON (always available)
uv run python -c "import json; print('OK')"
```

If `CodeWeaverSettings` doesn't work, check what's available:
```bash
uv run python -c "from codeweaver import config; print(dir(config))"
```

---

## Risk Assessment

**Risk Level**: Low

**Potential Issues**:
- CodeWeaverSettings may need additional parameters
- JSON format might not be preferred over TOML
- Default settings might not be suitable for all projects

**Mitigation**:
- Test with actual settings import first
- Verify settings.model_dump() produces valid output
- Keep fix minimal - don't add features
- Add TODO comments for future enhancements

**Rollback Plan**:
- Git revert if issues found
- Original code is non-functional anyway
- No risk of regression

---

## Success Criteria

✅ Command can be imported without errors
✅ `--help` displays correctly
✅ Config file is created with valid structure
✅ MCP config is created at correct location
✅ All client types work (claude_code, cursor, vscode, etc.)
✅ Both transport types work (stdio, streamable-http)
✅ No exceptions during execution

---

## Validation Checklist

After implementing fixes:

- [ ] Code imports successfully
- [ ] Help text displays
- [ ] Config creation works
- [ ] MCP config creation works
- [ ] All client types supported
- [ ] Both transports work
- [ ] Files created in correct locations
- [ ] JSON/TOML format is valid
- [ ] No exceptions or crashes
- [ ] Backup logic works
- [ ] Error handling works
