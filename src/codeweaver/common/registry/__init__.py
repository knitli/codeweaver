# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0


from codeweaver.common.registry.registry import (
    Feature,
    ModelRegistry,
    ProviderRegistry,
    ServiceCard,
    ServiceCardDict,
    ServicesRegistry,
    get_model_registry,
    get_provider_registry,
    get_services_registry,
    initialize_registries,
    register_agent_provider,
    register_agentic_profile,
    register_data_provider,
    register_embedding_capabilities,
    register_embedding_provider,
    register_reranking_capabilities,
    register_reranking_provider,
    register_service,
    register_sparse_embedding_capabilities,
    register_sparse_embedding_provider,
    register_vector_store_provider,
    resolve_agentic_profile,
)



__all__ = (
    "Feature",
    "ModelRegistry",
    "ProviderRegistry",
    "ServiceCard",
    "ServiceCardDict",
    "ServicesRegistry",
    "get_model_registry",
    "get_provider_registry",
    "get_services_registry",
    "initialize_registries",
    "register_agent_provider",
    "register_agentic_profile",
    "register_data_provider",
    "register_embedding_capabilities",
    "register_embedding_provider",
    "register_reranking_capabilities",
    "register_reranking_provider",
    "register_service",
    "register_sparse_embedding_capabilities",
    "register_sparse_embedding_provider",
    "register_vector_store_provider",
    "resolve_agentic_profile",
)