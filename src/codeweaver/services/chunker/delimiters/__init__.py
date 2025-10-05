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

from codeweaver.services.chunker.delimiters.families import LanguageFamily, detect_language_family
from codeweaver.services.chunker.delimiters.patterns import DelimiterPattern, expand_pattern


__all__ = ["DelimiterPattern", "LanguageFamily", "detect_language_family", "expand_pattern"]
