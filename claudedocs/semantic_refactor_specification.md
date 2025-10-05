# Semantic Package Refactor Specification

**Version**: 1.0
**Date**: 2025-01-10
**Status**: Design Phase
**Based on**: Grammar structure analysis of 21 languages

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Data-Driven Insights](#data-driven-insights)
3. [Architecture Design](#architecture-design)
4. [API Design: node_type_parser Improvements](#api-design-node_type_parser-improvements)
5. [New Component: GrammarBasedClassifier](#new-component-grammarbasedclassifier)
6. [Modified Components](#modified-components)
7. [Implementation Roadmap](#implementation-roadmap)
8. [Migration Strategy](#migration-strategy)
9. [Testing Strategy](#testing-strategy)
10. [Success Criteria](#success-criteria)

---

## Executive Summary

This specification defines a comprehensive refactor of the semantic package to prioritize the inherent structure in tree-sitter `node_types.json` files while preserving pattern-based classification as a fallback for unsupported languages.

### Key Changes

1. **New `GrammarBasedClassifier`**: Primary classification using grammar structure
2. **Enhanced `node_type_parser`**: Better API with NamedTuples and semantic extraction methods
3. **Simplified `classifier.py`**: Thin routing layer (grammar → pattern fallback)
4. **Renamed `hierarchical.py` → `pattern_classifier.py`**: Clarify role as fallback system
5. **Unchanged `categories.py`**: Stable domain model

### Data Foundation

Analysis of 21 languages reveals:
- **102 total abstract types** across all grammars
- **Top abstract categories**: `expression` (71% of languages), `statement` (52%), `type` (33%)
- **Universal field names**: `name` (279 uses), `body` (193), `type` (182), `value` (110)
- **Field semantic patterns**: Clear relationships between fields and categories
- **High structure coverage**: 68-87% of named nodes have fields

---

## Data-Driven Insights

### Abstract Type Patterns (from grammar_structure_analysis.md)

```python
# Universal abstract categories (appear in 15+ languages)
UNIVERSAL_ABSTRACT_TYPES = {
    "expression": 15,      # 71.4% of languages
    "statement": 11,       # 52.4% of languages
    "type": 7,             # 33.3% of languages
    "primary_expression": 5,  # 23.8%
    "declaration": 5,      # 23.8%
    "pattern": 5,          # 23.8%
    "literal": 4,          # 19.0%
}

# Language-family specific (C-like languages)
C_FAMILY_ABSTRACT = {
    "abstract_declarator": 2,   # C, C++
    "declarator": 2,
    "field_declarator": 2,
    "type_declarator": 2,
    "type_specifier": 2,
}
```

### Field Semantic Patterns (from analysis)

```python
# Strong semantic signal from field names
FIELD_CATEGORY_MAPPING = {
    "name": {
        "type_def": 65,      # Primary: class/struct/interface names
        "callable": 32,      # Secondary: function names
        "control_flow": 24,  # Tertiary: loop labels, etc.
    },
    "body": {
        "control_flow": 52,  # Primary: if/while/for bodies
        "type_def": 27,      # Secondary: class bodies
        "callable": 26,      # Tertiary: function bodies
    },
    "type": {
        "type_def": 57,      # Primary: type definitions
        "callable": 8,       # Secondary: return types
    },
    "condition": {
        "control_flow": 60,  # Exclusive: if/while conditions
    },
    "operator": {
        "operation": 39,     # Primary: binary/unary expressions
    },
    "parameters": {
        "callable": 34,      # Primary: function parameters
        "type_def": 3,       # Secondary: generic type parameters
    },
}
```

### Structural Coverage Statistics

```
Average Coverage Across 21 Languages:
- Nodes with fields: 79.2% of named nodes
- Nodes with both fields and children: Varies 20-87%
- Abstract types: 0-15 per language (avg: 4.8)
- Extra nodes (syntactic): 0-4 per language
```

**Key Insight**: Grammar structure provides explicit semantic information for the vast majority of named nodes. Pattern matching is only needed for:
1. Languages without abstract types (CSS, Elixir, Swift, YAML)
2. Nodes without fields (~21% average)
3. Dynamically loaded grammars (future feature)

---

## Architecture Design

### Current Architecture

```
classifier.py (320 lines)
  ├─> LanguageExtensionManager (language-specific overrides)
  ├─> HierarchicalMapper (4-phase pattern pipeline)
  │     ├─> SyntacticClassifier (fast-path for punctuation)
  │     ├─> Tier-based pattern matching
  │     ├─> Pattern-based fallback
  │     └─> Ultimate fallback
  └─> ConfidenceScorer (confidence calculation)

categories.py (stable)
  ├─> SemanticCategory (domain model)
  ├─> SemanticNodeCategory (enum with 30 categories)
  ├─> SemanticTier (5-tier hierarchy)
  └─> ImportanceScores (multi-dimensional scoring)

node_type_parser.py (624 lines)
  ├─> TypedDicts for node field types
  ├─> NodeTypeParser (parse node_types.json)
  └─> Basic parsing methods
```

### Target Architecture

```
classifier.py (150 lines - SIMPLIFIED)
  ├─> LanguageExtensionManager (unchanged)
  ├─> GrammarBasedClassifier (NEW - primary path)
  │     ├─> Abstract type classification (from subtypes)
  │     ├─> Field-based inference (from fields)
  │     ├─> Children constraint analysis
  │     └─> Extra node handling
  ├─> PatternBasedClassifier (RENAMED from HierarchicalMapper)
  │     └─> Fallback for unsupported cases
  └─> ConfidenceScorer (unchanged)

categories.py (NO CHANGES - stable)
  └─> (Unchanged)

node_type_parser.py (750 lines - ENHANCED)
  ├─> NamedTuples for node info (IMPROVED API)
  ├─> NodeTypeParser (enhanced)
  ├─> Semantic extraction methods (NEW)
  │     ├─> get_abstract_category_map()
  │     ├─> get_field_semantic_roles()
  │     ├─> get_node_semantic_info()
  │     └─> get_supertype_hierarchy()
  └─> Cached property optimizations

grammar_classifier.py (NEW - 400 lines)
  ├─> GrammarBasedClassifier
  │     ├─> Abstract type classification
  │     ├─> Field-based inference
  │     ├─> Pre-computed mappings
  │     └─> High-confidence results
  └─> NodeSemanticInfo (NamedTuple)
```

---

## API Design: node_type_parser Improvements

### Current API Issues

**Problems with TypedDict approach**:
```python
# Current: Confusing nested dict structure
node_info: dict[str, Any] = {
    "type": "function_definition",
    "named": True,
    "fields": {
        "name": {"required": True, "types": [...]},
        "body": {"required": True, "types": [...]},
    }
}

# Access pattern is fragile
name_field = node_info.get("fields", {}).get("name", {}).get("types", [])
is_required = node_info.get("fields", {}).get("name", {}).get("required", False)
```

**Limitations**:
- No computed properties or helper methods
- Unclear access patterns for nested data
- No type narrowing based on discriminator
- Hard to add domain logic

### Improved API with NamedTuples + Pydantic Models

**Design Philosophy**:
- **NamedTuples**: For simple, immutable data structures with helper properties
- **Pydantic BaseModel**: For complex structures needing validation
- **Hybrid approach**: Use what fits best for each layer

```python
# Improved: Clean NamedTuple API with helper methods

from typing import NamedTuple, Sequence
from functools import cached_property


class FieldInfo(NamedTuple):
    """Information about a field in a node type."""
    name: str
    required: bool
    multiple: bool
    types: tuple[str, ...]  # Immutable

    @property
    def is_required(self) -> bool:
        """Check if field is required."""
        return self.required

    @property
    def is_collection(self) -> bool:
        """Check if field can have multiple values."""
        return self.multiple

    @cached_property
    def type_names(self) -> frozenset[str]:
        """Get set of type names for fast lookup."""
        return frozenset(self.types)

    def accepts_type(self, type_name: str) -> bool:
        """Check if this field accepts a given type."""
        return type_name in self.type_names


class NodeSemanticInfo(NamedTuple):
    """Semantic information extracted from grammar for a node type."""
    node_type: str
    language: str
    is_named: bool
    is_abstract: bool                  # Has subtypes
    is_extra: bool                     # Can appear anywhere
    is_root: bool                      # Root node

    # Relationships
    abstract_category: str | None      # Supertype if this is a concrete type
    concrete_subtypes: tuple[str, ...]  # If this is abstract

    # Structure
    fields: tuple[FieldInfo, ...]      # Named fields
    children_types: tuple[str, ...]    # Allowed child types

    @property
    def has_fields(self) -> bool:
        """Check if node has named fields."""
        return len(self.fields) > 0

    @property
    def has_children_constraints(self) -> bool:
        """Check if node has children constraints."""
        return len(self.children_types) > 0

    @cached_property
    def required_field_names(self) -> frozenset[str]:
        """Get set of required field names."""
        return frozenset(f.name for f in self.fields if f.is_required)

    @cached_property
    def field_map(self) -> dict[str, FieldInfo]:
        """Get mapping from field name to field info."""
        return {f.name: f for f in self.fields}

    def get_field(self, name: str) -> FieldInfo | None:
        """Get field info by name."""
        return self.field_map.get(name)

    def infer_semantic_category(self) -> str:
        """Infer semantic category from grammar structure."""
        # Use field names to infer category
        field_names = {f.name for f in self.fields}

        # Callable: has parameters or body
        if "parameters" in field_names or ("name" in field_names and "body" in field_names):
            return "callable"

        # Type definition: has type-related fields
        if "type_parameters" in field_names or self.node_type.endswith("_definition"):
            return "type_def"

        # Control flow: has condition
        if "condition" in field_names:
            return "control_flow"

        # Operation: has operator
        if "operator" in field_names:
            return "operation"

        # Abstract type suggests definition
        if self.is_abstract:
            return self.abstract_category or "unknown"

        return "unknown"


class AbstractTypeInfo(NamedTuple):
    """Information about an abstract type and its subtypes."""
    abstract_type: str
    language: str
    concrete_subtypes: tuple[str, ...]

    @cached_property
    def subtype_set(self) -> frozenset[str]:
        """Get set of subtypes for fast lookup."""
        return frozenset(self.concrete_subtypes)

    def is_subtype(self, type_name: str) -> bool:
        """Check if a type is a subtype of this abstract type."""
        return type_name in self.subtype_set
```

### Enhanced NodeTypeParser

```python
class NodeTypeParser:
    """Parser for tree-sitter node-types.json files with semantic extraction."""

    node_types_dir: Path

    # Existing methods...
    def parse_all_node_types(self, language: str) -> RootNodeTypes: ...
    def get_all_node_types(self, language: str) -> Sequence[str]: ...

    # NEW: Semantic extraction methods

    @cached_property
    def abstract_type_map(self) -> dict[str, dict[str, AbstractTypeInfo]]:
        """Map of abstract types to their info across all languages.

        Returns:
            {
                "expression": {
                    "python": AbstractTypeInfo(...),
                    "javascript": AbstractTypeInfo(...),
                    ...
                },
                "statement": {...},
                ...
            }
        """
        type_map: dict[str, dict[str, AbstractTypeInfo]] = defaultdict(dict)

        for language in self._supported_languages():
            node_types = self.parse_all_node_types(language.value)

            for node_info in node_types.flatten():
                if hasattr(node_info, "subtypes") and node_info.subtypes:
                    abstract_name = node_info.type_name.lstrip("_")
                    subtypes = tuple(st.type_name for st in node_info.subtypes)

                    type_map[abstract_name][language.value] = AbstractTypeInfo(
                        abstract_type=abstract_name,
                        language=language.value,
                        concrete_subtypes=subtypes,
                    )

        return dict(type_map)

    @cached_property
    def field_semantic_patterns(self) -> dict[str, dict[str, int]]:
        """Map field names to their common semantic categories.

        Based on empirical analysis of grammar structures.

        Returns:
            {
                "name": {"type_def": 65, "callable": 32, ...},
                "body": {"control_flow": 52, "type_def": 27, ...},
                ...
            }
        """
        # Pre-computed from grammar analysis
        return {
            "name": {"type_def": 65, "callable": 32, "control_flow": 24},
            "body": {"control_flow": 52, "type_def": 27, "callable": 26},
            "type": {"type_def": 57, "callable": 8, "control_flow": 6},
            "condition": {"control_flow": 60},
            "operator": {"operation": 39, "boundary": 2, "type_def": 1},
            "parameters": {"callable": 34, "type_def": 3},
            "return_type": {"callable": 16, "type_def": 1},
            # ... (from grammar analysis data)
        }

    def get_node_semantic_info(
        self,
        node_type: str,
        language: SemanticSearchLanguage | str,
    ) -> NodeSemanticInfo | None:
        """Get comprehensive semantic information for a node type.

        This is the primary method for grammar-based classification.

        Args:
            node_type: The node type name (e.g., "function_definition")
            language: The programming language

        Returns:
            NodeSemanticInfo with all extracted semantic data, or None if not found
        """
        if not isinstance(language, SemanticSearchLanguage):
            language = SemanticSearchLanguage.from_string(language)

        # Parse node types for language
        node_types = self.parse_all_node_types(language.value)

        # Find node info
        node_info = self._find_node_info(node_types, node_type)
        if not node_info:
            return None

        # Extract semantic information
        return self._extract_semantic_info(node_info, language.value)

    def _extract_semantic_info(
        self,
        node_info: NodeTypeInfo,
        language: str,
    ) -> NodeSemanticInfo:
        """Extract semantic information from node type info."""
        # Extract fields
        fields = self._extract_fields(node_info)

        # Extract children constraints
        children = self._extract_children_types(node_info)

        # Check if abstract (has subtypes)
        is_abstract = hasattr(node_info, "subtypes") and bool(node_info.subtypes)
        subtypes = tuple(
            st.type_name for st in getattr(node_info, "subtypes", [])
        ) if is_abstract else ()

        # Find supertype if this is a concrete type
        supertype = self._find_supertype(node_info.type_name, language)

        return NodeSemanticInfo(
            node_type=node_info.type_name,
            language=language,
            is_named=node_info.named,
            is_abstract=is_abstract,
            is_extra=getattr(node_info, "extra", False),
            is_root=getattr(node_info, "root", False),
            abstract_category=supertype,
            concrete_subtypes=subtypes,
            fields=fields,
            children_types=children,
        )

    def _extract_fields(self, node_info: NodeTypeInfo) -> tuple[FieldInfo, ...]:
        """Extract field information from node type info."""
        if not hasattr(node_info, "fields"):
            return ()

        fields: list[FieldInfo] = []
        for field_name, field_data in node_info.fields.items():
            types = tuple(t["type"] for t in field_data.get("types", []))
            fields.append(FieldInfo(
                name=field_name,
                required=field_data.get("required", False),
                multiple=field_data.get("multiple", False),
                types=types,
            ))

        return tuple(fields)

    def _extract_children_types(self, node_info: NodeTypeInfo) -> tuple[str, ...]:
        """Extract allowed children types from node type info."""
        if not hasattr(node_info, "children"):
            return ()

        children_data = node_info.children
        if not isinstance(children_data, dict):
            return ()

        types = children_data.get("types", [])
        return tuple(t.get("type", "") for t in types if isinstance(t, dict))

    def _find_supertype(self, node_type: str, language: str) -> str | None:
        """Find supertype (abstract category) for a concrete node type."""
        for abstract_name, lang_map in self.abstract_type_map.items():
            if language in lang_map:
                type_info = lang_map[language]
                if type_info.is_subtype(node_type):
                    return abstract_name
        return None

    def get_supertype_hierarchy(
        self,
        node_type: str,
        language: SemanticSearchLanguage | str,
    ) -> list[str]:
        """Get hierarchy of supertypes for a node type.

        Returns:
            List of supertypes from most specific to most general.
            E.g., ["binary_expression", "expression", "primary_expression"]
        """
        if not isinstance(language, SemanticSearchLanguage):
            language = SemanticSearchLanguage.from_string(language)

        hierarchy = []
        current = node_type

        while supertype := self._find_supertype(current, language.value):
            hierarchy.append(supertype)
            current = supertype

            # Prevent infinite loops
            if len(hierarchy) > 10:
                break

        return hierarchy
```

### Benefits of the New API

1. **Type Safety**: NamedTuples provide better typing than dicts
2. **Discoverability**: Helper methods make API self-documenting
3. **Performance**: Cached properties for expensive operations
4. **Immutability**: NamedTuples are immutable by default
5. **Computed Properties**: Can add domain logic without changing data
6. **Clean Access**: `info.is_named` vs `info.get("named", False)`

---

## New Component: GrammarBasedClassifier

### File: `src/codeweaver/semantic/grammar_classifier.py`

```python
"""Grammar-based semantic node classification using inherent tree-sitter structure.

This module provides primary classification by leveraging the explicit semantic
relationships encoded in node_types.json files:
- Subtypes → Abstract categories
- Fields → Structural relationships and semantic hints
- Children → Positional constraints
- Extra → Syntactic elements

SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-License-Identifier: MIT OR Apache-2.0
"""

from __future__ import annotations

from functools import lru_cache
from typing import NamedTuple

from codeweaver.language import SemanticSearchLanguage
from codeweaver.semantic.categories import SemanticNodeCategory, SemanticTier
from codeweaver.semantic.node_type_parser import NodeTypeParser, NodeSemanticInfo


class GrammarClassificationResult(NamedTuple):
    """Result of grammar-based classification."""

    category: SemanticNodeCategory
    tier: SemanticTier
    confidence: float
    classification_method: str  # "abstract_type" | "field_inference" | "children" | "extra"
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
        self,
        node_type: str,
        language: SemanticSearchLanguage | str,
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

        # Method 4: Extra nodes (syntactic)
        if semantic_info.is_extra:
            return GrammarClassificationResult(
                category=SemanticNodeCategory.SYNTAX_REFERENCES,
                tier=SemanticTier.SYNTAX_REFERENCES,
                confidence=0.95,
                classification_method="extra",
                evidence=f"Node marked as 'extra' in grammar (can appear anywhere)"
            )

        return None  # Could not classify using grammar

    def _classify_from_abstract_type(
        self,
        info: NodeSemanticInfo,
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
            evidence=f"Subtype of '{info.abstract_category}' abstract category"
        )

    def _classify_from_fields(
        self,
        info: NodeSemanticInfo,
    ) -> GrammarClassificationResult | None:
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
            "control_flow": SemanticNodeCategory.CONTROL_FLOW_CONDITIONAL,
            "operation": SemanticNodeCategory.OPERATION_COMPUTATION,
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
            evidence=evidence
        )

    def _classify_from_children(
        self,
        info: NodeSemanticInfo,
    ) -> GrammarClassificationResult | None:
        """Classify based on children constraints."""
        if not info.has_children_constraints:
            return None

        # Heuristic: If has both fields and children, likely a structural definition
        if info.has_fields:
            # Structural nodes with complex children
            return GrammarClassificationResult(
                category=SemanticNodeCategory.STRUCTURE_BLOCK,
                tier=SemanticTier.CONTROL_FLOW_LOGIC,
                confidence=0.70,  # Moderate confidence
                classification_method="children",
                evidence=f"Has fields and children constraints (structural pattern)"
            )

        # Just children, likely an expression or statement container
        return GrammarClassificationResult(
            category=SemanticNodeCategory.SYNTAX_COMPOSITE,
            tier=SemanticTier.SYNTAX_REFERENCES,
            confidence=0.65,  # Lower confidence
            classification_method="children",
            evidence="Has children constraints only (composite structure)"
        )

    def _build_abstract_category_map(self) -> dict[str, SemanticNodeCategory]:
        """Build mapping from abstract type names to semantic categories.

        Based on empirical analysis:
        - expression → OPERATION_COMPUTATION
        - statement → CONTROL_FLOW_* (depends on context)
        - type → DEFINITION_TYPE
        - declaration → DEFINITION_*
        - pattern → PATTERN_MATCH
        - literal → SYNTAX_LITERAL
        """
        return {
            # Universal abstract types
            "expression": SemanticNodeCategory.OPERATION_COMPUTATION,
            "primary_expression": SemanticNodeCategory.OPERATION_COMPUTATION,
            "statement": SemanticNodeCategory.CONTROL_FLOW_SEQUENTIAL,
            "type": SemanticNodeCategory.DEFINITION_TYPE,
            "declaration": SemanticNodeCategory.DEFINITION_DATA,
            "pattern": SemanticNodeCategory.PATTERN_MATCH,
            "literal": SemanticNodeCategory.SYNTAX_LITERAL,

            # C-family specifics
            "declarator": SemanticNodeCategory.DEFINITION_DATA,
            "type_specifier": SemanticNodeCategory.DEFINITION_TYPE,

            # Language-specific
            "simple_statement": SemanticNodeCategory.CONTROL_FLOW_SEQUENTIAL,
            "simple_type": SemanticNodeCategory.DEFINITION_TYPE,

            # Add more from grammar analysis as needed
        }

    @lru_cache(maxsize=1000)
    def get_abstract_category_for_language(
        self,
        abstract_type: str,
        language: SemanticSearchLanguage,
    ) -> SemanticNodeCategory | None:
        """Get semantic category for an abstract type in a specific language."""
        # Check if this abstract type exists for this language
        lang_map = self.parser.abstract_type_map.get(abstract_type, {})
        if language.value not in lang_map:
            return None

        return self._abstract_to_category.get(abstract_type)
```

---

## Modified Components

### classifier.py (Simplified)

```python
"""Main semantic node classifier with grammar-first routing.

SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-License-Identifier: MIT OR Apache-2.0
"""

from codeweaver.semantic.grammar_classifier import GrammarBasedClassifier
from codeweaver.semantic.pattern_classifier import PatternBasedClassifier
from codeweaver.semantic.extensions import LanguageExtensionManager


class SemanticNodeClassifier:
    """Primary semantic node classifier with intelligent routing."""

    def __init__(self) -> None:
        """Initialize classifier with grammar-first architecture."""
        self.grammar_classifier = GrammarBasedClassifier()
        self.pattern_fallback = PatternBasedClassifier()  # Renamed from HierarchicalMapper
        self.extensions = LanguageExtensionManager()
        self.confidence_scorer = ConfidenceScorer()  # Unchanged

    def classify_node(
        self,
        node_type: str,
        language: SemanticSearchLanguage | str,
        context: str | None = None,
        **kwargs,
    ) -> EnhancedClassificationResult:
        """Main classification entry point with grammar-first routing.

        Classification pipeline:
        1. Language extensions (highest specificity)
        2. Grammar-based classification (primary path - NEW)
        3. Pattern-based fallback (for unsupported cases)

        Args:
            node_type: The node type name
            language: Programming language
            context: Optional context for classification
            **kwargs: Additional context (parent_type, sibling_types, file_path, etc.)

        Returns:
            Enhanced classification result with confidence scoring
        """
        if not isinstance(language, SemanticSearchLanguage):
            language = SemanticSearchLanguage.from_string(language)

        # Phase 1: Check language-specific extensions first
        if ext_result := self.extensions.classify_with_context(
            node_type, language, **kwargs
        ):
            return self._enhance_result(ext_result, "language_extension", **kwargs)

        # Phase 2: Grammar-based classification (NEW - primary path)
        if grammar_result := self.grammar_classifier.classify_node(node_type, language):
            # Apply extension refinements if available
            refined = self.extensions.refine_classification(grammar_result, language, context)
            return self._enhance_result(refined or grammar_result, "grammar", **kwargs)

        # Phase 3: Pattern-based fallback
        fallback_result = self.pattern_fallback.classify_node(node_type, language, context)
        return self._enhance_result(fallback_result, "pattern_fallback", **kwargs)

    def _enhance_result(
        self,
        result: ClassificationResult,
        source: str,
        **context_kwargs,
    ) -> EnhancedClassificationResult:
        """Enhance classification result with confidence scoring."""
        # Existing confidence scoring logic
        return self.confidence_scorer.enhance(result, source, **context_kwargs)
```

---

## Implementation Roadmap

### Phase 1: Foundation (Week 1)

**Goal**: Establish data foundation and API improvements without breaking existing code

1. **Day 1-2: API Design**
   - [ ] Create NamedTuple definitions (`FieldInfo`, `NodeSemanticInfo`, `AbstractTypeInfo`)
   - [ ] Add to `node_type_parser.py` (keep TypedDicts for backward compatibility)
   - [ ] Write unit tests for new NamedTuple API

2. **Day 3-4: Semantic Extraction**
   - [ ] Implement `abstract_type_map` cached property
   - [ ] Implement `field_semantic_patterns` (from analysis data)
   - [ ] Implement `get_node_semantic_info()` method
   - [ ] Implement `get_supertype_hierarchy()` method
   - [ ] Write comprehensive tests for extraction

3. **Day 5: Grammar Structure Analysis Integration**
   - [ ] Update `analyze_grammar_structure.py` to use new API
   - [ ] Verify mappings with real data
   - [ ] Document findings

**Deliverable**: Enhanced `node_type_parser.py` with new API and semantic extraction methods

**Testing**: Unit tests for all new methods, integration tests with real grammars

---

### Phase 2: Grammar-Based Classifier (Week 2)

**Goal**: Implement primary grammar-based classification

1. **Day 1-2: Core Classifier**
   - [ ] Create `grammar_classifier.py` file
   - [ ] Implement `GrammarBasedClassifier` class
   - [ ] Implement `_classify_from_abstract_type()`
   - [ ] Implement `_classify_from_fields()`
   - [ ] Implement `_classify_from_children()`
   - [ ] Build abstract category mapping

2. **Day 3-4: Testing & Validation**
   - [ ] Write unit tests for each classification method
   - [ ] Create test fixtures from real node types
   - [ ] Measure classification accuracy on sample nodes
   - [ ] Compare confidence scores with pattern-based system

3. **Day 5: Optimization**
   - [ ] Add caching for expensive operations
   - [ ] Benchmark performance vs pattern matching
   - [ ] Optimize pre-computed mappings

**Deliverable**: Working `GrammarBasedClassifier` with >85% accuracy on supported languages

**Testing**:
- Unit tests for all methods
- Integration tests with 21 languages
- Accuracy measurements vs ground truth
- Performance benchmarks

---

### Phase 3: Integration (Week 3)

**Goal**: Integrate grammar-based classifier into main classification pipeline

1. **Day 1-2: Routing Layer**
   - [ ] Refactor `classifier.py` to use grammar-first routing
   - [ ] Update `classify_node()` to try grammar → pattern fallback
   - [ ] Ensure extensions still work as refinements
   - [ ] Preserve existing confidence scoring

2. **Day 3: Rename & Clarify**
   - [ ] Rename `hierarchical.py` → `pattern_classifier.py`
   - [ ] Update imports throughout codebase
   - [ ] Add docstrings clarifying fallback role
   - [ ] Update `HierarchicalMapper` → `PatternBasedClassifier`

3. **Day 4-5: Testing & Validation**
   - [ ] Update all tests to reflect new architecture
   - [ ] Integration tests for full pipeline
   - [ ] Regression tests to ensure no behavior changes
   - [ ] Measure classification improvements

**Deliverable**: Integrated system with grammar-first classification

**Testing**:
- Full integration test suite
- Regression tests
- Accuracy improvements vs baseline
- Performance benchmarks

---

### Phase 4: Cleanup & Documentation (Week 4)

**Goal**: Polish, document, and prepare for release

1. **Day 1-2: Code Cleanup**
   - [ ] Remove dead code from pattern classifier
   - [ ] Reduce complexity in orchestration
   - [ ] Add type hints where missing
   - [ ] Run linting and formatting

2. **Day 3: Documentation**
   - [ ] Update module docstrings
   - [ ] Add architecture documentation
   - [ ] Create migration guide
   - [ ] Update CHANGELOG

3. **Day 4: Performance & Quality**
   - [ ] Profile classification performance
   - [ ] Optimize hot paths
   - [ ] Run full test suite
   - [ ] Generate coverage reports

4. **Day 5: Release Preparation**
   - [ ] Final testing on all 21 languages
   - [ ] Prepare release notes
   - [ ] Tag release version
   - [ ] Deploy documentation

**Deliverable**: Production-ready semantic package refactor

**Testing**:
- Complete test coverage (>90%)
- Performance benchmarks
- Quality metrics
- Documentation review

---

## Migration Strategy

### Backward Compatibility

**No Breaking Changes** - All refactoring is internal:

1. **Public API**: Unchanged
   - `classify_semantic_node()` function signature same
   - Return types same (`EnhancedClassificationResult`)
   - No changes to `categories.py` exports

2. **Internal Changes**: Additive
   - New `grammar_classifier.py` module (addition)
   - Enhanced `node_type_parser.py` API (additions, not replacements)
   - Renamed `hierarchical.py` (internal module)

3. **TypedDict Compatibility**: Keep both
   ```python
   # Keep existing TypedDicts for backward compat
   class SimpleField(TypedDict): ...

   # Add new NamedTuple API
   class FieldInfo(NamedTuple): ...

   # Provide conversion helpers
   def field_info_from_dict(d: SimpleField) -> FieldInfo: ...
   ```

### Gradual Migration Path

1. **Week 1**: Add new API alongside old
2. **Week 2**: Implement new classifier using new API
3. **Week 3**: Switch routing to prefer grammar-based
4. **Week 4**: Mark old patterns as fallback (no removal)

**Future (post-release)**: Consider deprecating TypedDict API in favor of NamedTuples

---

## Testing Strategy

### Unit Testing

```python
# tests/semantic/test_grammar_classifier.py

def test_classify_from_abstract_type_expression():
    """Test classification of expression subtype."""
    classifier = GrammarBasedClassifier()
    result = classifier.classify_node("binary_expression", "python")

    assert result is not None
    assert result.category == SemanticNodeCategory.OPERATION_COMPUTATION
    assert result.confidence >= 0.85
    assert result.classification_method == "abstract_type"


def test_classify_from_fields_function_definition():
    """Test field-based classification of function definition."""
    classifier = GrammarBasedClassifier()
    result = classifier.classify_node("function_definition", "python")

    assert result is not None
    assert result.category == SemanticNodeCategory.DEFINITION_CALLABLE
    assert result.confidence >= 0.80
    assert "parameters" in result.evidence or "body" in result.evidence


def test_fallback_to_none_for_unknown():
    """Test that unknown nodes return None (fall back to pattern matching)."""
    classifier = GrammarBasedClassifier()
    result = classifier.classify_node("nonexistent_node", "python")

    assert result is None


def test_extra_node_classification():
    """Test classification of extra (syntactic) nodes."""
    classifier = GrammarBasedClassifier()
    result = classifier.classify_node("comment", "python")

    assert result is not None
    assert result.category == SemanticNodeCategory.SYNTAX_REFERENCES
    assert result.classification_method == "extra"
```

### Integration Testing

```python
# tests/semantic/test_integration.py

def test_full_pipeline_grammar_first():
    """Test full classification pipeline with grammar-first routing."""
    classifier = SemanticNodeClassifier()

    # Test grammar-based classification
    result = classifier.classify_node("function_definition", "python")
    assert result.phase == "grammar"
    assert result.confidence >= 0.80

    # Test pattern fallback for CSS (no abstract types)
    result_css = classifier.classify_node("declaration", "css")
    assert result_css.phase in ["grammar", "pattern_fallback"]


def test_accuracy_improvement():
    """Test that grammar-based classification improves accuracy."""
    old_classifier = PatternBasedClassifier()  # Old system
    new_classifier = GrammarBasedClassifier()  # New system

    # Sample of known correct classifications
    test_cases = [
        ("function_definition", "python", SemanticNodeCategory.DEFINITION_CALLABLE),
        ("class_definition", "python", SemanticNodeCategory.DEFINITION_TYPE),
        ("if_statement", "python", SemanticNodeCategory.CONTROL_FLOW_CONDITIONAL),
        # ... more test cases
    ]

    old_correct = 0
    new_correct = 0

    for node_type, language, expected_category in test_cases:
        old_result = old_classifier.classify_node(node_type, language)
        new_result = new_classifier.classify_node(node_type, language)

        if old_result and old_result.category == expected_category:
            old_correct += 1

        if new_result and new_result.category == expected_category:
            new_correct += 1

    # Assert improvement
    assert new_correct >= old_correct
    print(f"Accuracy: Old={old_correct}/{len(test_cases)}, New={new_correct}/{len(test_cases)}")
```

### Performance Testing

```python
# tests/semantic/test_performance.py

import time

def test_classification_performance():
    """Benchmark grammar-based vs pattern-based classification."""
    grammar_classifier = GrammarBasedClassifier()
    pattern_classifier = PatternBasedClassifier()

    test_nodes = [
        ("function_definition", "python"),
        ("class_definition", "python"),
        ("if_statement", "python"),
        # ... 100+ test cases
    ]

    # Benchmark grammar-based
    start = time.perf_counter()
    for node_type, language in test_nodes:
        grammar_classifier.classify_node(node_type, language)
    grammar_time = time.perf_counter() - start

    # Benchmark pattern-based
    start = time.perf_counter()
    for node_type, language in test_nodes:
        pattern_classifier.classify_node(node_type, language)
    pattern_time = time.perf_counter() - start

    print(f"Grammar-based: {grammar_time:.3f}s")
    print(f"Pattern-based: {pattern_time:.3f}s")

    # Grammar-based should be faster (pre-computed lookups)
    assert grammar_time <= pattern_time * 1.5  # Allow some overhead
```

---

## Success Criteria

### Quantitative Metrics

1. **Classification Accuracy**: >90% for nodes with grammar info
2. **Coverage**: Grammar-based handles >80% of common nodes in 21 languages
3. **Performance**: <10ms per classification (vs current pattern matching)
4. **Confidence**: Average confidence >0.85 (vs current ~0.70)
5. **Fallback Rate**: <20% of classifications require pattern fallback
6. **Test Coverage**: >90% code coverage
7. **No Regressions**: All existing tests pass

### Qualitative Metrics

1. **Code Maintainability**: Reduced complexity in `classifier.py`
2. **API Usability**: NamedTuple API easier to use than TypedDict
3. **Documentation**: Clear architecture docs and migration guide
4. **Developer Experience**: Faster development with clearer patterns

### Validation Process

1. **Unit Tests**: All new code has >90% coverage
2. **Integration Tests**: Full pipeline tested with real grammars
3. **Regression Tests**: No behavior changes in public API
4. **Performance Tests**: Benchmarks show improvement or parity
5. **Manual Testing**: Sample classifications manually verified
6. **Peer Review**: Code reviewed by at least one other developer

---

## Appendix: Data Foundations

### Grammar Analysis Summary

**Languages Analyzed**: 21 (bash, c, cpp, c_sharp, css, elixir, go, haskell, html, java, json, kotlin, lua, nix, php, python, ruby, rust, scala, swift, yaml)

**Key Findings**:
- Universal abstract types: expression (71%), statement (52%), type (33%)
- Universal field names: name, body, type, value, condition (appear in most languages)
- Strong field→category correlations: parameters→callable, condition→control_flow
- High structural coverage: 68-87% of named nodes have fields

**Data Source**: `claudedocs/grammar_structure_analysis.md` (generated by `scripts/analyze_grammar_structure.py`)

### TypedDict → NamedTuple Migration Rationale

**Problem with TypedDict**:
- No runtime type checking
- No computed properties or methods
- Verbose nested access patterns
- Hard to extend with domain logic

**Benefits of NamedTuples**:
- Immutable by default (good for caching)
- Can add properties and methods
- Better IDE support and autocomplete
- Cleaner access patterns
- Lightweight (no Pydantic overhead for simple data)

**When to Use Each**:
- **NamedTuple**: Simple data structures with helper methods (FieldInfo, NodeSemanticInfo)
- **Pydantic BaseModel**: Complex validation needs, serialization (SemanticCategory)
- **TypedDict**: Backward compatibility only

---

## Review & Sign-off

**Specification Version**: 1.0
**Author**: Claude (AI Assistant)
**Date**: 2025-01-10
**Status**: Ready for Review

**Reviewers**:
- [ ] Technical Lead - Architecture Review
- [ ] Senior Developer - Code Review
- [ ] QA Lead - Testing Strategy Review

**Approval**:
- [ ] Approved for Implementation
- [ ] Date: ___________
- [ ] Signature: ___________
