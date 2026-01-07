# OpenAI Embedding API Configuration Research

**Date**: 2026-01-04
**Purpose**: Establish proper configuration structure for OpenAI-compatible embedding providers
**Target**: `OpenAIEmbeddingConfig` class and `SerializedEmbeddingOptionsDict`

---

## Executive Summary

The OpenAI embeddings API has a **remarkably simple parameter surface** compared to other providers. The core `embeddings.create()` method accepts only **5 content parameters** plus **4 request control parameters**.

### Key Findings

1. **Content Parameters** (5 total):
   - `input`: Text(s) to embed (required)
   - `model`: Model identifier (required)
   - `dimensions`: Output dimensionality (optional, v3+ models only)
   - `encoding_format`: Response format "float" or "base64" (optional)
   - `user`: End-user identifier for abuse monitoring (optional)

2. **Request Control Parameters** (4 total):
   - `timeout`: Override client timeout
   - `extra_headers`: Additional HTTP headers
   - `extra_query`: Additional query parameters
   - `extra_body`: Additional JSON body properties

3. **No Distinction** between document and query embedding parameters - same parameters for both operations

4. **Provider Compatibility**: All OpenAI-compatible providers (Azure, Ollama, Together, Fireworks, GitHub Models) use the same core parameters

---

## OpenAI Python SDK Analysis

### Method Signature

From `openai-python/src/openai/resources/embeddings.py`:

```python
def create(
    self,
    *,
    input: Union[str, SequenceNotStr[str], Iterable[int], Iterable[Iterable[int]]],
    model: Union[str, EmbeddingModel],
    dimensions: int | Omit = omit,
    encoding_format: Literal["float", "base64"] | Omit = omit,
    user: str | Omit = omit,
    # Request control parameters
    extra_headers: Headers | None = None,
    extra_query: Query | None = None,
    extra_body: Body | None = None,
    timeout: float | httpx.Timeout | None | NotGiven = not_given,
) -> CreateEmbeddingResponse:
```

### Parameter Details

#### Required Parameters

**`input`**: `Union[str, SequenceNotStr[str], Iterable[int], Iterable[Iterable[int]]`
- Text or array of texts to embed
- Can be:
  - Single string
  - Array of strings
  - Array of token IDs
  - Array of token ID arrays
- **Limits**:
  - Max 8,192 tokens per input (all embedding models)
  - Max 300,000 tokens total across all inputs in single request
  - Cannot be empty string
  - Arrays must be ≤2,048 dimensions

**`model`**: `Union[str, EmbeddingModel]`
- Model identifier
- Examples: `"text-embedding-3-small"`, `"text-embedding-3-large"`, `"text-embedding-ada-002"`
- For compatible providers: use provider-specific model names

#### Optional Content Parameters

**`dimensions`**: `int | Omit`
- Number of dimensions in output embeddings
- **Only supported** in `text-embedding-3-*` models (v3+)
- Allows reducing dimensionality without losing concept-representing properties
- Valid ranges (model-specific):
  - `text-embedding-3-small`: 512 or 1536 (default: 1536)
  - `text-embedding-3-large`: 256, 1024, or 3072 (default: 3072)
- **Not supported** in `text-embedding-ada-002` and earlier models
- **When set**: Must call `adjust_collection_config_for_dimensionality()` to update vector store

**`encoding_format`**: `Literal["float", "base64"] | Omit`
- Format for returned embeddings
- Options:
  - `"float"`: Standard floating-point array (default in user code)
  - `"base64"`: Base64-encoded string (SDK default for optimization)
- SDK behavior: Defaults to `"base64"` internally for efficiency, then decodes to float/numpy
- User code: Should typically use `"float"` for simplicity

**`user`**: `str | Omit`
- Unique identifier for end-user
- Helps OpenAI monitor and detect abuse
- Optional but recommended for production systems
- See: https://platform.openai.com/docs/guides/safety-best-practices#end-user-ids

#### Request Control Parameters

**`timeout`**: `float | httpx.Timeout | None | NotGiven`
- Override client-level timeout for this request
- Specified in seconds
- Can be:
  - Float: simple timeout in seconds
  - `httpx.Timeout`: granular control (connect, read, write, pool)
- Default: 600 seconds (10 minutes) at client level
- Current CodeWeaver default: 30 seconds (from line 200 of openai_factory.py)

**`extra_headers`**: `Headers | None`
- Additional HTTP headers to send
- Type: `Dict[str, str]` or similar mapping
- Use case: Custom authentication, tracing headers, etc.

