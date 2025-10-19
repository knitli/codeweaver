"""Optimized composite check patterns grouped by language and classification."""

import re

from codeweaver.language import SemanticSearchLanguage
from codeweaver.semantic.classifications import SemanticClass


# Language-specific pattern groups (ordered by frequency)
# Structure: {Language: tuple[(SemanticClass, compiled_pattern), ...]
LANG_SPECIFIC_PATTERNS: dict[
    SemanticSearchLanguage, tuple[tuple[SemanticClass, re.Pattern[str]], ...]
] = {
    SemanticSearchLanguage.BASH: (
        (
            SemanticClass.SYNTAX_KEYWORD,
            re.compile(r"^(?:(?:(command_name|do_group|case_item|herestring_redirect)))$"),
        ),
        (SemanticClass.SYNTAX_PUNCTUATION, re.compile(r"^(?:(?:(file_redirect|subscript)))$")),
    ),
    SemanticSearchLanguage.C_LANG: (
        (
            SemanticClass.BOUNDARY_MODULE,
            re.compile(
                r"^(?:(?:(imports?(_(directive|list|name|specifier))?|linkage_specification)))$"
            ),
        ),
        (
            SemanticClass.DEFINITION_DATA,
            re.compile(
                r"^(?:(?:(init_declarator|initializer_pair|subscript_range_designator))|(?:.+_designator))$"
            ),
        ),
        (SemanticClass.DEFINITION_TYPE, re.compile(r"^(?:(?:enumerator))$")),
        (
            SemanticClass.FLOW_BRANCHING,
            re.compile(r"^(?:(?:(switch(_case|_default)|she_(except|finally)_clause)))$"),
        ),
        (SemanticClass.OPERATION_OPERATOR, re.compile(r"^(?:(?:comma_expression))$")),
        (
            SemanticClass.SYNTAX_ANNOTATION,
            re.compile(
                r"^(?:(?:gnu_asm_(clobber_list|goto_list|input_operand(_list)?|output_operand(_list)?))|(?:preproc_(call|def|function_def|include)))$"
            ),
        ),
    ),
    SemanticSearchLanguage.C_PLUS_PLUS: (
        (
            SemanticClass.BOUNDARY_MODULE,
            re.compile(
                r"^(?:(?:(imports?(_(directive|list|name|specifier))?|linkage_specification)))$"
            ),
        ),
        (
            SemanticClass.DEFINITION_DATA,
            re.compile(
                r"^(?:(?:lambda_capture_initializer)|(?:(init_declarator|initializer_pair|subscript_range_designator))|(?:.+_designator))$"
            ),
        ),
        (
            SemanticClass.DEFINITION_TYPE,
            re.compile(
                r"^(?:(?:(alias_declaration|concept_definition|new_declarator|pointer_type_declarator|namespace_alias_definition|lambda_declarator|friend_declaration|simple_requirement|init_statement|module_(name|partition)|trailing_return_type|explicit_object_parameter_declaration))|(?:optional_type_parameter_declaration)|(?:enumerator))$"
            ),
        ),
        (
            SemanticClass.FLOW_BRANCHING,
            re.compile(
                r"^(?:(?:(switch(_case|_default)|she_(except|finally)_clause))|(?:catch_(clause|declaration))|(?:condition_clause))$"
            ),
        ),
        (SemanticClass.OPERATION_OPERATOR, re.compile(r"^(?:(?:comma_expression))$")),
        (
            SemanticClass.SYNTAX_ANNOTATION,
            re.compile(
                r"^(?:(?:gnu_asm_(clobber_list|goto_list|input_operand(_list)?|output_operand(_list)?))|(?:(consteval_block|static_assert)_declaration)|(?:preproc_(call|def|function_def|include)))$"
            ),
        ),
    ),
    SemanticSearchLanguage.C_SHARP: (
        (SemanticClass.BOUNDARY_MODULE, re.compile(r"^(?:(?:file_scoped_namespace_declaration))$")),
        (SemanticClass.FLOW_BRANCHING, re.compile(r"^(?:(?:catch_(clause|declaration)))$")),
        (SemanticClass.OPERATION_OPERATOR, re.compile(r"^(?:(?:(unary|declaration)_expression))$")),
        (SemanticClass.SYNTAX_ANNOTATION, re.compile(r"^(?:(?:preproc_(region|endregion)))$")),
        (
            SemanticClass.SYNTAX_IDENTIFIER,
            re.compile(r"^(?:(?:(member_binding_expression|tuple_element)))$"),
        ),
        (
            SemanticClass.SYNTAX_KEYWORD,
            re.compile(
                r"^(?:(?:(primary_constructor_base_type|parenthesized_variable_designation|arrow_expression_clause|subpattern|positional_pattern_clause|property_pattern_clause|interpolation_alignment_clause|argument|global_attribute|join_into_clause)))$"
            ),
        ),
    ),
    SemanticSearchLanguage.CSS: (
        (SemanticClass.SYNTAX_IDENTIFIER, re.compile(r"^(?:(?:.+_selector))$")),
        (
            SemanticClass.SYNTAX_KEYWORD,
            re.compile(r"^(?:(?:(at_rule|class_name|rule_set|selectors)))$"),
        ),
        (SemanticClass.SYNTAX_LITERAL, re.compile(r"^(?:(?:.+_(query|statement|value)))$")),
    ),
    SemanticSearchLanguage.ELIXIR: (
        (SemanticClass.OPERATION_OPERATOR, re.compile(r"^(?:(?:(access_call|unary_operator)))$")),
        (SemanticClass.SYNTAX_IDENTIFIER, re.compile(r"^(?:(?:pair(_pattern)?))$")),
        (
            SemanticClass.SYNTAX_LITERAL,
            re.compile(
                r"^(?:(?:(bitstring|body|charlist|keywords|map_content|sigil|source|quoted_(atom|keyword))))$"
            ),
        ),
    ),
    SemanticSearchLanguage.GO: (
        (
            SemanticClass.BOUNDARY_MODULE,
            re.compile(
                r"^(?:(?:(imports?(_(directive|list|name|specifier))?|linkage_specification)))$"
            ),
        ),
        (
            SemanticClass.DEFINITION_TYPE,
            re.compile(r"^(?:(?:(implicit_length_array_type|method_elem|keyed_element)))$"),
        ),
        (
            SemanticClass.FLOW_BRANCHING,
            re.compile(r"^(?:(?:(communication_case|default_case|literal_(element|value))))$"),
        ),
        (
            SemanticClass.FLOW_ITERATION,
            re.compile(
                r"^(?:(?:for(_clause|_in_clause|_numeric_clause)?)|(?:(range_clause|receive_statement)))$"
            ),
        ),
    ),
    SemanticSearchLanguage.HASKELL: (
        (
            SemanticClass.BOUNDARY_MODULE,
            re.compile(
                r"^(?:(?:(imports?(_(directive|list|name|specifier))?|linkage_specification)))$"
            ),
        ),
        (
            SemanticClass.DEFINITION_DATA,
            re.compile(
                r"^(?:(?:(lazy|strict)_field)|(?:(binding|binding_set|binding_list|local_binds))|(?:(equations|children|fields|header|match|prefix|qualifiers|quoted_decls)))$"
            ),
        ),
        (
            SemanticClass.DEFINITION_TYPE,
            re.compile(
                r"^(?:(?:(fundep|fundeps|kind_application|field_path))|(?:(full_)?enum(erators?|_case|_assignment|_entry))|(?:instance_declarations)|(?:class_(body|declarations?))|(?:(associated_type|constructor_synonym|explicit_type|gadt_constructor(s)?|newtype_constructor)))$"
            ),
        ),
        (
            SemanticClass.FLOW_BRANCHING,
            re.compile(
                r"^(?:(?:match(_conditional_expression|_default_expression))|(?:(alternative|alternatives)))$"
            ),
        ),
        (SemanticClass.FLOW_ITERATION, re.compile(r"^(?:(?:do_(block|module)))$")),
        (
            SemanticClass.OPERATION_INVOCATION,
            re.compile(r"^(?:(?:(construct_signature|data_constructors?)))$"),
        ),
        (
            SemanticClass.SYNTAX_KEYWORD,
            re.compile(
                r"^(?:(?:(annotated|constructor_synonyms|equation|quoter|field_(name|update)|function_head_parens|haskell|inferred|infix_id|special|quantified_variables|type_(params|patterns)|guards)))$"
            ),
        ),
    ),
    SemanticSearchLanguage.HTML: (
        (
            SemanticClass.SYNTAX_ANNOTATION,
            re.compile(r"^(?:(?:(attribute|quoted_attribute_value)))$"),
        ),
        (
            SemanticClass.SYNTAX_PUNCTUATION,
            re.compile(
                r"^(?:(?:(element|script_element|style_element))|(?:erroneous_end_tag)|(?:(start|end|self_closing)_tag))$"
            ),
        ),
    ),
    SemanticSearchLanguage.JAVA: (
        (
            SemanticClass.OPERATION_INVOCATION,
            re.compile(r"^(?:(?:explicit_constructor_invocation))$"),
        ),
        (
            SemanticClass.SYNTAX_ANNOTATION,
            re.compile(
                r"^(?:(?:annotation)|(?:(element_value_pair|marker_annotation|scoped_identifier)))$"
            ),
        ),
        (
            SemanticClass.SYNTAX_IDENTIFIER,
            re.compile(
                r"^(?:(?:(variable(_declarator|_declaration|_list))|value_binding_pattern))$"
            ),
        ),
        (
            SemanticClass.SYNTAX_KEYWORD,
            re.compile(
                r"^(?:(?:(dimensions(_expr)?|catch_type|receiver_parameter|record_pattern(_component)?|inferred_parameters|superclass|string_interpolation)))$"
            ),
        ),
    ),
    SemanticSearchLanguage.JAVASCRIPT: (
        (
            SemanticClass.BOUNDARY_MODULE,
            re.compile(
                r"^(?:(?:(imports?(_(directive|list|name|specifier))?|linkage_specification)))$"
            ),
        ),
        (SemanticClass.DEFINITION_DATA, re.compile(r"^(?:(?:class_static_block))$")),
        (
            SemanticClass.DEFINITION_TYPE,
            re.compile(
                r"^(?:(?:(full_)?enum(erators?|_case|_assignment|_entry))|(?:class_(body|declarations?)))$"
            ),
        ),
        (
            SemanticClass.FLOW_BRANCHING,
            re.compile(
                r"^(?:(?:finally_clause)|(?:(switch(_case|_default)|she_(except|finally)_clause))|(?:catch_(clause|declaration)))$"
            ),
        ),
        (
            SemanticClass.SYNTAX_IDENTIFIER,
            re.compile(
                r"^(?:(?:assignment_pattern)|(?:(variable(_declarator|_declaration|_list))|value_binding_pattern)|(?:(nested_identifier|field_definition|object_assignment_pattern))|(?:(jsx_(attribute|expression|namespace_name)|namespace_(import|export)|named_imports|import_require_clause|constraint|default_type|rest_type|class_heritage|computed_property_name|sequence_expression))|(?:pair(_pattern)?))$"
            ),
        ),
        (SemanticClass.SYNTAX_LITERAL, re.compile(r"^(?:(?:jsx_(closing|opening)_element))$")),
    ),
    SemanticSearchLanguage.JSON: (
        (SemanticClass.SYNTAX_IDENTIFIER, re.compile(r"^(?:(?:pair))$")),
    ),
    SemanticSearchLanguage.JSX: (
        (
            SemanticClass.BOUNDARY_MODULE,
            re.compile(
                r"^(?:(?:(imports?(_(directive|list|name|specifier))?|linkage_specification)))$"
            ),
        ),
        (SemanticClass.DEFINITION_DATA, re.compile(r"^(?:(?:class_static_block))$")),
        (
            SemanticClass.DEFINITION_TYPE,
            re.compile(
                r"^(?:(?:(full_)?enum(erators?|_case|_assignment|_entry))|(?:class_(body|declarations?)))$"
            ),
        ),
        (
            SemanticClass.FLOW_BRANCHING,
            re.compile(
                r"^(?:(?:finally_clause)|(?:(switch(_case|_default)|she_(except|finally)_clause))|(?:catch_(clause|declaration)))$"
            ),
        ),
        (
            SemanticClass.SYNTAX_IDENTIFIER,
            re.compile(
                r"^(?:(?:assignment_pattern)|(?:(variable(_declarator|_declaration|_list))|value_binding_pattern)|(?:(nested_identifier|field_definition|object_assignment_pattern))|(?:(jsx_(attribute|expression|namespace_name)|namespace_(import|export)|named_imports|import_require_clause|constraint|default_type|rest_type|class_heritage|computed_property_name|sequence_expression))|(?:pair(_pattern)?))$"
            ),
        ),
        (SemanticClass.SYNTAX_LITERAL, re.compile(r"^(?:(?:jsx_(closing|opening)_element))$")),
    ),
    SemanticSearchLanguage.KOTLIN: (
        (
            SemanticClass.DEFINITION_DATA,
            re.compile(
                r"^(?:(?:(primary_constructor|when_(subject|entry)|annotated_lambda|multi_variable_declaration|property_delegate|range_test|getter|function_type_parameters)))$"
            ),
        ),
        (
            SemanticClass.DEFINITION_TYPE,
            re.compile(r"^(?:(?:(full_)?enum(erators?|_case|_assignment|_entry)))$"),
        ),
        (
            SemanticClass.EXPRESSION_ANONYMOUS,
            re.compile(
                r"^(?:(?:(annotated_lambda|anonymous_class|anonymous_function_use_clause)))$"
            ),
        ),
    ),
    SemanticSearchLanguage.LUA: (
        (
            SemanticClass.FLOW_BRANCHING,
            re.compile(r"^(?:(?:(if_)?guards?)|(?:else_(clause|statement)))$"),
        ),
        (
            SemanticClass.FLOW_ITERATION,
            re.compile(
                r"^(?:(?:for_generic_clause)|(?:for(_clause|_in_clause|_numeric_clause)?))$"
            ),
        ),
        (SemanticClass.OPERATION_INVOCATION, re.compile(r"^(?:(?:method_index_expression))$")),
        (
            SemanticClass.SYNTAX_IDENTIFIER,
            re.compile(
                r"^(?:(?:(variable(_declarator|_declaration|_list))|value_binding_pattern))$"
            ),
        ),
    ),
    SemanticSearchLanguage.NIX: (
        (
            SemanticClass.DEFINITION_DATA,
            re.compile(r"^(?:(?:(binding|binding_set|binding_list|local_binds)))$"),
        ),
        (
            SemanticClass.SYNTAX_IDENTIFIER,
            re.compile(
                r"^(?:(?:(attrpath|formal|formals|inherit_from|inherited_attrs|interpolation|source_code)))$"
            ),
        ),
    ),
    SemanticSearchLanguage.PHP: (
        (
            SemanticClass.DEFINITION_DATA,
            re.compile(r"^(?:(?:(property_element|static_variable_declaration)))$"),
        ),
        (SemanticClass.DEFINITION_TYPE, re.compile(r"^(?:(?:(simple_)?enum_case))$")),
        (
            SemanticClass.EXPRESSION_ANONYMOUS,
            re.compile(
                r"^(?:(?:(annotated_lambda|anonymous_class|anonymous_function_use_clause)))$"
            ),
        ),
        (
            SemanticClass.FLOW_BRANCHING,
            re.compile(
                r"^(?:(?:(if_)?guards?)|(?:finally_clause)|(?:match(_conditional_expression|_default_expression))|(?:else_(clause|statement)))$"
            ),
        ),
        (
            SemanticClass.SYNTAX_KEYWORD,
            re.compile(
                r"^(?:(?:(anonymous_class|use_instead_of_clause|property_(hook|promotion_parameter)|class_interface_clause|const_element|by_ref|declare_directive|list_literal)))$"
            ),
        ),
    ),
    SemanticSearchLanguage.PYTHON: (
        (
            SemanticClass.FLOW_BRANCHING,
            re.compile(r"^(?:(?:(if_)?guards?)|(?:else_(clause|statement)))$"),
        ),
        (
            SemanticClass.FLOW_ITERATION,
            re.compile(r"^(?:(?:for(_clause|_in_clause|_numeric_clause)?))$"),
        ),
        (
            SemanticClass.SYNTAX_IDENTIFIER,
            re.compile(
                r"^(?:(?:(keyword_argument|with_item|interpolation))|(?:dotted_name)|(?:pair(_pattern)?))$"
            ),
        ),
        (
            SemanticClass.SYNTAX_KEYWORD,
            re.compile(
                r"^(?:(?:(constrained_type|member_type|parenthesized_list_splat|chevron|if_clause|slice|relative_import|except_clause)))$"
            ),
        ),
        (SemanticClass.SYNTAX_LITERAL, re.compile(r"^(?:(?:format_expression))$")),
    ),
    SemanticSearchLanguage.RUBY: (
        (
            SemanticClass.FLOW_BRANCHING,
            re.compile(r"^(?:(?:(if|unless)_guard)|(?:(block|in_clause|rescue)))$"),
        ),
        (SemanticClass.FLOW_ITERATION, re.compile(r"^(?:(?:do_(block|module)))$")),
        (
            SemanticClass.SYNTAX_IDENTIFIER,
            re.compile(
                r"^(?:(?:(exception_variable|exceptions|destructured_(left_assignment|parameter)|rest_assignment|method_parameters|block_parameters|body_statement|bare_(string|symbol)))|(?:pair(_pattern)?))$"
            ),
        ),
    ),
    SemanticSearchLanguage.RUST: (
        (
            SemanticClass.BOUNDARY_MODULE,
            re.compile(r"^(?:(?:(macro_rule|scoped_use_list|use_as_clause)))$"),
        ),
        (
            SemanticClass.DEFINITION_TYPE,
            re.compile(
                r"^(?:(?:lifetime_parameter)|(?:(use_(wildcard|bounds)|trait_bounds|self_parameter|token_(tree|repetition)|for_lifetimes|match_arm|let_chain))|(?:(higher_ranked_trait_bound|generic_type_with_turbofish|where_predicate)))$"
            ),
        ),
        (SemanticClass.FLOW_BRANCHING, re.compile(r"^(?:(?:let_condition))$")),
    ),
    SemanticSearchLanguage.SCALA: (
        (
            SemanticClass.DEFINITION_TYPE,
            re.compile(
                r"^(?:(?:(lazy|repeated)_parameter_type)|(?:(contravariant|covariant)_type_parameter)|(?:(simple_)?enum_case)|(?:(full_)?enum(erators?|_case|_assignment|_entry))|(?:(compound_type|applied_constructor_type|named_tuple_type|structural_type|match_type|singleton_type|type_case_clause|self_type|stable_type_identifier|identifiers|bindings|refinement|namespace_selectors|given_conditional|annotated_lambda|indented_cases|literal_type|parameter_types|access_(modifier|qualifier)))|(?:(name_and_type|view_bound))|(?:(context|lower|upper)_bound))$"
            ),
        ),
        (SemanticClass.SYNTAX_ANNOTATION, re.compile(r"^(?:(?:annotation))$")),
        (SemanticClass.SYNTAX_IDENTIFIER, re.compile(r"^(?:(?:(arrow|as)_renamed_identifier))$")),
    ),
    SemanticSearchLanguage.SOLIDITY: (
        (
            SemanticClass.BOUNDARY_MODULE,
            re.compile(
                r"^(?:(?:(imports?(_(directive|list|name|specifier))?|linkage_specification)))$"
            ),
        ),
        (
            SemanticClass.DEFINITION_DATA,
            re.compile(
                r"^(?:(?:(call_struct_argument|parameter))|(?:(struct_field_assignment|struct_member)))$"
            ),
        ),
        (
            SemanticClass.DEFINITION_TYPE,
            re.compile(r"^(?:(?:(full_)?enum(erators?|_case|_assignment|_entry)))$"),
        ),
        (
            SemanticClass.OPERATION_OPERATOR,
            re.compile(
                r"^(?:(?:update_expression)|(?:member_expression)|(?:(array|slice)_access)|(?:(unary|declaration)_expression))$"
            ),
        ),
        (
            SemanticClass.SYNTAX_ANNOTATION,
            re.compile(
                r"^(?:(?:solidity_pragma_token)|(?:(pragma_directive|assembly_statement|revert_(statement|arguments)|emit_statement)))$"
            ),
        ),
        (
            SemanticClass.SYNTAX_IDENTIFIER,
            re.compile(
                r"^(?:(?:(variable(_declarator|_declaration|_list))|value_binding_pattern))$"
            ),
        ),
        (
            SemanticClass.SYNTAX_KEYWORD,
            re.compile(
                r"^(?:(?:(error_declaration|event_definition|constructor_definition|fallback_receive_definition|meta_type_expression|payable_conversion_expression|inline_array_expression|user_defined_type(_definition)?|using_alias|return_type_definition|assembly_flags|any_pragma_token|type_name|expression|statement|block_statement))|(?:yul_.+))$"
            ),
        ),
    ),
    SemanticSearchLanguage.SWIFT: (
        (
            SemanticClass.DEFINITION_TYPE,
            re.compile(
                r"^(?:(?:protocol_(body|function_declaration|property_declaration|property_requirements)))$"
            ),
        ),
        (
            SemanticClass.OPERATION_OPERATOR,
            re.compile(
                r"^(?:(?:bitwise_operation)|(?:(additive|multiplicative|bitwise_operation|comparison|equality|conjunction|disjunction)_expression)|(?:(unary|declaration)_expression))$"
            ),
        ),
        (
            SemanticClass.SYNTAX_ANNOTATION,
            re.compile(r"^(?:(?:(navigation_suffix|suppressed_constraint)))$"),
        ),
        (
            SemanticClass.SYNTAX_IDENTIFIER,
            re.compile(
                r"^(?:(?:(variable(_declarator|_declaration|_list))|value_binding_pattern))$"
            ),
        ),
        (
            SemanticClass.SYNTAX_KEYWORD,
            re.compile(
                r"^(?:(?:(computed_(getter|setter|modify|property)|call_suffix|capture_list_item|key_path_(expression|string_expression)|constructor_(expression|suffix)|typealias_declaration|precedence_group_(declaration|attribute|attributes)|playground_literal|raw_str_interpolation|interpolated_expression|deinit_declaration|directly_assignable_expression|guard_statement|repeat_while_statement|availability_condition|directive|control_transfer_statement|statements|associatedtype_declaration|external_macro_definition|macro_declaration|macro_invocation|enum_type_parameters|equality_constraint|subscript_declaration|tuple_type_item|value_(argument_label|pack_expansion|parameter_pack)|type_pack_expansion|type_parameter_pack|opaque_type|protocol_composition_type|metatype)))$"
            ),
        ),
        (
            SemanticClass.SYNTAX_LITERAL,
            re.compile(
                r"^(?:(?:(array|dictionary)_literal)|(?:(line|multi_line)_string_literal)|(?:(tuple|array_literal|dictionary_literal|nil_coalescing|open_(end|start)_range|range)_expression))$"
            ),
        ),
    ),
    SemanticSearchLanguage.TSX: (
        (
            SemanticClass.BOUNDARY_MODULE,
            re.compile(
                r"^(?:(?:(imports?(_(directive|list|name|specifier))?|linkage_specification)))$"
            ),
        ),
        (SemanticClass.DEFINITION_DATA, re.compile(r"^(?:(?:class_static_block))$")),
        (
            SemanticClass.DEFINITION_TYPE,
            re.compile(
                r"^(?:(?:mapped_type_clause)|(?:(full_)?enum(erators?|_case|_assignment|_entry)))$"
            ),
        ),
        (
            SemanticClass.FLOW_BRANCHING,
            re.compile(
                r"^(?:(?:finally_clause)|(?:(switch(_case|_default)|she_(except|finally)_clause))|(?:catch_(clause|declaration)))$"
            ),
        ),
        (
            SemanticClass.OPERATION_INVOCATION,
            re.compile(r"^(?:(?:call_signature)|(?:(construct_signature|data_constructors?)))$"),
        ),
        (
            SemanticClass.SYNTAX_IDENTIFIER,
            re.compile(
                r"^(?:(?:assignment_pattern)|(?:(variable(_declarator|_declaration|_list))|value_binding_pattern)|(?:(nested_identifier|field_definition|object_assignment_pattern))|(?:(jsx_(attribute|expression|namespace_name)|namespace_(import|export)|named_imports|import_require_clause|constraint|default_type|rest_type|class_heritage|computed_property_name|sequence_expression))|(?:pair(_pattern)?))$"
            ),
        ),
        (SemanticClass.SYNTAX_LITERAL, re.compile(r"^(?:(?:jsx_(closing|opening)_element))$")),
    ),
    SemanticSearchLanguage.TYPESCRIPT: (
        (
            SemanticClass.BOUNDARY_MODULE,
            re.compile(
                r"^(?:(?:(imports?(_(directive|list|name|specifier))?|linkage_specification)))$"
            ),
        ),
        (SemanticClass.DEFINITION_DATA, re.compile(r"^(?:(?:class_static_block))$")),
        (
            SemanticClass.DEFINITION_TYPE,
            re.compile(
                r"^(?:(?:mapped_type_clause)|(?:(full_)?enum(erators?|_case|_assignment|_entry)))$"
            ),
        ),
        (
            SemanticClass.FLOW_BRANCHING,
            re.compile(
                r"^(?:(?:finally_clause)|(?:(switch(_case|_default)|she_(except|finally)_clause))|(?:catch_(clause|declaration)))$"
            ),
        ),
        (
            SemanticClass.OPERATION_INVOCATION,
            re.compile(r"^(?:(?:call_signature)|(?:(construct_signature|data_constructors?)))$"),
        ),
        (
            SemanticClass.SYNTAX_IDENTIFIER,
            re.compile(
                r"^(?:(?:assignment_pattern)|(?:(variable(_declarator|_declaration|_list))|value_binding_pattern)|(?:(nested_identifier|field_definition|object_assignment_pattern))|(?:(jsx_(attribute|expression|namespace_name)|namespace_(import|export)|named_imports|import_require_clause|constraint|default_type|rest_type|class_heritage|computed_property_name|sequence_expression))|(?:pair(_pattern)?))$"
            ),
        ),
        (SemanticClass.SYNTAX_LITERAL, re.compile(r"^(?:(?:jsx_(closing|opening)_element))$")),
    ),
    SemanticSearchLanguage.YAML: ((SemanticClass.SYNTAX_LITERAL, re.compile(r"^(?:(?:scalar))$")),),
}


