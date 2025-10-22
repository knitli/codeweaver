"""Defines metadata types and enums for code chunks in CodeWeaver."""

from __future__ import annotations

import contextlib

from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, NamedTuple, NotRequired, Required, Self, TypedDict

from ast_grep_py import SgNode
from pydantic import UUID7, ConfigDict, Field, PositiveFloat

from codeweaver._utils import normalize_ext, uuid7
from codeweaver.core.language import (
    ConfigLanguage,
    SemanticSearchLanguage,
    has_semantic_extension,
    is_semantic_config_ext,
)
from codeweaver.core.types import (
    FROZEN_BASEDMODEL_CONFIG,
    BasedModel,
    BaseEnum,
    LanguageName,
    LiteralStringT,
)


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
            default_factory=lambda data: data["primary_node"],
        ),
    ] = None
    thing_id: UUID7 = uuid7()
    parent_thing_id: UUID7 | None = None
    is_partial_node: Annotated[
        bool,
        Field(
            description="""Whether the node is a partial node. Partial nodes are created when the node is too large for the context window."""
        ),
    ] = False

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
        if isinstance(language, SemanticSearchLanguage):
            if isinstance(kind, ChunkKind):
                return cls(language=language, kind=kind)
            return cls(
                language=language,
                kind=ChunkKind.CONFIG if language.is_config_language else ChunkKind.CODE,
            )
        if isinstance(language, ConfigLanguage) and language not in (
            ConfigLanguage.BASH,
            ConfigLanguage.SELF,
            ConfigLanguage.KOTLIN,
        ):
            return cls(
                language=language.as_semantic_search_language or language, kind=ChunkKind.CONFIG
            )
        if isinstance(language, ConfigLanguage):
            return cls(
                language=language.as_semantic_search_language or language,
                kind=ChunkKind.CODE_OR_CONFIG,
            )
        with contextlib.suppress(KeyError, ValueError, AttributeError):
            if semantic := SemanticSearchLanguage.from_string(language):
                return cls.from_language(semantic, kind)
        from codeweaver._constants import CODE_LANGUAGES, CONFIG_FILE_LANGUAGES, DOCS_LANGUAGES

        if language in CONFIG_FILE_LANGUAGES:
            return cls(language=LanguageName(language), kind=ChunkKind.CONFIG)
        if language in CODE_LANGUAGES:
            return cls(language=LanguageName(language), kind=ChunkKind.CODE)
        if language in DOCS_LANGUAGES:
            return cls(language=LanguageName(language), kind=ChunkKind.DOCS)
        if isinstance(kind, ChunkKind):
            return cls(language=LanguageName(language), kind=kind)
        if found_kind := ChunkKind.from_string(kind):
            return cls(language=LanguageName(language), kind=found_kind)  # pyright: ignore[reportArgumentType]
        return cls(language=LanguageName(language), kind=ChunkKind.OTHER)  # pyright: ignore[reportArgumentType]

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


__all__ = ("ChunkKind", "ChunkSource", "ExtKind", "Metadata", "SemanticMetadata")
