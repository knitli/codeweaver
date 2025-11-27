<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Data Model: PyPI Build and Publishing System

**Date**: 2025-10-28
**Branch**: 004-we-re-preparing

## Overview

This feature primarily deals with process orchestration and artifact management rather than persistent data models. The "data" consists of package metadata, build artifacts, and workflow state - all ephemeral and derived from repository state.

## Core Entities

### 1. PackageMetadata

**Description**: Project metadata embedded in distributions, defined in `pyproject.toml` following PEP 621

**Fields**:
- `name` (str, required): PyPI package name - "codeweaver"
- `version` (str, dynamic): Derived automatically by uv-versioning from git state
- `description` (str, required): One-line package summary
- `readme` (Path, required): Path to README.md for long description
- `requires-python` (str, required): Minimum Python version - ">=3.12"
- `license` (dict, required): SPDX identifier - "MIT OR Apache-2.0"
- `authors` (list[dict], required): Author names and emails
- `keywords` (list[str], optional): PyPI search keywords
- `classifiers` (list[str], optional): PyPI trove classifiers
- `urls` (dict, optional): Project URLs (homepage, repository, issues, docs)
- `dependencies` (list[str], dynamic): Runtime dependencies from project
- `optional-dependencies` (dict[str, list[str]], optional): Grouped dependencies (dev, test, docs)

**Validation Rules**:
- `name` must be valid PyPI package name (lowercase, hyphens allowed)
- `version` must follow PEP 440 versioning scheme
- `requires-python` must be valid version specifier
- `license` must be valid SPDX identifier
- `authors` must have at least one entry with name or email
- `classifiers` must be from official PyPI classifier list

**Source**: `pyproject.toml` `[project]` table
**Consumer**: Build backend (hatchling), PyPI
**Lifespan**: Static (from source), embedded in every distribution

### 2. VersionIdentifier

**Description**: Semantic version derived from repository state via uv-versioning

**Fields**:
- `base_version` (str): Semantic version from most recent git tag (e.g., "0.1.0")
- `commit_distance` (int): Number of commits since tag (0 for tagged releases)
- `commit_hash` (str): Short git commit hash (e.g., "gfc4f90a")
- `dirty` (bool): Whether working directory has uncommitted changes
- `is_prerelease` (bool): True if commit_distance > 0 (not a tagged release)

**Derived Format**:
- **Tagged release**: `{base_version}` (e.g., "0.1.0")
- **Pre-release**: `{base_version}rc{commit_distance}+{commit_hash}` (e.g., "0.1.0rc295+gfc4f90a")
- **Dirty working directory**: Appends `.dirty` suffix

**Validation Rules**:
- Must follow PEP 440 version scheme
- `base_version` must be semantic version (MAJOR.MINOR.PATCH)
- `commit_distance` must be non-negative integer
- `commit_hash` must be valid git short hash

**Source**: Derived by uv-versioning from git repository state
**Consumer**: Build backend, PyPI, package installers
**Lifespan**: Ephemeral, computed at build time

### 3. BuildArtifact

**Description**: Distributable package file created by build backend

**Fields**:
- `filename` (Path): Full filename with version (e.g., "codeweaver_mcp-0.1.0-py3-none-any.whl")
- `artifact_type` (enum): "wheel" or "sdist" (source distribution)
- `size_bytes` (int): File size in bytes
- `sha256_hash` (str): SHA-256 checksum for integrity verification
- `build_timestamp` (datetime): When artifact was created
- `python_version` (str): Target Python version ("py3" for pure Python)
- `platform` (str): Target platform ("any" for pure Python)

**Validation Rules**:
- `filename` must follow PEP 427 (wheel) or PEP 625 (sdist) naming convention
- `artifact_type` must be "wheel" or "sdist"
- `size_bytes` must be positive
- `sha256_hash` must be 64-character hexadecimal string
- Both wheel and sdist must be created for each release

**Source**: Created by `uv build` command
**Consumer**: PyPI, pip/uv installers
**Lifespan**: Ephemeral locally (cleaned after publish), permanent on PyPI

### 4. BuildManifest

**Description**: Record of build environment and configuration for reproducibility

**Fields**:
- `build_backend` (str): Name and version (e.g., "hatchling==1.18.0")
- `build_backend_dependencies` (list[str]): Backend plugin dependencies (e.g., ["uv-versioning==0.1.0"])
- `python_version` (str): Python version used for build (e.g., "3.12.5")
- `uv_version` (str): uv version used (e.g., "0.4.18")
- `git_commit` (str): Full git commit hash for source state
- `git_tag` (str | None): Git tag if building from tagged commit
- `build_timestamp` (datetime): ISO 8601 timestamp of build
- `ci_environment` (dict | None): CI environment info if applicable (runner OS, GitHub Actions version)

