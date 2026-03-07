# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Semantic node classification and importance scoring system.

The semantic package provides tools, types, and utilities for analyzing and classifying [tree-sitter](https://tree-sitter.github.io/tree-sitter/) grammars, which inform CodeWeaver's code context intelligence features. Most of the package is focused on classifying grammars (grammars are the 'what can be' of a programming language, defining its idioms, syntax and structure) into semantic classes (the 'what it means' of a programming language, defining the intent and purpose of code constructs). It provides granular mapping of grammar nodes, which we call 'things', to semantic classifications, and assigns importance based on these classifications, combined with the task at hand, their context in the actual code, and other factors.

After some frustrating experiences with Tree-Sitter's built-in node types, we decided to apply our own plain language descriptions and classifications to the structures. We hope this will help you understand and reason about code more effectively. For a complete overview of CodeWeaver's system and differences in terminology, see the module comment in `codeweaver.semantic.grammar`. //LINK - src/codeweaver/semantic/grammar.py

The package also includes serializable wrappers around `Ast-Grep`'s core types, which we use for parsing and analyzing code. These wrappers provide a more user-friendly interface for working with ASTs, add additional functionality, like integration with our classification and scoring systems, and make for easy serialization and deserialization of ASTs.
"""

from __future__ import annotations


"""Dynamically import submodules and classes for the semantic package.

Maps class/function/type names to their respective module paths for lazy loading.
"""

# === MANAGED EXPORTS ===

# Exportify manages this section. It contains lazy-loading infrastructure
# for the package: imports and runtime declarations (__all__, __getattr__,
# __dir__). Manual edits will be overwritten by `exportify fix`.

from types import MappingProxyType
from typing import TYPE_CHECKING

from lateimport import create_late_getattr


if TYPE_CHECKING:
    from codeweaver.semantic.ast_grep import (
        AstGrepNode,
        AstGrepRoot,
        AstThing,
        FileThing,
        MetaVar,
        Position,
        Range,
        SgRange,
        Strictness,
        ThingRegistryDep,
        rebuild_models_for_tests,
    )
    from codeweaver.semantic.classifications import (
        AgentTask,
        BaseAgentTask,
        ImportanceRank,
        ImportanceScores,
        ImportanceScoresDict,
        MappingProxyType,
        ScoreValidation,
        SemanticClass,
        SemanticClassDict,
        ThingClass,
        UsageMetrics,
    )
    from codeweaver.semantic.classifier import (
        ClassificationMethod,
        EvidenceKind,
        GrammarBasedClassifier,
        GrammarClassificationResult,
        is_composite_thing,
        is_token,
    )
    from codeweaver.semantic.dependencies import NodeParserDep, NodeParsingFailureError
    from codeweaver.semantic.grammar import (
        AllThingsDict,
        Category,
        CompositeThing,
        Connection,
        DirectConnection,
        Grammar,
        PositionalConnections,
        Thing,
        ThingOrCategoryType,
        ThingType,
        Token,
        cat_name_normalizer,
        get_all_grammars,
        get_grammar,
        name_normalizer,
        role_name_normalizer,
        thing_name_normalizer,
    )
    from codeweaver.semantic.node_type_parser import (
        NodeArray,
        NodeTypeFileLoader,
        NodeTypeParser,
        get_things,
    )
    from codeweaver.semantic.registry import ThingRegistry, build_models
    from codeweaver.semantic.scoring import SemanticScorer
    from codeweaver.semantic.token_patterns import (
        IS_ANNOTATION,
        IS_IDENTIFIER,
        IS_KEYWORD,
        IS_LITERAL,
        IS_OPERATOR,
        LANGUAGE_SPECIFIC_TOKEN_EXCEPTIONS,
        NAMED_NODE_COUNTS,
        NOT_SYMBOL,
        TokenPatternCacheDict,
        get_checks,
        get_token_patterns_sync,
    )
    from codeweaver.semantic.types import (
        ChildTypeDTO,
        ConnectionClass,
        ConnectionConstraint,
        NodeTypeDTO,
        SemanticMetadata,
        SimpleNodeTypeDTO,
        ThingKind,
        TokenPurpose,
    )

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "IS_ANNOTATION": (__spec__.parent, "token_patterns"),
    "IS_IDENTIFIER": (__spec__.parent, "token_patterns"),
    "IS_KEYWORD": (__spec__.parent, "token_patterns"),
    "IS_LITERAL": (__spec__.parent, "token_patterns"),
    "IS_OPERATOR": (__spec__.parent, "token_patterns"),
    "LANGUAGE_SPECIFIC_TOKEN_EXCEPTIONS": (__spec__.parent, "token_patterns"),
    "NAMED_NODE_COUNTS": (__spec__.parent, "token_patterns"),
    "NOT_SYMBOL": (__spec__.parent, "token_patterns"),
    "AgentTask": (__spec__.parent, "classifications"),
    "AllThingsDict": (__spec__.parent, "grammar"),
    "AstGrepNode": (__spec__.parent, "ast_grep"),
    "AstGrepRoot": (__spec__.parent, "ast_grep"),
    "AstThing": (__spec__.parent, "ast_grep"),
    "BaseAgentTask": (__spec__.parent, "classifications"),
    "Category": (__spec__.parent, "grammar"),
    "ClassificationMethod": (__spec__.parent, "classifier"),
    "CompositeThing": (__spec__.parent, "grammar"),
    "Connection": (__spec__.parent, "grammar"),
    "ConnectionClass": (__spec__.parent, "types"),
    "ConnectionConstraint": (__spec__.parent, "types"),
    "DirectConnection": (__spec__.parent, "grammar"),
    "EvidenceKind": (__spec__.parent, "classifier"),
    "FileThing": (__spec__.parent, "ast_grep"),
    "Grammar": (__spec__.parent, "grammar"),
    "GrammarBasedClassifier": (__spec__.parent, "classifier"),
    "GrammarClassificationResult": (__spec__.parent, "classifier"),
    "ImportanceRank": (__spec__.parent, "classifications"),
    "ImportanceScores": (__spec__.parent, "classifications"),
    "ImportanceScoresDict": (__spec__.parent, "classifications"),
    "MappingProxyType": (__spec__.parent, "classifications"),
    "MetaVar": (__spec__.parent, "ast_grep"),
    "NodeArray": (__spec__.parent, "node_type_parser"),
    "NodeParserDep": (__spec__.parent, "dependencies"),
    "NodeParsingFailureError": (__spec__.parent, "dependencies"),
    "NodeTypeFileLoader": (__spec__.parent, "node_type_parser"),
    "NodeTypeParser": (__spec__.parent, "node_type_parser"),
    "Position": (__spec__.parent, "ast_grep"),
    "PositionalConnections": (__spec__.parent, "grammar"),
    "Range": (__spec__.parent, "ast_grep"),
    "ScoreValidation": (__spec__.parent, "classifications"),
    "SemanticClass": (__spec__.parent, "classifications"),
    "SemanticClassDict": (__spec__.parent, "classifications"),
    "SemanticMetadata": (__spec__.parent, "types"),
    "SemanticScorer": (__spec__.parent, "scoring"),
    "SgRange": (__spec__.parent, "ast_grep"),
    "Strictness": (__spec__.parent, "ast_grep"),
    "Thing": (__spec__.parent, "grammar"),
    "ThingClass": (__spec__.parent, "classifications"),
    "ThingKind": (__spec__.parent, "types"),
    "ThingRegistry": (__spec__.parent, "registry"),
    "ThingRegistryDep": (__spec__.parent, "ast_grep"),
    "Token": (__spec__.parent, "grammar"),
    "TokenPatternCacheDict": (__spec__.parent, "token_patterns"),
    "TokenPurpose": (__spec__.parent, "types"),
    "UsageMetrics": (__spec__.parent, "classifications"),
    "build_models": (__spec__.parent, "registry"),
    "cat_name_normalizer": (__spec__.parent, "grammar"),
    "ChildTypeDTO": (__spec__.parent, "types"),
    "get_all_grammars": (__spec__.parent, "grammar"),
    "get_checks": (__spec__.parent, "token_patterns"),
    "get_grammar": (__spec__.parent, "grammar"),
    "get_things": (__spec__.parent, "node_type_parser"),
    "get_token_patterns_sync": (__spec__.parent, "token_patterns"),
    "is_composite_thing": (__spec__.parent, "classifier"),
    "is_token": (__spec__.parent, "classifier"),
    "name_normalizer": (__spec__.parent, "grammar"),
    "NodeTypeDTO": (__spec__.parent, "types"),
    "rebuild_models_for_tests": (__spec__.parent, "ast_grep"),
    "role_name_normalizer": (__spec__.parent, "grammar"),
    "SimpleNodeTypeDTO": (__spec__.parent, "types"),
    "thing_name_normalizer": (__spec__.parent, "grammar"),
})

__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    "IS_ANNOTATION",
    "IS_IDENTIFIER",
    "IS_KEYWORD",
    "IS_LITERAL",
    "IS_OPERATOR",
    "LANGUAGE_SPECIFIC_TOKEN_EXCEPTIONS",
    "NAMED_NODE_COUNTS",
    "NOT_SYMBOL",
    "AgentTask",
    "AllThingsDict",
    "AstGrepNode",
    "AstGrepRoot",
    "AstThing",
    "BaseAgentTask",
    "Category",
    "ChildTypeDTO",
    "ClassificationMethod",
    "CompositeThing",
    "Connection",
    "ConnectionClass",
    "ConnectionConstraint",
    "DirectConnection",
    "EvidenceKind",
    "FileThing",
    "Grammar",
    "GrammarBasedClassifier",
    "GrammarClassificationResult",
    "ImportanceRank",
    "ImportanceScores",
    "ImportanceScoresDict",
    "MappingProxyType",
    "MetaVar",
    "NodeArray",
    "NodeParserDep",
    "NodeParsingFailureError",
    "NodeTypeDTO",
    "NodeTypeFileLoader",
    "NodeTypeParser",
    "Position",
    "PositionalConnections",
    "Range",
    "ScoreValidation",
    "SemanticClass",
    "SemanticClassDict",
    "SemanticMetadata",
    "SemanticScorer",
    "SgRange",
    "SimpleNodeTypeDTO",
    "Strictness",
    "Thing",
    "ThingClass",
    "ThingKind",
    "ThingOrCategoryType",
    "ThingRegistry",
    "ThingRegistryDep",
    "ThingType",
    "Token",
    "TokenPatternCacheDict",
    "TokenPurpose",
    "UsageMetrics",
    "build_models",
    "cat_name_normalizer",
    "get_all_grammars",
    "get_checks",
    "get_grammar",
    "get_things",
    "get_token_patterns_sync",
    "is_composite_thing",
    "is_token",
    "name_normalizer",
    "rebuild_models_for_tests",
    "role_name_normalizer",
    "thing_name_normalizer",
)


def __dir__() -> list[str]:
    """List available attributes for the package."""
    return list(__all__)
