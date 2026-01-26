# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Dependency Injection for CodeWeaver.

Provides a FastAPI-inspired declarative injection system.

## Registering Providers

To register a provider function or class with the DI container, use the `@dependency_provider` decorator:

```python "Registering a Provider Function"
from codeweaver.core.di import dependency_provider


@dependency_provider(ServiceProvider)
def service_factory() -> ServiceProvider:
    return ServiceProvider()
```

```python "Registering a Provider Class (Self-Registration)"
from codeweaver.core.di import dependency_provider


@dependency_provider(scope="singleton")
class ServiceProvider:
    def __init__(self):
        self.value = 42
```

The `@dependency_provider` decorator automatically registers your factory with the global DI container.
No additional setup needed - just decorate and inject!

## Creating a Type Alias for Dependency Injection

Create a type alias for cleaner, more maintainable code:

```python "Creating a Type Alias"
from typing import TYPE_CHECKING, Annotated

from codeweaver.core.di import INJECTED

if TYPE_CHECKING:
    from someplace import ServiceProvider

# Simple type alias (relies on auto-resolution)
type ServiceDep = ServiceProvider

# Or with explicit Depends marker for custom behavior
from codeweaver.core.di import depends

type ServiceDepWithScope = Annotated[ServiceProvider, depends(scope="request")]
```

## Using Your Dependency in Functions

Use the `INJECTED` sentinel to mark parameters for dependency injection:

```python "Using Dependencies"
from typing import TYPE_CHECKING
from codeweaver.core.di import INJECTED

if TYPE_CHECKING:
    from someplace import ServiceProvider


async def my_function(service: ServiceProvider = INJECTED) -> None:
    # service will be injected automatically by the DI container
    # The type annotation tells the container what to inject
    ...
```

The container automatically:
1. Discovers all `@dependency_provider` registrations
2. Resolves dependencies recursively
3. Manages singleton/request/function scopes
4. Handles async factories and generators
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from codeweaver.core.di.container import Container, get_container, reset_container
from codeweaver.core.utils import create_lazy_getattr


if TYPE_CHECKING:
    from codeweaver.core.di.depends import (
        INJECTED,
        Depends,
        DependsPlaceholder,
        depends,
        is_depends_marker,
    )
    from codeweaver.core.di.utils import (
        ProviderMetadata,
        dependency_provider,
        get_all_provider_metadata,
        get_all_providers,
        get_provider,
        get_provider_metadata,
        is_provider_registered,
    )


_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "INJECTED": (__spec__.parent, "depends"),
    "Depends": (__spec__.parent, "depends"),
    "DependsPlaceholder": (__spec__.parent, "depends"),
    "is_depends_marker": (__spec__.parent, "depends"),
    "depends": (__spec__.parent, "depends"),
    "ProviderMetadata": (__spec__.parent, "utils"),
    "ResolutionResult": (__spec__.parent, "container"),
    "get_all_provider_metadata": (__spec__.parent, "utils"),
    "get_all_providers": (__spec__.parent, "utils"),
    "get_provider": (__spec__.parent, "utils"),
    "get_provider_metadata": (__spec__.parent, "utils"),
    "is_provider_registered": (__spec__.parent, "utils"),
    "dependency_provider": (__spec__.parent, "utils"),
})

__getattr__ = create_lazy_getattr(_dynamic_imports, globals(), __name__)


__all__ = (
    "INJECTED",
    "Container",
    "Depends",
    "DependsPlaceholder",
    "ProviderMetadata",
    "ResolutionResult",
    "dependency_provider",
    "depends",
    "get_all_provider_metadata",
    "get_all_providers",
    "get_container",
    "get_provider",
    "get_provider_metadata",
    "is_depends_marker",
    "is_provider_registered",
    "reset_container",
)


def __dir__() -> list[str]:
    """Return the list of attributes for the module."""
    return list(__all__)
