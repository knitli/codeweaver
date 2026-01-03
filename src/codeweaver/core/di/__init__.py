# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Dependency Injection for CodeWeaver.

Provides a FastAPI-inspired declarative injection system.

## Registering Providers

To register a provider function or class with the DI container, you can use the provider decorator from
the `codeweaver.core.di` module:

```python "Registering a Provider"
from codeweaver.core.di import provider


@provider
def service_factory() -> ServiceProvider:
    return ServiceProvider()
```

## Creating a Dependency factory

You can create a factory for your dependencies using the `create_provider_factory` function:

```python "Creating a Dependency Factory"
# ⚠️ Important: Your must register your provider before calling this function. Order matters! ⚠️

from codeweaver.core.di import create_provider_factory

service_factory_provider = create_provider_factory(ServiceProvider)
```

## Creating a Dependency Marker

You can create a dependency marker using the `depends` helper function:

```python "Creating a Dependency Marker"
from codeweaver.core.di import depends

service_dependency = depends(service_factory_provider, use_cache=True)
```

## Create a Type Alias for Dependency Injection

Calling a function in a function signature is a bit sloppy. Create a type alias for cleaner code:

```python "Creating a Type Alias for Dependency Injection"
from typing import TYPE_CHECKING, Annotated

from codeweaver.core.di import depends

if TYPE_CHECKING:
    from someplace import ServiceProvider

type ServiceDep = Annotated[ServiceProvider, depends(service_factory_provider)]

# or if you created your own depends variable already:

type ServiceDep = Annotated[ServiceProvider, service_dependency]
```

## Using Your Dependency in Functions

Now you can use your dependency type alias in function signatures:

```python "Using Your Dependency in Functions"
from typing import TYPE_CHECKING
from codeweaver.core.di import INJECTED
from wherever import ServiceDep

if TYPE_CHECKING:
    from someplace import ServiceProvider


def my_function(service: ServiceDep = INJECTED[ServiceProvider]) -> None:
    # service will be injected by the DI container
    ...
```
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from codeweaver.core import create_lazy_getattr


if TYPE_CHECKING:
    from codeweaver.core.di.container import Container, get_container, reset_container
    from codeweaver.core.di.depends import (
        INJECTED,
        Depends,
        DependsPlaceholder,
        depends,
        is_depends_marker,
    )
    from codeweaver.core.di.utils import (
        ProviderMetadata,
        get_all_provider_metadata,
        get_all_providers,
        get_provider,
        get_provider_metadata,
        is_provider_registered,
        provider,
    )


_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "Container": (__spec__.parent, "container"),
    "get_container": (__spec__.parent, "container"),
    "reset_container": (__spec__.parent, "container"),
    "INJECTED": (__spec__.parent, "depends"),
    "Depends": (__spec__.parent, "depends"),
    "DependsPlaceholder": (__spec__.parent, "depends"),
    "is_depends_marker": (__spec__.parent, "depends"),
    "depends": (__spec__.parent, "depends"),
    "ProviderMetadata": (__spec__.parent, "utils"),
    "get_all_provider_metadata": (__spec__.parent, "utils"),
    "get_all_providers": (__spec__.parent, "utils"),
    "get_provider": (__spec__.parent, "utils"),
    "get_provider_metadata": (__spec__.parent, "utils"),
    "is_provider_registered": (__spec__.parent, "utils"),
    "provider": (__spec__.parent, "utils"),
})

__getattr__ = create_lazy_getattr(_dynamic_imports, globals(), __name__)


__all__ = (
    "INJECTED",
    "Container",
    "Depends",
    "DependsPlaceholder",
    "ProviderMetadata",
    "depends",
    "get_all_provider_metadata",
    "get_all_providers",
    "get_container",
    "get_provider",
    "get_provider_metadata",
    "is_depends_marker",
    "is_provider_registered",
    "provider",
    "reset_container",
)


def __dir__() -> list[str]:
    """Return the list of attributes for the module."""
    return list(__all__)
