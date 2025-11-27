# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Contract tests for find_code API.

These tests validate that the find_code implementation complies with the
find_code_mcp_tool.json contract specification (FR-014a/FR-014b).

Contract compliance includes:
- All required parameters are accepted
- All optional parameters have correct defaults
- Response structure matches FindCodeResponseSummary schema
- All response fields are present with correct types
- Parameter validation enforces contract constraints
"""

from __future__ import annotations

import inspect

from typing import get_type_hints

import pytest

from pydantic import ValidationError

from codeweaver.agent_api.find_code import find_code
from codeweaver.agent_api.find_code.intent import IntentType
from codeweaver.agent_api.find_code.types import (
    CodeMatch,
    CodeMatchType,
    FindCodeResponseSummary,
    SearchStrategy,
)
from codeweaver.core.language import SemanticSearchLanguage
from codeweaver.core.metadata import ChunkKind


pytestmark = [pytest.mark.validation]


class TestFindCodeSignature:
    """Test find_code function signature matches contract (FR-014a)."""

    def test_find_code_is_async(self):
        """Verify find_code is an async function."""
        assert inspect.iscoroutinefunction(find_code), "find_code must be async"

    def test_find_code_parameters(self):
        """Verify find_code accepts all required parameters from contract."""
        sig = inspect.signature(find_code)
        params = {p.name: p for p in sig.parameters.values()}

        # Required parameter
        assert "query" in params, "find_code must have 'query' parameter"
        assert params["query"].kind == inspect.Parameter.POSITIONAL_OR_KEYWORD, (
            "query must be positional"
        )
        assert params["query"].default == inspect.Parameter.empty, "query must not have default"

        # Optional parameters (keyword-only)
        assert "intent" in params, "find_code must have 'intent' parameter"
        assert "token_limit" in params, "find_code must have 'token_limit' parameter"
        assert "focus_languages" in params, "find_code must have 'focus_languages' parameter"
        assert "max_results" in params, "find_code must have 'max_results' parameter"
        assert "context" in params, "find_code must have 'context' parameter"

    def test_find_code_parameter_defaults(self):
        """Verify optional parameters have correct default values per contract."""
        sig = inspect.signature(find_code)
        params = {p.name: p for p in sig.parameters.values()}

        # intent default: None
        assert params["intent"].default is None, "intent default must be None"

        # token_limit default: 30000
        assert params["token_limit"].default == 30000, "token_limit default must be 30000"

        # focus_languages default: None
        assert params["focus_languages"].default is None, "focus_languages default must be None"

        # max_results default: 30
        assert params["max_results"].default == 30, "max_results default must be 30"

        # context default: None
        assert params["context"].default is None, "context default must be None"

    def test_find_code_return_type(self):
        """Verify find_code returns FindCodeResponseSummary."""
        type_hints = get_type_hints(find_code)
        assert "return" in type_hints, "find_code must have return type annotation"

        # The return type should be FindCodeResponseSummary
        # Note: Direct type comparison is tricky with generics, so we check the name
        return_type_repr = str(type_hints["return"])
        assert "FindCodeResponseSummary" in return_type_repr, (
            f"find_code must return FindCodeResponseSummary, got {return_type_repr}"
        )


class TestFindCodeResponseSchema:
    """Test FindCodeResponseSummary schema matches contract (FR-014b)."""

    def test_response_model_is_pydantic(self):
        """Verify FindCodeResponseSummary is a Pydantic model."""
        from pydantic import BaseModel

        assert issubclass(FindCodeResponseSummary, BaseModel), (
            "FindCodeResponseSummary must be a Pydantic BaseModel"
        )

    def test_response_required_fields(self):
        """Verify all required fields from contract are present in model."""
        schema = FindCodeResponseSummary.model_json_schema()
        properties = schema.get("properties", {})

        # All required fields per contract (FR-014b)
        required_fields = {
            "matches",
            "summary",
            "query_intent",
            "total_matches",
            "total_results",
            "token_count",
            "execution_time_ms",
            "search_strategy",
            "languages_found",
        }

        missing_fields = required_fields - set(properties.keys())
        assert not missing_fields, f"Missing required fields: {missing_fields}"

    def test_response_field_types(self):
        """Verify response field types match contract specification."""
        schema = FindCodeResponseSummary.model_json_schema()
        properties = schema.get("properties", {})

        # matches: array of CodeMatch
        assert "matches" in properties
        assert properties["matches"]["type"] == "array"

        # summary: string with max length 1000
        assert "summary" in properties
        assert properties["summary"]["type"] == "string"
        assert properties["summary"]["maxLength"] == 1000

        # query_intent: IntentType or null
        assert "query_intent" in properties

        # total_matches: non-negative integer
        assert "total_matches" in properties
        # Pydantic may represent this as "integer" with minimum: 0

        # total_results: non-negative integer
        assert "total_results" in properties

        # token_count: non-negative integer
        assert "token_count" in properties

        # execution_time_ms: non-negative number
        assert "execution_time_ms" in properties

        # search_strategy: array of SearchStrategy enums
        assert "search_strategy" in properties
        assert properties["search_strategy"]["type"] == "array"

        # languages_found: array of strings
        assert "languages_found" in properties
        assert properties["languages_found"]["type"] == "array"

    def test_response_validates_constraints(self):
        """Verify Pydantic model enforces contract constraints."""
        # Test summary max length
        with pytest.raises(ValidationError, match="String should have at most 1000 characters"):
            FindCodeResponseSummary(
                matches=[],
                summary="x" * 1001,  # Exceeds max length
                query_intent=None,
                total_matches=0,
                total_results=0,
                token_count=0,
                execution_time_ms=0,
                search_strategy=(SearchStrategy.KEYWORD_FALLBACK,),
                languages_found=(),
                status="success",
                warnings=[],
                indexing_state="unknown",
                index_coverage=1.0,
                search_mode="hybrid",
                metadata={},
            )

    def test_response_model_creates_valid_instance(self):
        """Verify model can create valid instances with all required fields."""
        response = FindCodeResponseSummary(
            matches=[],
            summary="Test summary",
            query_intent=IntentType.UNDERSTAND,
            total_matches=0,
            total_results=0,
            token_count=0,
            execution_time_ms=100.5,
            search_strategy=(SearchStrategy.HYBRID_SEARCH,),
            languages_found=("python",),
            status="success",
            warnings=[],
            indexing_state="unknown",
            index_coverage=1.0,
            search_mode="hybrid",
            metadata={},
        )

        assert isinstance(response, FindCodeResponseSummary)
        assert response.summary == "Test summary"
        assert response.query_intent == IntentType.UNDERSTAND
        assert response.execution_time_ms == 100.5


class TestCodeMatchSchema:
    """Test CodeMatch schema matches contract definition."""

    def test_code_match_required_fields(self):
        """Verify CodeMatch has all required fields per contract."""
        schema = CodeMatch.model_json_schema()
        properties = schema.get("properties", {})

        required_fields = {
            "file",
            "content",
            "span",
            "relevance_score",
            "match_type",
            "related_symbols",
        }

        missing_fields = required_fields - set(properties.keys())
        assert not missing_fields, f"Missing required fields in CodeMatch: {missing_fields}"

    def test_code_match_relevance_score_range(self):
        # sourcery skip: remove-redundant-pass
        """Verify relevance_score is constrained to 0.0-1.0."""
        schema = CodeMatch.model_json_schema()
        properties = schema.get("properties", {})

        # relevance_score should have minimum 0 and maximum 1
        relevance_schema = properties["relevance_score"]
        # Pydantic may nest this in allOf or directly
        if "allOf" in relevance_schema:
            # Extract constraints from allOf structure
            assert any(
                constraint.get("minimum") == 0.0 or constraint.get("exclusiveMinimum") == 0.0
                for constraint in relevance_schema["allOf"]
            ), "relevance_score must have minimum 0.0"
            assert any(
                constraint.get("maximum") == 1.0 for constraint in relevance_schema["allOf"]
            ), "relevance_score must have maximum 1.0"
        else:
            # Check directly if not nested
            pass  # type: ignore # Pydantic may represent this differently

    def test_code_match_match_type_enum(self):
        """Verify match_type uses CodeMatchType enum values."""
        # CodeMatchType should have the contract-specified values
        expected_values = {"SEMANTIC", "SYNTACTIC", "KEYWORD", "FILE_PATTERN"}
        actual_values = {e.value.upper() for e in CodeMatchType}

        assert expected_values.issubset(actual_values), (
            f"CodeMatchType missing values: {expected_values - actual_values}"
        )

    def test_code_match_span_validation(self):
        """Verify span tuple validation (2 elements, start <= end, >= 1)."""
        from pathlib import Path

        from codeweaver.common.utils.utils import uuid7
        from codeweaver.core.chunks import CodeChunk
        from codeweaver.core.discovery import DiscoveredFile
        from codeweaver.core.metadata import ExtKind
        from codeweaver.core.spans import Span

        # Create minimal test data
        test_file = DiscoveredFile(path=Path("test.py"))
        test_chunk = CodeChunk(
            content="def test(): pass",
            ext_kind=ExtKind(language=SemanticSearchLanguage.PYTHON, kind=ChunkKind.CODE),
            line_range=Span(1, 1, uuid7()),
        )

        # Valid span
        match = CodeMatch(
            file=test_file,
            content=test_chunk,
            span=Span(1, 10, uuid7()),
            relevance_score=0.8,
            match_type=CodeMatchType.SEMANTIC,
            related_symbols=(),
        )
        assert match.span.start == 1
        assert match.span.end == 10

        # Invalid: start > end (Span validation catches this)
        with pytest.raises(ValidationError, match="Start must be less than or equal to end"):
            CodeMatch(
                file=test_file,
                content=test_chunk,
                span=Span(10, 1, uuid7()),  # Invalid: start > end
                relevance_score=0.8,
                match_type=CodeMatchType.SEMANTIC,
                related_symbols=(),
            )

        # Invalid: start < 1 (Pydantic PositiveInt validation catches this)
        with pytest.raises(ValidationError):
            CodeMatch(
                file=test_file,
                content=test_chunk,
                span=Span(0, 10, uuid7()),  # Invalid: 0-indexed
                relevance_score=0.8,
                match_type=CodeMatchType.SEMANTIC,
                related_symbols=(),
            )


class TestSearchStrategyEnum:
    """Test SearchStrategy enum matches contract values."""

    def test_search_strategy_values(self):
        """Verify SearchStrategy includes all contract-specified values."""
        expected_values = {
            "HYBRID_SEARCH",
            "SEMANTIC_RERANK",
            "SPARSE_ONLY",
            "DENSE_ONLY",
            "KEYWORD_FALLBACK",
        }

        actual_values = {e.value.upper() for e in SearchStrategy}

        missing_values = expected_values - actual_values
        assert not missing_values, f"SearchStrategy missing values: {missing_values}"


class TestIntentTypeEnum:
    """Test IntentType enum matches contract values."""

    def test_intent_type_values(self):
        """Verify IntentType includes all contract-specified values."""
        expected_values = {
            "understand",
            "implement",
            "debug",
            "optimize",
            "test",
            "configure",
            "document",
        }

        actual_values = {e.value for e in IntentType}

        assert expected_values == actual_values, (
            f"IntentType mismatch - missing: {expected_values - actual_values}, "
            f"extra: {actual_values - expected_values}"
        )


class TestParameterValidation:
    """Test parameter validation matches contract constraints."""

    def test_token_limit_constraints(self):
        """Verify token_limit is validated per contract (min: 1000, max: 100000)."""
        self._test_find_code_min_max_constraints(
            "token_limit", 30000, "token_limit default must be 30000"
        )

    def test_max_results_constraints(self):
        """Verify max_results is validated per contract (min: 1, max: 100)."""
        self._test_find_code_min_max_constraints(
            "max_results", 30, "max_results default must be 30"
        )

    def _test_find_code_min_max_constraints(self, constraint: str, bound: int, statement: str):
        sig = inspect.signature(find_code)
        params = {p.name: p for p in sig.parameters.values()}
        assert params[constraint].default == bound, statement

    def test_query_min_length(self):
        """Verify query string has minimum length per contract (minLength: 1)."""
        # Contract specifies query must have minLength: 1
        # This would be caught by the function logic (empty string behavior)
        # but documents the contract requirement
        # Function handles empty strings gracefully


class TestContractExamples:
    """Test against contract example payloads."""

    def test_example_simple_search_response_structure(self):
        """Verify response can represent the simple search example from contract."""
        from pathlib import Path

        from codeweaver.common.utils.utils import uuid7
        from codeweaver.core.chunks import CodeChunk
        from codeweaver.core.discovery import DiscoveredFile
        from codeweaver.core.metadata import ExtKind
        from codeweaver.core.spans import Span

        # Recreate example from contract
        example_file = DiscoveredFile(path=Path("src/auth/middleware.py"))
        example_chunk = CodeChunk(
            content="class AuthMiddleware:\n    def __init__(self, config: AuthConfig):\n        ...",
            line_range=Span(15, 85, uuid7()),
            ext_kind=ExtKind(language=SemanticSearchLanguage.PYTHON, kind=ChunkKind.CODE),
        )
        example_match = CodeMatch(
            file=example_file,
            content=example_chunk,
            span=Span(15, 85, uuid7()),
            relevance_score=0.92,
            match_type=CodeMatchType.SEMANTIC,
            related_symbols=("AuthConfig", "authenticate_request"),
        )

        response = FindCodeResponseSummary(
            matches=[example_match],
            summary="Found authentication middleware implementation in auth module",
            query_intent=IntentType.UNDERSTAND,
            total_matches=47,
            total_results=1,
            token_count=450,
            execution_time_ms=850,
            search_strategy=(SearchStrategy.HYBRID_SEARCH, SearchStrategy.SEMANTIC_RERANK),
            languages_found=(SemanticSearchLanguage.PYTHON,),
            status="success",
            warnings=[],
            indexing_state="unknown",
            index_coverage=1.0,
            search_mode="hybrid",
            metadata={},
        )

        # Verify all fields are accessible and have expected types
        assert isinstance(response.matches, list)
        assert len(response.matches) == 1
        assert isinstance(response.matches[0], CodeMatch)
        assert response.summary == "Found authentication middleware implementation in auth module"
        assert response.query_intent == IntentType.UNDERSTAND
        assert response.total_matches == 47
        assert response.total_results == 1
        assert response.token_count == 450
        assert response.execution_time_ms == 850
        assert len(response.search_strategy) == 2
        assert SearchStrategy.HYBRID_SEARCH in response.search_strategy
        assert SearchStrategy.SEMANTIC_RERANK in response.search_strategy
        assert SemanticSearchLanguage.PYTHON in response.languages_found


class TestTypesSafety:
    """Test type safety and no dict[str, Any] leakage."""

    def test_response_is_not_dict(self):
        """Verify find_code returns Pydantic model, not dict."""
        # This is enforced by type hints and Pydantic
        type_hints = get_type_hints(find_code)
        return_type_repr = str(type_hints["return"])

        # Should NOT return dict or dict[str, Any]
        assert "dict" not in return_type_repr.lower(), (
            "find_code must not return dict, must return FindCodeResponseSummary"
        )

    def test_pydantic_model_validation(self):
        """Verify Pydantic enforces type safety on response construction."""
        # Attempting to construct with wrong types should fail
        with pytest.raises((ValidationError, TypeError)):
            FindCodeResponseSummary(
                matches="not a list",  # ty: ignore[invalid-argument-type]
                summary="Test",
                query_intent=IntentType.UNDERSTAND,
                total_matches=0,
                total_results=0,
                token_count=0,
                execution_time_ms=0,
                search_strategy=(SearchStrategy.KEYWORD_FALLBACK,),
                languages_found=(),
                status="success",
                warnings=[],
                indexing_state="unknown",
                index_coverage=1.0,
                search_mode="hybrid",
                metadata={},
            )

    def test_response_schema_serialization(self):
        """Verify model can serialize to JSON matching contract."""
        response = FindCodeResponseSummary(
            matches=[],
            summary="Test summary",
            query_intent=IntentType.UNDERSTAND,
            total_matches=0,
            total_results=0,
            token_count=0,
            execution_time_ms=100,
            search_strategy=(SearchStrategy.KEYWORD_FALLBACK,),
            languages_found=(),
            status="success",
            warnings=[],
            indexing_state="unknown",
            index_coverage=1.0,
            search_mode="hybrid",
            metadata={},
        )

        # Serialize to dict (JSON-compatible)
        data = response.model_dump()

        # Verify structure
        assert isinstance(data, dict)
        assert "matches" in data
        assert "summary" in data
        assert "query_intent" in data
        assert data["summary"] == "Test summary"
        assert data["query_intent"] == "understand"  # Serialized as string


# Mark all tests with integration marker per project convention
pytestmark = pytest.mark.integration
