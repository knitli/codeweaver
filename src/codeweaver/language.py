# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# sourcery skip: docstrings-for-functions
"""Classes and functions for handling languages and their configuration files in the CodeWeaver project."""

from __future__ import annotations

import os

from collections.abc import Generator, Iterable
from functools import cache
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Annotated, Any, NamedTuple, cast, overload

from langchain_text_splitters import Language as LC_Language
from pydantic import Field

from codeweaver._common import BasedModel, BaseEnum, LiteralStringT
from codeweaver._constants import ALL_LANGUAGES, ExtLangPair, get_ext_lang_pairs
from codeweaver._supported_languages import SecondarySupportedLanguage
from codeweaver._utils import get_project_root


if TYPE_CHECKING:
    from codeweaver.settings_types import CustomDelimiter


PROJECT_ROOT = get_project_root() or Path.cwd().resolve()

ConfigPathPair = NamedTuple(
    "ConfigPathPair", (("path", Path), ("language", "SemanticSearchLanguage"))
)
"""A tuple representing a configuration file path and its associated language, like `(Path("pyproject.toml"), SemanticSearchLanguage.PYTHON)` or `(Path("CMakeLists.txt"), ConfigLanguage.CMAKE)`."""

ConfigNamePair = NamedTuple(
    "ConfigNamePair",
    (("filename", LiteralStringT), ("language", "SemanticSearchLanguage | ConfigLanguage")),
)
"""A tuple representing a configuration file name and its associated language, like `("pyproject.toml", SemanticSearchLanguage.PYTHON)` or `("CMakeLists.txt", ConfigLanguage.CMAKE)`."""

ExtPair = NamedTuple(
    "ExtPair", (("extension", LiteralStringT), ("language", "SemanticSearchLanguage"))
)
"""Nearly identical to `ExtLangPair` in `codeweaver._constants` and `ConfigNamePair`, but here we use `SemanticSearchLanguage` instead of `LiteralStringT` or `ConfigLanguage`for the language type."""


