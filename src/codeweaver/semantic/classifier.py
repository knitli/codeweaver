# sourcery skip: lambdas-should-be-short
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

from collections.abc import Callable, Sequence
from types import MappingProxyType
from typing import TYPE_CHECKING, Annotated, NamedTuple, cast

from ast_grep_py import SgNode
from pydantic import Field, NonNegativeFloat, NonNegativeInt, computed_field
from typing_extensions import TypeIs

from codeweaver.common.utils.utils import rpartial
from codeweaver.core.language import SemanticSearchLanguage
from codeweaver.core.types.aliases import CategoryName, CategoryNameT, ThingNameT
from codeweaver.core.types.enum import BaseEnum
from codeweaver.semantic.classifications import ImportanceRank, SemanticClass


if TYPE_CHECKING:
    from codeweaver.semantic.ast_grep import AstThing
    from codeweaver.semantic.grammar import CompositeThing, Token


CONFIDENCE_THRESHOLD = 0.80


def is_token(thing: CompositeThing | Token) -> TypeIs[Token]:
    """Type guard to check if a Thing is a Token."""
    return thing.is_token


def is_composite_thing(thing: CompositeThing | Token) -> TypeIs[CompositeThing]:
    """Type guard to check if a Thing is a CompositeThing."""
    return thing.is_composite


class ClassificationMethod(BaseEnum):
    """Enumeration of classification methods."""

    CATEGORY = "category"
    CONNECTION_INFERENCE = "connection_inference"
    POSITIONAL = "positional"
    THING_INFERENCE = "thing_inference"
    TOKEN_PURPOSE = "token_purpose"  # noqa: S105  # definitely not a password
    ANYWHERE = "anywhere"
    SPECIFIC_THING = "specific_thing"


class EvidenceKind(int, BaseEnum):
    """Kinds of evidence used for classifying Things.

    An int-enum for easy comparison of evidence strength. Higher numbers indicate stronger evidence. The confidence score is estimated based on the combined strength of the evidence kinds used.
    """

    HEURISTIC = 10
    """Evidence based on a heuristic rule or pattern, e.g. that a Thing has both direct and positional connections."""
    SIMPLE_NAME_PATTERN = 20
    """Evidence based on a pattern in the Thing's name, e.g. that it contains 'comment'."""
    LANGUAGE = 30
    """Evidence based on the programming language context, e.g. that a specific thing is only in one language, or that the language has rules that make certain things more likely."""
    CONNECTIONS = 65
    """Evidence based on the CompositeThing's connections."""
    CATEGORIES = 80
    """Evidence based on the grammar categories the Thing belongs to."""
    ROLES = 85
    """Evidence based on the semantic roles of the Thing's connections."""
    SPECIFIC_THING = 90
    """Evidence based on a specific instance of a Thing. This is based on empirical knowledge of specific Things in specific languages."""
    PURPOSE = 95
    """Evidence based on a Token's purpose classification. CodeWeaver's token purpose classification is robust and high-confidence.

    It relies on extensive regex patterns custom fit to each language //LINK - /src/codeweaver/semantic/_constants.py , so this is a strong form of evidence."""

    @classmethod
    def confidence(cls, kinds: Sequence[EvidenceKind], adjustment: NonNegativeInt = 0) -> float:
        """Estimate confidence score based on the kinds of evidence used.

        Args:
            kinds: List of EvidenceKind values used in classification.

        Returns:
            Confidence score from 0.0 to 1.0
        """
        if not kinds:
            return min(max(adjustment / 100.0, 0.0), 1.0) if adjustment else 0.0
        # We get total adjusted strength by summing the evidence kinds and adding any adjustment
        # Note: This can exceed 100, so we clamp the final confidence to 1.0
        total_strength = sum(kinds) + adjustment
        return min(max(total_strength / 100.0, 0.0), 1.0)

    @property
    def statement(self) -> str:
        """Human-readable statement of the evidence kind."""
        return {
            EvidenceKind.HEURISTIC: "Matched a heuristic rule or pattern",
            EvidenceKind.SIMPLE_NAME_PATTERN: "Inferred from the Thing's name",
            EvidenceKind.LANGUAGE: "Inferred from the programming language context",
            EvidenceKind.CONNECTIONS: "Inferred from the Thing's connections",
            EvidenceKind.ROLES: "Inferred from the semantic roles of the Thing's connections",
            EvidenceKind.CATEGORIES: "Inferred from the grammar categories the Thing belongs to",
            EvidenceKind.SPECIFIC_THING: "Based on empirical knowledge of this specific Thing",
            EvidenceKind.PURPOSE: "Based on the Token's purpose classification",
        }[self]

    @classmethod
    def evidence_summary(cls, kinds: Sequence[EvidenceKind]) -> str:
        """Generate a human-readable summary of the evidence kinds used.

        Args:
            kinds: List of EvidenceKind values used in classification.

        Returns:
            Human-readable summary of the evidence kinds.
        """
        if not kinds:
            return "No evidence available for classification."

        summaries = (
            f"- {kind.as_title}: {kind.statement} ({kind.value})"
            for kind in sorted(kinds, reverse=True)
        )
        return "\n".join(summaries)


