# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

# sourcery skip: avoid-single-character-names-variables, no-complex-if-expressions
"""Bedrock reranking provider.

Pydantic models and provider class for Bedrock reranking. Excuse the many pyright ignores -- boto3 is boto3.
"""

from __future__ import annotations

import asyncio
import logging

from collections.abc import Iterator, Sequence
from typing import TYPE_CHECKING, Annotated, Any, Literal, Self, cast

from pydantic import AliasGenerator, ConfigDict, Field, JsonValue, PositiveInt, model_validator
from pydantic.alias_generators import to_camel, to_snake

from codeweaver.config.providers import AWSProviderSettings
from codeweaver.core.types.models import BasedModel
from codeweaver.exceptions import ValidationError as CodeWeaverValidationError
from codeweaver.providers.provider import Provider
from codeweaver.providers.reranking.capabilities.amazon import get_amazon_reranking_capabilities
from codeweaver.providers.reranking.capabilities.base import RerankingModelCapabilities
from codeweaver.providers.reranking.providers.base import RerankingProvider, RerankingResult


if TYPE_CHECKING:
    from codeweaver.core.chunks import CodeChunk, StructuredDataInput


class BaseBedrockModel(BasedModel):
    """Base model for Bedrock-related Pydantic models."""

    model_config = BasedModel.model_config | ConfigDict(
        alias_generator=AliasGenerator(validation_alias=to_snake, serialization_alias=to_camel),
        from_attributes=True,
        # spellchecker:off
        ser_json_inf_nan="null",
        # spellchecker:on
        serialize_by_alias=True,
    )


logger = logging.getLogger(__name__)

VALID_REGIONS = ["us-west-2", "ap-northeast-1", "ca-central-1", "eu-central-1"]
"""AWS has rerank models available in very few regions. https://docs.aws.amazon.com/bedrock/latest/userguide/models-supported.html"""
VALID_REGION_PATTERN = "|".join(VALID_REGIONS)


class BedrockTextQuery(BaseBedrockModel):
    """A query for reranking."""

    text_query: Annotated[
        dict[
            Literal["text"],
            Annotated[str, Field(description="""The text of the query.""", max_length=32_000)],
        ],
        Field(description="""The text query."""),
    ]
    # we need to avoid the `type` keyword in python
    kind: Annotated[
        Literal["TEXT"], Field(description="""The kind of query.""", serialization_alias="type")
    ] = "TEXT"


class BedrockRerankModelConfiguration(BaseBedrockModel):
    """Configuration for a Bedrock reranking model."""

    additional_model_request_fields: Annotated[
        None,
        Field(
            description="""A json object where each key is a model parameter and the value is the value for that parameter. Currently there's not any values worth setting that can't be set elsewhere."""
        ),
    ] = None
    model_arn: Annotated[
        str,
        Field(
            description="""The ARN of the model.""",
            pattern=r"^arn:aws:bedrock:(" + VALID_REGION_PATTERN + r"):\d{12}:.*$",
        ),
    ]


class BedrockRerankConfiguration(BaseBedrockModel):
    """Configuration for Bedrock reranking."""

    model_configuration: Annotated[
        BedrockRerankModelConfiguration, Field(description="""The model configuration.""")
    ]
    number_of_results: Annotated[
        PositiveInt, Field(description="""Number of results to return -- this is `top_n`.""")
    ] = 40


class RerankConfiguration(BaseBedrockModel):
    """Configuration for reranking."""

    bedrock_reranking_configuration: Annotated[
        BedrockRerankConfiguration, Field(description="""Configuration for reranking.""")
    ]
    kind: Annotated[
        Literal["BEDROCK_RERANKING_MODEL"],
        Field(description="""The kind of configuration.""", serialization_alias="type"),
    ] = "BEDROCK_RERANKING_MODEL"

    @classmethod
    def from_arn(cls, arn: str, top_n: PositiveInt = 40) -> Self:
        """Create a RerankConfiguration from a Bedrock model ARN."""
        return cls.model_validate({
            "bedrock_reranking_configuration": {
                "model_configuration": {"model_arn": arn},
                "number_of_results": top_n,
            }
        })


