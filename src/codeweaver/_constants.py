# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""
Constants used throughout the CodeWeaver project, primarily for default configurations.
"""

from __future__ import annotations

import contextlib

from collections.abc import Callable, Generator
from pathlib import Path
from types import MappingProxyType
from typing import Annotated, Literal, NamedTuple, NewType, TypedDict, cast, overload

from pydantic import Field

from codeweaver._types import LiteralStringT


Extension = NewType("Extension", LiteralStringT)
LanguageName = NewType("LanguageName", LiteralStringT)


METADATA_PATH = "metadata"


class ExtLangPair(NamedTuple):
    """
    Mapping of file extensions to their corresponding programming languages.

    Not all 'extensions' are actually file extensions, some are file names or special cases, like `Makefile` or `Dockerfile`.
    """

    ext: Annotated[Extension, Field(min_length=2, max_length=30, default_factory=Extension)]
    """The file extension, including leading dot if it's a file extension. May also be a full file name."""

    language: Annotated[
        LanguageName, Field(min_length=1, max_length=50, default_factory=LanguageName)
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
    ".eslintcache",
    ".git",
    ".hg",
    ".history",
    ".idea",
    ".jj",
    ".next",
    ".nuxt",
    ".ruff_cache",
    ".svn",
    ".temp",
    ".tmp",
    ".tsbuildinfo",
    ".venv",
    ".vs",
    "Debug",
    "Release",
    "Releases",
    "Thumbs.db",
    "__pycache__",
    "__pytest_cache__",
    "aarch64",
    "arm",
    "arm64",
    "bower_components",
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
    "tmp",
    "vendor",
    "venv",
    "win32",
    "win64",
    "x64",
    "x86",
})

DEFAULT_EXCLUDED_EXTENSIONS: frozenset[Extension] = frozenset({
    Extension(".7z"),
    Extension(".avi"),
    Extension(".avif"),
    Extension(".bmp"),
    Extension(".builds"),
    Extension(".cache"),
    Extension(".class"),
    Extension("codeweaver.local.json"),
    Extension("codeweaver.local.toml"),
    Extension("codeweaver.local.yaml"),
    Extension(".code-workspace"),
    Extension(".coverage"),
    Extension(".coverage.xml"),
    Extension(".dll"),
    Extension(".dmg"),
    Extension(".env"),
    Extension(".exe"),
    Extension(".gif"),
    Extension(".gz"),
    Extension(".iobj"),
    Extension(".jar"),
    Extension(".jpeg"),
    Extension(".jpg"),
    Extension(".lcov"),
    Extension(".local"),
    Extension(".lock"),
    Extension(".log"),
    Extension(".meta"),
    Extension(".mov"),
    Extension(".mp3"),
    Extension(".mp4"),
    Extension(".mpeg"),
    Extension(".mpg"),
    Extension(".ms"),
    Extension(".msi"),
    Extension(".o"),
    Extension(".obj"),
    Extension(".pch"),
    Extension(".pdb"),
    Extension(".pgc"),
    Extension(".pgd"),
    Extension(".png"),
    Extension(".pyc"),
    Extension(".pyo"),
    Extension(".rar"),
    Extension(".rsp"),
    Extension(".scc"),
    Extension(".sig"),
    Extension(".snk"),
    Extension(".so"),
    Extension(".svclog"),
    Extension(".svg"),
    Extension(".swo"),
    Extension(".swp"),
    Extension(".tar"),
    Extension(".temp"),
    Extension(".tlb"),
    Extension(".tlog"),
    Extension(".tmp"),
    Extension(".tmp_proj"),
    Extension(".vspec"),
    Extension(".vssscc"),
    Extension(".wav"),
    Extension(".webm"),
    Extension(".webp"),
    Extension(".zip"),
})

DATA_FILES_EXTENSIONS: tuple[ExtLangPair, ...] = (
    ExtLangPair(ext=Extension(".csv"), language=LanguageName("csv")),
    ExtLangPair(ext=Extension(".dat"), language=LanguageName("data")),
    ExtLangPair(ext=Extension(".db"), language=LanguageName("sql")),
    ExtLangPair(ext=Extension(".dbf"), language=LanguageName("dbf")),
    ExtLangPair(
        ext=Extension(".nw"), language=LanguageName("nw")
    ),  # Node-Webkit (.zip container with .nw extension) files
    ExtLangPair(ext=Extension(".sqlite"), language=LanguageName("sql")),
    ExtLangPair(ext=Extension(".sqlite3"), language=LanguageName("sql")),
    ExtLangPair(ext=Extension(".svg"), language=LanguageName("xml")),
    ExtLangPair(ext=Extension(".tsv"), language=LanguageName("tsv")),
    ExtLangPair(ext=Extension(".xlsx"), language=LanguageName("excel")),
)

