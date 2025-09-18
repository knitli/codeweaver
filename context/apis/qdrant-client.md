<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Qdrant-Client SDK - Advanced Vector Store Integration Research

*Expert API Analyst Research - Vector Store Foundation for CodeWeaver Clean Rebuild*

## Summary

**Feature Name**: Qdrant-Client Advanced Vector Store Integration  
**Feature Description**: Comprehensive vector database integration with advanced multi-modal/hybrid search, named vectors, sparse indexing, and payload-based filtering capabilities  
**Feature Goal**: Enable CodeWeaver's intelligent codebase context layer with sophisticated vector search, multiple embedding support, and semantic filtering through robust metadata indexing

**Primary External Surface(s)**: `QdrantClient`/`AsyncQdrantClient` classes, collection management, multi-vector point operations, hybrid search with filtering, payload indexing system, performance optimization features

**Integration Confidence**: High - Well-documented API with extensive advanced features, proven enterprise-ready architecture, and comprehensive support for all CodeWeaver requirements including named vectors, sparse indexing, cloud inference capabilities, and robust vector invalidation patterns

## Core Types

| Name | Kind | Definition | Role |
|------|------|------------|------|
| `QdrantClient` | Class | Primary synchronous client interface | Main client for all vector operations and collection management |
| `AsyncQdrantClient` | Class | Asynchronous client interface | Non-blocking operations for high-performance scenarios |
| `PointStruct` | Dataclass | Point with ID, vectors, payload | Core data structure for storing code contexts with metadata |
| `VectorParams` | Model | Vector configuration (size, distance) | Defines single vector space parameters |
| `VectorParamsMap` | Model | Named vector configurations | Enables multiple embeddings per collection |
| `SparseVectorParamsMap` | Model | Sparse vector configurations | Enables hybrid dense+sparse search capabilities |
| `Filter` | Model | Query filter conditions | Complex payload-based filtering for semantic search |
| `FieldCondition` | Model | Individual field filter | Specific metadata filtering conditions |
| `Distance` | Enum | Similarity metrics | COSINE, DOT, EUCLIDEAN distance calculations |

## Signatures

### Core Client Initialization

**Name**: `QdrantClient.__init__`  
**Import Path**: `from qdrant_client import QdrantClient`  
**Concrete Path**: `qdrant_client/qdrant_client.py:QdrantClient.__init__`  
**Signature**: `def __init__(self, url: str = None, host: str = None, port: int = 6333, grpc_port: int = 6334, prefer_grpc: bool = False, api_key: str = None, path: str = None, **kwargs)`

**Params**:
- `url: str` (optional) - Full URL for Qdrant Cloud or remote instance
- `host: str` (optional) - Hostname for self-hosted instance  
- `port: int = 6333` (optional) - HTTP communication port
- `grpc_port: int = 6334` (optional) - gRPC communication port (higher performance)
- `prefer_grpc: bool = False` (optional) - Prefer gRPC over HTTP for operations
- `api_key: str` (optional) - Authentication for Qdrant Cloud/secured instances
- `path: str` (optional) - Local storage path (":memory:" for in-memory)

**Returns**: `QdrantClient` instance  
**Errors**: `ConnectionError` if unable to connect, `ValueError` for invalid configuration  
**Notes**: Supports local (:memory:, persistent), remote (HTTP/gRPC), and cloud deployment modes. gRPC preferred for bulk operations and collection uploads.

### Collection Management with Advanced Vector Configuration

**Name**: `QdrantClient.create_collection`  
**Import Path**: `from qdrant_client import QdrantClient`  
**Signature**: `def create_collection(self, collection_name: str, vectors_config: Union[VectorParams, Dict[str, VectorParams]], sparse_vectors_config: Dict[str, SparseVectorParams] = None, **kwargs)`

**Params**:
- `collection_name: str` (required) - Unique collection identifier
- `vectors_config: Union[VectorParams, Dict[str, VectorParams]]` (required) - Single or named vector configurations
- `sparse_vectors_config: Dict[str, SparseVectorParams]` (optional) - Sparse vector configurations for hybrid search
- `hnsw_config: HnswConfig` (optional) - HNSW index configuration for performance tuning
- `quantization_config: QuantizationConfig` (optional) - Vector quantization for memory optimization

