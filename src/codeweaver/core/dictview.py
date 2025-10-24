# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Read-only view wrapper around a mapping (intended for TypedDict-backed dicts)."""

from collections.abc import ItemsView, Iterator, KeysView, Mapping, ValuesView
from types import MappingProxyType
from typing import TYPE_CHECKING, Any, cast


class DictView[TypedDictT: (Mapping[str, Any])](Mapping[str, Any]):
    """Read-only view wrapper around a mapping (intended for TypedDict-backed dicts).

    Provides a read-only view of a TypedDict (or other) mapping, preventing any modifications to the underlying data. This is useful for exposing configuration or data structures that should not be altered after creation.

    Args:
        mapping (TypedDictT): The mapping to wrap.
        make_immutable (bool, optional): Whether to make the underlying mapping immutable using `MappingProxyType`. Defaults to `True`. Important things to understand here:
            - DictView is always read-only, and the underlying mapping, if it is mutable, cannot be modified through the DictView interface (but can still be modified directly if the original mapping is accessible).
            - If `make_immutable` is `True`, the underlying mapping is wrapped in a `MappingProxyType`, making it immutable. This prevents any modifications to the original mapping through any references *to this mapping* -- like DictView, MappingProxyType provides a dynamic read-only view of the original mapping. The main difference is hashability and performance: MappingProxyType is hashable and slightly faster for read operations.
            - If `make_immutable` is `False`, the original mapping is used directly. This is useful if the original mapping is already immutable or you're not paranoid about mutability like we are.
    """

    __slots__ = ("_mapping", "data")

    # Expose the concrete typed-mapping as `data` for typecheckers to grab
    data: TypedDictT

    def __init__(self, mapping: TypedDictT, /, *, make_immutable: bool = True) -> None:
        """Initialize the DictView with the given mapping."""
        # We keep the underlying mapping read-only via MappingProxyType by default.
        self._mapping = MappingProxyType(mapping) if make_immutable else mapping
        # Give a typed alias for callers and type checkers
        self.data = cast(TypedDictT, self._mapping) if TYPE_CHECKING else self._mapping

    # Mapping protocol
    def __getitem__(self, key: str) -> Any:
        """Return the value for the given key."""
        return self._mapping[key]

    def __iter__(self) -> Iterator[str]:
        """Return an iterator over the keys in the mapping."""
        return iter(self._mapping)

    def __len__(self) -> int:
        """Return the number of items in the mapping."""
        return len(self._mapping)

    def __contains__(self, key: object) -> bool:
        """Return whether the mapping contains the given key."""
        return key in self._mapping

    # Convenience / views
    def keys(self) -> KeysView[str]:
        """Return a view of the keys in the mapping."""
        return self._mapping.keys()

    def values(self) -> ValuesView[Any]:
        """Return a view of the values in the mapping."""
        return self._mapping.values()

    def items(self) -> ItemsView[str, Any]:
        """Return a view of the items in the mapping."""
        return self._mapping.items()

    def get(self, key: str, default: Any = None) -> Any:
        """Return the value for the given key, or the default value if the key is not found."""
        return self._mapping.get(key, default)

    def __setattr__(self, name: str, value: Any) -> None:
        """Prevent setting attributes on the DictView, except during __init__."""
        # allow setting during __init__, which sets _mapping and data
        if name in {"_mapping", "data"}:
            object.__setattr__(self, name, value)
            return
        raise AttributeError("DictView is read-only")

    def __delattr__(self, name: str) -> None:
        """Prevent deleting attributes on the DictView."""
        raise AttributeError("DictView is read-only")

    def __repr__(self) -> str:
        """Return a string representation of the DictView."""
        return f"{type(self).__name__}({dict(self._mapping)})"
