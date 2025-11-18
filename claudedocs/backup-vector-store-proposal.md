<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Vector Store Backup and Failover System - Design Proposal

## Executive Summary

This proposal outlines an architecture for automatic failover to an in-memory vector store backup when the primary vector store becomes unavailable. The system leverages existing infrastructure (in-memory provider, circuit breaker, backup profile) to provide users with degraded-but-functional service within ~60 seconds of primary failure.

## Current State Analysis

### Existing Infrastructure

#### 1. In-Memory Vector Store (`MemoryVectorStoreProvider`)
- **Status**: Fully implemented with JSON persistence
- **Capabilities**:
  - Complete vector database state serialization/deserialization
  - Periodic background persistence (`_periodic_persist_task`)
  - Graceful shutdown with automatic state saving
  - Point-in-time restoration from disk
- **File**: `src/codeweaver/providers/vector_stores/inmemory.py`

#### 2. Backup Configuration Profile
- **Status**: Exists but not integrated into failover logic
- **Location**: `codeweaver.config.profiles._backup_profile()`
- **Configuration**: Uses memory provider with local embeddings (quickstart-based)
- **File**: `src/codeweaver/config/profiles.py:222-234`

#### 3. Circuit Breaker Pattern
- **Status**: Implemented in `VectorStoreProvider` base class
- **Monitoring**: Automatic health tracking with three states
  - `CLOSED`: Normal operation
  - `OPEN`: Failing, rejecting requests (after 3 failures)
  - `HALF_OPEN`: Testing recovery
- **Thresholds**: 3 consecutive failures trigger OPEN state, 30s timeout for recovery
- **File**: `src/codeweaver/providers/vector_stores/base.py:305-359`

#### 4. Provider Initialization
- **Status**: Graceful degradation but no automatic recovery
- **Current Behavior**: Logs warnings when providers fail, sets to `None`, continues
- **Location**: `Indexer._initialize_providers_async()`
- **File**: `src/codeweaver/engine/indexer/indexer.py:330-378`

### Key Gaps

1. **No Automatic Failover**: Circuit breaker detects failures but doesn't trigger backup
2. **No Resource Guards**: No memory/performance checks before backup activation
3. **No Backup Sync**: Primary → backup state transfer not implemented
4. **No User Communication**: No mechanism to inform users of degraded mode
5. **No Recovery Logic**: No automatic restoration when primary recovers

## Proposed Architecture

### 1. Failover Detection and Activation

#### Trigger Conditions
Activate backup when **any** of these occur:

1. **Circuit Breaker Opens** (3 consecutive vector store failures)
2. **Initialization Failure** (primary vector store fails to initialize)
3. **Connection Timeout** (network issues, misconfiguration)
4. **Explicit User Request** (manual failover command)

#### Activation Flow

```
Primary Fails (Circuit Breaker OPEN)
    ↓
Check Resource Constraints
    ↓
├─ Resources OK ────→ Activate Backup ────→ Notify User
│                          ↓
│                     Restore from Persist (if available)
│                          ↓
│                     Re-index if needed
│
└─ Resources LOW ───→ Warn User ──────────→ Continue WITHOUT vector store
                           ↓
                     (embeddings only, no search)
```

### 2. Resource Constraint Handling

Before activating backup, verify system can handle it:

#### Memory Estimation
```python
def estimate_backup_memory_requirements(
    project_path: Path,
    stats: IndexingStats | None = None
) -> tuple[int, bool]:
    """
    Estimate memory needed for in-memory backup.

    Returns:
        (estimated_bytes, is_safe_to_proceed)
    """
    # Estimation factors:
    # - Number of files (from stats or quick scan)
    # - Average chunk size (estimate ~500 bytes text + 768*4 bytes dense + sparse)
    # - Rough multiplier: ~5KB per chunk
    # - Safety margin: require 2x estimated + 500MB buffer

    if stats:
        estimated_chunks = stats.chunks_created or stats.files_discovered * 10
    else:
        # Quick file count estimation
        file_count = estimate_file_count(project_path)
        estimated_chunks = file_count * 10  # Conservative estimate

    # Per-chunk memory: ~5KB (text + embeddings + metadata)
    estimated_memory = estimated_chunks * 5000

    # System checks
    available_memory = psutil.virtual_memory().available
    required_memory = estimated_memory * 2 + 500_000_000  # 2x + 500MB buffer

    is_safe = available_memory > required_memory

    return estimated_memory, is_safe
```

