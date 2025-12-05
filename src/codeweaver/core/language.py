# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# sourcery skip: docstrings-for-functions, equality-identity, no-complex-if-expressions
"""Classes and functions for handling languages and their configuration files in the CodeWeaver project."""

from __future__ import annotations

import contextlib
import os

from collections.abc import Generator
from functools import cache
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, NamedTuple, TypedDict, cast

from pydantic import computed_field

from codeweaver.common.utils import LazyImport, lazy_import, normalize_ext
from codeweaver.core.types.aliases import (
    DirectoryName,
    DirectoryNameT,
    FileExt,
    FileExtensionT,
    FileGlob,
    FileGlobT,
    FileName,
    FileNameT,
    LanguageNameT,
    LiteralStringT,
)
from codeweaver.core.types.enum import BaseEnum


if TYPE_CHECKING:
    from codeweaver.core.metadata import ExtLangPair


type KeyPath = tuple[LiteralStringT, ...]

get_ext_lang_pairs: LazyImport[Generator[ExtLangPair, None, None]] = lazy_import(
    "codeweaver.core.metadata", "get_ext_lang_pairs"
)

ConfigPathPair = NamedTuple(
    "ConfigPathPair", (("path", Path), ("language", "SemanticSearchLanguage"))
)
"""A tuple representing a configuration file path and its associated language, like `(Path("pyproject.toml"), SemanticSearchLanguage.PYTHON)` or `(Path("CMakeLists.txt"), ConfigLanguage.CMAKE)`."""

ConfigNamePair = NamedTuple(
    "ConfigNamePair",
    (("filename", FileNameT), ("language", "SemanticSearchLanguage | ConfigLanguage")),
)
"""A tuple representing a configuration file name and its associated language, like `("pyproject.toml", SemanticSearchLanguage.PYTHON)` or `("CMakeLists.txt", ConfigLanguage.CMAKE)`."""


class LanguageConfigFile(NamedTuple):
    """
    Represents a language configuration file with its name, path, and language type.
    """

    language: SemanticSearchLanguage

    path: Path

    language_type: ConfigLanguage

    dependency_key_paths: tuple[tuple[str, ...], ...] | None = None
    """
    A tuple consisting of tuples. Each inner tuple represents a path to the package dependencies in the config file (not dev, build, or any other dependency groups -- just package dependencies).

    For example, in `pyproject.toml`, there are at least two paths to package dependencies:

      ```python
        dependency_key_paths=(
            ("tool", "poetry", "dependencies"),  # poetry users
            ("project", "dependencies"),         # normal people... I mean, PEP 621 followers
            )
        ```

    If there's only one path, you should still represent it as tuple of tuples, like:
      - `(("tool", "poetry", "dependencies"),)`  # <-- the trailing comma is important

    Some cases me just be a single path with a single key, like:
        - `(("dependencies",),)`

    Makefiles don't really have keys, per-se, but we instead use the `dependency_key_paths` to indicate which variable is used for dependencies, like `CXXFLAGS` or `LDFLAGS`:
    - `dependency_key_paths=(("CXXFLAGS",),)`  # for C++ Makefiles
    - `dependency_key_paths=(("LDFLAGS",),)`   # for C Makefiles
    """

    def exists(self) -> bool:
        """
        Checks if the configuration file exists at the specified path.
        """
        return self.path.exists()


class ConfigLanguage(BaseEnum):
    """
    Enum representing common configuration languages.
    """

    BASH = "bash"
    CMAKE = "cmake"
    INI = "ini"
    HCL = "hcl"
    JSON = "json"
    GROOVY = "groovy"  # Used for Gradle build scripts for Java
    KOTLIN = "kotlin"  # Used for Kotlin build scripts for Java
    MAKE = "make"
    PROPERTIES = "properties"
    SELF = "self"
    """Language's config is written in the same language (e.g., Kotlin, Scala)"""
    TOML = "toml"
    XML = "xml"
    YAML = "yaml"

    @classmethod
    def from_extension(cls, ext: str) -> ConfigLanguage | None:
        """
        Returns the ConfigLanguage associated with the given file extension.
        """
        ext = ext.lower() if ext.startswith(".") else ext
        if ext in cls.all_extensions():
            return next((language for language in cls if ext in language.extensions), None)
        return None

    @property
    def extensions(self) -> tuple[str, ...]:
        """
        Returns the file extensions associated with this configuration language.

        The special value `SELF` indicates that the configuration file is written in the same language as the codebase (e.g., Kotlin, Scala).

        Note: These are only common configuration file extensions for each language. There may be other extensions used in specific cases.
        """
        return {
            # Clearly not all bash, but they are posix shell config files and we can treat them as bash for our purposes
            ConfigLanguage.BASH: (
                ".bashrc",
                ".zshrc",
                ".zprofile",
                ".profile",
                ".bash_profile",
                ".bash_logout",
            ),
            ConfigLanguage.CMAKE: (".cmake", "CMakeLists.txt", "CMakefile", ".cmake.in"),
            ConfigLanguage.INI: (".ini", ".cfg"),
            ConfigLanguage.HCL: (".tf", ".hcl", ".tfvars", ".nomad", ".workflow"),
            ConfigLanguage.JSON: (".json", ".jsonc", ".json5"),
            ConfigLanguage.GROOVY: (".gradle", ".gradle.kts"),
            ConfigLanguage.KOTLIN: (".kts",),
            # spellchecker:off
            ConfigLanguage.MAKE: ("Makefile", "makefile", ".makefile", ".mak", ".make"),
            # spellchecker:on
            ConfigLanguage.PROPERTIES: (".properties",),
            ConfigLanguage.SELF: ("SELF",),
            ConfigLanguage.TOML: (".toml",),
            ConfigLanguage.XML: (".xml",),
            ConfigLanguage.YAML: (".yaml", ".yml"),
        }[self]

    @property
    def is_semantic_search_language(self) -> bool:
        """
        Returns True if this configuration language is also a SemanticSearchLanguage.
        """
        return self.value in SemanticSearchLanguage.values()

    @property
    def as_semantic_search_language(self) -> SemanticSearchLanguage | None:
        """
        Returns a mapping of ConfigLanguage to SemanticSearchLanguage.
        This is used to quickly look up the SemanticSearchLanguage based on ConfigLanguage.
        """
        if self.is_semantic_search_language:
            return SemanticSearchLanguage.from_string(self.value)
        return None

    @classmethod
    def all_extensions(cls) -> Generator[str]:
        """
        Returns all file extensions for all configuration languages.
        """
        yield from (ext for lang in cls for ext in lang.extensions if ext and ext != "SELF")


