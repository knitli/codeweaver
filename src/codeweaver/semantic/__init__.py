# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Semantic node classification and importance scoring system.

The semantic package provides tools, types, and utilities for analyzing and classifying [tree-sitter](https://tree-sitter.github.io/tree-sitter/) grammars, which inform CodeWeaver's code context intelligence features. Most of the package is focused on classifying grammars (grammars are the 'what can be' of a programming language, defining its idioms, syntax and structure) into semantic classes (the 'what it means' of a programming language, defining the intent and purpose of code constructs). It provides granular mapping of grammar nodes, which we call 'things', to semantic classifications, and assigns importance based on these classifications, combined with the task at hand, their context in the actual code, and other factors.

After some frustrating experiences with Tree-Sitter's built-in node types, we decided to apply our own plain language descriptions and classifications to the structures. We hope this will help you understand and reason about code more effectively. For a complete overview of CodeWeaver's system and differences in terminology, see the module comment in `codeweaver.semantic.grammar`. //LINK - src/codeweaver/semantic/grammar.py

The package also includes serializable wrappers around `Ast-Grep`'s core types, which we use for parsing and analyzing code. These wrappers provide a more user-friendly interface for working with ASTs, add additional functionality, like integration with our classification and scoring systems, and make for easy serialization and deserialization of ASTs.
"""
# pyright: reportUnsupportedDunderAll=none

from __future__ import annotations

from importlib import import_module
from types import MappingProxyType

from codeweaver.semantic.grammar import get_all_grammars, get_grammar
from codeweaver.semantic.registry import get_registry


_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "AgentTask": (__spec__.parent, "classifications"),
    "AstThing": (__spec__.parent, "ast_grep"),
    "Category": (__spec__.parent, "grammar"),
    "CategoryName": (__spec__.parent, "types"),
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
    "NthChild": (__spec__.parent, "ast_grep"),
    "Pattern": (__spec__.parent, "ast_grep"),
    "Position": (__spec__.parent, "ast_grep"),
    "PosRule": (__spec__.parent, "ast_grep"),
    "PositionalConnections": (__spec__.parent, "grammar"),
    "Range": (__spec__.parent, "ast_grep"),
    "Role": (__spec__.parent, "types"),
    "RangeRule": (__spec__.parent, "ast_grep"),
    "Relation": (__spec__.parent, "ast_grep"),
    "Rule": (__spec__.parent, "ast_grep"),
    "RuleWithoutNot": (__spec__.parent, "ast_grep"),
    "SemanticClass": (__spec__.parent, "classifications"),
    "SemanticScorer": (__spec__.parent, "scoring"),
    "ThingClass": (__spec__.parent, "classifications"),
    "ThingKind": (__spec__.parent, "types"),
    "ThingName": (__spec__.parent, "types"),
    "ThingRegistry": (__spec__.parent, "registry"),
    "ThingType": (__spec__.parent, "grammar"),
    "Token": (__spec__.parent, "grammar"),
    "TokenPurpose": (__spec__.parent, "types"),
})
"""Dynamically import submodules and classes for the semantic package.

Maps class/function/type names to their respective module paths for lazy loading.
"""


def __getattr__(name: str) -> object:
    """Dynamically import submodules and classes for the semantic package."""
    if name in _dynamic_imports:
        module_name, submodule_name = _dynamic_imports[name]
        module = import_module(f"{module_name}.{submodule_name}")
        result = getattr(module, name)
        globals()[name] = result  # Cache in globals for future access
        return result
    if globals().get(name) is not None:
        return globals()[name]
    raise AttributeError(f"module {__name__} has no attribute {name}")


__all__ = (
    "AgentTask",
    "AstThing",
    "Category",
    "CategoryName",
    "ClassificationMethod",
    "CompositeThing",
    "ConnectionClass",
    "ConnectionConstraint",
    "DirectConnection",
    "EvidenceKind",
    "FileThing",
    "Grammar",
    "GrammarBasedClassifier",
    "GrammarClassificationResult",
    "ImportanceScores",
    "MetaVar",
    "Position",
    "PositionalConnections",
    "Range",
    "Role",
    "SemanticClass",
    "SemanticScorer",
    "ThingClass",
    "ThingKind",
    "ThingName",
    "ThingRegistry",
    "ThingType",
    "Token",
    "TokenPurpose",
    "get_all_grammars",
    "get_grammar",
    "get_registry",
)


def __dir__() -> list[str]:
    """List available attributes for the semantic package."""
    return list(__all__)
