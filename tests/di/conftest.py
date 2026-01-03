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
    """
    from codeweaver.core import utils

    # Store original state
    original_providers = utils._providers.copy()
    original_metadata = utils._provider_metadata.copy()

    yield

    # Restore original state
    utils._providers.clear()
    utils._providers.update(original_providers)
    utils._provider_metadata.clear()
    utils._provider_metadata.update(original_metadata)