**Returns**: Collection creation response with status  
**Errors**: `ValueError` for invalid configuration, `DuplicateError` if collection exists  
**Notes**: Supports both single vector (simple) and named vectors (advanced) configurations. Named vectors enable multiple embedding types per point.

**Type Information**:
```python
# Single vector configuration
vectors_config = VectorParams(size=384, distance=Distance.COSINE)

# Named vectors configuration (multiple embeddings per point)
vectors_config = {
    "dense": VectorParams(size=384, distance=Distance.COSINE),
    "sparse": SparseVectorParams(),
    "code": VectorParams(size=768, distance=Distance.DOT),
    "semantic": VectorParams(size=1536, distance=Distance.COSINE)
}
```

### Advanced Point Operations with Multi-Vector Support

**Name**: `QdrantClient.upsert`  
**Import Path**: `from qdrant_client import QdrantClient`  
**Signature**: `def upsert(self, collection_name: str, points: List[PointStruct], wait: bool = True, batch_size: int = 64, **kwargs)`

**Params**:
- `collection_name: str` (required) - Target collection name
- `points: List[PointStruct]` (required) - Points with vectors and metadata
- `wait: bool = True` (optional) - Wait for operation completion
- `batch_size: int = 64` (optional) - Batch size for bulk operations

**Returns**: Operation result with status and timing  
**Errors**: `ValueError` for malformed points, `CollectionError` if collection missing  
**Notes**: Supports both single vectors and named vectors per point. Batch processing optimized for performance.

**Type Information**:
```python
# Single vector point
PointStruct(
    id=1, 
    vector=[0.1, 0.2, 0.3], 
    payload={"file": "auth.py", "line": 42, "type": "function"}
)

# Named vectors point (multiple embeddings per point)
PointStruct(
    id=1,
    vector={
        "dense": [0.1, 0.2, 0.3],      # Dense semantic embedding
        "sparse": {"indices": [1, 5, 10], "values": [0.8, 0.6, 0.4]},  # Sparse keyword features
        "code": [0.05, 0.15, 0.25]     # Code-specific embedding
    },
    payload={
        "file_path": "src/auth.py",
        "line_number": 42,
        "function_name": "authenticate",
        "complexity": "medium",
        "language": "python"
    }
)
```

### Advanced Hybrid Search Operations

**Name**: `QdrantClient.search`  
**Import Path**: `from qdrant_client import QdrantClient`  
**Signature**: `def search(self, collection_name: str, query_vector: Union[List[float], Dict[str, Union[List[float], SparseVector]]], query_filter: Filter = None, limit: int = 10, offset: int = 0, with_payload: bool = True, with_vectors: bool = False, **kwargs)`

**Params**:
- `collection_name: str` (required) - Collection to search
- `query_vector: Union[List[float], Dict[str, Union[List[float], SparseVector]]]` (required) - Query vector(s)
- `query_filter: Filter` (optional) - Payload-based filtering conditions
- `limit: int = 10` (optional) - Maximum results to return
- `offset: int = 0` (optional) - Results offset for pagination
- `with_payload: bool = True` (optional) - Include payload in results
- `with_vectors: bool = False` (optional) - Include vectors in results

**Returns**: `SearchResult` with scored points and metadata  
**Errors**: `CollectionError`, `InvalidQueryError` for malformed queries  
**Notes**: Supports single vector search, named vector search, and hybrid search combining multiple vector types.

**Type Information**:
```python
# Named vector search (hybrid search)
query_vector = {
    "dense": [0.1, 0.2, 0.3],  # Semantic similarity
    "sparse": {"indices": [1, 5], "values": [0.9, 0.7]}  # Keyword matching
}

# Complex filter example
query_filter = Filter(
    must=[
        FieldCondition(key="language", match=MatchValue(value="python")),
        FieldCondition(key="line_number", range=Range(gte=1, lte=100))
    ],
    should=[
        FieldCondition(key="complexity", match=MatchValue(value="medium")),
        FieldCondition(key="type", match=MatchValue(value="function"))
    ]
)
```

### Query Building and Advanced Search

**Name**: `QdrantClient.query_points`  
**Import Path**: `from qdrant_client import QdrantClient`  
**Signature**: `def query_points(self, collection_name: str, query: Union[List[float], Document, Dict], query_filter: Filter = None, limit: int = 10, offset: int = 0, **kwargs)`

