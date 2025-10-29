<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Publishing Process

CodeWeaver uses GitHub Actions trusted publishing to automatically publish packages to PyPI and TestPyPI.

## Overview

Two publishing workflows are configured:
- **publish.yml**: Publishes to production PyPI (triggered by version tags)
- **publish-test.yml**: Publishes to TestPyPI (manual trigger for testing)

## Prerequisites

### GitHub Actions Trusted Publishing
Trusted publishing is already configured for this repository:
- **PyPI**: Configured for tag-based releases (`v*` tags)
- **TestPyPI**: Configured for manual workflow dispatch

No API tokens needed - GitHub Actions authenticates via OIDC (OpenID Connect).

### Python Versions
All tests must pass on:
- Python 3.12
- Python 3.13
- Python 3.14

## Publishing to TestPyPI

Use TestPyPI to validate publishing before production:

### Manual Workflow Dispatch
1. Go to [GitHub Actions](https://github.com/knitli/codeweaver-mcp/actions)
2. Select "Publish to TestPyPI" workflow
3. Click "Run workflow"
4. Select branch
5. Choose whether to run tests (default: yes)
6. Click "Run workflow" button

### What Happens
1. (Optional) Runs tests on Python 3.12, 3.13, 3.14
2. Builds package with current version
3. Validates with `twine check`
4. Publishes to https://test.pypi.org/project/codeweaver-mcp/

### Verifying TestPyPI Publish
After workflow completes:
```bash
# Create test environment
python -m venv /tmp/test-install
source /tmp/test-install/bin/activate

# Install from TestPyPI
pip install --index-url https://test.pypi.org/simple/ \
            --extra-index-url https://pypi.org/simple/ \
            codeweaver-mcp

# Verify
python -c "import codeweaver; print(codeweaver.__version__)"

# Cleanup
deactivate
rm -rf /tmp/test-install
```

## Publishing to Production PyPI

Production publishing is fully automated via git tags.

### Release Process
1. **Ensure all tests pass** on main branch

2. **Create version tag**:
   ```bash
   git checkout main
   git pull origin main
   git tag v0.1.0
   git push origin v0.1.0
   ```

3. **GitHub Actions automatically**:
   - Runs tests on Python 3.12, 3.13, 3.14
   - Builds package
   - Validates metadata with `twine check`
   - Publishes to https://pypi.org/project/codeweaver-mcp/
   - Creates GitHub release with notes

### Monitoring Release
Watch workflow at: https://github.com/knitli/codeweaver-mcp/actions/workflows/publish.yml

### Verifying PyPI Publish
After workflow completes:
```bash
# Install from PyPI
pip install codeweaver-mcp==0.1.0

# Verify
python -c "import codeweaver; print(codeweaver.__version__)"
```

Check package page: https://pypi.org/project/codeweaver-mcp/0.1.0/

## Workflow Details

### publish.yml (Production)
```yaml
on:
  push:
    tags:
      - v*

jobs:
  tests:
    # Runs on Python 3.12, 3.13, 3.14

  build:
    needs: tests
    # Builds with uv build --clean
    # Validates with twine check

  publish-to-pypi:
    needs: [tests, build]
    environment: pypi
    permissions:
      id-token: write
    # Publishes via pypa/gh-action-pypi-publish
```

### publish-test.yml (TestPyPI)
```yaml
on:
  workflow_dispatch:
    inputs:
      run_tests: true

jobs:
  tests:
    if: ${{ inputs.run_tests }}
    # Runs on Python 3.12, 3.13, 3.14

  build:
    needs: tests
    # Builds with uv build --clean
    # Validates with twine check

  publish-to-testpypi:
    needs: [build]
    environment: testpypi
    permissions:
      id-token: write
    # Publishes to test.pypi.org
```

## Troubleshooting

### Build Fails
**Symptom**: Workflow fails at build step
**Check**:
- pyproject.toml metadata is valid
- All required dependencies are listed
- README.md renders correctly

**Fix**: Run locally to debug
```bash
uv build
twine check dist/*
```

### Tests Fail
**Symptom**: Tests fail in CI
**Check**: Tests pass locally on all Python versions
```bash
python3.12 -m pytest
python3.13 -m pytest
python3.14 -m pytest
```

### Version Already Exists
**Symptom**: PyPI rejects upload - version already exists
**Cause**: PyPI versions are immutable (cannot delete/overwrite)
**Fix**: Create new tag with incremented version
```bash
git tag v0.1.1
git push origin v0.1.1
```

### Trusted Publishing Auth Fails
**Symptom**: "Trusted publisher authentication failed"
**Check**:
- Repository settings → Environments → pypi/testpypi configured
- Workflow has `permissions: id-token: write`
- Trusted publisher configured at PyPI/TestPyPI

**Verify**: Check https://pypi.org/manage/account/publishing/

### Metadata Validation Fails
**Symptom**: `twine check` fails
**Check**: README.md is valid Markdown
```bash
pip install readme-renderer
python -m readme_renderer README.md
```

## Build Artifacts

Each build creates:
- **Wheel**: `codeweaver_mcp-{version}-py3-none-any.whl` (pure Python)
- **Sdist**: `codeweaver_mcp-{version}.tar.gz` (source distribution)

Both artifacts are:
- Validated with `twine check` before publish
- Uploaded to PyPI/TestPyPI
- Attached to GitHub releases (production only)

## Best Practices

1. **Test on TestPyPI first**: Always validate with TestPyPI before production
2. **Verify metadata**: Check PyPI project page displays correctly
3. **Test installation**: Install from TestPyPI and verify functionality
4. **Clean tags**: Only create release tags from main branch with clean working directory
5. **Monitor workflows**: Watch GitHub Actions for any failures
6. **Update changelog**: Document changes before creating release tag

## Emergency Rollback

PyPI versions are immutable - you **cannot** delete or overwrite published versions.

If a broken version is published:
1. **Quick fix**: Publish new patch version immediately
   ```bash
   # Fix the issue
   git commit -m "fix: critical bug in v0.1.0"
   git tag v0.1.1
   git push origin v0.1.1
   ```

2. **Yanking**: Mark version as "yanked" on PyPI (users can still install with `==version`)
   - Go to https://pypi.org/manage/project/codeweaver-mcp/releases/
   - Find the version
   - Click "Yank release"
   - Publish fixed version

3. **Communication**: Update README and documentation with fix version

## Security

- **No API tokens**: Trusted publishing uses GitHub OIDC
- **Environment protection**: pypi environment can require manual approval
- **Restricted permissions**: Workflows only get `id-token: write` and `contents: read`
- **Artifact attestation**: Enabled for supply chain verification

## Resources

- PyPI Project: https://pypi.org/project/codeweaver-mcp/
- TestPyPI Project: https://test.pypi.org/project/codeweaver-mcp/
- GitHub Actions: https://github.com/knitli/codeweaver-mcp/actions
- Trusted Publishing Guide: https://docs.pypi.org/trusted-publishers/
