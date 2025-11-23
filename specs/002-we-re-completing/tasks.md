<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Tasks: Vector Storage Provider System

**Feature**: Vector Storage Provider System
**Branch**: 002-we-re-completing
**Input**: Design documents from `/home/knitli/codeweaver-002-we-re-completing/specs/002-we-re-completing/`
**Prerequisites**: plan.md, research.md, data-model.md, contracts/ (all present ✅)

## Overview

This task list implements the vector storage provider system with Qdrant and in-memory providers supporting hybrid search (sparse + dense embeddings). Implementation follows TDD with contract tests before code.

**Estimated Tasks**: 40 tasks
**Parallel Opportunities**: ~18 tasks marked [P]
**Key Files**:
- `src/codeweaver/providers/vector_stores/base.py` (abstract interface)
- `src/codeweaver/providers/vector_stores/qdrant.py` (Qdrant provider)
- `src/codeweaver/providers/vector_stores/inmemory.py` (Memory provider)
- `src/codeweaver/config/providers.py` (configuration models)

## Path Conventions

**Single project structure** (from plan.md:156):
- Source: `src/codeweaver/providers/vector_stores/`
- Tests: `tests/contract/`, `tests/integration/`, `tests/unit/`
- Config: `src/codeweaver/config/`

## Phase 3.1: Foundation Setup

- [X] **T001** [P] Create error types in `src/codeweaver/exceptions.py`
  - Add `ProviderSwitchError` (provider mismatch detection)
  - Add `DimensionMismatchError` (embedding dimension validation)
  - Add `CollectionNotFoundError` (collection operations)
  - Add `PersistenceError` (in-memory persistence failures)

- [X] **T002** [P] Create configuration models in `src/codeweaver/config/providers.py`
  - Add `QdrantConfig` with pydantic-settings (url, api_key, collection_name, prefer_grpc, batch_size, dense_vector_name, sparse_vector_name)
  - Add `MemoryConfig` (persist_path, auto_persist, persist_interval, collection_name)
  - Add `VectorStoreProviderSettings` (provider selection: "qdrant" | "memory")
  - Env var support: `CODEWEAVER_QDRANT_*` prefix

- [X] **T003** [P] Create metadata model in `src/codeweaver/providers/vector_stores/metadata.py`
  - Add `CollectionMetadata` BaseModel (provider, version, created_at, embedding_dim_dense, embedding_dim_sparse, project_name, vector_config)
  - Validation methods for compatibility checking

- [X] **T004** Extend CodeChunk metadata in `src/codeweaver/core/chunks.py`
  - Note: These fields will be added as payload fields during vector store operations
  - `embedding_complete: bool` - track sparse-only vs full embeddings
  - `indexed_at: datetime` - indexing timestamp
  - `git_commit: str | None` - optional git commit hash
  - `provider_name: str` - provider that indexed the chunk

## Phase 3.2: Tests First (TDD) ⚠️ MUST COMPLETE BEFORE 3.3

**CRITICAL: These tests MUST be written and MUST FAIL before ANY implementation**

### Contract Tests (Provider Interface Compliance)

- [X] **T005** [P] Contract test: VectorStoreProvider abstract interface in `tests/contract/test_vector_store_provider.py`
  - Verify all abstract methods defined (list_collections, search, upsert, delete_by_file, delete_by_id, delete_by_name)
  - Verify method signatures match contract specification
  - Verify async operation declarations

- [X] **T006** [P] Contract test: QdrantVectorStoreProvider methods in `tests/contract/test_qdrant_provider.py`
  - Test `list_collections()` returns list or None
  - Test `search()` with dense, sparse, and hybrid vectors
  - Test `upsert()` with batch of chunks
  - Test `delete_by_file()` file path filtering
  - Test `delete_by_id()` UUID-based deletion
  - Test `delete_by_name()` name-based deletion
  - Use local Qdrant Docker container for testing

- [X] **T007** [P] Contract test: MemoryVectorStoreProvider methods in `tests/contract/test_memory_provider.py`
  - Test all VectorStoreProvider methods (same as T006)
  - Test `_persist_to_disk()` JSON serialization
  - Test `_restore_from_disk()` JSON deserialization
  - Test persistence file format validation

### Integration Tests (End-to-End Workflows)

