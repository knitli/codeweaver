# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Validator module for lazy imports.

Provides validation of lazy_import calls, package consistency, and import resolution.
"""

from __future__ import annotations

from tools.lazy_imports.validator.consistency import ConsistencyChecker
from tools.lazy_imports.validator.resolver import ImportResolver
from tools.lazy_imports.validator.validator import LazyImportValidator


# Alias for backward compatibility with tests
ImportValidator = LazyImportValidator

__all__ = ["ConsistencyChecker", "ImportResolver", "ImportValidator", "LazyImportValidator"]
