
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Security tests for the dependency injection container.

This module verifies that the DI container safely resolves string type
annotations, preventing arbitrary code execution while supporting
complex Python type hints including generics, unions, and Annotated types.
"""

from typing import Annotated, List, Optional, Union, get_args, get_origin

import pytest

from codeweaver.core.di.container import Container
from codeweaver.core.di.dependency import Depends

def test_safe_type_resolution():
    container = Container()
    globalns = {
        "List": List,
        "Optional": Optional,
        "Union": Union,
        "Annotated": Annotated,
        "Depends": Depends,
        "int": int,
        "str": str,
    }

    # Valid type strings
    assert container._resolve_string_type("int", globalns) is int
    assert container._resolve_string_type("List[int]", globalns) == List[int]
    assert container._resolve_string_type("Optional[str]", globalns) == Optional[str]
    assert container._resolve_string_type("int | str", globalns) == (int | str)

    # Annotated with Depends
    resolved_annotated = container._resolve_string_type("Annotated[int, Depends()]", globalns)

    # Check that it's an Annotated type in a cross-version compatible way.
    # get_origin(Annotated[int, ...]) should be Annotated, but some environments
    # might unwrap it or return a different origin. We check for __metadata__
    # which is specific to Annotated types.
    assert hasattr(resolved_annotated, "__metadata__"), f"Expected Annotated type, got {type(resolved_annotated)}"
    assert get_args(resolved_annotated)[0] is int
    assert any(isinstance(m, Depends) for m in resolved_annotated.__metadata__)

def test_malicious_type_resolution():
    container = Container()
    globalns = {"__name__": "__main__"}

    # Malicious strings that should be blocked
    malicious_strings = [
        "__import__('os').system('echo VULNERABLE')",
        "eval('1+1')",
        "getattr(int, '__name__')",
        "int.__class__",
        "(lambda x: x)(1)",
    ]

    for s in malicious_strings:
        result = container._resolve_string_type(s, globalns)
        assert result is None, f"String '{s}' should have been blocked"

def test_dunder_blocking():
    container = Container()
    globalns = {"int": int}

    # Dunder name blocking
    assert container._resolve_string_type("__name__", {"__name__": "foo"}) is None

    # Dunder attribute blocking
    assert container._resolve_string_type("int.__name__", globalns) is None

def test_safe_builtins_resolution():
    container = Container()
    # No globals provided for basic types
    assert container._resolve_string_type("int", {"__name__": "foo"}) is int
    assert container._resolve_string_type("list[str]", {"__name__": "foo"}) == list[str]
