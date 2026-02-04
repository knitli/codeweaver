# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""CLI utility functions."""

from __future__ import annotations

from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from codeweaver.core import Provider, ProviderKind


def check_provider_package_available(provider: Provider, kind: ProviderKind) -> bool:
    """Check if the required package for a provider is installed.

    This replaces the registry.is_provider_available logic.
    """
    from codeweaver.core.types import SDKClient

    # Check if all required packages are available
    if (sdk_clients := SDKClient.for_provider_and_kind(provider, kind)) and (
        results := list(sdk_clients)
    ):
        for result in results:
            if result.client_available():
                return True
    return False


__all__ = ("check_provider_package_available",)
