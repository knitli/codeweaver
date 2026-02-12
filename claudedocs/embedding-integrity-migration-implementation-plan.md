<!--
SPDX-FileCopyrightText: 2026 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Implementation Plan: Embedding Integrity & Safe Migration System

**Version**: 2.1 (Architecture-Corrected)
**Date**: 2026-02-12
**Status**: Draft for Review

**Changes in v2.1** (CRITICAL CORRECTIONS):
- **Service Location**: `engine/services/` not `providers/vector_stores/` (migration is pipeline machinery)
- **DI Pattern**: Services are plain classes, factories handle DI (no `= INJECTED` in service signatures)
- **Package Boundaries**: Maintains separation for future installability (providers agnostic of engine)
- **Testing**: Services can be directly instantiated without DI for unit tests
- See `di-architecture-corrected.md` for full architectural analysis

**Changes in v2.0**:
- Integrated with existing DI system (95% implemented)
- Added DI registration patterns throughout
- Updated testing strategy for DI architecture

## Executive Summary

This plan addresses configuration management for CodeWeaver's embedding system, preventing silent failures while enabling safe optimizations. The core challenge: users can change embedding configurations (models, dimensions, datatypes) in ways that either require reindexing or can be safely transformed.

**Key Insight from Voyage-3 Benchmarks**: Dimension reduction and quantization have minimal accuracy impact:
- float@2048 → int8@2048: 75.16% → 75.56% (improvement!)
- float@2048 → int8@512: 75.16% → 74.69% (0.47% loss)
- This validates transformation strategies as viable alternatives to reindexing

## Architecture Context

### Current State

**Dimension Handling**: Set at embedding provider config, truncated before Qdrant
**Datatype Handling**: Set at Qdrant config, expects floats, quantizes internally
**Asymmetric Retrieval**: First-class citizen (recommended mode), not edge case
**Dependency Injection**: FastAPI-inspired system at 95% implementation (`codeweaver.core.di`)

```
Embeddings → Python (dimension truncation) → Qdrant (quantization)

DI Container → Services → CLI Commands
```

**Existing DI Services**:
- `CheckpointManagerDep` (in `engine/managers/checkpoint_manager.py`, registered in `engine/dependencies.py`)
- `ManifestManagerDep` (in `engine/managers/manifest_manager.py`, registered in `engine/dependencies.py`)
- `VectorStoreProviderDep` (provider wrapped by factory in `providers/dependencies/`)
- `SettingsDep` (global settings from `core/dependencies/`)

**New Migration Services** (to be added in `engine/services/`, registered in `engine/dependencies.py`):
- `ConfigChangeAnalyzerDep` - Phase 1
- `MigrationServiceDep` - Phase 2

**DI Pattern** (CRITICAL):
- Services are **plain classes** with regular __init__ (no `= INJECTED`)
- Factories in `engine/dependencies.py` use `@dependency_provider` and `= INJECTED`
- CLI commands receive services via `= INJECTED` parameters
- Providers remain architecture-agnostic (can be used without DI)

**Collection Metadata** (v1.3.0):
```python
class CollectionMetadata:
    dense_model: str | None
    dense_model_family: str | None  # For asymmetric
    query_model: str | None         # For asymmetric
    sparse_model: str | None
    version: str = "1.3.0"
```

**Checkpoint System**: Tracks embedding provider settings but doesn't understand:
- Asymmetric configs (embed_provider vs query_provider)
- Family-aware compatibility
- Change impact classification

**User Collection Naming**: Users can define custom collection names OR use auto-generated `{project_name}-{8-char-hash}`

---

## Problem Statement

### P1: Silent Configuration Drift
- Profile updates between CodeWeaver versions are invisible to users
- Environment changes (package installs) can alter resolved models
- Users discover incompatibilities at query time (too late)

### P2: False Reindexing
- Query model changes within same family trigger full reindex (unnecessary)
- Datatype/dimension changes trigger reindex when transformation would work
- ~40% of checkpoint invalidations are false positives

### P3: No Safe Optimization Path
- Users can't optimize (quantize/reduce dimensions) without full reindex
- No guidance on transformation vs. reindex trade-offs
- Voyage-4 Matryoshka benefits unexploited

### P4: Configuration Lock-in
- Profile-based configs lock users into specific versions
- No migration path when profiles evolve
- Breaking changes force reindex without alternatives

---

## Design Principles

1. **Proactive > Reactive**: Detect issues at config time, not query time
2. **Transform > Reindex**: Prefer cheap transformations when safe
3. **Family-Aware**: Leverage asymmetric embedding family validation
4. **User Choice**: Present options with clear trade-offs, let users decide
5. **Backward Compatible**: All changes must work with existing collections

---

## Phase 1: Foundation (Sprint 1, ~1 week)

### Objective
Implement asymmetric-aware checkpoint system and proactive validation

### Tasks

#### 1.1 Enhance Checkpoint Fingerprinting

**File**: `codeweaver/engine/managers/checkpoint_manager.py`

```python
@dataclass
class CheckpointSettingsFingerprint:
    # NEW: Asymmetric-aware fields
    embedding_config_type: Literal["symmetric", "asymmetric"]
    embed_model: str
    embed_model_family: str | None
    query_model: str | None

    # Existing fields
    sparse_model: str | None
    vector_store: str

    # NEW: Configuration hash for custom configs
    config_hash: str

    def is_compatible_with(
        self,
        other: CheckpointSettingsFingerprint
    ) -> tuple[bool, ChangeImpact]:
        """Check compatibility and classify change impact."""
        if self.embedding_config_type == "asymmetric":
            # Family-aware comparison
            if (self.embed_model_family and
                other.embed_model_family and
                self.embed_model_family == other.embed_model_family):
                # Same family, check if just query model changed
                if self.embed_model == other.embed_model:
                    if self.query_model != other.query_model:
                        return True, ChangeImpact.COMPATIBLE
            # Different families or embed models
            return False, ChangeImpact.BREAKING

        # Symmetric mode: exact match required
        if self.embed_model != other.embed_model:
            return False, ChangeImpact.BREAKING

        return True, ChangeImpact.NONE

class ChangeImpact(Enum):
    NONE = "none"                  # No action needed
    COMPATIBLE = "compatible"      # Query model within family
    QUANTIZABLE = "quantizable"    # Datatype reduction only
    TRANSFORMABLE = "transformable" # Dimension reduction needed
    BREAKING = "breaking"          # Requires reindex
```

