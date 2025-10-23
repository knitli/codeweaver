<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Telemetry Integration Checklist

**Purpose**: Step-by-step guide for integrating the telemetry system into CodeWeaver's search pipeline

**Status**: Ready for Integration  
**Created**: 2025-10-23

---

## Prerequisites

- [x] Telemetry module implemented (`src/codeweaver/telemetry/`)
- [x] Privacy filter with comprehensive tests
- [x] Event schemas defined
- [x] Baseline comparison calculator
- [x] Configuration system with opt-out
- [x] POC script demonstrating workflow

---

## Phase 1: Core Integration (Week 1)

### Search Pipeline Integration

- [ ] **Add semantic tracking hook**
  - Location: Search result assembly in `engine/` or `search/`
  - Extract `SemanticClass` from `CodeChunk.metadata`
  - Call `session_statistics.semantic_statistics.add_uses(categories)`
  - Test: Verify categories are tracked after searches

- [ ] **Create telemetry helper**
  ```python
  # src/codeweaver/telemetry/helpers.py
  
  def create_session_summary_from_statistics(
      stats: SessionStatistics,
      session_start: datetime,
  ) -> SessionSummaryEvent:
      """Create telemetry event from session statistics."""
      # Extract data from stats
      # Create SessionSummaryEvent
      # Return for sending
  ```

- [ ] **Add session lifecycle hooks**
  - Session start: Initialize statistics
  - Session end: Generate and send telemetry
  - Periodic: Send summaries every N minutes

### Middleware Integration

- [ ] **Create telemetry middleware**
  ```python
  # src/codeweaver/middleware/telemetry.py
  
  class TelemetryMiddleware(Middleware):
      """Send telemetry at appropriate intervals."""
      
      async def on_call_tool(self, context, call_next):
          # Execute tool
          result = await call_next(context)
          
          # If tool is find_code, check if should send telemetry
          if should_send_telemetry():
              send_session_summary()
          
          return result
  ```

- [ ] **Register middleware**
  - Add to FastMCP middleware stack
  - Configure send interval (default: 5 minutes)
  - Test: Verify telemetry sent periodically

### Configuration

- [ ] **Add telemetry to default config**
  ```toml
  [telemetry]
  enabled = true
  posthog_api_key = "${CODEWEAVER_POSTHOG_API_KEY}"
  batch_interval_seconds = 300  # 5 minutes
  ```

- [ ] **Update install extras**
  - Verify `posthog>=6.3.0` in `recommended`
  - Verify absent in `recommended-no-telemetry`
  - Test both install variants

---

## Phase 2: Baseline Comparison (Week 2)

### Comparison Integration

- [ ] **Add comparison to search flow**
  ```python
  # After search completes
  
  from codeweaver.telemetry.comparison import BaselineComparator
  
  comparator = BaselineComparator()
  baseline = comparator.estimate_naive_grep_approach(
      query_keywords=extract_keywords(query),
      repository_files=get_repository_file_list(),
  )
  
  codeweaver_metrics = CodeWeaverMetrics(
      files_returned=len(results.files),
      lines_returned=sum(r.line_count for r in results),
      actual_tokens=results.token_count,
      actual_cost_usd=calculate_cost(results.token_count),
  )
  
  comparison = comparator.compare(baseline, codeweaver_metrics)
  
  # Send benchmark event
  if should_send_benchmark():
      send_performance_benchmark(comparison)
  ```

- [ ] **Cache repository file list**
  - Expensive to recalculate every search
  - Update on file changes
  - Store in application state

- [ ] **Optimize token estimation**
  - Profile accuracy of estimates
  - Tune TOKENS_PER_KB ratios
  - Document methodology

### Benchmark Event Sending

- [ ] **Add benchmark event creation**
  ```python
  def create_benchmark_event(comparison: ComparisonReport) -> PerformanceBenchmarkEvent:
      return PerformanceBenchmarkEvent(
          comparison_type="naive_vs_codeweaver",
          baseline_approach=comparison.baseline.approach,
          # ... fill all fields
      )
  ```

- [ ] **Configure send frequency**
  - Too frequent: Noisy data
  - Too infrequent: Limited insights
  - Recommendation: 1 per session or every 10 searches

---

## Phase 3: Testing & Validation (Week 3)

### Automated Tests

- [ ] **Run existing privacy tests**
  ```bash
  pytest tests/telemetry/test_privacy.py -v
  ```
  - All tests must pass
  - No exceptions

- [ ] **Add integration tests**
  ```python
  # tests/integration/test_telemetry_integration.py
  
  @pytest.mark.integration
  async def test_telemetry_sent_after_search():
      """Verify telemetry event sent after search completion."""
      # Perform search
      # Check telemetry client called
      # Validate event structure
  
  @pytest.mark.integration
  async def test_telemetry_disabled_doesnt_send():
      """Verify no events sent when telemetry disabled."""
      # Disable telemetry
      # Perform search
      # Verify no calls to PostHog
  ```

- [ ] **Add baseline comparison tests**
  ```python
  # tests/telemetry/test_comparison.py
  
  def test_baseline_always_greater_than_codeweaver():
      """Baseline should always >= CodeWeaver."""
      # Create test data
      # Calculate baseline
      # Verify baseline >= codeweaver
  
  def test_token_estimation_reasonable():
      """Token estimates should be within expected range."""
      # Test various file sizes
      # Verify estimates reasonable
  ```

### Manual Validation

- [ ] **Test with PostHog staging**
  - Create test PostHog project
  - Send events from development
  - Verify events appear correctly
  - Check dashboard queries

