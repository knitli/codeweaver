<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# CodeWeaver Telemetry Module

Privacy-preserving telemetry system for collecting anonymized metrics to prove CodeWeaver's efficiency claims.

## Overview

The telemetry module provides:

- **PostHog Integration**: Wrapper around PostHog Python client with context API support
- **Event Schemas**: Structured event types for session statistics and per-search analytics
- **Privacy Filtering**: Automatic privacy filtering via `serialize_for_telemetry()` on data models
- **Feature Flags**: A/B testing support via PostHog feature flags
- **Configuration**: Easy opt-out mechanism via environment variables or config files

## Privacy Guarantees

### What We NEVER Collect (unless you explicitly opt-in with `CODEWEAVER__TELEMETRY__TOOLS_OVER_PRIVACY=true`)

- ❌ Query content or search terms
- ❌ Code snippets or file contents
- ❌ File paths or repository names
- ❌ User identifiers (usernames, emails, IPs)

### What We DO Collect (Aggregated & Anonymized)

- ✅ Session summaries (search counts, success rates, averages)
- ✅ Token usage and cost savings estimates
- ✅ Language distribution (counts only, no file names)
- ✅ Semantic category usage frequencies
- ✅ Config settings used (True/False, not the content)

### Opt-In for Enhanced Telemetry

If you want to help us improve CodeWeaver with richer data:

```bash
export CODEWEAVER__TELEMETRY__TOOLS_OVER_PRIVACY=true
```

This allows collection of query patterns and result quality metrics (still anonymized).

## Quick Start

### Installation

Telemetry is included by default in the `recommended` install:

```bash
uv pip install "codeweaver[recommended]"
```

Or opt-out with:

```bash
uv pip install "codeweaver[recommended-no-telemetry]"
```

### Configuration

**Disable telemetry:**

```bash
export CODEWEAVER__TELEMETRY__DISABLE_TELEMETRY=true
```

**Opt-in to enhanced telemetry:**

```bash
export CODEWEAVER__TELEMETRY__TOOLS_OVER_PRIVACY=true
```

**Use your own PostHog instance:**

```bash
export CODEWEAVER__TELEMETRY__POSTHOG_API_KEY="phc_your_key_here"
# also accepts:
export CODEWEAVER_POSTHOG_API_KEY
export CODEWEAVER__TELEMETRY__POSTHOG_HOST="https://your-posthog-instance.com"
```

Or in config file:

```toml
[telemetry]
disable_telemetry = true  # to disable
tools_above_privacy = true  # to opt-in to enhanced
```

### Basic Usage

```python
from codeweaver.common.telemetry import get_telemetry_client

# Get singleton client (configured from settings)
client = get_telemetry_client()

# Start session with metadata
client.start_session({"version": "0.5.0", "backend": "qdrant"})

if client.enabled:
    # Send event
    client.capture(
        event="codeweaver_search",
        properties={
            "intent": "UNDERSTAND",
            "execution_time_ms": 125.5,
            "results": {"candidates": 50, "returned": 10},
        }
    )

# End session and flush events
client.end_session()
```

### Using Event Schemas

```python
from codeweaver.common.telemetry.events import capture_search_event
from codeweaver.agent_api.find_code.intent import IntentType
from codeweaver.agent_api.find_code.types import SearchStrategy

# Capture a search event (convenience function)
capture_search_event(
    response=find_code_response,  # FindCodeResponseSummary
    query="how does authentication work",
    intent_type=IntentType.UNDERSTAND,
    strategies=[SearchStrategy.HYBRID],
    execution_time_ms=125.5,
    tools_over_privacy=False,  # Opt-in for enhanced tracking
)
```

### Context Manager Pattern

```python
from codeweaver.common.telemetry import get_telemetry_client

# Automatic session cleanup
with get_telemetry_client() as client:
    client.start_session({"version": "0.5.0"})
    # ... use client ...
    # end_session() called automatically on exit
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

## Feature Flags

CodeWeaver supports A/B testing via PostHog feature flags:

```python
from codeweaver.common.telemetry import get_telemetry_client

