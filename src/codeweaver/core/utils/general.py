# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""General utilities for CodeWeaver."""

from __future__ import annotations

import contextlib
import os

from collections.abc import Callable, Iterable
from functools import cache
from pathlib import Path
from typing import cast

from codeweaver.core.types import BaseCodeWeaverSettings
from codeweaver.core.types.aliases import CategoryName, LiteralStringT


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
        return func(*(fargs + args), **dict(fkwargs | kwargs))  # ty:ignore[invalid-argument-type]

    return partial_right


def _try_for_settings() -> BaseCodeWeaverSettings | None:
    """Try to import and return the settings map if available."""
    with contextlib.suppress(Exception):
        from codeweaver.core.config import get_settings

        if (settings := get_settings()) is not None:
            from codeweaver.core.types.sentinel import Unset

            if not isinstance(settings, Unset):
                return settings  # ty:ignore[invalid-return-type]
    return None


def _get_project_name() -> str:
    """Get the project name from settings or fallback to the project path name."""
    from codeweaver.core.types.sentinel import Unset
    from codeweaver.core.utils.filesystem import get_project_path

    if (env_project_name := os.environ.get("CODEWEAVER_PROJECT_NAME")) is not None:
        return env_project_name

    project_name = None
    if (
        (settings := _try_for_settings()) is not None
        and (project_name := settings.project_name) is not None
        and project_name is not Unset
    ):
        return cast(str, project_name)
    return get_project_path().name


def supported_languages() -> list[str]:
    """Return the supported languages."""
    from codeweaver.core.file_extensions import ALL_LANGUAGES
    from codeweaver.core.language import ConfigLanguage, SemanticSearchLanguage

    semantic = {lang.variable for lang in SemanticSearchLanguage}
    all_languages = {str(lang) for lang in ALL_LANGUAGES if str(lang).lower() not in semantic}
    return sorted(
        all_languages
        | {f"{lang} (AST support)" for lang in SemanticSearchLanguage}
        | {lang.variable for lang in ConfigLanguage if not lang.is_semantic_search_language}
    )


def supported_language_count() -> int:
    """Return the count of supported languages."""
    return len(supported_languages())


__all__ = (
    "DictInputTypesT",
    "DictOutputTypesT",
    "dict_set_to_tuple",
    "ensure_iterable",
    "generate_collection_name",
    "rpartial",
    "supported_language_count",
    "supported_languages",
)
