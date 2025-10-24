# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Defines metadata types and enums for code chunks in CodeWeaver."""

from __future__ import annotations

import contextlib

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
    overload,
)

from ast_grep_py import SgNode
from pydantic import UUID7, ConfigDict, Field, PositiveFloat

from codeweaver.common.utils import normalize_ext, uuid7
from codeweaver.core.language import (
    ConfigLanguage,
    SemanticSearchLanguage,
    has_semantic_extension,
    is_semantic_config_ext,
)
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
    DOCS = "docs"
    OTHER = "other"


class ChunkSource(BaseEnum):
    """Represents the type of a code chunk -- basically how it was extracted."""

    TEXT_BLOCK = "text_block"
    FILE = "file"  # the whole file is the chunk
    SEMANTIC = "semantic"  # semantic chunking, e.g. from AST nodes
    EXTERNAL = "external"  # from internet or similar external sources, not from code files


class SemanticMetadata(BasedModel):
    """Metadata associated with the semantics of a code chunk."""

    model_config = FROZEN_BASEDMODEL_CONFIG | ConfigDict(validate_assignment=True)

    language: Annotated[
        SemanticSearchLanguage | str,
        Field(description="""The programming language of the code chunk"""),
    ]
    thing: AstThing[SgNode] | None
    positional_connections: tuple[AstThing[SgNode], ...] = ()
    # TODO: Logic for symbol extraction from AST nodes
    symbol: Annotated[
        str | None,
        Field(
            description="""The symbol represented by the node""",
            default_factory=lambda data: data["primary_thing"].name
            if data.get("primary_thing")
            else None,
        ),
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
        if isinstance(thing, SgNode):
            thing = AstThing.from_sg_node(thing, language=language)  # pyright: ignore[reportUnknownVariableType]
        return cls(
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
        Annotated[
            SemanticMetadata | None,
            Field(
                description="""Semantic metadata associated with the code chunk, if applicable. Should be included if the code chunk was from semantic chunking."""
            ),
        ]
    ]
    context: Annotated[
        dict[str, Any] | None,
        Field(
            default_factory=dict,
            description="""Optional context for evaluating the chunk's origin, transformation, etc. You can really put anything here.""",
        ),
    ]


class ExtLangPair(NamedTuple):
    """
    Mapping of file extensions to their corresponding programming languages.

    Not all 'extensions' are actually file extensions, some are file names or special cases, like `Makefile` or `Dockerfile`.
    """

    ext: FileExtensionT
    """The file extension, including leading dot if it's a file extension. May also be a full file name."""

    language: LanguageNameT
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

        return self.language in CONFIG_FILE_LANGUAGES

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


def determine_ext_kind(validated_data: dict[str, Any]) -> ExtKind | None:
    """Determine the ExtKind based on the validated data."""
    if "file_path" in validated_data:
        return ExtKind.from_file(validated_data["file_path"])
    source = validated_data.get("source", ChunkSource.TEXT_BLOCK)
    if (
        source == ChunkSource.SEMANTIC
        and "metadata" in validated_data
        and "semantic_meta" in validated_data["metadata"]
        and (language := validated_data["metadata"]["semantic_meta"].get("language"))
    ):
        return ExtKind.from_language(language, "code")
    if "language" in validated_data and source != source.TEXT_BLOCK:
        if source == ChunkSource.EXTERNAL:
            return ExtKind.from_language(validated_data["language"], ChunkKind.OTHER)
        if source in (ChunkSource.FILE):
            return ExtKind.from_language(validated_data["language"], "docs")
        return ExtKind.from_language(validated_data["language"], "code")
    return None


def get_ext_lang_pairs(*, include_data: bool = False) -> Generator[ExtLangPair]:
    """Yield all `ExtLangPair` instances for code, config, and docs files."""
    from codeweaver.core.file_extensions import (
        CODE_FILES_EXTENSIONS,
        DATA_FILES_EXTENSIONS,
        DOC_FILES_EXTENSIONS,
    )

    if include_data:
        yield from (*CODE_FILES_EXTENSIONS, *DATA_FILES_EXTENSIONS, *DOC_FILES_EXTENSIONS)
    yield from (*CODE_FILES_EXTENSIONS, *DOC_FILES_EXTENSIONS)


@overload
def _handle_fallback(
    path: Path, *, pair: ExtLangPair, extension: None = None
) -> ExtLangPair | None: ...
@overload
def _handle_fallback(
    path: Path, *, pair: None = None, extension: FileExt
) -> ExtLangPair | None: ...
def _handle_fallback(
    path: Path, *, pair: ExtLangPair | None = None, extension: FileExt | None = None
) -> ExtLangPair | None:
    """Handle fallback for a given ExtLangPair and file path."""
    from codeweaver.core.file_extensions import FALLBACK_TEST

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
    from codeweaver.core.file_extensions import FALLBACK_TEST

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
    extension: FileExt | LiteralStringT,
    *,
    path: Path | None = None,
    hook: Callable[[FileExt, Path | None], LanguageName | None] | None = None,
) -> LanguageName | None:
    """Get the language associated with a given file extension."""
    extension = FileExt(extension)
    if path and path.is_file() and (fallback := _handle_fallback(path, extension=extension)):
        return fallback.language
    return next(
        (pair.language for pair in get_ext_lang_pairs() if pair and pair.ext == extension),
        hook(extension, path) if hook else None,
    )


def _run_fallback_test(extension: FileExt, path: Path) -> LanguageName:
    """Run the fallback test for a given extension and file path."""
    from codeweaver.core.file_extensions import FALLBACK_TEST

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
    return LanguageName("matlab") if extension == FileExt(".m") else LanguageName("coq")


def _categorize_language(language: LanguageName) -> ChunkKind:
    """Categorize a language into its corresponding ChunkKind."""
    from codeweaver.core.file_extensions import (
        CODE_LANGUAGES,
        CONFIG_FILE_LANGUAGES,
        DOCS_LANGUAGES,
    )

    if language in CONFIG_FILE_LANGUAGES:
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
    def from_file(cls, file: str | Path) -> ExtKind | None:
        """
        Create an ExtKind from a file path.
        """
        filename = Path(file).name if isinstance(file, str) else file.name
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

        filename_parts = tuple(part for part in filename.split(".") if part)
        extension = (
            normalize_ext(filename_parts[-1]) if filename_parts else filename_parts[0].lower()
        )

        if (
            semantic_config_language := has_semantic_extension(extension)
        ) and is_semantic_config_ext(extension):
            return cls(language=semantic_config_language, kind=ChunkKind.CONFIG)

        if semantic_language := has_semantic_extension(extension):
            return cls(language=semantic_language, kind=ChunkKind.CODE)

        return next(
            (
                cls(language=extpair.language, kind=ChunkKind.from_string(extpair.category))  # pyright: ignore[reportArgumentType]
                for extpair in get_ext_lang_pairs()
                if extpair.is_same(filename)
            ),
            None,
        )

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