#### Size Thresholds
- **Green Zone**: <100K chunks (~500MB) → Always safe
- **Yellow Zone**: 100K-500K chunks (500MB-2.5GB) → Check available memory
- **Red Zone**: >500K chunks (>2.5GB) → Warn user, require explicit confirmation

#### Fallback Strategy
If resources insufficient:
1. Log warning with memory estimates
2. Continue without vector store (embeddings-only mode)
3. Suggest user actions (free memory, use remote vector store, subset indexing)

### 3. Backup Persistence and Quick Recovery

#### Pre-emptive Persistence Strategy

**Option A: Continuous Sync (Recommended)**
```python
class BackupManager:
    """Manages backup persistence and state synchronization."""

    async def enable_shadow_backup(
        self,
        primary_store: VectorStoreProvider,
        backup_path: Path
    ) -> None:
        """
        Enable shadow backup that mirrors primary operations.

        - Intercepts upsert/delete operations
        - Asynchronously persists to JSON after each batch
        - Low overhead: ~5-10% performance impact
        """
        # Hook into indexer batch completion
        # After each batch indexed to primary, also persist backup
```

**Benefits**:
- Backup always current (within last batch)
- Fast activation (<10 seconds to load from disk)
- Low overhead (async writes after batches)

**Option B: Periodic Snapshots**
```python
async def schedule_backup_snapshots(
    interval_seconds: int = 300  # 5 minutes
) -> None:
    """
    Periodically snapshot primary state to backup.

    - Queries primary for all indexed chunks
    - Writes to JSON backup file
    - Lower overhead but less current
    """
```

**Benefits**:
- Minimal performance impact
- Simpler implementation
- Good enough for many use cases (5-min staleness acceptable)

**Recommendation**: Start with **Option B** (simpler), offer **Option A** as advanced feature

#### Backup File Structure
```json
{
  "version": "1.0",
  "metadata": {
    "created_at": "2025-01-15T10:30:00Z",
    "last_synced": "2025-01-15T10:35:00Z",
    "primary_provider": "qdrant_local",
    "backup_type": "continuous|snapshot",
    "project_path": "hash://abc123",
    "chunk_count": 15234,
    "file_count": 1523
  },
  "collections": {
    "codeweaver_default": {
      "metadata": {...},
      "vectors_config": {...},
      "sparse_vectors_config": {...},
      "points": [...]
    }
  }
}
```

**Location**: `{project_path}/.codeweaver/backup/vector_store.json`

### 4. Failover Implementation

#### New Class: `VectorStoreFailoverManager`

