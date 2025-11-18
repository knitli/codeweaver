<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Quickstart: PyPI Build and Publishing System

**Purpose**: End-to-end validation guide for verifying the build and publishing system works correctly

**Audience**: Developers, CI/CD systems, QA testers

**Prerequisites**:
- Python 3.12+ installed
- uv package manager installed
- Git repository initialized
- GitHub Actions configured (for publishing)

---

## Local Development Flow

### 1. Build Package Locally

**Goal**: Create distributable packages (wheel + sdist) from current repository state

```bash
# Clean previous builds
rm -rf dist/

# Build packages
uv build

# Expected output:
# Building wheel...
# Built codeweaver_mcp-{version}-py3-none-any.whl
# Building source distribution...
# Built codeweaver_mcp-{version}.tar.gz
```

**Validation**:
```bash
# Verify artifacts created
ls dist/

# Expected: 2 files
# codeweaver_mcp-{version}-py3-none-any.whl
# codeweaver_mcp-{version}.tar.gz

# Check version derived correctly
# For untagged commits: should be pre-release (e.g., 0.1.0rc295+gfc4f90a)
# For tagged commits: should be release version (e.g., 0.1.0)
```

**Success Criteria**:
- ✅ `dist/` contains exactly 2 files (wheel + sdist)
- ✅ Filenames include correct package name (`codeweaver_mcp`)
- ✅ Version follows PEP 440 format
- ✅ Build completes in reasonable time (<30 seconds)

---

### 2. Validate Package Metadata

**Goal**: Verify package metadata is complete and correct before publishing

```bash
# Install validation tool (if not already available)
uv pip install twine

# Validate metadata
twine check dist/*

# Expected output:
# Checking dist/codeweaver_mcp-{version}-py3-none-any.whl: PASSED
# Checking dist/codeweaver_mcp-{version}.tar.gz: PASSED
```

**Success Criteria**:
- ✅ Both artifacts pass validation
- ✅ No metadata warnings or errors
- ✅ README renders correctly as long description

---

### 3. Test Package Installation

**Goal**: Verify package installs correctly and is importable

```bash
# Create clean test environment
python -m venv /tmp/test-codeweaver
source /tmp/test-codeweaver/bin/activate

# Install from local build
pip install dist/codeweaver_mcp-*.whl

# Verify importable
python -c "import codeweaver; print(codeweaver.__version__)"

# Expected output:
# {version} (should match wheel version)

# Clean up
deactivate
rm -rf /tmp/test-codeweaver
```

**Success Criteria**:
- ✅ Package installs without errors
- ✅ Import succeeds
- ✅ Version matches built version
- ✅ No missing dependencies

---

## Publishing Flow (Manual Testing)

### 4. Publish to TestPyPI (Dry Run)

**Goal**: Test full publishing workflow without affecting production PyPI

**Prerequisites**:
- TestPyPI account created
- GitHub Actions trusted publisher configured for TestPyPI

```bash
# Trigger TestPyPI publish workflow (assuming manual trigger configured)
# Via GitHub Actions UI or gh CLI:
gh workflow run publish-test.yml

# Or manually using twine (if GitHub Actions not available):
# twine upload --repository testpypi dist/*
```

**Validation**:
```bash
# Visit TestPyPI package page
# https://test.pypi.org/project/codeweaver/{version}/

# Verify metadata displayed correctly:
# - Package name: codeweaver
# - Description matches README
# - License: MIT OR Apache-2.0
# - Supported Python versions: 3.12, 3.13, 3.14
# - Keywords and classifiers present

# Test installation from TestPyPI
python -m venv /tmp/test-testpypi
source /tmp/test-testpypi/bin/activate

pip install --index-url https://test.pypi.org/simple/ \
            --extra-index-url https://pypi.org/simple/ \
            codeweaver=={version}

python -c "import codeweaver; print(codeweaver.__version__)"

# Clean up
deactivate
rm -rf /tmp/test-testpypi
```

**Success Criteria**:
- ✅ Package published successfully to TestPyPI
- ✅ Package page displays correct metadata
- ✅ Installation from TestPyPI succeeds
- ✅ All dependencies resolve correctly

---

### 5. Publish to Production PyPI (Tagged Release)

**Goal**: Publish official release to production PyPI

**Prerequisites**:
- All tests passing on CI (Python 3.12, 3.13, 3.14)
- Version tag created (e.g., `v0.1.0`)
- GitHub Actions trusted publisher configured for PyPI

```bash
# Create and push version tag
git tag v0.1.0
git push origin v0.1.0

# GitHub Actions workflow automatically triggered by tag push
# Monitor workflow: https://github.com/{org}/codeweaver/actions
```

**Validation**:
```bash
# Verify workflow completed successfully
gh run list --workflow=publish.yml --limit=1

# Visit PyPI package page
# https://pypi.org/project/codeweaver/0.1.0/

# Test installation from PyPI
python -m venv /tmp/test-pypi
source /tmp/test-pypi/bin/activate

pip install codeweaver==0.1.0

python -c "import codeweaver; print(codeweaver.__version__)"

# Run smoke tests
python -m pytest tests/smoke/

# Clean up
deactivate
rm -rf /tmp/test-pypi
```

**Success Criteria**:
- ✅ GitHub Actions workflow succeeds
- ✅ Package published to PyPI
- ✅ Package installable via `pip install codeweaver`
- ✅ Smoke tests pass
- ✅ Version matches tag (e.g., `0.1.0`)

---

## Version Management Scenarios

