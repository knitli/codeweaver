<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Client Instantiation Architecture Design

**Date**: 2025-11-03
**Status**: Design Complete - Ready for Implementation
**Priority**: 🔴 CRITICAL

## Executive Summary

This document describes the unified client instantiation architecture that will fix the critical gap in CodeWeaver's provider system where client instances are never created, causing provider instantiation to fail.

## Problem Statement

### Current State ❌

```
Settings → Provider Registry → Provider Instance (FAILS)
                              ↓
                         Missing: client parameter
```

**Critical Issues:**
1. Providers expect a `client` parameter in `__init__` but none is created
2. Registry prepares `client_options` but never instantiates actual clients
3. Would cause `TypeError: missing required argument 'client'`

### Expected State ✅

```
Settings → Provider Registry → Client Factory → Provider Instance
           ↓                    ↓
           configuration        actual API client
```

**Flow:**
1. Settings defines provider configuration (API keys, models, options)
2. Registry reads configuration and identifies provider type
3. **Client Factory** creates actual client instances (VoyageAI, Qdrant, etc.)
4. Provider instances are created with configured clients
5. Registry manages and caches provider instances

## Architecture Design

### Component: Client Factory

**Location**: `src/codeweaver/common/registry/provider.py`

**Responsibilities:**
1. Create provider-specific client instances
2. Apply user configuration and client_options
3. Handle authentication (API keys, credentials)
4. Support both sync and async clients where applicable

### Implementation Plan

#### 1. Add Client Factory Methods

**For Model Providers** (embedding, sparse_embedding, reranking):

```python
def _create_model_provider_client(
    self,
    provider: Provider,
    provider_settings: dict[str, Any] | None,
    client_options: dict[str, Any] | None,
) -> Any:
    """Create client instance for model providers.

    Args:
        provider: Provider enum (VOYAGE, OPENAI, etc.)
        provider_settings: Provider-specific auth/config
        client_options: User-specified client options

    Returns:
        Configured client instance ready for API calls
    """
    match provider:
        case Provider.VOYAGE:
            from voyageai import AsyncClient
            api_key = provider_settings.get("api_key") if provider_settings else None
            if not api_key:
                api_key = os.getenv("VOYAGE_API_KEY")
            return AsyncClient(api_key=api_key, **(client_options or {}))

        case Provider.OPENAI:
            from openai import AsyncOpenAI
            api_key = provider_settings.get("api_key") if provider_settings else None
            return AsyncOpenAI(api_key=api_key, **(client_options or {}))

        case Provider.COHERE:
            from cohere import AsyncClientV2
            api_key = provider_settings.get("api_key") if provider_settings else None
            return AsyncClientV2(api_key=api_key, **(client_options or {}))

        case Provider.FASTEMBED:
            # FastEmbed doesn't use a traditional client
            return None

        case Provider.JINA:
            from jina_client import JinaAsyncClient
            api_key = provider_settings.get("api_key") if provider_settings else None
            return JinaAsyncClient(api_key=api_key, **(client_options or {}))

        case _:
            logger.warning(
                "No client factory for provider '%s', passing None", provider
            )
            return None
```

**For Vector Store Providers**:

```python
def _create_vector_store_client(
    self,
    provider: Provider,
    provider_settings: dict[str, Any] | None,
    client_options: dict[str, Any] | None,
) -> Any:
    """Create client instance for vector store providers.

    Args:
        provider: Provider enum (QDRANT, CHROMA, etc.)
        provider_settings: Provider-specific connection config
        client_options: User-specified client options

    Returns:
        Configured vector store client instance
    """
    match provider:
        case Provider.QDRANT:
            from qdrant_client import QdrantClient

            # Determine connection mode
            url = provider_settings.get("url") if provider_settings else None
            path = provider_settings.get("path") if provider_settings else None

            if url:
                # Remote Qdrant server
                api_key = provider_settings.get("api_key")
                return QdrantClient(url=url, api_key=api_key, **(client_options or {}))
            elif path:
                # Local persistent storage
                return QdrantClient(path=path, **(client_options or {}))
            else:
                # In-memory mode
                return QdrantClient(location=":memory:", **(client_options or {}))

        case Provider.CHROMA:
            from chromadb import AsyncClient

            # Support both HTTP and persistent modes
            host = provider_settings.get("host") if provider_settings else None
            path = provider_settings.get("path") if provider_settings else None

            if host:
                port = provider_settings.get("port", 8000)
                return AsyncClient(host=host, port=port, **(client_options or {}))
            else:
                # Local persistent client
                return AsyncClient(path=path, **(client_options or {}))

        case Provider.FAISS:
            # FAISS doesn't use a traditional client, return None
            return None

        case _:
            logger.warning(
                "No client factory for vector store '%s', passing None", provider
            )
            return None
```

