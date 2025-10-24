# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Intent classification models for query analysis."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import Field, NonNegativeFloat, NonNegativeInt

from codeweaver.core import BasedModel, BaseEnum


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
        tuple[str],
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
        tuple[str], Field(default_factory=tuple, description="""Patterns to exclude from search""")
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


__all__ = ("IntentResult", "IntentType", "QueryComplexity", "QueryIntent")
