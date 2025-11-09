"""Type and signature introspection utilities.

The utilities are thin wrappers around the standard library's `inspect` module,
providing convenient access to function signatures, annotations, and source code.
"""

from __future__ import annotations

import inspect

from collections.abc import Callable, Sequence
from inspect import Attribute, Parameter, Signature
from pathlib import Path
from types import MappingProxyType
from typing import Any


def get_function_signature(func: Callable[..., Any]) -> Signature:
    """Retrieve the signature of a given function.

    Args:
        func (callable): The function to introspect.

    Returns:
        inspect.Signature: The signature of the function.
    """
    return inspect.signature(func)


def get_function_annotations(func: Callable[..., Any]) -> dict[str, Any]:
    """Retrieve the annotations of a given function.

    Args:
        func (callable): The function to introspect.

    Returns:
        dict[str, Any]: The annotations of the function.
    """
    return func.__annotations__


def get_function_parameters(func: Callable[..., Any]) -> MappingProxyType[str, Parameter]:
    """Retrieve the parameters of a given function.

    Args:
        func (callable): The function to introspect.

    Returns:
        dict[str, inspect.Parameter]: The parameters of the function.
    """
    signature = get_function_signature(func)
    return signature.parameters


def get_source_start_end(obj: Any) -> tuple[int, int]:
    """Retrieve the source code of a given function.

    Args:
        obj (Any): The object to introspect.

    Returns:
        tuple[int, int]: The start and end line numbers of the source code.
    """
    try:
        source_lines, starting_line_no = inspect.getsourcelines(obj)
        return starting_line_no, len(source_lines) + starting_line_no
    except OSError:
        return 1, 1


def get_source_code(obj: Any) -> str:
    """Retrieve the source code of a given function.

    Args:
        obj (Any): The object to introspect.

    Returns:
        str: The source code of the object.
    """
    try:
        return inspect.getsource(obj)
    except OSError:
        return ""


def return_type(func: Callable[..., Any]) -> Any | inspect._empty:
    """Retrieve the return type annotation of a given function.

    Args:
        func (callable): The function to introspect.

    Returns:
        Any: The return type annotation of the function.
    """
    return get_function_signature(func).return_annotation


def positional_args(func: Callable[..., Any]) -> list[str]:
    """Retrieve the names of positional arguments of a given function.

    Args:
        func (callable): The function to introspect.

    Returns:
        list[str]: The names of positional arguments.
    """
    signature = get_function_signature(func)
    return [
        name
        for name, param in signature.parameters.items()
        if param.kind in (param.POSITIONAL_ONLY, param.POSITIONAL_OR_KEYWORD)
    ]


def keyword_args(func: Callable[..., Any]) -> list[str]:
    """Retrieve the names of keyword arguments of a given function.

    Args:
        func (callable): The function to introspect.

    Returns:
        list[str]: The names of keyword arguments.
    """
    signature = get_function_signature(func)
    return [
        name
        for name, param in signature.parameters.items()
        if param.kind in (param.KEYWORD_ONLY, param.POSITIONAL_OR_KEYWORD)
    ]


def takes_args(func: Callable[..., Any]) -> bool:
    """Check if a function accepts variable positional arguments (*args).

    Args:
        func (callable): The function to introspect.

    Returns:
        bool: True if the function accepts *args, False otherwise.
    """
    signature = get_function_signature(func)
    return any(param.kind == param.VAR_POSITIONAL for param in signature.parameters.values())


def takes_kwargs(func: Callable[..., Any]) -> bool:
    """Check if a function accepts variable keyword arguments (**kwargs).

    Args:
        func (callable): The function to introspect.

    Returns:
        bool: True if the function accepts **kwargs, False otherwise.
    """
    signature = get_function_signature(func)
    return any(param.kind == param.VAR_KEYWORD for param in signature.parameters.values())


def get_file_path(obj: Any) -> Path | None:
    """Retrieve the file path where the given object is defined.

    Args:
        obj (Any): The object to introspect.

    Returns:
        Path | None: The file path where the object is defined, or None if not found.
    """
    try:
        return Path(inspect.getfile(obj))
    except OSError:
        return None


# #================================================
# *               Re-exports
#      Convenience re-exports from `inspect`
# ================================================

getdoc = inspect.getdoc
isclass = inspect.isclass
ismethod = inspect.ismethod
isfunction = inspect.isfunction
getsourcefile = inspect.getsourcefile
getmodule = inspect.getmodule
getmodulename = inspect.getmodulename


# #================================================
# *               Deeper Inspection
# ==================================================


def get_class_attrs(cls: type) -> tuple[Attribute, ...]:
    """Retrieve the public and private (sunder `_` not dunder `__`) attributes defined on a given class.

    Filters out stdlib dunder attributes inherited from `object` and attributes starting with `__`.

    Args:
        cls (type): The class to introspect.

    Returns:
        tuple[Attribute, ...]: The attributes of the class.
    """
    return tuple(
        attr
        for attr in inspect.classify_class_attrs(cls)
        if attr.defining_class is not object and not attr.name.startswith("__")
    )


def get_class_methods(cls: type) -> tuple[Attribute, ...]:
    """Retrieve the public and private (sunder `_` not dunder `__`) methods defined on a given class.

    Filters out stdlib dunder methods inherited from `object` and methods starting with `__`.

    Args:
        cls (type): The class to introspect.

    Returns:
        tuple[Attribute, ...]: The methods of the class.
    """
    return tuple(attr for attr in get_class_attrs(cls) if attr.kind == "method")


