# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""
Lazy import utilities for deferred module loading.

This module provides a LazyImport class inspired by cyclopts' CommandSpec pattern,
enabling true lazy loading where both module import AND attribute access are deferred
until the imported object is actually used.

Unlike importlib.util.LazyLoader which defers import until first attribute access,
LazyImport allows you to chain attribute accesses and defer the entire import until
the final resolution point (typically a function call or value access).
"""

from __future__ import annotations

import threading

from typing import Any


class LazyImport[Import: Any]:
    """
    Lazy import specification that defers both module import and attribute access.

    Inspired by cyclopts' CommandSpec pattern, this class creates a proxy that
    delays import execution until the imported object is actually used (called,
    accessed for its value, etc.), not just referenced.

    Unlike LazyLoader which defers import until attribute access, LazyImport
    defers EVERYTHING until the final resolution point.

    Examples:
        Basic module import with deferred attribute access:

        >>> tiktoken = lazy_import("tiktoken")
        >>> # No import has happened yet
        >>> encoding = tiktoken.get_encoding("cl100k_base")  # Import happens HERE
        >>> tokens = encoding.encode("hello world")

        Specific function import:

        >>> uuid_gen = lazy_import("uuid", "uuid4")
        >>> # No import yet
        >>> new_id = uuid_gen()  # Import happens HERE when called

        Attribute chaining without immediate resolution:

        >>> Settings = lazy_import("codeweaver.config").CodeWeaverSettings
        >>> # Still no import!
        >>> config = Settings()  # Import happens HERE when instantiated

        Global-level lazy imports (main use case):

        >>> # At module level
        >>> _get_settings = lazy_import("codeweaver.config").get_settings
        >>> _tiktoken = lazy_import("tiktoken")
        >>>
        >>> # Later in code - imports happen when actually used
        >>> def my_function():
        ...     settings = _get_settings()  # config module imports NOW
        ...     encoder = _tiktoken.get_encoding("gpt2")  # tiktoken imports NOW
    """

    __slots__ = ("_attrs", "_lock", "_module_name", "_parent", "_resolved")  # type: ignore

    def __init__(self, module_name: str, *attrs: str) -> None:
        """
        Create a lazy import specification.

        Args:
            module_name: Fully qualified module name (e.g., "package.submodule")
            *attrs: Optional attribute chain to access from the module

        Examples:
            >>> LazyImport("os")  # Lazy module import
            >>> LazyImport("os.path", "join")  # Lazy function import
            >>> LazyImport("pydantic", "BaseModel")  # Lazy class import
            >>> LazyImport("collections", "abc", "Mapping")  # Nested attributes
        """
        object.__setattr__(self, "_module_name", module_name)
        object.__setattr__(self, "_attrs", attrs)
        object.__setattr__(self, "_resolved", None)
        object.__setattr__(self, "_parent", None)
        object.__setattr__(self, "_lock", threading.Lock())

    def _resolve(self) -> Import:
        """
        Import the module and resolve the attribute chain.

        This is called automatically when the lazy import is actually used.
        The result is cached for subsequent accesses.

        Returns:
            The resolved module or attribute

        Raises:
            ImportError: If the module cannot be imported
            AttributeError: If an attribute in the chain doesn't exist

        Thread Safety:
            This method uses a lock to ensure thread-safe resolution.
            Multiple threads can safely access the same LazyImport instance.
        """
        resolved = object.__getattribute__(self, "_resolved")
        if resolved is not None:
            return resolved

        # Thread-safe resolution
        with object.__getattribute__(self, "_lock"):
            return self._handle_resolve()

    def _handle_resolve(self) -> Import:
        """
        Internal method to perform the actual resolution logic.
        """
        # Double-check after acquiring lock
        resolved = object.__getattribute__(self, "_resolved")
        if resolved is not None:
            return resolved

        module_name = object.__getattribute__(self, "_module_name")
        attrs = object.__getattribute__(self, "_attrs")

        # Import the module
        try:
            module = __import__(module_name, fromlist=[""])
        except ImportError as e:
            msg = f"Cannot import module {module_name!r} from LazyImport"
            raise ImportError(msg) from e

        # Walk the attribute chain
        result = module
        for i, attr in enumerate(attrs):
            try:
                result = getattr(result, attr)
            except AttributeError as e:
                attr_path = ".".join(attrs[: i + 1])
                msg = f"Module {module_name!r} has no attribute path {attr_path!r}"
                raise AttributeError(msg) from e

        object.__setattr__(self, "_resolved", result)

        # Mark parent as resolved if we have one
        parent = object.__getattribute__(self, "_parent")
        if parent is not None:
            # Recursively mark parent chain as resolved
            parent._mark_resolved()

        return result

    def _mark_resolved(self) -> None:
        """
        Mark this LazyImport as resolved without actually resolving it.

        This is used to mark parent LazyImports as resolved when their children
        are resolved, since accessing any attribute of a module means the module
        itself has been imported.

        This method is called recursively up the parent chain to ensure all
        ancestors are marked as resolved.
        """
        # Already resolved, nothing to do
        if object.__getattribute__(self, "_resolved") is not None:
            return

        # Mark as resolved (we use a sentinel to indicate "resolved but not cached")
        # We can't store the actual module without resolving it, so we use True as marker
        object.__setattr__(self, "_resolved", True)

        # Recursively mark parent
        parent = object.__getattribute__(self, "_parent")
        if parent is not None:
            parent._mark_resolved()

    def __getattr__(self, name: str) -> LazyImport[Import]:
        """
        Chain attribute access without resolving.

        Returns a new LazyImport with the attribute added to the chain.
        This allows you to write: lazy_import("pkg").module.Class
        without triggering any imports until the final usage.

        Args:
            name: Attribute name to access

        Returns:
            New LazyImport with extended attribute chain
        """
        module_name = object.__getattribute__(self, "_module_name")
        attrs = object.__getattribute__(self, "_attrs")
        child = LazyImport(module_name, *attrs, name)
        # Set parent reference so child can mark parent as resolved
        object.__setattr__(child, "_parent", self)
        return child

    def __call__(self, *args: Any, **kwargs: Any) -> Import:
        """
        Resolve and call the imported callable.

        This is typically where the actual import happens for function/class imports.

        Args:
            *args: Positional arguments to pass to the callable
            **kwargs: Keyword arguments to pass to the callable

        Returns:
            Result of calling the resolved object

        Raises:
            TypeError: If the resolved object is not callable
        """
        return self._resolve()(*args, **kwargs)

    def __repr__(self) -> str:
        """Debug representation showing import path and resolution status."""
        module_name = object.__getattribute__(self, "_module_name")
        attrs = object.__getattribute__(self, "_attrs")
        resolved = object.__getattribute__(self, "_resolved")

        path = module_name
        if attrs:
            path += "." + ".".join(attrs)

        status = "resolved" if resolved is not None else "not resolved"
        return f"<LazyImport {path!r} ({status})>"

    def __setattr__(self, name: str, value: Any) -> None:
        """
        Forward attribute setting to resolved object.

        Args:
            name: Attribute name
            value: Value to set
        """
        setattr(self._resolve(), name, value)

    def __dir__(self) -> list[str]:
        """
        Return attributes of the resolved object.

        Note: This triggers resolution since we need to inspect the actual object.

        Returns:
            List of attribute names
        """
        return dir(self._resolve())

    @property
    def is_resolved(self) -> bool:
        """
        Check if this lazy import has been resolved yet.

        Returns:
            True if resolved, False otherwise

        Examples:
            >>> lazy = lazy_import("os")
            >>> lazy.is_resolved
            False
            >>> _ = lazy.path  # Access attribute
            >>> lazy.is_resolved
            False  # Still not resolved! Just chained
            >>> result = lazy.path.join("a", "b")  # Call method
            >>> lazy.is_resolved
            True  # NOW it's resolved
        """
        return object.__getattribute__(self, "_resolved") is not None


def lazy_import[Import: Any](module_name: str, *attrs: str) -> LazyImport[Import]:  # pyright: ignore[reportInvalidTypeVarUse] # being explicit about return type
    """
    Create a lazy import that defers module loading until actual use.

    This is the main entry point for creating lazy imports. Unlike traditional
    lazy import patterns that still execute on first attribute access, this
    returns a LazyImport proxy that can chain attribute accesses without
    triggering any imports until the final usage point.

    Args:
        module_name: Module to import (e.g., "codeweaver.config")
        *attrs: Optional attribute path to access (e.g., "get_settings")

    Returns:
        LazyImport proxy that resolves on use

    Examples:
        Simple module import:

        >>> tiktoken = lazy_import("tiktoken")
        >>> encoding = tiktoken.get_encoding("cl100k_base")  # Imports NOW

        Specific function import:

        >>> get_settings = lazy_import("codeweaver.config", "get_settings")
        >>> settings = get_settings()  # Imports NOW

        Attribute chaining:

        >>> Settings = lazy_import("codeweaver.config").CodeWeaverSettings
        >>> config = Settings()  # Imports NOW

        Global-level usage (main use case):

        >>> # At module level - no imports happen
        >>> _settings = lazy_import("codeweaver.config").get_settings()
        >>> _tiktoken_encoder = lazy_import("tiktoken").get_encoding
        >>>
        >>> # Later in code - imports happen when called
        >>> def process():
        ...     settings = _settings  # No import yet - it's the result of get_settings()
        ...     encoder = _tiktoken_encoder("gpt2")  # tiktoken imports NOW

    """
    return LazyImport(module_name, *attrs)


__all__ = ("LazyImport", "lazy_import")
