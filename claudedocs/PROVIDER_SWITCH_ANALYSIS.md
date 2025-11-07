# Provider Switch Test: Alignment Analysis

## Current State Misalignments

### 1. **Docstring vs Implementation**

**File:** `src/codeweaver/providers/vector_stores/metadata.py:76-102`

```python
def validate_compatibility(self, other: CollectionMetadata) -> None:
    """...
    Raises:
        ProviderSwitchError: If provider doesn't match collection metadata  # ⚠️ WRONG
        DimensionMismatchError: If embedding dimensions don't match
    """
    if self.embedding_model and self.embedding_model != other.embedding_model:
        raise ModelSwitchError(  # ✅ ACTUAL IMPLEMENTATION
            ...
        )
```

**Issue:** Docstring claims `ProviderSwitchError`, but code raises `ModelSwitchError`

---

### 2. **Test Expectation vs Reality**

**File:** `tests/integration/test_provider_switch.py:26-69`

```python
async def test_provider_switch_detection(qdrant_test_manager):
    # Phase 1: Create collection with Qdrant
    qdrant_provider = QdrantVectorStoreProvider(...)

    # Phase 2: Try to use same collection with Memory provider
    memory_provider = MemoryVectorStoreProvider(config={"collection_name": collection_name})

    # Should raise ProviderSwitchError ⚠️
    with pytest.raises(ProviderSwitchError) as exc_info:
        await memory_provider._initialize()
```

**Issues:**
1. Test expects `ProviderSwitchError` but implementation only raises `ModelSwitchError`
2. **Architectural flaw:** Qdrant (server) and Memory (in-memory) use completely separate storage
   - Qdrant: Persistent server with gRPC API
   - Memory: Local Qdrant in `:memory:` mode
   - They **cannot share collections** - different storage backends entirely
3. Test will never raise an error because Memory provider creates its own new collection

---

### 3. **Architectural Concern: What Should We Actually Prevent?**

Based on your explanation:

#### ✅ **Real Concern: Model Switching**
```yaml
scenario: "User changes embedding model"
example:
  original: "voyage-code-3 (1536 dimensions)"
  changed_to: "text-embedding-ada-002 (1536 dimensions)"
problem: "Different embeddings → meaningless similarity search"
solution: "Raise ModelSwitchError ✅ (already implemented)"
```

#### ⚠️ **Not Really a Concern: Provider Switching**
```yaml
scenario: "User changes vector store provider"
example:
  original: "Qdrant"
  changed_to: "Pinecone"
acceptable_if:
  - "Same embedding model"
  - "Migrate embeddings to new provider"
  - "No data loss"
solution: "Allow with migration, not an error ✅"
```

#### 🤔 **Edge Case: Provider + Storage Incompatibility**
```yaml
scenario: "User switches between incompatible storage backends"
example:
  original: "Qdrant server (persistent)"
  changed_to: "Memory (in-memory, non-persistent)"
problem: "Can't access existing data, but also can't corrupt it"
current_behavior: "Memory creates new collection, ignores Qdrant data"
is_this_an_error: "Debatable - data loss vs fresh start?"
```

---

## Decision Matrix: Three Paths Forward

### **Option A: Align on Model Switching Only (RECOMMENDED)**

**Philosophy:** Only prevent embedding model changes, allow provider migration

**Changes Required:**
1. ✅ Keep `ModelSwitchError` implementation (already correct)
2. ❌ Remove `ProviderSwitchError` or mark as unused
3. 🔧 Fix docstring in `metadata.py:83` to say `ModelSwitchError`
4. 🔧 Rename test to `test_model_switch_detection.py`
5. 🔧 Rewrite test to validate model switching:

```python
async def test_model_switch_detection(qdrant_test_manager):
    """Prevent using different embedding models with same collection."""
    # Create collection with voyage-code-3
    await store_chunks_with_model("voyage-code-3")

    # Try to use same collection with different model
    metadata_old = CollectionMetadata(embedding_model="voyage-code-3", ...)
    metadata_new = CollectionMetadata(embedding_model="text-embedding-ada-002", ...)

    with pytest.raises(ModelSwitchError):
        metadata_new.validate_compatibility(metadata_old)
```

**Pros:**
- Aligns with actual architectural concern
- Test validates real user-facing problem
- Clean, focused error handling

**Cons:**
- Doesn't prevent provider switching (but you said that's OK with migration)

---

### **Option B: Implement True Provider Switch Detection**

**Philosophy:** Prevent provider changes even with same model

**Changes Required:**
1. ✅ Keep `ModelSwitchError` for model changes
2. ✅ Keep `ProviderSwitchError` for provider changes
3. 🔧 Add provider validation to `validate_compatibility()`:

