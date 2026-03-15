<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Migration State Machine Specification

## Visual State Diagram

```
                                  ┌─────────────┐
                             ┌────┤   PENDING   │◄────┐
                             │    └─────────────┘     │
                             │                        │
                             │ start                  │ retry
                             │                        │
                             ▼                        │
                      ┌──────────────┐                │
                      │ IN_PROGRESS  │                │
                      └──────────────┘                │
                            ╱  ╲                      │
                           ╱    ╲                     │
                 success  ╱      ╲  failure           │
                         ╱        ╲                   │
                        ╱          ╲                  │
                       ▼            ▼                 │
              ┌─────────────┐  ┌─────────┐           │
              │  COMPLETED  │  │ FAILED  │───────────┘
              └─────────────┘  └─────────┘
                     │
                     │ rollback
                     │
                     ▼
              ┌─────────────┐
              │  ROLLBACK   │
              └─────────────┘
                     │
                     │ retry
                     └─────────────────────────────────┐
                                                       │
                                                       ▼
                                                ┌─────────────┐
                                                │   PENDING   │
                                                └─────────────┘
```

## State Definitions

### PENDING
- **Description**: Initial state for new migrations
- **Entry**: Migration created OR retry after failure/rollback
- **Exit**: Transition to IN_PROGRESS when migration starts
- **Valid Transitions**:
  - → IN_PROGRESS (start migration)
