<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# CodeWeaver Telemetry Module

Privacy-preserving telemetry system for collecting anonymized metrics to prove CodeWeaver's efficiency claims.

## Overview

The telemetry module provides:

- **PostHog Integration**: Wrapper around PostHog Python client
- **Event Schemas**: Structured event types for session summaries, performance benchmarks, and semantic validation  
- **Privacy Filtering**: Automatic privacy filtering via `serialize_for_telemetry()` on data models
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
from codeweaver.server.telemetry import get_telemetry_client

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
from codeweaver.server.telemetry.events import SessionSummaryEvent

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
└── comparison.py         # Baseline comparison
```

## Privacy Filtering

Privacy filtering is now handled automatically via the `serialize_for_telemetry()` method on BasedModel and DataclassSerializationMixin objects. Each model defines its sensitive fields via the `_telemetry_keys()` method:

```python
from codeweaver.core.types import BasedModel, AnonymityConversion, FilteredKey

class MyModel(BasedModel):
    public_data: str = "safe"
    sensitive_path: str = "/home/user/secret.py"
    
    def _telemetry_keys(self):
        return {
            FilteredKey("sensitive_path"): AnonymityConversion.HASH,
        }

model = MyModel()
telemetry_data = model.serialize_for_telemetry()
# sensitive_path is now hashed, not exposed as raw value
```

### Anonymity Conversion Methods

- **FORBIDDEN**: Completely exclude field from telemetry
- **BOOLEAN**: Convert to boolean presence/absence  
- **COUNT**: Convert to count (e.g., list length)
- **HASH**: Hash the value for anonymity
- **DISTRIBUTION**: Convert to distribution of values
- **AGGREGATE**: Aggregate values (e.g., sum)
- **TEXT_COUNT**: Convert text to character count

## Baseline Comparison

Calculate efficiency improvements vs naive approaches:

```python
from codeweaver.server.telemetry.comparison import (
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
pytest tests/unit/telemetry/ -v
```

Privacy serialization tests verify filtering works correctly:

```bash
pytest tests/unit/telemetry/test_privacy_serialization.py -v -m telemetry
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
from codeweaver.core.types import DATACLASS_CONFIG, DataclassSerializationMixin
from pydantic.dataclasses import dataclass

@dataclass(config=DATACLASS_CONFIG)
class MyCustomEvent(DataclassSerializationMixin):
    """My custom telemetry event."""
    
    my_metric: int
    
    def _telemetry_keys(self):
        return None  # No sensitive fields
    
    def to_posthog_event(self) -> tuple[str, dict]:
        return ("my_custom_event", {"my_metric": self.my_metric})
```

2. Add test in test file:

```python
def test_my_custom_event_serializes():
    event = MyCustomEvent(my_metric=10)
    serialized = event.serialize_for_telemetry()
    assert "my_metric" in serialized
    assert serialized["my_metric"] == 10
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

## Troubleshooting

### Telemetry Not Working

1. Check if enabled:
```bash
python -c "from codeweaver.server.telemetry import get_telemetry_client; print(get_telemetry_client().enabled)"
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

### Privacy Concerns

All telemetry events use `serialize_for_telemetry()` which:
- Filters sensitive fields based on `_telemetry_keys()` mappings
- Applies anonymization methods (HASH, COUNT, BOOLEAN, etc.)
- Excludes FORBIDDEN fields completely

To verify what data is sent:
```python
event = MyEvent(...)
print(event.serialize_for_telemetry())
```

## Links

- [Implementation Plan](../../../plans/telemetry-metrics-implementation-plan.md)
- [POC Script](../../../scripts/testing/metrics-poc.py)
- [Privacy Tests](../../../tests/unit/telemetry/test_privacy_serialization.py)
- [PostHog Documentation](https://posthog.com/docs)

## License

Dual-licensed under MIT OR Apache-2.0. See LICENSE files in repository root.
