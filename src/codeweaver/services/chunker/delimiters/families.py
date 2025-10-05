# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Language family classification and delimiter grouping.

This module provides language family definitions and detection logic for grouping
languages with similar delimiter patterns. Families enable code reuse and provide
reasonable defaults for unknown languages.

Example:
    >>> detect_language_family("function foo() { return 42; }")
    <LanguageFamily.C_STYLE: 'c_style'>

    >>> FAMILY_PATTERNS[LanguageFamily.C_STYLE]
    [FUNCTION_PATTERN, CLASS_PATTERN, ...]
"""

from __future__ import annotations

import asyncio

from concurrent.futures import ThreadPoolExecutor
from typing import TYPE_CHECKING

import textcase

from codeweaver._common import BaseEnum


if TYPE_CHECKING:
    from codeweaver.services.chunker.delimiters.patterns import DelimiterPattern


class LanguageFamily(str, BaseEnum):
    """Major language family classifications based on syntax patterns.

    Language families group languages with similar delimiter patterns, enabling:
    - Code reuse through shared delimiter definitions
    - Reasonable defaults for unknown/undefined languages
    - Simplified language-specific delimiter composition

    Families are detected by characteristic delimiter presence in code samples.
    """

    C_STYLE = "c_style"  # C, C++, Java, JavaScript, Rust, Go, C#, Swift
    PYTHON_STYLE = "python_style"  # Python, CoffeeScript, Nim
    ML_STYLE = "ml_style"  # OCaml, F#, Standard ML, Reason
    LISP_STYLE = "lisp_style"  # Lisp, Scheme, Clojure, Racket
    MARKUP_STYLE = "markup_style"  # HTML, XML, JSX, Vue, Svelte
    SHELL_STYLE = "shell_style"  # Bash, Zsh, Fish, PowerShell
    FUNCTIONAL_STYLE = "functional_style"  # Haskell, Elm, PureScript, Agda
    LATEX_STYLE = "latex_style"  # TeX, LaTeX, ConTeXt
    RUBY_STYLE = "ruby_style"  # Ruby, Crystal
    MATLAB_STYLE = "matlab_style"  # MATLAB, Octave
    UNKNOWN = "unknown"  # Unclassified or insufficient information

    __slots__ = ()

    @classmethod
    def from_known_language(cls, language: str | BaseEnum) -> LanguageFamily:
        """Map known languages to their families.

        Provides deterministic mapping for known languages, avoiding the need
        for heuristic detection. This is the preferred method when the language
        is already known from file extensions or other metadata.

        Args:
            language: Language name (string) or BaseEnum with `.variable` attribute

        Returns:
            The corresponding LanguageFamily, or UNKNOWN if not recognized

        Example:
            >>> LanguageFamily.from_known_language("python")
            <LanguageFamily.PYTHON_STYLE: 'python_style'>

            >>> LanguageFamily.from_known_language("typescript")
            <LanguageFamily.C_STYLE: 'c_style'>
        """
        # Normalize to snake_case string
        lang = language.variable if isinstance(language, BaseEnum) else textcase.snake(language)

        # Use dictionary lookup for better performance and reduced complexity
        lang_variants = {
            lang.replace("_", ""),
            lang.replace("plus_plus", "++"),
            lang.replace("sharp", "#"),
            lang.rstrip("ml"),  # reasonml -> reason
            lang.rstrip("script"),  # coffeescript -> coffee
        }
        if language_found := _LANGUAGE_TO_FAMILY.get(lang):
            return language_found
        for variant in lang_variants:
            if language_found := _LANGUAGE_TO_FAMILY.get(variant):
                return language_found
        return cls.UNKNOWN


# Language-to-family mapping for known languages
_LANGUAGE_TO_FAMILY: dict[str, LanguageFamily] = {
    "agda": LanguageFamily.FUNCTIONAL_STYLE,
    "amslatex": LanguageFamily.LATEX_STYLE,
    "asciidoc": LanguageFamily.MARKUP_STYLE,
    "assembly": LanguageFamily.SHELL_STYLE,  # ; comments
    "assemblyscript": LanguageFamily.C_STYLE,
    "astro": LanguageFamily.MARKUP_STYLE,
    "bash": LanguageFamily.SHELL_STYLE,
    "batch": LanguageFamily.SHELL_STYLE,
    "beamer": LanguageFamily.LATEX_STYLE,
    "beef": LanguageFamily.C_STYLE,
    "c": LanguageFamily.C_STYLE,
    "c#": LanguageFamily.C_STYLE,
    "c++": LanguageFamily.C_STYLE,
    "carbon": LanguageFamily.C_STYLE,
    "chapel": LanguageFamily.FUNCTIONAL_STYLE,
    "clojure": LanguageFamily.LISP_STYLE,
    "cmake": LanguageFamily.SHELL_STYLE,
    "cmd": LanguageFamily.SHELL_STYLE,
    "cobol": LanguageFamily.UNKNOWN,  # Unique syntax, we have custom patterns for it
    "coffeescript": LanguageFamily.PYTHON_STYLE,
    "commonlisp": LanguageFamily.LISP_STYLE,
    "confluence": LanguageFamily.MARKUP_STYLE,
    "context": LanguageFamily.LATEX_STYLE,
    "coq": LanguageFamily.ML_STYLE,
    "cpp": LanguageFamily.C_STYLE,
    "crystal": LanguageFamily.RUBY_STYLE,
    "csh": LanguageFamily.SHELL_STYLE,
    "csharp": LanguageFamily.C_STYLE,
    "css": LanguageFamily.C_STYLE,  # C-style comments and blocks
    "cue": LanguageFamily.C_STYLE,
    "cython": LanguageFamily.PYTHON_STYLE,
    "dart": LanguageFamily.C_STYLE,
    "devicetree": LanguageFamily.C_STYLE,
    "dhall": LanguageFamily.FUNCTIONAL_STYLE,
    "dlang": LanguageFamily.C_STYLE,
    "docker": LanguageFamily.SHELL_STYLE,
    "dockerfile": LanguageFamily.SHELL_STYLE,
    "elisp": LanguageFamily.LISP_STYLE,
    "elixir": LanguageFamily.RUBY_STYLE,  # Similar syntax to Ruby
    "elm": LanguageFamily.FUNCTIONAL_STYLE,
    "elmish": LanguageFamily.FUNCTIONAL_STYLE,
    "elvish": LanguageFamily.SHELL_STYLE,
    "emacs": LanguageFamily.LISP_STYLE,
    "erlang": LanguageFamily.FUNCTIONAL_STYLE,
    "eta": LanguageFamily.FUNCTIONAL_STYLE,
    "f#": LanguageFamily.ML_STYLE,
    "factor": LanguageFamily.LISP_STYLE,
    "fish": LanguageFamily.SHELL_STYLE,
    "fortran": LanguageFamily.MATLAB_STYLE,
    "frege": LanguageFamily.FUNCTIONAL_STYLE,
    "fsharp": LanguageFamily.ML_STYLE,
    "gleam": LanguageFamily.FUNCTIONAL_STYLE,
    "gnuplot": LanguageFamily.MATLAB_STYLE,
    "go": LanguageFamily.C_STYLE,
    "gosu": LanguageFamily.C_STYLE,
    "graphql": LanguageFamily.MARKUP_STYLE,
    "groovy": LanguageFamily.C_STYLE,
    "hack": LanguageFamily.C_STYLE,
    "haskell": LanguageFamily.FUNCTIONAL_STYLE,
    "hcl": LanguageFamily.SHELL_STYLE,
    "hjson": LanguageFamily.MARKUP_STYLE,
    "hlsl": LanguageFamily.C_STYLE,
    "html": LanguageFamily.MARKUP_STYLE,
    "hy": LanguageFamily.LISP_STYLE,  # Lisp on Python
    "idris": LanguageFamily.FUNCTIONAL_STYLE,
    "imba": LanguageFamily.C_STYLE,
    "ini": LanguageFamily.SHELL_STYLE,  # # comments
    "io": LanguageFamily.LISP_STYLE,
    "janet": LanguageFamily.LISP_STYLE,
    "java": LanguageFamily.C_STYLE,
    "javascript": LanguageFamily.C_STYLE,
    "jruby": LanguageFamily.RUBY_STYLE,
    "json": LanguageFamily.MARKUP_STYLE,
    "jsx": LanguageFamily.MARKUP_STYLE,
    "jule": LanguageFamily.C_STYLE,
    "julia": LanguageFamily.MATLAB_STYLE,
    "just": LanguageFamily.SHELL_STYLE,
    "kotlin": LanguageFamily.C_STYLE,
    "lagda": LanguageFamily.FUNCTIONAL_STYLE,  # Literate Agda
    "latex": LanguageFamily.LATEX_STYLE,
    "less": LanguageFamily.C_STYLE,
    "lhs": LanguageFamily.FUNCTIONAL_STYLE,  # Literate Haskell
    "lisp": LanguageFamily.LISP_STYLE,
    "livescript": LanguageFamily.PYTHON_STYLE,
    "lua": LanguageFamily.RUBY_STYLE,  # Similar end-based syntax
    "lualatex": LanguageFamily.LATEX_STYLE,
    "lucee": LanguageFamily.C_STYLE,
    "make": LanguageFamily.SHELL_STYLE,
    "markdown": LanguageFamily.MARKUP_STYLE,
    "matlab": LanguageFamily.MATLAB_STYLE,
    "mediawiki": LanguageFamily.MARKUP_STYLE,
    "mojo": LanguageFamily.PYTHON_STYLE,
    "move": LanguageFamily.C_STYLE,
    "mruby": LanguageFamily.RUBY_STYLE,
    "nim": LanguageFamily.PYTHON_STYLE,
    "nix": LanguageFamily.FUNCTIONAL_STYLE,
    "nushell": LanguageFamily.C_STYLE,  # hard to classify, leaning C-style despite being a shell language
    "objective_c": LanguageFamily.C_STYLE,
    "objectivec": LanguageFamily.C_STYLE,
    "ocaml": LanguageFamily.ML_STYLE,
    "octave": LanguageFamily.MATLAB_STYLE,
    "odin": LanguageFamily.C_STYLE,
    "opal": LanguageFamily.RUBY_STYLE,
    "org": LanguageFamily.MARKUP_STYLE,
    "pascal": LanguageFamily.ML_STYLE,  # (* *) comments, begin/end blocks
    "perl": LanguageFamily.SHELL_STYLE,
    "pharo": LanguageFamily.ML_STYLE,
    "php": LanguageFamily.C_STYLE,  # //, /* */, { } blocks - C-like syntax
    "pkl": LanguageFamily.C_STYLE,
    "plaintex": LanguageFamily.LATEX_STYLE,
    "pony": LanguageFamily.FUNCTIONAL_STYLE,
    "powershell": LanguageFamily.SHELL_STYLE,
    "properties": LanguageFamily.SHELL_STYLE,  # # comments
    "protobuf": LanguageFamily.MARKUP_STYLE,
    "purescript": LanguageFamily.FUNCTIONAL_STYLE,
    "python": LanguageFamily.PYTHON_STYLE,
    "qb64": LanguageFamily.UNKNOWN,
    "qml": LanguageFamily.C_STYLE,
    "r": LanguageFamily.MATLAB_STYLE,
    "racket": LanguageFamily.LISP_STYLE,
    "raku": LanguageFamily.FUNCTIONAL_STYLE,
    "rakudo": LanguageFamily.SHELL_STYLE,
    "reason": LanguageFamily.ML_STYLE,
    "reasonml": LanguageFamily.ML_STYLE,
    "red": LanguageFamily.LISP_STYLE,
    "rescript": LanguageFamily.C_STYLE,
    "restructuredtext": LanguageFamily.MARKUP_STYLE,
    "ring": LanguageFamily.C_STYLE,
    "rmarkdown": LanguageFamily.MARKUP_STYLE,
    "rmd": LanguageFamily.MARKUP_STYLE,  # R Markdown
    "rnw": LanguageFamily.LATEX_STYLE,  # R + LaTeX
    "ruby": LanguageFamily.RUBY_STYLE,
    "rust": LanguageFamily.C_STYLE,
    "sas": LanguageFamily.MATLAB_STYLE,
    "sass": LanguageFamily.PYTHON_STYLE,  # Indentation-based
    "scala": LanguageFamily.C_STYLE,
    "scheme": LanguageFamily.LISP_STYLE,
    "scilab": LanguageFamily.MATLAB_STYLE,
    "scss": LanguageFamily.C_STYLE,
    "sh": LanguageFamily.SHELL_STYLE,
    "shell": LanguageFamily.SHELL_STYLE,
    "smali": LanguageFamily.SHELL_STYLE,
    "sml": LanguageFamily.ML_STYLE,
    "solidity": LanguageFamily.C_STYLE,
    "sql": LanguageFamily.FUNCTIONAL_STYLE,  # -- comments (like Haskell)
    "standard": LanguageFamily.ML_STYLE,
    "standardml": LanguageFamily.ML_STYLE,
    "svelte": LanguageFamily.MARKUP_STYLE,
    "svg": LanguageFamily.MARKUP_STYLE,
    "swift": LanguageFamily.C_STYLE,
    "tex": LanguageFamily.LATEX_STYLE,
    "textile": LanguageFamily.MARKUP_STYLE,
    "toml": LanguageFamily.MARKUP_STYLE,
    "tsx": LanguageFamily.MARKUP_STYLE,
    "typescript": LanguageFamily.C_STYLE,
    "vala": LanguageFamily.C_STYLE,
    "vale": LanguageFamily.FUNCTIONAL_STYLE,
    "vbscript": LanguageFamily.UNKNOWN,  # Unique syntax
    "verilog": LanguageFamily.C_STYLE,
    "vhdl": LanguageFamily.C_STYLE,
    "visualbasic6": LanguageFamily.UNKNOWN,
    "vlang": LanguageFamily.C_STYLE,
    "vue": LanguageFamily.MARKUP_STYLE,
    "wiki": LanguageFamily.MARKUP_STYLE,
    "xaml": LanguageFamily.MARKUP_STYLE,
    "xelatex": LanguageFamily.LATEX_STYLE,
    "xml": LanguageFamily.MARKUP_STYLE,
    "xonsh": LanguageFamily.PYTHON_STYLE,
    "yaml": LanguageFamily.MARKUP_STYLE,
    "zig": LanguageFamily.C_STYLE,
    "zsh": LanguageFamily.SHELL_STYLE,
}


def defined_languages() -> tuple[str, ...]:
    """Get a list of all languages with defined families.

    Returns:
        List of language names with known family mappings

    Example:
        >>> "python" in defined_languages()
        True

        >>> "unknownlang" in defined_languages()
        False
    """
    return tuple(_LANGUAGE_TO_FAMILY.keys())


# Family delimiter pattern mappings
# Lazy import to avoid circular dependencies
def _get_family_patterns() -> dict[LanguageFamily, list[DelimiterPattern]]:
    """Get family delimiter patterns with lazy import."""
    from codeweaver.services.chunker.delimiters.patterns import (
        ARRAY_PATTERN,
        BEGIN_END_BLOCK_PATTERN,
        BRACE_BLOCK_PATTERN,
        C_BLOCK_COMMENT_PATTERN,
        CLASS_PATTERN,
        CONDITIONAL_PATTERN,
        CONDITIONAL_TEX_PATTERN,
        CONTEXT_MANAGER_PATTERN,
        DASH_COMMENT_PATTERN,
        DECORATOR_PATTERN,
        DOCSTRING_HASH_PATTERN,
        DOCSTRING_MATLAB_PATTERN,
        DOCSTRING_QUOTE_PATTERN,
        DOCSTRING_RUBY_PATTERN,
        DOCSTRING_SEMICOLON_PATTERN,
        DOCSTRING_SLASH_PATTERN,
        EMPTY_PATTERN,
        ENUM_PATTERN,
        EXTENSION_PATTERN,
        FUNCTION_PATTERN,
        HASH_COMMENT_PATTERN,
        HASKELL_BLOCK_COMMENT_PATTERN,
        HTML_COMMENT_PATTERN,
        IMPL_PATTERN,
        INTERFACE_PATTERN,
        LATEX_BLOCK_PATTERN,
        LET_END_BLOCK_PATTERN,
        LISP_BLOCK_COMMENT_PATTERN,
        LOOP_PATTERN,
        ML_BLOCK_COMMENT_PATTERN,
        MODULE_BOUNDARY_PATTERN,
        MODULE_PATTERN,
        NEWLINE_PATTERN,
        PARAGRAPH_PATTERN,
        PERCENT_COMMENT_PATTERN,
        PRAGMA_PATTERN,
        PROPERTY_PATTERN,
        SEMICOLON_COMMENT_PATTERN,
        SLASH_COMMENT_PATTERN,
        STRING_BACKTICK_QUOTE_PATTERN,
        STRING_BYTES_PATTERN,
        STRING_FORMATTED_PATTERN,
        STRING_HASH_PATTERN,
        STRING_QUOTE_PATTERN,
        STRING_RAW_BYTES_PATTERN,
        STRING_RAW_FORMATTED_PATTERN,
        STRING_RAW_PATTERN,
        STRUCT_PATTERN,
        TEMPLATE_ANGLE_PATTERN,
        TEMPLATE_BRACE_PATTERN,
        TEMPLATE_BRACKET_PATTERN,
        TEMPLATE_PERCENT_PATTERN,
        TRY_CATCH_PATTERN,
        TUPLE_PATTERN,
        TYPE_ALIAS_PATTERN,
        WHITESPACE_PATTERN,
    )

    return {
        LanguageFamily.C_STYLE: [
            # Code elements
            FUNCTION_PATTERN,
            CLASS_PATTERN,
            STRUCT_PATTERN,
            INTERFACE_PATTERN,
            ENUM_PATTERN,
            TYPE_ALIAS_PATTERN,
            IMPL_PATTERN,
            EXTENSION_PATTERN,
            MODULE_BOUNDARY_PATTERN,
            # Control flow
            CONDITIONAL_PATTERN,
            LOOP_PATTERN,
            TRY_CATCH_PATTERN,
            CONTEXT_MANAGER_PATTERN,
            # Commentary
            SLASH_COMMENT_PATTERN,
            C_BLOCK_COMMENT_PATTERN,
            DOCSTRING_SLASH_PATTERN,
            # Structural
            BRACE_BLOCK_PATTERN,
            ARRAY_PATTERN,
            TUPLE_PATTERN,
            # Data
            PRAGMA_PATTERN,
            STRING_QUOTE_PATTERN,
            STRING_RAW_PATTERN,
            # Special
            PARAGRAPH_PATTERN,
            NEWLINE_PATTERN,
            WHITESPACE_PATTERN,
            EMPTY_PATTERN,
        ],
        LanguageFamily.PYTHON_STYLE: [
            # Code elements
            FUNCTION_PATTERN,
            CLASS_PATTERN,
            TYPE_ALIAS_PATTERN,
            MODULE_BOUNDARY_PATTERN,
            # Control flow
            CONDITIONAL_PATTERN,
            LOOP_PATTERN,
            TRY_CATCH_PATTERN,
            CONTEXT_MANAGER_PATTERN,
            # Commentary
            HASH_COMMENT_PATTERN,
            DOCSTRING_QUOTE_PATTERN,
            DOCSTRING_HASH_PATTERN,
            # Structural
            ARRAY_PATTERN,
            TUPLE_PATTERN,
            # Data
            DECORATOR_PATTERN,
            PROPERTY_PATTERN,
            STRING_QUOTE_PATTERN,
            STRING_RAW_PATTERN,
            STRING_FORMATTED_PATTERN,
            STRING_RAW_FORMATTED_PATTERN,
            STRING_BYTES_PATTERN,
            STRING_RAW_BYTES_PATTERN,
            # Special
            PARAGRAPH_PATTERN,
            NEWLINE_PATTERN,
            WHITESPACE_PATTERN,
            EMPTY_PATTERN,
        ],
        LanguageFamily.ML_STYLE: [
            # Code elements
            FUNCTION_PATTERN,
            MODULE_PATTERN,
            STRUCT_PATTERN,
            # Control flow
            CONDITIONAL_PATTERN,
            LOOP_PATTERN,
            # Commentary
            ML_BLOCK_COMMENT_PATTERN,
            # Structural
            LET_END_BLOCK_PATTERN,
            BEGIN_END_BLOCK_PATTERN,
            ARRAY_PATTERN,
            TUPLE_PATTERN,
            # Data
            STRING_QUOTE_PATTERN,
            # Special
            PARAGRAPH_PATTERN,
            NEWLINE_PATTERN,
            WHITESPACE_PATTERN,
            EMPTY_PATTERN,
        ],
        LanguageFamily.LISP_STYLE: [
            # Code elements
            FUNCTION_PATTERN,
            MODULE_PATTERN,
            # Commentary
            SEMICOLON_COMMENT_PATTERN,
            DOCSTRING_SEMICOLON_PATTERN,
            LISP_BLOCK_COMMENT_PATTERN,
            # Structural
            TUPLE_PATTERN,  # S-expressions
            ARRAY_PATTERN,
            # Data
            STRING_QUOTE_PATTERN,
            STRING_HASH_PATTERN,
            # Special
            PARAGRAPH_PATTERN,
            NEWLINE_PATTERN,
            WHITESPACE_PATTERN,
            EMPTY_PATTERN,
        ],
        LanguageFamily.MARKUP_STYLE: [
            # Commentary
            HTML_COMMENT_PATTERN,
            # Structural
            TEMPLATE_ANGLE_PATTERN,
            TEMPLATE_BRACE_PATTERN,
            TEMPLATE_BRACKET_PATTERN,
            TEMPLATE_PERCENT_PATTERN,
            # Data
            STRING_QUOTE_PATTERN,
            STRING_BACKTICK_QUOTE_PATTERN,
            # Special
            PARAGRAPH_PATTERN,
            NEWLINE_PATTERN,
            WHITESPACE_PATTERN,
            EMPTY_PATTERN,
        ],
        LanguageFamily.SHELL_STYLE: [
            # Code elements
            FUNCTION_PATTERN,
            # Control flow
            CONDITIONAL_PATTERN,
            LOOP_PATTERN,
            # Commentary
            HASH_COMMENT_PATTERN,
            # Structural
            BRACE_BLOCK_PATTERN,
            ARRAY_PATTERN,
            TUPLE_PATTERN,
            # Data
            STRING_QUOTE_PATTERN,
            STRING_RAW_PATTERN,
            # Special
            PARAGRAPH_PATTERN,
            NEWLINE_PATTERN,
            WHITESPACE_PATTERN,
            EMPTY_PATTERN,
        ],
        LanguageFamily.FUNCTIONAL_STYLE: [
            # Code elements
            FUNCTION_PATTERN,
            CLASS_PATTERN,
            MODULE_PATTERN,
            TYPE_ALIAS_PATTERN,
            # Control flow
            CONDITIONAL_PATTERN,
            # Commentary
            DASH_COMMENT_PATTERN,
            HASKELL_BLOCK_COMMENT_PATTERN,
            # Structural
            LET_END_BLOCK_PATTERN,
            ARRAY_PATTERN,
            TUPLE_PATTERN,
            # Data
            STRING_QUOTE_PATTERN,
            # Special
            PARAGRAPH_PATTERN,
            NEWLINE_PATTERN,
            WHITESPACE_PATTERN,
            EMPTY_PATTERN,
        ],
        LanguageFamily.LATEX_STYLE: [
            # Control flow
            CONDITIONAL_TEX_PATTERN,
            # Commentary
            PERCENT_COMMENT_PATTERN,
            # Structural
            LATEX_BLOCK_PATTERN,
            BRACE_BLOCK_PATTERN,
            ARRAY_PATTERN,
            # Special
            PARAGRAPH_PATTERN,
            NEWLINE_PATTERN,
            WHITESPACE_PATTERN,
            EMPTY_PATTERN,
        ],
        LanguageFamily.RUBY_STYLE: [
            # Code elements
            FUNCTION_PATTERN,
            CLASS_PATTERN,
            MODULE_PATTERN,
            # Control flow
            CONDITIONAL_PATTERN,
            LOOP_PATTERN,
            TRY_CATCH_PATTERN,
            # Commentary
            HASH_COMMENT_PATTERN,
            DOCSTRING_RUBY_PATTERN,
            # Structural
            BEGIN_END_BLOCK_PATTERN,
            ARRAY_PATTERN,
            TUPLE_PATTERN,
            # Data
            STRING_QUOTE_PATTERN,
            STRING_RAW_PATTERN,
            STRING_FORMATTED_PATTERN,
            # Special
            PARAGRAPH_PATTERN,
            NEWLINE_PATTERN,
            WHITESPACE_PATTERN,
            EMPTY_PATTERN,
        ],
        LanguageFamily.MATLAB_STYLE: [
            # Code elements
            FUNCTION_PATTERN,
            # Control flow
            CONDITIONAL_PATTERN,
            LOOP_PATTERN,
            # Commentary
            PERCENT_COMMENT_PATTERN,
            DOCSTRING_MATLAB_PATTERN,
            # Structural
            ARRAY_PATTERN,
            BRACE_BLOCK_PATTERN,
            TUPLE_PATTERN,
            # Data
            STRING_QUOTE_PATTERN,
            # Special
            PARAGRAPH_PATTERN,
            NEWLINE_PATTERN,
            WHITESPACE_PATTERN,
            EMPTY_PATTERN,
        ],
        LanguageFamily.UNKNOWN: [
            # Generic fallback patterns
            PARAGRAPH_PATTERN,
            BRACE_BLOCK_PATTERN,
            ARRAY_PATTERN,
            TUPLE_PATTERN,
            NEWLINE_PATTERN,
            WHITESPACE_PATTERN,
            EMPTY_PATTERN,
        ],
    }


# Cache family patterns for performance
_family_patterns_cache: dict[LanguageFamily, list[DelimiterPattern]] | None = None


def get_family_patterns(family: LanguageFamily) -> list[DelimiterPattern]:
    """Get delimiter patterns for a language family.

    Args:
        family: The language family to get patterns for

    Returns:
        List of DelimiterPattern objects for the family

    Example:
        >>> patterns = get_family_patterns(LanguageFamily.C_STYLE)
        >>> len(patterns) > 10
        True
    """
    global _family_patterns_cache
    if _family_patterns_cache is None:
        _family_patterns_cache = _get_family_patterns()
    return _family_patterns_cache.get(family, [])


def _detect_language_family_sync(content: str, min_confidence: int = 3) -> LanguageFamily:
    """Synchronous language family detection used by the async wrapper.

    Chooses the family with the most pattern matches. If the highest number
    of matches is less than min_confidence, returns LanguageFamily.UNKNOWN.
    """
    # Reuse the existing characteristic analyzer
    characteristics = detect_family_characteristics(content)

    best_family = LanguageFamily.UNKNOWN
    best_matches = -1
    best_confidence = 0.0

    for family, stats in characteristics.items():
        matches = int(stats.get("pattern_matches", 0))
        confidence = float(stats.get("confidence", 0.0))

        # Prefer higher match count, tiebreak on confidence
        if matches > best_matches or (matches == best_matches and confidence > best_confidence):
            best_matches = matches
            best_confidence = confidence
            best_family = family

    return LanguageFamily.UNKNOWN if best_matches < min_confidence else best_family


async def detect_language_family(content: str, min_confidence: int = 3) -> LanguageFamily:
    r"""Detect language family from code sample asynchronously.

    Runs in a thread pool to avoid blocking the event loop.
    """
    loop = asyncio.get_event_loop()
    with ThreadPoolExecutor(max_workers=1) as executor:
        # Offload the synchronous detection helper to the thread pool.
        return await loop.run_in_executor(
            executor, _detect_language_family_sync, content, min_confidence
        )


def detect_family_characteristics(content: str) -> dict[LanguageFamily, dict[str, int | float]]:
    """Analyze family characteristics in code sample.

    Provides detailed scoring breakdown for all families, useful for
    debugging classifier performance or understanding mixed-language files.

    Args:
        content: Code sample to analyze

    Returns:
        Dictionary mapping families to their characteristics:
        - pattern_matches: Number of delimiter patterns found
        - confidence: Normalized confidence score (0.0-1.0)

    Example:
        >>> chars = detect_family_characteristics("function foo() { }")
        >>> chars[LanguageFamily.C_STYLE]["pattern_matches"]
        4
    """
    results: dict[LanguageFamily, dict[str, int | float]] = {}

    for family in LanguageFamily:
        if family == LanguageFamily.UNKNOWN:
            continue

        patterns = get_family_patterns(family)
        matches = 0

        for pattern in patterns:
            for start in pattern.starts:
                if start and start in content:
                    matches += 1
                    break

        # Calculate confidence as percentage of patterns matched
        total_patterns = len(patterns)
        confidence = matches / total_patterns if total_patterns > 0 else 0.0

        results[family] = {"pattern_matches": matches, "confidence": confidence}

    return results


__all__ = (
    "LanguageFamily",
    "defined_languages",
    "detect_family_characteristics",
    "detect_language_family",
    "get_family_patterns",
)
