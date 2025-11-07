# sourcery skip: no-complex-if-expressions
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Defines metadata types and enums for code chunks in CodeWeaver."""

from __future__ import annotations

import contextlib
import re

from collections.abc import Callable, Generator
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    Literal,
    NamedTuple,
    NotRequired,
    Required,
    Self,
    TypedDict,
    cast,
)

from ast_grep_py import SgNode
from pydantic import UUID7, ConfigDict, Field, PositiveFloat, SkipValidation

from codeweaver.common.utils import uuid7
from codeweaver.core.language import ConfigLanguage, SemanticSearchLanguage, has_semantic_extension
from codeweaver.core.types.aliases import (
    FileExt,
    FileExtensionT,
    LanguageName,
    LanguageNameT,
    LiteralStringT,
)
from codeweaver.core.types.enum import BaseEnum
from codeweaver.core.types.models import FROZEN_BASEDMODEL_CONFIG, BasedModel


if TYPE_CHECKING:
    from codeweaver.semantic.ast_grep import AstThing


# ------------------------------------------------
# *          Metadata Types and Enums          *
# ------------------------------------------------


class ChunkKind(BaseEnum):
    """Represents the kind of a code chunk."""

    CODE = "code"
    CONFIG = "config"
    CODE_OR_CONFIG = "code_or_config"
    """The Chunk is either code or a config, but requires further analysis to determine which. This happens in a narrow set of cases where the file belongs to a language that is used in configs and code, usually for itself, primarily this is for Kotlin and Groovy."""
    DATA = "data"
    DOCS = "docs"
    OTHER = "other"

    @classmethod
    def from_path(cls, path: Path, *, include_data: bool = False) -> ChunkKind | None:
        """Create a ChunkKind from a file path."""
        from codeweaver.core.metadata import get_ext_lang_pair_for_file

        if ext_lang_pair := get_ext_lang_pair_for_file(path, include_data=include_data):
            return cls.from_string(ext_lang_pair.category)
        return None


class ChunkSource(BaseEnum):
    """Represents the type of a code chunk -- basically how it was extracted."""

    TEXT_BLOCK = "text_block"
    FILE = "file"  # the whole file is the chunk
    SEMANTIC = "semantic"  # semantic chunking, e.g. from AST nodes
    EXTERNAL = "external"  # from internet or similar external sources, not from code files


def _set_symbol(data: Any) -> str | None:
    """Helper function to set the symbol field based on the primary_thing."""
    from codeweaver.semantic.ast_grep import AstThing

    if thing := data.get("thing"):
        if isinstance(thing, AstThing) and thing.symbol and (0 < len(thing.symbol.strip()) < 20):
            return thing.symbol
    return None


class SemanticMetadata(BasedModel):
    """Metadata associated with the semantics of a code chunk."""

    model_config = FROZEN_BASEDMODEL_CONFIG | ConfigDict(
        validate_assignment=True, arbitrary_types_allowed=True
    )

    language: Annotated[
        SemanticSearchLanguage | str,
        Field(description="""The programming language of the code chunk"""),
    ]
    thing: Any = None  # AstThing[SgNode] | None - using Any to avoid forward reference issues
    positional_connections: Any = ()  # tuple[AstThing[SgNode], ...] - using Any to avoid forward reference issues
    # TODO: Logic for symbol extraction from AST nodes
    symbol: Annotated[
        str | None,
        Field(description="""The symbol represented by the node""", default_factory=_set_symbol),
    ]
    thing_id: UUID7 = uuid7()
    parent_thing_id: UUID7 | None = None
    is_partial_node: Annotated[
        bool,
        Field(
            description="""Whether the node is a partial node. Partial nodes are created when the node is too large for the context window."""
        ),
    ] = False

    def _telemetry_keys(self) -> None:
        return None  # we'll exclude identifying info in the value types

    def __getstate__(self) -> dict[str, Any]:
        """Custom pickle support - exclude unpicklable AST nodes."""
        state = self.__dict__.copy()
        # Remove unpicklable fields (SgNode and AstThing objects)
        state["thing"] = None
        state["positional_connections"] = ()  # Clear AST node references
        return state

    def __setstate__(self, state: dict[str, Any]) -> None:
        """Custom pickle support - restore state without AST nodes."""
        self.__dict__.update(state)

    def _serialize_for_cli(self) -> dict[str, Any]:
        """Serialize the SemanticMetadata for CLI output."""
        self_map = self.model_dump(
            mode="python",
            round_trip=True,
            exclude_none=True,
            # we can exclude language because the parent classes will include it
            exclude={"model_config", "thing_id", "parent_thing_id", "language"},
        )
        return {
            k: v.serialize_for_cli() if hasattr(v, "serialize_for_cli") else v
            for k, v in self_map.items()
        }

    @classmethod
    def from_parent_meta(
        cls, child: AstThing[SgNode], parent_meta: SemanticMetadata, **overrides: Any
    ) -> Self:
        """Create a SemanticMetadata instance from a parent SemanticMetadata instance."""
        return cls(
            language=parent_meta.language,
            thing=child,
            positional_connections=tuple(child.positional_connections),
            thing_id=child.thing_id or uuid7(),
            parent_thing_id=parent_meta.thing_id,
            **overrides,
        )

    @classmethod
    def from_node(cls, thing: AstThing[SgNode] | SgNode, language: SemanticSearchLanguage) -> Self:
        """Create a SemanticMetadata instance from an AST node."""
        from codeweaver.semantic.ast_grep import AstThing

        if isinstance(thing, SgNode):
            thing = AstThing.from_sg_node(thing, language=language)
        # Use model_construct to bypass validation since AstThing may not be fully defined yet
        return cls.model_construct(
            language=language or thing.language or "",
            thing=thing,
            positional_connections=tuple(thing.positional_connections),
            thing_id=thing.thing_id,
            symbol=thing.symbol,
            parent_thing_id=thing.parent_thing_id,
            is_partial_node=False,  # if we're creating from a full node, it's not partial
        )


class Metadata(TypedDict, total=False):
    """Metadata associated with a code chunk."""

    chunk_id: Required[
        Annotated[UUID7, Field(description="""Unique identifier for the code chunk""")]
    ]
    created_at: Required[
        Annotated[PositiveFloat, Field(description="""Timestamp when the chunk was created""")]
    ]
    name: NotRequired[
        Annotated[str | None, Field(description="""Name of the code chunk, if applicable""")]
    ]
    kind: NotRequired[
        Annotated[
            Any | None,
            Field(
                description="""Optional kind/type classification of the chunk (e.g., DelimiterKind for delimiter chunks)"""
            ),
        ]
    ]
    nesting_level: NotRequired[
        Annotated[
            int | None, Field(description="""Nesting level for delimiter chunks (0 = top level)""")
        ]
    ]
    priority: NotRequired[
        Annotated[int | None, Field(description="""Priority value for delimiter chunks""")]
    ]
    line_start: NotRequired[
        Annotated[int | None, Field(description="""Starting line number for the chunk""")]
    ]
    line_end: NotRequired[
        Annotated[int | None, Field(description="""Ending line number for the chunk""")]
    ]
    fallback_to_generic: NotRequired[
        Annotated[bool | None, Field(description="""Whether generic/fallback chunking was used""")]
    ]
    updated_at: NotRequired[
        Annotated[
            PositiveFloat | None,
            Field(
                description="""Timestamp when the chunk was last updated or checked for accuracy."""
            ),
        ]
    ]
    tags: NotRequired[
        Annotated[
            tuple[str, ...] | None,
            Field(description="""Tags associated with the code chunk, if applicable"""),
        ]
    ]
    semantic_meta: NotRequired[
        SkipValidation[SemanticMetadata | None]  # type: ignore[valid-type]
    ]
    context: Annotated[
        dict[str, Any] | None,
        Field(
            default_factory=dict,
            description="""Optional context for evaluating the chunk's origin, transformation, etc. You can really put anything here.""",
        ),
    ]


