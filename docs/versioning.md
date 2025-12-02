<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Version Management

CodeWeaver uses automatic version derivation from git tags powered by `uv-dynamic-versioning`.

## Version Formats

### Tagged Release (Production)
**Format**: `X.Y.Z`
**Example**: `0.1.0`

When you tag a commit with a version number:
```bash
git tag v0.1.0
git push origin v0.1.0
```

The build will create packages with version `0.1.0` (clean semantic version).

### Alpha Release (Early Testing)
**Format**: `X.Y.Z-alpha.N`
**Example**: `0.1.0-alpha.1`
**PyPI Format**: `0.1.0a1` (normalized per PEP 440)

For early alpha releases:
```bash
git tag v0.1.0-alpha.1
git push origin v0.1.0-alpha.1
```

The build will create packages with version `0.1.0a1` (Python normalizes `-alpha.1` to `a1`).

### Beta Release (Feature Complete)
**Format**: `X.Y.Z-beta.N`
**Example**: `0.1.0-beta.1`
**PyPI Format**: `0.1.0b1` (normalized per PEP 440)

For beta releases:
```bash
git tag v0.1.0-beta.1
git push origin v0.1.0-beta.1
```

The build will create packages with version `0.1.0b1` (Python normalizes `-beta.1` to `b1`).

### Pre-Release (Development)
<!-- Note: This is the correct pep440 syntax for release candidates (`rcN` not `rc.N`). While you may commonly see `rc.N` in the wild, it is not valid pep440. -->
**Format**: `X.Y.ZrcN+gHASH` (where `rcN` is concatenated, e.g., `rc295`)
**Example**: `0.1.0rc295+gfc4f90a`

For untagged commits (commits after the latest tag):
- `X.Y.Z`: Version from latest tag
- `rcN`: Release candidate with commit distance N from tag (concatenated, no dot or dash, e.g., `rc295` - this differs from commonly seen `rc.N` style)
- `+gHASH`: Git commit short hash

### Dirty Working Directory
**Format**: `X.Y.ZrcN+gHASH.dirty` (where `rcN` is concatenated, e.g., `rc295`)
**Example**: `0.1.0rc295+gfc4f90a.dirty`

Building with uncommitted changes appends `.dirty` suffix.

⚠️ **Warning**: Dirty builds should not be published to PyPI.

## Version Workflow

### Development Workflow
1. Work on features on feature branches
2. Each commit gets unique pre-release version
3. Build creates: `codeweaver_mcp-0.1.0rc298+g2080710-py3-none-any.whl`

### Alpha Release Workflow
1. Commit and push changes to your branch
2. Create alpha tag:
   ```bash
   git tag v0.1.0-alpha.1
   git push origin v0.1.0-alpha.1
   ```
3. GitHub Actions automatically:
   - Runs tests on Python 3.12, 3.13, 3.14
   - Builds package with version `0.1.0a1`
   - Publishes to PyPI (users must explicitly opt-in to pre-releases)
   - Creates GitHub release marked as "pre-release"

### Production Release Workflow
1. Merge to main branch
2. Create version tag:
   ```bash
   git tag v0.1.0
   git push origin v0.1.0
   ```
3. GitHub Actions automatically:
   - Runs tests on Python 3.12, 3.13, 3.14
   - Builds package with version `0.1.0`
   - Publishes to PyPI
   - Creates GitHub release

### Testing TestPyPI
To test publishing without affecting production:
1. Go to GitHub Actions
2. Run "Publish to TestPyPI" workflow manually
3. Package published to https://test.pypi.org/project/codeweaver/

## Version Configuration

Version management is configured in `pyproject.toml`:

```toml
[project]
version = "dynamic"  # Version derived from git

[build-system]
requires = ["hatchling>=1.27.0", "uv-dynamic-versioning>=0.11.2"]
build-backend = "hatchling.build"

[tool.uv-dynamic-versioning]
vcs = "git"
style = "semver"
bump = true
tag-branch = "main"
commit-prefix = "g"

[tool.hatch.version]
source = "uv-dynamic-versioning"
```

## Checking Current Version

To see what version will be built from current git state:

```bash
# Build locally and check artifacts
uv build
ls dist/

# Output: codeweaver_mcp-{version}-py3-none-any.whl
```

