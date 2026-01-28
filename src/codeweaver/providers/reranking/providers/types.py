# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""
Reranking result types for CodeWeaver.
"""

from typing import Annotated, NamedTuple

from pydantic import Field

from codeweaver.core import CodeChunk, generate_field_title


class RerankingResult(NamedTuple):
    """Result of a reranking operation."""

    original_index: Annotated[
        int,
        Field(
            description="Original index of the document", field_title_generator=generate_field_title
        ),
    ]
    batch_rank: Annotated[
        int,
        Field(
            description="Rank of the document in the batch",
            field_title_generator=generate_field_title,
        ),
    ]
    score: Annotated[
        float,
        Field(description="Score of the document", field_title_generator=generate_field_title),
    ]
    chunk: Annotated[
        CodeChunk,
        Field(
            description="Code chunk associated with the document",
            field_title_generator=generate_field_title,
        ),
    ]
    # Optional search metadata preserved from vector search results
    original_score: Annotated[
        float | None,
        Field(
            description="Original score of the document", field_title_generator=generate_field_title
        ),
    ] = None
    # currently CodeWeaver only uses Reciprocal Rank Fusion, returning combined ranks. But we keep these fields for potential future use.
    dense_score: Annotated[
        float | None,
        Field(
            description="Dense score of the document", field_title_generator=generate_field_title
        ),
    ] = None
    sparse_score: Annotated[
        float | None,
        Field(
            description="Sparse score of the document", field_title_generator=generate_field_title
        ),
    ] = None


__all__ = ("RerankingResult",)
