# sourcery skip: avoid-single-character-names-variables, no-complex-if-expressions
"""Bedrock embedding provider."""

# SPDX-FileCopyrightText: 2025 (c) 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
from __future__ import annotations

import logging

from collections.abc import Sequence
from io import BytesIO
from typing import (
    Annotated,
    Any,
    ClassVar,
    Literal,
    NotRequired,
    Required,
    TypedDict,
    TypeGuard,
    cast,
)

from pydantic import (
    AliasGenerator,
    BaseModel,
    ConfigDict,
    Field,
    PositiveInt,
    ValidationError,
    ValidationInfo,
    model_serializer,
    model_validator,
)
from pydantic.alias_generators import to_camel, to_snake

from codeweaver._data_structures import CodeChunk
from codeweaver._settings import Provider
from codeweaver.embedding.capabilities import EmbeddingModelCapabilities
from codeweaver.embedding.providers.base import EmbeddingProvider


logger = logging.getLogger(__name__)


class BaseBedrockModel(BaseModel):
    """Base model for Bedrock-related Pydantic models."""

    model_config = ConfigDict(
        alias_generator=AliasGenerator(validation_alias=to_snake, serialization_alias=to_camel),
        str_strip_whitespace=True,
        # spellchecker:off
        ser_json_inf_nan="null",
        # spellchecker:on
        serialize_by_alias=True,
    )


def is_cohere_request(data: dict[Any, Any] | str | bytes | bytearray) -> bool:
    """Determine if the given data is a Cohere embedding request."""
    if isinstance(data, dict):
        return (
            ("texts" in data and data["texts"] is not None)
            or ("images" in data and data["images"] is not None)
        ) and "input_type" in data
    if isinstance(data, str):
        return ("'texts':" in data or '"texts":' in data) and (
            "'input_type':" in data or '"input_type":' in data
        )
    return (b"'texts':" in data or b'"texts":' in data) and (
        b"'input_type':" in data or b'"input_type":' in data
    )


def is_cohere_response(data: dict[Any, Any] | str | bytes | bytearray) -> bool:
    """Determine if the given data is a Cohere embedding response."""
    if isinstance(data, dict):
        return ("embeddings" in data and "id" in data) or ("response_type" in data)
    if isinstance(data, str):
        return ("'embeddings':" in data or '"embeddings":' in data) and (
            "'response_type':" in data or '"response_type":' in data
        )
    return (b"'embeddings':" in data or b'"embeddings":' in data) and (
        b"'response_type':" in data or b'"response_type":' in data
    )


def is_titan_response(data: dict[Any, Any] | str | bytes | bytearray) -> bool:
    """Determine if the given data is a Titan Embedding V2 response."""
    if isinstance(data, dict):
        return ("embedding" in data and "input_text_token_count" in data) or (
            "embeddings_by_type" in data
        )
    if isinstance(data, str):
        return ("'embedding':" in data or '"embedding":' in data) and (
            "'input_text_token_count':" in data or '"input_text_token_count":' in data
        )
    return (b"'embedding':" in data or b'"embedding":' in data) and (
        b"'input_text_token_count':" in data or b'"input_text_token_count":' in data
    )


def is_one_of_valid_types(
    data: Any,
) -> TypeGuard[dict[str, Any] | str | bytes | bytearray | BytesIO]:
    """Check if the data is one of the valid types."""
    if isinstance(data, dict):
        return all(isinstance(key, str) for key in data if key)  # pyright: ignore[reportUnknownVariableType]
    return isinstance(data, str | bytes | bytearray | BytesIO)


class CohereEmbeddingRequestBody(BaseBedrockModel):
    """Request body for Cohere embedding model."""

    input_type: Annotated[
        Literal["search_document", "search_query", "classification", "clustering", "image"],
        Field(description="The type of input to generate embeddings for."),
    ]
    texts: Annotated[
        list[Annotated[str, Field(max_length=2048)]],
        Field(description="The input texts to generate embeddings for.", max_length=96),
    ]
    images: Annotated[
        list[str] | None,
        Field(
            description="The input image (as base64-encoded strings) to generate embeddings for.",
            max_length=1,  # your read that right, only one image at a time... even if you give it as a list...
        ),
    ] = None
    truncate: Annotated[
        Literal["NONE", "START", "END"] | None, Field(description="Truncation strategy.")
    ] = None
    embedding_types: Annotated[
        list[Literal["float", "int8", "uint8", "binary", "ubinary"]] | None,
        Field(
            description="The type of embeddings to generate. You can specify one or more types. Default is float."
        ),
    ] = None

    @model_serializer
    def serialize(self) -> BytesIO:
        """Serialize the model to a UTF-8 encoded JSON byte stream.

        Bedrock expects the body to be a byte stream (e.g. `BytesIO`).
        """
        return shared_serializer(self)

    @model_validator(mode="before")
    @classmethod
    def _validate_input(cls, data: Any, info: ValidationInfo) -> Any:
        """Ensure that only one of `input_text` or `input_texts` is provided."""
        return shared_validator(cls, data, info, "request")


