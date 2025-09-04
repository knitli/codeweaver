# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""
Constants used throughout the CodeWeaver project, primarily for default configurations.
"""

from collections.abc import Generator
from typing import Literal, NamedTuple

from codeweaver._common import LiteralStringT


METADATA_PATH = "metadata"


class ExtLangPair(NamedTuple):
    """
    Mapping of file extensions to their corresponding programming languages.

    Not all 'extensions' are actually file extensions, some are file names or special cases, like `Makefile` or `Dockerfile`.
    """

    ext: LiteralStringT
    """The file extension, including leading dot if it's a file extension."""

    language: LiteralStringT
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

    def is_same(self, filename: str) -> bool:
        """Check if the given filename is the same filetype as the extension."""
        if self.is_actual_ext:
            return filename.endswith(self.ext)
        return filename == self.ext if self.is_file_name else False


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
    "li64",
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
    ".avif",
    ".bmp",
    ".builds",
    ".cache",
    ".class",
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
    ExtLangPair(ext=".R", language="r"),
    ExtLangPair(ext=".Rprofile", language="r"),
    ExtLangPair(ext=".app.src", language="erlang"),
    ExtLangPair(ext=".as", language="assemblyscript"),
    ExtLangPair(ext=".asd", language="lisp"),
    ExtLangPair(ext=".aux", language="latex"),
    ExtLangPair(ext=".bat", language="batch"),
    ExtLangPair(ext=".bb", language="clojure"),
    ExtLangPair(ext=".beef", language="beef"),
    ExtLangPair(ext=".boot", language="clojure"),
    ExtLangPair(ext=".carbon", language="carbon"),
    ExtLangPair(ext=".chapel", language="chapel"),
    ExtLangPair(ext=".clj", language="clojure"),
    ExtLangPair(ext=".cljc", language="clojure"),
    ExtLangPair(ext=".cljs", language="clojure"),
    ExtLangPair(ext=".cljx", language="clojure"),
    ExtLangPair(ext=".cls", language="latex"),
    ExtLangPair(ext=".cmake", language="cmake"),
    ExtLangPair(ext=".coffee", language="coffeescript"),
    ExtLangPair(ext=".cr", language="crystal"),
    ExtLangPair(ext=".cue", language="cue"),
    ExtLangPair(ext=".d", language="dlang"),
    ExtLangPair(ext=".dart", language="dart"),
    ExtLangPair(ext=".dfm", language="pascal"),
    ExtLangPair(ext=".dlang", language="dlang"),
    ExtLangPair(ext=".dpr", language="pascal"),
    ExtLangPair(ext=".dts", language="devicetree"),
    ExtLangPair(ext=".dtsi", language="devicetree"),
    ExtLangPair(ext=".dtso", language="devicetree"),
    ExtLangPair(ext=".edn", language="clojure"),
    ExtLangPair(ext=".el", language="emacs"),
    ExtLangPair(ext=".elm", language="elm"),
    ExtLangPair(ext=".elv", language="elvish"),
    ExtLangPair(ext=".emacs", language="emacs"),
    ExtLangPair(ext=".erl", language="erlang"),
    ExtLangPair(ext=".es", language="erlang"),
    ExtLangPair(ext=".escript", language="erlang"),
    ExtLangPair(ext=".eta", language="eta"),
    ExtLangPair(ext=".factor", language="factor"),
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
    ExtLangPair(ext=".m", language="objective-c"),
    ExtLangPair(ext=".mak", language="make"),
    ExtLangPair(ext=".makefile", language="make"),
    ExtLangPair(ext=".mk", language="make"),
    ExtLangPair(ext=".ml", language="ocaml"),
    ExtLangPair(ext=".mli", language="ocaml"),
    ExtLangPair(ext=".mm", language="objective-c"),
    ExtLangPair(ext=".mojo", language="mojo"),
    ExtLangPair(ext=".nh", language="newick"),
    ExtLangPair(ext=".nhx", language="newick"),
    ExtLangPair(ext=".nim", language="nim"),
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
    ExtLangPair(ext=".pl", language="perl"),
    ExtLangPair(ext=".pm", language="perl"),
    ExtLangPair(ext=".pony", language="pony"),
    ExtLangPair(ext=".pp", language="pascal"),
    ExtLangPair(ext=".ps1", language="powershell"),
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
    ExtLangPair(ext=".red", language="red"),
    ExtLangPair(ext=".reds", language="red"),
    ExtLangPair(ext=".ring", language="ring"),
    ExtLangPair(ext=".rkt", language="racket"),
    ExtLangPair(ext=".rktd", language="racket"),
    ExtLangPair(ext=".rktl", language="racket"),
    ExtLangPair(ext=".rsx", language="r"),
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
    ExtLangPair(ext=".sv", language="verilog"),
    ExtLangPair(ext=".svelte", language="svelte"),
    ExtLangPair(ext=".tex", language="latex"),
    ExtLangPair(ext=".tf", language="hcl"),
    ExtLangPair(ext=".tfvars", language="hcl"),
    ExtLangPair(ext=".v", language="v"),
    ExtLangPair(ext=".v", language="verilog"),
    ExtLangPair(ext=".vale", language="vale"),
    ExtLangPair(ext=".vhd", language="vhdl"),
    ExtLangPair(ext=".vhdl", language="vhdl"),
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
)
# spellchecker:on
"""A tuple of `ExtLangPair`."""

CONFIG_FILE_LANGUAGES = frozenset({
    "bash",
    "yaml",
    "json",
    "toml",
    "ini",
    "make",
    "cmake",
    "xml",
    "cfg",
    "properties",
})

CODE_LANGUAGES = frozenset({ext.language for ext in CODE_FILES_EXTENSIONS})

DOCS_LANGUAGES = frozenset({ext.language for ext in DOC_FILES_EXTENSIONS})


def get_ext_lang_pairs() -> Generator[ExtLangPair]:
    """Yield all `ExtLangPair` instances for code, config, and docs files."""
    yield from (*CODE_FILES_EXTENSIONS, *DOC_FILES_EXTENSIONS)