class ExtTestDef(NamedTuple):
    """A NamedTuple defining a file extension test. Consists of the extension, the language if the test passes, and the test -- a callable that takes the file content and returns a bool."""

    extension: FileExtensionT
    language: LanguageNameT
    test: Callable[[str], bool]
    """A callable that takes the file content and returns a bool."""

    def test_ext(self, extension: FileExtensionT, content: str) -> bool:
        """Run the test callable with the given extension and content."""
        return False if extension != self.extension else self.test(content)


BASH_SHEBANG = re.compile(
    r"^#!(/usr|/usr/local)?/bin/(ba|fi|da|k|z|c|tc)?sh|^#!/usr/bin/env ((/bin/|/usr/bin/|/usr/local/bin)?(ba|da|fi|k|z|c|tc)?sh).*",
    re.IGNORECASE | re.DOTALL,
)
PYTHON_SHEBANG = re.compile(
    r"^(#(/usr/bin/env (-S )?(/usr/bin/|/usr/local/bin/)?(python3?|uv (-s)?).*))",
    re.IGNORECASE | re.DOTALL,
)
PERL_SHEBANG = re.compile(
    r"^(#(/usr/bin/env (-S )?(/usr/bin/|/usr/local/bin/)?(perl).*))", re.IGNORECASE | re.DOTALL
)


