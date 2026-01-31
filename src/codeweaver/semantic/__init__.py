# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Semantic node classification and importance scoring system.

The semantic package provides tools, types, and utilities for analyzing and classifying [tree-sitter](https://tree-sitter.github.io/tree-sitter/) grammars, which inform CodeWeaver's code context intelligence features. Most of the package is focused on classifying grammars (grammars are the 'what can be' of a programming language, defining its idioms, syntax and structure) into semantic classes (the 'what it means' of a programming language, defining the intent and purpose of code constructs). It provides granular mapping of grammar nodes, which we call 'things', to semantic classifications, and assigns importance based on these classifications, combined with the task at hand, their context in the actual code, and other factors.

After some frustrating experiences with Tree-Sitter's built-in node types, we decided to apply our own plain language descriptions and classifications to the structures. We hope this will help you understand and reason about code more effectively. For a complete overview of CodeWeaver's system and differences in terminology, see the module comment in `codeweaver.semantic.grammar`. //LINK - src/codeweaver/semantic/grammar.py

The package also includes serializable wrappers around `Ast-Grep`'s core types, which we use for parsing and analyzing code. These wrappers provide a more user-friendly interface for working with ASTs, add additional functionality, like integration with our classification and scoring systems, and make for easy serialization and deserialization of ASTs.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from codeweaver.core.utils.lazy_importer import create_lazy_getattr


if TYPE_CHECKING:
    from codeweaver.semantic.ast_grep import (
        AstThing,
        CustomLang,
        FileThing,
        MetaVar,
        NthChild,
        Pattern,
        Position,
        PosRule,
        Range,
        RangeRule,
        Relation,
        Rule,
        RuleWithoutNot,
    )
    from codeweaver.semantic.classifications import (
        AgentTask,
        ImportanceScores,
        SemanticClass,
        ThingClass,
    )
    from codeweaver.semantic.classifier import (
        ClassificationMethod,
        EvidenceKind,
        GrammarBasedClassifier,
        GrammarClassificationResult,
    )
    from codeweaver.semantic.dependencies import NodeParserDep, ThingRegistryDep
    from codeweaver.semantic.grammar import (
        Category,
        CompositeThing,
        DirectConnection,
        Grammar,
        PositionalConnections,
        ThingType,
        Token,
        get_all_grammars,
        get_grammar,
    )
    from codeweaver.semantic.node_type_parser import NodeTypeParser
    from codeweaver.semantic.registry import ThingRegistry
    from codeweaver.semantic.scoring import SemanticScorer
    from codeweaver.semantic.types import (
        ConnectionClass,
        ConnectionConstraint,
        ThingKind,
        TokenPurpose,
    )

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "AgentTask": (__spec__.parent, "classifications"),
    "AstThing": (__spec__.parent, "ast_grep"),
    "Category": (__spec__.parent, "grammar"),
    "ClassificationMethod": (__spec__.parent, "classifier"),
    "CompositeThing": (__spec__.parent, "grammar"),
    "ConnectionClass": (__spec__.parent, "types"),
    "ConnectionConstraint": (__spec__.parent, "types"),
    "CustomLang": (__spec__.parent, "ast_grep"),
    "DirectConnection": (__spec__.parent, "grammar"),
    "EvidenceKind": (__spec__.parent, "classifier"),
    "FileThing": (__spec__.parent, "ast_grep"),
    "Grammar": (__spec__.parent, "grammar"),
    "GrammarBasedClassifier": (__spec__.parent, "classifier"),
    "GrammarClassificationResult": (__spec__.parent, "classifier"),
    "ImportanceScores": (__spec__.parent, "classifications"),
    "MetaVar": (__spec__.parent, "ast_grep"),
    "NodeParserDep": (__spec__.parent, "dependencies"),
    "NodeTypeParser": (__spec__.parent, "node_type_parser"),
    "NthChild": (__spec__.parent, "ast_grep"),
    "Pattern": (__spec__.parent, "ast_grep"),
    "PosRule": (__spec__.parent, "ast_grep"),
    "Position": (__spec__.parent, "ast_grep"),
    "PositionalConnections": (__spec__.parent, "grammar"),
    "Range": (__spec__.parent, "ast_grep"),
    "RangeRule": (__spec__.parent, "ast_grep"),
    "Relation": (__spec__.parent, "ast_grep"),
    "Rule": (__spec__.parent, "ast_grep"),
    "RuleWithoutNot": (__spec__.parent, "ast_grep"),
    "SemanticClass": (__spec__.parent, "classifications"),
    "SemanticScorer": (__spec__.parent, "scoring"),
    "ThingClass": (__spec__.parent, "classifications"),
    "ThingKind": (__spec__.parent, "types"),
    "ThingRegistry": (__spec__.parent, "registry"),
    "ThingRegistryDep": (__spec__.parent, "dependencies"),
    "ThingType": (__spec__.parent, "grammar"),
    "Token": (__spec__.parent, "grammar"),
    "TokenPurpose": (__spec__.parent, "types"),
    "get_all_grammars": (__spec__.parent, "grammar"),
    "get_grammar": (__spec__.parent, "grammar"),
})
"""Dynamically import submodules and classes for the semantic package.

Maps class/function/type names to their respective module paths for lazy loading.
"""


__getattr__ = create_lazy_getattr(_dynamic_imports, globals(), __name__)


__all__ = (
    "AgentTask",
    "AstThing",
    "Category",
    "ClassificationMethod",
    "CompositeThing",
    "ConnectionClass",
    "ConnectionConstraint",
    "CustomLang",
    "DirectConnection",
    "EvidenceKind",
    "FileThing",
    "Grammar",
    "GrammarBasedClassifier",
    "GrammarClassificationResult",
    "ImportanceScores",
    "MetaVar",
    "NodeParserDep",
    "NodeTypeParser",
    "NthChild",
    "Pattern",
    "PosRule",
    "Position",
    "PositionalConnections",
    "Range",
    "RangeRule",
    "Relation",
    "Rule",
    "RuleWithoutNot",
    "SemanticClass",
    "SemanticScorer",
    "ThingClass",
    "ThingKind",
    "ThingRegistry",
    "ThingRegistryDep",
    "ThingType",
    "Token",
    "TokenPurpose",
    "get_all_grammars",
    "get_grammar",
)


def __dir__() -> list[str]:
    """List available attributes for the semantic package."""
    return list(__all__)
