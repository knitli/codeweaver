# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
"""
Complete implementation specification for CodeWeaver's new semantic categorization system
based on language workbench methodology with multi-dimensional importance scoring.
"""

from __future__ import annotations

import contextlib

from collections import Counter
from collections.abc import Sequence
from functools import cached_property
from types import MappingProxyType
from typing import Annotated, Self, TypedDict, Unpack

import textcase

from pydantic import Field, NonNegativeFloat, NonNegativeInt, computed_field, field_validator
from pydantic.dataclasses import dataclass

from codeweaver._common import BasedModel, BaseEnum, DataclassSerializationMixin
from codeweaver.language import SemanticSearchLanguage


# =============================================================================
# Core Data Structures
# =============================================================================


class ContextWeightDict(TypedDict):
    """Typed dictionary for context weights in AI assistant scenarios."""

    discovery: Annotated[
        NonNegativeFloat,
        Field(description="Weight for discovery context; finding relevant code", ge=0.0, le=1.0),
    ]
    comprehension: Annotated[
        NonNegativeFloat,
        Field(
            description="Weight for comprehension context; understanding behavior", ge=0.0, le=1.0
        ),
    ]
    modification: Annotated[
        NonNegativeFloat,
        Field(description="Weight for modification context; safe editing points", ge=0.0, le=1.0),
    ]
    debugging: Annotated[
        NonNegativeFloat,
        Field(description="Weight for debugging context; tracing execution", ge=0.0, le=1.0),
    ]
    documentation: Annotated[
        NonNegativeFloat,
        Field(description="Weight for documentation context; explaining code", ge=0.0, le=1.0),
    ]


@dataclass(frozen=True)
class ImportanceScores(DataclassSerializationMixin):
    """Multi-dimensional importance scoring for AI assistant contexts."""

    discovery: Annotated[
        NonNegativeFloat,
        Field(description="Weight for discovery context; finding relevant code", ge=0.0, le=1.0),
    ]
    comprehension: Annotated[
        NonNegativeFloat,
        Field(
            description="Weight for comprehension context; understanding behavior", ge=0.0, le=1.0
        ),
    ]
    modification: Annotated[
        NonNegativeFloat,
        Field(description="Weight for modification context; safe editing points", ge=0.0, le=1.0),
    ]
    debugging: Annotated[
        NonNegativeFloat,
        Field(description="Weight for debugging context; tracing execution", ge=0.0, le=1.0),
    ]
    documentation: Annotated[
        NonNegativeFloat,
        Field(description="Weight for documentation context; explaining code", ge=0.0, le=1.0),
    ]

    def weighted_score(self, context_weights: ContextWeightDict) -> float:
        """Calculate weighted importance score for given AI assistant context."""
        return (
            self.discovery * context_weights.get("discovery", 0.2)
            + self.comprehension * context_weights.get("comprehension", 0.2)
            + self.modification * context_weights.get("modification", 0.2)
            + self.debugging * context_weights.get("debugging", 0.2)
            + self.documentation * context_weights.get("documentation", 0.2)
        )

    def as_dict(self) -> ContextWeightDict:
        """Convert importance scores to a dictionary format."""
        return ContextWeightDict(**self.dump_python())

    @classmethod
    def from_dict(cls, **data: Unpack[ContextWeightDict]) -> Self:
        """Create ImportanceScores from a dictionary format."""
        return cls.validate_python(data=data)  # pyright: ignore[reportArgumentType]


class SemanticTier(int, BaseEnum):
    """Semantic importance tiers from highest to lowest priority."""

    STRUCTURAL_DEFINITIONS = 1  # Core code structures
    BEHAVIORAL_CONTRACTS = 2  # Interfaces and boundaries
    CONTROL_FLOW_LOGIC = 3  # Execution flow control
    OPERATIONS_EXPRESSIONS = 4  # Data operations and computations
    SYNTAX_REFERENCES = 5  # Literals and syntax elements


class SemanticCategoryDict(TypedDict):
    """Typed dictionary for semantic category definitions."""

    name: Annotated[
        SemanticNodeCategory | str,
        Field(description="Category identifier", pattern=r"^[A-Z][A-Z0-9_]+$", max_length=50),
    ]
    description: Annotated[str, Field(description="Human-readable description")]
    tier: Annotated[int, Field(description="Importance tier")]
    importance_scores: Annotated[ContextWeightDict, Field(description="Importance scores")]
    parent_category: Annotated[str | None, Field(description="Parent category identifier")]
    language_specific: Annotated[bool, Field(description="Is language-specific")]
    language: Annotated[
        SemanticSearchLanguage | str | None, Field(description="Programming language")
    ]
    examples: tuple[str, ...]