#### 2. Integrate Client Factory into `create_provider`

**Modified Flow** (lines 617-664):

```python
def create_provider(
    self, provider: Provider, provider_kind: LiteralKinds, **kwargs: Any
) -> (
    EmbeddingProvider[Any]
    | RerankingProvider[Any]
    | VectorStoreProvider[Any]
    | AgentProvider[Any]
    | Any
):
    """Create a provider instance by provider enum and provider kind.

    Args:
        provider: The provider enum identifier
        provider_kind: The type of provider
        **kwargs: Provider-specific initialization arguments

    Returns:
        An initialized provider instance
    """
    retrieved_cls = None
    if self._is_literal_model_kind(provider_kind):
        retrieved_cls = self.get_provider_class(provider, provider_kind)
    if self._is_literal_vector_store_kind(provider_kind):
        retrieved_cls = self.get_provider_class(provider, provider_kind)
    if self._is_literal_data_kind(provider_kind):
        retrieved_cls = self.get_provider_class(provider, provider_kind)

    # 🔧 NEW: Create client instance before provider instantiation
    if "client" not in kwargs:
        # Extract settings for client creation
        provider_settings = kwargs.get("provider_settings")
        client_options = kwargs.get("client_options")

        # Create appropriate client based on provider kind
        if self._is_literal_model_kind(provider_kind):
            client = self._create_model_provider_client(
                provider, provider_settings, client_options
            )
            if client is not None:
                kwargs["client"] = client

        elif self._is_literal_vector_store_kind(provider_kind):
            client = self._create_vector_store_client(
                provider, provider_settings, client_options
            )
            if client is not None:
                kwargs["client"] = client

    # Special handling for embedding provider (has different logic)
    if provider_kind in (ProviderKind.EMBEDDING, "embedding"):
        if self._is_openai_factory(retrieved_cls):
            retrieved_cls = self._construct_openai_provider_class(
                provider, retrieved_cls, **kwargs
            )

        name = None
        with contextlib.suppress(Exception):
            name = retrieved_cls.__name__
        if not name:
            logger.warning("Embedding provider '%s' could not be imported.", provider)
            raise ConfigurationError(f"Embedding provider '{provider}' could not be imported.")
        return cast(EmbeddingProvider[Any], retrieved_cls(**kwargs))

    # Standard handling for other providers
    if isinstance(retrieved_cls, LazyImport):
        return self._create_provider(provider, retrieved_cls, **kwargs)
    return retrieved_cls(**kwargs)
```

#### 3. Update `_prepare_model_provider_kwargs`

Ensure `provider_settings` and `client_options` are properly extracted:

```python
def _prepare_model_provider_kwargs(
    self,
    config: DictView[EmbeddingProviderSettings]
    | DictView[SparseEmbeddingProviderSettings]
    | DictView[RerankingProviderSettings]
    | DictView[AgentProviderSettings],
    **user_kwargs: Any,
) -> dict[str, Any]:
    """Prepare kwargs for model providers from config."""
    kwargs: dict[str, Any] = {}

    # Add capabilities
    if "caps" not in user_kwargs and "model_settings" in config:
        model = config["model_settings"].get("model")
        if model:
            kwargs["caps"] = self._get_capabilities_for_model(model)

    # Add model settings
    if "model_settings" in config:
        self._add_model_settings_to_kwargs(config["model_settings"], kwargs)

    # Add provider settings (for client creation)
    if "provider_settings" in config:
        self._add_provider_settings_to_kwargs(config["provider_settings"], kwargs)

    # 🔧 IMPORTANT: Preserve client_options for client factory
    if "client_options" in config:
        kwargs["client_options"] = config["client_options"]

    # User kwargs override everything
    kwargs.update(user_kwargs)

    return kwargs
```

### Authentication Strategy

**Priority Order:**
1. Explicit `provider_settings` in config
2. Environment variables (provider-specific)
3. Global environment variables (for backward compatibility)

**Environment Variable Patterns:**

```bash
# Provider-specific (preferred)
VOYAGE_API_KEY=xxx
OPENAI_API_KEY=xxx
COHERE_API_KEY=xxx
QDRANT_URL=http://localhost:6333
QDRANT_API_KEY=xxx

# CodeWeaver settings (alternative)
CODEWEAVER_PROVIDER__EMBEDDING__0__PROVIDER_SETTINGS__API_KEY=xxx
```

### Error Handling

**Client Creation Failures:**