DOC_FILES_EXTENSIONS: tuple[ExtLangPair, ...] = (
    ExtLangPair(ext=Extension(".1"), language=LanguageName("man")),
    ExtLangPair(ext=Extension(".2"), language=LanguageName("man")),
    ExtLangPair(ext=Extension(".3"), language=LanguageName("man")),
    ExtLangPair(ext=Extension(".4"), language=LanguageName("man")),
    ExtLangPair(ext=Extension(".5"), language=LanguageName("man")),
    ExtLangPair(ext=Extension(".6"), language=LanguageName("man")),
    ExtLangPair(ext=Extension(".7"), language=LanguageName("man")),
    ExtLangPair(ext=Extension(".8"), language=LanguageName("man")),
    ExtLangPair(ext=Extension(".9"), language=LanguageName("man")),
    ExtLangPair(ext=Extension(".Rmd"), language=LanguageName("rmarkdown")),
    ExtLangPair(ext=Extension(".adoc"), language=LanguageName("asciidoc")),
    ExtLangPair(ext=Extension(".asc"), language=LanguageName("asciidoc")),
    ExtLangPair(ext=Extension(".asciidoc"), language=LanguageName("asciidoc")),
    ExtLangPair(ext=Extension(".bib"), language=LanguageName("latex")),
    ExtLangPair(ext=Extension(".confluence"), language=LanguageName("confluence")),
    ExtLangPair(ext=Extension(".creole"), language=LanguageName("creole")),
    ExtLangPair(ext=Extension(".dita"), language=LanguageName("dita")),
    ExtLangPair(ext=Extension(".docbook"), language=LanguageName("docbook")),
    ExtLangPair(ext=Extension(".help"), language=LanguageName("help")),
    ExtLangPair(ext=Extension(".hlp"), language=LanguageName("help")),
    ExtLangPair(ext=Extension(".info"), language=LanguageName("info")),
    ExtLangPair(ext=Extension(".ipynb"), language=LanguageName("jupyter")),
    ExtLangPair(ext=Extension(".lagda"), language=LanguageName("lagda")),
    ExtLangPair(ext=Extension(".latex"), language=LanguageName("latex")),
    ExtLangPair(ext=Extension(".lhs"), language=LanguageName("lhs")),
    ExtLangPair(ext=Extension(".man"), language=LanguageName("man")),
    ExtLangPair(ext=Extension(".manpage"), language=LanguageName("man")),
    ExtLangPair(ext=Extension(".markdown"), language=LanguageName("markdown")),
    ExtLangPair(ext=Extension(".md"), language=LanguageName("markdown")),
    ExtLangPair(ext=Extension(".mdown"), language=LanguageName("markdown")),
    ExtLangPair(ext=Extension(".mdx"), language=LanguageName("markdown")),
    ExtLangPair(ext=Extension(".mediawiki"), language=LanguageName("mediawiki")),
    ExtLangPair(ext=Extension(".mkd"), language=LanguageName("markdown")),
    ExtLangPair(ext=Extension(".mkdn"), language=LanguageName("markdown")),
    ExtLangPair(ext=Extension(".org"), language=LanguageName("org")),
    ExtLangPair(ext=Extension(".pod"), language=LanguageName("pod")),
    ExtLangPair(ext=Extension(".pyx"), language=LanguageName("cython")),
    ExtLangPair(ext=Extension(".rdoc"), language=LanguageName("markdown")),
    ExtLangPair(ext=Extension(".rest"), language=LanguageName("restructuredtext")),
    ExtLangPair(ext=Extension(".rmd"), language=LanguageName("rmd")),
    ExtLangPair(ext=Extension(".rnw"), language=LanguageName("rnw")),
    ExtLangPair(ext=Extension(".rst"), language=LanguageName("restructuredtext")),
    ExtLangPair(ext=Extension(".rtf"), language=LanguageName("rtf")),
    ExtLangPair(ext=Extension(".tex"), language=LanguageName("latex")),
    ExtLangPair(ext=Extension(".texi"), language=LanguageName("texinfo")),
    ExtLangPair(ext=Extension(".texinfo"), language=LanguageName("texinfo")),
    ExtLangPair(ext=Extension(".text"), language=LanguageName("text")),
    ExtLangPair(ext=Extension(".textile"), language=LanguageName("textile")),
    ExtLangPair(ext=Extension(".txt"), language=LanguageName("text")),
    ExtLangPair(ext=Extension(".wiki"), language=LanguageName("wiki")),
    ExtLangPair(ext=Extension(".xml"), language=LanguageName("xml")),
    ExtLangPair(ext=Extension(".yard"), language=LanguageName("yard")),
)
"""A tuple of `ExtLangPair` for documentation files."""

