# Specification: CodeWeaver Indexing Engine v2 (CW-Index-V2)

## 1. Vision Statement
CW-Index-V2 is a declarative, stream-oriented data enrichment engine. It replaces the procedural, path-heavy logic of the legacy indexer with a decoupled architecture of isolated micro-services. It is designed to index anything (files, web, APIs), enrich data with multiple embedding layers, and ensure 100% availability through a self-healing storage mesh.

---

## 2. Core Abstractions

### 2.1 UnifiedDocument
Instead of `Path` objects, the pipeline processes `UnifiedDocument` instances.
- **SourceID**: Unique URI (e.g., `file://src/main.py`, `web://google.com/search?q=...`).
- **Content**: Raw text payload.
- **Fingerprint**: BLAKE3 hash of content + critical metadata.
- **Metadata Context**: Schema-less dictionary carrying source-specific data (line numbers, URLs, DOM selectors).

### 2.2 EnrichmentLayer
A specification for a single vector transformation.
- **LayerID**: Literal string (e.g., `fast_scan`, `deep_narrow`).
- **ModelSpec**: Reference to a provider and model version.
- **VectorType**: `DENSE`, `SPARSE`, or `LATE_INTERACTION`.
- **Policy**: Rules for when this layer is applied (e.g., `min_tokens`, `max_tokens`).

### 2.3 StorageTopology
Defines the mapping between `EnrichmentLayers` and physical hardware.
- **PrimaryStore**: The high-priority target.
- **IsolationStore**: The backup/failover target.
- **ReplicationMode**: `SYNC`, `ASYNC`, or `MIRRORED`.

---

## 3. Component Architecture

### 3.1 The Ingestion Grid (`SourceProviders`)
Sources are registered as pluggable providers that emit a stream of `UnifiedDocuments`.
- **FileSystemProvider**: Monitors disk via `rignore` and `watchfiles`.
- **WebDiscoveryProvider**: Ingests search results, documentation scrapes, or API responses.
- **Incremental Logic**: Every provider implements `get_delta()`, returning only what has changed since the last `Checkpoint`.

### 3.2 The Transformation Engine (`ChunkerRegistry`)
A policy-based engine that converts documents into chunks.
- **Selector**: Uses a "Best Fit" algorithm. If AST-Grep supports the language, use `SemanticChunker`; otherwise, fallback to `DelimiterChunker`.
- **Context Preservation**: Every chunk retains a reference to its parent `UnifiedDocument` and its relative position (offset/lines).

### 3.3 The Enrichment Factory (`VectorFactory`)
The factory executes the `EmbeddingRecipe`.
- **Batch Aggregator**: Groups chunks by `LayerID` to maximize provider throughput.
- **Concurrency Control**: Individually throttles different providers (e.g., high-rate for local FastEmbed, low-rate for rate-limited Cloud APIs).
- **Multi-Layering**: Can generate a 384-dim "fast" vector and a 3072-dim "precise" vector for the same chunk simultaneously.

### 3.4 The Storage Router (`VectorMesh`)
The router masks the complexity of multiple stores.
- **Circuit Breaker**: If a store fails 3 consecutive heartbeats, it is marked `UNAVAILABLE`.
- **Layer Routing**: Directs `fast_scan` layers to in-memory caches and `deep_narrow` layers to persistent disk.
- **Journaling**: Every write is logged in the `Global Manifest` with layer-level granularity (e.g., `Chunk_A: [fast_scan: OK, deep_narrow: PENDING]`).

---

## 4. Resilience & Self-Healing

### 4.1 Automated Failover
When the `PrimaryStore` fails:
1.  The Router shifts to the `IsolationStore`.
2.  The pipeline continues processing.
3.  New entries are tagged in the Manifest as `DEGRADED_STATE`.

### 4.2 The Promotion Pass (Handover)
When the `PrimaryStore` returns:
1.  **Reconciliation Pass**: The system compares the Manifest against the Primary Store.
2.  **Backfill**: Missing data is "promoted" from the `IsolationStore` to the Primary.
3.  **Upgrade**: If the `BackupModel` was used (lower quality), the system re-runs the `PrimaryModel` using raw text from the `BlakeStore`.
4.  **Atomic Switch**: Search queries are routed back to Primary only after the delta reaches < 1%.

### 4.3 Background Reconciliation
A low-priority service that constantly sweeps the manifest.
- **Audit**: Detects "Vector Drift" (where the model version in the store doesn't match the current Recipe).
- **Repair**: Injects `RepairTasks` to re-embed and update specific layers without touching the rest of the chunk.

---

## 5. Search Strategy Implementation

The system supports **Multi-Stage Narrowing**:
1.  **Level 1 (The Sweep)**: Query the `fast_scan` layer in the Memory Store (Top 1000).
2.  **Level 2 (The Filter)**: Apply `sparse_keyword` filters to prune the Top 1000 to Top 100.
3.  **Level 3 (The Narrow)**: Query the `deep_narrow` layer in the Persistent Store for the Top 100.
4.  **Level 4 (The Rerank)**: Cross-encoder reranking of the final Top 10.

---

## 6. Success Metrics (V2 vs V1)
- **Modularity**: No single file exceeds 500 lines.
- **Performance**: 40% reduction in indexing time via parallel enrichment batches.
- **Reliability**: 99.9% search availability through automated Isolation Store failover.
- **Extensibility**: Adding a new source type requires < 100 lines of code.
