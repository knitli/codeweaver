# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""
Constants used throughout the CodeWeaver project, primarily for default configurations.
"""

from __future__ import annotations

from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Literal, TypedDict, cast

from codeweaver.core.types.aliases import (
    DirectoryName,
    DirectoryNameT,
    FileExt,
    FileExtensionT,
    FileGlob,
    FileGlobT,
    LanguageName,
    LanguageNameT,
    LiteralStringT,
)
from codeweaver.core.utils import COMMON_LLM_TOOLING_PATHS, COMMON_TOOLING_PATHS, lazy_import


if TYPE_CHECKING:
    from codeweaver.core.metadata import ExtLangPair
    from codeweaver.core.utils import LazyImport


LangPair: LazyImport[ExtLangPair] = lazy_import("codeweaver.core.metadata", "ExtLangPair")


METADATA_PATH = "metadata"


DEFAULT_EXCLUDED_DIRS: frozenset[DirectoryNameT] = frozenset({
    DirectoryName(".DS_Store"),
    DirectoryName(".cache"),
    DirectoryName(".eslintcache"),
    DirectoryName(".git"),
    DirectoryName(".hg"),
    DirectoryName(".history"),
    DirectoryName(".htmlcov"),
    DirectoryName(".idea"),
    DirectoryName(".jj"),
    DirectoryName(".next"),
    DirectoryName(".nuxt"),
    DirectoryName(".ruff_cache"),
    DirectoryName(".svn"),
    DirectoryName(".temp"),
    DirectoryName(".tmp"),
    DirectoryName(".tsbuildinfo"),
    DirectoryName(".venv"),
    DirectoryName(".vs"),
    DirectoryName("Debug"),
    DirectoryName("Release"),
    DirectoryName("Releases"),
    DirectoryName("Thumbs.db"),
    DirectoryName("__pycache__"),
    DirectoryName("__pytest_cache__"),
    DirectoryName("aarch64"),
    DirectoryName("arm"),
    DirectoryName("arm64"),
    DirectoryName("bower_components"),
    DirectoryName("debug"),
    DirectoryName("dist"),
    DirectoryName("htmlcov"),
    DirectoryName("lib64"),
    DirectoryName("log"),
    DirectoryName("logs"),
    DirectoryName("node_modules"),
    DirectoryName("obj"),
    DirectoryName("out"),
    DirectoryName("release"),
    DirectoryName("releases"),
    DirectoryName("remote-debug-profile"),
    DirectoryName("site"),
    DirectoryName("target"),
    DirectoryName("temp"),
    DirectoryName("tmp"),
    DirectoryName("vendor"),
    DirectoryName("venv"),
    DirectoryName("win32"),
    DirectoryName("win64"),
    DirectoryName("x64"),
    DirectoryName("x86"),
})

DEFAULT_EXCLUDED_EXTENSIONS: frozenset[FileExtensionT] = frozenset({
    FileExt(".7z"),
    FileExt(".avi"),
    FileExt(".avif"),
    FileExt(".bmp"),
    FileExt(".builds"),
    FileExt(".cache"),
    FileExt(".class"),
    FileExt("codeweaver.local.json"),
    FileExt("codeweaver.local.toml"),
    FileExt("codeweaver.local.yaml"),
    FileExt(".code-workspace"),
    FileExt(".coverage"),
    FileExt(".coverage.xml"),
    FileExt(".dll"),
    FileExt(".dmg"),
    FileExt(".env"),  # avoid env because api keys/secrets
    FileExt(".exe"),
    FileExt(".gif"),
    FileExt(".gz"),
    FileExt(".iobj"),
    FileExt(".jar"),
    FileExt(".jpeg"),
    FileExt(".jpg"),
    FileExt(".lcov"),
    FileExt(".local"),
    FileExt(".lock"),
    FileExt(".log"),
    FileExt(".meta"),
    FileExt(".mov"),
    FileExt(".mp3"),
    FileExt(".mp4"),
    FileExt(".mpeg"),
    FileExt(".mpg"),
    FileExt(".ms"),
    FileExt(".msi"),
    FileExt(".o"),
    FileExt(".obj"),
    FileExt(".pch"),
    FileExt(".pdb"),
    FileExt(".pgc"),
    FileExt(".pgd"),
    FileExt(".png"),
    FileExt(".pyc"),
    FileExt(".pyo"),
    FileExt(".rar"),
    FileExt(".rsp"),
    FileExt(".scc"),
    FileExt(".sig"),
    FileExt(".snk"),
    FileExt(".so"),
    FileExt(".svclog"),
    FileExt(".svg"),
    FileExt(".swo"),
    FileExt(".swp"),
    FileExt(".tar"),
    FileExt(".temp"),
    FileExt(".tlb"),
    FileExt(".tlog"),
    FileExt(".tmp"),
    FileExt(".tmp_proj"),
    FileExt(".vspec"),
    FileExt(".vssscc"),
    FileExt(".wav"),
    FileExt(".webm"),
    FileExt(".webp"),
    FileExt(".zip"),
})

REPO_POLICY_FILES: frozenset[FileGlobT] = frozenset({
    FileGlob("CODE_OF_CONDUCT.*"),
    FileGlob("CODE_OF_CONDUCT*"),
    FileGlob("SECURITY.*"),
    FileGlob("SECURITY*"),
    FileGlob("CONTRIBUTING.*"),
    FileGlob("CONTRIBUTING*"),
    FileGlob("NOTICE.*"),
    FileGlob("NOTICE*"),
    FileGlob("AUTHORS.*"),
    FileGlob("AUTHORS*"),
    FileGlob("MAINTAINERS.*"),
    FileGlob("MAINTAINERS*"),
    FileGlob("CONTRIBUTORS*"),  # CLA files
    FileGlob("CLA*"),
    FileGlob("CODEOWNERS"),
    FileGlob("DEVELOPERS*"),  # DCO files
    FileGlob("DCO*"),
})
"""Common file name patterns for repository policy files, not including license files."""

DATA_FILES_EXTENSIONS: tuple[ExtLangPair, ...] = (
    LangPair(ext=FileExt(".csv"), language=LanguageName("csv")),
    LangPair(ext=FileExt(".dat"), language=LanguageName("data")),
    LangPair(ext=FileExt(".db"), language=LanguageName("sql")),
    LangPair(ext=FileExt(".dbf"), language=LanguageName("dbf")),
    LangPair(
        ext=FileExt(".nw"), language=LanguageName("nw")
    ),  # Node-Webkit (.zip container with .nw extension) files
    LangPair(ext=FileExt(".sqlite"), language=LanguageName("sql")),
    LangPair(ext=FileExt(".sqlite3"), language=LanguageName("sql")),
    LangPair(ext=FileExt(".svg"), language=LanguageName("xml")),
    LangPair(ext=FileExt(".tsv"), language=LanguageName("tsv")),
    LangPair(ext=FileExt(".xlsx"), language=LanguageName("excel")),
)
"""Extensions for common data files. NOTE: CodeWeaver does *not* index data files by default. You must explicitly include them if desired. We have not tested our chunkers on data files, so your mileage may vary -- csv/tsv/svg/xlsx are likely to work best."""

DOC_FILES_EXTENSIONS: tuple[ExtLangPair, ...] = (
    LangPair(ext=FileExt(".1"), language=LanguageName("man")),
    LangPair(ext=FileExt(".2"), language=LanguageName("man")),
    LangPair(ext=FileExt(".3"), language=LanguageName("man")),
    LangPair(ext=FileExt(".4"), language=LanguageName("man")),
    LangPair(ext=FileExt(".5"), language=LanguageName("man")),
    LangPair(ext=FileExt(".6"), language=LanguageName("man")),
    LangPair(ext=FileExt(".7"), language=LanguageName("man")),
    LangPair(ext=FileExt(".8"), language=LanguageName("man")),
    LangPair(ext=FileExt(".9"), language=LanguageName("man")),
    LangPair(ext=FileExt(".Rmd"), language=LanguageName("rmarkdown")),
    LangPair(ext=FileExt(".adoc"), language=LanguageName("asciidoc")),
    LangPair(ext=FileExt(".asc"), language=LanguageName("asciidoc")),
    LangPair(ext=FileExt(".asciidoc"), language=LanguageName("asciidoc")),
    LangPair(ext=FileExt(".bib"), language=LanguageName("latex")),
    LangPair(ext=FileExt(".confluence"), language=LanguageName("confluence")),
    LangPair(ext=FileExt(".creole"), language=LanguageName("creole")),
    LangPair(ext=FileExt(".dita"), language=LanguageName("dita")),
    LangPair(ext=FileExt(".docbook"), language=LanguageName("docbook")),
    LangPair(ext=FileExt(".help"), language=LanguageName("help")),
    LangPair(ext=FileExt(".hlp"), language=LanguageName("help")),
    LangPair(ext=FileExt(".info"), language=LanguageName("info")),
    LangPair(ext=FileExt(".ipynb"), language=LanguageName("jupyter")),
    LangPair(ext=FileExt(".lagda"), language=LanguageName("lagda")),
    LangPair(ext=FileExt(".latex"), language=LanguageName("latex")),
    LangPair(ext=FileExt(".lhs"), language=LanguageName("lhs")),
    LangPair(ext=FileExt(".man"), language=LanguageName("man")),
    LangPair(ext=FileExt(".manpage"), language=LanguageName("man")),
    LangPair(ext=FileExt(".markdown"), language=LanguageName("markdown")),
    LangPair(ext=FileExt(".md"), language=LanguageName("markdown")),
    LangPair(ext=FileExt(".mdown"), language=LanguageName("markdown")),
    LangPair(ext=FileExt(".mdx"), language=LanguageName("markdown")),
    LangPair(ext=FileExt(".mediawiki"), language=LanguageName("mediawiki")),
    LangPair(ext=FileExt(".mkd"), language=LanguageName("markdown")),
    LangPair(ext=FileExt(".mkdn"), language=LanguageName("markdown")),
    LangPair(ext=FileExt(".org"), language=LanguageName("org")),
    LangPair(ext=FileExt(".pod"), language=LanguageName("pod")),
    LangPair(ext=FileExt(".pyx"), language=LanguageName("cython")),
    LangPair(ext=FileExt(".rdoc"), language=LanguageName("markdown")),
    LangPair(ext=FileExt(".rest"), language=LanguageName("restructuredtext")),
    LangPair(ext=FileExt(".rmd"), language=LanguageName("rmd")),
    LangPair(ext=FileExt(".rnw"), language=LanguageName("rnw")),
    LangPair(ext=FileExt(".rst"), language=LanguageName("restructuredtext")),
    LangPair(ext=FileExt(".rtf"), language=LanguageName("rtf")),
    LangPair(ext=FileExt(".tex"), language=LanguageName("latex")),
    LangPair(ext=FileExt(".texi"), language=LanguageName("texinfo")),
    LangPair(ext=FileExt(".texinfo"), language=LanguageName("texinfo")),
    LangPair(ext=FileExt(".text"), language=LanguageName("text")),
    LangPair(ext=FileExt(".textile"), language=LanguageName("textile")),
    LangPair(ext=FileExt(".txt"), language=LanguageName("text")),
    LangPair(ext=FileExt(".wiki"), language=LanguageName("wiki")),
    LangPair(ext=FileExt(".xml"), language=LanguageName("xml")),
    LangPair(ext=FileExt(".yard"), language=LanguageName("yard")),
)
"""A tuple of `ExtLangPair` for documentation files."""

# spellchecker:off
CODE_FILES_EXTENSIONS: tuple[ExtLangPair, ...] = (
    LangPair(ext=FileExt(".F"), language=LanguageName("fortran")),
    LangPair(ext=FileExt(".R"), language=LanguageName("r")),
    LangPair(ext=FileExt(".Rprofile"), language=LanguageName("r")),
    LangPair(ext=FileExt(".app.src"), language=LanguageName("erlang")),
    LangPair(ext=FileExt(".as"), language=LanguageName("assemblyscript")),
    LangPair(ext=FileExt(".asd"), language=LanguageName("lisp")),
    LangPair(ext=FileExt(".asm"), language=LanguageName("assembly")),
    LangPair(ext=FileExt(".aux"), language=LanguageName("latex")),
    LangPair(ext=FileExt(".astro"), language=LanguageName("astro")),
    LangPair(ext=FileExt(".bat"), language=LanguageName("batch")),
    LangPair(ext=FileExt(".bb"), language=LanguageName("clojure")),
    LangPair(ext=FileExt(".beef"), language=LanguageName("beef")),
    LangPair(ext=FileExt(".binpb"), language=LanguageName("protobuf")),
    LangPair(ext=FileExt(".boot"), language=LanguageName("clojure")),
    LangPair(ext=FileExt(".carbon"), language=LanguageName("carbon")),
    LangPair(ext=FileExt(".cbl"), language=LanguageName("cobol")),
    LangPair(ext=FileExt(".chapel"), language=LanguageName("chapel")),
    LangPair(ext=FileExt(".clj"), language=LanguageName("clojure")),
    LangPair(ext=FileExt(".cljc"), language=LanguageName("clojure")),
    LangPair(ext=FileExt(".cljs"), language=LanguageName("clojure")),
    LangPair(ext=FileExt(".cljx"), language=LanguageName("clojure")),
    LangPair(ext=FileExt(".cls"), language=LanguageName("latex")),
    LangPair(ext=FileExt(".cmake"), language=LanguageName("cmake")),
    LangPair(ext=FileExt(".cob"), language=LanguageName("cobol")),
    LangPair(ext=FileExt(".cobol"), language=LanguageName("cobol")),
    LangPair(ext=FileExt(".coffee"), language=LanguageName("coffeescript")),
    LangPair(ext=FileExt(".cr"), language=LanguageName("crystal")),
    LangPair(ext=FileExt(".cu"), language=LanguageName("cuda")),
    LangPair(ext=FileExt(".cue"), language=LanguageName("cue")),
    LangPair(ext=FileExt(".cuh"), language=LanguageName("cuda")),
    LangPair(ext=FileExt(".d"), language=LanguageName("dlang")),
    LangPair(ext=FileExt(".dart"), language=LanguageName("dart")),
    LangPair(ext=FileExt(".dfm"), language=LanguageName("pascal")),
    LangPair(ext=FileExt(".dhall"), language=LanguageName("dhall")),
    LangPair(ext=FileExt(".dlang"), language=LanguageName("dlang")),
    LangPair(ext=FileExt(".dpr"), language=LanguageName("pascal")),
    LangPair(ext=FileExt(".dts"), language=LanguageName("devicetree")),
    LangPair(ext=FileExt(".dtsi"), language=LanguageName("devicetree")),
    LangPair(ext=FileExt(".dtso"), language=LanguageName("devicetree")),
    LangPair(ext=FileExt(".duck"), language=LanguageName("duck")),
    LangPair(ext=FileExt(".dyck"), language=LanguageName("dyck")),
    LangPair(ext=FileExt(".e"), language=LanguageName("eiffel")),
    LangPair(ext=FileExt(".ecl"), language=LanguageName("ecl")),
    LangPair(ext=FileExt(".eclsp"), language=LanguageName("ecl")),
    LangPair(ext=FileExt(".eclxml"), language=LanguageName("ecl")),
    LangPair(ext=FileExt(".edn"), language=LanguageName("clojure")),
    LangPair(ext=FileExt(".el"), language=LanguageName("emacs")),
    LangPair(ext=FileExt(".elm"), language=LanguageName("elm")),
    LangPair(ext=FileExt(".elv"), language=LanguageName("elvish")),
    LangPair(ext=FileExt(".emacs"), language=LanguageName("emacs")),
    LangPair(ext=FileExt(".erl"), language=LanguageName("erlang")),
    LangPair(ext=FileExt(".es"), language=LanguageName("erlang")),
    LangPair(ext=FileExt(".escript"), language=LanguageName("erlang")),
    LangPair(ext=FileExt(".eta"), language=LanguageName("eta")),
    LangPair(ext=FileExt(".f"), language=LanguageName("fortran")),
    LangPair(ext=FileExt(".f03"), language=LanguageName("fortran")),
    LangPair(ext=FileExt(".f08"), language=LanguageName("fortran")),
    LangPair(ext=FileExt(".f18"), language=LanguageName("fortran")),
    LangPair(ext=FileExt(".f23"), language=LanguageName("fortran")),
    LangPair(ext=FileExt(".f90"), language=LanguageName("fortran")),
    LangPair(ext=FileExt(".f95"), language=LanguageName("fortran")),
    LangPair(ext=FileExt(".factor"), language=LanguageName("factor")),
    LangPair(ext=FileExt(".for"), language=LanguageName("fortran")),
    LangPair(ext=FileExt(".fr"), language=LanguageName("frege")),
    LangPair(ext=FileExt(".fs"), language=LanguageName("fsharp")),
    LangPair(ext=FileExt(".fsi"), language=LanguageName("fsharp")),
    LangPair(ext=FileExt(".fsx"), language=LanguageName("fsharp")),
    LangPair(ext=FileExt(".gleam"), language=LanguageName("gleam")),
    LangPair(ext=FileExt(".gql"), language=LanguageName("graphql")),
    LangPair(ext=FileExt(".graphql"), language=LanguageName("graphql")),
    LangPair(ext=FileExt(".graphqls"), language=LanguageName("graphql")),
    LangPair(ext=FileExt(".groovy"), language=LanguageName("groovy")),
    LangPair(ext=FileExt(".gs"), language=LanguageName("gosu")),
    LangPair(ext=FileExt(".hack"), language=LanguageName("hack")),
    LangPair(ext=FileExt(".hck"), language=LanguageName("hack")),
    LangPair(ext=FileExt(".hcl"), language=LanguageName("hcl")),
    LangPair(ext=FileExt(".hhi"), language=LanguageName("hack")),
    LangPair(ext=FileExt(".hjson"), language=LanguageName("hjson")),
    LangPair(ext=FileExt(".hlsl"), language=LanguageName("hlsl")),
    LangPair(ext=FileExt(".hrl"), language=LanguageName("erlang")),
    LangPair(ext=FileExt(".hrl"), language=LanguageName("erlang")),
    LangPair(ext=FileExt(".idr"), language=LanguageName("idris")),
    LangPair(ext=FileExt(".imba"), language=LanguageName("imba")),
    LangPair(ext=FileExt(".io"), language=LanguageName("io")),
    LangPair(ext=FileExt(".its"), language=LanguageName("devicetree")),
    LangPair(ext=FileExt(".janet"), language=LanguageName("janet")),
    LangPair(ext=FileExt(".jdn"), language=LanguageName("janet")),
    LangPair(ext=FileExt(".jelly"), language=LanguageName("jelly")),  # jenkins
    LangPair(ext=FileExt(".jinja"), language=LanguageName("jinja")),
    LangPair(ext=FileExt(".jinja2"), language=LanguageName("jinja")),
    LangPair(ext=FileExt(".jl"), language=LanguageName("julia")),
    LangPair(ext=FileExt(".joke"), language=LanguageName("clojure")),
    LangPair(ext=FileExt(".joker"), language=LanguageName("clojure")),
    LangPair(ext=FileExt(".jule"), language=LanguageName("jule")),
    LangPair(ext=FileExt(".less"), language=LanguageName("less")),
    LangPair(ext=FileExt(".lidr"), language=LanguageName("idris")),
    LangPair(ext=FileExt(".lisp"), language=LanguageName("lisp")),
    LangPair(ext=FileExt(".lpr"), language=LanguageName("pascal")),
    LangPair(ext=FileExt(".ls"), language=LanguageName("livescript")),
    LangPair(ext=FileExt(".lsc"), language=LanguageName("lisp")),
    LangPair(ext=FileExt(".lsp"), language=LanguageName("lisp")),
    LangPair(ext=FileExt(".lucee"), language=LanguageName("lucee")),
    LangPair(ext=FileExt(".m"), language=LanguageName("matlab")),
    LangPair(ext=FileExt(".mak"), language=LanguageName("make")),
    LangPair(ext=FileExt(".makefile"), language=LanguageName("make")),
    LangPair(ext=FileExt(".mk"), language=LanguageName("make")),
    LangPair(ext=FileExt(".ml"), language=LanguageName("ocaml")),
    LangPair(ext=FileExt(".mli"), language=LanguageName("ocaml")),
    LangPair(ext=FileExt(".mm"), language=LanguageName("objective-c")),
    LangPair(ext=FileExt(".mojo"), language=LanguageName("mojo")),
    LangPair(ext=FileExt(".move"), language=LanguageName("move")),
    LangPair(ext=FileExt(".nh"), language=LanguageName("newick")),
    LangPair(ext=FileExt(".nhx"), language=LanguageName("newick")),
    LangPair(ext=FileExt(".nim"), language=LanguageName("nimble")),
    LangPair(ext=FileExt(".nim.cfg"), language=LanguageName("nimble")),
    LangPair(ext=FileExt(".nim.cfg"), language=LanguageName("nimble")),
    LangPair(ext=FileExt(".nimble"), language=LanguageName("nimble")),
    LangPair(ext=FileExt(".nimble.cfg"), language=LanguageName("nimble")),
    LangPair(ext=FileExt(".nimble.json"), language=LanguageName("json")),
    LangPair(ext=FileExt(".nimble.toml"), language=LanguageName("toml")),
    LangPair(ext=FileExt(".nomad"), language=LanguageName("hcl")),
    LangPair(ext=FileExt(".nu"), language=LanguageName("nushell")),
    LangPair(ext=FileExt(".nushell"), language=LanguageName("nushell")),
    LangPair(ext=FileExt(".nwk"), language=LanguageName("newick")),
    LangPair(ext=FileExt(".odin"), language=LanguageName("odin")),
    LangPair(ext=FileExt(".pas"), language=LanguageName("pascal")),
    LangPair(ext=FileExt(".pascal"), language=LanguageName("pascal")),
    LangPair(ext=FileExt(".pgsql"), language=LanguageName("sql")),
    LangPair(ext=FileExt(".pharo"), language=LanguageName("pharo")),
    LangPair(ext=FileExt(".pkl"), language=LanguageName("pkl")),
    LangPair(ext=FileExt(".pl"), language=LanguageName("perl")),
    LangPair(ext=FileExt(".pm"), language=LanguageName("perl")),
    LangPair(ext=FileExt(".pony"), language=LanguageName("pony")),
    LangPair(ext=FileExt(".pp"), language=LanguageName("pascal")),
    LangPair(ext=FileExt(".proto"), language=LanguageName("protobuf")),
    LangPair(ext=FileExt(".ps1"), language=LanguageName("powershell")),
    LangPair(ext=FileExt(".psm1"), language=LanguageName("powershell")),
    LangPair(ext=FileExt(".pssc"), language=LanguageName("powershell")),
    LangPair(ext=FileExt(".purs"), language=LanguageName("purescript")),
    LangPair(ext=FileExt(".pxd"), language=LanguageName("cython")),
    LangPair(ext=FileExt(".pyx"), language=LanguageName("cython")),
    LangPair(ext=FileExt(".qb64"), language=LanguageName("qb64")),
    LangPair(ext=FileExt(".qml"), language=LanguageName("qml")),
    LangPair(ext=FileExt(".r"), language=LanguageName("r")),
    LangPair(ext=FileExt(".raku"), language=LanguageName("raku")),
    LangPair(ext=FileExt(".rakudoc"), language=LanguageName("raku")),
    LangPair(ext=FileExt(".rakudoc"), language=LanguageName("rakudo")),
    LangPair(ext=FileExt(".rd"), language=LanguageName("r")),
    LangPair(ext=FileExt(".re"), language=LanguageName("reason")),
    LangPair(ext=FileExt(".red"), language=LanguageName("red")),
    LangPair(ext=FileExt(".reds"), language=LanguageName("red")),
    LangPair(ext=FileExt(".rei"), language=LanguageName("reason")),
    LangPair(ext=FileExt(".res"), language=LanguageName("rescript")),
    LangPair(ext=FileExt(".rescript"), language=LanguageName("rescript")),
    LangPair(ext=FileExt(".ring"), language=LanguageName("ring")),
    LangPair(ext=FileExt(".rkt"), language=LanguageName("racket")),
    LangPair(ext=FileExt(".rktd"), language=LanguageName("racket")),
    LangPair(ext=FileExt(".rktl"), language=LanguageName("racket")),
    LangPair(ext=FileExt(".rsx"), language=LanguageName("r")),
    LangPair(ext=FileExt(".s"), language=LanguageName("assembly")),
    LangPair(ext=FileExt(".sas"), language=LanguageName("sas")),
    LangPair(ext=FileExt(".sass"), language=LanguageName("sass")),
    LangPair(ext=FileExt(".sc"), language=LanguageName("scheme")),
    LangPair(ext=FileExt(".sch"), language=LanguageName("scheme")),
    LangPair(ext=FileExt(".scheme"), language=LanguageName("scheme")),
    LangPair(ext=FileExt(".scm"), language=LanguageName("scheme")),
    LangPair(ext=FileExt(".scss"), language=LanguageName("scss")),
    LangPair(ext=FileExt(".sld"), language=LanguageName("scheme")),
    LangPair(ext=FileExt(".smali"), language=LanguageName("smali")),
    LangPair(ext=FileExt(".sml"), language=LanguageName("sml")),  # Standard ML
    LangPair(ext=FileExt(".sql"), language=LanguageName("sql")),
    LangPair(ext=FileExt(".sqlite"), language=LanguageName("sql")),
    LangPair(ext=FileExt(".sqlite3"), language=LanguageName("sql")),
    LangPair(ext=FileExt(".sty"), language=LanguageName("latex")),
    LangPair(
        ext=FileExt(".sv"), language=LanguageName("verilog")
    ),  # systemverilog -- more likely these days than `v` for verilog
    LangPair(ext=FileExt(".svelte"), language=LanguageName("svelte")),
    LangPair(ext=FileExt(".svh"), language=LanguageName("verilog")),
    LangPair(ext=FileExt(".tex"), language=LanguageName("latex")),
    LangPair(ext=FileExt(".textproto"), language=LanguageName("protobuf")),
    LangPair(ext=FileExt(".tf"), language=LanguageName("hcl")),
    LangPair(ext=FileExt(".tfvars"), language=LanguageName("hcl")),
    LangPair(ext=FileExt(".txtpb"), language=LanguageName("protobuf")),
    LangPair(
        ext=FileExt(".v"), language=LanguageName("coq")
    ),  # coq vernacular files -- could also be verilog.
    LangPair(ext=FileExt(".vala"), language=LanguageName("vala")),
    LangPair(ext=FileExt(".vale"), language=LanguageName("vale")),
    LangPair(ext=FileExt(".vapi"), language=LanguageName("vala")),
    LangPair(ext=FileExt(".vbs"), language=LanguageName("vbscript")),
    LangPair(ext=FileExt(".vhd"), language=LanguageName("vhdl")),
    LangPair(ext=FileExt(".vhdl"), language=LanguageName("vhdl")),
    LangPair(ext=FileExt(".vlang"), language=LanguageName("vlang")),
    LangPair(ext=FileExt(".vls"), language=LanguageName("vlang")),
    LangPair(ext=FileExt(".vsh"), language=LanguageName("vlang")),
    LangPair(ext=FileExt(".vue"), language=LanguageName("vue")),
    LangPair(ext=FileExt(".workflow"), language=LanguageName("hcl")),
    LangPair(ext=FileExt(".xaml"), language=LanguageName("xml")),
    LangPair(ext=FileExt(".xhtml"), language=LanguageName("xml")),
    LangPair(ext=FileExt(".xib"), language=LanguageName("xml")),
    LangPair(ext=FileExt(".xlf"), language=LanguageName("xml")),
    LangPair(ext=FileExt(".xlf"), language=LanguageName("xml")),
    LangPair(ext=FileExt(".xmi"), language=LanguageName("xml")),
    LangPair(ext=FileExt(".xml"), language=LanguageName("xml")),
    LangPair(ext=FileExt(".xml.dist"), language=LanguageName("xml")),
    LangPair(ext=FileExt(".xml.in"), language=LanguageName("xml")),
    LangPair(ext=FileExt(".xml.inc"), language=LanguageName("xml")),
    LangPair(ext=FileExt(".xrl"), language=LanguageName("erlang")),
    LangPair(ext=FileExt(".xsd"), language=LanguageName("xml")),
    LangPair(ext=FileExt(".xsh"), language=LanguageName("xonsh")),
    LangPair(ext=FileExt(".xsl"), language=LanguageName("xml")),
    LangPair(ext=FileExt(".yrl"), language=LanguageName("erlang")),
    LangPair(ext=FileExt(".zig"), language=LanguageName("zig")),
    LangPair(ext=FileExt(".zsh"), language=LanguageName("zsh")),
    LangPair(ext=FileExt("BSDmakefile"), language=LanguageName("make")),
    LangPair(ext=FileExt("CMakefile"), language=LanguageName("cmake")),
    LangPair(ext=FileExt("Cask"), language=LanguageName("emacs")),
    LangPair(ext=FileExt("Dockerfile"), language=LanguageName("docker")),
    LangPair(ext=FileExt("Emakefile"), language=LanguageName("erlang")),
    LangPair(ext=FileExt("GNUmakefile"), language=LanguageName("make")),
    LangPair(ext=FileExt("Justfile"), language=LanguageName("just")),
    LangPair(ext=FileExt("Kbuild"), language=LanguageName("make")),
    LangPair(ext=FileExt("Makefile"), language=LanguageName("make")),
    LangPair(ext=FileExt("Makefile.am"), language=LanguageName("make")),
    LangPair(ext=FileExt("Makefile.boot"), language=LanguageName("make")),
    LangPair(ext=FileExt("Makefile.in"), language=LanguageName("make")),
    LangPair(ext=FileExt("Makefile.inc"), language=LanguageName("make")),
    LangPair(ext=FileExt("Makefile.wat"), language=LanguageName("make")),
    LangPair(ext=FileExt("Rakefile"), language=LanguageName("rake")),
    LangPair(ext=FileExt("_emacs"), language=LanguageName("emacs")),
    LangPair(ext=FileExt("makefile"), language=LanguageName("make")),
    LangPair(ext=FileExt("makefile.sco"), language=LanguageName("make")),
    LangPair(ext=FileExt("mkfile"), language=LanguageName("make")),
    LangPair(ext=FileExt("rebar.config"), language=LanguageName("erlang")),
    LangPair(ext=FileExt(".bas"), language=LanguageName("visualbasic6")),
    LangPair(ext=FileExt(".cls"), language=LanguageName("visualbasic6")),
    LangPair(ext=FileExt(".ctl"), language=LanguageName("visualbasic6")),
    LangPair(ext=FileExt(".frm"), language=LanguageName("visualbasic6")),
    LangPair(ext=FileExt(".pag"), language=LanguageName("visualbasic6")),
    LangPair(ext=FileExt(".res"), language=LanguageName("visualbasic6")),
    LangPair(ext=FileExt(".vb"), language=LanguageName("visualbasic6")),
    LangPair(ext=FileExt(".vba"), language=LanguageName("visualbasic6")),
    LangPair(ext=FileExt(".vbg"), language=LanguageName("visualbasic6")),
    LangPair(ext=FileExt(".vbi"), language=LanguageName("visualbasic6")),
    LangPair(ext=FileExt(".vbp"), language=LanguageName("visualbasic6")),
)
# spellchecker:on
"""A tuple of `ExtLangPair` for common programming languages."""


TEST_DIR_NAMES: tuple[DirectoryNameT, ...] = (
    DirectoryName("__tests__"),
    DirectoryName("__specs__"),
    DirectoryName("test"),
    DirectoryName("tests"),
    DirectoryName("spec"),
    DirectoryName("specs"),
    DirectoryName("test-*"),
    DirectoryName("spec-*"),
    DirectoryName("Tests"),  # swift
)
"""Common directory names used for test code."""

TEST_FILE_PATTERNS: tuple[FileGlobT, ...] = (
    FileGlob("*.test.*"),
    FileGlob("*.spec.*"),
    FileGlob("*_test.*"),
    FileGlob("*_spec.*"),
)
"""Common file name patterns used for test code."""


def all_js_exts(stem: str) -> tuple[str, ...]:
    """Return all common JavaScript-related extensions for a given stem.

    Args:
        stem: The file stem (name without extension).

    Returns:
        A tuple of file names with common JavaScript-related extensions. Does not include `.jsx` or `.tsx` extensions.
    """
    return (f"{stem}.js", f"{stem}.cjs", f"{stem}.mjs", f"{stem}.ts", f"{stem}.cts", f"{stem}.mts")


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

_js_fam_paths = frozenset((
    Path("package.json"),
    Path("package-lock.json"),
    Path("yarn.lock"),
    Path("pnpm-lock.yaml"),
    Path("node_modules"),
    Path("bun.lockb"),
    Path("bun.lock"),
))
"""Common paths for JavaScript family languages (JavaScript, TypeScript, JSX, TSX)."""

LANGUAGE_SPECIFIC_PATHS: MappingProxyType[LanguageNameT, frozenset[Path]] = MappingProxyType({
    LanguageName("csharp"): frozenset((*Path().glob("*.csproj"), Path("*.sln"))),
    LanguageName(cast(LiteralStringT, "elixir")): frozenset((Path("mix.exs"), Path("mix.lock"))),
    LanguageName("erlang"): frozenset((Path("rebar.config"), Path("rebar.lock"))),
    LanguageName("go"): frozenset((
        Path("go.mod"),
        Path("go.sum"),
        Path("go.work"),
        Path("cmd"),
        Path("internal"),
    )),
    LanguageName("haskell"): frozenset((
        Path("stack.yaml"),
        Path("cabal.project"),
        Path("package.yaml"),
    )),
    LanguageName("java"): frozenset((
        Path("build.gradle"),
        Path("build.gradle.kts"),
        Path("pom.xml"),
        Path("pom.xml"),
        Path("src/main/java"),
        Path("src/main/tests"),
    )),
    LanguageName("javascript"): _js_fam_paths,
    LanguageName("jsx"): _js_fam_paths,
    LanguageName("kotlin"): frozenset((Path("src/main/kotlin"), Path("src/test/kotlin"))),
    LanguageName("lua"): frozenset((Path("*.rockspec"),)),
    LanguageName("php"): frozenset((Path("composer.json"), Path("composer.lock"))),
    LanguageName("python"): frozenset((
        Path("Pipfile"),
        Path("Pipfile.lock"),
        Path("pyproject.toml"),
        Path("requirements-dev.txt"),
        Path("requirements.txt"),
        Path("setup.cfg"),
        Path("setup.py"),
    )),
    LanguageName("ruby"): frozenset((
        Path("*.gemspec"),
        Path("Gemfile"),
        Path("Gemfile.lock"),
        Path("Rakefile"),
        Path("config.ru"),
        Path("spec"),
    )),
    LanguageName("rust"): frozenset((Path("Cargo.toml"), Path("Cargo.lock"))),
    LanguageName("scala"): frozenset((
        Path("build.sbt"),
        Path("project/build.properties"),
        Path("project/plugins.sbt"),
        Path("src/main/scala"),
        Path("src/test/scala"),
    )),
    LanguageName("solidity"): frozenset((
        Path("contracts"),
        Path("foundry.toml"),
        Path("hardhat.config.js"),
        Path("hardhat.config.ts"),
        Path("truffle-config.js"),
        Path("truffle-config.ts"),
    )),
    LanguageName("swift"): frozenset((
        Path("Package.swift"),
        Path(".xcodeproj"),
        Path(".xcworkspace"),
    )),
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
    fallback_to: LanguageNameT
    """The language to fallback to if the test passes."""


FALLBACK_TEST: MappingProxyType[FileExtensionT, FallBackTestDef] = MappingProxyType({
    FileExt(".v"): FallBackTestDef({
        "values": ("Proof", "Qed", "Proof", "Defined", "Admitted"),
        "on": "not in",
        "fallback_to": LanguageName(cast(LiteralStringT, "verilog")),  # type: ignore
    }),
    FileExt(".m"): FallBackTestDef({
        "values": ("switch", "end", "parfor", "function"),
        "on": "not in",
        "fallback_to": LanguageName(cast(LiteralStringT, "objective-c")),  # type: ignore
    }),
    FileExt(""): FallBackTestDef({
        "values": (
            "#!/bin/bash",
            "!#/bin/sh",
            "#!/usr/bin/env bash",
            "#!/usr/bin/env sh",
            "#!/usr/bin/env zsh",
            "#!/usr/bin/env fish",
            "#!/usr/bin/env /bin/bash",
            "#!/usr/bin/env /bin/sh",
            "#!/usr/bin/env /bin/zsh",
            "#!/usr/bin/env /usr/bin/zsh",
            "#!/usr/bin/env /usr/bin/fish",
        ),
        "on": "in",
        "fallback_to": LanguageName(cast(LiteralStringT, "bash")),  # type: ignore
    }),
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
    frozenset[LanguageNameT],
    frozenset[LanguageNameT],
    frozenset[LanguageNameT],
    frozenset[LanguageNameT],
]:
    """Helper function to get all languages as frozensets."""
    code_langs: set[LanguageNameT] = cast(
        set[LanguageNameT], {ext.language for ext in CODE_FILES_EXTENSIONS}
    )
    data_langs: set[LanguageNameT] = cast(
        set[LanguageNameT], {ext.language for ext in DATA_FILES_EXTENSIONS}
    )
    doc_langs: set[LanguageNameT] = cast(
        set[LanguageNameT], {ext.language for ext in DOC_FILES_EXTENSIONS}
    )
    all_langs: set[LanguageNameT] = code_langs | data_langs | doc_langs
    return frozenset(code_langs), frozenset(data_langs), frozenset(doc_langs), frozenset(all_langs)


CODE_LANGUAGES, DATA_LANGUAGES, DOCS_LANGUAGES, ALL_LANGUAGES = _get_languages_helper()
"""Frozen sets of languages for code, data, documentation, and all combined."""


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
    "FallBackTestDef",
)
