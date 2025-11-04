# Provider Instantiation Lifecycle Analysis

**Date**: 2025-11-03
**Scope**: Embedding, Sparse Embedding, Vector Store, and Reranking Providers
**Purpose**: Trace complete "cradle to grave" lifecycle of provider instantiation

---

## Executive Summary

The CodeWeaver provider system follows a multi-stage initialization pattern:
1. **Settings Resolution** via pydantic-settings hierarchy
2. **Provider Selection** based on configured settings and availability
3. **Client Creation** through provider-specific factory logic
4. **Registry Management** for singleton instances and lifecycle

**Critical Gap Identified**: The actual client instantiation (creating voyageai.AsyncClient, qdrant_client.QdrantClient, etc.) is NOT clearly implemented in the current codebase. Provider classes expect clients to be passed to their `__init__`, but there's no visible code that creates these clients.

---

## 1. Settings Resolution Flow

### Configuration Hierarchy (Highest to Lowest Priority)

**Source**: `/home/knitli/codeweaver-mcp/src/codeweaver/config/settings.py:222-638`

```
1. init_settings          - Direct CodeWeaverSettings() constructor args
2. env_settings           - Environment variables (CODEWEAVER_*)
3. dotenv_settings        - .env files (.local.env, .env, .codeweaver.local.env, etc.)
4. config_files           - TOML/YAML/JSON files in order:
   - .codeweaver.local.{toml,yaml,yml,json}
   - .codeweaver.{toml,yaml,yml,json}
   - .codeweaver/codeweaver.local.{toml,yaml,yml,json}
   - .codeweaver/codeweaver.{toml,yaml,yml,json}
   - ~/.config/codeweaver/codeweaver.{toml,yaml,yml,json}
5. secrets_settings       - ~/.config/codeweaver/secrets/
6. cloud_secrets          - AWS Secrets Manager, Azure Key Vault, Google Secret Manager
```

### Settings Model Structure

**CodeWeaverSettings Structure**:
```python
class CodeWeaverSettings(BaseSettings):
    provider: ProviderSettings | Unset  # Top-level provider config
    # ... other settings
```

**ProviderSettings Structure** (`src/codeweaver/config/providers.py:467-516`):
```python
class ProviderSettings(BasedModel):
    data: tuple[DataProviderSettings, ...] | Unset
    embedding: tuple[EmbeddingProviderSettings, ...] | Unset
    sparse_embedding: tuple[SparseEmbeddingProviderSettings, ...] | Unset
    reranking: tuple[RerankingProviderSettings, ...] | Unset
    vector_store: tuple[VectorStoreProviderSettings, ...] | Unset
    agent: tuple[AgentProviderSettings, ...] | Unset
```

**Individual Provider Settings** (e.g., `EmbeddingProviderSettings:230-236`):
```python
class EmbeddingProviderSettings(BaseProviderSettings):
    model_settings: Required[EmbeddingModelSettings]
    provider_settings: NotRequired[ProviderSpecificSettings | None]
```

### Default Resolution Logic

**Location**: `src/codeweaver/config/providers.py:330-448`

Defaults are determined at module load time via:

```python
# Embedding defaults
_embedding_defaults = _get_default_embedding_settings()

DefaultEmbeddingProviderSettings = (
    EmbeddingProviderSettings(
        provider=_embedding_defaults.provider,
        enabled=_embedding_defaults.enabled,
        model_settings=EmbeddingModelSettings(model=_embedding_defaults.model),
    ),
)
```

**Default Selection Logic** (`_get_default_embedding_settings():330-367`):
- Check for installed libraries in order: `voyageai`, `cohere`, `fastembed_gpu`, `fastembed`, `sentence_transformers`
- Return first available with appropriate model:
  - VoyageAI → `voyage:voyage-code-3`
  - Cohere → `cohere:embed-english-v3.0`
  - Fastembed → `fastembed:BAAI/bge-small-en-v1.5`
  - Sentence Transformers → `sentence-transformers:ibm-granite/granite-embedding-small-english-r2`
- If none available → `Provider.NOT_SET` with `enabled=False`

**Settings Application** (`CodeWeaverSettings.model_post_init:347-399`):
```python
def model_post_init(self, __context: Any, /) -> None:
    # ... field resolution
    self.provider = (
        ProviderSettings.model_validate(AllDefaultProviderSettings)
        if isinstance(self.provider, Unset)
        else self.provider
    )
    # ... other defaults
```

