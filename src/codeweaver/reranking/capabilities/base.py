"""Reranking model capabilities and settings."""

from collections.abc import Callable, Sequence
from typing import Annotated, Any, Literal, NotRequired, Required, TypedDict

from pydantic import BaseModel, Field, NonNegativeInt, PositiveInt

from codeweaver._data_structures import CodeChunk, SerializedCodeChunk
from codeweaver._settings import Provider
from codeweaver.tokenizers.base import Tokenizer


def _is_correct_return_type(output: Any) -> bool:
    """Check if the output is of the correct return type."""
    return (
        (hasattr(output, "__iter__"))
        and all(hasattr(i, "__iter__") for i in output)
        and (
            all(isinstance(j, float) for i in output for j in i)
            or all(isinstance(j, int) for i in output for j in i)
        )
    )


def default_input_transformer(
    input_chunks: list[CodeChunk],
) -> list[SerializedCodeChunk[CodeChunk]]:
    """Default input transformer for reranking models."""
    return [chunk.serialize_for_embedding() for chunk in input_chunks]


def default_output_transformer(results: Any) -> Sequence[Sequence[float]] | Sequence[Sequence[int]]:
    """Default output transformer for reranking models."""
    if _is_correct_return_type(results):
        return results
    if attrs := [attr for attr in dir(results) if not attr.startswith("_")]:
        for attr in attrs:
            if (actual_attr := getattr(results, attr, None)) and _is_correct_return_type(
                actual_attr
            ):
                return actual_attr
    raise TypeError(
        f"Expected output to be a sequence of sequences of floats or ints, got {type(results).__name__} with attributes {attrs}"
    )


type PartialRerankingCapabilities = dict[
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


class RerankingCapabilities(TypedDict, total=False):
    """Describes the capabilities of a reranking model."""

    name: Required[str]
    provider: Required[Provider]
    max_query: NotRequired[PositiveInt | None]
    max_input: (
        NotRequired[PositiveInt]
        | Callable[[Sequence[CodeChunk], str], tuple[bool, NonNegativeInt]]
        | None
    )
    context_window: NotRequired[PositiveInt]
    supports_custom_prompt: NotRequired[bool]
    custom_prompt: NotRequired[str]
    tokenizer: NotRequired[Literal["tokenizers", "tiktoken"]]
    tokenizer_model: NotRequired[str]
    other: NotRequired[dict[str, Any]]


class RerankingModelCapabilities(BaseModel):
    """Capabilities of a reranking model."""

    name: Annotated[str, Field(description="The name of the model.")] = ""
    provider: Annotated[Provider, Field(description="The provider of the model.")] = Provider._UNSET  # pyright: ignore[reportPrivateUsage]
    max_query: Annotated[
        PositiveInt | None,
        Field(description="The maximum number of tokens the model can handle for a single query."),
    ] = None
    max_input: Annotated[
        Callable[[Sequence[CodeChunk], str], tuple[bool, NonNegativeInt]] | PositiveInt | None,
        Field(
            description="In the simple case, takes an integer for the maximum number of tokens the model can handle. A function that returns a tuple where the first value is a boolean indicating if the passed input exceeds the model's maximum input length, and the second value is an integer -- if the returned boolean is True (within limits), will be 0, but if it exceeds limits, the integer will be the maximum safe index of the input that can be provided. Callable receives a list of CodeChunks and the query string."
        ),
    ] = None
    input_transformer: Callable[[Sequence[CodeChunk]], Any] | None = None
    output_transformer: (
        Callable[..., Sequence[Sequence[float]] | Sequence[Sequence[int]]] | None
    ) = default_output_transformer
    context_window: Annotated[
        PositiveInt, Field(description="The context window size of the model.")
    ] = 256
    supports_custom_prompt: Annotated[
        bool | None, Field(description="Whether the model supports custom prompts.")
    ] = None
    custom_prompt: Annotated[
        str | None, Field(description="The custom prompt to use for the model.")
    ] = None
    tokenizer: Annotated[
        Literal["tokenizers", "tiktoken"] | None,
        Field(description="The tokenizer to use for the model."),
    ] = None
    tokenizer_model: Annotated[
        str | None, Field(description="The tokenizer model to use for the model.")
    ] = None
    other: Annotated[dict[str, Any], Field(description="Extra model-specific settings.")] = {}

    @property
    def token_processor(self) -> Tokenizer[Any]:
        """Return the tokenizer for the model."""
        from codeweaver.tokenizers import get_tokenizer

        if self.tokenizer and self.tokenizer_model:
            return get_tokenizer(self.tokenizer, self.tokenizer_model)
        return get_tokenizer("tiktoken", "cl100k_base")

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
            raise TypeError(f"Expected max_input to be an int, got {type(self.max_input).__name__}")
        return self._process_max_input_with_tokenizer(input_chunks)

    def is_within_limits(
        self, input_chunks: Sequence[CodeChunk], query: str
    ) -> tuple[bool, NonNegativeInt]:
        """Check if the input chunks are within the model's limits."""
        if not self.max_input:
            return True, 0
        if isinstance(self.max_input, int):
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
        return self.max_input(input_chunks, query) if callable(self.max_input) else (True, 0)