class TitanEmbeddingV2RequestBody(BaseBedrockModel):
    """Request body for Titan Embedding V2. Note that it's one document per request.

    This model serializes to the JSON body that Bedrock expects, **even when serialized to Python dicts**.
    """

    input_text: Annotated[
        str, Field(description="The input text to generate embeddings for.", max_length=50_000)
    ]
    dimensions: Annotated[
        Literal[1024, 512, 256],
        Field(description="The number of dimensions for the generated embeddings."),
    ] = 1024
    normalize: Annotated[
        bool,
        Field(
            description="Whether to normalize the embeddings. Amazon defaults to False, but we default to True for our purposes."
        ),
    ] = True
    embedding_types: Annotated[
        list[Literal["float", "binary"]] | None,
        Field(
            description="The type of embeddings to generate. You can specify one or both types. I guess that could be useful if you want to keep your options open, especially once data gets stale."
        ),
    ] = None

    @model_serializer
    def serialize(self) -> BytesIO:
        """Serialize the model to a UTF-8 encoded JSON byte stream.

        Bedrock expects the body to be a byte stream (e.g. `BytesIO`).
        """
        return shared_serializer(self)

    @model_validator(mode="before")
    @classmethod
    def _validate_input(cls, data: Any, info: ValidationInfo) -> Any:
        """Ensure that only one of `input_text` or `input_texts` is provided."""
        return shared_validator(cls, data, info, "request")


def shared_serializer(
    instance: CohereEmbeddingRequestBody
    | TitanEmbeddingV2RequestBody
    | CohereEmbeddingResponse
    | TitanEmbeddingV2Response,
) -> BytesIO:
    """Shared serializer to serialize the model to a UTF-8 encoded JSON byte stream."""
    return BytesIO(instance.model_dump_json().encode("utf-8"))


def shared_validator(
    _cls: type[
        CohereEmbeddingRequestBody
        | TitanEmbeddingV2RequestBody
        | CohereEmbeddingResponse
        | TitanEmbeddingV2Response
    ],
    data: Any,
    info: ValidationInfo,
    kind: Literal["request", "response"] = "request",
) -> Any:
    """Shared validator to route JSON/text/bytes to the appropriate Bedrock model."""
    mode = info.mode

    if isinstance(data, BytesIO):
        data = data.getvalue()

    if not is_one_of_valid_types(data):
        raise ValidationError(
            f"Invalid data type. Expected one of: dict, str, bytes, bytearray, BytesIO. Full validation info:\n{info}"
        )
    data = cast(dict[str, Any] | str | bytes | bytearray, data)
    if kind == "request":
        return _handle_data_type_validation(
            mode,
            data,
            CohereEmbeddingRequestBody if is_cohere_request(data) else TitanEmbeddingV2RequestBody,
        )
    return _handle_data_type_validation(
        mode,
        cast(dict[str, Any] | bytes | bytearray, data),
        CohereEmbeddingResponse if is_cohere_response(data) else TitanEmbeddingV2Response,
    )


def _handle_data_type_validation(
    mode: Literal["python", "json"],
    data: dict[str, Any] | bytes | bytearray,
    cls: type[
        CohereEmbeddingRequestBody
        | TitanEmbeddingV2RequestBody
        | CohereEmbeddingResponse
        | TitanEmbeddingV2Response
    ],
) -> (
    dict[str, Any]
    | CohereEmbeddingRequestBody
    | TitanEmbeddingV2RequestBody
    | CohereEmbeddingResponse
    | TitanEmbeddingV2Response
):
    """Handle data type validation for Bedrock request/response models.

    - If Pydantic is running in python mode and a dict is provided, return the dict so
      Pydantic will validate it normally into the provided cls.
    - Otherwise, parse the provided JSON (bytes/str) into the target cls.
    """
    if mode == "python" and isinstance(data, dict):
        return data

    # Otherwise parse JSON text/bytes into the requested model.
    # model_validate_json accepts str or bytes
    return cls.model_validate_json(cast(str | bytes | bytearray, data))