class RepoConventions(TypedDict, total=False):
    """
    A TypedDict representing common repository conventions for a language.
    """

    source_dirs: tuple[DirectoryNameT, ...]
    """Directories that typically contain source code files."""
    test_dirs: tuple[DirectoryNameT, ...]
    """Directories that typically contain test files."""
    test_patterns: tuple[FileGlobT, ...]
    """File name patterns commonly used for test files."""
    binary_dirs: tuple[DirectoryNameT, ...]
    """Directories that typically contain compiled binaries or build artifacts."""
    binary_patterns: tuple[FileGlobT, ...]
    """File name patterns commonly used for binary files."""
    private_package_dirs: tuple[DirectoryNameT, ...]
    workspace_dirs: tuple[DirectoryNameT, ...]
    """Directories that indicate a workspace, monorepo, or multi-package repository structure or that are used to group packages under a language's conventions."""
    workspace_files: tuple[FileNameT | FileGlobT, ...]
    """Files that indicate a workspace, monorepo, or multi-package repository structure or that are used to group packages under a language's conventions."""
    workspace_defined_in_file: bool
    """Indicates whether the workspace is defined in a specific file (e.g., `settings.gradle.kts` for Kotlin)."""
    workspace_definition_files: tuple[tuple[FileGlobT | FileNameT, KeyPath], ...]
    """Tuple of files and keys or paths within those files that specify the workspace structure."""
    ci_files: tuple[FileNameT | FileGlobT, ...]
    """Common continuous integration (CI) configuration files associated with the language."""


