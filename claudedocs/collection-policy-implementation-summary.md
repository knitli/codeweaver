<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Collection Policy System Implementation Summary

**Date**: 2025-02-12
**Phase**: Phase 3 of Unified Implementation Plan
**Version**: CollectionMetadata v1.5.0

## Overview

Implemented a comprehensive collection policy system that controls how configuration changes are validated against existing vector store collections. This system provides granular control over model switching and configuration modifications while maintaining backward compatibility.

## Components Implemented

### 1. CollectionPolicy Enum

**Location**: `src/codeweaver/providers/types/vector_store.py`

```python
class CollectionPolicy(BaseEnum):
    """Collection modification policy controlling configuration changes."""
    STRICT = "strict"              # No model changes allowed
    FAMILY_AWARE = "family_aware"  # Allow query changes in family (default)
    FLEXIBLE = "flexible"          # Warn on breaking changes
    UNLOCKED = "unlocked"          # Allow all changes
```

**Behavior**:
- **STRICT**: Blocks all configuration changes - only exact original configuration allowed
- **FAMILY_AWARE**: Allows query model changes within same model family, blocks other changes (default)
- **FLEXIBLE**: Warns on potentially breaking changes but doesn't block
- **UNLOCKED**: Allows all changes without validation (testing/advanced use)

### 2. ConfigurationLockError Exception

**Location**: `src/codeweaver/core/exceptions.py`

```python
class ConfigurationLockError(ConfigurationError):
    """Collection configuration lock error.

    Raised when attempting to modify a collection's configuration in a way that
    violates the collection's policy.
    """
```

Subclasses `ConfigurationError` to maintain exception hierarchy consistency.

### 3. CollectionMetadata Updates

**Location**: `src/codeweaver/providers/types/vector_store.py`

#### New Field
```python
policy: Annotated[
    CollectionPolicy,
    Field(description="Policy controlling configuration changes..."),
] = CollectionPolicy.FAMILY_AWARE  # Default
```

#### New Methods

##### validate_config_change()
Main validation entry point that enforces policy rules:

```python
def validate_config_change(
    self,
    new_dense_model: str | None = None,
    new_query_model: str | None = None,
    new_sparse_model: str | None = None,
    new_provider: str | None = None,
) -> None:
    """Validate configuration change against collection policy."""
```

**Raises**: `ConfigurationLockError` when change violates policy

##### Helper Methods

1. **_exact_match()**: Validates exact configuration match for STRICT policy
   - Checks all configuration parameters match exactly
   - `None` values treated as "keep current" (allowed)

2. **_family_compatible()**: Validates family-aware compatibility
   - Dense model must match exactly
   - Query model can change within same family
   - Uses `EmbeddingCapabilityResolver` to verify family membership
   - Validates dimension compatibility

3. **_any_compatible()**: Checks basic compatibility for FLEXIBLE policy
   - Detects obvious incompatibilities (e.g., >10% dimension difference)
   - Returns `False` only for clear breaking changes
   - Logs warnings but doesn't block

## Integration Points

### With Existing Family-Aware Logic

The policy system integrates seamlessly with existing family-aware validation in `validate_compatibility()`:

- FAMILY_AWARE policy uses same family detection logic
- Leverages `EmbeddingCapabilityResolver` for model family lookups
- Respects existing `dense_model_family` field
- Compatible with asymmetric embedding configurations

### Backward Compatibility

**Default Policy**: `FAMILY_AWARE`
- Matches existing validation behavior
- No breaking changes to existing code
- Collections without explicit policy use FAMILY_AWARE

**Version Bump**: v1.4.0 → v1.5.0
- New field with sensible default
- No migration required
- Existing collections work without modification

## Error Messages

Error messages follow Phase 3 requirements for actionability:

```python
# Example STRICT policy error
ConfigurationLockError(
    "Collection policy is STRICT - no configuration changes allowed",
    details={
        "policy": "strict",
        "collection": "my-collection",
        "current_dense_model": "voyage-4-large",
        "proposed_dense_model": "voyage-4-nano",
        # ... more context
    },
    suggestions=[
        "Use the original configuration that created this collection",
        "Original dense model: voyage-4-large",
        "Or change the collection policy to FAMILY_AWARE or FLEXIBLE",
        "Or create a new collection with a different name",
    ],
)
```