```python
class VectorStoreFailoverManager(BasedModel):
    """
    Manages failover between primary and backup vector stores.

    Responsibilities:
    - Monitor primary health via circuit breaker
    - Activate backup on failure
    - Manage state synchronization
    - Handle recovery to primary
    - User communication
    """

    primary_store: VectorStoreProvider | None
    backup_store: MemoryVectorStoreProvider | None
    active_store: VectorStoreProvider | None

    backup_enabled: bool = True
    backup_persistence_enabled: bool = True
    backup_sync_interval: int = 300  # seconds

    _circuit_monitor_task: asyncio.Task | None = None
    _sync_task: asyncio.Task | None = None
    _failover_active: bool = False

    async def initialize(
        self,
        primary_config: VectorStoreProviderSettings,
        project_path: Path,
        enable_backup: bool = True
    ) -> None:
        """Initialize primary and optionally prepare backup."""
        # Initialize primary
        self.primary_store = await self._create_provider(primary_config)
        self.active_store = self.primary_store

        if enable_backup:
            # Prepare backup configuration
            backup_config = self._create_backup_config(project_path)
            self.backup_store = await self._create_memory_provider(backup_config)

            # Start monitoring and sync tasks
            self._circuit_monitor_task = asyncio.create_task(
                self._monitor_primary_health()
            )

            if self.backup_persistence_enabled:
                self._sync_task = asyncio.create_task(
                    self._sync_backup_periodically()
                )

    async def _monitor_primary_health(self) -> None:
        """Continuously monitor primary circuit breaker state."""
        while True:
            await asyncio.sleep(5)  # Check every 5 seconds

            if self.primary_store and \
               self.primary_store.circuit_breaker_state == CircuitBreakerState.OPEN:
                # Primary failed - trigger failover
                await self._activate_failover()

            elif self._failover_active and \
                 self.primary_store and \
                 self.primary_store.circuit_breaker_state == CircuitBreakerState.CLOSED:
                # Primary recovered - consider restoring
                await self._consider_restoration()

    async def _activate_failover(self) -> None:
        """Activate backup vector store."""
        if self._failover_active:
            return  # Already in failover

        logger.warning("Primary vector store failed - activating backup")

        # 1. Resource check
        memory_estimate, is_safe = estimate_backup_memory_requirements(
            self.project_path,
            self.indexer.stats if self.indexer else None
        )

        if not is_safe:
            logger.error(
                "Insufficient resources for backup activation. "
                f"Estimated: {memory_estimate/1e9:.2f}GB, "
                f"Available: {psutil.virtual_memory().available/1e9:.2f}GB"
            )
            await self._notify_user_resource_constraint(memory_estimate)
            return

        # 2. Initialize backup if needed
        if not self.backup_store:
            self.backup_store = await self._initialize_backup_store()

        # 3. Restore from persistence if available
        backup_file = self.project_path / ".codeweaver/backup/vector_store.json"
        if backup_file.exists():
            logger.info("Restoring backup from persisted state")
            await self.backup_store._restore_from_disk()
            logger.info("Backup restored successfully")
        else:
            logger.info("No persisted backup found - will re-index")
            # Backup will be populated as indexing continues

        # 4. Switch active store
        self.active_store = self.backup_store
        self._failover_active = True

        # 5. Notify user
        await self._notify_user_failover_active()

        logger.info("Backup vector store activated successfully")

    async def _consider_restoration(self) -> None:
        """Consider restoring to primary when it recovers."""
        if not self._failover_active or not self.primary_store:
            return

        # Test primary with a simple query
        try:
            await self.primary_store.list_collections()
            # Primary is healthy - restore
            await self._restore_to_primary()
        except Exception as e:
            logger.debug(f"Primary still unhealthy: {e}")
            # Keep using backup

    async def _restore_to_primary(self) -> None:
        """Restore to primary vector store."""
        logger.info("Primary vector store recovered - restoring")

        # 1. Sync backup state to primary (if backup has newer data)
        if self.backup_store and self._has_unsync_changes():
            logger.info("Syncing backup changes to primary")
            await self._sync_backup_to_primary()

        # 2. Switch back to primary
        self.active_store = self.primary_store
        self._failover_active = False

        # 3. Notify user
        await self._notify_user_restored()

        logger.info("Restored to primary vector store")

    async def _sync_backup_periodically(self) -> None:
        """Periodically sync primary state to backup."""
        while True:
            await asyncio.sleep(self.backup_sync_interval)

            if not self._failover_active and self.primary_store:
                try:
                    await self._persist_current_state()
                except Exception as e:
                    logger.warning(f"Backup sync failed: {e}")

    async def _persist_current_state(self) -> None:
        """Persist current active store state."""
        if self.backup_store:
            await self.backup_store._persist_to_disk()
            logger.debug("Backup state persisted to disk")
```

**Location**: `src/codeweaver/engine/failover.py` (new file)

### 5. Integration with Indexer

Modify `Indexer._initialize_providers_async()`:

