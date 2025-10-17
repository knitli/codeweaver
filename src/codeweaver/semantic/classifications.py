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
from typing import TYPE_CHECKING, Annotated, Any, Self, TypedDict, Unpack, cast

import textcase

from pydantic import (
    Field,
    FieldSerializationInfo,
    GetCoreSchemaHandler,
    NonNegativeFloat,
    NonNegativeInt,
    PositiveFloat,
    ValidatorFunctionWrapHandler,
    computed_field,
    field_serializer,
    field_validator,
)
from pydantic.dataclasses import dataclass
from pydantic_core import ArgsKwargs, core_schema

from codeweaver._common import DATACLASS_CONFIG, BasedModel, BaseEnum, DataclassSerializationMixin
from codeweaver.language import SemanticSearchLanguage


if TYPE_CHECKING:
    from codeweaver.semantic.grammar_things import TokenPurpose


# =============================================================================
# Core Data Structures
# =============================================================================


class ImportanceScoresDict(TypedDict):
    """Typed dictionary for context weights in AI assistant scenarios.

    `ImportanceScoresDict` is the python-serialized and mutable version of `ImportanceScores`.
    """

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


@dataclass(frozen=True, config=DATACLASS_CONFIG)
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

    def weighted_score(self, context_weights: ImportanceScoresDict) -> PositiveFloat:
        """Calculate weighted importance score for given AI assistant context."""
        return (
            self.discovery * context_weights["discovery"]
            + self.comprehension * context_weights["comprehension"]
            + self.modification * context_weights["modification"]
            + self.debugging * context_weights["debugging"]
            + self.documentation * context_weights["documentation"]
        )

    def as_dict(self) -> ImportanceScoresDict:
        """Convert importance scores to a dictionary format."""
        return ImportanceScoresDict(**self.dump_python())

    @classmethod
    def from_dict(cls, **data: Unpack[ImportanceScoresDict]) -> Self:
        """Create ImportanceScores from a dictionary format."""
        return cls.validate_python(data=data)  # pyright: ignore[reportArgumentType]


class ImportanceRank(int, BaseEnum):
    """Semantic importance rankings from highest to lowest priority.

    These are general guidelines. The actual importance depends on the task and context, but these serve as a useful baseline.
    """

    PRIMARY_DEFINITIONS = 1  # Core code structures
    BEHAVIORAL_CONTRACTS = 2  # Interfaces and boundaries
    CONTROL_FLOW_LOGIC = 3  # Execution flow control
    OPERATIONS_EXPRESSIONS = 4  # Data operations and computations
    SYNTAX_REFERENCES = 5  # Literals and syntax elements

    @property
    def semantic_classifications(self) -> tuple[SemanticClass, ...]:
        """Get all semantic classifications in this rank."""
        return tuple(node for node, rank in SemanticClass.rank_map().items() if rank == self)

    @classmethod
    def from_classification(cls, classification: SemanticClass | str) -> ImportanceRank:
        """Get semantic importance rank for a given classification."""
        if not isinstance(classification, SemanticClass):
            classification = SemanticClass.from_string(classification)
        return classification.rank or next(
            rank for rank in cls if classification in rank.semantic_classifications
        )

    @classmethod
    def from_token_purpose(cls, purpose: TokenPurpose) -> ImportanceRank:
        """Map token purpose to an approximate importance rank."""
        from codeweaver.semantic.grammar_things import TokenPurpose

        if purpose == TokenPurpose.OPERATOR:
            return ImportanceRank.OPERATIONS_EXPRESSIONS
        return ImportanceRank.SYNTAX_REFERENCES


class SemanticCategoryDict(TypedDict):
    """Typed dictionary for semantic category definitions."""

    name: Annotated[
        SemanticClass | str,
        Field(description="Category identifier", pattern=r"^[A-Z][A-Z0-9_]+$", max_length=50),
    ]
    description: Annotated[str, Field(description="Human-friendly description")]
    rank: Annotated[int, Field(description="Importance rank")]
    importance_scores: Annotated[ImportanceScoresDict, Field(description="Importance scores")]
    parent_classification: Annotated[
        SemanticClass | None,
        Field(description="Parent category identifier, used for language-specific categories"),
    ]
    language_specific: Annotated[bool, Field(description="Is language-specific")]
    language: Annotated[
        SemanticSearchLanguage | str | None, Field(description="Programming language")
    ]
    examples: tuple[str, ...]


class ThingClass(BasedModel):
    """Universal semantic category for AST nodes."""

    name: Annotated[SemanticClass, Field(description="Category identifier")]
    description: Annotated[str, Field(description="Human-readable description")]
    rank: Annotated[ImportanceRank, Field(description="Importance rank")]
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
        with contextlib.suppress(KeyError, AttributeError, ValueError):
            if not self.name.category:
                SemanticClass._update_categories(self)  # pyright: ignore[reportPrivateUsage]
            if not self.name.rank:
                SemanticClass._update_rank_map(self)  # pyright: ignore[reportPrivateUsage]

    @field_validator("name", mode="before")
    @classmethod
    def validate_name(cls, v: str | SemanticClass) -> SemanticClass:
        """Ensure name is a SemanticClass."""
        if isinstance(v, SemanticClass):
            return v
        with contextlib.suppress(ValueError, AttributeError):
            return SemanticClass.from_string(v)
        return SemanticClass.add_member(textcase.upper(v), textcase.snake(v))

    @field_validator("importance_scores", mode="before")
    @classmethod
    def validate_importance_scores(
        cls, v: ImportanceScoresDict | ImportanceScores
    ) -> ImportanceScores:
        """Ensure importance_scores is a ImportanceScoresDict."""
        return (
            ImportanceScores.validate_python(cast(dict[str, Any], v)) if isinstance(v, dict) else v
        )

    def is_extension_of(self, core_category: str) -> bool:
        """Check if this category extends a core category."""
        return self.parent_category == core_category

    def get_composite_score(self, context: str = "default") -> float:
        """Get composite importance score for specific context."""
        context_weights = AgentTask.profiles().get(
            AgentTask.from_string(context), AgentTask.DEFAULT.profile
        )
        return self.importance_scores.weighted_score(context_weights)