# spellchecker:off
CODE_FILES_EXTENSIONS: tuple[ExtLangPair, ...] = (
    ExtLangPair(ext=Extension(".F"), language=LanguageName("fortran")),
    ExtLangPair(ext=Extension(".R"), language=LanguageName("r")),
    ExtLangPair(ext=Extension(".Rprofile"), language=LanguageName("r")),
    ExtLangPair(ext=Extension(".app.src"), language=LanguageName("erlang")),
    ExtLangPair(ext=Extension(".as"), language=LanguageName("assemblyscript")),
    ExtLangPair(ext=Extension(".asd"), language=LanguageName("lisp")),
    ExtLangPair(ext=Extension(".asm"), language=LanguageName("assembly")),
    ExtLangPair(ext=Extension(".aux"), language=LanguageName("latex")),
    ExtLangPair(ext=Extension(".astro"), language=LanguageName("astro")),
    ExtLangPair(ext=Extension(".bat"), language=LanguageName("batch")),
    ExtLangPair(ext=Extension(".bb"), language=LanguageName("clojure")),
    ExtLangPair(ext=Extension(".beef"), language=LanguageName("beef")),
    ExtLangPair(ext=Extension(".binpb"), language=LanguageName("protobuf")),
    ExtLangPair(ext=Extension(".boot"), language=LanguageName("clojure")),
    ExtLangPair(ext=Extension(".carbon"), language=LanguageName("carbon")),
    ExtLangPair(ext=Extension(".cbl"), language=LanguageName("cobol")),
    ExtLangPair(ext=Extension(".chapel"), language=LanguageName("chapel")),
    ExtLangPair(ext=Extension(".clj"), language=LanguageName("clojure")),
    ExtLangPair(ext=Extension(".cljc"), language=LanguageName("clojure")),
    ExtLangPair(ext=Extension(".cljs"), language=LanguageName("clojure")),
    ExtLangPair(ext=Extension(".cljx"), language=LanguageName("clojure")),
    ExtLangPair(ext=Extension(".cls"), language=LanguageName("latex")),
    ExtLangPair(ext=Extension(".cmake"), language=LanguageName("cmake")),
    ExtLangPair(ext=Extension(".cob"), language=LanguageName("cobol")),
    ExtLangPair(ext=Extension(".cobol"), language=LanguageName("cobol")),
    ExtLangPair(ext=Extension(".coffee"), language=LanguageName("coffeescript")),
    ExtLangPair(ext=Extension(".cr"), language=LanguageName("crystal")),
    ExtLangPair(ext=Extension(".cu"), language=LanguageName("cuda")),
    ExtLangPair(ext=Extension(".cue"), language=LanguageName("cue")),
    ExtLangPair(ext=Extension(".cuh"), language=LanguageName("cuda")),
    ExtLangPair(ext=Extension(".d"), language=LanguageName("dlang")),
    ExtLangPair(ext=Extension(".dart"), language=LanguageName("dart")),
    ExtLangPair(ext=Extension(".dfm"), language=LanguageName("pascal")),
    ExtLangPair(ext=Extension(".dhall"), language=LanguageName("dhall")),
    ExtLangPair(ext=Extension(".dlang"), language=LanguageName("dlang")),
    ExtLangPair(ext=Extension(".dpr"), language=LanguageName("pascal")),
    ExtLangPair(ext=Extension(".dts"), language=LanguageName("devicetree")),
    ExtLangPair(ext=Extension(".dtsi"), language=LanguageName("devicetree")),
    ExtLangPair(ext=Extension(".dtso"), language=LanguageName("devicetree")),
    ExtLangPair(ext=Extension(".duck"), language=LanguageName("duck")),
    ExtLangPair(ext=Extension(".dyck"), language=LanguageName("dyck")),
    ExtLangPair(ext=Extension(".e"), language=LanguageName("eiffel")),
    ExtLangPair(ext=Extension(".ecl"), language=LanguageName("ecl")),
    ExtLangPair(ext=Extension(".eclsp"), language=LanguageName("ecl")),
    ExtLangPair(ext=Extension(".eclxml"), language=LanguageName("ecl")),
    ExtLangPair(ext=Extension(".edn"), language=LanguageName("clojure")),
    ExtLangPair(ext=Extension(".el"), language=LanguageName("emacs")),
    ExtLangPair(ext=Extension(".elm"), language=LanguageName("elm")),
    ExtLangPair(ext=Extension(".elv"), language=LanguageName("elvish")),
    ExtLangPair(ext=Extension(".emacs"), language=LanguageName("emacs")),
    ExtLangPair(ext=Extension(".erl"), language=LanguageName("erlang")),
    ExtLangPair(ext=Extension(".es"), language=LanguageName("erlang")),
    ExtLangPair(ext=Extension(".escript"), language=LanguageName("erlang")),
    ExtLangPair(ext=Extension(".eta"), language=LanguageName("eta")),
    ExtLangPair(ext=Extension(".f"), language=LanguageName("fortran")),
    ExtLangPair(ext=Extension(".f03"), language=LanguageName("fortran")),
    ExtLangPair(ext=Extension(".f08"), language=LanguageName("fortran")),
    ExtLangPair(ext=Extension(".f18"), language=LanguageName("fortran")),
    ExtLangPair(ext=Extension(".f23"), language=LanguageName("fortran")),
    ExtLangPair(ext=Extension(".f90"), language=LanguageName("fortran")),
    ExtLangPair(ext=Extension(".f95"), language=LanguageName("fortran")),
    ExtLangPair(ext=Extension(".factor"), language=LanguageName("factor")),
    ExtLangPair(ext=Extension(".for"), language=LanguageName("fortran")),
    ExtLangPair(ext=Extension(".fr"), language=LanguageName("frege")),
    ExtLangPair(ext=Extension(".fs"), language=LanguageName("fsharp")),
    ExtLangPair(ext=Extension(".fsi"), language=LanguageName("fsharp")),
    ExtLangPair(ext=Extension(".fsx"), language=LanguageName("fsharp")),
    ExtLangPair(ext=Extension(".gleam"), language=LanguageName("gleam")),
    ExtLangPair(ext=Extension(".gql"), language=LanguageName("graphql")),
    ExtLangPair(ext=Extension(".graphql"), language=LanguageName("graphql")),
    ExtLangPair(ext=Extension(".graphqls"), language=LanguageName("graphql")),
    ExtLangPair(ext=Extension(".groovy"), language=LanguageName("groovy")),
    ExtLangPair(ext=Extension(".gs"), language=LanguageName("gosu")),
    ExtLangPair(ext=Extension(".hack"), language=LanguageName("hack")),
    ExtLangPair(ext=Extension(".hck"), language=LanguageName("hack")),
    ExtLangPair(ext=Extension(".hcl"), language=LanguageName("hcl")),
    ExtLangPair(ext=Extension(".hhi"), language=LanguageName("hack")),
    ExtLangPair(ext=Extension(".hjson"), language=LanguageName("hjson")),
    ExtLangPair(ext=Extension(".hlsl"), language=LanguageName("hlsl")),
    ExtLangPair(ext=Extension(".hrl"), language=LanguageName("erlang")),
    ExtLangPair(ext=Extension(".hrl"), language=LanguageName("erlang")),
    ExtLangPair(ext=Extension(".idr"), language=LanguageName("idris")),
    ExtLangPair(ext=Extension(".imba"), language=LanguageName("imba")),
    ExtLangPair(ext=Extension(".io"), language=LanguageName("io")),
    ExtLangPair(ext=Extension(".its"), language=LanguageName("devicetree")),
    ExtLangPair(ext=Extension(".janet"), language=LanguageName("janet")),
    ExtLangPair(ext=Extension(".jdn"), language=LanguageName("janet")),
    ExtLangPair(ext=Extension(".jelly"), language=LanguageName("jelly")),  # jenkins
    ExtLangPair(ext=Extension(".jinja"), language=LanguageName("jinja")),
    ExtLangPair(ext=Extension(".jinja2"), language=LanguageName("jinja")),
    ExtLangPair(ext=Extension(".jl"), language=LanguageName("julia")),
    ExtLangPair(ext=Extension(".joke"), language=LanguageName("clojure")),
    ExtLangPair(ext=Extension(".joker"), language=LanguageName("clojure")),
    ExtLangPair(ext=Extension(".jule"), language=LanguageName("jule")),
    ExtLangPair(ext=Extension(".less"), language=LanguageName("less")),
    ExtLangPair(ext=Extension(".lidr"), language=LanguageName("idris")),
    ExtLangPair(ext=Extension(".lisp"), language=LanguageName("lisp")),
    ExtLangPair(ext=Extension(".lpr"), language=LanguageName("pascal")),
    ExtLangPair(ext=Extension(".ls"), language=LanguageName("livescript")),
    ExtLangPair(ext=Extension(".lsc"), language=LanguageName("lisp")),
    ExtLangPair(ext=Extension(".lsp"), language=LanguageName("lisp")),
    ExtLangPair(ext=Extension(".lucee"), language=LanguageName("lucee")),
    ExtLangPair(ext=Extension(".m"), language=LanguageName("matlab")),
    ExtLangPair(ext=Extension(".mak"), language=LanguageName("make")),
    ExtLangPair(ext=Extension(".makefile"), language=LanguageName("make")),
    ExtLangPair(ext=Extension(".mk"), language=LanguageName("make")),
    ExtLangPair(ext=Extension(".ml"), language=LanguageName("ocaml")),
    ExtLangPair(ext=Extension(".mli"), language=LanguageName("ocaml")),
    ExtLangPair(ext=Extension(".mm"), language=LanguageName("objective-c")),
    ExtLangPair(ext=Extension(".mojo"), language=LanguageName("mojo")),
    ExtLangPair(ext=Extension(".move"), language=LanguageName("move")),
    ExtLangPair(ext=Extension(".nh"), language=LanguageName("newick")),
    ExtLangPair(ext=Extension(".nhx"), language=LanguageName("newick")),
    ExtLangPair(ext=Extension(".nim"), language=LanguageName("nimble")),
    ExtLangPair(ext=Extension(".nim.cfg"), language=LanguageName("nimble")),
    ExtLangPair(ext=Extension(".nim.cfg"), language=LanguageName("nimble")),
    ExtLangPair(ext=Extension(".nimble"), language=LanguageName("nimble")),
    ExtLangPair(ext=Extension(".nimble.cfg"), language=LanguageName("nimble")),
    ExtLangPair(ext=Extension(".nimble.json"), language=LanguageName("json")),
    ExtLangPair(ext=Extension(".nimble.toml"), language=LanguageName("toml")),
    ExtLangPair(ext=Extension(".nomad"), language=LanguageName("hcl")),
    ExtLangPair(ext=Extension(".nu"), language=LanguageName("nushell")),
    ExtLangPair(ext=Extension(".nushell"), language=LanguageName("nushell")),
    ExtLangPair(ext=Extension(".nwk"), language=LanguageName("newick")),
    ExtLangPair(ext=Extension(".odin"), language=LanguageName("odin")),
    ExtLangPair(ext=Extension(".pas"), language=LanguageName("pascal")),
    ExtLangPair(ext=Extension(".pascal"), language=LanguageName("pascal")),
    ExtLangPair(ext=Extension(".pgsql"), language=LanguageName("sql")),
    ExtLangPair(ext=Extension(".pharo"), language=LanguageName("pharo")),
    ExtLangPair(ext=Extension(".pkl"), language=LanguageName("pkl")),
    ExtLangPair(ext=Extension(".pl"), language=LanguageName("perl")),
    ExtLangPair(ext=Extension(".pm"), language=LanguageName("perl")),
    ExtLangPair(ext=Extension(".pony"), language=LanguageName("pony")),
    ExtLangPair(ext=Extension(".pp"), language=LanguageName("pascal")),
    ExtLangPair(ext=Extension(".proto"), language=LanguageName("protobuf")),
    ExtLangPair(ext=Extension(".ps1"), language=LanguageName("powershell")),
    ExtLangPair(ext=Extension(".psm1"), language=LanguageName("powershell")),
    ExtLangPair(ext=Extension(".pssc"), language=LanguageName("powershell")),
    ExtLangPair(ext=Extension(".purs"), language=LanguageName("purescript")),
    ExtLangPair(ext=Extension(".pxd"), language=LanguageName("cython")),
    ExtLangPair(ext=Extension(".pyx"), language=LanguageName("cython")),
    ExtLangPair(ext=Extension(".qb64"), language=LanguageName("qb64")),
    ExtLangPair(ext=Extension(".qml"), language=LanguageName("qml")),
    ExtLangPair(ext=Extension(".r"), language=LanguageName("r")),
    ExtLangPair(ext=Extension(".raku"), language=LanguageName("raku")),
    ExtLangPair(ext=Extension(".rakudoc"), language=LanguageName("raku")),
    ExtLangPair(ext=Extension(".rakudoc"), language=LanguageName("rakudo")),
    ExtLangPair(ext=Extension(".rd"), language=LanguageName("r")),
    ExtLangPair(ext=Extension(".re"), language=LanguageName("reason")),
    ExtLangPair(ext=Extension(".red"), language=LanguageName("red")),
    ExtLangPair(ext=Extension(".reds"), language=LanguageName("red")),
    ExtLangPair(ext=Extension(".rei"), language=LanguageName("reason")),
    ExtLangPair(ext=Extension(".res"), language=LanguageName("rescript")),
    ExtLangPair(ext=Extension(".rescript"), language=LanguageName("rescript")),
    ExtLangPair(ext=Extension(".ring"), language=LanguageName("ring")),
    ExtLangPair(ext=Extension(".rkt"), language=LanguageName("racket")),
    ExtLangPair(ext=Extension(".rktd"), language=LanguageName("racket")),
    ExtLangPair(ext=Extension(".rktl"), language=LanguageName("racket")),
    ExtLangPair(ext=Extension(".rsx"), language=LanguageName("r")),
    ExtLangPair(ext=Extension(".s"), language=LanguageName("assembly")),
    ExtLangPair(ext=Extension(".sas"), language=LanguageName("sas")),
    ExtLangPair(ext=Extension(".sass"), language=LanguageName("sass")),
    ExtLangPair(ext=Extension(".sc"), language=LanguageName("scheme")),
    ExtLangPair(ext=Extension(".sch"), language=LanguageName("scheme")),
    ExtLangPair(ext=Extension(".scheme"), language=LanguageName("scheme")),
    ExtLangPair(ext=Extension(".scm"), language=LanguageName("scheme")),
    ExtLangPair(ext=Extension(".scss"), language=LanguageName("scss")),
    ExtLangPair(ext=Extension(".sld"), language=LanguageName("scheme")),
    ExtLangPair(ext=Extension(".smali"), language=LanguageName("smali")),
    ExtLangPair(ext=Extension(".sml"), language=LanguageName("sml")),  # Standard ML
    ExtLangPair(ext=Extension(".sql"), language=LanguageName("sql")),
    ExtLangPair(ext=Extension(".sqlite"), language=LanguageName("sql")),
    ExtLangPair(ext=Extension(".sqlite3"), language=LanguageName("sql")),
    ExtLangPair(ext=Extension(".sty"), language=LanguageName("latex")),
    ExtLangPair(
        ext=Extension(".sv"), language=LanguageName("verilog")
    ),  # systemverilog -- more likely these days than `v` for verilog
    ExtLangPair(ext=Extension(".svelte"), language=LanguageName("svelte")),
    ExtLangPair(ext=Extension(".svh"), language=LanguageName("verilog")),
    ExtLangPair(ext=Extension(".tex"), language=LanguageName("latex")),
    ExtLangPair(ext=Extension(".textproto"), language=LanguageName("protobuf")),
    ExtLangPair(ext=Extension(".tf"), language=LanguageName("hcl")),
    ExtLangPair(ext=Extension(".tfvars"), language=LanguageName("hcl")),
    ExtLangPair(ext=Extension(".txtpb"), language=LanguageName("protobuf")),
    ExtLangPair(
        ext=Extension(".v"), language=LanguageName("coq")
    ),  # coq vernacular files -- could also be verilog. We have a parser for coq so we'll default to that.
    ExtLangPair(ext=Extension(".vala"), language=LanguageName("vala")),
    ExtLangPair(ext=Extension(".vale"), language=LanguageName("vale")),
    ExtLangPair(ext=Extension(".vapi"), language=LanguageName("vala")),
    ExtLangPair(ext=Extension(".vbs"), language=LanguageName("vbscript")),
    ExtLangPair(ext=Extension(".vhd"), language=LanguageName("vhdl")),
    ExtLangPair(ext=Extension(".vhdl"), language=LanguageName("vhdl")),
    ExtLangPair(ext=Extension(".vlang"), language=LanguageName("vlang")),
    ExtLangPair(ext=Extension(".vls"), language=LanguageName("vlang")),
    ExtLangPair(ext=Extension(".vsh"), language=LanguageName("vlang")),
    ExtLangPair(ext=Extension(".vue"), language=LanguageName("vue")),
    ExtLangPair(ext=Extension(".workflow"), language=LanguageName("hcl")),
    ExtLangPair(ext=Extension(".xaml"), language=LanguageName("xml")),
    ExtLangPair(ext=Extension(".xhtml"), language=LanguageName("xml")),
    ExtLangPair(ext=Extension(".xib"), language=LanguageName("xml")),
    ExtLangPair(ext=Extension(".xlf"), language=LanguageName("xml")),
    ExtLangPair(ext=Extension(".xlf"), language=LanguageName("xml")),
    ExtLangPair(ext=Extension(".xmi"), language=LanguageName("xml")),
    ExtLangPair(ext=Extension(".xml"), language=LanguageName("xml")),
    ExtLangPair(ext=Extension(".xml.dist"), language=LanguageName("xml")),
    ExtLangPair(ext=Extension(".xml.in"), language=LanguageName("xml")),
    ExtLangPair(ext=Extension(".xml.inc"), language=LanguageName("xml")),
    ExtLangPair(ext=Extension(".xrl"), language=LanguageName("erlang")),
    ExtLangPair(ext=Extension(".xsd"), language=LanguageName("xml")),
    ExtLangPair(ext=Extension(".xsh"), language=LanguageName("xonsh")),
    ExtLangPair(ext=Extension(".xsl"), language=LanguageName("xml")),
    ExtLangPair(ext=Extension(".yrl"), language=LanguageName("erlang")),
    ExtLangPair(ext=Extension(".zig"), language=LanguageName("zig")),
    ExtLangPair(ext=Extension(".zsh"), language=LanguageName("zsh")),
    ExtLangPair(ext=Extension("BSDmakefile"), language=LanguageName("make")),
    ExtLangPair(ext=Extension("CMakefile"), language=LanguageName("cmake")),
    ExtLangPair(ext=Extension("Cask"), language=LanguageName("emacs")),
    ExtLangPair(ext=Extension("Dockerfile"), language=LanguageName("docker")),
    ExtLangPair(ext=Extension("Emakefile"), language=LanguageName("erlang")),
    ExtLangPair(ext=Extension("GNUmakefile"), language=LanguageName("make")),
    ExtLangPair(ext=Extension("Justfile"), language=LanguageName("just")),
    ExtLangPair(ext=Extension("Kbuild"), language=LanguageName("make")),
    ExtLangPair(ext=Extension("Makefile"), language=LanguageName("make")),
    ExtLangPair(ext=Extension("Makefile.am"), language=LanguageName("make")),
    ExtLangPair(ext=Extension("Makefile.boot"), language=LanguageName("make")),
    ExtLangPair(ext=Extension("Makefile.in"), language=LanguageName("make")),
    ExtLangPair(ext=Extension("Makefile.inc"), language=LanguageName("make")),
    ExtLangPair(ext=Extension("Makefile.wat"), language=LanguageName("make")),
    ExtLangPair(ext=Extension("Rakefile"), language=LanguageName("rake")),
    ExtLangPair(ext=Extension("_emacs"), language=LanguageName("emacs")),
    ExtLangPair(ext=Extension("makefile"), language=LanguageName("make")),
    ExtLangPair(ext=Extension("makefile.sco"), language=LanguageName("make")),
    ExtLangPair(ext=Extension("mkfile"), language=LanguageName("make")),
    ExtLangPair(ext=Extension("rebar.config"), language=LanguageName("erlang")),
    # We're only going to cover the main ones for VB6, but langchain has a splitter for it so we'll support it.
    ExtLangPair(ext=Extension(".bas"), language=LanguageName("visualbasic6")),
    ExtLangPair(ext=Extension(".cls"), language=LanguageName("visualbasic6")),
    ExtLangPair(ext=Extension(".ctl"), language=LanguageName("visualbasic6")),
    ExtLangPair(ext=Extension(".frm"), language=LanguageName("visualbasic6")),
    ExtLangPair(ext=Extension(".pag"), language=LanguageName("visualbasic6")),
    ExtLangPair(ext=Extension(".res"), language=LanguageName("visualbasic6")),
    ExtLangPair(ext=Extension(".vb"), language=LanguageName("visualbasic6")),
    ExtLangPair(ext=Extension(".vba"), language=LanguageName("visualbasic6")),
    ExtLangPair(ext=Extension(".vbg"), language=LanguageName("visualbasic6")),
    ExtLangPair(ext=Extension(".vbi"), language=LanguageName("visualbasic6")),
    ExtLangPair(ext=Extension(".vbp"), language=LanguageName("visualbasic6")),
)
# spellchecker:on
"""A tuple of `ExtLangPair`."""

