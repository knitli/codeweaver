# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Utility to create standardized __getattr__ functions for lazy imports."""

from types import MappingProxyType


def create_lazy_getattr(
    dynamic_imports: MappingProxyType[str, tuple[str, str]],
    module_globals: dict[str, object],
    module_name: str,
) -> object:
    """
    Create a standardized __getattr__ function for package lazy imports.
    """

    def __getattr__(name: str) -> object:  # noqa: N807
        """Dynamically import submodules and classes for the package."""
        if name in dynamic_imports:
            parent_module, submodule_name = dynamic_imports[name]
            module = __import__(f"{parent_module}.{submodule_name}", fromlist=[""])
            result = getattr(module, name)
            # it's a LazyImport if it has a _resolve attribute
            if (
                hasattr(result, "_resolve")
                and result._resolve is not None
                and callable(result._resolve)
            ):
                result = result._resolve()
            module_globals[name] = result  # Cache for future access
            return result

        # Check if already cached
        if name in module_globals:
            return module_globals[name]

        raise AttributeError(f"module {module_name!r} has no attribute {name!r}")

    __getattr__.__module__ = module_name
    __getattr__.__doc__ = f"""
    Dynamic __getattr__ for lazy imports in module {module_name!r}."""

    return __getattr__


__all__ = ("create_lazy_getattr",)
