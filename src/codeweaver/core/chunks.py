from __future__ import annotations

import textwrap

from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
from functools import cached_property
from pathlib import Path
from typing import Annotated, NotRequired, Required, TypedDict, cast

from pydantic import (
    UUID7,
    AfterValidator,
    Field,
    NonNegativeFloat,
    PositiveFloat,
    PositiveInt,
    computed_field,
)
from pydantic.dataclasses import is_typeddict
from pydantic_core import to_json

from codeweaver._utils import ensure_iterable, set_relative_path, uuid7
from codeweaver.core.language import SemanticSearchLanguage
from codeweaver.core.metadata import ChunkSource, ExtKind, Metadata
from codeweaver.core.spans import Span, SpanTuple
from codeweaver.core.types import BasedModel


# ---------------------------------------------------------------------------
# *                    Code Search and Chunks
# ---------------------------------------------------------------------------

type SerializedCodeChunk[CodeChunk] = str | bytes | bytearray
type ChunkSequence = (
    Sequence[CodeChunk]
    | Sequence[SerializedCodeChunk[CodeChunk]]
    | Sequence[CodeChunkDict]
    | Iterator[CodeChunk]
    | Iterator[SerializedCodeChunk[CodeChunk]]
    | Iterator[CodeChunkDict]
)
type StructuredDataInput = (
    CodeChunk | SerializedCodeChunk[CodeChunk] | ChunkSequence | CodeChunkDict
)


class SearchResult(BasedModel):
    """Result from vector search operations."""

    content: str | CodeChunk
    file_path: Annotated[
        Path | None,
        Field(description="""Path to the source file"""),
        AfterValidator(set_relative_path),
    ]
    score: Annotated[NonNegativeFloat, Field(description="""Similarity score""")]
    metadata: Annotated[
        Metadata | None, Field(description="""Additional metadata about the result""")
    ] = None


class CodeChunkDict(TypedDict, total=False):
    """A python dictionary of a CodeChunk.

    Primarily provides type hints and documentation for the expected structure of a CodeChunk when represented as a dictionary.
    """

    content: Required[str]
    line_range: Required[SpanTuple | Span]
    file_path: NotRequired[Path | None]
    language: NotRequired[SemanticSearchLanguage | str | None]
    source: NotRequired[ChunkSource | None]
    timestamp: NotRequired[PositiveFloat]
    chunk_id: NotRequired[UUID7]
    parent_id: NotRequired[UUID7 | None]
    metadata: NotRequired[Metadata | None]
    _embedding_batch: NotRequired[UUID7 | None]


