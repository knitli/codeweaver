#!/usr/bin/env python3
"""Script to generate edit commands for adding remaining classification patterns."""

# Define all the additions needed
ADDITIONS = {
    "JAVA": """    SemanticSearchLanguage.JAVA: (
        (SemanticClass.BOUNDARY_ERROR, re.compile(r"^(?:(?:catch_type))$")),
        (SemanticClass.BOUNDARY_RESOURCE, re.compile(r"^(?:(?:resource_specification))$")),
        (
            SemanticClass.DEFINITION_DATA,
            re.compile(r"^(?:(?:(inferred_parameters|receiver_parameter)))$"),
        ),
        (
            SemanticClass.DEFINITION_TYPE,
            re.compile(
                r"^(?:(?:(dimensions(_expr)?|enum_body_declarations|superclass)))$"
            ),
        ),
        (SemanticClass.FLOW_BRANCHING, re.compile(r"^(?:(?:record_pattern_component))$")),
        (
            SemanticClass.SYNTAX_ANNOTATION,
            re.compile(r"^(?:(?:(marker_annotation|element_value_pair)))$"),
        ),
        (SemanticClass.SYNTAX_LITERAL, re.compile(r"^(?:(?:string_interpolation))$")),
    ),""",
    "KOTLIN": """(SemanticClass.BOUNDARY_MODULE, re.compile(r"^(?:(?:package_header))$")),
        (SemanticClass.DEFINITION_TYPE, re.compile(r"^(?:(?:(full_)?enum(erators?|_case|_assignment|_entry)|explicit_delegation))$")),
        (SemanticClass.SYNTAX_ANNOTATION, re.compile(r"^(?:(?:file_annotation))$")),
        (SemanticClass.SYNTAX_KEYWORD, re.compile(r"^(?:(?:modifiers))$")),""",
    "HASKELL": """(SemanticClass.DEFINITION_DATA, re.compile(r"^(?:(?:(lazy|strict)_field|(declarations))|(?:(binding|binding_set|binding_list|local_binds))|(?:(equations|children|fields|header|match|prefix|qualifiers|quoted_decls)))$")),
        (SemanticClass.FLOW_BRANCHING, re.compile(r"^(?:(?:match(_conditional_expression|_default_expression)|(patterns))|(?:(alternative|alternatives)))$")),""",
    "RUBY": """(SemanticClass.DEFINITION_TYPE, re.compile(r"^(?:(?:superclass))$")),""",
    "RUST": """(SemanticClass.DEFINITION_DATA, re.compile(r"^(?:(?:closure_parameters))$")),
        (SemanticClass.DEFINITION_TYPE, re.compile(r"^(?:(?:lifetime_parameter|bracketed_type)|(?:(use_(wildcard|bounds)|trait_bounds|self_parameter|token_(tree|repetition)|for_lifetimes|match_arm|let_chain))|(?:(higher_ranked_trait_bound|generic_type_with_turbofish|where_predicate)))$")),""",
    "SCALA": """(SemanticClass.FLOW_BRANCHING, re.compile(r"^(?:(?:case_clause))$")),
        (SemanticClass.DEFINITION_TYPE, re.compile(r"^(?:(?:(lazy|repeated)_parameter_type|(enum_case_definitions))|(?:(contravariant|covariant)_type_parameter)|(?:(simple_)?enum_case)|(?:(full_)?enum(erators?|_case|_assignment|_entry))|(?:(compound_type|applied_constructor_type|named_tuple_type|structural_type|match_type|singleton_type|type_case_clause|self_type|stable_type_identifier|identifiers|bindings|refinement|namespace_selectors|given_conditional|annotated_lambda|indented_cases|literal_type|parameter_types|access_(modifier|qualifier)))|(?:(name_and_type|view_bound))|(?:(context|lower|upper)_bound))$")),
        (SemanticClass.SYNTAX_KEYWORD, re.compile(r"^(?:(?:modifiers))$")),
        (SemanticClass.SYNTAX_LITERAL, re.compile(r"^(?:(?:interpolated_string))$")),""",
    "SOLIDITY": """(SemanticClass.DEFINITION_DATA, re.compile(r"^(?:(?:(call_struct_argument|parameter|variable_declaration_statement|variable_declaration_tuple))|(?:(struct_field_assignment|struct_member)))$")),
        (SemanticClass.OPERATION_OPERATOR, re.compile(r"^(?:(?:update_expression|payable_conversion_expression)|(?:member_expression)|(?:(array|slice)_access)|(?:(unary|declaration)_expression))$")),""",
    "SWIFT": """(SemanticClass.DEFINITION_DATA, re.compile(r"^(?:(?:lambda_function_type_parameters))$")),
        (SemanticClass.DEFINITION_TYPE, re.compile(r"^(?:(?:protocol_(body|function_declaration|property_declaration|property_requirements)|lambda_function_type))$")),
        (SemanticClass.SYNTAX_KEYWORD, re.compile(r"^(?:(?:computed_(getter|setter|modify|property)|call_suffix|capture_list_item|key_path_(expression|string_expression)|constructor_(expression|suffix)|typealias_declaration|precedence_group_(declaration|attribute|attributes)|playground_literal|raw_str_interpolation|interpolated_expression|deinit_declaration|directly_assignable_expression|guard_statement|repeat_while_statement|availability_condition|directive|control_transfer_statement|statements|associatedtype_declaration|external_macro_definition|macro_declaration|macro_invocation|enum_type_parameters|equality_constraint|subscript_declaration|tuple_type_item|value_(argument_label|pack_expansion|parameter_pack)|type_pack_expansion|type_parameter_pack|opaque_type|protocol_composition_type|metatype|modifiers))$")),""",
    "TYPESCRIPT": """(SemanticClass.OPERATION_INVOCATION, re.compile(r"^(?:(?:call_signature)|(?:(construct_signature|data_constructors?)))$")),
        (SemanticClass.SYNTAX_ANNOTATION, re.compile(r"^(?:(?:asserts_annotation|type_predicate_annotation))$")),""",
    "TSX": """(SemanticClass.OPERATION_INVOCATION, re.compile(r"^(?:(?:call_signature)|(?:(construct_signature|data_constructors?)))$")),
        (SemanticClass.SYNTAX_ANNOTATION, re.compile(r"^(?:(?:asserts_annotation|type_predicate_annotation))$")),""",
}

print("Generated pattern additions for remaining languages")
print("\n=== Instructions ===")
print("1. Insert JAVA entry between HASKELL and HTML")
print("2. Update KOTLIN, HASKELL, RUBY, RUST, SCALA, SOLIDITY, SWIFT to include new patterns")
print("3. Update TYPESCRIPT and TSX to include new patterns")
