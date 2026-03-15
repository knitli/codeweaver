<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# TestPyPI Setup Checklist

Complete setup guide for publishing CodeWeaver to TestPyPI via GitHub Actions.

## Prerequisites ✅

### 1. TestPyPI Account
- [ ] Create account at https://test.pypi.org/account/register/
- [ ] Verify email address
- [ ] Enable 2FA (recommended)

### 2. GitHub Repository Configuration
- [ ] Repository: https://github.com/knitli/codeweaver
- [ ] Admin access to repository settings

## Trusted Publisher Configuration 🔐

TestPyPI uses OIDC-based trusted publishing (no API tokens needed).

### On TestPyPI
1. **Login to TestPyPI**: https://test.pypi.org/
2. **Navigate to Publishing**: https://test.pypi.org/manage/account/publishing/
3. **Add a new pending publisher**:
   - **PyPI Project Name**: `code-weaver`
   - **Owner**: `knitli`
   - **Repository**: `codeweaver`
   - **Workflow**: `publish-test.yml`
   - **Environment name**: `testpypi`

### On GitHub
1. **Navigate to**: Settings → Environments
2. **Create environment**: `testpypi`
3. **Environment protection rules** (optional):
   - [ ] Required reviewers (for manual approval before publish)
   - [ ] Wait timer (delay before publish)
   - [ ] Deployment branches (restrict to specific branches)

## GitHub Actions Workflow ⚙️

The workflow is already configured at [`.github/workflows/publish-test.yml`](.github/workflows/publish-test.yml).

### Workflow Configuration Checklist
- [x] Workflow file exists: `.github/workflows/publish-test.yml`
- [x] Uses trusted publishing (OIDC): `permissions: id-token: write`
- [x] Environment configured: `environment: testpypi`
- [x] Repository URL correct: `https://test.pypi.org/legacy/`
- [x] Package name correct: `code-weaver`
- [x] Attestations enabled: `attestations: true`

### Build Configuration Checklist
- [x] Build workflow exists: `.github/workflows/_reusable-build.yml`
- [x] Uses UV for building: `uv build`
- [x] Validates with twine: `twine check dist/*`
- [x] Uploads artifacts: `python-package-distributions`
- [x] Clean build enabled: `clean-build: true`

## Package Configuration 📦

### pyproject.toml Checklist
- [x] Package name: `code-weaver` (not `codeweaver`)
- [x] Version: Dynamically generated via `uv-dynamic-versioning`
- [x] Metadata complete: description, license, authors, keywords
- [x] Dependencies listed correctly
- [x] Build backend: `hatchling`

### Verification
```bash
# Check package metadata locally
uv build
uvx twine check dist/*

# Verify version
python -c "import codeweaver; print(codeweaver.__version__)"
```

## First Publish Test 🚀

### Pre-Flight Checks
- [ ] All tests passing locally
- [ ] Git working directory clean
- [ ] On intended branch (main or feature branch)

### Manual Workflow Trigger
1. **Navigate to**: https://github.com/knitli/codeweaver/actions/workflows/publish-test.yml
2. **Click**: "Run workflow"
3. **Select branch**: (current branch)
4. **Run tests**: ✅ (recommended for first publish)
5. **Click**: "Run workflow" button

### Monitor Workflow
Watch at: https://github.com/knitli/codeweaver/actions

**Expected steps**:
1. ✅ Run Tests (if enabled)
   - Tests on Python 3.12, 3.13
   - Quality checks (ruff, type checking)
2. ✅ Build Distribution
   - Creates wheel and source dist
   - Validates with twine
3. ✅ Publish to TestPyPI
   - Authenticates via OIDC
   - Uploads to test.pypi.org

### Post-Publish Verification

#### 1. Check TestPyPI Page
Visit: https://test.pypi.org/project/code-weaver/

Verify:
- [ ] Package appears
- [ ] Version is correct
- [ ] Description renders properly
- [ ] License shows: MIT OR Apache-2.0
- [ ] Python versions: 3.12, 3.13, 3.14
- [ ] Project URLs work
- [ ] Keywords visible

#### 2. Test Installation
```bash
# Create isolated test environment
python -m venv /tmp/testpypi-verify
source /tmp/testpypi-verify/bin/activate

# Install from TestPyPI
pip install --index-url https://test.pypi.org/simple/ \
            --extra-index-url https://pypi.org/simple/ \
            code-weaver

# Verify installation
python -c "import codeweaver; print(f'Version: {codeweaver.__version__}')"

# Test basic functionality
python -c "from codeweaver import __version__; print('✅ Import successful')"

# Cleanup
deactivate
rm -rf /tmp/testpypi-verify
```

#### 3. Run Automated Tests
```bash
# Run smoke tests
pytest tests/smoke/test_testpypi_install.py -v --no-cov

# Expected: PASSED
```

## Troubleshooting 🔧

### Common Issues

#### "Trusted publisher authentication failed"
**Cause**: OIDC configuration mismatch

**Fix**:
1. Verify TestPyPI publisher settings match exactly:
   - Owner: `knitli`
   - Repository: `codeweaver`
   - Workflow: `publish-test.yml`
   - Environment: `testpypi`
2. Check GitHub environment name matches: `testpypi`
3. Ensure workflow has `permissions: id-token: write`

#### "Package already exists"
**Cause**: Version already published

**Solution**: TestPyPI versions are immutable
- Cannot delete or overwrite versions
- Must increment version number
- For testing: Use dev versions (e.g., `0.1.0a6.dev1`)

#### Build Fails
**Check**:
```bash
# Run build locally
uv build

# Check for errors in:
# - pyproject.toml syntax
# - Missing dependencies
# - Invalid metadata
```

#### Tests Fail in Workflow
**Check**:
```bash
# Run tests locally on all versions
python3.12 -m pytest
python3.13 -m pytest

# Check markers to ensure tests aren't skipped
pytest tests/smoke/ -v --no-cov
```

### Getting Help
- GitHub Actions logs: https://github.com/knitli/codeweaver/actions
- TestPyPI support: https://test.pypi.org/help/
- Trusted publishing guide: https://docs.pypi.org/trusted-publishers/

## Continuous Publishing 🔄

### Regular Testing
After initial setup, use TestPyPI to:
- Test alpha/beta releases before production
- Validate packaging changes
- Verify new dependencies
- Test installation on different platforms

### Best Practices
1. **Always test on TestPyPI first** before production releases
2. **Run full test suite** before publishing
3. **Verify installation** after every TestPyPI publish
4. **Check package metadata** displays correctly
5. **Document changes** in CHANGELOG.md

## Next Steps After TestPyPI

Once TestPyPI publishing works successfully:

1. **Configure Production PyPI**:
   - Follow same trusted publisher setup
   - Use environment name: `production`
   - Workflow: `release.yml`

2. **Automated Releases**:
   - Production publishes on version tags
   - Push `v*` tag triggers release workflow
   - TestPyPI for manual testing only

3. **Run Smoke Tests**:
   ```bash
   # Test PyPI installation works
   pytest tests/smoke/test_pypi_install.py -v --no-cov
   ```

## Checklist Summary ✓

Quick verification before publishing:

- [ ] TestPyPI account created and verified
- [ ] Trusted publisher configured on TestPyPI
- [ ] GitHub environment `testpypi` created
- [ ] Package name is `code-weaver`
- [ ] Workflow file at `.github/workflows/publish-test.yml`
- [ ] Tests passing locally
- [ ] Build works: `uv build && uvx twine check dist/*`

**Ready to publish!** 🎉

Trigger workflow at: https://github.com/knitli/codeweaver/actions/workflows/publish-test.yml
