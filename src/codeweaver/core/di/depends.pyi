# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Type stubs for dependency injection markers.

This stub file provides explicit type information for type checkers, allowing INJECTED
to work seamlessly as a default value for dependency-injected parameters. It supports:

1. Bare INJECTED usage: `def func(param: SomeDep = INJECTED)`
2. Subscripted usage: `def func(param: SomeDep = INJECTED[SomeType])`

Type checkers will infer the correct type from the parameter annotation or the subscript.
"""

from typing import Any, overload

from codeweaver.core.types import Sentinel

T_co = Any  # Covariant type for flexibility in dependency injection

class _InjectedProxy[Dep: type[T_co], S: Sentinel]:
    """Proxy object providing type-safe dependency injection.
    
    Supports both:
    - `INJECTED[SomeType]` - explicit type subscripting
    - `INJECTED` - bare usage with type inference from parameter annotation
    
    At runtime, this proxy wraps the DependsPlaceholder sentinel. Type checkers
    will recognize it as compatible with any dependency-injected parameter.
    """

    def __init__(self, sentinel: S) -> None: ...

    @overload
    def __getitem__(self, item: type[T_co]) -> T_co: ...
    
    def __getattr__(self, name: str) -> Any: ...
    
    def __bool__(self) -> bool: ...
    
    def __repr__(self) -> str: ...

class DependsPlaceholder(Sentinel):
    """Sentinel marking parameters for dependency injection."""
    ...

class Depends:
    """Dependency marker for declarative dependency injection.
    
    Indicates that a parameter should be resolved by the DI container.
    """

    def __init__(
        self,
        dependency: object | None = None,
        *,
        use_cache: bool = True,
        scope: str | None = None,
    ) -> None: ...
    
    def __repr__(self) -> str: ...

def depends(
    dependency: object | None = None,
    *,
    use_cache: bool = True,
    scope: str | None = None,
) -> Depends:
    """Helper to create a Depends marker for declarative injection."""
    ...

def is_depends_marker(value: Any) -> bool:
    """Check if a value is a DI injection marker or sentinel."""
    ...

# INJECTED is the universal sentinel for dependency injection.
# Type checkers see this as `Any` to allow flexible usage as a default value,
# while still supporting type inference from parameter annotations or subscripts.
#
# Usage patterns:
#   1. type Dep = Annotated[SomeType, depends(...)]
#      def func(param: Dep = INJECTED) -> None: ...
#
#   2. def func(param: SomeDep = INJECTED[SomeType]) -> None: ...
#
# In both cases, the DI container will inject the appropriate value at runtime.
INJECTED: Any