```python
def _create_model_provider_client(
    self,
    provider: Provider,
    provider_settings: dict[str, Any] | None,
    client_options: dict[str, Any] | None,
) -> Any:
    """Create client with error handling."""
    try:
        # ... client creation logic
    except ImportError as e:
        logger.error(
            "Failed to import client for provider '%s': %s. "
            "Ensure the provider package is installed.",
            provider, e
        )
        raise ConfigurationError(
            f"Provider '{provider}' client import failed. "
            f"Install with: pip install {provider.client_package}"
        ) from e
    except Exception as e:
        logger.error(
            "Failed to create client for provider '%s': %s",
            provider, e
        )
        raise ConfigurationError(
            f"Provider '{provider}' client creation failed: {e}"
        ) from e
```

## Implementation Checklist

- [x] Design client factory architecture
- [ ] Implement `_create_model_provider_client` method
- [ ] Implement `_create_vector_store_client` method
- [ ] Update `create_provider` to use client factory
- [ ] Update `_prepare_model_provider_kwargs` to preserve client_options
- [ ] Add authentication resolution logic
- [ ] Add comprehensive error handling
- [ ] Add unit tests for client factory
- [ ] Add integration tests for full flow
- [ ] Update documentation
- [ ] Add telemetry for client creation

## Testing Strategy

### Unit Tests

```python
def test_create_voyage_client():
    """Test Voyage client creation with API key."""
    registry = ProviderRegistry()

    provider_settings = {"api_key": "test_key"}
    client_options = {"timeout": 30.0}

    client = registry._create_model_provider_client(
        Provider.VOYAGE, provider_settings, client_options
    )

    assert isinstance(client, AsyncClient)
    assert client.api_key == "test_key"


def test_create_qdrant_client_url_mode():
    """Test Qdrant client creation with URL."""
    registry = ProviderRegistry()

    provider_settings = {
        "url": "http://localhost:6333",
        "api_key": "test_key"
    }

    client = registry._create_vector_store_client(
        Provider.QDRANT, provider_settings, None
    )

    assert isinstance(client, QdrantClient)
```

### Integration Tests

```python
async def test_full_provider_instantiation_flow():
    """Test complete flow from settings to provider instance."""
    # 1. Configure settings
    settings = CodeWeaverSettings(
        provider=ProviderSettings(
            embedding=(
                EmbeddingProviderSettings(
                    provider=Provider.VOYAGE,
                    model_settings={"model": "voyage-code-3"},
                    provider_settings={"api_key": "test_key"},
                    client_options={"timeout": 30.0}
                ),
            )
        )
    )

    # 2. Create registry
    registry = ProviderRegistry(settings)

    # 3. Get provider instance
    provider = registry.get_provider_instance(ProviderKind.EMBEDDING)

    # 4. Verify client was created
    assert provider.client is not None
    assert isinstance(provider.client, AsyncClient)

    # 5. Test actual embedding call
    result = await provider.embed(["test text"])
    assert len(result) == 1
    assert len(result[0]) == 1024  # voyage-code-3 dimension
```

## Migration Path

### Phase 1: Add Client Factory (This PR)
- Implement client factory methods
- Integrate into `create_provider`
- Add tests
- **No breaking changes** - backward compatible

### Phase 2: Settings Refactor (Future PR)
- Convert TypedDict to BaseSettings
- Flatten provider structure
- Add validation aliases
- **Breaking changes** - major version bump

### Phase 3: Enhanced Features (Future)
- Hot-reload support
- Connection pooling
- Client health checks
- Metrics and monitoring

## Compliance

**Constitutional Alignment:**
- ✅ AI-First Context: Enables proper provider instantiation for AI operations
- ✅ Proven Patterns: Uses match/case for clean factory pattern
- ✅ Evidence-Based: Design based on analysis of actual code flow
- ✅ Testing Philosophy: Comprehensive tests for critical functionality
- ✅ Simplicity: Clear factory pattern with minimal complexity

**Code Quality:**
- ✅ Type hints throughout
- ✅ Comprehensive docstrings
- ✅ Error handling and logging
- ✅ Follows existing code style
- ✅ Maintains backward compatibility

## Success Criteria

1. ✅ Providers can be instantiated without `TypeError`
2. ✅ Clients are created with user configuration
3. ✅ Authentication works from multiple sources
4. ✅ All existing tests pass
5. ✅ New tests achieve >90% coverage of factory code
6. ✅ Documentation is updated
7. ✅ No breaking changes to public API

## References

- Analysis: System Architect Agent Report
- Analysis: Backend Architect Settings Analysis
- Code: `src/codeweaver/common/registry/provider.py:617-664`
- Code: `src/codeweaver/config/providers.py`
- Constitution: `.specify/memory/constitution.md`
