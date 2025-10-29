# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Intent classification models for query analysis."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, NonNegativeFloat, NonNegativeInt

from codeweaver.core.types import BasedModel, BaseEnum


class QueryComplexity(BaseEnum):
    """Enumeration of query complexity levels."""

    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"

    @classmethod
    def default(cls) -> Literal[QueryComplexity.MODERATE]:
        """Return the default query complexity level."""
        return cls.MODERATE


class IntentType(str, BaseEnum):
    """Enumeration of intent types."""

    UNDERSTAND = "understand"
    """You want to understand the codebase structure, a specific feature or functionality, or how different components interact."""
    IMPLEMENT = "implement"
    """You want to implement a new feature or functionality in the codebase."""
    DEBUG = "debug"
    """You want to debug an issue or error in the codebase."""
    OPTIMIZE = "optimize"
    """You want to optimize the performance or efficiency of the codebase."""
    TEST = "test"
    """You want to write or modify tests for the codebase."""
    CONFIGURE = "configure"
    """You want to update, change, or implement configuration settings (like, `package.json`, `pyproject.toml`) and need to understand the current configuration."""
    DOCUMENT = "document"
    """You want to write or update documentation for the codebase or understand the structure and organization of the documentation."""

    __slots__ = ()


class QueryIntent(BasedModel):
    """Classified query intent with confidence scoring."""

    model_config = BasedModel.model_config | {"defer_build": True}

    intent_type: IntentType

    confidence: Annotated[NonNegativeFloat, Field(le=1.0)]
    reasoning: Annotated[str, Field(description="""Why this intent was detected""")]

    # Intent-specific parameters
    focus_areas: Annotated[
        tuple[str, ...],
        Field(default_factory=tuple, description="""Specific areas of focus within the intent"""),
    ]
    complexity_level: Annotated[
        QueryComplexity | Literal["simple", "moderate", "complex"],
        Field(default=QueryComplexity.MODERATE),
    ]

    def _telemetry_keys(self) -> None:
        return None


class IntentResult(BasedModel):
    """Result of intent analysis with strategy recommendations."""

    model_config = BasedModel.model_config | {"defer_build": True}

    intent: QueryIntent

    # Strategy parameters
    file_patterns: Annotated[
        list[str], Field(default_factory=list, description="""File patterns to prioritize""")
    ]
    exclude_patterns: Annotated[
        tuple[str, ...],
        Field(default_factory=tuple, description="""Patterns to exclude from search"""),
    ]

    # Search strategy weights
    semantic_weight: Annotated[
        NonNegativeFloat, Field(le=1.0, description="""Weight for semantic search""")
    ] = 0.6
    syntactic_weight: Annotated[
        NonNegativeFloat, Field(le=1.0, description="""Weight for syntactic search""")
    ] = 0.3
    keyword_weight: Annotated[
        NonNegativeFloat, Field(le=1.0, description="""Weight for keyword search""")
    ] = 0.1

    # Response formatting preferences
    include_context: Annotated[
        bool, Field(description="""Whether to include context in the response""")
    ] = True
    max_matches_per_file: Annotated[
        NonNegativeInt, Field(default=5, description="""Maximum matches per file""")
    ]
    prioritize_entry_points: Annotated[
        bool, Field(description="""Whether to prioritize entry points in results""")
    ] = False

    def _telemetry_keys(self) -> None:
        return None


# =============================================================================
# Intent Detection
# =============================================================================

# Keyword mappings for intent classification
INTENT_KEYWORDS: dict[IntentType, tuple[str, ...]] = {
    IntentType.UNDERSTAND: ("how does", "what is", "explain", "understand", "how to", "show me"),
    IntentType.IMPLEMENT: ("implement", "create", "add", "build", "write", "make", "generate"),
    IntentType.DEBUG: (
        "debug",
        "fix",
        "error",
        "bug",
        "issue",
        "broken",
        "crash",
        "exception",
        "why",
        "fail",
    ),
    IntentType.OPTIMIZE: (
        "optimize",
        "improve",
        "faster",
        "performance",
        "slow",
        "speed up",
        "efficient",
    ),
    IntentType.TEST: ("test", "testing", "unittest", "verify", "spec", "should"),
    IntentType.CONFIGURE: (
        "configure",
        "config",
        "setup",
        "settings",
        "environment",
        "configuration",
    ),
    IntentType.DOCUMENT: ("document", "docs", "documentation", "comment", "readme", "docstring"),
}