class SemanticSearchLanguage(str, BaseEnum):
    """
    Enum representing supported languages for semantic (AST) search.

    Note: This is the list of built-in languages supported by ast-grep. Ast-grep supports dynamic languages using pre-compiled tree-sitter grammars. We haven't added support for those yet.
    """

    BASH = "bash"
    C_LANG = "c"
    C_PLUS_PLUS = "cpp"
    C_SHARP = "csharp"
    CSS = "css"
    ELIXIR = "elixir"
    GO = "go"
    HASKELL = "haskell"
    HCL = "hcl"
    HTML = "html"
    JAVA = "java"
    JAVASCRIPT = "javascript"
    JSX = "jsx"  # The JavaScript grammar includes JSX support, but we separate it here for clarity
    JSON = "json"
    KOTLIN = "kotlin"
    LUA = "lua"
    NIX = "nix"
    PHP = "php"
    PYTHON = "python"
    RUBY = "ruby"
    RUST = "rust"
    SCALA = "scala"
    SOLIDITY = "solidity"
    SWIFT = "swift"
    # Unlike JSX, the TSX grammar is a separate grammar, but in the same repo and with shared common definitions.
    # While they usually come bundled, they can be separated, so we treat them as separate languages here (and for clarity like with JS/JSX).
    TYPESCRIPT = "typescript"
    TSX = "tsx"
    YAML = "yaml"

    __slots__ = ()

    @property
    def alias(self) -> str | None:
        """
        Provide special-case short-form aliases for certain languages.

        `BaseEnum.from_string` has robust handling for common variations in case, punctuation, and spacing, but it doesn't handle all possible variations. This property, which is accessed by `from_string` and `cls.aliases()`, provides a way to handle special cases that don't fit the general pattern.
        """
        return {
            SemanticSearchLanguage.BASH: "shell",
            SemanticSearchLanguage.C_LANG: "c",
            SemanticSearchLanguage.C_PLUS_PLUS: "c++",
            SemanticSearchLanguage.C_SHARP: "c#",
            SemanticSearchLanguage.HCL: "terraform",
            SemanticSearchLanguage.JAVASCRIPT: "js",
            SemanticSearchLanguage.TYPESCRIPT: "ts",
            SemanticSearchLanguage.PYTHON: "py",
            SemanticSearchLanguage.PHP: "php_sparse",  # there are two tree-sitter grammars for PHP; we call one 'sparse' to differentiate it, but we need to handle 'php' as an alias for it
        }.get(self)

    @classmethod
    def extension_map(cls) -> MappingProxyType[SemanticSearchLanguage, tuple[FileExtensionT, ...]]:
        """
        Returns a mapping of file extensions to their corresponding SemanticSearchLanguage.
        This is used to quickly look up the language based on file extension.
        """
        return MappingProxyType({
            # the bash grammar is pretty tolerant of posix shell scripts, so we include common shell script extensions here
            cls.BASH: (
                FileExt(".bash"),
                FileExt(".bash_profile"),
                FileExt(".bashrc"),
                FileExt(".csh"),
                FileExt(".cshrc"),
                FileExt(".ksh"),
                FileExt(".kshrc"),
                FileExt(".profile"),
                FileExt(".sh"),
                FileExt(".tcsh"),
                FileExt(".tcshrc"),
                FileExt(".zprofile"),
                FileExt(".zsh"),
                FileExt(".zshrc"),
            ),
            cls.C_LANG: (FileExt(".c"), FileExt(".h")),
            cls.C_PLUS_PLUS: (FileExt(".cpp"), FileExt(".hpp"), FileExt(".cc"), FileExt(".cxx")),
            cls.C_SHARP: (FileExt(".cs"), FileExt(".csharp")),
            cls.CSS: (FileExt(".css"),),
            cls.ELIXIR: (FileExt(".ex"), FileExt(".exs")),
            cls.GO: (FileExt(".go"),),
            cls.HASKELL: (FileExt(".hs"),),
            cls.HCL: (
                FileExt(".tf"),
                FileExt(".hcl"),
                FileExt(".nomad"),
                FileExt(".tf"),
                FileExt(".tfvars"),
                FileExt(".workflow"),
            ),
            cls.HTML: (FileExt(".html"), FileExt(".htm"), FileExt(".xhtml")),
            cls.JAVA: (FileExt(".java"),),
            cls.JAVASCRIPT: (FileExt(".js"), FileExt(".mjs"), FileExt(".cjs")),
            cls.JSON: (FileExt(".json"), FileExt(".jsonc"), FileExt(".json5")),
            cls.JSX: (FileExt(".jsx"),),
            cls.KOTLIN: (FileExt(".kt"), FileExt(".kts"), FileExt(".ktm")),
            cls.LUA: (FileExt(".lua"),),
            cls.NIX: (FileExt(".nix"),),
            cls.PHP: (FileExt(".php"), FileExt(".phtml")),
            cls.PYTHON: (
                FileExt(".py"),
                FileExt(".pyi"),
                FileExt(".py3"),
                FileExt(".bzl"),
                FileExt(".ipynb"),
            ),
            cls.RUBY: (FileExt(".rb"), FileExt(".gemspec"), FileExt(".rake"), FileExt(".ru")),
            cls.RUST: (FileExt(".rs"),),
            cls.SCALA: (FileExt(".scala"), FileExt(".sc"), FileExt(".sbt")),
            cls.SOLIDITY: (FileExt(".sol"),),
            cls.SWIFT: (FileExt(".swift"),),
            cls.TYPESCRIPT: (FileExt(".ts"), FileExt(".mts"), FileExt(".cts")),
            cls.TSX: (FileExt(".tsx"),),
            cls.YAML: (FileExt(".yaml"), FileExt(".yml")),
        })

    @classmethod
    def from_extension(cls, ext: FileExtensionT | LiteralStringT) -> SemanticSearchLanguage | None:
        """
        Returns the SemanticSearchLanguage associated with the given file extension.
        """
        ext = FileExt(ext.lower()) if ext.startswith(".") else FileExt(f".{ext.lower()}")
        return next(
            (language for language, extensions in cls.extension_map().items() if ext in extensions),
            None,
        )

    @property
    def extensions(self) -> tuple[FileExtensionT, ...] | None:
        """
        Returns the file extensions associated with this language.
        """
        return type(self).extension_map()[self]

    @property
    def config_files(self) -> tuple[LanguageConfigFile, ...] | None:  # noqa: C901  # it's long, but not complex
        """
        Returns the LanguageConfigFiles associated with this language.

        # We haven't implemented dependency extraction yet, but when we do, we want to make sure these paths are correct.
        """
        match self:
            case SemanticSearchLanguage.C_LANG:
                return (
                    LanguageConfigFile(
                        language=self,
                        path=Path("Makefile"),
                        language_type=ConfigLanguage.MAKE,
                        dependency_key_paths=(("CFLAGS",), ("LDFLAGS",)),
                    ),
                )
            case SemanticSearchLanguage.C_PLUS_PLUS:
                return (
                    LanguageConfigFile(
                        language=self,
                        path=Path("CMakeLists.txt"),
                        language_type=ConfigLanguage.CMAKE,
                        dependency_key_paths=(("CMAKE_CXX_FLAGS",), ("CMAKE_EXE_LINKER_FLAGS",)),
                    ),
                    LanguageConfigFile(
                        language=self,
                        path=Path("Makefile"),
                        language_type=ConfigLanguage.MAKE,
                        dependency_key_paths=(("CXXFLAGS",), ("LDFLAGS",)),
                    ),
                )
            case SemanticSearchLanguage.C_SHARP:
                return (
                    LanguageConfigFile(
                        language=self,
                        path=Path("app.config"),
                        language_type=ConfigLanguage.XML,
                        dependency_key_paths=(
                            ("configuration", "appSettings", "add"),
                            ("configuration", "connectionStrings", "add"),
                            (
                                "configuration",
                                "runtime",
                                "assemblyBinding",
                                "dependentAssembly",
                                "assemblyIdentity",
                            ),
                        ),
                    ),
                    LanguageConfigFile(
                        language=self,
                        path=next(iter(Path().glob("*.csproj")), None),  # type: ignore
                        language_type=ConfigLanguage.XML,
                        dependency_key_paths=(
                            ("Project", "ItemGroup", "PackageReference"),
                            ("Project", "ItemGroup", "Reference"),
                            ("Project", "ItemGroup", "ProjectReference"),
                        ),
                    ),
                )
            case SemanticSearchLanguage.ELIXIR:
                return (
                    LanguageConfigFile(
                        language=self,
                        path=Path("mix.exs"),
                        language_type=ConfigLanguage.SELF,
                        dependency_key_paths=(("deps",), ("aliases", "deps")),
                    ),
                )
            case SemanticSearchLanguage.GO:
                return (
                    LanguageConfigFile(
                        language=self,
                        path=Path("go.mod"),
                        language_type=ConfigLanguage.INI,
                        dependency_key_paths=(("require",), ("replace",)),
                    ),
                )
            case SemanticSearchLanguage.HASKELL:
                return (
                    LanguageConfigFile(
                        language=self,
                        path=Path("package.yaml"),
                        language_type=ConfigLanguage.YAML,
                        dependency_key_paths=(("dependencies",), ("build-depends",)),
                    ),
                    LanguageConfigFile(
                        language=self,
                        path=Path(os.environ.get("STACK_YAML") or Path("stack.yml")),
                        language_type=ConfigLanguage.YAML,
                        dependency_key_paths=(("extra-deps",),),
                    ),
                    LanguageConfigFile(
                        language=self,
                        path=next(iter(Path().glob("*.cabal")), Path("package.cabal")),
                        language_type=ConfigLanguage.INI,
                        dependency_key_paths=(
                            ("build-depends",),
                            ("library", "build-depends"),
                            ("executable", "build-depends"),
                        ),
                    ),
                )
            case SemanticSearchLanguage.JAVA:
                return (
                    LanguageConfigFile(
                        language=self,
                        path=Path("pom.xml"),
                        language_type=ConfigLanguage.XML,
                        dependency_key_paths=(
                            ("project", "dependencies", "dependency"),
                            ("project", "dependencyManagement", "dependencies", "dependency"),
                        ),
                    ),
                    LanguageConfigFile(
                        language=self,
                        path=Path("build.gradle"),
                        language_type=ConfigLanguage.GROOVY,
                        dependency_key_paths=(
                            ("dependencies",),
                            ("configurations", "compileClasspath", "dependencies"),
                            ("configurations", "runtimeClasspath", "dependencies"),
                        ),
                    ),
                    LanguageConfigFile(
                        language=self,
                        path=Path("build.gradle.kts"),
                        language_type=ConfigLanguage.KOTLIN,
                        dependency_key_paths=(
                            ("dependencies",),
                            ("configurations", "compileClasspath", "dependencies"),
                            ("configurations", "runtimeClasspath", "dependencies"),
                        ),
                    ),
                )
            case (
                SemanticSearchLanguage.JAVASCRIPT
                | SemanticSearchLanguage.JSX
                | SemanticSearchLanguage.TYPESCRIPT
                | SemanticSearchLanguage.TSX
            ):
                return (
                    LanguageConfigFile(
                        language=self,
                        path=Path("package.json"),
                        language_type=ConfigLanguage.JSON,
                        dependency_key_paths=(("dependencies",),),
                    ),
                )
            case SemanticSearchLanguage.KOTLIN:
                return (
                    LanguageConfigFile(
                        language=self,
                        path=Path("build.gradle.kts"),
                        language_type=ConfigLanguage.SELF,
                        dependency_key_paths=(
                            ("dependencies",),
                            ("configurations", "compileClasspath", "dependencies"),
                            ("configurations", "runtimeClasspath", "dependencies"),
                        ),
                    ),
                    LanguageConfigFile(
                        language=self,
                        path=Path("settings.gradle.kts"),
                        language_type=ConfigLanguage.SELF,
                        dependency_key_paths=(
                            ("dependencyResolutionManagement", "repositories"),
                            ("pluginManagement", "repositories"),
                        ),
                    ),
                )
            case SemanticSearchLanguage.LUA:
                return (
                    LanguageConfigFile(
                        language=self,
                        path=Path("luarocks.json"),
                        language_type=ConfigLanguage.JSON,
                        dependency_key_paths=(("dependencies",), ("build_dependencies",)),
                    ),
                    LanguageConfigFile(
                        language=self,
                        path=Path("rockspec.json"),
                        language_type=ConfigLanguage.JSON,
                        dependency_key_paths=(("dependencies",), ("build_dependencies",)),
                    ),
                    LanguageConfigFile(
                        language=self,
                        path=Path("rockspec"),
                        language_type=ConfigLanguage.INI,
                        dependency_key_paths=(("dependencies",), ("build_dependencies",)),
                    ),
                )
            case SemanticSearchLanguage.NIX:
                return (
                    LanguageConfigFile(
                        language=self,
                        path=Path("default.nix"),
                        language_type=ConfigLanguage.SELF,
                        dependency_key_paths=(
                            ("dependencies",),
                            ("buildInputs",),
                            ("nativeBuildInputs",),
                            ("propagatedBuildInputs",),
                            ("buildInputs", "dependencies"),
                        ),
                    ),
                )
            case SemanticSearchLanguage.PHP:
                return (
                    LanguageConfigFile(
                        language=self,
                        path=Path("composer.json"),
                        language_type=ConfigLanguage.JSON,
                        dependency_key_paths=(("require",),),
                    ),
                )
            case SemanticSearchLanguage.PYTHON:
                return (
                    LanguageConfigFile(
                        language=self,
                        path=Path("pyproject.toml"),
                        language_type=ConfigLanguage.TOML,
                        dependency_key_paths=(
                            ("tool", "poetry", "dependencies"),
                            ("project", "dependencies"),
                        ),
                    ),
                )
            case SemanticSearchLanguage.RUBY:
                return (
                    LanguageConfigFile(
                        language=self,
                        path=Path("Gemfile"),
                        language_type=ConfigLanguage.SELF,
                        dependency_key_paths=(
                            ("gems",),
                            ("source", "gems"),
                            ("source", "gemspec", "gems"),
                        ),
                    ),
                    LanguageConfigFile(
                        language=self,
                        path=Path("Rakefile"),
                        language_type=ConfigLanguage.SELF,
                        dependency_key_paths=(
                            ("gems",),
                            ("source", "gems"),
                            ("source", "gemspec", "gems"),
                        ),
                    ),
                    LanguageConfigFile(
                        language=self,
                        path=Path("gemspec"),
                        language_type=ConfigLanguage.SELF,
                        dependency_key_paths=(("dependencies",),),
                    ),
                    LanguageConfigFile(
                        language=self,
                        path=Path("config.ru"),
                        language_type=ConfigLanguage.SELF,
                        dependency_key_paths=(
                            ("gems",),
                            ("source", "gems"),
                            ("source", "gemspec", "gems"),
                        ),
                    ),
                )
            case SemanticSearchLanguage.RUST:
                return (
                    LanguageConfigFile(
                        language=self,
                        path=Path("Cargo.toml"),
                        language_type=ConfigLanguage.TOML,
                        dependency_key_paths=(("dependencies",),),
                    ),
                )
            case SemanticSearchLanguage.SCALA:
                return (
                    LanguageConfigFile(
                        language=self,
                        path=Path("build.sbt"),
                        language_type=ConfigLanguage.SELF,
                        dependency_key_paths=(
                            ("libraryDependencies",),
                            ("compile", "dependencies"),
                            ("runtime", "dependencies"),
                        ),
                    ),
                    LanguageConfigFile(
                        language=self,
                        path=Path("project") / "build.properties",
                        language_type=ConfigLanguage.PROPERTIES,
                        dependency_key_paths=(("sbt.version",),),
                    ),
                )
            case SemanticSearchLanguage.SWIFT:
                return (
                    LanguageConfigFile(
                        language=self,
                        path=Path("Package.swift"),
                        language_type=ConfigLanguage.SELF,
                        dependency_key_paths=(
                            ("dependencies",),
                            ("targets", "dependencies"),
                            ("products", "dependencies"),
                        ),
                    ),
                )
            case _:
                return None

    @property
    def ast_grep(self) -> str:
        """
        Returns the ast-grep language name for this language.
        """
        return {
            SemanticSearchLanguage.BASH: "bash",
            SemanticSearchLanguage.C_PLUS_PLUS: "cpp",
            SemanticSearchLanguage.C_SHARP: "csharp",
            SemanticSearchLanguage.CSS: "css",
            SemanticSearchLanguage.ELIXIR: "elixir",
            SemanticSearchLanguage.HCL: "hcl",
            SemanticSearchLanguage.HTML: "html",
            SemanticSearchLanguage.JAVA: "java",
            SemanticSearchLanguage.JAVASCRIPT: "javascript",
            SemanticSearchLanguage.JSX: "jsx",
            SemanticSearchLanguage.JSON: "json",
            SemanticSearchLanguage.KOTLIN: "kotlin",
            SemanticSearchLanguage.LUA: "lua",
            SemanticSearchLanguage.NIX: "nix",
            SemanticSearchLanguage.PHP: "php",
            SemanticSearchLanguage.PYTHON: "python",
            SemanticSearchLanguage.RUBY: "ruby",
            SemanticSearchLanguage.RUST: "rust",
            SemanticSearchLanguage.SCALA: "scala",
            SemanticSearchLanguage.SOLIDITY: "solidity",
            SemanticSearchLanguage.SWIFT: "swift",
            SemanticSearchLanguage.TYPESCRIPT: "typescript",
            SemanticSearchLanguage.TSX: "tsx",
            SemanticSearchLanguage.YAML: "yaml",
        }[self]

    @classmethod
    def injection_languages(cls) -> tuple[SemanticSearchLanguage, ...]:
        """
        Returns supported languages that commonly contain embedded code snippets from other languages.
        """
        return (cls.HTML, cls.JAVASCRIPT, cls.JSX, cls.TYPESCRIPT, cls.TSX, cls.PHP)

    @property
    def is_injection_language(self) -> bool:
        """
        Returns True if this language commonly contains embedded code snippets from other languages.
        """
        return self in type(self).injection_languages()

    @property
    def injected_languages(self) -> tuple[SemanticSearchLanguage, ...] | None:
        """
        Returns the languages commonly injected into this language, if any.
        """
        return {
            SemanticSearchLanguage.HTML: (
                SemanticSearchLanguage.CSS,
                SemanticSearchLanguage.JAVASCRIPT,
            ),
            SemanticSearchLanguage.JAVASCRIPT: (
                SemanticSearchLanguage.HTML,
                SemanticSearchLanguage.CSS,
            ),
            SemanticSearchLanguage.JSX: (SemanticSearchLanguage.HTML, SemanticSearchLanguage.CSS),
            SemanticSearchLanguage.TYPESCRIPT: (
                SemanticSearchLanguage.HTML,
                SemanticSearchLanguage.CSS,
            ),
            SemanticSearchLanguage.TSX: (SemanticSearchLanguage.HTML, SemanticSearchLanguage.CSS),
            SemanticSearchLanguage.PHP: (
                SemanticSearchLanguage.HTML,
                SemanticSearchLanguage.JAVASCRIPT,
                SemanticSearchLanguage.CSS,
            ),
            SemanticSearchLanguage.TYPESCRIPT: (
                SemanticSearchLanguage.HTML,
                SemanticSearchLanguage.CSS,
            ),
        }.get(self)

    @property
    def is_config_language(self) -> bool:
        """
        Returns True if this language is a configuration language.
        """
        return self.value in ConfigLanguage.values() and self is not SemanticSearchLanguage.KOTLIN

    @classmethod
    def config_language_exts(cls) -> Generator[str]:
        """
        Returns all file extensions associated with the configuration languages.
        """
        yield from (
            ext
            for lang in cls
            for ext in cls.extension_map()[lang]
            if isinstance(lang, cls) and lang.is_config_language and ext and ext != FileExt(".sh")
        )

    @property
    def as_config_language(self) -> ConfigLanguage | None:
        """
        Returns the corresponding ConfigLanguage if this SemanticSearchLanguage is a configuration language.
        """
        return (
            ConfigLanguage.from_string(self.value)
            if self in type(self).config_languages()
            else None
        )

    @classmethod
    def config_languages(cls) -> tuple[SemanticSearchLanguage, ...]:
        """
        Returns all SemanticSearchLanguages that are also configuration languages.
        """
        return tuple(lang for lang in cls if lang.is_config_language)

    @classmethod
    def all_config_paths(cls) -> Generator[Path]:
        """
        Returns all configuration file paths for all languages.
        """
        for _lang, config_files in cls.config_pairs():
            yield from (
                config_file.path
                for config_file in config_files
                if config_file and isinstance(config_file, LanguageConfigFile)
            )

    @classmethod
    def all_extensions(cls) -> Generator[LiteralStringT]:
        """
        Returns all file extensions for all languages.
        """
        yield from (ext for lang in cls for ext in cls.extension_map()[lang] if ext)

    @classmethod
    def filename_pairs(cls) -> Generator[ConfigNamePair]:
        """
        Returns a frozenset of tuples containing file names and their corresponding SemanticSearchLanguage.
        """
        for lang in cls:
            if lang.config_files is not None:
                yield from (
                    ConfigNamePair(
                        filename=config_file.path.name,
                        language=config_file.language_type
                        if config_file.language_type != ConfigLanguage.SELF
                        else lang,
                    )
                    for config_file in lang.config_files
                    if config_file.path
                )

    @classmethod
    def code_extensions(cls) -> Generator[str]:
        """
        Returns all file extensions associated with programming languages (excluding configuration languages).
        """
        yield from (
            ext for ext in cls.all_extensions() if ext and ext not in cls.config_language_exts()
        )

    @classmethod
    def ext_pairs(cls) -> Generator[ExtLangPair]:
        """
        Returns a frozenset of tuples containing file extensions and their corresponding SemanticSearchLanguage.
        """
        from codeweaver.core.metadata import ExtLangPair

        for lang, exts in cls.extension_map().items():
            yield from (ExtLangPair(ext=FileExt(ext), language=lang) for ext in exts if ext)  # type: ignore

    @classmethod
    def config_pairs(cls) -> Generator[ConfigPathPair]:
        """
        Returns a tuple mapping of all config file paths to their corresponding LanguageConfigFile.
        """
        all_paths: list[ConfigPathPair] = []
        for lang in cls:
            if not lang.config_files:
                continue
            all_paths.extend(
                ConfigPathPair(path=config_file.path, language=lang)
                for config_file in lang.config_files
                if config_file and config_file.path
            )
        yield from all_paths

    @classmethod
    def _language_from_config_file(cls, config_file: Path) -> SemanticSearchLanguage | None:
        """
        Returns the SemanticSearchLanguage for a given configuration file path.

        Args:
            config_file: The path to the configuration file.

        Returns:
            The corresponding SemanticSearchLanguage, or None if not found.
        """
        normalized_path = Path(config_file.name)
        if not normalized_path.exists() or all(
            str(normalized_path) not in str(p) for p in cls.all_config_paths()
        ):
            return None
        if config_file.name in ("Makefile", "build.gradle.kts"):
            if config_file.name == "Makefile":
                # C++ is more popular... no other reasoning here

                return SemanticSearchLanguage.C_PLUS_PLUS
            # Java's more common than Kotlin, but Kotlin is more likely to use 'build.gradle.kts' ... I think. 🤷‍♂️
            return SemanticSearchLanguage.KOTLIN
        if config_file.suffix in cast(tuple[str, ...], cls.HCL.extensions):
            return SemanticSearchLanguage.HCL
        return next(
            (
                lang
                for lang in cls
                if lang.config_files is not None
                and next(
                    (
                        cfg.path.name
                        for cfg in lang.config_files
                        if cfg.path.name == config_file.name
                    ),
                    None,
                )
            ),
            None,
        )

    @classmethod
    def lang_from_ext(cls, ext: str) -> SemanticSearchLanguage | None:
        # sourcery skip: equality-identity
        """
        Returns the SemanticSearchLanguage for a given file extension.

        Args:
            ext: The file extension to look up.

        Returns:
            The corresponding SemanticSearchLanguage, or None if not found.
        """
        return next(
            (
                lang
                for lang in cls
                if lang.extensions
                if next((extension for extension in lang.extensions if ext == extension), None)
            ),
            None,
        )

    @computed_field
    @property
    def repo_conventions(self) -> RepoConventions:
        """
        Returns the repository conventions associated with this language.
        """
        defaults = RepoConventions(
            source_dirs=(DirectoryName("src"), DirectoryName("source"), DirectoryName("lib")),
            test_dirs=(DirectoryName("tests"), DirectoryName("test"), DirectoryName("spec")),
            test_patterns=(FileGlob("test_*"), FileGlob("_test")),
            binary_dirs=(DirectoryName("build"), DirectoryName("bin"), DirectoryName("obj")),
            workspace_defined_in_file=False,
        )
        return {
            SemanticSearchLanguage.BASH: defaults
            | RepoConventions(
                source_dirs=(DirectoryName("scripts"), DirectoryName("bin"), DirectoryName("lib")),
                test_dirs=(DirectoryName("tests"), DirectoryName("test")),
                test_patterns=(FileGlob("test_*"), FileGlob("_test.sh"), FileGlob(".bats")),
                binary_dirs=(),
            ),
            SemanticSearchLanguage.C_LANG: defaults
            | RepoConventions(
                source_dirs=(DirectoryName("src"),),
                test_dirs=(DirectoryName("tests"), DirectoryName("test")),
                test_patterns=(FileGlob("test_*"), FileGlob("_test.c")),
                binary_dirs=(DirectoryName("build"), DirectoryName("bin"), DirectoryName("obj")),
                binary_patterns=(FileGlob("*.o"), FileGlob("*.out"), FileGlob("*.exe")),
                workspace_files=(FileName("CMakeLists.txt"), FileName("Makefile")),
            ),
            SemanticSearchLanguage.C_PLUS_PLUS: defaults
            | RepoConventions(
                source_dirs=(DirectoryName("src"), DirectoryName("include")),
                test_dirs=(DirectoryName("tests"), DirectoryName("test")),
                test_patterns=(FileGlob("test_*"), FileGlob("_test.cpp"), FileGlob("_test.cc")),
                binary_dirs=(
                    DirectoryName("build"),
                    DirectoryName("bin"),
                    DirectoryName("obj"),
                    DirectoryName("cmake-build-debug"),
                    DirectoryName("cmake-build-release"),
                ),
                workspace_files=(FileName("CMakeLists.txt"), FileName("Makefile")),
            ),
            SemanticSearchLanguage.C_SHARP: defaults
            | RepoConventions(
                source_dirs=(DirectoryName("src"),),
                test_dirs=(DirectoryName("tests"), DirectoryName("test")),
                test_patterns=(FileGlob("Test.cs"), FileGlob("Tests.cs")),
                binary_dirs=(DirectoryName("bin"), DirectoryName("obj")),
                workspace_files=(FileName("*.sln"),),
                workspace_defined_in_file=True,
                workspace_definition_files=(
                    (
                        FileGlob("*.sln"),
                        ("Project",),
                    ),  # Solution files list projects # type: ignore
                ),
            ),
            SemanticSearchLanguage.CSS: defaults
            | RepoConventions(
                source_dirs=(
                    DirectoryName("src"),
                    DirectoryName("styles"),
                    DirectoryName("css"),
                    DirectoryName("assets"),
                ),
                test_dirs=(),  # CSS rarely has dedicated test directories
                test_patterns=(),
                binary_dirs=(DirectoryName("dist"), DirectoryName("build")),
            ),
            SemanticSearchLanguage.ELIXIR: defaults
            | RepoConventions(
                source_dirs=(DirectoryName("lib"),),
                test_dirs=(DirectoryName("test"),),
                test_patterns=(FileGlob("_test.exs"),),
                binary_dirs=(DirectoryName("_build"), DirectoryName("deps")),
                workspace_dirs=(DirectoryName("apps"),),
                workspace_files=(FileName("mix.exs"),),
                workspace_defined_in_file=True,
                workspace_definition_files=(
                    (FileName("mix.exs"), ("umbrella",)),  # umbrella: true in mix.exs
                ),
            ),
            SemanticSearchLanguage.GO: defaults
            | RepoConventions(
                source_dirs=(DirectoryName("internal"), DirectoryName("pkg"), DirectoryName("cmd")),
                test_dirs=(DirectoryName("tests"), DirectoryName("test")),
                test_patterns=(FileGlob("_test.go"),),
                binary_dirs=(DirectoryName("bin"), DirectoryName("build")),
                private_package_dirs=(DirectoryName("internal"),),  # Compiler-enforced
                workspace_files=(FileName("go.work"), FileName("go.mod")),
                workspace_defined_in_file=True,
                workspace_definition_files=(
                    (FileName("go.work"), ("use",)),  # go.work lists workspace members
                ),
            ),
            SemanticSearchLanguage.HASKELL: defaults
            | RepoConventions(
                source_dirs=(DirectoryName("src"),),
                test_dirs=(DirectoryName("test"),),
                test_patterns=(
                    FileGlob("Spec.hs"),
                    FileGlob("Test.hs"),
                    FileGlob("*Spec.hs"),
                    FileGlob("*Test.hs"),
                ),
                binary_dirs=(
                    DirectoryName("dist"),
                    DirectoryName("dist-newstyle"),
                    DirectoryName(".stack-work"),
                ),
                workspace_dirs=(DirectoryName("app"), DirectoryName("apps")),
                workspace_files=(
                    FileName("cabal.project"),
                    FileName("stack.yaml"),
                    FileName("package.yaml"),
                ),
                workspace_defined_in_file=True,
                workspace_definition_files=(
                    (FileName("cabal.project"), ("packages",)),
                    (FileName("stack.yaml"), ("packages",)),
                    (FileName("package.yaml"), ("packages",)),
                ),
            ),
            SemanticSearchLanguage.HCL: defaults
            | RepoConventions(
                source_dirs=(
                    DirectoryName("."),
                    DirectoryName("infrastructure"),
                    DirectoryName("infra"),
                    DirectoryName("terraform"),
                ),
                test_dirs=(DirectoryName("test"),),
                test_patterns=(),
                binary_dirs=(DirectoryName("bin"), DirectoryName("build")),
            ),
            SemanticSearchLanguage.HTML: defaults
            | RepoConventions(
                source_dirs=(
                    DirectoryName("src"),
                    DirectoryName("public"),
                    DirectoryName("static"),
                ),
                test_dirs=(),
                test_patterns=(),
                binary_dirs=(DirectoryName("dist"), DirectoryName("build")),
            ),
            SemanticSearchLanguage.JAVA: defaults
            | RepoConventions(
                source_dirs=(DirectoryName("src/main/java"), DirectoryName("src")),
                test_dirs=(
                    DirectoryName("src/test/java"),
                    DirectoryName("tests"),
                    DirectoryName("test"),
                ),
                test_patterns=(FileGlob("Test.java"), FileGlob("*Test.java")),
                binary_dirs=(
                    DirectoryName("target"),
                    DirectoryName("build"),
                    DirectoryName("out"),
                    DirectoryName("bin"),
                ),
                workspace_files=(
                    FileName("settings.gradle"),
                    FileName("settings.gradle.kts"),
                    FileName("pom.xml"),
                    FileName("build.gradle"),
                    FileName("build.gradle.kts"),
                ),
                workspace_defined_in_file=True,
                workspace_definition_files=(
                    (FileName("settings.gradle"), ("include",)),
                    (FileName("settings.gradle.kts"), ("include",)),
                    (FileName("pom.xml"), ("modules",)),
                ),
            ),
            SemanticSearchLanguage.JAVASCRIPT: defaults
            | RepoConventions(
                source_dirs=(DirectoryName("src"), DirectoryName("lib")),
                test_dirs=(
                    DirectoryName("tests"),
                    DirectoryName("test"),
                    DirectoryName("__tests__"),
                ),
                test_patterns=(
                    FileGlob(".*.test.js"),
                    FileGlob(".*.spec.js"),
                    FileGlob("test/*"),
                    FileGlob("spec/*"),
                ),
                binary_dirs=(
                    DirectoryName("node_modules"),
                    DirectoryName("dist"),
                    DirectoryName("build"),
                ),
                private_package_dirs=(DirectoryName("node_modules"),),
                workspace_dirs=(DirectoryName("packages"), DirectoryName("apps")),
                workspace_files=(
                    FileName("package.json"),
                    FileName("lerna.json"),
                    FileName("pnpm-workspace.yaml"),
                    FileName("turbo.json"),
                    FileName("nx.json"),
                ),
                workspace_defined_in_file=True,
                workspace_definition_files=(
                    (FileName("package.json"), ("workspaces",)),
                    (FileName("lerna.json"), ("packages",)),
                    (FileName("pnpm-workspace.yaml"), ("packages",)),
                ),
            ),
            SemanticSearchLanguage.JSX: defaults
            | RepoConventions(
                source_dirs=(
                    DirectoryName("src"),
                    DirectoryName("lib"),
                    DirectoryName("components"),
                ),
                test_dirs=(
                    DirectoryName("tests"),
                    DirectoryName("test"),
                    DirectoryName("__tests__"),
                ),
                test_patterns=(
                    FileGlob(".*.test.jsx"),
                    FileGlob(".*.spec.jsx"),
                    FileGlob("test/*"),
                    FileGlob("spec/*"),
                ),
                binary_dirs=(
                    DirectoryName("node_modules"),
                    DirectoryName("dist"),
                    DirectoryName("build"),
                ),
                private_package_dirs=(DirectoryName("node_modules"),),
                workspace_dirs=(DirectoryName("packages"), DirectoryName("apps")),
                workspace_files=(
                    FileName("package.json"),
                    FileName("lerna.json"),
                    FileName("pnpm-workspace.yaml"),
                    FileName("turbo.json"),
                    FileName("nx.json"),
                ),
                workspace_defined_in_file=True,
                workspace_definition_files=(
                    (FileName("package.json"), ("workspaces",)),
                    (FileName("lerna.json"), ("packages",)),
                    (FileName("pnpm-workspace.yaml"), ("packages",)),
                ),
            ),
            SemanticSearchLanguage.JSON: defaults
            | RepoConventions(
                source_dirs=(
                    DirectoryName("config"),
                    DirectoryName("data"),
                    DirectoryName("schemas"),
                ),
                test_dirs=(),
                test_patterns=(),
                binary_dirs=(),
            ),
            SemanticSearchLanguage.KOTLIN: defaults
            | RepoConventions(
                source_dirs=(DirectoryName("src/main/kotlin"), DirectoryName("src")),
                test_dirs=(
                    DirectoryName("src/test/kotlin"),
                    DirectoryName("tests"),
                    DirectoryName("test"),
                ),
                test_patterns=(FileGlob("Test.kt"), FileGlob("*Test.kt")),
                binary_dirs=(DirectoryName("target"), DirectoryName("build"), DirectoryName("out")),
                workspace_files=(
                    FileName("settings.gradle"),
                    FileName("settings.gradle.kts"),
                    FileName("build.gradle.kts"),
                ),
                workspace_defined_in_file=True,
                workspace_definition_files=(
                    (FileName("settings.gradle"), ("include",)),
                    (FileName("settings.gradle.kts"), ("include",)),
                ),
            ),
            SemanticSearchLanguage.LUA: defaults
            | RepoConventions(
                source_dirs=(DirectoryName("src"), DirectoryName("lib")),
                test_dirs=(DirectoryName("test"), DirectoryName("spec")),
                test_patterns=(FileGlob("_spec.lua"), FileGlob("_test.lua")),
                workspace_files=(FileName("*.rockspec"),),
            ),
            SemanticSearchLanguage.NIX: defaults
            | RepoConventions(
                source_dirs=(
                    DirectoryName("."),
                ),  # Nix files are often at root or in various locations
                test_dirs=(DirectoryName("tests"),),
                test_patterns=(FileGlob("test.nix"),),
                binary_dirs=(DirectoryName("result"),),  # Nix build output symlink
            ),
            SemanticSearchLanguage.PHP: defaults
            | RepoConventions(
                source_dirs=(DirectoryName("src"), DirectoryName("lib"), DirectoryName("app")),
                test_dirs=(DirectoryName("tests"),),
                test_patterns=(FileGlob("Test.php"), FileGlob("*Test.php")),
                binary_dirs=(DirectoryName("vendor"), DirectoryName("build")),
                private_package_dirs=(DirectoryName("vendor"),),
                workspace_files=(FileName("composer.json"),),
                workspace_defined_in_file=True,
                workspace_definition_files=(
                    (
                        FileName("composer.json"),
                        (("repositories"),),
                    ),  # Path repositories for monorepos
                ),
            ),
            SemanticSearchLanguage.PYTHON: defaults
            | RepoConventions(
                source_dirs=(DirectoryName("src"), DirectoryName("lib")),
                test_dirs=(DirectoryName("tests"), DirectoryName("test")),
                test_patterns=(FileGlob("test_*"), FileGlob("_test.py")),
                binary_dirs=(
                    DirectoryName("build"),
                    DirectoryName("dist"),
                    DirectoryName("__pycache__"),
                    DirectoryName(".pytest_cache"),
                    DirectoryName(".mypy_cache"),
                    DirectoryName("*.egg-info"),
                ),
                private_package_dirs=(
                    DirectoryName(".venv"),
                    DirectoryName("venv"),
                    DirectoryName(".env"),
                    DirectoryName("env"),
                    DirectoryName("virtualenv"),
                ),
                workspace_files=(FileName("pyproject.toml"), FileName("setup.py")),
                workspace_defined_in_file=True,
                workspace_definition_files=(
                    (FileName("pyproject.toml"), (("tool.poetry"),)),
                    (FileName("pyproject.toml"), (("tool.hatch"),)),  # Poetry/Hatch workspaces
                ),
            ),
            SemanticSearchLanguage.RUBY: defaults
            | RepoConventions(
                source_dirs=(DirectoryName("lib"),),
                test_dirs=(DirectoryName("spec"), DirectoryName("test")),
                test_patterns=(FileGlob("_spec.rb"), FileGlob("_test.rb")),
                binary_dirs=(DirectoryName("vendor"), DirectoryName("bundle")),
                private_package_dirs=(DirectoryName("vendor"),),
                workspace_files=(FileName("Gemfile"), FileGlob("*.gemspec")),
                workspace_defined_in_file=True,
                workspace_definition_files=(
                    (FileName("Gemfile"), (("path:"),)),  # Local gems via path: option
                ),
            ),
            SemanticSearchLanguage.RUST: defaults
            | RepoConventions(
                source_dirs=(DirectoryName("src"), DirectoryName("crates")),
                test_dirs=(DirectoryName("tests"),),
                test_patterns=(FileGlob("test_*"), FileGlob("_test.rs")),
                binary_dirs=(DirectoryName("target"),),
                workspace_dirs=(DirectoryName("crates"),),
                workspace_files=(FileName("Cargo.toml"),),
                workspace_defined_in_file=True,
                workspace_definition_files=(
                    (FileName("Cargo.toml"), (("workspace"),)),  # [workspace] section
                ),
            ),
            SemanticSearchLanguage.SCALA: defaults
            | RepoConventions(
                source_dirs=(DirectoryName("src/main/scala"),),
                test_dirs=(DirectoryName("src/test/scala"),),
                test_patterns=(
                    FileGlob("Test.scala"),
                    FileGlob("*Test.scala"),
                    FileGlob("*Spec.scala"),
                ),
                binary_dirs=(DirectoryName("target"), DirectoryName("project/target")),
                workspace_files=(FileName("build.sbt"),),
                workspace_defined_in_file=True,
                workspace_definition_files=(
                    (
                        FileName("build.sbt"),
                        (("lazy val"),),
                    ),  # Multiple lazy val definitions indicate subprojects
                ),
            ),
            SemanticSearchLanguage.SOLIDITY: defaults
            | RepoConventions(
                source_dirs=(DirectoryName("contracts"), DirectoryName("src")),
                test_dirs=(DirectoryName("test"),),
                test_patterns=(
                    FileGlob(".*.test.sol"),
                    FileGlob(".*.t.sol"),
                ),  # Foundry uses .t.sol
                binary_dirs=(
                    DirectoryName("artifacts"),
                    DirectoryName("cache"),
                    DirectoryName("out"),
                ),
                workspace_files=(
                    FileName("hardhat.config.js"),
                    FileName("hardhat.config.ts"),
                    FileName("foundry.toml"),
                    FileName("truffle-config.js"),
                ),
            ),
            SemanticSearchLanguage.SWIFT: defaults
            | RepoConventions(
                source_dirs=(DirectoryName("Sources"), DirectoryName("src")),
                test_dirs=(DirectoryName("Tests"),),
                test_patterns=(FileGlob("Tests.swift"), FileGlob("*Tests.swift")),
                binary_dirs=(DirectoryName(".build"), DirectoryName("build")),
                workspace_files=(
                    FileName("Package.swift"),
                    FileGlob("*.xcodeproj"),
                    FileGlob("*.xcworkspace"),
                ),
                workspace_defined_in_file=True,
                workspace_definition_files=(
                    (FileName("Package.swift"), ("targets",)),  # SPM defines targets
                ),
            ),
            SemanticSearchLanguage.TYPESCRIPT: defaults
            | RepoConventions(
                source_dirs=(DirectoryName("src"), DirectoryName("lib")),
                test_dirs=(
                    DirectoryName("tests"),
                    DirectoryName("test"),
                    DirectoryName("__tests__"),
                ),
                test_patterns=(
                    FileGlob(".*.test.ts"),
                    FileGlob(".*.spec.ts"),
                    FileGlob("test/*"),
                    FileGlob("spec/*"),
                ),
                binary_dirs=(
                    DirectoryName("node_modules"),
                    DirectoryName("dist"),
                    DirectoryName("build"),
                ),
                private_package_dirs=(DirectoryName("node_modules"),),
                workspace_dirs=(DirectoryName("packages"), DirectoryName("apps")),
                workspace_files=(
                    FileName("package.json"),
                    FileName("lerna.json"),
                    FileName("pnpm-workspace.yaml"),
                    FileName("turbo.json"),
                    FileName("nx.json"),
                    FileName("tsconfig.json"),
                ),
                workspace_defined_in_file=True,
                workspace_definition_files=(
                    (FileName("package.json"), ("workspaces",)),
                    (FileName("lerna.json"), ("packages",)),
                    (FileName("pnpm-workspace.yaml"), ("packages",)),
                ),
            ),
            SemanticSearchLanguage.TSX: defaults
            | RepoConventions(
                source_dirs=(
                    DirectoryName("src"),
                    DirectoryName("lib"),
                    DirectoryName("components"),
                ),
                test_dirs=(
                    DirectoryName("tests"),
                    DirectoryName("test"),
                    DirectoryName("__tests__"),
                ),
                test_patterns=(
                    FileGlob(".*.test.tsx"),
                    FileGlob(".*.spec.tsx"),
                    FileGlob("test/*"),
                    FileGlob("spec/*"),
                ),
                binary_dirs=(
                    DirectoryName("node_modules"),
                    DirectoryName("dist"),
                    DirectoryName("build"),
                ),
                private_package_dirs=(DirectoryName("node_modules"),),
                workspace_dirs=(DirectoryName("packages"), DirectoryName("apps")),
                workspace_files=(
                    FileName("package.json"),
                    FileName("lerna.json"),
                    FileName("pnpm-workspace.yaml"),
                    FileName("turbo.json"),
                    FileName("nx.json"),
                ),
                workspace_defined_in_file=True,
                workspace_definition_files=(
                    (FileName("package.json"), ("workspaces",)),
                    (FileName("lerna.json"), ("packages",)),
                    (FileName("pnpm-workspace.yaml"), ("packages",)),
                ),
            ),
            SemanticSearchLanguage.YAML: defaults
            | RepoConventions(
                source_dirs=(
                    DirectoryName("config"),
                    DirectoryName("ci"),
                    DirectoryName(".github"),
                ),
                test_dirs=(),
                test_patterns=(),
                binary_dirs=(),
                ci_files=(
                    FileGlob(".github/workflows/*.yml"),
                    FileGlob(".github/workflows/*.yaml"),
                    FileGlob(".gitlab-ci.yml"),
                    FileGlob(".circleci/config.yml"),
                ),
            ),
        }.get(self, RepoConventions())


