# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Node mapping system for converting language-specific node types to semantic categories."""

from __future__ import annotations

import re

from functools import partial
from types import MappingProxyType
from typing import Annotated, Any

from pydantic import (
    Field,
    FieldSerializationInfo,
    SerializerFunctionWrapHandler,
    ValidatorFunctionWrapHandler,
    field_serializer,
    field_validator,
)

from codeweaver._common import BasedModel
from codeweaver.language import SemanticSearchLanguage
from codeweaver.semantic._constants import CLASSIFICATION_PATTERNS
from codeweaver.semantic.categories import SemanticNodeCategory


class NodeMapper(BasedModel):
    """Maps language-specific AST node types to semantic categories using heuristics and mappings."""

    # Heuristic patterns for automatic classification
    classification_patterns: MappingProxyType[SemanticNodeCategory, tuple[str, ...]] = (
        CLASSIFICATION_PATTERNS
    )

    manual_overrides: Annotated[
        dict[SemanticSearchLanguage, dict[str, SemanticNodeCategory]],
        Field(
            default_factory=lambda x: MappingProxyType(dict(x)),
            description="""Manual overrides: SemanticSearchLanguage -> {node_type: SemanticNodeCategory}""",
        ),
    ]

    @field_serializer(
        "classification_patterns",
        mode="wrap",
        when_used="json",
        return_type=dict[SemanticNodeCategory, tuple[str, ...]],
    )
    def _serialize_classification_patterns(
        self,
        value: MappingProxyType[SemanticNodeCategory, tuple[str, ...]],
        nxt: SerializerFunctionWrapHandler,
        _info: FieldSerializationInfo,
    ) -> dict[SemanticNodeCategory, tuple[str, ...]]:
        """Serialize classification patterns as a regular dict with lists for JSON."""
        return nxt(dict(value))  # type: ignore

    @field_validator("classification_patterns", mode="wrap")
    @classmethod
    def _validate_classification_patterns(
        cls, value: Any, nxt: ValidatorFunctionWrapHandler
    ) -> MappingProxyType[SemanticNodeCategory, tuple[str, ...]]:
        """Ensure classification patterns are a MappingProxyType."""
        if isinstance(value, MappingProxyType) and all(
            isinstance(k, SemanticNodeCategory) and isinstance(v, tuple)
            for k, v in value.items()
            if k and v
        ):
            return value
        if isinstance(value, MappingProxyType | dict):
            return MappingProxyType({nxt(k): nxt(v) for k, v in value.items()})
        if isinstance(value, str | bytes | bytearray):
            return cls._validate_classification_patterns(nxt(value), nxt)
        raise ValueError("classification_patterns must be a MappingProxyType or dict")

    def classify_node_type(
        self, node_type: str, language: SemanticSearchLanguage | str
    ) -> SemanticNodeCategory:
        """Classify a node type into a semantic category.

        Args:
            node_type: The tree-sitter node type name
            language: Optional language context for language-specific overrides

        Returns:
            The semantic category for this node type
        """
        if not isinstance(language, SemanticSearchLanguage):
            language = SemanticSearchLanguage.from_string(language)
        if (
            language
            and language in self.manual_overrides
            and node_type in self.manual_overrides[language]
        ):
            return self.manual_overrides[language][node_type]

        # Use heuristic classification
        return self._classify_with_heuristics(node_type)

    def _classify_with_heuristics(self, node_type: str) -> SemanticNodeCategory:
        """Classify a node type using pattern matching heuristics.

        Args:
            node_type: The node type to classify

        Returns:
            The best matching semantic category, or UNKNOWN if no match
        """
        node_type_lower = node_type.lower()

        # Try to match against patterns for each category
        for category, patterns in self.classification_patterns.items():
            for pattern in patterns:
                if re.match(pattern, node_type_lower):
                    return category

        # If no pattern matches, return UNKNOWN
        return SemanticNodeCategory.UNKNOWN

    def add_manual_override(
        self, language: SemanticSearchLanguage | str, node_type: str, category: SemanticNodeCategory
    ) -> None:
        """Add a manual override for a specific language and node type.

        Args:
            language: The language identifier
            node_type: The node type name
            category: The semantic category to assign
        """
        if not isinstance(language, SemanticSearchLanguage):
            language = SemanticSearchLanguage.from_string(language)
        if language not in self.manual_overrides:
            self.manual_overrides[language] = {}
        self.manual_overrides[language][node_type] = category

    def get_classification_confidence(
        self, node_type: str, language: SemanticSearchLanguage | str
    ) -> float:
        """Get confidence score for the classification of a node type.

        Args:
            node_type: The node type to assess
            language: Optional language context

        Returns:
            Confidence score from 0.0 to 1.0
        """
        if not isinstance(language, SemanticSearchLanguage):
            language = SemanticSearchLanguage.from_string(language)

        # Manual overrides have highest confidence
        if (
            language
            and language in self.manual_overrides
            and node_type in self.manual_overrides[language]
        ):
            return 1.0

        # Heuristic classification confidence based on pattern specificity
        node_type_lower = node_type.lower()
        best_confidence = 0.0

        for patterns in self.classification_patterns.values():
            for pattern in patterns:
                if re.match(pattern, node_type_lower):
                    # More specific patterns get higher confidence
                    pattern_specificity = len(pattern) / 50.0  # Normalize
                    confidence = min(0.9, 0.5 + pattern_specificity)
                    best_confidence = max(best_confidence, confidence)

        return best_confidence


