# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Type definitions for lazy import system.

These types define the data contracts used by the CLI and core components.

Note: This module re-exports types from common.types for backward compatibility
and to provide a stable public API.
"""

from __future__ import annotations

# Re-export all types from common.types
from tools.lazy_imports.common.types import (
    CacheStatistics,
    ExportGenerationResult,
    GenerationMetrics,
    ValidationError,
    ValidationMetrics,
    ValidationReport,
    ValidationWarning,
)

__all__ = (
    "CacheStatistics",
    "ExportGenerationResult",
    "GenerationMetrics",
    "ValidationError",
    "ValidationMetrics",
    "ValidationReport",
    "ValidationWarning",
)