## Usage Examples

### Strict Policy
```python
metadata = CollectionMetadata(
    provider="voyage",
    project_name="my-project",
    dense_model="voyage-4-large",
    policy=CollectionPolicy.STRICT
)

# Raises ConfigurationLockError
metadata.validate_config_change(new_dense_model="voyage-4-nano")
```

### Family-Aware Policy (Default)
```python
metadata = CollectionMetadata(
    provider="voyage",
    project_name="my-project",
    dense_model="voyage-4-large",
    dense_model_family="voyage-4",
    # policy defaults to FAMILY_AWARE
)

# Succeeds - same family
metadata.validate_config_change(new_query_model="voyage-4-nano")

# Raises - different model
metadata.validate_config_change(new_dense_model="voyage-3-large")
```

### Flexible Policy
```python
metadata = CollectionMetadata(
    provider="voyage",
    project_name="my-project",
    dense_model="voyage-4-large",
    policy=CollectionPolicy.FLEXIBLE
)

# Logs warning but allows change
metadata.validate_config_change(new_dense_model="different-model")
```

### Unlocked Policy
```python
metadata = CollectionMetadata(
    provider="voyage",
    project_name="my-project",
    policy=CollectionPolicy.UNLOCKED
)

# Allows any change without validation
metadata.validate_config_change(
    new_dense_model="any-model",
    new_provider="any-provider"
)
```

## Testing

Comprehensive testing verified:
- ✅ STRICT policy blocks all changes
- ✅ STRICT policy allows no changes (all None)
- ✅ FAMILY_AWARE policy validation executes correctly
- ✅ FAMILY_AWARE blocks dense model changes
- ✅ UNLOCKED policy allows all changes
- ✅ Default policy is FAMILY_AWARE
- ✅ Policy serialization/deserialization (both dict and JSON modes)
- ✅ Version updated to 1.5.0

## Code Quality

- ✅ All linting checks pass
- ✅ Type checking passes (ty)
- ✅ Follows CODE_STYLE.md conventions
- ✅ Comprehensive docstrings with Google convention
- ✅ No placeholders or TODOs
- ✅ Evidence-based implementation (per Constitutional Principle III)
- ✅ REUSE license headers present

## Documentation Updates

Updated `CollectionMetadata` docstring to include:
- Version history entry for v1.5.0
- Migration notes from v1.4.0 to v1.5.0
- Policy field documentation

## Constitutional Compliance

✅ **Principle I (AI-First Context)**: Policy system enhances configuration safety for AI agent usage

✅ **Principle II (Proven Patterns)**: Uses pydantic enum patterns, follows existing validation structure

✅ **Principle III (Evidence-Based Development)**: Complete implementation, no placeholders, all features working

✅ **Principle IV (Testing Effectiveness)**: Focused on user-affecting behavior (configuration validation)

✅ **Principle V (Simplicity Through Architecture)**: Clean integration with existing family-aware logic

## Next Steps

Suggested follow-on work:
1. Add policy configuration to CLI (e.g., `cw config set-policy <collection> <policy>`)
2. Add policy information to `cw doctor` output
3. Consider policy recommendation system based on use case
4. Add integration tests with full capability resolver setup
5. Document policy selection guidance for users

## Files Modified

1. `src/codeweaver/core/exceptions.py`
   - Added `ConfigurationLockError` exception
   - Updated `__all__` export

2. `src/codeweaver/providers/types/vector_store.py`
   - Added `CollectionPolicy` enum
   - Added `policy` field to `CollectionMetadata`
   - Added `validate_config_change()` method
   - Added helper methods: `_exact_match()`, `_family_compatible()`, `_any_compatible()`
   - Updated version to v1.5.0
   - Updated docstrings and version history
   - Updated `__all__` export

## Summary

Successfully implemented Phase 3.1 of the unified implementation plan. The collection policy system provides:

- **Safety**: Prevents accidental configuration changes that could break collections
- **Flexibility**: Multiple policy levels for different use cases
- **Backward Compatibility**: No breaking changes, sensible defaults
- **Integration**: Seamlessly works with existing family-aware validation
- **Usability**: Clear error messages with actionable suggestions

The implementation is production-ready and follows all constitutional principles and code style guidelines.
