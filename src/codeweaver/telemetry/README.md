<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# CodeWeaver Telemetry Module

Privacy-preserving telemetry system for collecting anonymized metrics to prove CodeWeaver's efficiency claims.

## Overview

The telemetry module provides:

- **PostHog Integration**: Wrapper around PostHog Python client with privacy filtering
- **Event Schemas**: Structured event types for session summaries, performance benchmarks, and semantic validation
- **Privacy Filtering**: Strict filtering to ensure no PII or sensitive data is collected
- **Baseline Comparison**: Calculator for estimating naive search approaches vs CodeWeaver
- **Configuration**: Easy opt-out mechanism via environment variables or config files

## Privacy Guarantees

### What We NEVER Collect

- ❌ Query content or search terms
- ❌ Code snippets or file contents
- ❌ File paths or repository names
- ❌ User identifiers (usernames, emails, IPs)
- ❌ Individual query timing (could fingerprint projects)

### What We DO Collect (Aggregated & Anonymized)

- ✅ Session summaries (search counts, success rates, averages)
- ✅ Token usage and cost savings estimates
- ✅ Language distribution (counts only, no file names)
- ✅ Semantic category usage frequencies

## Quick Start

### Installation

Telemetry is included by default in the `recommended` install:

```bash
uv pip install "codeweaver-mcp[recommended]"
```

Or opt-out with:

```bash
uv pip install "codeweaver-mcp[recommended-no-telemetry]"
```

### Configuration

Set PostHog API key (if sending telemetry):

```bash
export CODEWEAVER_POSTHOG_API_KEY="phc_your_key_here"
```

Disable telemetry:

```bash
export CODEWEAVER_TELEMETRY_ENABLED=false
```

Or in config file:

```toml
[telemetry]
enabled = false
```

### Basic Usage

```python
from codeweaver.telemetry import get_telemetry_client

# Get singleton client (configured from settings)
client = get_telemetry_client()

if client.enabled:
    # Send event
    client.capture(
        event="codeweaver_session_summary",
        properties={
            "total_searches": 10,
            "success_rate": 0.95,
            # ... more aggregated metrics
        }
    )

# Shutdown at application exit
client.shutdown()
```

### Using Event Schemas

```python
from codeweaver.telemetry.events import SessionSummaryEvent

# Create structured event
event = SessionSummaryEvent(
    session_duration_minutes=45.0,
    total_searches=12,
    successful_searches=11,
    failed_searches=1,
    success_rate=0.917,
    avg_response_ms=1250.0,
    # ... more fields
)

# Send to PostHog
client.capture_from_event(event)
```

## Module Structure

```
src/codeweaver/telemetry/
├── __init__.py           # Package exports
├── client.py             # PostHog client wrapper
├── config.py             # Configuration settings
├── events.py             # Event schemas
├── privacy.py            # Privacy filtering
└── comparison.py         # Baseline comparison
```

## Privacy Filter

The privacy filter automatically validates all events before sending:

```python
from codeweaver.telemetry.privacy import PrivacyFilter

filter = PrivacyFilter(strict_mode=True)

event = {
    "event": "test",
    "properties": {
        "total_searches": 10,  # ✅ Allowed
        "query": "test",       # ❌ Blocked
    }
}

# Validate before sending
if filter.validate_event(event):
    client.capture(event["event"], event["properties"])
```

### Disallowed Keys

The following keys are NEVER allowed in telemetry:

- `query`, `search`, `term`, `content`, `code`, `snippet`
- `path`, `file`, `filename`, `directory`, `folder`
- `repository`, `repo`, `project`
- `user`, `username`, `email`, `name`, `id`, `ip`, `host`

## Baseline Comparison

Calculate efficiency improvements vs naive approaches:

```python
from codeweaver.telemetry.comparison import (
    BaselineComparator,
    CodeWeaverMetrics,
)

comparator = BaselineComparator()

# Estimate naive grep approach
baseline = comparator.estimate_naive_grep_approach(
    query_keywords=["authentication", "middleware"],
    repository_files=[
        (Path("auth.py"), "python", 5000),
        # ... more files
    ]
)

# Create CodeWeaver metrics
codeweaver = CodeWeaverMetrics(
    files_returned=8,
    lines_returned=450,
    actual_tokens=12000,
    actual_cost_usd=0.065,
)

# Generate comparison report
comparison = comparator.compare(baseline, codeweaver)

print(f"Token reduction: {comparison.tokens_reduction_pct:.1f}%")
print(f"Cost savings: {comparison.cost_savings_pct:.1f}%")
```