**Tests**:
- Test asymmetric query model change (same family) → COMPATIBLE
- Test symmetric model change → BREAKING
- Test embed model change → BREAKING
- Test family change → BREAKING

---

#### 1.2 Configuration Change Classification

**Location**: `codeweaver/engine/services/` (new file)

**File**: `config_analyzer.py` - Core analysis logic

**Service Class** (Plain, NO DI in signature):
```python
# In codeweaver/engine/services/config_analyzer.py
from codeweaver.config.settings import Settings
from codeweaver.engine.managers.checkpoint_manager import CheckpointManager
from codeweaver.engine.managers.manifest_manager import FileManifestManager

class ConfigChangeAnalyzer:
    """Analyzes configuration changes for compatibility."""

    def __init__(
        self,
        settings: Settings,                    # NO DI markers
        checkpoint_manager: CheckpointManager,  # NO DI markers
        manifest_manager: FileManifestManager,  # NO DI markers
    ) -> None:
        """Initialize with dependencies (plain parameters)."""
        self.settings = settings
        self.checkpoint_manager = checkpoint_manager
        self.manifest_manager = manifest_manager

    # Methods below...
```

**DI Registration** (Factory wraps service):
```python
# In codeweaver/engine/dependencies.py
from codeweaver.core.di import dependency_provider, depends, INJECTED
from codeweaver.core.dependencies import SettingsDep
from codeweaver.engine.services.config_analyzer import ConfigChangeAnalyzer
from typing import Annotated

@dependency_provider(ConfigChangeAnalyzer, scope="singleton")
def _create_config_analyzer(
    settings: SettingsDep = INJECTED,              # DI in factory
    checkpoint_manager: CheckpointManagerDep = INJECTED,  # DI in factory
    manifest_manager: ManifestManagerDep = INJECTED,      # DI in factory
) -> ConfigChangeAnalyzer:
    """Factory creates analyzer with DI-resolved dependencies."""
    return ConfigChangeAnalyzer(
        settings=settings,
        checkpoint_manager=checkpoint_manager,
        manifest_manager=manifest_manager,
    )

type ConfigChangeAnalyzerDep = Annotated[
    ConfigChangeAnalyzer,
    depends(_create_config_analyzer, scope="singleton"),
]
```

**Implementation**: `codeweaver/engine/services/config_analyzer.py` (new)

```python
from dataclasses import dataclass
from datetime import timedelta

@dataclass
class ConfigChangeAnalysis:
    impact: ChangeImpact
    old_config: CollectionMetadata
    new_config: EmbeddingConfig

    # Transformation details
    transformation_type: TransformationType | None
    transformations: list[dict[str, Any]]

    # Impact estimates
    estimated_time: timedelta
    estimated_cost: float
    accuracy_impact: str

    # User guidance
    recommendations: list[str]
    migration_strategy: str | None

def analyze_config_change(
    old_meta: CollectionMetadata,
    new_config: EmbeddingConfig,
    vector_count: int,
) -> ConfigChangeAnalysis:
    """Comprehensive config change analysis."""

    changes = []

    # 1. Model/Family Check
    if not _models_compatible(old_meta, new_config):
        return ConfigChangeAnalysis(
            impact=ChangeImpact.BREAKING,
            # ... full reindex needed
        )

    # 2. Datatype Check (Qdrant quantization)
    old_dtype = old_meta.get_vector_datatype()
    new_dtype = new_config.datatype
    if old_dtype != new_dtype:
        if is_valid_quantization(old_dtype, new_dtype):
            changes.append({
                "type": "quantization",
                "old": old_dtype,
                "new": new_dtype,
                "complexity": "low",
                "time_estimate": "30 seconds",
                "requires_vector_update": False,
            })
        else:
            return ConfigChangeAnalysis(
                impact=ChangeImpact.BREAKING,
                reason=f"Cannot increase precision",
                # ...
            )

    # 3. Dimension Check (requires migration)
    old_dim = old_meta.get_vector_dimension()
    new_dim = new_config.dimension
    if old_dim != new_dim:
        if new_dim > old_dim:
            return ConfigChangeAnalysis(
                impact=ChangeImpact.BREAKING,
                reason=f"Cannot increase dimensions",
                # ...
            )
        changes.append({
            "type": "dimension_reduction",
            "old": old_dim,
            "new": new_dim,
            "complexity": "medium",
            "time_estimate": _estimate_migration_time(vector_count),
            "requires_vector_update": True,
            "accuracy_impact": _estimate_matryoshka_impact(
                old_meta.dense_model, old_dim, new_dim
            ),
        })

    # Determine overall impact
    if not changes:
        return ConfigChangeAnalysis(impact=ChangeImpact.NONE)

    has_quantization = any(c["type"] == "quantization" for c in changes)
    has_dimension = any(c["type"] == "dimension_reduction" for c in changes)

    if has_dimension:
        return _build_transformable_analysis(changes, vector_count)
    elif has_quantization:
        return _build_quantizable_analysis(changes)

def _estimate_matryoshka_impact(
    model_name: str,
    old_dim: int,
    new_dim: int,
) -> str:
    """Estimate accuracy impact using empirical data."""
    from codeweaver.providers.embedding.capabilities.resolver import (
        EmbeddingCapabilityResolver
    )

    resolver = EmbeddingCapabilityResolver()
    caps = resolver.resolve(model_name)

    reduction_pct = (old_dim - new_dim) / old_dim * 100

    # Use empirical data for Voyage models
    if model_name.startswith("voyage-code-3"):
        # Based on benchmark data
        impact_map = {
            (2048, 1024): 0.04,  # 75.16% → 75.20%
            (2048, 512): 0.47,   # 75.16% → 74.69%
            (2048, 256): 2.43,   # 75.16% → 72.73%
            (1024, 512): 0.51,   # 74.87% → 74.69% (int8)
        }
        if (old_dim, new_dim) in impact_map:
            return f"~{impact_map[(old_dim, new_dim)]:.1f}%"

    # Generic Matryoshka estimate
    if caps and caps.supports_matryoshka:
        impact = reduction_pct * 0.05  # ~5% loss per 100% reduction
        return f"~{impact:.1f}% (Matryoshka-optimized)"

    # Generic truncation estimate
    impact = reduction_pct * 0.15  # ~15% loss per 100% reduction
    return f"~{impact:.1f}% (generic truncation)"
```