### Scenario A: Untagged Commit (Pre-Release Version)

**Context**: Working on feature branch, no version tag

```bash
# Current state:
git log --oneline -1
# fc4f90a feat: Add new feature

git tag --list 'v*' | tail -1
# v0.0.1

git rev-list v0.0.1..HEAD --count
# 295

# Build from this state
uv build

# Check generated version
ls dist/
# codeweaver_mcp-0.0.1rc295+gfc4f90a-py3-none-any.whl
# codeweaver_mcp-0.0.1rc295+gfc4f90a.tar.gz

# Version format: {last_tag}rc{commits_since_tag}+g{commit_hash}
```

**Expected**: Pre-release version `0.0.1rc295+gfc4f90a`

---

### Scenario B: Tagged Commit (Release Version)

**Context**: Creating official release

```bash
# Create release tag
git tag v0.1.0
git log --oneline -1
# fc4f90a (tag: v0.1.0) release: Version 0.1.0

# Build from tagged commit
uv build

# Check generated version
ls dist/
# codeweaver_mcp-0.1.0-py3-none-any.whl
# codeweaver_mcp-0.1.0.tar.gz

# Version format: {tag_version} (clean semantic version)
```

**Expected**: Release version `0.1.0`

---

### Scenario C: Dirty Working Directory

**Context**: Uncommitted changes in working directory

```bash
# Make uncommitted change
echo "# test" >> README.md

# Build with dirty state
uv build

# Check generated version
ls dist/
# codeweaver_mcp-0.0.1rc295+gfc4f90a.dirty-py3-none-any.whl
# codeweaver_mcp-0.0.1rc295+gfc4f90a.dirty.tar.gz

# Version format: appends .dirty suffix
```

**Expected**: Version includes `.dirty` suffix
**Warning**: Publishing dirty builds should be prevented by CI

---

## Troubleshooting Guide

### Issue: Build Fails with "Metadata Error"

**Symptoms**:
```
ERROR: Required metadata field missing: {field}
```

**Resolution**:
```bash
# Verify pyproject.toml [project] table
cat pyproject.toml | grep -A 20 "\[project\]"

# Ensure all required fields present:
# - name
# - version (should be "dynamic")
# - description
# - readme
# - requires-python
# - license
# - authors
```

---

### Issue: Version Not Derived Correctly

**Symptoms**: Version is `0.0.0` or missing

**Resolution**:
```bash
# Verify git tags exist
git tag --list 'v*'

# If no tags, create initial tag
git tag v0.0.1
git push origin v0.0.1

# Verify uv-versioning plugin installed
uv pip list | grep uv-versioning

# Check uv-versioning configuration
cat pyproject.toml | grep -A 5 "\[tool.hatch.version\]"
```

---

### Issue: twine check Fails

**Symptoms**:
```
ERROR: Long description rendering failed
```

**Resolution**:
```bash
# Verify README.md is valid Markdown
# Check for syntax errors, broken links, invalid tables

# Test README rendering locally
pip install readme-renderer
python -m readme_renderer README.md
```

---

### Issue: PyPI Upload Fails with "Version Already Exists"

**Symptoms**:
```
ERROR: Version {version} already exists on PyPI
```

**Resolution**:
```
PyPI version numbers are immutable. Cannot delete or overwrite.

Actions:
1. Increment version number (create new git tag)
2. For pre-releases: add commit to generate new version
3. For releases: create new tag (e.g., v0.1.1)
```

---

### Issue: GitHub Actions OAuth Authentication Fails

**Symptoms**:
```
ERROR: Trusted publisher authentication failed
```

**Resolution**:
```bash
# Verify trusted publisher configured at:
# https://pypi.org/manage/account/publishing/

# Check GitHub Actions workflow permissions
cat .github/workflows/publish.yml | grep -A 5 "permissions:"

# Must include:
# permissions:
#   id-token: write
#   contents: read
```

---

## Success Metrics

### Build Performance
- ✅ Build completes in <30 seconds (pure Python package)
- ✅ Artifacts are <10 MB each (reasonable package size)

### Validation Coverage
- ✅ Metadata validation passes (`twine check`)
- ✅ Package installable on Python 3.12, 3.13, 3.14
- ✅ Import succeeds, version correct
- ✅ Smoke tests pass

### Publishing Reliability
- ✅ TestPyPI publishing succeeds (dry run)
- ✅ Production PyPI publishing succeeds (tagged releases)
- ✅ No manual intervention required for CI/CD
- ✅ Clear error messages for failures

### Version Management
- ✅ Pre-release versions generated correctly for untagged commits
- ✅ Release versions match git tags
- ✅ Version increments coordinate with changeset workflow

---

## Next Steps After Quickstart

Once this quickstart validates successfully:

1. **Automate in CI**: Integrate build and publish into GitHub Actions workflow
2. **Add Smoke Tests**: Create `tests/smoke/` directory with installation validation tests
3. **Monitor Performance**: Track build times, identify optimization opportunities if needed
4. **Document for Users**: Update README.md with installation instructions
5. **Coordinate with Changesets**: Document version bump workflow with changesets

---

**Validation Checklist**:

- [ ] Local build succeeds
- [ ] Metadata validation passes
- [ ] Local installation works
- [ ] TestPyPI publish succeeds
- [ ] TestPyPI installation works
- [ ] Production PyPI publish succeeds
- [ ] Production PyPI installation works
- [ ] Version management scenarios work correctly
- [ ] All Python versions supported (3.12, 3.13, 3.14)
- [ ] Troubleshooting guide covers common issues
