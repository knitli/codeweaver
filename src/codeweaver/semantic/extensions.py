# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Language extension integration for semantic node classification."""

from __future__ import annotations

import contextlib
import re

from dataclasses import dataclass
from typing import Annotated, ClassVar, Literal, NamedTuple

from pydantic import Field, NonNegativeFloat

from codeweaver._common import DataclassSerializationMixin
from codeweaver.language import SemanticSearchLanguage
from codeweaver.semantic.classifications import (
    ClassificationRegistry,
    ImportanceScoresDict,
    SemanticCategoryDict,
    SemanticClass,
    create_default_registry,
)
from codeweaver.semantic.pattern_classifier import ClassificationPhase, ClassificationResult


type CacheKey = tuple[str, str]  # (node_type, language_name)
"""Type alias for cache keys. A tuple of (node_type, language_name)."""


class LanguagePattern(NamedTuple):
    """Pattern for specialized language classification."""

    pattern: re.Pattern[str]
    category: SemanticClass
    group_name: Annotated[str, Field(max_length=50)]


@dataclass(frozen=True)
class ExtensionResult(DataclassSerializationMixin):
    """Result from language extension classification."""

    category: SemanticClass
    confidence: NonNegativeFloat
    source: Literal["registry_mapping", "specialized_pattern", "heuristic"]
    matched_pattern: str | None = None


def _check_registry_mapping_cached(
    node_type: str, language_name: SemanticSearchLanguage | str, registry: ClassificationRegistry
) -> tuple[SemanticClass | None, float, str | None]:
    """Registry mapping check - caching moved to instance level to avoid unhashable issues."""
    if not isinstance(language_name, SemanticSearchLanguage):
        language_name = SemanticSearchLanguage.from_string(language_name)
    with contextlib.suppress(ValueError, AttributeError):
        if category := registry.categorize_node(node_type, language_name):
            return category.name, 0.95, f"registry:{node_type}"
    return None, 0.0, None