# Mapping from IntentType to AgentTask for ImportanceScores weighting
# Used in find_code pipeline to adjust semantic ranking based on query intent
INTENT_TO_AGENT_TASK: dict[IntentType, str] = {
    IntentType.UNDERSTAND: "SEARCH",
    IntentType.IMPLEMENT: "IMPLEMENT",
    IntentType.DEBUG: "DEBUG",
    IntentType.OPTIMIZE: "REFACTOR",
    IntentType.TEST: "TEST",
    IntentType.CONFIGURE: "LOCAL_EDIT",
    IntentType.DOCUMENT: "DOCUMENT",
}


def detect_intent(query: str) -> QueryIntent:
    """Analyze query and return intent classification with confidence.

    Uses keyword-based heuristics for v0.1 (agent-driven analysis planned for v0.2).

    Args:
        query: Search query string to analyze

    Returns:
        QueryIntent with detected intent_type, confidence score, reasoning, and metadata

    Examples:
        >>> detect_intent("how does authentication work")
        QueryIntent(intent_type=IntentType.UNDERSTAND, confidence=0.9, ...)

        >>> detect_intent("fix login bug")
        QueryIntent(intent_type=IntentType.DEBUG, confidence=0.9, ...)

        >>> detect_intent("add user registration")
        QueryIntent(intent_type=IntentType.IMPLEMENT, confidence=0.9, ...)
    """
    query_lower = query.lower()

    # Track matches for each intent type
    matches: dict[IntentType, tuple[int, list[str]]] = {}  # intent -> (count, matched_keywords)

    for intent_type, keywords in INTENT_KEYWORDS.items():
        matched_keywords = [kw for kw in keywords if kw in query_lower]
        if matched_keywords:
            matches[intent_type] = (len(matched_keywords), matched_keywords)

    # Determine best match
    if not matches:
        # No keywords matched - default to UNDERSTAND with low confidence
        return QueryIntent(
            intent_type=IntentType.UNDERSTAND,
            confidence=0.3,
            reasoning="No specific intent keywords detected, defaulting to UNDERSTAND",
            focus_areas=tuple(_extract_focus_areas(query)),
            complexity_level=_determine_complexity(query),
        )

    # Find intent with most keyword matches
    best_intent = max(matches.items(), key=lambda x: (x[1][0], len(x[1][1])))
    intent_type, (match_count, matched_keywords) = best_intent

    # Calculate confidence based on match count and query length
    # Exact match (single keyword covers most of query) = 0.9
    # Multiple matches = 0.9
    # Single match = 0.6
    if match_count >= 2:
        confidence = 0.9
        reasoning = f"Multiple intent keywords detected: {', '.join(matched_keywords[:3])}"
    elif match_count == 1:
        # Check if keyword is significant portion of query
        keyword_ratio = len(matched_keywords[0]) / len(query_lower)
        if keyword_ratio > 0.3:
            confidence = 0.9
            reasoning = f"Strong intent keyword detected: '{matched_keywords[0]}'"
        else:
            confidence = 0.6
            reasoning = f"Intent keyword detected: '{matched_keywords[0]}'"
    else:
        confidence = 0.3
        reasoning = "Weak intent signal"

    return QueryIntent(
        intent_type=intent_type,
        confidence=confidence,
        reasoning=reasoning,
        focus_areas=tuple(_extract_focus_areas(query)),
        complexity_level=_determine_complexity(query),
    )


def _extract_focus_areas(query: str) -> list[str]:
    """Extract specific focus areas from query text.

    Args:
        query: Search query string

    Returns:
        List of focus area keywords (e.g., ["authentication", "middleware"])
    """
    # Simple keyword extraction - look for common technical terms
    focus_keywords = [
        "auth",
        "authentication",
        "middleware",
        "database",
        "api",
        "route",
        "handler",
        "model",
        "service",
        "config",
        "test",
        "validation",
        "error",
        "logging",
        "cache",
        "security",
        "performance",
    ]

    query_lower = query.lower()
    return [kw for kw in focus_keywords if kw in query_lower]


def _determine_complexity(query: str) -> QueryComplexity:
    """Determine query complexity level based on query characteristics.

    Args:
        query: Search query string

    Returns:
        QueryComplexity level (SIMPLE, MODERATE, COMPLEX)
    """
    # Simple heuristics:
    # - Short queries (<5 words) = SIMPLE
    # - Medium queries (5-15 words) = MODERATE
    # - Long queries (>15 words) or multiple clauses = COMPLEX

    word_count = len(query.split())

    if word_count < 5:
        return QueryComplexity.SIMPLE
    if word_count > 15 or " and " in query.lower() or " or " in query.lower():
        return QueryComplexity.COMPLEX
    return QueryComplexity.MODERATE


__all__ = (
    "INTENT_TO_AGENT_TASK",
    "IntentResult",
    "IntentType",
    "QueryComplexity",
    "QueryIntent",
    "detect_intent",
)
