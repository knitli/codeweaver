# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Fixtures for env_registry tests."""

import pytest


@pytest.fixture
def reset_provider_env_registry():
    """Reset the ProviderEnvRegistry between tests."""
    from codeweaver.providers.env_registry.registry import ProviderEnvRegistry

    ProviderEnvRegistry._reset()
    yield
    ProviderEnvRegistry._reset()