class LanguageExtensionManager:
    """Manages language-specific category extensions."""

    special_patterns: ClassVar[dict[SemanticSearchLanguage, tuple[LanguagePattern, ...]]] | None = (
        None
    )

    def __init__(self, registry: ClassificationRegistry | None = None) -> None:
        """Initialize the extension manager with a category registry."""
        self.registry = registry or create_default_registry()
        if not type(self).special_patterns:
            type(self).special_patterns = self._compile_specialized_patterns()
        self.specialized_patterns = type(self).special_patterns
        # Instance-level cache to avoid unhashable registry issues
        self._registry_cache: dict[CacheKey, tuple[SemanticClass | None, float, str | None]] = {}

    def _compile_specialized_patterns(
        self,
    ) -> dict[SemanticSearchLanguage, tuple[LanguagePattern, ...]]:
        """Compile language-specific patterns for specialized classification."""
        # React/JSX patterns
        jsx_patterns = (
            LanguagePattern(
                pattern=re.compile(r"(?P<jsx_element>(j|t)sx.*element)", re.IGNORECASE),
                category=SemanticClass.add_language_member(
                    SemanticSearchLanguage.JSX,
                    SemanticCategoryDict(
                        name="jsx_markup_element",
                        description="A JSX or TSX element or markup component",
                        rank=3,
                        importance_scores=ImportanceScoresDict(
                            discovery=0.70,
                            comprehension=0.60,
                            modification=0.65,
                            debugging=0.55,
                            documentation=0.35,
                        ),
                        parent_classification=SemanticClass.DEFINITION_CALLABLE,
                        language_specific=True,
                        language=SemanticSearchLanguage.JSX,
                        examples=("JSX element", "TSX element", "react element"),
                    ),
                ),
                group_name="jsx_element",
            ),
            LanguagePattern(
                pattern=re.compile(r"(?P<react_hook>use[A-Z][a-zA-Z]*)", re.IGNORECASE),
                category=SemanticClass.OPERATION_INVOCATION,
                group_name="react_hook",
            ),
            LanguagePattern(
                pattern=re.compile(r"(?P<component_name>.*Component$)", re.IGNORECASE),
                category=SemanticClass.DEFINITION_CALLABLE,
                group_name="component_name",
            ),
            LanguagePattern(
                pattern=re.compile(r".*Hook$", re.IGNORECASE),
                category=SemanticClass.SYNTAX_IDENTIFIER,
                group_name="hook_name",
            ),
        )
        return (
            {SemanticSearchLanguage.JSX: jsx_patterns, SemanticSearchLanguage.TSX: jsx_patterns}
            | {
                SemanticSearchLanguage.RUST: (
                    LanguagePattern(
                        pattern=re.compile(
                            r"(?P<trait_or_impl_item>(impl|trait|struct|enum).*item)", re.IGNORECASE
                        ),
                        category=SemanticClass.DEFINITION_TYPE,
                        group_name="trait_or_impl_item",
                    ),
                    LanguagePattern(
                        pattern=re.compile(r"(?P<lifetime>.*lifetime.*)", re.IGNORECASE),
                        category=SemanticClass.SYNTAX_ANNOTATION,
                        group_name="lifetime",
                    ),
                    LanguagePattern(
                        pattern=re.compile(r"(?P<generic_param>generic.*param)", re.IGNORECASE),
                        category=SemanticClass.DEFINITION_TYPE,
                        group_name="generic_param",
                    ),
                )
            }
            | {
                SemanticSearchLanguage.PYTHON: (
                    LanguagePattern(
                        pattern=re.compile(
                            r"(?P<comprehension>(list|set|dict|mapping|generator|tuple).*(comprehension|expression))",
                            re.IGNORECASE,
                        ),
                        category=SemanticClass.EXPRESSION_ANONYMOUS,
                        group_name="comprehension",
                    ),
                    LanguagePattern(
                        pattern=re.compile(r"with.*statement", re.IGNORECASE),
                        category=SemanticClass.BOUNDARY_RESOURCE,
                        group_name="with_statement",
                    ),
                )
            }
            | {
                SemanticSearchLanguage.GO: (
                    # Go patterns
                    LanguagePattern(
                        pattern=re.compile(r"package.*clause", re.IGNORECASE),
                        category=SemanticClass.BOUNDARY_MODULE,
                        group_name="package",
                    ),
                    LanguagePattern(
                        pattern=re.compile(r"type.*decl", re.IGNORECASE),
                        category=SemanticClass.DEFINITION_TYPE,
                        group_name="type_decl",
                    ),
                    LanguagePattern(
                        pattern=re.compile(r"defer.*statement", re.IGNORECASE),
                        category=SemanticClass.BOUNDARY_RESOURCE,
                        group_name="defer",
                    ),
                )
            }
        )

    def check_extensions_first(
        self, node_type: str, language: SemanticSearchLanguage
    ) -> ClassificationResult | None:
        """Check language extensions before hierarchical classification."""
        # Phase 1: Direct registry mapping (highest priority)
        if registry_result := self._check_registry_mapping(node_type, language):
            return ClassificationResult(
                classification=registry_result.category,
                confidence=registry_result.confidence,
                phase=ClassificationPhase.LANGUAGE_EXT,
                rank=registry_result.category.rank,
                matched_pattern=registry_result.matched_pattern,
            )

        # Phase 2: Specialized pattern matching
        if pattern_result := self._check_specialized_patterns(node_type, language):
            return ClassificationResult(
                classification=pattern_result.category,
                confidence=pattern_result.confidence,
                phase=ClassificationPhase.LANGUAGE_EXT,
                rank=pattern_result.category.rank,
                matched_pattern=pattern_result.matched_pattern,
            )

        return None

    def refine_classification(
        self,
        base_result: ClassificationResult,
        language: SemanticSearchLanguage,
        context: str | None = None,
    ) -> ClassificationResult:
        """Refine base classification with language-specific knowledge."""
        # Check if we can upgrade the base result with language-specific information
        extension_result = self._check_language_refinement(
            base_result.classification, language, base_result.matched_pattern
        )

        if extension_result and extension_result.confidence > base_result.confidence:
            return ClassificationResult(
                classification=extension_result.category,
                confidence=extension_result.confidence,
                phase=ClassificationPhase.LANGUAGE_EXT,
                rank=extension_result.category.rank,
                matched_pattern=extension_result.matched_pattern,
                alternative_categories=base_result.alternative_categories,
            )

        return base_result

    @property
    def patterns(self) -> dict[SemanticSearchLanguage, tuple[LanguagePattern, ...]]:
        """Access the specialized patterns."""
        if not self.specialized_patterns:
            self.specialized_patterns = (
                type(self).special_patterns or self._compile_specialized_patterns()
            )
        return self.specialized_patterns

    def _check_registry_mapping(
        self, node_type: str, language: SemanticSearchLanguage
    ) -> ExtensionResult | None:
        """Check direct registry mapping for node type with instance-level caching."""
        cache_key: CacheKey = (node_type, language.name)

        # Check instance cache first
        if cache_key in self._registry_cache:
            category, confidence, pattern = self._registry_cache[cache_key]
        else:
            # Compute and cache the result
            category, confidence, pattern = _check_registry_mapping_cached(
                node_type, language.name, self.registry
            )
            self._registry_cache[cache_key] = (category, confidence, pattern)

        if category:
            return ExtensionResult(
                category=category,
                confidence=confidence,
                source="registry_mapping",
                matched_pattern=pattern,
            )

        return None

    def _check_specialized_patterns(
        self, node_type: str, language: SemanticSearchLanguage
    ) -> ExtensionResult | None:
        """Check language-specific specialized patterns."""
        if not any(lang for lang in self.patterns if lang == language):
            return None

        patterns = self.patterns[language]

        for pattern, category, group in patterns:
            if pattern.match(node_type):
                confidence = self._calculate_pattern_confidence(pattern, node_type)
                return ExtensionResult(
                    category=category,
                    confidence=confidence,
                    source="specialized_pattern",
                    matched_pattern=f"{group}:{pattern.pattern}",
                )

        return None

    def _check_language_refinement(
        self,
        base_category: SemanticClass,
        language: SemanticSearchLanguage,
        matched_pattern: str | None,
    ) -> ExtensionResult | None:
        """Check if we can refine a base category with language-specific knowledge."""
        # Example refinements based on base categories and languages
        if language in self.patterns:
            for pattern, category, group in self.patterns[language]:
                if matched_pattern and (
                    pattern.pattern in matched_pattern
                    or matched_pattern == f"{group}:{pattern.pattern}"
                ):
                    confidence = self._calculate_pattern_confidence(pattern, matched_pattern)
                    if category != base_category:
                        return ExtensionResult(
                            category=category,
                            confidence=confidence,
                            source="heuristic",
                            matched_pattern=f"{group}:{pattern.pattern}",
                        )

        return None

    def _calculate_pattern_confidence(self, pattern: re.Pattern[str], node_type: str) -> float:
        """Calculate confidence based on pattern specificity and match quality."""
        # Base confidence from pattern length and complexity
        serialized_pattern = pattern.pattern
        base_confidence = min(0.9, (0.6) + (len(serialized_pattern) / 100.0))

        # Boost confidence for exact matches
        if pattern.match(node_type):
            base_confidence += 0.1

        # Boost confidence for case-sensitive matches
        if not (pattern.flags & re.IGNORECASE) and pattern.search(node_type):
            base_confidence += 0.05

        return min(0.95, base_confidence)

    def get_available_extensions(
        self, language: SemanticSearchLanguage
    ) -> dict[str, SemanticClass]:
        """Get all available extensions for a language."""
        extensions: dict[str, SemanticClass] = {}

        # Get registered extensions from the registry
        if hasattr(self.registry, "_extensions") and language in self.registry._extensions:  # type: ignore
            for category_name, category_obj in self.registry._extensions[language].items():  # type: ignore
                extensions[category_obj.name] = category_name

        # Add pattern-based extensions
        if language in self.patterns:
            for _, category, group in self.patterns[language]:
                extensions[f"pattern:{group}"] = category

        return extensions

    def validate_extension_coverage(
        self, language: SemanticSearchLanguage, node_types: list[str]
    ) -> dict[str, str]:
        """Validate that node types have appropriate extension coverage."""
        coverage: dict[str, str] = {}

        for node_type in node_types:
            result = self.check_extensions_first(node_type, language)
            if result:
                coverage[node_type] = f"{result.classification.name} ({result.confidence:.2f})"
            else:
                coverage[node_type] = "No extension coverage"

        return coverage


