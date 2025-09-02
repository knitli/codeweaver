# Copyright (c) 2024 to present Pydantic Services Inc
# SPDX-License-Identifier: MIT
# Applies to original code in this directory (`src/codeweaver/embedding_providers/`) from `pydantic_ai`.
#
# SPDX-FileCopyrightText: 2025 (c) 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
# applies to new/modified code in this directory (`src/codeweaver/embedding_providers/`)

"""Entry point for embedding providers. Defines the abstract base class and includes a utility for retrieving specific provider implementations."""

from typing import Any

from codeweaver._settings import Provider
from codeweaver.embedding.providers.base import EmbeddingProvider


def _infer_embedding_provider_class(  # noqa: C901
    provider: Provider,
    client: Any | None = None,
    model_name: str | None = None,
    provider_kwargs: dict[str, Any] | None = None,
) -> type[EmbeddingProvider[Any]]:  # long? yes. Complex. No.
    # sourcery skip: no-long-functions
    """
    Infer the embedding provider class from the provider name.

    Args:
        provider: The Provider enum representing the embedding provider.

    Returns:
        The class of the embedding provider.
    """
    if model_name is not None and provider in {
        Provider.OPENAI,
        Provider.FIREWORKS,
        Provider.HEROKU,
        Provider.GITHUB,
        Provider.GROQ,
        Provider.OLLAMA,
        Provider.TOGETHER,
    }:
        from codeweaver.embedding.providers.openai_factory import OpenAIEmbeddingBase

        return OpenAIEmbeddingBase.get_provider_class(
            model_name=model_name, provider=provider, client=client, provider_kwargs=provider_kwargs
        )
    if provider == Provider.AZURE:
        if "cohere" in model_name.lower():
            from codeweaver.embedding.providers.cohere import CohereEmbeddingProvider

            return CohereEmbeddingProvider
        else:  # noqa: RET505  # not sure if it's necessary, but I don't want to invite the potentially bad import here
            from codeweaver.embedding.providers.openai_factory import OpenAIEmbeddingBase

            return OpenAIEmbeddingBase.get_provider_class(
                model_name=model_name,
                provider=provider,
                client=client,
                provider_kwargs=provider_kwargs,
            )
    if provider == Provider.VOYAGE:
        from codeweaver.embedding.providers.voyage import VoyageEmbeddingProvider

        return VoyageEmbeddingProvider  # type: ignore[return-value]

    if provider == Provider.MISTRAL:
        from codeweaver.embedding.providers.mistral import MistralEmbeddingProvider

        return MistralEmbeddingProvider  # type: ignore[return-value]

    if provider == Provider.COHERE:
        from codeweaver.embedding.providers.cohere import CohereEmbeddingProvider

        return CohereEmbeddingProvider  # type: ignore[return-value]

    if provider == Provider.BEDROCK:
        from codeweaver.embedding.providers.bedrock import BedrockEmbeddingProvider

        return BedrockEmbeddingProvider  # type: ignore[return-value]
    if provider == Provider.GOOGLE:
        from codeweaver.embedding.providers.google import GoogleEmbeddingProvider

        return GoogleEmbeddingProvider  # type: ignore[return-value]
    if provider == Provider.HUGGINGFACE_INFERENCE:
        from codeweaver.embedding.providers.huggingface import HuggingFaceEmbeddingProvider

        return HuggingFaceEmbeddingProvider  # type: ignore[return-value]

    if provider == Provider.AZURE:
        from codeweaver.embedding.providers.azure import AzureEmbeddingProvider

        return AzureEmbeddingProvider  # type: ignore[return-value]

    raise ValueError(f"Unknown embedding provider: {provider}")


def infer_embedding_provider(
    provider: Provider,
    client: Any | None = None,
    model_name: str | None = None,
    provider_kwargs: dict[str, Any] | None = None,
) -> type[EmbeddingProvider[Any]]:
    """
    Infer the embedding provider from the provider name.

    Args:
        provider: The name of the embedding provider.

    Returns:
        An instance of the embedding provider.
    """
    return _infer_embedding_provider_class(
        provider, client=client, model_name=model_name, provider_kwargs=provider_kwargs
    )


__all__ = ("EmbeddingProvider", "infer_embedding_provider")
