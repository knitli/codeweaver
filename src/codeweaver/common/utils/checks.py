# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Utility functions for type checking and validation."""

from __future__ import annotations

import inspect
import logging
import os
import sys

from importlib import metadata, util
from pathlib import Path
from typing import Any

from pydantic import BaseModel, TypeAdapter
from typing_extensions import TypeIs

from codeweaver.common.utils.git import in_codeweaver_clone


logger = logging.getLogger(__name__)


def is_pydantic_basemodel(model: Any) -> TypeIs[type[BaseModel] | BaseModel]:
    """Check if a model is a Pydantic BaseModel."""
    return isinstance(model, type) and (
        issubclass(model, BaseModel) or isinstance(model, BaseModel)
    )


def is_class(obj: Any) -> TypeIs[type[Any]]:
    """Check if an object is a class."""
    return inspect.isclass(obj)


def is_typeadapter(adapter: Any) -> TypeIs[TypeAdapter[Any] | type[TypeAdapter[Any]]]:
    """Check if an object is a Pydantic TypeAdapter."""
    return hasattr(adapter, "pydantic_complete") and hasattr(adapter, "validate_python")


def has_package(package_name: str) -> bool:
    """Check if a package is installed."""
    try:
        if util.find_spec(package_name):
            return True
    except metadata.PackageNotFoundError:
        return False
    return False


def is_debug() -> bool:
    """Check if the application is running in debug mode."""
    env = os.getenv("CODEWEAVER_DEBUG")

    explicit_true = (env in ("1", "true", "True", "TRUE")) if env is not None else False
    explicit_false = os.getenv("CODEWEAVER_DEBUG", "1") in ("false", "0", "", "False", "FALSE")

    has_debugger = (
        hasattr(sys, "gettrace") and callable(sys.gettrace) and (sys.gettrace() is not None)
    )
    repo_heuristic = in_codeweaver_clone(Path.cwd()) and not explicit_false

    return explicit_true or has_debugger or repo_heuristic


def is_ci() -> bool:
    """Check if the code is running in a Continuous Integration environment."""
    ci_indicators = [
        "APPVEYOR",
        "BUILDKITE",
        "BUILD_NUMBER",
        "CI",
        "CIRCLECI",
        "CONTINUOUS_INTEGRATION",
        "GITHUB_ACTIONS",
        "GITLAB_CI",
        "JENKINS_URL",
        "RUN_ID",
        "TF_BUILD",
        "TRAVIS",
    ]
    return any(os.getenv(var) for var in ci_indicators)


def file_is_binary(file_path: Path) -> bool:
    """Check if a file is binary by reading its initial bytes."""
    try:
        with file_path.open("rb") as f:
            initial_bytes = f.read(1024)
            if b"\0" in initial_bytes:
                return True
            text_characters = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)))
            non_text = initial_bytes.translate(None, text_characters)
            if len(non_text) / len(initial_bytes) > 0.30:
                return True
    except Exception as e:
        logger.warning("Could not read file %s to determine if binary: %s", file_path, e)
        return False
    return False


def is_test_environment() -> bool:
    """Check if the code is running in a test environment."""
    pytest_loaded = "pytest" in sys.modules
    pytest_flagged = any(arg.startswith("-m") and "pytest" in arg for arg in sys.argv)
    test_mode_disabled = os.environ.get("CODEWEAVER_TEST_MODE", "0") not in {
        "1",
        "true",
        "True",
        "TRUE",
    }
    pytest_current_test = bool(os.environ.get("PYTEST_CURRENT_TEST"))

    return pytest_loaded or (pytest_flagged and (test_mode_disabled or pytest_current_test))


__all__ = (
    "file_is_binary",
    "has_package",
    "is_ci",
    "is_class",
    "is_debug",
    "is_pydantic_basemodel",
    "is_test_environment",
    "is_typeadapter",
)
