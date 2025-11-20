# sourcery skip: avoid-global-variables
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""
Helper functions for CodeWeaver utilities.
"""

from __future__ import annotations

import contextlib
import logging
import os
import sys

from collections.abc import Callable, Iterable
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, cast

from pydantic import UUID7


if TYPE_CHECKING:
    from codeweaver.config.types import CodeWeaverSettingsDict
    from codeweaver.core.types import CategoryName, DictView, LiteralStringT


logger = logging.getLogger(__name__)

if sys.version_info < (3, 14):
    from uuid_extensions import uuid7 as uuid7_gen
else:
    from uuid import uuid7 as uuid7_gen


def uuid7() -> UUID7:
    """Generate a new UUID7."""
    return cast(
        UUID7, uuid7_gen()
    )  # it's always UUID7 and not str | int | bytes because we don't take kwargs


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
    return dict(  # ty: ignore[invalid-return-type]
        sorted({k: tuple(sorted(v)) for k, v in d.items()}.items()), key=lambda item: str(item[0])
    )


def estimate_tokens(text: str | bytes, encoder: str = "cl100k_base") -> int:
    """Estimate the number of tokens in a text using tiktoken. Defaults to cl100k_base encoding.

    Most embedding and reranking models *don't* use this encoding, but it's fast and a reasonable estimate for most texts.
    """
    import tiktoken

    encoding = tiktoken.get_encoding(encoder)
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="ignore")
    return len(encoding.encode(text))


def _check_env_var(var_name: str) -> str | None:
    """Check if an environment variable is set and return its value, or None if not set."""
    return os.getenv(var_name)


def get_possible_env_vars() -> tuple[tuple[str, str], ...] | None:
    """Get a tuple of any resolved environment variables for all providers and provider environment variables. If none are set, returns None."""
    from codeweaver.providers.provider import Provider

    env_vars = sorted({item[1][0] for item in Provider.all_envs()})
    found_vars = tuple(
        (var, value) for var in env_vars if (value := _check_env_var(var)) is not None
    )
    return found_vars or None


# Even Python's latest and greatest typing (as of 3.12+), Python can't properly express this function.
# You can't combine `TypeVarTuple` with `ParamSpec`, or use `Concatenate` to
# express combining some args and some kwargs, particularly from the right.
def rpartial[**P, R](func: Callable[P, R], *args: object, **kwargs: object) -> Callable[P, R]:
    """Return a new function that behaves like func called with the given arguments from the right.

    `rpartial` is like `functools.partial`, but it appends the given arguments to the right.
    It's useful for functions that take a variable number of arguments, especially when you want to fix keywords and modifier-type arguments, which tend to come at the end of the argument list.
    You can supply any number of contiguous positional and keyword arguments from the right.

    Examples:
        ```python
        def example_function(a: int, b: int, c: int) -> int:
            return a + b + c


        # Create a new function with the last argument fixed
        # this is equivalent to: lambda a, b: example_function(a, b, 3)
        new_function = rpartial(example_function, 3)

        # Call the new function with the remaining arguments
        result = new_function(1, 2)
        print(result)  # Output: 6
        ```

        ```python
        # with keyword arguments

        # we'll fix a positional argument and a keyword argument
        def more_complex_example(x: int, y: int, z: int = 0, flag: bool = False) -> int:
            if flag:
                return x + y + z
            return x * y * z


        new_function = rpartial(
            more_complex_example, z=5, flag=True
        )  # could also do `rpartial(more_complex_example, 5, flag=True)` if z was positional-only
        result = new_function(2, 3)  # returns 10 (2 + 3 + 5)
        ```
    """

    def partial_right(*fargs: P.args, **fkwargs: P.kwargs) -> R:
        """Return a new partial object which when called will behave like func called with the
        given arguments.
        """
        return func(*(fargs + args), **dict(fkwargs | kwargs))

    return partial_right


def ensure_iterable[T](value: Iterable[T] | T) -> Iterable[T]:
    """Ensure the value is iterable.

    Note: If you pass `ensure_iterable` a `Mapping` (like a `dict`), it will yield the keys of the mapping, not its items/values.
    """
    if isinstance(value, Iterable) and not isinstance(value, (bytes | bytearray | str)):
        yield from cast(Iterable[T], value)
    else:
        yield cast(T, value)


def get_user_config_dir(*, base_only: bool = False) -> Path:
    """Get the user configuration directory based on the operating system."""
    import platform

    if (system := platform.system()) == "Windows":
        config_dir = Path(os.getenv("APPDATA", Path("~\\AppData\\Roaming").expanduser()))
    if system == "Darwin":
        config_dir = Path.home() / "Library" / "Application Support"
    else:
        config_dir = Path(os.getenv("XDG_CONFIG_HOME", Path.home() / ".config"))
    return config_dir if base_only else config_dir / "codeweaver"


@cache
def asyncio_or_uvloop() -> object:
    """Set uvloop as the event loop policy if available and appropriate."""
    import platform
    import sys

    from importlib.util import find_spec

    if (
        sys.platform not in {"win32", "cygwin", "wasi", "ios"}
        and platform.python_implementation() == "CPython"
        and find_spec("uvloop") is not None
    ):
        import uvloop

        return uvloop
    import asyncio

    return asyncio


def _try_for_settings() -> DictView[CodeWeaverSettingsDict] | None:
    """Try to import and return the settings map if available."""
    with contextlib.suppress(Exception):
        from codeweaver.config.settings import get_settings_map

        if (settings_map := get_settings_map()) is not None:
            from codeweaver.core.types.sentinel import Unset

            if not isinstance(settings_map, Unset):
                return settings_map
    return None


def _get_project_name() -> str:
    """Get the project name from settings or fallback to the project path name."""
    from codeweaver.common.utils.git import get_project_path
    from codeweaver.core.types.sentinel import Unset

    project_name = None
    if (
        (settings_map := _try_for_settings()) is not None
        and (project_name := settings_map.get("project_name"))
        and project_name is not Unset
    ):
        return project_name
    return get_project_path().name


def backup_file_path(*, project_name: str | None = None, project_path: Path | None = None) -> Path:
    """Get the default backup file path for the vector store."""
    return (
        get_user_config_dir()
        / ".vectors"
        / "backup"
        / f"{generate_collection_name(is_backup=True, project_name=project_name, project_path=project_path)}.json"
    )


def generate_collection_name(
    *, is_backup: bool = False, project_name: str | None = None, project_path: Path | None = None
) -> str:
    """Generate a collection name based on whether it's for backup embeddings."""
    project_name = project_name or _get_project_name()
    collection_suffix = "-backup" if is_backup else ""
    if not project_path:
        from codeweaver.common.utils.git import get_project_path

        project_path = get_project_path()
    from codeweaver.core.stores import get_blake_hash

    blake_hash = get_blake_hash(str(project_path.absolute()).encode("utf-8"))[:8]
    return f"{project_name}-{blake_hash}{collection_suffix}"


__all__ = (
    "ensure_iterable",
    "estimate_tokens",
    "get_possible_env_vars",
    "get_user_config_dir",
    "rpartial",
    "uuid7",
)
