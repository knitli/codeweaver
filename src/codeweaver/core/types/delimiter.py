# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Delimiter related types moved to core to break circular dependencies."""

from __future__ import annotations

from collections.abc import Callable
from typing import Annotated, Literal, NamedTuple, NotRequired, Required, TypedDict

import textcase

from pydantic import Field, PositiveInt

from codeweaver.core.types.enum import BaseEnum
from codeweaver.core.types.utils import generate_field_title


class LineStrategy(NamedTuple):
    """A strategy for how to handle lines when chunking."""

    inclusive: bool
    take_whole_lines: bool


class DelimiterKind(str, BaseEnum):
    """Delimiter metadata that provide semantic information on the resulting chunk."""

    FUNCTION = "function"
    CLASS = "class"
    METHOD = "method"
    INTERFACE = "interface"
    STRUCT = "struct"
    ENUM = "enum"
    TYPE_ALIAS = "type_alias"
    IMPL_BLOCK = "impl_block"
    EXTENSION = "extension"
    NAMESPACE = "namespace"
    MODULE = "module"
    MODULE_BOUNDARY = "module_boundary"

    CONDITIONAL = "conditional"
    LOOP = "loop"
    TRY_CATCH = "try_catch"
    CONTEXT_MANAGER = "context_manager"

    COMMENT_LINE = "comment_line"
    COMMENT_BLOCK = "comment_block"
    DOCSTRING = "docstring"

    BLOCK = "block"
    ARRAY = "array"
    TUPLE = "tuple"

    STRING = "string"
    TEMPLATE_STRING = "template_string"

    ANNOTATION = "annotation"
    DECORATOR = "decorator"
    PROPERTY = "property"
    PRAGMA = "pragma"

    PARAGRAPH = "paragraph"
    WHITESPACE = "whitespace"
    GENERIC = "generic"
    UNKNOWN = "unknown"

    __slots__ = ()

    @property
    def is_code_element(self) -> bool:
        """Whether the delimiter kind represents a code element like functions or classes."""
        return self in {
            DelimiterKind.FUNCTION,
            DelimiterKind.CLASS,
            DelimiterKind.METHOD,
            DelimiterKind.INTERFACE,
            DelimiterKind.STRUCT,
            DelimiterKind.ENUM,
            DelimiterKind.TYPE_ALIAS,
            DelimiterKind.IMPL_BLOCK,
            DelimiterKind.EXTENSION,
            DelimiterKind.NAMESPACE,
            DelimiterKind.MODULE,
            DelimiterKind.MODULE_BOUNDARY,
        }

    @property
    def is_structure(self) -> bool:
        """Whether the delimiter kind represents a structural element like blocks or arrays."""
        return self in {DelimiterKind.BLOCK, DelimiterKind.ARRAY, DelimiterKind.TUPLE}

    @property
    def is_control_flow(self) -> bool:
        """Whether the delimiter kind represents control flow constructs."""
        return self in {
            DelimiterKind.CONDITIONAL,
            DelimiterKind.LOOP,
            DelimiterKind.TRY_CATCH,
            DelimiterKind.CONTEXT_MANAGER,
        }

    @property
    def is_commentary(self) -> bool:
        """Whether the delimiter kind represents commentary like comments or docstrings."""
        return self in {
            DelimiterKind.COMMENT_LINE,
            DelimiterKind.COMMENT_BLOCK,
            DelimiterKind.DOCSTRING,
        }

    @property
    def is_generic(self) -> bool:
        """Whether the delimiter kind represents generic or unknown content."""
        return self in {
            DelimiterKind.PARAGRAPH,
            DelimiterKind.WHITESPACE,
            DelimiterKind.GENERIC,
            DelimiterKind.UNKNOWN,
        }

    @property
    def is_data(self) -> bool:
        """Whether the delimiter kind represents data structures like strings or arrays."""
        return self in {DelimiterKind.STRING, DelimiterKind.TEMPLATE_STRING}

    @property
    def is_meta(self) -> bool:
        """Whether the delimiter kind represents meta constructs like annotations or decorators."""
        return self in {
            DelimiterKind.ANNOTATION,
            DelimiterKind.DECORATOR,
            DelimiterKind.PROPERTY,
            DelimiterKind.PRAGMA,
            DelimiterKind.WHITESPACE,
        }

    @property
    def default_priority(self) -> PositiveInt:
        """The default priority of the delimiter kind."""
        return {
            DelimiterKind.MODULE_BOUNDARY: 90,
            DelimiterKind.CLASS: 85,
            DelimiterKind.INTERFACE: 80,
            DelimiterKind.TYPE_ALIAS: 75,
            DelimiterKind.IMPL_BLOCK: 75,
            DelimiterKind.STRUCT: 75,
            DelimiterKind.EXTENSION: 70,
            DelimiterKind.FUNCTION: 70,
            DelimiterKind.PROPERTY: 65,
            DelimiterKind.METHOD: 65,
            DelimiterKind.ENUM: 65,
            DelimiterKind.CONTEXT_MANAGER: 60,
            DelimiterKind.MODULE: 60,
            DelimiterKind.DOCSTRING: 60,
            DelimiterKind.DECORATOR: 55,
            DelimiterKind.NAMESPACE: 55,
            DelimiterKind.COMMENT_BLOCK: 55,
            DelimiterKind.TRY_CATCH: 50,
            DelimiterKind.LOOP: 50,
            DelimiterKind.CONDITIONAL: 50,
            DelimiterKind.PARAGRAPH: 40,
            DelimiterKind.BLOCK: 30,
            DelimiterKind.ANNOTATION: 30,
            DelimiterKind.ARRAY: 25,
            DelimiterKind.TUPLE: 20,
            DelimiterKind.COMMENT_LINE: 20,
            DelimiterKind.TEMPLATE_STRING: 15,
            DelimiterKind.STRING: 10,
            DelimiterKind.PRAGMA: 5,
            DelimiterKind.GENERIC: 3,
            DelimiterKind.WHITESPACE: 1,
            DelimiterKind.UNKNOWN: 1,
        }[self]

    def infer_nestable(self) -> bool:
        """Infer whether the delimiter kind is nestable."""
        return self in {
            DelimiterKind.FUNCTION,
            DelimiterKind.CLASS,
            DelimiterKind.INTERFACE,
            DelimiterKind.STRUCT,
            DelimiterKind.ENUM,
            DelimiterKind.IMPL_BLOCK,
            DelimiterKind.EXTENSION,
            DelimiterKind.NAMESPACE,
            DelimiterKind.CONDITIONAL,
            DelimiterKind.LOOP,
            DelimiterKind.TRY_CATCH,
            DelimiterKind.CONTEXT_MANAGER,
            DelimiterKind.BLOCK,
            DelimiterKind.ARRAY,
            DelimiterKind.TUPLE,
            DelimiterKind.STRING,
            DelimiterKind.TEMPLATE_STRING,
        }

    def infer_inline_strategy(self) -> LineStrategy:
        """Infer the line strategy based on the delimiter kind."""
        if self.is_code_element or self.is_control_flow:
            return LineStrategy(inclusive=True, take_whole_lines=True)
        if self.is_structure or self.is_data or self.is_meta:
            return LineStrategy(inclusive=False, take_whole_lines=True)
        if self.is_commentary:
            return (
                LineStrategy(inclusive=True, take_whole_lines=False)
                if self == DelimiterKind.COMMENT_LINE
                else LineStrategy(inclusive=False, take_whole_lines=True)
            )
        return LineStrategy(inclusive=False, take_whole_lines=False)


