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
import datetime
import logging
import os
import sys

from collections.abc import Callable
from functools import cache
from pathlib import Path
from typing import TYPE_CHECKING, Literal, overload

from pydantic import UUID7


if TYPE_CHECKING:
    from codeweaver.config.types import CodeWeaverSettingsDict
    from codeweaver.core.types import CategoryName, DictView, LiteralStringT


from codeweaver.core.utils import elapsed_time_to_human_readable, get_user_config_dir, uuid7
from codeweaver.core.utils import ensure_iterable as ensure_iterable


logger = logging.getLogger(__name__)


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


def estimate_tokens(text: str | bytes, encoder: str = "cl100k_base") -> int:
    """Estimate the number of tokens in a text using tiktoken. Defaults to cl100k_base encoding."""
    import tiktoken

    encoding = tiktoken.get_encoding(encoder)
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="ignore")
    return len(encoding.encode(text))


def _check_env_var(var_name: str) -> str | None:
    """Check if an environment variable is set and return its value, or None if not set."""
    return os.getenv(var_name)


def get_possible_env_vars() -> tuple[tuple[str, str], ...] | None:
    """Get a tuple of any resolved environment variables for all providers."""
    from codeweaver.core.types.provider import Provider

    env_vars = sorted({item[1][0] for item in Provider.all_envs()})
    found_vars = tuple(
        (var, value) for var in env_vars if (value := _check_env_var(var)) is not None
    )
    return found_vars or None


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
                return settings_map
    return None


def _get_project_name() -> str:
    """Get the project name from settings or fallback to the project path name."""
    from codeweaver.core.types.sentinel import Unset
    from codeweaver.core.utils import get_project_path

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
    result = f"{project_name}-{blake_hash}{collection_suffix}"
    return result


__all__ = (
    "backup_file_path",
    "elapsed_time_to_human_readable",
    "ensure_iterable",
    "estimate_tokens",
    "generate_collection_name",
    "get_possible_env_vars",
    "get_user_config_dir",
    "rpartial",
    "uuid7",
)
