# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Semantic node categories and importance scoring definitions."""

from __future__ import annotations

from typing import NewType

from codeweaver._common import BaseEnum


# Type alias for importance scores (0.0 to 1.0)
ImportanceScore = NewType("ImportanceScore", float)


class SemanticNodeCategory(str, BaseEnum):
    """Language-agnostic semantic categories for AST nodes with default importance scores.

    Categories are ordered roughly by typical search relevance and code structure importance.
    Higher scores indicate nodes more likely to be relevant for semantic search and chunking.
    """

    # === High Importance: Primary Code Structures (0.8-1.0) ===

    CLASS_DEFINITION = "class_definition"
    """Class, struct, interface, trait, or type definitions."""

    FUNCTION_DEFINITION = "function_definition"
    """Function, method, procedure, or subroutine definitions."""

    METHOD_DEFINITION = "method_definition"
    """Class methods, instance methods, static methods."""

    INTERFACE_DEFINITION = "interface_definition"
    """Interface, protocol, or abstract base definitions."""

    TRAIT_DEFINITION = "trait_definition"
    """Traits, mixins, or similar composition constructs."""

    ENUM_DEFINITION = "enum_definition"
    """Enumeration definitions."""

    # === Medium-High Importance: Declarations & Imports (0.6-0.8) ===

    TYPE_DEFINITION = "type_definition"
    """Type aliases, typedef, or custom type definitions."""

    VARIABLE_DECLARATION = "variable_declaration"
    """Variable, constant, or field declarations."""

    IMPORT_STATEMENT = "import_statement"
    """Import, require, use, include statements."""

    EXPORT_STATEMENT = "export_statement"
    """Export, public, module export statements."""

    NAMESPACE_DEFINITION = "namespace_definition"
    """Namespace, module, package definitions."""

    # === Medium Importance: Control Flow & Logic (0.4-0.6) ===

    CONDITIONAL_STATEMENT = "conditional_statement"
    """If, else, elif, switch, match statements."""

    LOOP_STATEMENT = "loop_statement"
    """For, while, do-while, repeat loops."""

    TRY_CATCH_STATEMENT = "try_catch_statement"
    """Try, catch, except, finally, error handling."""

    MATCH_STATEMENT = "match_statement"
    """Pattern matching, switch expressions."""

    RETURN_STATEMENT = "return_statement"
    """Return, yield statements."""

    BREAK_CONTINUE_STATEMENT = "break_continue_statement"
    """Break, continue, next statements."""

    # === Medium-Low Importance: Expressions & Operations (0.2-0.4) ===

    FUNCTION_CALL = "function_call"
    """Function calls, method invocations."""

    ASSIGNMENT_EXPRESSION = "assignment_expression"
    """Assignment operations, variable updates."""

    BINARY_EXPRESSION = "binary_expression"
    """Binary operations, arithmetic, comparisons."""

    UNARY_EXPRESSION = "unary_expression"
    """Unary operations, prefix/postfix operators."""

    LAMBDA_EXPRESSION = "lambda_expression"
    """Lambda, anonymous functions, closures."""

    OBJECT_CREATION = "object_creation"
    """Constructor calls, object instantiation."""

    PROPERTY_ACCESS = "property_access"
    """Field access, property access, member access."""

    # === Low Importance: Literals & Syntax (0.0-0.2) ===

    IDENTIFIER = "identifier"
    """Variable names, identifiers."""

    LITERAL = "literal"
    """String, number, boolean literals."""

    COMMENT = "comment"
    """Comments, documentation strings."""

    ANNOTATION = "annotation"
    """Decorators, attributes, annotations."""

    # === Language-Specific & Modern Constructs (0.3-0.5) ===

    ASYNC_STATEMENT = "async_statement"
    """Async/await constructs, futures, promises."""

    PATTERN_MATCHING = "pattern_matching"
    """Pattern matching, destructuring, case patterns."""

    OPERATOR = "operator"
    """Language operators, arithmetic, logical, comparison."""

    MARKUP_ELEMENT = "markup_element"
    """HTML elements, XML nodes, markup structures."""

    PREPROCESSOR = "preprocessor"
    """Preprocessor directives, macros, compiler hints."""

    PUNCTUATION = "punctuation"
    """Braces, parentheses, semicolons."""

    WHITESPACE = "whitespace"
    """Whitespace, newlines."""

    UNKNOWN = "unknown"
    """Unclassified or language-specific nodes."""

    __slots__ = ()

    def default_importance_score(self) -> ImportanceScore:
        """Get the default importance score for this semantic category."""
        return ImportanceScore(_DEFAULT_IMPORTANCE_SCORES[self])


