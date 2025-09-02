# SPDX-FileCopyrightText: 2025 (c) 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
"""Google embedding provider."""

from collections.abc import Sequence
from typing import Any, Literal, cast

from google.genai.types import HttpOptions

from codeweaver._common import BaseEnum
from codeweaver._data_structures import CodeChunk
from codeweaver.embedding.providers.base import EmbeddingProvider


def get_shared_kwargs() -> dict[str, dict[str, HttpOptions] | int]:
    """Common baseline kwargs for the GoogleEmbeddingProvider."""
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
    from google.genai import types


except ImportError as e:
    raise ImportError(
        "The 'google-genai' package is required to use the Google embedding provider. Please install it with 'pip install google-genai'."
    ) from e


class GoogleEmbeddingProvider(EmbeddingProvider[genai.Client]):
    """Google embedding provider."""

    _client: genai.Client

    async def _embed_documents(self, documents: Sequence[CodeChunk], **kwargs: dict[str, Any]):
        readied_docs = self.chunks_to_strings(documents)
        config_kwargs = self.doc_kwargs.get("config", {})
        response = await self._client.aio.models.embed_content(
            model=self._caps.name,
            contents=cast(types.ContentListUnion, readied_docs),
            config=types.EmbedContentConfig(
                task_type=str(GoogleEmbeddingTasks.RETRIEVAL_DOCUMENT), **config_kwargs
            ),
        )
