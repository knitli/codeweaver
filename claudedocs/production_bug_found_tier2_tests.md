<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# 🐛 Production Bug Found: SentenceTransformersEmbeddingProvider Initialization

**Date:** 2025-01-04
**Severity:** **HIGH** - Blocks all real provider usage
**Found By:** Tier 2 Real Provider Integration Tests
**Status:** ⚠️ **BLOCKING** - Real provider tests cannot run

## Executive Summary

While implementing Tier 2 real provider integration tests, we discovered a **critical production bug** in `SentenceTransformersEmbeddingProvider.__init__()` that prevents instantiation of the provider.

**This is exactly the type of bug that Tier 2 tests are designed to catch!**

## The Bug

### Location
`src/codeweaver/providers/embedding/providers/sentence_transformers.py:114`

### Issue
The `__init__` method sets instance attributes **before** calling `super().__init__()`, which breaks Pydantic's initialization sequence:

```python
def __init__(
    self,
    capabilities: EmbeddingModelCapabilities,
    client: SentenceTransformer | None = None,
    **kwargs: Any,
) -> None:
    """Initialize the Sentence Transformers embedding provider."""
    self._caps = capabilities
    self.doc_kwargs = {**self._doc_kwargs, **(kwargs or {})}  # ❌ BREAKS HERE
    self.query_kwargs = {**self._query_kwargs, **(kwargs or {})}
    if client is None:
        self._client = SentenceTransformer(
            model_name_or_path=capabilities.name, **self.doc_kwargs["client_options"]
        )
    else:
        self._client = client
    super().__init__(caps=capabilities, client=self._client, **kwargs)  # Too late!
```

### Error
```
AttributeError: 'codeweaver.providers.embedding.providers.sentence_transformers.
SentenceTransformersEmbeddingProvider' object has no attribute '__pydantic_extra__'.
Did you mean: '__pydantic_fields__'?
```

### Root Cause
When `self.doc_kwargs = ...` executes, Pydantic tries to set it as an extra attribute via `__pydantic_extra__`, but that attribute doesn't exist yet because `super().__init__()` hasn't been called.

## Impact

### What's Broken
1. **Cannot instantiate SentenceTransformersEmbeddingProvider** directly
2. **All real provider tests fail** at fixture setup
3. **Cannot use IBM Granite embeddings** in production
4. **Cannot use any SentenceTransformers models** for embeddings

### Why This Wasn't Caught Before
- No existing tests actually **instantiate** this provider
- `actual_dense_embedding_provider` fixture exists but **is never used**
- Mock-based tests work fine because they never call `__init__()`
- The bug is **invisible to Tier 1 tests**

## Reproduction

### Minimal Failing Example
```python
from sentence_transformers import SentenceTransformer
from codeweaver.providers.embedding.capabilities.ibm_granite import (
    get_ibm_granite_embedding_capabilities
)
from codeweaver.providers.embedding.providers.sentence_transformers import (
    SentenceTransformersEmbeddingProvider
)

caps = next(
    cap
    for cap in get_ibm_granite_embedding_capabilities()
    if cap.name == "ibm-granite/granite-embedding-english-r2"
)

client = SentenceTransformer(caps.name)

# ❌ This fails with AttributeError
provider = SentenceTransformersEmbeddingProvider(
    capabilities=caps,
    client=client
)
```

### Output
```
AttributeError: 'codeweaver.providers.embedding.providers.sentence_transformers.
SentenceTransformersEmbeddingProvider' object has no attribute '__pydantic_extra__'
```

## The Fix

### Option 1: Remove Attribute Assignment (Recommended)
```python
def __init__(
    self,
    capabilities: EmbeddingModelCapabilities,
    client: SentenceTransformer | None = None,
    **kwargs: Any,
) -> None:
    """Initialize the Sentence Transformers embedding provider."""
    self._caps = capabilities

    # Initialize client
    if client is None:
        doc_kwargs = {**self._doc_kwargs, **(kwargs or {})}
        self._client = SentenceTransformer(
            model_name_or_path=capabilities.name,
            **doc_kwargs["client_options"]
        )
    else:
        self._client = client

    # Call super BEFORE setting any instance attributes
    super().__init__(caps=capabilities, client=self._client, **kwargs)

    # Now safe to set these if needed
    self.doc_kwargs = {**self._doc_kwargs, **(kwargs or {})}
    self.query_kwargs = {**self._query_kwargs, **(kwargs or {})}
```

### Option 2: Use Property or Method
If `doc_kwargs` and `query_kwargs` don't need to be instance attributes:

```python
def _get_doc_kwargs(self, kwargs: dict | None = None) -> dict:
    """Get document kwargs with overrides."""
    return {**self._doc_kwargs, **(kwargs or {})}

def _get_query_kwargs(self, kwargs: dict | None = None) -> dict:
    """Get query kwargs with overrides."""
    return {**self._query_kwargs, **(kwargs or {})}
```