client = get_telemetry_client()

# Get single feature flag
variant = client.get_feature_flag("new_reranker")
if variant == "test":
    # Use experimental reranker
    pass

# Get all feature flags
all_flags = client.get_all_feature_flags()
```

## Event Types

### SessionEvent

Aggregated session statistics sent at session end:

```python
from codeweaver.common.telemetry.events import capture_session_event

# Capture session event (convenience function)
capture_session_event(
    stats=session_statistics,  # SessionStatistics object
    version="0.5.0",
    setup_success=True,
    setup_attempts=1,
    config_errors=[],
    duration_seconds=3600.0,
)
```

**Tracks:**
- Setup success/failure
- Request statistics and performance
- Token economics and savings
- Repository characteristics (languages, file counts)
- Failover statistics

### SearchEvent

Per-search analytics for find_code:

```python
from codeweaver.common.telemetry.events import capture_search_event

# Capture search event
capture_search_event(
    response=find_code_response,  # FindCodeResponseSummary
    query="authentication flow",
    intent_type=IntentType.UNDERSTAND,
    strategies=[SearchStrategy.HYBRID],
    execution_time_ms=125.5,
    tools_over_privacy=False,
    feature_flags={"new_reranker": "control"},
)
```

**Tracks:**
- Search intent and strategies used
- Performance timing
- Result quality metrics (relevance scores, match types)
- Index state
- Feature flags for A/B testing
- Optional query patterns (with `tools_over_privacy=True`)

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

### Adding New Events

1. Create event class in `events.py`:

```python
from typing import Any

class MyCustomEvent:
    """My custom telemetry event."""

    EVENT_NAME = "my_custom_event"

    def __init__(self, my_metric: int):
        self.my_metric = my_metric

    def to_posthog_event(self) -> tuple[str, dict[str, Any]]:
        """Convert to PostHog format."""
        return (self.EVENT_NAME, {"my_metric": self.my_metric})
```

2. Use in application:

```python
from codeweaver.common.telemetry import get_telemetry_client

client = get_telemetry_client()
event = MyCustomEvent(my_metric=10)
client.capture_from_event(event)
```

**Note**: If your event data comes from BasedModel or DataclassSerializationMixin objects, use `capture_with_serialization()` to automatically apply privacy filtering via `serialize_for_telemetry()`.

## Configuration Options

All settings use `CODEWEAVER__TELEMETRY__` prefix (note the double underscores):

| Environment Variable | Type | Default | Description |
|---------------------|------|---------|-------------|
| `DISABLE_TELEMETRY` | bool | false | Disable all telemetry |
| `TOOLS_OVER_PRIVACY` | bool | false | Opt-in to enhanced telemetry (query patterns, results) |
| `POSTHOG_API_KEY` | str | None | PostHog API key (for custom instance) |
| `POSTHOG_HOST` | str | https://us.i.posthog.com | PostHog host |
| `BATCH_SIZE` | int | 10 | Events per batch |
| `BATCH_INTERVAL_SECONDS` | int | 60 | Batch interval |

## Troubleshooting

### Telemetry Not Working

1. Check if enabled:
```bash
python -c "from codeweaver.common.telemetry import get_telemetry_client; print(get_telemetry_client().enabled)"
```

2. Check if disabled:
```bash
echo $CODEWEAVER__TELEMETRY__DISABLE_TELEMETRY
```

3. Verify API key (if using custom instance):
```bash
echo $CODEWEAVER__TELEMETRY__POSTHOG_API_KEY
```

4. Check logs:
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

- [Privacy Tests](../../../tests/unit/telemetry/test_privacy_serialization.py) - Verify anonymization works correctly
- [PostHog Documentation](https://posthog.com/docs) - Official PostHog docs

## License

Dual-licensed under MIT OR Apache-2.0. See LICENSE files in repository root.