EXTENSION_TESTS: tuple[ExtTestDef, ...] = (
    ExtTestDef(
        extension=FileExt(".v"),
        language=LanguageName(cast(LiteralStringT, "coq")),
        test=lambda content: any(kw in content for kw in ("Proof", "Qed", "Defined", "Admitted")),  # type: ignore # give me a way to type a lambda...
    ),
    ExtTestDef(
        extension=FileExt(".v"),
        language=LanguageName(cast(LiteralStringT, "verilog")),
        test=lambda content: any(  # type: ignore
            kw in content for kw in ("module", "endmodule", "assign", "wire", "reg")
        ),
    ),
    ExtTestDef(
        extension=FileExt(".m"),
        language=LanguageName(cast(LiteralStringT, "matlab")),
        test=lambda content: any(  # type: ignore
            kw in content for kw in ("function", "end", "parfor", "switch")
        ),
    ),
    ExtTestDef(
        extension=FileExt(".m"),
        language=LanguageName(cast(LiteralStringT, "objective-c")),
        test=lambda content: all(  # type: ignore
            kw not in content for kw in ("switch", "end", "parfor", "function")
        ),
    ),
    ExtTestDef(
        extension=FileExt(""),
        language=LanguageName(cast(LiteralStringT, "bash")),
        test=lambda content: bool(BASH_SHEBANG.match(content)),  # type: ignore
    ),
    ExtTestDef(
        extension=FileExt(""),
        language=LanguageName(cast(LiteralStringT, "python")),
        test=lambda content: bool(PYTHON_SHEBANG.match(content)),  # type: ignore
    ),
    ExtTestDef(
        extension=FileExt(""),
        language=LanguageName(cast(LiteralStringT, "perl")),
        test=lambda content: bool(PERL_SHEBANG.match(content)),  # type: ignore
    ),
)


