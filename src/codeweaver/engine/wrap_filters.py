# SPDX-CopyrightText: 2024-2025 Qdrant Solutions GmbH
# SPDX-License-Identifier: Apache-2.0
# from https://github.com/qdrant/mcp-server-qdrant/blob/master/src/mcp_server_qdrant/common/wrap_filters.py
#
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
"""Filter wrapping utility for result and query functions. Replaces a single `query_filter` parameter with multiple parameters defined by `filterable_fields`.

Nearly all of this file and its contents were adapted from Qdrant's example MCP server, [mcp-server-qdrant](https://github.com/qdrant/mcp-server-qdrant/), and fall under Qdrant's copyright and Apache 2.0 license. Any modifications or changes made to the original code are copyrighted by Knitli Inc. and are licensed under MIT OR Apache-2.0, whichever you want.
"""

import inspect

from collections.abc import Callable
from functools import wraps
from typing import Annotated, Any

from pydantic import Field

from codeweaver.engine.filter import FilterableField, make_filter


def make_partial_function(
    original_func: Callable[..., Any], fixed_values: dict[str, Any]
) -> Callable[..., Any]:
    """Creates a partial function with fixed values."""
    sig = inspect.signature(original_func)

    @wraps(original_func)
    def wrapper(*args: Any, **kwargs: dict[str, Any]) -> Any:
        # Start with fixed values
        bound_args = dict(fixed_values)

        # Bind positional/keyword args from caller
        bound_args.update(dict(zip(remaining_params, args, strict=True)))
        bound_args.update(kwargs)

        return original_func(**bound_args)

    # Only keep parameters NOT in fixed_values
    remaining_params = [name for name in sig.parameters if name not in fixed_values]
    new_params = [sig.parameters[name] for name in remaining_params]

    # Set the new __signature__ for introspection
    wrapper.__signature__ = sig.replace(parameters=new_params)  # type:ignore

    return wrapper


def _get_field_type(field: FilterableField) -> type:
    """Get the Python type for a FilterableField."""
    if field.field_type == "keyword":
        return str
    if field.field_type == "integer":
        return int
    if field.field_type == "float":
        return float
    if field.field_type == "bool":
        return bool
    raise ValueError(f"Unsupported field type: {field.field_type}")


def _validate_and_adjust_field_type(field: FilterableField, field_type: type) -> type:
    """Validate and adjust field type for list conditions."""
    if field.condition in {"any", "except"}:
        if field_type not in {str, int}:
            raise ValueError(
                f'Only "keyword" and "integer" types are supported for "{field.condition}" condition'
            )
        return list[field_type]  # type: ignore
    return field_type


def _create_parameter_from_field(field: FilterableField) -> inspect.Parameter:
    """Create an inspect.Parameter from a FilterableField."""
    field_name = field.name
    field_type = _get_field_type(field)
    field_type = _validate_and_adjust_field_type(field, field_type)

    if field.required:
        annotation = Annotated[field_type, Field(description=field.description)]  # type: ignore
        return inspect.Parameter(
            name=field_name, kind=inspect.Parameter.POSITIONAL_OR_KEYWORD, annotation=annotation
        )
    annotation = Annotated[  # type: ignore
        field_type | None, Field(description=field.description)
    ]
    return inspect.Parameter(
        name=field_name,
        kind=inspect.Parameter.POSITIONAL_OR_KEYWORD,
        default=None,
        annotation=annotation,
    )


def _build_new_signature(
    sig: inspect.Signature, filterable_fields: dict[str, FilterableField]
) -> inspect.Signature:
    """Build new signature by replacing query_filter with filterable field parameters."""
    param_names = [name for name in sig.parameters if name != "query_filter"]
    new_params = [sig.parameters[param_name] for param_name in param_names]

    required_new_params: list[inspect.Parameter] = []
    optional_new_params: list[inspect.Parameter] = []

    for field in filterable_fields.values():
        parameter = _create_parameter_from_field(field)
        if field.required:
            required_new_params.append(parameter)
        else:
            optional_new_params.append(parameter)

    new_params.extend(required_new_params)
    new_params.extend(optional_new_params)

    return sig.replace(parameters=new_params)


def _set_wrapper_annotations(wrapper: Callable[..., Any], new_signature: inspect.Signature) -> None:
    """Set __annotations__ on wrapper function for introspection."""
    new_annotations = {
        param.name: param.annotation
        for param in new_signature.parameters.values()
        if param.annotation != inspect.Parameter.empty
    }
    if new_signature.return_annotation != inspect.Parameter.empty:
        new_annotations["return"] = new_signature.return_annotation

    wrapper.__annotations__ = new_annotations


def wrap_filters(
    original_func: Callable[..., Any], filterable_fields: dict[str, FilterableField]
) -> Callable[..., Any]:
    """
    Wraps the original_func function: replaces `query_filter` parameter with multiple parameters defined by `filterable_fields`.
    """
    sig = inspect.signature(original_func)

    @wraps(original_func)
    def wrapper(*args: Any, **kwargs: dict[str, Any]) -> Any:
        filter_values: dict[str, Any] = {}

        for field_name in filterable_fields:
            if field_name in kwargs:
                filter_values[field_name] = kwargs.pop(field_name)

        query_filter = make_filter(filterable_fields, filter_values)
        return original_func(**kwargs, query_filter=query_filter)

    new_signature = _build_new_signature(sig, filterable_fields)
    wrapper.__signature__ = new_signature  # type: ignore
    _set_wrapper_annotations(wrapper, new_signature)

    return wrapper


__all__ = ("make_partial_function", "wrap_filters")