```python
async def _initialize_providers_async(self) -> None:
    """Initialize providers with failover support."""
    if self._providers_initialized:
        return

    # Initialize embedding providers (unchanged)
    # ...

    # Initialize vector store with failover manager
    from codeweaver.engine.failover import VectorStoreFailoverManager

    try:
        # Get vector store config
        from codeweaver.config.settings import get_settings
        settings = get_settings()

        # Create failover manager
        self._failover_manager = VectorStoreFailoverManager()

        # Initialize with failover support
        await self._failover_manager.initialize(
            primary_config=settings.provider.vector_store,
            project_path=self._checkpoint_manager.project_path,
            enable_backup=True  # Could be controlled by settings
        )

        # Use active store (initially primary)
        self._vector_store = self._failover_manager.active_store

        logger.info(
            "Vector store initialized with backup failover support: %s",
            type(self._vector_store).__name__
        )

    except Exception as e:
        logger.warning("Could not initialize vector store with failover: %s", e)
        self._vector_store = None
        self._failover_manager = None

    # ... rest of initialization
```

### 6. User Communication

#### Status Reporting

**CLI Command**: `codeweaver status`
```bash
$ codeweaver status

CodeWeaver Status Report
========================

Vector Store: ⚠️  BACKUP MODE ACTIVE
  Primary:    qdrant (localhost:6333) - DOWN
  Backup:     in-memory - ACTIVE
  Reason:     Primary connection failed
  Since:      2025-01-15 10:35:42 (5 minutes ago)

  Backup Status:
    - Restored from: /project/.codeweaver/backup/vector_store.json
    - Last sync: 2025-01-15 10:30:00 (10 minutes ago)
    - Chunks indexed: 15,234
    - Memory usage: 524 MB

  Primary Health:
    - Last check: 10 seconds ago
    - Status: Connection refused
    - Will retry automatically

Indexing:
  Files indexed: 1,523
  Chunks created: 15,234
  Status: ✓ Fully functional in backup mode

Recommendations:
  - Check Qdrant service: sudo systemctl status qdrant
  - Verify network connectivity to localhost:6333
  - Primary will automatically restore when available
```

#### Log Messages

```python
# Failover activation
logger.warning(
    "⚠️  PRIMARY VECTOR STORE UNAVAILABLE - Activating backup mode. "
    "Search functionality will continue with in-memory backup. "
    "Run 'codeweaver status' for details."
)

# Successful restoration
logger.info(
    "✓ PRIMARY VECTOR STORE RESTORED - Backup mode deactivated. "
    "Normal operation resumed."
)

# Resource constraint
logger.error(
    "❌ BACKUP ACTIVATION FAILED - Insufficient memory. "
    f"Required: {required_gb:.1f}GB, Available: {available_gb:.1f}GB. "
    "Continuing without vector store (embeddings only). "
    "Free up memory or use remote vector store for full functionality."
)
```

#### MCP Tool Response

When `find_code` is called during backup mode:

```json
{
  "matches": [...],
  "metadata": {
    "total_matches": 42,
    "search_time_ms": 156,
    "mode": "backup",
    "warning": "Currently using backup vector store. Primary unavailable since 2025-01-15T10:35:42Z"
  }
}
```

### 7. Configuration Settings

Add to `codeweaver.config.settings.Settings`:

```python
class BackupSettings(BasedModel):
    """Vector store backup configuration."""

    enabled: bool = True
    """Enable automatic failover to backup vector store"""

    sync_interval: int = 300
    """Seconds between backup syncs (default: 5 minutes)"""

    persistence_enabled: bool = True
    """Enable backup persistence to disk"""

    persistence_path: Path | None = None
    """Custom backup file path (default: .codeweaver/backup/vector_store.json)"""

    max_memory_mb: int = 2048
    """Maximum memory for backup (MB). Fail if estimate exceeds this."""

    auto_restore: bool = True
    """Automatically restore to primary when it recovers"""

    restore_delay: int = 60
    """Seconds to wait after primary recovery before restoring"""
```

Usage in `codeweaver.toml`:
```toml
[backup]
enabled = true
sync_interval = 300
persistence_enabled = true
max_memory_mb = 2048
auto_restore = true
restore_delay = 60
```

## Implementation Plan

### Phase 1: Foundation (Week 1)
1. Create `VectorStoreFailoverManager` class
2. Implement basic failover detection (circuit breaker monitoring)
3. Add resource estimation utilities
4. Integrate with `Indexer._initialize_providers_async()`