class SemanticCategory(BasedModel):
    """Universal semantic category for AST nodes."""

    name: Annotated[SemanticNodeCategory, Field(description="Category identifier")]
    description: Annotated[str, Field(description="Human-readable description")]
    tier: Annotated[SemanticTier, Field(description="Importance tier")]
    importance_scores: Annotated[
        ImportanceScores, Field(description="Multi-dimensional importance")
    ]
    parent_category: Annotated[
        str | None,
        Field(
            repr=True,
            description="If the category is language-specific, the parent category identifier. Should always be `None` for core categories.",
        ),
    ] = None  # For language extensions
    language_specific: Annotated[
        bool, Field(init=False, description="If the category is specific to a programming language")
    ] = False
    language: Annotated[
        SemanticSearchLanguage | None,
        Field(
            description="Programming language associated with the category. Only for language-specific categories."
        ),
    ] = None
    examples: Annotated[
        tuple[str, ...], Field(default_factory=tuple, description="Example constructs")
    ]

    def __model_post_init__(self) -> None:
        """Post-initialization validation."""
        with contextlib.suppress(KeyError, AttributeError):
            if not self.name.category:
                SemanticNodeCategory.categories = lambda: MappingProxyType({
                    **SemanticNodeCategory.categories(),
                    self.name: self,
                })
                SemanticNodeCategory.tier_map = lambda: MappingProxyType({
                    **SemanticNodeCategory.tier_map(),
                    self.name: self.tier,
                })

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, v: str | SemanticNodeCategory) -> SemanticNodeCategory:
        """Ensure name is a SemanticNodeCategory."""
        if isinstance(v, SemanticNodeCategory):
            return v
        return SemanticNodeCategory.add_member(textcase.upper(v), textcase.snake(v))

    @field_validator("importance_scores", mode="before")
    @classmethod
    def validate_importance_scores(
        cls, v: ContextWeightDict | ImportanceScores
    ) -> ImportanceScores:
        """Ensure importance_scores is a ContextWeightDict."""
        return ImportanceScores.validate_python(v) if isinstance(v, dict) else v

    def is_extension_of(self, core_category: str) -> bool:
        """Check if this category extends a core category."""
        return self.parent_category == core_category

    def get_composite_score(self, context: str = "default") -> float:
        """Get composite importance score for specific context."""
        context_weights = CONTEXT_WEIGHT_PROFILES.get(context, DEFAULT_CONTEXT_WEIGHTS)
        return self.importance_scores.weighted_score(context_weights)


