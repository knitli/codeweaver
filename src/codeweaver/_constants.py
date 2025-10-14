# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""
Constants used throughout the CodeWeaver project, primarily for default configurations.
"""

from __future__ import annotations

import contextlib

from collections.abc import Generator
from pathlib import Path
from types import MappingProxyType
from typing import Annotated, Literal, NamedTuple, TypedDict, cast

from pydantic import Field

from codeweaver._common import LiteralStringT


METADATA_PATH = "metadata"


class ExtLangPair(NamedTuple):
    """
    Mapping of file extensions to their corresponding programming languages.

    Not all 'extensions' are actually file extensions, some are file names or special cases, like `Makefile` or `Dockerfile`.
    """

    ext: Annotated[LiteralStringT, Field(min_length=2, max_length=30)]
    """The file extension, including leading dot if it's a file extension."""

    language: Annotated[
        LiteralStringT, Field(min_length=1, max_length=50, default_factory=lambda x: str(x).lower())
    ]
    """The programming or config language associated with the file extension."""

    @property
    def is_actual_ext(self) -> bool:
        """Check if the extension is a valid file extension."""
        return self.ext.startswith(".")

    @property
    def is_file_name(self) -> bool:
        """Check if the extension is a file name."""
        return not self.ext.startswith(".")

    @property
    def is_config(self) -> bool:
        """Check if the extension is a configuration file."""
        return self.language in CONFIG_FILE_LANGUAGES

    @property
    def is_doc(self) -> bool:
        """Check if the extension is a documentation file."""
        return next((True for doc_ext in DOC_FILES_EXTENSIONS if doc_ext.ext == self.ext), False)

    @property
    def is_code(self) -> bool:
        """Check if the extension is a code file."""
        return not self.is_config and not self.is_doc and not self.is_file_name

    @property
    def category(self) -> Literal["code", "docs", "config"]:
        """Return the language of file based on its extension."""
        if self.is_code:
            return "code"
        if self.is_doc:
            return "docs"
        if self.is_config:
            return "config"
        raise ValueError(f"Unknown category for {self.ext}")

    @property
    def is_weird_extension(self) -> bool:
        """Check if a file extension doesn't fit the usual pattern of a dot followed by alphanumerics."""
        if not self.is_actual_ext or self.is_file_name:
            return True
        if self.ext.istitle():
            return True
        return True if self.ext.find(".", 1) != -1 else "." not in self.ext

    def is_same(self, filename: str) -> bool:
        """Check if the given filename is the same filetype as the extension."""
        # fast case first for elimination
        if self.ext.lower() not in filename.lower():
            return False
        # a couple of these may seem redundant but we're descending in confidence levels here
        if not self.is_weird_extension and filename.endswith(self.ext):
            return True
        if self.is_file_name and filename == self.ext:
            return True
        return bool(self.is_weird_extension and filename.lower().endswith(self.ext.lower()))


DEFAULT_EXCLUDED_DIRS: frozenset[LiteralStringT] = frozenset({
    ".DS_Store",
    ".cache",
    ".claude",
    ".eslintcache",
    ".git",
    ".hg",
    ".history",
    ".idea",
    ".jj",
    ".next",
    ".nuxt",
    ".roo",
    ".ruff_cache",
    ".svn",
    ".temp",
    ".tmp",
    ".tsbuildinfo",
    ".venv",
    ".vs",
    ".vscode",
    "Debug",
    "Release",
    "Releases",
    "Thumbs.db",
    "__pycache__",
    "__pytest_cache__",
    "aarch64",
    "arm",
    "arm64",
    "bin",
    "bld",
    "bower_components",
    "build",
    "debug",
    "dist",
    "htmlcov",
    "lib64",
    "log",
    "logs",
    "node_modules",
    "obj",
    "out",
    "release",
    "releases",
    "remote-debug-profile",
    "site",
    "target",
    "temp",
    "venv",
    "win32",
    "win64",
    "x64",
    "x86",
})