**Params**:
- `collection_name: str` (required) - Collection to query
- `query: Union[List[float], Document, Dict]` (required) - Query vector, document, or named vector query
- `query_filter: Filter` (optional) - Complex filtering conditions
- `limit: int = 10` (optional) - Maximum results
- `offset: int = 0` (optional) - Pagination offset

**Returns**: `QueryResult` with points and metadata  
**Errors**: `QueryError`, `CollectionError`  
**Notes**: Unified interface for vector search, document search, and hybrid queries. Supports automatic embedding for Document queries.

### Payload Indexing for Performance Optimization

**Name**: `QdrantClient.create_payload_index`  
**Import Path**: `from qdrant_client import QdrantClient`  
**Signature**: `def create_payload_index(self, collection_name: str, field_name: str, field_type: str, **kwargs)`

**Params**:
- `collection_name: str` (required) - Target collection
- `field_name: str` (required) - Payload field to index
- `field_type: str` (required) - Index type: 'keyword', 'integer', 'float', 'geo', 'text'

**Returns**: Index creation status  
**Errors**: `IndexError` for invalid field types  
**Notes**: Critical for high-performance filtering on large collections. Supports multiple index types optimized for different data types.

## Type Graph

```
QdrantClient -> contains -> HTTPClient/GRPCClient
QdrantClient -> creates -> Collection
QdrantClient -> manages -> PointStruct[]

Collection -> configured_with -> VectorParams | VectorParamsMap
Collection -> optionally_configured_with -> SparseVectorParamsMap
Collection -> contains -> PointStruct[]

PointStruct -> has -> id: Union[int, str]  
PointStruct -> has -> vector: Union[List[float], Dict[str, Vector]]
PointStruct -> has -> payload: Optional[Dict[str, Any]]

VectorParamsMap -> maps -> str -> VectorParams
SparseVectorParamsMap -> maps -> str -> SparseVectorParams

VectorParams -> defines -> size: int
VectorParams -> defines -> distance: Distance

Filter -> contains -> must: List[FieldCondition]
Filter -> contains -> should: List[FieldCondition]  
Filter -> contains -> must_not: List[FieldCondition]

FieldCondition -> filters -> key: str
FieldCondition -> uses -> match | range | geo | text

SearchResult -> contains -> points: List[ScoredPoint]
ScoredPoint -> has -> score: float
ScoredPoint -> has -> payload: Dict
ScoredPoint -> optionally_has -> vector: Dict
```

## Request/Response Schemas

### Collection Creation with Named Vectors

**Request Shape**:
```python
{
    "collection_name": "codebase_vectors",
    "vectors_config": {
        "semantic": {
            "size": 1536,
            "distance": "Cosine"
        },
        "code": {
            "size": 768,
            "distance": "Dot"
        }
    },
    "sparse_vectors_config": {
        "keywords": {
            "index": {
                "type": "immutable_ram"
            }
        }
    },
    "hnsw_config": {
        "m": 16,
        "ef_construct": 100
    }
}
```

**Response Shape**:
```python
{
    "result": True,
    "time": 0.042
}
```

### Multi-Vector Point Insertion

**Request Shape**:
```python
{
    "collection_name": "codebase_vectors",
    "points": [
        {
            "id": "file_123_func_456",
            "vector": {
                "semantic": [0.1, 0.2, ...],  # 1536 dimensions
                "code": [0.05, 0.15, ...],     # 768 dimensions
                "keywords": {
                    "indices": [1, 5, 10, 23],
                    "values": [0.8, 0.6, 0.9, 0.4]
                }
            },
            "payload": {
                "file_path": "src/auth/login.py",
                "line_start": 42,
                "line_end": 58,
                "function_name": "authenticate_user",
                "complexity_score": 7.2,
                "language": "python",
                "ast_type": "FunctionDef",
                "dependencies": ["bcrypt", "jwt"]
            }
        }
    ],
    "wait": True
}
```

### Hybrid Search Query

