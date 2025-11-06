# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Reranking model capabilities and settings."""

from __future__ import annotations

from collections.abc import Sequence
from typing import TYPE_CHECKING, Annotated, Any, Literal

from pydantic import ConfigDict, Field, NonNegativeInt, PositiveInt

from codeweaver.core.types.models import BasedModel
from codeweaver.exceptions import ValidationError as CodeWeaverValidationError
from codeweaver.providers.provider import Provider
from codeweaver.tokenizers.base import Tokenizer


if TYPE_CHECKING:
    from codeweaver.core.chunks import CodeChunk


class RerankingModelCapabilities(BasedModel):
    """Capabilities of a reranking model."""

    model_config = BasedModel.model_config | ConfigDict(frozen=True)

    name: Annotated[str, Field(description="""The name of the model.""")] = ""
    provider: Annotated[Provider, Field(description="""The provider of the model.""")] = (
        Provider.NOT_SET
    )
    max_query: Annotated[
        PositiveInt | None,
        Field(
            description="""The maximum number of tokens the model can handle for a single query."""
        ),
    ] = None
    max_input: Annotated[
        PositiveInt | None,
        Field(
            description="""The maximum number of tokens the model can handle for input documents."""
        ),
    ] = None
    context_window: Annotated[
        PositiveInt,
        Field(
            description="""The context window size of the model. Defaults to 256, which is the minimum of all supported models."""
        ),
    ] = 256
    supports_custom_prompt: Annotated[
        bool | None, Field(description="""Whether the model supports custom prompts.""")
    ] = None
    custom_prompt: Annotated[
        str | None, Field(description="""The custom prompt to use for the model.""")
    ] = None
    tokenizer: Annotated[
        Literal["tokenizers", "tiktoken"] | None,
        Field(description="""The tokenizer to use for the model."""),
    ] = None
    tokenizer_model: Annotated[
        str | None, Field(description="""The tokenizer model to use for the model.""")
    ] = None
    other: Annotated[
        dict[str, Any] | None, Field(description="""Extra model-specific settings.""")
    ] = None

    _available: Annotated[
        bool,
        Field(
            init=False,
            description="""Whether the model is available, meaning its package is available in the environment and it has been implemented.""",
        ),
    ] = False  # defaults to False, set to True when the model is known to be available

    def __init__(self, **data: Any) -> None:
        """Initialize the RerankingModelCapabilities."""
        # Set defaults before calling super().__init__()
        if "tokenizer" not in data:
            data["tokenizer"] = "tiktoken"
            data["tokenizer_model"] = "cl100k_base"
        if "other" not in data:
            data["other"] = {}

        # Call super().__init__() FIRST to initialize Pydantic model
        super().__init__(**data)

    def _telemetry_keys(self) -> None:
        return None

    @property
    def token_processor(self) -> Tokenizer[Any]:
        """Return the tokenizer for the model."""
        from codeweaver.tokenizers import get_tokenizer

        if self.tokenizer and self.tokenizer_model:
            return get_tokenizer(self.tokenizer, self.tokenizer_model)
        return get_tokenizer("tiktoken", "cl100k_base")

    @property
    def available(self) -> bool:
        """Check if the model is available."""
        return self._available

    def query_ok(self, query: str) -> bool:
        """Check if the query is within the model's limits."""
        if not self.max_query:
            return True
        return self.token_processor.estimate(query) <= self.max_query

    def _process_max_input_with_tokenizer(
        self, input_chunks: Sequence[str]
    ) -> tuple[bool, NonNegativeInt]:
        """Process max_input using the specified tokenizer."""
        # TODO: We need to handle the case where the first chunk is larger than the max_input.
        # we can prevent it if we pass the max_input down to the chunker, but we should also handle it here.
        if not self.max_input or not isinstance(self.max_input, int):
            return True, 0
        tokenizer = self.token_processor
        chunk_counts = [tokenizer.estimate(chunk) for chunk in input_chunks]
        total_count = sum(chunk_counts)
        if total_count <= self.max_input:
            return True, 0
        summed_count: int = 0
        while summed_count < self.max_input and chunk_counts:
            for i, count in enumerate(chunk_counts):
                if summed_count + count > self.max_input:
                    return False, i - 1 if i > 0 else 0
                summed_count += count
        return False, len(chunk_counts) - 1

    def _handle_int_max_input(self, input_chunks: Sequence[str]) -> tuple[bool, NonNegativeInt]:
        """Handle integer max_input case."""
        if not isinstance(self.max_input, int):
            raise CodeWeaverValidationError(
                "Reranking capability max_input must be an integer",
                details={
                    "field": "max_input",
                    "expected_type": "int",
                    "received_type": type(self.max_input).__name__,
                    "received_value": str(self.max_input),
                },
                suggestions=[
                    "Set max_input as an integer in capabilities",
                    "Check capability configuration schema",
                    "Verify model capability definition",
                ],
            )
        return self._process_max_input_with_tokenizer(input_chunks)

    def is_within_limits(
        self, input_chunks: Sequence[CodeChunk], query: str
    ) -> tuple[bool, NonNegativeInt]:
        """Check if the input chunks are within the model's limits."""
        if not self.max_input:
            return True, 0
        # before we do an expensive check, let's check if we're in the neighborhood of the limit
        if query and not self.query_ok(query):
            return False, 0
        # we'll check if we're within 85% of the max_input limit, assuming 4 tokens per character as a rough estimate
        if (
            input_chunks
            and sum(len(chunk.content) for chunk in input_chunks) < (self.max_input * 4) * 0.85
        ):
            return True, 0
        return self._handle_int_max_input([  # pyright: ignore[reportUnknownArgumentType]
            (query + chunk.serialize_for_embedding())  # pyright: ignore[reportOperatorIssue]  # it's a string, I promise
            for chunk in input_chunks  # pyright: ignore[reportOperatorIssue]
        ])


__all__ = ("RerankingModelCapabilities",)
