---
name: scattered-temp-files
enabled: true
event: file
conditions:
  - field: file_path
    operator: regex_match
    pattern: ^(?!.*(?:scripts/|tools/|bin/|tests/|\.claude/)).*(?:debug\.sh|test_.*\.py|utility\.js|temp.*\.(py|js|sh)|script\.(py|js|sh))$
---

⚠️ **Temporary file in wrong location**

You're creating a temporary file that should be organized in a proper directory.

**Workspace hygiene rule**: Temporary files, scripts, and utilities should be placed in specific directories:
- **Scripts**: `scripts/`, `tools/`, or `bin/` directories
- **Tests**: `tests/`, `__tests__/`, or `test/` directories
- **Analysis/Reports**: `claudedocs/` directory
- **Config/Local**: `.claude/` directory

**Examples of organized locations:**
- ✅ `scripts/deploy.sh` (not `deploy.sh` in root)
- ✅ `tests/auth.test.js` (not `auth.test.js` next to source)
- ✅ `claudedocs/analysis.md` (not random markdown files)
- ❌ `debug.sh` in project root
- ❌ `test_*.py` scattered throughout codebase
- ❌ `temp_script.js` in random location

**Please relocate or reorganize this file to the appropriate directory.**
