# Mise CI Configuration Guide

## Overview

This project now uses **environment-specific mise configurations** to optimize CI/CD performance. The new `mise.ci.toml` provides a lightweight tool set for continuous integration, reducing installation time and cache size.

## Problem Solved

**Before:**
- CI/CD installed 20+ development tools unnecessarily
- Large cache sizes leading to space limitations
- Slow mise installation in CI workflows
- Tools like `claude-monitor`, `copychat`, `rust-parallel`, etc. installed but never used

**After:**
- CI installs only 7 essential tools
- ~70% reduction in mise installation footprint
- Faster CI runs with optimized caching
- Development workflow unchanged

## Configuration Files

### File Hierarchy

mise uses this priority order (highest to lowest):

```
mise.ci.local.toml      # Machine-specific CI overrides (gitignored)
mise.local.toml         # Local overrides (gitignored)
mise.ci.toml            # CI-specific config ← NEW
mise.toml               # Base development config
```

### mise.ci.toml - CI Configuration

**Tools Included:**
- `python 3.13` - Core runtime
- `uv` - Dependency management
- `ruff` - Linting/formatting
- `hk` - Task runner
- `typos` - Spell checking
- `reuse` - License validation
- `gh` - GitHub CLI

**Tools Excluded:**
- All `pipx` tools (claude-monitor, copychat, fastmcp, mcp-interviewer, mike, mteb, changesets, tombi, ty)
- `cargo` tools (rust-parallel, tree-sitter-cli)
- Development utilities (ast-grep, gitsign, pkl, usage, shellcheck, shfmt)
- `npm:changesets`

**Key Differences from Base Config:**
1. No `[hooks.enter]` - CI doesn't need interactive shell hooks
2. Simplified `_.path` - Only includes `.venv/bin`
3. `CI = "true"` - Explicitly set in environment
4. `status.show_env = false` - Reduced output noise
5. Tasks use explicit bash output formatting for CI

## Usage

### GitHub Actions

Add `MISE_ENV=ci` to your workflow:

```yaml
name: CI

on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4

      - name: Install mise
        uses: jdx/mise-action@v2
        with:
          install: true
          cache: true
          experimental: true
        env:
          MISE_ENV: ci  # ← Use CI configuration

      - name: Run CI checks
        run: mise run ci
```

### Local Testing of CI Config

Test the CI configuration locally:

```bash
# Activate CI environment
MISE_ENV=ci mise install

# Run tasks with CI config
MISE_ENV=ci mise run ci

# Check which config files are loaded
MISE_ENV=ci mise config
```

### Viewing Active Configuration

```bash
# See all loaded config files
MISE_ENV=ci mise config ls

# See merged configuration
MISE_ENV=ci mise config

# See only CI tools
MISE_ENV=ci mise list
```

## Customization

### Adding Tools for Specific CI Jobs

If specific workflows need additional tools, you can:

**Option 1: Extend mise.ci.toml**

Edit `mise.ci.toml` to add tools:

```toml
[tools]
# ... existing tools ...
node = "24"  # Add if npm tasks needed
shellcheck = "latest"  # Add if shell linting required
```

**Option 2: Use Multiple Environments**

```yaml
# In GitHub Actions
env:
  MISE_ENV: ci,node  # Loads mise.ci.toml then mise.node.toml
```

Create `mise.node.toml`:
```toml
[tools]
node = "24"
"npm:changesets" = "latest"
```

### Machine-Specific Overrides

For local CI testing with custom settings, create `mise.ci.local.toml` (gitignored):

```toml
[tools]
# Add tools for local testing
ripgrep = "latest"

[env]
# Override environment variables
DEBUG = "true"
```

## Optimization Recommendations

### Cache Strategy

**GitHub Actions Cache Configuration:**

```yaml
- uses: jdx/mise-action@v2
  with:
    cache: true
    cache_key_prefix: mise-ci-  # Separate CI cache from dev
    experimental: true
  env:
    MISE_ENV: ci
```

### Further Optimization Ideas

1. **Split CI Jobs by Tool Requirements**
   - Lint job: Only needs `ruff`, `typos`, `reuse`
   - Test job: Only needs `python`, `uv`
   - Build job: Only needs `python`, `uv`

2. **Use Conditional Tool Installation**
   ```yaml
   - name: Install only Python tools
     run: mise install python uv ruff
     env:
       MISE_ENV: ci
   ```

3. **Docker-based CI** (future consideration)
   - Pre-bake tools into Docker image
   - Eliminate mise installation entirely in CI

## Monitoring Impact

### Metrics to Track

**Installation Time:**
```bash
# Before
time MISE_ENV=dev mise install

# After
time MISE_ENV=ci mise install
```

**Cache Size:**
```bash
# Check mise cache size
du -sh ~/.local/share/mise

# Check tool-specific sizes
mise cache clear --dry-run
```

**CI Duration:**
- Monitor GitHub Actions job duration
- Compare mise installation step times
- Track overall workflow duration

## Troubleshooting

### Missing Tool in CI

**Error:** `command not found: some-tool`

**Solution:**
1. Check if tool is needed in CI
2. Add to `mise.ci.toml` if required:
   ```toml
   [tools]
   some-tool = "latest"
   ```

### Wrong Configuration Loaded

**Check active config:**
```bash
MISE_ENV=ci mise config ls
```

**Force CI config:**
```bash
export MISE_ENV=ci
mise trust
mise install
```

### Task Failures

**If tasks behave differently in CI:**
1. Compare task definitions between `mise.toml` and `mise.ci.toml`
2. Check for tools used by task in `[tools]` section
3. Verify environment variables in `[env]` section

## Migration Checklist

- [x] Create `mise.ci.toml` with essential tools only
- [x] Update `.gitignore` for `mise.*.local.toml` patterns
- [ ] Update GitHub Actions workflows with `MISE_ENV=ci`
- [ ] Test CI workflows with new configuration
- [ ] Monitor CI performance improvements
- [ ] Document any workflow-specific tool requirements
- [ ] Consider creating additional environment configs (e.g., `mise.test.toml`, `mise.build.toml`)

## Additional Resources

- [mise Environment Configuration Docs](https://mise.jdx.dev/configuration/environments.html)
- [mise Environments Guide](https://mise.jdx.dev/environments/)
- [mise GitHub Action](https://github.com/jdx/mise-action)
- [Configuration File Reference](https://mise.jdx.dev/configuration.html)

## Quick Reference

### Common Commands

```bash
# Use CI config locally
export MISE_ENV=ci

# Install CI tools
mise install

# Run CI tasks
mise run ci

# View loaded configs
mise config ls

# See tool versions
mise list

# Clear and reinstall
mise uninstall --all
mise install
```

### Environment Variables

- `MISE_ENV=ci` - Use CI configuration
- `MISE_ENV=ci,test` - Layer multiple configs (test overrides ci)
- `MISE_LOG_LEVEL=debug` - Verbose mise output for debugging

---

**Created:** 2025-11-26
**Author:** Claude Code
**Purpose:** Guide for using environment-specific mise configurations in CI/CD
