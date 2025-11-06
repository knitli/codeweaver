# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""CodeWeaver: Extensible MCP server for semantic code search."""

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
