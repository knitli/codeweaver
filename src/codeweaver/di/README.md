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

### 2. `Depends`
A marker used in function signatures or `Annotated` type hints to declare a dependency.

```python
from typing import Annotated
from codeweaver.di import Depends
from codeweaver.di.providers import get_embedding_provider, EmbeddingDep

# Usage in a function
async def search(embedding: EmbeddingDep):
    return await embedding.embed_query("...")

# Or explicitly
async def search(embedding: EmbeddingProvider = Depends(get_embedding_provider)):
    ...
```

### 3. `providers.py`
Contains standard factory functions that bridge the existing registry system with the DI container. These factories encapsulate the complexity of looking up settings and capabilities.

## Usage in Services

To make a service injectable, declare its dependencies in the `__init__` method using `Depends` or `Annotated` type hints.

```python
class MyService:
    def __init__(self, indexer: IndexerDep):
        self.indexer = indexer
```

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

## Architecture Principles

1. **Transport Agnostic**: The DI system does not depend on FastMCP or any specific server transport.
2. **Type Safe**: Full support for type hints and static analysis.
3. **Lazy**: Dependencies are only instantiated when first requested (for singletons).