DEFAULT_EXCLUDED_EXTENSIONS: frozenset[LiteralStringT] = frozenset({
    ".7z",
    ".avi",
    ".avif",
    ".bmp",
    ".builds",
    ".cache",
    ".class",
    "codeweaver.local.json",
    "codeweaver.local.toml",
    "codeweaver.local.yaml",
    ".code-workspace",
    ".coverage",
    ".coverage.xml",
    ".dll",
    ".dmg",
    ".env",
    ".exe",
    ".gif",
    ".gz",
    ".iobj",
    ".jar",
    ".jpeg",
    ".jpg",
    ".lcov",
    ".local",
    ".lock",
    ".log",
    ".meta",
    ".mov",
    ".mp3",
    ".mp4",
    ".mpeg",
    ".mpg",
    ".ms",
    ".msi",
    ".o",
    ".obj",
    ".pch",
    ".pdb",
    ".pgc",
    ".pgd",
    ".png",
    ".pyc",
    ".pyo",
    ".rar",
    ".rsp",
    ".scc",
    ".sig",
    ".snk",
    ".so",
    ".svclog",
    ".svg",
    ".swo",
    ".swp",
    ".tar",
    ".temp",
    ".tlb",
    ".tlog",
    ".tmp",
    ".tmp_proj",
    ".vspec",
    ".vssscc",
    ".wav",
    ".webm",
    ".webp",
    ".zip",
})

DATA_FILES_EXTENSIONS: tuple[ExtLangPair, ...] = (
    ExtLangPair(ext=".csv", language="csv"),
    ExtLangPair(ext=".dat", language="data"),
    ExtLangPair(ext=".db", language="sql"),
    ExtLangPair(ext=".dbf", language="dbf"),
    ExtLangPair(ext=".sqlite", language="sql"),
    ExtLangPair(ext=".sqlite3", language="sql"),
    ExtLangPair(ext=".tsv", language="tsv"),
    ExtLangPair(ext=".xls", language="excel"),
    ExtLangPair(ext=".xlsx", language="excel"),
)

DOC_FILES_EXTENSIONS: tuple[ExtLangPair, ...] = (
    ExtLangPair(ext=".1", language="man"),
    ExtLangPair(ext=".2", language="man"),
    ExtLangPair(ext=".3", language="man"),
    ExtLangPair(ext=".4", language="man"),
    ExtLangPair(ext=".5", language="man"),
    ExtLangPair(ext=".6", language="man"),
    ExtLangPair(ext=".7", language="man"),
    ExtLangPair(ext=".8", language="man"),
    ExtLangPair(ext=".9", language="man"),
    ExtLangPair(ext=".Rmd", language="rmarkdown"),
    ExtLangPair(ext=".adoc", language="asciidoc"),
    ExtLangPair(ext=".asc", language="asciidoc"),
    ExtLangPair(ext=".asciidoc", language="asciidoc"),
    ExtLangPair(ext=".bib", language="latex"),
    ExtLangPair(ext=".confluence", language="confluence"),
    ExtLangPair(ext=".creole", language="creole"),
    ExtLangPair(ext=".dita", language="dita"),
    ExtLangPair(ext=".docbook", language="docbook"),
    ExtLangPair(ext=".help", language="help"),
    ExtLangPair(ext=".hlp", language="help"),
    ExtLangPair(ext=".info", language="info"),
    ExtLangPair(ext=".ipynb", language="jupyter"),
    ExtLangPair(ext=".lagda", language="lagda"),
    ExtLangPair(ext=".latex", language="latex"),
    ExtLangPair(ext=".lhs", language="lhs"),
    ExtLangPair(ext=".man", language="man"),
    ExtLangPair(ext=".manpage", language="man"),
    ExtLangPair(ext=".markdown", language="markdown"),
    ExtLangPair(ext=".md", language="markdown"),
    ExtLangPair(ext=".mdown", language="markdown"),
    ExtLangPair(ext=".mdx", language="markdown"),
    ExtLangPair(ext=".mediawiki", language="mediawiki"),
    ExtLangPair(ext=".mkd", language="markdown"),
    ExtLangPair(ext=".mkdn", language="markdown"),
    ExtLangPair(ext=".nw", language="nw"),
    ExtLangPair(ext=".org", language="org"),
    ExtLangPair(ext=".pmd", language="pmd"),
    ExtLangPair(ext=".pod", language="pod"),
    ExtLangPair(ext=".pyx", language="cython"),
    ExtLangPair(ext=".rdoc", language="rdoc"),
    ExtLangPair(ext=".rest", language="restructuredtext"),
    ExtLangPair(ext=".rmd", language="rmd"),
    ExtLangPair(ext=".rnw", language="rnw"),
    ExtLangPair(ext=".rst", language="restructuredtext"),
    ExtLangPair(ext=".rtf", language="rtf"),
    ExtLangPair(ext=".tex", language="latex"),
    ExtLangPair(ext=".texi", language="texinfo"),
    ExtLangPair(ext=".texinfo", language="texinfo"),
    ExtLangPair(ext=".text", language="text"),
    ExtLangPair(ext=".textile", language="textile"),
    ExtLangPair(ext=".txt", language="text"),
    ExtLangPair(ext=".wiki", language="wiki"),
    ExtLangPair(ext=".xml", language="xml"),
    ExtLangPair(ext=".yard", language="yard"),
)
"""A tuple of `ExtLangPair` for documentation files."""

