<!--
SPDX-FileCopyrightText: 2026 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Detailed Refactoring Plan for `codeweaver.server`

This document outlines the step-by-step plan to refactor the server package (`src/codeweaver/server/`) to align with the new Dependency Injection (DI) architecture, `pydantic-settings` configuration system, and the updated engine services pattern.

## 1. Context & Architecture

**Goal:** Eliminate the `_state` global singleton and the Service Locator pattern (`get_state()`). Move to a pure Dependency Injection model where the Server, Management API, and Background Services are composed via `src/codeweaver/server/dependencies.py`.

### Key Issues to Resolve (Code Smells)
*   **Global State/Singleton Abuse:** `server.py` maintains a global `_state` variable accessed via `get_state()`. This makes testing difficult and hides dependencies.
*   **Tight Coupling:** `ManagementServer` and `HealthService` are manually instantiated in `lifespan` and tightly coupled to the monolithic `CodeWeaverState`.
*   **Implicit Dependencies:** Route handlers in `management.py` (e.g., `health`, `status`) import `get_state` inside the function body, making dependencies invisible.
*   **Initialization Scatter:** Logic for wiring services is spread across `lifespan`, `server.py`, and `background_services.py`.

### Target Architecture
*   **Configuration:** `CodeWeaverSettings` provided via `SettingsDep`.
*   **Services:** `IndexingService`, `FailoverService`, `HealthService` are singletons injected into consumers.
*   **State:** `CodeWeaverState` becomes a dumb DTO (Data Transfer Object) or Facade that is *injected*, not accessed globally.
*   **Wiring:** All construction logic moves to `src/codeweaver/server/dependencies.py`.

---

## 2. Refactoring Plan

### Phase 1: Dependency Injection Wiring (`server/dependencies.py`)

**Goal:** Create the factories necessary to instantiate server components without manual wiring.

**Action:** Create `src/codeweaver/server/dependencies.py`.

```python
# src/codeweaver/server/dependencies.py (Draft)
from codeweaver.core import dependency_provider, depends, INJECTED, SettingsDep
from codeweaver.engine.dependencies import (
    IndexingServiceDep, FailoverServiceDep, IndexingStatsDep, 
    FileWatchingServiceDep, CheckpointManagerDep
)
from codeweaver.server.health.health_service import HealthService
from codeweaver.server.management import ManagementServer
from codeweaver.server.server import CodeWeaverState

@dependency_provider(HealthService, scope="singleton")
def _create_health_service(
    indexer: IndexingServiceDep = INJECTED,
    failover: FailoverServiceDep = INJECTED,
    settings: SettingsDep = INJECTED,
    # ... other deps
) -> HealthService:
    return HealthService(indexer=indexer, failover=failover, settings=settings)

@dependency_provider(CodeWeaverState, scope="singleton")
def _create_server_state(
    settings: SettingsDep = INJECTED,
    indexer: IndexingServiceDep = INJECTED,
    health: HealthServiceDep = INJECTED,
    failover: FailoverServiceDep = INJECTED,
    # ... inject everything that currently lives in state
) -> CodeWeaverState:
    # This replaces the manual construction in lifespan
    return CodeWeaverState(
        settings=settings,
        indexer=indexer,
        health_service=health,
        failover_manager=failover,
        # ...
    )

# Type aliases
type HealthServiceDep = Annotated[HealthService, depends(_create_health_service, scope="singleton")]
type CodeWeaverStateDep = Annotated[CodeWeaverState, depends(_create_server_state, scope="singleton")]
```

### Phase 2: Refactor `HealthService`

**Goal:** Decouple `HealthService` from `CodeWeaverState`.

*   **Refactoring:** Dependency Inversion.
*   **Before:** `HealthService` accepts `CodeWeaverState` or uses `get_state()`.
*   **After:** `HealthService.__init__` accepts specific services (`IndexingService`, `VectorStoreProvider`, etc.).

**Steps:**
1.  Modify `src/codeweaver/server/health/health_service.py`:
    *   Update `__init__` to accept `IndexingService`, `FailoverService`, etc.
    *   Remove any imports of `get_state`.
    *   Update `get_health_response` to use `self.indexer`, `self.failover` directly.

