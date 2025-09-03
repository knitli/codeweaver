# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Intent classification models for query analysis."""

from __future__ import annotations

from typing import Annotated, Literal

from pydantic import BaseModel, Field, NonNegativeFloat, NonNegativeInt

from codeweaver._common import BaseEnum


class QueryComplexity(BaseEnum):
    """Enumeration of query complexity levels."""

    SIMPLE = "simple"
    MODERATE = "moderate"
    COMPLEX = "complex"

    @classmethod
    def default(cls) -> Literal[QueryComplexity.MODERATE]:
        """Return the default query complexity level."""
        return cls.MODERATE


class IntentType(BaseEnum):
    """Enumeration of intent types."""

    UNDERSTAND = "understand"
    IMPLEMENT = "implement"
    DEBUG = "debug"
    OPTIMIZE = "optimize"
    TEST = "test"
    CONFIGURE = "configure"
    DOCUMENT = "document"


class QueryIntent(BaseModel):
    """Classified query intent with confidence scoring."""

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


class IntentResult(BaseModel):
    """Result of intent analysis with strategy recommendations."""

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
        NonNegativeFloat, Field(default=0.6, le=1.0, description="""Weight for semantic search""")
    ]
    syntactic_weight: Annotated[
        NonNegativeFloat, Field(default=0.3, le=1.0, description="""Weight for syntactic search""")
    ]
    keyword_weight: Annotated[
        NonNegativeFloat, Field(default=0.1, le=1.0, description="""Weight for keyword search""")
    ]

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