class SemanticClass(str, BaseEnum):
    """Language-agnostic semantic categories for AST nodes."""

    # Tier 1: Structural Definitions
    DEFINITION_CALLABLE = "definition_callable"
    """Named function and method definitions with explicit declarations. Excludes anonymous functions, lambdas, and inline expressions."""
    DEFINITION_TYPE = "definition_type"
    """Type and class definitions including classes, structs, interfaces, traits, generics, and type aliases. Excludes type usage and instantiation."""
    DEFINITION_DATA = "definition_data"
    """Named data declarations including enums, module-level constants, configuration schemas, and static data structures. Excludes literal values and runtime assignments."""
    DEFINITION_TEST = "definition_test"
    """Test function definitions, test case declarations, test suites, and testing framework constructs. Excludes assertion statements and test execution calls."""

    # Tier 2: Behavioral Contracts
    BOUNDARY_MODULE = "boundary_module"
    """Imports, exports, namespaces, package declarations"""
    BOUNDARY_ERROR = "boundary_error"
    """Error type definitions, exception class declarations, and error boundary specifications. Excludes throw/catch statements and error control flow."""
    BOUNDARY_RESOURCE = "boundary_resource"
    """Resource acquisition and lifecycle declarations including file handles, database connections, memory allocators, and cleanup specifications. Excludes resource usage and operations."""
    DOCUMENTATION_STRUCTURED = "documentation_structured"
    """Structured documentation with formal syntax including API documentation, docstrings, JSDoc comments, and contract specifications. Excludes regular comments and inline annotations."""

    # Tier 3: Control Flow & Logic
    FLOW_BRANCHING = "flow_branching"
    """Branching control flow structures (if, switch)"""
    FLOW_ITERATION = "flow_iteration"
    """Iteration control flow structures (for, while)"""
    FLOW_CONTROL = "flow_control"
    """Explicit control flow statements including return, break, continue, and goto statements. Excludes exception throwing and error handling."""
    FLOW_ASYNC = "flow_async"
    """Asynchronous control flow structures (async, await)"""

    # Tier 4: Operations & Expressions
    OPERATION_INVOCATION = "operation_invocation"
    """Function/method invocation expressions"""
    OPERATION_DATA = "operation_data"
    """Variable assignments, property access, field modifications, and data structure operations. Excludes mathematical computations and logical operations."""
    OPERATION_OPERATOR = "operation_computation"
    """Mathematical and logical computation operations, including arithmetic, comparisons, and boolean logic and use of operator literals. Excludes data structure manipulations and assignments (OPERATION_DATA) where we can distinguish them. Because some data structure manipulations use operators, OPERATION_DATA may sometimes be misclassified as OPERATION_OPERATOR."""
    EXPRESSION_ANONYMOUS = "expression_anonymous"
    """Anonymous function expressions including lambdas, closures, arrow functions, and inline function literals. Excludes named function declarations."""

    # Tier 5: Syntax & References
    SYNTAX_KEYWORD = "syntax_keyword"
    """Language keywords and reserved words, including type keywords like 'int', 'string', 'class', 'def', etc."""
    SYNTAX_IDENTIFIER = "syntax_identifier"
    """Identifiers and references (variables)"""
    SYNTAX_LITERAL = "syntax_literal"
    """Literal values (strings, numbers, booleans)"""
    SYNTAX_ANNOTATION = "syntax_annotation"
    """Metadata annotations including decorators, attributes, pragmas, and compiler directives. Excludes type annotations and regular comments. More significant decorators (like in Python) will be classified as SYNTAX_KEYWORD"""
    SYNTAX_PUNCTUATION = "syntax_punctuation"
    """Punctuation syntax elements (braces, parentheses, punctuation)"""

    __slots__ = ()

    @property
    def simple_rank(self) -> int:
        """Get a simple integer rank for this category (lower is more important)."""
        return {member: idx for idx, member in enumerate(type(self), start=1)}[self]

    @classmethod
    def from_token_purpose(cls, purpose: TokenPurpose, token_name: str) -> SemanticClass:
        """Map token purpose to an approximate semantic category."""
        from codeweaver.semantic._constants import IS_ANNOTATION
        from codeweaver.semantic.grammar_things import TokenPurpose

        if (purpose == TokenPurpose.COMMENT and token_name == "line_comment") or (  # noqa: S105
            purpose == TokenPurpose.KEYWORD and IS_ANNOTATION.match(token_name)
        ):
            return cls.SYNTAX_ANNOTATION
        if (
            purpose == TokenPurpose.COMMENT
        ):  # we have to assume anything else is a doc/function/method/class comment
            # With actual text analysis we can further reduce false positives here
            return cls.DOCUMENTATION_STRUCTURED
        return {
            TokenPurpose.IDENTIFIER: cls.SYNTAX_IDENTIFIER,
            TokenPurpose.LITERAL: cls.SYNTAX_LITERAL,
            TokenPurpose.OPERATOR: cls.OPERATION_OPERATOR,
            TokenPurpose.KEYWORD: cls.SYNTAX_KEYWORD,
            TokenPurpose.PUNCTUATION: cls.SYNTAX_PUNCTUATION,
        }[purpose]

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
    def rank(self) -> ImportanceRank:
        """Get the semantic rank for this category."""
        return self.rank_map().get(self, ImportanceRank.SYNTAX_REFERENCES)

    @classmethod
    def rank_map(cls) -> MappingProxyType[SemanticClass, ImportanceRank]:
        """Get mapping of categories to their semantic ranks."""
        if not hasattr(cls, "_rank_map_cache"):
            cls._rank_map_cache = cls._rank_map()
        return cls._rank_map_cache

    @classmethod
    def _rank_map(cls) -> MappingProxyType[SemanticClass, ImportanceRank]:
        """Get mapping of categories to their semantic ranks."""
        return MappingProxyType({
            # Top priority definitions
            cls.DEFINITION_CALLABLE: ImportanceRank.PRIMARY_DEFINITIONS,
            cls.DEFINITION_TYPE: ImportanceRank.PRIMARY_DEFINITIONS,
            cls.DEFINITION_DATA: ImportanceRank.PRIMARY_DEFINITIONS,
            cls.DEFINITION_TEST: ImportanceRank.PRIMARY_DEFINITIONS,
            # Behavioral contracts and boundaries (rank 2)
            cls.BOUNDARY_MODULE: ImportanceRank.BEHAVIORAL_CONTRACTS,
            cls.BOUNDARY_ERROR: ImportanceRank.BEHAVIORAL_CONTRACTS,
            cls.BOUNDARY_RESOURCE: ImportanceRank.BEHAVIORAL_CONTRACTS,
            cls.DOCUMENTATION_STRUCTURED: ImportanceRank.BEHAVIORAL_CONTRACTS,
            # Control flow and logic (rank 3)
            cls.FLOW_BRANCHING: ImportanceRank.CONTROL_FLOW_LOGIC,
            cls.FLOW_ITERATION: ImportanceRank.CONTROL_FLOW_LOGIC,
            cls.FLOW_CONTROL: ImportanceRank.CONTROL_FLOW_LOGIC,
            cls.FLOW_ASYNC: ImportanceRank.CONTROL_FLOW_LOGIC,
            # Operations and expressions (rank 4)
            cls.OPERATION_INVOCATION: ImportanceRank.OPERATIONS_EXPRESSIONS,
            cls.OPERATION_DATA: ImportanceRank.OPERATIONS_EXPRESSIONS,
            cls.OPERATION_OPERATOR: ImportanceRank.OPERATIONS_EXPRESSIONS,
            cls.EXPRESSION_ANONYMOUS: ImportanceRank.OPERATIONS_EXPRESSIONS,
            # Syntax and references (rank 5 - lowest priority)
            cls.SYNTAX_IDENTIFIER: ImportanceRank.SYNTAX_REFERENCES,
            cls.SYNTAX_LITERAL: ImportanceRank.SYNTAX_REFERENCES,
            cls.SYNTAX_ANNOTATION: ImportanceRank.SYNTAX_REFERENCES,
            cls.SYNTAX_PUNCTUATION: ImportanceRank.SYNTAX_REFERENCES,
        })

    @classmethod
    def categories(cls) -> MappingProxyType[SemanticClass, ThingClass]:
        """Get mapping of categories to their ThingClass definitions."""
        if not hasattr(cls, "_categories_cache"):
            cls._categories_cache = cls._categories()
        return cls._categories_cache

    @classmethod
    def _categories(cls) -> MappingProxyType[SemanticClass, ThingClass]:
        """Get mapping of categories to their ThingClass definitions."""
        return MappingProxyType({
            cls.DEFINITION_CALLABLE: ThingClass(
                name=cls.DEFINITION_CALLABLE,
                description="Named function and method definitions with explicit declarations",
                rank=ImportanceRank.PRIMARY_DEFINITIONS,
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
                    "class constructors",
                    "procedure declarations",
                ),
            ),
            cls.DEFINITION_TYPE: ThingClass(
                name=cls.DEFINITION_TYPE,
                description="Type and class definitions including classes, structs, interfaces, traits, generics, and type aliases",
                rank=ImportanceRank.PRIMARY_DEFINITIONS,
                importance_scores=ImportanceScores(
                    discovery=0.95,
                    comprehension=0.92,
                    modification=0.90,
                    debugging=0.80,
                    documentation=0.92,
                ),
                examples=(
                    "class definitions",
                    "interface declarations",
                    "struct definitions",
                    "generic type parameters",
                    "type aliases",
                ),
            ),
            cls.DEFINITION_DATA: ThingClass(
                name=cls.DEFINITION_DATA,
                description="Named data declarations including enums, module-level constants, configuration schemas, and static data structures",
                rank=ImportanceRank.PRIMARY_DEFINITIONS,
                importance_scores=ImportanceScores(
                    discovery=0.85,
                    comprehension=0.88,
                    modification=0.80,
                    debugging=0.65,
                    documentation=0.90,
                ),
                examples=(
                    "enum definitions",
                    "const/final declarations",
                    "JSON schemas",
                    "static data tables",
                    "module exports",
                ),
            ),
            cls.DEFINITION_TEST: ThingClass(
                name=cls.DEFINITION_TEST,
                description="Test function definitions, test case declarations, test suites, and testing framework constructs",
                rank=ImportanceRank.PRIMARY_DEFINITIONS,
                importance_scores=ImportanceScores(
                    discovery=0.88,
                    comprehension=0.90,
                    modification=0.70,
                    debugging=0.90,
                    documentation=0.85,
                ),
                examples=(
                    "test functions",
                    "test suite definitions",
                    "describe/it blocks",
                    "@Test annotations",
                    "fixture definitions",
                ),
            ),
            cls.BOUNDARY_MODULE: ThingClass(
                name=cls.BOUNDARY_MODULE,
                description="Module boundary declarations including imports, exports, namespaces, and package specifications",
                rank=ImportanceRank.BEHAVIORAL_CONTRACTS,
                importance_scores=ImportanceScores(
                    discovery=0.85,
                    comprehension=0.80,
                    modification=0.85,
                    debugging=0.60,
                    documentation=0.75,
                ),
                examples=(
                    "import statements",
                    "export declarations",
                    "namespace definitions",
                    "package declarations",
                    "module specifications",
                    "using directives",
                ),
            ),
            cls.BOUNDARY_ERROR: ThingClass(
                name=cls.BOUNDARY_ERROR,
                description="Error type definitions, exception class declarations, and error boundary specifications",
                rank=ImportanceRank.BEHAVIORAL_CONTRACTS,
                importance_scores=ImportanceScores(
                    discovery=0.70,
                    comprehension=0.85,
                    modification=0.75,
                    debugging=0.95,
                    documentation=0.70,
                ),
                examples=(
                    "exception class definitions",
                    "error type declarations",
                    "error boundary components",
                    "custom error constructors",
                ),
            ),
            cls.BOUNDARY_RESOURCE: ThingClass(
                name=cls.BOUNDARY_RESOURCE,
                description="Resource acquisition and lifecycle declarations including file handles, database connections, memory allocators, and cleanup specifications",
                rank=ImportanceRank.BEHAVIORAL_CONTRACTS,
                importance_scores=ImportanceScores(
                    discovery=0.65,
                    comprehension=0.80,
                    modification=0.80,
                    debugging=0.90,
                    documentation=0.65,
                ),
                examples=(
                    "file handle declarations",
                    "database connection pools",
                    "memory allocator definitions",
                    "context manager protocols",
                    "resource cleanup specifications",
                ),
            ),
            cls.DOCUMENTATION_STRUCTURED: ThingClass(
                name=cls.DOCUMENTATION_STRUCTURED,
                description="Structured documentation with formal syntax including API documentation, docstrings, JSDoc comments, and contract specifications",
                rank=ImportanceRank.BEHAVIORAL_CONTRACTS,
                importance_scores=ImportanceScores(
                    discovery=0.55,
                    comprehension=0.75,
                    modification=0.50,
                    debugging=0.40,
                    documentation=0.95,
                ),
                examples=(
                    "JSDoc function documentation",
                    "Python docstrings",
                    "Rust doc comments (///)",
                    "API contract specifications",
                    "OpenAPI documentation",
                ),
            ),
            cls.FLOW_BRANCHING: ThingClass(
                name=cls.FLOW_BRANCHING,
                description="Conditional and pattern-based control flow including if statements, switch expressions, and pattern matching",
                rank=ImportanceRank.CONTROL_FLOW_LOGIC,
                importance_scores=ImportanceScores(
                    discovery=0.60,
                    comprehension=0.75,
                    modification=0.65,
                    debugging=0.90,
                    documentation=0.50,
                ),
                examples=(
                    "if/else statements",
                    "switch/case statements",
                    "match expressions",
                    "pattern matching",
                    "conditional expressions (ternary)",
                ),
            ),
            cls.FLOW_ITERATION: ThingClass(
                name=cls.FLOW_ITERATION,
                description="Iterative control flow including loops and iteration constructs",
                rank=ImportanceRank.CONTROL_FLOW_LOGIC,
                importance_scores=ImportanceScores(
                    discovery=0.50,
                    comprehension=0.70,
                    modification=0.65,
                    debugging=0.80,
                    documentation=0.45,
                ),
                examples=(
                    "for loops",
                    "while loops",
                    "do-while loops",
                    "foreach/for-in loops",
                    "loop comprehensions",
                ),
            ),
            cls.FLOW_CONTROL: ThingClass(
                name=cls.FLOW_CONTROL,
                description="Explicit control flow statements including return, break, continue, and goto statements",
                rank=ImportanceRank.CONTROL_FLOW_LOGIC,
                importance_scores=ImportanceScores(
                    discovery=0.45,
                    comprehension=0.65,
                    modification=0.55,
                    debugging=0.90,
                    documentation=0.35,
                ),
                examples=(
                    "return statements",
                    "break statements",
                    "continue statements",
                    "goto labels",
                    "yield statements",
                ),
            ),
            cls.FLOW_ASYNC: ThingClass(
                name=cls.FLOW_ASYNC,
                description="Asynchronous control flow including async/await expressions, futures, promises, and coroutine constructs",
                rank=ImportanceRank.CONTROL_FLOW_LOGIC,
                importance_scores=ImportanceScores(
                    discovery=0.65,
                    comprehension=0.80,
                    modification=0.75,
                    debugging=0.85,
                    documentation=0.60,
                ),
                examples=(
                    "async function declarations",
                    "await expressions",
                    "promise chains",
                    "coroutine definitions",
                    "parallel execution blocks",
                ),
            ),
            cls.OPERATION_INVOCATION: ThingClass(
                name=cls.OPERATION_INVOCATION,
                description="Function and method invocations including calls, constructor invocations, and operator calls",
                rank=ImportanceRank.OPERATIONS_EXPRESSIONS,
                importance_scores=ImportanceScores(
                    discovery=0.45,
                    comprehension=0.65,
                    modification=0.45,
                    debugging=0.75,
                    documentation=0.25,
                ),
                examples=(
                    "function calls (func())",
                    "method invocations (obj.method())",
                    "constructor calls (new Class())",
                    "operator overload calls",
                    "macro invocations",
                ),
            ),
            cls.OPERATION_DATA: ThingClass(
                name=cls.OPERATION_DATA,
                description="Variable assignments, property access, field modifications, and data structure operations",
                rank=ImportanceRank.OPERATIONS_EXPRESSIONS,
                importance_scores=ImportanceScores(
                    discovery=0.35,
                    comprehension=0.55,
                    modification=0.50,
                    debugging=0.70,
                    documentation=0.25,
                ),
                examples=(
                    "variable assignments",
                    "property access (obj.prop)",
                    "field modifications",
                    "array/object indexing",
                    "destructuring assignments",
                ),
            ),
            cls.OPERATION_OPERATOR: ThingClass(
                name=cls.OPERATION_OPERATOR,
                description="Mathematical and logical computation operations including arithmetic, comparisons, and boolean logic",
                rank=ImportanceRank.OPERATIONS_EXPRESSIONS,
                importance_scores=ImportanceScores(
                    discovery=0.25,
                    comprehension=0.45,
                    modification=0.35,
                    debugging=0.60,
                    documentation=0.25,
                ),
                examples=(
                    "arithmetic operations (+, -, *, /)",
                    "comparison operations (==, <, >)",
                    "logical operations (&&, ||, !)",
                    "bitwise operations (&, |, ^)",
                    "mathematical functions",
                ),
            ),
            cls.EXPRESSION_ANONYMOUS: ThingClass(
                name=cls.EXPRESSION_ANONYMOUS,
                description="Anonymous function expressions including lambdas, closures, arrow functions, and inline function literals",
                rank=ImportanceRank.OPERATIONS_EXPRESSIONS,
                importance_scores=ImportanceScores(
                    discovery=0.40,
                    comprehension=0.65,
                    modification=0.50,
                    debugging=0.60,
                    documentation=0.45,
                ),
                examples=(
                    "lambda expressions (λ)",
                    "arrow functions (=>)",
                    "inline closures",
                    "anonymous function literals",
                    "function expressions",
                ),
            ),
            cls.SYNTAX_IDENTIFIER: ThingClass(
                name=cls.SYNTAX_IDENTIFIER,
                description="Variable names, type names, and symbol references excluding literals and operators",
                rank=ImportanceRank.SYNTAX_REFERENCES,
                importance_scores=ImportanceScores(
                    discovery=0.25,
                    comprehension=0.40,
                    modification=0.25,
                    debugging=0.45,
                    documentation=0.20,
                ),
                examples=(
                    "variable names",
                    "type references",
                    "function name references",
                    "module/namespace references",
                    "symbol identifiers",
                ),
            ),
            cls.SYNTAX_LITERAL: ThingClass(
                name=cls.SYNTAX_LITERAL,
                description="Literal constant values including strings, numbers, booleans, and null values",
                rank=ImportanceRank.SYNTAX_REFERENCES,
                importance_scores=ImportanceScores(
                    discovery=0.15,
                    comprehension=0.20,
                    modification=0.15,
                    debugging=0.40,
                    documentation=0.20,
                ),
                examples=(
                    'string literals ("text")',
                    "numeric literals (42, 3.14)",
                    "boolean literals (true/false)",
                    "null/undefined values",
                    "character literals ('a')",
                ),
            ),
            cls.SYNTAX_ANNOTATION: ThingClass(
                name=cls.SYNTAX_ANNOTATION,
                description="Metadata annotations including decorators, attributes, pragmas, and compiler directives",
                rank=ImportanceRank.SYNTAX_REFERENCES,
                importance_scores=ImportanceScores(
                    discovery=0.35,
                    comprehension=0.45,
                    modification=0.60,
                    debugging=0.40,
                    documentation=0.40,
                ),
                examples=(
                    "Python decorators (@decorator)",
                    "Java annotations (@Override)",
                    "C# attributes ([Attribute])",
                    "Rust attributes (#[derive])",
                    "compiler pragmas (#pragma)",
                ),
            ),
            cls.SYNTAX_PUNCTUATION: ThingClass(
                name=cls.SYNTAX_PUNCTUATION,
                description="Structural syntax elements including braces, parentheses, delimiters, and punctuation marks",
                rank=ImportanceRank.SYNTAX_REFERENCES,
                importance_scores=ImportanceScores(
                    discovery=0.01,
                    comprehension=0.02,
                    modification=0.15,
                    debugging=0.20,
                    documentation=0.05,
                ),
                examples=(
                    "braces ({ })",
                    "parentheses (( ))",
                    "brackets ([ ])",
                    "semicolons (;)",
                    "commas (,)",
                    "angle brackets (< >)",
                ),
            ),
        })

    @classmethod
    def _update_categories(cls, category: ThingClass) -> None:
        """Internal method to update categories mapping."""
        new_categories = MappingProxyType({**cls.categories(), category.name: category})
        cls._categories_cache = new_categories

    @classmethod
    def _update_rank_map(cls, category: ThingClass) -> None:
        """Internal method to update rank mapping."""
        new_rank_map = MappingProxyType({**cls.rank_map(), category.name: category.rank})
        cls._rank_map_cache = new_rank_map

    @property
    def category(self) -> ThingClass:
        """Get the ThingClass definition for this category."""
        return self.categories()[self]

    @classmethod
    def add_language_member(
        cls, language: SemanticSearchLanguage | str, category: ThingClass | SemanticCategoryDict
    ) -> SemanticClass:
        """Add a new language-specific semantic category."""
        if not isinstance(language, SemanticSearchLanguage):
            language = SemanticSearchLanguage.from_string(language)
        if isinstance(category, dict):
            category["language"] = language
            category = ThingClass.model_validate(category)
        if not category.language_specific:
            raise ValueError("Only language-specific categories can be added.")
        member_name = f"{language.name.upper()}_{category.name}"
        new_member = cls.add_member(member_name, textcase.snake(member_name))
        category = category.model_copy(update={"name": new_member})
        cls._update_categories(category)
        cls._update_rank_map(category)
        return new_member


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
    def profiles(cls) -> MappingProxyType[AgentTask, ImportanceScoresDict]:
        """Get list of available context weight profiles."""
        return MappingProxyType({
            cls.LOCAL_EDIT: ImportanceScoresDict(
                discovery=0.4,
                comprehension=0.3,
                modification=0.2,
                debugging=0.05,
                documentation=0.05,
            ),
            cls.DEBUG: ImportanceScoresDict(
                discovery=0.2,
                comprehension=0.3,
                modification=0.1,
                debugging=0.35,
                documentation=0.05,
            ),
            cls.REFACTOR: ImportanceScoresDict(
                discovery=0.15,
                comprehension=0.25,
                modification=0.45,
                debugging=0.1,
                documentation=0.05,
            ),
            cls.DOCUMENT: ImportanceScoresDict(
                discovery=0.2,
                comprehension=0.2,
                modification=0.1,
                debugging=0.05,
                documentation=0.45,
            ),
            cls.SEARCH: ImportanceScoresDict(
                discovery=0.5,
                comprehension=0.2,
                modification=0.15,
                debugging=0.1,
                documentation=0.05,
            ),
            cls.IMPLEMENT: ImportanceScoresDict(
                discovery=0.3,
                comprehension=0.3,
                modification=0.25,
                debugging=0.1,
                documentation=0.05,
            ),
            cls.REVIEW: ImportanceScoresDict(
                discovery=0.25,
                comprehension=0.35,
                modification=0.15,
                debugging=0.15,
                documentation=0.1,
            ),
            cls.DEFAULT: ImportanceScoresDict(
                discovery=0.25,
                comprehension=0.25,
                modification=0.2,
                debugging=0.15,
                documentation=0.15,
            ),
        })

    @property
    def profile(self) -> ImportanceScoresDict:
        """Get the context weight profile for this task."""
        return self.profiles().get(self, self.profiles()[self.DEFAULT])