---

## 2. Provider Selection Logic

### Registry Initialization

**Location**: `src/codeweaver/common/registry/provider.py:60-1211`

**Global Singleton**:
```python
class ProviderRegistry:
    _instance: ProviderRegistry | None = None

    @classmethod
    def get_instance(cls) -> ProviderRegistry:
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
```

**Provider Registration** (`__init__:141-171`):
The registry maintains separate dictionaries for:
- `_embedding_providers: MutableMapping[Provider, LazyImport | type[EmbeddingProvider]]`
- `_sparse_embedding_providers: MutableMapping[Provider, LazyImport | type[SparseEmbeddingProvider]]`
- `_vector_store_providers: MutableMapping[Provider, LazyImport | type[VectorStoreProvider]]`
- `_reranking_providers: MutableMapping[Provider, LazyImport | type[RerankingProvider]]`
- Instance caches for singletons: `_embedding_instances`, etc.

### Provider Selection Flow

**Step 1: Get Configured Provider Settings**

**Function**: `get_configured_provider_settings(provider_kind):1126-1183`

```python
def get_configured_provider_settings(
    self, provider_kind: LiteralKinds
) -> DictView[EmbeddingProviderSettings] | ...:
    # Delegates to utility functions
    if provider_kind == ProviderKind.EMBEDDING:
        return get_model_config("embedding")  # from utils
    # ... similar for other kinds
```

**Utility Function**: `get_model_config` (`src/codeweaver/common/registry/utils.py:122-175`):

```python
def get_model_config(kind: Literal[...]) -> DictView[...] | None:
    provider_settings = get_provider_settings()  # Gets from global settings
    match kind:
        case ProviderKind.EMBEDDING:
            return _get_embedding_config(provider_settings["embedding"])
```

**Helper**: `_get_embedding_config` (`utils.py:58-71`):

```python
def _get_embedding_config(
    embedding_settings: tuple[EmbeddingProviderSettings, ...]
) -> DictView[EmbeddingProviderSettings] | None:
    return next(
        (
            DictView(setting)
            for setting in embedding_settings
            if setting.get("model_settings") and setting.get("enabled")
        ),
        None,
    )
```

**Step 2: Get Provider Enum**

**Function**: `get_provider_enum_for(kind):1191-1202`

```python
def get_provider_enum_for(self, kind: LiteralKinds) -> Provider | tuple[Provider, ...] | None:
    if config := self.get_configured_provider_settings(kind):
        return config["provider"]  # Extracts Provider enum from settings
    return None
```

**Usage Example** (`src/codeweaver/engine/indexer.py:62-71`):

```python
def _get_embedding_instance(*, sparse: bool = False) -> EmbeddingProvider[Any] | None:
    kind = "sparse_embedding" if sparse else "embedding"
    registry = get_provider_registry()

    if provider_enum := registry.get_provider_enum_for(kind):
        return registry.get_provider_instance(provider_enum, kind, singleton=True)
    return None
```

---

## 3. Provider Instance Creation

### The Missing Piece: Client Instantiation

**CRITICAL GAP**: The codebase shows providers expecting clients in their constructors but doesn't show WHERE clients are created.

**Provider Constructor Signature** (`EmbeddingProvider.__init__:170-197`):

```python
def __init__(
    self,
    client: EmbeddingClient,  # ← Client is EXPECTED, not created
    caps: EmbeddingModelCapabilities,
    kwargs: dict[str, Any] | None,
) -> None:
    self._client = client  # Just stores the client
    # ... initialization
```

**Example Provider** (`VoyageEmbeddingProvider:48-120`):

```python
class VoyageEmbeddingProvider(EmbeddingProvider[AsyncClient]):
    _client: AsyncClient  # Expects voyageai.AsyncClient
    # No __init__ override - uses base class
    # Base class expects client to be passed in
```

### Registry Instance Creation Flow

**Entry Point**: `get_provider_instance(provider, provider_kind, singleton=False, **kwargs):744-802`

