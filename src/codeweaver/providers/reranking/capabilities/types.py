# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Types for reranking model capabilities."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import TYPE_CHECKING, Annotated, Any, Literal, NotRequired, Required, TypedDict

from pydantic import NonNegativeInt, PositiveInt


if TYPE_CHECKING:
    from codeweaver.core.chunks import CodeChunk
    from codeweaver.providers.provider import Provider

type PartialRerankingCapabilitiesDict = dict[
    Literal[
        "name",
        "extra",
        "provider",
        "max_input",
        "max_query",
        "input_transformer",
        "output_transformer",
        "context_window",
        "supports_custom_prompt",
        "custom_prompt",
        "tokenizer",
        "tokenizer_model",
    ],
    str
    | PositiveInt
    | bool
    | None
    | Provider
    | Callable[[Sequence[CodeChunk], str], Any]
    | Callable[..., Sequence[Sequence[float]] | Sequence[Sequence[int]]]
    | tuple[bool, NonNegativeInt]
    | dict[str, Any],
]


class RerankingCapabilitiesDict(TypedDict, total=False):
    """Describes the capabilities of a reranking model."""

    name: Required[str]
    provider: Required[Provider]
    max_query: NotRequired[PositiveInt | None]
    max_input: Annotated[
        PositiveInt | Callable[[Sequence[CodeChunk], str], tuple[bool, NonNegativeInt]] | None,
        NotRequired,
    ]
    context_window: NotRequired[PositiveInt]
    supports_custom_prompt: NotRequired[bool]
    custom_prompt: NotRequired[str]
    tokenizer: NotRequired[Literal["tokenizers", "tiktoken"]]
    tokenizer_model: NotRequired[str]
    other: NotRequired[dict[str, Any]]