**`extra_query`**: `Query | None`
- Additional URL query parameters
- Type: `Dict[str, Any]` or similar mapping
- Use case: Provider-specific query params

**`extra_body`**: `Body | None`
- Additional JSON properties in request body
- Type: `Dict[str, Any]`
- Use case: Undocumented or provider-specific parameters

---

## Provider Compatibility Analysis

### Core OpenAI-Compatible Providers

All providers in `openai_factory.py` use the **same parameter set**:

1. **OpenAI** (official)
2. **Azure OpenAI** - Microsoft's hosted OpenAI
3. **Ollama** - Local model inference
4. **Together AI** - Hosted open-source models
5. **Fireworks AI** - Fast inference platform
6. **GitHub Models** - GitHub's model hosting
7. **Groq** - Hardware-accelerated inference
8. **Heroku** - Heroku-hosted models

### Provider-Specific Notes

#### Azure OpenAI
- Uses same parameters as OpenAI
- Differences are in **endpoint URL construction** and **authentication**
- Base URL format: `https://{endpoint}.{region}.inference.ai.azure.com/v1`
- Still uses standard `dimensions`, `encoding_format`, etc.

#### Ollama
- Accepts all OpenAI parameters
- API key can be any value (uses `"ollama"` by default)
- Local endpoint: `http://localhost:11434/v1`
- Model names differ (e.g., `"nomic-embed-text"`)

#### Together AI / Fireworks AI / Groq
- Full OpenAI API compatibility
- Same parameters, different base URLs and model names
- May not support all models that support `dimensions` parameter

### What's NOT Provider-Specific

- Parameter names and types are identical
- Request/response structure is the same
- The `dimensions` parameter works the same way (if model supports it)
- No provider-specific embedding parameters

### Current CodeWeaver Implementation

From `openai_factory.py` line 201-210:
```python
self._shared_kwargs = {"model": self.model_name, "encoding_format": "float", "timeout": 30}
self.valid_client_kwargs = (
    "model",
    "encoding_format",
    "timeout",
    "dimensions",
    "user",
    "extra_headers",
    "extra_query",
    "extra_body",
)
```

This already captures all valid parameters correctly.

---

## Recommended Configuration Structure

### OpenAI Embedding Options TypedDict

```python
class OpenAIEmbeddingRequestParams(TypedDict, total=False):
    """Parameters for OpenAI embedding requests.

    Used for both document and query embedding - OpenAI uses identical
    parameters for both operations.
    """

    dimensions: NotRequired[int]
    """Number of output dimensions. Only supported in text-embedding-3-* models.

    Valid values:
    - text-embedding-3-small: 512 or 1536 (default: 1536)
    - text-embedding-3-large: 256, 1024, or 3072 (default: 3072)
    - Not supported in text-embedding-ada-002
    """

    encoding_format: NotRequired[Literal["float", "base64"]]
    """Format for returned embeddings. Defaults to "float" for user code.

    Options:
    - "float": Standard floating-point array (recommended)
    - "base64": Base64-encoded string (used internally for optimization)
    """

    user: NotRequired[str]
    """Unique identifier for end-user to help monitor and detect abuse.

    See: https://platform.openai.com/docs/guides/safety-best-practices#end-user-ids
    """

    timeout: NotRequired[float]
    """Override client-level timeout for this request, in seconds.

    Default: 30 seconds (CodeWeaver default)
    Client default: 600 seconds (10 minutes)
    """

    extra_headers: NotRequired[dict[str, str]]
    """Additional HTTP headers to send with the request.

    Use for: Custom authentication, tracing headers, provider-specific headers
    """

    extra_query: NotRequired[dict[str, Any]]
    """Additional URL query parameters.

    Use for: Provider-specific query parameters
    """

    extra_body: NotRequired[dict[str, Any]]
    """Additional JSON properties in request body.

    Use for: Undocumented or provider-specific parameters
    """


class OpenAIEmbeddingConfig(BaseEmbeddingConfig):
    """Configuration for OpenAI-compatible embedding providers.

    Supports: OpenAI, Azure OpenAI, Ollama, Together AI, Fireworks AI,
    GitHub Models, Groq, Heroku.
    """

    model_name: LiteralString
    """The embedding model identifier.

    Examples:
    - OpenAI: "text-embedding-3-small", "text-embedding-3-large"
    - Ollama: "nomic-embed-text", "mxbai-embed-large"
    - Together: "togethercomputer/m2-bert-80M-8k-retrieval"
    """

    embedding: OpenAIEmbeddingRequestParams | None = None
    """Parameters for embedding requests (both documents and queries)."""

    def _as_options(self) -> SerializedEmbeddingOptionsDict:
        """Convert configuration to serialized options."""
        # Check if we need to adjust collection config
        if self.embedding and (dimensions := self.embedding.get("dimensions")):
            adjust_collection_config_for_dimensionality(dimensions)

        # OpenAI uses same params for both document and query embedding
        embedding_options = self.embedding or {}

        return SerializedEmbeddingOptionsDict(
            model_name=self.model_name,
            embedding=embedding_options,
            query=embedding_options,  # Identical to embedding
            model={},  # No model-level config for OpenAI
        )

    @property
    def _defaults(self) -> dict[str, Any]:
        """Return default values for the configuration."""
        return {
            "embedding": {
                "encoding_format": "float",
                "timeout": 30,
            }
        }
```

