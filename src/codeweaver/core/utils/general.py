# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""General utilities for CodeWeaver."""

from __future__ import annotations

import contextlib

from collections.abc import Callable, Iterable
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, cast

from codeweaver.core.types.aliases import CategoryName, LiteralStringT
from codeweaver.core.types.dictview import DictView


if TYPE_CHECKING:
    from importlib.util import find_spec

    if find_spec("codeweaver.config") is not None:
        from codeweaver.config.types import CodeWeaverSettingsDict
    else:
        CodeWeaverSettingsDict = dict[str, object]


@cache
def generate_collection_name(
    *, is_backup: bool = False, project_name: str | None = None, project_path: Path | None = None
) -> str:
    """Generate a collection name based on whether it's for backup embeddings."""
    project_name = project_name or _get_project_name()
    collection_suffix = "-backup" if is_backup else ""
    if not project_path:
        from codeweaver.core.utils import get_project_path

        project_path = get_project_path()
    from codeweaver.core.stores import get_blake_hash

    blake_hash = get_blake_hash(str(project_path.absolute()).encode("utf-8"))[:8]
    return f"{project_name}-{blake_hash}{collection_suffix}"


def ensure_iterable[T](value: Iterable[T] | T) -> Iterable[T]:
    """Ensure the value is iterable.

    Note: If you pass `ensure_iterable` a `Mapping` (like a `dict`), it will yield the keys of the mapping, not its items/values.
    """
    if isinstance(value, Iterable) and not isinstance(value, (bytes | bytearray | str)):
        yield from cast(Iterable[T], value)
    else:
        yield cast(T, value)


type DictInputTypesT = (
    dict[str, set[str]]
    | dict[LiteralStringT, set[LiteralStringT]]
    | dict[CategoryName, set[LiteralStringT]]
    | dict[LiteralStringT, set[CategoryName]]
)

type DictOutputTypesT = (
    dict[str, tuple[str, ...]]
    | dict[LiteralStringT, tuple[LiteralStringT, ...]]
    | dict[CategoryName, tuple[LiteralStringT, ...]]
    | dict[LiteralStringT, tuple[CategoryName, ...]]
)


def dict_set_to_tuple(d: DictInputTypesT) -> DictOutputTypesT:
    """Convert all sets in a dictionary to tuples."""
    return dict(  # ty: ignore[invalid-return-type, no-matching-overload]
        sorted({k: tuple(sorted(v)) for k, v in d.items()}.items()), key=lambda item: str(item[0])
    )


def rpartial[**P, R](func: Callable[P, R], *args: object, **kwargs: object) -> Callable[P, R]:
    """Return a new function that behaves like func called with the given arguments from the right."""

    def partial_right(*fargs: P.args, **fkwargs: P.kwargs) -> R:
        """Return a new partial object which when called will behave like func called with the
        given arguments.
        """
        return func(*(fargs + args), **dict(fkwargs | kwargs))

    return partial_right


def _try_for_settings() -> DictView[CodeWeaverSettingsDict] | None:
    """Try to import and return the settings map if available."""
    with contextlib.suppress(Exception):
        from codeweaver.config.settings import get_settings_map

        if (settings_map := get_settings_map()) is not None:
            from codeweaver.core.types.sentinel import Unset

            if not isinstance(settings_map, Unset):
                return settings_map  # ty:ignore[invalid-return-type]
    return None


def _get_project_name() -> str:
    """Get the project name from settings or fallback to the project path name."""
    from codeweaver.core.types.sentinel import Unset
    from codeweaver.core.utils.filesystem import get_project_path

    project_name = None
    if (
        (settings_map := _try_for_settings()) is not None
        and (project_name := settings_map.get("project_name"))
        and project_name is not Unset
    ):
        return project_name
    return get_project_path().name


__all__ = (
    "DictInputTypesT",
    "DictOutputTypesT",
    "dict_set_to_tuple",
    "ensure_iterable",
    "generate_collection_name",
    "rpartial",
)
