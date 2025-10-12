# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Grammar-based semantic node classification using inherent tree-sitter structure.

This module provides primary classification by leveraging the explicit semantic
relationships encoded in node_types.json files:
- Categories → Abstract groupings (was: Subtypes/Abstract types)
- DirectConnections → Structural relationships with semantic Roles (was: Fields)
- PositionalConnections → Ordered relationships without Roles (was: Children)
- can_be_anywhere → Syntactic elements that can appear anywhere (was: Extra)
"""

from __future__ import annotations

from typing import TYPE_CHECKING, NamedTuple

from codeweaver._common import BaseEnum
from codeweaver.language import SemanticSearchLanguage
from codeweaver.semantic.categories import ImportanceRank, SemanticClass


if TYPE_CHECKING:
    from codeweaver.semantic.node_type_parser import (
        CategoryName,
        CompositeThing,
        NodeTypeParser,
        ThingName,
        Token,
    )


class ClassificationMethod(BaseEnum):
    """Enumeration of classification methods."""

    CATEGORY = "category"
    CONNECTION_INFERENCE = "connection_inference"
    POSITIONAL = "positional"
    ANYWHERE = "anywhere"


class GrammarClassificationResult(NamedTuple):
    """Result of grammar-based classification.

    Attributes:
        category: Semantic category assigned to the node
        tier: Semantic tier (importance level)
        confidence: Confidence score (0.0-1.0)
        classification_method: Method used for classification
        evidence: Human-readable explanation of classification reasoning
    """

    category: SemanticClass
    tier: ImportanceRank
    confidence: float
    classification_method: ClassificationMethod
    evidence: str  # Human-readable explanation of classification reasoning


class GrammarBasedClassifier:
    """Primary classifier using grammar structure from node_types.json.

    Uses the new intuitive API: Category (abstract types), Thing (concrete nodes),
    DirectConnection (fields with Roles), PositionalConnection (ordered children).
    """

    def __init__(self, parser: NodeTypeParser | None = None) -> None:
        """Initialize grammar-based classifier.

        Args:
            parser: NodeTypeParser instance. If None, creates a new one.
        """
        from codeweaver.semantic.node_type_parser import NodeTypeParser

        self.parser = parser or NodeTypeParser()

        # Build Category name → SemanticClass mapping
        self._category_map = self._build_category_to_semantic_map()

    def classify_thing(
        self, thing_name: ThingName, language: SemanticSearchLanguage | str
    ) -> GrammarClassificationResult | None:
        """Classify a thing using grammar structure.

        Classification pipeline (highest to lowest confidence):
        1. can_be_anywhere flag (0.99): All Comments with two exceptions (was: extra)
        2. Category membership (0.90): Explicit grammar Categories (was: abstract types)
        3. DirectConnection Roles (0.85): Semantic Role patterns (was: field inference)
        4. PositionalConnections (0.65-0.70): Structural patterns (was: children)

        Args:
            thing_name: The Thing name (e.g., "function_definition")
            language: The programming language

        Returns:
            Classification result with confidence, or None if classification not possible
        """
        from codeweaver.semantic.node_type_parser import get_things

        if not isinstance(language, SemanticSearchLanguage):
            language = SemanticSearchLanguage.from_string(language)

        # Get Thing from registry
        things = get_things(languages=[language])
        thing = next((t for t in things if t.name == thing_name), None)
        if thing is None:
            return None  # Thing not found for language
        if not isinstance(thing, CompositeThing | Token):
            return None  # Unsupported Thing type

        # Classification pipeline (highest to lowest confidence)
        # Method 1: can_be_anywhere flag (confidence: 0.95)
        if thing.can_be_anywhere and "comment" in str(thing_name).lower():
            # Special case: comments are always DOCUMENTATION_STRUCTURED
            return GrammarClassificationResult(
                category=SemanticClass.DOCUMENTATION_STRUCTURED,
                tier=ImportanceRank.BEHAVIORAL_CONTRACTS,
                confidence=0.99,
                classification_method=ClassificationMethod.ANYWHERE,
                evidence="Thing marked as can_be_anywhere and name contains 'comment'",
            )
        if thing.can_be_anywhere:
            if str(thing_name).lower() == "line_continuation":
                # Special case: line_continuation is SYNTAX_PUNCTUATION
                return GrammarClassificationResult(
                    category=SemanticClass.SYNTAX_PUNCTUATION,
                    tier=ImportanceRank.SYNTAX_REFERENCES,
                    confidence=0.99,
                    classification_method=ClassificationMethod.ANYWHERE,
                    evidence="Thing marked as can_be_anywhere and name is 'line_continuation'",
                )
            if str(thing_name).lower() == "text_interpolation":
                # Special case: text_interpolation is SYNTAX_IDENTIFIER
                return GrammarClassificationResult(
                    category=SemanticClass.SYNTAX_IDENTIFIER,
                    tier=ImportanceRank.SYNTAX_REFERENCES,
                    confidence=0.99,
                    classification_method=ClassificationMethod.ANYWHERE,
                    evidence="Through deduction, this is PHP's 'text_interpolation' thing.",
                )

        # Method 2: Category membership (confidence: 0.90)
        if result := self._classify_from_category(thing):
            return result

        # Method 3: DirectConnection Role inference (confidence: 0.85)
        # Only applicable to CompositeThings
        if isinstance(thing, CompositeThing) and (
            result := self._classify_from_direct_connections(thing)
        ):
            return result

        # Method 4: PositionalConnection patterns (confidence: 0.65-0.70)
        # Only applicable to CompositeThings
        if isinstance(thing, CompositeThing) and (
            result := self._classify_from_positional_connections(thing)
        ):
            return result

        return None  # Could not classify using grammar

    def _build_category_to_semantic_map(self) -> dict[CategoryName, SemanticClass]:
        """Build mapping from grammar Category names to SemanticClass enum values.

        Based on empirical analysis of 25 languages, ~110 unique Categories.

        Returns:
            Mapping from CategoryName (from node_types.json) to SemanticClass enum
        """
        from codeweaver.semantic.node_type_parser import CategoryName

        category_map = {
            # Universal Categories (appear in most languages)
            CategoryName("expression"): SemanticClass.OPERATION_OPERATOR,
            CategoryName("primary_expression"): SemanticClass.OPERATION_OPERATOR,
            CategoryName("statement"): SemanticClass.FLOW_BRANCHING,
            CategoryName("type"): SemanticClass.DEFINITION_TYPE,
            CategoryName("declaration"): SemanticClass.DEFINITION_DATA,
            CategoryName("pattern"): SemanticClass.FLOW_BRANCHING,
            CategoryName("literal"): SemanticClass.SYNTAX_LITERAL,
            # C-family Categories
            CategoryName("declarator"): SemanticClass.DEFINITION_DATA,
            CategoryName("abstract_declarator"): SemanticClass.DEFINITION_DATA,
            CategoryName("field_declarator"): SemanticClass.DEFINITION_DATA,
            CategoryName("type_declarator"): SemanticClass.DEFINITION_DATA,
            CategoryName("type_specifier"): SemanticClass.DEFINITION_TYPE,
            # Language-specific Categories
            CategoryName("simple_statement"): SemanticClass.FLOW_CONTROL,
            CategoryName("simple_type"): SemanticClass.DEFINITION_TYPE,
            CategoryName("compound_statement"): SemanticClass.FLOW_BRANCHING,
            # Additional Categories from multi-language analysis
            CategoryName("parameter"): SemanticClass.DEFINITION_DATA,
            CategoryName("argument"): SemanticClass.SYNTAX_ANNOTATION,
            CategoryName("identifier"): SemanticClass.SYNTAX_IDENTIFIER,
        }
        # add keys with underscores in front of them
        return category_map | {CategoryName(f"_{k!s}"): v for k, v in category_map.items()}  # type: ignore

    def _classify_from_category(
        self, thing: CompositeThing | Token
    ) -> GrammarClassificationResult | None:
        """Classify a Thing based on its Category membership.

        Highest confidence classification method (0.90) using explicit grammar Categories.

        Args:
            thing: The Thing (CompositeThing or Token) to classify

        Returns:
            Classification result with high confidence, or None if no Category match
        """
        if not thing.categories:
            return None

        # For Things with single Category, use it directly
        if thing.is_single_category:
            return self._classify_from_primary_category(thing)
        # For multi-category Things (13.5% of Things), try all Categories
        for category in thing.categories:
            if semantic_category := self._category_map.get(category.name):
                tier = ImportanceRank.from_category(semantic_category)

                category_names = sorted(cat.name for cat in thing.categories)
                return GrammarClassificationResult(
                    category=semantic_category,
                    tier=tier,
                    confidence=0.85,  # Lower confidence for multi-category
                    classification_method=ClassificationMethod.CATEGORY,
                    evidence=f"Member of multiple Categories: {category_names}",
                )

        return None

    def _classify_from_primary_category(
        self, thing: CompositeThing | Token
    ) -> GrammarClassificationResult | None:
        """Classify a Thing based on its primary Category membership."""
        primary_category = thing.primary_category
        if primary_category is None:
            return None  # Shouldn't happen but be defensive

        semantic_category = self._category_map.get(primary_category.name)
        if not semantic_category:
            return None

        tier = ImportanceRank.from_category(semantic_category)

        return GrammarClassificationResult(
            category=semantic_category,
            tier=tier,
            confidence=0.90,
            classification_method=ClassificationMethod.CATEGORY,
            evidence=f"Member of '{primary_category.name}' Category",
        )

    def _classify_from_direct_connections(
        self, thing: CompositeThing
    ) -> GrammarClassificationResult | None:
        """Classify based on DirectConnection Role patterns.

        High confidence classification method (0.85) using semantic Role analysis.

        Args:
            thing: CompositeThing to analyze (only CompositeThings have DirectConnections)

        Returns:
            Classification with high confidence, or None if no pattern match
        """
        if not thing.direct_connections:
            return None

        # Extract Roles from DirectConnections
        roles = frozenset(str(conn.role) for conn in thing.direct_connections)

        # Pattern matching on Role combinations
        category: SemanticClass | None = None

        # Callable definitions: have 'body' and 'name' Roles
        if {"body", "name"}.issubset(roles):
            category = SemanticClass.DEFINITION_CALLABLE

        # Branching control flow: have 'condition' Role
        elif {"condition", "consequence"}.issubset(roles) or {"condition", "body"}.issubset(roles):
            category = SemanticClass.FLOW_BRANCHING

        # Binary operations: have 'left', 'right', 'operator' Roles
        elif {"left", "right", "operator"}.issubset(roles):
            category = SemanticClass.OPERATION_OPERATOR

        # Type definitions: have 'name' and 'body' but also 'superclass' or 'interfaces'
        elif {"name", "body"}.issubset(roles) and (
            "superclass" in roles or "interfaces" in roles or "base" in roles
        ):
            category = SemanticClass.DEFINITION_TYPE

        # Variable/data definitions: have 'type' and 'declarator' or 'value'
        elif {"type"}.issubset(roles) and (
            "declarator" in roles or "value" in roles or "default" in roles
        ):
            category = SemanticClass.DEFINITION_DATA

        if category is None:
            return None

        tier = ImportanceRank.from_category(category)
        role_names = sorted(roles)

        return GrammarClassificationResult(
            category=category,
            tier=tier,
            confidence=0.85,
            classification_method=ClassificationMethod.CONNECTION_INFERENCE,
            evidence=f"DirectConnection Roles: {role_names}",
        )

    def _classify_from_positional_connections(
        self, thing: CompositeThing
    ) -> GrammarClassificationResult | None:
        """Classify based on PositionalConnection patterns.

        Moderate confidence classification method (0.65-0.70) using structural patterns.

        Args:
            thing: CompositeThing to analyze

        Returns:
            Classification with moderate confidence, or None if no pattern match
        """
        if not thing.positional_connections:
            return None

        # Heuristic: CompositeThings with both DirectConnections and
        # PositionalConnections are likely structural control flow nodes
        if thing.direct_connections:
            return GrammarClassificationResult(
                category=SemanticClass.FLOW_BRANCHING,
                tier=ImportanceRank.CONTROL_FLOW_LOGIC,
                confidence=0.70,
                classification_method=ClassificationMethod.POSITIONAL,
                evidence="Has both DirectConnections and PositionalConnections (structural pattern)",
            )

        # Just PositionalConnections, likely a container/expression/list node
        return GrammarClassificationResult(
            category=SemanticClass.SYNTAX_IDENTIFIER,
            tier=ImportanceRank.SYNTAX_REFERENCES,
            confidence=0.65,
            classification_method=ClassificationMethod.POSITIONAL,
            evidence="Has PositionalConnections only (composite structure)",
        )