# =============================================================================
# Extension System for Language-Specific Categories
# =============================================================================


def _validate_categories(
    value: Any, nxt: ValidatorFunctionWrapHandler, _info: core_schema.ValidationInfo
) -> Any:
    """Validate core categories for JSON input."""
    if (
        isinstance(value, ArgsKwargs)
        and hasattr(value.args, "__len__")
        and len(value.args) == 3
        and value.args[0] == {}
        and value.args[1] == {}
        and isinstance(value.args[2], MappingProxyType | dict)
    ):
        return (
            value.args[0],
            value.args[1],
            MappingProxyType(
                nxt(
                    dict(value.args[2])  # type: ignore
                    if isinstance(value.args[2], MappingProxyType)
                    else value.args[2]
                )
            ),
        )  # type: ignore
    if isinstance(value, MappingProxyType) and all(
        isinstance(k, SemanticClass) and isinstance(v, ThingClass)
        for k, v in value.items()  # type: ignore
        if k and v  # type: ignore
    ):
        return value  # type: ignore
    if isinstance(value, MappingProxyType | dict):
        return MappingProxyType(nxt(dict(value) if isinstance(value, MappingProxyType) else value))  # type: ignore
    if isinstance(value, str | bytes | bytearray):
        return _validate_categories(nxt(value), nxt, _info)
    raise ValueError("Invalid type for core_categories")