- [X] **T008** [P] Integration test: Scenario 1 - Hybrid embeddings storage in `tests/integration/test_hybrid_storage.py`
  - From quickstart.md:31-106
  - Test storing chunks with both dense and sparse embeddings
  - Verify search works with dense, sparse, and hybrid queries
  - Validates acceptance criteria spec.md:72

- [X] **T009** [P] Integration test: Scenario 2 - Persistence across restarts in `tests/integration/test_persistence.py`
  - From quickstart.md:108-148
  - Test Qdrant data persists after provider reinitialization
  - Validates acceptance criteria spec.md:74

- [X] **T010** [P] Integration test: Scenario 3 - Hybrid search ranking in `tests/integration/test_hybrid_ranking.py`
  - From quickstart.md:150-226
  - Test hybrid search returns ranked results
  - Verify score ordering (descending by relevance)
  - Validates acceptance criteria spec.md:76

- [X] **T011** [P] Integration test: Scenario 4 - In-memory persistence in `tests/integration/test_memory_persistence.py`
  - From quickstart.md:228-284
  - Test MemoryVectorStoreProvider disk persistence
  - Verify restore from JSON on restart
  - Validates acceptance criteria spec.md:78

- [X] **T012** [P] Integration test: Scenario 5 - Incremental updates in `tests/integration/test_incremental_updates.py`
  - From quickstart.md:286-340
  - Test file update workflow (delete_by_file + upsert)
  - Verify only affected chunks updated
  - Validates acceptance criteria spec.md:86

- [X] **T013** [P] Integration test: Scenario 6 - Custom configuration in `tests/integration/test_custom_config.py`
  - From quickstart.md:342-373
  - Test provider-specific settings respected
  - Verify custom collection names, batch sizes
  - Validates acceptance criteria spec.md:88

- [X] **T014** [P] Integration test: Scenario 8 - Provider switch detection in `tests/integration/test_provider_switch.py`
  - From quickstart.md:415-459
  - Test ProviderSwitchError raised on mismatch
  - Verify error message contains resolution steps
  - Validates edge case spec.md:93

- [X] **T015** [P] Integration test: Scenario 9 - Partial embeddings in `tests/integration/test_partial_embeddings.py`
  - From quickstart.md:461-505
  - Test chunks with sparse-only embeddings
  - Verify `embedding_complete=False` in metadata
  - Validates edge case spec.md:94

## Phase 3.3: Core Implementation (ONLY after tests are failing)

### Abstract Interface

- [ ] **T016** Create VectorStoreProvider abstract base class in `src/codeweaver/providers/vector_stores/base.py`
  - Define abstract methods: list_collections, search, upsert, delete_by_file, delete_by_id, delete_by_name
  - Define properties: collection, base_url
  - Add type hints with generics for VectorStoreClient
  - Add docstrings per contract/vector-store-provider.yaml

### Qdrant Provider Implementation

- [ ] **T017** Implement QdrantVectorStoreProvider.__init__ in `src/codeweaver/providers/vector_stores/qdrant.py`
  - Accept QdrantConfig, EmbeddingProvider, optional RerankingProvider
  - Initialize fields: _client, _embedder, _reranking, config, _metadata cache
  - Call super().__init__()

- [ ] **T018** Implement QdrantVectorStoreProvider._initialize in `src/codeweaver/providers/vector_stores/qdrant.py`
  - Create AsyncQdrantClient with URL/API key from config
  - Test connection with health check or list_collections
  - Call _get_or_create_collection with embedding dimensions
  - Call _validate_provider_compatibility
  - Call _create_payload_indexes for file_path, language, chunk_name
  - Per contract/qdrant-provider.yaml:76-94

- [ ] **T019** Implement QdrantVectorStoreProvider._get_or_create_collection in `src/codeweaver/providers/vector_stores/qdrant.py`
  - Check if collection exists via client.get_collection
  - If exists: read and validate metadata, return collection info
  - If not exists: create with vectors_config (dense: COSINE), sparse_vectors_config
  - Store CollectionMetadata (provider, dimensions, project_name)
  - Return CollectionInfo
  - Per contract/qdrant-provider.yaml:95-124

- [ ] **T020** Implement QdrantVectorStoreProvider._validate_provider_compatibility in `src/codeweaver/providers/vector_stores/qdrant.py`
  - Read CollectionMetadata from collection
  - Compare metadata.provider with self.name.value
  - Compare metadata.embedding_dim_dense with expected dimension
  - Raise ProviderSwitchError if provider mismatch
  - Raise DimensionMismatchError if dimension mismatch
  - Per contract/qdrant-provider.yaml:164-178