class ContextualExtensionManager(LanguageExtensionManager):
    """Extended manager that considers additional contextual factors for extensions."""

    def classify_with_context(
        self,
        node_type: str,
        language: SemanticSearchLanguage,
        parent_type: str | None = None,
        sibling_types: list[str] | None = None,
        file_path: str | None = None,
    ) -> ClassificationResult | None:
        """Enhanced extension classification with context."""
        # Get base extension result
        base_result = self.check_extensions_first(node_type, language)
        if not base_result:
            return None
        # Apply contextual enhancements
        enhanced_confidence = self._enhance_confidence_with_context(
            base_result, parent_type, sibling_types, file_path
        )

        return ClassificationResult(
            classification=base_result.classification,
            confidence=enhanced_confidence,
            phase=base_result.phase,
            rank=base_result.rank,
            matched_pattern=base_result.matched_pattern,
            alternative_categories=base_result.alternative_categories,
        )

    def _safe_lower(self, value: str | None) -> str:
        """Safe lowercase helper that guards against None."""
        return value.lower() if isinstance(value, str) else ""

    def _apply_file_path_heuristics(
        self,
        confidence: float,
        classification_name: str,
        parent_type: str | None,
        file_path: str | None,
    ) -> float:
        """File-path based confidence adjustments."""
        if not file_path:
            return confidence

        fp_lower = file_path.lower()

        # JSX/TSX signals in path or parent_type
        jsx_path_indicators = ("component", "react", "ui", "frontend")
        jsx_classification = (
            classification_name.lower().startswith(("tsx", "jsx"))
            or "jsx" in classification_name
            or "react" in classification_name
        )
        parent_lower = self._safe_lower(parent_type)

        if jsx_classification and (
            any(ind in fp_lower for ind in jsx_path_indicators)
            or "component" in parent_lower
            or "react" in parent_lower
            or "jsx" in parent_lower
        ):
            confidence = min(0.98, confidence * 1.1)

        # File-extension based matching
        exts = set(SemanticSearchLanguage.JSX.extensions or ()) | set(
            SemanticSearchLanguage.TSX.extensions or ()
        )
        if exts and any(fp_lower.endswith(ext) for ext in exts):
            confidence = min(0.98, confidence * 1.1)

        # Rust-specific heuristics
        if classification_name.lower().startswith("rust"):
            rust_exts = SemanticSearchLanguage.RUST.extensions or (".rs",)
            if any(fp_lower.endswith(ext) for ext in rust_exts):
                confidence = min(0.95, confidence * 1.05)

        return confidence

    def _apply_parent_heuristics(
        self, confidence: float, category_name: str, parent_type: str | None
    ) -> float:
        """Parent-type based confidence adjustments."""
        if not isinstance(parent_type, str) or not parent_type:
            return confidence
        pt = parent_type.lower()
        if ("react" in pt or "jsx" in pt or "component" in pt) and (
            category_name.startswith(("tsx", "jsx"))
            or "jsx" in category_name
            or "react" in category_name
        ):
            confidence = min(0.98, confidence * 1.1)
        if "rust" in category_name and "rust" in pt:
            confidence = min(0.95, confidence * 1.05)
        return confidence

    def _apply_sibling_heuristics(
        self, confidence: float, result_category: SemanticClass, sibling_types: list[str] | None
    ) -> float:
        """Sibling-based confidence adjustments."""
        if not sibling_types:
            return confidence
        try:
            react_indicators = sum(
                "jsx" in s.lower() or "react" in s.lower() for s in sibling_types if s
            )
        except Exception:
            react_indicators = 0
        # Preserve previous behavior: only boost if category name contains 'JSX' literal
        if react_indicators > 0 and "JSX" in getattr(result_category, "name", ""):
            confidence = min(0.95, confidence * (1 + react_indicators * 0.02))
        return confidence

    def _enhance_confidence_with_context(
        self,
        result: ClassificationResult,
        parent_type: str | None,
        sibling_types: list[str] | None,
        file_path: str | None,
    ) -> float:
        """Enhance confidence based on contextual information (refactored)."""
        confidence = float(result.confidence)
        # Prefer category.name if available, else fallback to str(classification)
        if hasattr(result.classification, "name"):
            category_name = self._safe_lower(getattr(result.classification, "name", None))
        else:
            category_name = self._safe_lower(str(result.classification))

        # Apply heuristics in sequence
        confidence = self._apply_file_path_heuristics(
            confidence, category_name, parent_type, file_path
        )
        confidence = self._apply_parent_heuristics(confidence, category_name, parent_type)
        confidence = self._apply_sibling_heuristics(
            confidence, result.classification, sibling_types
        )

        return float(confidence)


# Global instances for convenient access
_extension_manager = LanguageExtensionManager()
_contextual_extension_manager = ContextualExtensionManager()


def check_language_extensions(
    node_type: str, language: SemanticSearchLanguage
) -> ClassificationResult | None:
    """Convenient function for checking language extensions."""
    return _extension_manager.check_extensions_first(node_type, language)


def refine_with_extensions(
    base_result: ClassificationResult, language: SemanticSearchLanguage, context: str | None = None
) -> ClassificationResult:
    """Convenient function for refining classification with extensions."""
    return _extension_manager.refine_classification(base_result, language, context)


def get_language_extensions(language: SemanticSearchLanguage) -> dict[str, SemanticClass]:
    """Get available extensions for a language."""
    return _extension_manager.get_available_extensions(language)


def classify_with_context(
    node_type: str,
    language: SemanticSearchLanguage,
    parent_type: str | None = None,
    sibling_types: list[str] | None = None,
    file_path: str | None = None,
) -> ClassificationResult | None:
    """Convenient function for contextual extension classification."""
    return _contextual_extension_manager.classify_with_context(
        node_type, language, parent_type, sibling_types, file_path
    )
