#!/usr/bin/env python3

# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Helper functions for @overload detection in AST parser."""

from __future__ import annotations

import ast
import logging


logger = logging.getLogger(__name__)


def is_overloaded_function(node: ast.FunctionDef | ast.AsyncFunctionDef) -> bool:
    r"""Check if function has @overload decorator.

    Args:
        node: Function definition AST node

    Returns:
        True if function has @overload decorator

    Example:
        >>> node = ast.parse("@overload\ndef f(): ...").body[0]
        >>> is_overloaded_function(node)
        True
    """
    for decorator in node.decorator_list:
        # Direct reference: @overload
        if isinstance(decorator, ast.Name) and decorator.id == "overload":
            return True

        # Attribute reference: @typing.overload
        if isinstance(decorator, ast.Attribute) and decorator.attr == "overload":
            return True

    return False


def group_functions_by_name(tree: ast.Module) -> dict[str, dict[str, object]]:
    """Group top-level functions by name, handling @overload.

    Args:
        tree: Parsed AST module

    Returns:
        Dict mapping function name to metadata about all definitions

    Example:
        >>> tree = ast.parse('''
        ... @overload
        ... def f(x: int) -> int: ...
        ... @overload
        ... def f(x: str) -> str: ...
        ... def f(x): return x
        ... ''')
        >>> groups = group_functions_by_name(tree)
        >>> groups["f"]["has_overload"]
        True
        >>> groups["f"]["overload_count"]
        2
    """
    function_groups: dict[str, dict[str, object]] = {}

    # Find all top-level functions
    for node in tree.body:
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            func_name = node.name

            if func_name not in function_groups:
                function_groups[func_name] = {
                    "definitions": [],
                    "overloads": [],
                    "implementation": None,
                    "first_definition": node,
                    "has_overload": False,
                    "overload_count": 0,
                    "has_implementation": False,
                }

            group = function_groups[func_name]
            group["definitions"].append(node)  # type: ignore[union-attr]

            if is_overloaded_function(node):
                group["overloads"].append(node)  # type: ignore[union-attr]
                group["has_overload"] = True
            else:
                # Non-overload definition is the implementation
                group["implementation"] = node

    # Calculate final metadata
    for func_name, group in function_groups.items():
        overloads: list = group["overloads"]  # type: ignore[assignment]
        group["overload_count"] = len(overloads)
        group["has_implementation"] = group["implementation"] is not None

        # Warn if multiple definitions without @overload
        definitions: list = group["definitions"]  # type: ignore[assignment]
        if len(definitions) > 1 and not group["has_overload"]:
            logger.warning(
                "Function '%s' defined %d times without @overload decorator",
                func_name,
                len(definitions),
            )

    return function_groups


__all__ = ["group_functions_by_name", "is_overloaded_function"]