# Global instance for convenient access
_default_mapper: NodeMapper | None = None


def get_node_mapper() -> NodeMapper:
    """Get the default global NodeMapper instance."""
    global _default_mapper
    if _default_mapper is None:
        _default_mapper = NodeMapper(manual_overrides={})
        _load_default_overrides(_default_mapper)
    return _default_mapper


def map_language_nodes_to_category(
    mapper: NodeMapper,
    language: SemanticSearchLanguage | str,
    node_type: tuple[str, ...],
    category: SemanticNodeCategory,
) -> None:
    """Map multiple node types for a language to a specific semantic category."""
    for nt in node_type:
        mapper.add_manual_override(language, nt, category)


def _load_python_overrides(mapper: NodeMapper) -> NodeMapper:
    """Load Python-specific manual overrides into the mapper."""
    loader = partial(map_language_nodes_to_category, mapper, SemanticSearchLanguage.PYTHON)
    mapper.add_manual_override(
        SemanticSearchLanguage.PYTHON, "module", SemanticNodeCategory.NAMESPACE_DEFINITION
    )
    loader(("import_from_statement", "import_statement"), SemanticNodeCategory.IMPORT_STATEMENT)
    loader(
        ("_compound_statement", "if_statement", "pattern", "as_pattern", "block"),
        SemanticNodeCategory.CONDITIONAL_STATEMENT,
    )

    mapper.add_manual_override(
        SemanticSearchLanguage.PYTHON, "_simple_statement", SemanticNodeCategory.RETURN_STATEMENT
    )
    mapper.add_manual_override(
        SemanticSearchLanguage.PYTHON,
        "expression_statement",
        SemanticNodeCategory.BINARY_EXPRESSION,
    )
    # Additional Python overrides from analysis
    mapper.add_manual_override(
        SemanticSearchLanguage.PYTHON, "parameter", SemanticNodeCategory.VARIABLE_DECLARATION
    )
    mapper.add_manual_override(
        SemanticSearchLanguage.PYTHON, "argument_list", SemanticNodeCategory.PUNCTUATION
    )
    mapper.add_manual_override(
        SemanticSearchLanguage.PYTHON, "attribute", SemanticNodeCategory.PROPERTY_ACCESS
    )
    loader(("binary_operator", "boolean_operator"), SemanticNodeCategory.OPERATOR)
    loader(("case_clause", "case_pattern"), SemanticNodeCategory.PATTERN_MATCHING)
    return mapper


