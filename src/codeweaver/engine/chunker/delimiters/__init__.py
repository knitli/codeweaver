# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Delimiter system for semantic code chunking.

This module provides a comprehensive delimiter-based chunking system with:

- Pattern-based delimiter definitions (DSL)
- Language family classification and reuse
- Cross-platform line ending support
- Unknown language inference
- Automatic delimiter generation
- Async/non-blocking language detection

The delimiter system is organized into three tiers:

1. **Patterns** (`patterns.py`): Language-agnostic delimiter patterns. Additionally, `custom.py` provides language-specific overrides and additions, like for Bash's `keyword`...`done` semantics like `do...done`.
2. **Families** (`families.py`): Reusable language family delimiter groups
3. **Languages** (generated): Language-specific delimiter sets composed from patterns

Together, these components enable robust and flexible code chunking across many programming languages, with over 170 languages explicitly supported, and the ability to infer delimiters for unknown languages (note: CodeWeaver does not index unknown file extensions, so users must expressly set new languages for indexing in the configuration, either with `codeweaver.settings.CodeWeaverSettings.custom_delimiters` or `codeweaver.settings.CodeWeaverSettings.custom_languages`).

Key exports:
    - DelimiterPattern: Pattern definition for delimiter generation
    - LanguageFamily: Language family classification
    - expand_pattern: Convert patterns to concrete delimiters
    - detect_language_family: Infer family without blocking event loop (async)
"""

from __future__ import annotations

from importlib import import_module
from types import MappingProxyType
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from codeweaver.engine.chunker.delimiters.custom import CustomDelimiterSet
    from codeweaver.engine.chunker.delimiters.families import LanguageFamily, detect_language_family
    from codeweaver.engine.chunker.delimiters.kind import DelimiterKind, LineStrategy
    from codeweaver.engine.chunker.delimiters.language import LanguageDelimiterSet
    from codeweaver.engine.chunker.delimiters.patterns import (
        DelimiterPattern,
        DelimiterPatternDict,
        expand_pattern,
        get_all_patterns,
    )


_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "DelimiterPattern": (__spec__.parent, "patterns"),
    "DelimiterPatternDict": (__spec__.parent, "patterns"),
    "expand_pattern": (__spec__.parent, "patterns"),
    "get_all_patterns": (__spec__.parent, "patterns"),
    "LanguageFamily": (__spec__.parent, "families"),
    "detect_language_family": (__spec__.parent, "families"),
    "LanguageDelimiterSet": (__spec__.parent, "language"),
    "CustomDelimiterSet": (__spec__.parent, "custom"),
    "DelimiterKind": (__spec__.parent, "kind"),
    "LineStrategy": (__spec__.parent, "kind"),
})


def __getattr__(name: str) -> object:
    """Dynamically import submodules and classes for the delimiters package."""
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
    "CustomDelimiterSet",
    "DelimiterKind",
    "DelimiterPattern",
    "DelimiterPatternDict",
    "LanguageDelimiterSet",
    "LanguageFamily",
    "LineStrategy",
    "detect_language_family",
    "expand_pattern",
    "get_all_patterns",
)


def __dir__() -> list[str]:
    """Customize dir() to include dynamically imported names."""
    return list(__all__)
