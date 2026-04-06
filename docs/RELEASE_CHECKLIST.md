<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Release Checklist

## Minor Release (e.g., v0.2.0)

### Pre-Release Preparation

- [ ] **Review README.md**
  - [ ] Installation instructions are current
  - [ ] Known limitations are documented
  - [ ] API key requirements are listed

- [ ] **Documentation Review**
  - [ ] Getting started guide works end-to-end
  - [ ] Configuration examples are valid
  - [ ] Error messages are clear and actionable
  - [ ] Provider setup guides are complete

- [ ] **Code Quality**
  - [ ] All tests pass: `mise run test`
  - [ ] Linting passes: `mise run lint`
  - [ ] Type checking passes: `mise run type-check`
  - [ ] No critical TODOs in core functionality

- [ ] **User Experience**
  - [ ] Error messages are clear and helpful
  - [ ] CLI help text is complete
  - [ ] Configuration validation provides guidance
  - [ ] First-run experience is smooth

### Release Process

- [ ] **Commit and Tag**
  ```bash
  # Commit all changes
  git add -A
  git commit -m "chore: prepare for v0.2.0 release"

  # Create version tag
  git tag v0.2.0

  # Verify version
  uv build
  ls -la dist/  # Should show: code_weaver-0.2.0-py3-none-any.whl
  ```

- [ ] **Push Release**
  ```bash
  # Push commit
  git push origin HEAD

  # Push tag (triggers GitHub Actions)
  git push origin v0.2.0
  ```

- [ ] **Verify Build**
  - [ ] GitHub Actions workflow completes successfully
  - [ ] Tests pass on all Python versions (3.12, 3.13, 3.14)
  - [ ] Package builds without errors
  - [ ] GitHub release created

- [ ] **Verify PyPI Upload**
  - [ ] Package appears on PyPI: https://pypi.org/project/code-weaver/
  - [ ] Version shows correctly
  - [ ] README renders correctly on PyPI
  - [ ] Installation works: `pip install code-weaver`

### Post-Release

- [ ] **Announcement**
  - [ ] Update project status in README (if needed)
  - [ ] Announce on relevant channels

- [ ] **Monitoring**
  - [ ] Watch for GitHub issues
  - [ ] Monitor telemetry (if enabled)
  - [ ] Track installation metrics

- [ ] **Feedback Collection**
  - [ ] Create issue templates for bug reports
  - [ ] Create issue template for feature requests
  - [ ] Document known issues in GitHub

## Stable Release (v1.0.0)

### Prerequisites
- [ ] All 0.x development milestones complete
- [ ] All critical bugs resolved
- [ ] Documentation comprehensive and accurate
- [ ] Breaking changes documented
- [ ] Migration guide available (if applicable)
- [ ] Performance benchmarks run
- [ ] Security review completed

### Additional Steps
- [ ] Create CHANGELOG.md if not exists
- [ ] Update version references in docs
- [ ] Announce stable release

## Version Progression

```
v0.1.0            → Initial public release
v0.1.1            → Patch fixes
v0.2.0            → Monorepo split, extensibility
v0.3.0            → Context Agent, pipeline orchestration
v0.4.0            → Cloud orchestration, distributed indexing
v1.0.0            → Stable release, API guarantees
```

## Rollback Procedure

If critical issues are discovered after release:

1. **Yank the release from PyPI** (makes it unavailable for new installs)
   ```bash
   # Requires PyPI maintainer permissions
   # Can't be done via git, must use PyPI web interface or API
   ```

2. **Create GitHub issue** documenting the problem

3. **Fix the issue** and release new version
   - For minor: create patch release (e.g., `v0.2.1`)
   - For stable: create patch release (e.g., `v1.0.1`)

## Notes

- **Version immutability**: Once published to PyPI, a version cannot be re-uploaded (must increment)
- **Tag naming**: Always prefix with `v` (e.g., `v0.2.0` not `0.2.0`)
- **SemVer 0.x**: Under `0.x.y`, minor version bumps may include breaking changes per SemVer convention