# spellchecker:off
CODE_FILES_EXTENSIONS: tuple[ExtLangPair, ...] = (
    ExtLangPair(ext=".F", language="fortran"),
    ExtLangPair(ext=".R", language="r"),
    ExtLangPair(ext=".Rprofile", language="r"),
    ExtLangPair(ext=".app.src", language="erlang"),
    ExtLangPair(ext=".as", language="assemblyscript"),
    ExtLangPair(ext=".asd", language="lisp"),
    ExtLangPair(ext=".asm", language="assembly"),
    ExtLangPair(ext=".aux", language="latex"),
    ExtLangPair(ext=".bat", language="batch"),
    ExtLangPair(ext=".bb", language="clojure"),
    ExtLangPair(ext=".beef", language="beef"),
    ExtLangPair(ext=".binpb", language="protobuf"),
    ExtLangPair(ext=".boot", language="clojure"),
    ExtLangPair(ext=".carbon", language="carbon"),
    ExtLangPair(ext=".cbl", language="cobol"),
    ExtLangPair(ext=".chapel", language="chapel"),
    ExtLangPair(ext=".clj", language="clojure"),
    ExtLangPair(ext=".cljc", language="clojure"),
    ExtLangPair(ext=".cljs", language="clojure"),
    ExtLangPair(ext=".cljx", language="clojure"),
    ExtLangPair(ext=".cls", language="latex"),
    ExtLangPair(ext=".cmake", language="cmake"),
    ExtLangPair(ext=".cob", language="cobol"),
    ExtLangPair(ext=".cobol", language="cobol"),
    ExtLangPair(ext=".coffee", language="coffeescript"),
    ExtLangPair(ext=".cr", language="crystal"),
    ExtLangPair(ext=".cu", language="cuda"),
    ExtLangPair(ext=".cuh", language="cuda"),
    ExtLangPair(ext=".cue", language="cue"),
    ExtLangPair(ext=".d", language="dlang"),
    ExtLangPair(ext=".dart", language="dart"),
    ExtLangPair(ext=".dfm", language="pascal"),
    ExtLangPair(ext=".dhall", language="dhall"),
    ExtLangPair(ext=".dlang", language="dlang"),
    ExtLangPair(ext=".dpr", language="pascal"),
    ExtLangPair(ext=".dts", language="devicetree"),
    ExtLangPair(ext=".dtsi", language="devicetree"),
    ExtLangPair(ext=".dtso", language="devicetree"),
    ExtLangPair(ext=".dyck", language="dyck"),
    ExtLangPair(ext=".edn", language="clojure"),
    ExtLangPair(ext=".el", language="emacs"),
    ExtLangPair(ext=".elm", language="elm"),
    ExtLangPair(ext=".elv", language="elvish"),
    ExtLangPair(ext=".emacs", language="emacs"),
    ExtLangPair(ext=".erl", language="erlang"),
    ExtLangPair(ext=".es", language="erlang"),
    ExtLangPair(ext=".escript", language="erlang"),
    ExtLangPair(ext=".eta", language="eta"),
    ExtLangPair(ext=".f", language="fortran"),
    ExtLangPair(ext=".f03", language="fortran"),
    ExtLangPair(ext=".f08", language="fortran"),
    ExtLangPair(ext=".f18", language="fortran"),
    ExtLangPair(ext=".f23", language="fortran"),
    ExtLangPair(ext=".f90", language="fortran"),
    ExtLangPair(ext=".f95", language="fortran"),
    ExtLangPair(ext=".factor", language="factor"),
    ExtLangPair(ext=".for", language="fortran"),
    ExtLangPair(ext=".fr", language="frege"),
    ExtLangPair(ext=".fs", language="fsharp"),
    ExtLangPair(ext=".fsi", language="fsharp"),
    ExtLangPair(ext=".fsx", language="fsharp"),
    ExtLangPair(ext=".gleam", language="gleam"),
    ExtLangPair(ext=".gql", language="graphql"),
    ExtLangPair(ext=".graphql", language="graphql"),
    ExtLangPair(ext=".graphqls", language="graphql"),
    ExtLangPair(ext=".groovy", language="groovy"),
    ExtLangPair(ext=".gs", language="gosu"),
    ExtLangPair(ext=".hack", language="hack"),
    ExtLangPair(ext=".hck", language="hack"),
    ExtLangPair(ext=".hcl", language="hcl"),
    ExtLangPair(ext=".hhi", language="hack"),
    ExtLangPair(ext=".hjson", language="hjson"),
    ExtLangPair(ext=".hlsl", language="hlsl"),
    ExtLangPair(ext=".hrl", language="erlang"),
    ExtLangPair(ext=".hrl", language="erlang"),
    ExtLangPair(ext=".idr", language="idris"),
    ExtLangPair(ext=".imba", language="imba"),
    ExtLangPair(ext=".io", language="io"),
    ExtLangPair(ext=".its", language="devicetree"),
    ExtLangPair(ext=".janet", language="janet"),
    ExtLangPair(ext=".jdn", language="janet"),
    ExtLangPair(ext=".jelly", language="jelly"),
    ExtLangPair(ext=".jl", language="julia"),
    ExtLangPair(ext=".joke", language="clojure"),
    ExtLangPair(ext=".joker", language="clojure"),
    ExtLangPair(ext=".jule", language="jule"),
    ExtLangPair(ext=".less", language="less"),
    ExtLangPair(ext=".lidr", language="idris"),
    ExtLangPair(ext=".lisp", language="lisp"),
    ExtLangPair(ext=".lpr", language="pascal"),
    ExtLangPair(ext=".ls", language="livescript"),
    ExtLangPair(ext=".lsc", language="lisp"),
    ExtLangPair(ext=".lsp", language="lisp"),
    ExtLangPair(ext=".lucee", language="lucee"),
    ExtLangPair(
        ext=".m", language="matlab"
    ),  # .m is also objective-c, octave, and mercury, but these days, matlab is most likely IMO for active projects
    ExtLangPair(ext=".mak", language="make"),
    ExtLangPair(ext=".makefile", language="make"),
    ExtLangPair(ext=".mk", language="make"),
    ExtLangPair(ext=".ml", language="ocaml"),
    ExtLangPair(ext=".mli", language="ocaml"),
    ExtLangPair(ext=".mm", language="objective-c"),
    ExtLangPair(ext=".mojo", language="mojo"),
    ExtLangPair(ext=".move", language="move"),
    ExtLangPair(ext=".nh", language="newick"),
    ExtLangPair(ext=".nhx", language="newick"),
    ExtLangPair(ext=".nim", language="nimble"),
    ExtLangPair(ext=".nim.cfg", language="nimble"),
    ExtLangPair(ext=".nim.cfg", language="nimble"),
    ExtLangPair(ext=".nimble", language="nimble"),
    ExtLangPair(ext=".nimble.cfg", language="nimble"),
    ExtLangPair(ext=".nimble.json", language="nimble"),
    ExtLangPair(ext=".nimble.toml", language="nimble"),
    ExtLangPair(ext=".nomad", language="hcl"),
    ExtLangPair(ext=".nu", language="nushell"),
    ExtLangPair(ext=".nushell", language="nushell"),
    ExtLangPair(ext=".nwk", language="newick"),
    ExtLangPair(ext=".odin", language="odin"),
    ExtLangPair(ext=".pas", language="pascal"),
    ExtLangPair(ext=".pascal", language="pascal"),
    ExtLangPair(ext=".pgsql", language="sql"),
    ExtLangPair(ext=".pharo", language="pharo"),
    ExtLangPair(ext=".pkl", language="pkl"),
    ExtLangPair(ext=".pl", language="perl"),
    ExtLangPair(ext=".pm", language="perl"),
    ExtLangPair(ext=".pony", language="pony"),
    ExtLangPair(ext=".pp", language="pascal"),
    ExtLangPair(ext=".proto", language="protobuf"),
    ExtLangPair(ext=".ps1", language="powershell"),
    ExtLangPair(ext=".psm1", language="powershell"),
    ExtLangPair(ext=".pssc", language="powershell"),
    ExtLangPair(ext=".purs", language="purescript"),
    ExtLangPair(ext=".pxd", language="cython"),
    ExtLangPair(ext=".pyx", language="cython"),
    ExtLangPair(ext=".qb64", language="qb64"),
    ExtLangPair(ext=".qml", language="qml"),
    ExtLangPair(ext=".r", language="r"),
    ExtLangPair(ext=".raku", language="raku"),
    ExtLangPair(ext=".rakudoc", language="raku"),
    ExtLangPair(ext=".rakudoc", language="rakudo"),
    ExtLangPair(ext=".rd", language="r"),
    ExtLangPair(ext=".re", language="reason"),
    ExtLangPair(ext=".red", language="red"),
    ExtLangPair(ext=".reds", language="red"),
    ExtLangPair(ext=".res", language="rescript"),
    ExtLangPair(ext=".rescript", language="rescript"),
    ExtLangPair(ext=".ring", language="ring"),
    ExtLangPair(ext=".rkt", language="racket"),
    ExtLangPair(ext=".rktd", language="racket"),
    ExtLangPair(ext=".rktl", language="racket"),
    ExtLangPair(ext=".rsx", language="r"),
    ExtLangPair(ext=".s", language="assembly"),
    ExtLangPair(ext=".sas", language="sas"),
    ExtLangPair(ext=".sass", language="sass"),
    ExtLangPair(ext=".sc", language="scheme"),
    ExtLangPair(ext=".sch", language="scheme"),
    ExtLangPair(ext=".scheme", language="scheme"),
    ExtLangPair(ext=".scm", language="scheme"),
    ExtLangPair(ext=".scss", language="scss"),
    ExtLangPair(ext=".sld", language="scheme"),
    ExtLangPair(ext=".smali", language="smali"),
    ExtLangPair(ext=".sql", language="sql"),
    ExtLangPair(ext=".sqlite", language="sql"),
    ExtLangPair(ext=".sqlite3", language="sql"),
    ExtLangPair(ext=".sty", language="latex"),
    ExtLangPair(ext=".rei", language="reason"),
    ExtLangPair(
        ext=".sv", language="verilog"
    ),  # systemverilog -- more likely these days than `v` for verilog
    ExtLangPair(ext=".svelte", language="svelte"),
    ExtLangPair(ext=".svh", language="verilog"),
    ExtLangPair(ext=".tex", language="latex"),
    ExtLangPair(ext=".textproto", language="protobuf"),
    ExtLangPair(ext=".tf", language="hcl"),
    ExtLangPair(ext=".tfvars", language="hcl"),
    ExtLangPair(ext=".txtpb", language="protobuf"),
    ExtLangPair(
        ext=".v", language="coq"
    ),  # coq vernacular files -- could also be verilog. We have a parser for coq so we'll default to that.
    ExtLangPair(ext=".vala", language="vala"),
    ExtLangPair(ext=".vale", language="vale"),
    ExtLangPair(ext=".vapi", language="vala"),
    ExtLangPair(ext=".vbs", language="vbscript"),
    ExtLangPair(ext=".vhd", language="vhdl"),
    ExtLangPair(ext=".vhdl", language="vhdl"),
    ExtLangPair(ext=".vlang", language="vlang"),
    ExtLangPair(ext=".vls", language="vlang"),
    ExtLangPair(ext=".vsh", language="vlang"),
    ExtLangPair(ext=".vue", language="vue"),
    ExtLangPair(ext=".workflow", language="hcl"),
    ExtLangPair(ext=".xhtml", language="xml"),
    ExtLangPair(ext=".xlf", language="xml"),
    ExtLangPair(ext=".xml", language="xml"),
    ExtLangPair(ext=".xrl", language="erlang"),
    ExtLangPair(ext=".xsd", language="xml"),
    ExtLangPair(ext=".xsl", language="xml"),
    ExtLangPair(ext=".yrl", language="erlang"),
    ExtLangPair(ext=".zig", language="zig"),
    ExtLangPair(ext="BSDmakefile", language="make"),
    ExtLangPair(ext="CMakefile", language="cmake"),
    ExtLangPair(ext="Cask", language="emacs"),
    ExtLangPair(ext="Dockerfile", language="docker"),
    ExtLangPair(ext="Emakefile", language="erlang"),
    ExtLangPair(ext="GNUmakefile", language="make"),
    ExtLangPair(ext="Justfile", language="just"),
    ExtLangPair(ext="Kbuild", language="make"),
    ExtLangPair(ext="Makefile", language="make"),
    ExtLangPair(ext="Makefile.am", language="make"),
    ExtLangPair(ext="Makefile.boot", language="make"),
    ExtLangPair(ext="Makefile.in", language="make"),
    ExtLangPair(ext="Makefile.inc", language="make"),
    ExtLangPair(ext="Makefile.wat", language="make"),
    ExtLangPair(ext="Rakefile", language="rake"),
    ExtLangPair(ext="_emacs", language="emacs"),
    ExtLangPair(ext="makefile", language="make"),
    ExtLangPair(ext="makefile.sco", language="make"),
    ExtLangPair(ext="mkfile", language="make"),
    ExtLangPair(ext="rebar.config", language="erlang"),
    # We're only going to cover the main ones for VB6, but langchain has a splitter for it so we'll support it.
    ExtLangPair(ext=".bas", language="visualbasic6"),
    ExtLangPair(ext=".cls", language="visualbasic6"),
    ExtLangPair(ext=".ctl", language="visualbasic6"),
    ExtLangPair(ext=".frm", language="visualbasic6"),
    ExtLangPair(ext=".pag", language="visualbasic6"),
    ExtLangPair(ext=".res", language="visualbasic6"),
    ExtLangPair(ext=".vb", language="visualbasic6"),
    ExtLangPair(ext=".vba", language="visualbasic6"),
    ExtLangPair(ext=".vbg", language="visualbasic6"),
    ExtLangPair(ext=".vbi", language="visualbasic6"),
    ExtLangPair(ext=".vbp", language="visualbasic6"),
)
# spellchecker:on
"""A tuple of `ExtLangPair`."""


