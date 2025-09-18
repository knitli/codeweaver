# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""CodeWeaver: Extensible MCP server for semantic code search."""

from codeweaver._version import __version__
from codeweaver.exceptions import (
    CodeWeaverError,
    ConfigurationError,
    IndexingError,
    ProviderError,
    QueryError,
    ValidationError,
)


__all__ = (
    "CodeWeaverError",
    "ConfigurationError",
    "IndexingError",
    "ProviderError",
    "QueryError",
    "ValidationError",
    "__version__",
)
