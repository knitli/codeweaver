# Phase 2.3: Provider Auto-Discovery Integration

## Summary

This document describes the implementation of Phase 2.3, which integrates provider auto-discovery into the Container initialization system. The enhanced `@provider` decorator now seamlessly integrates with the Container to automatically register providers without manual registration calls.

## Implementation Overview

### Key Components

1. **Provider Registry** (`di/utils.py`)
   - `_providers`: Global dict mapping types to factory functions
   - `_provider_metadata`: Global dict storing ProviderMetadata for each type
   - `@provider` decorator: Registers providers with metadata
   - Thread-safe registration via `_registry_lock`

2. **Container Auto-Discovery** (`di/container.py`)
   - `_load_providers()`: Loads providers from registry on first access
   - `_providers_loaded`: Flag to ensure loading happens only once
   - Integration with `resolve()`: Triggers loading on first resolve
   - Scope mapping: Converts metadata scope to singleton/request behavior

3. **Public API** (`di/__init__.py`)
   - Exported `provider` decorator
   - Exported provider utility functions
   - Maintained backward compatibility

## How It Works

### 1. Provider Registration

Developers use the `@provider` decorator to register providers:

```python
from codeweaver.di import provider

# Function provider with explicit type
@provider(DatabaseConnection, scope="singleton")
async def create_database() -> AsyncIterator[DatabaseConnection]:
    db = DatabaseConnection()
    await db.connect()
    yield db
    await db.disconnect()

# Class self-registration
@provider(scope="request")
class CacheService:
    def __init__(self):
        self.data = {}
```

### 2. Metadata Storage

The decorator stores two pieces of information:
- **Factory function**: The callable that creates instances
- **Metadata**: Scope, generator detection, optional module info

```python
_providers[DatabaseConnection] = create_database
_provider_metadata[DatabaseConnection] = ProviderMetadata(
    scope="singleton",
    is_generator=False,
    is_async_generator=True,
    module=None
)
```

### 3. Lazy Loading

When the container's `resolve()` method is first called:

1. Checks `_providers_loaded` flag
2. If `False`, calls `_load_providers()`
3. Loads all providers from the global registry
4. Maps metadata scope to container's singleton flag
5. Sets `_providers_loaded = True`

This ensures:
- All `@provider` decorators have been processed during module imports
- Loading happens only once per container instance
- Thread-safe operation

### 4. Scope Mapping

Provider metadata scope is mapped to container behavior:

| Metadata Scope | Container Behavior |
|----------------|-------------------|
| `"singleton"` | `singleton=True` (app lifetime cache) |
| `"request"` | `singleton=False` (request-scoped cache) |
| `"function"` | `singleton=False` (no caching) |

The container already has request-scoped caching via `_request_cache`, which is used when `Depends(scope="request")` is specified.

### 5. Generator Support

The container already supports async generators for cleanup:
- Detected via `inspect.isasyncgenfunction()`
- Wrapped in async context managers
- Cleanup happens via `AsyncExitStack` in `lifespan()` context

## Usage Examples

### Basic Usage

```python
from codeweaver.di import Container, provider

@provider(MyService, scope="singleton")
def create_service() -> MyService:
    return MyService()

# Auto-discovery happens on first resolve
container = Container()
service = await container.resolve(MyService)
```

### With Generators (Cleanup)

```python
@provider(DatabasePool, scope="singleton")
async def create_pool() -> AsyncIterator[DatabasePool]:
    pool = DatabasePool()
    await pool.connect()
    yield pool
    await pool.disconnect()

async with container.lifespan():
    pool = await container.resolve(DatabasePool)
    # Use pool...
# Pool disconnected automatically
```

### Request Scope

```python
@provider(RequestContext, scope="request")
def create_context() -> RequestContext:
    return RequestContext()

# Same instance within request
ctx1 = await container.resolve(RequestContext)
ctx2 = await container.resolve(RequestContext)
assert ctx1 is ctx2

# New instance after request cache clear
container.clear_request_cache()
ctx3 = await container.resolve(RequestContext)
assert ctx1 is not ctx3
```

## Benefits

### 1. Eliminates Dual Registration

**Before (Phase 2.2):**
```python
# providers.py
def setup_default_container(container: Container):
    # Register by class
    container.register(MyService, get_my_service)
    # ALSO register the function
    container.register(get_my_service, get_my_service)
```