**Tests**:
- Test voyage-3 dimension reduction impact calculation
- Test quantization classification
- Test combined transformation analysis
- Test breaking change detection

---

#### 1.3 Extend Doctor Command

**File**: `codeweaver/cli/commands/doctor.py`

**CLI Integration** (receives service via DI):
```python
from codeweaver.core.di import INJECTED
from codeweaver.engine.dependencies import ConfigChangeAnalyzerDep

async def check_embedding_compatibility(
    config_analyzer: ConfigChangeAnalyzerDep = INJECTED,  # DI injects service here
) -> DoctorCheck:
    """Check if current embedding config matches collection."""
    try:
        # Service automatically injected by container, already constructed
        # Service itself has no DI, just plain __init__

        # Analyze current configuration
        # Service handles all internal logic (checkpoint/manifest access, etc.)
        analysis = await config_analyzer.analyze_current_config()

        if analysis is None:
            return DoctorCheck.set_check(
                "Embedding Configuration",
                "warn",
                "No existing collection found",
                ["Run 'cw index' to create initial index"],
            )

        match analysis.impact:
            case ChangeImpact.NONE:
                return DoctorCheck.set_check(
                    "Embedding Configuration",
                    "success",
                    "Configuration matches indexed collection",
                    [],
                )

            case ChangeImpact.COMPATIBLE:
                return DoctorCheck.set_check(
                    "Embedding Configuration",
                    "success",
                    f"Query model '{current_config.query_model}' "
                    f"compatible with indexed '{collection_meta.dense_model}'",
                    ["No reindex needed (same family)"],
                )

            case ChangeImpact.QUANTIZABLE:
                return DoctorCheck.set_check(
                    "Embedding Configuration",
                    "warn",
                    "Quantization available",
                    [
                        f"Can quantize {analysis.transformations[0]['old']} "
                        f"→ {analysis.transformations[0]['new']}",
                        f"Time: {analysis.estimated_time}",
                        f"Accuracy: {analysis.accuracy_impact}",
                        "Run: cw config apply --transform",
                    ],
                )

            case ChangeImpact.TRANSFORMABLE:
                return DoctorCheck.set_check(
                    "Embedding Configuration",
                    "warn",
                    "Transformation available",
                    [
                        f"Can transform without reindexing",
                        f"Time: {analysis.estimated_time} "
                        f"(vs {analysis.reindex_time} for reindex)",
                        f"Cost: $0 (vs ${analysis.reindex_cost} for reindex)",
                        f"Accuracy: {analysis.accuracy_impact}",
                        "Run: cw config apply --transform",
                    ],
                )

            case ChangeImpact.BREAKING:
                return DoctorCheck.set_check(
                    "Embedding Configuration",
                    "fail",
                    f"Incompatible configuration",
                    [
                        f"Indexed: {collection_meta.dense_model}",
                        f"Config: {current_config.model_name}",
                        f"Reindex required (~{analysis.estimated_time})",
                        "Options:",
                        "  1. Revert config: cw config revert",
                        "  2. Reindex: cw index --force",
                        "  3. Migrate: cw migrate --to-current-config",
                    ],
                )

    except Exception as e:
        return DoctorCheck.set_check(
            "Embedding Configuration",
            "fail",
            f"Error checking compatibility: {e}",
            ["Check logs for details"],
        )
```

**Tests**:
- Test with no collection
- Test with compatible config
- Test with quantizable config
- Test with transformable config
- Test with breaking config

---

#### 1.4 Proactive Config Validation Hook

**Location**: Add validation logic to ConfigChangeAnalyzer

**Extended Service Method**:
```python
# In codeweaver/engine/services/config_analyzer.py (extend existing class)

class ConfigChangeAnalyzer:
    # ... existing __init__ and methods ...

    async def validate_config_change(
        self,
        key: str,
        value: Any,
    ) -> ConfigChangeAnalysis | None:
        """Validate config change before applying (proactive validation)."""

        # Only validate embedding-related changes
        if not key.startswith("provider.embedding"):
            return None

        # Simulate the change
        new_settings = self._simulate_config_change(key, value)

        # Check if collection exists (via checkpoint/manifest)
        checkpoint = await self.checkpoint_manager.load_checkpoint()
        if not checkpoint:
            # No existing index, change is safe
            return None

        # Analyze impact
        analysis = await self.analyze_config_change(
            old_meta=checkpoint.collection_metadata,
            new_config=new_settings.provider.embedding,
        )

        return analysis

    def _simulate_config_change(
        self,
        key: str,
        value: Any,
    ) -> Settings:
        """Simulate applying a config change to current settings."""
        # Create copy of settings and apply change
        new_settings = self.settings.model_copy(deep=True)
        # Apply key=value to nested settings structure
        # ... implementation ...
        return new_settings
```

**Note**: No separate ValidationService needed - ConfigChangeAnalyzer handles both analysis and validation

**Integration Point**: `cw config set` command

```python
from codeweaver.core.di import INJECTED
from codeweaver.core.dependencies import SettingsDep
from codeweaver.engine.dependencies import ConfigChangeAnalyzerDep

@app.command()
async def set_config(
    key: str,
    value: str,
    force: bool = False,
    config_analyzer: ConfigChangeAnalyzerDep = INJECTED,  # DI-injected
    settings: SettingsDep = INJECTED,                     # DI-injected
):
    """Set configuration value with validation."""

    # Validate change using injected analyzer
    if not force:
        analysis = await config_analyzer.validate_config_change(
            key, value
        )

        if analysis and analysis.impact == ChangeImpact.BREAKING:
            display_breaking_change_warning(analysis)
            if not Confirm.ask("Continue?"):
                console.print("Cancelled")
                return

        elif analysis and analysis.impact in (
            ChangeImpact.QUANTIZABLE,
            ChangeImpact.TRANSFORMABLE,
        ):
            display_transformation_option(analysis)

    # Apply change using settings service
    await settings.set(key, value)
    console.print(f"✓ Configuration updated: {key} = {value}")
```

