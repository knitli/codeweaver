# Fix: test_inmemory_persistence Dimension Mismatch

## Problem

Test `tests/integration/test_memory_persistence.py::test_inmemory_persistence` was failing with:
```
ValueError: could not broadcast input array from shape (512,) into shape (384,)
```

## Root Cause Analysis

1. **Test hardcoded 512 dimensions** for dense embeddings in lines 58 and 82
2. **Actual collection dimension** depends on the configured embedding provider:
   - Testing profile (with sentence_transformers): `minishlab/potion-base-8M` → **256 dimensions**
   - Fallback (without sentence_transformers): `BAAI/bge-small-en-v1.5` → **384 dimensions**
   - Base default: **512 dimensions**

3. **Mismatch occurred** because:
   - Test created embeddings with hardcoded 512 dimensions
   - Collection was created with 384 dimensions (BAAI fallback model)
   - Qdrant rejected the dimension mismatch during upsert

## Configuration Flow

```
testing profile → minishlab/potion-base-8M (256 dims) if HAS_ST
                → BAAI/bge-small-en-v1.5 (384 dims) otherwise
                → default 512 dims if no config
```

## Solution

**Changed from:** Hardcoded 512-dimension embeddings
**Changed to:** Dynamically query the actual embedding dimension from the provider configuration

### Code Changes

**Before:**
```python
dense_embedding=[0.7] * 512,  # Match default dimension (512)
```

**After:**
```python
dense_caps = provider1._embedding_caps.get("dense")
embedding_dim = dense_caps.default_dimension if dense_caps else 512

dense_embedding=[0.7] * embedding_dim,  # Match actual configured dimension
```

This was applied to both:
1. Phase 1: Creating and upserting the test chunk (line ~61)
2. Phase 2: Searching for the restored chunk (line ~89)

## Why This is the Correct Fix

1. **Test Configuration Independence**: Test now works regardless of which embedding provider is configured
2. **Matches Production Behavior**: Uses the same dimension resolution as production code
3. **Environment Resilience**: Works whether sentence_transformers is available or not
4. **Future-Proof**: Automatically adapts if default models change

## Testing

Test now passes successfully:
```bash
pytest tests/integration/test_memory_persistence.py::test_inmemory_persistence -xvs
# Result: PASSED ✅
```

## Files Modified

- `/home/knitli/codeweaver/tests/integration/test_memory_persistence.py`
  - Lines 50-53: Query embedding dimension from provider configuration
  - Line 61: Use dynamic `embedding_dim` instead of hardcoded 512
  - Lines 82-83: Query dimension again for phase 2
  - Line 89: Use dynamic `embedding_dim2` instead of hardcoded 512

## Related Code

- `/home/knitli/codeweaver/src/codeweaver/providers/vector_stores/base.py`:
  - `_default_embedding_caps()` factory function
  - `_get_caps()` dimension resolution logic
- `/home/knitli/codeweaver/src/codeweaver/config/profiles.py`:
  - Backup profile configuration (lines 251-265)
- `/home/knitli/codeweaver/src/codeweaver/providers/embedding/capabilities/`:
  - `minishlab.py`: 256 dims
  - `baai.py`: 384 dims for bge-small-en-v1.5
  - `base.py`: 512 dims default
