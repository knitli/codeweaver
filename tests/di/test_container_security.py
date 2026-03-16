
import pytest
from typing import Annotated, List, Optional, Union
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
    assert get_origin(resolved_annotated) is Annotated
    assert get_args(resolved_annotated)[0] is int
    assert isinstance(get_args(resolved_annotated)[1], Depends)

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

def get_origin(tp):
    if hasattr(tp, "__origin__"):
        return tp.__origin__
    return None

def get_args(tp):
    if hasattr(tp, "__args__"):
        return tp.__args__
    return []
