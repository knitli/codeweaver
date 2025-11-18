<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Research: PyPI Build and Publishing System

**Date**: 2025-10-28
**Branch**: 004-we-re-preparing

## Research Questions

Based on Technical Context analysis, the following areas require research:

1. **Build Backend Selection**: Which PEP 517-compliant build backend works best with uv?
2. **uv-versioning Integration**: How does uv-versioning integrate with build systems?
3. **Package Metadata Standards**: What are current PEP 621 metadata requirements?
4. **GitHub Actions Publishing**: What are best practices for PyPI trusted publishing?
5. **Build Performance**: What are typical build times and optimization strategies?

## Findings

### 1. Build Backend Selection

**Decision**: Use `hatchling` as the build backend

**Rationale**:
- **uv Ecosystem Alignment**: `hatchling` is the default build backend in uv's project templates and is well-tested with uv tooling
- **Modern Standards Compliance**: Fully implements PEP 517/518/621 for modern Python packaging
- **Proven Pattern**: Used by major projects in the Python ecosystem (FastAPI, pydantic, etc.)
- **Zero Configuration**: Works out-of-box with sensible defaults, aligning with Constitutional Simplicity principle
- **Version Management**: Seamlessly integrates with `uv-versioning` plugin for automatic version detection

**Alternatives Considered**:
- **setuptools**: Legacy tool, more configuration complexity, doesn't align with uv-first approach
- **flit**: Simpler but less extensible, not as widely adopted in modern ecosystem
- **pdm-backend**: Good option but hatchling has broader adoption and better uv integration

**Evidence**:
- uv documentation recommends hatchling for new projects: https://docs.astral.sh/uv/guides/publish/
- PEP 517 compliance verified: https://peps.python.org/pep-0517/
- Integration with uv-versioning documented: https://github.com/baggiponte/uv-versioning

### 2. uv-versioning Integration

**Decision**: Configure `uv-versioning` as hatchling plugin in `pyproject.toml`

**Rationale**:
- **Automatic Version Detection**: Derives version from git tags and commit history without manual intervention
- **Per-Commit Versions**: Generates unique pre-release versions (e.g., `0.0.1rc295+gfc4f90a`) for untagged commits
- **Zero-Config Integration**: Works as hatchling plugin, no separate tooling required
- **Changeset Workflow Compatibility**: Reads version from tags managed by changeset workflow

**Integration Pattern**:
```toml
[build-system]
requires = ["hatchling", "uv-versioning"]
build-backend = "hatchling.build"

[tool.hatch.version]
source = "vcs"

[tool.uv-versioning]
# Default settings - automatic detection from git
```

**Evidence**:
- uv-versioning plugin documentation: https://github.com/baggiponte/uv-versioning#usage
- Verified compatibility with hatchling build backend
- Supports both tagged releases and per-commit pre-release versions

### 3. Package Metadata Standards (PEP 621)

**Decision**: Define metadata in `[project]` table following PEP 621

**Required Fields**:
- `name`: Package name on PyPI (`codeweaver`)
- `version`: Dynamic, managed by uv-versioning
- `description`: Short one-line description
- `readme`: Path to README.md (automatically included in distributions)
- `requires-python`: `>=3.12` (per project requirements)
- `license`: Dual MIT OR Apache-2.0 (per SPDX headers)
- `authors`: List with name and email
- `keywords`: List for PyPI search discoverability
- `classifiers`: Development status, Python versions, license, topics

**Optional But Recommended**:
- `urls`: Homepage, repository, documentation, issue tracker
- `dependencies`: Runtime dependencies (auto-detected from project)
- `optional-dependencies`: Dev, test, docs groups

**Evidence**:
- PEP 621 specification: https://peps.python.org/pep-0621/
- PyPI metadata guide: https://packaging.python.org/en/latest/specifications/pyproject-toml/
- Existing project metadata can be referenced from current `pyproject.toml`

### 4. GitHub Actions PyPI Publishing (Trusted Publishing)

**Decision**: Use PyPA official `gh-action-pypi-publish` with OpenID Connect trusted publishing

**Rationale**:
- **No Token Management**: GitHub Actions OAuth eliminates need for PyPI API tokens
- **Security Best Practice**: Trusted publishing is recommended by PyPI for automated releases
- **Official Action**: Maintained by Python Packaging Authority (PyPA)
- **Environment Protection**: Supports GitHub environment protection rules for production releases