@dataclass(config=DATACLASS_CONFIG)
class ClassificationRegistry(DataclassSerializationMixin):
    """Registry for core and language-specific semantic categories."""

    _extensions: Annotated[
        dict[SemanticSearchLanguage, dict[SemanticClass, ThingClass]],
        Field(
            default_factory=dict, description="Language-specific category extensions", init=False
        ),
    ]
    _mappings: Annotated[
        dict[SemanticSearchLanguage, dict[str, SemanticClass]],
        Field(
            default_factory=dict,
            description="Language-specific mappings from node types to categories",
            init=False,
        ),
    ]

    _core_categories: Annotated[
        MappingProxyType[SemanticClass, ThingClass],
        Field(
            default_factory=SemanticClass.categories,
            description="Core semantic categories",
            init=False,
        ),
    ]

    def __post_init__(self) -> None:
        """Setup the category registry."""
        self._extensions: dict[SemanticSearchLanguage, dict[SemanticClass, ThingClass]] = {}
        self._mappings: dict[
            SemanticSearchLanguage, dict[str, SemanticClass]
        ] = {}  # language -> {node_type -> category}

    def register_core(
        self, category: ThingClass | SemanticCategoryDict
    ) -> MappingProxyType[SemanticClass, ThingClass]:
        """Register a new core category."""
        if isinstance(category, dict):
            if category.get("language_specific", False):
                raise ValueError("Core categories cannot be language-specific.")
            if category.get("language") is not None:
                raise ValueError("Core categories cannot have a specific language.")
            category = ThingClass.model_validate(category)
        if not isinstance(category.name, SemanticClass):  # type: ignore
            node = SemanticClass.add_member(category.name.upper(), textcase.snake(category.name))
            category = category.model_copy(update={"name": node})
            SemanticClass._update_categories(category)  # pyright: ignore[reportPrivateUsage]
            SemanticClass._update_rank_map(category)  # pyright: ignore[reportPrivateUsage]
        self._core_categories = SemanticClass.categories()
        return self._core_categories

    def register_extension(
        self, language: str | SemanticSearchLanguage, category: ThingClass | SemanticCategoryDict
    ) -> None:
        """Register a language-specific extension category."""
        if not hasattr(self, "_extensions"):
            self._extensions = {}
            self._mappings = {}
        if not isinstance(language, SemanticSearchLanguage):
            language = SemanticSearchLanguage.from_string(language)
        if language not in self._extensions:
            self._extensions[language] = {}
        if isinstance(category, dict):
            category["language"] = language
            category["language_specific"] = True
            category = ThingClass.model_validate(category)
        self._extensions[language][category.name] = category

    def register_mapping(
        self, language: SemanticSearchLanguage, node_type: str, category_name: SemanticClass
    ) -> None:
        """Register mapping from tree-sitter node type to semantic category."""
        if language not in self._mappings:
            self._mappings[language] = {}
        self._mappings[language][node_type] = category_name

    def get_category(
        self,
        category_name: str | SemanticClass,
        language: SemanticSearchLanguage | str | None = None,
    ) -> ThingClass | None:
        """Get category by name, checking language extensions first."""
        if not isinstance(language, SemanticSearchLanguage) and language is not None:
            language = SemanticSearchLanguage.from_string(language)
        if not isinstance(category_name, SemanticClass):
            category_name = SemanticClass.from_string(category_name)
        if (
            language
            and language in self._extensions
            and category_name in self._extensions[language]
        ):
            return self._extensions[language][category_name]
        return self._core_categories.get(category_name)

    def categorize_node(
        self, node_type: str, language: SemanticSearchLanguage | str
    ) -> ThingClass | None:
        """Categorize a tree-sitter node type."""
        # Check language-specific mappings first
        if not isinstance(language, SemanticSearchLanguage):
            language = SemanticSearchLanguage.from_string(language)
        if language in self._mappings and node_type in self._mappings[language]:
            category_name = self._mappings[language][node_type]
            return self.get_category(category_name, language)

        # Fallback to heuristic mapping
        return self._heuristic_categorize(node_type)

    def _heuristic_categorize(self, node_type: str) -> ThingClass | None:
        """Heuristic categorization for unmapped node types."""
        node_lower = node_type.lower()

        # Function/method patterns
        if any(pattern in node_lower for pattern in {"function", "method", "procedure", "def"}):
            return self._core_categories[SemanticClass.DEFINITION_CALLABLE]

        # Class/type patterns
        if any(pattern in node_lower for pattern in {"class", "struct", "interface", "type"}):
            return self._core_categories[SemanticClass.DEFINITION_TYPE]

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
            return self._core_categories[SemanticClass.FLOW_BRANCHING]

        # Loop patterns
        if any(pattern in node_lower for pattern in {"for", "while", "loop", "repeat"}):
            return self._core_categories[SemanticClass.FLOW_ITERATION]

        # Import/export patterns
        if any(pattern in node_lower for pattern in {"import", "export", "require", "use"}):
            return self._core_categories[SemanticClass.BOUNDARY_MODULE]

        # Default to unknown
        return None

    @classmethod
    def __get_pydantic_core_schema__(
        cls, _source: Any, _handler: GetCoreSchemaHandler
    ) -> core_schema.CoreSchema:
        """Get Pydantic core schema for ClassificationRegistry."""
        return core_schema.with_info_wrap_validator_function(
            _validate_categories,
            core_schema.dict_schema(),
            field_name="_core_categories",
            # spellchecker:off
            serialization=core_schema.plain_serializer_function_ser_schema(
                cls._serialize_core_categories,
                is_field_serializer=True,
                info_arg=True,
                when_used="json",
            ),
            # spellchecker:on
        )

    @field_serializer(
        "_core_categories",
        mode="plain",
        when_used="json",
        return_type=dict[SemanticClass, ThingClass],
    )
    def _serialize_core_categories(
        self, value: MappingProxyType[SemanticClass, ThingClass], _info: FieldSerializationInfo
    ) -> str:
        """Serialize core categories for JSON output."""
        return dict(value)  # type: ignore


