# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Registry for managing services and their features in CodeWeaver."""

from __future__ import annotations

from collections.abc import MutableMapping
from types import MappingProxyType
from typing import ClassVar

from pydantic import ConfigDict, PrivateAttr

from codeweaver.common.registry.types import Feature, ServiceCard, ServiceCardDict, ServiceName
from codeweaver.core.types.models import BasedModel


#! TODO: Not fully implemented.
class ServicesRegistry(BasedModel):
    """Registry for managing available services."""

    model_config = BasedModel.model_config | ConfigDict(
        arbitrary_types_allowed=True, validate_assignment=True, defer_build=True
    )

    _services: MutableMapping[Feature, list[ServiceCard]] = PrivateAttr(default_factory=dict)

    _instance: ClassVar[ServicesRegistry | None] = None

    def __init__(self) -> None:
        """Initialize the services registry."""
        # TODO register default services
        super().__init__()

    def _telemetry_keys(self) -> None:
        return None

    @classmethod
    def get_instance(cls) -> ServicesRegistry:
        """Get or create the global services registry instance."""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance

    def register_service(self, card: ServiceCard | ServiceCardDict) -> None:
        """Register a service feature as enabled or disabled.

        Args:
            card: The service card to register
        """
        if isinstance(card, dict):
            card = ServiceCard.from_dict(card)
        self._services[card.feature].append(card)

    def is_service_enabled(self, feature: Feature) -> bool:
        """Check if a service feature is enabled.

        Args:
            feature: The feature enum identifier

        Returns:
            True if the feature is enabled, False otherwise
        """
        cards = self._services.get(feature, ())
        return len(cards) > 0 and any(card.enabled for card in cards)

    def list_available_services(self) -> MappingProxyType[Feature, list[ServiceCard]]:
        """List all available services.

        Returns:
            Returns a read-only mapping of features to lists of ServiceCard instances
        """
        return MappingProxyType(self._services)

    def get_service_dependencies(self, feature: Feature) -> set[Feature]:
        """Get the dependencies for a service feature.

        Args:
            feature: The feature enum identifier

        Returns:
            A set of feature dependencies
        """
        cards = self._services.get(feature, ())
        return {dep for card in cards for dep in card.dependencies}

    def get_service_status(self) -> tuple[ServiceCard, ...]:
        """Get the status of all registered services.

        Returns:
            A tuple of ServiceCard instances representing the status of each service
        """
        raise NotImplementedError("Service status tracking is not implemented yet.")


_services_registry: ServicesRegistry | None = None


def get_services_registry() -> ServicesRegistry:
    """Get the global services registry instance.

    Returns:
        The global ServicesRegistry instance
    """
    global _services_registry
    if _services_registry is None:
        _services_registry = ServicesRegistry.get_instance()
    return _services_registry


__all__ = (
    "Feature",
    "ServiceCard",
    "ServiceCardDict",
    "ServiceName",
    "ServicesRegistry",
    "get_services_registry",
)