class ExtLangPair(NamedTuple):
    """
    Mapping of file extensions to their corresponding programming languages.

    Not all 'extensions' are actually file extensions, some are file names or special cases, like `Makefile` or `Dockerfile`.
    """

    ext: FileExtensionT
    """The file extension, including leading dot if it's a file extension. May also be a full file name."""

    language: LanguageNameT | SemanticSearchLanguage | ConfigLanguage
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
        from codeweaver.core.file_extensions import CONFIG_FILE_LANGUAGES

        return self.language in CONFIG_FILE_LANGUAGES or isinstance(self.language, ConfigLanguage)

    @property
    def is_doc(self) -> bool:
        """Check if the extension is a documentation file."""
        from codeweaver.core.file_extensions import DOC_FILES_EXTENSIONS

        return next((True for doc_ext in DOC_FILES_EXTENSIONS if doc_ext.ext == self.ext), False)

    @property
    def is_code(self) -> bool:
        """Check if the extension is a code file."""
        return not self.is_config and not self.is_doc and not self.is_file_name

    @property
    def is_data(self) -> bool:
        """Check if the extension is a data file."""
        from codeweaver.core.file_extensions import DATA_FILES_EXTENSIONS

        return next((True for data_ext in DATA_FILES_EXTENSIONS if data_ext.ext == self.ext), False)

    @property
    def as_source(self) -> ChunkSource:
        """Return the chunk source based on the extension type."""
        if isinstance(self.language, SemanticSearchLanguage) or (
            isinstance(self.language, ConfigLanguage) and self.language.is_semantic_search_language
        ):
            return ChunkSource.SEMANTIC
        return ChunkSource.FILE

    @property
    def category(self) -> Literal["code", "docs", "config", "data"]:
        """Return the language of file based on its extension."""
        if self.is_code:
            return "code"
        if self.is_doc:
            return "docs"
        if self.is_config:
            return "config"
        if self.is_data:
            return "data"
        raise ValueError(f"Unknown category for extension: {self.ext}")

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


def determine_ext_kind(validated_data: dict[str, Any]) -> ExtKind | None:
    """Determine the ExtKind based on validated data (`Metadata` extraction)."""
    if "file_path" in validated_data and validated_data["file_path"] is not None:
        return ExtKind.from_file(validated_data["file_path"])
    source = (
        validated_data.get("source")
        or validated_data.get("metadata", {}).get("source")
        or ChunkSource.TEXT_BLOCK
    )
    meta = validated_data.get("metadata", validated_data.get("semantic_meta", {}))
    if "semantic_meta" in meta:
        meta = meta["semantic_meta"]
    if not meta:
        return None
    if (language := meta.get("language") or validated_data.get("language")) and isinstance(
        language, SemanticSearchLanguage
    ):
        if language == SemanticSearchLanguage.KOTLIN:
            return ExtKind.from_language(language, ChunkKind.CODE_OR_CONFIG)
        return (
            ExtKind.from_language(language, ChunkKind.CODE)
            if language
            not in (
                SemanticSearchLanguage.JSON,
                SemanticSearchLanguage.YAML,
                SemanticSearchLanguage.HCL,
            )
            else ExtKind.from_language(language, ChunkKind.CONFIG)
        )

    if language and isinstance(language, ConfigLanguage):
        return ExtKind.from_language(
            language.as_semantic_search_language or language, ChunkKind.CONFIG
        )
    from codeweaver.core.file_extensions import CODE_LANGUAGES, DATA_LANGUAGES, DOCS_LANGUAGES

    if language and language in {pair.language for pair in DATA_LANGUAGES}:  # type: ignore
        return ExtKind.from_language(language, ChunkKind.DATA)
    if language and language in {pair.language for pair in DOCS_LANGUAGES}:  # type: ignore
        return ExtKind.from_language(language, ChunkKind.DOCS)
    if language and language in {pair.language for pair in CODE_LANGUAGES}:  # type: ignore
        return ExtKind.from_language(language, ChunkKind.CODE)
    return ExtKind.from_language(language, ChunkKind.OTHER) if language else None


def get_ext_lang_pairs(*, include_data: bool = False) -> Generator[ExtLangPair]:
    """Yield all `ExtLangPair` instances for code, config, and docs files."""
    from codeweaver.core.file_extensions import (
        CODE_FILES_EXTENSIONS,
        DATA_FILES_EXTENSIONS,
        DOC_FILES_EXTENSIONS,
    )

    if include_data:
        yield from (*CODE_FILES_EXTENSIONS, *DATA_FILES_EXTENSIONS, *DOC_FILES_EXTENSIONS)
    else:
        yield from (*CODE_FILES_EXTENSIONS, *DOC_FILES_EXTENSIONS)


