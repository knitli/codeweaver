---
title: "Universal Extensibility: The DI System"
---

# Universal Extensibility: The DI System

> **TL;DR:** This module handles Universal Extensibility via Dependency Injection (DI). Use it when you need to register services or inject them into functions. It decouples implementation from usage, allowing you to swap providers with zero code changes.

CodeWeaver Alpha 6 uses a lightweight, FastAPI-inspired Dependency Injection (DI) system. This architecture makes the platform extremely extensible—you can swap an embedding provider, a vector store, or even core services by simply updating your configuration.

---

## Core Components

The DI system relies on three primary markers to manage services:

### 1. `@dependency_provider` (The Registration Decorator)
Use this decorator to register a factory function or a class as a provider for a specific type. By default, providers are **singletons** (one instance for the entire application lifetime).

```python
from codeweaver.core.di import dependency_provider

@dependency_provider(MyService, scope="singleton")
async def create_my_service() -> MyService:
    return MyService(api_key="secret")
```

### 2. `INJECTED` (The Type Sentinel)
The `INJECTED` sentinel serves as a default value for function parameters. It tells the DI container: "Don't use a literal value here; look up the correct provider based on the type hint."

```python
async def search_code(service: MyService = INJECTED) -> None:
    # 'service' is automatically populated by the DI container
    result = await service.search("query")
```

### 3. `Depends` (The Injection Marker)
For more complex scenarios, use the `Depends` marker within an `Annotated` type hint. This allows you to specify a specific factory or change the injection scope.

```python
from typing import Annotated
from codeweaver.core.di import Depends, INJECTED

async def advanced_search(
    service: Annotated[MyService, Depends(custom_factory)] = INJECTED
) -> None:
    ...
```

---

## Lifecycle Scopes

CodeWeaver manages objects based on their required lifetime:

| Scope | Description | Use Case |
| :--- | :--- | :--- |
| **`singleton`** | One instance per application lifetime. | Shared caches, database clients, settings. |
| **`request`** | One instance per search request or operation. | Telemetry trackers, request-specific state. |
| **`function`** | A new instance created for every call. | Temporary files, ephemeral workers. |

---

## Advanced Features

### Collection Registration
Sometimes a type needs multiple providers (for example, many different embedding models). Use `collection=True` to register a factory that returns a list of instances.

```python
@dependency_provider(Capability, scope="singleton", collection=True)
def get_all_capabilities() -> Sequence[Capability]:
    return [Capability("Search"), Capability("Rerank")]
```

### Automatic Local Fallback
The DI system handles resilience by allowing "backup" providers. If a primary cloud provider fails, the system automatically falls back to a locally registered provider (like FastEmbed or Sentence-Transformers) without interrupting the agent's workflow.

---

## Why This Matters

1.  **Zero-Code Provider Swapping:** Switch from OpenAI to Anthropic or Qdrant to Memory by changing a single line in `codeweaver.toml`.
2.  **Testability:** Inject mock services during testing without monkey-patching your codebase.
3.  **Predictability:** The DI system validates dependencies at startup, catching "Missing Provider" errors before they reach production.