```python
def get_provider_instance(
    self,
    provider: Provider,
    provider_kind: LiteralKinds,
    *,
    singleton: bool = False,
    **kwargs: Any,
) -> EmbeddingProvider[Any] | ...:
    # 1. Check singleton cache
    instance_cache = self._get_instance_cache_for_kind(provider_kind)
    if singleton and provider in instance_cache:
        return instance_cache[provider]

    # 2. Get configuration
    config = self.get_configured_provider_settings(provider_kind)

    # 3. Prepare constructor kwargs from config
    constructor_kwargs = self._prepare_constructor_kwargs(provider_kind, config, **kwargs)

    # 4. Create instance
    instance = self.create_provider(provider, provider_kind, **constructor_kwargs)

    # 5. Cache if singleton
    if singleton:
        instance_cache[provider] = instance

    return instance
```

### Constructor Kwargs Preparation

**Function**: `_prepare_constructor_kwargs:830-861`

```python
def _prepare_constructor_kwargs(
    self,
    provider_kind: LiteralKinds,
    config: DictView[...] | None,
    **user_kwargs: Any,
) -> dict[str, Any]:
    if self._is_literal_model_kind(provider_kind):
        return self._prepare_model_provider_kwargs(config, **user_kwargs)
    # ... other kinds
```

**Model Provider Kwargs**: `_prepare_model_provider_kwargs:863-896`

```python
def _prepare_model_provider_kwargs(
    self,
    config: DictView[EmbeddingProviderSettings] | ...,
    **user_kwargs: Any,
) -> dict[str, Any]:
    if not config:
        return user_kwargs

    kwargs: dict[str, Any] = {}

    # Extract model settings
    self._add_model_settings_to_kwargs(config, kwargs, user_kwargs)

    # Extract provider settings and merge into client_options
    self._add_provider_settings_to_kwargs(config, kwargs)

    # User kwargs override everything
    kwargs |= user_kwargs
    return kwargs
```

**Add Model Settings**: `_add_model_settings_to_kwargs:898-914`

```python
def _add_model_settings_to_kwargs(
    self, config: DictView[Any], kwargs: dict[str, Any], user_kwargs: dict[str, Any]
) -> None:
    model_settings = config.get("model_settings")
    if not model_settings:
        return

    # Get capabilities for the model
    if (model_name := user_kwargs.get("model") or model_settings.get("model")) and (
        caps := self._get_capabilities_for_model(model_name, config["provider"])
    ):
        kwargs["caps"] = caps

    # Add model-specific settings
    for key in ("dimension", "data_type", "custom_prompt", "embed_options", "model_options"):
        if value := model_settings.get(key):
            kwargs[key] = value
```

**Add Provider Settings**: `_add_provider_settings_to_kwargs:916-948`

```python
def _add_provider_settings_to_kwargs(
    self, config: DictView[Any], kwargs: dict[str, Any]
) -> None:
    provider_settings = config.get("provider_settings")
    if not provider_settings:
        return

    client_options = kwargs.get("client_options", {})

    # AWS settings (Bedrock)
    for key in ("region_name", "model_arn", "aws_access_key_id", ...):
        if value := provider_settings.get(key):
            client_options[key] = value

    # Azure settings
    for key in ("model_deployment", "api_key", "azure_resource_name"):
        if value := provider_settings.get(key):
            client_options[key] = value

    # ... other provider-specific settings

    if client_options:
        kwargs["client_options"] = client_options
```

### The Actual Provider Creation

**Function**: `create_provider(provider, provider_kind, **kwargs):618-665`

```python
def create_provider(
    self, provider: Provider, provider_kind: LiteralKinds, **kwargs: Any
) -> EmbeddingProvider[Any] | ...:
    # 1. Get provider class
    retrieved_cls = None
    if self._is_literal_model_kind(provider_kind):
        retrieved_cls = self.get_provider_class(provider, provider_kind)
    # ... handle other kinds

    # 2. Special handling for embedding providers
    if provider_kind in (ProviderKind.EMBEDDING, "embedding"):
        # Check if this is an OpenAI factory that needs construction
        if self._is_openai_factory(retrieved_cls):
            retrieved_cls = self._construct_openai_provider_class(
                provider, retrieved_cls, **kwargs
            )

        # Verify the class can be imported
        name = None
        with contextlib.suppress(Exception):
            name = retrieved_cls.__name__
        if not name:
            raise ConfigurationError(f"Embedding provider '{provider}' could not be imported.")

        # ❌ PROBLEM: This calls the provider constructor
        # but kwargs doesn't contain a 'client' - where does it come from?
        return cast(EmbeddingProvider[Any], retrieved_cls(**kwargs))

    # Standard handling for other providers
    if isinstance(retrieved_cls, LazyImport):
        return self._create_provider(provider, retrieved_cls, **kwargs)
    return retrieved_cls(**kwargs)
```