class BedrockInvokeEmbeddingRequest(BaseBedrockModel):
    """Request for Bedrock embedding."""

    body: Annotated[
        TitanEmbeddingV2RequestBody | CohereEmbeddingRequestBody,
        Field(
            description=(
                "The request body for the embedding. This must be either a TitanEmbeddingV2RequestBody or a CohereEmbeddingRequestBody. When serialized to Python or JSON, this will be a UTF-8 encoded JSON string. Amazon requires the body to be a byte stream (e.g. `BinaryIO`)"
            )
        ),
    ]
    content_type: Annotated[
        Literal["application/json"],
        Field(description="The content type of the body. This must be 'application/json'."),
    ] = "application/json"
    accept: Annotated[
        Literal["application/json"],
        Field(description="The accept header. This must be 'application/json'."),
    ] = "application/json"
    model_id: Annotated[
        str,
        Field(
            description="The model ID to use for generating embeddings. The value for this depends on the model, your account, and other factors. [See the Bedrock docs](https://boto3.amazonaws.com/v1/documentation/api/latest/reference/services/bedrock-runtime/client/invoke_model.html) for more information. tl;dr use the model ARN if you aren't sure."
        ),
    ]
    trace: Annotated[
        Literal["ENABLED", "DISABLED", "ENABLED_FULL"],
        Field(
            description="The trace level to use for the request. This controls the amount of tracing information returned in the response."
        ),
    ] = "DISABLED"
    guardrail_identifier: Annotated[
        str | None,
        Field(
            description="The guardrail identifier to use for the request. This is used to enforce safety and compliance policies. We'll default to null/None. If you need this, you'll know."
        ),
    ] = None
    guardrail_version: Annotated[
        str | None, Field(description="The guardrail version to use, if using guardrail.")
    ] = None
    performance_config_latency: Annotated[
        Literal["standard", "optimized"],
        Field(
            description="The performance configuration to use for the request. This controls the latency and throughput of the request."
        ),
    ] = "standard"


class TitanEmbeddingV2Response(BaseBedrockModel):
    """Response from Titan Embedding V2."""

    embedding: Annotated[
        Sequence[float], Field(description="The generated embedding as a list of floats.")
    ]
    input_text_token_count: Annotated[
        int, Field(description="The number of tokens in the input text.")
    ]
    embeddings_by_type: Annotated[
        dict[Literal["float", "binary"], list[float] | list[int]],
        Field(description="The generated embeddings by type."),
    ]

    @model_serializer
    def serialize(self) -> BytesIO:
        """Serialize the model to a UTF-8 encoded JSON byte stream."""
        return shared_serializer(self)

    @model_validator(mode="before")
    @classmethod
    def _validate_input(cls, data: Any, info: ValidationInfo) -> Any:
        return shared_validator(cls, data, info, "response")


class ImageDescription(BaseBedrockModel):
    """Description of an image in the request."""

    width: PositiveInt
    height: PositiveInt
    fmt: Annotated[str, Field(alias="format")]
    bit_depth: PositiveInt


class CohereEmbeddingResponse(BaseBedrockModel):
    """Response from Cohere embedding."""

    embeddings: Annotated[
        Sequence[Sequence[float] | Sequence[Sequence[int]]],
        Field(
            description="The generated embeddings as a list of lists. Floats or ints depending on type."
        ),
    ]
    id: Annotated[str, Field(description="The ID of the request.")]
    response_type: Annotated[
        Literal["embedding_floats"], Field(description="The type of response.")
    ] = "embedding_floats"
    texts: Annotated[
        list[str] | None, Field(description="The input texts for the embedding request.")
    ]
    images: Annotated[
        list[ImageDescription] | None,
        Field(description="A description of the image in the request."),
    ] = None

    @model_serializer
    def serialize(self) -> BytesIO:
        """Serialize the model to a UTF-8 encoded JSON byte stream."""
        return shared_serializer(self)

    @model_validator(mode="before")
    @classmethod
    def _validate_input(cls, data: Any, info: ValidationInfo) -> Any:
        return shared_validator(cls, data, info, "response")


class InvokeRequestDict(TypedDict, total=False):
    """Request dict for invoking the model."""

    body: Required[BytesIO]
    content_type: Required[Literal["application/json"]]
    accept: Required[Literal["application/json"]]
    model_id: Required[str]
    trace: NotRequired[Literal["ENABLED", "DISABLED", "ENABLED_FULL"]]
    guardrail_identifier: NotRequired[str | None]
    guardrail_version: NotRequired[str | None]
    performance_config_latency: NotRequired[Literal["standard", "optimized"]]


