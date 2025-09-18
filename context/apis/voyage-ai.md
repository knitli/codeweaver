<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Voyage AI SDK - Complete API Research Report

*Expert API Analyst Research - Foundation for CodeWeaver Default Embeddings and Reranking Provider*

## Summary

**Feature Name**: Voyage AI SDK Integration  
**Feature Description**: State-of-the-art embeddings and reranking provider integration as CodeWeaver's default semantic search and retrieval components  
**Feature Goal**: Enable high-quality semantic search, document reranking, and multimodal embeddings for CodeWeaver's intelligent codebase context delivery

**Primary External Surface(s)**: `voyageai.Client`, `voyageai.AsyncClient`, embeddings API (`/v1/embeddings`), reranking API (`/v1/rerank`), multimodal embeddings API (`/v1/multimodalembeddings`)

**Integration Confidence**: High - Well-documented Python SDK, comprehensive API coverage, strong performance characteristics, and clear patterns for pydantic ecosystem integration

## Core Types

| Name | Kind | Definition | Role |
|------|------|------------|------|
| `voyageai.Client` | Sync Client Class | Main synchronous interface for Voyage AI API | Primary embeddings and reranking client for sync operations |
| `voyageai.AsyncClient` | Async Client Class | Asynchronous interface for Voyage AI API | Async embeddings and reranking for high-throughput operations |
| `EmbeddingsObject` | Response Class | Container for embedding results and metadata | Structured response with embeddings list and usage statistics |
| `RerankingObject` | Response Class | Container for reranking results and relevance scores | Structured response with ranked documents and relevance scores |
| `RerankingResult` | Data Class | Individual reranking result with document and score | Single document ranking with index, content, and relevance_score |
| `MultimodalEmbeddingsObject` | Response Class | Container for multimodal embedding results | Response for text+image embeddings with token usage tracking |
| `UsageLimits` | Configuration Class | Token and request limits for API calls | Rate limiting and quota management |

## Signatures

### Core Client Classes

