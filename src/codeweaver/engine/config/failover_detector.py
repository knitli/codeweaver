# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Failover detector abstraction to break circular dependency with ProviderSettings."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import TYPE_CHECKING

from codeweaver.core.di import INJECTED, dependency_provider


if TYPE_CHECKING:
    from codeweaver.providers import ProviderSettingsDep


class FailoverDetector(ABC):
    """Abstract interface for detecting whether failover should be disabled.

    This abstraction breaks the circular dependency between FailoverSettings
    and ProviderSettings by inverting the dependency. FailoverSettings depends
    on this abstract interface, while concrete implementations depend on
    ProviderSettings.

    The detector pattern follows the Dependency Inversion Principle (SOLID),
    allowing high-level failover logic to remain independent of provider
    configuration details.
    """

    @abstractmethod
    def should_disable_failover(self) -> bool:
        """Determine whether failover should be automatically disabled.

        Returns:
            True if failover should be disabled based on provider configuration,
            False otherwise.
        """
        ...


@dependency_provider(FailoverDetector, scope="singleton")
class LocalEmbeddingDetector(FailoverDetector):
    """Detect whether to disable failover based on local embedding provider.

    This implementation disables failover when the primary embedding provider
    is local, as local providers don't require network failover mechanisms.

    The detector is registered with the DI container to provide the
    FailoverDetector interface, enabling automatic injection into consumers.
    """

    def __init__(self, settings: ProviderSettingsDep = INJECTED) -> None:
        """Initialize the detector with provider settings.

        Args:
            settings: Provider settings containing embedding configuration.
                     Injected automatically by the DI container.
        """
        self._settings = settings

    def should_disable_failover(self) -> bool:
        """Check if the primary embedding provider is local.

        Failover is automatically disabled when:
        - The embedding provider list is non-empty AND
        - The first (primary) embedding provider is marked as local

        If no embedding providers are configured (empty list), failover
        remains enabled as a safety measure.

        Returns:
            True if the primary embedding provider is local and failover
            should be disabled, False otherwise.
        """
        # Handle edge case: no embedding providers configured
        if not self._settings.embedding:
            return False

        # Check if first (primary) provider is local
        primary_embedding = self._settings.embedding[0]
        return primary_embedding.is_local()


__all__ = ("FailoverDetector", "LocalEmbeddingDetector")
