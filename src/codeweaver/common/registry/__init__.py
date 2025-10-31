# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Registry package for CodeWeaver common components. This entrypoint exposes the main registry classes and types. The package internals are not for public use."""

from codeweaver.common.registry.models import ModelRegistry, get_model_registry
from codeweaver.common.registry.provider import ProviderRegistry, get_provider_registry
from codeweaver.common.registry.services import ServicesRegistry, get_services_registry
from codeweaver.common.registry.types import Feature, ServiceCard, ServiceCardDict, ServiceName


__all__ = [
    "Feature",
    "ModelRegistry",
    "ProviderRegistry",
    "ServiceCard",
    "ServiceCardDict",
    "ServiceName",
    "ServicesRegistry",
    "get_model_registry",
    "get_provider_registry",
    "get_services_registry",
]
