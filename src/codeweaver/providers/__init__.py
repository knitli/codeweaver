"""The providers package provides definitions and capabilities for various service providers used in CodeWeaver at the root level, and contains subpackages for embedding, reranking, and vector store providers."""

from codeweaver.providers.capabilities import (
    PROVIDER_CAPABILITIES,
    VECTOR_PROVIDER_CAPABILITIES,
    get_provider_kinds,
)
from codeweaver.providers.embedding import (
    get_embedding_model_provider,
    user_settings_to_provider_settings,
)
from codeweaver.providers.provider import (
    LiteralProvider,
    LiteralProviderKind,
    Provider,
    ProviderEnvVars,
    ProviderKind,
)
from codeweaver.providers.reranking import load_default_capabilities
from codeweaver.providers.vector_stores import VectorStoreProvider


__all__ = (
    "PROVIDER_CAPABILITIES",
    "VECTOR_PROVIDER_CAPABILITIES",
    "LiteralProvider",
    "LiteralProviderKind",
    "Provider",
    "ProviderEnvVars",
    "ProviderKind",
    "VectorStoreProvider",
    "get_embedding_model_provider",
    "get_provider_kinds",
    "load_default_capabilities",
    "user_settings_to_provider_settings",
)