class ExtensionRegistry(BasedModel):
    """
    A registry for custom file extensions and their associated languages.
    """

    _registry: Annotated[
        dict[
            LiteralStringT,
            SemanticSearchLanguage | SecondarySupportedLanguage | ConfigLanguage | LiteralStringT,
        ],
        Field(
            default_factory=dict,
            description="""A mapping of file extensions to their associated languages.""",
        ),
    ]

    def __init__(self, *, include_data: bool = False, **kwargs: Any) -> None:
        """
        Initializes the ExtensionRegistry.

        Args:
            include_data: If False (default), omits extensions associated with data files (e.g., .csv, .db, .xlsx) from the registry. This will not exclude documentation and config files (e.g., .md, .json, .yaml). If True, includes all extensions.
            **kwargs: Additional keyword arguments for the BasedModel.
        """
        super().__init__(**kwargs)
        extpairs = get_ext_lang_pairs(include_data=include_data)
        languages = {pair.language for pair in extpairs}
        for lang in languages:
            exts = tuple(pair.ext for pair in extpairs if pair.language == lang)
            self._add_exts_to_registry(
                cast(Iterable[LiteralStringT], exts), cast(SecondarySupportedLanguage, lang)
            )
        for lang in ConfigLanguage:
            if lang.extensions:
                self._add_exts_to_registry(cast(Iterable[LiteralStringT], lang.extensions), lang)
        for lang in SemanticSearchLanguage:
            if lang.extensions:
                self._add_exts_to_registry(cast(Iterable[LiteralStringT], lang.extensions), lang)

    def lookup(
        self, ext: LiteralStringT
    ) -> (
        SemanticSearchLanguage | SecondarySupportedLanguage | ConfigLanguage | LiteralStringT | None
    ):
        """
        Looks up the language associated with a given file extension.

        Args:
            ext: The file extension to look up.

        Returns:
            The associated language, or None if not found.
        """
        return self._registry.get(ext, None)

    def _add_exts_to_registry(
        self,
        exts: Iterable[LiteralStringT] | None,
        language: SemanticSearchLanguage
        | SecondarySupportedLanguage
        | ConfigLanguage
        | LiteralStringT,
    ) -> None:
        """Adds file extensions to the registry."""
        if not exts:
            return
        for ext in exts:
            if ext in self._registry:
                continue
            self._registry[ext] = language

    @overload
    def register(
        self, *, ext_tuple: ExtLangPair | ExtPair | ConfigNamePair | ConfigPathPair
    ) -> None: ...
    @overload
    def register(
        self,
        *,
        extension: LiteralStringT,
        language: SemanticSearchLanguage
        | ConfigLanguage
        | SecondarySupportedLanguage
        | LiteralStringT,
    ) -> None: ...
    def register(
        self,
        *,
        ext_tuple: ExtLangPair | ExtPair | ConfigNamePair | ConfigPathPair | None = None,
        extension: LiteralStringT | None = None,
        language: SemanticSearchLanguage
        | ConfigLanguage
        | SecondarySupportedLanguage
        | LiteralStringT
        | None = None,
    ) -> None:
        """
        Registers a new file extension and its associated language.

        Args:
            ext_tuple: A tuple containing the file extension and its associated language.
            extension: The file extension to register.
            language: The language associated with the file extension.
        """
        if ext_tuple is not None:
            match ext_tuple:
                case ConfigPathPair():
                    exts = (*(ext_tuple.language.extensions or ()), ext_tuple.path.name)
                    self._add_exts_to_registry(exts, ext_tuple.language)  # type: ignore
                case ConfigNamePair():
                    exts = ext_tuple.language.extensions
                    self._add_exts_to_registry(
                        cast(tuple[LiteralStringT, ...], (*(exts or ()), ext_tuple.filename)),
                        ext_tuple.language,
                    )  # type: ignore
                case ExtPair() | ExtLangPair():
                    self._add_exts_to_registry(
                        (
                            ext_tuple.ext
                            if isinstance(ext_tuple, ExtLangPair)
                            else ext_tuple.extension,
                        ),
                        ext_tuple.language,
                    )
        if extension is not None and language is not None:
            self._add_exts_to_registry((extension,), language)


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