**Request Shape**:
```python
{
    "collection_name": "codebase_vectors",
    "query": {
        "semantic": [0.1, 0.2, ...],  # Semantic similarity vector
        "keywords": {
            "indices": [1, 5, 10],
            "values": [0.9, 0.8, 0.7]
        }
    },
    "filter": {
        "must": [
            {
                "key": "language",
                "match": {"value": "python"}
            },
            {
                "key": "complexity_score",
                "range": {"gte": 5.0, "lte": 8.0}
            }
        ],
        "should": [
            {
                "key": "ast_type",
                "match": {"value": "FunctionDef"}
            }
        ]
    },
    "limit": 10,
    "with_payload": True,
    "with_vectors": False
}
```

**Response Shape**:
```python
{
    "points": [
        {
            "id": "file_123_func_456",
            "score": 0.95,
            "payload": {
                "file_path": "src/auth/login.py",
                "line_start": 42,
                "line_end": 58,
                "function_name": "authenticate_user",
                "complexity_score": 7.2,
                "language": "python",
                "ast_type": "FunctionDef",
                "dependencies": ["bcrypt", "jwt"]
            }
        }
    ],
    "time": 0.003
}
```

## Patterns

### Multi-Embedding Architecture Pattern

Qdrant enables sophisticated multi-embedding strategies through named vectors, allowing CodeWeaver to combine different embedding types for comprehensive code understanding:

```python
# Collection configuration for multi-modal code search
vectors_config = {
    "semantic": VectorParams(size=1536, distance=Distance.COSINE),    # Natural language understanding
    "syntactic": VectorParams(size=768, distance=Distance.DOT),       # Code structure patterns  
    "api": VectorParams(size=512, distance=Distance.COSINE),          # API usage patterns
}

sparse_vectors_config = {
    "keywords": SparseVectorParams(),     # Keyword-based matching
    "identifiers": SparseVectorParams()   # Variable/function name matching
}

client.create_collection(
    collection_name="codebase_multi_modal",
    vectors_config=vectors_config,
    sparse_vectors_config=sparse_vectors_config
)
```

### Hybrid Search Implementation Pattern

Combining dense and sparse vectors for comprehensive code search:

```python
# Hybrid search query combining semantic understanding with keyword matching
search_result = client.search(
    collection_name="codebase_multi_modal",
    query_vector={
        "semantic": semantic_embedding,      # Dense vector from code description
        "keywords": sparse_keyword_vector    # Sparse vector from identifiers
    },
    query_filter=Filter(
        must=[
            FieldCondition(key="language", match=MatchValue(value="python")),
            FieldCondition(key="file_path", match=MatchText(text="auth"))
        ]
    ),
    limit=20
)
```

### Performance Optimization Patterns

**Payload Indexing Strategy**:
```python
# Create indexes for frequently filtered fields
client.create_payload_index("codebase", "language", "keyword")
client.create_payload_index("codebase", "complexity_score", "float")  
client.create_payload_index("codebase", "file_path", "text")
```

**Batch Operations Pattern**:
```python
# Efficient bulk insertion with optimal batch sizes
batch_size = 100
for i in range(0, len(points), batch_size):
    batch = points[i:i + batch_size]
    client.upsert(
        collection_name="codebase",
        points=batch,
        wait=True  # Ensure consistency
    )
```

### Async/Await Integration Pattern

For high-performance non-blocking operations:

```python
async def process_codebase_async(client: AsyncQdrantClient, file_chunks):
    tasks = []
    for chunk in file_chunks:
        task = client.upsert(
            collection_name="codebase",
            points=chunk,
            wait=False  # Non-blocking for async
        )
        tasks.append(task)
    
    # Await all operations
    results = await asyncio.gather(*tasks)
    return results
```

### Local Development Pattern

```python
# Local development with in-memory storage
client = QdrantClient(":memory:")

# Local development with persistent storage  
client = QdrantClient(path="./qdrant_data")

# Production deployment with gRPC optimization
client = QdrantClient(
    host="production-qdrant",
    grpc_port=6334,
    prefer_grpc=True,
    api_key=os.environ["QDRANT_API_KEY"]
)
```

## Differences vs Project

### Alignment Strengths

1. **Advanced Multi-Vector Support**: Perfect match for CodeWeaver's multi-modal search requirements with named vectors supporting different embedding types per point

2. **Hybrid Search Capabilities**: Native support for combining dense and sparse vectors enables sophisticated code search combining semantic understanding with keyword/identifier matching

3. **Payload-Based Filtering**: Robust metadata filtering system aligns with CodeWeaver's need for semantic search with file path, language, and complexity filters