class FallBackTestDef(TypedDict):
    """Definition for a fallback test based on file content."""

    values: tuple[LiteralStringT, ...]
    """The values to check for in the file content."""
    on: Literal["in", "not in"]
    """The condition to check: 'in' or 'not in'. Not in will check that none of the values are present. 'in' will check that at least one value is present."""
    fallback_to: LiteralStringT
    """The language to fallback to if the test passes."""


type FallbackInputExtension = Literal[".m", ".v"]
type FallbackLanguage = Literal["matlab", "coq", "objective-c", "verilog"]

FALLBACK_TEST: MappingProxyType[FallbackInputExtension, FallBackTestDef] = MappingProxyType({
    ".v": {
        "values": ("Proof", "Qed", "Proof", "Defined", "Admitted"),
        "on": "not in",
        "fallback_to": "verilog",
    },
    ".m": {
        "values": ("switch", "end", "parfor", "function"),
        "on": "not in",
        "fallback_to": "objective-c",
    },
})
"""A mapping of file extensions to their fallback test definitions."""


CONFIG_FILE_LANGUAGES = frozenset({
    "bash",
    "cfg",
    "cmake",
    "docker",
    "hcl",
    "ini",
    "json",
    "json5",
    "jsonc",
    "just",
    "make",
    "pkl",
    "properties",
    "toml",
    "xml",
    "yaml",
})