```python
def validate_compatibility(self, other: CollectionMetadata) -> None:
    # Check provider first
    if self.provider != other.provider:
        raise ProviderSwitchError(
            f"Collection created with {other.provider}, "
            f"but current provider is {self.provider}",
            suggestions=[...]
        )

    # Then check model (existing code)
    if self.embedding_model != other.embedding_model:
        raise ModelSwitchError(...)
```

4. 🔧 Fix test to use same provider backend (Qdrant → Qdrant with different config)

**Pros:**
- Comprehensive validation
- Prevents accidental provider switches

**Cons:**
- Blocks legitimate migration workflows
- Requires users to delete collections to change providers
- More restrictive than necessary given your stated concerns

---

### **Option C: Test Storage Backend Compatibility**

**Philosophy:** Detect incompatible storage backends (persistent → ephemeral)

**Changes Required:**
1. ✅ Keep current `ModelSwitchError` implementation
2. 🔧 Add storage persistence validation
3. 🔧 Rewrite test to validate storage compatibility:

```python
async def test_storage_backend_incompatibility():
    """Warn when switching from persistent to ephemeral storage."""
    # Create with persistent Qdrant
    await qdrant_provider.store_chunks(...)

    # Detect if user tries to use ephemeral storage
    # (This might just be a warning, not an error)
```

**Pros:**
- Prevents data loss from storage downgrades
- Focused on actual user harm scenario

**Cons:**
- Complex to implement across all providers
- May not be worth the effort (users will notice missing data)

---

## Recommended Action: Option A

**Rationale:**
1. Your stated concern is **model switching** ✅
2. Provider switching is **acceptable with migration** ✅
3. Current implementation **already handles model switching correctly** ✅
4. Test is **architecturally flawed** (Memory vs Qdrant can't share collections) ❌

**Minimal Fix:**
1. Fix docstring: `s/ProviderSwitchError/ModelSwitchError/`
2. Rename test: `test_provider_switch.py` → `test_model_switch.py`
3. Rewrite test to validate model switching, not provider switching
4. Consider deprecating `ProviderSwitchError` (or keep for future use)

---

## Implementation Proposal

**File Changes:**

### 1. `src/codeweaver/providers/vector_stores/metadata.py`

```python
def validate_compatibility(self, other: CollectionMetadata) -> None:
    """Validate collection metadata against current provider configuration.

    Args:
        other: Other collection metadata to compare against

    Raises:
        ModelSwitchError: If embedding models don't match  # ✅ FIXED
        DimensionMismatchError: If embedding dimensions don't match
    """
    # ... existing implementation (no code changes needed)
```

### 2. `tests/integration/test_provider_switch.py` → `tests/integration/test_model_switch.py`

```python
"""Integration test: Model switch detection to prevent embedding corruption."""

from codeweaver.exceptions import ModelSwitchError
from codeweaver.providers.vector_stores.metadata import CollectionMetadata


async def test_model_switch_detection():
    """Prevent using different embedding models with same collection."""
    metadata_original = CollectionMetadata(
        provider="qdrant",
        project_name="test-project",
        embedding_model="voyage-code-3",
        embedding_dim_dense=1536,
        vector_config={},
    )

    metadata_switched = CollectionMetadata(
        provider="qdrant",  # Same provider OK
        project_name="test-project",
        embedding_model="text-embedding-ada-002",  # Different model NOT OK
        embedding_dim_dense=1536,
        vector_config={},
    )

    with pytest.raises(ModelSwitchError) as exc_info:
        metadata_switched.validate_compatibility(metadata_original)

    error_msg = str(exc_info.value).lower()
    assert "voyage-code-3" in error_msg
    assert "text-embedding-ada-002" in error_msg
    assert "re-index" in error_msg

    print("✅ Model switch detected with clear error message")
```

---

## Questions for Decision

1. **Should we prevent provider switching at all?**
   - Your answer: No, provider switching is OK with data migration ✅

2. **Should we deprecate `ProviderSwitchError`?**
   - Option A: Remove it entirely
   - Option B: Keep for future use (documented as unused)
   - Option C: Implement provider validation later

3. **Should we warn about storage backend incompatibility?**
   - Memory → Qdrant: Upgrade to persistent (safe)
   - Qdrant → Memory: Downgrade to ephemeral (data loss risk)
   - Or just let users discover this naturally?

---

## Conclusion

The test is failing because:
1. ✅ **Implementation is correct** - raises `ModelSwitchError` for model changes
2. ❌ **Test is wrong** - expects `ProviderSwitchError` which is never raised
3. ❌ **Test scenario is flawed** - Memory and Qdrant can't share collections anyway
4. ⚠️ **Docstring is misleading** - claims `ProviderSwitchError` but code raises `ModelSwitchError`

**Recommended fix:** Align everything on model switching (Option A), which matches your stated architectural concern.
