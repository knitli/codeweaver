# sourcery skip: avoid-single-character-names-variables
# SPDX-FileCopyrightText: 2025 (c) 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
"""Google embedding provider."""

from __future__ import annotations

import contextlib
import logging


with contextlib.suppress(Exception):
    import warnings

    from pydantic.warnings import PydanticDeprecatedSince212

    warnings.simplefilter("ignore", PydanticDeprecatedSince212)
    import os

    os.environ["PYTHONWARNINGS"] = "ignore::pydantic.warnings.PydanticDeprecatedSince212"

from collections.abc import Iterable, Sequence
from typing import TYPE_CHECKING, Any, Literal, cast

from google.genai.types import HttpOptions

from codeweaver.core.types.enum import BaseEnum
from codeweaver.exceptions import ConfigurationError
from codeweaver.providers.embedding.providers.base import EmbeddingProvider


if TYPE_CHECKING:
    from codeweaver.core.chunks import CodeChunk

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
    import google.genai as genai

    from google.genai import errors as genai_errors
    from google.genai import types as genai_types


except ImportError as e:
    raise ConfigurationError(
        "The 'google-genai' package is required to use the Google embedding provider. Please install it with 'pip install codeweaver[google]'."
    ) from e


class GoogleEmbeddingProvider(EmbeddingProvider[genai.Client]):
    """Google embedding provider."""

    client: genai.Client

    async def _report_stats(self, documents: Iterable[genai_types.Part]) -> None:
        """Report token usage statistics."""
        http_kwargs = self.doc_kwargs.get("config", {}).get("http_options", {})
        try:
            response = await self.client.aio.models.count_tokens(
                model=self.caps.name,
                contents=list(documents),
                config=genai_types.CountTokensConfig(http_options=http_kwargs),
            )
            if response and response.total_tokens is not None and response.total_tokens > 0:
                _ = self._fire_and_forget(
                    lambda: self._update_token_stats(token_count=cast(int, response.total_tokens))
                )
        except genai_errors.APIError:
            logger.exception(
                "Error requesting token stats from Google. Falling back to local tokenizer for approximation."
            )
            _ = self._fire_and_forget(
                lambda: self._update_token_stats(
                    from_docs=[cast(str, part.text) for part in documents]
                )
            )

    async def _embed_documents(
        self, documents: Sequence[CodeChunk], **kwargs: Any
    ) -> list[list[float]]:
        """
        Embed the documents using the Google embedding provider.
        """
        readied_docs = self.chunks_to_strings(documents)
        config_kwargs = self.doc_kwargs.get("config", {})
        content = (genai_types.Part.from_text(text=cast(str, doc)) for doc in readied_docs)
        response = await self.client.aio.models.embed_content(
            model=self.caps.name,
            contents=list(content),
            config=genai_types.EmbedContentConfig(
                task_type=str(GoogleEmbeddingTasks.RETRIEVAL_DOCUMENT), **config_kwargs
            ),
            **kwargs,
        )
        embeddings = [
            item.values
            for item in cast(list[genai_types.ContentEmbedding], response.embeddings)
            if response.embeddings is not None and item
        ] or [[]]
        _ = await self._report_stats(content)
        return embeddings

    async def _embed_query(self, query: Sequence[str], **kwargs: Any) -> list[list[float]]:
        """
        Embed the query using the Google embedding provider.
        """
        config_kwargs = self.query_kwargs.get("config", {})
        content = [genai_types.Part.from_text(text=q) for q in query]
        response = await self.client.aio.models.embed_content(
            model=self.caps.name,
            contents=cast(genai_types.ContentListUnion, content),
            config=genai_types.EmbedContentConfig(
                task_type=str(GoogleEmbeddingTasks.CODE_RETRIEVAL_QUERY), **config_kwargs
            ),
            **kwargs,
        )
        embeddings = [
            item.values
            for item in cast(list[genai_types.ContentEmbedding], response.embeddings)
            if response.embeddings is not None and item
        ] or [[]]
        _ = await self._report_stats(content)
        return embeddings
