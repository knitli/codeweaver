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

from codeweaver.core.types.enum import BaseEnum


if TYPE_CHECKING:
    from codeweaver.engine.chunker.delimiters.patterns import DelimiterPattern


class LanguageFamily(str, BaseEnum):
    """Major language family classifications based on syntax patterns.

    Language families group languages with similar delimiter patterns, enabling:
    - Code reuse through shared delimiter definitions
    - Reasonable defaults for unknown/undefined languages
    - Simplified language-specific delimiter composition

    Families are detected by characteristic delimiter presence in code samples.
    """

    C_STYLE = "c_style"  # C, C++, Java, JavaScript, Rust, Go, C#, Swift
    FUNCTIONAL_STYLE = "functional_style"  # Haskell, Elm, PureScript, Agda
    LATEX_STYLE = "latex_style"  # TeX, LaTeX, ConTeXt
    LISP_STYLE = "lisp_style"  # Lisp, Scheme, Clojure, Racket
    MARKUP_STYLE = "markup_style"  # HTML, XML, JSX, Vue, Svelte
    MATLAB_STYLE = "matlab_style"  # MATLAB, Octave
    ML_STYLE = "ml_style"  # OCaml, F#, Standard ML, Reason
    PLAIN_TEXT = "plain_text"  # Plain text, config files, logs
    PYTHON_STYLE = "python_style"  # Python, CoffeeScript, Nim
    RUBY_STYLE = "ruby_style"  # Ruby, Crystal
    SHELL_STYLE = "shell_style"  # Bash, Zsh, Fish, PowerShell
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
    "creole": LanguageFamily.MARKUP_STYLE,
    "crystal": LanguageFamily.RUBY_STYLE,
    "csh": LanguageFamily.SHELL_STYLE,
    "csharp": LanguageFamily.C_STYLE,
    "css": LanguageFamily.C_STYLE,  # C-style comments and blocks
    "csv": LanguageFamily.PLAIN_TEXT,
    "cuda": LanguageFamily.C_STYLE,
    "cue": LanguageFamily.C_STYLE,
    "cython": LanguageFamily.PYTHON_STYLE,
    "dart": LanguageFamily.C_STYLE,
    "devicetree": LanguageFamily.C_STYLE,
    "dhall": LanguageFamily.FUNCTIONAL_STYLE,
    "dlang": LanguageFamily.C_STYLE,
    "docbook": LanguageFamily.MARKUP_STYLE,
    "docker": LanguageFamily.SHELL_STYLE,
    "dockerfile": LanguageFamily.SHELL_STYLE,
    "duck": LanguageFamily.FUNCTIONAL_STYLE,
    "dyck": LanguageFamily.LISP_STYLE,  # Dyck language (parenthesis-based)
    "ecl": LanguageFamily.LISP_STYLE,
    "eclisp": LanguageFamily.LISP_STYLE,
    "eiffel": LanguageFamily.ML_STYLE,
    "elixirscript": LanguageFamily.RUBY_STYLE,
    "elisp": LanguageFamily.LISP_STYLE,
    "elixir": LanguageFamily.RUBY_STYLE,  # Similar syntax to Ruby
    "elm": LanguageFamily.FUNCTIONAL_STYLE,
    "elmish": LanguageFamily.FUNCTIONAL_STYLE,
    "elvish": LanguageFamily.SHELL_STYLE,
    "emacs": LanguageFamily.LISP_STYLE,
    "erlang": LanguageFamily.FUNCTIONAL_STYLE,
    "eta": LanguageFamily.FUNCTIONAL_STYLE,
    "excel": LanguageFamily.MARKUP_STYLE,  # Formulas and XML-based files
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
    "help": LanguageFamily.MARKUP_STYLE,
    "hjson": LanguageFamily.MARKUP_STYLE,
    "hlsl": LanguageFamily.C_STYLE,
    "html": LanguageFamily.MARKUP_STYLE,
    "hy": LanguageFamily.LISP_STYLE,  # Lisp on Python
    "idris": LanguageFamily.FUNCTIONAL_STYLE,
    "imba": LanguageFamily.C_STYLE,
    "ini": LanguageFamily.SHELL_STYLE,  # # comments
    "info": LanguageFamily.MARKUP_STYLE,  # .info files
    "io": LanguageFamily.LISP_STYLE,
    "janet": LanguageFamily.LISP_STYLE,
    "java": LanguageFamily.C_STYLE,
    "javascript": LanguageFamily.C_STYLE,
    "jelly": LanguageFamily.MARKUP_STYLE,
    "jinja": LanguageFamily.MARKUP_STYLE,
    "jruby": LanguageFamily.RUBY_STYLE,
    "json": LanguageFamily.MARKUP_STYLE,
    "jsx": LanguageFamily.MARKUP_STYLE,
    "jule": LanguageFamily.C_STYLE,
    "julia": LanguageFamily.MATLAB_STYLE,
    "jupyter": LanguageFamily.PYTHON_STYLE,  # Primarily Python, but can contain other languages and is JSON-based
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
    "man": LanguageFamily.MARKUP_STYLE,  # manpages (i.e. '.1', '.2' files)
    "markdown": LanguageFamily.MARKUP_STYLE,
    "matlab": LanguageFamily.MATLAB_STYLE,
    "mediawiki": LanguageFamily.MARKUP_STYLE,
    "mojo": LanguageFamily.PYTHON_STYLE,
    "move": LanguageFamily.C_STYLE,
    "mruby": LanguageFamily.RUBY_STYLE,
    "newick": LanguageFamily.PLAIN_TEXT,  # Newick format for tree visualization with minimal syntax
    "nim": LanguageFamily.PYTHON_STYLE,
    "nimble": LanguageFamily.PYTHON_STYLE,
    "nix": LanguageFamily.FUNCTIONAL_STYLE,
    "nushell": LanguageFamily.C_STYLE,  # hard to classify, leaning C-style despite being a shell language
    "objective-c": LanguageFamily.C_STYLE,
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
    "rake": LanguageFamily.RUBY_STYLE,
    "raku": LanguageFamily.FUNCTIONAL_STYLE,
    "rakudo": LanguageFamily.SHELL_STYLE,
    "rdoc": LanguageFamily.MARKUP_STYLE,
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
    "rtf": LanguageFamily.PLAIN_TEXT,
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
    "texinfo": LanguageFamily.MARKUP_STYLE,
    "text": LanguageFamily.PLAIN_TEXT,
    "textile": LanguageFamily.MARKUP_STYLE,
    "toml": LanguageFamily.MARKUP_STYLE,
    "tsx": LanguageFamily.MARKUP_STYLE,
    "tsv": LanguageFamily.PLAIN_TEXT,
    "typescript": LanguageFamily.C_STYLE,
    "txt": LanguageFamily.PLAIN_TEXT,
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
    "yml": LanguageFamily.MARKUP_STYLE,
    "yard": LanguageFamily.MARKUP_STYLE,
    "yardoc": LanguageFamily.MARKUP_STYLE,
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
    from codeweaver.engine.chunker.delimiters.patterns import (
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
        LATEX_ALIGN_PATTERNS,
        LATEX_ARRAY_PATTERNS,
        LATEX_BLOCK_PATTERNS,
        LATEX_ENV_PATTERN,
        LATEX_LITERALS_PATTERNS,
        LATEX_SECTION_PATTERN,
        LATEX_STRING_PATTERN,
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
        LanguageFamily.PLAIN_TEXT: [
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
            LATEX_SECTION_PATTERN,
            # Control flow
            CONDITIONAL_TEX_PATTERN,
            # Commentary
            PERCENT_COMMENT_PATTERN,
            # Structural
            *LATEX_BLOCK_PATTERNS,
            LATEX_ENV_PATTERN,
            *LATEX_ARRAY_PATTERNS,
            *LATEX_ALIGN_PATTERNS,
            # Data
            BRACE_BLOCK_PATTERN,
            ARRAY_PATTERN,
            # Special
            *LATEX_LITERALS_PATTERNS,
            LATEX_STRING_PATTERN,
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

    Chooses the family with the highest weighted score (distinctive pattern matches).
    If the highest match count is less than min_confidence, returns LanguageFamily.UNKNOWN.
    """
    # Reuse the existing characteristic analyzer
    characteristics = detect_family_characteristics(content)

    best_family = LanguageFamily.UNKNOWN
    best_weighted_score = -1.0
    best_matches = -1
    best_pattern_count = 0

    for family, stats in characteristics.items():
        weighted_score = float(stats.get("weighted_score", 0.0))
        matches = int(stats.get("pattern_matches", 0))
        # Use total non-excluded patterns as another tiebreaker
        from codeweaver.engine.chunker.delimiters.kind import DelimiterKind

        excluded_kinds = {
            DelimiterKind.PARAGRAPH,
            DelimiterKind.WHITESPACE,
            DelimiterKind.GENERIC,
            DelimiterKind.UNKNOWN,
        }
        pattern_count = len([
            p for p in get_family_patterns(family) if p.kind not in excluded_kinds
        ])

        confidence = float(stats.get("confidence", 0.0))

        # Primary criterion: weighted score (favors distinctive patterns)
        # Tiebreaker 1: raw match count (more matches better)
        # Tiebreaker 2: more total patterns (more comprehensive family)
        # Tiebreaker 3: confidence (higher % of patterns matched)
        is_better = False
        # Use small tolerance for floating point comparison
        if weighted_score > best_weighted_score + 0.001:
            is_better = True
        elif abs(weighted_score - best_weighted_score) <= 0.001:
            if matches > best_matches:
                is_better = True
            elif matches == best_matches:
                # Prefer family with more total patterns (more comprehensive)
                if pattern_count > best_pattern_count:
                    is_better = True
                elif pattern_count == best_pattern_count:
                    # Only then use confidence as final tiebreaker
                    best_confidence = characteristics[best_family].get("confidence", 0.0) if best_family != LanguageFamily.UNKNOWN else 0.0
                    if confidence > best_confidence:
                        is_better = True

        if is_better:
            best_weighted_score = weighted_score
            best_matches = matches
            best_pattern_count = pattern_count
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
        - weighted_score: Score weighted by pattern distinctiveness

    Example:
        >>> chars = detect_family_characteristics("function foo() { }")
        >>> chars[LanguageFamily.C_STYLE]["pattern_matches"]
        4
    """
    # First, calculate pattern distinctiveness (how many families have each pattern)
    from codeweaver.engine.chunker.delimiters.kind import DelimiterKind

    pattern_family_counts: dict[tuple, int] = {}
    family_patterns_map: dict[LanguageFamily, list] = {}

    # Exclude universal/generic patterns that don't help discrimination
    excluded_kinds = {
        DelimiterKind.PARAGRAPH,
        DelimiterKind.WHITESPACE,
        DelimiterKind.GENERIC,
        DelimiterKind.UNKNOWN,
    }

    for family in LanguageFamily:
        if family == LanguageFamily.UNKNOWN:
            continue
        patterns = get_family_patterns(family)
        family_patterns_map[family] = patterns
        for pattern in patterns:
            # Skip universal patterns that don't help distinguish families
            if pattern.kind in excluded_kinds:
                continue
            # Use pattern kind + starts as key for uniqueness
            pattern_key = (pattern.kind, tuple(sorted(pattern.starts)))
            pattern_family_counts[pattern_key] = pattern_family_counts.get(pattern_key, 0) + 1

    results: dict[LanguageFamily, dict[str, int | float]] = {}

    for family in LanguageFamily:
        if family == LanguageFamily.UNKNOWN:
            continue

        patterns = family_patterns_map[family]
        matches = 0
        weighted_score = 0.0

        for pattern in patterns:
            # Skip universal patterns in matching too
            if pattern.kind in excluded_kinds:
                continue

            pattern_key = (pattern.kind, tuple(sorted(pattern.starts)))
            for start in pattern.starts:
                if start and start in content:
                    matches += 1
                    # Weight by distinctiveness: 1/count (rare patterns worth more)
                    distinctiveness_weight = 1.0 / pattern_family_counts.get(pattern_key, 1)
                    # Weight by specificity: penalize single chars, favor 2-4 char patterns
                    # Longer patterns can have false matches (e.g., 'class' in HTML attribute)
                    if len(start) == 1:
                        specificity_weight = 0.05  # Single chars are very unreliable
                    elif len(start) == 2:
                        specificity_weight = 0.5  # 2-char patterns are good ({{, //, etc.)
                    elif len(start) == 3:
                        specificity_weight = 0.7  # 3-char patterns are reliable (def, end, etc.)
                    elif len(start) == 4:
                        specificity_weight = 0.8  # 4-char patterns are quite reliable
                    else:
                        specificity_weight = 0.6  # 5+ char patterns can have context issues
                    weight = distinctiveness_weight * specificity_weight
                    weighted_score += weight
                    break

        # Calculate confidence as percentage of patterns matched
        total_patterns = len(patterns)
        confidence = matches / total_patterns if total_patterns > 0 else 0.0

        results[family] = {
            "pattern_matches": matches,
            "confidence": confidence,
            "weighted_score": weighted_score,
        }

    return results


__all__ = (
    "LanguageFamily",
    "defined_languages",
    "detect_family_characteristics",
    "detect_language_family",
    "get_family_patterns",
)
