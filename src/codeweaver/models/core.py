# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Core models for CodeWeaver responses and data structures."""

from __future__ import annotations

from typing import Annotated

from pydantic import BaseModel, ConfigDict, Field, NonNegativeFloat, NonNegativeInt, model_validator

from codeweaver._common import BaseEnum
from codeweaver._data_structures import DiscoveredFile, Span
from codeweaver.language import SemanticSearchLanguage
from codeweaver.models.intent import IntentType


class SearchStrategy(BaseEnum):
    """Enumeration of search types."""

    COMMIT_SEARCH = "commit_search"
    FILE_DISCOVERY = "file_discovery"
    LANGUAGE_SEARCH = "language_search"
    SYMBOL_SEARCH = "symbol_search"
    TEXT_SEARCH = "text_search"


class CodeMatchType(BaseEnum):
    """Enumeration of code match types."""

    SEMANTIC = "semantic"
    SYNTACTIC = "syntactic"
    KEYWORD = "keyword"
    FILE_PATTERN = "file_pattern"


class CodeMatch(BaseModel):
    """Individual code match with context and metadata."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "file": {
                    "path": "src/auth/middleware.py",
                    "language": "python",
                    "file_hash": "9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08",
                    "file_size": 1234,
                },
                "content": "class AuthMiddleware(BaseMiddleware): ...",
                "span": [
                    15,
                    45,
                    "5f6d4c46-39cc-4cf5-8477-3d5b4a9e3c31",
                ],  # spans have a source_id for the chunk they came from
                "relevance_score": 0.92,
                "match_type": "text_search",
            }
        }
    )

    # File information
    file: Annotated[DiscoveredFile, Field(description="""File information""")]

    # Content
    content: Annotated[str, Field(description="""Relevant code content""")]

    span: Annotated[Span, Field(description="""Start and end line numbers""")]

    # Relevance scoring1
    relevance_score: Annotated[
        NonNegativeFloat, Field(le=1.0, description="""Relevance score (0.0-1.0)""")
    ]

    match_type: Annotated[
        CodeMatchType, Field(description="""The type of match for this code match""")
    ]

    # Context
    surrounding_context: Annotated[
        str | None, Field(description="""Additional context around the match""")
    ] = None

    related_symbols: Annotated[
        tuple[str],
        Field(default_factory=tuple, description="""Related functions, classes, or symbols"""),
    ]

    @model_validator(mode="after")
    def validate_span(self) -> CodeMatch:
        """Validate span consistency."""
        start, end = self.span
        if start > end:
            raise ValueError("Start line must be <= end line")
        if start < 1:
            raise ValueError("Line numbers must start from 1")
        return self


class FindCodeResponseSummary(BaseModel):
    """Structured response from find_code tool."""

    model_config = ConfigDict(
        json_schema_extra={
            "example": {
                "matches": [],
                "summary": "Found authentication middleware in 3 files...",
                "query_intent": {
                    "type": "understand",
                    "confidence": 0.9,
                    "reasoning": "Query indicates need for authentication setup",
                    "focus_areas": ["middleware", "authentication"],
                    "complexity_level": "moderate",
                },
                "total_matches": 15,
                "total_token_count": 8543,
                "execution_time_ms": 1234.5,
                "search_strategy": ["file_discovery", "text_search"],
                "languages_found": ["python", "typescript"],
            }
        }
    )

    # Core results
    matches: Annotated[
        list[CodeMatch], Field(description="""Relevant code matches ranked by relevance""")
    ]

    summary: Annotated[
        str, Field(description="""High-level summary of findings""", max_length=1000)
    ]

    query_intent: Annotated[
        IntentType | None, Field(description="""Detected or specified intent""")
    ]

    total_matches: Annotated[
        NonNegativeInt, Field(description="""Total matches found before ranking""")
    ]

    token_count: Annotated[NonNegativeInt, Field(description="""Actual tokens used in response""")]

    execution_time_ms: Annotated[NonNegativeFloat, Field(description="""Total processing time""")]

    # Context information
    search_strategy: Annotated[
        tuple[SearchStrategy, ...], Field(description="""Search methods used""")
    ]

    languages_found: Annotated[
        tuple[SemanticSearchLanguage | str, ...],
        Field(
            description="""Programming languages in the results. If the language is supported for semantic search, it will be a `SemanticSearchLanguage`, otherwise a `str` from languages in `codeweaver._constants.py`"""
        ),
    ]


__all__ = ("CodeMatch", "CodeMatchType", "FindCodeResponseSummary", "SearchStrategy")
