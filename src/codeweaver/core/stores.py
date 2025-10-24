# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""A foundational enum class for the CodeWeaver project for common functionality."""

from __future__ import annotations

import contextlib
import copy
import os
import sys

from collections.abc import Callable, ItemsView, Iterator, KeysView, ValuesView
from functools import cached_property
from types import MappingProxyType
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    Literal,
    NewType,
    NotRequired,
    Required,
    TypedDict,
    TypeGuard,
    TypeVar,
    cast,
)
from weakref import WeakValueDictionary

from pydantic import (
    UUID7,
    ConfigDict,
    Field,
    NonNegativeInt,
    PositiveInt,
    PrivateAttr,
    Tag,
    computed_field,
)
from typing_extensions import TypeIs

from codeweaver.common.utils.utils import uuid7
from codeweaver.core import BasedModel


if TYPE_CHECKING:
    from codeweaver.core.types import AnonymityConversion, FilteredKey

try:
    # there are a handful of rare situations where users might not be able to install blake3
    # luckily the apis are the same
    from blake3 import blake3
except ImportError:
    from hashlib import blake2b as blake3


BlakeKey = NewType("BlakeKey", str)
BlakeHashKey = Annotated[
    BlakeKey, Field(description="""A blake3 hash key string""", min_length=64, max_length=64)
]

HashKeyKind = TypeVar(
    "HashKeyKind", Annotated[UUID7, Tag("uuid")], Annotated[BlakeHashKey, Tag("blake")]
)


def get_blake_hash[AnyStr: (str, bytes)](value: AnyStr) -> BlakeHashKey:
    """Hash a value using blake3 and return the hex digest."""
    return BlakeKey(blake3(value.encode("utf-8") if isinstance(value, str) else value).hexdigest())


def get_blake_hash_generic(value: str | bytes) -> BlakeHashKey:
    """Hash a value using blake3 and return the hex digest - generic version."""
    return BlakeKey(blake3(value.encode("utf-8") if isinstance(value, str) else value).hexdigest())


def to_uuid() -> UUID7:
    """Generate a new UUID7."""
    return uuid7()


class StoreDict(TypedDict, total=False):
    """Dictionary representation of a _SimpleTypedStore.

    Note: This schema was simplified in the 2025 refactor.
    Legacy fields like 'use_uuid' and 'sub_value_type' are no longer supported.
    Use make_uuid_store() or make_blake_store() factory functions instead.
    """

    value_type: Required[type]
    store: NotRequired[dict[UUID7 | BlakeHashKey, Any]]
    _size_limit: NotRequired[PositiveInt | None]
    _id: NotRequired[UUID7]


