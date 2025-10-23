<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Telemetry and Metrics Implementation Plan

**Status**: Planning  
**Version**: 1.0.0  
**Created**: 2025-10-23  
**Author**: GitHub Copilot via Structural Refactor Branch

---

## Executive Summary

This plan outlines the implementation of a comprehensive telemetry and metrics capture system for CodeWeaver that will:

1. Prove efficiency claims (60-80% context reduction, >90% relevance, cost savings)
2. Validate semantic importance scoring system
3. Enable continuous improvement through data-driven insights
4. Maintain strict privacy guarantees (no PII, no code, no repo names)

The system integrates PostHog for telemetry, enhances existing statistics infrastructure, and provides baseline comparison mechanisms to demonstrate CodeWeaver's value proposition with concrete, measurable data.

---

## Table of Contents

1. [Background](#background)
2. [Goals and Success Criteria](#goals-and-success-criteria)
3. [System Architecture](#system-architecture)
4. [Privacy and Security](#privacy-and-security)
5. [Metrics to Capture](#metrics-to-capture)
6. [Baseline Comparison Methodology](#baseline-comparison-methodology)
7. [Semantic Frequency Tracking](#semantic-frequency-tracking)
8. [PostHog Integration](#posthog-integration)
9. [Implementation Phases](#implementation-phases)
10. [Testing Strategy](#testing-strategy)
11. [Configuration and Opt-Out](#configuration-and-opt-out)
12. [Documentation Requirements](#documentation-requirements)
13. [Future Enhancements](#future-enhancements)

---

## Background

### Current State

CodeWeaver has robust statistics infrastructure in `src/codeweaver/common/statistics.py`:

- **TimingStatistics**: Tracks timing for all MCP operations and HTTP requests
- **FileStatistics**: Tracks file operations by category and language
- **TokenCounter**: Tracks token usage with cost calculations
- **SessionStatistics**: Aggregates all statistics with success/failure tracking

Additionally, `src/codeweaver/semantic/classifications.py` includes:

- **UsageMetrics**: Semantic category usage tracking (not yet integrated)
- **ImportanceScores**: Multi-dimensional importance scoring for AI contexts
- **SemanticClass**: Language-agnostic semantic categories

### The Gap

What's missing:

1. **PostHog Integration**: No telemetry sending infrastructure
2. **Semantic Integration**: UsageMetrics not connected to search pipeline
3. **Baseline Comparison**: No mechanism to compare against naive approaches
4. **Validation Framework**: No way to prove efficiency claims with data

### Efficiency Claims to Prove

From PRODUCT.md and README.md:

| Metric | Target | How to Measure |
|--------|--------|----------------|
| Context Token Reduction | 60-80% vs traditional | TokenCounter.context_saved |
| Search Relevance | >90% results relevant | User feedback + manual validation |
| Cost Per Query | <$0.10 (vs $0.20-$0.30) | TokenCounter.money_saved |
| Query Latency | <2 seconds typical | TimingStatistics.averages |
| Precision Improvement | 40-60% vs keyword-only | Baseline comparison |

---

## Goals and Success Criteria

### Primary Goals

1. **Quantify Value**: Provide concrete data proving CodeWeaver's efficiency gains
2. **Enable Optimization**: Identify opportunities for improvement through usage patterns
3. **Validate Design**: Confirm semantic importance scoring aligns with real-world usage
4. **Maintain Privacy**: Collect metrics without compromising user privacy

### Success Criteria

#### Phase 1 (Foundation)
- [ ] PostHog client operational with privacy filtering
- [ ] Telemetry events sent successfully (with user consent)
- [ ] Configuration system allows easy opt-out
- [ ] Zero PII leaks in production telemetry

#### Phase 2 (Integration)
- [ ] UsageMetrics integrated into search pipeline
- [ ] Baseline comparison produces reasonable estimates
- [ ] POC script demonstrates end-to-end metrics collection
- [ ] Statistics accurately reflect system behavior

#### Phase 3 (Validation)
- [ ] Data confirms 60-80% context reduction claim
- [ ] Query latency measurements validate <2s target
- [ ] Semantic category frequencies inform importance tuning
- [ ] Cost savings calculations verified against actual API costs

---

## System Architecture

### Component Overview

```
┌─────────────────────────────────────────────────────────┐
│                  CodeWeaver Application                  │
├─────────────────────────────────────────────────────────┤
│                                                          │
│  ┌──────────────────────────────────────────────────┐  │
│  │         Search Pipeline                          │  │
│  │  - Query Processing                              │  │
│  │  - Result Assembly                               │  │
│  │  - Semantic Classification ─────┐               │  │
│  └──────────────────────────────────│───────────────┘  │
│                                     │                   │
│  ┌──────────────────────────────────▼───────────────┐  │
│  │      SessionStatistics                           │  │
│  │  - TimingStatistics                              │  │
│  │  - FileStatistics                                │  │
│  │  - TokenCounter                                  │  │
│  │  - UsageMetrics (NEW)                            │  │
│  └──────────────────────────────────┬───────────────┘  │
│                                     │                   │
│  ┌──────────────────────────────────▼───────────────┐  │
│  │      Telemetry Module                            │  │
│  │  ┌────────────┐  ┌──────────────┐               │  │
│  │  │  Privacy   │  │  PostHog     │               │  │
│  │  │  Filter    ├─▶│  Client      │               │  │
│  │  └────────────┘  └──────────────┘               │  │
│  │  ┌────────────┐  ┌──────────────┐               │  │
│  │  │  Baseline  │  │  Events      │               │  │
│  │  │  Compare   │  │  Schema      │               │  │
│  │  └────────────┘  └──────────────┘               │  │
│  └─────────────────────────────────────────────────┘  │
│                                                          │
└───────────────────────────┬──────────────────────────────┘
                            │
                            ▼
                   ┌─────────────────┐
                   │  PostHog        │
                   │  Analytics      │
                   └─────────────────┘
```

### Module Structure

```
src/codeweaver/telemetry/
├── __init__.py           # Package exports
├── client.py             # PostHog client wrapper
├── config.py             # Telemetry configuration
├── events.py             # Event schemas and definitions
├── privacy.py            # Privacy filtering and anonymization
└── comparison.py         # Baseline comparison calculator

scripts/testing/
└── metrics-poc.py        # Proof of concept demonstration

tests/telemetry/
├── test_client.py
├── test_privacy.py
├── test_events.py
└── test_comparison.py
```

---

## Privacy and Security

### Privacy Principles

Following CodeWeaver's commitment: "extreme care not to collect any information that could reveal your identity or projects"

### What We NEVER Collect

❌ **Query Content**: No search queries or natural language input  
❌ **Code Snippets**: No code from search results  
❌ **File Paths**: No absolute or relative paths  
❌ **Repository Names**: No repo identifiers  
❌ **User Identifiers**: No usernames, emails, or IP addresses  
❌ **Individual Query Timing**: Could fingerprint specific projects  
❌ **Specific File Names**: Could reveal project structure  

### What We DO Collect (Aggregated & Anonymized)

✅ **Session Summaries**: Aggregated statistics per session
- Total searches count
- Success/failure rates
- Average response times (not individual)
- Session duration

✅ **Token Statistics**: Aggregated token usage
- Total tokens generated (embeddings)
- Total tokens delivered (to agent)
- Total tokens saved (efficiency measure)
- Estimated cost savings

✅ **Language Distribution**: Anonymized counts
```json
{"languages": {"python": 45, "typescript": 23, "rust": 12}}
```
No file paths, just counts by language

✅ **Semantic Category Usage**: Frequency distribution
```json
{
  "semantic_frequencies": {
    "definition_callable": 0.25,
    "flow_branching": 0.15,
    "operation_data": 0.10
  }
}
```

✅ **Performance Benchmarks**: Improvement percentages
- Context reduction percentage
- Baseline vs CodeWeaver comparison
- No specific values that could fingerprint

### Privacy Filtering Implementation

```python
# privacy.py

class PrivacyFilter:
    """Ensures no PII or sensitive data in telemetry events."""
    
    DISALLOWED_KEYS = {
        "query", "content", "code", "path", "file", "filename",
        "repository", "repo", "user", "email", "ip", "host"
    }
    
    def filter_event(self, event: dict) -> dict:
        """Remove any potentially sensitive data from event."""
        
    def anonymize_statistics(self, stats: SessionStatistics) -> dict:
        """Extract only aggregated, anonymized data."""
        
    def validate_event(self, event: dict) -> bool:
        """Ensure event passes privacy requirements."""
```

### Security Considerations

1. **API Key Security**: PostHog API key stored securely (environment variable or secrets manager)
2. **Transport Security**: All data sent over HTTPS
3. **Data Retention**: Follow PostHog's data retention policies
4. **Audit Logging**: Log what events are sent (for debugging/verification)

---

## Metrics to Capture

### 1. Session Summary Metrics

**Event**: `codeweaver_session_summary`  
**Frequency**: End of session or every N minutes  
**Purpose**: Overall system performance and usage patterns

```json
{
  "event": "codeweaver_session_summary",
  "timestamp": "2025-10-23T15:30:00Z",
  "properties": {
    "session_duration_minutes": 45,
    "total_searches": 12,
    "successful_searches": 11,
    "failed_searches": 1,
    "success_rate": 0.917,
    
    "timing": {
      "avg_response_ms": 1250,
      "median_response_ms": 1100,
      "p95_response_ms": 1800
    },
    
    "tokens": {
      "total_generated": 50000,
      "total_delivered": 15000,
      "total_saved": 35000,
      "context_reduction_pct": 70.0,
      "estimated_cost_savings_usd": 0.85
    },
    
    "languages": {
      "python": 45,
      "typescript": 23,
      "rust": 12
    },
    
    "semantic_frequencies": {
      "definition_callable": 0.25,
      "definition_type": 0.18,
      "flow_branching": 0.15,
      "operation_data": 0.12,
      "other": 0.30
    }
  }
}
```

### 2. Performance Benchmark Metrics

**Event**: `codeweaver_performance_benchmark`  
**Frequency**: Per significant search or periodically  
**Purpose**: Prove efficiency gains against baselines

```json
{
  "event": "codeweaver_performance_benchmark",
  "timestamp": "2025-10-23T15:35:00Z",
  "properties": {
    "comparison_type": "naive_vs_codeweaver",
    
    "baseline": {
      "approach": "grep_full_files",
      "estimated_files": 47,
      "estimated_lines": 12000,
      "estimated_tokens": 45000,
      "estimated_cost_usd": 0.25
    },
    
    "codeweaver": {
      "files_returned": 8,
      "lines_returned": 450,
      "tokens_delivered": 12000,
      "actual_cost_usd": 0.05
    },
    
    "improvement": {
      "files_reduction_pct": 83.0,
      "lines_reduction_pct": 96.3,
      "tokens_reduction_pct": 73.3,
      "cost_savings_pct": 80.0
    }
  }
}
```

### 3. Semantic Category Validation Metrics

**Event**: `codeweaver_semantic_validation`  
**Frequency**: Daily or weekly aggregate  
**Purpose**: Validate importance scoring system

```json
{
  "event": "codeweaver_semantic_validation",
  "timestamp": "2025-10-23T23:59:59Z",
  "properties": {
    "period": "daily",
    "total_chunks_analyzed": 5000,
    
    "category_usage": {
      "definition_callable": 1250,
      "definition_type": 900,
      "flow_branching": 750,
      "operation_data": 600,
      "other": 1500
    },
    
    "usage_frequencies": {
      "definition_callable": 0.25,
      "definition_type": 0.18,
      "flow_branching": 0.15,
      "operation_data": 0.12,
      "other": 0.30
    },
    
    "alignment_with_scores": {
      "correlation": 0.85,
      "note": "High correlation suggests importance scores are accurate"
    }
  }
}
```

---

## Baseline Comparison Methodology

### Purpose

To prove CodeWeaver's efficiency, we need concrete comparisons against traditional approaches. This section defines how to estimate what "naive" search would return.

### Baseline Approaches to Model

#### 1. Naive Grep Approach
**Behavior**: Search for keywords, return entire files that match

```python
def estimate_naive_grep(query: str, repository: Repository) -> BaselineMetrics:
    """
    Estimate naive grep approach:
    1. Extract keywords from query
    2. Search all files for keyword matches
    3. Return ENTIRE files (not just matched sections)
    4. Count total tokens
    """
```

**Example**:
- Query: "authentication middleware"
- Keywords: ["authentication", "middleware"]
- Matches: 47 files contain these words
- Returns: All 47 complete files (not just relevant sections)
- Estimated tokens: ~45,000 (assuming 1000 tokens/file average)

#### 2. File-Based Search
**Behavior**: Search file names, return related files

```python
def estimate_file_based_search(query: str, repository: Repository) -> BaselineMetrics:
    """
    Estimate file-name search:
    1. Search for query terms in file paths
    2. Return matched files + files in same directory
    3. Count total tokens
    """
```

**Example**:
- Query: "authentication"
- Matches: auth/*.py, middleware/auth.py, config/auth.py
- Also includes: All files in auth/, middleware/, config/ dirs
- Estimated tokens: ~30,000

#### 3. Directory-Based Search
**Behavior**: Return entire directories

```python
def estimate_directory_based_search(query: str, repository: Repository) -> BaselineMetrics:
    """
    Estimate directory-level search:
    1. Find directories related to query
    2. Return ALL files in those directories
    3. Count total tokens
    """
```

**Example**:
- Query: "authentication"
- Matches: auth/ directory
- Returns: All ~20 files in auth/
- Estimated tokens: ~25,000

### Token Estimation

Since we can't tokenize files we're not actually reading:

```python
def estimate_tokens_for_file(path: Path, ext_kind: ExtKind) -> int:
    """
    Estimate token count without reading file.
    
    Uses:
    - File size (bytes)
    - Language-specific token-to-byte ratios
    - Statistical models from training data
    """
    
    # Average tokens per 1000 bytes by language
    TOKENS_PER_KB = {
        "python": 250,      # ~4 bytes per token
        "typescript": 220,  # ~4.5 bytes per token
        "rust": 200,        # ~5 bytes per token
        "markdown": 300,    # ~3.3 bytes per token
    }
```

### Comparison Calculator

```python
@dataclass
class BaselineMetrics:
    """Metrics from baseline approach."""
    approach: str
    files_matched: int
    total_lines: int
    estimated_tokens: int
    estimated_cost_usd: float

@dataclass
class CodeWeaverMetrics:
    """Metrics from actual CodeWeaver search."""
    files_returned: int
    lines_returned: int
    actual_tokens: int
    actual_cost_usd: float

@dataclass
class ComparisonReport:
    """Comparison between baseline and CodeWeaver."""
    baseline: BaselineMetrics
    codeweaver: CodeWeaverMetrics
    
    @property
    def files_reduction_pct(self) -> float:
        return (1 - self.codeweaver.files_returned / self.baseline.files_matched) * 100
    
    @property
    def tokens_reduction_pct(self) -> float:
        return (1 - self.codeweaver.actual_tokens / self.baseline.estimated_tokens) * 100
    
    @property
    def cost_savings_pct(self) -> float:
        return (1 - self.codeweaver.actual_cost_usd / self.baseline.estimated_cost_usd) * 100
```

### Validation

To ensure baseline estimates are reasonable:

1. **Sanity Checks**: 
   - Baseline should always be >= CodeWeaver
   - Token ratios should be within expected ranges
   - Cost calculations should match pricing models

2. **Spot Validation**:
   - Manually verify estimates for sample queries
   - Compare estimates to actual naive search results (when feasible)
   - Adjust estimation models based on discrepancies

3. **Documentation**:
   - Document all assumptions
   - Provide confidence intervals
   - Clearly state "estimated baseline" vs "actual CodeWeaver"

---

## Semantic Frequency Tracking

### Purpose

Track which SemanticClass categories appear most frequently in search results to:
1. Validate importance scoring system
2. Identify patterns in agent needs
3. Tune ranking algorithms
4. Guide feature development

### Integration Point

```python
# In search result assembly pipeline

def assemble_search_results(chunks: list[CodeChunk]) -> SearchResults:
    """Assemble chunks into final results."""
    
    # Extract semantic categories from chunks
    categories = [
        chunk.metadata.semantic_classification 
        for chunk in chunks 
        if chunk.metadata.semantic_classification
    ]
    
    # Update usage metrics
    session_stats = get_session_statistics()
    if session_stats.semantic_statistics:
        session_stats.semantic_statistics.add_uses(categories)
    
    return SearchResults(chunks=chunks, ...)
```

### SessionStatistics Enhancement

Update `src/codeweaver/common/statistics.py`:

```python
@dataclass
class SessionStatistics(DataclassSerializationMixin):
    """Statistics for tracking session performance and usage."""
    
    timing_statistics: TimingStatistics | None = None
    index_statistics: FileStatistics | None = None
    token_statistics: TokenCounter | None = None
    
    # NEW: Semantic usage tracking
    semantic_statistics: UsageMetrics | None = None
    
    def __post_init__(self) -> None:
        """Post-initialization processing."""
        if not self.semantic_statistics:
            from codeweaver.semantic.classifications import UsageMetrics
            from collections import Counter
            self.semantic_statistics = UsageMetrics(
                category_usage_counts=Counter()
            )
```

### Usage Analysis

```python
# Analyze semantic category usage

def analyze_semantic_usage(
    usage_metrics: UsageMetrics,
    importance_scores: dict[SemanticClass, ImportanceScores]
) -> dict:
    """
    Analyze alignment between usage frequency and importance scores.
    
    Returns:
        Dictionary with correlation analysis and recommendations
    """
    
    # Calculate correlation
    frequencies = usage_metrics.usage_frequencies
    scores = {cat: score.discovery for cat, score in importance_scores.items()}
    
    # Identify discrepancies
    high_usage_low_score = [
        cat for cat in frequencies 
        if frequencies[cat] > 0.15 and scores.get(cat, 0) < 0.5
    ]
    
    return {
        "correlation": calculate_correlation(frequencies, scores),
        "discrepancies": high_usage_low_score,
        "recommendations": generate_tuning_recommendations(...)
    }
```

---

## PostHog Integration

### Client Setup

```python
# src/codeweaver/telemetry/client.py

from posthog import Posthog
from typing import Any
import logging

class PostHogClient:
    """
    Wrapper for PostHog client with privacy filtering and error handling.
    """
    
    def __init__(
        self,
        api_key: str,
        host: str = "https://app.posthog.com",
        enabled: bool = True,
    ):
        self.enabled = enabled
        self.logger = logging.getLogger(__name__)
        
        if enabled:
            self.client = Posthog(project_api_key=api_key, host=host)
        else:
            self.client = None
    
    def capture(
        self,
        event: str,
        properties: dict[str, Any],
        distinct_id: str = "anonymous",
    ) -> None:
        """
        Send event to PostHog with privacy filtering.
        """
        if not self.enabled or not self.client:
            self.logger.debug("Telemetry disabled, skipping event: %s", event)
            return
        
        try:
            # Filter for privacy
            from codeweaver.telemetry.privacy import PrivacyFilter
            filter = PrivacyFilter()
            
            if not filter.validate_event({"event": event, "properties": properties}):
                self.logger.warning("Event failed privacy validation: %s", event)
                return
            
            filtered_properties = filter.filter_event(properties)
            
            # Send to PostHog
            self.client.capture(
                distinct_id=distinct_id,
                event=event,
                properties=filtered_properties,
            )
            
            self.logger.info("Telemetry event sent: %s", event)
            
        except Exception as e:
            # Never fail application due to telemetry
            self.logger.exception("Failed to send telemetry event: %s", e)
    
    def shutdown(self) -> None:
        """Flush pending events and close client."""
        if self.client:
            self.client.flush()
```

### Event Sender

```python
# src/codeweaver/telemetry/events.py

from dataclasses import dataclass
from typing import Protocol

class TelemetryEvent(Protocol):
    """Protocol for telemetry events."""
    
    def to_posthog_event(self) -> tuple[str, dict]:
        """Convert to PostHog event format."""
        ...

@dataclass
class SessionSummaryEvent:
    """Session summary telemetry event."""
    
    session_duration_minutes: float
    total_searches: int
    success_rate: float
    avg_response_ms: float
    total_tokens_generated: int
    total_tokens_delivered: int
    total_tokens_saved: int
    estimated_cost_savings_usd: float
    languages: dict[str, int]
    semantic_frequencies: dict[str, float]
    
    def to_posthog_event(self) -> tuple[str, dict]:
        return (
            "codeweaver_session_summary",
            {
                "session_duration_minutes": self.session_duration_minutes,
                "total_searches": self.total_searches,
                "success_rate": self.success_rate,
                "timing": {"avg_response_ms": self.avg_response_ms},
                "tokens": {
                    "total_generated": self.total_tokens_generated,
                    "total_delivered": self.total_tokens_delivered,
                    "total_saved": self.total_tokens_saved,
                    "estimated_cost_savings_usd": self.estimated_cost_savings_usd,
                },
                "languages": self.languages,
                "semantic_frequencies": self.semantic_frequencies,
            },
        )

# Similar classes for other event types...
```

### Integration with SessionStatistics

```python
# Add method to SessionStatistics

def create_telemetry_event(self) -> SessionSummaryEvent:
    """Create telemetry event from current statistics."""
    
    timing_summary = self.get_timing_statistics()
    token_usage = self.get_token_usage()
    
    # Calculate averages
    avg_response_ms = timing_summary["averages"]["on_call_tool_requests"]["combined"]
    
    # Extract language distribution
    lang_summary = self.index_statistics.get_summary_by_language()
    languages = {
        str(lang): summary["total_operations"]
        for lang, summary in lang_summary.items()
    }
    
    # Extract semantic frequencies
    semantic_frequencies = {}
    if self.semantic_statistics:
        semantic_frequencies = {
            str(cat): freq
            for cat, freq in self.semantic_statistics.usage_frequencies.items()
        }
    
    return SessionSummaryEvent(
        session_duration_minutes=...,  # Calculate from session start
        total_searches=self.total_requests,
        success_rate=self.success_rate,
        avg_response_ms=avg_response_ms,
        total_tokens_generated=token_usage[TokenCategory.EMBEDDING],
        total_tokens_delivered=token_usage[TokenCategory.USER_AGENT],
        total_tokens_saved=token_usage.context_saved,
        estimated_cost_savings_usd=token_usage.money_saved,
        languages=languages,
        semantic_frequencies=semantic_frequencies,
    )
```

---

## Implementation Phases

### Phase 1: Foundation (Week 1)

**Goal**: Establish telemetry infrastructure and privacy guarantees

**Tasks**:
- [ ] Create `src/codeweaver/telemetry/` package structure
- [ ] Implement `PostHogClient` with privacy filtering
- [ ] Implement `PrivacyFilter` with comprehensive tests
- [ ] Create event schemas (SessionSummaryEvent, etc.)
- [ ] Implement telemetry configuration system
- [ ] Add opt-out mechanism (environment variable + config)
- [ ] Write privacy filtering tests (critical!)
- [ ] Document privacy guarantees

**Deliverables**:
- Working PostHog client (with mocked PostHog for testing)
- Privacy filter passing all tests
- Configuration allowing easy opt-out
- Documentation of what's collected

### Phase 2: Integration (Week 2)

**Goal**: Connect telemetry to existing statistics and search pipeline

**Tasks**:
- [ ] Add `semantic_statistics: UsageMetrics` to SessionStatistics
- [ ] Integrate semantic tracking into search result assembly
- [ ] Implement baseline comparison calculator
- [ ] Add telemetry event creation to SessionStatistics
- [ ] Create telemetry sending middleware (or hook into existing)
- [ ] Implement batching/throttling for events
- [ ] Add telemetry to HTTP endpoints (if appropriate)

**Deliverables**:
- Statistics automatically track semantic usage
- Baseline comparisons calculated for searches
- Telemetry events sent at appropriate intervals
- Integration tests passing

### Phase 3: Validation (Week 3)

**Goal**: Prove efficiency claims with real data

**Tasks**:
- [ ] Create POC script (`scripts/testing/metrics-poc.py`)
- [ ] Run POC on CodeWeaver repository itself
- [ ] Collect baseline comparison data
- [ ] Generate efficiency reports
- [ ] Validate against target metrics (60-80% reduction, etc.)
- [ ] Document methodology and findings
- [ ] Create dashboard queries in PostHog

**Deliverables**:
- POC script demonstrating full workflow
- Efficiency report showing concrete improvements
- Validation of key claims
- Dashboard for ongoing monitoring

### Phase 4: Refinement (Week 4)

**Goal**: Optimize and enhance based on initial data

**Tasks**:
- [ ] Analyze semantic usage patterns
- [ ] Tune importance scores if needed
- [ ] Optimize baseline estimation algorithms
- [ ] Add additional metrics if valuable
- [ ] Performance optimization (if telemetry adds overhead)
- [ ] User documentation and guides

**Deliverables**:
- Refined telemetry system
- Documentation for users and developers
- Tuned semantic importance scores
- Performance optimizations

---

## Testing Strategy

### Critical Tests (Following Constitutional Principle IV)

Focus on critical behavior affecting user experience and privacy.

#### 1. Privacy Tests (CRITICAL)

```python
# tests/telemetry/test_privacy.py

def test_privacy_filter_blocks_pii():
    """Ensure PII never gets through."""
    
def test_privacy_filter_blocks_code_snippets():
    """Ensure code never gets through."""
    
def test_privacy_filter_blocks_file_paths():
    """Ensure paths never get through."""
    
def test_privacy_filter_blocks_repo_names():
    """Ensure repo names never get through."""
    
def test_privacy_filter_blocks_query_content():
    """Ensure queries never get through."""
```

#### 2. Statistics Accuracy Tests

```python
# tests/telemetry/test_statistics.py

def test_token_counter_calculates_savings_correctly():
    """Verify cost savings calculations."""
    
def test_semantic_statistics_tracks_usage():
    """Verify semantic usage tracking."""
    
def test_session_statistics_aggregates_correctly():
    """Verify statistics aggregation."""
```

#### 3. Baseline Comparison Tests

```python
# tests/telemetry/test_comparison.py

def test_baseline_estimation_reasonable():
    """Baseline should always be >= CodeWeaver."""
    
def test_token_estimation_accuracy():
    """Token estimation within acceptable error margin."""
```

#### 4. Integration Tests

```python
# tests/integration/test_telemetry_integration.py

def test_telemetry_event_creation_from_session():
    """SessionStatistics can create valid telemetry event."""
    
def test_telemetry_disabled_doesnt_send():
    """When disabled, no events sent."""
    
def test_telemetry_error_doesnt_crash_app():
    """Telemetry errors don't affect application."""
```

#### 5. E2E Test (POC Script)

```python
# scripts/testing/metrics-poc.py

def test_full_workflow():
    """
    End-to-end test demonstrating:
    1. Statistics collection
    2. Baseline comparison
    3. Telemetry event creation
    4. Report generation
    """
```

### Testing Approach

- **Unit Tests**: For privacy filtering, event schemas, calculations
- **Integration Tests**: For statistics aggregation, telemetry sending
- **E2E Test**: POC script as executable test
- **Manual Validation**: Verify PostHog events in dashboard

### Test Coverage Goals

Not chasing 100% coverage. Focus on:
- Privacy filtering: 100% coverage (CRITICAL)
- Event schemas: Validate all fields
- Calculations: Edge cases and boundary conditions
- Integration: Key workflows work end-to-end

---

## Configuration and Opt-Out

### Configuration Sources (Priority Order)

1. **Explicit Config File Setting** (highest priority)
2. **Environment Variable**
3. **Install Variant Default**

### Configuration Schema

```python
# src/codeweaver/telemetry/config.py

from pydantic_settings import BaseSettings
from typing import Optional

class TelemetrySettings(BaseSettings):
    """Telemetry configuration settings."""
    
    # Enable/disable telemetry
    telemetry_enabled: bool = True
    
    # PostHog configuration
    posthog_api_key: Optional[str] = None
    posthog_host: str = "https://app.posthog.com"
    
    # Event batching
    batch_size: int = 10
    batch_interval_seconds: int = 60
    
    # Privacy settings
    strict_privacy_mode: bool = True  # Extra validation
    
    class Config:
        env_prefix = "CODEWEAVER_"
        case_sensitive = False
```

### Environment Variables

```bash
# Disable telemetry
export CODEWEAVER_TELEMETRY_ENABLED=false

# Configure PostHog
export CODEWEAVER_POSTHOG_API_KEY="phc_..."
export CODEWEAVER_POSTHOG_HOST="https://app.posthog.com"

# Adjust batching
export CODEWEAVER_BATCH_SIZE=20
export CODEWEAVER_BATCH_INTERVAL_SECONDS=120
```

### Config File

```toml
# codeweaver.toml

[telemetry]
enabled = true
posthog_api_key = "phc_..."
posthog_host = "https://app.posthog.com"
batch_size = 10
batch_interval_seconds = 60
strict_privacy_mode = true
```

### Opt-Out Instructions

**Method 1: Environment Variable** (simplest)
```bash
export CODEWEAVER_TELEMETRY_ENABLED=false
```

**Method 2: Config File**
```toml
[telemetry]
enabled = false
```

**Method 3: Install Variant**
```bash
uv pip install "codeweaver-mcp[recommended-no-telemetry]"
```

### Verification

Users can verify telemetry is disabled:

```bash
# Check current telemetry status
codeweaver config telemetry status

# Output:
# Telemetry: DISABLED
# Reason: Environment variable CODEWEAVER_TELEMETRY_ENABLED=false
```

---

## Documentation Requirements

### User-Facing Documentation

#### 1. README Updates

Add section on telemetry:

```markdown
## Telemetry

CodeWeaver includes privacy-preserving telemetry by default to help us improve the product.

### What We Collect

We collect **aggregated, anonymized metrics** only:
- Session statistics (search counts, success rates, timing averages)
- Token usage and cost savings estimates
- Language distribution (counts, not file names)
- Semantic category usage frequencies

### What We NEVER Collect

We **never** collect:
- ❌ Your search queries or code
- ❌ File paths or repository names
- ❌ Personal identifiers (usernames, emails, IPs)
- ❌ Any information that could identify you or your projects

### Opt Out

Disable telemetry anytime:

```bash
export CODEWEAVER_TELEMETRY_ENABLED=false
```

Or install the no-telemetry variant:

```bash
uv pip install "codeweaver-mcp[recommended-no-telemetry]"
```

See [TELEMETRY.md](TELEMETRY.md) for complete details.
```

#### 2. TELEMETRY.md (New Document)

Comprehensive telemetry documentation:

```markdown
# CodeWeaver Telemetry

Complete guide to CodeWeaver's privacy-preserving telemetry system.

## Table of Contents
1. [Overview](#overview)
2. [What We Collect](#what-we-collect)
3. [What We Never Collect](#what-we-never-collect)
4. [Privacy Guarantees](#privacy-guarantees)
5. [How to Opt Out](#how-to-opt-out)
6. [Technical Implementation](#technical-implementation)
7. [Verification](#verification)

...
```

### Developer Documentation

#### 1. Architecture Documentation

Add to ARCHITECTURE.md:

```markdown
## Telemetry System

CodeWeaver includes a privacy-preserving telemetry system...

### Design Decisions
- Constitutional Principle III: Evidence-Based Development
- Privacy by design
- Fail-safe (errors don't affect app)
- Opt-out by default for no-telemetry variant

...
```

#### 2. Contributing Guide

Add telemetry guidelines:

```markdown
## Working with Telemetry

When adding new metrics:
1. Verify privacy compliance
2. Add privacy filter tests
3. Update TELEMETRY.md
4. Follow event schema patterns

...
```

---

## Future Enhancements

### Phase 5 and Beyond

Once core system is operational, consider:

#### 1. User Feedback Integration

- Add optional feedback mechanism ("Was this helpful?")
- Track relevance ratings
- Correlate with semantic categories

#### 2. A/B Testing Framework

- Test different ranking algorithms
- Compare baseline estimation methods
- Validate importance score tuning

#### 3. Advanced Analytics

- Cohort analysis (usage patterns over time)
- Funnel analysis (search → success)
- Retention metrics

#### 4. Cost Optimization

- Real-time cost tracking
- Budget alerts
- Provider comparison

#### 5. Semantic Tuning Automation

- Automatic importance score adjustment
- Based on usage patterns
- With human review

#### 6. Comparative Benchmarks

- Public benchmarks against other tools
- Standardized test suites
- Published methodology

#### 7. Real-Time Dashboard

- Live metrics dashboard
- For users (opt-in)
- Shows personal efficiency gains

---

## Appendix

### A. Glossary

**Baseline**: Estimated performance of naive search approaches  
**PostHog**: Open-source product analytics platform  
**PII**: Personally Identifiable Information  
**POC**: Proof of Concept  
**Session**: Single period of CodeWeaver usage  
**Telemetry**: Automated data collection for analysis

### B. References

- [PostHog Documentation](https://posthog.com/docs)
- [PRODUCT.md](../PRODUCT.md) - Success metrics
- [ARCHITECTURE.md](../ARCHITECTURE.md) - System architecture
- [Constitutional Principles](../.specify/memory/constitution.md)

### C. Questions and Answers

**Q: Why PostHog?**  
A: Open-source, privacy-focused, well-documented, proven at scale.

**Q: Can I see what data is sent?**  
A: Yes, enable debug logging to see all telemetry events.

**Q: Is telemetry required?**  
A: No, easily disabled via environment variable or config.

**Q: How often are events sent?**  
A: Batched every 60 seconds or 10 events, whichever comes first.

**Q: Where is data stored?**  
A: PostHog cloud or your self-hosted PostHog instance.

---

**Document Version**: 1.0.0  
**Last Updated**: 2025-10-23  
**Next Review**: After Phase 1 completion
