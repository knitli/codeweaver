# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Lazy import utilities for deferred module loading and attribute access."""

from __future__ import annotations

from importlib import import_module
from types import MappingProxyType, ModuleType
from typing import Any, cast


INTROSPECTION_ATTRS: frozenset[str] = frozenset({
    "__annotations__",
    "__class__",
    "__closure__",
    "__code__",
    "__defaults__",
    "__dict__",
    "__doc__",
    "__func__",
    "__globals__",
    "__kwdefaults__",
    "__module__",
    "__name__",
    "__qualname__",
    "__self__",
    "__signature__",
    "__text_signature__",
    "__wrapped__",
})


class LazyImport[Import: Any]:
    """
    Lazy import specification that defers both module import and attribute access.

    Inspired by cyclopts' CommandSpec pattern, this class creates a proxy that
    delays import execution until the imported object is actually used (called,
    accessed for its value, etc.), not just referenced.
    """

    __slots__ = ("_attrs", "_lock", "_module_name", "_parent", "_resolved")
    "Attributes that trigger immediate resolution when accessed.\n\n    These attributes are commonly used for introspection and should not\n    be lazily resolved to ensure correct behavior when inspecting the object.\n    "

    def __init__(self, module_name: str, *attrs: str) -> None:
        """Initialize the LazyImport with the module name and attribute path."""
        import threading

        object.__setattr__(self, "_module_name", module_name)
        object.__setattr__(self, "_attrs", attrs)
        object.__setattr__(self, "_resolved", None)
        object.__setattr__(self, "_parent", None)
        object.__setattr__(self, "_lock", threading.Lock())

    def _resolve(self) -> Import:
        resolved = object.__getattribute__(self, "_resolved")
        if resolved is not None:
            return resolved
        with object.__getattribute__(self, "_lock"):
            return self._handle_resolve()

    def _handle_resolve(self) -> Import:
        resolved = object.__getattribute__(self, "_resolved")
        if resolved is not None:
            return resolved
        module_name = object.__getattribute__(self, "_module_name")
        attrs = object.__getattribute__(self, "_attrs")
        try:
            module = __import__(module_name, fromlist=[""])
        except ImportError as e:
            msg = f"Cannot import module {module_name!r} from LazyImport"
            raise ImportError(msg) from e
        result = module
        for i, attr in enumerate(attrs):
            try:
                result = getattr(result, attr)
            except AttributeError as e:
                attr_path = ".".join(attrs[: i + 1])
                msg = f"Module {module_name!r} has no attribute path {attr_path!r}"
                raise AttributeError(msg) from e
        object.__setattr__(self, "_resolved", result)
        self._resolve_parents(default_to=True)
        return cast(Import, result)

    def _mark_resolved(self) -> None:
        if object.__getattribute__(self, "_resolved") is not None:
            return
        self._resolve_parents(default_to=True)

    def _resolve_parents(self, *, default_to: bool) -> None:
        current = object.__getattribute__(self, "_resolved")
        if current is None:
            object.__setattr__(self, "_resolved", default_to)
        parent = object.__getattribute__(self, "_parent")
        if parent is not None:
            parent._mark_resolved()

    def __getattr__(self, name: str) -> LazyImport[Import]:
        """Get attribute from the resolved object, or create a new LazyImport for it."""
        if name in INTROSPECTION_ATTRS:
            try:
                resolved = self._resolve()
            except AttributeError as e:
                module_name = object.__getattribute__(self, "_module_name")
                attrs = object.__getattribute__(self, "_attrs")
                path = f"{module_name}.{'.'.join(attrs)}" if attrs else module_name
                raise AttributeError(
                    f"Attribute {name!r} not found during resolution of {path!r}"
                ) from e
            else:
                return getattr(resolved, name)
        module_name = object.__getattribute__(self, "_module_name")
        attrs = object.__getattribute__(self, "_attrs")
        child: LazyImport[Import] = LazyImport(module_name, *attrs, name)
        object.__setattr__(child, "_parent", self)
        return child

    def __call__(self, *args: Any, **kwargs: Any) -> Import:
        """Call the resolved object with the provided arguments."""
        return self._resolve()(*args, **kwargs)

    def __repr__(self) -> str:
        """String representation of the LazyImport object."""
        module_name = object.__getattribute__(self, "_module_name")
        attrs = object.__getattribute__(self, "_attrs")
        resolved = object.__getattribute__(self, "_resolved")
        path = module_name
        if attrs:
            path += "." + ".".join(attrs)
        status = "resolved" if resolved is not None else "not resolved"
        return f"<LazyImport {path!r} ({status})>"

    def __setattr__(self, name: str, value: Any) -> None:
        """Set attribute on the resolved object."""
        setattr(self._resolve(), name, value)

    def __dir__(self) -> list[str]:
        """List available attributes for the resolved object."""
        return dir(self._resolve())

    def is_resolved(self) -> bool:
        """Check if the lazy import has been resolved."""
        return object.__getattribute__(self, "_resolved") is not None


def lazy_import[Import: Any](module_name: str, *attrs: str) -> LazyImport[Import]:
    """Create a lazy import that defers module loading until actual use."""
    return LazyImport(module_name, *attrs)


def create_lazy_getattr(
    dynamic_imports: MappingProxyType[str, tuple[str, str]],
    module_globals: dict[str, object],
    module_name: str,
) -> object:
    """Create a standardized __getattr__ function for package lazy imports."""

    def __getattr__(attr_name: str) -> object:  # noqa: N807
        # Handle missing attributes with AttributeError (standard for __getattr__)
        # This prevents KeyError when Python introspects for special attributes like __func__
        try:
            dynamic_attr = dynamic_imports[attr_name]
        except KeyError as e:
            raise AttributeError(f"module '{module_name}' has no attribute '{attr_name}'") from e

        package, target_module = dynamic_attr

        if target_module == "__module__":
            result = import_module(f".{attr_name}", package=package)
            globals()[attr_name] = result._resolve() if isinstance(result, LazyImport) else result
            return result

        module: ModuleType = import_module(f".{target_module}", package=package)
        result = getattr(module, attr_name)

        # Cache only the requested attribute, not all attributes from the module
        # This avoids circular import issues during eager caching
        g = globals()
        g[attr_name] = result._resolve() if isinstance(result, LazyImport) else result

        return g[attr_name]

    __getattr__.__module__ = module_name
    __getattr__.__doc__ = f"Dynamic __getattr__ for lazy imports in module {module_name!r}."
    return __getattr__


__all__ = ("INTROSPECTION_ATTRS", "LazyImport", "create_lazy_getattr", "lazy_import")
