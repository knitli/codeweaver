<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Test Infrastructure Analysis - Executive Summary

**Date**: 2025-12-10
**Status**: 29 skipped + 4 xfail tests with no periodic validation
**Risk Level**: Medium (coverage blind spots)

---

## Problem Statement

The project has **113 test files** but **32 skip/xfail decorators** that never run in CI. Current CI filter is extremely restrictive:

```
not docker and not qdrant and not dev_only and not skip_ci and not network and not external_api and not flaky
```

This means ~20-25% of test coverage blind spots.

---

## Recommended Solution: 4-Tier CI Strategy

### Tier 1: Fast PR Tests (Current)
- **Frequency**: Every PR
- **Duration**: 5-10 minutes
- **Coverage**: 70-80%
- **Status**: ✅ Already implemented

### Tier 2: Nightly Integration Tests (NEW)
- **Frequency**: Daily at 2 AM UTC
- **Duration**: 20-30 minutes
- **Coverage**: 85-90%
- **Adds**: Docker, Qdrant, network tests
- **Status**: ❌ Needs implementation

### Tier 3: Weekly Heavy Tests (NEW)
- **Frequency**: Sunday 3 AM UTC
- **Duration**: 45-60 minutes
- **Coverage**: 95%+
- **Adds**: Model downloads, expensive tests, real providers
- **Status**: ❌ Needs implementation

### Tier 4: Manual Validation (NEW)
- **Frequency**: After releases
- **Coverage**: Package validation
- **Adds**: TestPyPI/PyPI smoke tests
- **Status**: ❌ Needs process

---

## Key Recommendations

### 1. Test Categorization

Add 9 new pytest markers:

```toml
requires_models: Tests that download ML models
expensive: Tests with >30s execution time
requires_gpu: Tests that need GPU acceleration
linux_only/windows_only/macos_only: Platform-specific tests
requires_api_keys: Tests requiring API credentials
real_providers: Tests using actual implementations (not mocks)
timing_sensitive: Tests with strict timing requirements
```

### 2. CI Workflow Files

Create 3 new workflows:
- `.github/workflows/ci-nightly.yml` - Integration tests
- `.github/workflows/ci-weekly.yml` - Heavy tests with model caching
- `.github/workflows/ci-platform-matrix.yml` - Multi-OS validation

### 3. Local Development Commands

Add mise tasks for developers:

```bash
mise run test-fast          # Fast CI subset (<5 min)
mise run test-integration   # Integration tests (~15 min)
mise run test-heavy         # Heavy tests with models (30-60 min)
mise run test-skip          # Run ONLY skipped tests
mise run test-all           # Everything (VERY SLOW)
mise run test-categories    # Show test counts
```

### 4. Model Caching Strategy

Pre-download models in CI setup step:
- Cache models in GitHub Actions cache (10GB free)
- Expected cache hit rate: >90%
- Reduces weekly test time by ~40%

### 5. Coverage Tracking

Separate coverage reports per tier:
- Fast tests → fast coverage badge
- Nightly tests → integration coverage badge
- Weekly tests → heavy coverage badge

Track skipped test trends with automated reporting.

---

## Current Test Breakdown

| Category | Count | Markers Needed | CI Tier |
|----------|-------|----------------|---------|
| Model Downloads | 2 | `requires_models` + `network` | Weekly |
| Platform-Specific | 3 | `linux_only`, `skipif(...)` | Platform Matrix |
| API Key Required | 1 | `requires_api_keys` + `skipif(...)` | Nightly |
| Manual Validation | 4 | `contract` + `skip_ci` | Manual |
| Optional Dependency | 7 | `skipif(...)` with reason | (Current) |
| Provider API | 2 | `external_api` + `skip_ci` | Manual |
| Not Implemented | 1 | Remove skip when done | N/A |
| Timing Sensitive | 1 | `timing_sensitive` + `skip_ci` | Never |
| Debug Only | 1 | `dev_only` + `real_providers` | Never |
| Pydantic v2 Issues | 4 | `xfail` (keep until fixed) | (Current) |