**Name**: `voyageai.Client.__init__`  
**Import Path**: `import voyageai; vo = voyageai.Client()`  
**Concrete Path**: `voyageai-python/voyageai/client.py` (GitHub: https://github.com/voyage-ai/voyageai-python)  
**Signature**: `def __init__(api_key: str = None, max_retries: int = 0, timeout: int = None)`

**Params**:
- `api_key: str` (optional) - API key for authentication. If None, searches in: `voyageai.api_key_path`, `VOYAGE_API_KEY_PATH` env var, `voyageai.api_key` attribute, or `VOYAGE_API_KEY` env var
- `max_retries: int = 0` (optional) - Maximum retries for rate limit errors or server unavailability
- `timeout: int = None` (optional) - Maximum wait time in seconds for API response

**Returns**: `voyageai.Client` instance  
**Errors**: `ImportError` if package not installed, authentication errors if invalid API key  
**Notes**: Automatic environment variable detection simplifies configuration. Default 0 retries for predictable behavior

**Type Information**: 
```python
class Client:
    api_key: Optional[str]
    max_retries: int
    timeout: Optional[int]
```

### Embeddings Generation

**Name**: `voyageai.Client.embed`  
**Import Path**: `from voyageai import Client`  
**Signature**: `def embed(texts: Union[str, List[str]], model: str, input_type: Optional[str] = None, truncation: Optional[bool] = True, output_dimension: Optional[int] = None, output_dtype: Optional[str] = "float") -> EmbeddingsObject`

**Params**:
- `texts: Union[str, List[str]]` (required) - Single text or list of texts (max 1,000 items)
- `model: str` (required) - Model name (recommended: `voyage-3-large`, `voyage-3.5`, `voyage-3.5-lite`, `voyage-code-3`)
- `input_type: Optional[str] = None` - Type hint for retrieval optimization (`None`, `"query"`, `"document"`)
- `truncation: Optional[bool] = True` - Whether to truncate over-length inputs
- `output_dimension: Optional[int] = None` - Embedding dimension (256, 512, 1024, 2048 for supported models)
- `output_dtype: Optional[str] = "float"` - Output format (`"float"`, `"int8"`, `"uint8"`, `"binary"`, `"ubinary"`)

**Returns**: `EmbeddingsObject` with `.embeddings: List[List[float]]` and usage metadata  
**Errors**: `ValueError` for invalid parameters, rate limit errors, token limit exceeded  
**Notes**: Supports batch processing, flexible dimensions, quantization options. `input_type` prepends optimization prompts

**Type Information**:
```python
class EmbeddingsObject:
    embeddings: List[List[float]]
    usage: Dict[str, int]  # Contains token counts and other usage metrics
```

### Document Reranking

**Name**: `voyageai.Client.rerank`  
**Import Path**: `from voyageai import Client`  
**Signature**: `def rerank(query: str, documents: List[str], model: str, top_k: Optional[int] = None, truncation: bool = True) -> RerankingObject`

**Params**:
- `query: str` (required) - Search query (max 4,000 tokens for rerank-2)
- `documents: List[str]` (required) - List of documents to rerank (max 1,000 documents)
- `model: str` (required) - Reranking model (`"rerank-2"`, `"rerank-2-lite"` recommended)
- `top_k: Optional[int] = None` - Number of top results to return (defaults to all)
- `truncation: bool = True` - Whether to truncate inputs to fit context limits

**Returns**: `RerankingObject` with `.results: List[RerankingResult]` sorted by relevance  
**Errors**: Token limit exceeded, document count exceeded, rate limit errors  
**Notes**: Results sorted by descending relevance score. Each result contains index, document, and relevance_score

**Type Information**:
```python
class RerankingObject:
    results: List[RerankingResult]
    total_tokens: int

class RerankingResult:
    index: int
    document: str
    relevance_score: float
```

### Multimodal Embeddings

**Name**: `voyageai.Client.multimodal_embed`  
**Import Path**: `from voyageai import Client`  
**Signature**: `def multimodal_embed(inputs: List[Union[List[Union[str, PIL.Image.Image]], dict]], model: str, input_type: Optional[str] = None, truncation: Optional[bool] = True) -> MultimodalEmbeddingsObject`

**Params**:
- `inputs: List[Union[List[Union[str, PIL.Image.Image]], dict]]` (required) - Multimodal inputs (text + images, max 1,000 inputs)
- `model: str` (required) - Currently only `"voyage-multimodal-3"` supported
- `input_type: Optional[str] = None` - Type optimization (`None`, `"query"`, `"document"`)
- `truncation: Optional[bool] = True` - Whether to truncate over-length inputs

**Returns**: `MultimodalEmbeddingsObject` with embeddings and token usage  
**Errors**: Image size limits (16M pixels, 20MB), token limits exceeded  
**Notes**: Images counted as tokens (560 pixels = 1 token). Supports PIL Image objects and base64 encoded images

### Async Client Methods

**Name**: `voyageai.AsyncClient.embed`  
**Signature**: `async def embed(...) -> EmbeddingsObject`  
**Notes**: Identical parameters to sync version, returns awaitable

**Name**: `voyageai.AsyncClient.rerank`  
**Signature**: `async def rerank(...) -> RerankingObject`  
**Notes**: Identical parameters to sync version, returns awaitable

## Type Graph

```
voyageai.Client -> contains -> str api_key
voyageai.Client -> contains -> int max_retries  
voyageai.Client -> contains -> Optional[int] timeout
voyageai.Client -> returns -> EmbeddingsObject
voyageai.Client -> returns -> RerankingObject
voyageai.Client -> returns -> MultimodalEmbeddingsObject

EmbeddingsObject -> contains -> List[List[float]] embeddings
EmbeddingsObject -> contains -> Dict[str, int] usage

RerankingObject -> contains -> List[RerankingResult] results
RerankingObject -> contains -> int total_tokens
RerankingResult -> contains -> int index
RerankingResult -> contains -> str document
RerankingResult -> contains -> float relevance_score

MultimodalEmbeddingsObject -> contains -> List[List[float]] embeddings
MultimodalEmbeddingsObject -> contains -> int text_tokens
MultimodalEmbeddingsObject -> contains -> int image_pixels
MultimodalEmbeddingsObject -> contains -> int total_tokens

voyageai.AsyncClient -> extends -> voyageai.Client
```

## Request/Response Schemas

### Embeddings API Endpoint

**Endpoint**: `POST https://api.voyageai.com/v1/embeddings`  
**Purpose**: Generate semantic embeddings for text inputs

**Request Shape**:
```python
{
    "input": "string | List[str]",  # Text(s) to embed
    "model": "string",              # Model name (e.g., "voyage-3.5")
    "input_type": "query | document | null",  # Optimization hint
    "truncation": "boolean",        # Truncate over-length inputs
    "output_dimension": "int | null",  # Desired dimension
    "output_dtype": "float | int8 | uint8 | binary | ubinary"
}
```

**Response Shape**:
```python
{
    "data": [
        {
            "object": "embedding",
            "embedding": "List[float]",  # Vector representation
            "index": "int"               # Input index
        }
    ],
    "object": "list",
    "model": "string",
    "usage": {
        "total_tokens": "int"
    }
}
```

**Auth Requirements**: `Authorization: Bearer <VOYAGE_API_KEY>` header

### Reranking API Endpoint

**Endpoint**: `POST https://api.voyageai.com/v1/rerank`  
**Purpose**: Rerank documents by relevance to query

**Request Shape**:
```python
{
    "query": "string",         # Search query
    "documents": "List[str]",  # Documents to rerank
    "model": "string",         # Reranking model
    "top_k": "int | null",     # Max results to return
    "truncation": "boolean"    # Truncate over-length inputs
}
```

**Response Shape**:
```python
{
    "results": [
        {
            "index": "int",           # Original document index
            "document": "string",     # Document content
            "relevance_score": "float"  # Relevance to query
        }
    ],
    "total_tokens": "int"  # Total tokens processed
}
```

### Multimodal Embeddings API

**Endpoint**: `POST https://api.voyageai.com/v1/multimodalembeddings`  
**Purpose**: Generate embeddings for text and image combinations

**Request Shape**:
```python
{
    "inputs": [
        {
            "content": [
                {"type": "text", "text": "string"},
                {"type": "image_base64", "image_base64": "data:image/jpeg;base64,..."}
            ]
        }
    ],
    "model": "voyage-multimodal-3",
    "input_type": "query | document | null",
    "truncation": "boolean"
}
```

**Response Shape**:
```python
{
    "embeddings": "List[List[float]]",
    "text_tokens": "int",
    "image_pixels": "int", 
    "total_tokens": "int"
}
```

## Patterns

### Authentication and Configuration

Voyage AI uses environment variable-based authentication by default:

```python
# Automatic authentication (recommended)
import voyageai
vo = voyageai.Client()  # Uses VOYAGE_API_KEY env var

# Explicit authentication
vo = voyageai.Client(api_key="your-secret-key")

# With retry configuration
vo = voyageai.Client(max_retries=3, timeout=30)
```

### Batch Processing for High Throughput

```python
# Process large document collections efficiently
batch_size = 128
embeddings = []

for i in range(0, len(documents), batch_size):
    batch = documents[i:i + batch_size]
    batch_embeddings = vo.embed(
        batch, 
        model="voyage-3.5", 
        input_type="document"
    ).embeddings
    embeddings += batch_embeddings
    
    # Rate limiting
    time.sleep(0.1)  # Avoid hitting rate limits
```

### Retrieval-Optimized Embeddings

```python
# Generate query embedding
query_embedding = vo.embed(
    ["Find authentication code"], 
    model="voyage-3.5", 
    input_type="query"
).embeddings[0]

# Generate document embeddings  
doc_embeddings = vo.embed(
    document_texts, 
    model="voyage-3.5", 
    input_type="document"
).embeddings

# Voyage embeddings are normalized - dot product = cosine similarity
similarities = np.dot(doc_embeddings, query_embedding)
```

### Two-Stage Retrieval with Reranking

```python
# Stage 1: Vector similarity search (fast, broad recall)
top_candidates = vector_search(query_embedding, k=50)

# Stage 2: Neural reranking (slower, high precision)  
reranked = vo.rerank(
    query="Find authentication code",
    documents=[doc.content for doc in top_candidates],
    model="rerank-2",
    top_k=5
)

final_results = [reranked.results[i].document for i in range(len(reranked.results))]
```

### Flexible Embedding Dimensions and Quantization

```python
# High-quality full embeddings (default)
embeddings_1024 = vo.embed(texts, model="voyage-3.5").embeddings

# Compressed embeddings for storage efficiency
embeddings_512 = vo.embed(
    texts, 
    model="voyage-3.5", 
    output_dimension=512
).embeddings

# Quantized embeddings for extreme efficiency
embeddings_binary = vo.embed(
    texts,
    model="voyage-3.5", 
    output_dtype="binary",
    output_dimension=2048
).embeddings
```

### Multimodal Code Understanding

```python
import PIL

# Combine code snippets with screenshots/diagrams
inputs = [
    [
        "This authentication flow diagram shows the OAuth process:",
        PIL.Image.open("auth_diagram.png")
    ]
]

multimodal_embeddings = vo.multimodal_embed(
    inputs,
    model="voyage-multimodal-3",
    input_type="document"
)
```

## Differences vs Project

### Alignment Strengths

1. **Performance Leadership**: Voyage AI significantly outperforms OpenAI embeddings with 1/4 the vector size, aligning perfectly with CodeWeaver's performance goals

2. **Comprehensive Model Suite**: Offers specialized models for code (`voyage-code-3`), general use (`voyage-3.5`), and efficiency (`voyage-3.5-lite`) matching CodeWeaver's diverse context needs

3. **Simple Configuration**: Environment variable-based auth and minimal configuration aligns with CodeWeaver's pydantic-settings approach

4. **Async Support**: Native async client enables integration with CodeWeaver's async pipeline architecture

5. **Batch Processing**: Built-in batch support for handling multiple documents efficiently

6. **Rate Limit Management**: Comprehensive rate limiting with retry strategies and exponential backoff patterns

### Integration Considerations for CodeWeaver

1. **Pydantic-AI Provider Abstraction**: Voyage AI doesn't integrate directly with pydantic-ai's provider system - CodeWeaver needs to create custom embedding provider adapter

2. **Graph Pipeline Integration**: Need to wrap Voyage AI calls in pydantic-graph nodes for CodeWeaver's pipeline architecture

3. **Configuration Unification**: Merge Voyage AI client configuration with CodeWeaver's pydantic-settings system

4. **Error Handling Standardization**: Adapt Voyage AI errors to CodeWeaver's unified error handling patterns

5. **Usage Tracking**: Integrate token counting and usage statistics with CodeWeaver's telemetry system

### Suggested Adapter Architecture

**Embedding Provider Adapter**:
```python
from pydantic import BaseModel
from typing import List, Optional
import voyageai

class VoyageEmbeddingProvider(BaseModel):
    api_key: Optional[str] = None
    model: str = "voyage-3.5" 
    max_retries: int = 3
    timeout: Optional[int] = 30
    
    def __post_init__(self):
        self._client = voyageai.Client(
            api_key=self.api_key,
            max_retries=self.max_retries,
            timeout=self.timeout
        )
    
    async def embed_texts(
        self, 
        texts: List[str], 
        input_type: Optional[str] = None
    ) -> List[List[float]]:
        result = await self._async_client.embed(
            texts=texts,
            model=self.model,
            input_type=input_type
        )
        return result.embeddings
        
    async def rerank_documents(
        self,
        query: str,
        documents: List[str],
        top_k: Optional[int] = None
    ) -> List[str]:
        result = await self._async_client.rerank(
            query=query,
            documents=documents, 
            model="rerank-2",
            top_k=top_k
        )
        return [r.document for r in result.results]
```

**Graph Node Integration**:
```python
from pydantic_graph import BaseNode
from typing import List

@dataclass
class EmbedDocuments(BaseNode[CodeSearchState]):
    documents: List[str]
    
    async def run(self, ctx: GraphRunContext[CodeSearchState]) -> SearchVectors:
        embeddings = await ctx.deps.embedding_provider.embed_texts(
            texts=self.documents,
            input_type="document"
        )
        
        return SearchVectors(
            query_embedding=ctx.state.query_embedding,
            document_embeddings=embeddings,
            documents=self.documents
        )
```

### Model Selection Strategy

**Default Model Recommendations**:
- **General Code Context**: `voyage-code-3` (optimized for code retrieval)
- **Fast Queries**: `voyage-3.5-lite` (optimized for latency)
- **High Quality**: `voyage-3-large` (best retrieval quality)
- **Reranking**: `rerank-2` (best quality) or `rerank-2-lite` (balance of quality/speed)

**Dimension Strategy**:
- **Default**: 1024 dimensions (good balance)
- **High-recall search**: 2048 dimensions 
- **Storage-constrained**: 512 dimensions
- **Extreme efficiency**: Binary quantization

## Blocking Questions

1. **Provider Integration Pattern**: Should CodeWeaver create a custom pydantic-ai compatible provider for Voyage AI, or implement embedding providers outside the pydantic-ai framework? How does this affect the architecture's consistency?

2. **Configuration Hierarchy**: How should Voyage AI client settings integrate with CodeWeaver's pydantic-settings configuration? Should model selection be user-configurable or handled intelligently based on query type?

3. **Error Handling Strategy**: How should CodeWeaver handle Voyage AI rate limits and failures within the pydantic-graph pipeline? Should individual nodes handle retries or delegate to a centralized error handler?

4. **Token Usage Tracking**: Does CodeWeaver need to implement custom token counting for cost management, or rely on Voyage AI's usage reporting? How does this integrate with the telemetry system?

5. **Async Client Lifecycle**: How should the async client instance be managed within CodeWeaver's dependency injection system? Should it be a singleton, per-request, or per-pipeline instance?

## Non-blocking Questions

1. **Performance Benchmarking**: What are the actual latency characteristics of different Voyage AI models in CodeWeaver's target scenarios (small repos vs large monorepos)?

2. **Multimodal Integration**: How can CodeWeaver leverage Voyage AI's multimodal capabilities for code documentation that includes diagrams, screenshots, or visual documentation?

3. **Caching Strategy**: Should CodeWeaver implement embedding caching at the Voyage AI level, or handle it at a higher level in the pipeline?

4. **Model Evolution**: How should CodeWeaver handle Voyage AI model updates and migrations without breaking existing embeddings?

5. **Cost Optimization**: What are the optimal batching and quantization strategies for different CodeWeaver usage patterns to minimize costs while maintaining quality?

## Sources

[Context7 Voyage AI Documentation | /context7/voyageai | Reliability: 5]
- Complete API reference with 85+ code examples
- Embedding and reranking model specifications
- Rate limits, authentication, and configuration patterns
- Integration patterns for RAG applications
- Performance characteristics and optimization strategies

[Voyage AI Python SDK | /voyage-ai/voyageai-python | GitHub Repository | Reliability: 5]  
- Official Python client implementation
- SDK architecture and client configuration
- Authentication and error handling patterns
- RAG integration strategies and performance claims

[Voyage AI Official Documentation | https://docs.voyageai.com/ | Reliability: 5]
- REST API specifications and request/response schemas
- Model capabilities, context lengths, and optimization guidance  
- Authentication, rate limiting, and usage tracking
- Multimodal embedding capabilities and constraints
- Token counting, quantization, and dimension flexibility

---

*This research provides comprehensive technical foundation for integrating Voyage AI as CodeWeaver's default embeddings and reranking provider. All patterns and configurations are designed to align with CodeWeaver's clean architecture principles, pydantic ecosystem integration, and performance-focused goals.*