<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Alpha Release Setup - Complete

## Overview

CodeWeaver is now **ready for alpha release** (v0.1.0-alpha.1). Your infrastructure is configured to support semantic versioning with pre-release tags.

## What's Been Set Up

### ✅ Version Management
- **Tool**: `uv-dynamic-versioning` (already configured in `pyproject.toml`)
- **Style**: SemVer with pre-release support
- **Format**: Git tag `v0.1.0-alpha.1` → PyPI version `0.1.0a1` (PEP 440 normalized)
- **Documentation**: Updated in `docs/versioning.md`

### ✅ GitHub Actions Workflows
- **`publish.yml`**: Triggers on any `v*` tag, publishes to PyPI
- **`release.yml`**: Creates GitHub releases, automatically marks alpha/beta as "pre-release"
- **Fixed**: Dynamic versioning check (was incorrectly checking `pyproject.toml`)

### ✅ Documentation Updates
- **`docs/versioning.md`**: Added alpha/beta/rc sections
- **`README.md`**: Updated with alpha status warning and PyPI install instructions
- **`RELEASE_CHECKLIST.md`**: Created comprehensive release checklist

### ✅ PyPI Pre-Release Handling
- Alpha versions require `--pre` flag: `pip install --pre codeweaver`
- Protects users from accidentally installing unstable versions
- Explicit opt-in for early testers

## Release Process

### Quick Start (When Ready to Release)

```bash
# 1. Commit all changes
git add -A
git commit -m "chore: prepare for v0.1.0-alpha.1 release"

# 2. Create alpha tag
git tag v0.1.0-alpha.1

# 3. Test locally
uv build
ls dist/  # Should show: codeweaver_mcp-0.1.0a1-py3-none-any.whl

# 4. Push (triggers GitHub Actions)
git push origin HEAD
git push origin v0.1.0-alpha.1
```

### What Happens Automatically

1. **GitHub Actions runs** (triggered by tag push):
   - **Tests** on Python 3.12, 3.13, 3.14 with full test suite
   - **Builds** wheel and source distribution once
   - **Creates GitHub release** marked as "pre-release" for alpha/beta
   - **Publishes to PyPI** via trusted publisher (OIDC)

2. **PyPI receives**:
   - Version: `0.1.0a1` (normalized from `0.1.0-alpha.1`)
   - Users must use `--pre` flag to install
   - Visible at: https://pypi.org/project/codeweaver/

3. **GitHub release**:
   - Automatically marked as "pre-release" ✅
   - Includes build artifacts
   - Auto-generated changelog

## Version Progression

```
Current State:    No tags (defaults to 0.0.1rc532+g92179dc1.dirty)
                       ↓
Alpha Release:    v0.1.0-alpha.1  →  PyPI: 0.1.0a1
                       ↓
Bug Fixes:        v0.1.0-alpha.2  →  PyPI: 0.1.0a2
                       ↓
Beta Release:     v0.1.0-beta.1   →  PyPI: 0.1.0b1
                       ↓
Release Candidate: v0.1.0-rc.1    →  PyPI: 0.1.0rc1
                       ↓
Stable Release:   v0.1.0          →  PyPI: 0.1.0
```

## Why Alpha is Right for CodeWeaver

### Your Assessment
> "Unusually robust infrastructure for an initial release -- support for 20+ providers... but it's not heavily tested, and fragile."

### Alpha Signals
- ✅ Feature-complete but not battle-tested (your exact situation)
- ✅ Robust architecture (20+ providers, weighted intent strategies)
- ✅ Clear error messages and guides (unusual for alpha - a strength!)
- ✅ Sets appropriate expectations for early testers

### User Experience
**Positive Surprise**: "Wow, this alpha has better error messages than most 1.0 releases!"
vs.
**Disappointment**: "This 0.1 release is pretty rough..."

Alpha tag = appropriate expectations + positive surprises

## Pre-Release Best Practices

### Communication
- ✅ README clearly states alpha status
- ✅ Installation requires explicit `--pre` flag
- ✅ GitHub releases automatically marked "pre-release"

### User Protection
- Alpha versions don't auto-install for unsuspecting users
- Explicit opt-in required: `pip install --pre codeweaver`
- Clear warnings in documentation

### Iteration Speed
- Can release `alpha.2`, `alpha.3` as needed
- No stigma of "unstable 0.1.x releases"
- Clear progression to beta/stable

## Testing Before Release

Run through the checklist in `RELEASE_CHECKLIST.md`:

```bash
# Quick validation
mise run test        # All tests pass?
mise run lint        # No critical issues?
mise run type-check  # Types valid?

# End-to-end test
codeweaver init      # Does first-run work?
codeweaver --help    # Is CLI clear?
```

## Post-Release Monitoring

### First 48 Hours
- Watch GitHub Issues for bug reports
- Monitor PyPI download stats
- Check for install failures

### First 2 Weeks
- Collect feedback on rough edges
- Document known issues
- Plan alpha.2 if needed

### Path to Beta (2-4 weeks)
- Address critical bugs from alpha testing
- Validate core functionality with real users
- Update docs based on feedback
- Tag `v0.1.0-beta.1` when ready

## Rollback Plan

If critical issues discovered after release:

1. **Yank from PyPI** (makes unavailable for new installs)
   - Use PyPI web interface: Project Settings → Manage → Yank
   - Doesn't affect already-installed versions

2. **Document issue** in GitHub

3. **Fix and release** `v0.1.0-alpha.2`

## Key Files Modified

- ✅ `docs/versioning.md` - Added alpha/beta sections
- ✅ `README.md` - Alpha warning + PyPI install instructions
- ✅ `.github/workflows/release.yml` - Fixed dynamic version check
- ✅ `RELEASE_CHECKLIST.md` - New comprehensive checklist
- ✅ `ALPHA_RELEASE_SUMMARY.md` - This document

## Questions?

- **Q: Can I release alpha from a feature branch?**
  - A: Yes! Your config allows building on any branch. But consider merging to main first for consistency.

- **Q: What if I want to test PyPI upload first?**
  - A: Use TestPyPI workflow (`.github/workflows/publish-test.yml`)

- **Q: How do I move from alpha to beta?**
  - A: Just tag `v0.1.0-beta.1` when ready. The workflow handles it automatically.

- **Q: Can I skip beta and go straight to stable?**
  - A: Yes! Tag `v0.1.0` when ready. But beta gives you another feedback cycle.

## Ready to Release?

Follow the checklist in `RELEASE_CHECKLIST.md` and run:

```bash
git tag v0.1.0-alpha.1
git push origin v0.1.0-alpha.1
```

That's it! The automation handles the rest. 🚀