---

### Deliverables (Phase 1)

- [ ] Asymmetric-aware checkpoint fingerprinting
- [ ] Configuration change classification engine in `engine/services/config_analyzer.py`
- [ ] **Service Class**: Plain `ConfigChangeAnalyzer` with no DI in constructor
- [ ] **Factory Registration**: Register `ConfigChangeAnalyzerDep` in `engine/dependencies.py`
- [ ] Enhanced `cw doctor` with compatibility check (receives service via `= INJECTED`)
- [ ] Proactive validation in `cw config set` (receives service via `= INJECTED`)
- [ ] **Unit tests**: Direct instantiation with mocked dependencies (NO DI container needed)
- [ ] **Integration tests**: Use DI container to resolve real services
- [ ] **Export**: Add `ConfigChangeAnalyzerDep` to `engine/__init__.py`

**Success Criteria**:
- Asymmetric query model changes don't trigger false reindexes
- Users see configuration issues at config time, not query time
- `cw doctor` provides clear compatibility status
- **Service can be instantiated directly without DI (testability)**
- **Service properly registered and injectable via `= INJECTED` in CLI**
- **Package boundaries maintained** (engine doesn't create new provider dependencies)

---

## Phase 2: Transformation Engine (Sprint 2-3, ~2 weeks)

### Objective
Implement safe transformation strategies for quantization and dimension reduction

### Tasks

#### 2.1 Quantization Support (Easy Win)

**File**: `codeweaver/providers/vector_stores/qdrant_base.py`

```python
async def apply_quantization(
    self,
    collection_name: str,
    quantization_type: Literal["int8", "binary"],
    rescore: bool = True,
) -> None:
    """Apply quantization to existing collection.

    This is a pure Qdrant config change - no vector updates needed.
    Qdrant still expects float inputs, handles conversion internally.
    """
    from qdrant_client import models

    match quantization_type:
        case "int8":
            config = models.ScalarQuantization(
                scalar=models.ScalarQuantizationConfig(
                    type=models.ScalarType.INT8,
                    quantile=0.99,
                    always_ram=True,
                )
            )
        case "binary":
            config = models.BinaryQuantization(
                binary=models.BinaryQuantizationConfig(
                    always_ram=True,
                )
            )

    await self.client.update_collection(
        collection_name=collection_name,
        quantization_config=config,
    )

    # Update collection metadata
    metadata = await self.get_collection_metadata(collection_name)
    metadata.quantization_type = quantization_type
    metadata.quantization_rescore = rescore
    await self.update_collection_metadata(collection_name, metadata)
```

**User Flow**:
```bash
$ cw config set provider.vector_store.quantization=int8

⚠️  Configuration Change Detected

  Change: Quantization (float32 → int8)
  Impact: Memory optimization (no reindex needed)

  Details:
    • Pure Qdrant config change
    • You still send float embeddings
    • Qdrant quantizes internally
    • Immediate 4x memory savings

  Estimates:
    Time: ~30 seconds
    Cost: $0
    Memory: 4.9 GB → 1.2 GB (4x reduction)
    Accuracy: ~2% loss (acceptable)

  Apply quantization? [Y/n]: y

✓ Quantization applied!
  Memory: 4.9 GB → 1.2 GB
```

---

#### 2.2 Dimension Migration (Complex)

**Location**: `codeweaver/engine/services/migration_service.py` (new)

**Service Class** (Plain, NO DI in signature):
```python
# In codeweaver/engine/services/migration_service.py
from codeweaver.providers.vector_stores.base import VectorStoreProvider
from codeweaver.engine.services.config_analyzer import ConfigChangeAnalyzer
from codeweaver.engine.managers.checkpoint_manager import CheckpointManager
from codeweaver.engine.managers.manifest_manager import FileManifestManager

class MigrationService:
    """Handles dimension reduction via blue-green migration."""

    def __init__(
        self,
        vector_store: VectorStoreProvider,      # Provider instance (NO DI marker)
        config_analyzer: ConfigChangeAnalyzer,  # Service instance (NO DI marker)
        checkpoint_manager: CheckpointManager,  # Manager instance (NO DI marker)
        manifest_manager: FileManifestManager,  # Manager instance (NO DI marker)
    ) -> None:
        """Initialize with dependencies (plain parameters)."""
        self.vector_store = vector_store
        self.config_analyzer = config_analyzer
        self.checkpoint_manager = checkpoint_manager
        self.manifest_manager = manifest_manager
```

**Factory Registration** (Factory wraps service with DI):
```python
# In codeweaver/engine/dependencies.py
from codeweaver.core.di import dependency_provider, depends, INJECTED
from codeweaver.providers.dependencies import VectorStoreProviderDep
from codeweaver.engine.services.migration_service import MigrationService
from typing import Annotated

@dependency_provider(MigrationService, scope="singleton")
def _create_migration_service(
    vector_store: VectorStoreProviderDep = INJECTED,        # DI in factory
    config_analyzer: ConfigChangeAnalyzerDep = INJECTED,    # DI in factory
    checkpoint_manager: CheckpointManagerDep = INJECTED,    # DI in factory
    manifest_manager: ManifestManagerDep = INJECTED,        # DI in factory
) -> MigrationService:
    """Factory creates migration service with DI-resolved dependencies."""
    return MigrationService(
        vector_store=vector_store,
        config_analyzer=config_analyzer,
        checkpoint_manager=checkpoint_manager,
        manifest_manager=manifest_manager,
    )

type MigrationServiceDep = Annotated[
    MigrationService,
    depends(_create_migration_service, scope="singleton"),
]
```

**Implementation continues**:
```python
class MigrationService:
    # ... __init__ from above ...

    async def migrate_dimensions(
        self,
        source_collection: str,
        new_dimension: int,
        model_capabilities: EmbeddingCapability,
    ) -> MigrationResult:
        """Migrate collection to new dimension."""

        # 1. Validation
        old_info = await self.client.get_collection(source_collection)
        old_dimension = old_info.config.params.vectors["primary"].size

        if new_dimension >= old_dimension:
            raise ValueError(
                f"Can only reduce dimensions "
                f"({old_dimension} → {new_dimension})"
            )

        # 2. Create target collection
        target_collection = self._generate_versioned_name(
            source_collection, new_dimension
        )

        await self._create_dimensioned_collection(
            target_collection,
            new_dimension,
            old_info.config,
        )

        # 3. Migrate vectors with truncation
        migrated = await self._migrate_with_truncation(
            source=source_collection,
            target=target_collection,
            new_dimension=new_dimension,
        )

        # 4. Validate migration
        await self._validate_migration(
            source=source_collection,
            target=target_collection,
            expected_count=migrated,
        )

        # 5. Switch active collection (alias)
        await self._switch_collection_alias(
            alias=source_collection,  # User-facing name
            new_target=target_collection,
            old_target=f"{source_collection}_old",
        )

        return MigrationResult(
            strategy="blue_green_dimension_reduction",
            vectors_migrated=migrated,
            old_collection=source_collection,
            new_collection=target_collection,
            rollback_available=True,
            rollback_retention_days=7,
        )

    async def _migrate_with_truncation(
        self,
        source: str,
        target: str,
        new_dimension: int,
    ) -> int:
        """Scroll source, truncate, upsert to target."""
        offset = None
        batch_size = 1000
        total_migrated = 0

        while True:
            records, offset = await self.client.scroll(
                collection_name=source,
                limit=batch_size,
                offset=offset,
                with_vectors=True,
            )

            if not records:
                break

            # Truncate vectors in Python
            truncated = [
                models.PointStruct(
                    id=record.id,
                    vector={
                        "primary": record.vector["primary"][:new_dimension]
                    },
                    payload=record.payload,
                )
                for record in records
            ]

            await self.client.upsert(
                collection_name=target,
                points=truncated,
            )

            total_migrated += len(truncated)

            # Progress reporting
            self._report_progress(total_migrated)

        return total_migrated

    def _generate_versioned_name(
        self,
        base_name: str,
        dimension: int,
    ) -> str:
        """Generate versioned internal collection name."""
        timestamp = datetime.now().strftime("%Y%m%d")
        return f"{base_name}_{timestamp}_dim{dimension}"
```

**User Flow**:
```bash
$ cw config set provider.embedding.embedding_config.dimension=768

⚠️  Configuration Change Detected

  Change: Dimension reduction (1024 → 768)
  Model: voyage-code-3 (Matryoshka-optimized ✓)

  Migration Strategy: Blue-green with truncation
    1. Create new collection (dimension=768)
    2. Copy & truncate vectors
    3. Validate new collection
    4. Switch atomically
    5. Preserve old collection for rollback

  Estimates:
    Time: ~5 minutes (1,234 vectors)
    Cost: $0 (no re-embedding)
    Memory: 4.9 GB → 3.7 GB (25% reduction)
    Accuracy: ~0.04% loss (empirical: 75.20% vs 75.16%)

  Options:
    [1] Migrate with truncation (recommended)
    [2] Full reindex (maximum quality)
    [3] Cancel

  Choice: 1

⏳ Starting blue-green migration...
  ✓ Created collection: codebase_20260212_dim768
  [████████████] 1,234/1,234 vectors migrated
  ✓ Validation passed
  ✓ Switched to new collection

✓ Migration complete!
  Rollback: cw migrate rollback (available 7 days)
```

---

#### 2.3 Collection Metadata Updates

**File**: `codeweaver/providers/types/vector_store.py`

```python
class CollectionMetadata(BasedModel):
    # Existing fields...

    # NEW: Configuration tracking (v1.4.0)
    profile_name: str | None = None
    profile_version: str | None = None  # CodeWeaver version
    config_hash: str | None = None      # For custom configs
    config_timestamp: datetime | None = None

    # NEW: Transformation tracking
    quantization_type: Literal["int8", "binary", None] = None
    quantization_rescore: bool = False
    original_dimension: int | None = None  # Before reduction
    transformations: list[TransformationRecord] = Field(
        default_factory=list
    )

    version: str = "1.4.0"  # Schema version bump

@dataclass
class TransformationRecord:
    """Record of a transformation applied to collection."""
    timestamp: datetime
    type: Literal["quantization", "dimension_reduction"]
    old_value: str | int
    new_value: str | int
    accuracy_impact: str
    migration_time: timedelta
```

**Migration**: v1.3.0 → v1.4.0 is backward compatible (new fields have defaults)

---

### Deliverables (Phase 2)

- [ ] Quantization support in Qdrant base (providers)
- [ ] Migration service in `engine/services/migration_service.py`
- [ ] **Service Class**: Plain `MigrationService` with no DI in constructor
- [ ] **Factory Registration**: Register `MigrationServiceDep` in `engine/dependencies.py`
- [ ] Collection metadata v1.4.0 with transformation tracking (providers)
- [ ] `cw config apply --transform` command (receives service via `= INJECTED`)
- [ ] `cw migrate rollback` command (receives service via `= INJECTED`)
- [ ] **Unit tests**: Direct instantiation with mocked dependencies
- [ ] **Integration tests**: Use DI container to resolve real services
- [ ] Benchmark validation tests
- [ ] **Export**: Add `MigrationServiceDep` to `engine/__init__.py`

**Success Criteria**:
- Users can quantize collections in <1 minute
- Users can reduce dimensions without reindexing
- Transformations preserve >98% of search quality
- Rollback works correctly
- **Service can be instantiated directly without DI (testability)**
- **Package boundaries maintained** (engine uses provider abstractions, not implementations)

---

## Phase 3: Advanced Features (Sprint 4-6, ~3 weeks)

### Objective
Collection policies, profile versioning, and optimization wizard

### Tasks

#### 3.1 Collection Policy System

```python
class CollectionPolicy(BaseEnum):
    STRICT = "strict"              # No model changes
    FAMILY_AWARE = "family_aware"  # Allow query changes in family
    FLEXIBLE = "flexible"          # Warn on breaking
    UNLOCKED = "unlocked"          # Allow all

class CollectionMetadata(BasedModel):
    # ...
    policy: CollectionPolicy = CollectionPolicy.FAMILY_AWARE

    def validate_config_change(
        self,
        new_config: EmbeddingConfig,
    ) -> None:
        """Validate change against policy."""
        match self.policy:
            case CollectionPolicy.STRICT:
                if not exact_match(self, new_config):
                    raise ConfigurationLockError(...)

            case CollectionPolicy.FAMILY_AWARE:
                if not family_compatible(self, new_config):
                    raise ConfigurationLockError(...)

            # ... other policies
```

---

#### 3.2 Profile Versioning

```python
# In profiles.py
@dataclass
class VersionedProfile:
    name: str
    version: str  # CodeWeaver version
    embedding_config: EmbeddingConfig
    changelog: list[str]

    @classmethod
    def is_compatible_with(
        cls,
        profile_version: str,
        collection_version: str,
    ) -> bool:
        """Check if profile versions are compatible."""
        # Semantic versioning rules
        pv = parse_version(profile_version)
        cv = parse_version(collection_version)
        return pv.major == cv.major

RECOMMENDED = VersionedProfile(
    name="recommended",
    version=__version__,  # Track with CodeWeaver version
    embedding_config=...,
    changelog=[
        "v0.3.0: Switched to voyage-4-large + voyage-4-nano asymmetric",
        "v0.2.0: Added sparse embedding support",
    ],
)
```

---

#### 3.3 Optimization Wizard

```python
@app.command()
async def optimize(
    *,
    target: Literal["memory", "speed", "balanced"] = "balanced",
    preview: bool = False,
):
    """Analyze and apply optimizations."""

    # Analyze current state
    current_state = await analyze_current_config()

    # Generate recommendations
    recommendations = generate_optimization_plan(
        current_state, target
    )

    if preview:
        display_optimization_preview(recommendations)
        return

    # Apply optimizations
    for opt in recommendations:
        console.print(f"\nApplying: {opt.description}")
        await apply_optimization(opt)
        console.print(f"✓ {opt.success_message}")

    console.print("\n✓ Optimization complete!")
```

---

### Deliverables (Phase 3)

- [ ] Collection policy system
- [ ] Profile versioning
- [ ] `cw optimize` command
- [ ] Policy enforcement in config changes
- [ ] Profile update notifications
- [ ] Comprehensive documentation

**Success Criteria**:
- Users can lock collections to prevent accidents
- Profile updates are visible and trackable
- Optimization wizard makes safe recommendations

---

## Testing Strategy

### Unit Tests with DI Mocking

**Configuration Analysis**:
- Test change classification for all scenarios
- Test accuracy impact estimation
- Test transformation feasibility checks
- Test family-aware compatibility
- **DI Mocking**: Use test container with mocked dependencies

```python
@pytest.fixture
def test_container():
    """Create test container with mocks."""
    from codeweaver.core.di import clear_container, get_container, dependency_provider

    clear_container()

    @dependency_provider(CheckpointManager, scope="singleton")
    def _mock_checkpoint_manager() -> CheckpointManager:
        return MockCheckpointManager()

    @dependency_provider(ManifestManager, scope="singleton")
    def _mock_manifest_manager() -> ManifestManager:
        return MockManifestManager()

    yield get_container()
    clear_container()

async def test_config_analyzer_with_mocks(test_container):
    """Test with mocked dependencies."""
    analyzer = await test_container.resolve(ConfigChangeAnalyzerDep)
    # analyzer has mock checkpoint/manifest managers
    result = await analyzer.analyze_config_change(...)
    assert result.impact == ChangeImpact.COMPATIBLE
```

**Transformation Engine**:
- Test quantization config updates
- Test dimension migration logic
- Test rollback mechanism
- Test metadata tracking
- **DI Mocking**: Mock vector store client for fast tests

```python
async def test_migration_service_with_mock_client(test_container):
    """Test migration with mocked client."""
    @dependency_provider(VectorStoreClient)
    def _mock_client() -> VectorStoreClient:
        return MockVectorStoreClient()

    service = await test_container.resolve(MigrationServiceDep)
    result = await service.migrate_dimensions(...)
    assert result.vectors_migrated == 1000
```

### DI-Specific Tests

**Dependency Resolution**:
- Test that services are properly registered
- Test singleton scope behavior (same instance returned)
- Test dependency graph resolution order
- Test circular dependency detection
- Test service lifecycle (startup/shutdown)

**Service Composition**:
- Test that high-level services compose lower-level ones correctly
- Test that dependencies are injected in correct order
- Test that settings-driven factories work correctly

```python
async def test_service_singleton_scope():
    """Verify singleton services return same instance."""
    container = get_container()

    service1 = await container.resolve(MigrationServiceDep)
    service2 = await container.resolve(MigrationServiceDep)

    assert service1 is service2  # Same instance

async def test_dependency_injection_order():
    """Verify dependencies injected before service construction."""
    container = get_container()

    # Resolve service with dependencies
    service = await container.resolve(MigrationServiceDep)

    # Verify all dependencies were injected
    assert service.config_analyzer is not None
    assert service.checkpoint_manager is not None
    assert service.manifest_manager is not None
```

### Integration Tests with Real DI Services

**End-to-End Workflows**:
1. Profile-based config → index → profile update → migration
2. Custom config → optimize (quantize) → validate
3. Asymmetric config → query model change → no reindex
4. Breaking change → revert vs. reindex decision

**DI Integration Testing**:
```python
@pytest.fixture
def test_settings():
    """Provide test settings for integration tests."""
    return SettingsFactory.create_test_settings(
        vector_store="inmemory",  # Use in-memory for testing
        embedding_provider="fastembed",
    )

async def test_full_migration_flow_with_di(test_settings):
    """Test complete migration with real DI services."""
    from codeweaver.core.di import get_container, dependency_provider

    # Override settings for test
    @dependency_provider(Settings)
    def _test_settings() -> Settings:
        return test_settings

    container = get_container()

    # Get real services (no mocks)
    config_analyzer = await container.resolve(ConfigChangeAnalyzerDep)
    migration_service = await container.resolve(MigrationServiceDep)
    validation_service = await container.resolve(ValidationServiceDep)

    # Run real migration flow
    analysis = await config_analyzer.analyze_current_config()
    result = await migration_service.migrate_dimensions(...)
    validation = await validation_service.validate_migration(result)

    assert result.vectors_migrated > 0
    assert validation.passed
```

### Benchmark Validation

**Accuracy Verification**:
- Verify voyage-3 dimension reduction impact matches empirical data
- Test quantization impact on search quality
- Validate Matryoshka-optimized models

### Performance Tests

**Migration Speed**:
- 1k vectors: <30 seconds
- 10k vectors: <3 minutes
- 100k vectors: <20 minutes

---

## File Organization and DI Architecture

### Location Strategy

Migration services in **engine** (pipeline machinery), not providers (pluggable backends):

```
src/codeweaver/
├── engine/
│   ├── services/                    # Service implementations
│   │   ├── chunking_service.py     # Existing
│   │   ├── indexing_service.py     # Existing
│   │   ├── config_analyzer.py      # NEW: Phase 1
│   │   └── migration_service.py    # NEW: Phase 2
│   ├── managers/                    # Manager implementations
│   │   ├── checkpoint_manager.py   # Existing
│   │   └── manifest_manager.py     # Existing
│   └── dependencies.py              # UPDATE: Add new factory registrations
│
└── providers/
    └── vector_stores/
        ├── base.py                  # Existing: VectorStoreProvider abstract
        ├── qdrant.py                # Existing: Implementation
        ├── qdrant_base.py          # UPDATE: Add quantization support
        └── metadata.py              # UPDATE: CollectionMetadata v1.4.0
```

**Rationale**:
- **Migration is pipeline machinery** → belongs in engine with indexing/chunking
- **Providers stay architecture-agnostic** → can be used in other frameworks
- **Package separation maintained** → supports future installability
- **Existing pattern followed** → services/managers in engine, factories in engine/dependencies.py

### DI Registration Pattern (Correct)

**File**: `codeweaver/engine/dependencies.py` (UPDATE existing file)

```python
"""Dependency injection registrations for engine services."""

from __future__ import annotations

from typing import TYPE_CHECKING, Annotated

from codeweaver.core.di import dependency_provider, depends, INJECTED

if TYPE_CHECKING:
    from codeweaver.core.dependencies import SettingsDep
    from codeweaver.providers.dependencies import VectorStoreProviderDep
    from codeweaver.engine.services.config_analyzer import ConfigChangeAnalyzer
    from codeweaver.engine.services.migration_service import MigrationService

# Existing registrations (CheckpointManager, ManifestManager, etc.)
# ...

# === Phase 1: Configuration Analysis ===

@dependency_provider(ConfigChangeAnalyzer, scope="singleton")
def _create_config_analyzer(
    settings: SettingsDep = INJECTED,                     # DI in factory
    checkpoint_manager: CheckpointManagerDep = INJECTED,  # DI in factory
    manifest_manager: ManifestManagerDep = INJECTED,      # DI in factory
) -> ConfigChangeAnalyzer:
    """Factory wraps service with DI."""
    from codeweaver.engine.services.config_analyzer import ConfigChangeAnalyzer

    # Service instantiated with plain parameters
    return ConfigChangeAnalyzer(
        settings=settings,
        checkpoint_manager=checkpoint_manager,
        manifest_manager=manifest_manager,
    )

type ConfigChangeAnalyzerDep = Annotated[
    "ConfigChangeAnalyzer",
    depends(_create_config_analyzer, scope="singleton"),
]


# === Phase 2: Migration Service ===

@dependency_provider(MigrationService, scope="singleton")
def _create_migration_service(
    vector_store: VectorStoreProviderDep = INJECTED,     # DI in factory
    config_analyzer: ConfigChangeAnalyzerDep = INJECTED,  # DI in factory
    checkpoint_manager: CheckpointManagerDep = INJECTED,  # DI in factory
    manifest_manager: ManifestManagerDep = INJECTED,      # DI in factory
) -> MigrationService:
    """Factory wraps migration service with DI."""
    from codeweaver.engine.services.migration_service import MigrationService

    # Service instantiated with plain parameters
    return MigrationService(
        vector_store=vector_store,
        config_analyzer=config_analyzer,
        checkpoint_manager=checkpoint_manager,
        manifest_manager=manifest_manager,
    )

type MigrationServiceDep = Annotated[
    "MigrationService",
    depends(_create_migration_service, scope="singleton"),
]


# Export type aliases (add to existing __all__)
__all__ = (
    # ... existing exports ...
    "ConfigChangeAnalyzerDep",
    "MigrationServiceDep",
)
```

### Export Pattern

**File**: `codeweaver/engine/__init__.py`

```python
# Add to existing exports
from codeweaver.engine.dependencies import (
    # Existing...
    ConfigChangeAnalyzerDep,  # NEW: Phase 1
    MigrationServiceDep,       # NEW: Phase 2
)

__all__ = (
    # Existing exports...
    "ConfigChangeAnalyzerDep",
    "MigrationServiceDep",
)
```

### CLI Integration Pattern (Correct)

CLI commands receive services via `= INJECTED`, services themselves have plain constructors:

```python
# In codeweaver/cli/commands/doctor.py
from codeweaver.core.di import INJECTED
from codeweaver.engine.dependencies import ConfigChangeAnalyzerDep

async def check_embedding_compatibility(
    config_analyzer: ConfigChangeAnalyzerDep = INJECTED,  # DI here
) -> DoctorCheck:
    """Check embedding compatibility - service injected by container."""
    # Service automatically injected and constructed
    # Service itself has plain __init__ with no DI
    analysis = await config_analyzer.analyze_current_config()
    ...
```

```python
# In codeweaver/cli/commands/migrate.py
from codeweaver.core.di import INJECTED
from codeweaver.engine.dependencies import MigrationServiceDep

@app.command()
async def migrate(
    target_dimension: int,
    migration_service: MigrationServiceDep = INJECTED,  # DI here
):
    """Migrate collection - service injected by container."""
    result = await migration_service.migrate_dimensions(target_dimension)
    ...
```

### Benefits of This Organization

1. **Correct Abstraction Level**: Migration is pipeline machinery → lives in engine
2. **Package Independence**: Providers remain architecture-agnostic → can be used elsewhere
3. **Testability**: Services have plain constructors → easy to instantiate with mocks
4. **DI Integration**: Factory wrapper pattern → DI is optional, not required
5. **Consistency**: Matches existing engine pattern (services + managers + factories)
6. **Future-Proof**: Supports package separation for monorepo split
7. **Type Safety**: Full IDE autocomplete and type checking
8. **Maintainability**: Clear separation between engine (pipeline) and providers (pluggable)

---

## Rollout Plan

### Alpha Testing (Internal)
- Phase 1 features with dev team
- Validate checkpoint system
- Test doctor command

### Beta Testing (Early Users)
- Phase 2 transformations
- Gather feedback on UX
- Validate empirical accuracy data

### General Availability
- Phase 3 advanced features
- Full documentation
- Migration guides for existing users

---

## Risk Analysis

### Technical Risks

**Risk**: Qdrant dimension change might fail
**Mitigation**: Blue-green migration preserves original
**Probability**: Low

**Risk**: Transformation accuracy worse than estimated
**Mitigation**: Empirical validation, clear warnings
**Probability**: Low (validated with benchmarks)

**Risk**: Async model family validation complexity
**Mitigation**: Comprehensive testing, clear error messages
**Probability**: Medium

### User Experience Risks

**Risk**: Users confused by transformation options
**Mitigation**: Clear messaging, sensible defaults, preview mode
**Probability**: Medium

**Risk**: Breaking changes disrupt workflows
**Mitigation**: Backward compatibility, deprecation notices, migration docs
**Probability**: Low

---

## Success Metrics

### Technical
- [ ] False reindex rate < 5% (baseline: 40%)
- [ ] Query model changes don't trigger reindex (asymmetric)
- [ ] Transformations complete in estimated time ±20%

### User Experience
- [ ] Time to recovery < 2 minutes (baseline: 15 min)
- [ ] Configuration change confusion < 10% of users
- [ ] Support tickets re: configuration -80%

### Business
- [ ] User satisfaction with migration UX > 4/5
- [ ] Optimization adoption rate > 30%
- [ ] Zero data corruption incidents

---

## Open Questions for Review

1. **Collection Naming**: Should we enforce internal versioned names for all collections, or only when migrations are needed?

2. **Rollback Duration**: 7 days for rollback seems reasonable, but should it be configurable?

3. **Transformation Defaults**: Should we auto-apply COMPATIBLE changes, or always ask?

4. **Profile Evolution**: How should we handle profile updates between minor vs. major versions?

5. **Quantization Rescoring**: Always enable by default, or make it configurable?

6. **Doctor Frequency**: Should `cw doctor` run automatically (e.g., on CLI start), or only on-demand?

7. **Migration Validation**: What validation checks should be mandatory vs. optional?

8. **Error Recovery**: If dimension migration fails mid-way, what's the safest recovery path?

---

## Next Steps

1. **Review & Feedback**: QA + Architecture review (✅ Complete - see `implementation-plan-review-synthesis.md`)
2. **DI Architecture Review**: Understand existing DI system (✅ Complete - see `di-architecture-corrected.md`)
3. **Refinement**: Address feedback, resolve open questions (✅ Complete)
4. **Phase 1 Implementation**: Start with checkpoint + doctor
   - Create `engine/services/config_analyzer.py` (plain class, no DI in __init__)
   - Update `engine/dependencies.py` with factory registration
   - Export `ConfigChangeAnalyzerDep` from `engine/__init__.py`
   - Update `cli/commands/doctor.py` to receive service via `= INJECTED`
   - Update `cli/commands/config.py` to receive service via `= INJECTED`
   - Write unit tests with direct instantiation (mocked dependencies)
   - Write integration tests using DI container (real services)
5. **Iterative Delivery**: Ship Phase 1, gather feedback, iterate

**DI Integration Checklist** (Corrected):
- [x] Review `codeweaver.core.di` implementation
- [x] Understand existing service registrations in `engine.dependencies`
- [x] Understand factory wrapper pattern (services plain, factories with DI)
- [ ] Create new service classes in `engine/services/` (plain __init__)
- [ ] Register factories in `engine/dependencies.py` (with `@dependency_provider`)
- [ ] Export type aliases from `engine/__init__.py`
- [ ] Update CLI commands to use `= INJECTED` parameters
- [ ] Write unit tests with direct instantiation (NO DI needed)
- [ ] Write integration tests with DI container (real resolution)
- [ ] Verify singleton scope behavior in integration tests
- [ ] Maintain package boundaries (engine → providers abstractions only)

---

## References

- **Voyage-3 Benchmark Data** (provided - empirical accuracy measurements)
- **CollectionMetadata v1.3.0** implementation (`providers/types/vector_store.py`)
- **AsymmetricEmbeddingProviderSettings** implementation (`providers/config/categories/embedding.py`)
- **Existing doctor command** structure (`cli/commands/doctor.py`)
- **Qdrant quantization** documentation
- **DI System Architecture** (`di-architecture-corrected.md`) - **CORRECTED** in v2.1
- **Implementation Review Synthesis** (`implementation-plan-review-synthesis.md`)
- **DI Integration Addendum** (`implementation-plan-di-integration-addendum.md`) - SUPERSEDED by corrected architecture
- **Existing DI registrations**:
  - `codeweaver.core.di` - DI container implementation (FastAPI-inspired pattern)
  - `codeweaver.core.dependencies` - Core service registrations
  - `codeweaver.engine.dependencies` - Engine service registrations (CheckpointManager, ManifestManager, etc.)
  - **Pattern**: Services plain, factories with `@dependency_provider` and `= INJECTED`