class SemanticNodeCategory(str, BaseEnum):
    """Language-agnostic semantic categories for AST nodes."""

    # Tier 1: Structural Definitions
    DEFINITION_CALLABLE = "definition_callable"
    """Functions, methods, procedures, named lambdas"""
    DEFINITION_TYPE = "definition_type"
    """Classes, structs, interfaces, traits, generics, type aliases"""
    DEFINITION_DATA = "definition_data"
    """Enums, constants, configuration blocks, named data"""
    DEFINITION_TEST = "definition_test"
    """Test functions, test cases, examples, assertions"""

    # Tier 2: Behavioral Contracts
    BOUNDARY_MODULE = "boundary_module"
    """Imports, exports, namespaces, package declarations"""
    BOUNDARY_ERROR = "boundary_error"
    """Error boundaries, exception handling, error messages"""
    BOUNDARY_RESOURCE = "boundary_resource"
    """Resource boundaries, API endpoints, data sources"""
    DOCUMENTATION_STRUCTURED = "documentation_structured"
    """Structured documentation, API docs, user guides"""

    # Tier 3: Control Flow & Logic
    FLOW_BRANCHING = "flow_branching"
    """Branching control flow structures (if, switch)"""
    FLOW_ITERATION = "flow_iteration"
    """Iteration control flow structures (for, while)"""
    FLOW_CONTROL = "flow_control"
    """General control flow structures (break, continue)"""
    FLOW_ASYNC = "flow_async"
    """Asynchronous control flow structures (async, await)"""

    # Tier 4: Operations & Expressions
    OPERATION_INVOCATION = "operation_invocation"
    """Function/method invocation expressions"""
    OPERATION_DATA = "operation_data"
    """Data access and manipulation operations"""
    OPERATION_COMPUTATION = "operation_computation"
    """Mathematical and logical computation operations"""
    EXPRESSION_ANONYMOUS = "expression_anonymous"
    """Anonymous expressions (e.g., lambdas, closures)"""

    # Tier 5: Syntax & References
    REFERENCE_IDENTIFIER = "reference_identifier"
    """Identifiers and references (variables, built-in types)"""
    LITERAL_VALUE = "literal_value"
    """Literal values (strings, numbers, booleans)"""
    ANNOTATION_METADATA = "annotation_metadata"
    """Decorators, attributes, pragmas, compiler hints (not type annotations)"""
    SYNTAX_STRUCTURAL = "syntax_structural"
    """Structural syntax elements (braces, parentheses, punctuation)"""

    __slots__ = ()

    @property
    def is_core(self) -> bool:
        """Check if this category is a core (non-language-specific) category."""
        return not self.category.language_specific

    @property
    def is_extension(self) -> bool:
        """Check if this category is a language-specific category."""
        return self.category.language_specific

    @property
    def for_language(self) -> SemanticSearchLanguage | None:
        """Get the programming language associated with this category, if any."""
        return None if self.is_core else self.category.language

    @property
    def tier(self) -> SemanticTier:
        """Get the semantic tier for this category."""
        return self.tier_map().get(self, SemanticTier.SYNTAX_REFERENCES)

    @classmethod
    def tier_map(cls) -> MappingProxyType[SemanticNodeCategory, SemanticTier]:
        """Get mapping of categories to their semantic tiers."""
        return MappingProxyType({
            cls.DEFINITION_CALLABLE: SemanticTier.STRUCTURAL_DEFINITIONS,
            cls.DEFINITION_TYPE: SemanticTier.STRUCTURAL_DEFINITIONS,
            cls.DEFINITION_DATA: SemanticTier.STRUCTURAL_DEFINITIONS,
            cls.DEFINITION_TEST: SemanticTier.STRUCTURAL_DEFINITIONS,
            cls.BOUNDARY_MODULE: SemanticTier.BEHAVIORAL_CONTRACTS,
            cls.BOUNDARY_ERROR: SemanticTier.BEHAVIORAL_CONTRACTS,
            cls.BOUNDARY_RESOURCE: SemanticTier.BEHAVIORAL_CONTRACTS,
            cls.DOCUMENTATION_STRUCTURED: SemanticTier.BEHAVIORAL_CONTRACTS,
            cls.FLOW_BRANCHING: SemanticTier.CONTROL_FLOW_LOGIC,
            cls.FLOW_ITERATION: SemanticTier.CONTROL_FLOW_LOGIC,
            cls.FLOW_CONTROL: SemanticTier.CONTROL_FLOW_LOGIC,
            cls.FLOW_ASYNC: SemanticTier.CONTROL_FLOW_LOGIC,
            cls.OPERATION_INVOCATION: SemanticTier.OPERATIONS_EXPRESSIONS,
            cls.OPERATION_DATA: SemanticTier.OPERATIONS_EXPRESSIONS,
            cls.OPERATION_COMPUTATION: SemanticTier.OPERATIONS_EXPRESSIONS,
            cls.EXPRESSION_ANONYMOUS: SemanticTier.OPERATIONS_EXPRESSIONS,
            cls.REFERENCE_IDENTIFIER: SemanticTier.SYNTAX_REFERENCES,
            cls.LITERAL_VALUE: SemanticTier.SYNTAX_REFERENCES,
            cls.ANNOTATION_METADATA: SemanticTier.SYNTAX_REFERENCES,
            cls.SYNTAX_STRUCTURAL: SemanticTier.SYNTAX_REFERENCES,
        })

    @classmethod
    def categories(cls) -> MappingProxyType[SemanticNodeCategory, SemanticCategory]:
        """Get mapping of categories to their SemanticCategory definitions."""
        return MappingProxyType({
            cls.DEFINITION_CALLABLE: SemanticCategory(
                name=cls.DEFINITION_CALLABLE,
                description="Functions, methods, procedures, named lambdas",
                tier=SemanticTier.STRUCTURAL_DEFINITIONS,
                importance_scores=ImportanceScores(
                    discovery=0.95,
                    comprehension=0.92,
                    modification=0.85,
                    debugging=0.85,
                    documentation=0.92,
                ),
                examples=(
                    "function definitions",
                    "method definitions",
                    "procedures",
                    "named lambdas",
                ),
            ),
            cls.DEFINITION_TYPE: SemanticCategory(
                name=cls.DEFINITION_TYPE,
                description="Classes, structs, interfaces, traits, generics, type aliases",
                tier=SemanticTier.STRUCTURAL_DEFINITIONS,
                importance_scores=ImportanceScores(
                    discovery=0.95,
                    comprehension=0.92,
                    modification=0.90,
                    debugging=0.80,
                    documentation=0.92,
                ),
                examples=(
                    "class definitions",
                    "interface definitions",
                    "struct definitions",
                    "generic types",
                ),
            ),
            cls.DEFINITION_DATA: SemanticCategory(
                name=cls.DEFINITION_DATA,
                description="Enums, constants, configuration blocks, named data",
                tier=SemanticTier.STRUCTURAL_DEFINITIONS,
                importance_scores=ImportanceScores(
                    discovery=0.85,
                    comprehension=0.88,
                    modification=0.80,
                    debugging=0.65,
                    documentation=0.90,
                ),
                examples=("enum definitions", "constant declarations", "configuration objects"),
            ),
            cls.DEFINITION_TEST: SemanticCategory(
                name=cls.DEFINITION_TEST,
                description="Test functions, test cases, examples, assertions",
                tier=SemanticTier.STRUCTURAL_DEFINITIONS,
                importance_scores=ImportanceScores(
                    discovery=0.88,
                    comprehension=0.90,
                    modification=0.70,
                    debugging=0.90,
                    documentation=0.85,
                ),
                examples=("test functions", "test cases", "assertion blocks", "example code"),
            ),
            cls.BOUNDARY_MODULE: SemanticCategory(
                name=cls.BOUNDARY_MODULE,
                description="Imports, exports, namespaces, package declarations",
                tier=SemanticTier.BEHAVIORAL_CONTRACTS,
                importance_scores=ImportanceScores(
                    discovery=0.85,
                    comprehension=0.80,
                    modification=0.85,
                    debugging=0.60,
                    documentation=0.75,
                ),
                examples=("import statements", "export declarations", "namespace definitions"),
            ),
            cls.BOUNDARY_ERROR: SemanticCategory(
                name=cls.BOUNDARY_ERROR,
                description="Exception definitions, error types, error handling blocks",
                tier=SemanticTier.BEHAVIORAL_CONTRACTS,
                importance_scores=ImportanceScores(
                    discovery=0.70,
                    comprehension=0.85,
                    modification=0.75,
                    debugging=0.95,
                    documentation=0.70,
                ),
                examples=("exception classes", "try/catch blocks", "error handling", "error types"),
            ),
            cls.BOUNDARY_RESOURCE: SemanticCategory(
                name=cls.BOUNDARY_RESOURCE,
                description="Resource management, lifecycle, cleanup",
                tier=SemanticTier.BEHAVIORAL_CONTRACTS,
                importance_scores=ImportanceScores(
                    discovery=0.65,
                    comprehension=0.80,
                    modification=0.80,
                    debugging=0.90,
                    documentation=0.65,
                ),
                examples=(
                    "file handles",
                    "database connections",
                    "memory management",
                    "RAII patterns",
                ),
            ),
            cls.DOCUMENTATION_STRUCTURED: SemanticCategory(
                name=cls.DOCUMENTATION_STRUCTURED,
                description="Formal documentation, API docs, contracts",
                tier=SemanticTier.BEHAVIORAL_CONTRACTS,
                importance_scores=ImportanceScores(
                    discovery=0.55,
                    comprehension=0.75,
                    modification=0.50,
                    debugging=0.40,
                    documentation=0.95,
                ),
                examples=(
                    "JSDoc comments",
                    "docstrings",
                    "API documentation",
                    "contract specifications",
                ),
            ),
            cls.FLOW_BRANCHING: SemanticCategory(
                name=cls.FLOW_BRANCHING,
                description="Conditionals, pattern matching, switch statements",
                tier=SemanticTier.CONTROL_FLOW_LOGIC,
                importance_scores=ImportanceScores(
                    discovery=0.60,
                    comprehension=0.75,
                    modification=0.65,
                    debugging=0.90,
                    documentation=0.50,
                ),
                examples=(
                    "if/else statements",
                    "match expressions",
                    "switch statements",
                    "pattern matching",
                ),
            ),
            cls.FLOW_ITERATION: SemanticCategory(
                name=cls.FLOW_ITERATION,
                description="Loops, generators, iterators",
                tier=SemanticTier.CONTROL_FLOW_LOGIC,
                importance_scores=ImportanceScores(
                    discovery=0.50,
                    comprehension=0.70,
                    modification=0.65,
                    debugging=0.80,
                    documentation=0.45,
                ),
                examples=("for loops", "while loops", "generator functions", "iterator patterns"),
            ),
            cls.FLOW_CONTROL: SemanticCategory(
                name=cls.FLOW_CONTROL,
                description="Return, break, continue, goto, exceptions",
                tier=SemanticTier.CONTROL_FLOW_LOGIC,
                importance_scores=ImportanceScores(
                    discovery=0.45,
                    comprehension=0.65,
                    modification=0.55,
                    debugging=0.90,
                    documentation=0.35,
                ),
                examples=(
                    "return statements",
                    "break/continue",
                    "throw statements",
                    "goto statements",
                ),
            ),
            cls.FLOW_ASYNC: SemanticCategory(
                name=cls.FLOW_ASYNC,
                description="Async/await, futures, promises, coroutines",
                tier=SemanticTier.CONTROL_FLOW_LOGIC,
                importance_scores=ImportanceScores(
                    discovery=0.65,
                    comprehension=0.80,
                    modification=0.75,
                    debugging=0.85,
                    documentation=0.60,
                ),
                examples=("async functions", "await expressions", "promise handling", "coroutines"),
            ),
            cls.OPERATION_INVOCATION: SemanticCategory(
                name=cls.OPERATION_INVOCATION,
                description="Function calls, method calls, constructor calls",
                tier=SemanticTier.OPERATIONS_EXPRESSIONS,
                importance_scores=ImportanceScores(
                    discovery=0.45,
                    comprehension=0.65,
                    modification=0.45,
                    debugging=0.75,
                    documentation=0.25,
                ),
                examples=(
                    "function calls",
                    "method invocations",
                    "constructor calls",
                    "object creation",
                ),
            ),
            cls.OPERATION_DATA: SemanticCategory(
                name=cls.OPERATION_DATA,
                description="Assignments, property access, data manipulation",
                tier=SemanticTier.OPERATIONS_EXPRESSIONS,
                importance_scores=ImportanceScores(
                    discovery=0.35,
                    comprehension=0.55,
                    modification=0.50,
                    debugging=0.70,
                    documentation=0.25,
                ),
                examples=(
                    "variable assignments",
                    "property access",
                    "field access",
                    "array indexing",
                ),
            ),
            cls.OPERATION_COMPUTATION: SemanticCategory(
                name=cls.OPERATION_COMPUTATION,
                description="Arithmetic, logical, comparison operations",
                tier=SemanticTier.OPERATIONS_EXPRESSIONS,
                importance_scores=ImportanceScores(
                    discovery=0.25,
                    comprehension=0.45,
                    modification=0.35,
                    debugging=0.60,
                    documentation=0.25,
                ),
                examples=(
                    "arithmetic operations",
                    "logical operations",
                    "comparison operations",
                    "bitwise operations",
                ),
            ),
            cls.EXPRESSION_ANONYMOUS: SemanticCategory(
                name=cls.EXPRESSION_ANONYMOUS,
                description="Lambdas, closures, anonymous functions",
                tier=SemanticTier.OPERATIONS_EXPRESSIONS,
                importance_scores=ImportanceScores(
                    discovery=0.40,
                    comprehension=0.65,
                    modification=0.50,
                    debugging=0.60,
                    documentation=0.45,
                ),
                examples=(
                    "lambda expressions",
                    "arrow functions",
                    "closures",
                    "anonymous functions",
                ),
            ),
            cls.REFERENCE_IDENTIFIER: SemanticCategory(
                name=cls.REFERENCE_IDENTIFIER,
                description="Variable names, type names, references",
                tier=SemanticTier.SYNTAX_REFERENCES,
                importance_scores=ImportanceScores(
                    discovery=0.25,
                    comprehension=0.40,
                    modification=0.25,
                    debugging=0.45,
                    documentation=0.20,
                ),
                examples=("variable names", "type references", "identifiers", "symbol references"),
            ),
            cls.LITERAL_VALUE: SemanticCategory(
                name=cls.LITERAL_VALUE,
                description="Strings, numbers, booleans, null values",
                tier=SemanticTier.SYNTAX_REFERENCES,
                importance_scores=ImportanceScores(
                    discovery=0.15,
                    comprehension=0.20,
                    modification=0.15,
                    debugging=0.40,
                    documentation=0.20,
                ),
                examples=(
                    "string literals",
                    "numeric constants",
                    "boolean values",
                    "null/undefined",
                ),
            ),
            cls.ANNOTATION_METADATA: SemanticCategory(
                name=cls.ANNOTATION_METADATA,
                description="Decorators, attributes, pragmas, compiler hints",
                tier=SemanticTier.SYNTAX_REFERENCES,
                importance_scores=ImportanceScores(
                    discovery=0.35,
                    comprehension=0.45,
                    modification=0.60,
                    debugging=0.40,
                    documentation=0.40,
                ),
                examples=(
                    "Python decorators",
                    "Java annotations",
                    "C# attributes",
                    "compiler pragmas",
                ),
            ),
            cls.SYNTAX_STRUCTURAL: SemanticCategory(
                name=cls.SYNTAX_STRUCTURAL,
                description="Structural syntax elements (braces, parentheses, punctuation)",
                tier=SemanticTier.SYNTAX_REFERENCES,
                importance_scores=ImportanceScores(
                    discovery=0.01,
                    comprehension=0.02,
                    modification=0.15,
                    debugging=0.20,
                    documentation=0.05,
                ),
                examples=("braces", "parentheses", "semicolons", "commas"),
            ),
        })

    @property
    def category(self) -> SemanticCategory:
        """Get the SemanticCategory definition for this category."""
        return self.categories()[self]

    @classmethod
    def add_language_member(
        cls,
        language: SemanticSearchLanguage | str,
        category: SemanticCategory | SemanticCategoryDict,
    ) -> SemanticNodeCategory:
        """Add a new language-specific semantic category."""
        if not isinstance(language, SemanticSearchLanguage):
            language = SemanticSearchLanguage.from_string(language)
        if isinstance(category, dict):
            category = SemanticCategory.model_validate(category)
        if not category.language_specific:
            raise ValueError("Only language-specific categories can be added.")
        member_name = f"{language.name.upper()}_{category.name}"
        return cls.add_member(member_name, textcase.snake(member_name))