**Helper**: `_create_provider:667-685`

```python
def _create_provider(
    self, provider: Provider, importer: LazyImport[type[Any]], **kwargs: Any
) -> Any:
    resolved = None
    try:
        resolved = importer._resolve()
    except Exception as e:
        raise ConfigurationError(f"Provider '{provider}' could not be imported.") from e

    # ❌ PROBLEM: Same issue - where's the client?
    return resolved(**kwargs)
```

---

## 4. Current vs Expected Flow

### EXPECTED Flow (Based on Architecture)

```
1. Settings Resolution
   ├─ Config files loaded via pydantic-settings
   ├─ Environment variables override
   └─ Defaults applied for unset values

2. Provider Selection
   ├─ Registry.get_provider_enum_for(kind)
   ├─ Reads from resolved settings
   └─ Returns configured Provider enum

3. Client Creation ← ❌ MISSING
   ├─ Should read provider_settings.client_options
   ├─ Should create voyageai.AsyncClient(**client_options)
   ├─ Should create qdrant_client.QdrantClient(**client_options)
   └─ Should handle auth, base URLs, etc.

4. Provider Instantiation
   ├─ Registry.get_provider_instance(provider_enum, kind, **kwargs)
   ├─ Calls create_provider with prepared kwargs
   ├─ kwargs should include: client, caps, custom settings
   └─ Provider.__init__(client, caps, kwargs)

5. Singleton Caching
   └─ Registry stores instance in _embedding_instances, etc.
```

### ACTUAL Flow (Based on Code)

```
1. Settings Resolution ✅ WORKING
   └─ pydantic-settings correctly loads and merges config

2. Provider Selection ✅ WORKING
   └─ Registry correctly identifies provider from settings

3. Kwargs Preparation ⚠️ PARTIAL
   ├─ Correctly extracts caps, model settings
   ├─ Correctly creates client_options dict
   └─ ❌ Never converts client_options → actual client

4. Provider Instantiation ❌ BROKEN
   ├─ retrieved_cls(**kwargs) called
   ├─ kwargs contains: {caps, dimension, client_options, ...}
   ├─ kwargs MISSING: client (required param)
   └─ Provider.__init__ expects (client, caps, kwargs)

5. Expected Failure Point
   └─ TypeError: missing required argument 'client'
```

---

## 5. The Missing Client Factory

### What SHOULD Exist But Doesn't

**Expected Location**: Somewhere between `_prepare_constructor_kwargs` and `create_provider`

**Expected Logic**:

```python
def _create_client_for_provider(
    self,
    provider: Provider,
    provider_kind: ProviderKind,
    client_options: dict[str, Any]
) -> Any:
    """Create the actual client instance for a provider."""

    match provider:
        case Provider.VOYAGE:
            from voyageai import AsyncClient
            api_key = client_options.get("api_key") or os.getenv("VOYAGE_API_KEY")
            return AsyncClient(api_key=api_key, **client_options)

        case Provider.COHERE:
            from cohere import AsyncClient
            api_key = client_options.get("api_key") or os.getenv("COHERE_API_KEY")
            return AsyncClient(api_key=api_key, **client_options)

        case Provider.OPENAI | Provider.FIREWORKS | Provider.GROQ | ...:
            from openai import AsyncOpenAI
            api_key = client_options.get("api_key") or os.getenv(f"{provider}_API_KEY")
            base_url = client_options.get("base_url") or self._get_base_url_for_provider(provider)
            return AsyncOpenAI(api_key=api_key, base_url=base_url, **client_options)

        case Provider.BEDROCK:
            import boto3
            return boto3.client("bedrock-runtime", **client_options)

        case Provider.QDRANT:
            from qdrant_client import QdrantClient
            url = client_options.get("url") or os.getenv("QDRANT_URL")
            api_key = client_options.get("api_key") or os.getenv("QDRANT_API_KEY")
            return QdrantClient(url=url, api_key=api_key, **client_options)

        case Provider.FASTEMBED | Provider.SENTENCE_TRANSFORMERS:
            # Local providers don't need external clients
            return None

        case _:
            raise ConfigurationError(f"Unknown provider: {provider}")
```

### Where This Should Be Called

**Modified** `create_provider`:

