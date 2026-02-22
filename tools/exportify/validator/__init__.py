# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Validator module for lazy imports.

Provides validation of lazy_import calls, package consistency, and import resolution.
"""

from __future__ import annotations

from tools.exportify.validator.consistency import ConsistencyChecker
from tools.exportify.validator.resolver import ImportResolver
from tools.exportify.validator.validator import LazyImportValidator


# Alias for backward compatibility with tests
ImportValidator = LazyImportValidator

__all__ = ["ConsistencyChecker", "ImportResolver", "ImportValidator", "LazyImportValidator"]