# =============================================================================
# Validation and Testing Framework
# =============================================================================


@dataclass(config=DATACLASS_CONFIG)
class CoverageReport(DataclassSerializationMixin):
    """Report on coverage of semantic categories."""

    covered_categories: Sequence[SemanticClass]
    language: SemanticSearchLanguage

    @computed_field
    @cached_property
    def total_categories(self) -> int:
        """Calculate total number of categories for the language."""
        return len(self.possible_categories)

    @computed_field
    @cached_property
    def possible_categories(self) -> tuple[SemanticClass, ...]:
        """Get a list of all possible categories for the language."""
        cores = [cat for cat in SemanticClass if cat.is_core]
        cores.extend([
            cat for cat in SemanticClass if cat.is_extension and cat.for_language == self.language
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
    def uncovered_categories(self) -> tuple[SemanticClass, ...]:
        """Get a list of uncovered categories."""
        return tuple(cat for cat in self.possible_categories if cat not in self.covered_categories)


@dataclass(config=DATACLASS_CONFIG)
class UsageMetrics(DataclassSerializationMixin):
    """Metrics on real-world usage of semantic categories."""

    category_usage_counts: Counter[SemanticClass]

    @computed_field
    @property
    def total_use(self) -> NonNegativeInt:
        """Calculate total number of usages across all categories."""
        return sum(self.category_usage_counts.values())

    @computed_field
    @property
    def usage_frequencies(self) -> dict[SemanticClass, NonNegativeFloat]:
        """Calculate usage frequency for each category."""
        if self.total_use == 0:
            return dict.fromkeys(self.category_usage_counts, 0.0)
        return {
            cat: (count / self.total_use) * 100.0
            for cat, count in self.category_usage_counts.items()
        }

    def add_uses(self, categories: Sequence[SemanticClass]) -> None:
        """Add usage counts for a list of categories."""
        self.category_usage_counts.update(categories)


@dataclass(config=DATACLASS_CONFIG)
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
    def discrepancies(self) -> dict[SemanticClass, float]:
        """Identify categories with significant discrepancies."""
        # Placeholder for actual discrepancy identification
        return {}


class CategoryValidationSuite:
    """Validation suite for semantic categorization system."""

    def __init__(self, registry: ClassificationRegistry) -> None:
        """Initialize with a ClassificationRegistry instance."""
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
RUST_DEFINITION_TRAIT_IMPL = SemanticClass.add_language_member(
    SemanticSearchLanguage.RUST,
    SemanticCategoryDict(
        name="RUST_DEFINITION_TRAIT_IMPL",
        description="Rust trait implementations",
        rank=ImportanceRank.PRIMARY_DEFINITIONS,
        parent_classification=SemanticClass.DEFINITION_TYPE,
        language_specific=True,
        language=SemanticSearchLanguage.RUST,
        importance_scores=ImportanceScoresDict(
            discovery=0.90,
            comprehension=0.85,
            modification=0.88,
            debugging=0.70,
            documentation=0.85,
        ),
        examples=("impl blocks", "trait implementations"),
    ),
)

RUST_ANNOTATION_LIFETIME = SemanticClass.add_language_member(
    SemanticSearchLanguage.RUST,
    SemanticCategoryDict(
        name="RUST_ANNOTATION_LIFETIME",
        description="Rust lifetime annotations",
        rank=ImportanceRank.PRIMARY_DEFINITIONS,
        parent_classification=SemanticClass.DEFINITION_TYPE,
        language_specific=True,
        language=SemanticSearchLanguage.RUST,
        importance_scores=ImportanceScoresDict(
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

REACT_DEFINITION_COMPONENT = SemanticClass.add_language_member(
    SemanticSearchLanguage.JSX,
    SemanticCategoryDict(
        name="REACT_DEFINITION_COMPONENT",
        description="React component definitions",
        rank=ImportanceRank.PRIMARY_DEFINITIONS,
        parent_classification=SemanticClass.DEFINITION_CALLABLE,
        language_specific=True,
        language=SemanticSearchLanguage.JSX,
        importance_scores=ImportanceScoresDict(
            discovery=0.95,
            comprehension=0.90,
            modification=0.85,
            debugging=0.75,
            documentation=0.90,
        ),
        examples=("function components", "class components", "component definitions"),
    ),
)

REACT_OPERATION_HOOK = SemanticClass.add_language_member(
    SemanticSearchLanguage.JSX,
    SemanticCategoryDict(
        name="REACT_OPERATION_HOOK",
        description="React hook usage",
        rank=ImportanceRank.OPERATIONS_EXPRESSIONS,
        parent_classification=SemanticClass.OPERATION_INVOCATION,
        language_specific=True,
        language=SemanticSearchLanguage.JSX,
        importance_scores=ImportanceScoresDict(
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
    SemanticClass.add_language_member(
        SemanticSearchLanguage.TSX,
        REACT_DEFINITION_COMPONENT.category.model_copy(
            update={"language": SemanticSearchLanguage.TSX}
        ),
    ),
    SemanticClass.add_language_member(
        SemanticSearchLanguage.TSX,
        REACT_OPERATION_HOOK.category.model_copy(update={"language": SemanticSearchLanguage.TSX}),
    ),
]

TSX_REACT_EXTENSIONS = {cat.name: cat for cat in TSX_REACT}

# =============================================================================
# Factory and Setup Functions
# =============================================================================


def create_default_registry() -> ClassificationRegistry:
    """Create a ClassificationRegistry with all core categories registered."""
    registry = ClassificationRegistry({}, {}, SemanticClass.categories())

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
