# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Custom type definitions for boto3.

After fussing too much with other type stub packages, I decided it was easiest to just create my own for the small subset of boto3 that I use.
"""

from pydantic import JsonValue
from io import BytesIO
from typing import Literal, overload, TypedDict, Required, NotRequired

from botocore.client import BaseClient

# ===========================================================================
# *                    Embedding Request/Response Types
# ===========================================================================

# ===========================
# *    Response
# ===========================

class BedrockInvokeModelResponseDict(TypedDict):
    body: bytes
    content_type: Literal["application/json", "text/plain", "application/octet-stream"]

# ===========================
# *    Request
# ===========================

class BedrockInvokeRequest(TypedDict, total=False):
    body: Required[BytesIO]
    content_type: Required[Literal["application/json", "text/plain", "application/octet-stream"]]
    accept: Required[Literal["application/json", "text/plain", "application/octet-stream"]]
    trace: NotRequired[Literal["ENABLED", "DISABLED", "ENABLED_FULL"]]
    guardrail_identifier: NotRequired[str]
    guardrail_version: NotRequired[str]
    performance_config_latency: NotRequired[Literal["standard", "optimized"]]

# ===========================
# * Embedding client (BedrockRuntimeClient)
# Client for embedding requests and responses

class BedrockRuntimeClient(BaseClient):
    """Invokes a Bedrock model."""
    def invoke_model(self, **kwargs: BedrockInvokeRequest) -> BedrockInvokeModelResponseDict: ...

# ===========================================================================
# *                  Reranking Request/Response Types
# ===========================================================================

# ===========================
# *      Requests
# ===========================

class BedrockTextQueryDict(TypedDict, total=False):
    """Represents a text query for Bedrock reranking."""

    text_query: Required[dict[Literal["text"], str]]
    kind: Required[Literal["TEXT"]]

class InlineDocumentSourceDict(TypedDict, total=False):
    """Represents an inline document source for Bedrock reranking."""

    inline_document_source: Required[DocumentSourceDict]
    kind: Required[Literal["INLINE"]]

class BedrockRerankModelConfigurationDict(TypedDict, total=False):
    """Represents the configuration for a Bedrock reranking model."""

    additional_model_request_fields: NotRequired[dict[str, JsonValue]]
    model_arn: Required[str]

class BedrockRerankConfigurationDict(TypedDict, total=False):
    """Represents the configuration for a Bedrock reranking model."""

    model_configuration: Required[BedrockRerankModelConfigurationDict]
    number_of_results: Required[int]

class RerankingConfigurationDict(TypedDict, total=False):
    """Represents the configuration for Bedrock reranking."""

    bedrock_reranking_configuration: Required[BedrockRerankConfigurationDict]
    kind: Required[Literal["BEDROCK_RERANKING_MODEL"]]

class BedrockRerankRequest(TypedDict, total=False):
    queries: Required[list[BedrockTextQueryDict]]

    reranking_configuration: Required[RerankingConfigurationDict]

    sources: Required[list[InlineDocumentSourceDict]]

    next_token: NotRequired[str]

# ===========================
# *    Response
# ===========================

class DocumentSourceDict(TypedDict, total=False):
    """Represents a document source for Bedrock reranking.

    Must provide either json_document or text_document, and a kind that corresponds to the provided document.
    """

    json_document: NotRequired[dict[str, JsonValue]]
    text_document: NotRequired[dict[Literal["text"], str]]
    kind: Required[Literal["JSON", "TEXT"]]

class BedrockRerankResultItemDict(TypedDict):
    document: DocumentSourceDict

    index: int

    relevance_score: float

class BedrockRerankResultDict(TypedDict, total=False):
    results: Required[list[BedrockRerankResultItemDict]]
    next_token: NotRequired[str]

# ===========================================================================
# * Reranking Client (AgentsforBedrockRuntimeClient)
# same client also for Agents, but those are typed in Pydantic-AI

class AgentsforBedrockRuntimeClient(BaseClient):
    def rerank(self, **kwargs: BedrockRerankRequest) -> BedrockRerankResultDict: ...

# ===========================================================================
# *                   Boto3 Client Getter
# ===========================================================================

@overload
def boto3(
    client_name: Literal["bedrock-runtime"], /, **kwargs: Any
) -> AgentsforBedrockRuntimeClient: ...
@overload
def boto3(client_name: Literal["bedrock"], /, **kwargs: Any) -> BedrockRuntimeClient: ...
def boto3(
    client_name: Literal["bedrock", "bedrock-runtime"], /, **kwargs: Any
) -> [BedrockRuntimeClient | AgentsforBedrockRuntimeClient]: ...

__all__ = [
    "AgentsforBedrockRuntimeClient",
    "BedrockInvokeModelResponseDict",
    "BedrockInvokeRequest",
    "BedrockRerankConfigurationDict",
    "BedrockRerankModelConfigurationDict",
    "BedrockRerankRequest",
    "BedrockRerankResultDict",
    "BedrockRerankResultItemDict",
    "BedrockRuntimeClient",
    "BedrockTextQueryDict",
    "DocumentSourceDict",
    "InlineDocumentSourceDict",
    "RerankingConfigurationDict",
    "boto3",
]
