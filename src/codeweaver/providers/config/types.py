# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Shared types for providers configurations."""

from __future__ import annotations

import asyncio
import ssl

from collections.abc import Awaitable, Callable, Mapping
from dataclasses import asdict, dataclass, field
from typing import TYPE_CHECKING, Annotated, Any, Literal, NotRequired, TypedDict

from pydantic import Field, NonNegativeInt, PositiveInt, SecretStr

from codeweaver.core.constants import ZERO
from codeweaver.core.types import LiteralStringT
from codeweaver.providers.agent.capabilities import KnownAgentModelName


if TYPE_CHECKING:
    from qdrant_client.models import Document


class AzureOptions(TypedDict, total=False):
    """Azure-specific options."""

    model_deployment: str
    base_url: str | None
    api_base: str | None
    endpoint: str | None
    region_name: str | None
    api_key: (
        SecretStr | Callable[[], str | SecretStr] | Callable[[], Awaitable[str | SecretStr]] | None
    )


# Mirror types to avoid httpx dependency at module initialization
# These will accept httpx types at runtime but don't require httpx import
class HttpxClientParams(TypedDict, total=False):
    """Parameters for configuring an httpx client.

    Note: Type annotations use Any to avoid httpx import at initialization.
    At runtime, these accept the corresponding httpx types.
    """

    auth: NotRequired[Any]  # httpx._types.AuthTypes
    params: NotRequired[Any]  # httpx._types.QueryParamTypes
    headers: NotRequired[Any]  # httpx._types.HeaderTypes
    cookies: NotRequired[Any]  # httpx._types.CookieTypes
    verify: NotRequired[bool | ssl.SSLContext | str]
    cert: NotRequired[Any]  # httpx._types.CertTypes
    http1: NotRequired[bool]
    http2: NotRequired[bool]
    proxy: NotRequired[Any]  # httpx._types.ProxyTypes
    mounts: NotRequired[Mapping[str, Any]]  # Mapping[str, httpx._transports.AsyncBaseTransport]
    timeout: NotRequired[Any]  # httpx._types.TimeoutTypes
    follow_redirects: NotRequired[bool]
    limits: NotRequired[Any]  # httpx.Limits
    max_redirects: NotRequired[NonNegativeInt]
    event_hooks: NotRequired[Mapping[str, list[Callable[..., Any]]]]
    base_url: NotRequired[Any | str]  # httpx.URL | str
    transport: NotRequired[Any]  # httpx._transports.AsyncBaseTransport
    trust_env: NotRequired[bool]
    default_encoding: NotRequired[
        Literal["utf-8", "utf-16", "utf-32"]
        | Callable[[bytes], Literal["utf-8", "utf-16", "utf-32"]]
    ]


class CohereRequestOptionsDict(TypedDict, total=False):
    """Additional request options for the Cohere API."""

    timeout_in_seconds: NotRequired[PositiveInt]
    """Timeout for the request in seconds."""

    max_retries: NotRequired[PositiveInt]
    """Number of retries for the request in case of failure."""

    additional_headers: NotRequired[dict[str, Any]]
    """Additional headers to include in the request."""

    additional_query_parameters: NotRequired[dict[str, Any]]
    """Additional query parameters to include in the request."""


@dataclass(slots=True)
class Bm25Config:
    """CodeWeaver's BM25 configuration for Qdrant vector store."""

    k: float = 1.2
    "Frequency term saturation. Higher values = more impact on term frequency."
    b: float = 0.3
    "Document length normalization (0 to 1) -- higher numbers penalize long documents. We set this low because document length is not well correlated to relevance for code."
    avg_len: int = 512
    "Average document length for BM25 normalization. This is a placeholder value, in practice it's computed from the text batch for embedding."
    tokenizer = "WORD"
    "Tokenizer type to use for BM25. WORD is currently the best available for code, though less than ideal. Trying to submit a code specific tokenizer upstream is on the to-do list."
    language: Literal["none"] = "none"
    "Language for the tokenizer and stemmer -- we disable it with 'none' because language normalization messes up code."
    lowercase: bool = True
    "Whether to lowercase tokens. Defaults to True."
    ascii_folding: bool = False
    "Whether to fold ASCII characters. Defaults to False."
    stopwords: None = None
    "Stopwords to remove. Set to None to avoid loss of keywords like 'as' 'is', 'with' that have significance in code."
    stemmer: None = None
    "Stemmer to use for tokens. Set to None to avoid stemming code tokens."
    min_token_len: int = 1
    "Minimum token length to include in the index."
    max_token_len: int = 128
    "Maximum token length to include in the index."

    async def serialize_for_upsert(self, avg_length: int) -> dict[str, Any]:
        """Serialize the BM25 config for Qdrant upsert, updating avg_len."""
        await asyncio.sleep(ZERO)
        self.avg_len = avg_length
        return asdict(self)


@dataclass(slots=True)
class DocumentRepr:
    """A shell representation of a `qdrant_client.models.Document`. Document itself requires text for embedding, and a model name, which in our case is always `Qdrant/Bm25`, but this representation only includes the fields necessary for configuration purposes.

    We don't currently allow users to set these options directly -- we want to experiment and identify optimal configuration for general and specific code search use cases, so we need to control these settings internally.
    """

    model: Literal["Qdrant/Bm25"] = "Qdrant/Bm25"
    options: Bm25Config = field(default_factory=Bm25Config)

    async def serialize_for_upsert(self, texts: list[str]) -> list[Document]:
        """Serialize the document representations for Qdrant upsert."""
        await asyncio.sleep(ZERO)
        avg_length = sum(len(text.strip()) for text in texts) // len(texts) if texts else 0
        options = await self.options.serialize_for_upsert(avg_length)
        return [Document(text=text, model=self.model, options=options) for text in texts]


type AgentModelNameString = Annotated[
    KnownAgentModelName | LiteralStringT,
    Field(description="The model string, as it appears in `pydantic_ai.models.KnownModelName`."),
]
"""Type for agent model name strings."""


__all__ = (
    "AgentModelNameString",
    "AzureOptions",
    "Bm25Config",
    "CohereRequestOptionsDict",
    "DocumentRepr",
    "HttpxClientParams",
)
