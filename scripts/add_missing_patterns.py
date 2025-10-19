#!/usr/bin/env python3
"""Add missing pattern classifications to _constants.py."""

# Remaining patterns to add to specific languages:
ADDITIONS = {
    "JAVA": {
        "BOUNDARY_ERROR": ["catch_type"],
        "BOUNDARY_RESOURCE": ["resource_specification"],
        "DEFINITION_DATA": ["inferred_parameters", "receiver_parameter"],
        "DEFINITION_TYPE": [
            "dimensions",
            "dimensions_expr",
            "enum_body_declarations",
            "superclass",
        ],
        "FLOW_BRANCHING": ["record_pattern_component"],
        "SYNTAX_ANNOTATION": ["marker_annotation", "element_value_pair"],
        "SYNTAX_LITERAL": ["string_interpolation"],
    },
    "KOTLIN": {
        "BOUNDARY_MODULE": ["package_header"],
        "DEFINITION_TYPE": ["explicit_delegation"],
        "SYNTAX_ANNOTATION": ["file_annotation"],
        "SYNTAX_KEYWORD": ["modifiers"],
    },
    "RUST": {"DEFINITION_DATA": ["closure_parameters"], "DEFINITION_TYPE": ["bracketed_type"]},
    "SCALA": {
        "FLOW_BRANCHING": ["case_clause"],
        "DEFINITION_TYPE": ["enum_case_definitions"],
        "SYNTAX_KEYWORD": ["modifiers"],
        "SYNTAX_LITERAL": ["interpolated_string"],
    },
    "SOLIDITY": {
        "DEFINITION_DATA": ["variable_declaration_statement", "variable_declaration_tuple"],
        "OPERATION_OPERATOR": ["payable_conversion_expression"],
    },
    "SWIFT": {
        "DEFINITION_DATA": ["lambda_function_type_parameters"],
        "DEFINITION_TYPE": ["lambda_function_type"],
        "SYNTAX_KEYWORD": ["modifiers"],
    },
    "RUBY": {"DEFINITION_TYPE": ["superclass"]},
    "HASKELL": {"DEFINITION_DATA": ["declarations"], "FLOW_BRANCHING": ["patterns"]},
    "TYPESCRIPT": {"SYNTAX_ANNOTATION": ["asserts_annotation", "type_predicate_annotation"]},
    "TSX": {"SYNTAX_ANNOTATION": ["asserts_annotation", "type_predicate_annotation"]},
}

print("Patterns to add:")
for lang, categories in ADDITIONS.items():
    print(f"\n{lang}:")
    for category, patterns in categories.items():
        print(f"  {category}: {', '.join(patterns)}")