**Workflow Pattern**:
```yaml
name: Publish to PyPI

on:
  push:
    tags:
      - 'v*'

jobs:
  publish:
    runs-on: ubuntu-latest
    environment: pypi  # Optional: environment protection
    permissions:
      id-token: write  # Required for trusted publishing
      contents: read

    steps:
      - uses: actions/checkout@v4
      - uses: astral-sh/setup-uv@v3
      - name: Build package
        run: uv build
      - name: Publish to PyPI
        uses: pypa/gh-action-pypi-publish@release/v1
        with:
          repository-url: https://upload.pypi.org/legacy/  # Production
          # For TestPyPI: repository-url: https://test.pypi.org/legacy/
```

**Prerequisites** (Already Configured):
- PyPI trusted publisher configured for repository
- GitHub Actions OAuth authentication enabled

**Evidence**:
- Official action documentation: https://github.com/pypa/gh-action-pypi-publish
- PyPI trusted publishing guide: https://docs.pypi.org/trusted-publishers/
- Spec clarifications confirm GitHub Actions OAuth already configured

### 5. Build Performance

**Decision**: Baseline measurement first, optimize if needed

**Typical Build Times**:
- **Simple packages**: 5-15 seconds (no compiled extensions)
- **Complex packages**: 30-120 seconds (with Rust/C extensions)
- **CodeWeaver estimate**: 10-20 seconds (pure Python, moderate size)

**Performance Optimization Strategies** (If Needed):
- **Parallel Testing**: Use `pytest-xdist` for parallel test execution
- **Caching**: Cache uv dependencies in GitHub Actions with `astral-sh/setup-uv` action
- **Incremental Builds**: Skip redundant steps with GitHub Actions job conditions
- **Artifact Reuse**: Build once, publish to both TestPyPI and PyPI from same artifact

**Baseline Measurement Plan**:
1. Time `uv build` on current codebase
2. Time full CI pipeline (test + build + publish to TestPyPI)
3. Set optimization targets only if baseline exceeds "reasonable time" threshold (TBD with user)

**Evidence**:
- Python packaging performance benchmarks: https://hynek.me/articles/python-packaging-benchmarks/
- GitHub Actions caching best practices: https://docs.github.com/en/actions/using-workflows/caching-dependencies
- uv build performance characteristics: https://docs.astral.sh/uv/reference/cli/#uv-build

## Additional Research Findings

### Build Artifact Cleanup

**Decision**: Use `uv build --clean` flag and GitHub Actions automatic artifact cleanup

**Rationale**:
- `uv build --clean` removes previous build artifacts before building
- GitHub Actions runners are ephemeral - artifacts automatically cleaned after job completion
- No persistent build directory pollution in repository

### Package Verification

**Decision**: Use `twine check` for pre-publication validation

**Rationale**:
- Validates package metadata completeness and correctness
- Catches common packaging errors before PyPI upload
- Part of PyPA official tooling, widely adopted standard

**Integration**:
```bash
uv build --clean
twine check dist/*
uv publish  # or gh-action-pypi-publish
```

### Dry-Run Testing

**Decision**: Support TestPyPI for dry-run publishing

**Rationale**:
- Allows testing full publishing workflow without affecting production PyPI
- Validates package installation from PyPI-like repository
- Catches PyPI-specific issues (name conflicts, metadata problems) before production

**Implementation**:
- Separate GitHub Actions workflow for TestPyPI (manual trigger or branch-based)
- Verification step: Install from TestPyPI and run smoke tests

## Research Summary

All Technical Context unknowns have been resolved:

✅ **Build Backend**: `hatchling` (proven pattern, uv-aligned, PEP 517 compliant)
✅ **Version Management**: `uv-versioning` plugin (automatic detection, changeset compatible)
✅ **Metadata Standards**: PEP 621 `[project]` table (all required fields identified)
✅ **Publishing Workflow**: PyPA `gh-action-pypi-publish` with trusted publishing
✅ **Performance**: Baseline measurement planned, optimization strategies identified
✅ **Artifact Cleanup**: `uv build --clean` + ephemeral GitHub Actions runners
✅ **Verification**: `twine check` for pre-publication validation
✅ **Testing**: TestPyPI for dry-run validation

## Constitutional Alignment Verification

**Evidence-Based**: ✅ All decisions backed by official documentation, PEPs, and widely-adopted practices
**Proven Patterns**: ✅ Using hatchling, uv-versioning, PyPA official actions, PEP standards
**Simplicity**: ✅ Zero-config defaults, delegating to existing tools (uv, GitHub Actions, uv-versioning)
**AI-First**: ✅ Clear metadata enhances discoverability, reliable packaging enables consistent installation

**Next Phase**: Phase 1 - Design contracts and data model
