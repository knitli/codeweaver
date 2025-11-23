<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Release Checklist

## Alpha Release (v0.1.0-alpha.1)

### Pre-Release Preparation

- [ ] **Review README.md**
  - [ ] Installation instructions are current
  - [ ] Alpha status is clearly communicated
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
  git commit -m "chore: prepare for v0.1.0-alpha.1 release"
  
  # Create alpha tag
  git tag v0.1.0-alpha.1
  
  # Verify version
  uv build
  ls -la dist/  # Should show: codeweaver_mcp-0.1.0a1-py3-none-any.whl
  ```

- [ ] **Push Release**
  ```bash
  # Push commit
  git push origin HEAD
  
  # Push tag (triggers GitHub Actions)
  git push origin v0.1.0-alpha.1
  ```

- [ ] **Verify Build**
  - [ ] GitHub Actions workflow completes successfully
  - [ ] Tests pass on all Python versions (3.12, 3.13, 3.14)
  - [ ] Package builds without errors
  - [ ] GitHub release created and marked as "pre-release"

- [ ] **Verify PyPI Upload**
  - [ ] Package appears on PyPI: https://pypi.org/project/codeweaver/
  - [ ] Version shows as `0.1.0a1`
  - [ ] README renders correctly on PyPI
  - [ ] Installation works: `pip install --pre codeweaver`

### Post-Release

- [ ] **Announcement**
  - [ ] Update project status in README (if needed)
  - [ ] Announce on relevant channels
  - [ ] Set expectations: "Alpha - feature complete but not heavily tested"

- [ ] **Monitoring**
  - [ ] Watch for GitHub issues
  - [ ] Monitor telemetry (if enabled)
  - [ ] Track installation metrics

- [ ] **Feedback Collection**
  - [ ] Create issue templates for bug reports
  - [ ] Create issue template for feature requests
  - [ ] Document known issues in GitHub

## Beta Release (v0.1.0-beta.1)

### Prerequisites
- [ ] Alpha testing phase complete (2-4 weeks recommended)
- [ ] Critical bugs from alpha addressed
- [ ] Documentation updated based on alpha feedback
- [ ] Core functionality validated by early testers

### Process
Follow same steps as alpha, but use `v0.1.0-beta.1` tag.

## Stable Release (v0.1.0)

### Prerequisites
- [ ] Beta testing phase complete
- [ ] All critical bugs resolved
- [ ] Documentation comprehensive and accurate
- [ ] Breaking changes documented
- [ ] Migration guide available (if applicable)
- [ ] Performance benchmarks run
- [ ] Security review completed

### Additional Steps
- [ ] Create CHANGELOG.md if not exists
- [ ] Update version references in docs
- [ ] Remove "alpha/beta" warnings from README
- [ ] Announce stable release

## Version Progression

```
v0.1.0-alpha.1    → Alpha testing, gather feedback
v0.1.0-alpha.2    → Bug fixes from alpha.1
v0.1.0-beta.1     → Feature complete, wider testing
v0.1.0-beta.2     → Bug fixes from beta.1
v0.1.0-rc.1       → Release candidate, final validation
v0.1.0            → Stable release
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
   - For alpha: increment to `alpha.2`
   - For beta: increment to `beta.2`
   - For stable: create patch release `v0.1.1`

## Notes

- **PyPI version normalization**: Git tag `v0.1.0-alpha.1` becomes `0.1.0a1` on PyPI (this is correct per PEP 440)
- **Pre-release visibility**: Users must use `--pre` flag to install alpha/beta versions
- **Version immutability**: Once published to PyPI, a version cannot be re-uploaded (must increment)
- **Tag naming**: Always prefix with `v` (e.g., `v0.1.0-alpha.1` not `0.1.0-alpha.1`)