def _load_javascript_typescript_overrides(mapper: NodeMapper) -> NodeMapper:
    """Load JavaScript/TypeScript-specific manual overrides into the mapper."""
    mapper.add_manual_override(
        SemanticSearchLanguage.JAVASCRIPT, "program", SemanticNodeCategory.NAMESPACE_DEFINITION
    )
    mapper.add_manual_override(
        SemanticSearchLanguage.TYPESCRIPT, "program", SemanticNodeCategory.NAMESPACE_DEFINITION
    )
    mapper.add_manual_override(
        SemanticSearchLanguage.JAVASCRIPT, "arrow_function", SemanticNodeCategory.LAMBDA_EXPRESSION
    )
    mapper.add_manual_override(
        SemanticSearchLanguage.TYPESCRIPT, "arrow_function", SemanticNodeCategory.LAMBDA_EXPRESSION
    )
    mapper.add_manual_override(
        SemanticSearchLanguage.TSX, "arrow_function", SemanticNodeCategory.LAMBDA_EXPRESSION
    )
    mapper.add_manual_override(
        SemanticSearchLanguage.JAVASCRIPT, "class", SemanticNodeCategory.CLASS_DEFINITION
    )
    mapper.add_manual_override(
        SemanticSearchLanguage.TYPESCRIPT, "class", SemanticNodeCategory.CLASS_DEFINITION
    )
    # Additional JS/TS overrides from analysis
    for lang in [SemanticSearchLanguage.JAVASCRIPT, SemanticSearchLanguage.TYPESCRIPT]:
        mapper.add_manual_override(lang, "pattern", SemanticNodeCategory.CONDITIONAL_STATEMENT)
        mapper.add_manual_override(lang, "arguments", SemanticNodeCategory.PUNCTUATION)
        mapper.add_manual_override(lang, "array", SemanticNodeCategory.LITERAL)
        mapper.add_manual_override(
            lang, "array_pattern", SemanticNodeCategory.CONDITIONAL_STATEMENT
        )
        mapper.add_manual_override(lang, "catch_clause", SemanticNodeCategory.TRY_CATCH_STATEMENT)
    # TypeScript-specific type overrides
    mapper.add_manual_override(
        SemanticSearchLanguage.TYPESCRIPT, "accessibility_modifier", SemanticNodeCategory.ANNOTATION
    )
    map_language_nodes_to_category(
        mapper,
        SemanticSearchLanguage.TYPESCRIPT,
        (
            "asserts",
            "asserts_annotation",
            "computed_property_name",
            "constraint",
            "decorator",
            "adding_type_annotation",
            "array_type",
            "as_expression",
            "generic_type",
            "index_signature",
            "intersection_type",
            "literal_type",
            "lookup_type",
            "type",
            "primary_type",
            "mapped_type_clause",
            "object_type",
            "optional_type",
            "parenthesized_type",
            "predefined_type",
            "rest_type",
            "template_literal_type",
            "tuple_type",
            "type",
            "type_alias",
            "type_alias_declaration",
            "type_annotation",
            "type_arguments",
            "type_parameter",
            "type_parameters",
            "type_predicate",
            "type_query",
            "union_type",
        ),
        SemanticNodeCategory.TYPE_DEFINITION,
    )
    return mapper


