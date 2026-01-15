# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Tests for default value provider system."""

import pytest

from codeweaver.core.config.defaults import clear_defaults, get_default, register_default_provider


@pytest.fixture(autouse=True)
def _cleanup():
    """Clean up defaults after each test."""
    yield
    clear_defaults()


def test_register_and_get_default():
    """Test registering and getting a default value."""
    register_default_provider("test.key", lambda: 42)

    value = get_default("test.key")
    assert value == 42


def test_get_default_nonexistent_key():
    """Test getting a default for a non-existent key."""
    value = get_default("nonexistent.key")
    assert value is None


def test_get_default_none_value():
    """Test that None values are skipped."""
    register_default_provider("test.key", lambda: None)
    register_default_provider("test.key", lambda: 42)

    value = get_default("test.key")
    assert value == 42  # Should get the second provider's value


def test_get_default_first_non_none_wins():
    """Test that first non-None value wins."""
    register_default_provider("test.key", lambda: None)
    register_default_provider("test.key", lambda: "first")
    register_default_provider("test.key", lambda: "second")

    value = get_default("test.key")
    assert value == "first"  # Should stop at first non-None


def test_multiple_keys():
    """Test multiple keys with different providers."""
    register_default_provider("key1", lambda: "value1")
    register_default_provider("key2", lambda: "value2")

    assert get_default("key1") == "value1"
    assert get_default("key2") == "value2"


def test_clear_defaults():
    """Test clearing all default providers."""
    register_default_provider("test.key", lambda: 42)

    assert get_default("test.key") == 42

    clear_defaults()

    assert get_default("test.key") is None


def test_conditional_provider():
    """Test provider with conditional logic."""
    condition = True

    register_default_provider("test.conditional", lambda: "enabled" if condition else "disabled")

    assert get_default("test.conditional") == "enabled"

    # Change condition
    condition = False
    # Note: The lambda captures the variable, so this won't change the result
    # This test demonstrates that providers are evaluated at call time
    register_default_provider("test.conditional2", lambda: "enabled" if condition else "disabled")

    assert get_default("test.conditional2") == "disabled"


def test_provider_with_computation():
    """Test provider that does computation."""
    register_default_provider("test.computed", lambda: 10 * 20 + 5)

    assert get_default("test.computed") == 205