class DocumentSource(BaseBedrockModel):
    """A document source for reranking."""

    json_document: Annotated[
        dict[str, JsonValue] | None,
        Field(
            description="""A Json document to rerank against. Practically, CodeWeaver will always use this."""
        ),
    ]
    text_document: Annotated[
        dict[Literal["text"], str] | None,
        Field(description="""A text document to rerank against.""", max_length=32_000),
    ] = None
    kind: Annotated[
        Literal["JSON", "TEXT"],
        Field(description="""The kind of document.""", serialization_alias="type"),
    ] = "JSON"

    @model_validator(mode="after")
    def validate_documents(self) -> Self:
        """Validate that exactly one document type is provided."""
        if (self.json_document and self.text_document) or (
            not self.json_document and not self.text_document
        ):
            raise CodeWeaverValidationError(
                "Bedrock reranking requires exactly one document type",
                details={
                    "provider": "bedrock",
                    "model": "reranking",
                    "json_document_provided": self.json_document is not None,
                    "text_document_provided": self.text_document is not None,
                },
                suggestions=[
                    "Provide either json_document OR text_document, not both",
                    "Ensure at least one document type is specified",
                    "Check the document format matches the model requirements",
                ],
            )
        return self


class BedrockInlineDocumentSource(BaseBedrockModel):
    """An inline document source for reranking."""

    inline_document_source: Annotated[
        DocumentSource, Field(description="""The inline document source to rerank.""")
    ]
    kind: Annotated[
        Literal["INLINE"],
        Field(description="""The kind of document source.""", serialization_alias="type"),
    ] = "INLINE"


class BedrockRerankRequest(BaseBedrockModel):
    """Request for Bedrock reranking."""

    queries: Annotated[
        list[BedrockTextQuery], Field(description="""List of text queries to rerank against.""")
    ]
    reranking_configuration: Annotated[
        RerankConfiguration, Field(description="""Configuration for reranking.""")
    ]
    sources: Annotated[
        list[BedrockInlineDocumentSource],
        Field(description="""List of document sources to rerank against."""),
    ]
    next_token: Annotated[str | None, Field()] = None


class BedrockRerankResultItem(BaseBedrockModel):
    """A single reranked result item."""

    document: Annotated[DocumentSource, Field(description="""The document that was reranked.""")]
    index: Annotated[
        PositiveInt,
        Field(description="""The ranking of the document in the results. (Lower is better.)"""),
    ]
    relevance_score: Annotated[
        float,
        Field(
            description="""The relevance score of the document. Higher values indicate greater relevance."""
        ),
    ]


class BedrockRerankingResult(BaseBedrockModel):
    """Result of a Bedrock reranking request."""

    results: Annotated[
        list[BedrockRerankResultItem], Field(description="""List of reranked results.""")
    ]
    next_token: Annotated[
        str | None, Field(description="""Token for the next set of results, if any.""")
    ] = None


try:
    from boto3 import client as boto3_client
    from types_boto3_bedrock_agent_runtime.client import AgentsforBedrockRuntimeClient

except ImportError as e:
    logger.exception("Failed to import boto3")
    raise ImportError("boto3 is not installed. Please install it with `pip install boto3`.") from e


def _to_doc_sources(documents: list[DocumentSource]) -> list[BedrockInlineDocumentSource]:
    return [
        BedrockInlineDocumentSource.model_validate([
            {"inline_document_source": doc.model_dump(mode="python"), "type": "INLINE"}
            for doc in documents
        ])
    ]


def bedrock_reranking_input_transformer(
    documents: StructuredDataInput,
) -> list[BedrockInlineDocumentSource]:  # this is the sources field of BedrockRerankRequest
    """Transform input documents into the format expected by the Bedrock API.

    We can't actually produce the full objects we need here with just the documents. We need the query and model config to construct the full object.
    We're going to handle that in the rerank method, and break type override law. 👮
    """
    from codeweaver.core.chunks import CodeChunk

    # Transform the input documents into the format expected by the Bedrock API
    if isinstance(documents, list | tuple | set):
        docs = [
            DocumentSource.model_validate(
                {"json_document": doc.serialize(), "text_document": None}
                if isinstance(doc, CodeChunk)
                else {"text_document": {"text": str(doc)}, "json_document": None, "kind": "TEXT"}
            )
            for doc in documents
        ]
    else:
        docs = (
            [
                DocumentSource.model_validate({
                    "json_document": documents.serialize(),
                    "text_document": None,
                })
            ]
            if isinstance(documents, CodeChunk)
            # this will never happen, but we do it to satisfy the type checker:
            else [
                DocumentSource.model_validate({
                    "text_document": {"text": str(documents)},
                    "json_document": None,
                    "kind": "TEXT",
                })
            ]
        )
    return _to_doc_sources(docs)