class GrammarClassificationResult(NamedTuple):
    """Result of grammar-based classification.

    Attributes:
        classification: Semantic classification assigned to the thing
        rank: Semantic rank (importance level)
        classification_method: Method used for classification
        evidence: Kinds of evidence used for classification
        evidence_summary: Human-readable explanation of classification reasoning
        confidence: Confidence score (0.0-1.0)
    """

    classification: Annotated[
        SemanticClass, Field(description="Semantic classification assigned to the node")
    ]
    rank: Annotated[
        ImportanceRank,
        Field(
            description="Importance rank (1-5), lower is more important",
            default_factory=lambda data: ImportanceRank.from_classification(data["classification"]),
        ),
    ]
    classification_method: ClassificationMethod
    evidence: Annotated[
        tuple[EvidenceKind, ...],
        Field(description="Kinds of evidence used for classification", default_factory=tuple),
    ]
    adjustment: Annotated[
        int, Field(description="Manual adjustment to confidence. Any integer.")
    ] = 0

    alternate_classifications: (
        Annotated[
            dict[SemanticClass, tuple[EvidenceKind, ...]],
            Field(
                description="Alternate classifications for the node. Only used when there are multiple classifications and none above the confidence threshold."
            ),
        ]
        | None
    ) = None

    assessment_comment: Annotated[
        str | None,
        Field(
            description="Optional human-readable comment regarding the classification assessment."
        ),
    ] = None

    differentiator: Annotated[
        Callable[[AstThing[SgNode]], SemanticClass | None] | None,
        Field(
            description="Optional function to differentiate between alternate classifications based on AST node context. The function receives an AstThing and returns a SemanticClass or None."
        ),
    ] = None

    @computed_field(
        description="Confidence score (0.0-1.0) computed from evidence kinds and adjustment",
        repr=True,
    )
    @property
    def confidence(self) -> NonNegativeFloat:
        """Confidence score (0.0-1.0) computed from evidence kinds."""
        return EvidenceKind.confidence(self.evidence, self.adjustment or 0)

    @computed_field(description="Whether the confidence level is above the threshold", repr=True)
    def is_confident(self) -> bool:
        """Whether the confidence level is above the threshold."""
        return self.confidence >= CONFIDENCE_THRESHOLD

    @computed_field(description="Human-readable summary of the evidence kinds used", repr=False)
    def evidence_summary(self) -> str:
        """Human-readable summary of the evidence kinds used."""
        return EvidenceKind.evidence_summary(self.evidence)

    @staticmethod
    def _adjust_for_disparity(
        results: Sequence[GrammarClassificationResult],
        confident_result: GrammarClassificationResult,
    ) -> int:
        """Adjust confidence based on rank discrepancy.

        Args:
            results: List of GrammarClassificationResult instances to analyze.
            confident_result: The result with the highest confidence.

        Returns:
            Adjustment value to be added to confidence calculation.
        """
        if not results:
            return 0
        if all(result.rank == confident_result.rank for result in results):
            return 10  # all the same rank, boost confidence
        # more granular comparison using classification simple_rank
        discrepancy = int(
            sum(
                abs(result.classification.simple_rank - confident_result.classification.simple_rank)
                for result in results
            )
            / len(results)
        )
        if discrepancy >= 5:
            return -(
                5 * discrepancy - 5 if discrepancy > 5 else 5
            )  # large discrepancy, reduce confidence proportionally
        return 0

    @classmethod
    def from_results(
        cls, results: Sequence[GrammarClassificationResult]
    ) -> GrammarClassificationResult | None:
        """Combine multiple classification results into a single result.

        Args:
            results: List of GrammarClassificationResult instances to combine.

        Returns:
            Combined GrammarClassificationResult with highest confidence, or None if no results.
        """
        if not results:
            return None
        # Choose the result with the highest confidence
        max_confidence_result = max(results, key=lambda r: r.confidence)
        if any(
            result.classification
            for result in results
            if result.classification == max_confidence_result.classification
            and result != max_confidence_result
        ):
            results = [
                result
                for result in results
                if result.classification == max_confidence_result.classification
            ]
            evidence: tuple[EvidenceKind, ...] = tuple({
                evidence
                for result in results
                for evidence in result.evidence
                if result.classification == max_confidence_result.classification
            })
            adjustment = 0
            # we adjust confidence based on the disparity of classification simple_ranks -- wide disparity means less confidence
            # we first compare true ranks, then the classification's simple_rank (a 1 to n for each classification)
            adjustment += cls._adjust_for_disparity(results, max_confidence_result)
            return max_confidence_result._replace(
                evidence=evidence,
                adjustment=adjustment,
                alternate_classifications={
                    result.classification: result.evidence
                    for result in results
                    if result.classification != max_confidence_result.classification
                },
            )
        if len([result for result in results if result != max_confidence_result]) > 1:
            # we adjust confidence based on the disparity of classification simple_ranks -- wide disparity means less confidence
            # we first compare true ranks, then the classification's simple_rank (a 1 to n for each classification)
            adjustment = cls._adjust_for_disparity(results, max_confidence_result)
            results = [result for result in results if result != max_confidence_result]
            return max_confidence_result._replace(
                adjustment=adjustment,
                alternate_classifications={
                    result.classification: result.evidence
                    for result in results
                    if result.classification != max_confidence_result.classification
                },
            )
        return max_confidence_result


