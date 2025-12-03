---
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

title: semantic
description: API reference for semantic
---

# semantic

Semantic node classification and importance scoring system.

The semantic package provides tools, types, and utilities for analyzing and classifying [tree-sitter](https://tree-sitter.github.io/tree-sitter/) grammars, which inform CodeWeaver's code context intelligence features. Most of the package is focused on classifying grammars (grammars are the 'what can be' of a programming language, defining its idioms, syntax and structure) into semantic classes (the 'what it means' of a programming language, defining the intent and purpose of code constructs). It provides granular mapping of grammar nodes, which we call 'things', to semantic classifications, and assigns importance based on these classifications, combined with the task at hand, their context in the actual code, and other factors.

After some frustrating experiences with Tree-Sitter's built-in node types, we decided to apply our own plain language descriptions and classifications to the structures. We hope this will help you understand and reason about code more effectively. For a complete overview of CodeWeaver's system and differences in terminology, see the module comment in `codeweaver.semantic.grammar`. //LINK - src/codeweaver/semantic/grammar.py

The package also includes serializable wrappers around `Ast-Grep`'s core types, which we use for parsing and analyzing code. These wrappers provide a more user-friendly interface for working with ASTs, add additional functionality, like integration with our classification and scoring systems, and make for easy serialization and deserialization of ASTs.

## Functions