4. **Performance Optimization**: Built-in payload indexing, batch operations, and gRPC support enable high-performance operations on large codebases

5. **Flexible Deployment**: Supports local development (:memory:, persistent), cloud deployment, and self-hosted options fitting CodeWeaver's diverse deployment needs

6. **Pydantic Integration**: Type-safe models align perfectly with CodeWeaver's pydantic-based architecture

### Implementation Strategies for CodeWeaver

1. **Collection Design**: Use named vectors for different embedding types:
   - `semantic`: Natural language understanding (Voyage embeddings)
   - `syntactic`: Code structure patterns (Code-specific embeddings)  
   - `keywords`: Sparse vectors for identifier/keyword matching

2. **Payload Schema**: Standardize metadata structure for consistent filtering:
   ```python
   payload_schema = {
       "file_path": str,
       "line_start": int,
       "line_end": int, 
       "language": str,
       "ast_type": str,
       "complexity": float,
       "dependencies": List[str]
   }
   ```

3. **Performance Optimization**: 
   - Create payload indexes for frequently filtered fields
   - Use gRPC for bulk operations
   - Implement async operations for non-blocking indexing

4. **Integration with pydantic-ai**: Use QdrantClient within pydantic-ai agent tools for context retrieval

5. **Error Handling Strategy**: Implement retry logic for network operations and graceful degradation for search failures

### Potential Integration Challenges

1. **Named Vector Complexity**: Need to carefully manage multiple embedding types and ensure consistent vector dimensions across all points

2. **Sparse Vector Implementation**: May require custom implementation of sparse vector generation from code identifiers/keywords

3. **Memory Management**: Large codebases may require careful memory management and vector quantization configuration

4. **Local vs Cloud**: Need abstraction layer to seamlessly switch between local development and production cloud deployments

5. **Version Compatibility**: Must ensure qdrant-client version compatibility with required advanced features (named vectors, sparse vectors)

## Blocking Questions

1. **Named Vector Performance**: What are the performance characteristics of named vector search compared to single vector search for large collections (>1M points)?

2. **Sparse Vector Generation**: Does qdrant-client provide utilities for generating sparse vectors from text/code, or does CodeWeaver need to implement this separately?

3. **Collection Migration**: How does qdrant handle collection schema changes when adding/removing named vectors or changing vector dimensions in production?

4. **Memory Requirements**: What are the memory requirements for hybrid search with multiple named vectors compared to single vector search?

5. **Concurrent Operations**: How does qdrant handle concurrent upsert and search operations, especially with payload index updates?

## Non-blocking Questions

1. **Quantization Impact**: How does vector quantization affect search accuracy for different embedding types and sizes?

2. **Backup/Recovery**: What are the recommended strategies for backing up and recovering large qdrant collections in production?

3. **Monitoring**: What metrics should CodeWeaver monitor for qdrant performance and health in production?

## Deep-Dive Research: Advanced Capabilities

### Sparse Vector Generation

**Status**: ✅ Resolved - Custom Implementation Required

Qdrant-client provides the `SparseVectorParams` configuration but **does not include built-in utilities for generating sparse vectors** from text or code. CodeWeaver will need to implement sparse vector generation separately.

**Key Findings**:
- `SparseVectorParams()` class supports sparse vector configuration in collections
- Sparse vectors use `indices` and `values` arrays for memory-efficient representation
- `SparseVectorParamsMap` allows multiple sparse vector types per collection
- Integration requires custom sparse vector generation pipeline using libraries like scikit-learn, spaCy, or custom TF-IDF implementations

**Recommended Implementation**:
```python
from qdrant_client.models import SparseVectorParams

# Collection configuration with sparse vectors
sparse_vectors_config = {
    "keywords": SparseVectorParams(),
    "identifiers": SparseVectorParams()
}

# CodeWeaver would implement:
def generate_sparse_vector(text: str, vocabulary: Dict[str, int]) -> SparseVector:
    # Custom TF-IDF or keyword extraction implementation
    pass
```

### Cloud Inference

**Status**: ✅ Resolved - Comprehensive Cloud Integration Available

Qdrant-client provides **robust cloud inference capabilities** through the `cloud_inference=True` parameter, enabling remote embedding generation and processing.