### SerializedEmbeddingOptionsDict Structure

For OpenAI providers:

```python
{
    "model_name": "text-embedding-3-small",  # Required
    "embedding": {
        "dimensions": 512,           # Optional
        "encoding_format": "float",  # Default
        "timeout": 30,              # Default
        "user": "user-123",         # Optional
        # Request control (rare usage)
        "extra_headers": {...},     # Optional
        "extra_query": {...},       # Optional
        "extra_body": {...},        # Optional
    },
    "query": {
        # Identical to embedding - no distinction in OpenAI API
        "dimensions": 512,
        "encoding_format": "float",
        "timeout": 30,
        "user": "user-123",
    },
    "model": {},  # Empty for OpenAI - no model-level config
}
```

---

## Key Differences from Other Providers

### vs. Bedrock
- **Bedrock**: Separate `model_id` in request params + model-specific config
- **OpenAI**: Model name only, no separate model config dict
- **Bedrock**: Model-specific embedding types (float, int8, uint8, binary)
- **OpenAI**: Only float or base64 encoding format

### vs. Google
- **Google**: Uses `output_dimensionality` instead of `dimensions`
- **OpenAI**: Uses `dimensions` parameter
- **Google**: Model name in embedding params, not as model field
- **OpenAI**: Model is top-level parameter

### vs. Cohere/Voyage
- **Cohere/Voyage**: Different params for documents vs queries (`input_type`)
- **OpenAI**: Identical parameters for both operations
- **Cohere**: Truncation options
- **OpenAI**: No truncation control (handled automatically)

---

## Default Values

### Recommended Defaults

```python
{
    "encoding_format": "float",  # Simplest for users
    "timeout": 30,              # Current CodeWeaver standard
}
```

### Don't Default

- `dimensions`: Model-specific, should be explicit if used
- `user`: Application-specific, should be explicit
- `extra_*`: Only used when needed

### SDK Defaults

- `encoding_format`: SDK defaults to `"base64"` internally for optimization, but converts to float
- `timeout`: 600 seconds (10 minutes) at client level

---

## Usage Examples

### Basic Usage

```python
config = OpenAIEmbeddingConfig(
    model_name="text-embedding-3-small",
)

options = config.as_options()
# {
#     "model_name": "text-embedding-3-small",
#     "embedding": {"encoding_format": "float", "timeout": 30},
#     "query": {"encoding_format": "float", "timeout": 30},
#     "model": {}
# }
```

### With Dimensionality Reduction

```python
config = OpenAIEmbeddingConfig(
    model_name="text-embedding-3-small",
    embedding={
        "dimensions": 512,  # Reduce from 1536 default
    }
)

# This will trigger adjust_collection_config_for_dimensionality(512)
options = config.as_options()
```

### With User Tracking

```python
config = OpenAIEmbeddingConfig(
    model_name="text-embedding-3-large",
    embedding={
        "user": "user-abc123",  # For abuse monitoring
        "timeout": 60,          # Longer timeout
    }
)
```

### Azure OpenAI (Same Config)

```python
# Same config class, different client initialization
config = OpenAIEmbeddingConfig(
    model_name="text-embedding-ada-002",  # Azure deployment name
    embedding={
        "extra_headers": {
            "api-key": "azure-key-here"
        }
    }
)
```

---

## Integration Notes

### Constructor vs. Client Options

Based on the pattern from other providers:

