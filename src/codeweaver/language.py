# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Classes and functions for handling languages and their configuration files in the CodeWeaver project."""

from __future__ import annotations

import os

from collections.abc import Generator
from functools import cache
from pathlib import Path
from types import MappingProxyType
from typing import NamedTuple

from codeweaver._common import BaseEnum
from codeweaver._utils import walk_down_to_git_root


PROJECT_ROOT = walk_down_to_git_root(Path.cwd()) or Path.cwd().resolve()

ConfigPathPair = NamedTuple(
    "ConfigPathPair", (("path", Path), ("language", "SemanticSearchLanguage"))
)

ConfigNamePair = NamedTuple(
    "ConfigNamePair", (("filename", str), ("language", "SemanticSearchLanguage | ConfigLanguage"))
)

ExtPair = NamedTuple("ExtPair", (("extension", str), ("language", "SemanticSearchLanguage")))


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
            ConfigLanguage.JSON: (".json",),
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


class SemanticSearchLanguage(BaseEnum):
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

    @classmethod
    def extension_map(cls) -> MappingProxyType[SemanticSearchLanguage, tuple[str, ...]]:
        """
        Returns a mapping of file extensions to their corresponding SemanticSearchLanguage.
        This is used to quickly look up the language based on file extension.
        """
        return MappingProxyType({
            cls.BASH: (
                ".sh",
                ".bash",
                ".zsh",
                ".bashrc",
                ".bash_profile",
                ".zshrc",
                ".profile",
                ".ksh",
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
            cls.JSON: (".json",),
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
    def all_extensions(cls) -> Generator[str]:
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
    def ext_pairs(cls) -> Generator[ExtPair]:
        """
        Returns a frozenset of tuples containing file extensions and their corresponding SemanticSearchLanguage.
        """
        for lang, exts in cls.extension_map().items():
            yield from (ExtPair(extension=ext, language=lang) for ext in exts if ext)

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