```python
def create_provider(
    self, provider: Provider, provider_kind: LiteralKinds, **kwargs: Any
) -> EmbeddingProvider[Any] | ...:
    # ... existing class retrieval logic

    # ✅ ADD: Create client if not provided
    if "client" not in kwargs and provider_kind in model_kinds:
        client_options = kwargs.pop("client_options", {})
        client = self._create_client_for_provider(
            provider, provider_kind, client_options
        )
        if client is not None:
            kwargs["client"] = client

    # Now kwargs has all required parameters
    return cast(EmbeddingProvider[Any], retrieved_cls(**kwargs))
```

---

## 6. Code Locations Requiring Changes

### Primary Changes Needed

**File**: `src/codeweaver/common/registry/provider.py`

**Location 1**: Add client factory method (~line 468, after `_get_base_url_for_provider`)

```python
def _create_client_for_provider(
    self,
    provider: Provider,
    provider_kind: ProviderKind,
    client_options: dict[str, Any]
) -> Any:
    """Create the actual client instance for a provider.

    Args:
        provider: The provider enum
        provider_kind: Type of provider (embedding, reranking, etc.)
        client_options: Provider-specific client options

    Returns:
        Initialized client instance or None for local providers
    """
    # Implementation as shown above
```

**Location 2**: Modify `create_provider` method (~line 618)

```python
def create_provider(...) -> ...:
    # ... existing code up to kwargs preparation

    # NEW: Create client if needed
    if "client" not in kwargs:
        if self._is_literal_model_kind(provider_kind):
            client_options = kwargs.pop("client_options", {})
            if client := self._create_client_for_provider(
                provider, provider_kind, client_options
            ):
                kwargs["client"] = client
        elif self._is_literal_vector_store_kind(provider_kind):
            # Vector stores also need clients
            config = kwargs.get("config", {})
            if client := self._create_vector_store_client(provider, config):
                kwargs["client"] = client

    # ... existing instantiation code
```

**Location 3**: Add vector store client factory (~line 500)

```python
def _create_vector_store_client(
    self,
    provider: Provider,
    config: dict[str, Any]
) -> Any:
    """Create vector store client instance."""
    match provider:
        case Provider.QDRANT:
            from qdrant_client import QdrantClient
            # Extract from QdrantConfig
            # ...
        case Provider.MEMORY:
            # In-memory doesn't need external client
            return None
```

### Secondary Changes (Better Encapsulation)

**File**: `src/codeweaver/providers/embedding/providers/base.py`

**Consideration**: Make `client` parameter optional and add factory logic

```python
def __init__(
    self,
    client: EmbeddingClient | None = None,  # Make optional
    caps: EmbeddingModelCapabilities | None = None,
    kwargs: dict[str, Any] | None = None,
) -> None:
    """Initialize the embedding provider.

    If client is not provided, it will be created using client_options from kwargs.
    """
    if client is None:
        # Factory logic here - could delegate to registry
        client = self._create_default_client(kwargs)

    self._client = client
    # ... rest of init
```

---

## 7. Testing the Flow

### Verification Steps

**Step 1**: Settings are resolved correctly
```python
from codeweaver.config import get_settings

settings = get_settings()
assert settings.provider.embedding is not Unset
assert settings.provider.embedding[0].provider == Provider.VOYAGE  # or expected default
```

**Step 2**: Provider selection works
```python
from codeweaver.common.registry import get_provider_registry

registry = get_provider_registry()
provider_enum = registry.get_provider_enum_for("embedding")
assert provider_enum is not None
```

**Step 3**: Client creation (CURRENTLY FAILS)
```python
# This should work after implementing client factory
provider_instance = registry.get_provider_instance(
    provider_enum, "embedding", singleton=True
)
assert provider_instance.client is not None
assert isinstance(provider_instance, EmbeddingProvider)
```

**Step 4**: End-to-end usage
```python
from codeweaver.engine.indexer import _get_embedding_instance

embedding_provider = _get_embedding_instance()
assert embedding_provider is not None

# Should be able to embed
result = await embedding_provider.embed_query(["test query"])
assert len(result) == 1
assert len(result[0]) > 0  # Has embeddings
```

---

## 8. Additional Observations

### Environment Variable Handling

**Gap**: Client options that come from provider_settings need to fall back to environment variables

**Example**: VoyageAI API key resolution
```python
# Current (in client factory):
api_key = client_options.get("api_key")  # Only checks config

# Should be:
api_key = (
    client_options.get("api_key")
    or os.getenv("VOYAGE_API_KEY")
    or os.getenv("CODEWEAVER_PROVIDER__EMBEDDING__PROVIDER_SETTINGS__API_KEY")
)
```