class GrammarBasedClassifier:
    """Primary classifier using grammar structure from node_types.json."""

    def __init__(self) -> None:
        """Initialize grammar-based classifier."""
        # Build Category name → SemanticClass mapping
        self._classification_map = self._build_category_to_semantic_map

    def _classify_by_can_be_anywhere(
        self, thing: CompositeThing | Token, language: SemanticSearchLanguage
    ) -> GrammarClassificationResult | None:
        """Classify a Thing based on can_be_anywhere flag.

        There's a small set of Things that can appear anywhere in the syntax tree, or are marked as such in the grammar. All but two are comments:

        - Since we're talking about comments that can be anywhere (unlike, for example, docstring comments that may be constrained for some languages), we know that these are either line comments or block comments (typically module-level comments).
        - Most grammars don't distinguish between line and block comments *within nodes that can be anywhere*. Swift is an exception, which has "comment" (line) and "multiline_comment" (block).
        - So for swift, we can have high confidence in distinguishing line vs block comments.
        - The two exceptions are:

            - Python's "line_continuation" (which is actually a syntax element, not a comment)
            - PHP's "text_interpolation" (which are string interpolation nodes for templated strings)

        - Others will need further disambiguation to more confidently classify as line vs block comments.

        Args:
            thing: The Thing instance
            language: The programming language
        """
        result_func = rpartial(
            self._to_classification_result,
            method=ClassificationMethod.ANYWHERE,
            evidence=[EvidenceKind.SPECIFIC_THING, EvidenceKind.LANGUAGE, EvidenceKind.HEURISTIC],
            adjustment=100,
            differentiator=None,
        )  # type: ignore

        if not thing.can_be_anywhere:
            return None
        # NOTE: we know exactly what each of these are from empirical analysis of all can_be_anywhere Things across all languages
        if language == SemanticSearchLanguage.SWIFT:
            if str(thing.name).lower() == "comment":
                return result_func(SemanticClass.SYNTAX_ANNOTATION)  # type: ignore
            if str(thing.name).lower() == "multiline_comment":
                return result_func(SemanticClass.DOCUMENTATION_STRUCTURED)  # type: ignore
        if (
            str(thing.name).lower() == "line_continuation"
            and language == SemanticSearchLanguage.PYTHON
        ):
            # Special case: Python line_continuation is SYNTAX_PUNCTUATION
            return result_func(SemanticClass.SYNTAX_PUNCTUATION)  # type: ignore
        if str(thing.name).lower() == "text_interpolation":
            # Special case: (PHP) text_interpolation is SYNTAX_IDENTIFIER
            return result_func(SemanticClass.SYNTAX_IDENTIFIER)  # type: ignore
        return None

    def _handle_comment_cases(
        self, thing: CompositeThing | Token, language: SemanticSearchLanguage
    ) -> GrammarClassificationResult | None:
        """Handle special cases for comment Things."""
        if "comment" in str(thing.name).lower() and "line" in str(thing.name).lower():
            return self._to_classification_result(
                SemanticClass.SYNTAX_ANNOTATION,
                method=ClassificationMethod.SPECIFIC_THING,
                evidence=[
                    EvidenceKind.SPECIFIC_THING,
                    EvidenceKind.LANGUAGE,
                    EvidenceKind.SIMPLE_NAME_PATTERN,
                ],
                adjustment=90,
                differentiator=None,
            )  # type: ignore
        if language == SemanticSearchLanguage.RUST and str(thing.name).lower() in {
            "doc_comment",
            "block_comment",
        }:
            return self._to_classification_result(
                SemanticClass.DOCUMENTATION_STRUCTURED,
                method=ClassificationMethod.SPECIFIC_THING,
                evidence=[
                    EvidenceKind.SPECIFIC_THING,
                    EvidenceKind.LANGUAGE,
                    EvidenceKind.SIMPLE_NAME_PATTERN,
                ],
                adjustment=90,
                differentiator=lambda thing: (  # type: ignore
                    SemanticClass.DOCUMENTATION_STRUCTURED
                    if thing.text.strip().startswith(("/**", "///", "//!", "#[doc", "#![doc"))  # type: ignore
                    else SemanticClass.SYNTAX_ANNOTATION
                ),  # type: ignore
            )
        if str(thing.name).lower() in {  # type: ignore
            "block_comment",
            "multiline_comment",
            "comment",
        }:
            return self._to_classification_result(
                SemanticClass.DOCUMENTATION_STRUCTURED,
                method=ClassificationMethod.SPECIFIC_THING,
                evidence=[
                    EvidenceKind.SPECIFIC_THING,
                    EvidenceKind.LANGUAGE,
                    EvidenceKind.SIMPLE_NAME_PATTERN,
                ],
                adjustment=-30 if str(thing.name) == "comment" else -20,
                differentiator=None,
            )  # type: ignore
        return None

    def _classify_from_composite_checks(
        self, thing: CompositeThing, language: SemanticSearchLanguage
    ) -> GrammarClassificationResult | None:
        """Classify based on composite structure checks using optimized tiered lookup.

        Uses a three-tier lookup system for ~10-15x faster classification:
        1. Language-specific grouped patterns (fastest)
        2. Generic cross-language patterns
        """
        from codeweaver.semantic.token_patterns import get_checks

        if match := next((iter(get_checks(str(thing.name), language=language))), None):
            return self._to_classification_result(
                classification=match,
                method=ClassificationMethod.SPECIFIC_THING,
                evidence=[
                    EvidenceKind.SPECIFIC_THING,
                    EvidenceKind.LANGUAGE,
                    EvidenceKind.HEURISTIC,
                ],
                adjustment=20,
            )
        return None

    def _classify_known_exceptions(
        self, thing: CompositeThing | Token, language: SemanticSearchLanguage
    ) -> GrammarClassificationResult | None:
        """Classify known exceptions that don't fit other patterns or that have very high confidence based on their specific characteristics."""
        if classification := self._handle_comment_cases(thing, language):
            return classification
        from codeweaver.semantic.registry import get_registry

        registry = get_registry()
        result_func = rpartial(
            self._to_classification_result,
            method=ClassificationMethod.SPECIFIC_THING,
            evidence=[EvidenceKind.SPECIFIC_THING, EvidenceKind.LANGUAGE, EvidenceKind.PURPOSE],
            adjustment=10,
        )
        if is_token(thing) and (str(thing.name) in registry.composite_things[language]):
            # a rare number of Things are *both* Tokens and CompositeThings in some languages
            return result_func(
                classification=SemanticClass.from_token_purpose(thing.purpose, thing.name)  # type: ignore
            )
        if (
            is_composite_thing(thing)
            and thing.name in registry.tokens[language]
            and (token := (registry.tokens[language][thing.name]))
        ):
            return result_func(
                classification=SemanticClass.from_token_purpose(token.purpose, token.name)  # type: ignore
            )
        if is_composite_thing(thing):
            return self._classify_from_composite_checks(thing, language)
        return None

    def _classify_ruby_primary(self, thing_name: str) -> GrammarClassificationResult | None:  # noqa: C901
        """Classify specific Ruby primary category members.

        The primary category in Ruby is extremely broad, spanning all 5 tiers:
        - Tier 1 (PRIMARY_DEFINITIONS): class, module, method, singleton_method, singleton_class
        - Tier 3 (CONTROL_FLOW_LOGIC): if, unless, while, until, case, case_match, for, break, next, redo, retry, return, yield
        - Tier 4 (OPERATIONS_EXPRESSIONS): unary, call, lambda (anonymous functions)
        - Tier 5 (SYNTAX_REFERENCES): literals, collections, identifiers, statement groupings

        Args:
            thing_name: The specific thing name (e.g., "class", "if", "string")

        Returns:
            High-confidence classification for the specific thing, or None
        """
        result_func = rpartial(
            self._to_classification_result,
            method=ClassificationMethod.SPECIFIC_THING,
            evidence=[EvidenceKind.SPECIFIC_THING, EvidenceKind.LANGUAGE],
            adjustment=15,
        )
        match thing_name:
            case "class" | "module" | "singleton_class":
                return result_func(classification=SemanticClass.DEFINITION_TYPE)  # type: ignore
            case "method" | "singleton_method":
                return result_func(classification=SemanticClass.DEFINITION_CALLABLE)  # type: ignore
            case "if" | "unless" | "case" | "case_match":
                return result_func(classification=SemanticClass.FLOW_BRANCHING)  # type: ignore
            case "while" | "until" | "for":
                return result_func(classification=SemanticClass.FLOW_ITERATION)  # type: ignore
            case "break" | "next" | "redo" | "retry" | "return" | "yield":
                return result_func(classification=SemanticClass.FLOW_CONTROL)  # type: ignore
            case "unary":
                return result_func(classification=SemanticClass.OPERATION_OPERATOR)  # type: ignore
            case "call":
                return result_func(classification=SemanticClass.OPERATION_INVOCATION)  # type: ignore
            case "lambda":
                return result_func(classification=SemanticClass.EXPRESSION_ANONYMOUS)  # type: ignore
            case (
                "simple_numeric"
                | "character"
                | "string"
                | "simple_symbol"
                | "delimited_symbol"
                | "chained_string"
                | "regex"
                | "array"
                | "string_array"
                | "symbol_array"
                | "hash"
            ):
                return result_func(classification=SemanticClass.SYNTAX_LITERAL)  # type: ignore
            case "lhs":
                return result_func(classification=SemanticClass.SYNTAX_IDENTIFIER)  # type: ignore
            case "begin" | "subshell" | "parenthesized_statements" | "heredoc_beginning":
                return result_func(classification=SemanticClass.SYNTAX_PUNCTUATION)  # type: ignore
            case _:
                return None

    @staticmethod
    def _to_classification_result(
        classification: SemanticClass,
        method: ClassificationMethod,
        evidence: Sequence[EvidenceKind],
        adjustment: int = 0,
        differentiator: Callable[[AstThing[SgNode]], SemanticClass] | None = None,
    ) -> GrammarClassificationResult:
        """Helper to create a GrammarClassificationResult with consistent rank calculation."""
        return GrammarClassificationResult(
            classification=classification,
            rank=classification.rank,
            classification_method=method,
            evidence=tuple(evidence),
            adjustment=adjustment,
            differentiator=differentiator,
        )

    def _classify_rust_declaration_statement(
        self, thing_name: str
    ) -> GrammarClassificationResult | None:
        """Classify specific Rust declaration_statement members.

        The declaration_statement category in Rust is extremely broad, spanning:
        - Tier 1 (PRIMARY_DEFINITIONS): function_item, struct_item, enum_item, trait_item, type_item, impl_item
        - Tier 2 (BOUNDARY_MODULE): use_declaration, extern_crate_declaration, mod_item, foreign_mod_item
        - Tier 1 (DEFINITION_DATA): const_item, static_item, let_declaration
        - Special: macro_invocation, macro_definition, attribute_item, inner_attribute_item, empty_statement

        Args:
            thing_name: The specific thing name (e.g., "let_declaration")

        Returns:
            High-confidence classification for the specific thing, or None
        """
        result_func = rpartial(
            self._to_classification_result,
            method=ClassificationMethod.SPECIFIC_THING,
            evidence=[EvidenceKind.SPECIFIC_THING, EvidenceKind.LANGUAGE],
            adjustment=15,
        )

        match thing_name:
            # Tier 1: Type definitions
            case (
                "struct_item"
                | "enum_item"
                | "union_item"
                | "trait_item"
                | "type_item"
                | "impl_item"
            ):
                return result_func(classification=SemanticClass.DEFINITION_TYPE)  # type: ignore

            # Tier 1: Callable definitions
            case "function_item" | "function_signature_item":
                return result_func(classification=SemanticClass.DEFINITION_CALLABLE)  # type: ignore

            # Tier 1: Data definitions
            case "const_item" | "static_item" | "let_declaration" | "associated_type":
                return result_func(classification=SemanticClass.DEFINITION_DATA)  # type: ignore

            # Tier 2: Module boundaries
            case "use_declaration" | "extern_crate_declaration" | "mod_item" | "foreign_mod_item":
                return result_func(classification=SemanticClass.BOUNDARY_MODULE)  # type: ignore

            # Syntax/metadata
            case "attribute_item" | "inner_attribute_item":
                return result_func(classification=SemanticClass.SYNTAX_ANNOTATION)  # type: ignore

            # Macros - treat as callable definitions
            case "macro_invocation" | "macro_definition":
                return result_func(classification=SemanticClass.DEFINITION_CALLABLE)  # type: ignore

            # Empty statement
            case "empty_statement":
                return result_func(classification=SemanticClass.SYNTAX_PUNCTUATION)  # type: ignore
            case _:
                return None

    def _classify_scala_definition(self, thing_name: str) -> GrammarClassificationResult | None:
        """Classify specific Scala definition members.

        The definition category in Scala spans:
        - Tier 1 (DEFINITION_CALLABLE): function_declaration, function_definition, given_definition
        - Tier 1 (DEFINITION_TYPE): class_definition, trait_definition, enum_definition, object_definition, type_definition
        - Tier 1 (DEFINITION_DATA): var_definition, val_definition, var_declaration, val_declaration
        - Tier 2 (BOUNDARY_MODULE): import_declaration, export_declaration, package_clause, package_object
        - Special: extension_definition

        Args:
            thing_name: The specific thing name (e.g., "function_definition")

        Returns:
            High-confidence classification for the specific thing, or None
        """
        result_func = rpartial(
            self._to_classification_result,
            method=ClassificationMethod.SPECIFIC_THING,
            evidence=[EvidenceKind.SPECIFIC_THING, EvidenceKind.LANGUAGE],
            adjustment=15,
        )
        match thing_name:
            # Tier 1: Callable definitions
            case "function_declaration" | "function_definition" | "given_definition":
                return result_func(classification=SemanticClass.DEFINITION_CALLABLE)  # type: ignore
            # Tier 1: Type definitions
            case "class_definition" | "trait_definition" | "enum_definition" | "object_definition":
                return result_func(classification=SemanticClass.DEFINITION_TYPE)  # type: ignore
            case "type_definition":
                return result_func(classification=SemanticClass.DEFINITION_TYPE)  # type: ignore
            # Tier 1: Data definitions
            case "var_definition" | "val_definition" | "var_declaration" | "val_declaration":
                return result_func(classification=SemanticClass.DEFINITION_DATA)  # type: ignore
            # Tier 2: Module boundaries
            case "import_declaration" | "export_declaration" | "package_clause" | "package_object":
                return result_func(classification=SemanticClass.BOUNDARY_MODULE)  # type: ignore
            case "extension_definition":
                return result_func(classification=SemanticClass.DEFINITION_TYPE)  # type: ignore
            case _:
                return None

    def _classify_multi_tier_things(
        self, thing: CompositeThing | Token, language: SemanticSearchLanguage
    ) -> GrammarClassificationResult | None:
        """Classify things from broad categories that span multiple semantic tiers.

        This method provides high-confidence thing-specific classifications for categories
        that are too broad to classify accurately at the category level alone.

        Args:
            thing: The Thing instance
            language: The programming language

        Returns:
            High-confidence classification if thing is from a multi-tier category, or None
        """
        thing_name = str(thing.name)
        return {
            SemanticSearchLanguage.RUBY: lambda: self._classify_ruby_primary(thing_name)
            # ty seems to think this is not ok -- it's explicitly defined on `Thing` as `__contains__`
            if CategoryName("primary") in thing  # ty: ignore[unsupported-operator]
            else None,
            SemanticSearchLanguage.RUST: lambda: self._classify_rust_declaration_statement(
                thing_name
            )
            if CategoryName("declaration_statement") in thing  # ty: ignore[unsupported-operator]
            else None,
            SemanticSearchLanguage.SCALA: lambda: self._classify_scala_definition(thing_name)
            if CategoryName("definition") in thing  # ty: ignore[unsupported-operator]
            else None,
        }.get(language, lambda: None)()

    def _classify_by_cross_language_lookup(
        self, thing: CompositeThing | Token, language: SemanticSearchLanguage
    ) -> GrammarClassificationResult | None:
        """Classify by looking up the same thing name in other languages.

        This is a fallback mechanism for languages with sparse category definitions.
        If we can't classify a thing in language A, we check if the same thing name
        exists in other languages where it HAS been classified, and use that
        classification with reduced confidence.

        IMPORTANT: This method only uses high-confidence classification methods directly
        (categories, token purpose, specific things) to avoid infinite recursion.

        Args:
            thing: The Thing to classify
            language: The current language (to exclude from lookup)

        Returns:
            Classification result with reduced confidence, or None if no match found
        """
        from codeweaver.semantic.registry import get_registry

        registry = get_registry()

        thing_name = str(thing.name)
        if (
            other_similar_things := [
                t
                for t in registry.all_cats_and_things
                if isinstance(t, type(thing)) and t.name == thing_name and t.language != language
            ]
        ) and (
            results := [
                t.classification_result
                for t in other_similar_things
                if t.classification_result and t.classification_result.is_confident is True
            ]
        ):
            if len(results) == 1:
                # single high-confidence match in another language
                result = results[0]
                return self._to_classification_result(
                    classification=result.classification,
                    method=ClassificationMethod.THING_INFERENCE,
                    evidence=[
                        EvidenceKind.LANGUAGE,
                        EvidenceKind.SIMPLE_NAME_PATTERN,
                        EvidenceKind.HEURISTIC,
                    ],
                    adjustment=-20,  # reduce confidence due to cross-language uncertainty
                )
            if all(result.classification == results[0].classification for result in results):
                # multiple matches but all agree on classification
                result = results[0]
                return self._to_classification_result(
                    classification=result.classification,
                    method=ClassificationMethod.THING_INFERENCE,
                    evidence=[
                        EvidenceKind.LANGUAGE,
                        EvidenceKind.SIMPLE_NAME_PATTERN,
                        EvidenceKind.HEURISTIC,
                    ],
                    adjustment=-5,  # we have multiple agreeing matches, so less reduction in confidence
                )
            if combined_results := GrammarClassificationResult.from_results(results):
                return combined_results._replace(
                    classification_method=ClassificationMethod.THING_INFERENCE,
                    adjustment=combined_results.adjustment - 10,  # reduce confidence
                )
        return None

    def classify_thing(
        self, thing_name: ThingNameT, language: SemanticSearchLanguage | str
    ) -> GrammarClassificationResult | None:
        """Classify a thing using grammar structure.

        Classification pipeline (highest to lowest confidence):
        very high confidence:
        1. Known exceptions (e.g., comments)
        2. can_be_anywhere Things (mostly comments, but small number and all known)
        3. Token purpose classification (very high confidence)
        4. Multi-tier Thing classification for specific language-category pairs (e.g., Ruby primary, Rust declaration_statement)
        5. Category-based classification for other categories

        medium-high confidence:
        6. Direct connections analysis (medium confidence)

        lower confidence:
        7. Cross-language lookup (lowest confidence, fallback only) -- looks for same-named Things in other languages with high-confidence classifications. It generally works but because of language differences, confidence is lower. Can still produce high confidence results if multiple other languages agree on classification.

        Args:
            thing_name: The Thing name (e.g., "function_definition")
            language: The programming language

        Returns:
            Classification result with confidence, or None if classification not possible
        """
        from codeweaver.semantic.grammar import get_grammar

        if not isinstance(language, SemanticSearchLanguage):
            language = SemanticSearchLanguage.from_string(language)

        # Get Thing from registry
        grammar = get_grammar(language)
        things = grammar.things
        thing = next((t for t in things if t.name == thing_name), None)
        if thing is None:
            return None  # Thing not found for language
        if is_composite_thing(thing) and thing.is_file:
            return self._to_classification_result(
                SemanticClass.FILE_THING,
                method=ClassificationMethod.SPECIFIC_THING,
                evidence=[EvidenceKind.SPECIFIC_THING],
                adjustment=100,
            )
        results: list[GrammarClassificationResult] = []
        for method in [
            self._classify_known_exceptions,
            self._classify_by_can_be_anywhere,
            self._classify_from_token_purpose,
            self._classify_multi_tier_things,
            self._classify_from_category,
            self._classify_from_direct_connections,
            self._classify_by_cross_language_lookup,
        ]:
            if classification := method(thing, language):
                # Check if it's a tuple but NOT a GrammarClassificationResult (which is a NamedTuple, hence a tuple)
                if not isinstance(classification, GrammarClassificationResult):
                    results.extend(classification)
                    continue
                # if we have multiple classifications, we need to disambiguate
                # fast path: if we have a classification above the confidence threshold, and it's the first one, return it immediately
                if classification.confidence >= CONFIDENCE_THRESHOLD and not results:
                    return classification
                # If we have multiple classifications, we need to disambiguate
                # We collect all classifications and then choose the best one at the end
                # This method allows us to consider all evidence before making a final decision
                results.append(classification)
        return GrammarClassificationResult.from_results(results) if results else None

    @property
    def _build_category_to_semantic_map(self) -> MappingProxyType[CategoryNameT, SemanticClass]:
        """Build mapping from grammar Category names to SemanticClass enum values.

        Based on empirical analysis of 25 languages, ~40 unique Categories once normalized.

        Returns:
            Mapping view from CategoryName (from node_types.json) to SemanticClass enum

        NOTE: There's not standardization of Categories or their meanings across languages. Commonly found Categories reflect grammars that were largely written by the same people (the tree-sitter core team). Many Categories are language-specific or only found in one or two languages. This mapping is based on empirical analysis of all categories found in the 25 languages we support, and assigning them to the closest fitting SemanticClass. This is a living document and will evolve as we analyze more languages and refine our understanding of existing ones.
        """
        return MappingProxyType({
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
            # These categories are found in only one or two languages each
            CategoryName(
                "arg"
            ): SemanticClass.OPERATION_OPERATOR,  # ruby - expressions used as arguments (binary, conditional, assignment, etc.)
            CategoryName("call_operator"): SemanticClass.OPERATION_OPERATOR,  # ruby ✓
            CategoryName("class_decl"): SemanticClass.DEFINITION_TYPE,  # haskell ✓
            CategoryName("class_member_declaration"): SemanticClass.DEFINITION_DATA,  # kotlin ✓
            CategoryName(
                "constraint"
            ): SemanticClass.DEFINITION_TYPE,  # haskell - type constraints (Eq a, Ord a, etc.) NOT control flow
            CategoryName(
                "constraints"
            ): SemanticClass.DEFINITION_TYPE,  # haskell - collections of type constraints in signatures
            CategoryName("decl"): SemanticClass.DEFINITION_CALLABLE,  # haskell ✓
            CategoryName(
                "declaration_statement"
            ): SemanticClass.DEFINITION_TYPE,  # Rust - broad category, needs thing-specific refinement for let/use declarations
            CategoryName(
                "definition"
            ): SemanticClass.DEFINITION_CALLABLE,  # scala - broad category spanning all definition types, needs refinement
            CategoryName(
                "expression_statement"
            ): SemanticClass.OPERATION_DATA,  # python - assignments and data operations, NOT anonymous functions
            CategoryName(
                "guard"
            ): SemanticClass.FLOW_BRANCHING,  # haskell - pattern guards are conditional branches, not explicit control flow
            CategoryName("instance_decl"): SemanticClass.DEFINITION_TYPE,  # haskell ✓
            CategoryName(
                "lhs"
            ): SemanticClass.SYNTAX_IDENTIFIER,  # ruby - left-hand side assignable locations (variables, element refs, etc.)
            CategoryName("literal_pattern"): SemanticClass.SYNTAX_LITERAL,  # rust ✓
            CategoryName("lvalue_expression"): SemanticClass.SYNTAX_IDENTIFIER,  # C# ✓
            CategoryName("method_name"): SemanticClass.SYNTAX_IDENTIFIER,  # ruby ✓
            CategoryName("module_directive"): SemanticClass.BOUNDARY_MODULE,  # java ✓
            CategoryName(
                "non_lvalue_expression"
            ): SemanticClass.OPERATION_OPERATOR,  # C# - complex expressions and operations, NOT literals
            CategoryName("nonlocal_variable"): SemanticClass.SYNTAX_IDENTIFIER,  # ruby ✓
            CategoryName("pattern_constant"): SemanticClass.SYNTAX_LITERAL,  # ruby ✓
            CategoryName(
                "pattern_expr"
            ): SemanticClass.FLOW_BRANCHING,  # ruby - pattern matching expressions
            CategoryName(
                "pattern_expr_basic"
            ): SemanticClass.FLOW_BRANCHING,  # ruby - basic pattern matching expressions
            CategoryName("pattern_primitive"): SemanticClass.SYNTAX_LITERAL,  # ruby ✓
            CategoryName(
                "pattern_top_expr_body"
            ): SemanticClass.FLOW_BRANCHING,  # ruby - pattern body
            CategoryName(
                "primary"
            ): SemanticClass.OPERATION_OPERATOR,  # ruby - primary expressions (broad mix, not just literals)
            CategoryName("primary_type"): SemanticClass.DEFINITION_TYPE,  # typescript ✓
            CategoryName(
                "qualifier"
            ): SemanticClass.FLOW_ITERATION,  # haskell - list comprehension qualifiers (generators, guards, let bindings)
            CategoryName("quantified_type"): SemanticClass.DEFINITION_TYPE,  # haskell ✓
            CategoryName("simple_numeric"): SemanticClass.SYNTAX_LITERAL,  # ruby ✓
            CategoryName("type_declaration"): SemanticClass.DEFINITION_TYPE,  # C# ✓
            CategoryName("type_param"): SemanticClass.DEFINITION_TYPE,  # haskell ✓
            CategoryName(
                "unannotated_type"
            ): SemanticClass.DEFINITION_TYPE,  # java - type specifications, not identifiers
            CategoryName("value"): SemanticClass.SYNTAX_LITERAL,  # json ✓
            CategoryName("variable"): SemanticClass.SYNTAX_IDENTIFIER,  # lua ✓
        })

    def _classify_from_token_purpose(
        self, token: Token | CompositeThing, _language: SemanticSearchLanguage
    ) -> GrammarClassificationResult | None:
        """Classify a Token based on its purpose classification.

        Very high confidence classification method (0.95) using CodeWeaver's token purpose classification.

        Args:
            token: The Token to classify

        Returns:
            Classification result with very high confidence, or None if no purpose classification
        """
        if is_composite_thing(token):
            return None  # Only Tokens have purpose classifications
        classification = SemanticClass.from_token_purpose(token.purpose, token.name)
        adjustment = 0
        if classification == SemanticClass.DOCUMENTATION_STRUCTURED:
            adjustment = -15  # We need more context to be sure it's a docstring
        return self._to_classification_result(
            classification=classification,
            method=ClassificationMethod.TOKEN_PURPOSE,
            evidence=[EvidenceKind.PURPOSE, EvidenceKind.SPECIFIC_THING],
            adjustment=adjustment,
        )

    def _classify_from_category(
        self, thing: CompositeThing | Token, _language: SemanticSearchLanguage
    ) -> tuple[GrammarClassificationResult, ...] | None:
        """Classify a Thing based on its Category membership.

        Highest confidence classification method (0.90) using explicit grammar Categories.

        Args:
            thing: The Thing (CompositeThing or Token) to classify

        Returns:
            A tuple of classifications (one per unique Category mapping), or None.
        """
        if not thing.categories:
            return None

        # For Things with single Category, use it directly
        if thing.is_single_category:
            response = self._classify_from_primary_category(thing, _language)
            return (response,) if response else None
        # For multi-category Things (13.5% of Things), try all Categories
        if alternates := {
            self._classification_map.get(cat.name)
            for cat in thing.categories
            if self._classification_map.get(cat.name)
        }:
            if len(alternates) == 1:
                return (
                    self._to_classification_result(
                        cast(SemanticClass, alternates.pop()),
                        method=ClassificationMethod.CATEGORY,
                        evidence=[EvidenceKind.CATEGORIES, EvidenceKind.HEURISTIC],
                        adjustment=5 * len(thing.categories),
                    ),
                )
            results = [
                self._to_classification_result(
                    classification,
                    method=ClassificationMethod.CATEGORY,
                    evidence=[EvidenceKind.CATEGORIES, EvidenceKind.HEURISTIC],
                    adjustment=-5 * len([alt for alt in alternates if alt is not None]),
                )
                for classification in alternates
                if classification is not None
            ]  # type: ignore
            return tuple(results) if results else None
        return None

    def _classify_from_primary_category(
        self, thing: CompositeThing | Token, _language: SemanticSearchLanguage
    ) -> GrammarClassificationResult | None:
        """Classify a Thing based on its primary Category membership."""
        primary_category = thing.primary_category
        if primary_category is None:
            return None  # Shouldn't happen but be defensive

        if semantic_classification := self._classification_map.get(primary_category.name):
            return self._to_classification_result(
                classification=semantic_classification,
                method=ClassificationMethod.CATEGORY,
                evidence=[EvidenceKind.CATEGORIES],
                adjustment=5,
            )
        return None

    def _classify_from_direct_connections(
        self, thing: CompositeThing | Token, _language: SemanticSearchLanguage
    ) -> GrammarClassificationResult | None:
        """Classify based on DirectConnection Role patterns.

        High confidence classification method (0.85) using semantic Role analysis.

        Args:
            thing: CompositeThing to analyze (only CompositeThings have DirectConnections)

        Returns:
            Classification with high confidence, or None if no pattern match
        """
        if is_token(thing):
            return None  # Only CompositeThings have DirectConnections

        # Extract Roles from DirectConnections
        roles = frozenset(str(conn.role) for conn in thing.direct_connections)

        # Pattern matching on Role combinations
        classification: SemanticClass | None = None

        # Callable definitions: have 'body' and 'name' Roles
        if {"body", "name"}.issubset(roles):
            classification = SemanticClass.DEFINITION_CALLABLE

        # Branching control flow: have 'condition' Role
        elif {"condition", "consequence"}.issubset(roles) or {"condition", "body"}.issubset(roles):
            classification = SemanticClass.FLOW_BRANCHING

        # Binary operations: have 'left', 'right', 'operator' Roles
        elif {"left", "right", "operator"}.issubset(roles):
            classification = SemanticClass.OPERATION_OPERATOR

        # Type definitions: have 'name' and 'body' but also 'superclass' or 'interfaces'
        elif {"name", "body"}.issubset(roles) and (
            "superclass" in roles or "interfaces" in roles or "base" in roles
        ):
            classification = SemanticClass.DEFINITION_TYPE

        # Variable/data definitions: have 'type' and 'declarator' or 'value'
        elif {"type"}.issubset(roles) and (
            "declarator" in roles or "value" in roles or "default" in roles
        ):
            classification = SemanticClass.DEFINITION_DATA

        if classification is None:
            return None

        return self._to_classification_result(
            classification=classification,
            method=ClassificationMethod.CONNECTION_INFERENCE,
            evidence=(EvidenceKind.ROLES, EvidenceKind.CONNECTIONS),
            adjustment=10,
        )