class ConfigLanguage(BaseEnum):
    """
    Enum representing common configuration languages.
    """

    BASH = "bash"
    CMAKE = "cmake"
    INI = "ini"
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

    @property
    def extensions(self) -> tuple[str, ...]:
        """
        Returns the file extensions associated with this configuration language.

        The special value `SELF` indicates that the configuration file is written in the same language as the codebase (e.g., Kotlin, Scala).

        Note: We won't provide extensions that are not commonly used for configuration files, not all extensions associated with the language.
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
            ConfigLanguage.JSON: (".json", ".jsonc", ".json5"),
            ConfigLanguage.GROOVY: (".gradle", ".gradle.kts"),
            ConfigLanguage.KOTLIN: (".kts",),
            ConfigLanguage.MAKE: ("Makefile", "makefile", ".makefile", ".mak", ".make"),
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
            return SemanticSearchLanguage.from_string(self.value)  # pyright: ignore[reportReturnType]
        return None

    @classmethod
    def all_extensions(cls) -> Generator[str]:
        """
        Returns all file extensions for all configuration languages.
        """
        yield from (ext for lang in cls for ext in lang.extensions if ext and ext != "SELF")


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
    HTML = "html"
    JAVA = "java"
    JAVASCRIPT = "javascript"
    JSX = "jsx"
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
            SemanticSearchLanguage.JAVASCRIPT: "js",
            SemanticSearchLanguage.TYPESCRIPT: "ts",
            SemanticSearchLanguage.PYTHON: "py",
            SemanticSearchLanguage.PHP: "php_sparse",  # there are two tree-sitter grammars for PHP; we call one 'sparse' to differentiate it, but we need to handle 'php' as an alias for it
        }.get(self)

    @classmethod
    def extension_map(cls) -> MappingProxyType[SemanticSearchLanguage, tuple[str, ...]]:
        """
        Returns a mapping of file extensions to their corresponding SemanticSearchLanguage.
        This is used to quickly look up the language based on file extension.
        """
        return MappingProxyType({
            cls.BASH: (
                ".bash",
                ".bash_profile",
                ".bashrc",
                ".csh",
                ".cshrc",
                ".ksh",
                ".kshrc",
                ".profile",
                ".sh",
                ".tcsh",
                ".tcshrc",
                ".zprofile",
                ".zsh",
                ".zshrc",
            ),
            cls.C_LANG: (".c", ".h"),
            cls.C_PLUS_PLUS: (".cpp", ".hpp", ".cc", ".cxx"),
            cls.C_SHARP: (".cs", ".csharp"),
            cls.CSS: (".css",),
            cls.ELIXIR: (".ex", ".exs"),
            cls.GO: (".go",),
            cls.HASKELL: (".hs",),
            cls.HTML: (".html", ".htm", ".xhtml"),
            cls.JAVA: (".java",),
            cls.JAVASCRIPT: (".js", ".mjs", ".cjs"),
            cls.JSON: (".json", ".jsonc", ".json5"),
            cls.JSX: (".jsx",),
            cls.KOTLIN: (".kt", ".kts", ".ktm"),
            cls.LUA: (".lua",),
            cls.NIX: (".nix",),
            cls.PHP: (".php", ".phtml"),
            cls.PYTHON: (".py", ".pyi", ".py3", ".bzl"),
            cls.RUBY: (".rb", ".gemspec", ".rake", ".ru"),
            cls.RUST: (".rs",),
            cls.SCALA: (".scala", ".sc", ".sbt"),
            cls.SOLIDITY: (".sol",),
            cls.SWIFT: (".swift",),
            cls.TYPESCRIPT: (".ts", ".mts", ".cts"),
            cls.TSX: (".tsx",),
            cls.YAML: (".yaml", ".yml"),
        })

    @classmethod
    def from_extension(cls, ext: str) -> SemanticSearchLanguage | None:
        """
        Returns the SemanticSearchLanguage associated with the given file extension.
        """
        ext = ext.lower() if ext.startswith(".") else f".{ext.lower()}"
        return next(
            (language for language, extensions in cls.extension_map().items() if ext in extensions),
            None,
        )

    @property
    def extensions(self) -> tuple[str, ...] | None:
        """
        Returns the file extensions associated with this language.
        """
        return type(self).extension_map()[self]

    @property
    def config_files(self) -> tuple[LanguageConfigFile, ...] | None:  # noqa: C901  # it's long, but not complex
        """
        Returns the LanguageConfigFiles associated with this language.

        TODO: Validate the `dependency_key_paths` for each config file to ensure they are correct. If you use these languages, please let us know if you find any issues with the `dependency_key_paths` in the config files. Some are probably incorrect.
        # We haven't implemented dependency extraction yet, but when we do, we want to make sure these paths are correct.
        """
        match self:
            case SemanticSearchLanguage.C_LANG:
                return (
                    LanguageConfigFile(
                        language=self,
                        path=PROJECT_ROOT / "Makefile",
                        language_type=ConfigLanguage.MAKE,
                        dependency_key_paths=(("CFLAGS",), ("LDFLAGS",)),
                    ),
                )
            case SemanticSearchLanguage.C_PLUS_PLUS:
                return (
                    LanguageConfigFile(
                        language=self,
                        path=PROJECT_ROOT / "CMakeLists.txt",
                        language_type=ConfigLanguage.CMAKE,
                        dependency_key_paths=(("CMAKE_CXX_FLAGS",), ("CMAKE_EXE_LINKER_FLAGS",)),
                    ),
                    LanguageConfigFile(
                        language=self,
                        path=PROJECT_ROOT / "Makefile",
                        language_type=ConfigLanguage.MAKE,
                        dependency_key_paths=(("CXXFLAGS",), ("LDFLAGS",)),
                    ),
                )
            case SemanticSearchLanguage.C_SHARP:
                return (
                    LanguageConfigFile(
                        language=self,
                        path=PROJECT_ROOT / "app.config",
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
                        path=next(iter(PROJECT_ROOT.glob("*.csproj")), None),  # type: ignore
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
                        path=PROJECT_ROOT / "mix.exs",
                        language_type=ConfigLanguage.SELF,
                        dependency_key_paths=(("deps",), ("aliases", "deps")),
                    ),
                )
            case SemanticSearchLanguage.GO:
                return (
                    LanguageConfigFile(
                        language=self,
                        path=PROJECT_ROOT / "go.mod",
                        language_type=ConfigLanguage.INI,
                        dependency_key_paths=(("require",), ("replace",)),
                    ),
                )
            case SemanticSearchLanguage.HASKELL:
                return (
                    LanguageConfigFile(
                        language=self,
                        path=PROJECT_ROOT / "package.yaml",
                        language_type=ConfigLanguage.YAML,
                        dependency_key_paths=(("dependencies",), ("build-depends",)),
                    ),
                    LanguageConfigFile(
                        language=self,
                        path=Path(os.environ.get("STACK_YAML") or PROJECT_ROOT / "stack.yml"),
                        language_type=ConfigLanguage.YAML,
                        dependency_key_paths=(("extra-deps",),),
                    ),
                    LanguageConfigFile(
                        language=self,
                        path=next(iter(PROJECT_ROOT.glob("*.cabal"))),
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
                        path=PROJECT_ROOT / "pom.xml",
                        language_type=ConfigLanguage.XML,
                        dependency_key_paths=(
                            ("project", "dependencies", "dependency"),
                            ("project", "dependencyManagement", "dependencies", "dependency"),
                        ),
                    ),
                    LanguageConfigFile(
                        language=self,
                        path=PROJECT_ROOT / "build.gradle",
                        language_type=ConfigLanguage.GROOVY,
                        dependency_key_paths=(
                            ("dependencies",),
                            ("configurations", "compileClasspath", "dependencies"),
                            ("configurations", "runtimeClasspath", "dependencies"),
                        ),
                    ),
                    LanguageConfigFile(
                        language=self,
                        path=PROJECT_ROOT / "build.gradle.kts",
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
                        path=PROJECT_ROOT / "package.json",
                        language_type=ConfigLanguage.JSON,
                        dependency_key_paths=(("dependencies",),),
                    ),
                )
            case SemanticSearchLanguage.KOTLIN:
                return (
                    LanguageConfigFile(
                        language=self,
                        path=PROJECT_ROOT / "build.gradle.kts",
                        language_type=ConfigLanguage.SELF,
                        dependency_key_paths=(
                            ("dependencies",),
                            ("configurations", "compileClasspath", "dependencies"),
                            ("configurations", "runtimeClasspath", "dependencies"),
                        ),
                    ),
                    LanguageConfigFile(
                        language=self,
                        path=PROJECT_ROOT / "settings.gradle.kts",
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
                        path=PROJECT_ROOT / "luarocks.json",
                        language_type=ConfigLanguage.JSON,
                        dependency_key_paths=(("dependencies",), ("build_dependencies",)),
                    ),
                    LanguageConfigFile(
                        language=self,
                        path=PROJECT_ROOT / "rockspec.json",
                        language_type=ConfigLanguage.JSON,
                        dependency_key_paths=(("dependencies",), ("build_dependencies",)),
                    ),
                    LanguageConfigFile(
                        language=self,
                        path=PROJECT_ROOT / "rockspec",
                        language_type=ConfigLanguage.INI,
                        dependency_key_paths=(("dependencies",), ("build_dependencies",)),
                    ),
                )
            case SemanticSearchLanguage.NIX:
                return (
                    LanguageConfigFile(
                        language=self,
                        path=PROJECT_ROOT / "default.nix",
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
                        path=PROJECT_ROOT / "composer.json",
                        language_type=ConfigLanguage.JSON,
                        dependency_key_paths=(("require",),),
                    ),
                )
            case SemanticSearchLanguage.PYTHON:
                return (
                    LanguageConfigFile(
                        language=self,
                        path=PROJECT_ROOT / "pyproject.toml",
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
                        path=PROJECT_ROOT / "Gemfile",
                        language_type=ConfigLanguage.SELF,
                        dependency_key_paths=(
                            ("gems",),
                            ("source", "gems"),
                            ("source", "gemspec", "gems"),
                        ),
                    ),
                    LanguageConfigFile(
                        language=self,
                        path=PROJECT_ROOT / "Rakefile",
                        language_type=ConfigLanguage.SELF,
                        dependency_key_paths=(
                            ("gems",),
                            ("source", "gems"),
                            ("source", "gemspec", "gems"),
                        ),
                    ),
                    LanguageConfigFile(
                        language=self,
                        path=PROJECT_ROOT / "gemspec",
                        language_type=ConfigLanguage.SELF,
                        dependency_key_paths=(("dependencies",),),
                    ),
                    LanguageConfigFile(
                        language=self,
                        path=PROJECT_ROOT / "config.ru",
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
                        path=PROJECT_ROOT / "Cargo.toml",
                        language_type=ConfigLanguage.TOML,
                        dependency_key_paths=(("dependencies",),),
                    ),
                )
            case SemanticSearchLanguage.SCALA:
                return (
                    LanguageConfigFile(
                        language=self,
                        path=PROJECT_ROOT / "build.sbt",
                        language_type=ConfigLanguage.SELF,
                        dependency_key_paths=(
                            ("libraryDependencies",),
                            ("compile", "dependencies"),
                            ("runtime", "dependencies"),
                        ),
                    ),
                    LanguageConfigFile(
                        language=self,
                        path=PROJECT_ROOT / "project" / "build.properties",
                        language_type=ConfigLanguage.PROPERTIES,
                        dependency_key_paths=(("sbt.version",),),
                    ),
                )
            case SemanticSearchLanguage.SWIFT:
                return (
                    LanguageConfigFile(
                        language=self,
                        path=PROJECT_ROOT / "Package.swift",
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
            if isinstance(lang, cls) and lang.is_config_language and ext and ext != ".sh"
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
        )  # pyright: ignore[reportReturnType]

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
        yield from (ext for lang in cls for ext in cls.extension_map()[lang] if ext)  # pyright: ignore[reportReturnType]

    @classmethod
    def filename_pairs(cls) -> Generator[ConfigNamePair]:
        """
        Returns a frozenset of tuples containing file names and their corresponding SemanticSearchLanguage.
        """
        for lang in cls:
            if lang.config_files is not None:
                yield from (
                    ConfigNamePair(
                        filename=config_file.path.name,  # pyright: ignore[reportArgumentType]
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
    def ext_pairs(cls) -> Generator[ExtPair]:
        """
        Returns a frozenset of tuples containing file extensions and their corresponding SemanticSearchLanguage.
        """
        for lang, exts in cls.extension_map().items():
            yield from (
                ExtPair(extension=cast(LiteralStringT, ext), language=lang) for ext in exts if ext
            )

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
        normalized_path = PROJECT_ROOT / config_file.name
        if not normalized_path.exists() or all(
            str(normalized_path) not in str(p) for p in cls.all_config_paths()
        ):
            return None
        if config_file.name in ("Makefile", "build.gradle.kts"):
            # there's language ambiguity here. TODO: Add check to resolve this ambiguity
            # for now, we make an educated guess
            if config_file.name == "Makefile":
                # C++ is more popular... no other reasoning here
                return SemanticSearchLanguage.C_PLUS_PLUS
            # Java's more common than Kotlin, but Kotlin is more likely to use 'build.gradle.kts' ... I think. 🤷‍♂️
            return SemanticSearchLanguage.KOTLIN
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


# Helper functions


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

    TODO: Integrate into indexing and search services to use these languages.
    """
    # We get the Path for each config file that exists and then map it to the corresponding SemanticSearchLanguage.
    if (config_paths := find_config_paths()) and (
        associated_languages := [language_from_config_file(p) for p in config_paths]
    ):
        return tuple(lang for lang in associated_languages if lang)
    return None


