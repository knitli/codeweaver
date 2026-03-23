# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Unit tests for query intent detection."""

import pytest

from codeweaver.server.agent_api.search.intent import (
    IntentType,
    QueryComplexity,
    detect_intent,
)


@pytest.mark.parametrize(
    ("query", "expected_intent"),
    [
        ("how does authentication work", IntentType.UNDERSTAND),
        ("explain the database schema", IntentType.UNDERSTAND),
        ("implement user login", IntentType.IMPLEMENT),
        ("create a new api endpoint", IntentType.IMPLEMENT),
        ("fix the crash on startup", IntentType.DEBUG),
        ("why is the route failing", IntentType.DEBUG),
        ("optimize the caching layer", IntentType.OPTIMIZE),
        ("improve the query to be faster", IntentType.OPTIMIZE),
        ("write a unittest for the model", IntentType.TEST),
        ("verify the security changes", IntentType.TEST),
        ("update the configuration settings", IntentType.CONFIGURE),
        ("configure the development environment", IntentType.CONFIGURE),
        ("add documentation for the handler", IntentType.DOCUMENT),
        ("update the readme", IntentType.DOCUMENT),
        ("HOW DOES AUTHENTICATION WORK?", IntentType.UNDERSTAND),
        ("Fix the crash on startup!!!", IntentType.DEBUG),
        ("OpTiMiZe the CACHING layer", IntentType.OPTIMIZE),
    ],
)
def test_detect_intent_categories(query: str, expected_intent: IntentType) -> None:
    """Test classification of different intent categories."""
    intent = detect_intent(query)
    assert intent.intent_type == expected_intent


def test_detect_intent_default_fallback() -> None:
    """Test fallback to UNDERSTAND when no keywords match."""
    intent = detect_intent("some generic phrase")
    assert intent.intent_type == IntentType.UNDERSTAND
    assert 0.0 <= intent.confidence <= 0.5
    assert "default" in intent.reasoning.lower()


def test_detect_intent_confidence_multiple_matches() -> None:
    """Test confidence calculation with multiple keyword matches."""
    # "how does" and "explain" both match UNDERSTAND
    intent = detect_intent("how does this work, explain it to me")
    assert intent.intent_type == IntentType.UNDERSTAND
    assert intent.confidence > 0.5
    assert "multiple" in intent.reasoning.lower()


def test_detect_intent_confidence_strong_keyword() -> None:
    """Test confidence calculation with a single strong keyword match."""
    # "implement" is a significant portion of this short query
    intent = detect_intent("implement login")
    assert intent.intent_type == IntentType.IMPLEMENT
    assert intent.confidence > 0.5
    assert "strong" in intent.reasoning.lower()


def test_detect_intent_confidence_weak_keyword() -> None:
    """Test confidence calculation with a single weak keyword match."""
    # "fix" is a small portion of this long query
    intent = detect_intent("I need to apply a fix for this really long and complicated process")
    assert intent.intent_type == IntentType.DEBUG
    assert 0.4 <= intent.confidence <= 0.8
    assert "keyword detected" in intent.reasoning.lower()


@pytest.mark.parametrize(
    ("query", "expected_complexity"),
    [
        ("fix bug", QueryComplexity.SIMPLE),  # < 5 words
        ("how does the authentication middleware work", QueryComplexity.MODERATE),  # 5-15 words
        (
            "explain how the user authentication middleware interacts with the caching layer and the database models",
            QueryComplexity.COMPLEX,
        ),  # > 15 words
        ("implement user login and user registration", QueryComplexity.COMPLEX),  # contains " and ", >= 5 words
        ("fix the crash or fix the fail", QueryComplexity.COMPLEX),  # contains " or ", >= 5 words
    ],
)
def test_detect_intent_complexity(query: str, expected_complexity: QueryComplexity) -> None:
    """Test complexity level detection."""
    intent = detect_intent(query)
    assert intent.complexity_level == expected_complexity


def test_detect_intent_focus_areas() -> None:
    """Test extraction of focus areas."""
    intent = detect_intent("how does authentication middleware work with the database")
    expected_areas = {"auth", "authentication", "middleware", "database"}
    assert set(intent.focus_areas) == expected_areas


def test_detect_intent_empty_string() -> None:
    """Test handling of an empty string."""
    intent = detect_intent("")
    assert intent.intent_type == IntentType.UNDERSTAND
    assert intent.confidence < 0.5
    assert intent.complexity_level == QueryComplexity.SIMPLE
    assert not intent.focus_areas


def test_detect_intent_focus_areas_with_noise() -> None:
    """Test that focus area extraction handles noise."""
    query = "how does the system work with the database in production and staging and and and"
    intent = detect_intent(query)

    focus_areas = set(intent.focus_areas)
    expected_signal_terms = {"database"}
    assert expected_signal_terms.issubset(focus_areas)
