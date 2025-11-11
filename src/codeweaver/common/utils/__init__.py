# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Common utility functions and classes used across the CodeWeaver project."""

from __future__ import annotations

from importlib import import_module
from types import MappingProxyType
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    # Import everything for IDE and type checker support
    # These imports are never executed at runtime, only during type checking
    from codeweaver.common.utils.checks import (
        file_is_binary,
        has_package,
        is_ci,
        is_class,
        is_debug,
        is_pydantic_basemodel,
        is_test_environment,
        is_typeadapter,
    )
    from codeweaver.common.utils.git import (
        get_git_branch,
        get_git_revision,
        get_project_path,
        in_codeweaver_clone,
        is_git_dir,
        set_relative_path,
        try_git_rev_parse,
    )
    from codeweaver.common.utils.lazy_importer import LazyImport, lazy_import
    from codeweaver.common.utils.normalize import normalize_ext, sanitize_unicode
    from codeweaver.common.utils.utils import (
        ensure_iterable,
        estimate_tokens,
        get_possible_env_vars,
        get_user_config_dir,
        rpartial,
        uuid7,
    )

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "file_is_binary": (__spec__.parent, "checks"),
    "has_package": (__spec__.parent, "checks"),
    "is_ci": (__spec__.parent, "checks"),
    "is_class": (__spec__.parent, "checks"),
    "is_debug": (__spec__.parent, "checks"),
    "is_pydantic_basemodel": (__spec__.parent, "checks"),
    "is_test_environment": (__spec__.parent, "checks"),
    "is_typeadapter": (__spec__.parent, "checks"),
    "get_git_branch": (__spec__.parent, "git"),
    "get_git_revision": (__spec__.parent, "git"),
    "get_project_path": (__spec__.parent, "git"),
    "in_codeweaver_clone": (__spec__.parent, "git"),
    "is_git_dir": (__spec__.parent, "git"),
    "set_relative_path": (__spec__.parent, "git"),
    "try_git_rev_parse": (__spec__.parent, "git"),
    "LazyImport": (__spec__.parent, "lazy_importer"),
    "lazy_import": (__spec__.parent, "lazy_importer"),
    "normalize_ext": (__spec__.parent, "normalize"),
    "sanitize_unicode": (__spec__.parent, "normalize"),
    "ensure_iterable": (__spec__.parent, "utils"),
    "estimate_tokens": (__spec__.parent, "utils"),
    "get_possible_env_vars": (__spec__.parent, "utils"),
    "get_user_config_dir": (__spec__.parent, "utils"),
    "rpartial": (__spec__.parent, "utils"),
    "uuid7": (__spec__.parent, "utils"),
})


def __getattr__(name: str) -> object:
    """Dynamically import submodules and classes for the utils package."""
    if name in _dynamic_imports:
        module_name, submodule_name = _dynamic_imports[name]
        module = import_module(f"{module_name}.{submodule_name}")
        result = getattr(module, name)
        globals()[name] = result  # Cache in globals for future access
        return result
    if globals().get(name) is not None:
        return globals()[name]
    raise AttributeError(f"module {__name__} has no attribute {name}")


__all__ = (
    "LazyImport",
    "ensure_iterable",
    "estimate_tokens",
    "file_is_binary",
    "get_git_branch",
    "get_git_revision",
    "get_possible_env_vars",
    "get_project_path",
    "get_user_config_dir",
    "has_package",
    "in_codeweaver_clone",
    "is_ci",
    "is_class",
    "is_debug",
    "is_git_dir",
    "is_pydantic_basemodel",
    "is_test_environment",
    "is_typeadapter",
    "lazy_import",
    "normalize_ext",
    "rpartial",
    "sanitize_unicode",
    "set_relative_path",
    "try_git_rev_parse",
    "uuid7",
)


def __dir__() -> list[str]:
    """List available attributes for the module."""
    return list(__all__)