def get_class_properties(cls: type) -> tuple[Attribute, ...]:
    """Retrieve the public and private (sunder `_` not dunder `__`) properties defined on a given class.

    Filters out stdlib dunder properties inherited from `object` and properties starting with `__`.

    Args:
        cls (type): The class to introspect.

    Returns:
        tuple[Attribute, ...]: The properties of the class.
    """
    return tuple(attr for attr in get_class_attrs(cls) if attr.kind == "property")


def get_class_variables(cls: type) -> tuple[Attribute, ...]:
    """Retrieve the public and private (sunder `_` not dunder `__`) variables defined on a given class.

    Filters out stdlib dunder variables inherited from `object` and variables starting with `__`.

    Args:
        cls (type): The class to introspect.

    Returns:
        tuple[Attribute, ...]: The variables of the class.
    """
    return tuple(attr for attr in get_class_attrs(cls) if attr.kind == "data")


def get_class_constructor(cls: type) -> Attribute:
    """Retrieve the constructors (`__init__` methods) defined on a given class.

    Args:
        cls (type): The class to introspect.

    Returns:
        Attribute: The constructor of the class.
    """
    return next(
        (attr for attr in inspect.classify_class_attrs(cls) if attr.name == "__init__"),
        next(attr for attr in inspect.classify_class_attrs(cls) if attr.name == "__new__"),
    )


def is_constructor_arg[ClassT: type](
    cls: ClassT, arg_name: str, *, alt_constructor: Callable[..., ClassT] | None = None
) -> bool:
    """Check if a given argument name is a constructor argument for the specified class.

    Args:
        cls (type): The class to introspect.
        arg_name (str): The argument name to check.
        alt_constructor (callable): An alternative constructor (i.e. classmethod or factory function) function to use instead of the default.

    Returns:
        bool: True if the argument is a constructor argument, False otherwise.
    """
    constructor = get_class_constructor(cls)
    return arg_name in get_function_parameters(alt_constructor or constructor.object)


def _construct_args(
    positional: list[str], calling_args: dict[str, Any], func: Callable[..., Any]
) -> tuple[tuple[Any, ...], dict[str, Any]]:
    """Construct positional and keyword argument tuples for a function based on the provided arguments."""
    if not positional:
        return (), calling_args
    new_pos_args = {}
    if "args" in calling_args and (isinstance(calling_args.get("args"), dict) or takes_args(func)):
        if isinstance(calling_args.get("args"), dict):
            new_pos_args = calling_args.pop("args", {})
        elif (
            takes_args(func)
            and isinstance(calling_args.get("args"), Sequence)
            and not isinstance(calling_args.get("args"), str)
        ):
            new_pos_args = tuple(calling_args.pop("args"))
    pos_args = []
    for arg in positional:
        if arg in calling_args:
            pos_args.append(calling_args.pop(arg))
        elif isinstance(new_pos_args, dict) and arg in new_pos_args:
            pos_args.append(new_pos_args.pop(arg))
    if isinstance(new_pos_args, tuple):
        pos_args.extend(new_pos_args)
    return tuple(pos_args), calling_args


def _add_conditional_kwargs(
    keywords: list[str], calling_args: dict[str, Any], *, takes_kwargs: bool
) -> dict[str, Any]:
    """Add conditional keyword arguments to the keyword argument dictionary."""
    kw_args = {}
    for key in ("client_options", "provider_options", "provider_settings"):
        if (
            key in calling_args
            and (takes_kwargs and key not in keywords)
            and isinstance(calling_args[key], dict)
        ):
            kw_args |= calling_args.pop(key)
        elif (
            key in calling_args
            and isinstance(calling_args[key], dict)
            and (more_kwargs := {k: v for k, v in calling_args[key].items() if k in keywords})
        ):
            kw_args |= more_kwargs
            calling_args.pop(key)
    return kw_args


def _construct_kwargs(
    keywords: list[str], calling_args: dict[str, Any], func: Callable[..., Any]
) -> dict[str, Any]:
    """Construct keyword argument dictionary for a function based on the provided arguments."""
    if not keywords:
        return {}
    combined = calling_args | calling_args.pop("kwargs", {})
    kw_args = {}
    if not takes_kwargs(func):
        kw_args = {k: v for k, v in combined.items() if k in keywords}
    kw_args |= _add_conditional_kwargs(keywords, combined, takes_kwargs=takes_kwargs(func))
    return kw_args


def clean_args(
    args: dict[str, Any], func: Callable[..., Any] | type
) -> tuple[tuple[Any, ...], dict[str, Any]]:
    """Remove any keys from the args dictionary that aren't accepted by the target function.

    Args:
        args (dict[str, Any]): The arguments dictionary to clean.

    Returns:
        tuple[tuple[Any], dict[str, Any]]: The cleaned arguments tuple and dictionary.
    """
    if not isfunction(func) and not ismethod(func):
        raise TypeError("func must be a function or method")
    if isclass(func):
        func = get_class_constructor(func).object
    keywords = keyword_args(func)
    positional = [arg for arg in positional_args(func) if arg not in keywords]
    if "kwargs" in args and isinstance(args.get("kwargs"), dict) and "kwargs" not in keywords:
        args |= args.pop("kwargs")
    new_pos_args, new_kw_args = (
        _construct_args(positional, args, func) if positional else ((), args)
    )
    kwargs = _construct_kwargs(keywords, new_kw_args, func) if keywords and new_kw_args else {}
    return new_pos_args, kwargs


__all__ = (
    "clean_args",
    "get_class_attrs",
    "get_class_constructor",
    "get_class_methods",
    "get_class_properties",
    "get_class_variables",
    "get_function_annotations",
    "get_function_parameters",
    "get_function_signature",
    "get_source_code",
    "getdoc",
    "getmodule",
    "getmodulename",
    "getsourcefile",
    "isclass",
    "isfunction",
    "ismethod",
)