codeweaver_to_langchain = {
    k.value: k.value for k in LC_Language if k.value not in ("js", "ts", "proto", "rst", "sol", "c")
} | {
    "javascript": "js",
    "typescript": "ts",
    "protobuf": "proto",
    "solidity": "sol",
    "c_lang": "c",
    "restructuredtext": "rst",
}


_custom_delimiters: list[CustomDelimiter] = []
"""A global list to hold custom delimiters registered by the user.

Note: We had previously used a set here but realized the order may be important if defining multiple CustomDelimiters for the same language. Users should provide them in priority order, and we want to respect that order when using them.
"""


class Chunker(int, BaseEnum):
    """Defines chunkers/parsers/splitters that CodeWeaver supports.

    An int enum, the members are in order of preference/robustness with the most general and least robust at lower numbers, and the richest at higher numbers. The final fallback (lowest value) is `langchain_text_splitters.RecursiveCharacterTextSplitter`. The richest/best is our own semantic chunker, which uses `ast_grep_py` (tree-sitter).
    """

    LANGCHAIN_RECURSIVE = 0
    """The final fallback chunker, `langchain_text_splitters.RecursiveCharacterTextSplitter`"""
    LANGCHAIN_SPECIAL = 1
    """A language-specific chunker provided by `langchain_text_splitters`, such as for markdown."""
    BUILTIN_DELIMITER = 2
    """CodeWeaver's delimiter-based text chunkers; delimiters are defined here."""
    USER_DELIMITER = 3
    """A user-defined delimiter, using our delimiter-based chunker. Defined in config files and registered at runtime."""
    SEMANTIC = 4
    """CodeWeaver's semantic chunker. The most robust chunker, using `ast_grep_py` (tree-sitter)."""

    def _chunkers(self) -> list[CustomDelimiter]:
        global _custom_delimiters
        return _custom_delimiters

    @staticmethod
    def _as_literal_tuple(values: Iterable[str]) -> tuple[LiteralStringT, ...]:
        """
        Internal helper to coerce an iterable of str into tuple[LiteralStringT, ...].

        We centralize the cast to keep callsites clean and ensure type checkers
        narrow the union branch for supported_languages correctly.
        """
        return cast(tuple[LiteralStringT, ...], tuple(values))

    @classmethod
    def _recursive_all_languages(cls) -> tuple[LiteralStringT, ...]:
        """
        Build the complete language set used by LANGCHAIN_RECURSIVE.

        Returns a homogeneous tuple[LiteralStringT, ...].

        Composition:
          - All SemanticSearchLanguage member values
          - ALL_LANGUAGES (code + data + docs)
          - Any custom delimiter languages (if registered)

        Deterministic ordering (sorted) improves cacheability & test stability.
        """
        languages: set[LiteralStringT] = set(ALL_LANGUAGES)
        languages.update(cast(LiteralStringT, lang.variable) for lang in SemanticSearchLanguage)
        languages.update(cast(LiteralStringT, lang.variable) for lang in ConfigLanguage)
        if custom := cls._custom_delimiter_languages():
            languages.update(custom)
        return cls._as_literal_tuple(sorted(languages))

    @property
    def supported_languages(
        self,
    ) -> (
        tuple[SemanticSearchLanguage, ...]
        | tuple[SecondarySupportedLanguage, ...]
        | tuple[LiteralStringT, ...]
        | tuple[SemanticSearchLanguage | SecondarySupportedLanguage, ...]
    ):
        """
        Returns a tuple of supported languages for the chunker.

        LANGCHAIN_RECURSIVE:
            Returns tuple[LiteralStringT, ...] built from semantic + secondary + custom.
        BUILTIN_DELIMITER, LANGCHAIN_SPECIAL, USER_DELIMITER:
            Return tuple[LiteralStringT, ...].
        SEMANTIC:
            Returns tuple[SemanticSearchLanguage, ...].
        """
        from codeweaver.services.chunker.delimiters.families import defined_languages

        if self is Chunker.LANGCHAIN_RECURSIVE:
            return type(self)._recursive_all_languages()
        if self is Chunker.BUILTIN_DELIMITER:
            return type(self)._as_literal_tuple(sorted(defined_languages()))
        if self is Chunker.LANGCHAIN_SPECIAL:
            return type(self)._as_literal_tuple(sorted(codeweaver_to_langchain.keys()))
        if self is Chunker.USER_DELIMITER:
            return type(self)._as_literal_tuple(sorted(type(self)._custom_delimiter_languages()))
        if self is Chunker.SEMANTIC:
            return tuple(SemanticSearchLanguage)
        raise AssertionError(f"Unhandled chunker: {self}")

    @classmethod
    def custom_delimiters(cls) -> list[CustomDelimiter]:
        """
        Returns a set of custom delimiters registered by the user.

        Returns:
            set: A set of CustomDelimiter instances.
        """
        global _custom_delimiters
        return _custom_delimiters

    @classmethod
    def _custom_delimiter_languages(cls) -> frozenset[LiteralStringT]:
        """
        Returns a frozenset of language names for which custom chunkers have been registered.

        Returns:
            frozenset: A frozenset of language names.
        """
        languages: set[LiteralStringT] = set()
        global _custom_delimiters
        for d in _custom_delimiters:
            if d.language:
                languages.add(d.language)
            if d.extensions:
                languages |= {ext.language for ext in d.extensions if ext.language}
        return frozenset(languages)

    @classmethod
    def register_custom_chunker(cls, chunker: CustomDelimiter) -> None:
        """
        Registers a custom chunker for a given language.

        Args:
            chunker (CustomDelimiter): The custom chunker to register.
        """
        global _custom_delimiters
        _custom_delimiters.append(chunker)

    @classmethod
    def no_special_chunker_languages(cls) -> frozenset[LiteralStringT]:
        """
        Returns a frozenset of languages that do not have a special chunker in LangChain, or defined in CodeWeaver.

        This includes languages that are not in the `codeweaver_to_langchain` mapping.

        Returns:
            frozenset: A frozenset of language names.
        """
        from codeweaver.services.chunker.delimiters.families import defined_languages

        known_languages = set(codeweaver_to_langchain.keys())
        known_languages.update(defined_languages())
        known_languages.update(cls._custom_delimiter_languages())
        known_languages.update(lang.variable for lang in ConfigLanguage)
        known_languages.update(lang.variable for lang in SemanticSearchLanguage)
        all_languages = set(ALL_LANGUAGES)
        return frozenset(all_languages - known_languages)  # pyright: ignore[reportOperatorIssue, reportUnknownArgumentType]

    def next_chunker(self, *, language: LiteralStringT | None = None) -> Chunker | None:
        """
        Returns the next chunker in the order of preference/robustness.

        Returns:
            Chunker | None: The next chunker, or None if this is the last chunker.
        """
        if language and language in ("markdown", "md", "latex"):
            # markdown and latex have special chunkers in langchain
            if self == Chunker.BUILTIN_DELIMITER:
                return None
            return (
                Chunker.LANGCHAIN_SPECIAL
                if self != Chunker.LANGCHAIN_SPECIAL
                else Chunker.BUILTIN_DELIMITER
            )
        return None if self == Chunker.LANGCHAIN_RECURSIVE else Chunker(self - 1)


__all__ = (
    "Chunker",
    "ConfigLanguage",
    "ConfigNamePair",
    "ConfigPathPair",
    "ExtPair",
    "LanguageConfigFile",
    "SemanticSearchLanguage",
    "find_config_paths",
    "language_from_config_file",
    "languages_present_from_configs",
)
