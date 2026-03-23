# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
from unittest.mock import patch

import pytest
from pydantic import BaseModel

from codeweaver.core import SearchStrategy
from codeweaver.server.agent_api.search.intent import IntentType
from pathlib import Path
from codeweaver.core import SearchStrategy, CodeChunk, DiscoveredFile, ExtCategory, Span, SemanticSearchLanguage, LanguageName, ChunkKind, ConfigLanguage
from codeweaver.server.agent_api.search.intent import IntentType
from codeweaver.server.agent_api.search.types import CodeMatch, CodeMatchType

class MockCodeChunk(BaseModel):
    content: str
    language: str = "python"

class MockSpan(BaseModel):
    start: int
    end: int

# Update CodeMatch in types.py locally for the test if it restricts content type,
# actually the easiest way is to mock CodeMatch completely or use dicts if it accepts it.
# Wait, CodeMatch expects CodeChunk. Let's patch types.CodeMatch
from codeweaver.server.agent_api.search.response import build_success_response, calculate_token_count, generate_summary, extract_languages


@pytest.fixture
def mock_get_indexer_state_info():
    with patch(
        "codeweaver.server.agent_api.search.response.get_indexer_state_info"
    ) as mock:
        mock.return_value = ("unknown", None)
        yield mock


@pytest.mark.unit
@pytest.mark.parametrize(
    "strategy,expected_mode,expected_status,expected_warning",
    [
        (SearchStrategy.HYBRID_SEARCH, "hybrid", "success", None),
        (
            SearchStrategy.DENSE_ONLY,
            "dense_only",
            "success",
            "Sparse embeddings unavailable - using dense search only",
        ),
        (
            SearchStrategy.SPARSE_ONLY,
            "sparse_only",
            "partial",
            "Dense embeddings unavailable - using sparse search only (degraded mode)",
        ),
        (
            SearchStrategy.KEYWORD_FALLBACK,
            "sparse_only",
            "partial",
            "Dense embeddings unavailable - using sparse search only (degraded mode)",
        ),
    ],
)
def test_build_success_response_search_modes(
    strategy, expected_mode, expected_status, expected_warning, mock_get_indexer_state_info
):
    """Test successful response building with different search strategies and modes."""
    response = build_success_response(
        code_matches=[],
        query="test",
        intent_type=IntentType.UNDERSTAND,
        total_candidates=0,
        token_limit=1000,
        execution_time_ms=10.0,
        strategies_used=[strategy],
    )

    assert response.search_mode == expected_mode
    assert response.status == expected_status
    if expected_warning:
        assert expected_warning in response.warnings
    else:
        assert not response.warnings


class FakeCodeMatch:
    def __init__(self, file, content, span, relevance_score, match_type):
        self.file = file
        self.content = content
        self.span = span
        self.relevance_score = relevance_score
        self.match_type = match_type

@pytest.fixture
def sample_code_matches():
    return [
        FakeCodeMatch(
            file=DiscoveredFile(
                path=Path("src/main.py"),
                ext_category=ExtCategory(
                    language=SemanticSearchLanguage.PYTHON, kind=ChunkKind.CODE
                ),
                mime_type="text/x-python",
            ),
            content=MockCodeChunk(content="def hello_world():\n    print('Hello World!')"),
            span=MockSpan(start=1, end=2),
            relevance_score=0.9,
            match_type=CodeMatchType.SEMANTIC,
        ),
        FakeCodeMatch(
            file=DiscoveredFile(
                path=Path("src/utils.py"),
                ext_category=ExtCategory(
                    language=SemanticSearchLanguage.PYTHON, kind=ChunkKind.CODE
                ),
                mime_type="text/x-python",
            ),
            content=MockCodeChunk(content="def helper():\n    pass"),
            span=MockSpan(start=1, end=2),
            relevance_score=0.8,
            match_type=CodeMatchType.SEMANTIC,
        ),
        FakeCodeMatch(
            file=DiscoveredFile(
                path=Path("config.json"),
                ext_category=ExtCategory(
                    language=ConfigLanguage.JSON, kind=ChunkKind.CONFIG
                ),
                mime_type="application/json",
            ),
            content=MockCodeChunk(content='{"key": "value"}'),
            span=MockSpan(start=1, end=1),
            relevance_score=0.5,
            match_type=CodeMatchType.KEYWORD,
        ),
    ]


@pytest.mark.unit
def test_calculate_token_count(sample_code_matches):
    """Test token count calculation."""
    # First item: 5 words * 1.3 = 6.5 -> 6
    # Second item: 3 words * 1.3 = 3.9 -> 3
    # Third item: 2 words * 1.3 = 2.6 -> 2
    count = calculate_token_count(sample_code_matches, token_limit=1000)
    assert count == 11

    # Test limit
    count_capped = calculate_token_count(sample_code_matches, token_limit=10)
    assert count_capped == 10


@pytest.mark.unit
def test_generate_summary_empty():
    """Test summary generation with empty matches."""
    summary = generate_summary([], IntentType.UNDERSTAND, "test query")
    assert summary == "No matches found for query: 'test query'"


@pytest.mark.unit
def test_generate_summary_populated(sample_code_matches):
    """Test summary generation with matches."""
    summary = generate_summary(sample_code_matches, IntentType.DEBUG, "fix bug")
    assert "Found 3 relevant matches for debug query" in summary
    assert "Top results in" in summary
    assert "main.py" in summary
    assert "utils.py" in summary


@pytest.mark.unit
def test_extract_languages(sample_code_matches):
    """Test language extraction filters out config languages."""
    languages = extract_languages(sample_code_matches)
    assert len(languages) == 1
    assert languages[0] == SemanticSearchLanguage.PYTHON


@pytest.mark.unit
@patch("codeweaver.server.agent_api.search.response.FindCodeResponseSummary")
def test_build_success_response_with_matches(mock_response_summary, mock_get_indexer_state_info, sample_code_matches):
    """Test full build_success_response integration with CodeMatch objects."""
    # We patch FindCodeResponseSummary so we can just verify the values passed to it, bypassing pydantic validation of fake objects
    mock_response_summary.return_value = "MockedResponse"
    response = build_success_response(
        code_matches=sample_code_matches,
        query="test code",
        intent_type=IntentType.IMPLEMENT,
        total_candidates=10,
        token_limit=1000,
        execution_time_ms=15.5,
        strategies_used=[SearchStrategy.HYBRID_SEARCH],
    )

    assert response == "MockedResponse"
    mock_response_summary.assert_called_once()
    kwargs = mock_response_summary.call_args[1]

    assert kwargs["search_mode"] == "hybrid"
    assert kwargs["status"] == "success"
    assert len(kwargs["matches"]) == 3
    assert kwargs["total_matches"] == 10
    assert kwargs["total_results"] == 3
    assert "Found 3 relevant matches for implement query" in kwargs["summary"]
    assert kwargs["token_count"] == 11
    assert kwargs["execution_time_ms"] == 15.5
    assert len(kwargs["languages_found"]) == 1
    assert kwargs["languages_found"][0] == SemanticSearchLanguage.PYTHON