TEST_DIR_NAMES: tuple[LiteralStringT, ...] = (
    "__tests__",
    "__specs__",
    "test",
    "tests",
    "spec",
    "specs",
    "test-*",
    "spec-*",
    "Tests",  # swift
)

TEST_FILE_PATTERNS: tuple[LiteralStringT, ...] = ("*.test.*", "*.spec.*", "*_test.*", "*_spec.*")

type DevTool = Literal[
    "ast-grep",
    "bazel",
    "bun",
    "cargo",
    "changesets",
    "cmake",
    "composer",
    "deno",
    "devcontainer",
    "docker",
    "esbuild",
    "gradle",
    "hardhat",
    "hk",
    "husky",
    "intellij",
    "just",
    "lerna",
    "maven",
    "mise",
    "moon",
    "nextjs",
    "npm",
    "nuxt",
    "nx",
    "pnpm",
    "poetry",
    "pre-commit",
    "proto",
    "rollbar",
    "rollup",
    "ruff",
    "rush",
    "sbt",
    "skaffold",
    "stylelint",
    "tailwind",
    "typos",
    "turborepo",
    "uv",
    "vite",
    "vitest",
    "vscode",
    "webpack",
    "xtask",
    "yarn",
]
"""Literal type for development tools."""

COMMON_TOOLING_PATHS: tuple[tuple[DevTool, tuple[Path, ...]], ...] = (
    ("ast-grep", (Path("sgconfig.yml"),)),
    ("cargo", (Path("Cargo.toml"), Path("Cargo.lock"), Path(".cargo"))),
    (
        "docker",
        (
            Path("Dockerfile"),
            Path("docker-compose.yml"),
            Path("docker-compose.yaml"),
            Path("docker"),
        ),
    ),
    (
        "devcontainer",
        (
            Path(".devcontainer"),
            Path(".devcontainer/devcontainer.json"),
            Path(".devcontainer/devcontainer.local.json"),
        ),
    ),
    ("bazel", (Path("WORKSPACE"), Path("BUILD.bazel"), Path("BUILD"))),
    (
        "cmake",
        (
            Path("CMakeLists.txt"),
            Path("CMakeCache.txt"),
            Path("cmake-build-debug"),
            Path("CMakeFiles"),
        ),
    ),
    ("bun", (Path("bun.lockb"), Path("bunfig.toml"), Path("bunfig.json"), Path("bun.lock"))),
    ("changesets", (Path(".changeset"),)),
    ("composer", (Path("composer.json"), Path("composer.lock"))),
    ("esbuild", (Path("esbuild.config.js"), Path("esbuild.config.ts"))),
    (
        "gradle",
        (
            Path("build.gradle"),
            Path("build.gradle.kts"),
            Path("gradlew"),
            Path("gradlew.bat"),
            Path("gradle"),
            Path("settings.gradle"),
            Path("settings.gradle.kts"),
        ),
    ),
    ("deno", (Path("deno.json"), Path("deno.jsonc"), Path("deno.lock"))),
    ("hardhat", (Path("hardhat.config.js"), Path("hardhat.config.ts"))),
    ("hk", (Path("hk.pkl"),)),
    ("husky", (Path(".husky"), Path(".husky/pre-commit"), Path(".husky/pre-push"))),
    ("intellij", (Path(".idea"), Path(".idea/misc.xml"), Path(".idea/modules.xml"))),
    ("just", (Path("Justfile"), Path("justfile"))),
    ("lerna", (Path("lerna.json"),)),
    (
        "maven",
        (Path("pom.xml"), Path("settings.xml"), Path(".mvn"), Path("mvnw"), Path("mvnw.cmd")),
    ),
    ("mise", (Path("mise.toml"),)),
    ("moon", (Path("moon.yml"), Path("moon.yaml"), Path(".moon"))),
    ("nextjs", (Path("next.config.js"), Path("next.config.ts"))),
    ("npm", (Path("package-lock.json"), Path(".npmrc"))),
    ("nuxt", (Path("nuxt.config.js"), Path("nuxt.config.ts"))),
    ("nx", (Path("nx.json"), Path("workspace.json"), Path("angular.json"))),
    ("pnpm", (Path("pnpm-lock.yaml"), Path("pnpm-workspace.yaml"))),
    ("poetry", (Path("poetry.lock"),)),
    ("pre-commit", (Path(".pre-commit-config.yaml"), Path(".pre-commit-config.yml"))),
    (
        "proto",
        (Path("proto.toml"), Path("proto.pkl"), Path("prototools.toml"), Path("prototools.pkl")),
    ),
    ("rollbar", (Path("rollbar.config.js"), Path("rollbar.config.ts"))),
    ("rollup", (Path("rollup.config.js"), Path("rollup.config.ts"))),
    ("ruff", (Path("ruff.toml"), Path(".ruff.toml"))),
    ("rush", (Path("rush.json"),)),
    ("sbt", (Path("build.sbt"), Path("project/build.properties"), Path("project/plugins.sbt"))),
    ("skaffold", (Path("skaffold.yaml"), Path("skaffold.yml"))),
    (
        "stylelint",
        (
            Path(".stylelintrc"),
            Path(".stylelintrc.json"),
            Path(".stylelintrc.yaml"),
            Path(".stylelintrc.yml"),
        ),
    ),
    ("tailwind", (Path("tailwind.config.js"), Path("tailwind.config.ts"))),
    ("typos", (Path("_typos.toml"), Path(".typos.toml"), Path("typos.toml"))),
    ("turborepo", (Path("turbo.json"),)),
    ("uv", (Path("uv.toml"), Path("uv.lock"))),
    ("vite", (Path("vite.config.js"), Path("vite.config.ts"))),
    ("vitest", (Path("vitest.config.js"), Path("vitest.config.ts"))),
    ("vscode", (Path(".vscode"), Path(".vscode/settings.json"), Path(".vscode/launch.json"))),
    ("webpack", (Path("webpack.config.js"), Path("webpack.config.ts"))),
    ("xtask", (Path("xtask"), Path("xtask/src/main.rs"))),
    ("yarn", (Path("yarn.lock"), Path(".yarn"), Path(".yarnrc"), Path(".yarnrc.yml"))),
)
"""Common paths for build and development tooling used in projects. This needs expansion, pull requests are welcome!"""

