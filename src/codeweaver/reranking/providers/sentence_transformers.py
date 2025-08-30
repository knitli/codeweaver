# sourcery skip: no-complex-if-expressions
"""Reranking provider for FastEmbed."""

import asyncio
import logging

from collections.abc import Callable, Sequence
from typing import Any, cast

import numpy as np

from codeweaver._settings import Provider
from codeweaver._utils import rpartial
from codeweaver.reranking.capabilities.base import RerankingModelCapabilities
from codeweaver.reranking.providers.base import RerankingProvider


logger = logging.getLogger(__name__)

try:
    from sentence_transformers import CrossEncoder

except ImportError as e:
    logger.exception("Failed to import CrossEncoder from sentence_transformers")
    raise ImportError(
        "SentenceTransformers is not installed. Please install it with `pip install sentence-transformers`."
    ) from e


def preprocess_for_qwen(
    query: str,
    documents: Sequence[str],
    instruction: str,
    prefix: str,
    suffix: str,
    model_name: str,
) -> Sequence[tuple[str, str]]:
    """Preprocess the query and documents for Qwen models."""

    def format_doc(doc: str) -> tuple[str, str]:
        return (
            f"{prefix}<Instruct>: {instruction}\n<Query>:\n{query}\n",
            f"<Document>:\n{doc}{suffix}",
        )

    return [format_doc(doc) for doc in documents]


class SentenceTransformersRerankingProvider(RerankingProvider[CrossEncoder]):
    """
    SentenceTransformers implementation of the reranking provider.

    model_name: The name of the SentenceTransformers model to use.
    """

    _client: CrossEncoder
    _provider: Provider = Provider.SENTENCE_TRANSFORMERS
    _caps: RerankingModelCapabilities

    _rerank_kwargs: dict[str, Any] = {"trust_remote_code": True}  # noqa: RUF012

    def __init__(
        self,
        capabilities: RerankingModelCapabilities,
        client: CrossEncoder | None = None,
        prompt: str | None = None,
        top_k: int = 40,
        **kwargs: Any,
    ) -> None:
        """Initialize the SentenceTransformersRerankingProvider."""
        self._caps = capabilities
        self._rerank_kwargs = {**type(self)._rerank_kwargs, **kwargs}
        self._client = client or CrossEncoder(self._caps.name, **self._rerank_kwargs)
        self._prompt = prompt
        self._top_k = top_k
        super().__init__(
            capabilities,
            client=self._client,
            prompt=prompt,
            top_k=top_k,
            **self._rerank_kwargs,  # pyright: ignore[reportCallIssue]  # we're intentionally reassigning here
        )

    def _initialize(self) -> None:
        """
        Initialize the SentenceTransformersRerankingProvider.
        """
        if "model_name" not in self.kwargs:
            self.kwargs["model_name"] = self._caps.name
        name = self.kwargs.pop("model_name")
        if not isinstance(name, str):
            raise TypeError(f"Expected model_name to be str, got {type(name).__name__}")
        self._client = self._client or CrossEncoder(name, **(self.kwargs or {}))  # pyright: ignore[reportArgumentType]
        if "Qwen3" in name:
            self._setup_qwen3()

    async def _execute_rerank(
        self,
        query: str,
        documents: Sequence[str],
        *,
        top_k: int = 40,
        **kwargs: dict[str, Any] | None,
    ) -> Any:
        """Execute the reranking process."""
        preprocessed = (
            preprocess_for_qwen(
                query=query,
                documents=documents,
                instruction=self._caps.custom_prompt or "",
                prefix=self._query_prefix,
                suffix=self._doc_suffix,
                model_name=self.kwargs["model_name"]
                if isinstance(self.kwargs["model_name"], str)
                else "this won't happen",
            )
            if "Qwen3" in self._caps.name
            else [(query, doc) for doc in documents]
        )
        predict_partial = rpartial(
            cast(Callable[..., np.ndarray], self._client.predict), convert_to_numpy=True
        )
        loop = asyncio.get_running_loop()
        scores = await loop.run_in_executor(None, predict_partial, preprocessed)  # pyright: ignore[reportArgumentType, reportUnknownMemberType, reportUnknownVariableType]
        return scores.tolist()

    def _setup_qwen3(self) -> None:
        """Sets up Qwen3 specific parameters."""
        if "Qwen3" not in cast(str, self.kwargs["model_name"]):
            return
        from importlib import metadata

        try:
            has_flash_attention = metadata.version("flash_attn")
        except Exception:
            has_flash_attention = None

        if other := self._caps.other:
            self._query_prefix = f"{other.get('prefix', '')}{self._caps.custom_prompt}\n<Query>:\n"
            self._doc_suffix = other.get("suffix", "")
        self.kwargs["model_kwargs"] = {"torch_dtype": "torch.float16"}
        if has_flash_attention:
            self.kwargs["model_kwargs"]["attention_implementation"] = "flash_attention_2"
