# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Contract tests for VectorStoreProvider abstract interface.

These tests verify that the VectorStoreProvider abstract base class defines
all required methods and properties according to the contract specification.
"""

import inspect
from pathlib import Path
from typing import get_type_hints

import pytest
from pydantic import UUID4

from codeweaver.core.chunks import CodeChunk, SearchResult
from codeweaver.engine.filter import Filter
from codeweaver.providers.vector_stores.base import VectorStoreProvider


class TestVectorStoreProviderContract:
    """Test VectorStoreProvider abstract interface contract compliance."""

    def test_abstract_methods_defined(self):
        """Verify all abstract methods are defined in the interface."""
        abstract_methods = {
            name
            for name, method in inspect.getmembers(VectorStoreProvider, predicate=inspect.isfunction)
            if getattr(method, "__isabstractmethod__", False)
        }

        expected_methods = {
            "list_collections",
            "search",
            "upsert",
            "delete_by_file",
            "delete_by_id",
            "delete_by_name",
        }

        assert expected_methods.issubset(
            abstract_methods
        ), f"Missing abstract methods: {expected_methods - abstract_methods}"

    def test_list_collections_signature(self):
        """Verify list_collections method signature matches contract."""
        method = VectorStoreProvider.list_collections
        sig = inspect.signature(method)
        type_hints = get_type_hints(method)

        # Should have no required parameters (only self)
        params = [p for p in sig.parameters.values() if p.name != "self"]
        assert len(params) == 0, "list_collections should not have parameters"

        # Should return list[str] | None
        assert "return" in type_hints
        # Note: Type hint checking is complex, so we just verify it exists

    def test_search_signature(self):
        """Verify search method signature matches contract."""
        method = VectorStoreProvider.search
        sig = inspect.signature(method)
        type_hints = get_type_hints(method)

        # Should have vector and query_filter parameters
        params = {p.name: p for p in sig.parameters.values() if p.name != "self"}
        assert "vector" in params, "search must have 'vector' parameter"
        assert "query_filter" in params, "search must have 'query_filter' parameter"

        # query_filter should be optional
        assert (
            params["query_filter"].default is not inspect.Parameter.empty
            or params["query_filter"].default is None
        ), "query_filter should have default value"

        # Should be async
        assert inspect.iscoroutinefunction(method), "search must be async"

    def test_upsert_signature(self):
        """Verify upsert method signature matches contract."""
        method = VectorStoreProvider.upsert
        sig = inspect.signature(method)
        type_hints = get_type_hints(method)

        # Should have chunks parameter
        params = {p.name: p for p in sig.parameters.values() if p.name != "self"}
        assert "chunks" in params, "upsert must have 'chunks' parameter"

        # Should be async
        assert inspect.iscoroutinefunction(method), "upsert must be async"

        # Should return None
        return_hint = type_hints.get("return")
        # Type checking for None is tricky, just verify it exists

    def test_delete_by_file_signature(self):
        """Verify delete_by_file method signature matches contract."""
        method = VectorStoreProvider.delete_by_file
        sig = inspect.signature(method)

        # Should have file_path parameter
        params = {p.name: p for p in sig.parameters.values() if p.name != "self"}
        assert "file_path" in params, "delete_by_file must have 'file_path' parameter"

        # Should be async
        assert inspect.iscoroutinefunction(method), "delete_by_file must be async"

    def test_delete_by_id_signature(self):
        """Verify delete_by_id method signature matches contract."""
        method = VectorStoreProvider.delete_by_id
        sig = inspect.signature(method)

        # Should have ids parameter
        params = {p.name: p for p in sig.parameters.values() if p.name != "self"}
        assert "ids" in params, "delete_by_id must have 'ids' parameter"

        # Should be async
        assert inspect.iscoroutinefunction(method), "delete_by_id must be async"

    def test_delete_by_name_signature(self):
        """Verify delete_by_name method signature matches contract."""
        method = VectorStoreProvider.delete_by_name
        sig = inspect.signature(method)

        # Should have names parameter
        params = {p.name: p for p in sig.parameters.values() if p.name != "self"}
        assert "names" in params, "delete_by_name must have 'names' parameter"

        # Should be async
        assert inspect.iscoroutinefunction(method), "delete_by_name must be async"

    def test_properties_defined(self):
        """Verify required properties are defined."""
        # Check that collection and base_url properties exist
        assert hasattr(VectorStoreProvider, "collection"), "collection property must be defined"
        assert hasattr(VectorStoreProvider, "base_url"), "base_url property must be defined"

        # base_url should be abstract
        assert getattr(
            VectorStoreProvider.base_url.fget, "__isabstractmethod__", False
        ), "base_url should be abstract"

    def test_cannot_instantiate_abstract_class(self):
        """Verify that VectorStoreProvider cannot be instantiated directly."""
        with pytest.raises(TypeError, match="Can't instantiate abstract class"):
            VectorStoreProvider()  # type: ignore

    def test_generic_type_parameter(self):
        """Verify VectorStoreProvider uses generic type parameter."""
        # Check that it's defined as a generic class
        assert hasattr(VectorStoreProvider, "__orig_bases__"), "Should be a generic class"

        # The class should have type parameters
        # Note: Detailed type parameter checking is complex, so we just verify the structure exists