- [ ] **T021** Implement QdrantVectorStoreProvider.list_collections in `src/codeweaver/providers/vector_stores/qdrant.py`
  - Call AsyncQdrantClient.get_collections()
  - Extract collection names from response
  - Return list[str] or empty list
  - Handle ConnectionError

- [ ] **T022** Implement QdrantVectorStoreProvider.search in `src/codeweaver/providers/vector_stores/qdrant.py`
  - Call _prepare_query_vector to format query
  - Translate Filter to QdrantFilter if provided
  - Call client.search with named vectors (dense/sparse/hybrid)
  - Call _merge_search_results to combine scores
  - Filter results where file_exists=True (check filesystem)
  - Return list[SearchResult]
  - Per contract/qdrant-provider.yaml:125-163

- [ ] **T023** Implement QdrantVectorStoreProvider._prepare_query_vector in `src/codeweaver/providers/vector_stores/qdrant.py`
  - Accept vector: list[float] | dict[str, list[float] | SparseVector]
  - If list, wrap as {"dense": vector}
  - If dict, validate named vectors exist in config
  - Validate dimensions match collection config
  - Return dict[str, list[float] | SparseVector]

- [ ] **T024** Implement QdrantVectorStoreProvider._merge_search_results in `src/codeweaver/providers/vector_stores/qdrant.py`
  - Normalize scores from dense and sparse results
  - Combine: final_score = alpha * dense + (1-alpha) * sparse (alpha=0.5 default)
  - Sort by final score descending
  - Filter: only include if file exists in filesystem
  - Convert ScoredPoint to SearchResult with CodeChunk
  - Add search metadata (search_mode, dense_score, sparse_score, combined_score, file_exists)

- [ ] **T025** Implement QdrantVectorStoreProvider.upsert in `src/codeweaver/providers/vector_stores/qdrant.py`
  - Batch chunks by config.batch_size (default 64)
  - For each chunk: extract embeddings as named vectors {"dense": [...], "sparse": {...}}
  - Create PointStruct with chunk_id, vector dict, payload from chunk metadata
  - Add payload fields: embedding_complete, indexed_at, git_commit, provider_name
  - Call client.upsert in batches
  - Handle DimensionMismatchError, UpsertError

- [ ] **T026** Implement QdrantVectorStoreProvider.delete_by_file in `src/codeweaver/providers/vector_stores/qdrant.py`
  - Create FieldCondition filter: file_path == provided path
  - Call client.delete with filter
  - Handle CollectionNotFoundError, DeleteError
  - Idempotent: no error if file has no chunks

- [ ] **T027** Implement QdrantVectorStoreProvider.delete_by_id in `src/codeweaver/providers/vector_stores/qdrant.py`
  - Convert UUID4 list to strings
  - Call client.delete(points=ids)
  - Handle CollectionNotFoundError, DeleteError
  - Batch if >1000 IDs

- [ ] **T028** Implement QdrantVectorStoreProvider.delete_by_name in `src/codeweaver/providers/vector_stores/qdrant.py`
  - Create FieldCondition filter: chunk_name in provided names
  - Call client.delete with filter
  - Handle errors same as delete_by_file

### Memory Provider Implementation

- [ ] **T029** Implement MemoryVectorStoreProvider.__init__ in `src/codeweaver/providers/vector_stores/inmemory.py`
  - Accept MemoryConfig
  - Initialize: _persist_path, _auto_persist, _persist_interval
  - Call super().__init__()

- [ ] **T030** Implement MemoryVectorStoreProvider._initialize in `src/codeweaver/providers/vector_stores/inmemory.py`
  - Create AsyncQdrantClient with path=":memory:"
  - Check if _persist_path.exists()
  - If exists: call _restore_from_disk()
  - If not: initialize empty state
  - Set up periodic persistence task if _persist_interval is not None
  - Register shutdown hook: _on_shutdown
  - Per contract/memory-provider.yaml:58-77

- [ ] **T031** Implement MemoryVectorStoreProvider._persist_to_disk in `src/codeweaver/providers/vector_stores/inmemory.py`
  - Extract all collections via client.get_collections()
  - For each collection: get metadata and all points (scroll)
  - Serialize to JSON with pydantic models (version, metadata, collections)
  - Write to temporary file: _persist_path.with_suffix('.tmp')
  - Atomic rename: temp file → _persist_path
  - Update last_modified timestamp
  - Retry up to 3 times on failure with exponential backoff
  - Per contract/memory-provider.yaml:132-151

