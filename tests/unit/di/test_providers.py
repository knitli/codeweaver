# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

from unittest.mock import MagicMock, patch

import pytest

from codeweaver.di.providers import (
    get_embedding_provider,
    get_reranking_provider,
    get_sparse_embedding_provider,
    get_vector_store,
)


@pytest.mark.asyncio
async def test_get_embedding_provider():
    mock_registry = MagicMock()
    mock_registry.get_provider_enum_for.return_value = "voyage"
    mock_instance = MagicMock()
    mock_registry.get_provider_instance.return_value = mock_instance

    with patch("codeweaver.common.registry.get_provider_registry", return_value=mock_registry):
        result = await get_embedding_provider()
        assert result is mock_instance
        mock_registry.get_provider_enum_for.assert_called_with("embedding")


@pytest.mark.asyncio
async def test_get_sparse_embedding_provider():
    mock_registry = MagicMock()
    mock_registry.get_provider_enum_for.return_value = "fastembed"
    mock_instance = MagicMock()
    mock_registry.get_provider_instance.return_value = mock_instance

    with patch("codeweaver.common.registry.get_provider_registry", return_value=mock_registry):
        result = await get_sparse_embedding_provider()
        assert result is mock_instance
        mock_registry.get_provider_enum_for.assert_called_with("sparse_embedding")


@pytest.mark.asyncio
async def test_get_vector_store():
    mock_registry = MagicMock()
    mock_registry.get_provider_enum_for.return_value = "qdrant"
    mock_instance = MagicMock()
    mock_registry.get_provider_instance.return_value = mock_instance

    with patch("codeweaver.common.registry.get_provider_registry", return_value=mock_registry):
        result = await get_vector_store()
        assert result is mock_instance
        mock_registry.get_provider_enum_for.assert_called_with("vector_store")


@pytest.mark.asyncio
async def test_get_reranking_provider():
    mock_registry = MagicMock()
    mock_registry.get_provider_enum_for.return_value = "voyage"
    mock_instance = MagicMock()
    mock_registry.get_provider_instance.return_value = mock_instance

    with patch("codeweaver.common.registry.get_provider_registry", return_value=mock_registry):
        result = await get_reranking_provider()
        assert result is mock_instance
        mock_registry.get_provider_enum_for.assert_called_with("reranking")