class LanguageFamily(str, BaseEnum):
    """Major language family classifications based on syntax patterns."""

    C_STYLE = "c_style"
    FUNCTIONAL_STYLE = "functional_style"
    LATEX_STYLE = "latex_style"
    LISP_STYLE = "lisp_style"
    MARKUP_STYLE = "markup_style"
    MATLAB_STYLE = "matlab_style"
    ML_STYLE = "ml_style"
    PLAIN_TEXT = "plain_text"
    PYTHON_STYLE = "python_style"
    RUBY_STYLE = "ruby_style"
    SHELL_STYLE = "shell_style"
    UNKNOWN = "unknown"

    __slots__ = ()

    @classmethod
    def from_known_language(cls, language: str | BaseEnum) -> LanguageFamily:
        """Get the language family from a known programming language."""
        lang = language.variable if isinstance(language, BaseEnum) else textcase.snake(language)
        lang_variants = {
            lang.replace("_", ""),
            lang.replace("plus_plus", "++"),
            lang.replace("sharp", "#"),
            lang.rstrip("ml"),
            lang.rstrip("script"),
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


class DelimiterDict(TypedDict, total=False):
    """A dictionary representation of a delimiter pattern."""

    start: Required[str]
    end: Required[str]
    kind: NotRequired[DelimiterKind]
    priority_override: NotRequired[PositiveInt]
    inclusive: NotRequired[bool]
    take_whole_lines: NotRequired[bool]
    nestable: NotRequired[bool]


class DelimiterPattern(NamedTuple):
    """A pattern for matching delimiters in code."""

    starts: Annotated[
        list[str],
        Field(description="The start delimiters.", field_title_generator=generate_field_title),
    ]
    ends: Annotated[
        list[str] | Literal["ANY"],
        Field(description="The end delimiters.", field_title_generator=generate_field_title),
    ]
    kind: Annotated[
        DelimiterKind,
        Field(description="The kind of delimiter.", field_title_generator=generate_field_title),
    ] = DelimiterKind.UNKNOWN
    priority_override: (
        Annotated[
            PositiveInt,
            Field(
                gt=0,
                lt=100,
                description="The priority of the delimiter.",
                field_title_generator=generate_field_title,
            ),
        ]
        | None
    ) = None
    inclusive: Annotated[
        bool | None,
        Field(
            description="Whether to include the delimiters in the resulting chunk.",
            field_title_generator=generate_field_title,
        ),
    ] = None
    take_whole_lines: Annotated[
        bool | None,
        Field(
            description="Whether to expand the chunk to include whole lines if matched within it.",
            field_title_generator=generate_field_title,
        ),
    ] = None
    nestable: Annotated[
        bool | None,
        Field(
            description="Whether the delimiter can be nested.",
            field_title_generator=generate_field_title,
        ),
    ] = None
    formatter: Annotated[
        Callable[[str], str] | None,
        Field(
            description="An optional formatter function to apply to the chunk text.",
            field_title_generator=generate_field_title,
        ),
    ] = None

    @property
    def as_dicts(self) -> tuple[DelimiterDict, ...]:
        """Get the delimiter pattern as a tuple of DelimiterDicts."""
        return tuple(
            DelimiterDict(
                start=start,
                end=end if self.ends != "ANY" else "",
                kind=self.kind,
                priority_override=self.priority_override or self.kind.default_priority,
                inclusive=self.inclusive
                if self.inclusive is not None
                else self.kind.infer_inline_strategy().inclusive,
                take_whole_lines=self.take_whole_lines
                if self.take_whole_lines is not None
                else self.kind.infer_inline_strategy().take_whole_lines,
                nestable=self.nestable if self.nestable is not None else self.kind.infer_nestable(),
            )
            for start, end in zip(
                self.starts,
                self.ends if self.ends != "ANY" else [""] * len(self.starts),
                strict=True,
            )
        )

    def format(self, text: str) -> str:
        """Format the given text using the delimiter's formatter, if one is defined."""
        return self.formatter(text) if self.formatter else text


__all__ = ("DelimiterDict", "DelimiterKind", "DelimiterPattern", "LanguageFamily", "LineStrategy")