### Phase 2: Persistence (Week 1-2)
5. Implement periodic backup sync
6. Add backup file versioning and validation
7. Test restore from backup scenarios
8. Memory estimation and safety checks

### Phase 3: Recovery (Week 2)
9. Implement primary recovery detection
10. Add sync-back logic (backup → primary)
11. Automatic restoration flow
12. Manual override commands

### Phase 4: Communication (Week 2-3)
13. Add user-facing status reporting
14. Implement logging and notifications
15. CLI `status` command
16. MCP tool metadata for backup mode

### Phase 5: Testing (Week 3)
17. Integration tests for failover scenarios
18. Resource constraint testing
19. Recovery testing (primary comes back)
20. Performance benchmarking

## Testing Strategy

### Unit Tests
```python
class TestVectorStoreFailover:
    async def test_failover_on_circuit_breaker_open(self):
        """Test automatic failover when circuit breaker opens"""

    async def test_resource_constraint_prevents_activation(self):
        """Test backup activation blocked when memory insufficient"""

    async def test_backup_restore_from_persistence(self):
        """Test backup loads correctly from JSON file"""

    async def test_primary_recovery_restoration(self):
        """Test automatic restoration when primary recovers"""

    async def test_sync_backup_to_primary(self):
        """Test changes made during failover sync back to primary"""
```

### Integration Tests
```python
class TestEndToEndFailover:
    async def test_full_failover_cycle(self):
        """
        Test complete failover cycle:
        1. Index with primary
        2. Kill primary (circuit breaker opens)
        3. Verify backup activates
        4. Continue indexing on backup
        5. Restore primary
        6. Verify restoration and sync
        """

    async def test_large_codebase_failover(self):
        """Test failover with CodeWeaver itself (~52K LOC)"""
```

### Performance Tests
```python
class TestFailoverPerformance:
    def test_backup_activation_time(self):
        """Verify backup activates within 60 seconds"""

    def test_persistence_overhead(self):
        """Verify periodic sync has <5% overhead"""

    def test_memory_usage(self):
        """Verify backup memory usage matches estimates"""
```

## Success Criteria

1. **Activation Speed**: Backup activates within 60 seconds of primary failure
2. **Functionality**: Search works identically in backup mode (for indexed data)
3. **Persistence**: Backup restores within 10 seconds from JSON
4. **Memory Safety**: Never activate backup if memory insufficient
5. **Recovery**: Automatically restores to primary within 120 seconds of recovery
6. **Transparency**: Clear user communication about backup mode
7. **Performance**: <5% overhead from backup persistence

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Backup activation OOM kills process | High | Pre-flight memory checks, conservative estimates |
| Backup out of sync with primary | Medium | Periodic syncs (5 min), timestamp validation |
| Slow backup activation | Medium | Pre-persist backups, optimize JSON serialization |
| User confusion about backup mode | Low | Clear status reporting, prominent warnings |
| Backup fails to restore | Medium | Graceful degradation, re-index if needed |

## Future Enhancements

1. **Multi-level Backup**: Local memory → Remote memory → Degraded mode
2. **Partial Backup**: Backup most-used collections only (memory optimization)
3. **Smart Sync**: Only sync changed chunks (delta persistence)
4. **User Control**: Manual failover/restore commands
5. **Metrics**: Track failover frequency, backup usage patterns
6. **Cloud Backup**: S3/GCS backup storage option

## Conclusion

This proposal leverages CodeWeaver's existing infrastructure to provide robust failover with minimal new code. The in-memory provider's persistence capabilities, combined with the circuit breaker pattern, create a solid foundation for automatic backup.

Key advantages:
- **Builds on existing code**: ~70% of needed functionality already exists
- **Fast activation**: Target <60s from failure to functional backup
- **Resource safe**: Conservative memory checks prevent OOM issues
- **Transparent**: Clear communication keeps users informed
- **Automatic recovery**: Minimal user intervention required

The implementation can be delivered incrementally over 3 weeks, with each phase providing incremental value.