---

## Implementation Plan (4 Weeks)

### Week 1: Foundation
- Add new markers to `pyproject.toml`
- Create 3 new CI workflow files
- Add mise tasks for test tiers
- Create `tests/TESTING_GUIDE.md`

### Week 2: Test Migration
- Update test files with appropriate markers
- Review and clarify all skip reasons
- Convert generic skips to specific markers

### Week 3: CI Infrastructure
- Setup model caching in GitHub Actions
- Configure Docker Compose for nightly
- Setup Qdrant test instance
- Configure Codecov flags

### Week 4: Monitoring & Docs
- Implement skip tracking script
- Create coverage badges
- Update CONTRIBUTING.md
- Setup failure alerts

---

## Success Metrics

### 1 Month
- ✅ Nightly CI running successfully
- ✅ Model cache hit rate >80%
- ✅ All tests have clear markers

### 3 Months
- ✅ Weekly tests covering 95%+ of codebase
- ✅ Skip count reduced by 25%
- ✅ Platform matrix on all 3 OSes

### 6 Months
- ✅ Skip count reduced by 50%
- ✅ All xfail tests fixed or tracked
- ✅ Coverage >90% across all tiers

---

## Risks & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| Model download failures | High | Pre-download with retry, aggressive caching |
| API rate limits | Medium | Exponential backoff, test-specific keys |
| CI cost increase | Low | Free for public repos, optimize parallelization |
| Test maintenance | Medium | Clear markers, automated skip tracking |
| Platform failures | Low | `continue-on-error`, async investigation |

---

## Cost Estimate

**Total Monthly CI Cost**: $0 (public repo, unlimited minutes)

If converted to private repo:
- ~2,500 GitHub Actions minutes/month
- Free tier: 2,000 minutes/month
- Expected overage: ~$10-15/month

Model cache storage: Free (10GB GitHub Actions cache limit, using ~600MB)

---

## Next Steps

1. **Immediate** (Today):
   - Review this analysis
   - Approve marker taxonomy
   - Create GitHub issues for implementation

2. **Week 1** (Next 7 days):
   - Implement Phase 1 (foundation)
   - Create CI workflow files
   - Add mise tasks

3. **Week 2-3** (Days 8-21):
   - Update test files with markers
   - Setup CI infrastructure
   - Test workflows end-to-end

4. **Week 4** (Days 22-28):
   - Deploy monitoring
   - Finalize documentation
   - Generate baseline metrics

---

## Files to Review

- **Main Analysis**: `/home/knitli/codeweaver/claudedocs/test-infrastructure-analysis.md` (comprehensive 500+ line document)
- **Current Config**: `/home/knitli/codeweaver/pyproject.toml` (lines 379-448)
- **Current CI**: `/home/knitli/codeweaver/.github/workflows/ci.yml`
- **Test Runner**: `/home/knitli/codeweaver/.github/workflows/_reusable-test.yml`

---

## Questions to Answer

1. **Model caching strategy**: Use GitHub Actions cache or self-host?
   - **Recommendation**: GitHub Actions cache (simpler, free, sufficient)

2. **Qdrant for nightly**: Ephemeral or persistent test instance?
   - **Recommendation**: Ephemeral (cleaner, no state issues)

3. **Platform matrix**: All OSes weekly or on-demand?
   - **Recommendation**: Weekly + on-demand for releases

4. **Skip tracking**: Manual review or automated tickets?
   - **Recommendation**: Automated report + manual monthly review

5. **Coverage threshold**: Increase from 50%?
   - **Recommendation**: Gradually increase (60% → 70% → 80% over 6 months)

---

## Conclusion

This strategy eliminates coverage blind spots by ensuring **100% of tests run on some cadence** while keeping CI fast for developers. Implementation is low-risk with zero additional costs and clear success metrics.

**Approval needed to proceed with Phase 1 implementation.**
