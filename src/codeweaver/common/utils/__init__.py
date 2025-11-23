# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Common utility functions and classes used across the CodeWeaver project."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from codeweaver.common.utils.lazy_importer import LazyImport, create_lazy_getattr, lazy_import


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
        is_wsl,
        is_wsl_vscode,
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
    from codeweaver.common.utils.normalize import normalize_ext, sanitize_unicode
    from codeweaver.common.utils.procs import (
        asyncio_or_uvloop,
        get_optimal_workers,
        low_priority,
        very_low_priority,
    )
    from codeweaver.common.utils.textify import (
        format_docstring,
        format_signature,
        format_snippet_name,
        humanize,
        to_lowly_lowercase,
        to_tokens,
    )
    from codeweaver.common.utils.utils import (
        backup_file_path,
        ensure_iterable,
        estimate_tokens,
        generate_collection_name,
        get_possible_env_vars,
        get_user_config_dir,
        rpartial,
        uuid7,
    )

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "asyncio_or_uvloop": (__spec__.parent, "proc"),
    "backup_file_path": (__spec__.parent, "utils"),
    "ensure_iterable": (__spec__.parent, "utils"),
    "estimate_tokens": (__spec__.parent, "utils"),
    "file_is_binary": (__spec__.parent, "checks"),
    "format_docstring": (__spec__.parent, "textify"),
    "format_signature": (__spec__.parent, "textify"),
    "format_snippet_name": (__spec__.parent, "textify"),
    "generate_collection_name": (__spec__.parent, "utils"),
    "get_git_branch": (__spec__.parent, "git"),
    "get_git_revision": (__spec__.parent, "git"),
    "get_optimal_workers": (__spec__.parent, "procs"),
    "get_possible_env_vars": (__spec__.parent, "utils"),
    "get_project_path": (__spec__.parent, "git"),
    "get_user_config_dir": (__spec__.parent, "utils"),
    "has_package": (__spec__.parent, "checks"),
    "humanize": (__spec__.parent, "textify"),
    "in_codeweaver_clone": (__spec__.parent, "git"),
    "is_ci": (__spec__.parent, "checks"),
    "is_class": (__spec__.parent, "checks"),
    "is_debug": (__spec__.parent, "checks"),
    "is_git_dir": (__spec__.parent, "git"),
    "is_pydantic_basemodel": (__spec__.parent, "checks"),
    "is_test_environment": (__spec__.parent, "checks"),
    "is_typeadapter": (__spec__.parent, "checks"),
    "is_wsl": (__spec__.parent, "checks"),
    "is_wsl_vscode": (__spec__.parent, "checks"),
    "low_priority": (__spec__.parent, "procs"),
    "normalize_ext": (__spec__.parent, "normalize"),
    "rpartial": (__spec__.parent, "utils"),
    "sanitize_unicode": (__spec__.parent, "normalize"),
    "set_relative_path": (__spec__.parent, "git"),
    "to_lowly_lowercase": (__spec__.parent, "textify"),
    "to_tokens": (__spec__.parent, "textify"),
    "try_git_rev_parse": (__spec__.parent, "git"),
    "uuid7": (__spec__.parent, "utils"),
    "very_low_priority": (__spec__.parent, "procs"),
})


__getattr__ = create_lazy_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    "LazyImport",
    "asyncio_or_uvloop",
    "backup_file_path",
    "create_lazy_getattr",
    "ensure_iterable",
    "estimate_tokens",
    "file_is_binary",
    "format_docstring",
    "format_signature",
    "format_snippet_name",
    "generate_collection_name",
    "get_git_branch",
    "get_git_revision",
    "get_optimal_workers",
    "get_possible_env_vars",
    "get_project_path",
    "get_user_config_dir",
    "has_package",
    "humanize",
    "in_codeweaver_clone",
    "is_ci",
    "is_class",
    "is_debug",
    "is_git_dir",
    "is_pydantic_basemodel",
    "is_test_environment",
    "is_typeadapter",
    "is_wsl",
    "is_wsl_vscode",
    "lazy_import",
    "low_priority",
    "normalize_ext",
    "rpartial",
    "sanitize_unicode",
    "set_relative_path",
    "to_lowly_lowercase",
    "to_tokens",
    "try_git_rev_parse",
    "uuid7",
    "very_low_priority",
)


def __dir__() -> list[str]:
    """List available attributes for the module."""
    return list(__all__)
