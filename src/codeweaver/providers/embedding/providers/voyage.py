"""VoyageAI embedding provider."""

from __future__ import annotations

from collections.abc import Callable, Sequence
from typing import Annotated, Any, ClassVar, cast

from pydantic import PrivateAttr, SkipValidation
from voyageai.object.embeddings import EmbeddingsObject

from codeweaver.core import CodeChunk, ConfigurationError, Provider
from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities
from codeweaver.providers.embedding.providers import EmbeddingProvider


try:
    from voyageai.client_async import AsyncClient
    from voyageai.object.contextualized_embeddings import ContextualizedEmbeddingsObject
    from voyageai.object.embeddings import EmbeddingsObject
except ImportError as _import_error:
    raise ConfigurationError(
        'Please install the `voyageai` package to use the Voyage provider, you can use the `voyage` optional group -- `pip install "code-weaver\\[voyage]"`'
    ) from _import_error


def voyage_context_output_transformer(
    result: ContextualizedEmbeddingsObject,
) -> list[list[float]] | list[list[int]]:
    """Transform the output of the Voyage AI context chunk embedding model."""
    results = result.results
    embeddings = [res.embeddings for res in results if res and res.embeddings]
    if embeddings and isinstance(embeddings[0][0][0], list):
        embeddings = cast(list[list[float]], [emb for sublist in embeddings for emb in sublist])
    return embeddings


def voyage_output_transformer(result: EmbeddingsObject) -> list[list[float]] | list[list[int]]:
    """Transform the output of the Voyage AI model."""
    return result.embeddings


class VoyageEmbeddingProvider(EmbeddingProvider[AsyncClient]):
    """VoyageAI embedding provider."""

    client: SkipValidation[AsyncClient]
    _provider: ClassVar[Provider] = Provider.VOYAGE
    caps: EmbeddingModelCapabilities
    embed_options: ClassVar[dict[str, Any]] = {"input_type": "document"}
    query_options: ClassVar[dict[str, Any]] = {"input_type": "query"}
    _output_transformer: ClassVar[Callable[[Any], list[list[float]] | list[list[int]]]] = (
        voyage_output_transformer
    )
    _is_context_model: Annotated[bool, PrivateAttr()] = False

    def _initialize(self, caps: EmbeddingModelCapabilities) -> None:
        self._is_context_model = "context" in caps.name
        configured_dimension = self.get_dimension()
        shared_kwargs = {
            "model": caps.name,
            "output_dimension": configured_dimension,
            "output_dtype": "float",
        }
        self.embed_options |= shared_kwargs
        self.query_options |= shared_kwargs

    def _process_output(self, output_data: Any) -> list[list[float]] | list[list[int]]:
        """Process output data using the appropriate transformer."""
        transformer = (
            voyage_context_output_transformer
            if self._is_context_model
            else voyage_output_transformer
        )
        return transformer(output_data)

    @property
    def name(self) -> Provider:
        """Get the name of the embedding provider."""
        return Provider.VOYAGE

    @property
    def base_url(self) -> str | None:
        """Get the base URL of the embedding provider."""
        return "https://api.voyageai.com/v1"

    async def _embed_documents(
        self, documents: Sequence[CodeChunk], **kwargs: Any
    ) -> list[list[float]] | list[list[int]]:
        """Embed a list of documents into vectors."""
        import logging

        logger = logging.getLogger(__name__)
        ready_documents = cast(list[str], self.chunks_to_strings(documents))
        try:
            results: EmbeddingsObject = await self.client.embed(
                texts=ready_documents, **kwargs | self.embed_options
            )
            self._fire_and_forget(
                lambda: self._update_token_stats(token_count=results.total_tokens)
            )
        except Exception as e:
            error_msg = str(e)
            if "max allowed tokens per submitted batch" in error_msg.lower() and len(documents) > 1:
                logger.warning(
                    "Voyage batch token limit exceeded (%s), splitting batch of %d chunks in half and retrying",
                    error_msg.split("Your batch has")[1].split("tokens")[0].strip()
                    if "Your batch has" in error_msg
                    else "unknown",
                    len(documents),
                )
                mid = len(documents) // 2
                first_half = await self._embed_documents(documents[:mid], **kwargs)
                second_half = await self._embed_documents(documents[mid:], **kwargs)
                return first_half + second_half
            raise
        else:
            return self._process_output(results)

    async def _embed_query(
        self, query: Sequence[str], **kwargs: Any
    ) -> list[list[float]] | list[list[int]]:
        """Embed a query or group of queries into vectors."""
        results: EmbeddingsObject = await self.client.embed(
            texts=list(query), **kwargs | self.query_options
        )
        self._fire_and_forget(lambda: self._update_token_stats(token_count=results.total_tokens))
        return self._process_output(results)

    @property
    def dimension(self) -> int:
        """Get the size of the vector for the collection."""
        return self.embed_options.get("output_dimension", self.caps.default_dimension)


__all__ = ("VoyageEmbeddingProvider",)