def _load_rust_overrides(mapper: NodeMapper) -> NodeMapper:
    """Load Rust-specific manual overrides into the mapper."""
    map_language_nodes_to_category(
        mapper,
        SemanticSearchLanguage.RUST,
        ("impl_item", "trait_item"),
        SemanticNodeCategory.TRAIT_DEFINITION,
    )
    mapper.add_manual_override(
        SemanticSearchLanguage.RUST, "struct_item", SemanticNodeCategory.CLASS_DEFINITION
    )
    mapper.add_manual_override(SemanticSearchLanguage.RUST, "literal", SemanticNodeCategory.LITERAL)
    map_language_nodes_to_category(
        mapper,
        SemanticSearchLanguage.RUST,
        (
            "_pattern",
            "_type",
            "array_type",
            "attribute_item",
            "base_field_initializer",
            "block_comment",
            "captured_pattern",
            "closure_parameters",
            "generic_type",
            "lifetime",
            "type_arguments",
            "type_parameters",
            "where_clause",
            "bounded_type",
            "higher_ranked_trait_bound",
            "reference_type",
            "pointer_type",
            "tuple_type",
            "unit_type",
            "never_type",
            "slice_type",
            "function_type",
            "trait_bounds",
        ),
        SemanticNodeCategory.TYPE_DEFINITION,
    )
    mapper.add_manual_override(
        SemanticSearchLanguage.RUST, "arguments", SemanticNodeCategory.PUNCTUATION
    )
    mapper.add_manual_override(
        SemanticSearchLanguage.RUST, "block", SemanticNodeCategory.CONDITIONAL_STATEMENT
    )
    return mapper


def _load_go_overrides(mapper: NodeMapper) -> NodeMapper:
    """Load Go-specific manual overrides into the mapper."""
    mapper.add_manual_override(
        SemanticSearchLanguage.GO, "type_declaration", SemanticNodeCategory.TYPE_DEFINITION
    )
    mapper.add_manual_override(
        SemanticSearchLanguage.GO, "package_clause", SemanticNodeCategory.NAMESPACE_DEFINITION
    )
    mapper.add_manual_override(
        SemanticSearchLanguage.GO, "const_declaration", SemanticNodeCategory.VARIABLE_DECLARATION
    )
    map_language_nodes_to_category(
        mapper,
        SemanticSearchLanguage.GO,
        (
            "_simple_type",
            "_type",
            "array_type",
            "channel_type",
            "function_type",
            "interface_type",
            "map_type",
            "pointer_type",
            "qualified_type",
            "slice_type",
            "struct_type",
            "type_assertion",
            "type_constraint",
            "type_conversion",
            "type_declaration",
            "type_element",
            "type_identity",
            "type_parameter",
            "type_spec",
            "type_switch",
        ),
        SemanticNodeCategory.TYPE_DEFINITION,
    )
    mapper.add_manual_override(
        SemanticSearchLanguage.GO, "argument_list", SemanticNodeCategory.PUNCTUATION
    )
    mapper.add_manual_override(
        SemanticSearchLanguage.GO, "block", SemanticNodeCategory.CONDITIONAL_STATEMENT
    )
    map_language_nodes_to_category(
        mapper,
        SemanticSearchLanguage.GO,
        ("communication_case", "default_case", "expression_case"),
        SemanticNodeCategory.CONDITIONAL_STATEMENT,
    )
    mapper.add_manual_override(
        SemanticSearchLanguage.GO, "const_spec", SemanticNodeCategory.VARIABLE_DECLARATION
    )
    return mapper


def _load_html_overrides(mapper: NodeMapper) -> NodeMapper:
    """Load HTML-specific manual overrides into the mapper."""
    mapper.add_manual_override(
        SemanticSearchLanguage.HTML, "element", SemanticNodeCategory.CLASS_DEFINITION
    )
    mapper.add_manual_override(
        SemanticSearchLanguage.HTML, "attribute", SemanticNodeCategory.VARIABLE_DECLARATION
    )
    mapper.add_manual_override(
        SemanticSearchLanguage.HTML, "document", SemanticNodeCategory.NAMESPACE_DEFINITION
    )
    # Additional HTML overrides from analysis
    map_language_nodes_to_category(
        mapper,
        SemanticSearchLanguage.HTML,
        ("end_tag", "erroneous_end_tag"),
        SemanticNodeCategory.PUNCTUATION,
    )
    mapper.add_manual_override(
        SemanticSearchLanguage.HTML, "script_element", SemanticNodeCategory.FUNCTION_DEFINITION
    )
    mapper.add_manual_override(
        SemanticSearchLanguage.HTML, "doctype", SemanticNodeCategory.ANNOTATION
    )

    # HTML/Markup overrides
    map_language_nodes_to_category(
        mapper,
        SemanticSearchLanguage.HTML,
        (
            "self_closing_tag",
            "start_tag",
            "style_element",
            "end_tag",
            "script_element",
            "erroneous_end_tag",
        ),
        SemanticNodeCategory.MARKUP_ELEMENT,
    )
    map_language_nodes_to_category(
        mapper,
        SemanticSearchLanguage.HTML,
        ("attribute_value", "quoted_attribute_value"),
        SemanticNodeCategory.LITERAL,
    )
    mapper.add_manual_override(
        SemanticSearchLanguage.HTML, "attribute_name", SemanticNodeCategory.PROPERTY_ACCESS
    )
    mapper.add_manual_override(
        SemanticSearchLanguage.HTML, "doctype", SemanticNodeCategory.PREPROCESSOR
    )
    return mapper