class BedrockInvokeEmbeddingResponse(BaseBedrockModel):
    """Response from Bedrock embedding."""

    body: Annotated[
        TitanEmbeddingV2Response | CohereEmbeddingResponse,
        Field(
            description="The body of the response. This is what AWS calls a `StreamingBody` response -- a bytestream. It will contain a UTF-8 encoded JSON string that will be either be the JSON-serialized form of TitanEmbeddingV2Response or CohereEmbeddingResponse, depending on which model you used."
        ),
    ]
    content_type: Annotated[
        str,
        Field(
            description="The mimetype of the response body. Most likely 'application/json', but AWS isn't clear on this."
        ),
    ] = "application/json"

    @classmethod
    def from_boto3_response(cls, response: Any) -> BedrockInvokeEmbeddingResponse:
        """Create a BedrockInvokeEmbeddingResponse from a boto3 response."""
        return cls.model_validate_json(response, by_alias=True)


try:
    from boto3 import client as bedrock_client
    from botocore.client import BaseClient

    bedrock_client = bedrock_client("bedrock-runtime")

except ImportError as e:
    logger.exception(
        "Failed to import boto3. Bedrock embedding provider will not work. You should install boto3."
    )
    raise RuntimeError("Failed to import boto3.") from e


class BedrockEmbeddingProvider(EmbeddingProvider[BaseClient]):
    """Bedrock embedding provider."""

    _client: BaseClient = bedrock_client
    _provider: Provider = Provider.BEDROCK
    _caps: EmbeddingModelCapabilities

    _doc_kwargs: ClassVar[dict[str, Any]] = {}
    _query_kwargs: ClassVar[dict[str, Any]] = {}

    def _initialize(self) -> None:
        self._preprocessor = super()._input_transformer
        self._postprocessor = self._handle_response

    def _handle_response(
        self, response: dict[str, Any]
    ) -> Sequence[Sequence[float]] | Sequence[Sequence[int]]:
        """Handle the response from Bedrock for embedding requests."""
        if "cohere" in self._caps.name.lower():
            return self._handle_cohere_response(response)
        return self._handle_titan_response(response)

    def _handle_titan_response(
        self, response: dict[str, Any]
    ) -> Sequence[Sequence[float]] | Sequence[Sequence[int]]:
        """Handle the response from Titan for embedding requests."""
        deserialized = BedrockInvokeEmbeddingResponse.from_boto3_response(response)
        if (
            isinstance(deserialized.body, TitanEmbeddingV2Response)
            and hasattr(deserialized.body, "input_text_token_count")
            and (count := deserialized.body.input_text_token_count)
        ):
            self._update_token_stats(token_count=count)
        return (
            [deserialized.body.embedding]
            if isinstance(deserialized.body, TitanEmbeddingV2Response)
            else []
        )

    def _handle_cohere_response(
        self, response: dict[str, Any]
    ) -> Sequence[Sequence[float]] | Sequence[Sequence[int]]:
        """Handle the response from Bedrock for embedding requests and normalize to Sequence[float]."""
        deserialized = BedrockInvokeEmbeddingResponse.from_boto3_response(response)
        if not isinstance(deserialized.body, CohereEmbeddingResponse):
            raise TypeError("Response body is not a CohereEmbeddingResponse.")
        return (
            cast(
                "Sequence[Sequence[float]] | Sequence[Sequence[int]]", deserialized.body.embeddings
            )
            if deserialized.body
            else []
        )

    def _create_request(self, inputs: Sequence[CodeChunk]) -> list[InvokeRequestDict]:
        """Create the Bedrock embedding request."""
        requests: list[BedrockInvokeEmbeddingRequest] = []
        if "cohere" in self._caps.name.lower():
            texts = [self._process_input(doc) for doc in inputs]
            texts = self.chunks_to_strings([subitem for item in texts for subitem in item])
            body = {
                "input_type": "search_document" if len(texts) > 1 else "search_query",
                "texts": texts,
                "embedding_types": ["float"],
            }
            requests.append(
                BedrockInvokeEmbeddingRequest.model_validate({
                    "body": body,
                    "model_id": self._caps.name,
                })
            )
        else:
            text = self._process_input(inputs)
            processed = self.chunks_to_strings(text)
            for doc in processed:
                if len(doc) > 50_000:
                    raise ValueError(
                        f"Input text is too long for Titan Embedding V2. Max length is 50,000 characters. Input length is {len(doc)} characters."
                    )
                body = TitanEmbeddingV2RequestBody.model_validate({
                    "input_text": doc,
                    "dimensions": 1024,
                    "normalize": True,
                    "embedding_types": ["float"],
                })
                requests.append(
                    BedrockInvokeEmbeddingRequest.model_validate({
                        "body": body,
                        "model_id": self._caps.name,
                    })
                )

        return [InvokeRequestDict(**dict(req.model_dump(by_alias=True))) for req in requests]
