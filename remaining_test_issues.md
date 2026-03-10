<!--
SPDX-FileCopyrightText: 2026 Knitli Inc.

SPDX-License-Identifier: MIT OR Apache-2.0
-->
# Remaining Test Issues & Proposed Solutions

This document outlines the current state of the test suite after initial fixes, including specific issues that are blocking tests from passing and proposed solutions for each.

## 1. The `AsyncMock` Attribute Issue in `test_config_validation_flow.py`

**Issue:**
Tests in `test_config_validation_flow.py` are failing with:
`AttributeError: 'coroutine' object has no attribute 'is_compatible_with'` or `RuntimeWarning: coroutine 'AsyncMockMixin._execute_mock_call' was never awaited`.

**Root Cause:**
In `test_config_validation_flow.py`, `mock_checkpoint_manager` is an `AsyncMock()`. Python's `AsyncMock` recursively returns new `AsyncMock` instances for any unconfigured method calls.
When `ConfigChangeAnalyzer` calls `self.checkpoint_manager._extract_fingerprint()`, it gets an `AsyncMock` back (which acts as a coroutine), rather than a `CheckpointSettingsFingerprint` or a standard `Mock`. Later, when it attempts to call `.is_compatible_with()` on this returned object, it throws an `AttributeError` because the returned object is a coroutine, not a fingerprint instance.

**Proposed Solutions:**
1.  **Change Base Mock Type:** Change `mock_checkpoint_manager` from `AsyncMock()` to a standard `Mock()`, and explicitly configure its async methods:
    ```python
    manager = Mock()
    manager.load = AsyncMock(return_value=checkpoint)
    manager.validate_checkpoint_compatibility = AsyncMock(return_value=(True, "NONE"))
    ```
    This prevents synchronous methods like `_extract_fingerprint` from returning coroutines.

2.  **Explicitly Mock Synchronous Methods:** Explicitly configure `_extract_fingerprint` and `_create_fingerprint` on the `AsyncMock` to return a regular `Mock()` object with a mocked `is_compatible_with` method that can be configured per-test.

## 2. DI Container and `actual_vector_store` Warnings

**Issue:**
There are several `RuntimeWarning: coroutine 'actual_vector_store' was never awaited` warnings in pytest output.

**Root Cause:**
The `actual_vector_store` fixture is defined as an `async def` but is likely being injected into synchronous tests or other synchronous fixtures without being awaited properly, or the test runner isn't fully recognizing the fixture dependencies correctly due to a mix of pytest-asyncio versions or missing `@pytest.mark.asyncio` markers on the tests that consume it indirectly.

**Proposed Solutions:**
1. Ensure that any test or fixture consuming `actual_vector_store` is an `async` function and properly marked with `@pytest.mark.asyncio`.
2. Evaluate if `actual_vector_store` genuinely needs to be an async fixture. If it only creates a synchronous object (like an in-memory dictionary), it can be converted to a normal `def` fixture.

## 3. General Pytest Version Compatibility

**Issue:**
During the run, there were warnings related to `PytestRemovedIn9Warning`, and the environment required explicitly pinning `pytest-asyncio` to avoid crashes.

**Proposed Solutions:**
1.  **Standardize Pytest Async Markers:** Ensure all asynchronous tests are consistently decorated with `@pytest.mark.asyncio` (not `@pytest.mark.async_test` which is a custom or typoed mark).
2.  **Update Fixtures:** Verify all `async def` fixtures are decorated with `@pytest_asyncio.fixture` rather than `@pytest.fixture`, as standard pytest no longer supports `async def` fixtures natively without the explicit `pytest_asyncio` decorator.

## 4. Unimplemented and Skipped Tests

**Issue:**
A large number of tests (around 95) are skipped due to missing infrastructure (e.g., Docker Qdrant instances) or pending DI integration implementations.

**Proposed Solutions:**
1.  **CI Infrastructure:** For tests requiring Qdrant or real external APIs, either use mock containers (like testcontainers) during CI or ensure the environment variables/services are spun up correctly before running the suite.
2.  **DI Updates:** Complete the integration of the new Dependency Injection system into the legacy tests that are marked with "DI integration not yet implemented". This usually involves replacing `reset_settings` and `get_settings()` patches with `container.override()`.
