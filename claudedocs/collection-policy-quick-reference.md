<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Collection Policy System - Quick Reference

## Policy Levels

| Policy | Dense Model | Query Model | Sparse Model | Provider | Use Case |
|--------|-------------|-------------|--------------|----------|----------|
| **STRICT** | ❌ No changes | ❌ No changes | ❌ No changes | ❌ No changes | Production collections, regulatory compliance |
| **FAMILY_AWARE** ⭐ | ❌ Must match | ✅ Within family | ❌ Must match | ⚠️ Warn only | Default, asymmetric embedding |
| **FLEXIBLE** | ⚠️ Warn only | ⚠️ Warn only | ⚠️ Warn only | ⚠️ Warn only | Development, experimentation |
| **UNLOCKED** | ✅ Allow all | ✅ Allow all | ✅ Allow all | ✅ Allow all | Testing, advanced users |

⭐ = Default policy

## Quick API Reference

### Setting Policy

```python
from codeweaver.providers.types.vector_store import CollectionMetadata, CollectionPolicy

# Create with specific policy
metadata = CollectionMetadata(
    provider="voyage",
    project_name="my-project",
    dense_model="voyage-4-large",
    policy=CollectionPolicy.STRICT  # or FAMILY_AWARE, FLEXIBLE, UNLOCKED
)
```

### Validating Changes

```python
# Validate configuration change before applying
try:
    metadata.validate_config_change(
        new_dense_model="voyage-4-nano",  # or None to keep current
        new_query_model="voyage-4-nano",   # or None to keep current
        new_sparse_model=None,              # or new model
        new_provider=None                   # or new provider
    )
    # Change is allowed - proceed
except ConfigurationLockError as e:
    # Change blocked by policy
    print(f"Cannot change: {e.message}")
    for suggestion in e.suggestions:
        print(f"  - {suggestion}")
```

## Policy Selection Guide

### When to Use STRICT
- ✅ Production collections with regulatory requirements
- ✅ Shared collections across teams
- ✅ Collections with strict reproducibility requirements
- ✅ When configuration must never change

### When to Use FAMILY_AWARE (Default)
- ✅ Most use cases (recommended default)
- ✅ Asymmetric embedding configurations
- ✅ When you want flexibility for query model optimization
- ✅ Balance between safety and flexibility

### When to Use FLEXIBLE
- ✅ Development and experimentation
- ✅ Prototype collections
- ✅ When you understand the risks
- ✅ Collections that can tolerate degraded quality

### When to Use UNLOCKED
- ✅ Testing environments only
- ✅ Temporary collections
- ✅ Advanced users who fully understand implications
- ❌ Never for production

## Policy Behavior Matrix

### STRICT Policy

| Change Type | Behavior | Notes |
|-------------|----------|-------|
| Dense model | ❌ Block | Must exactly match original |
| Query model | ❌ Block | Must exactly match original (or be None) |
| Sparse model | ❌ Block | Must exactly match original (or be None) |
| Provider | ❌ Block | Must exactly match original |
| No changes | ✅ Allow | Passing all None is allowed |

### FAMILY_AWARE Policy (Default)

| Change Type | Behavior | Notes |
|-------------|----------|-------|
| Dense model | ❌ Block | Must exactly match indexed model |
| Query model to same family | ✅ Allow | Enables asymmetric embedding |
| Query model to different family | ❌ Block | Would break vector compatibility |
| Sparse model | ❌ Block | Must exactly match indexed model |
| Provider with family | ❌ Block | Would break family tracking |
| Provider without family | ⚠️ Warn | Backward compatibility mode |

### FLEXIBLE Policy

| Change Type | Behavior | Notes |
|-------------|----------|-------|
| Any model change | ⚠️ Warn | Checks for obvious incompatibilities |
| Large dimension change (>10%) | ❌ Block | Would definitely break |
| Provider change | ⚠️ Warn | Logs warning |
| Compatible changes | ✅ Allow | Silently allows |

### UNLOCKED Policy

| Change Type | Behavior | Notes |
|-------------|----------|-------|
| Any change | ✅ Allow | No validation performed |
| All fields | ✅ Allow | Use with caution |

