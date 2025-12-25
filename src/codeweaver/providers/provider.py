# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Provider enum and related functionality.

The `Provider` enum defines the available providers across the CodeWeaver project,
and includes methods for validating providers, checking capabilities, and retrieving
provider-specific settings.

A companion enum, `ProviderKind`, categorizes providers by their capabilities,
such as `embedding`, `sparse_embedding`, `reranking`, `vector_store`, `agent`, and `data`.

The `Provider` enum also includes methods for retrieving some provider-specific information, such as environment variables used by the provider's client that are not part of CodeWeaver's settings.
"""

from codeweaver.core.types.env import EnvVarInfo as ProviderEnvVarInfo
from codeweaver.core.types.provider import Provider, ProviderEnvVars, ProviderKind


__all__ = ("Provider", "ProviderEnvVarInfo", "ProviderEnvVars", "ProviderKind")