# Generic cross-language patterns (ordered by frequency)
# Structure: tuple[(SemanticClass, compiled_pattern), ...]
GENERIC_PATTERNS: tuple[tuple[SemanticClass, re.Pattern[str]], ...] = (
    (
        SemanticClass.BOUNDARY_MODULE,
        re.compile(
            r"^(?:(?:(aliased_import|extern_alias_directive|import_spec))|(?:(import|export|namespace)_(clause|attribute|spec_list|use_clause|use_group)))$"
        ),
    ),
    (
        SemanticClass.DEFINITION_CALLABLE,
        re.compile(r"^(?:(?:(method|property|function|abstract_method|index)_signature))$"),
    ),
    (
        SemanticClass.DEFINITION_DATA,
        re.compile(
            r"^(?:(?:(formal|lambda|class|function_value|bracketed)_parameters?)|(?:(block|error|event|return|call_struct_argument|function_pointer|hash_splat|keyword|optional|simple|splat|variadic|yul_variable_declaration)_parameter)|(?:.+_declaration)|(?:.+_initializer(_list)?))$"
        ),
    ),
    (
        SemanticClass.DEFINITION_TYPE,
        re.compile(
            r"^(?:(?:type_(argument|parameter|constraint|projection|bound|test|case|requirement|elem)s?(_list)?)|(?:(adding|omitting|opting|asserts|type_predicate)_type_annotation)|(?:(extends_type_clause|derives_clause|inheritance_specifier))|(?:(array|dictionary|optional|function|generic|projected|qualified)_type)|(?:template_(argument_list|parameter_list|declaration|body|substitution|template_parameter_declaration))|(?:type_(alias|annotation|application|binder|binding|lambda|parameter(_declaration)?|predicate|spec|family_(result|injectivity)))|(?:(extends|implements|base|super|delegation)_(clause|list|interfaces|class|specifiers?))|(?:.+_constraint))$"
        ),
    ),
    (
        SemanticClass.FLOW_BRANCHING,
        re.compile(
            r"^(?:(?:(switch|case)_(body|block|entry|section|label|rule|expression_arm|pattern|block_statement_group))|(?:(keyword|token_binding|view)_pattern)|(?:(catch|finally|rescue|after|else)_(block|clause|formal_parameter))|(?:(with|from|where|let|join|order_by|group|select|when|catch_filter)_clause)|(?:.+_pattern))$"
        ),
    ),
    (
        SemanticClass.OPERATION_OPERATOR,
        re.compile(
            r"^(?:(?:(spread|splat|hash_splat|dictionary_splat|variadic)_(element|argument|parameter|unpacking|pattern|type))|(?:(prefix|postfix|navigation|check)_expression))$"
        ),
    ),
    (
        SemanticClass.OPERATION_INVOCATION,
        re.compile(
            r"^(?:(?:(getter|setter|modify|didset|willset)_(specifier|clause))|(?:.+_invocation))$"
        ),
    ),
    (
        SemanticClass.SYNTAX_ANNOTATION,
        re.compile(
            r"^(?:(?:decorator)|(?:preproc_(elif|ifdef|elifdef|defined|error|line|pragma|undef|warning))|(?:.+_(modifier|modifiers|specifier|qualifier)))$"
        ),
    ),
    (
        SemanticClass.SYNTAX_LITERAL,
        re.compile(
            r"^(?:(?:(heredoc|nowdoc)_(body|redirect))|(?:(bare|quoted)_(string|symbol|atom|keyword|expression|pattern|type)))$"
        ),
    ),
    (
        SemanticClass.SYNTAX_PUNCTUATION,
        re.compile(
            r"^(?:(?:(field|ordered_field)_declaration_list)|(?:(expression|statement)_(list|case))|(?:(arguments?|parameters))|(?:(program|source_file|compilation_unit|translation_unit|document|stylesheet|chunk))|(?:.+_(list|arguments?))|(?:.+_(body|block|block_list)))$"
        ),
    ),
)


# Predicate-based checks (special cases): 2 checks
# These are preserved from the original COMPOSITE_CHECKS
# Original count: 145 individual checks
# Optimized count: 26 language groups + 10 generic patterns + 2 predicates