def _get_languages_helper() -> tuple[
    frozenset[LiteralStringT],
    frozenset[LiteralStringT],
    frozenset[LiteralStringT],
    frozenset[LiteralStringT],
]:
    """Helper function to get all languages as frozensets."""
    code_langs: set[LiteralStringT] = {ext.language for ext in CODE_FILES_EXTENSIONS}
    data_langs: set[LiteralStringT] = {ext.language for ext in DATA_FILES_EXTENSIONS}
    doc_langs: set[LiteralStringT] = {ext.language for ext in DOC_FILES_EXTENSIONS}
    all_langs: set[LiteralStringT] = code_langs | data_langs | doc_langs
    return frozenset(code_langs), frozenset(data_langs), frozenset(doc_langs), frozenset(all_langs)


CODE_LANGUAGES, DATA_LANGUAGES, DOCS_LANGUAGES, ALL_LANGUAGES = _get_languages_helper()
"""Frozen sets of languages for code, data, documentation, and all combined."""

SEMANTIC_KINDS = MappingProxyType({
    "python": {
        "function_definition",
        "class_definition",
        "import_statement",
        "import_from_statement",
    },
    "javascript": {
        "function_declaration",
        "function_expression",
        "class_declaration",
        "method_definition",
        "import_statement",
    },
    "typescript": {
        "function_declaration",
        "function_expression",
        "class_declaration",
        "method_definition",
        "interface_declaration",
        "import_statement",
    },
    "java": {
        "method_declaration",
        "class_declaration",
        "interface_declaration",
        "import_declaration",
    },
    "rust": {"function_item", "struct_item", "impl_item", "trait_item", "use_declaration"},
    "go": {"function_declaration", "method_declaration", "type_declaration", "import_declaration"},
    "cpp": {
        "function_definition",
        "class_specifier",
        "namespace_definition",
        "template_declaration",
    },
    "c": {"function_definition", "struct_specifier", "typedef_declaration"},
})


