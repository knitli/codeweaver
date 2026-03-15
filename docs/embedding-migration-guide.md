<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Embedding Configuration Migration Guide

This guide covers safe migration of embedding configurations including model changes, dimension reduction, quantization, and collection policy management.

## Table of Contents

- [Quick Start](#quick-start)
- [Understanding Migrations](#understanding-migrations)
- [When to Use What](#when-to-use-what)
- [Collection Policies](#collection-policies)
- [Migration Workflows](#migration-workflows)
- [Profile Management](#profile-management)
- [Advanced Features](#advanced-features)
- [Best Practices](#best-practices)

---

## Quick Start

### Check Current Configuration

Before making any changes, check your current embedding configuration:

```bash
# View current config and collection status
codeweaver config

# Check if migration is needed for a config change
codeweaver config validate
```

### Basic Migration Workflow

```bash
# 1. Analyze what would happen with a config change
codeweaver config analyze --preview

# 2. Update your config file (codeweaver.toml)
# Edit: embedding.model = "voyage-code-3" → "new-model"

# 3. Validate the change
codeweaver config validate

# 4. Apply migration if needed
codeweaver migrate apply

# 5. Verify results
codeweaver doctor
```

---

## Understanding Migrations

### What is a Migration?

A migration transforms your existing vector embeddings to work with a new configuration without requiring a full reindex. Common migrations include:

- **Dimension Reduction**: 2048 → 512 dimensions (using Matryoshka embeddings)
- **Quantization**: float32 → int8 (reduces storage by 75%)
- **Model Changes**: Within compatible families (e.g., voyage-code-3 → voyage-4-large)

### Why Migrate Instead of Reindex?

**Reindexing** regenerates all embeddings from source files:
- ✅ Always works for any config change
- ❌ Slow (minutes to hours for large codebases)
- ❌ Requires API credits for embedding provider

**Migration** transforms existing embeddings:
- ✅ Fast (seconds to minutes)
- ✅ No API costs
- ✅ Preserves existing work
- ⚠️ Only works for compatible changes

### Migration Trade-offs

CodeWeaver uses empirically validated transformation strategies:

| Transformation | Storage Savings | Accuracy Impact | Use Case |
|---------------|----------------|-----------------|----------|
| float32 → int8 (2048d) | 75% | +0.40% | Production optimization |
| 2048d → 512d (float32) | 75% | -0.47% | Storage constrained |
| 2048d → 512d + int8 | 93.75% | -0.62% | Maximum compression |

**Real-world example** (voyage-code-3 on MTEB benchmarks):
- Baseline: float32@2048 = 75.16% accuracy
- int8@2048: 75.56% accuracy (improvement!)
- int8@512: 74.69% accuracy (minimal loss)

---

## When to Use What

### Decision Tree

```
Config change needed?
│
├─ Model change within family (e.g., voyage-3 → voyage-4)?
│  └─ Use FAMILY_AWARE policy → Safe migration
│
├─ Dimension reduction (2048 → 512)?
│  ├─ Model supports Matryoshka? → Safe migration
│  └─ Model doesn't support it? → Reindex required
│
├─ Quantization (float32 → int8)?
│  └─ Vector store supports it? → Safe migration
│
├─ Model change across families?
│  └─ Reindex required
│
└─ Unknown compatibility?
   └─ Run: codeweaver config analyze
```

### Safe Migrations (No Reindex)

✅ **Dimension Reduction** (Matryoshka models only)
```toml
# Before
[embedding]
model = "voyage-code-3"
dimension = 2048

# After (safe migration)
[embedding]
model = "voyage-code-3"
dimension = 512
```

✅ **Quantization**
```toml
# Before
[embedding.vector_store]
datatype = "float32"

# After (safe migration)
[embedding.vector_store]
datatype = "int8"
```

✅ **Family-Compatible Model Changes**
```toml
# Before (voyage-3 family)
[embedding]
model = "voyage-code-3"

# After (voyage-4 family, compatible query models)
[embedding]
model = "voyage-4-large"
```

### Reindex Required

❌ **Cross-Family Model Changes**
```toml
# Requires reindex
model = "voyage-code-3" → "openai/text-embedding-3-large"
```

❌ **Dimension Increase**
```toml
# Requires reindex (can't create dimensions from nothing)
dimension = 512 → 2048
```

❌ **Non-Matryoshka Dimension Changes**
```toml
# If model doesn't support Matryoshka, requires reindex
model = "some-non-matryoshka-model"
dimension = 1024 → 512
```

---

## Collection Policies

Collection policies control what configuration changes are allowed without explicit migration or reindexing.

### Policy Types

#### STRICT
**Purpose**: Production environments, mission-critical collections

```toml
[embedding.collection]
policy = "strict"
```

- ❌ No configuration changes allowed
- ❌ Model changes blocked
- ❌ Dimension changes blocked
- ❌ Quantization changes blocked
- ✅ Guarantees stability

**Use when**:
- Production search indexes
- Team collaboration (prevent accidental changes)
- Regulatory compliance requirements

#### FAMILY_AWARE (Default)
**Purpose**: Balanced safety and flexibility

```toml
[embedding.collection]
policy = "family_aware"  # default
```

- ✅ Query model changes within family
- ✅ Safe dimension reduction (Matryoshka)
- ✅ Quantization
- ❌ Cross-family model changes
- ⚠️ Warns on potential issues

**Use when**:
- Active development
- Optimization experiments
- Standard use cases

#### FLEXIBLE
**Purpose**: Exploration and experimentation

```toml
[embedding.collection]
policy = "flexible"
```

- ✅ Most configuration changes
- ⚠️ Warns on breaking changes
- ⚠️ Allows risky operations
- ⚠️ May degrade accuracy

**Use when**:
- Prototyping
- Testing different configs
- Temporary development branches

#### UNLOCKED
**Purpose**: Full control, maximum risk

```toml
[embedding.collection]
policy = "unlocked"
```

- ✅ All changes allowed
- ⚠️ No warnings or validation
- ⚠️ No safety checks
- ⚠️ User assumes all risk

**Use when**:
- Advanced users only
- Custom workflows
- You know exactly what you're doing

### Changing Collection Policy

```bash
# Update your config file
# Edit codeweaver.toml:
[embedding.collection]
policy = "flexible"

# Apply the policy change
codeweaver config apply

# Verify
codeweaver config show
```

**Note**: Policy changes take effect immediately and don't require migration.

---

## Migration Workflows

### Workflow 1: Optimize Existing Collection

**Goal**: Reduce storage costs without reindexing

```bash
# Step 1: Check current storage usage
codeweaver doctor

# Step 2: Analyze optimization options
codeweaver config analyze --show-alternatives

# Step 3: Update config for int8 quantization
# Edit codeweaver.toml:
[embedding.vector_store]
datatype = "int8"

# Step 4: Preview migration impact
codeweaver migrate preview
# Output:
# - Storage reduction: 75%
# - Estimated accuracy impact: +0.40% (improvement)
# - Migration time: ~2 minutes

# Step 5: Apply migration with checkpointing
codeweaver migrate apply --checkpoint-interval 1000

# Step 6: Validate results
codeweaver migrate validate
codeweaver search "test query"  # verify search quality
```

### Workflow 2: Dimension Reduction

**Goal**: Reduce dimensions for faster search

```bash
# Step 1: Verify model supports Matryoshka
codeweaver list models --model voyage-code-3 --capabilities
# Output: supports_matryoshka: true

# Step 2: Update config
# Edit codeweaver.toml:
[embedding]
dimension = 512  # was 2048

# Step 3: Analyze impact
codeweaver config analyze
# Output:
# - Type: DIMENSION_REDUCTION
# - Strategy: matryoshka_truncate
# - Expected accuracy loss: ~0.47%

# Step 4: Apply with parallel workers
codeweaver migrate apply \
  --workers 4 \
  --checkpoint-interval 500

# Step 5: Compare search results
codeweaver search "authentication" --limit 10 > after.txt
# Compare with previous results
```

### Workflow 3: Model Upgrade

**Goal**: Upgrade to newer model version

```bash
# Step 1: Check model family compatibility
codeweaver list models --model voyage-4-large --family
# Output: family: voyage-4

# Step 2: Update config
# Edit codeweaver.toml:
[embedding]
model = "voyage-4-large"  # was voyage-code-3

# Step 3: Check if migration is possible
codeweaver config validate
# Output: ⚠️ Cross-family change requires reindex

# Step 4: Decide: migrate or reindex
# Option A: Safe - reindex with new model
codeweaver index --force-reindex

# Option B: Risky - override policy (not recommended)
codeweaver config set-policy unlocked
codeweaver migrate apply --force
# Then restore policy
codeweaver config set-policy family_aware
```

### Workflow 4: Recovery from Failed Migration

**Goal**: Rollback after migration issues

```bash
# Step 1: Check migration status
codeweaver migrate status

# Step 2: Review checkpoint
codeweaver migrate checkpoint list

# Step 3: Rollback to last good state
codeweaver migrate rollback

# Step 4: Verify rollback
codeweaver doctor
codeweaver search "test query"

# Step 5: Fix underlying issue
# - Check logs: ~/.codeweaver/logs/
# - Verify config: codeweaver config validate
# - Check resources: codeweaver doctor --verbose

# Step 6: Retry migration with more conservative settings
codeweaver migrate apply \
  --workers 2 \
  --checkpoint-interval 100 \
  --retry-limit 3
```

---

## Profile Management

### Understanding Profiles

Profiles are named embedding configurations that track versions and compatibility:

```toml
# Built-in profiles
[profiles.recommended]  # voyage-4 family, optimized
[profiles.fast]         # Smaller models, faster indexing
[profiles.accurate]     # Largest models, best results
```

### Profile Versioning

Profiles track CodeWeaver versions for compatibility:

```bash
# Show profile versions
codeweaver list profiles

# Output:
# recommended (v0.3.0):
#   - model: voyage-4-large
#   - query_model: voyage-4-nano
#   - dimension: 2048
#   - Compatible with collection: YES

# fast (v0.3.0):
#   - model: voyage-code-3
#   - dimension: 512
#   - Compatible with collection: YES
```

### Upgrading Profiles

When CodeWeaver updates built-in profiles:

```bash
# Check for profile updates
codeweaver config check-updates

# Output:
# Profile 'recommended' has update available:
#   Current: v0.2.0 (voyage-code-3)
#   Latest:  v0.3.0 (voyage-4-large)
#   Migration: Required (cross-family change)

# Preview upgrade impact
codeweaver profile upgrade recommended --preview

# Apply upgrade (triggers migration if possible)
codeweaver profile upgrade recommended

# Or reindex if needed
codeweaver profile upgrade recommended --reindex
```

### Custom Profiles

Create your own versioned profiles:

```toml
# codeweaver.toml
[profiles.my_custom]
version = "1.0.0"
model = "voyage-code-3"
dimension = 1024
datatype = "int8"

[profiles.my_custom.changelog]
"1.0.0" = "Initial custom profile"
```

```bash
# Use custom profile
codeweaver config set-profile my_custom

# Version your profile changes
# Edit codeweaver.toml:
[profiles.my_custom]
version = "1.1.0"
dimension = 512  # changed

[profiles.my_custom.changelog]
"1.1.0" = "Reduced dimensions for faster search"
"1.0.0" = "Initial custom profile"

# Apply profile update
codeweaver config apply-profile my_custom
```

---

## Advanced Features

### Parallel Migration

Speed up migrations with concurrent workers:

```bash
# Use 4 parallel workers
codeweaver migrate apply --workers 4

# Adjust for your system
codeweaver migrate apply \
  --workers 8 \
  --max-concurrent-requests 50 \
  --rate-limit 100
```

**Resource considerations**:
- CPU cores: Set `--workers` = (cores - 1)
- Memory: Each worker uses ~500MB
- API rate limits: Adjust `--rate-limit`

### Checkpoint Management

Checkpoints enable resume and rollback:

```bash
# Create checkpoint before risky operation
codeweaver migrate checkpoint create "before_quantization"

# List checkpoints
codeweaver migrate checkpoint list

# Restore from specific checkpoint
codeweaver migrate checkpoint restore "before_quantization"

# Clean old checkpoints (keep last 5)
codeweaver migrate checkpoint clean --keep 5
```

### Progressive Migration

For large collections, migrate incrementally:

```bash
# Migrate with frequent checkpoints
codeweaver migrate apply \
  --checkpoint-interval 500 \
  --batch-size 100

# Resume interrupted migration
codeweaver migrate resume

# Monitor progress
codeweaver migrate status --watch
```

### Validation Tuning

Control validation strictness:

```bash
# Strict validation (default)
codeweaver migrate apply --validate strict

# Relaxed validation (faster)
codeweaver migrate apply --validate relaxed

# Skip validation (not recommended)
codeweaver migrate apply --no-validate
```

---

## Best Practices

### Before Migration

1. **Backup your collection**
   ```bash
   codeweaver backup create
   ```

2. **Test on small subset**
   ```bash
   # Test with first 1000 vectors
   codeweaver migrate apply --limit 1000 --dry-run
   ```

3. **Check available resources**
   ```bash
   codeweaver doctor --verbose
   ```

4. **Review migration plan**
   ```bash
   codeweaver migrate preview --detailed
   ```

### During Migration

1. **Use checkpoints for large collections**
   ```bash
   # Checkpoint every 1000 vectors
   codeweaver migrate apply --checkpoint-interval 1000
   ```

2. **Monitor progress**
   ```bash
   # In another terminal
   watch -n 5 'codeweaver migrate status'
   ```

3. **Adjust workers based on performance**
   ```bash
   # Start conservative
   codeweaver migrate apply --workers 2

   # Scale up if resources allow
   # (cancel and resume with more workers)
   codeweaver migrate resume --workers 4
   ```

### After Migration

1. **Validate data integrity**
   ```bash
   codeweaver migrate validate
   ```

2. **Compare search quality**
   ```bash
   # Run sample queries
   codeweaver search "critical queries" --limit 10
   ```

3. **Check storage savings**
   ```bash
   codeweaver doctor
   ```

4. **Clean up checkpoints**
   ```bash
   codeweaver migrate checkpoint clean
   ```

### Production Recommendations

**For production environments**:
- Use `STRICT` or `FAMILY_AWARE` policy
- Always create backup before migration
- Test migrations in staging first
- Use conservative worker counts
- Enable frequent checkpointing
- Validate results thoroughly

**Example production workflow**:
```bash
# 1. Backup
codeweaver backup create production_$(date +%Y%m%d)

# 2. Test in staging
codeweaver --project ./staging migrate apply --dry-run

# 3. Apply to production with safety
codeweaver --project ./production migrate apply \
  --workers 2 \
  --checkpoint-interval 500 \
  --validate strict \
  --retry-limit 3

# 4. Validate
codeweaver --project ./production migrate validate

# 5. Monitor for issues
# Check search quality, performance metrics
```

### Performance Tips

**Optimize migration speed**:
```bash
# Faster (fewer safety checks)
codeweaver migrate apply \
  --workers 8 \
  --batch-size 500 \
  --checkpoint-interval 5000 \
  --validate relaxed

# Safer (more validation)
codeweaver migrate apply \
  --workers 2 \
  --batch-size 100 \
  --checkpoint-interval 500 \
  --validate strict
```

**Trade-offs**:
- More workers = faster but more memory
- Larger batches = faster but less checkpoint granularity
- Less frequent checkpoints = faster but harder to recover
- Relaxed validation = faster but may miss issues

---

## Next Steps

- [API Reference](api-reference.md) - Detailed API documentation
- [Troubleshooting Guide](troubleshooting-migration.md) - Common issues and solutions
- [CLI Reference](CLI.md) - Complete command reference

---

## Related Documentation

- [Configuration Guide](configuration.md)
- [Indexing Guide](indexing.md)
- [Collection Management](collections.md)