def _load_config_overrides(mapper: NodeMapper) -> NodeMapper:
    """Load configuration language manual overrides into the mapper."""
    # JSON-specific overrides
    mapper.add_manual_override(
        SemanticSearchLanguage.JSON, "object", SemanticNodeCategory.CLASS_DEFINITION
    )
    mapper.add_manual_override(SemanticSearchLanguage.JSON, "array", SemanticNodeCategory.LITERAL)
    mapper.add_manual_override(
        SemanticSearchLanguage.JSON, "pair", SemanticNodeCategory.VARIABLE_DECLARATION
    )

    # YAML-specific overrides
    map_language_nodes_to_category(
        mapper,
        SemanticSearchLanguage.YAML,
        ("bool", "float", "int", "null", "scalar"),
        SemanticNodeCategory.LITERAL,
    )

    # CSS-specific overrides -- is it a config language? Probably not, but close enough
    map_language_nodes_to_category(
        mapper,
        SemanticSearchLanguage.CSS,
        ("attribute_selector", "adjacent_sibling_selector", "at_rule"),
        SemanticNodeCategory.CONDITIONAL_STATEMENT,
    )

    mapper.add_manual_override(
        SemanticSearchLanguage.CSS, "arguments", SemanticNodeCategory.PUNCTUATION
    )
    mapper.add_manual_override(
        SemanticSearchLanguage.CSS, "attribute_name", SemanticNodeCategory.PROPERTY_ACCESS
    )
    return mapper


def _load_default_overrides(mapper: NodeMapper) -> None:
    """Load default manual overrides into the mapper."""
    # Python-specific overrides
    mapper = _load_python_overrides(mapper)
    # JavaScript/TypeScript-specific overrides
    mapper = _load_javascript_typescript_overrides(mapper)
    # Rust-specific overrides
    mapper = _load_rust_overrides(mapper)
    # Go-specific overrides
    mapper = _load_go_overrides(mapper)

    # HTML-specific overrides
    mapper = _load_html_overrides(mapper)

    # Configuration languages overrides for JSON/YAML and CSS
    mapper = _load_config_overrides(mapper)

    # Java/C# type system overrides
    for lang in (SemanticSearchLanguage.JAVA, SemanticSearchLanguage.C_SHARP):
        map_language_nodes_to_category(
            mapper,
            lang,
            (
                "_type",
                "annotated_type",
                "_simple_type",
                "_unannotated_type",
                "type",
                "type_identifier",
                "type_specifier",
            ),
            SemanticNodeCategory.TYPE_DEFINITION,
        )

    # C/C++ type system overrides
    for lang in (SemanticSearchLanguage.C_LANG, SemanticSearchLanguage.C_PLUS_PLUS):
        map_language_nodes_to_category(
            mapper,
            lang,
            (
                "_abstract_declarator",
                "_declarator",
                "_field_declarator",
                "_type_declarator",
                "_type_specifier",
            ),
            SemanticNodeCategory.TYPE_DEFINITION,
        )
