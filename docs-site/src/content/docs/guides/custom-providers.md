# Custom Providers

> **TL;DR:** This module handles the registration and implementation of custom providers via the Dependency Injection (DI) system. Use it when you need to integrate a niche embedding model or vector store. It saves development time by allowing you to extend CodeWeaver without modifying the core codebase.

The Dependency Injection (DI) architecture of CodeWeaver Alpha 6 makes it simple to add support for new providers. Whether you have a proprietary internal embedding API or want to experiment with a new vector database, you can plug your implementation into CodeWeaver with just a few classes.

---

## 1. Implement the Provider Class

To create a new embedding provider, you must subclass `EmbeddingProvider`. This class defines how CodeWeaver interacts with your model's SDK or API.

```python
from typing import Sequence, Any
from codeweaver.core import CodeChunk, Provider
from codeweaver.providers.embedding.providers import EmbeddingProvider

class MyCustomProvider(EmbeddingProvider[MyClient]):
    _provider = Provider("MY_CUSTOM_PROVIDER")

    def _initialize(self, **kwargs):
        # Setup your client or load your model
        self.client = MyClient(api_key=self.config.api_key)

    async def _embed_documents(self, documents: Sequence[CodeChunk], **kwargs) -> list[list[float]]:
        # Convert chunks to strings and send to your model
        texts = [chunk.content for chunk in documents]
        return await self.client.embed_batch(texts)

    async def _embed_query(self, query: Sequence[str], **kwargs) -> list[list[float]]:
        # Embed a single search query
        return await self.client.embed_query(query[0])

    @property
    def base_url(self) -> str | None:
        return "https://api.mycustomprovider.com"
```

---

## 2. Register Your Provider

Once your class is defined, register it with the CodeWeaver DI system using the `@dependency_provider` decorator. This allows CodeWeaver to discover and instantiate your provider at boot-time.

```python
from codeweaver.core.di import dependency_provider

@dependency_provider(MyCustomProvider, scope="singleton")
def create_my_custom_provider(
    config: MyConfig = INJECTED,
    registry: EmbeddingRegistry = INJECTED,
    cache: CacheManager = INJECTED,
) -> MyCustomProvider:
    return MyCustomProvider(
        client=MyClient(),
        config=config,
        registry=registry,
        cache_manager=cache
    )
```

---

## 3. Configuration

To use your new provider, simply update your `codeweaver.toml`. CodeWeaver will use the `provider` name to look up your registered class in the DI container.

```toml
[provider.embedding.0]
provider = "MY_CUSTOM_PROVIDER"
model_name = "my-special-model"
api_key = "${MY_SECRET_KEY}"
```

---

## Best Practices

### A. Use `INJECTED` and `Depends`
Always use the DI markers for dependencies like the `EmbeddingRegistry` and `CacheManager`. This ensures your provider participates in CodeWeaver's deduplication and resilience features automatically.

### B. Define Capabilities
For optimal search results, define an `EmbeddingModelCapabilities` object for your model. This tells CodeWeaver about the model's token limits and dimension sizes.

### C. Handle Errors Gracefully
Raise a `ProviderError` if your API fails. CodeWeaver will catch this and automatically attempt to use a local fallback provider (if enabled).

---

## Summary

Custom providers turn CodeWeaver into a truly universal context platform. By following the DI-driven patterns of Alpha 6, you can ensure your integrations are as robust and resilient as the built-in providers.