# =============================================================================
# Context Weight Profiles for Different AI Assistant Scenarios
# =============================================================================


class AgentTask(str, BaseEnum):
    """Predefined coding assistant tasks."""

    DEBUG = "debug"
    DEFAULT = "default"
    DOCUMENT = "document"
    IMPLEMENT = "implement"
    LOCAL_EDIT = "local_edit"
    REFACTOR = "refactor"
    REVIEW = "review"
    SEARCH = "search"

    __slots__ = ()

    @classmethod
    def profiles(cls) -> MappingProxyType[AgentTask, ContextWeightDict]:
        """Get list of available context weight profiles."""
        return MappingProxyType({
            cls.LOCAL_EDIT: ContextWeightDict(
                discovery=0.4,
                comprehension=0.3,
                modification=0.2,
                debugging=0.05,
                documentation=0.05,
            ),
            cls.DEBUG: ContextWeightDict(
                discovery=0.2,
                comprehension=0.3,
                modification=0.1,
                debugging=0.35,
                documentation=0.05,
            ),
            cls.REFACTOR: ContextWeightDict(
                discovery=0.15,
                comprehension=0.25,
                modification=0.45,
                debugging=0.1,
                documentation=0.05,
            ),
            cls.DOCUMENT: ContextWeightDict(
                discovery=0.2,
                comprehension=0.2,
                modification=0.1,
                debugging=0.05,
                documentation=0.45,
            ),
            cls.SEARCH: ContextWeightDict(
                discovery=0.5,
                comprehension=0.2,
                modification=0.15,
                debugging=0.1,
                documentation=0.05,
            ),
            cls.IMPLEMENT: ContextWeightDict(
                discovery=0.3,
                comprehension=0.3,
                modification=0.25,
                debugging=0.1,
                documentation=0.05,
            ),
            cls.REVIEW: ContextWeightDict(
                discovery=0.25,
                comprehension=0.35,
                modification=0.15,
                debugging=0.15,
                documentation=0.1,
            ),
            cls.DEFAULT: ContextWeightDict(
                discovery=0.25,
                comprehension=0.25,
                modification=0.2,
                debugging=0.15,
                documentation=0.15,
            ),
        })