### Phase 3: Refactor `ManagementServer` & Endpoints

**Goal:** Remove `get_state()` from HTTP endpoints.

*   **Problem:** Starlette functional endpoints (`def health(_request): ...`) are hard to inject into if they rely on globals.
*   **Refactoring:** Use a Factory Pattern for the App, or convert endpoints to a class-based view or closure-based structure where dependencies are captured.

**Steps:**
1.  **Refactor `management.py`:**
    *   Instead of standalone functions accessing globals, consider binding them during app creation or using the `CodeWeaverStateDep` injection if we keep the state object as the holder.
    *   *Alternative (Recommended):* Keep `CodeWeaverState` as the injected "Context" for the Starlette app.
    *   Update `state_info`, `health`, `status_info` to retrieve state from `request.app.state.background` (which is already set in `create_app` but currently populated from `__init__`).
    *   Ensure `ManagementServer` is initialized via DI (Phase 1) so it receives the fully populated `CodeWeaverState`.

```python
# src/codeweaver/server/management.py

# CHANGE: Don't import get_state inside functions.
@timed_http("health")
async def health(request: Request) -> PlainTextResponse:
    # Retrieve the state from the app context, which was injected at startup
    state: CodeWeaverState = request.app.state.background
    if not state.health_service:
        # handle error...
    return await state.health_service.get_health_response()
```

2.  **Update `ManagementServer` class:**
    *   Ensure it receives `CodeWeaverState` (injected) in `__init__`.

### Phase 4: Clean up `server.py` and `lifespan`

**Goal:** The `lifespan` function should be a simple "Resolve and Run" sequence.

*   **Code Smell:** Long Method (current `lifespan` does configuration, instantiation, logic, error handling).
*   **Refactoring:** Extract Method / Move Logic to Factory.

**Steps:**
1.  **Remove Global `_state`:** Delete `_state` variable and `get_state()` function from `server.py`.
2.  **Update `lifespan`:**

```python
@asynccontextmanager
async def lifespan(app: Any, ...) -> AsyncIterator[CodeWeaverState]:
    container = get_container()
    
    # 1. Resolve the entire state graph
    # This triggers the factories in dependencies.py, creating Indexer, HealthService, etc.
    state = await container.resolve(CodeWeaverState)
    state.initialized = True
    
    # 2. Start Background Tasks
    # (Ideally, these services should have .start() methods we call here)
    indexing_task = asyncio.create_task(run_background_indexing(state, ...))
    
    yield state
    
    # 3. Cleanup
    await _cleanup_state(state, indexing_task, ...)
```

3.  **Update `background_services.py`:**
    *   Refactor `run_background_indexing` to accept `FileWatchingService` directly instead of resolving it manually or constructing it.

### Phase 5: Verification & Testing

**Tests to Write/Update:**
1.  **DI Resolution Test:** Create a test that simply tries to `await container.resolve(CodeWeaverState)` and asserts that the resulting object has all fields populated (Indexer, HealthService, etc.) and they are not None.
2.  **Management API Test:** Test `/health` and `/status` endpoints ensuring they return 200 OK without relying on the global `_state` variable (mock the app state injection).

## 3. Safe Refactoring Sequence

1.  **Create `server/dependencies.py`**: Start by defining the factories. This is additive and safe.
2.  **Update `CodeWeaverState`**: Add `scope="singleton"` and ensure it can be constructed with all fields passed in.
3.  **Update `HealthService`**: Change signature to accept dependencies. Update `server/dependencies.py` to match.
4.  **Update `ManagementServer` endpoints**: Switch from `get_state()` to `request.app.state.background`.
5.  **Switch `lifespan`**: Cut over to using `container.resolve(CodeWeaverState)`.
6.  **Delete `_state`**: Remove the global variable and accessor. Fix any lingering compilation errors.

## 4. Design Patterns Applied
*   **Dependency Injection:** Replacing manual composition.
*   **Singleton Pattern (Managed):** Using DI container scope instead of module-level globals.
*   **Facade Pattern:** `CodeWeaverState` acts as a simplified facade over complex subsystems (`IndexingService`, `FailoverService`) for the API layer.