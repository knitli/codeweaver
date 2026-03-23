from unittest.mock import patch

import pytest

from codeweaver.core import SearchStrategy
from codeweaver.server.agent_api.search.intent import IntentType
from codeweaver.server.agent_api.search.response import build_success_response


@pytest.fixture
def mock_get_indexer_state_info():
    with patch(
        "codeweaver.server.agent_api.search.response.get_indexer_state_info"
    ) as mock:
        mock.return_value = ("unknown", None)
        yield mock


def test_build_success_response_hybrid(mock_get_indexer_state_info):
    response = build_success_response(
        code_matches=[],
        query="test",
        intent_type=IntentType.UNDERSTAND,
        total_candidates=0,
        token_limit=1000,
        execution_time_ms=10.0,
        strategies_used=[SearchStrategy.HYBRID_SEARCH],
    )

    assert response.search_mode == "hybrid"
    assert response.status == "success"
    assert response.warnings == []


def test_build_success_response_dense_only(mock_get_indexer_state_info):
    response = build_success_response(
        code_matches=[],
        query="test",
        intent_type=IntentType.UNDERSTAND,
        total_candidates=0,
        token_limit=1000,
        execution_time_ms=10.0,
        strategies_used=[SearchStrategy.DENSE_ONLY],
    )

    assert response.search_mode == "dense_only"
    assert response.status == "success"
    assert "Sparse embeddings unavailable - using dense search only" in response.warnings


def test_build_success_response_sparse_only(mock_get_indexer_state_info):
    response = build_success_response(
        code_matches=[],
        query="test",
        intent_type=IntentType.UNDERSTAND,
        total_candidates=0,
        token_limit=1000,
        execution_time_ms=10.0,
        strategies_used=[SearchStrategy.SPARSE_ONLY],
    )

    assert response.search_mode == "sparse_only"
    assert response.status == "partial"
    assert (
        "Dense embeddings unavailable - using sparse search only (degraded mode)"
        in response.warnings
    )


def test_build_success_response_keyword_fallback(mock_get_indexer_state_info):
    response = build_success_response(
        code_matches=[],
        query="test",
        intent_type=IntentType.UNDERSTAND,
        total_candidates=0,
        token_limit=1000,
        execution_time_ms=10.0,
        strategies_used=[SearchStrategy.KEYWORD_FALLBACK],
    )

    assert response.search_mode == "sparse_only"
    assert response.status == "partial"
    assert (
        "Dense embeddings unavailable - using sparse search only (degraded mode)"
        in response.warnings
    )
