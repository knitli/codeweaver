<!--
SPDX-FileCopyrightText: 2026 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Test Parameter Fixes Guide

**File**: `tests/integration/test_config_validation_flow.py`
**Issue**: 12 calls to `analyze_config_change()` use wrong parameter names
**Fix**: Change `old_meta` to `old_fingerprint` and extract fingerprint from checkpoint

---

## The Problem

The service method signature is:

```python
async def analyze_config_change(
    self,
    old_fingerprint: Any,  # CheckpointSettingsFingerprint
    new_config: EmbeddingProviderSettingsType,
    vector_count: int,
) -> ConfigChangeAnalysis:
```

But tests are calling it with:

```python
analysis = await analyzer.analyze_config_change(
    old_meta=checkpoint.collection_metadata,  # ❌ Wrong parameter name
    new_config=new_config,
    vector_count=checkpoint.total_vectors,
)
```

---

## The Solution

### Step 1: Update Mock Fixture

Add a method to `mock_checkpoint_manager` that creates a fingerprint:

```python
@pytest.fixture
def mock_checkpoint_manager(
    test_checkpoint_data: dict,
) -> AsyncMock:
    """Create mock CheckpointManager with test data."""
    manager = AsyncMock()

    # ... existing checkpoint setup ...

    # ADD THIS METHOD:
    def create_fingerprint(checkpoint):
        """Create fingerprint from checkpoint metadata."""
        from codeweaver.engine.managers.checkpoint_manager import CheckpointSettingsFingerprint

        meta = checkpoint.collection_metadata
        return CheckpointSettingsFingerprint(
            embedding_config_type="symmetric",
            embed_model=meta.dense_model,
            embed_model_family=meta.dense_model_family,
            query_model=meta.query_model,
            sparse_model=None,
            vector_store="qdrant",
        )

    manager._extract_fingerprint = create_fingerprint

    return manager
```

### Step 2: Update All Test Calls

Change this pattern (12 locations):

```python
# ❌ BEFORE (Wrong)
checkpoint = await mock_checkpoint_manager.load_checkpoint()
analysis = await analyzer.analyze_config_change(
    old_meta=checkpoint.collection_metadata,
    new_config=new_config,
    vector_count=checkpoint.total_vectors,
)
```

To this:

```python
# ✅ AFTER (Correct)
checkpoint = await mock_checkpoint_manager.load_checkpoint()
old_fingerprint = mock_checkpoint_manager._extract_fingerprint(checkpoint)
analysis = await analyzer.analyze_config_change(
    old_fingerprint=old_fingerprint,
    new_config=new_config,
    vector_count=checkpoint.total_vectors,
)
```

---

## Affected Lines

All 12 locations that need updating:

1. **Line 257** - `test_compatible_query_model_change`
2. **Line 288** - `test_transformable_dimension_reduction`
3. **Line 320** - `test_breaking_model_change`
4. **Line 428** - `test_uses_voyage_3_empirical_data`
5. **Line 460** - `test_falls_back_to_generic_for_unmapped_dimensions`
6. **Line 508** - `test_handles_very_large_collection`
7. **Line 541** - `test_handles_zero_vectors`
8. **Line 587** - `test_breaking_change_provides_recovery_steps`
9. **Line 621** - `test_transformable_change_provides_strategy`
10. **Line 668** - `test_estimates_scale_with_vector_count` (first call)
11. **Line 675** - `test_estimates_scale_with_vector_count` (second call)
12. **Line 708** - `test_no_change_has_zero_estimates`

---

## Complete Fix Example

Here's a complete before/after for one test:

### Before (Line 257)

```python
async def test_compatible_query_model_change(
    self,
    mock_checkpoint_manager: AsyncMock,
    mock_manifest_manager: AsyncMock,
    test_settings: Mock,
) -> None:
    """Test that changing query model in asymmetric config is compatible."""
    from codeweaver.engine.managers.checkpoint_manager import ChangeImpact
    from codeweaver.engine.services.config_analyzer import ConfigChangeAnalyzer

    analyzer = ConfigChangeAnalyzer(
        settings=test_settings,
        checkpoint_manager=mock_checkpoint_manager,
        manifest_manager=mock_manifest_manager,
    )

    # Create asymmetric config
    new_config = Mock()
    new_config.embed_model = "voyage-code-3"
    new_config.embed_model_family = "voyage-4"
    new_config.query_model = "voyage-4-nano"
    new_config.dimension = 2048
    new_config.datatype = "float32"

    # Get checkpoint metadata
    checkpoint = await mock_checkpoint_manager.load_checkpoint()
    analysis = await analyzer.analyze_config_change(
        old_meta=checkpoint.collection_metadata,  # ❌ Wrong
        new_config=new_config,
        vector_count=checkpoint.total_vectors,
    )

    assert analysis.impact == ChangeImpact.COMPATIBLE
```

### After (Line 257)

```python
async def test_compatible_query_model_change(
    self,
    mock_checkpoint_manager: AsyncMock,
    mock_manifest_manager: AsyncMock,
    test_settings: Mock,
) -> None:
    """Test that changing query model in asymmetric config is compatible."""
    from codeweaver.engine.managers.checkpoint_manager import ChangeImpact
    from codeweaver.engine.services.config_analyzer import ConfigChangeAnalyzer

    analyzer = ConfigChangeAnalyzer(
        settings=test_settings,
        checkpoint_manager=mock_checkpoint_manager,
        manifest_manager=mock_manifest_manager,
    )

    # Create asymmetric config
    new_config = Mock()
    new_config.embed_model = "voyage-code-3"
    new_config.embed_model_family = "voyage-4"
    new_config.query_model = "voyage-4-nano"
    new_config.dimension = 2048
    new_config.datatype = "float32"

    # Get checkpoint and extract fingerprint
    checkpoint = await mock_checkpoint_manager.load_checkpoint()
    old_fingerprint = mock_checkpoint_manager._extract_fingerprint(checkpoint)  # ✅ Added
    analysis = await analyzer.analyze_config_change(
        old_fingerprint=old_fingerprint,  # ✅ Fixed parameter
        new_config=new_config,
        vector_count=checkpoint.total_vectors,
    )

    assert analysis.impact == ChangeImpact.COMPATIBLE
```

---

## Verification Steps

After making all fixes:

1. **Run type checker**:
   ```bash
   ty check tests/integration/test_config_validation_flow.py
   ```

   Expected: 0 parameter mismatch errors

2. **Run the test file**:
   ```bash
   pytest tests/integration/test_config_validation_flow.py -v
   ```

   Expected: All tests pass

3. **Run full test suite**:
   ```bash
   mise run test
   ```

   Expected: All tests pass

---

## Summary

- **Files to modify**: 1 (`test_config_validation_flow.py`)
- **Locations to update**: 12 (all `analyze_config_change` calls)
- **Changes required**:
  1. Add `_extract_fingerprint` method to mock fixture
  2. Extract fingerprint before each call
  3. Change parameter name from `old_meta` to `old_fingerprint`

- **Estimated time**: 15-30 minutes
- **Risk level**: Low (straightforward parameter rename)
- **Verification**: Type checker + test suite

---

**Last Updated**: 2026-02-12
**Status**: Ready to apply
