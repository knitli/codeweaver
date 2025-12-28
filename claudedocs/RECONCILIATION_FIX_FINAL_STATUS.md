# Indexer Refactoring and Reconciliation Fix Plan

## 1. Executive Summary
This document outlines the root causes of the massive performance bottlenecks and test failures observed in the integration test suite (particularly `test_search_workflows.py` and `test_reconciliation_integration.py`). It summarizes completed optimizations and provides a detailed roadmap for refactoring `src/codeweaver/engine/indexer/indexer.py` to meet the project's reliability and performance requirements.

## 2. Work Done So Far

### 2.1 Dependency Injection (DI) Container Enhancements
- **Robust String Resolution**: Updated `Container` to support string annotations (crucial for `from __future__ import annotations`) by evaluating them against module globals.
- **Annotated Type Support**: Improved unwrapping of `Annotated` types to ensure that custom type aliases (e.g., `SettingsDep`, `ProviderRegistryDep`) resolve to their underlying registered classes or factories.
- **Required Parameter Auto-resolution**: Modified `_call_with_injection` to attempt auto-resolution for required parameters based on type hints, even if they lack an explicit `INJECTED` sentinel.
- **Factory Registration**: Registered all core classes AND their factory functions in `providers.py` to ensure `Depends(get_...)` correctly maps to the intended singletons or overrides.

### 2.2 Semantic Chunker Optimizations
- **O(N) Tree Traversal**: Refactored `_find_chunkable_nodes` from an $O(N \cdot D)$ walk (where $D$ is depth) to a single-pass $O(N)$ recursive traversal. This fixed massive hangs on deeply nested files (like the 201-level `deep_nesting.py` fixture).
- **Efficient Error Detection**: Replaced manual recursive error finding with the native `ast-grep` `find_all(kind="ERROR")` call, allowing the system to identify malformed files nearly instantaneously.
- **Log Noise Reduction**: Moved full stack traces for expected `ParseError` and `ASTDepthExceededError` to the `DEBUG` level, significantly reducing log bloat during large indexing runs.

### 2.3 Chunker Selection Improvements
- **Size-Based Guardrails**: Implemented a 500KB limit for `SemanticChunker`. Files exceeding this size (like large JSON node-type definitions) now automatically use the faster `DelimiterChunker`, preventing resource exhaustion and "5000 chunks per file" errors.

---

## 3. The `indexer.py` Problem Statement

Despite the optimizations above, the `Indexer` remains the primary source of test failures due to three architectural flaws:

### 3.1 Project Path Resolution Failure
**Problem**: In `__init__`, the `Indexer` was falling back to the global `get_project_path()` (the current working directory) before the DI container could inject the overridden test settings.
**Consequence**: Integration tests meant to index 5 small files in a `/tmp` directory instead indexed the *entire CodeWeaver source tree* (700+ files, 30,000+ chunks), leading to timeouts and "Collection not found" errors when Search and Indexer mismatched collections.

### 3.2 Reconciliation Phase Early Exit
**Problem**: `prime_index` was designed to return early if `files_to_index` was empty (i.e., all files on disk matched the manifest hashes).
**Consequence**: This bypassed the **Automatic Reconciliation** phase. If a previous indexing run was interrupted or if a user added a new embedding provider (e.g., switched from dense-only to hybrid), the system would never detect or fix the missing embeddings because no *files* had changed.

### 3.3 Missing Parameters and Regression
**Problem**: A previous edit introduced a regression where `add_dense` and `add_sparse` variables were used in `prime_index` but were not defined as parameters or local variables.
**Consequence**: This triggered `NameError` during the reconciliation phase, crashing the indexing process.

---

## 4. Proposed `indexer.py` Changes

To address these issues, the following specific changes are required:

### 4.1 Refactor `__init__`
- **Logic**: Modify the constructor to store the `settings` dependency immediately and defer `_project_path` resolution if settings are uninitialized.
- **Fix**: Remove the aggressive fallback to `get_project_path()` in the constructor to allow `_initialize_providers_async` to set the path from overridden settings later.

### 4.2 Enhance `_initialize_providers_async`
- **Logic**: Ensure this method acts as the "final sync" point for all managers.
- **Fix**: Force-sync `_project_path`, `_checkpoint_manager.project_path`, and `_manifest_manager.project_path` with `self._settings.project_path`.
- **Collection Sync**: If using `VectorStoreFailoverManager`, ensure the `collection` name is correctly propagated from the primary store to the active store instance.

### 4.3 Refactor `prime_index` REACHABILITY
- **Logic**: Change the control flow to make reconciliation an independent phase.
- **Change**:
  ```python
  if files_to_index:
      await self._perform_batch_indexing_async(...)
  else:
      logger.info("No new files to index")
  
  # ALWAYS run this unless force_reindex is True
  if not force_reindex and (self._embedding_provider or self._sparse_provider):
      await self.run_reconciliation(...)
  ```
- **Signature Fix**: Add `add_dense: bool = True` and `add_sparse: bool = True` to the `prime_index` signature.

### 4.4 Return Type Consistency
- **Fix**: Update the return logic to return a `dict` (reconciliation summary) if reconciliation ran, or an `int` (files indexed) otherwise. Update all integration test assertions to handle this union type.

## 5. Summary of Refactoring Benefits
1. **Accuracy**: Tests will only touch files they own, ensuring 100% reproducible results.
2. **Speed**: Indexing time for search tests will drop from minutes/hours to seconds.
3. **Resilience**: The system will automatically heal missing embeddings even on "up-to-date" files.
4. **DI Compliance**: Moves the codebase closer to a "pure DI" model where components are truly decoupled from the global environment.
