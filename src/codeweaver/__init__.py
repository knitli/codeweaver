# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""CodeWeaver: Extensible MCP server for semantic code search."""

# Suppress pydantic deprecation warnings from third-party dependencies
# This must be at the very top before any imports
import warnings

try:
    from pydantic.warnings import PydanticDeprecatedSince212

    warnings.simplefilter("ignore", PydanticDeprecatedSince212)
except ImportError:
    pass

from codeweaver._version import __version__
from codeweaver.exceptions import (
    CodeWeaverError,
    CollectionNotFoundError,
    ConfigurationError,
    DimensionMismatchError,
    IndexingError,
    InitializationError,
    MissingValueError,
    ModelSwitchError,
    PersistenceError,
    ProviderError,
    ProviderSwitchError,
    QueryError,
    RerankingProviderError,
)
from codeweaver.exceptions import ValidationError as CodeWeaverValidationError


__all__ = (
    "CodeWeaverError",
    "CodeWeaverValidationError",
    "CollectionNotFoundError",
    "ConfigurationError",
    "DimensionMismatchError",
    "IndexingError",
    "InitializationError",
    "MissingValueError",
    "ModelSwitchError",
    "PersistenceError",
    "ProviderError",
    "ProviderSwitchError",
    "QueryError",
    "RerankingProviderError",
    "__version__",
)
