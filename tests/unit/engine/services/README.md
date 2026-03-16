<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Engine Services Test Suite

This directory contains comprehensive test suites for engine services, particularly focusing on state machine integrity and correctness.

## Migration State Machine Tests

**File**: `test_migration_state_machine.py`

### Overview

Comprehensive state machine test suite for the migration service. These tests MUST pass before any migration implementation code is written (P0 blocker from Phase 1 of unified implementation plan).

### Test Coverage

#### 1. Valid State Transitions (`TestValidStateTransitions`)
- **Purpose**: Verify all valid state transitions work correctly
- **Coverage**: 7 test methods
- **Tests**:
  - `test_all_valid_state_transitions()` - Comprehensive check of all valid transitions
  - `test_pending_to_in_progress()` - PENDING → IN_PROGRESS
  - `test_in_progress_to_completed()` - IN_PROGRESS → COMPLETED
  - `test_in_progress_to_failed()` - IN_PROGRESS → FAILED
  - `test_failed_to_pending_retry()` - FAILED → PENDING (retry)
  - `test_completed_to_rollback()` - COMPLETED → ROLLBACK
  - `test_rollback_to_pending()` - ROLLBACK → PENDING

#### 2. Invalid State Transitions (`TestInvalidStateTransitions`)
- **Purpose**: Ensure invalid transitions are properly rejected
- **Coverage**: 2 test methods, 14 invalid transition scenarios
- **Tests**:
  - `test_invalid_state_transitions()` - Comprehensive invalid transition testing
  - `test_no_self_transitions()` - Verify no state can transition to itself

**Invalid Transition Scenarios**:
```
PENDING → COMPLETED (skip in_progress)
PENDING → FAILED (can't fail before starting)
PENDING → ROLLBACK (can't rollback before starting)
COMPLETED → PENDING (can't go back directly)
COMPLETED → IN_PROGRESS (can't restart)
COMPLETED → FAILED (already completed)
IN_PROGRESS → PENDING (can't go backward)
IN_PROGRESS → ROLLBACK (invalid path)
FAILED → COMPLETED (can't succeed after failure)
FAILED → IN_PROGRESS (must retry from PENDING)
FAILED → ROLLBACK (can't rollback failure)
ROLLBACK → COMPLETED (can't complete rollback)
ROLLBACK → FAILED (can't fail rollback)
ROLLBACK → IN_PROGRESS (must retry from PENDING)
```

#### 3. State Transition Atomicity (`TestStateTransitionAtomicity`)
- **Purpose**: Verify state transitions are atomic and handle failures correctly
- **Coverage**: 2 test methods
- **Tests**:
  - `test_state_transitions_are_atomic()` - No partial updates on failure
  - `test_transition_preserves_migration_id()` - ID preserved across transitions

#### 4. State Reachability (`TestStateReachability`)
- **Purpose**: Verify all states are reachable and state machine is connected
- **Coverage**: 3 test methods
- **Tests**:
  - `test_all_states_reachable_from_pending()` - All states reachable from initial state
  - `test_state_machine_is_connected()` - State machine forms connected graph
  - `test_no_unreachable_states()` - No dead-end states exist

#### 5. State Persistence (`TestStatePersistence`)
- **Purpose**: Verify migration states can be persisted and restored
- **Coverage**: 2 test methods (1 parametrized across all states)
- **Tests**:
  - `test_state_persistence()` - Parametrized test for all 5 states
  - `test_persistence_preserves_metadata()` - Metadata preserved through save/load

#### 6. Concurrent State Transitions (`TestConcurrentStateTransitions`)
- **Purpose**: Verify state transitions are safe under concurrent access
- **Coverage**: 2 async test methods
- **Tests**:
  - `test_concurrent_state_transitions()` - Concurrent transitions to same state
  - `test_concurrent_different_transitions()` - Concurrent transitions to different states

#### 7. Property-Based Tests (`TestStateMachineProperties`)
- **Purpose**: Property-based testing of state machine invariants
- **Status**: Placeholder (requires hypothesis library)
- **Coverage**: 1 test method (currently skipped)
- **Planned Properties**:
  - Property 1: Every state has valid transitions or is terminal
  - Property 2: No state can transition to itself
  - Property 3: All transitions preserve migration ID

