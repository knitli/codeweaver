# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

from typing import Any, overload

from codeweaver.core.types import Sentinel

type T_co = Any  # Covariant type for flexibility in dependency injection

class _InjectedProxy[Dep: type[T_co], S: Sentinel]:
    def __init__(self, sentinel: S) -> None: ...
    @overload
    def __getitem__(self, item: type[T_co]) -> T_co: ...
    @overload
    def __getitem__(self, item: type[Dep]) -> Dep: ...
    def __getitem__(self, item: type[Dep | T_co]) -> Dep | T_co: ...
    def __getattr__(self, name: str) -> Any: ...

class DependsPlaceholder(Sentinel): ...

class Depends:
    def __init__(
        self, dependency: object | None = None, *, use_cache: bool = True, scope: str | None = None
    ) -> None: ...

def depends(
    dependency: object | None = None, *, use_cache: bool = True, scope: str | None = None
) -> Depends: ...
def is_depends_marker(value: Any) -> bool: ...

# INJECTED is the universal sentinel for dependency injection.
# Type checkers see this as `Any` to allow flexible usage as a default value,
# while still supporting type inference from parameter annotations or subscripts.
#
# Usage patterns:
#   1. type Dep = Annotated[SomeType, depends(...)]
#      def func(param: Dep = INJECTED) -> None: ...
#
#   2. def func(param: SomeDep = INJECTED) -> None: ...
#
# In both cases, the DI container will inject the appropriate value at runtime.
INJECTED: Any