type LlmTool = Literal[
    "agents",
    "claude",
    "codeweaver",
    "codex",
    "continue",
    "copilot",
    "cursor",
    "mcp",
    "roo",
    "serena",
    "specify",
]

COMMON_LLM_TOOLING_PATHS: tuple[tuple[LlmTool, tuple[Path, ...]], ...] = (
    ("agents", (Path("AGENTS.md"),)),
    ("codex", (Path(".codex"),)),
    ("claude", (Path("CLAUDE.md"), Path(".claude"), Path("claudedocs"), Path(".claude/commands"))),
    (
        "codeweaver",
        (
            Path("codeweaver.local.toml"),
            Path("codeweaver.local.yaml"),
            Path("codeweaver.local.json"),
            Path(".codeweaver"),
        ),
    ),
    ("continue", (Path(".continue"),)),
    ("copilot", (Path(".github/chatmodes"), Path(".github/prompts"))),
    ("cursor", (Path(".cursor"), Path(".cursor/config.yml"))),
    ("mcp", (Path(".mcp.json"), Path("mcp.json"), Path(".roo/mcp.json"), Path(".vscode/mcp.json"))),
    ("roo", (Path(".roo"), Path(".roomodes"), Path(".roo/commands"))),
    ("serena", (Path(".serena"), Path(".serena/project.yml"))),
    (
        "specify",
        (
            Path(".specify"),
            Path(".specify/memory"),
            Path(".specify/scripts/bash"),
            Path(".specify/templates"),
        ),
    ),
)
"""Common paths for LLM tooling used in projects. This needs expansion -- right now it's literally just what I've used."""