# Helper functions


@cache
def has_semantic_extension(ext: FileExtensionT) -> SemanticSearchLanguage | None:
    """Check if the given extension is a semantic search language."""
    return next(
        (lang for lang_ext, lang in SemanticSearchLanguage.ext_pairs() if lang_ext == ext), None
    )  # type: ignore


@cache
def is_semantic_config_ext(ext: str) -> bool:
    """Check if the given extension is a semantic config file."""
    ext = normalize_ext(ext)
    return any(ext == config_ext for config_ext in SemanticSearchLanguage.config_language_exts())


def find_config_paths() -> tuple[Path, ...] | None:
    """
    Finds all configuration files in the project root directory.

    Returns:
        A tuple of Path objects representing the configuration files, or None if no config files are found.
    """
    config_paths = tuple(p for p in SemanticSearchLanguage.all_config_paths() if p.exists())
    return config_paths or None


@cache
def language_from_config_file(config_file: Path) -> SemanticSearchLanguage | None:
    """
    Returns the SemanticSearchLanguage for a given configuration file path.

    Args:
        config_file: The path to the configuration file.

    Returns:
        The corresponding SemanticSearchLanguage, or None if not found.
    """
    return SemanticSearchLanguage._language_from_config_file(config_file)  # type: ignore  # we want people to use this function instead of the class method directly for caching