def get_semantic_or_config_lang(
    test_info: Path | LanguageNameT,
) -> SemanticSearchLanguage | ConfigLanguage | None:
    """Get the `SemanticSearchLanguage` or `ConfigLanguage` for a given file path."""
    is_file = isinstance(test_info, Path)
    file_path = test_info if is_file else None
    language_name = test_info if test_info and not is_file else None
    if language_name is not None:
        with contextlib.suppress(KeyError, ValueError, AttributeError):
            if semantic_lang := SemanticSearchLanguage.from_string(str(language_name)):
                return semantic_lang
            if config_lang := ConfigLanguage.from_string(str(language_name)):
                return config_lang
        return None
    if file_path:
        with contextlib.suppress(KeyError, ValueError, AttributeError):
            if semantic_lang := SemanticSearchLanguage.from_extension(
                FileExt(cast(LiteralStringT, file_path.suffix or file_path.name))
            ):
                if semantic_lang.config_files and next(
                    (cfg for cfg in semantic_lang.config_files if cfg.path.name == file_path.name),
                    None,
                ):
                    return ConfigLanguage.from_string(str(language_name))
                return semantic_lang
            if config_lang := ConfigLanguage.from_extension(
                str(file_path.suffix or file_path.name)
            ):
                return config_lang
    return None


def get_ext_lang_pair_for_file(
    file_path: Path, *, include_data: bool = False
) -> ExtLangPair | None:
    """Get the `ExtLangPair` for a given file path."""
    if in_tests := ExtKind.resolve_extension_tests(file_path):
        return ExtLangPair(
            ext=FileExt(cast(LiteralStringT, file_path.suffix or file_path.name)),
            language=get_semantic_or_config_lang(in_tests.language) or in_tests.language,  # type: ignore
        )
    if config_lang := ConfigLanguage.from_extension(file_path.suffix or file_path.name):
        return ExtLangPair(
            ext=FileExt(cast(LiteralStringT, file_path.suffix or file_path.name)),
            language=config_lang,
        )
    if other_lang := next(
        (
            pair
            for pair in get_ext_lang_pairs(include_data=include_data)
            if pair.is_same(file_path.name)
        ),
        None,
    ):
        return other_lang
    return None


def get_language_from_extension(
    extension: FileExt | LiteralStringT,
    *,
    path: Path | None = None,
    hook: Callable[[FileExt, Path | None], LanguageNameT | None] | None = None,
) -> LanguageNameT | SemanticSearchLanguage | ConfigLanguage | None:
    """Get the language associated with a given file extension."""
    extension = FileExt(extension)
    if semantic_ext := has_semantic_extension(extension):
        return semantic_ext
    if config_lang := next(
        lang for lang in ConfigLanguage if lang.extensions and extension in lang.extensions
    ):
        return config_lang
    return next(
        (pair.language for pair in get_ext_lang_pairs() if pair and pair.ext == extension),
        hook(extension, path) if hook else None,
    )


def _categorize_language(
    language: LanguageNameT | SemanticSearchLanguage | ConfigLanguage,
) -> ChunkKind:
    """Categorize a language into its corresponding ChunkKind."""
    from codeweaver.core.file_extensions import (
        CODE_LANGUAGES,
        CONFIG_FILE_LANGUAGES,
        DOCS_LANGUAGES,
    )

    if language in CONFIG_FILE_LANGUAGES or isinstance(language, ConfigLanguage):
        return ChunkKind.CONFIG
    if language in CODE_LANGUAGES:
        return ChunkKind.CODE
    return ChunkKind.DOCS if language in DOCS_LANGUAGES else ChunkKind.OTHER