class _SimpleTypedStore[KeyT: (UUID7, BlakeHashKey), T](BasedModel):
    """A key-value store with precise typing for keys and values.

    - KeyT is either UUID7 or BlakeHashKey, determined by the concrete subclass.
    - T is the value type for all items in the store.

    The store protects data integrity by copying data on get, pushes removed items to a trash heap for
    potential recovery, and can optionally limit the total size (default is 3MB).

    As an added bonus, the store itself is:

        1. Entirely serializable. You can save and load it as JSON. Weakrefs are *not serialized*.
        2. Supports complex data types. You can store any picklable Python object, including nested structures.
        3. Has an API that mimics a standard Python dictionary, making it easy to use.

    Example:
    ```python
    # Use concrete subclasses for type safety:
    store = UUIDStore[list[str]](value_type=list)
    store["item1"] = ["value1"]
    ```

    Hey, it started simple!
    """

    model_config = BasedModel.model_config | ConfigDict(validate_assignment=True)

    store: Annotated[
        dict[KeyT, T],
        Field(
            init=False,
            default_factory=dict,
            description="""The key-value store. Keys are UUID7 or Blake3 hash keys depending on configuration.""",
        ),
    ]

    _value_type: Annotated[type[T], PrivateAttr(init=False)]

    _keygen: Callable[[], UUID7] | Callable[[str | bytes], BlakeHashKey] = to_uuid

    _size_limit: Annotated[PositiveInt | None, Field(repr=False, kw_only=True)] = (
        3 * 1024 * 1024
    )  # 3 MB default limit

    # Per-instance trash heap; avoid sharing weakrefs across instances (don't want to accidentally maintain pointers across instances)
    _trash_heap: WeakValueDictionary[KeyT, T] = PrivateAttr(
        default_factory=lambda: WeakValueDictionary[KeyT, T]()
    )

    _id: Annotated[
        UUID7,
        Field(default_factory=uuid7, description="""Unique identifier for the store""", init=False),
    ] = to_uuid()

    def __init__(self, **data: Any) -> None:
        """Initialize the store with type checks and post-init processing."""
        if data.get("store") is not None:
            self.store = data.pop("store")
        if data.get("value_type"):
            self._value_type = data.pop("value_type")
        if data.get("_value_type"):
            self._value_type = data.pop("_value_type")
        elif not self._value_type and data:
            self._value_type = next(iter(data.values())).__class__  # type: ignore
        if not hasattr(self, "_value_type") or not self._value_type:
            raise ValueError(
                "`You must either provide `_value_type` or provide values to infer it from.`"
            )

    def __model_post_init__(self) -> None:
        """Post-initialization processing.

        Override this to customize initialization behavior.
        """

    def __pydantic_extra__(self, name: str, value: Any) -> dict[str, Any]:  # type: ignore
        """This is to prevent a pydantic bug that tries to set extra fields, when this method is deprecated.
        We'll remove once I get around to submitting a PR for it.
        """
        return {}

    @computed_field
    @property
    def value_type(self) -> type[T]:
        """Return the type of values stored in the store."""
        if not hasattr(self, "_value_type"):
            raise ValueError("No value_type set! You must provide it on initialization.")
        return self._value_type

    @computed_field
    @property
    def data_size(self) -> NonNegativeInt:
        """Return the size of the store in bytes."""
        return sum(sys.getsizeof(key) + sys.getsizeof(value) for key, value in self.store.items())

    @property
    def id(self) -> UUID7:
        """Return the unique identifier for the store."""
        return self._id

    @staticmethod
    def _trial_and_error_copy(item: T) -> Literal["deepcopy", "copy", "constructor", "iter"] | None:
        """Attempt to copy an item, falling back to a simpler method on failure."""
        with contextlib.suppress(Exception):
            if copy.deepcopy(item):
                return "deepcopy"
        with contextlib.suppress(Exception):
            if copy.copy(item):
                return "copy"
        with contextlib.suppress(Exception):
            # does it have a constructor that returns itself?
            if callable(item) and item(item) is item:
                return "constructor"
        if hasattr(item, "__iter__") and callable(item):
            with contextlib.suppress(Exception):
                if item(iter(item)):  # pyright: ignore[reportCallIssue, reportArgumentType]
                    return "iter"
        return None

    @cached_property
    def _get_copy_strategy(self) -> Callable[[T], T] | None:
        """Determine the best strategy for copying items from the store."""
        sample_item: T | None = None
        if self.values():
            sample_item = next(iter(self.values()))
        elif callable(self.value_type):
            with contextlib.suppress(Exception):
                sample_item = self.value_type()
        if not sample_item:
            return lambda item: item  # no-op copy
        if isinstance(sample_item, list | set | tuple):
            return lambda item: item.copy()  # pyright: ignore[reportUnknownMemberType, reportUnknownLambdaType, reportAttributeAccessIssue]
        if copy_strategy := self._trial_and_error_copy(sample_item):
            if copy_strategy == "deepcopy":
                return copy.deepcopy
            if copy_strategy == "copy":
                return copy.copy
            if copy_strategy == "constructor":
                return lambda item: type(item)(item)  # type: ignore  # we know it's callable from trial_and_error_copy
            # copy_strategy == "iter"
            return lambda item: type(item)(iter(item))  # type: ignore
        return lambda item: item  # no-op copy

    def get(self, key: KeyT, default: Any = None) -> T | None:
        """Get a value from the store."""
        if item := self.store.get(key):
            return self._get_copy_strategy(item) if self._get_copy_strategy else item
        # Try to recover from trash first, then return default
        return self.store.get(key, default) if self.recover(key) else default

    def __iter__(self) -> Iterator[KeyT]:  # pyright: ignore[reportIncompatibleMethodOverride]
        """Return an iterator over the keys in the store."""
        return iter(self.store)

    def __delitem__(self, key: KeyT) -> None:
        """Delete a value from the store."""
        if key in self:
            self.delete(key)
        raise KeyError(key)

    def __getitem__(self, key: KeyT) -> T:
        """Get an item from the store by key."""
        if key in self:
            return cast(T, self.get(key))
        raise KeyError(key)

    def __contains__(self, key: KeyT) -> bool:
        """Check if a key is in the store."""
        return key in self.store

    def __len__(self) -> int:
        return len(self.store)

    def __setitem__(self, key: KeyT, value: Any) -> None:
        """Set an item in the store by key."""
        self.set(key, value)

    def __and__(self, other: _SimpleTypedStore[KeyT, T]) -> _SimpleTypedStore[KeyT, T]:
        """Return a new store with items from both stores."""
        if self.value_type != other.value_type or type(self) is not type(other):
            return self
        new_store = type(self)(value_type=self.value_type, store={}, _size_limit=self._size_limit)
        new_store.store = self.store.copy()
        new_store.store |= other.store
        return new_store

    def _guard(self, item: Any) -> TypeIs[T]:
        """Ensure the item is of the correct type."""
        return isinstance(item, self.value_type)

    @property
    def keygen(self) -> Callable[[], UUID7] | Callable[[str | bytes], BlakeHashKey]:
        """Return the key generator function."""
        return self._keygen

    @property
    def view(self) -> MappingProxyType[KeyT, T]:
        """Return a read-only view of the store."""
        return MappingProxyType(self.store)

    def generate(self, value: str | bytes | None = None) -> KeyT:
        """Generate a new key for the store."""
        if self._keygen == to_uuid:
            return cast(KeyT, to_uuid())
        # we're dealing with BlakeHashKey:
        if not value:
            rand = os.urandom(16)
            value = rand
        return cast(KeyT, self._keygen(value))  # pyright: ignore[reportCallIssue]

    def keys(self) -> KeysView[KeyT]:
        """Return the keys in the store."""
        return self.store.keys()

    def values(self) -> ValuesView[T]:
        """Return the values in the store."""
        return self.store.values()

    def items(self) -> ItemsView[KeyT, T]:
        """Return the items in the store."""
        return self.store.items()

    def _validate_value(self, value: Any) -> TypeGuard[T]:
        """Validate that the value is of the correct type."""
        return self._guard(value)

    def _check_and_set(self, key: KeyT, value: T) -> KeyT:
        """Check the value type and set the sub-value type if needed."""
        if key in self.store:
            return key
        self.set(key, value)
        return key

    def update(self, values: dict[KeyT, T]) -> Iterator[KeyT]:
        """Update multiple items in the store."""
        if values and type(next(iter(values.keys()))) is type(next(iter(self.store.keys()))):
            for key, value in values.items():
                self[key] = value
            yield from values.keys()
        else:
            yield from (self.add(value) for value in values.values())

    def add(self, value: Any, *, hash_value: bytes | bytearray | None = None) -> KeyT:
        """Add a value to the store and return its key.

        Optionally provide a value to hash for the key if not using UUIDs and the value is large or complex.
        """
        if not self._validate_value(value):
            raise TypeError(f"Invalid value: {value}")
        key: UUID7 | None = to_uuid() if self.keygen == to_uuid else None  # pyright: ignore[reportAssignmentType]
        if key:
            return self._check_and_set(cast(KeyT, key), value)
        if hash_value:
            blake_key: BlakeHashKey = (  # pyright: ignore[reportRedeclaration]
                get_blake_hash(hash_value)
                if isinstance(hash_value, bytes)
                else get_blake_hash(bytes(hash_value))
            )
        else:
            # For Blake stores, generate a random value to hash if the value can't be hashed directly
            rand_value = os.urandom(16)
            blake_key = get_blake_hash_generic(rand_value)
        return self._check_and_set(cast(KeyT, blake_key), value)

    def _make_room(self, required_space: int) -> None:
        """Make room in the store by removing the least recently used items."""
        if not self._size_limit or required_space <= 0:
            return
        weight_loss_goal = (self._size_limit - self.data_size) + required_space
        if not self.store or weight_loss_goal <= 0:
            # We either have no items, or the item is too large to fit
            self.store.clear()
            return
        while self._size_limit and weight_loss_goal > 0:
            # LIFO removal strategy for simplicity
            removed = self.store.popitem()
            weight_loss_goal -= sys.getsizeof(removed[0]) + sys.getsizeof(removed[1])
            self._trash_heap[removed[0]] = removed[1]
            if weight_loss_goal <= 0:
                break

    def set(self, key: KeyT, value: Any) -> None:
        """Set a value in the store."""
        if not self._validate_value(value):
            raise TypeError(f"Invalid value: {value}")
        if not self.has_room(sys.getsizeof(value) + sys.getsizeof(key)):
            self._make_room(sys.getsizeof(value) + sys.getsizeof(key))
        if key in self.store:
            if value == self.store[key]:
                return
            _ = self._check_and_set(key, value)
        if key in self._trash_heap and self._trash_heap[key] is not None:
            del self._trash_heap[key]
        self.store[key] = value

    def has_room(self, additional_size: int = 0) -> bool:
        """Check if the store has room for additional data."""
        return not self._size_limit or (self.data_size + additional_size) <= self._size_limit

    def delete(self, key: KeyT) -> None:
        """Delete a value from the store."""
        if key in self.store:
            del self.store[key]
        if key in self._trash_heap:
            del self._trash_heap[key]

    def clear(self) -> None:
        """Clear the store."""
        self._trash_heap.update(self.store)
        self.store.clear()

    def clear_trash(self) -> None:
        """Clear the trash heap."""
        self._trash_heap.clear()

    def recover(self, key: KeyT) -> bool:
        """Recover a value from the trash heap."""
        if (
            key in self._trash_heap
            and key not in self.store
            and (actually_there := self._trash_heap.get(key)) is not None
        ):
            self.set(key, actually_there)
            return True
        return False

    def _telemetry_keys(self) -> dict[FilteredKey, AnonymityConversion]:
        from codeweaver.core.types import AnonymityConversion, FilteredKey

        return {FilteredKey("store"): AnonymityConversion.COUNT}


