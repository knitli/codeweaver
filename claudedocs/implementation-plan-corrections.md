<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Implementation Plan Corrections Summary

**Date**: 2025-01-28
**Status**: CORRECTED - Ready for implementation

## Critical Corrections Made

### 1. Context Access Pattern ✅ FIXED

**BEFORE (Incorrect)**:
```python
# This pattern DOES NOT EXIST in FastMCP
background_state = context.request_context.app.state.background
```

**AFTER (Correct)**:
```python
# Use global getter (same pattern as current get_state())
from codeweaver.server.background.state import get_background_state

background_state = get_background_state()

# Note: DI framework planned for future will replace global getter
```

**Why the correction**:
- FastMCP Context is request-scoped and doesn't provide `app.state` access
- Current codebase uses `get_state()` global function successfully
- Future DI framework will replace this pattern

### 2. SearchEvent Telemetry ✅ CLARIFIED

**Status**: Already correctly implemented, no changes needed

**Location**: `src/codeweaver/agent_api/find_code/__init__.py:387-395, 408-418`

**Implementation**:
```python
# Inside find_code business logic (NOT in middleware)
try:
    capture_search_event(
        response=response,
        query=query,
        intent_type=intent_type,
        strategies=strategies_used,
        execution_time_ms=execution_time_ms,
        tools_over_privacy=tools_over_privacy,
        feature_flags=feature_flags,
    )
except Exception:
    # Never fail find_code due to telemetry
    logger.debug("Failed to capture search telemetry")
```

**Why this is correct**:
- SearchEvent needs rich find_code execution context (query, response, intent, strategies)
- Too specific to find_code to be in general middleware
- Already implemented and working correctly
- StatisticsMiddleware handles MCP-level timing separately

### 3. Telemetry Architecture ✅ CLARIFIED

**Two Separate Telemetry Systems**:

1. **MCP-Level Timing** (StatisticsMiddleware - FastMCP middleware)
   - Captures: Request timing, success/failure, request IDs
   - Scope: ALL MCP operations (tools, resources, prompts)
   - Location: `src/codeweaver/middleware/statistics.py`
   - **No changes needed**

2. **SearchEvent Telemetry** (find_code business logic)
   - Captures: Query, response, intent, strategies, execution time, feature flags
   - Scope: Only find_code execution
   - Location: `src/codeweaver/agent_api/find_code/__init__.py`
   - **No changes needed**

**Why separate**:
- Different scopes (all MCP vs. find_code only)
- Different data requirements
- Different purposes (performance monitoring vs. search analytics)

## Architecture Diagram (Corrected)

```
┌─────────────────────────────────────────────────────────┐
│  CodeWeaver MCP Server Process                         │
│                                                          │
│  ┌────────────────────────────────────────────────────┐ │
│  │  MCP Protocol Layer (FastMCP)                      │ │
│  │  - FastMCP Middleware:                             │ │
│  │    * StatisticsMiddleware (MCP timing)             │ │
│  │    * ErrorHandlingMiddleware                       │ │
│  │    * RateLimitingMiddleware                        │ │
│  └────────────────────────────────────────────────────┘ │
│         ↓ Tools call get_background_state()             │
│  ┌────────────────────────────────────────────────────┐ │
│  │  Management Server (HTTP - Port 9329)              │ │
│  │  - /health, /metrics, /version, /settings, /state  │ │
│  │  - Accesses BackgroundState via get_state()        │ │
│  └────────────────────────────────────────────────────┘ │
│         ↓ Both access via global getter                 │
│  ┌────────────────────────────────────────────────────┐ │
│  │  BackgroundState (global singleton)                │ │
│  │  - get_background_state() function                 │ │
│  │  - ProviderRegistry                                │ │
│  │  - Indexer                                         │ │
│  │  - HealthService                                   │ │
│  │  - SessionStatistics                               │ │
│  │  - VectorStoreFailoverManager                      │ │
│  │  - ManagementServer reference                      │ │
│  └────────────────────────────────────────────────────┘ │
│         ↓                                               │
│  ┌────────────────────────────────────────────────────┐ │
│  │  find_code Business Logic                          │ │
│  │  - Accesses BackgroundState via getter             │ │
│  │  - Executes search                                 │ │
│  │  - Captures SearchEvent telemetry (internal)       │ │
│  │  - Returns FindCodeResponseSummary                 │ │
│  └────────────────────────────────────────────────────┘ │
└─────────────────────────────────────────────────────────┘
```

## Data Flow Summary (Corrected)

### Flow 1: MCP-Level Timing
```
Client → MCP Request → StatisticsMiddleware.on_call_tool()
                    → Captures timing, success/failure
                    → Updates SessionStatistics
                    → Calls actual tool
```

### Flow 2: SearchEvent Telemetry
```
find_code execution → Builds response
                   → capture_search_event() (internal)
                   → SearchEvent to PostHog
                   → Returns response
```

### Flow 3: BackgroundState Access
```
Tool/Endpoint → get_background_state() (global)
             → BackgroundState (singleton)
             → ProviderRegistry/Indexer/etc.
```

## Implementation Checklist Updates

### REMOVED from plan:
- ❌ BackgroundStateMiddleware (Starlette middleware) - NOT NEEDED
- ❌ Context injection pattern (`context.request_context.app.state.background`) - DOESN'T EXIST
- ❌ SearchEvent middleware - ALREADY IN find_code BUSINESS LOGIC

### KEPT in plan:
- ✅ `get_background_state()` global function
- ✅ StatisticsMiddleware (FastMCP middleware) for MCP timing
- ✅ SearchEvent telemetry in find_code business logic
- ✅ Management server on port 9329
- ✅ Rename AppState → BackgroundState

### NEW clarifications:
- ✅ Note: DI framework planned for future (replaces global getter)
- ✅ Telemetry is two separate systems with different purposes
- ✅ No middleware needed for state passing (global getter works)

## Files Updated

1. `/home/knitli/codeweaver/claudedocs/option-a-service-implementation-plan-final.md`
   - Fixed all `context.request_context.app.state.background` references
   - Updated to use `get_background_state()` global function
   - Clarified SearchEvent telemetry is already implemented
   - Added note about future DI framework

2. `/home/knitli/codeweaver/claudedocs/plan-analysis-architecture-review.md`
   - Original analysis document (kept for reference)
   - Shows the investigation that led to corrections

## What Stays the Same

1. ✅ Management server separation (port 9329)
2. ✅ Rename AppState → BackgroundState
3. ✅ HTTP-first cross-platform approach
4. ✅ StatisticsMiddleware for MCP-level timing
5. ✅ Same-process architecture
6. ✅ CLI commands structure
7. ✅ ONE TOOL principle

## Ready for Implementation

The plan is now accurate and ready for implementation:
- Correct state access pattern (global getter)
- Correct telemetry architecture (two separate systems)
- No unnecessary middleware
- Aligned with existing codebase patterns
- Path forward for future DI framework noted