- [ ] **Verify privacy compliance**
  - Review sample events in PostHog
  - Confirm no PII present
  - Check for accidental leaks
  - Document review process

- [ ] **Performance testing**
  - Measure telemetry overhead
  - Should be <10ms per operation
  - Should not block main thread
  - Verify async sending works

---

## Phase 4: Documentation (Week 4)

### User Documentation

- [ ] **Update README.md**
  ```markdown
  ## Telemetry
  
  CodeWeaver includes privacy-preserving telemetry...
  
  ### What We Collect
  - Aggregated session statistics
  - Token usage and savings
  - ...
  
  ### What We Never Collect
  - Your queries or code
  - File paths or repo names
  - ...
  
  ### Opt Out
  ```bash
  export CODEWEAVER_TELEMETRY_ENABLED=false
  ```
  
  See [TELEMETRY.md](TELEMETRY.md) for details.
  ```

- [ ] **Create TELEMETRY.md**
  - Comprehensive telemetry guide
  - Privacy guarantees
  - Configuration options
  - FAQ section
  - Contact information

- [ ] **Update ARCHITECTURE.md**
  - Add telemetry system section
  - Document architectural decisions
  - Explain privacy design
  - Link to implementation plan

### Developer Documentation

- [ ] **Add to CONTRIBUTING.md**
  ```markdown
  ## Working with Telemetry
  
  When adding telemetry:
  1. Verify privacy compliance
  2. Add privacy filter tests
  3. Update TELEMETRY.md
  4. Follow event schema patterns
  ```

- [ ] **Document PostHog setup**
  - How to create PostHog project
  - Dashboard configuration
  - Query examples
  - Alerting setup

---

## Phase 5: Deployment (Week 5)

### PostHog Setup

- [ ] **Create production PostHog project**
  - Sign up at posthog.com or self-host
  - Create project
  - Get API key
  - Configure retention policies

- [ ] **Create dashboards**
  - Session overview dashboard
  - Performance metrics dashboard
  - Semantic category analysis
  - Cost savings tracker

- [ ] **Set up alerts**
  - Alert on telemetry failures
  - Alert on privacy violations
  - Alert on anomalous patterns

### Configuration

- [ ] **Add API key to deployment**
  ```bash
  # Production environment
  export CODEWEAVER_POSTHOG_API_KEY="phc_prod_key_here"
  
  # Staging environment  
  export CODEWEAVER_POSTHOG_API_KEY="phc_staging_key_here"
  ```

- [ ] **Configure send intervals**
  - Production: 5-10 minutes
  - Staging: 1-2 minutes (faster feedback)
  - Development: Disabled or very low frequency

### Monitoring

- [ ] **Set up logging**
  ```python
  import logging
  logging.getLogger("codeweaver.telemetry").setLevel(logging.INFO)
  ```

- [ ] **Monitor telemetry health**
  - Events per hour
  - Error rate
  - Privacy filter rejections
  - PostHog API errors

- [ ] **Review data quality**
  - Sample events weekly
  - Verify metrics accuracy
  - Check for outliers
  - Validate privacy compliance

---

## Verification Checklist

Before considering telemetry complete:

### Functionality
- [ ] Events sent successfully to PostHog
- [ ] Privacy filter blocks all PII
- [ ] Baseline comparisons reasonable
- [ ] Semantic tracking works
- [ ] Opt-out mechanism works
- [ ] Configuration system works

### Testing
- [ ] All privacy tests pass
- [ ] Integration tests pass
- [ ] Baseline comparison tests pass
- [ ] POC script runs successfully
- [ ] Manual testing complete

### Documentation
- [ ] README updated
- [ ] TELEMETRY.md created
- [ ] ARCHITECTURE.md updated
- [ ] Code well-commented
- [ ] Examples provided

### Privacy
- [ ] No PII in events
- [ ] No code snippets
- [ ] No file paths
- [ ] No repo names
- [ ] Independent review completed

### Performance
- [ ] Telemetry overhead <10ms
- [ ] No blocking operations
- [ ] Async sending works
- [ ] Error handling robust

---

## Rollback Plan

If issues arise:

1. **Disable telemetry immediately**
   ```bash
   export CODEWEAVER_TELEMETRY_ENABLED=false
   ```

2. **Investigate issue**
   - Check logs
   - Review PostHog events
   - Identify problem

3. **Fix and redeploy**
   - Apply fix
   - Test thoroughly
   - Re-enable telemetry

4. **Data cleanup** (if needed)
   - Contact PostHog support
   - Request event deletion
   - Document incident

---

## Success Criteria

Telemetry integration is successful when:

1. ✅ **Privacy maintained**: No PII in any events
2. ✅ **Efficiency proven**: Data confirms 60-80% token reduction
3. ✅ **Performance acceptable**: <10ms overhead per operation
4. ✅ **User trust**: Clear documentation and easy opt-out
5. ✅ **Data actionable**: Metrics inform development decisions
6. ✅ **System reliable**: >99% event delivery rate

---

## Future Enhancements

After core integration complete:

- [ ] A/B testing framework for ranking algorithms
- [ ] User feedback integration ("Was this helpful?")
- [ ] Real-time cost optimization recommendations
- [ ] Semantic importance score auto-tuning
- [ ] Public benchmark comparisons
- [ ] User-facing efficiency dashboard (opt-in)

---

**Document Version**: 1.0.0  
**Last Updated**: 2025-10-23  
**Owner**: CodeWeaver Team  
**Review Date**: After Phase 5 completion
