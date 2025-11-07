# Provider Switch Implementation Summary

## Overview

Implemented **Option A** from the analysis: Focus on model switching detection with provider switch warnings.

## Changes Made

### 1. **Updated `metadata.py` Validation Logic**

**File:** `src/codeweaver/providers/vector_stores/metadata.py`

**Changes:**
- ✅ Fixed docstring: Changed `ProviderSwitchError` → `ModelSwitchError`
- ✅ Added provider switch warning (logs but doesn't block)
- ✅ Enhanced model switch detection with backwards compatibility

**Key Implementation:**

```python
def validate_compatibility(self, other: CollectionMetadata) -> None:
    """Validate collection metadata against current provider configuration.

    Args:
        other: Other collection metadata to compare against

    Raises:
        ModelSwitchError: If embedding models don't match
        DimensionMismatchError: If embedding dimensions don't match

    Warnings:
        Logs warning if provider has changed (suggests reindexing)
    """
    # Warn on provider switch - suggests reindexing but doesn't block
    if self.provider != other.provider:
        logger.warning(
            f"Provider switch detected: collection created with '{other.provider}', "
            f"but current provider is '{self.provider}'. "
            f"You should reindex your codebase to ensure data consistency. "
            f"Run 'codeweaver index' to rebuild the collection with the new provider."
        )

    # Error on model switch - this corrupts search results
    # Only raise if both have models and they differ (allow None for backwards compatibility)
    if (
        self.embedding_model
        and other.embedding_model
        and self.embedding_model != other.embedding_model
    ):
        raise ModelSwitchError(
            f"Your existing embedding collection was created with model '{other.embedding_model}', "
            f"but the current model is '{self.embedding_model}'. "
            f"You can't use different embedding models for the same collection.",
            suggestions=[...],
            details={...}
        )
```

---

### 2. **Created New Test Suite**

**File:** `tests/integration/test_model_switch.py` (NEW)

**Tests Implemented:**

#### ✅ `test_model_switch_detection`
Verifies that switching embedding models raises `ModelSwitchError` with:
- Clear error message mentioning both models
- Suggestions for remediation (re-index, revert, delete, rename)
- Detailed error metadata

#### ✅ `test_provider_switch_warning`
Verifies that switching providers (with same model) logs a warning:
- Warning message includes both provider names
- Suggests reindexing
- Does NOT raise an error

#### ✅ `test_dimension_mismatch_detection`
Verifies that dimension mismatches raise `DimensionMismatchError`:
- Clear error message with dimensions
- Remediation suggestions

#### ✅ `test_compatible_metadata_no_error`
Verifies that compatible configurations work without errors:
- Same provider, model, and dimensions pass validation

#### ✅ `test_model_switch_with_none_embedding`
Verifies backwards compatibility:
- Old collections without `embedding_model` (None) don't raise errors
- Allows migration from legacy data

---

### 3. **Deprecated Old Test**

**File:** `tests/integration/test_provider_switch.py` → `test_provider_switch.py.old`

**Why:**
- Test was architecturally flawed (Memory vs Qdrant can't share collections)
- Expected `ProviderSwitchError` which is no longer raised
- Replaced with comprehensive `test_model_switch.py`

---

## Design Decisions

### ✅ **Model Switching: BLOCK**

**Rationale:** Mixing embedding models corrupts search results
- voyage-code-3 (1536D) → text-embedding-ada-002 (1536D) = **INCOMPATIBLE**
- Even with same dimensions, embeddings are semantically different
- **Action:** Raise `ModelSwitchError`

### ⚠️ **Provider Switching: WARN**

**Rationale:** Provider switching is acceptable with data migration
- Qdrant → Pinecone with same model = **OK IF DATA MIGRATED**
- User may legitimately want to change vector store
- **Action:** Log warning suggesting reindex, but don't block

### 🔧 **Dimension Mismatch: BLOCK**

**Rationale:** Different dimensions can't be compared
- 1536D → 768D = **INCOMPATIBLE**
- Vector search requires matching dimensions
- **Action:** Raise `DimensionMismatchError`

### 🕰️ **Backwards Compatibility: ALLOW**

**Rationale:** Old collections may not have model tracking
- Legacy data with `embedding_model=None`
- **Action:** Allow None models (don't raise error)

---

## Test Results

```bash
$ python -m pytest tests/integration/test_model_switch.py -v

tests/integration/test_model_switch.py::test_model_switch_detection PASSED
tests/integration/test_model_switch.py::test_provider_switch_warning PASSED
tests/integration/test_model_switch.py::test_dimension_mismatch_detection PASSED
tests/integration/test_model_switch.py::test_compatible_metadata_no_error PASSED
tests/integration/test_model_switch.py::test_model_switch_with_none_embedding PASSED

============================== 5 passed in 10.85s ==============================
```

---

## User Experience

### **Scenario 1: User Switches Embedding Model**

```bash
$ codeweaver search "authentication"

Error: ModelSwitchError
Your existing embedding collection was created with model 'voyage-code-3',
but the current model is 'text-embedding-ada-002'. You can't use different
embedding models for the same collection.

Suggestions:
  • Option 1: Re-index your codebase with the new provider
  • Option 2: Revert provider setting to match the collection
  • Option 3: Delete the existing collection and re-index
  • Option 4: Create a new collection with a different name
```

### **Scenario 2: User Switches Vector Store Provider**

```bash
$ codeweaver search "authentication"

WARNING: Provider switch detected: collection created with 'qdrant',
but current provider is 'pinecone'. You should reindex your codebase
to ensure data consistency. Run 'codeweaver index' to rebuild the
collection with the new provider.

[Search continues normally...]
```

---

## Files Modified

| File | Changes |
|------|---------|
| `src/codeweaver/providers/vector_stores/metadata.py` | Added provider warning, fixed docstring, enhanced model validation |
| `tests/integration/test_model_switch.py` | NEW - Comprehensive test suite (5 tests) |
| `tests/integration/test_provider_switch.py` | Renamed to `.old` (deprecated) |

---

## Alignment with Architecture

### ✅ **Matches Stated Concerns**

Your stated concern: **"Folks trying to mix embedding models"**
- ✅ Blocks model switching with clear error
- ✅ Allows provider switching with warning
- ✅ Suggests reindexing for data migration

### ✅ **Follows Exception Hierarchy**

```
ProviderError
├── ModelSwitchError ← USED for model changes
├── DimensionMismatchError ← USED for dimension mismatches
└── ProviderSwitchError ← NOT USED (kept for future)
```

### ✅ **Backwards Compatible**

- Old collections without `embedding_model` field work
- None values handled gracefully
- Migration path exists

---

## Future Considerations

### **Should We Remove `ProviderSwitchError`?**

**Options:**
1. **Keep but mark as unused** - Reserve for future provider validation
2. **Remove entirely** - Clean up unused code
3. **Implement fully** - Block provider switching completely

**Recommendation:** Keep for now, document as "reserved for future use"

### **Should We Validate Storage Backend Compatibility?**

**Example:** Qdrant (persistent) → Memory (ephemeral)
- Data loss risk
- Could warn users
- Low priority (users will notice missing data)

---

## Conclusion

Implementation complete! The codebase now:
- ✅ Prevents embedding model mixing (primary concern)
- ✅ Warns on provider switching (suggests reindex)
- ✅ Validates dimension compatibility
- ✅ Maintains backwards compatibility
- ✅ Provides clear user-facing error messages
- ✅ All tests passing (5/5)

The old architecturally-flawed test has been replaced with a comprehensive test suite that validates the actual user-facing concerns.