def languages_present_from_configs() -> tuple[SemanticSearchLanguage, ...] | None:
    """
    Returns a tuple of SemanticSearchLanguage for all languages present in the configuration files.

    Returns:
        A tuple of SemanticSearchLanguage objects.
    """
    # We get the Path for each config file that exists and then map it to the corresponding SemanticSearchLanguage.
    if (config_paths := find_config_paths()) and (
        associated_languages := [language_from_config_file(p) for p in config_paths]
    ):
        return tuple(lang for lang in associated_languages if lang)
    return None


def language_from_path(
    file_path: Path,
) -> SemanticSearchLanguage | ConfigLanguage | LanguageNameT | None:
    """
    Returns the SemanticSearchLanguage for a given file path based on its extension.

    Args:
        file_path: The path to the file.
    """
    ext = normalize_ext(file_path.suffix)
    lang = None
    with contextlib.suppress(ValueError, KeyError, AttributeError):
        if has_semantic_extension(ext):
            lang = SemanticSearchLanguage.lang_from_ext(ext)
    if lang:
        return lang
    with contextlib.suppress(ValueError, KeyError, AttributeError):
        if (
            FileExt(ext) in ConfigLanguage.all_extensions()
            or file_path.name in ConfigLanguage.all_extensions()
        ):
            lang = ConfigLanguage.from_extension(ext)
    if lang:
        return lang
    from codeweaver.core.file_extensions import (
        CODE_FILES_EXTENSIONS,
        DATA_FILES_EXTENSIONS,
        DOC_FILES_EXTENSIONS,
    )

    all_languages = CODE_FILES_EXTENSIONS + DATA_FILES_EXTENSIONS + DOC_FILES_EXTENSIONS
    # Check if the extension or filename matches any known language extensions
    if (
        (all_exts := tuple(ext_pair.ext for ext_pair in all_languages)) and FileExt(ext) in all_exts  # type: ignore
    ) or FileExt(file_path.name) in all_exts:  # type: ignore
        return next(
            (
                ext_pair.language  # type: ignore
                for ext_pair in all_languages  # type: ignore
                if ext_pair.ext in [FileExt(ext), FileExt(file_path.name)]  # type: ignore
            ),  # type: ignore
            None,
        )
    return None


__all__ = (
    "ConfigLanguage",
    "ConfigNamePair",
    "ConfigPathPair",
    "LanguageConfigFile",
    "SemanticSearchLanguage",
    "find_config_paths",
    "has_semantic_extension",
    "is_semantic_config_ext",
    "language_from_config_file",
    "languages_present_from_configs",
)