The version in the filename is what will be used for PyPI.

## Troubleshooting

### Version is 0.0.0
**Cause**: No git tags exist
**Fix**: Create initial tag
```bash
git tag v0.0.1
git push origin v0.0.1
```

### Version doesn't match expected
**Cause**: Git state doesn't match expectations
**Fix**: Check current git state
```bash
git describe --tags --always --dirty
```

### Version collision on PyPI
**Cause**: Version already published (PyPI versions are immutable)
**Fix**: Create new tag with incremented version
```bash
git tag v0.1.1
git push origin v0.1.1
```

## Best Practices

1. **Use semantic versioning**: Major.Minor.Patch (e.g., 1.2.3)
2. **Tag on main branch**: Only create release tags after merging to main (alpha/beta can be on feature branches)
3. **Clean working directory**: Commit all changes before tagging
4. **Test on TestPyPI first**: Use TestPyPI workflow to validate before production
5. **Document changes**: Update CHANGELOG.md before tagging

### Pre-Release Strategy

**Alpha** (`-alpha.N`): Robust infrastructure, not heavily tested
- Signals "feature-complete but not battle-tested"
- Sets appropriate expectations for early testers
- Users must explicitly install: `pip install --pre codeweaver`

**Beta** (`-beta.N`): Feature complete, undergoing testing
- Signals "mostly stable, finding edge cases"
- Ready for broader testing audience
- Users must explicitly install: `pip install --pre codeweaver`

**Release Candidate** (`-rc.N`): Final testing before release
- Signals "production-ready pending final validation"
- No new features, bug fixes only
- Last stop before stable release

### Installing Pre-Releases

Users who want to test alpha/beta versions must explicitly opt-in:

```bash
# Install latest pre-release (alpha, beta, or rc)
pip install --pre codeweaver

# Install specific alpha version
pip install code-weaver==0.1.0a1

# Upgrade to latest pre-release
pip install --pre --upgrade codeweaver
```

By default, `pip install code-weaver` will **not** install pre-releases.

## Changelog Management

This project uses **git-cliff** for automated changelog generation. Changelogs are generated from pull request merge commits, filtering out individual commit noise.

### How It Works

- **PR-focused**: Only merge commits from pull requests are included in changelogs
- **Automatic categorization**: PRs are grouped by branch name patterns:
  - `feat/` or `feature/` → Features
  - `fix/`, `bugfix/`, `hotfix/`, `issue-` → Bug Fixes
  - `optimize/`, `perf/` → Performance
  - `docs/`, `doc/` → Documentation
  - `refactor/` → Refactoring
  - `ci/`, `workflow/` → CI/CD
  - `test/` → Testing
  - Everything else → Other Changes
- **Clean output**: Extracts PR descriptions instead of showing "Merge pull request..." messages
- **Manual triggers**: Generate changelogs on-demand via mise tasks or GitHub workflows

### Local Usage

Generate and view changelog:
```bash
# View full changelog (stdout)
mise run changelog

# View unreleased changes only (stdout)
mise run changelog-unreleased

# Update CHANGELOG.md with unreleased changes
mise run changelog-update

# Generate changelog for specific tag
mise run changelog-tag v0.1.0
```

### GitHub Workflow

The changelog can also be generated via GitHub Actions:

1. Go to **Actions** → **Generate Changelog**
2. Click **Run workflow**
3. Options:
   - **Tag**: Leave empty for unreleased changes, or specify a tag (e.g., `v0.1.0`)
   - **Commit**: Check to automatically commit and push CHANGELOG.md
4. Download the generated changelog as an artifact, or check the committed file

### Release Workflow Integration

When you create a release by pushing a tag, the release workflow automatically:
1. Generates release notes using git-cliff
2. Creates a GitHub release with categorized PR descriptions
3. Includes installation instructions and verification info

### Best Practices

1. **Maintain good PR descriptions**: Since the changelog is based on PR descriptions, clear and descriptive PR titles/descriptions result in better changelogs
2. **Use branch name conventions**: Follow the naming patterns (`feat/`, `fix/`, etc.) for automatic categorization
3. **Update before releases**: Run `mise run changelog-update` before creating release tags to keep CHANGELOG.md current
4. **Squash vs Merge**: The setup works with both squash commits and merge commits, but focuses on the final PR merge
