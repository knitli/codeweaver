<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# CodeWeaver Dependency Injection (DI)

CodeWeaver uses a FastAPI-inspired dependency injection system to manage components, reduce circular dependencies, and improve testability.

## Core Components

### 1. `Container`
The `Container` is the central registry for dependencies. it handles:
- **Registration**: Mapping interfaces to factories or concrete classes.
- **Resolution**: Recursive resolution of dependencies using `Depends` markers.
- **Lifecycle**: Optional async startup and shutdown hooks.
- **Testing**: Clean override mechanism for injecting mocks.

### 2. `Depends` and `INJECTED`
A marker used in function signatures or `Annotated` type hints to declare a dependency.

```python
from typing import Annotated
from codeweaver.core.di import Depends, INJECTED
from codeweaver.core.di.providers import get_embedding_provider, EmbeddingDep
from codeweaver.providers import EmbeddingProvider

# Recommended: Type-safe INJECTED with subscript syntax
async def search(embedding: EmbeddingDep = INJECTED[EmbeddingProvider]):
    return await embedding.embed_query("...")

# Alternative: Explicit Depends marker
async def search(embedding: Annotated[EmbeddingProvider, Depends(get_embedding_provider)]):
    ...

# Legacy (still works but not recommended)
async def search(embedding: EmbeddingDep):
    return await embedding.embed_query("...")
```

The `INJECTED[Type]` syntax provides type safety while avoiding the need for `ty:ignore` comments. At runtime, it returns the sentinel that the DI container recognizes, but type checkers see it as the specified type.

### 3. `providers.py`
Contains standard factory functions that bridge the existing registry system with the DI container. These factories encapsulate the complexity of looking up settings and capabilities.

## Usage in Services

To make a service injectable, declare its dependencies in the `__init__` method using the type-safe `INJECTED[Type]` syntax.

```python
from codeweaver.core.di import INJECTED
from codeweaver.core.di.providers import IndexerDep
from codeweaver.engine import Indexer

class MyService:
    def __init__(self, indexer: IndexerDep = INJECTED[Indexer]):
        self.indexer = indexer
```

The `INJECTED[Indexer]` syntax tells type checkers that `indexer` will be of type `Indexer`, while the DI container recognizes the default value as an injection marker.

## Testing with Overrides

DI makes testing easy by allowing you to swap real providers for mocks without monkeypatching.

```python
@pytest.mark.asyncio
async def test_my_feature():
    container = get_container()
    container.override(EmbeddingProvider, MockEmbedding())
    
    service = await container.resolve(MyService)
    # ... test service ...
    
    container.clear_overrides()
```

## Tag-Based Provider Selection

The DI system supports registering multiple providers for the same type using tags. This enables scenarios like primary/backup providers.

### Registering Tagged Providers

```python
from codeweaver.core.di import dependency_provider

# Register primary provider
@dependency_provider(EmbeddingProvider, scope="singleton", tags=["primary"])
def create_primary_embedding() -> EmbeddingProvider:
    return VoyageEmbedding()

# Register backup provider
@dependency_provider(EmbeddingProvider, scope="singleton", tags=["backup"])
def create_backup_embedding() -> EmbeddingProvider:
    return FastEmbedding()
```

### Resolving by Tags

```python
# Direct resolution
container = get_container()
primary = await container.resolve(EmbeddingProvider, tags={"primary"})
backup = await container.resolve(EmbeddingProvider, tags={"backup"})

# Without tags, gets the last registered provider
default = await container.resolve(EmbeddingProvider)  # Gets backup
```

### Dependency Injection with Tags

```python
class SearchService:
    def __init__(
        self,
        primary: Annotated[EmbeddingProvider, Depends(tags={"primary"})] = INJECTED[EmbeddingProvider],
        backup: Annotated[EmbeddingProvider, Depends(tags={"backup"})] = INJECTED[EmbeddingProvider],
    ):
        self.primary = primary
        self.backup = backup

    def search(self, query: str):
        try:
            return self.primary.embed(query)
        except Exception:
            return self.backup.embed(query)
```

### Tag Matching Rules

- **Subset Matching**: When resolving with tags, the provider must have ALL specified tags (subset matching)
- **No Tags**: When resolving without tags, returns the last registered provider
- **Multiple Matches**: If multiple providers match the tags, returns the most recently registered one

## Architecture Principles

1. **Transport Agnostic**: The DI system does not depend on FastMCP or any specific server transport.
2. **Type Safe**: Full support for type hints and static analysis.
3. **Lazy**: Dependencies are only instantiated when first requested (for singletons).
4. **Tag-Based Selection**: Support for multiple providers per type differentiated by tags.