# Default importance scores for each semantic category
_DEFAULT_IMPORTANCE_SCORES: dict[SemanticNodeCategory, float] = {
    # High Importance: Primary Code Structures (0.8-1.0)
    SemanticNodeCategory.CLASS_DEFINITION: 0.95,
    SemanticNodeCategory.FUNCTION_DEFINITION: 0.90,
    SemanticNodeCategory.METHOD_DEFINITION: 0.88,
    SemanticNodeCategory.INTERFACE_DEFINITION: 0.92,
    SemanticNodeCategory.TRAIT_DEFINITION: 0.90,
    SemanticNodeCategory.ENUM_DEFINITION: 0.85,
    # Medium-High Importance: Declarations & Imports (0.6-0.8)
    SemanticNodeCategory.TYPE_DEFINITION: 0.78,
    SemanticNodeCategory.VARIABLE_DECLARATION: 0.70,
    SemanticNodeCategory.IMPORT_STATEMENT: 0.72,
    SemanticNodeCategory.EXPORT_STATEMENT: 0.68,
    SemanticNodeCategory.NAMESPACE_DEFINITION: 0.75,
    # Medium Importance: Control Flow & Logic (0.4-0.6)
    SemanticNodeCategory.CONDITIONAL_STATEMENT: 0.55,
    SemanticNodeCategory.LOOP_STATEMENT: 0.58,
    SemanticNodeCategory.TRY_CATCH_STATEMENT: 0.60,
    SemanticNodeCategory.MATCH_STATEMENT: 0.56,
    SemanticNodeCategory.RETURN_STATEMENT: 0.50,
    SemanticNodeCategory.BREAK_CONTINUE_STATEMENT: 0.45,
    # Medium-Low Importance: Expressions & Operations (0.2-0.4)
    SemanticNodeCategory.FUNCTION_CALL: 0.38,
    SemanticNodeCategory.ASSIGNMENT_EXPRESSION: 0.35,
    SemanticNodeCategory.BINARY_EXPRESSION: 0.25,
    SemanticNodeCategory.UNARY_EXPRESSION: 0.22,
    SemanticNodeCategory.LAMBDA_EXPRESSION: 0.40,
    SemanticNodeCategory.OBJECT_CREATION: 0.36,
    SemanticNodeCategory.PROPERTY_ACCESS: 0.28,
    # Low Importance: Literals & Syntax (0.0-0.2)
    SemanticNodeCategory.IDENTIFIER: 0.18,
    SemanticNodeCategory.LITERAL: 0.12,
    SemanticNodeCategory.COMMENT: 0.20,  # Higher than other literals for documentation value
    SemanticNodeCategory.ANNOTATION: 0.25,  # Higher for metadata value
    # Language-Specific & Modern Constructs (0.3-0.5)
    SemanticNodeCategory.ASYNC_STATEMENT: 0.48,
    SemanticNodeCategory.PATTERN_MATCHING: 0.45,
    SemanticNodeCategory.OPERATOR: 0.15,
    SemanticNodeCategory.MARKUP_ELEMENT: 0.42,
    SemanticNodeCategory.PREPROCESSOR: 0.35,
    SemanticNodeCategory.PUNCTUATION: 0.05,
    SemanticNodeCategory.WHITESPACE: 0.02,
    SemanticNodeCategory.UNKNOWN: 0.10,  # Conservative default
}