## Error Handling

### ConfigurationLockError Structure

```python
try:
    metadata.validate_config_change(new_dense_model="different-model")
except ConfigurationLockError as e:
    # e.message: Human-readable error message
    # e.details: Dict with context (models, collection name, etc.)
    # e.suggestions: List of actionable suggestions
    # e.location: Where error was raised (file, line, module)
```

### Error Message Example

```
ConfigurationLockError: Collection policy is STRICT - no configuration changes allowed

Details:
- policy: strict
- collection: my-collection
- current_dense_model: voyage-4-large
- proposed_dense_model: voyage-4-nano

Suggestions:
- Use the original configuration that created this collection
- Original dense model: voyage-4-large
- Or change the collection policy to FAMILY_AWARE or FLEXIBLE
- Or create a new collection with a different name
```

## Integration with Existing Code

### validate_compatibility() vs validate_config_change()

| Method | Purpose | When to Use |
|--------|---------|-------------|
| `validate_compatibility()` | Compare collection metadata objects | When loading existing collection |
| `validate_config_change()` | Validate proposed changes | Before applying configuration changes |

Both methods respect the policy setting, but `validate_compatibility()` focuses on metadata-to-metadata comparison while `validate_config_change()` validates individual field changes.

## Migration Path

### From No Policy to Policy

Existing collections without explicit policy:
1. Default to `FAMILY_AWARE` automatically
2. No code changes required
3. Behavior matches existing family-aware validation
4. Can explicitly set policy via metadata update

### Changing Policy on Existing Collection

```python
# Load existing collection
metadata = CollectionMetadata.from_collection(collection_data)

# Update policy (requires collection metadata update)
metadata.policy = CollectionPolicy.FLEXIBLE

# Save back to collection
# (Implementation depends on vector store provider)
```

## Common Patterns

### Optimizing Query Performance

```python
# Use high-quality model for indexing
metadata = CollectionMetadata(
    provider="voyage",
    project_name="my-project",
    dense_model="voyage-4-large",      # High quality for documents
    dense_model_family="voyage-4",      # Enable family support
    policy=CollectionPolicy.FAMILY_AWARE  # Allow query optimization
)

# Later: optimize for fast queries
metadata.validate_config_change(
    new_query_model="voyage-4-nano"  # Fast, local, zero-cost
)
# ✅ Succeeds - same family
```

### Locked Production Collection

```python
metadata = CollectionMetadata(
    provider="voyage",
    project_name="production-app",
    dense_model="voyage-4-large",
    policy=CollectionPolicy.STRICT  # No changes allowed
)

# Any change attempt will be blocked
metadata.validate_config_change(new_query_model="voyage-4-nano")
# ❌ Raises ConfigurationLockError
```

### Development Collection

```python
metadata = CollectionMetadata(
    provider="fastembed",
    project_name="dev-experiments",
    dense_model="BAAI/bge-small-en-v1.5",
    policy=CollectionPolicy.FLEXIBLE  # Allow experimentation
)

# Try different model
metadata.validate_config_change(
    new_dense_model="sentence-transformers/all-MiniLM-L6-v2"
)
# ⚠️ Logs warning, but allows change
```

## Implementation Notes

### Version
- CollectionMetadata v1.5.0
- Backward compatible with v1.4.0 and earlier

### Dependencies
- Integrates with `EmbeddingCapabilityResolver` for family detection
- Uses existing family-aware validation logic
- No new external dependencies

### Performance
- O(1) for STRICT, UNLOCKED policies (simple checks)
- O(1) for FAMILY_AWARE policy with resolver cache hit
- Validation happens before costly operations (blocking errors early)

### Thread Safety
- `validate_config_change()` is read-only on metadata
- Safe for concurrent validation calls
- Policy changes should be synchronized externally

## See Also

- [Collection Policy Implementation Summary](./collection-policy-implementation-summary.md)
- [Unified Implementation Plan](./unified-implementation-plan.md) - Phase 3.1
- Source: `src/codeweaver/providers/types/vector_store.py`
