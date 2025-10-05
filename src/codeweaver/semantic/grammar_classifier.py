# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Grammar-based semantic node classification using inherent tree-sitter structure.

This module provides primary classification by leveraging the explicit semantic
relationships encoded in node_types.json files:
- Subtypes → Abstract categories
- Fields → Structural relationships and semantic hints
- Children → Positional constraints
- Extra → Syntactic elements
"""

from __future__ import annotations

from functools import cache
from typing import Literal, NamedTuple

from codeweaver.language import SemanticSearchLanguage
from codeweaver.semantic.categories import SemanticNodeCategory, SemanticTier
from codeweaver.semantic.grammar_types import NodeSemanticInfo
from codeweaver.semantic.node_type_parser import NodeTypeParser


class GrammarClassificationResult(NamedTuple):
    """Result of grammar-based classification."""

    category: SemanticNodeCategory
    tier: SemanticTier
    confidence: float
    classification_method: Literal["abstract_type", "field_inference", "children", "extra"]
    evidence: str  # Human-readable explanation


class GrammarBasedClassifier:
    """Primary classifier using grammar structure from node_types.json."""

    def __init__(self, parser: NodeTypeParser | None = None) -> None:
        """Initialize grammar-based classifier.

        Args:
            parser: NodeTypeParser instance. If None, creates a new one.
        """
        self.parser = parser or NodeTypeParser()

        # Pre-computed mappings for fast lookup
        self._abstract_to_category = self._build_abstract_category_map()
        self._field_patterns = self.parser.field_semantic_patterns

    def classify_node(
        self, node_type: str, language: SemanticSearchLanguage | str
    ) -> GrammarClassificationResult | None:
        """Classify a node using grammar structure.

        Classification pipeline:
        1. Check if node belongs to abstract category (via subtypes)
        2. Infer from field names (strongest semantic signal)
        3. Analyze children constraints
        4. Handle extra nodes (syntactic elements)

        Args:
            node_type: The node type name (e.g., "function_definition")
            language: The programming language

        Returns:
            Classification result with high confidence (>0.8), or None if
            grammar-based classification not possible.
        """
        if not isinstance(language, SemanticSearchLanguage):
            language = SemanticSearchLanguage.from_string(language)

        # Get semantic info from parser
        semantic_info = self.parser.get_node_semantic_info(node_type, language)
        if not semantic_info:
            return None  # Node not found in grammar

        # Pipeline: Try each method in order of confidence

        # Method 1: Abstract type classification (highest confidence)
        if result := self._classify_from_abstract_type(semantic_info):
            return result

        # Method 2: Field-based inference (very high confidence)
        if result := self._classify_from_fields(semantic_info):
            return result

        # Method 3: Children constraints (moderate confidence)
        if result := self._classify_from_children(semantic_info):
            return result

        # Method 4: Extra nodes (syntactic) -- often documentation/comments
        if semantic_info.is_extra:
            return GrammarClassificationResult(
                category=SemanticNodeCategory.DOCUMENTATION_STRUCTURED,
                tier=SemanticTier.BEHAVIORAL_CONTRACTS,
                confidence=0.95,
                classification_method="extra",
                evidence="Node marked as 'extra' in grammar (can appear anywhere)",
            )

        return None  # Could not classify using grammar

    def _classify_from_abstract_type(
        self, info: NodeSemanticInfo
    ) -> GrammarClassificationResult | None:
        """Classify based on abstract category (supertype)."""
        if not info.abstract_category:
            return None

        # Map abstract type to semantic category
        category = self._abstract_to_category.get(info.abstract_category)
        if not category:
            return None

        tier = SemanticTier.from_category(category)

        return GrammarClassificationResult(
            category=category,
            tier=tier,
            confidence=0.90,  # High confidence from explicit grammar structure
            classification_method="abstract_type",
            evidence=f"Subtype of '{info.abstract_category}' abstract category",
        )

    def _classify_from_fields(self, info: NodeSemanticInfo) -> GrammarClassificationResult | None:
        """Classify based on field names and patterns."""
        if not info.has_fields:
            return None

        # Use inferred category from NodeSemanticInfo
        inferred = info.infer_semantic_category()
        if inferred == "unknown":
            return None

        # Map inferred category to SemanticNodeCategory
        category_map = {
            "callable": SemanticNodeCategory.DEFINITION_CALLABLE,
            "type_def": SemanticNodeCategory.DEFINITION_TYPE,
            "control_flow": SemanticNodeCategory.FLOW_BRANCHING,
            "operation": SemanticNodeCategory.OPERATION_COMPUTATION,
            "pattern_match": SemanticNodeCategory.FLOW_BRANCHING,
        }

        category = category_map.get(inferred)
        if not category:
            return None

        tier = SemanticTier.from_category(category)

        # Build evidence from field names
        field_names = [f.name for f in info.fields]
        evidence = f"Fields {field_names} indicate {inferred} pattern"

        return GrammarClassificationResult(
            category=category,
            tier=tier,
            confidence=0.85,  # Very high confidence from field patterns
            classification_method="field_inference",
            evidence=evidence,
        )

    def _classify_from_children(self, info: NodeSemanticInfo) -> GrammarClassificationResult | None:
        """Classify based on children constraints."""
        if not info.has_children_constraints:
            return None

        # Heuristic: If has both fields and children, likely a structural definition
        if info.has_fields:
            # Structural nodes with complex children
            return GrammarClassificationResult(
                category=SemanticNodeCategory.FLOW_BRANCHING,
                tier=SemanticTier.CONTROL_FLOW_LOGIC,
                confidence=0.70,  # Moderate confidence
                classification_method="children",
                evidence="Has fields and children constraints (structural pattern)",
            )

        # Just children, likely an expression or statement container
        return GrammarClassificationResult(
            category=SemanticNodeCategory.REFERENCE_IDENTIFIER,
            tier=SemanticTier.SYNTAX_REFERENCES,
            confidence=0.65,  # Lower confidence
            classification_method="children",
            evidence="Has children constraints only (composite structure)",
        )

    def _build_abstract_category_map(self) -> dict[str, SemanticNodeCategory]:
        """Build mapping from abstract type names to semantic categories.

        Based on empirical analysis:
        - expression → OPERATION_COMPUTATION
        - statement → CONTROL_FLOW_SEQUENTIAL
        - type → DEFINITION_TYPE
        - declaration → DEFINITION_DATA
        - pattern → PATTERN_MATCH
        - literal → SYNTAX_LITERAL
        """
        return {
            # Universal abstract types (from grammar analysis)
            "expression": SemanticNodeCategory.OPERATION_COMPUTATION,
            "primary_expression": SemanticNodeCategory.OPERATION_COMPUTATION,
            "statement": SemanticNodeCategory.FLOW_BRANCHING,
            "type": SemanticNodeCategory.DEFINITION_TYPE,
            "declaration": SemanticNodeCategory.DEFINITION_DATA,
            "pattern": SemanticNodeCategory.FLOW_BRANCHING,
            "literal": SemanticNodeCategory.LITERAL_VALUE,
            # C-family specifics
            "declarator": SemanticNodeCategory.DEFINITION_DATA,
            "abstract_declarator": SemanticNodeCategory.DEFINITION_DATA,
            "field_declarator": SemanticNodeCategory.DEFINITION_DATA,
            "type_declarator": SemanticNodeCategory.DEFINITION_DATA,
            "type_specifier": SemanticNodeCategory.DEFINITION_TYPE,
            # Language-specific patterns
            # simple_statement is for python and go
            # for python, it is assert/break/continue/del ... but ALSO import and type_alias
            # for go, it's more like REFERENCE_IDENTIFIER: assignment, declaration, etc.
            "simple_statement": SemanticNodeCategory.FLOW_CONTROL,
            "simple_type": SemanticNodeCategory.DEFINITION_TYPE,
            "compound_statement": SemanticNodeCategory.FLOW_BRANCHING,
            # Additional categories from 21-language analysis
            "parameter": SemanticNodeCategory.DEFINITION_DATA,
            "argument": SemanticNodeCategory.ANNOTATION_METADATA,
            "identifier": SemanticNodeCategory.REFERENCE_IDENTIFIER,
        }

    @cache
    def get_abstract_category_for_language(
        self, abstract_type: str, language: SemanticSearchLanguage
    ) -> SemanticNodeCategory | None:
        """Get semantic category for an abstract type in a specific language.

        Args:
            abstract_type: Abstract type name (e.g., "expression", "statement")
            language: Programming language

        Returns:
            Semantic category if mapping exists, None otherwise
        """
        # Check if this abstract type exists for this language
        lang_map = self.parser.abstract_type_map.get(abstract_type, {})
        if language.value not in lang_map:
            return None

        return self._abstract_to_category.get(abstract_type)