**Validation Rules**:
- All version fields must be valid semantic versions
- `git_commit` must be 40-character hexadecimal SHA-1 hash
- `build_timestamp` must be valid ISO 8601 datetime

**Source**: Collected during build process
**Consumer**: Documentation, debugging, reproducibility verification
**Lifespan**: Stored in build logs, optionally embedded in package metadata

### 5. PublishRequest

**Description**: State for PyPI publishing operation (workflow state, not persistent data)

**Fields**:
- `repository_url` (HttpUrl): Target repository ("https://upload.pypi.org/legacy/" or "https://test.pypi.org/legacy/")
- `package_name` (str): Name being published (from metadata)
- `version` (str): Version being published (from metadata)
- `artifacts` (list[BuildArtifact]): Wheel and sdist to upload
- `authentication_method` (enum): "trusted_publisher" (GitHub Actions OAuth)
- `dry_run` (bool): Whether this is a test run (TestPyPI)

**Validation Rules**:
- `repository_url` must be valid HTTPS URL (PyPI or TestPyPI)
- `package_name` must match PackageMetadata.name
- `version` must match all artifacts' versions
- `artifacts` must include both wheel and sdist
- `authentication_method` must be "trusted_publisher" (token-based auth not supported per requirements)

**State Transitions**:
1. **pending** → artifacts validated, ready to publish
2. **publishing** → upload in progress
3. **published** → successfully uploaded to PyPI
4. **failed** → upload failed with error message

**Source**: GitHub Actions workflow
**Consumer**: PyPI publishing action
**Lifespan**: Ephemeral, exists only during workflow execution

## Entity Relationships

```
PackageMetadata (1) ──< VersionIdentifier (1)
       │                      │
       │                      │
       ├──────────────────────┴──> BuildArtifact (2: wheel + sdist)
       │                                   │
       │                                   │
       └──> BuildManifest (1) ─────────────┘
                                            │
                                            │
                                            v
                                    PublishRequest (1)
                                            │
                                            v
                                          PyPI
```

**Cardinality**:
- One PackageMetadata per build
- One VersionIdentifier per build (derived from git state)
- Two BuildArtifacts per build (wheel + sdist)
- One BuildManifest per build (reproducibility record)
- One PublishRequest per publish operation (can target multiple repositories sequentially)

## Data Flow

### Build Flow
```
1. Repository State (git tags, commits)
   → uv-versioning computes VersionIdentifier

2. pyproject.toml [project] table
   → PackageMetadata loaded

3. VersionIdentifier injected into PackageMetadata

4. Build backend (hatchling) + source code
   → BuildArtifacts (wheel + sdist) created

5. Build environment captured
   → BuildManifest recorded
```

### Publish Flow
```
1. BuildArtifacts validated
   → twine check confirms metadata correctness

2. CI tests pass on Python 3.12-3.14
   → Quality gate passed

3. PublishRequest created with BuildArtifacts

4. GitHub Actions OAuth authentication
   → Trusted publisher credentials obtained

5. PublishRequest executed
   → Artifacts uploaded to PyPI

6. PyPI validates and indexes package
   → Package available for installation
```

## Validation Strategy

### Pre-Build Validation
- Verify `pyproject.toml` syntax and PEP 621 compliance
- Check required metadata fields present
- Validate license, classifiers, version specifiers

### Build Validation
- Confirm both wheel and sdist created successfully
- Verify artifact filenames follow PEP conventions
- Check file sizes reasonable (not empty or suspiciously large)

### Pre-Publish Validation (Contract Tests)
- `twine check dist/*` validates metadata completeness
- Verify version not already published to PyPI (prevent duplicates)
- Confirm CI tests passed on all supported Python versions
- Validate artifact checksums match expected values

### Post-Publish Validation (Smoke Tests)
- Install from PyPI/TestPyPI
- Import main package and verify basic functionality
- Confirm installed version matches published version

## Configuration Schema

Build system configuration in `pyproject.toml`:

```toml
[build-system]
requires = ["hatchling", "uv-versioning"]
build-backend = "hatchling.build"

[tool.hatch.version]
source = "vcs"  # Delegate to uv-versioning

[tool.uv-versioning]
# Default configuration - automatic detection
```

All validation rules and constraints derive from:
- PEP 621 (Project metadata)
- PEP 440 (Version specifiers)
- PEP 427 (Wheel format)
- PEP 625 (Source distribution format)
- PEP 517/518 (Build system interface)

## Notes for Implementation

- **No Persistent Storage**: All entities are ephemeral, derived from repository state or build process
- **Immutable Artifacts**: BuildArtifacts and BuildManifest are created once, never modified
- **Idempotency**: Building from same git commit should produce identical artifacts (reproducible builds)
- **Error Handling**: Validation failures should provide clear, actionable error messages
- **Atomic Operations**: Publishing should be all-or-nothing (both wheel and sdist, or neither)
