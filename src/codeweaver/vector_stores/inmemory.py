# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""In-memory vector store implementation loosely based on langchain-core's `InMemoryVectorStore`."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel

from codeweaver.embedding.providers.base import EmbeddingProvider
from codeweaver.vector_stores.base import VectorStoreProvider


class MemoryVectorClient(BaseModel):
    """An in-memory vector store 'client'. Uses a Pydantic model for structure and serialization/deserialization."""


class MemoryVectorStoreProvider(VectorStoreProvider[None]):
    """In-memory vector store implementation using langchain-core."""

    client: Any = None
    embedder: EmbeddingProvider[Any]
    sparse_embedder: EmbeddingProvider[Any] | None = None
