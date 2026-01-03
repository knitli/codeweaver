Excellent! I've updated the plan to emphasize leveraging pydantic's mature internal utilities for type resolution. The plan now includes:

  Key Updates:

  1. Pydantic Utilities Integration 🎯
    - Use pydantic._internal._typing_extra for type detection (is_annotated, is_union_origin, is_none_type, etc.)
    - Use get_function_type_hints() for robust type hint extraction (handles PEP 563, forward refs, Python 3.13+)
    - Use get_type_ref() for stable cache keys (better than id())
    - Use lenient_isinstance/issubclass for safe type checks
  2. All FastAPI Edge Cases Covered:
    - ✅ Circular dependency detection
    - ✅ Generator/context manager deps
    - ✅ Union type handling
    - ✅ Scope lifecycle (singleton/request/function)
    - ✅ Error aggregation
    - ✅ use_cache flag implementation
    - ✅ Improved type resolution
  3. Clean @provider API - Eliminates manual getter imports

  The plan is comprehensive, implementable, and leverages battle-tested utilities instead of reinventing the wheel!

────────────────────────────────────────────────────────────────
 Ready to code?

 Here is Claude's plan:
╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌╌
 Phase 3 DI System Overhaul: API & Container Improvements

 Executive Summary

 Comprehensive redesign of CodeWeaver's dependency injection
 system for Phase 3, incorporating:
 1. Clean @provider decorator API - eliminate manual getter
 imports
 2. Robust type resolution - handle FastAPI-level edge cases
 3. Leverage pydantic._internal utilities - battle-tested type
 resolution instead of rolling our own
 4. Lifecycle management - scopes, generator deps, cleanup
 5. Production-ready validation - circular deps, error
 aggregation, cache management

 Key Innovation: Instead of reimplementing type resolution,
 leverage pydantic's mature utilities from
 pydantic._internal._typing_extra, _core_utils, and _utils.
 These are battle-tested by millions of users and handle all
 Python typing edge cases (PEP 563, forward refs, Python 3.13+,
  unions, etc.).

 Scope: Major breaking changes acceptable (Phase 3 refactor
 timing)

 ---
 Part 1: API Improvements - Clean Provider Registration

 Current Pain Points

 - Manual import of ~20 getters into di/providers.py
 - Dual registration (by class AND by function) causes
 confusion
 - Registry dependency (now deleted) needs replacement
 - No clear pattern for where providers live

 Proposed API Pattern

 # In the module where ServiceProvider lives (e.g., 
 engine/some_service.py)
 from codeweaver.di import provider

 @provider(ServiceProvider)  # Register for this type
 async def get_service_provider(
     settings: SettingsDep = INJECTED[CodeWeaverSettings],
 ) -> ServiceProvider:
     """Create and configure the service provider."""
     return ServiceProvider(settings=settings)

 # Alternatively, for simple cases:
 @provider(SimpleService)  # Auto-registers the class itself
 class SimpleService:
     def __init__(self, config: Config):
         self.config = config

 Type Alias Creation (Auto-Generated)

 # Instead of manually creating in di/providers.py, 
 auto-generate from @provider:
 from codeweaver.di import create_type_alias

 # This reads from the provider registry and creates:
 ServiceDep = Annotated[ServiceProvider,
 Depends(get_service_provider)]

 # Or even better - make it automatic via __getattr__:
 from codeweaver.di import deps

 def my_func(service: deps.ServiceProvider = 
 INJECTED[ServiceProvider]):
     # deps.ServiceProvider auto-resolves to the right 
 Annotated type
     pass

 Implementation Tasks

 File: src/codeweaver/di/utils.py (ENHANCE)
 - ✅ Already has basic @provider decorator
 - Add module parameter handling for scoped registration
 - Add support for @provider on classes (auto-registers
 __init__)
 - Add lifecycle hints: @provider(Service, scope="request"),
 @provider(Service, cleanup=True)
 - Thread-safe registration with _registry_lock

 File: src/codeweaver/di/container.py (INTEGRATE)
 - Auto-discover providers from di.utils._providers registry
 - Remove dual registration pattern (class + function)
 - Load providers lazily on first get_container() call

 File: src/codeweaver/di/__init__.py (NEW EXPORTS)
 - Export provider decorator
 - Create deps namespace for auto-generated type aliases
 - Add __getattr__ magic for deps.ServiceName →
 Annotated[Service, Depends(...)]

 File: src/codeweaver/di/providers.py (SIMPLIFY)
 - Delete manual getter imports
 - Keep only type alias definitions (or deprecate entirely)
 - Migration path: existing code continues to work, but new
 code uses @provider

 ---
 Part 2: Container Resolution - Typing Edge Cases

 Gap Analysis: FastAPI vs CodeWeaver

 | Feature                        | FastAPI
 | CodeWeaver             | Priority    |
 |--------------------------------|----------------------------
 |------------------------|-------------|
 | Circular dependency detection  | ✅ visited tracking
 | ❌                     | 🔴 CRITICAL |
 | Generator/context manager deps | ✅ is_gen_callable
 | ❌                     | 🟡 HIGH     |
 | Union type handling            | ✅ is_union_of_base_models
 | ❌                     | 🟢 MEDIUM   |
 | Optional/None handling         | ✅ Extensive
 | ❌                     | 🟢 MEDIUM   |
 | Scope validation               | ✅ Function/request scopes
 | ❌                     | 🟡 HIGH     |
 | Error aggregation              | ✅ Collects all errors
 | ❌ Fails fast          | 🟡 HIGH     |
 | Cache key management           | ✅ Smart deduplication
 | ❌                     | 🟢 MEDIUM   |
 | use_cache flag                 | ✅ Implemented
 | ⚠️ Defined but unused  | 🟡 HIGH     |
 | Forward reference resolution   | ✅ evaluate_forwardref
 | ✅ Basic via eval      | 🟢 OK       |
 | String type resolution         | ✅ Full
 | ✅ Via eval + fallback | 🟢 OK       |
 | Annotated extraction           | ✅ Robust
 | ✅ Good                | 🟢 OK       |

 LEVERAGE PYDANTIC INTERNALS 🎯

 Instead of rolling our own type resolution, use pydantic's 
 mature utilities:

 # From pydantic._internal._typing_extra:
 from pydantic._internal._typing_extra import (
     is_annotated,         # Better than get_origin() check
     annotated_type,       # Extract type from Annotated
     is_none_type,         # Detect None/NoneType/Literal[None]
     is_union_origin,      # Detect Union | types
     is_generic_alias,     # Detect generic types
     is_callable,          # Detect Callable
     is_classvar_annotation,  # Detect ClassVar
     is_finalvar,          # Detect Final
     is_namedtuple,        # Detect NamedTuple
 )

 # From pydantic._internal._typing_extra - Type evaluation:
 from pydantic._internal._typing_extra import (
     get_function_type_hints,  # Better than 
 typing.get_type_hints
     eval_type,                # Safe type evaluation
     eval_type_lenient,        # Lenient eval (ignores errors)
     try_eval_type,            # Try eval, return None on 
 failure
 )

 # From pydantic._internal._core_utils:
 from pydantic._internal._core_utils import (
     get_type_ref,  # Create unique cache keys for types 
 (better than id())
 )

 # From pydantic._internal._utils:
 from pydantic._internal._utils import (
     lenient_isinstance,   # Safe isinstance that won't error
     lenient_issubclass,   # Safe issubclass that won't error
     can_be_positional,    # Check if param accepts positional 
 args
     sequence_like,        # Detect sequence types
 )

 Benefits:
 - ✅ Battle-tested - Used by millions of pydantic users
 - ✅ Handles edge cases - Forward refs, string annotations,
 PEP 563, Python 3.13+ changes
 - ✅ Performance optimized - Cached and optimized over years
 - ✅ Maintained - Updated for new Python versions
 automatically
 - ✅ Type-safe - Proper TypeGuard returns for type narrowing

 Critical Improvements

 1. Circular Dependency Detection 🔴

 Problem: Infinite recursion if ServiceA depends on ServiceB
 which depends on ServiceA

 FastAPI Pattern:
 # From FastAPI's get_flat_dependant():
 def get_flat_dependant(
     dependant: Dependant,
     *,
     skip_repeats: bool = False,
     visited: Optional[list[DependencyCacheKey]] = None,
 ) -> Dependant:
     if visited is None:
         visited = []
     visited.append(dependant.cache_key)  # Track visited

     for sub_dependant in dependant.dependencies:
         if skip_repeats and sub_dependant.cache_key in
 visited:
             continue  # Prevent cycles

 CodeWeaver Implementation:
 # In container.py, add to resolve():
 async def resolve(
     self,
     interface: type[T],
     _resolution_stack: list[type[Any]] | None = None
 ) -> T:
     if _resolution_stack is None:
         _resolution_stack = []

     # Detect circular dependency
     if interface in _resolution_stack:
         cycle = " -> ".join(t.__name__ for t in
 _resolution_stack + [interface])
         raise CircularDependencyError(
             f"Circular dependency detected: {cycle}"
         )

     _resolution_stack.append(interface)
     try:
         # ... existing resolution logic ...
         instance = await self._call_with_injection(factory,
 _resolution_stack)
     finally:
         _resolution_stack.pop()

     return instance

 2. Generator/Context Manager Dependencies 🟡

 FastAPI Pattern:
 # Dependency with cleanup
 @asynccontextmanager
 async def get_db_session():
     session = await create_session()
     try:
         yield session
     finally:
         await session.close()

 # FastAPI handles this in _solve_generator():
 async def _solve_generator(
     *, dependant: Dependant, stack: AsyncExitStack, 
 sub_values: dict[str, Any]
 ) -> Any:
     if dependant.is_async_gen_callable:
         cm = asynccontextmanager(dependant.call)(**sub_values)
     elif dependant.is_gen_callable:
         cm = contextmanager_in_threadpool(contextmanager(depen
 dant.call)(**sub_values))
     return await stack.enter_async_context(cm)

 CodeWeaver Implementation:
 # In container.py:
 async def _call_with_injection(
     self,
     obj: Callable[..., Any],
     _resolution_stack: list[type[Any]] | None = None,
     _cleanup_stack: AsyncExitStack | None = None,
 ) -> Any:
     # ... existing signature inspection ...

     # Detect if this is a generator function
     if inspect.isasyncgenfunction(obj):
         # Wrap in async context manager
         cm = asynccontextmanager(obj)(**kwargs)
         if _cleanup_stack:
             return await
 _cleanup_stack.enter_async_context(cm)
         # No cleanup stack - can't properly clean up, warn?
         async with cm as value:
             return value

     elif inspect.isgeneratorfunction(obj):
         # Wrap sync generator
         @contextmanager
         def sync_cm():
             yield from obj(**kwargs)
         if _cleanup_stack:
             return await _cleanup_stack.enter_async_context(
                 contextmanager_in_threadpool(sync_cm())
             )

 Add to Container:
 class Container:
     def __init__(self):
         # ... existing fields ...
         self._cleanup_stack: AsyncExitStack | None = None

     @asynccontextmanager
     async def lifespan(self):
         async with AsyncExitStack() as stack:
             self._cleanup_stack = stack
             # ... startup hooks ...
             try:
                 yield self
             finally:
                 # ... shutdown hooks ...
                 self._cleanup_stack = None

 3. Scope Lifecycle Management 🟡

 FastAPI Pattern:
 - scope="function" - Created and destroyed per function call
 - scope="request" - Created once per request, shared across
 function calls in that request

 CodeWeaver Implementation:
 # In depends.py:
 @dataclass
 class Depends:
     dependency: Callable[..., Any] | None = None
     use_cache: bool = True
     scope: Literal["singleton", "request", "function"] | None
 = None  # ADD

 # In container.py:
 class Container:
     def __init__(self):
         # ... existing ...
         self._request_cache: dict[type[Any], Any] = {}  # 
 Request-scoped instances

     async def resolve(
         self,
         interface: type[T],
         scope_context: Literal["request", "function"] | None =
  None,
         _resolution_stack: list[type[Any]] | None = None
     ) -> T:
         # Check scope
         registered_scope = self._get_scope(interface)

         # Singleton - check singleton cache
         if registered_scope == "singleton":
             if interface in self._singletons:
                 return self._singletons[interface]

         # Request-scoped - check request cache
         elif registered_scope == "request" and scope_context
 == "request":
             if interface in self._request_cache:
                 return self._request_cache[interface]

         # Create instance...
         instance = await self._call_with_injection(factory,
 ...)

         # Cache appropriately
         if registered_scope == "singleton":
             self._singletons[interface] = instance
         elif registered_scope == "request" and scope_context
 == "request":
             self._request_cache[interface] = instance

         return instance

     def clear_request_cache(self):
         """Call this at the end of each request."""
         self._request_cache.clear()

 4. Error Aggregation 🟡

 FastAPI Pattern:
 # From solve_dependencies():
 errors: list[Any] = []
 for sub_dependant in dependant.dependencies:
     solved_result = await solve_dependencies(...)
     if solved_result.errors:
         errors.extend(solved_result.errors)  # Collect, don't 
 fail
         continue
     # ... use solved_result.values ...

 CodeWeaver Implementation:
 # In container.py:
 @dataclass
 class ResolutionResult:
     """Result of dependency resolution with error tracking."""
     values: dict[str, Any]
     errors: list[DependencyError]

 async def _call_with_injection(
     self,
     obj: Callable[..., Any],
     collect_errors: bool = False,  # NEW
     ...
 ) -> Any | ResolutionResult:
     errors = []
     kwargs = {}

     for name, param in signature.parameters.items():
         try:
             # ... existing resolution logic ...
             kwargs[name] = await self._resolve_dependency(...)
         except Exception as e:
             if collect_errors:
                 errors.append(DependencyError(param=name,
 error=e))
                 continue
             else:
                 raise  # Fail fast (current behavior)

     if collect_errors and errors:
         return ResolutionResult(values=kwargs, errors=errors)

     # ... call obj(**kwargs) ...

 5. use_cache Flag Implementation 🟡

 Problem: use_cache is defined in Depends but never checked
 during resolution

 Fix in container.py:
 async def _resolve_dependency(
     self,
     name: str,
     param: inspect.Parameter,
     marker: Depends,
     ...
 ) -> Any:
     # Check if caching is disabled for this specific 
 dependency
     if not marker.use_cache:
         # Always create new instance
         if marker.dependency:
             factory = self._factories.get(marker.dependency,
 marker.dependency)
             return await self._call_with_injection(factory,
 ...)

     # ... existing resolution with caching ...

 6. Union Type Handling 🟢

 Using pydantic utilities:
 # In container.py:
 from pydantic._internal._typing_extra import is_union_origin,
 is_none_type
 from pydantic._internal._utils import lenient_issubclass
 from typing_extensions import get_args

 async def _resolve_union_dependency(
     self,
     annotation: Any,
     ...
 ) -> Any:
     """Try to resolve from union types in order using pydantic
  utils."""
     if not is_union_origin(annotation):
         raise ValueError(f"Not a union type: {annotation}")

     union_args = get_args(annotation)

     # Try each type in the union
     for arg_type in union_args:
         # Skip None using pydantic's robust None detection
         if is_none_type(arg_type):
             continue

         # Check if registered
         if arg_type in self._factories or arg_type in
 self._overrides:
             return await self.resolve(arg_type)

     # Try to instantiate first non-None type
     for arg_type in union_args:
         if not is_none_type(arg_type):
             try:
                 return await self.resolve(arg_type)
             except Exception:
                 continue

     raise ValueError(f"Could not resolve any type from union: 
 {union_args}")

 7. Improved Type Resolution & Cache Keys 🟢

 Replace manual type resolution with pydantic utilities:

 # In container.py - REPLACE current implementation:
 from pydantic._internal._typing_extra import (
     get_function_type_hints,
     eval_type_lenient,
     is_annotated,
     annotated_type,
 )
 from pydantic._internal._core_utils import get_type_ref
 from pydantic._internal._utils import lenient_isinstance,
 lenient_issubclass

 def _get_signature_and_hints(
     self, obj: Callable[..., Any], globalns: dict[str, Any]
 ) -> tuple[inspect.Signature, dict[str, Any]]:
     """Get signature and type hints using pydantic's robust 
 utilities."""
     try:
         signature = inspect.signature(obj)
         # Use pydantic's function type hint getter (handles 
 PEP 563, forward refs, etc.)
         type_hints = get_function_type_hints(
             obj,
             include_extras=True,  # Preserve Annotated 
 metadata
             types_namespace=globalns,
         )
     except NameError:
         # Fallback for unresolvable forward refs
         signature = inspect.signature(obj)
         type_hints = {}

     return signature, type_hints

 def _unwrap_annotated(self, annotation: Any) -> Any:
     """Unwrap Annotated using pydantic utility."""
     # Use pydantic's annotated_type() instead of manual 
 get_origin check
     unwrapped = annotated_type(annotation)
     return unwrapped if unwrapped is not None else annotation

 def _create_cache_key(self, type_: type[Any]) -> str:
     """Create stable cache key using pydantic's 
 get_type_ref."""
     # This handles generics, type aliases, and edge cases 
 better than id()
     return get_type_ref(type_)

 # Use in resolution:
 async def resolve(
     self,
     interface: type[T],
     _resolution_stack: list[str] | None = None  # Use string 
 keys
 ) -> T:
     if _resolution_stack is None:
         _resolution_stack = []

     # Use pydantic's get_type_ref for stable cache keys
     cache_key = self._create_cache_key(interface)

     # Detect circular dependency using stable keys
     if cache_key in _resolution_stack:
         cycle = " -> ".join(_resolution_stack + [cache_key])
         raise CircularDependencyError(f"Circular dependency: 
 {cycle}")

     _resolution_stack.append(cache_key)
     try:
         # ... existing resolution logic ...
     finally:
         _resolution_stack.pop()

 ---
 Part 3: New Exception Hierarchy

 # In codeweaver/exceptions.py or di/exceptions.py:

 class DependencyError(Exception):
     """Base exception for DI system errors."""
     pass

 class CircularDependencyError(DependencyError):
     """Raised when a circular dependency is detected."""
     def __init__(self, cycle: str):
         super().__init__(f"Circular dependency detected: 
 {cycle}")
         self.cycle = cycle

 class UnresolvableDependencyError(DependencyError):
     """Raised when a dependency cannot be resolved."""
     def __init__(self, interface: type, reason: str):
         super().__init__(
             f"Cannot resolve dependency {interface.__name__}: 
 {reason}"
         )
         self.interface = interface
         self.reason = reason

 class ScopeViolationError(DependencyError):
     """Raised when scope rules are violated."""
     def __init__(self, dependent: str, dependency: str, 
 reason: str):
         super().__init__(
             f"Scope violation: {dependent} cannot depend on 
 {dependency}: {reason}"
         )

 class DependencyResolutionErrors(DependencyError):
     """Aggregate multiple dependency resolution errors."""
     def __init__(self, errors: list[DependencyError]):
         messages = "\n".join(f"  - {e}" for e in errors)
         super().__init__(f"Multiple dependency 
 errors:\n{messages}")
         self.errors = errors

 ---
 Part 4: Testing Strategy

 New Test Categories

 1. Circular Dependency Detection
 def test_circular_dependency_simple():
     """A -> B -> A should raise CircularDependencyError."""

 def test_circular_dependency_complex():
     """A -> B -> C -> A should raise 
 CircularDependencyError."""

 def test_circular_dependency_self_reference():
     """A -> A should raise CircularDependencyError."""

 2. Generator Dependencies
 async def test_async_generator_dependency():
     """Async generator dependencies should be cleaned up."""

 async def test_sync_generator_dependency():
     """Sync generator dependencies should be cleaned up."""

 async def test_nested_generator_dependencies():
     """Nested generators should all clean up in reverse 
 order."""

 3. Scope Lifecycle
 async def test_request_scope_isolation():
     """Request-scoped deps should not share across 
 requests."""

 async def test_singleton_vs_request_scope():
     """Singletons should persist, request-scoped should 
 not."""

 async def test_function_scope_creates_new_each_time():
     """Function-scoped deps should create new instance per 
 call."""

 4. Error Aggregation
 async def test_collect_all_resolution_errors():
     """Should collect and report all errors, not just 
 first."""

 async def test_error_aggregation_with_nested_deps():
     """Should collect errors from nested dependency chains."""

 5. Union Type Resolution
 async def test_union_type_resolution():
     """Should resolve first available type from union."""

 async def test_optional_dependency():
     """Should handle Optional[Service] = None gracefully."""

 6. Provider Decorator
 def test_provider_decorator_on_function():
     """@provider should register async functions."""

 def test_provider_decorator_on_class():
     """@provider should register classes."""

 def test_provider_decorator_with_scope():
     """@provider(Service, scope='request') should set 
 scope."""

 ---
 Part 5: Migration Path

 Phase 1: Container Backend (No API Changes)

 - Add circular dependency detection
 - Implement generator/context manager support
 - Fix use_cache flag
 - Add error aggregation option
 - Add scope support to container

 Breaking: None (all additive or bug fixes)

 Phase 2: Provider Decorator API (Breaking)

 - Implement @provider decorator fully
 - Auto-discovery of providers
 - Deprecate manual di/providers.py getters
 - Migration guide for existing code

 Breaking: Moderate - existing code works but deprecated

 Phase 3: Cleanup (Breaking)

 - Remove legacy registry bridge code
 - Remove manual provider imports
 - Enforce new patterns

 Breaking: Major - full cutover to new system

 ---
 Implementation Checklist

 Critical Files to Modify

 1. src/codeweaver/di/container.py - Core resolution logic
   - Replace type resolution with pydantic utilities:
       - Import from pydantic._internal._typing_extra,
 _core_utils, _utils
     - Replace _unwrap_annotated() with annotated_type()
     - Replace get_type_hints() with get_function_type_hints()
     - Use is_union_origin(), is_none_type() for type checks
     - Use lenient_isinstance(), lenient_issubclass() for safe
 checks
   - Add stable cache keys:
       - Create _create_cache_key() using get_type_ref()
     - Use string cache keys instead of type objects in
 resolution stack
   - Add _resolution_stack parameter to resolve()
   - Implement circular dependency detection with stable keys
   - Add generator/async generator detection and handling
   - Add _cleanup_stack field and lifecycle management
   - Implement scope support (singleton/request/function)
   - Fix use_cache flag handling
   - Add error aggregation option
   - Add union type resolution using pydantic utilities
   - Add _request_cache and clear_request_cache()
 2. src/codeweaver/di/utils.py - Provider registration
   - Enhance @provider decorator with scope, module params
   - Add support for @provider on classes
   - Add generator function detection
   - Add validation (no circular registration)
 3. src/codeweaver/di/depends.py - Dependency markers
   - Add scope parameter to Depends dataclass
   - Add cleanup hint for generator functions
 4. src/codeweaver/di/__init__.py - Public API
   - Export provider decorator
   - Add deps namespace with __getattr__ magic
   - Update module docstring with new patterns
 5. src/codeweaver/exceptions.py - Exception hierarchy
   - Add DependencyError base class
   - Add CircularDependencyError
   - Add UnresolvableDependencyError
   - Add ScopeViolationError
   - Add DependencyResolutionErrors
 6. tests/unit/di/ - Comprehensive tests
   - Test circular dependency detection
   - Test generator dependencies
   - Test scope lifecycle
   - Test error aggregation
   - Test union type resolution
   - Test @provider decorator
   - Test migration from old to new API

 ---
 Success Criteria

 ✅ No circular dependency runtime errors - all caught at
 resolution time
 ✅ Generator dependencies clean up - verified in tests
 ✅ Request scope isolation - verified across multiple
 "requests"
 ✅ Error aggregation works - can collect all errors before
 failing
 ✅ use_cache=False respected - creates new instances
 ✅ Union types resolve - picks first available type
 ✅ @provider decorator works - cleaner API than manual
 registration
 ✅ All tests pass - including new edge case coverage
 ✅ Migration guide complete - clear path from old to new API

 ---
 Risk Assessment

 🔴 High Risk: Circular dependency detection in production
 (must be fast)
 🟡 Medium Risk: Generator cleanup in error cases (need
 comprehensive tests)
 🟢 Low Risk: API migration (gradual with deprecation warnings)

 Timeline Estimate

 - Container backend improvements: 2-3 days
 - Provider decorator API: 1-2 days
 - Testing & validation: 2-3 days
 - Migration guide & cleanup: 1 day



 -----

 
  ---
  Question 1: Injecting Frequently-Resolved Config Values

  Problem: Repeated Resolution Anti-Pattern

  # Current pattern (problematic)
  def index_files():
      project_path = get_project_path()  # Call 1
      # ...

  def create_collection():
      project_path = get_project_path()  # Call 2
      collection_name = f"{project_path.name}_vectors"
      # ...

  def persist_index():
      config_dir = get_user_config_dir()  # Call 3
      # ...

  Issues:
  - Repeated resolution overhead
  - Hard to test (mocking get_project_path() everywhere)
  - Can't easily override for integration tests
  - Hidden dependencies

  Solution: Runtime Context Pattern

  Create a runtime context object that's resolved once at startup and injected:

  # core/config/runtime.py

  @dataclass
  class RuntimeContext:
      """Runtime configuration resolved once at application startup.
      
      These are values that:
      1. Are computed/discovered at runtime (not from settings files)
      2. Don't change during application lifetime
      3. Are needed across multiple packages
      """

      project_path: Path
      """Project root directory (from git discovery or cwd)."""

      user_config_dir: Path
      """User configuration directory (~/.config/codeweaver)."""

      cache_dir: Path
      """Cache directory for models, embeddings, etc."""

      collection_name: str
      """Qdrant collection name (derived from project)."""

      project_name: str
      """Normalized project name."""

      # Add other runtime values as needed
      is_git_repo: bool
      git_root: Path | None

  # core/config/providers.py (or core/di.py)

  @provider(RuntimeContext, scope="singleton")
  def create_runtime_context(
      settings: Annotated[CodeWeaverSettings, Depends(...)] = INJECTED[CodeWeaverSettings]
  ) -> RuntimeContext:
      """Create runtime context from settings and environment discovery."""
      from core.utils.filesystem import get_project_path, get_user_config_dir

      project_path = get_project_path()

      # Resolve collection name (with override from settings)
      collection_name = (
          settings.vector_store.collection.collection_name
          if settings.vector_store.collection
          else f"{project_path.name}_vectors"
      )

      return RuntimeContext(
          project_path=project_path,
          user_config_dir=get_user_config_dir(),
          cache_dir=get_user_config_dir() / "cache",
          collection_name=collection_name,
          project_name=project_path.name,
          is_git_repo=is_git_repository(project_path),
          git_root=find_git_root(project_path) if is_git_repository(project_path) else None
      )

  # Usage across codebase
  # engine/indexer/indexer.py

  class Indexer:
      def __init__(
          self,
          runtime: Annotated[RuntimeContext, Depends(...)] = INJECTED[RuntimeContext]
      ):
          self.runtime = runtime

      async def index_files(self):
          # No repeated calls!
          files = discover_files(self.runtime.project_path)
          # ...

  # providers/vector_stores/qdrant.py

  class QdrantVectorStore:
      def __init__(
          self,
          runtime: Annotated[RuntimeContext, Depends(...)] = INJECTED[RuntimeContext],
          settings: Annotated[QdrantSettings, Depends(...)] = INJECTED[QdrantSettings]
      ):
          self.runtime = runtime
          self.settings = settings

      async def create_collection(self):
          # Use injected value
          await self.client.create_collection(
              collection_name=self.runtime.collection_name,
              # ...
          )

  Benefits:

  - ✅ Resolved once at startup (singleton scope)
  - ✅ Easy testing - mock RuntimeContext instead of individual functions
  - ✅ Explicit dependencies - clear what each component needs
  - ✅ Type-safe - IDE autocomplete works
  - ✅ Overridable - register test override in container

  Testing Pattern:

  # tests/conftest.py

  @pytest.fixture
  def test_runtime_context(tmp_path):
      """Override runtime context for tests."""
      return RuntimeContext(
          project_path=tmp_path / "test_project",
          user_config_dir=tmp_path / ".config",
          cache_dir=tmp_path / ".cache",
          collection_name="test_collection",
          project_name="test_project",
          is_git_repo=False,
          git_root=None
      )

  @pytest.fixture
  def container_with_test_runtime(test_runtime_context):
      """Container with test runtime context."""
      container = Container()
      container.register_instance(RuntimeContext, test_runtime_context)
      return container

  # In tests
  async def test_indexer(container_with_test_runtime):
      indexer = await container_with_test_runtime.resolve(Indexer)
      # indexer.runtime is the test context!

  ---
  Question 2: Where to Define Provider Factories

  With the @provider decorator, you don't need a centralized registry file - providers can be defined anywhere and auto-discovered. But organization still matters.

  Recommended Pattern: Hybrid Approach

  src/codeweaver/
  ├── core/
  │   ├── config/
  │   │   ├── __init__.py
  │   │   ├── settings.py       # CoreConfig
  │   │   └── providers.py      # @provider for CoreConfig, RuntimeContext
  │   ├── chunks.py             # No DI needed (pure data)
  │   └── utils/
  │       └── filesystem.py     # Pure functions
  │
  ├── engine/
  │   ├── config/
  │   │   ├── __init__.py
  │   │   ├── settings.py       # EngineConfig
  │   │   └── providers.py      # @provider for engine configs
  │   ├── indexer/
  │   │   ├── indexer.py        # @provider(Indexer) on class
  │   │   └── manifest.py       # @provider(Manifest) on class
  │   └── chunker/
  │       └── base.py           # @provider on chunker classes
  │
  ├── providers/
  │   ├── config/
  │   │   └── providers.py      # @provider for provider settings
  │   ├── embedding/
  │   │   └── providers/
  │   │       └── voyage.py     # @provider(VoyageEmbeddingProvider)
  │   └── vector_stores/
  │       └── qdrant.py         # @provider(QdrantVectorStore)
  │
  └── server/
      ├── config/
      │   ├── settings.py       # CodeWeaverSettings (root)
      │   └── providers.py      # @provider for CodeWeaverSettings
      └── app.py

  Pattern Rules:

  1. Self-Registering Classes (Simple)
  # engine/indexer/indexer.py

  @provider(scope="singleton")  # No explicit type needed
  class Indexer:
      """Self-registering provider."""

      def __init__(
          self,
          runtime: Annotated[RuntimeContext, Depends(...)] = INJECTED[RuntimeContext],
          settings: Annotated[EngineConfig, Depends(...)] = INJECTED[EngineConfig]
      ):
          self.runtime = runtime
          self.settings = settings

  2. Factory Functions (Complex Setup)
  # providers/embedding/providers/voyage.py

  # Simple case - self-register
  @provider(scope="singleton")
  class VoyageEmbeddingProvider:
      ...

  # Complex case - factory function in providers.py
  # providers/embedding/config/providers.py

  @provider(VoyageEmbeddingProvider, scope="singleton")
  async def create_voyage_provider(
      settings: Annotated[EmbeddingProviderSettings, Depends(...)] = INJECTED[EmbeddingProviderSettings],
      runtime: Annotated[RuntimeContext, Depends(...)] = INJECTED[RuntimeContext]
  ) -> VoyageEmbeddingProvider:
      """Complex factory with async setup."""

      # Get model capabilities
      caps = get_model_capabilities(Provider.VOYAGE, settings.model_settings["model"])

      # Build configuration
      config = VoyageProviderConfig.from_settings(settings, caps)

      # Create and initialize provider
      provider = VoyageEmbeddingProvider(config=config, caps=caps)
      await provider.initialize_async()

      return provider

  3. Config Objects (Per-Package providers.py)
  # core/config/providers.py

  @provider(RuntimeContext, scope="singleton")
  def create_runtime_context(...) -> RuntimeContext:
      ...

  @provider(CoreConfig, scope="singleton")
  def create_core_config() -> CoreConfig:
      return CoreConfig()

  # engine/config/providers.py

  @provider(EngineConfig, scope="singleton")
  def create_engine_config() -> EngineConfig:
      return EngineConfig()

  # server/config/providers.py

  @provider(CodeWeaverSettings, scope="singleton")
  def create_settings(
      core: Annotated[CoreConfig, Depends(...)] = INJECTED[CoreConfig],
      engine: Annotated[EngineConfig, Depends(...)] = INJECTED[EngineConfig],
      # ... other configs
  ) -> CodeWeaverSettings:
      """Compose settings from all packages."""
      return CodeWeaverSettings(
          core=core,
          engine=engine,
          # ...
      )

  Discovery Pattern

  You don't need explicit discovery - just import the modules with @provider decorators before using the container:

  # server/app.py

  from codeweaver.di import get_container

  # Import modules with @provider decorators (triggers registration)
  import codeweaver.core.config.providers
  import codeweaver.engine.config.providers
  import codeweaver.engine.indexer.indexer
  import codeweaver.providers.embedding.providers.voyage
  import codeweaver.server.config.providers

  # Now container has all providers auto-discovered
  container = get_container()

  # Resolve what you need
  async def main():
      settings = await container.resolve(CodeWeaverSettings)
      indexer = await container.resolve(Indexer)

  Or use a discovery helper:

  # di/__init__.py

  def auto_discover_providers():
      """Import all modules with @provider decorators."""
      import importlib
      import pkgutil

      # Import all **/config/providers.py modules
      for package_name in ["core", "engine", "providers", "server"]:
          try:
              importlib.import_module(f"codeweaver.{package_name}.config.providers")
          except ImportError:
              pass

      # Import all provider implementation modules
      provider_packages = [
          "codeweaver.providers.embedding.providers",
          "codeweaver.providers.vector_stores",
          "codeweaver.engine.indexer",
          "codeweaver.engine.chunker",
      ]

      for package_name in provider_packages:
          package = importlib.import_module(package_name)
          for _, module_name, _ in pkgutil.iter_modules(package.__path__):
              importlib.import_module(f"{package_name}.{module_name}")

  # Usage
  from codeweaver.di import auto_discover_providers, get_container

  auto_discover_providers()
  container = get_container()

  ---
  Question 3: Config Discovery After Package Split

  Current Structure:

  core/config/       → CoreConfig
  engine/config/     → EngineConfig, IndexerConfig, ChunkerConfig
  providers/config/  → ProviderSettings
  server/config/     → CodeWeaverSettings (root)

  Solution: Explicit Composition (Recommended)

  Don't auto-discover configs - explicitly compose them:

  # server/config/settings.py

  from pydantic_settings import BaseSettings

  from codeweaver.core.config.settings import CoreConfig
  from codeweaver.engine.config.settings import EngineConfig
  from codeweaver.providers.config.providers import ProviderSettings

  class CodeWeaverSettings(BaseSettings):
      """Root settings composing all package configs.
      
      This is the single source of truth for all settings.
      """

      core: CoreConfig = Field(default_factory=CoreConfig)
      engine: EngineConfig = Field(default_factory=EngineConfig)
      providers: ProviderSettings = Field(default_factory=ProviderSettings)

      # Server-specific settings
      mcp_port: int = 9328
      management_port: int = 9329

      model_config = SettingsConfigDict(
          env_prefix="CODEWEAVER_",
          env_nested_delimiter="__",
          # ... other pydantic-settings config
      )

  Benefits:

  - ✅ Explicit dependencies - clear what configs exist
  - ✅ Type-safe - settings.core.log_level works
  - ✅ No magic - obvious where each config comes from
  - ✅ Easy to test - mock entire settings object
  - ✅ IDE support - full autocomplete

  Environment Variable Pattern:

  # All settings accessible via env vars with nesting
  CODEWEAVER_CORE__LOG_LEVEL=debug
  CODEWEAVER_ENGINE__INDEXER__BATCH_SIZE=128
  CODEWEAVER_PROVIDERS__EMBEDDING__PROVIDER=voyage

  DI Integration:

  # server/config/providers.py

  @provider(CodeWeaverSettings, scope="singleton")
  def create_settings() -> CodeWeaverSettings:
      """Load settings from env/files."""
      return CodeWeaverSettings()

  # Package configs are accessed through the root
  @provider(CoreConfig, scope="singleton")
  def get_core_config(
      settings: Annotated[CodeWeaverSettings, Depends(...)] = INJECTED[CodeWeaverSettings]
  ) -> CoreConfig:
      """Extract core config from root settings."""
      return settings.core

  @provider(EngineConfig, scope="singleton")
  def get_engine_config(
      settings: Annotated[CodeWeaverSettings, Depends(...)] = INJECTED[CodeWeaverSettings]
  ) -> EngineConfig:
      """Extract engine config from root settings."""
      return settings.engine

  ---
  Putting It All Together

  Recommended Organization:

  # 1. Each package has config/providers.py
  # core/config/providers.py
  @provider(RuntimeContext, scope="singleton")
  def create_runtime_context(
      settings: Annotated[CodeWeaverSettings, Depends(...)] = INJECTED[CodeWeaverSettings]
  ) -> RuntimeContext:
      ...

  # 2. Server composes root settings
  # server/config/settings.py
  class CodeWeaverSettings(BaseSettings):
      core: CoreConfig
      engine: EngineConfig
      providers: ProviderSettings

  # server/config/providers.py
  @provider(CodeWeaverSettings, scope="singleton")
  def create_settings() -> CodeWeaverSettings:
      return CodeWeaverSettings()

  # 3. App auto-discovers and initializes
  # server/app.py
  from codeweaver.di import auto_discover_providers, get_container

  async def create_app():
      # Auto-discover all @provider decorators
      auto_discover_providers()

      # Get container with all providers
      container = get_container()

      # Resolve root dependencies
      settings = await container.resolve(CodeWeaverSettings)
      runtime = await container.resolve(RuntimeContext)

      return app

  This gives you:
  - ✅ Runtime context for frequently-used values
  - ✅ Clean organization with package-level config/providers.py
  - ✅ No manual discovery needed (auto-discover helper)
  - ✅ Explicit composition of root settings
  - ✅ Easy testing with container overrides

  Want me to help implement the RuntimeContext pattern or the auto-discovery helper?

> for the ContextObject.... currently we always check the settings first because those values *can* be set, but they can also *not be set* ... but I guess you 
could just DI it, right?  Like, in the context object:  project_path: Path = SettingsDep._resolve().project_path or get_project_path() 

● Exactly! But you don't need SettingsDep._resolve() - just use the injected settings parameter in the factory function. The factory is where all the "settings or fallback" logic should live:

  Clean Pattern: Settings-First with Discovery Fallback

  # core/config/runtime.py

  @dataclass
  class RuntimeContext:
      """Runtime configuration values.
      
      Just data - no logic here.
      """
      project_path: Path
      user_config_dir: Path
      cache_dir: Path
      collection_name: str
      project_name: str
      is_git_repo: bool
      git_root: Path | None


  # core/config/providers.py

  @provider(RuntimeContext, scope="singleton")
  def create_runtime_context(
      settings: Annotated[CodeWeaverSettings, Depends(...)] = INJECTED[CodeWeaverSettings]
  ) -> RuntimeContext:
      """Create runtime context with settings-first, discovery fallback pattern."""

      # Settings-first, discovery fallback
      project_path = settings.project_path or get_project_path()
      user_config_dir = settings.user_config_dir or get_user_config_dir()

      # For nested optional settings, use helper
      collection_name = _resolve_collection_name(settings, project_path)

      # Derived values
      project_name = project_path.name
      is_git_repo = is_git_repository(project_path)
      git_root = find_git_root(project_path) if is_git_repo else None

      return RuntimeContext(
          project_path=project_path,
          user_config_dir=user_config_dir,
          cache_dir=user_config_dir / "cache",
          collection_name=collection_name,
          project_name=project_name,
          is_git_repo=is_git_repo,
          git_root=git_root
      )


  def _resolve_collection_name(settings: CodeWeaverSettings, project_path: Path) -> str:
      """Resolve collection name from settings or generate default.
      
      Helper to handle deeply nested optional settings.
      """
      # Try to get from settings (deeply nested)
      if (
          settings.providers.vector_store
          and (store_settings := settings.providers.vector_store[0])
          and store_settings.collection
          and (collection_name := store_settings.collection.collection_name)
      ):
          return collection_name

      # Fallback to project-based name
      return f"{project_path.name}_vectors"

  Better: Add Helper Methods to Settings

  If you find yourself doing this a lot, add helper methods to your settings classes:

  # server/config/settings.py

  class CodeWeaverSettings(BaseSettings):
      """Root settings."""

      core: CoreConfig = Field(default_factory=CoreConfig)
      providers: ProviderSettings = Field(default_factory=ProviderSettings)

      # Optional overrides
      project_path: Path | None = None
      user_config_dir: Path | None = None

      # Helper methods for common access patterns
      def get_collection_name(self, default_project_name: str) -> str:
          """Get collection name from settings or generate default."""
          if (
              self.providers.vector_store
              and (store := self.providers.vector_store[0])
              and store.collection
              and store.collection.collection_name
          ):
              return store.collection.collection_name

          return f"{default_project_name}_vectors"

      def get_project_path(self) -> Path:
          """Get project path from settings or discover it."""
          if self.project_path:
              return self.project_path

          from codeweaver.core.utils.filesystem import get_project_path
          return get_project_path()

      def get_user_config_dir(self) -> Path:
          """Get user config dir from settings or discover it."""
          if self.user_config_dir:
              return self.user_config_dir

          from codeweaver.core.utils.filesystem import get_user_config_dir
          return get_user_config_dir()

  Then the factory becomes super clean:

  @provider(RuntimeContext, scope="singleton")
  def create_runtime_context(
      settings: Annotated[CodeWeaverSettings, Depends(...)] = INJECTED[CodeWeaverSettings]
  ) -> RuntimeContext:
      """Create runtime context using settings helpers."""

      # Settings handle the fallback logic
      project_path = settings.get_project_path()
      user_config_dir = settings.get_user_config_dir()
      collection_name = settings.get_collection_name(project_path.name)

      # Derived values
      is_git_repo = is_git_repository(project_path)

      return RuntimeContext(
          project_path=project_path,
          user_config_dir=user_config_dir,
          cache_dir=user_config_dir / "cache",
          collection_name=collection_name,
          project_name=project_path.name,
          is_git_repo=is_git_repo,
          git_root=find_git_root(project_path) if is_git_repo else None
      )

  Why This Pattern?

  ✅ Benefits:
  1. No field defaults with side effects - RuntimeContext is pure data
  2. Clear fallback logic - obvious where settings vs discovery happens
  3. Testable - mock settings, test factory logic separately
  4. Type-safe - settings injection is properly typed
  5. Single responsibility - factory handles creation, dataclass holds data

  ❌ Don't do this:
  @dataclass
  class RuntimeContext:
      # ❌ Side effects in field defaults
      project_path: Path = field(default_factory=lambda: SettingsDep._resolve().project_path or get_project_path())

      # ❌ Doesn't work with DI
      # ❌ Triggers discovery on every import
      # ❌ Can't test
      # ❌ Hard to override

  For Testing

  The factory pattern makes testing trivial:

  # tests/conftest.py

  @pytest.fixture
  def test_settings():
      """Settings with explicit overrides for testing."""
      return CodeWeaverSettings(
          project_path=Path("/test/project"),
          user_config_dir=Path("/test/config"),
          providers=ProviderSettings(
              vector_store=QdrantVectorStoreProviderSettings(
                  collection=CollectionConfig(
                      collection_name="test_collection"
                  )
              )
          )
      )

  @pytest.fixture
  def test_runtime_context(test_settings):
      """Runtime context from test settings."""
      # Just call the factory with test settings
      return create_runtime_context(test_settings)

  # Or override in container
  @pytest.fixture
  def container_with_test_runtime(test_runtime_context):
      container = Container()
      container.register_instance(RuntimeContext, test_runtime_context)
      return container

  For Complex Nested Settings

  If you have lots of deeply nested optional settings, consider a settings accessor pattern:

  # core/config/accessor.py

  class SettingsAccessor:
      """Helper to safely access deeply nested settings."""

      def __init__(self, settings: CodeWeaverSettings):
          self.settings = settings

      def get_collection_name(self, default: str) -> str:
          """Safely get collection name."""
          return (
              self.settings.providers.vector_store
              and self.settings.providers.vector_store[0].collection
              and self.settings.providers.vector_store[0].collection.collection_name
          ) or default

      def get_vector_dimension(self, default: int = 1024) -> int:
          """Safely get vector dimension."""
          return (
              self.settings.providers.embedding
              and self.settings.providers.embedding[0].model_settings
              and self.settings.providers.embedding[0].model_settings.get("dimension")
          ) or default

      # ... other nested accessors

  # Usage in factory
  @provider(RuntimeContext, scope="singleton")
  def create_runtime_context(
      settings: Annotated[CodeWeaverSettings, Depends(...)] = INJECTED[CodeWeaverSettings]
  ) -> RuntimeContext:
      accessor = SettingsAccessor(settings)

      project_path = settings.get_project_path()

      return RuntimeContext(
          project_path=project_path,
          collection_name=accessor.get_collection_name(f"{project_path.name}_vectors"),
          # ...
      )

  Bottom line: Keep RuntimeContext as pure data, put all the "settings or fallback" logic in the factory function where you have access to injected settings. This keeps everything testable and type-safe.