_js_fam_paths = (
    Path("package.json"),
    Path("package-lock.json"),
    Path("yarn.lock"),
    Path("pnpm-lock.yaml"),
    Path("node_modules"),
    Path("bun.lockb"),
    Path("bun.lock"),
)

LANGUAGE_SPECIFIC_PATHS: MappingProxyType[LanguageName, tuple[Path, ...]] = MappingProxyType({
    LanguageName("csharp"): (Path("*.csproj"), Path("*.sln")),
    LanguageName("elixir"): (Path("mix.exs"), Path("mix.lock")),
    LanguageName("erlang"): (Path("rebar.config"), Path("rebar.lock")),
    LanguageName("go"): (
        Path("go.mod"),
        Path("go.sum"),
        Path("go.work"),
        Path("cmd"),
        Path("internal"),
    ),
    LanguageName("haskell"): (Path("stack.yaml"), Path("cabal.project"), Path("package.yaml")),
    LanguageName("java"): (
        Path("build.gradle"),
        Path("build.gradle.kts"),
        Path("pom.xml"),
        Path("pom.xml"),
        Path("src/main/java"),
        Path("src/main/tests"),
    ),
    LanguageName("javascript"): _js_fam_paths,
    LanguageName("jsx"): _js_fam_paths,
    LanguageName("kotlin"): (Path("src/main/kotlin"), Path("src/test/kotlin")),
    LanguageName("lua"): (Path("*.rockspec"),),
    LanguageName("php"): (Path("composer.json"), Path("composer.lock")),
    LanguageName("python"): (
        Path("Pipfile"),
        Path("Pipfile.lock"),
        Path("pyproject.toml"),
        Path("requirements-dev.txt"),
        Path("requirements.txt"),
        Path("setup.cfg"),
        Path("setup.py"),
    ),
    LanguageName("ruby"): (
        Path("*.gemspec"),
        Path("Gemfile"),
        Path("Gemfile.lock"),
        Path("Rakefile"),
        Path("config.ru"),
        Path("spec"),
    ),
    LanguageName("rust"): (Path("Cargo.toml"), Path("Cargo.lock")),
    LanguageName("scala"): (
        Path("build.sbt"),
        Path("project/build.properties"),
        Path("project/plugins.sbt"),
        Path("src/main/scala"),
        Path("src/test/scala"),
    ),
    LanguageName("solidity"): (
        Path("contracts"),
        Path("foundry.toml"),
        Path("hardhat.config.js"),
        Path("hardhat.config.ts"),
        Path("truffle-config.js"),
        Path("truffle-config.ts"),
    ),
    LanguageName("swift"): (Path("Package.swift"), Path(".xcodeproj"), Path(".xcworkspace")),
    LanguageName("typescript"): _js_fam_paths,
    LanguageName("tsx"): _js_fam_paths,
})
"""A mapping of language names to their specific common project paths."""