- **Invalid Transitions**:
  - → COMPLETED (must go through IN_PROGRESS)
  - → FAILED (can't fail before starting)
  - → ROLLBACK (can't rollback before starting)
  - → PENDING (can't transition to self)

### IN_PROGRESS
- **Description**: Migration is currently executing
- **Entry**: Start migration from PENDING
- **Exit**: Complete successfully OR fail during execution
- **Valid Transitions**:
  - → COMPLETED (migration succeeds)
  - → FAILED (migration fails)
- **Invalid Transitions**:
  - → PENDING (can't go backward)
  - → ROLLBACK (must complete first)
  - → IN_PROGRESS (can't transition to self)

### COMPLETED
- **Description**: Migration executed successfully
- **Entry**: Successful completion from IN_PROGRESS
- **Exit**: Initiate rollback if needed
- **Valid Transitions**:
  - → ROLLBACK (rollback completed migration)
- **Invalid Transitions**:
  - → PENDING (can't retry completed migration directly)
  - → IN_PROGRESS (can't re-execute)
  - → FAILED (already succeeded)
  - → COMPLETED (can't transition to self)

### FAILED
- **Description**: Migration failed during execution
- **Entry**: Failure during IN_PROGRESS
- **Exit**: Retry from PENDING
- **Valid Transitions**:
  - → PENDING (retry migration)
- **Invalid Transitions**:
  - → COMPLETED (can't succeed after failure without retry)
  - → IN_PROGRESS (must retry from PENDING)
  - → ROLLBACK (can't rollback failed migration)
  - → FAILED (can't transition to self)

### ROLLBACK
- **Description**: Rolling back a completed migration
- **Entry**: Rollback initiated from COMPLETED
- **Exit**: Retry from PENDING after rollback
- **Valid Transitions**:
  - → PENDING (retry after rollback)
- **Invalid Transitions**:
  - → COMPLETED (can't complete a rollback)
  - → IN_PROGRESS (must retry from PENDING)
  - → FAILED (can't fail a rollback)
  - → ROLLBACK (can't transition to self)

## State Machine Properties

### Graph Properties

- **States**: 5 (PENDING, IN_PROGRESS, COMPLETED, FAILED, ROLLBACK)
- **Transitions**: 6 valid transitions
- **Initial State**: PENDING
- **Terminal States**: None (all states can transition to another state)
- **Strongly Connected**: Yes (all states reachable from any state through PENDING)

### Invariants

1. **No Self-Transitions**: No state can transition to itself
2. **Single Initial State**: All migrations start at PENDING
3. **Reachability**: All states reachable from PENDING
4. **Determinism**: Same transition always produces same result
5. **ID Preservation**: Migration ID never changes during transitions
6. **Atomicity**: State transitions are atomic (no partial updates)

## Transition Rules

### Success Path
```
PENDING → IN_PROGRESS → COMPLETED → ROLLBACK → PENDING
```

### Failure Path
```
PENDING → IN_PROGRESS → FAILED → PENDING
```

### Retry Scenarios

**After Failure**:
```
FAILED → PENDING → IN_PROGRESS → ...
```

**After Rollback**:
```
ROLLBACK → PENDING → IN_PROGRESS → ...
```

## State Transition Matrix

|              | PENDING | IN_PROGRESS | COMPLETED | FAILED | ROLLBACK |
|--------------|---------|-------------|-----------|--------|----------|
| **PENDING**      | ❌      | ✅          | ❌        | ❌     | ❌       |
| **IN_PROGRESS**  | ❌      | ❌          | ✅        | ✅     | ❌       |
| **COMPLETED**    | ❌      | ❌          | ❌        | ❌     | ✅       |
| **FAILED**       | ✅      | ❌          | ❌        | ❌     | ❌       |
| **ROLLBACK**     | ✅      | ❌          | ❌        | ❌     | ❌       |

Legend:
- ✅ = Valid transition
- ❌ = Invalid transition (will raise `InvalidStateTransitionError`)

## Usage Examples

### Normal Migration Flow

```python
# Create new migration
migration = create_migration(MigrationState.PENDING)

# Start migration
migration = transition(migration, MigrationState.IN_PROGRESS)

# Complete successfully
migration = transition(migration, MigrationState.COMPLETED)

# Current state: COMPLETED
```

### Migration with Failure and Retry

```python
# Create new migration
migration = create_migration(MigrationState.PENDING)

# Start migration
migration = transition(migration, MigrationState.IN_PROGRESS)

# Migration fails
migration = transition(migration, MigrationState.FAILED)

# Retry migration
migration = transition(migration, MigrationState.PENDING)
migration = transition(migration, MigrationState.IN_PROGRESS)
migration = transition(migration, MigrationState.COMPLETED)

# Current state: COMPLETED
```

### Migration with Rollback

```python
# Migration is completed
migration = create_migration(MigrationState.COMPLETED)

# Rollback the migration
migration = transition(migration, MigrationState.ROLLBACK)

# Retry after rollback
migration = transition(migration, MigrationState.PENDING)
migration = transition(migration, MigrationState.IN_PROGRESS)
migration = transition(migration, MigrationState.COMPLETED)

# Current state: COMPLETED
```

### Invalid Transition (Raises Exception)

```python
# Create new migration
migration = create_migration(MigrationState.PENDING)

# Try to skip IN_PROGRESS (INVALID!)
try:
    migration = transition(migration, MigrationState.COMPLETED)
except InvalidStateTransitionError as e:
    print(f"Error: {e}")
    # Output: Invalid state transition: pending -> completed
```

## Concurrency Considerations

### Async Lock Usage

```python
async def safe_transition(migration, target_state):
    """Safely transition with concurrent access protection."""
    async with migration._transition_lock:
        if not can_transition(migration, target_state):
            raise InvalidStateTransitionError(...)

        # Atomic state update
        migration.current_state = target_state
        return migration
```

### Race Condition Prevention

- Lock acquired before state check
- State validation and update in single critical section
- Lock released after update complete

## Persistence and Recovery

### Save/Load Cycle

```python
# Save migration state
data = save_migration(migration)
# data = {"id": "...", "current_state": "completed", ...}

# Load migration state
restored = load_migration(data)
assert restored.current_state == migration.current_state
assert restored.id == migration.id
```

### Recovery Scenarios

**After System Crash**:
1. Load migration from persistent storage
2. Check current state
3. Determine recovery action based on state:
   - PENDING: Can start fresh
   - IN_PROGRESS: May need rollback or retry
   - COMPLETED: No action needed
   - FAILED: Ready for retry
   - ROLLBACK: Continue rollback or retry

## Testing Requirements

### Coverage Requirements

- ✅ All valid transitions tested
- ✅ All invalid transitions tested
- ✅ State persistence tested
- ✅ Concurrent transitions tested
- ✅ Atomicity tested
- ✅ Reachability tested

### Test Categories

1. Valid transitions (7 tests)
2. Invalid transitions (2 tests, 14 scenarios)
3. Atomicity (2 tests)
4. Reachability (3 tests)
5. Persistence (2 tests)
6. Concurrency (2 tests)
7. Properties (4 tests)
8. Documentation (2 tests)
9. Edge cases (3 tests)

## Implementation Notes

### Database Schema Requirements

```sql
CREATE TABLE migrations (
    id UUID PRIMARY KEY,
    current_state VARCHAR(20) NOT NULL,
    created_at TIMESTAMP NOT NULL,
    updated_at TIMESTAMP NOT NULL,
    metadata JSONB,
    CONSTRAINT valid_state CHECK (
        current_state IN ('pending', 'in_progress', 'completed', 'failed', 'rollback')
    )
);

CREATE INDEX idx_migrations_state ON migrations(current_state);
```

### Transaction Isolation

- Use `SERIALIZABLE` or `REPEATABLE READ` isolation level
- State transitions must be atomic
- Lock migration row during state update
- Rollback on any failure during transition

### Error Handling

```python
class InvalidStateTransitionError(Exception):
    """Raised when invalid state transition is attempted."""

    def __init__(self, current: str, target: str):
        super().__init__(
            f"Invalid state transition: {current} -> {target}"
        )
        self.current_state = current
        self.target_state = target
```

## References

- Implementation Plan: `/home/knitli/codeweaver/claudedocs/unified-implementation-plan.md` (lines 376-499)
- Test Suite: `/home/knitli/codeweaver/tests/unit/engine/services/test_migration_state_machine.py`
- Documentation: `/home/knitli/codeweaver/tests/unit/engine/services/README.md`
