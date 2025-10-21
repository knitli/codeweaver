# sourcery skip: avoid-single-character-names-variables
# SPDX-FileCopyrightText: 2025 (c) 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
"""Google embedding provider."""

import logging

from collections.abc import Iterable, Mapping, Sequence
from typing import Any, Literal, cast

from google.genai.types import HttpOptions

from codeweaver._data_structures import CodeChunk
from codeweaver._types import BaseEnum
from codeweaver.embedding.providers.base import EmbeddingProvider
from codeweaver.exceptions import ConfigurationError


logger = logging.getLogger(__name__)


def get_shared_kwargs() -> dict[str, dict[str, HttpOptions] | int]:
    """Get the default kwargs for the Google embedding provider."""
    from google.genai.types import HttpOptions

    return {
        "config": {"http_options": HttpOptions(api_version="v1alpha")},
        "output_dimensionality": 768,
    }


class GoogleEmbeddingTasks(BaseEnum):
    """Enum of the available modes for the Google embedding provider."""

    SENTENCE_SIMILARITY = "sentence_similarity"
    CLASSIFICATION = "classification"
    CLUSTERING = "clustering"
    RETRIEVAL_DOCUMENT = "retrieval_document"
    RETRIEVAL_QUERY = "retrieval_query"
    CODE_RETRIEVAL_QUERY = "code_retrieval_query"
    QUESTION_ANSWERING = "question_answering"
    FACT_VERIFICATION = "fact_verification"

    def __str__(
        self,
    ) -> Literal[
        "sentence_similarity",
        "classification",
        "clustering",
        "retrieval_document",
        "retrieval_query",
        "code_retrieval_query",
        "question_answering",
        "fact_verification",
    ]:
        """Returns the enum value."""
        return self.value


try:
    from google import genai
    from google.genai import errors, types


except ImportError as e:
    raise ConfigurationError(
        "The 'google-genai' package is required to use the Google embedding provider. Please install it with 'pip install codeweaver[provider-google]'."
    ) from e


class GoogleEmbeddingProvider(EmbeddingProvider[genai.Client]):
    """Google embedding provider."""

    _client: genai.Client

    async def _report_stats(self, documents: Iterable[types.Part]) -> None:
        """Report token usage statistics."""
        http_kwargs = self.doc_kwargs.get("config", {}).get("http_options", {})
        try:
            response = await self._client.aio.models.count_tokens(
                model=self._caps.name,
                contents=list(documents),
                config=types.CountTokensConfig(http_options=http_kwargs),
            )
            if response and response.total_tokens is not None and response.total_tokens > 0:
                _ = self._fire_and_forget(
                    lambda: self._update_token_stats(token_count=cast(int, response.total_tokens))
                )
        except errors.APIError:
            logger.exception(
                "Error requesting token stats from Google. Falling back to local tokenizer for approximation."
            )
            _ = self._fire_and_forget(
                lambda: self._update_token_stats(
                    from_docs=[cast(str, part.text) for part in documents]
                )
            )

    async def _embed_documents(  # pyright: ignore[reportIncompatibleMethodOverride]
        self, documents: Sequence[CodeChunk], **kwargs: Mapping[str, Any]
    ) -> list[list[float]]:
        """
        Embed the documents using the Google embedding provider.
        """
        readied_docs = self.chunks_to_strings(documents)
        config_kwargs = self.doc_kwargs.get("config", {})
        content = (types.Part.from_text(text=cast(str, doc)) for doc in readied_docs)
        response = await self._client.aio.models.embed_content(
            model=self._caps.name,
            contents=list(content),
            config=types.EmbedContentConfig(
                task_type=str(GoogleEmbeddingTasks.RETRIEVAL_DOCUMENT), **config_kwargs
            ),
            **kwargs,
        )
        embeddings = [
            item.values
            for item in cast(list[types.ContentEmbedding], response.embeddings)
            if response.embeddings is not None and item
        ] or [[]]
        _ = await self._report_stats(content)
        return embeddings  # pyright: ignore[reportReturnType]

    async def _embed_query(
        self, query: Sequence[str], **kwargs: Mapping[str, Any]
    ) -> list[list[float]]:
        """
        Embed the query using the Google embedding provider.
        """
        config_kwargs = self.query_kwargs.get("config", {})
        content = [types.Part.from_text(text=q) for q in query]
        response = await self._client.aio.models.embed_content(
            model=self._caps.name,
            contents=cast(types.ContentListUnion, content),
            config=types.EmbedContentConfig(
                task_type=str(GoogleEmbeddingTasks.CODE_RETRIEVAL_QUERY), **config_kwargs
            ),
            **kwargs,
        )
        embeddings = [
            item.values
            for item in cast(list[types.ContentEmbedding], response.embeddings)
            if response.embeddings is not None and item
        ] or [[]]
        _ = await self._report_stats(content)
        return embeddings  # pyright: ignore[reportReturnType]
