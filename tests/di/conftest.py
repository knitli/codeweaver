# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Pytest configuration for DI tests.

This conftest avoids importing the full codeweaver package to prevent
issues with module-level imports that may be broken in the current development state.
"""

import pytest


@pytest.fixture
def clean_registry():
    """Clean the provider registry before and after each test.

    This fixture is defined here to avoid duplication across test files.

    Note: The registry structure is now a dict mapping types to lists of
    (factory, ProviderMetadata) tuples, stored in utils._providers.
    """
    from codeweaver.core.di import utils

    # Store original state - deep copy to preserve the list structure
    original_providers = {k: v.copy() for k, v in utils._providers.items()}
    
    # Clear registry for test isolation
    utils._providers.clear()

    yield

    # Restore original state
    utils._providers.clear()
    utils._providers.update(original_providers)