DEFAULT_CONTEXT_WEIGHTS = {
    "discovery": 0.25,
    "comprehension": 0.25,
    "modification": 0.2,
    "debugging": 0.15,
    "documentation": 0.15,
}

CONTEXT_WEIGHT_PROFILES = {
    "code_completion": {
        "discovery": 0.4,
        "comprehension": 0.3,
        "modification": 0.2,
        "debugging": 0.05,
        "documentation": 0.05,
    },
    "debugging": {
        "discovery": 0.2,
        "comprehension": 0.3,
        "modification": 0.1,
        "debugging": 0.35,
        "documentation": 0.05,
    },
    "refactoring": {
        "discovery": 0.15,
        "comprehension": 0.25,
        "modification": 0.45,
        "debugging": 0.1,
        "documentation": 0.05,
    },
    "documentation": {
        "discovery": 0.2,
        "comprehension": 0.2,
        "modification": 0.1,
        "debugging": 0.05,
        "documentation": 0.45,
    },
    "search": {
        "discovery": 0.5,
        "comprehension": 0.2,
        "modification": 0.15,
        "debugging": 0.1,
        "documentation": 0.05,
    },
}


# =============================================================================
# Extension System for Language-Specific Categories
# =============================================================================


@dataclass
class CategoryRegistry(DataclassSerializationMixin):
    """Registry for core and language-specific semantic categories."""

    _extensions: dict[SemanticSearchLanguage, dict[SemanticNodeCategory, SemanticCategory]]
    _mappings: dict[SemanticSearchLanguage, dict[str, SemanticNodeCategory]]

    _core_categories: Annotated[
        MappingProxyType[SemanticNodeCategory, SemanticCategory],
        Field(
            default_factory=SemanticNodeCategory.categories,
            description="Core semantic categories",
            init=False,
        ),
    ]

    def __init__(self) -> None:
        """Setup the category registry."""
        self._extensions: dict[
            SemanticSearchLanguage, dict[SemanticNodeCategory, SemanticCategory]
        ] = {}
        self._mappings: dict[
            SemanticSearchLanguage, dict[str, SemanticNodeCategory]
        ] = {}  # language -> {node_type -> category}

    def register_core(
        self, category: SemanticCategory
    ) -> MappingProxyType[SemanticNodeCategory, SemanticCategory]:
        """Register a new core category."""
        if not isinstance(category.name, SemanticNodeCategory):
            node = SemanticNodeCategory.add_member(
                category.name.upper(), textcase.snake(category.name)
            )
            category = category.model_copy(update={"name": node})
        return MappingProxyType({**self._core_categories, category.name: category})

    def register_extension(
        self,
        language: str | SemanticSearchLanguage,
        category: SemanticCategory | SemanticCategoryDict,
    ) -> None:
        """Register a language-specific extension category."""
        if not isinstance(language, SemanticSearchLanguage):
            language = SemanticSearchLanguage.from_string(language)
        if language not in self._extensions:
            self._extensions[language] = {}
        if isinstance(category, dict):
            category["language"] = language
            category["language_specific"] = True
            category = SemanticCategory.model_validate(category)
        self._extensions[language][category.name] = category

    def register_mapping(
        self, language: SemanticSearchLanguage, node_type: str, category_name: SemanticNodeCategory
    ) -> None:
        """Register mapping from tree-sitter node type to semantic category."""
        if language not in self._mappings:
            self._mappings[language] = {}
        self._mappings[language][node_type] = category_name

    def get_category(
        self,
        category_name: str | SemanticNodeCategory,
        language: SemanticSearchLanguage | str | None = None,
    ) -> SemanticCategory | None:
        """Get category by name, checking language extensions first."""
        if not isinstance(language, SemanticSearchLanguage) and language is not None:
            language = SemanticSearchLanguage.from_string(language)
        if not isinstance(category_name, SemanticNodeCategory):
            category_name = SemanticNodeCategory.from_string(category_name)
        if (
            language
            and language in self._extensions
            and category_name in self._extensions[language]
        ):
            return self._extensions[language][category_name]
        return self._core_categories.get(category_name)

    def categorize_node(
        self, node_type: str, language: SemanticSearchLanguage | str
    ) -> SemanticCategory | None:
        """Categorize a tree-sitter node type."""
        # Check language-specific mappings first
        if not isinstance(language, SemanticSearchLanguage):
            language = SemanticSearchLanguage.from_string(language)
        if language in self._mappings and node_type in self._mappings[language]:
            category_name = self._mappings[language][node_type]
            return self.get_category(category_name, language)

        # Fallback to heuristic mapping
        return self._heuristic_categorize(node_type)

    def _heuristic_categorize(self, node_type: str) -> SemanticCategory | None:
        """Heuristic categorization for unmapped node types."""
        node_lower = node_type.lower()

        # Function/method patterns
        if any(pattern in node_lower for pattern in {"function", "method", "procedure", "def"}):
            return self._core_categories[SemanticNodeCategory.DEFINITION_CALLABLE]

        # Class/type patterns
        if any(pattern in node_lower for pattern in {"class", "struct", "interface", "type"}):
            return self._core_categories[SemanticNodeCategory.DEFINITION_TYPE]

        # Control flow patterns
        if any(
            pattern in node_lower
            for pattern in {
                "if",
                "else",
                "switch",
                "match",
                "case",
                "pattern",
                "when",
                "elif",
                "guard",
            }
        ):
            return self._core_categories[SemanticNodeCategory.FLOW_BRANCHING]

        # Loop patterns
        if any(pattern in node_lower for pattern in {"for", "while", "loop", "repeat"}):
            return self._core_categories[SemanticNodeCategory.FLOW_ITERATION]

        # Import/export patterns
        if any(pattern in node_lower for pattern in {"import", "export", "require", "use"}):
            return self._core_categories[SemanticNodeCategory.BOUNDARY_MODULE]

        # Default to unknown
        return None


