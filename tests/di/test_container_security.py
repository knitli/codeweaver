# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Security tests for the dependency injection container.

This module verifies that the DI container safely resolves string type
annotations, preventing arbitrary code execution while supporting
complex Python type hints including generics, unions, and Annotated types.
"""

from __future__ import annotations

from typing import Annotated, Optional, Union, get_args

import pytest

from codeweaver.core.di.container import Container
from codeweaver.core.di.dependency import Depends


pytestmark = [pytest.mark.unit]


def test_safe_type_resolution() -> None:
    """Verify that valid type strings resolve to the correct type objects."""
    container = Container()
    globalns = {
        "List": list,
        "Optional": Optional,
        "Union": Union,
        "Annotated": Annotated,
        "Depends": Depends,
        "int": int,
        "str": str,
    }

    # Valid type strings
    assert container._resolve_string_type("int", globalns) is int
    assert container._resolve_string_type("List[int]", globalns) == list[int]
    assert container._resolve_string_type("Optional[str]", globalns) == (str | None)
    assert container._resolve_string_type("int | str", globalns) == (int | str)

    # Annotated with Depends
    resolved_annotated = container._resolve_string_type("Annotated[int, Depends()]", globalns)

    # Check that it's an Annotated type in a cross-version compatible way.
    # get_origin(Annotated[int, ...]) should be Annotated, but some environments
    # might unwrap it or return a different origin. We check for __metadata__
    # which is specific to Annotated types.
    assert hasattr(resolved_annotated, "__metadata__"), (
        f"Expected Annotated type, got {type(resolved_annotated)}"
    )
    assert get_args(resolved_annotated)[0] is int
    assert any(isinstance(m, Depends) for m in resolved_annotated.__metadata__)


def test_malicious_type_resolution() -> None:
    """Verify that malicious type strings are blocked and return None."""
    container = Container()
    globalns: dict[str, object] = {"__name__": "__main__"}

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


def test_dunder_blocking() -> None:
    """Verify that dunder names and attributes are blocked and return None."""
    container = Container()
    globalns = {"int": int}

    # Dunder name blocking
    assert container._resolve_string_type("__name__", {"__name__": "foo"}) is None

    # Dunder attribute blocking
    assert container._resolve_string_type("int.__name__", globalns) is None


def test_safe_builtins_resolution() -> None:
    """Verify that basic builtin types resolve correctly without explicit globals."""
    container = Container()
    # No globals provided for basic types
    assert container._resolve_string_type("int", {"__name__": "foo"}) is int
    assert container._resolve_string_type("list[str]", {"__name__": "foo"}) == list[str]


def test_type_builtin_not_exploitable() -> None:
    """Verify that type() cannot be invoked to create new classes during resolution."""
    container = Container()
    # type() is excluded from safe_builtins, so dynamic class creation is blocked
    assert container._resolve_string_type("type('X', (object,), {})", {}) is None
