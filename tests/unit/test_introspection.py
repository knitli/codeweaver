# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Unit tests for the introspection utilities module.

Tests the clean_args function and related introspection utilities.
"""

import pytest

from codeweaver.common.utils.introspect import (
    clean_args,
    keyword_args,
    positional_args,
    takes_kwargs,
)


pytestmark = [pytest.mark.unit]


class TestCleanArgs:
    """Test the clean_args function."""

    def test_simple_function_filters_extra_kwargs(self):
        """Test that extra kwargs are filtered for functions without **kwargs."""

        def simple_func(a: int, b: str) -> str:
            return f"{a}: {b}"

        args_dict = {"a": 1, "b": "hello", "extra": "ignored"}
        pos_args, kwargs = clean_args(args_dict, simple_func)

        assert pos_args == ()
        assert kwargs == {"a": 1, "b": "hello"}
        assert "extra" not in kwargs

    def test_function_with_kwargs_passes_all_args(self):
        """Test that all args are passed to functions with **kwargs."""

        def func_with_kwargs(a: int, b: str, **kwargs) -> str:
            return f"{a}: {b}, kwargs: {kwargs}"

        args_dict = {
            "a": 1,
            "b": "hello",
            "extra": "should_be_passed",
            "another": "also_passed",
        }

        pos_args, kwargs = clean_args(args_dict, func_with_kwargs)

        assert pos_args == ()
        assert kwargs == {
            "a": 1,
            "b": "hello",
            "extra": "should_be_passed",
            "another": "also_passed",
        }

    def test_function_with_optional_params(self):
        """Test functions with optional parameters."""

        def func_with_optional(a: int, b: str = "default", c: int = 0) -> str:
            return f"{a}: {b}, {c}"

        # Test with all params
        args_dict = {"a": 1, "b": "hello", "c": 42}
        pos_args, kwargs = clean_args(args_dict, func_with_optional)

        assert pos_args == ()
        assert kwargs == {"a": 1, "b": "hello", "c": 42}

        # Test with some params
        args_dict = {"a": 1, "b": "hello"}
        pos_args, kwargs = clean_args(args_dict, func_with_optional)

        assert pos_args == ()
        assert kwargs == {"a": 1, "b": "hello"}

    def test_client_options_unpacking_with_kwargs(self):
        """Test that client_options are unpacked when function accepts **kwargs."""

        def client_with_kwargs(api_key: str, **kwargs):
            pass

        args_dict = {
            "api_key": "test_key",
            "model": "test-model",
            "client_options": {"timeout": 60, "max_retries": 5},
        }

        pos_args, kwargs = clean_args(args_dict, client_with_kwargs)

        assert pos_args == ()
        assert kwargs["api_key"] == "test_key"
        assert kwargs["timeout"] == 60
        assert kwargs["max_retries"] == 5

    def test_provider_settings_unpacking_with_kwargs(self):
        """Test that provider_settings are unpacked when function accepts **kwargs."""

        def client_with_kwargs(api_key: str, **kwargs):
            pass

        args_dict = {
            "api_key": "test_key",
            "provider_settings": {"region": "us-west-2", "custom_option": "value"},
        }

        pos_args, kwargs = clean_args(args_dict, client_with_kwargs)

        assert pos_args == ()
        assert kwargs["api_key"] == "test_key"
        assert kwargs["region"] == "us-west-2"
        assert kwargs["custom_option"] == "value"

    def test_kwargs_key_is_merged(self):
        """Test that a 'kwargs' key in input is properly merged."""

        def func_with_kwargs(a: int, b: str, **kwargs):
            pass

        args_dict = {
            "a": 1,
            "b": "hello",
            "kwargs": {"extra1": "value1", "extra2": "value2"},
        }

        pos_args, kwargs = clean_args(args_dict, func_with_kwargs)

        assert pos_args == ()
        assert kwargs == {"a": 1, "b": "hello", "extra1": "value1", "extra2": "value2"}

    def test_class_constructor(self):
        """Test clean_args with a class constructor."""

        class SimpleClient:
            def __init__(self, api_key: str, base_url: str = "https://api.example.com"):
                self.api_key = api_key
                self.base_url = base_url

        args_dict = {
            "api_key": "test_key_123",
            "base_url": "https://custom.api.com",
            "extra": "ignored",
        }

        pos_args, kwargs = clean_args(args_dict, SimpleClient.__init__)

        # Note: self is not in the output
        assert pos_args == ()
        assert kwargs == {
            "api_key": "test_key_123",
            "base_url": "https://custom.api.com",
        }
        assert "extra" not in kwargs

    def test_class_constructor_with_kwargs(self):
        """Test clean_args with a class constructor that accepts **kwargs."""

        class ComplexClient:
            def __init__(
                self,
                api_key: str,
                base_url: str = "https://api.example.com",
                **kwargs,
            ):
                self.api_key = api_key
                self.base_url = base_url
                self.kwargs = kwargs

        args_dict = {
            "api_key": "test_key_123",
            "base_url": "https://custom.api.com",
            "timeout": 60,
            "custom_option": "value",
        }

        pos_args, kwargs = clean_args(args_dict, ComplexClient.__init__)

        assert pos_args == ()
        assert kwargs == {
            "api_key": "test_key_123",
            "base_url": "https://custom.api.com",
            "timeout": 60,
            "custom_option": "value",
        }

    def test_no_extra_kwargs_without_kwargs_param(self):
        """Test that extra kwargs are filtered when function doesn't accept **kwargs."""

        def strict_func(a: int, b: str):
            pass

        args_dict = {"a": 1, "b": "hello", "c": "should_be_filtered", "d": "also_filtered"}

        pos_args, kwargs = clean_args(args_dict, strict_func)

        assert pos_args == ()
        assert kwargs == {"a": 1, "b": "hello"}
        assert "c" not in kwargs
        assert "d" not in kwargs

    def test_provider_settings_filtered_without_kwargs_param(self):
        """Test that provider_settings keys are filtered for matching params only."""

        def client_without_kwargs(api_key: str, timeout: int = 30):
            pass

        args_dict = {
            "api_key": "test_key",
            "provider_settings": {
                "timeout": 60,  # This should be extracted
                "region": "us-west-2",  # This should be ignored
            },
        }

        pos_args, kwargs = clean_args(args_dict, client_without_kwargs)

        assert pos_args == ()
        assert kwargs == {"api_key": "test_key", "timeout": 60}
        assert "region" not in kwargs


class TestIntrospectionHelpers:
    """Test helper functions for introspection."""

    def test_keyword_args(self):
        """Test keyword_args function."""

        def test_func(a: int, b: str, c: int = 0):
            pass

        result = keyword_args(test_func)
        assert set(result) == {"a", "b", "c"}

    def test_positional_args(self):
        """Test positional_args function."""

        def test_func(a: int, b: str, c: int = 0):
            pass

        result = positional_args(test_func)
        assert set(result) == {"a", "b", "c"}

    def test_takes_kwargs_true(self):
        """Test takes_kwargs returns True for **kwargs functions."""

        def test_func(a: int, **kwargs):
            pass

        assert takes_kwargs(test_func) is True

    def test_takes_kwargs_false(self):
        """Test takes_kwargs returns False for functions without **kwargs."""

        def test_func(a: int, b: str):
            pass

        assert takes_kwargs(test_func) is False
