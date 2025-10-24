# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""CodeWeaver Code Chunks and Search Results.

`CodeChunk` are the core building block of all CodeWeaver operations. They are the result of code parsing
and chunking operations, and they contain the actual code content along with metadata such as file path,
language, line ranges, and more. `SearchResult` is the output of a vector search operation -- before it has been processed through CodeWeaver's multi-layered reranking system.
"""

from __future__ import annotations

import textwrap

from collections.abc import Iterator, Sequence
from datetime import UTC, datetime
from functools import cached_property
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    NotRequired,
    Required,
    TypedDict,
    cast,
    is_typeddict,
)

from pydantic import (
    UUID7,
    AfterValidator,
    Field,
    NonNegativeFloat,
    PositiveFloat,
    PositiveInt,
    computed_field,
)
from pydantic_core import to_json

from codeweaver.common import ensure_iterable, set_relative_path, uuid7
from codeweaver.core.language import SemanticSearchLanguage
from codeweaver.core.metadata import ChunkSource, ExtKind, Metadata, determine_ext_kind
from codeweaver.core.spans import Span, SpanTuple
from codeweaver.core.types import BasedModel, LanguageNameT
from codeweaver.core.utils import truncate_text


if TYPE_CHECKING:
    from codeweaver.core.discovery import DiscoveredFile
    from codeweaver.core.types import AnonymityConversion, FilteredKey

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

    def _telemetry_keys(self) -> dict[FilteredKey, AnonymityConversion]:
        from codeweaver.core.types import AnonymityConversion, FilteredKey

        base = {FilteredKey("content"): AnonymityConversion.TEXT_COUNT}
        return {
            FilteredKey("file_path"): AnonymityConversion.BOOLEAN,
            FilteredKey("metadata"): AnonymityConversion.BOOLEAN,
        } | (base if isinstance(self.content, str) else {})


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
    language: SemanticSearchLanguage | LanguageNameT | None = None
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

    def _telemetry_keys(self) -> dict[FilteredKey, AnonymityConversion]:
        from codeweaver.core.types import AnonymityConversion, FilteredKey

        return {
            FilteredKey("content"): AnonymityConversion.TEXT_COUNT,
            FilteredKey("file_path"): AnonymityConversion.BOOLEAN,
            FilteredKey("metadata"): AnonymityConversion.AGGREGATE,
        }

    def serialize(self) -> SerializedCodeChunk[CodeChunk]:
        """Serialize the CodeChunk to a dictionary."""
        return self.model_dump_json(round_trip=True, exclude_none=True)

    @property
    def _serialization_order(self) -> tuple[str, ...]:
        """Define the order of fields during serialization."""
        return (
            "title",
            "content",
            "metadata",
            "file_path",
            "line_range",
            "ext_kind",
            "language",
            "source",
            "chunk_version",
        )

    def _serialize_metadata_for_cli(self) -> dict[str, Any]:
        """Serialize the metadata for CLI output."""
        if not self.metadata:
            return {}
        return {
            k: v.serialize_for_cli() if hasattr(v, "serialize_for_cli") else v  # type: ignore
            for k, v in self.metadata.items()
            if k in ("name", "context", "semantic_meta")
        }  # type: ignore

    def serialize_for_embedding(self) -> SerializedCodeChunk[CodeChunk]:
        """Serialize the CodeChunk for embedding."""
        self_map = self.model_dump(round_trip=True, exclude_unset=True, exclude=self._base_excludes)
        if metadata := self.metadata:
            metadata = {k: v for k, v in metadata.items() if k in ("name", "tags", "semantic_meta")}
        self_map["version"] = self._version
        self_map["metadata"] = metadata
        ordered_self_map = {k: self_map[k] for k in self._serialization_order if self_map.get(k)}
        return to_json({k: v for k, v in ordered_self_map.items() if v}, round_trip=True)

    @property
    def embedding_batch_id(self) -> UUID7 | None:
        """Get the batch ID for the code chunk."""
        return self._embedding_batch

    @property
    def _base_excludes(self) -> set[str]:
        """Get the base fields to exclude during serialization."""
        return {
            "_version",
            "_embedding_batch",
            "chunk_version",
            "timestamp",
            "chunk_id",
            "parent_id",
            "length",
        }

    def set_batch_id(self, batch_id: UUID7) -> None:
        """Set the batch ID for the code chunk."""
        self._embedding_batch = batch_id

    def serialize_for_cli(self) -> dict[str, Any]:
        """Serialize the CodeChunk for CLI output."""
        self_map: dict[str, Any] = {
            k: v for k, v in super().serialize_for_cli().items() if k not in self._base_excludes
        }
        if self.metadata:
            self_map["metadata"] = self._serialize_metadata_for_cli()
        if self_map.get("content"):
            self_map["content"] = truncate_text(self_map["content"])
        return self_map

    @classmethod
    def from_file(cls, file: DiscoveredFile, line_range: Span, content: str) -> CodeChunk:
        """Create a CodeChunk from a file."""
        return cls.model_validate({
            "file_path": file.path,
            "line_range": line_range,
            "content": content,
            "language": file.ext_kind.language
            if file.ext_kind
            else getattr(ExtKind.from_file(file.path), "language", None),
            "source": ChunkSource.FILE,
        })

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
        from codeweaver.common.utils.utils import ensure_iterable

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
