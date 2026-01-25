# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Tests for the new dict-based QueryResult type."""

import pytest

from codeweaver.core.types import QueryResult
from codeweaver.providers import SparseEmbedding


@pytest.mark.unit
class TestQueryResult:
    """Test the new dict-based QueryResult."""

    def test_create_with_primary_dense(self):
        """Test creating QueryResult with primary dense embedding."""
        dense_vector = [0.1, 0.2, 0.3]
        result = QueryResult(vectors={"primary": dense_vector})

        assert "primary" in result.intents
        assert result["primary"] == dense_vector
        assert result.get("primary") == dense_vector

    def test_create_with_sparse(self):
        """Test creating QueryResult with sparse embedding."""
        sparse = SparseEmbedding(indices=[1, 2, 3], values=[0.8, 0.7, 0.6])
        result = QueryResult(vectors={"sparse": sparse})

        assert "sparse" in result.intents
        assert result["sparse"] == sparse
        assert result.get("sparse") == sparse

    def test_create_with_multiple_intents(self):
        """Test creating QueryResult with multiple embedding intents."""
        dense_vector = [0.1, 0.2, 0.3]
        sparse = SparseEmbedding(indices=[1, 2], values=[0.9, 0.8])

        result = QueryResult(vectors={"primary": dense_vector, "sparse": sparse})

        assert len(result.intents) == 2
        assert "primary" in result.intents
        assert "sparse" in result.intents
        assert result["primary"] == dense_vector
        assert result["sparse"] == sparse

    def test_get_with_default(self):
        """Test safe access with default value."""
        result = QueryResult(vectors={"primary": [0.1, 0.2]})

        assert result.get("primary") == [0.1, 0.2]
        assert result.get("nonexistent") is None
        assert result.get("nonexistent", "default") == "default"

    def test_getitem_raises_on_missing(self):
        """Test that dict-like access raises KeyError on missing intent."""
        result = QueryResult(vectors={"primary": [0.1, 0.2]})

        with pytest.raises(KeyError):
            _ = result["nonexistent"]

    def test_intents_property(self):
        """Test intents property returns all available intents."""
        result = QueryResult(
            vectors={
                "primary": [0.1, 0.2],
                "sparse": SparseEmbedding(indices=[1], values=[0.9]),
                "backup": [0.3, 0.4],
            }
        )

        intents = result.intents
        assert len(intents) == 3
        assert "primary" in intents
        assert "sparse" in intents
        assert "backup" in intents

    def test_empty_query_result(self):
        """Test creating empty QueryResult."""
        result = QueryResult(vectors={})

        assert len(result.intents) == 0
        assert result.get("anything") is None

    def test_dict_access_pattern(self):
        """Test that QueryResult supports dict-like access patterns."""
        result = QueryResult(
            vectors={"primary": [0.1, 0.2], "sparse": SparseEmbedding(indices=[1], values=[0.9])}
        )

        # Test iteration over intents
        intent_list = list(result.intents)
        assert len(intent_list) == 2

        # Test get with default
        assert result.get("primary") is not None
        assert result.get("nonexistent", []) == []

        # Test membership
        assert "primary" in result.intents
        assert "nonexistent" not in result.intents