# =============================================================================
# Validation and Testing Framework
# =============================================================================


@dataclass
class CoverageReport(DataclassSerializationMixin):
    """Report on coverage of semantic categories."""

    covered_categories: Sequence[SemanticNodeCategory]
    language: SemanticSearchLanguage

    @computed_field
    @cached_property
    def total_categories(self) -> int:
        """Calculate total number of categories for the language."""
        return len(self.possible_categories)

    @computed_field
    @cached_property
    def possible_categories(self) -> tuple[SemanticNodeCategory, ...]:
        """Get a list of all possible categories for the language."""
        cores = [cat for cat in SemanticNodeCategory if cat.is_core]
        cores.extend([
            cat
            for cat in SemanticNodeCategory
            if cat.is_extension and cat.for_language == self.language
        ])
        return tuple(cores)

    @computed_field
    @cached_property
    def covered_count(self) -> int:
        """Get count of covered categories."""
        return len(self.covered_categories)

    @computed_field
    @cached_property
    def coverage_percentage(self) -> NonNegativeFloat:
        """Calculate coverage percentage."""
        if self.total_categories == 0:
            return 100.0
        return (self.covered_count / self.total_categories) * 100.0

    @computed_field
    @cached_property
    def uncovered_categories(self) -> tuple[SemanticNodeCategory, ...]:
        """Get a list of uncovered categories."""
        return tuple(cat for cat in self.possible_categories if cat not in self.covered_categories)