def get_ext_lang_pairs(*, include_data: bool = False) -> Generator[ExtLangPair]:
    """Yield all `ExtLangPair` instances for code, config, and docs files."""
    if include_data:
        yield from (*CODE_FILES_EXTENSIONS, *DATA_FILES_EXTENSIONS, *DOC_FILES_EXTENSIONS)
    yield from (*CODE_FILES_EXTENSIONS, *DOC_FILES_EXTENSIONS)


def _run_fallback_test(extension: FallbackInputExtension, path: Path) -> FallbackLanguage:
    """Run the fallback test for a given extension and file path."""
    if extension in FALLBACK_TEST and path.is_file():
        test_def = FALLBACK_TEST[extension]
        with contextlib.suppress(Exception):
            content = path.read_text(errors="ignore")
            if (
                test_def["on"] == "in" and any(value in content for value in test_def["values"])
            ) or (
                test_def["on"] == "not in"
                and all(value not in content for value in test_def["values"])
            ):
                return cast(FallbackLanguage, test_def["fallback_to"])
    return_value = "matlab" if extension == ".m" else "coq"
    return cast(FallbackLanguage, return_value)


def get_ext_lang_pair_for_file(
    file_path: Path, *, include_data: bool = False
) -> ExtLangPair | None:
    """Get the `ExtLangPair` for a given file path."""
    if not file_path.is_file():
        return None
    filename = file_path.name
    for pair in get_ext_lang_pairs(include_data=include_data):
        if pair.is_same(filename):
            if pair.ext in FALLBACK_TEST:
                language = _run_fallback_test(cast(FallbackInputExtension, pair.ext), file_path)
                return ExtLangPair(ext=pair.ext, language=language)
            return pair
    return None


def get_language_from_extension(
    extension: LiteralStringT, *, path: Path | None = None
) -> LiteralStringT | None:
    """Get the language associated with a given file extension."""
    if extension in FALLBACK_TEST and path and path.is_file():
        return _run_fallback_test(cast(FallbackInputExtension, extension), path)
    return next(
        (pair.language for pair in get_ext_lang_pairs(include_data=True) if pair.ext == extension),
        None,
    )


__all__ = (
    "ALL_LANGUAGES",
    "CODE_FILES_EXTENSIONS",
    "CODE_LANGUAGES",
    "CONFIG_FILE_LANGUAGES",
    "DATA_FILES_EXTENSIONS",
    "DATA_LANGUAGES",
    "DEFAULT_EXCLUDED_DIRS",
    "DEFAULT_EXCLUDED_EXTENSIONS",
    "DOCS_LANGUAGES",
    "DOC_FILES_EXTENSIONS",
    "FALLBACK_TEST",
    "ExtLangPair",
    "FallBackTestDef",
    "get_ext_lang_pairs",
    "get_language_from_extension",
)