## Event Types

### SessionSummaryEvent

Aggregated session metrics sent at session end or periodically:

```python
SessionSummaryEvent(
    session_duration_minutes=45.0,
    total_searches=12,
    success_rate=0.917,
    avg_response_ms=1250.0,
    total_tokens_generated=50000,
    total_tokens_delivered=15000,
    total_tokens_saved=35000,
    languages={"python": 6, "typescript": 2},
    semantic_frequencies={"definition_callable": 0.25},
)
```

### PerformanceBenchmarkEvent

Comparison metrics showing improvements vs baselines:

```python
PerformanceBenchmarkEvent(
    comparison_type="naive_vs_codeweaver",
    baseline_approach="grep_full_files",
    baseline_estimated_tokens=45000,
    codeweaver_tokens_delivered=12000,
    tokens_reduction_pct=73.3,
    cost_savings_pct=80.0,
    # ... more fields
)
```

### SemanticValidationEvent

Semantic category usage analysis:

```python
SemanticValidationEvent(
    period="daily",
    total_chunks_analyzed=5000,
    category_usage={"definition_callable": 1250},
    usage_frequencies={"definition_callable": 0.25},
    correlation=0.85,
)
```

## Testing

Run telemetry tests:

```bash
pytest tests/telemetry/ -v
```

Privacy filter tests are marked as critical:

```bash
pytest tests/telemetry/test_privacy.py -v -m telemetry
```

## Development

### Running the POC

Test the telemetry system without full CodeWeaver:

```bash
python scripts/testing/metrics-poc.py

# With detailed output:
python scripts/testing/metrics-poc.py --detailed

# Send to PostHog (requires API key):
CODEWEAVER_POSTHOG_API_KEY="phc_..." python scripts/testing/metrics-poc.py --send-telemetry
```

### Adding New Events

1. Create event class in `events.py`:

```python
@dataclass
class MyCustomEvent:
    """My custom telemetry event."""
    
    my_metric: NonNegativeInt
    
    def to_posthog_event(self) -> tuple[str, dict]:
        return ("my_custom_event", {"my_metric": self.my_metric})
```

2. Validate privacy:

```python
# Add test in test_privacy.py
def test_my_custom_event_privacy(privacy_filter):
    event = {"event": "my_custom_event", "properties": {"my_metric": 10}}
    assert privacy_filter.validate_event(event)
```

3. Use in application:

```python
event = MyCustomEvent(my_metric=10)
client.capture_from_event(event)
```

## Configuration Options

All settings use `CODEWEAVER_` prefix:

| Environment Variable | Type | Default | Description |
|---------------------|------|---------|-------------|
| `TELEMETRY_ENABLED` | bool | true | Enable/disable telemetry |
| `POSTHOG_API_KEY` | str | None | PostHog API key |
| `POSTHOG_HOST` | str | https://app.posthog.com | PostHog host |
| `BATCH_SIZE` | int | 10 | Events per batch |
| `BATCH_INTERVAL_SECONDS` | int | 60 | Batch interval |
| `STRICT_PRIVACY_MODE` | bool | true | Extra privacy validation |

## Troubleshooting

### Telemetry Not Working

1. Check if enabled:
```bash
python -c "from codeweaver.telemetry import get_telemetry_client; print(get_telemetry_client().enabled)"
```

2. Verify API key:
```bash
echo $CODEWEAVER_POSTHOG_API_KEY
```

3. Check logs:
```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

### Events Not Appearing in PostHog

1. Ensure `client.shutdown()` is called (flushes pending events)
2. Check PostHog dashboard for event name
3. Verify API key is correct
4. Check for privacy filter rejections in logs

### Privacy Validation Failures

If events are rejected:

1. Check logs for specific reason
2. Ensure no disallowed keys in properties
3. Verify strings don't look like paths or code
4. Review `privacy.py` DISALLOWED_KEYS list

## Links

- [Implementation Plan](../../../plans/telemetry-metrics-implementation-plan.md)
- [POC Script](../../../scripts/testing/metrics-poc.py)
- [Privacy Tests](../../../tests/telemetry/test_privacy.py)
- [PostHog Documentation](https://posthog.com/docs)

## License

Dual-licensed under MIT OR Apache-2.0. See LICENSE files in repository root.
