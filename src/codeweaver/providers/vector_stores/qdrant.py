# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Qdrant provider for vector and hybrid search/store."""

from __future__ import annotations

import logging

from typing import ClassVar

from codeweaver.core import Provider
from codeweaver.providers.config import QdrantVectorStoreProviderSettings
from codeweaver.providers.vector_stores.qdrant_base import QdrantBaseProvider


logger = logging.getLogger(__name__)


class QdrantVectorStoreProvider(QdrantBaseProvider):
    """Qdrant vector store provider supporting local and remote deployments.

    Supports hybrid search with dense and sparse embeddings via named vectors.
    """

    _provider: ClassVar[Provider] = Provider.QDRANT  # type: ignore
    config: QdrantVectorStoreProviderSettings

    @property
    def base_url(self) -> str | None:
        """Get the base URL for the Qdrant instance from config."""
        return str(self.config.client_options.url) or "http://localhost"

    async def _init_provider(self) -> None:
        """We don't use this method at the moment for the main Qdrant provider."""


__all__ = ("QdrantVectorStoreProvider",)
