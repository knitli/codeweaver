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
from typing import Any, ClassVar, Literal, cast

from codeweaver.core import BaseEnum, CodeChunk, ConfigurationError, Provider
from codeweaver.providers.embedding.providers.base import (
    EmbeddingCustomDeps,
    EmbeddingImplementationDeps,
    EmbeddingProvider,
)


logger = logging.getLogger(__name__)


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
        # normally we use .variable for string conversion, but it's more explicit this way (even if it's probably the same)
        return self.value


try:
    import google.genai as genai

    from google.genai import errors as genai_errors
    from google.genai import types as genai_types


except ImportError as e:
    raise ConfigurationError(
        r"The 'google-genai' package is required to use the Google embedding provider. Please install it with 'pip install code-weaver\[google]'."
    ) from e


class GoogleEmbeddingProvider(EmbeddingProvider[genai.Client]):
    """Google embedding provider."""

    client: genai.Client
    _provider: ClassVar[Literal[Provider.GOOGLE]] = Provider.GOOGLE

    def _initialize(
        self,
        impl_deps: EmbeddingImplementationDeps = None,
        custom_deps: EmbeddingCustomDeps = None,
        **kwargs: Any,
    ) -> None:
        """Initialize the Google embedding client."""
        # Nothing to initialize here - options are set in model_post_init

    async def _report_stats(self, documents: Iterable[genai_types.Part]) -> None:
        """Report token usage statistics."""
        try:
            response = await self.client.aio.models.count_tokens(
                model=self.caps.name,
                contents=list(documents),
                config=genai_types.CountTokensConfig(),
            )
            if response and response.total_tokens is not None and response.total_tokens > 0:
                loop = self._get_loop()
                _ = self._fire_and_forget(
                    lambda: self._update_token_stats(token_count=cast(int, response.total_tokens)),
                    loop=loop,
                )
        except genai_errors.APIError:
            logger.warning(
                "Error requesting token stats from Google. Falling back to local tokenizer for approximation.",
                exc_info=True,
            )
            loop = self._get_loop()
            _ = self._fire_and_forget(
                lambda: self._update_token_stats(
                    from_docs=[cast(str, part.text) for part in documents]
                ),
                loop=loop,
            )

    async def _embed_documents(
        self, documents: Sequence[CodeChunk], **kwargs: Any
    ) -> list[list[float]]:
        """
        Embed the documents using the Google embedding provider.
        """
        config_kwargs = (self.embed_options.as_settings() if self.embed_options else {}) | (
            kwargs or {}
        )
        readied_docs = self.chunks_to_strings(documents)
        content = (genai_types.Part.from_text(text=cast(str, doc)) for doc in readied_docs)
        response = await self.client.aio.models.embed_content(
            model=self.caps.name,
            contents=list(content),
            config=genai_types.EmbedContentConfig(
                task_type=str(GoogleEmbeddingTasks.RETRIEVAL_DOCUMENT), **config_kwargs
            ),
        )
        embeddings = [
            item.values
            for item in cast(list[genai_types.ContentEmbedding], response.embeddings)
            if response.embeddings is not None and item
        ] or [[]]
        _ = await self._report_stats(content)
        return embeddings  # ty: ignore[invalid-return-type]

    async def _embed_query(self, query: Sequence[str], **kwargs: Any) -> list[list[float]]:
        """
        Embed the query using the Google embedding provider.
        """
        config_kwargs = (self.query_options or {}) | (kwargs or {})
        content = [genai_types.Part.from_text(text=q) for q in query]
        response = await self.client.aio.models.embed_content(
            model=self.caps.name,
            contents=cast(genai_types.ContentListUnion, content),
            config=genai_types.EmbedContentConfig(
                task_type=str(GoogleEmbeddingTasks.CODE_RETRIEVAL_QUERY), **config_kwargs
            ),
        )
        if (
            self.caps
            and self.caps.default_dimension
            and self.dimension != self.caps.default_dimension
        ):
            embeddings = [
                self.normalize(item.values)
                for item in cast(list[genai_types.ContentEmbedding], response.embeddings)
                if response.embeddings is not None and item
            ] or [[]]
        else:
            embeddings = [
                item.values
                for item in cast(list[genai_types.ContentEmbedding], response.embeddings)
                if response.embeddings is not None and item
            ] or [[]]
        _ = await self._report_stats(content)
        return embeddings  # ty: ignore[invalid-return-type]


__all__ = ("GoogleEmbeddingProvider", "GoogleEmbeddingTasks")