**Key Findings**:
- **Cloud Connection**: Simple configuration with `url` and `api_key` parameters
- **Remote Inference**: `cloud_inference=True` enables server-side embedding generation
- **Seamless Integration**: Works with existing search and upsert operations
- **Production Ready**: Designed for scalable cloud deployments with managed infrastructure

**Implementation Pattern**:
```python
from qdrant_client import QdrantClient

# Cloud inference configuration
client = QdrantClient(
    url="https://xxxxx.us-east.aws.cloud.qdrant.io:6333",
    api_key="<your-api-key>",
    cloud_inference=True  # Enable remote inference
)

# Server-side embedding generation for CodeWeaver
result = client.search(
    collection_name="codeweaver_collection",
    query_vector=query_vector,  # Generated on cloud
    limit=10
)
```

**Benefits for CodeWeaver**:
- Reduces local compute requirements for embedding generation
- Scales automatically with cloud infrastructure
- Consistent embedding models across development and production
- Offloads embedding complexity from CodeWeaver core logic

### Vector Invalidation Strategies

**Status**: ✅ Resolved - Multiple Invalidation Patterns Available

Qdrant-client supports sophisticated **vector invalidation and update strategies** for handling codebase changes through upsert operations, filtering, and payload-based tracking.

**Key Strategies**:

**1. Upsert-Based Invalidation**:
```python
# CodeWeaver can track file modifications and re-embed changed files
client.upsert(
    collection_name="codebase",
    points=[
        PointStruct(
            id=f"file_{file_hash}",  # Use file hash as stable ID
            vector=new_embeddings,
            payload={
                "file_path": "/src/main.py",
                "last_modified": timestamp,
                "git_commit": commit_hash,
                "invalidation_token": generation_id
            }
        )
    ]
)
```

**2. Payload-Based Filtering for Stale Data**:
```python
# Remove outdated vectors based on metadata
client.delete(
    collection_name="codebase",
    points_selector=models.FilterSelector(
        filter=models.Filter(
            must=[
                models.FieldCondition(
                    key="last_modified",
                    range=models.Range(lt=cutoff_timestamp)
                )
            ]
        )
    )
)
```

**3. Batch Invalidation with Point IDs**:
```python
# Efficient removal of specific points
stale_point_ids = get_changed_file_ids(git_diff)
client.delete(
    collection_name="codebase",
    points_selector=models.PointIdsList(
        points=stale_point_ids
    )
)
```

**4. Version-Based Collection Management**:
```python
# Maintain collection generations for atomic updates
current_collection = "codebase_v1"
next_collection = "codebase_v2"

# Build new collection with updated vectors
# Atomically switch alias when ready
client.create_alias(
    alias_name="codebase_current",
    collection_name=next_collection
)
```

**Recommended Architecture for CodeWeaver**:
1. **File-Based Tracking**: Use file hash + modification time as point IDs
2. **Metadata Enrichment**: Include git commit, file type, and dependency info in payload
3. **Incremental Updates**: Batch upsert changed files on codebase modifications  
4. **Cleanup Strategies**: Periodic removal of stale vectors based on payload filters
5. **Version Management**: Collection aliasing for atomic codebase version switches

## Sources

[Context7 Qdrant-Client Documentation | /qdrant/qdrant-client | Reliability: 5]
- Complete API reference and implementation examples
- Advanced features: named vectors, sparse vectors, hybrid search
- Performance optimization patterns and payload indexing
- Collection management and point operations
- Async/await patterns and error handling

[Qdrant Client GitHub Repository | https://github.com/qdrant/qdrant-client | Reliability: 5]  
- Source code structure and protobuf definitions
- Advanced configuration options and performance tuning
- Integration patterns with machine learning frameworks
- Testing utilities and development setup

[Qdrant Collections Protobuf Definitions | qdrant_client.grpc.collections_pb2 | Reliability: 5]
- Advanced collection configuration options including VectorParamsMap and SparseVectorParamsMap
- HNSW configuration and quantization options
- Detailed field definitions for complex collection setups

---

*This research provides comprehensive technical foundation for integrating qdrant-client's advanced multi-modal vector search capabilities into CodeWeaver's clean rebuild. All patterns and examples are designed to support CodeWeaver's requirements for sophisticated codebase intelligence with hybrid search, multiple embeddings, and high-performance semantic filtering.*