### Option 3: Call super() First
```python
def __init__(
    self,
    capabilities: EmbeddingModelCapabilities,
    client: SentenceTransformer | None = None,
    **kwargs: Any,
) -> None:
    """Initialize the Sentence Transformers embedding provider."""
    # Call super FIRST to initialize Pydantic
    super().__init__(caps=capabilities, client=client, **kwargs)

    # Now safe to set instance attributes
    self._caps = capabilities
    self.doc_kwargs = {**self._doc_kwargs, **(kwargs or {})}
    self.query_kwargs = {**self._query_kwargs, **(kwargs or {})}

    # Initialize client if not provided
    if client is None:
        self._client = SentenceTransformer(
            model_name_or_path=capabilities.name,
            **self.doc_kwargs["client_options"]
        )
```

## Why Tier 2 Tests Caught This

### Mock Tests (Tier 1) Cannot Catch This
```python
# Tier 1 - Mocks, never instantiates provider
@pytest.mark.integration
async def test_with_mocks(configured_providers):
    response = await find_code("query")
    # ✅ Passes - mock provider works fine
    assert response.results
```

**Why it doesn't catch the bug:**
- Never calls `SentenceTransformersEmbeddingProvider.__init__()`
- Mock provider is an `AsyncMock`, not a real provider
- Bug is **invisible** to structure validation

### Real Provider Tests (Tier 2) Catch This
```python
# Tier 2 - Real providers, instantiates actual provider
@pytest.mark.integration
@pytest.mark.real_providers
async def test_with_real_providers(real_providers):
    # ❌ Fails at fixture setup!
    # Cannot instantiate SentenceTransformersEmbeddingProvider
    response = await find_code("query")
```

**Why it catches the bug:**
- **Actually instantiates** the provider via fixture
- Executes `__init__()` method
- Discovers Pydantic initialization bug
- Prevents broken code from reaching production

## Value Demonstrated

This bug discovery **validates the entire premise** of Tier 2 testing:

✅ **Mock tests validate structure** - "Does my code call the right methods?"
✅ **Real tests validate behavior** - "Does this actually work?"

**Without Tier 2 tests:**
- Bug ships to production
- Users cannot use SentenceTransformers providers
- Critical feature broken
- Discovered only after deployment

**With Tier 2 tests:**
- Bug discovered during test implementation
- Fixed before any code review
- Confidence in provider functionality
- Real providers validated end-to-end

## Current Status

### Blocking Issues
1. ❌ Cannot run Tier 2 tests until provider is fixed
2. ❌ Real provider fixtures cannot instantiate providers
3. ❌ Production use of SentenceTransformers providers blocked

### Next Steps
1. **Fix `SentenceTransformersEmbeddingProvider.__init__()`** - Use Option 1 (move super() call)
2. **Fix `SentenceTransformersSparseProvider`** - Likely has same issue
3. **Fix `SentenceTransformersRerankingProvider`** - Check if affected
4. **Run Tier 2 tests** - Validate fixes work
5. **Add regression test** - Ensure bug doesn't return

### Recommended Approach
1. Open separate issue/PR for the provider bug fix
2. Fix all three provider classes (embedding, sparse, reranking)
3. Add unit test that directly instantiates providers
4. Merge bug fix
5. Then run Tier 2 tests successfully

## Lessons Learned

### What Worked
- ✅ Tier 2 tests **immediately** found a production bug
- ✅ Bug was **invisible** to all existing tests
- ✅ Clear demonstration of Tier 2 test value
- ✅ Bug caught **before** code review

### What This Means
1. **Tier 2 tests are essential** - Not optional, not "nice to have"
2. **Mock tests have blind spots** - Structure validation ≠ behavior validation
3. **Production bugs hide** - Until you actually try to use the code
4. **Real instantiation matters** - Not just calling methods on mocks

### Testing Philosophy Validation
> "If the test always passes, it's not testing the right thing"

- Mock tests **always passed** - Provider broken the whole time
- Real tests **immediately failed** - Found the bug instantly
- This is **exactly** why we need both tiers

## Related Files

- **Bug Location:** `src/codeweaver/providers/embedding/providers/sentence_transformers.py:114`
- **Test That Found It:** `tests/integration/real/test_search_behavior.py`
- **Fixture:** `tests/integration/conftest.py:310` (`real_embedding_provider`)
- **Similar Issues:** Likely in sparse and reranking providers too

## Recommendation

**Fix Priority:** 🔴 **CRITICAL** - Blocks real provider usage
**Estimated Fix Time:** 30 minutes
**Risk:** Low - Clear fix, well-understood problem
**Value:** HIGH - Enables real provider tests + fixes production code

---

**Discovered:** 2025-01-04
**Impact:** Critical production bug
**Detection Method:** Tier 2 real provider integration tests
**Status:** Documented, awaiting fix