@dataclass
class UsageMetrics(DataclassSerializationMixin):
    """Metrics on real-world usage of semantic categories."""

    category_usage_counts: Counter[SemanticNodeCategory]

    @computed_field
    @property
    def total_use(self) -> NonNegativeInt:
        """Calculate total number of usages across all categories."""
        return sum(self.category_usage_counts.values())

    @computed_field
    @property
    def usage_frequencies(self) -> dict[SemanticNodeCategory, NonNegativeFloat]:
        """Calculate usage frequency for each category."""
        if self.total_use == 0:
            return dict.fromkeys(self.category_usage_counts, 0.0)
        return {
            cat: (count / self.total_use) * 100.0
            for cat, count in self.category_usage_counts.items()
        }

    def add_uses(self, categories: Sequence[SemanticNodeCategory]) -> None:
        """Add usage counts for a list of categories."""
        self.category_usage_counts.update(categories)


@dataclass
class ScoreValidation(DataclassSerializationMixin):
    """Validation results for importance score accuracy."""

    @computed_field
    @property
    def correlation_matrix(self) -> dict[str, float]:
        """Calculate correlation between importance scores and usage frequencies."""
        # Placeholder for actual correlation calculation
        return {}

    @computed_field
    @property
    def significance(self) -> bool:
        """Determine if the correlation is statistically significant."""
        # Placeholder for actual significance testing
        return False

    @computed_field
    @property
    def p_values(self) -> dict[str, float]:
        """Get p-values for the correlations."""
        # Placeholder for actual p-value calculation
        return {}

    @computed_field
    @property
    def discrepancies(self) -> dict[SemanticNodeCategory, float]:
        """Identify categories with significant discrepancies."""
        # Placeholder for actual discrepancy identification
        return {}


class CategoryValidationSuite:
    """Validation suite for semantic categorization system."""

    def __init__(self, registry: CategoryRegistry) -> None:
        """Initialize with a CategoryRegistry instance."""
        self.registry = registry

    def test_semantic_consistency(self, code_samples: dict[str, list[str]]) -> bool:
        """Test that semantically similar code gets same core categories across languages."""
        # Implementation would test code samples across languages
        raise NotImplementedError

    def test_ai_performance(
        self, benchmark_tasks: Sequence[AgentTask]
    ) -> dict[AgentTask, NonNegativeFloat]:
        """Test AgentTask performance with current vs. alternative categorizations."""
        # Implementation would A/B test different categorization schemes
        raise NotImplementedError

    def test_coverage(self, language_samples: dict[SemanticSearchLanguage, str]) -> CoverageReport:
        """Test that all language constructs have appropriate categories."""
        # Implementation would ensure comprehensive coverage
        raise NotImplementedError

    def validate_importance_scores(self, usage_data: UsageMetrics) -> ScoreValidation:
        """Validate importance scores against real usage patterns."""
        # Implementation would correlate scores with actual AI assistant performance
        raise NotImplementedError