#### 8. State Machine Documentation (`TestStateMachineDocumentation`)
- **Purpose**: Verify state machine is properly documented
- **Coverage**: 2 test methods
- **Tests**:
  - `test_all_states_documented()` - All states appear in VALID_TRANSITIONS
  - `test_state_machine_diagram_accuracy()` - Diagram matches implementation

#### 9. Edge Cases (`TestStateTransitionEdgeCases`)
- **Purpose**: Test boundary conditions and edge cases
- **Coverage**: 3 test methods
- **Tests**:
  - `test_rapid_state_transitions()` - Rapid sequential transitions
  - `test_state_transition_with_metadata()` - Metadata handling during transitions
  - `test_transition_error_messages()` - Clear, actionable error messages

### State Machine Definition

```python
class MigrationState(Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    ROLLBACK = "rollback"
```

**State Transition Diagram**:
```
PENDING → IN_PROGRESS → COMPLETED → ROLLBACK → PENDING
                      ↓
                    FAILED → PENDING
```

**Valid Transitions**:
- `PENDING` → `IN_PROGRESS`
- `IN_PROGRESS` → `COMPLETED`, `FAILED`
- `FAILED` → `PENDING` (retry)
- `COMPLETED` → `ROLLBACK`
- `ROLLBACK` → `PENDING`

### Test Statistics

- **Total Test Classes**: 9
- **Total Test Methods**: ~30
- **Parametrized Tests**: 5 (one per state)
- **Async Tests**: 2
- **Property Tests**: 1 (placeholder)
- **Coverage Target**: 100% state machine coverage

### Running Tests

```bash
# Run all state machine tests
pytest tests/unit/engine/services/test_migration_state_machine.py -v

# Run specific test class
pytest tests/unit/engine/services/test_migration_state_machine.py::TestValidStateTransitions -v

# Run with coverage
pytest tests/unit/engine/services/test_migration_state_machine.py --cov=codeweaver.engine.services

# Run only async tests
pytest tests/unit/engine/services/test_migration_state_machine.py -m async_test
```

### Test Utilities

The test file includes comprehensive helper functions for testing:

- `create_migration(state)` - Create migration in specified state
- `can_transition(migration, target)` - Check if transition is valid
- `transition(migration, target)` - Perform state transition
- `transition_async(migration, target)` - Async state transition
- `get_valid_transitions(state)` - Get valid transitions from state
- `find_path(start, target)` - Find path between states using BFS
- `save_migration(migration)` - Mock persistence
- `load_migration(data)` - Mock deserialization
- `inject_failure_during_transition()` - Context manager for testing atomicity

### Quality Requirements

**From Implementation Plan (lines 376-499)**:

✅ **100% state machine coverage** - All states and transitions tested
✅ **All invalid transitions tested** - 14 invalid scenarios covered
✅ **Atomic transaction testing** - Atomicity tests included
✅ **Concurrent safety testing** - 2 async concurrency tests
✅ **Property-based tests** - Placeholder ready for hypothesis
✅ **State persistence** - All states tested for save/load
✅ **Reachability analysis** - Complete graph connectivity tests

### Next Steps

1. **Add hypothesis to test dependencies** - Enable property-based tests
2. **Implement actual migration service** - Use these tests as specification
3. **Add integration tests** - Test against real database
4. **Performance testing** - Measure state transition latency
5. **Stress testing** - High concurrency scenarios

### Notes

- All tests are currently using **mock implementations** (no real migration service exists yet)
- Tests are designed to **fail initially** and serve as the specification
- Real implementation should replace mock helper functions with actual service calls
- Async tests use `asyncio.Lock` to simulate database transaction isolation
- Property-based tests require `hypothesis` library (not yet in dependencies)

### Meta-Test

The file includes `test_suite_completeness()` which verifies all required test categories exist and have test methods. This ensures the test suite meets the requirements from the unified implementation plan.

### Contributing

When implementing the migration service:

1. **Start with these tests** - They define the contract
2. **Replace mock helpers** - Use real service implementations
3. **All tests must pass** - This is a P0 blocker requirement
4. **Add integration tests** - Test with real database transactions
5. **Maintain 100% coverage** - Add tests for any new states or transitions
