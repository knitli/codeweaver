# Remaining Exception Updates - Quick Reference

This document provides exact file:line references and replacement templates for the remaining generic exceptions.

## Priority 1: High-Impact Provider Files

### 1. Bedrock Embedding - Titan Length Check
**File**: `src/codeweaver/providers/embedding/providers/bedrock.py:582`

```python
# BEFORE
raise ValueError(
    f"Input text is too long for Titan Embedding V2. Max length is 50,000 characters. Input length is {len(doc)} characters."
)

# AFTER
raise CodeWeaverValidationError(
    "Input text exceeds Titan Embedding V2 maximum length",
    details={
        "provider": "bedrock",
        "model": "titan-embed-v2",
        "max_length": 50_000,
        "actual_length": len(doc),
        "excess_chars": len(doc) - 50_000,
    },
    suggestions=[
        "Split the text into smaller chunks (< 50,000 characters)",
        "Use a different embedding model with larger context window",
        "Consider summarizing the text before embedding",
    ],
)
```

### 2. Bedrock Reranking - Document Type Validation
**File**: `src/codeweaver/providers/reranking/providers/bedrock.py:146`

```python
# BEFORE
raise ValueError("Exactly one of json_document or text_document must be provided.")

# AFTER
raise CodeWeaverValidationError(
    "Bedrock reranking requires exactly one document type",
    details={
        "provider": "bedrock",
        "model": self._caps.name,
        "json_document_provided": json_document is not None,
        "text_document_provided": text_document is not None,
    },
    suggestions=[
        "Provide either json_document OR text_document, not both",
        "Ensure at least one document type is specified",
        "Check the document format matches the model requirements",
    ],
)
```

### 3. Sentence Transformers Reranking - Type Check
**File**: `src/codeweaver/providers/reranking/providers/sentence_transformers.py:107`

```python
# BEFORE
raise TypeError(f"Expected model_name to be str, got {type(name).__name__}")

# AFTER
raise CodeWeaverValidationError(
    "Reranking model name must be a string",
    details={
        "provider": "sentence_transformers",
        "received_type": type(name).__name__,
        "received_value": str(name)[:100],
    },
    suggestions=[
        "Provide model_name as a string, not an object",
        "Check model configuration in capabilities",
        "Verify model name is properly initialized",
    ],
)
```

## Priority 2: Vector Store Files

### 4. Vector Store Utils - Missing Model
**File**: `src/codeweaver/providers/vector_stores/utils.py:26`

```python
# BEFORE
raise ValueError("No embedding model configured.")

# AFTER
raise ConfigurationError(
    "Embedding model not configured for vector store",
    details={
        "component": "vector_store",
    },
    suggestions=[
        "Set embedding model in configuration",
        "Ensure EMBEDDING_MODEL environment variable is set",
        "Check embedding provider is properly initialized",
    ],
)
```

### 5. Vector Store Base - Uninitialized Client
**File**: `src/codeweaver/providers/vector_stores/base.py:151`

```python
# BEFORE
raise RuntimeError("Vector store client is not initialized.")

# AFTER
raise ProviderError(
    "Vector store client not initialized",
    details={
        "provider": self._provider.value if hasattr(self, '_provider') else "unknown",
        "client_type": type(self).__name__,
    },
    suggestions=[
        "Ensure initialize() method was called before use",
        "Check vector store configuration is valid",
        "Verify required dependencies are installed",
    ],
)
```

### 6. Vector Store Init - Missing Qdrant Config
**File**: `src/codeweaver/providers/vector_stores/__init__.py:61`

```python
# BEFORE
raise ValueError("Qdrant provider selected but no qdrant config provided")

# AFTER
raise ConfigurationError(
    "Qdrant configuration missing",
    details={
        "provider": "qdrant",
        "config_location": "QdrantConfig parameter",
    },
    suggestions=[
        "Provide QdrantConfig when using Qdrant provider",
        "Set QDRANT_URL and QDRANT_API_KEY environment variables",
        "Check qdrant section in configuration file",
    ],
)
```

### 7. Vector Store Init - Unknown Provider
**File**: `src/codeweaver/providers/vector_stores/__init__.py:66`

```python
# BEFORE
raise ValueError(
    f"Unsupported vector store provider: {config.provider}. "
    "Supported providers: qdrant, chromadb, pgvector"
)

# AFTER
raise ConfigurationError(
    f"Unknown vector store provider: {config.provider}",
    details={
        "provided_provider": str(config.provider),
        "supported_providers": ["qdrant", "chromadb", "pgvector"],
    },
    suggestions=[
        "Use one of the supported providers: qdrant, chromadb, pgvector",
        "Check provider name spelling in configuration",
        "Install required provider package",
    ],
)
```

## Priority 3: Registry and Configuration Files

### 8. Embedding Registry
**File**: `src/codeweaver/providers/embedding/registry.py:74`

**Note**: Need to check context - likely ConfigurationError for unknown embedding provider

### 9. Reranking Init - Unknown Provider
**File**: `src/codeweaver/providers/reranking/__init__.py:72`

```python
# BEFORE
raise ValueError(f"Unknown reranking provider: {provider}")

# AFTER
raise ConfigurationError(
    f"Unknown reranking provider: {provider}",
    details={
        "provided_provider": str(provider),
        "supported_providers": list(RerankingProviderRegistry.keys()),
    },
    suggestions=[
        "Check provider name spelling in configuration",
        "Install required reranking provider package",
        "Review available providers in documentation",
    ],
)
```

### 10. Reranking Capabilities - Type Check
**File**: `src/codeweaver/providers/reranking/capabilities/base.py:135`

```python
# BEFORE
raise TypeError(f"Expected max_input to be an int, got {type(self.max_input).__name__}")

# AFTER
raise CodeWeaverValidationError(
    "Reranking capability max_input must be an integer",
    details={
        "field": "max_input",
        "expected_type": "int",
        "received_type": type(self.max_input).__name__,
        "received_value": str(self.max_input),
    },
    suggestions=[
        "Set max_input as an integer in capabilities",
        "Check capability configuration schema",
        "Verify model capability definition",
    ],
)
```

### 11. Agent Providers - Unknown Provider
**File**: `src/codeweaver/providers/agent/agent_providers.py:132`

```python
# BEFORE
raise ValueError(f"Unknown provider: {provider}")

# AFTER
raise ConfigurationError(
    f"Unknown agent provider: {provider}",
    details={
        "provided_provider": str(provider),
        "supported_providers": ["openai", "anthropic", "groq", "together", "etc"],
    },
    suggestions=[
        "Check provider name spelling in configuration",
        "Install required agent provider package",
        "Review supported providers in documentation",
    ],
)
```

## Required Imports

Add these imports to the beginning of each file you modify:

```python
# For ProviderError
from codeweaver.exceptions import ProviderError

# For ConfigurationError
from codeweaver.exceptions import ConfigurationError

# For ValidationError (avoid conflict with Pydantic)
from codeweaver.exceptions import ValidationError as CodeWeaverValidationError
```

## Verification Commands

After making changes:

```bash
# Compile check
python -m py_compile <modified_file>.py

# Run tests for modified providers
pytest tests/unit/providers/ -k <provider_name>

# Full type check
pyright src/codeweaver/providers/

# Lint check
ruff check src/codeweaver/providers/
```

## Summary Statistics

**Total Remaining Updates**: ~15 instances
- **High Priority (provider files)**: 3 instances
- **Medium Priority (vector stores)**: 4 instances
- **Low Priority (registry/config)**: 8 instances

**Estimated Time**: 30-45 minutes for complete update
**Complexity**: Low - straightforward find/replace with context-specific details