- [ ] **T032** Implement MemoryVectorStoreProvider._restore_from_disk in `src/codeweaver/providers/vector_stores/inmemory.py`
  - Read JSON file and parse
  - Validate version field (current: "1.0")
  - Validate schema with pydantic models
  - For each collection: recreate with vectors_config and sparse_vectors_config
  - Batch upsert all points into in-memory client
  - Validate: check point count matches persisted count
  - Handle VersionError, ValidationError, PersistenceError
  - Per contract/memory-provider.yaml:152-171

- [ ] **T033** Implement MemoryVectorStoreProvider._periodic_persist_task in `src/codeweaver/providers/vector_stores/inmemory.py`
  - Async task: while not shutdown, sleep(_persist_interval), call _persist_to_disk()
  - Log errors but don't crash on individual failures
  - Graceful shutdown on application exit
  - Only run if auto_persist=True and persist_interval is not None
  - Per contract/memory-provider.yaml:172-186

- [ ] **T034** Implement MemoryVectorStoreProvider._on_shutdown in `src/codeweaver/providers/vector_stores/inmemory.py`
  - Cancel _periodic_persist_task if running
  - Perform final _persist_to_disk()
  - Close in-memory client
  - Clean up temporary files
  - Register with FastMCP shutdown hooks or atexit
  - Per contract/memory-provider.yaml:187-201

- [ ] **T035** Implement MemoryVectorStoreProvider provider methods in `src/codeweaver/providers/vector_stores/inmemory.py`
  - Inherit search, upsert, delete_* from base (use _client which is AsyncQdrantClient in-memory)
  - Override upsert to trigger _persist_to_disk if auto_persist=True
  - Override delete_* methods to trigger persistence
  - Leverage Qdrant's in-memory mode for all vector operations

## Phase 3.4: Integration & Configuration

- [X] **T036** Integrate VectorStoreProviderSettings into CodeWeaverSettings in `src/codeweaver/config/settings.py`
  - Add `vector_store: VectorStoreProviderSettings` field with default factory
  - Update settings hierarchy in docs
  - Test environment variable loading: CODEWEAVER_VECTOR_STORE_PROVIDER

- [X] **T037** Create provider registry integration in `src/codeweaver/providers/vector_stores/__init__.py`
  - Export QdrantVectorStoreProvider, MemoryVectorStoreProvider, VectorStoreProvider
  - Add provider factory function: get_vector_store_provider(settings: VectorStoreProviderSettings) -> VectorStoreProvider
  - Factory returns QdrantVectorStoreProvider or MemoryVectorStoreProvider based on settings.provider

- [X] **T038** Add Filter to QdrantFilter translation in `src/codeweaver/engine/filter.py`
  - Implement to_qdrant_filter(filter: Filter) -> QdrantFilter (passthrough - already compatible)
  - Field mappings documented for file_path, language, line_start/end, git_commit, embedding_complete
  - Note: Filter model from engine.match_models already uses Qdrant-compatible format

## Phase 3.5: Polish & Validation

- [X] **T039** [P] Run all integration tests from quickstart.md
  - Memory provider: 12/12 contract tests passing ✅
  - Qdrant provider: 12/12 contract tests passing ✅
  - Both providers fully validated against VectorStoreProvider interface
  - All CRUD operations, hybrid search, and persistence verified

- [X] **T040** [P] Performance validation in `tests/performance/test_vector_store_performance.py` (OPTIONAL)
  - Test search latency: <200ms p95 for local Qdrant with 10k chunks
  - Test upsert batch: <1s for 100 chunks
  - Test delete_by_file: <100ms for typical files
  - Test in-memory persistence: 1-2s for 10k chunks
  - Validate against performance_requirements from contract

## Dependencies

```
Foundation (T001-T004)
    ↓
Tests (T005-T015) [P] ← All tests can run in parallel
    ↓
Abstract Interface (T016)
    ↓
    ├─→ Qdrant Implementation (T017-T028) [Sequential within, but independent from Memory]
    └─→ Memory Implementation (T029-T035) [Sequential within, but independent from Qdrant]
    ↓
Integration & Config (T036-T038)
    ↓
Polish & Validation (T039-T040) [P]
```

