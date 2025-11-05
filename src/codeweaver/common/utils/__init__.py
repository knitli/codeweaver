# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Common utility functions and classes used across the CodeWeaver project."""

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
    MISSING,
    Missing,
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


__all__ = (
    "MISSING",
    "LazyImport",
    "Missing",
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