- **`constructor`**: Parameters for client initialization (covered by `client_options`)
  - For OpenAI: API key, base URL, HTTP client, default timeout
  - **Not needed** in SerializedEmbeddingOptionsDict (handled separately)

- **`embedding`/`query`**: Parameters for `embeddings.create()` call
  - For OpenAI: dimensions, encoding_format, user, timeout, extra_*

### Current Implementation Compatibility

The current `openai_factory.py` implementation (lines 201-220) already:
- ✅ Validates against `valid_client_kwargs`
- ✅ Merges `_shared_kwargs` with request-specific kwargs
- ✅ Separates `embed_options` and `query_options` (though they're identical for OpenAI)
- ✅ Filters kwargs to only valid parameters

This config structure will integrate seamlessly.

---

## Validation Considerations

### Model-Specific Validation

```python
def _validate_dimensions(self) -> Self:
    """Validate dimensions parameter against model capabilities."""
    if not self.embedding:
        return self

    dimensions = self.embedding.get("dimensions")
    if not dimensions:
        return self

    # Validate based on model
    if "text-embedding-3-small" in self.model_name:
        if dimensions not in [512, 1536]:
            raise ConfigurationError(
                f"Invalid dimensions {dimensions} for text-embedding-3-small. "
                "Valid values: 512, 1536"
            )
    elif "text-embedding-3-large" in self.model_name:
        if dimensions not in [256, 1024, 3072]:
            raise ConfigurationError(
                f"Invalid dimensions {dimensions} for text-embedding-3-large. "
                "Valid values: 256, 1024, 3072"
            )
    elif "ada-002" in self.model_name:
        raise ConfigurationError(
            "The dimensions parameter is not supported for text-embedding-ada-002. "
            "Use text-embedding-3-small or text-embedding-3-large for dimension control."
        )

    return self
```

### Timeout Validation

```python
def _validate_timeout(self) -> Self:
    """Validate timeout is reasonable."""
    if self.embedding and (timeout := self.embedding.get("timeout")):
        if timeout <= 0:
            raise ConfigurationError("Timeout must be positive")
        if timeout > 600:
            # Warn but don't error - might be intentional
            logger.warning(
                f"Timeout {timeout}s exceeds OpenAI client default (600s). "
                "Consider using client-level timeout instead."
            )
    return self
```

---

## Testing Recommendations

### Unit Tests

1. **Config serialization**: Verify `as_options()` produces correct structure
2. **Default values**: Ensure defaults are applied correctly
3. **Dimensionality adjustment**: Mock `adjust_collection_config_for_dimensionality()` calls
4. **Validation**: Test model-specific dimension validation
5. **Identical query/embedding**: Verify both dicts are identical

### Integration Tests

1. **OpenAI provider**: Real API calls with config
2. **Azure provider**: Config with Azure-specific setup
3. **Ollama provider**: Local model with config
4. **Dimension reduction**: Verify reduced dimensions work
5. **Timeout override**: Test timeout parameter works

---

## Summary Table

| Parameter | Type | Required | Default | Notes |
|-----------|------|----------|---------|-------|
| `model` | `str` | Yes | - | Model identifier |
| `input` | `str \| list[str] \| list[int] \| list[list[int]]` | Yes | - | Text(s) to embed |
| `dimensions` | `int` | No | Model default | v3+ models only |
| `encoding_format` | `"float" \| "base64"` | No | `"float"` | Response format |
| `user` | `str` | No | - | End-user identifier |
| `timeout` | `float` | No | `30` | Request timeout (seconds) |
| `extra_headers` | `dict[str, str]` | No | - | Additional headers |
| `extra_query` | `dict[str, Any]` | No | - | Additional query params |
| `extra_body` | `dict[str, Any]` | No | - | Additional body params |

---

## References

1. **OpenAI API Reference**: https://platform.openai.com/docs/api-reference/embeddings
2. **OpenAI Embedding Guide**: https://platform.openai.com/docs/guides/embeddings
3. **OpenAI Python SDK**: https://github.com/openai/openai-python
4. **SDK Source**: https://github.com/openai/openai-python/blob/main/src/openai/resources/embeddings.py
5. **Azure OpenAI**: https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/embeddings
6. **Ollama Compatibility**: https://docs.ollama.com/api/openai-compatibility
7. **Fireworks Compatibility**: https://docs.fireworks.ai/tools-sdks/openai-compatibility
8. **Together AI Compatibility**: https://docs.together.ai/docs/openai-api-compatibility

---

**End of Research Report**