class ExtKind(NamedTuple):
    """Represents a file extension and its associated kind."""

    language: LanguageName | SemanticSearchLanguage | ConfigLanguage
    kind: ChunkKind

    def __str__(self) -> str:
        """Return a string representation of the extension kind."""
        return f"{self.kind}: {self.language}"

    @classmethod
    def from_language(
        cls,
        language: LanguageName | LiteralStringT | SemanticSearchLanguage | ConfigLanguage,
        kind: str | ChunkKind,
    ) -> ExtKind | None:
        """Create an ExtKind from a string representation."""
        # Handle SemanticSearchLanguage directly
        if isinstance(language, SemanticSearchLanguage):
            if isinstance(kind, ChunkKind):
                return cls(language=language, kind=kind)
            return cls(
                language=language,
                kind=ChunkKind.CONFIG if language.is_config_language else ChunkKind.CODE,
            )

        # Handle ConfigLanguage with special cases
        if isinstance(language, ConfigLanguage):
            special_config_langs = (ConfigLanguage.BASH, ConfigLanguage.SELF, ConfigLanguage.KOTLIN)
            target_kind = (
                ChunkKind.CODE_OR_CONFIG if language in special_config_langs else ChunkKind.CONFIG
            )
            return cls(language=language.as_semantic_search_language or language, kind=target_kind)

        # Try to convert string to SemanticSearchLanguage
        with contextlib.suppress(KeyError, ValueError, AttributeError):
            if semantic := SemanticSearchLanguage.from_string(language):
                return cls.from_language(semantic, kind)

        # Resolve as LanguageName and categorize
        lang_name = LanguageName(language)
        resolved_kind = kind if isinstance(kind, ChunkKind) else ChunkKind.from_string(kind)

        if resolved_kind:
            categorized_kind = _categorize_language(lang_name)
            return cls(language=lang_name, kind=categorized_kind)

        return cls(language=lang_name, kind=ChunkKind.OTHER)

    @classmethod
    def resolve_extension_tests(cls, file: str | Path) -> ExtKind | None:
        """
        Resolve the extension tests for a given file path.
        """
        file = Path(file) if isinstance(file, str) else file
        ext = FileExt(cast(LiteralStringT, file.suffix or file.name))
        return next(
            (
                cls.from_language(
                    ext_test.language,
                    (
                        ChunkKind.CODE
                        if ext_test.language not in (LanguageName("bash"), LanguageName("matlab"))
                        else ChunkKind.OTHER
                    ),
                )
                for ext_test in EXTENSION_TESTS
                if ext_test.test_ext(ext, file.read_text(errors="ignore"))
            ),
            None,
        )

    @classmethod
    def from_file(cls, file: str | Path) -> ExtKind | None:
        """
        Create an ExtKind from a file path.
        """
        from codeweaver.core.language import language_from_path

        file = Path(file) if isinstance(file, str) else file
        filename = file.name
        # The order we do this in is important:
        if semantic_config_file := next(
            (
                config
                for config in iter(SemanticSearchLanguage.filename_pairs())
                if config.filename == filename
            ),
            None,
        ):
            return cls(language=semantic_config_file.language, kind=ChunkKind.CONFIG)

        if language := language_from_path(file):
            if isinstance(language, ConfigLanguage):
                return cls(
                    language=language.as_semantic_search_language or language, kind=ChunkKind.CONFIG
                )
            if not isinstance(language, SemanticSearchLanguage):
                return cls(language=language, kind=_categorize_language(language))
            return cls(language=language, kind=ChunkKind.CODE)
        return None

    def serialize_for_cli(self) -> dict[str, Any]:
        """Serialize the ExtKind for CLI output."""
        return {
            "language": str(
                self.language.as_title
                if isinstance(self.language, SemanticSearchLanguage)
                else self.language
            ),
            "kind": str(self.kind.as_title),
        }


__all__ = (
    "ChunkKind",
    "ChunkSource",
    "ExtKind",
    "Metadata",
    "SemanticMetadata",
    "determine_ext_kind",
    "get_ext_lang_pair_for_file",
    "get_language_from_extension",
)