class UUIDStore[T](_SimpleTypedStore[UUID7, T]):
    """Typed store specialized for UUID keys."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the UUIDStore with UUID key generation."""
        super().__init__(**kwargs)
        self._keygen = to_uuid


class BlakeStore[T](_SimpleTypedStore[BlakeHashKey, T]):
    """Typed store specialized for Blake3-hash keys."""

    def __init__(self, **kwargs: Any) -> None:
        """Initialize the BlakeStore with Blake3 key generation."""
        super().__init__(**kwargs)
        self._keygen = get_blake_hash_generic


def make_uuid_store[T](
    *, value_type: type[T], size_limit: PositiveInt | None = None
) -> UUIDStore[T]:
    """Create a UUIDStore with the specified value type."""
    return UUIDStore[T](_value_type=value_type, store={}, _size_limit=size_limit)


def make_blake_store[T](
    *, value_type: type[T], size_limit: PositiveInt | None = None
) -> BlakeStore[T]:
    """Create a BlakeStore with the specified value type."""
    return BlakeStore[T](_value_type=value_type, store={}, _size_limit=size_limit)


__all__ = (
    "BlakeHashKey",
    "BlakeKey",
    "BlakeStore",
    "StoreDict",
    "UUIDStore",
    "make_blake_store",
    "make_uuid_store",
    "to_uuid",
)