### Provider-Specific Configuration

**OpenAI-Compatible Providers** (Fireworks, Groq, GitHub, Ollama, etc.):
- All use `openai.AsyncOpenAI`
- Differ only in `base_url` and API key env var name
- Already has `_get_base_url_for_provider` helper (line 449)

**Bedrock Providers**:
- Need boto3 client with region and credentials
- Config in `AWSProviderSettings` (line 160)

**Azure Providers**:
- Two types: Azure OpenAI and Azure Cohere
- Config in `AzureOpenAIProviderSettings` and `AzureCohereProviderSettings`

**Local Providers** (Fastembed, Sentence Transformers):
- Don't need external HTTP clients
- May need path configs (cache_dir, model_path)

### Singleton Management

**Current Implementation** (line 744-802):
- Correctly implements singleton pattern
- Caches in `_embedding_instances`, `_sparse_embedding_instances`, etc.
- `singleton=True` flag controls caching

**Usage Pattern**:
```python
# Always request singleton for providers to avoid recreating expensive clients
embedding_provider = registry.get_provider_instance(
    Provider.VOYAGE,
    "embedding",
    singleton=True  # ← Important
)
```

---

## 9. Summary and Recommendations

### Critical Issues

1. **Missing Client Factory** ⚠️ HIGH PRIORITY
   - No code exists to create actual client instances
   - Provider constructors expect clients but don't receive them
   - Would cause immediate runtime failures

2. **Incomplete client_options Handling** ⚠️ MEDIUM PRIORITY
   - Config extracts client_options but doesn't use them
   - No fallback to environment variables for missing keys

3. **OpenAI Factory Gap** ⚠️ MEDIUM PRIORITY
   - `_construct_openai_provider_class` exists but may not handle client creation
   - Need to verify this creates clients or just classes

### Implementation Roadmap

**Phase 1: Core Client Factory** (Blocking)
1. Implement `_create_client_for_provider` in ProviderRegistry
2. Integrate into `create_provider` method
3. Test with VoyageAI (most common case)

**Phase 2: Comprehensive Provider Support** (Important)
1. Add client factories for all embedding providers
2. Add vector store client factories
3. Add reranking provider clients

**Phase 3: Configuration Robustness** (Enhancement)
1. Improve env var fallback logic
2. Add validation for required client options
3. Better error messages for missing config

**Phase 4: Testing & Documentation** (Quality)
1. Unit tests for each provider's client creation
2. Integration tests for full flow
3. Document client_options format for each provider

### Architecture Alignment

**Strengths** ✅:
- pydantic-settings integration is clean and correct
- Registry pattern with singletons is well-designed
- Provider abstraction is solid
- Settings hierarchy is comprehensive

**Weaknesses** ❌:
- Client creation is completely missing
- Dependency on implicit behavior (providers should create own clients?)
- Unclear separation of concerns (who creates clients?)

**Recommended Pattern**:
```
Settings → Registry → Client Factory → Provider Constructor
         ↓          ↓                ↓
    Config Dict → client_options → AsyncClient(**options)
```

This maintains the "proven patterns" principle from the Constitution while filling the critical gap in the current implementation.

---

## Appendix: Key File Locations

| Component | File | Lines |
|-----------|------|-------|
| Main Settings | `src/codeweaver/config/settings.py` | 222-638 |
| Provider Settings | `src/codeweaver/config/providers.py` | 467-516 |
| Provider Defaults | `src/codeweaver/config/providers.py` | 330-448 |
| Provider Registry | `src/codeweaver/common/registry/provider.py` | 60-1211 |
| Registry Utils | `src/codeweaver/common/registry/utils.py` | 58-175 |
| Base Provider | `src/codeweaver/providers/embedding/providers/base.py` | 119-711 |
| Voyage Provider | `src/codeweaver/providers/embedding/providers/voyage.py` | 48-120 |
| Indexer Usage | `src/codeweaver/engine/indexer.py` | 62-71 |
| Pipeline Usage | `src/codeweaver/agent_api/find_code/pipeline.py` | 69-197 |
| Server Lifecycle | `src/codeweaver/server/server.py` | 319-379 |

---

**Document Version**: 1.0
**Last Updated**: 2025-11-03
**Reviewed By**: System Architect Analysis