def bedrock_reranking_output_transformer(
    response: BedrockRerankingResult, original_chunks: tuple[CodeChunk, ...] | Iterator[CodeChunk]
) -> list[RerankingResult]:
    """Transform the Bedrock API response into the format expected by the reranking provider."""
    from codeweaver.core.chunks import CodeChunk

    parsed_response = BedrockRerankingResult.model_validate_json(cast(bytes, response))
    results: list[RerankingResult] = []
    for item in parsed_response.results:
        # pyright doesn't know that this will always be CodeChunk-as-JSON because that's what we send.
        chunk = CodeChunk.model_validate_json(item.document.json_document)
        results.append(
            RerankingResult(
                original_index=original_chunks.index(chunk)
                if isinstance(original_chunks, tuple)
                else tuple(original_chunks).index(chunk),
                score=item.relevance_score,
                batch_rank=item.index,
                chunk=chunk,
            )
        )
    return results


class BedrockRerankingProvider(RerankingProvider[AgentsforBedrockRuntimeClient]):
    """Provider for Bedrock reranking."""

    client: AgentsforBedrockRuntimeClient
    _provider = Provider.BEDROCK
    caps: RerankingModelCapabilities = get_amazon_reranking_capabilities()[0]
    model_configuration: RerankConfiguration

    _kwargs: dict[str, Any] | None

    _input_transformer = bedrock_reranking_input_transformer
    _output_transformer = bedrock_reranking_output_transformer

    def __init__(
        self,
        bedrock_provider_settings: AWSProviderSettings,
        model_config: RerankConfiguration | None = None,
        caps: RerankingModelCapabilities | None = None,
        client: AgentsforBedrockRuntimeClient | None = None,
        top_n: PositiveInt = 40,
        prompt: str | None = None,
        **kwargs: Any,
    ) -> None:
        """Override base init to set up Bedrock-specific client and configuration."""
        from pydantic import SecretStr

        # Prepare all values BEFORE calling super().__init__()
        bedrock_settings = {
            k: v.get_secret_value() if isinstance(v, SecretStr) else v
            for k, v in bedrock_provider_settings.items()
            if v is not None
        }
        model_configuration = model_config or RerankConfiguration.from_arn(
            bedrock_provider_settings["model_arn"], kwargs.get("top_n", 40) if kwargs else top_n
        )
        _ = bedrock_provider_settings.pop("model_arn")  # ty: ignore[invalid-argument-type]  # the typed dict is mine, I do what I want

        # Initialize client if not provided
        if client is None:
            client = boto3_client(  # ty: ignore[invalid-assignment,no-matching-overload]
                "bedrock-agent-runtime", **bedrock_settings
            )

        final_caps = caps or get_amazon_reranking_capabilities()[0]

        if not client:
            raise ValueError("Either a Bedrock client or provider settings must be provided.")

        # Call super().__init__() FIRST which handles all Pydantic initialization
        super().__init__(client=client, caps=final_caps, top_n=top_n, prompt=prompt, **kwargs)

        # Set instance attributes AFTER Pydantic initialization
        self._bedrock_provider_settings = bedrock_settings
        self.model_configuration = model_configuration

    async def _execute_rerank(
        self,
        query: str,
        documents: Sequence[BedrockInlineDocumentSource],
        *,
        top_n: int = 40,
        **kwargs: dict[str, Any] | None,
    ) -> Any:
        """
        Execute the reranking process.
        """
        query_obj = BedrockTextQuery.model_validate({"text_query": {"text": query}})
        config = self.model_configuration
        request = BedrockRerankRequest.model_validate({
            "queries": [query_obj],
            "sources": documents,
            "reranking_configuration": config,
        })
        loop = asyncio.get_running_loop()
        return await loop.run_in_executor(None, self.client.rerank, request)


__all__ = ("BedrockRerankingProvider", "BedrockRerankingResult")
