"""Utility functions for generating identifiers and hashes."""

from __future__ import annotations

import datetime
import sys

from typing import Literal, cast, overload

from pydantic import UUID7

from codeweaver.core.types.aliases import BlakeHashKey, BlakeKey


if sys.version_info < (3, 14):
    from uuid_extensions import uuid7 as uuid7_gen
else:
    from uuid import uuid7 as uuid7_gen


def uuid7() -> UUID7:
    """Generate a new UUID7."""
    from pydantic import UUID7

    return cast(UUID7, uuid7_gen())


@overload
def uuid7_as_timestamp(
    uuid: str | int | UUID7, *, as_datetime: Literal[True]
) -> datetime.datetime | None: ...
@overload
def uuid7_as_timestamp(
    uuid: str | int | UUID7, *, as_datetime: Literal[False] = False
) -> int | None: ...
def uuid7_as_timestamp(
    uuid: str | UUID7 | int, *, as_datetime: bool = False
) -> int | datetime.datetime | None:
    """Utility to extract the timestamp from a UUID7, optionally as a datetime."""
    if sys.version_info < (3, 14):
        from uuid_extensions import time_ns, uuid_to_datetime

        return uuid_to_datetime(uuid) if as_datetime else time_ns(uuid)
    from uuid import uuid7

    uuid = uuid7(uuid) if isinstance(uuid, str | int) else uuid
    return (
        datetime.datetime.fromtimestamp(uuid.time // 1_000, datetime.UTC)
        if as_datetime
        else uuid.time
    )


try:
    # there are a handful of rare situations where users might not be able to install blake3
    # luckily the apis are the same
    from blake3 import blake3
except ImportError:
    from hashlib import blake2b as blake3


def get_blake_hash[AnyStr: (str, bytes)](value: AnyStr) -> BlakeHashKey:
    """Hash a value using blake3 and return the hex digest."""
    return BlakeKey(blake3(value.encode("utf-8") if isinstance(value, str) else value).hexdigest())


def get_blake_hash_generic(value: str | bytes) -> BlakeHashKey:
    """Hash a value using blake3 and return the hex digest - generic version."""
    return BlakeKey(blake3(value.encode("utf-8") if isinstance(value, str) else value).hexdigest())


__all__ = ("get_blake_hash", "get_blake_hash_generic", "uuid7", "uuid7_as_timestamp")