class FallBackTestDef(TypedDict):
    """Definition for a fallback test based on file content."""

    values: tuple[LiteralStringT, ...]
    """The values to check for in the file content."""
    on: Literal["in", "not in"]
    """The condition to check: 'in' or 'not in'. Not in will check that none of the values are present. 'in' will check that at least one value is present."""
    fallback_to: LanguageName
    """The language to fallback to if the test passes."""


FALLBACK_TEST: MappingProxyType[Extension, FallBackTestDef] = MappingProxyType({
    Extension(".v"): {
        "values": ("Proof", "Qed", "Proof", "Defined", "Admitted"),
        "on": "not in",
        "fallback_to": LanguageName("verilog"),
    },
    Extension(".m"): {
        "values": ("switch", "end", "parfor", "function"),
        "on": "not in",
        "fallback_to": LanguageName("objective-c"),
    },
})
"""A mapping of file extensions to their fallback test definitions."""


CONFIG_FILE_LANGUAGES = frozenset({
    LanguageName("bash"),
    LanguageName("cfg"),
    LanguageName("cmake"),
    LanguageName("docker"),
    LanguageName("hcl"),
    LanguageName("ini"),
    LanguageName("json"),
    LanguageName("json5"),
    LanguageName("jsonc"),
    LanguageName("just"),
    LanguageName("make"),
    LanguageName("pkl"),
    LanguageName("properties"),
    LanguageName("toml"),
    LanguageName("xml"),
    LanguageName("yaml"),
})