**After (Phase 2.3):**
```python
# Just use the decorator
@provider(MyService, scope="singleton")
def get_my_service() -> MyService:
    return MyService()

# Container automatically discovers and registers
```

### 2. Declarative Configuration

Providers are self-describing with clear scope and lifecycle:
```python
@provider(CacheService, scope="singleton")  # Clear: app-level singleton
@provider(RequestContext, scope="request")  # Clear: per-request instance
@provider(TempFile, scope="function")       # Clear: new instance every time
```

### 3. Type-Safe Auto-Discovery

The type system knows about registered providers:
```python
# TypeChecker knows DatabaseConnection is provided
db: DatabaseConnection = await container.resolve(DatabaseConnection)
```

### 4. Generator Lifecycle Management

Cleanup is automatically detected and handled:
```python
@provider(ResourcePool, scope="singleton")
async def create_pool() -> AsyncIterator[ResourcePool]:
    # Setup
    yield pool
    # Cleanup - automatically called via AsyncExitStack
```

## Testing

### Unit Tests

Located in `tests/di/test_provider_autodiscovery.py`:

- `test_provider_decorator_registers_in_utils_registry`: Verifies decorator registration
- `test_container_loads_providers_on_first_resolve`: Verifies lazy loading
- `test_provider_scope_respected_by_container`: Verifies scope behavior
- `test_provider_metadata_stored_correctly`: Verifies metadata storage
- `test_provider_generator_detection`: Verifies async generator detection
- `test_container_clear_resets_provider_loading_flag`: Verifies cleanup
- `test_multiple_containers_each_load_providers`: Verifies isolation
- `test_provider_without_explicit_type`: Verifies class self-registration
- `test_container_loads_providers_only_once`: Verifies idempotency
- `test_provider_registration_is_thread_safe`: Verifies thread safety

## Backward Compatibility

The implementation maintains backward compatibility:

1. **Existing manual registration still works**:
   ```python
   container.register(MyService, factory_function)
   ```

2. **Legacy `setup_default_container()` still called**:
   ```python
   def get_container() -> Container:
       if _default_container is None:
           _default_container = Container()
           # Auto-discovery via lazy loading
           # Plus legacy registrations
           setup_default_container(_default_container)
       return _default_container
   ```

3. **All existing Depends() patterns work unchanged**:
   ```python
   async def my_func(service: Annotated[MyService, Depends()]) -> None:
       ...
   ```

## Future Work

### Phase 3 Improvements

1. **Replace dual registration pattern entirely**
   - Remove manual `container.register()` calls in `setup_default_container()`
   - Convert all factory functions to use `@provider` decorator

2. **Enhanced scope support**
   - Add `"transient"` scope for explicit no-caching
   - Add `"scoped"` for custom scope contexts

3. **Module-scoped providers**
   - Use `module` parameter for namespace isolation
   - Support plugin-based provider discovery

4. **Validation and diagnostics**
   - Detect missing providers at startup
   - Warn about circular dependencies
   - Provider dependency graph visualization

## Files Modified

1. `/src/codeweaver/di/container.py`:
   - Added `_providers_loaded` flag to `Container.__init__()`
   - Added `_load_providers()` method for auto-discovery
   - Modified `resolve()` to trigger lazy loading
   - Updated `clear()` to reset loading flag
   - Enhanced `get_container()` documentation

2. `/src/codeweaver/di/__init__.py`:
   - Added `provider` and utility function exports
   - Updated `_dynamic_imports` mapping
   - Updated `__all__` tuple

3. `/tests/di/test_provider_autodiscovery.py`:
   - New test suite for auto-discovery functionality

## Summary

Phase 2.3 successfully integrates provider auto-discovery with the Container system, providing:

- **Seamless integration**: Providers registered with `@provider` automatically available in Container
- **Lazy loading**: Providers loaded on first `resolve()` call, after all decorators processed
- **Scope support**: Metadata-driven singleton/request/function scope behavior
- **Generator support**: Automatic cleanup via async generators
- **Thread safety**: Lock-protected registry operations
- **Backward compatibility**: Existing manual registration patterns still work
- **Type safety**: Full type checking support for auto-discovered providers

The implementation eliminates the need for dual registration (class + function) and provides a cleaner, more declarative API for dependency injection configuration.