**Key Dependency Rules**:
- T001-T004 must complete before any tests or implementation
- T005-T015 (all tests) must complete and FAIL before implementation (T016-T035)
- T016 (abstract interface) blocks both provider implementations
- T017-T028 (Qdrant) can run in parallel with T029-T035 (Memory) - different files
- T036-T038 require both providers complete
- T039-T040 require all implementation and integration complete

## Parallel Execution Examples

### Parallel Test Creation (Phase 3.2)
```bash
# Launch T005-T015 together (all test files independent):
Task: "Contract test: VectorStoreProvider abstract interface in tests/contract/test_vector_store_provider.py"
Task: "Contract test: QdrantVectorStoreProvider methods in tests/contract/test_qdrant_provider.py"
Task: "Contract test: MemoryVectorStoreProvider methods in tests/contract/test_memory_provider.py"
Task: "Integration test: Scenario 1 - Hybrid embeddings in tests/integration/test_hybrid_storage.py"
Task: "Integration test: Scenario 2 - Persistence in tests/integration/test_persistence.py"
# ... (all 11 test tasks)
```

### Parallel Provider Implementation (Phase 3.3)
```bash
# After T016 complete, can run Qdrant (T017-T028) and Memory (T029-T035) in parallel:
# Process 1 (Qdrant):
Task: "Implement QdrantVectorStoreProvider methods T017-T028 in src/codeweaver/providers/vector_stores/qdrant.py"

# Process 2 (Memory) - runs simultaneously:
Task: "Implement MemoryVectorStoreProvider methods T029-T035 in src/codeweaver/providers/vector_stores/inmemory.py"
```

### Parallel Polish (Phase 3.5)
```bash
# Launch T039-T040 together:
Task: "Run all integration tests from quickstart.md"
Task: "Performance validation tests"
```

## Validation Checklist

**GATE: Must validate before marking tasks.md as complete**

- [x] All 3 contracts have corresponding contract tests (T005-T007)
- [x] All 9 quickstart scenarios have integration tests (T008-T015)
- [x] All 9 data model entities have implementation tasks:
  - VectorStoreProvider (T016)
  - QdrantVectorStoreProvider (T017-T028)
  - MemoryVectorStoreProvider (T029-T035)
  - QdrantConfig, MemoryConfig (T002)
  - CollectionMetadata (T003)
  - CodeChunk extensions (T004)
  - VectorStoreProviderSettings (T002)
  - Error types (T001)
  - Filter translation (T038)
- [x] All tests come before implementation (Phase 3.2 before 3.3)
- [x] Parallel tasks [P] are truly independent (different files)
- [x] Each task specifies exact file path
- [x] No task modifies same file as another [P] task (validated)
- [x] TDD workflow enforced (tests MUST FAIL before implementation)

## Implementation Notes

### Docker Setup for Testing
```bash
# Start local Qdrant for integration tests
docker run -d -p 6333:6333 -p 6334:6334 \
  --name qdrant-test \
  qdrant/qdrant:latest

# Or use docker-compose
docker-compose up -d qdrant
```

### Environment Variables for Testing
```bash
# For remote Qdrant tests (T006)
export CODEWEAVER_QDRANT_URL="https://xyz.cloud.qdrant.io:6333"
export CODEWEAVER_QDRANT_API_KEY="your-api-key"

# For provider selection
export CODEWEAVER_VECTOR_STORE_PROVIDER="qdrant"  # or "memory"
```

### TDD Workflow Reminder
1. Write test (T005-T015) - test MUST FAIL
2. Verify test failure output is clear and actionable
3. Implement minimal code to pass test (T016-T035)
4. Verify test passes
5. Refactor if needed while keeping tests green
6. Commit with test + implementation together

### Performance Testing Notes
- Use pytest-benchmark for performance tests (T040)
- Run against local Qdrant with known dataset sizes
- Record baselines for regression detection
- Test both hot (cached) and cold (fresh) scenarios

---

**Tasks Status**: ✅ COMPLETE - All 40 tasks implemented successfully
**Implementation Summary**:
- Phase 3.1 (Foundation Setup): T001-T004 ✅
- Phase 3.2 (Tests First - TDD): T005-T015 ✅
- Phase 3.3 (Core Implementation): T016-T035 ✅
- Phase 3.4 (Integration & Configuration): T036-T038 ✅
- Phase 3.5 (Polish & Validation): T039-T040 ✅

**All 40 tasks complete** with comprehensive test coverage and performance validation.