def _get_languages_helper() -> tuple[
    frozenset[LanguageName],
    frozenset[LanguageName],
    frozenset[LanguageName],
    frozenset[LanguageName],
]:
    """Helper function to get all languages as frozensets."""
    code_langs: set[LanguageName] = {ext.language for ext in CODE_FILES_EXTENSIONS}
    data_langs: set[LanguageName] = {ext.language for ext in DATA_FILES_EXTENSIONS}
    doc_langs: set[LanguageName] = {ext.language for ext in DOC_FILES_EXTENSIONS}
    all_langs: set[LanguageName] = code_langs | data_langs | doc_langs
    return frozenset(code_langs), frozenset(data_langs), frozenset(doc_langs), frozenset(all_langs)


CODE_LANGUAGES, DATA_LANGUAGES, DOCS_LANGUAGES, ALL_LANGUAGES = _get_languages_helper()
"""Frozen sets of languages for code, data, documentation, and all combined."""


def get_ext_lang_pairs(*, include_data: bool = False) -> Generator[ExtLangPair]:
    """Yield all `ExtLangPair` instances for code, config, and docs files."""
    if include_data:
        yield from (*CODE_FILES_EXTENSIONS, *DATA_FILES_EXTENSIONS, *DOC_FILES_EXTENSIONS)
    yield from (*CODE_FILES_EXTENSIONS, *DOC_FILES_EXTENSIONS)


def _run_fallback_test(extension: Extension, path: Path) -> LanguageName:
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
                return test_def["fallback_to"]
    return LanguageName("matlab") if extension == Extension(".m") else LanguageName("coq")


@overload
def _handle_fallback(
    path: Path, *, pair: ExtLangPair, extension: None = None
) -> ExtLangPair | None: ...
@overload
def _handle_fallback(
    path: Path, *, pair: None = None, extension: Extension
) -> ExtLangPair | None: ...
def _handle_fallback(
    path: Path, *, pair: ExtLangPair | None = None, extension: Extension | None = None
) -> ExtLangPair | None:
    """Handle fallback for a given ExtLangPair and file path."""
    if extension is None and pair is None:
        raise ValueError("You must provide either 'pair' or 'extension'.")
    extension = extension or cast(ExtLangPair, pair).ext
    if extension in FALLBACK_TEST:
        return ExtLangPair(ext=extension, language=_run_fallback_test(extension, path))
    return pair


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
                language = _run_fallback_test(pair.ext, file_path)
                return ExtLangPair(ext=pair.ext, language=language)
            return pair
    return None


def get_language_from_extension(
    extension: Extension | LiteralStringT,
    *,
    path: Path | None = None,
    hook: Callable[[Extension, Path | None], LanguageName | None] | None = None,
) -> LanguageName | None:
    """Get the language associated with a given file extension."""
    extension = Extension(extension)
    if path and path.is_file() and (fallback := _handle_fallback(path, extension=extension)):
        return fallback.language
    return next(
        (pair.language for pair in get_ext_lang_pairs() if pair and pair.ext == extension),
        hook(extension, path) if hook else None,
    )


__all__ = (
    "ALL_LANGUAGES",
    "CODE_FILES_EXTENSIONS",
    "CODE_LANGUAGES",
    "COMMON_LLM_TOOLING_PATHS",
    "COMMON_TOOLING_PATHS",
    "CONFIG_FILE_LANGUAGES",
    "DATA_FILES_EXTENSIONS",
    "DATA_LANGUAGES",
    "DEFAULT_EXCLUDED_DIRS",
    "DEFAULT_EXCLUDED_EXTENSIONS",
    "DOCS_LANGUAGES",
    "DOC_FILES_EXTENSIONS",
    "FALLBACK_TEST",
    "TEST_DIR_NAMES",
    "TEST_FILE_PATTERNS",
    "ExtLangPair",
    "FallBackTestDef",
    "get_ext_lang_pairs",
    "get_language_from_extension",
)
