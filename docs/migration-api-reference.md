<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Migration System API Reference

Complete API reference for CodeWeaver's embedding configuration migration system.

## Table of Contents

- [ConfigChangeAnalyzer](#configchangeanalyzer)
- [MigrationService](#migrationservice)
- [Collection Policies](#collection-policies)
- [Profile Management](#profile-management)
- [CLI Commands](#cli-commands)
- [Type Definitions](#type-definitions)

---

## ConfigChangeAnalyzer

Analyzes embedding configuration changes for compatibility and migration requirements.

### Class Definition

```python
from codeweaver.engine.services.config_analyzer import ConfigChangeAnalyzer

class ConfigChangeAnalyzer:
    """Analyzes configuration changes for compatibility.

    This service determines if config changes require reindexing,
    can be safely migrated, or are incompatible.
    """

    def __init__(
        self,
        settings: Settings,
        checkpoint_manager: CheckpointManager,
        manifest_manager: FileManifestManager,
    ) -> None:
        """Initialize analyzer with dependencies."""
```

### Methods

#### analyze_current_config

Analyze current configuration against existing collection.

```python
async def analyze_current_config(
    self
) -> ConfigChangeAnalysis | None:
    """Analyze current config against existing collection.

    Returns:
        Analysis result, or None if no collection exists yet.

    Example:
        >>> analyzer = get_config_analyzer()
        >>> analysis = await analyzer.analyze_current_config()
        >>> if analysis and analysis.requires_action:
        ...     print(f"Action needed: {analysis.action_required}")
    """
```

**Returns**: `ConfigChangeAnalysis` with:
- `is_compatible`: Boolean indicating if change is safe
- `action_required`: `"none"`, `"migrate"`, or `"reindex"`
- `breaking_changes`: List of incompatible changes
- `warnings`: List of potential issues
- `safe_migrations`: List of available migration paths

**Example**:
```python
from codeweaver.config import Settings
from codeweaver.engine.services import get_config_analyzer

# Get analyzer instance (uses DI)
settings = Settings()
analyzer = get_config_analyzer(settings)

# Analyze current config
analysis = await analyzer.analyze_current_config()

if analysis is None:
    print("No existing collection - safe to index")
elif analysis.is_compatible:
    print("Config change is compatible")
    if analysis.action_required == "migrate":
        print("Migration recommended")
elif not analysis.is_compatible:
    print("Breaking changes detected:")
    for change in analysis.breaking_changes:
        print(f"  - {change}")
```

#### analyze_config_change

Analyze a specific configuration change.

```python
async def analyze_config_change(
    self,
    old_config: EmbeddingConfig,
    new_config: EmbeddingConfig,
) -> ConfigChangeAnalysis:
    """Analyze specific config change.

    Args:
        old_config: Current embedding configuration
        new_config: Proposed embedding configuration

    Returns:
        Detailed analysis of the configuration change

    Example:
        >>> old_cfg = EmbeddingConfig(model="voyage-code-3", dimension=2048)
        >>> new_cfg = EmbeddingConfig(model="voyage-code-3", dimension=512)
        >>> analysis = await analyzer.analyze_config_change(old_cfg, new_cfg)
        >>> print(f"Migration strategy: {analysis.migration_strategy}")
    """
```

**Example**:
```python
from codeweaver.config import EmbeddingConfig

# Define configurations
old_config = EmbeddingConfig(
    model="voyage-code-3",
    dimension=2048,
    datatype="float32",
)

new_config = EmbeddingConfig(
    model="voyage-code-3",
    dimension=512,  # Dimension reduction
    datatype="int8",  # Quantization
)

# Analyze the change
analysis = await analyzer.analyze_config_change(old_config, new_config)

# Check results
if analysis.is_compatible:
    print(f"Migration strategy: {analysis.migration_strategy}")
    print(f"Expected impact: {analysis.estimated_accuracy_impact}%")
    print(f"Storage savings: {analysis.storage_reduction}%")
else:
    print("Reindex required:")
    for reason in analysis.breaking_changes:
        print(f"  - {reason}")
```

#### validate_config_change

Validate configuration change against collection policy.

```python
async def validate_config_change(
    self,
    new_config: EmbeddingConfig,
) -> None:
    """Validate config change against collection policy.

    Args:
        new_config: Proposed configuration

    Raises:
        ConfigurationLockError: If change violates policy

    Example:
        >>> try:
        ...     await analyzer.validate_config_change(new_config)
        ... except ConfigurationLockError as e:
        ...     print(f"Policy violation: {e}")
    """
```

**Example**:
```python
from codeweaver.exceptions import ConfigurationLockError

new_config = EmbeddingConfig(
    model="openai/text-embedding-3-large",  # Different family
    dimension=3072,
)

try:
    await analyzer.validate_config_change(new_config)
    print("Config change is allowed by policy")
except ConfigurationLockError as e:
    print(f"Policy blocked change: {e}")
    print("Consider:")
    print("  1. Using a compatible model within the same family")
    print("  2. Changing collection policy to FLEXIBLE or UNLOCKED")
    print("  3. Reindexing with new model")
```

---

## MigrationService

Handles collection migrations with checkpointing, parallel processing, and rollback support.

### Class Definition

```python
from codeweaver.engine.services.migration_service import MigrationService

class MigrationService:
    """Handles collection migrations.

    Features:
    - Parallel worker pool for scalability
    - Checkpoint/resume capability
    - Data integrity validation
    - Retry logic with exponential backoff
    """

    def __init__(
        self,
        vector_store: VectorStoreProvider,
        config_analyzer: ConfigChangeAnalyzer,
        checkpoint_manager: CheckpointManager,
        manifest_manager: FileManifestManager,
        worker_pool_config: WorkerPoolConfig = WorkerPoolConfig(),
    ) -> None:
        """Initialize migration service."""
```

### Methods

#### migrate_collection

Migrate entire collection to new configuration.

```python
async def migrate_collection(
    self,
    target_config: EmbeddingConfig,
    *,
    workers: int = 4,
    checkpoint_interval: int = 1000,
    validate: bool = True,
) -> MigrationResult:
    """Migrate collection to target configuration.

    Args:
        target_config: Target embedding configuration
        workers: Number of parallel workers
        checkpoint_interval: Vectors between checkpoints
        validate: Whether to validate after migration

    Returns:
        Migration result with statistics

    Example:
        >>> service = get_migration_service()
        >>> result = await service.migrate_collection(
        ...     target_config,
        ...     workers=4,
        ...     checkpoint_interval=1000,
        ... )
        >>> print(f"Migrated {result.vectors_processed} vectors")
    """
```

**Example**:
```python
from codeweaver.config import EmbeddingConfig
from codeweaver.engine.services import get_migration_service

# Get service instance
service = get_migration_service()

# Define target configuration
target_config = EmbeddingConfig(
    model="voyage-code-3",
    dimension=512,
    datatype="int8",
)

# Run migration with options
result = await service.migrate_collection(
    target_config,
    workers=4,  # Use 4 parallel workers
    checkpoint_interval=1000,  # Checkpoint every 1000 vectors
    validate=True,  # Validate after completion
)

# Check results
print(f"Status: {result.status}")
print(f"Vectors processed: {result.vectors_processed}")
print(f"Duration: {result.duration_seconds}s")
print(f"Throughput: {result.vectors_per_second} vectors/sec")

if result.errors:
    print(f"Errors encountered: {len(result.errors)}")
    for error in result.errors[:5]:  # Show first 5
        print(f"  - {error}")
```

#### migrate_dimensions_parallel

Migrate dimensions with parallel processing.

```python
async def migrate_dimensions_parallel(
    self,
    old_dimension: int,
    new_dimension: int,
    *,
    workers: int = 4,
    batch_size: int = 100,
    checkpoint_interval: int = 1000,
) -> MigrationResult:
    """Migrate dimensions using parallel workers.

    Args:
        old_dimension: Current vector dimension
        new_dimension: Target vector dimension
        workers: Number of parallel workers
        batch_size: Vectors per batch
        checkpoint_interval: Vectors between checkpoints

    Returns:
        Migration result with statistics

    Example:
        >>> result = await service.migrate_dimensions_parallel(
        ...     old_dimension=2048,
        ...     new_dimension=512,
        ...     workers=8,
        ... )
    """
```

**Example**:
```python
# High-performance dimension reduction
result = await service.migrate_dimensions_parallel(
    old_dimension=2048,
    new_dimension=512,
    workers=8,  # More workers for faster processing
    batch_size=500,  # Larger batches
    checkpoint_interval=5000,  # Less frequent checkpoints
)

print(f"Reduced dimensions in {result.duration_seconds}s")
print(f"Performance: {result.vectors_per_second} vectors/sec")
```

#### migrate_quantization

Migrate datatype (quantization).

```python
async def migrate_quantization(
    self,
    old_datatype: str,
    new_datatype: str,
    *,
    workers: int = 4,
    validate_precision: bool = True,
) -> MigrationResult:
    """Migrate vector datatype (quantization).

    Args:
        old_datatype: Current datatype (e.g., "float32")
        new_datatype: Target datatype (e.g., "int8")
        workers: Number of parallel workers
        validate_precision: Validate precision after conversion

    Returns:
        Migration result with statistics

    Example:
        >>> result = await service.migrate_quantization(
        ...     old_datatype="float32",
        ...     new_datatype="int8",
        ... )
    """
```

**Example**:
```python
# Quantize to int8 for storage optimization
result = await service.migrate_quantization(
    old_datatype="float32",
    new_datatype="int8",
    workers=4,
    validate_precision=True,  # Check precision loss
)

if result.status == "completed":
    print(f"Storage reduced by ~75%")
    print(f"Precision impact: {result.precision_impact}%")
```

#### resume_migration

Resume interrupted migration.

```python
async def resume_migration(
    self,
    *,
    workers: int = 4,
) -> MigrationResult:
    """Resume interrupted migration from last checkpoint.

    Args:
        workers: Number of parallel workers

    Returns:
        Migration result

    Raises:
        MigrationError: If no checkpoint to resume from

    Example:
        >>> result = await service.resume_migration(workers=4)
    """
```

**Example**:
```python
# Resume after interruption (Ctrl+C, crash, etc.)
try:
    result = await service.resume_migration(workers=4)
    print(f"Resumed from checkpoint")
    print(f"Remaining vectors: {result.vectors_remaining}")
except MigrationError as e:
    print(f"Cannot resume: {e}")
    print("No checkpoint found or migration already complete")
```

#### rollback_migration

Rollback to previous configuration.

```python
async def rollback_migration(
    self,
    checkpoint_id: str | None = None,
) -> RollbackResult:
    """Rollback migration to previous state.

    Args:
        checkpoint_id: Specific checkpoint to restore, or latest if None

    Returns:
        Rollback result

    Example:
        >>> result = await service.rollback_migration()
        >>> print(f"Rolled back to {result.checkpoint_id}")
    """
```

**Example**:
```python
# Rollback to last checkpoint
result = await service.rollback_migration()

print(f"Rolled back to: {result.checkpoint_id}")
print(f"Restored config: {result.restored_config}")
print(f"Vectors restored: {result.vectors_restored}")

# Rollback to specific checkpoint
result = await service.rollback_migration(
    checkpoint_id="checkpoint_20250212_143022"
)
```

#### validate_migration

Validate migration integrity.

```python
async def validate_migration(
    self,
    sample_size: int = 1000,
) -> ValidationResult:
    """Validate migration data integrity.

    Args:
        sample_size: Number of vectors to validate

    Returns:
        Validation result with statistics

    Example:
        >>> result = await service.validate_migration(sample_size=1000)
        >>> print(f"Validation: {result.status}")
    """
```

**Example**:
```python
# Validate migration quality
result = await service.validate_migration(sample_size=1000)

if result.is_valid:
    print(f"✅ Migration validated successfully")
    print(f"Sampled {result.samples_checked} vectors")
    print(f"Error rate: {result.error_rate}%")
else:
    print(f"❌ Validation failed")
    print(f"Issues found: {len(result.issues)}")
    for issue in result.issues:
        print(f"  - {issue}")
```

---

## Collection Policies

### CollectionPolicy Enum

```python
from codeweaver.core.types import CollectionPolicy

class CollectionPolicy(BaseEnum):
    """Collection modification policy."""

    STRICT = "strict"              # No model changes
    FAMILY_AWARE = "family_aware"  # Allow query changes in family
    FLEXIBLE = "flexible"          # Warn on breaking changes
    UNLOCKED = "unlocked"          # Allow all changes
```

### Policy Configuration

```python
from codeweaver.engine.indexer.manifest import CollectionMetadata

class CollectionMetadata(BasedModel):
    """Collection metadata with policy enforcement."""

    policy: CollectionPolicy = CollectionPolicy.FAMILY_AWARE

    def validate_config_change(
        self,
        new_config: EmbeddingConfig,
    ) -> None:
        """Validate change against policy.

        Raises:
            ConfigurationLockError: If change violates policy
        """
```

**Example**:
```python
from codeweaver.core.types import CollectionPolicy
from codeweaver.config import EmbeddingConfig

# Load collection metadata
metadata = await manifest_manager.load_manifest()

# Check current policy
print(f"Current policy: {metadata.policy}")

# Update policy
metadata.policy = CollectionPolicy.FLEXIBLE
await manifest_manager.save_manifest(metadata)

# Validate a change against policy
new_config = EmbeddingConfig(model="new-model")
try:
    metadata.validate_config_change(new_config)
except ConfigurationLockError as e:
    print(f"Policy violation: {e}")
```

### Policy Comparison

| Policy | Model Changes | Dimension Changes | Quantization | Breaking Changes |
|--------|--------------|-------------------|--------------|------------------|
| **STRICT** | ❌ None | ❌ None | ❌ None | ❌ Blocked |
| **FAMILY_AWARE** | ✅ Within family | ✅ Matryoshka only | ✅ Allowed | ❌ Blocked |
| **FLEXIBLE** | ⚠️ Most allowed | ⚠️ Most allowed | ✅ Allowed | ⚠️ Warning |
| **UNLOCKED** | ✅ All allowed | ✅ All allowed | ✅ All allowed | ✅ Allowed |

---

## Profile Management

### VersionedProfile

```python
from codeweaver.config.profiles import VersionedProfile

@dataclass
class VersionedProfile:
    """Profile with version tracking."""

    name: str
    version: str  # Semantic version
    embedding_config: EmbeddingConfig
    changelog: list[str]

    @classmethod
    def is_compatible_with(
        cls,
        profile_version: str,
        collection_version: str,
    ) -> bool:
        """Check if profile versions are compatible.

        Args:
            profile_version: Profile semantic version
            collection_version: Collection semantic version

        Returns:
            True if major versions match
        """
```

**Example**:
```python
from codeweaver.config.profiles import VersionedProfile, RECOMMENDED

# Check built-in profile
profile = RECOMMENDED
print(f"Profile: {profile.name}")
print(f"Version: {profile.version}")
print(f"Config: {profile.embedding_config}")

# Check compatibility
compatible = VersionedProfile.is_compatible_with(
    profile_version="0.3.0",
    collection_version="0.3.5",
)
print(f"Compatible: {compatible}")  # True (major version matches)

# Create custom profile
from codeweaver.config import EmbeddingConfig

custom_profile = VersionedProfile(
    name="my_profile",
    version="1.0.0",
    embedding_config=EmbeddingConfig(
        model="voyage-code-3",
        dimension=1024,
    ),
    changelog=[
        "1.0.0: Initial custom profile for project X",
    ],
)
```

### Built-in Profiles

```python
from codeweaver.config.profiles import (
    RECOMMENDED,  # Optimal balance
    FAST,         # Fast indexing
    ACCURATE,     # Best accuracy
)

# RECOMMENDED profile (default)
print(f"Recommended: {RECOMMENDED.embedding_config.model}")
# Output: voyage-4-large + voyage-4-nano (asymmetric)

# FAST profile
print(f"Fast: {FAST.embedding_config.model}")
# Output: voyage-code-3 @ 512 dimensions

# ACCURATE profile
print(f"Accurate: {ACCURATE.embedding_config.model}")
# Output: voyage-4-large @ 2048 dimensions
```

---

## CLI Commands

### codeweaver config

Configuration management commands.

#### config validate

```bash
codeweaver config validate [OPTIONS]
```

Validate configuration against existing collection.

**Options**:
- `--show-details`: Show detailed analysis
- `--json`: Output in JSON format

**Example**:
```bash
# Basic validation
codeweaver config validate

# With details
codeweaver config validate --show-details

# JSON output for scripting
codeweaver config validate --json > validation.json
```

#### config analyze

```bash
codeweaver config analyze [OPTIONS]
```

Analyze configuration change impact.

**Options**:
- `--preview`: Show preview without applying
- `--show-alternatives`: Show alternative migration paths
- `--detailed`: Show detailed impact analysis

**Example**:
```bash
# Analyze current config
codeweaver config analyze

# Preview migration
codeweaver config analyze --preview

# Show alternatives
codeweaver config analyze --show-alternatives
```

#### config set-policy

```bash
codeweaver config set-policy POLICY
```

Set collection policy.

**Arguments**:
- `POLICY`: One of `strict`, `family_aware`, `flexible`, `unlocked`

**Example**:
```bash
# Set to flexible for experimentation
codeweaver config set-policy flexible

# Lock down for production
codeweaver config set-policy strict
```

### codeweaver migrate

Migration management commands.

#### migrate apply

```bash
codeweaver migrate apply [OPTIONS]
```

Apply pending migration.

**Options**:
- `--workers N`: Number of parallel workers (default: 4)
- `--checkpoint-interval N`: Vectors between checkpoints (default: 1000)
- `--batch-size N`: Vectors per batch (default: 100)
- `--validate / --no-validate`: Validate after migration (default: validate)
- `--dry-run`: Preview without applying

**Example**:
```bash
# Basic migration
codeweaver migrate apply

# High-performance migration
codeweaver migrate apply \
  --workers 8 \
  --batch-size 500 \
  --checkpoint-interval 5000

# Safe migration with frequent checkpoints
codeweaver migrate apply \
  --workers 2 \
  --checkpoint-interval 100

# Preview only
codeweaver migrate apply --dry-run
```

#### migrate resume

```bash
codeweaver migrate resume [OPTIONS]
```

Resume interrupted migration.

**Options**:
- `--workers N`: Number of parallel workers

**Example**:
```bash
# Resume with default workers
codeweaver migrate resume

# Resume with more workers
codeweaver migrate resume --workers 8
```

#### migrate rollback

```bash
codeweaver migrate rollback [OPTIONS]
```

Rollback to previous state.

**Options**:
- `--checkpoint ID`: Specific checkpoint to restore
- `--list`: List available checkpoints

**Example**:
```bash
# Rollback to last checkpoint
codeweaver migrate rollback

# List checkpoints
codeweaver migrate rollback --list

# Rollback to specific checkpoint
codeweaver migrate rollback --checkpoint checkpoint_20250212_143022
```

#### migrate validate

```bash
codeweaver migrate validate [OPTIONS]
```

Validate migration integrity.

**Options**:
- `--sample-size N`: Vectors to validate (default: 1000)
- `--strict`: Use strict validation
- `--json`: Output in JSON format

**Example**:
```bash
# Basic validation
codeweaver migrate validate

# Strict validation with larger sample
codeweaver migrate validate --strict --sample-size 5000

# JSON output
codeweaver migrate validate --json > validation.json
```

#### migrate status

```bash
codeweaver migrate status [OPTIONS]
```

Show migration status.

**Options**:
- `--watch`: Watch status in real-time
- `--json`: Output in JSON format

**Example**:
```bash
# Check status
codeweaver migrate status

# Watch progress
codeweaver migrate status --watch

# JSON for monitoring
codeweaver migrate status --json
```

#### migrate checkpoint

Checkpoint management commands.

```bash
# List checkpoints
codeweaver migrate checkpoint list

# Create checkpoint
codeweaver migrate checkpoint create [NAME]

# Restore checkpoint
codeweaver migrate checkpoint restore CHECKPOINT_ID

# Clean old checkpoints
codeweaver migrate checkpoint clean [--keep N]
```

**Example**:
```bash
# Create named checkpoint
codeweaver migrate checkpoint create "before_quantization"

# List all checkpoints
codeweaver migrate checkpoint list

# Restore from checkpoint
codeweaver migrate checkpoint restore before_quantization

# Keep only last 5 checkpoints
codeweaver migrate checkpoint clean --keep 5
```

### codeweaver profile

Profile management commands.

#### profile list

```bash
codeweaver profile list [OPTIONS]
```

List available profiles.

**Options**:
- `--verbose`: Show detailed info
- `--check-compatibility`: Check collection compatibility

**Example**:
```bash
# List profiles
codeweaver profile list

# Detailed view
codeweaver profile list --verbose

# Check compatibility
codeweaver profile list --check-compatibility
```

#### profile upgrade

```bash
codeweaver profile upgrade PROFILE_NAME [OPTIONS]
```

Upgrade to profile version.

**Options**:
- `--preview`: Preview upgrade impact
- `--reindex`: Force reindex instead of migration
- `--auto-migrate`: Automatically apply migration

**Example**:
```bash
# Preview upgrade
codeweaver profile upgrade recommended --preview

# Apply upgrade
codeweaver profile upgrade recommended

# Force reindex
codeweaver profile upgrade recommended --reindex
```

---

## Type Definitions

### ConfigChangeAnalysis

```python
@dataclass
class ConfigChangeAnalysis:
    """Result of configuration change analysis."""

    is_compatible: bool
    action_required: Literal["none", "migrate", "reindex"]
    breaking_changes: list[str]
    warnings: list[str]
    safe_migrations: list[str]
    migration_strategy: str | None
    estimated_accuracy_impact: float | None  # Percentage
    storage_reduction: float | None  # Percentage
```

### MigrationResult

```python
@dataclass
class MigrationResult:
    """Result of migration operation."""

    status: Literal["completed", "failed", "partial"]
    vectors_processed: int
    vectors_failed: int
    duration_seconds: float
    vectors_per_second: float
    checkpoints_created: int
    errors: list[str]
    precision_impact: float | None  # Percentage
```

### ValidationResult

```python
@dataclass
class ValidationResult:
    """Result of validation operation."""

    is_valid: bool
    samples_checked: int
    error_rate: float  # Percentage
    issues: list[str]
    recommendations: list[str]
```

### RollbackResult

```python
@dataclass
class RollbackResult:
    """Result of rollback operation."""

    checkpoint_id: str
    restored_config: EmbeddingConfig
    vectors_restored: int
    success: bool
    warnings: list[str]
```

### WorkerPoolConfig

```python
@dataclass
class WorkerPoolConfig:
    """Configuration for worker pool."""

    max_workers: int = 4
    max_concurrent_requests: int = 50
    rate_limit_per_second: int = 100
    batch_size: int = 100
    retry_limit: int = 3
    timeout_seconds: float = 30.0

    def validate(self) -> None:
        """Validate configuration parameters."""
```

---

## Integration Examples

### Full Migration Workflow

```python
from codeweaver.config import Settings, EmbeddingConfig
from codeweaver.engine.services import (
    get_config_analyzer,
    get_migration_service,
)

async def migrate_to_optimized_config():
    """Complete migration workflow example."""

    # 1. Initialize services
    settings = Settings()
    analyzer = get_config_analyzer(settings)
    migration_service = get_migration_service(settings)

    # 2. Define target config
    target_config = EmbeddingConfig(
        model="voyage-code-3",
        dimension=512,
        datatype="int8",
    )

    # 3. Analyze current config
    analysis = await analyzer.analyze_current_config()
    if analysis is None:
        print("No existing collection - proceed with indexing")
        return

    # 4. Check compatibility
    change_analysis = await analyzer.analyze_config_change(
        old_config=analysis.current_config,
        new_config=target_config,
    )

    if not change_analysis.is_compatible:
        print("Migration not possible - reindex required:")
        for reason in change_analysis.breaking_changes:
            print(f"  - {reason}")
        return

    # 5. Validate against policy
    try:
        await analyzer.validate_config_change(target_config)
    except ConfigurationLockError as e:
        print(f"Policy blocks migration: {e}")
        return

    # 6. Run migration
    print(f"Starting migration...")
    print(f"  Strategy: {change_analysis.migration_strategy}")
    print(f"  Expected impact: {change_analysis.estimated_accuracy_impact}%")

    result = await migration_service.migrate_collection(
        target_config,
        workers=4,
        checkpoint_interval=1000,
        validate=True,
    )

    # 7. Check results
    if result.status == "completed":
        print(f"✅ Migration completed successfully")
        print(f"  Processed: {result.vectors_processed} vectors")
        print(f"  Duration: {result.duration_seconds}s")
        print(f"  Throughput: {result.vectors_per_second} vectors/sec")
    else:
        print(f"❌ Migration failed: {result.status}")
        for error in result.errors:
            print(f"  - {error}")

        # Rollback on failure
        print("Rolling back...")
        rollback = await migration_service.rollback_migration()
        print(f"Rolled back to: {rollback.checkpoint_id}")
```

### Custom Validation and Error Handling

```python
from codeweaver.exceptions import (
    ConfigurationLockError,
    MigrationError,
    ValidationError,
)

async def safe_migration_with_validation():
    """Migration with comprehensive error handling."""

    service = get_migration_service()
    analyzer = get_config_analyzer()

    try:
        # Analyze config
        analysis = await analyzer.analyze_current_config()

        # Custom validation
        if analysis.estimated_accuracy_impact > 1.0:
            raise ValidationError(
                f"Accuracy impact too high: {analysis.estimated_accuracy_impact}%"
            )

        # Run migration
        result = await service.migrate_collection(
            target_config,
            workers=4,
            checkpoint_interval=500,  # Frequent checkpoints
        )

        # Validate results
        validation = await service.validate_migration(sample_size=2000)
        if not validation.is_valid:
            raise ValidationError(
                f"Validation failed: {validation.issues}"
            )

        return result

    except ConfigurationLockError as e:
        print(f"Policy violation: {e}")
        print("Consider changing collection policy or reindexing")
        raise

    except MigrationError as e:
        print(f"Migration failed: {e}")
        # Automatic rollback
        await service.rollback_migration()
        raise

    except ValidationError as e:
        print(f"Validation failed: {e}")
        # Rollback invalid migration
        await service.rollback_migration()
        raise

    except Exception as e:
        print(f"Unexpected error: {e}")
        # Try to rollback
        try:
            await service.rollback_migration()
        except Exception:
            print("Rollback also failed - manual intervention required")
        raise
```

---

## Related Documentation

- [Migration Guide](embedding-migration-guide.md) - User guide for migrations
- [Troubleshooting Guide](troubleshooting-migration.md) - Common issues and solutions
- [CLI Reference](CLI.md) - Complete command reference
- [Configuration Guide](configuration.md) - Configuration file reference