# =============================================================================
# Example Language Extensions
# =============================================================================

# Example: Rust-specific extensions
RUST_DEFINITION_TRAIT_IMPL = SemanticNodeCategory.add_language_member(
    SemanticSearchLanguage.RUST,
    SemanticCategoryDict(
        name="RUST_DEFINITION_TRAIT_IMPL",
        description="Rust trait implementations",
        tier=SemanticTier.STRUCTURAL_DEFINITIONS,
        parent_category="DEFINITION_TYPE",
        language_specific=True,
        language=SemanticSearchLanguage.RUST,
        importance_scores=ContextWeightDict(
            discovery=0.90,
            comprehension=0.85,
            modification=0.88,
            debugging=0.70,
            documentation=0.85,
        ),
        examples=("impl blocks", "trait implementations"),
    ),
)

RUST_ANNOTATION_LIFETIME = SemanticNodeCategory.add_language_member(
    SemanticSearchLanguage.RUST,
    SemanticCategoryDict(
        name="RUST_ANNOTATION_LIFETIME",
        description="Rust lifetime annotations",
        tier=SemanticTier.STRUCTURAL_DEFINITIONS,
        parent_category="DEFINITION_TYPE",
        language_specific=True,
        language=SemanticSearchLanguage.RUST,
        importance_scores=ContextWeightDict(
            discovery=0.90,
            comprehension=0.85,
            modification=0.88,
            debugging=0.70,
            documentation=0.85,
        ),
        examples=("lifetime parameters", "lifetime bounds"),
    ),
)

RUST_EXTENSIONS = {
    RUST_DEFINITION_TRAIT_IMPL.name: RUST_DEFINITION_TRAIT_IMPL,
    RUST_ANNOTATION_LIFETIME.name: RUST_ANNOTATION_LIFETIME,
}

REACT_DEFINITION_COMPONENT = SemanticNodeCategory.add_language_member(
    SemanticSearchLanguage.JSX,
    SemanticCategoryDict(
        name="REACT_DEFINITION_COMPONENT",
        description="React component definitions",
        tier=SemanticTier.STRUCTURAL_DEFINITIONS,
        parent_category="DEFINITION_CALLABLE",
        language_specific=True,
        language=SemanticSearchLanguage.JSX,
        importance_scores=ContextWeightDict(
            discovery=0.95,
            comprehension=0.90,
            modification=0.85,
            debugging=0.75,
            documentation=0.90,
        ),
        examples=("function components", "class components", "component definitions"),
    ),
)

REACT_OPERATION_HOOK = SemanticNodeCategory.add_language_member(
    SemanticSearchLanguage.JSX,
    SemanticCategoryDict(
        name="REACT_OPERATION_HOOK",
        description="React hook usage",
        tier=SemanticTier.OPERATIONS_EXPRESSIONS,
        parent_category="OPERATION_INVOCATION",
        language_specific=True,
        language=SemanticSearchLanguage.JSX,
        importance_scores=ContextWeightDict(
            discovery=0.70,
            comprehension=0.80,
            modification=0.75,
            debugging=0.85,
            documentation=0.70,
        ),
        examples=("useState calls", "useEffect calls", "custom hook usage"),
    ),
)

REACT_EXTENSIONS = {
    REACT_DEFINITION_COMPONENT.name: REACT_DEFINITION_COMPONENT,
    REACT_OPERATION_HOOK.name: REACT_OPERATION_HOOK,
}

TSX_REACT = [
    SemanticNodeCategory.add_language_member(
        SemanticSearchLanguage.TSX,
        REACT_DEFINITION_COMPONENT.category.model_copy(
            update={"language": SemanticSearchLanguage.TSX}
        ),
    ),
    SemanticNodeCategory.add_language_member(
        SemanticSearchLanguage.TSX,
        REACT_OPERATION_HOOK.category.model_copy(update={"language": SemanticSearchLanguage.TSX}),
    ),
]

TSX_REACT_EXTENSIONS = {cat.name: cat for cat in TSX_REACT}

# =============================================================================
# Factory and Setup Functions
# =============================================================================


def create_default_registry() -> CategoryRegistry:
    """Create a CategoryRegistry with all core categories registered."""
    registry = CategoryRegistry()

    # Core categories are in the class definition

    # Register example extensions
    for category in RUST_EXTENSIONS.values():
        registry.register_extension("rust", category.category)

    for category in REACT_EXTENSIONS.values():
        registry.register_extension("javascript", category.category)
        registry.register_extension("typescript", category.category)
        registry.register_extension("jsx", category.category)
        registry.register_extension("tsx", category.category)

    return registry


if __name__ == "__main__":
    # Example usage
    registry = create_default_registry()

    # Test categorization
    rust_impl = registry.categorize_node("impl_item", "rust")
    function_def = registry.categorize_node("function_definition", "python")

    print(f"Rust impl categorized as: {rust_impl.name if rust_impl else 'Unknown'}")
    print(f"Python function categorized as: {function_def.name if function_def else 'Unknown'}")

    # Test context-aware scoring
    if function_def:
        completion_score = function_def.get_composite_score("code_completion")
        debugging_score = function_def.get_composite_score("debugging")
        print(f"Function completion score: {completion_score:.2f}")
        print(f"Function debugging score: {debugging_score:.2f}")