class CodeChunk(BasedModel):
    """Represents a chunk of code or docs with metadata."""

    content: str
    line_range: Annotated[Span, Field(description="""Line range in the source file""")]
    file_path: Annotated[
        Path | None,
        Field(
            description="""Path to the source file. Not all chunks are from files, so this can be None."""
        ),
        AfterValidator(set_relative_path),
    ] = None
    language: SemanticSearchLanguage | str | None = None
    source: ChunkSource = ChunkSource.TEXT_BLOCK
    ext_kind: Annotated[
        ExtKind | None,
        Field(
            default_factory=determine_ext_kind,
            description="""The extension kind of the source file""",
        ),
    ] = None
    timestamp: Annotated[
        PositiveFloat,
        Field(
            default_factory=datetime.now(UTC).timestamp,
            kw_only=True,
            description="""Timestamp of the code chunk creation or modification""",
            frozen=True,
        ),
    ] = datetime.now(UTC).timestamp()
    chunk_id: Annotated[
        UUID7,
        Field(
            default_factory=uuid7,
            kw_only=True,
            description="""Unique identifier for the code chunk""",
            frozen=True,
        ),
    ] = uuid7()
    parent_id: Annotated[
        UUID7 | None, Field(description="""Parent chunk ID, such as the file ID, if applicable""")
    ] = None
    metadata: Annotated[
        Metadata | None,
        Field(
            default_factory=dict,
            kw_only=True,
            description="""Additional metadata about the code chunk""",
        ),
    ] = None
    _version: Annotated[str, Field(repr=True, init=False, serialization_alias="chunk_version")] = (
        "1.0.0"
    )
    _embedding_batch: Annotated[
        UUID7 | None,
        Field(
            repr=False,
            description="""Batch ID for the embedding batch the chunk was processed in.""",
        ),
    ] = None

    def serialize(self) -> SerializedCodeChunk[CodeChunk]:
        """Serialize the CodeChunk to a dictionary."""
        return self.model_dump_json(round_trip=True, exclude_none=True)

    def serialize_for_embedding(self) -> SerializedCodeChunk[CodeChunk]:
        """Serialize the CodeChunk for embedding."""
        self_map = self.model_dump(
            round_trip=True,
            exclude_unset=True,
            exclude={"chunk_id", "timestamp", "parent_id", "_embedding_batch"},
        )
        if metadata := self_map.get("metadata", {}):
            metadata = {k: v for k, v in metadata.items() if k in ("name", "tags", "semantic_meta")}
        ordered_self_map = {
            "title": self_map.get("title"),
            "content": self_map.get("content"),
            "metadata": metadata,
            "file_path": self_map.get("file_path"),
            "line_range": self_map.get("line_range"),
            "ext_kind": str(self_map.get("ext_kind")),
            "language": self_map.get("language"),
            "source": self_map.get("source"),
            "chunk_version": self._version,
        }

        return to_json({k: v for k, v in ordered_self_map.items() if v}, round_trip=True)

    def set_batch_id(self, batch_id: UUID7) -> None:
        """Set the batch ID for the code chunk."""
        self._embedding_batch = batch_id

    @computed_field
    @cached_property
    def title(self) -> str:
        """Return a title for the code chunk, if possible."""
        title_parts: list[str] = []
        if self.metadata and (name := self.metadata.get("name")):
            title_parts.append(f"Name: {name}")
        elif self.file_path:
            title_parts.append(f"Filename: {self.file_path.name}")
        if self.language:
            title_parts.append(f"Language: {str(self.language).capitalize()}")
        if self.source:
            title_parts.append(f"Category: {str(self.source).capitalize()}")
        return "\n".join(textwrap.wrap(" | ".join(title_parts), width=80, subsequent_indent="    "))

    @computed_field
    @cached_property
    def length(self) -> PositiveInt:
        """Return the length of the serialized content in characters."""
        return len(self.serialize_for_embedding())

    @classmethod
    def chunkify(cls, text: StructuredDataInput) -> Iterator[CodeChunk]:
        """Convert text to a CodeChunk."""
        from codeweaver._utils import ensure_iterable

        yield from (
            item
            if isinstance(item, cls)
            else (
                cls.model_validate_json(item)
                if isinstance(item, str | bytes | bytearray)
                else cls.model_validate(item)
            )
            for item in ensure_iterable(text)
        )

    @staticmethod
    def dechunkify(chunks: StructuredDataInput, *, for_embedding: bool = False) -> Iterator[str]:
        """Convert a sequence of CodeChunks or mixed serialized and deserialized chunks back to json strings."""
        for chunk in ensure_iterable(chunks):
            if isinstance(chunk, str | bytes | bytearray):
                yield chunk.decode("utf-8") if isinstance(chunk, bytes | bytearray) else chunk
            elif is_typeddict(chunk):
                result = (
                    CodeChunk.model_validate(chunk).serialize_for_embedding()
                    if for_embedding
                    else CodeChunk.model_validate(chunk).serialize()
                )
                yield result.decode("utf-8") if isinstance(result, bytes | bytearray) else result
            else:
                chunk = cast(CodeChunk, chunk)
                result = chunk.serialize_for_embedding() if for_embedding else chunk.serialize()
                yield result.decode("utf-8") if isinstance(result, bytes | bytearray) else result


__all__ = (
    "ChunkSequence",
    "CodeChunk",
    "CodeChunkDict",
    "SearchResult",
    "SerializedCodeChunk",
    "StructuredDataInput",
)
