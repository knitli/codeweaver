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
    NamedTuple,
    NotRequired,
    Required,
    Self,
    TypedDict,
    cast,
    is_typeddict,
)

from pydantic import (
    UUID7,
    AfterValidator,
    Field,
    NonNegativeInt,
    PositiveFloat,
    PositiveInt,
    computed_field,
)
from pydantic_core import to_json

from codeweaver.core.language import SemanticSearchLanguage
from codeweaver.core.metadata import ChunkSource, ExtKind, Metadata, determine_ext_kind
from codeweaver.core.spans import Span, SpanTuple
from codeweaver.core.stores import BlakeHashKey
from codeweaver.core.types import BasedModel, FilteredKeyT, LanguageNameT
from codeweaver.core.types.utils import generate_field_title
from codeweaver.core.utils import ensure_iterable, set_relative_path, truncate_text, uuid7


if TYPE_CHECKING:
    from codeweaver_tokenizers.base import Tokenizer

    from codeweaver.core.discovery import DiscoveredFile
    from codeweaver.core.types import AnonymityConversion
    from codeweaver.providers.embedding.registry import EmbeddingRegistry
    from codeweaver.providers.embedding.types import EmbeddingBatchInfo

# ---------------------------------------------------------------------------
# *                    Code Search and Chunks
# ---------------------------------------------------------------------------

type SerializedStrOnlyCodeChunk[CodeChunk] = str
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


def _get_registry() -> EmbeddingRegistry:
    from codeweaver.providers.embedding.registry import get_embedding_registry

    return get_embedding_registry()


class BatchKeyIndex(NamedTuple):
    """Tuple representing the index of a chunk within a batch.

    NOTE: While a CodeChunk can hypothetically have both primary and secondary batch keys for both dense and sparse embeddings, in practice, it's unlikely. The secondary/backup embedding process uses ultralightweight models with narrower context windows than most users will have by default. Consequently, the chunkers will produce smaller chunks that fit within these context windows, and these chunks will be embedded separately from the primary embeddings.
    """

    primary_dense: Annotated[
        BatchKeys | None,
        Field(
            description="""UUID7 key for looking up the embedding batch of the chunk's primary dense embeddings.""",
            field_title_generator=generate_field_title,
        ),
    ] = None
    primary_sparse: Annotated[
        BatchKeys | None,
        Field(
            description="""UUID7 key for looking up the embedding batch of the chunk's primary sparse embeddings.""",
            field_title_generator=generate_field_title,
        ),
    ] = None
    secondary_dense: Annotated[
        BatchKeys | None,
        Field(
            description="""UUID7 key for looking up the embedding batch of the chunk's secondary dense embeddings.""",
            field_title_generator=generate_field_title,
        ),
    ] = None
    secondary_sparse: Annotated[
        BatchKeys | None,
        Field(
            description="""UUID7 key for looking up the embedding batch of the chunk's secondary sparse embeddings.""",
            field_title_generator=generate_field_title,
        ),
    ] = None


class BatchKeys(NamedTuple):
    """Tuple representing batch keys for embedding operations."""

    id: Annotated[
        UUID7,
        Field(
            description="""The embedding batch ID the chunk belongs to.""",
            field_title_generator=generate_field_title,
        ),
    ]
    idx: Annotated[
        NonNegativeInt,
        Field(
            description="""The index of the chunk within the batch.""",
            field_title_generator=generate_field_title,
        ),
    ]
    sparse: Annotated[
        bool,
        Field(
            description="""Whether the batch's embeddings are sparse.""",
            field_title_generator=generate_field_title,
        ),
    ] = False


class CodeChunkDict(TypedDict, total=False):
    """A python dictionary of a CodeChunk.

    Primarily provides type hints and documentation for the expected structure of a CodeChunk when represented as a dictionary.
    """

    content: Required[str]
    line_range: Required[SpanTuple | Span]
    file_path: NotRequired[Path | None]
    language: NotRequired[SemanticSearchLanguage | LanguageNameT | None]
    source: NotRequired[ChunkSource | None]
    timestamp: NotRequired[PositiveFloat]
    chunk_id: NotRequired[UUID7]
    parent_id: NotRequired[UUID7 | None]
    metadata: NotRequired[Metadata | None]
    chunk_name: NotRequired[str | None]
    _embedding_index: NotRequired[BatchKeyIndex | None]
    blake_hash: NotRequired[BlakeHashKey]
    name: NotRequired[str]
    title: NotRequired[str]
    dense_batch_key: NotRequired[BatchKeys | None]
    sparse_batch_key: NotRequired[BatchKeys | None]
    secondary_keys: NotRequired[tuple[BatchKeys, BatchKeys] | tuple[BatchKeys] | None]
    length: NotRequired[PositiveInt]
    token_estimate: NotRequired[PositiveInt]
    line_start: NotRequired[PositiveInt]
    line_end: NotRequired[PositiveInt]


class CodeChunk(BasedModel):
    """Represents a chunk of code or docs with metadata."""

    content: str
    line_range: Annotated[Span, Field(description="""Line range in the source file""")]
    file_path: Annotated[
        Path | None,
        Field(
            description="""Relative path to the source file from project root. Not all chunks are from files, so this can be None."""
        ),
        AfterValidator(set_relative_path),
    ] = None
    language: SemanticSearchLanguage | LanguageNameT | None = None
    source: ChunkSource = ChunkSource.TEXT_BLOCK
    timestamp: Annotated[
        PositiveFloat,
        Field(
            kw_only=True,
            description="""Timestamp of the code chunk creation or modification""",
            frozen=True,
        ),
    ] = datetime.now(UTC).timestamp()
    chunk_id: Annotated[
        UUID7,
        Field(kw_only=True, description="""Unique identifier for the code chunk""", frozen=True),
    ] = uuid7()
    metadata: Metadata = Field(
        default_factory=lambda data: Metadata(
            chunk_id=data["chunk_id"],
            created_at=data["timestamp"],
            line_start=data["line_range"].start,
            line_end=data["line_range"].end,
            **(data.get("metadata") or {}),
        ),
        description="Additional metadata for the code chunk; includes ast-derived information under the `semantic` field for supported languages.",
    )
    ext_kind: ExtKind | None = Field(
        default_factory=determine_ext_kind, description="The file extension and its `ChunkKind`."
    )

    parent_id: UUID7 | None = Field(
        default_factory=lambda data: data["line_range"]._source_id,
        description="The source ID of the parent file or chunk.",
    )
    # Vector storage fields
    chunk_name: Annotated[
        str | None,
        Field(
            description="""Fully qualified chunk identifier (e.g., 'auth.py:UserAuth.validate')"""
        ),
    ] = None

    _version: Annotated[str, Field(repr=True, init=False, serialization_alias="chunk_version")] = (
        "1.0.0"
    )
    _embedding_index: Annotated[
        BatchKeyIndex | None,
        Field(
            repr=True,
            description="""Primary and secondary batch keys for embedding operations associated with this chunk""",
        ),
    ] = None

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        from codeweaver.core.types import AnonymityConversion, FilteredKey

        return {
            FilteredKey("content"): AnonymityConversion.TEXT_COUNT,
            FilteredKey("file_path"): AnonymityConversion.BOOLEAN,
            FilteredKey("metadata"): AnonymityConversion.AGGREGATE,
            FilteredKey("_embedding_index"): AnonymityConversion.BOOLEAN,
            FilteredKey("chunk_name"): AnonymityConversion.BOOLEAN,
            FilteredKey("name"): AnonymityConversion.HASH,
        }

    @computed_field
    @property
    def blake_hash(self) -> BlakeHashKey:
        """Compute a Blake3 hash of the chunk content for deduplication."""
        from codeweaver.core.stores import get_blake_hash

        return get_blake_hash(self.content)

    def serialize(self) -> SerializedCodeChunk[CodeChunk]:
        """Serialize the CodeChunk to a dictionary."""
        return self.model_dump_json(round_trip=True, exclude_none=True)

    def _construct_name(self) -> str:
        """Construct a name for the code chunk based on file path and line range."""
        parts: list[str] = []
        if self.file_path:
            parts.append(str(self.file_path))
        if self.line_range:
            parts.append(f"lines {self.line_range.start}-{self.line_range.end}")
        name = self.metadata.get("name") if self.metadata and self.metadata.get("name") else None
        semantic_meta = self.metadata.get("semantic_meta") if self.metadata else None
        semantic = (
            semantic_meta.symbol if semantic_meta and hasattr(semantic_meta, "symbol") else None
        )
        if semantic:
            parts.append(semantic)
        elif name:
            parts.append(name)
        return " | ".join(parts) if parts else "unnamed_chunk"

    @computed_field
    @property
    def name(self) -> str:
        """Get or construct the name of the code chunk."""
        return self.chunk_name or self._construct_name()

    @property
    def _serialization_order(self) -> tuple[str, ...]:
        """Define the order of fields during serialization."""
        return (
            "title",
            "name",
            "content",
            "metadata",
            "file_path",
            "line_range",
            "ext_kind",
            "language",
            "source",
            "chunk_version",
        )

    @property
    def embeddings(self) -> BatchKeyIndex | None:
        """Get the embedding batch key index, if available."""
        return self._embedding_index

    @computed_field
    @property
    def dense_batch_key(self) -> BatchKeys | None:
        """Get the dense embedding batch key, if available."""
        return self._embedding_index.primary_dense if self._embedding_index else None

    @computed_field
    @property
    def sparse_batch_key(self) -> BatchKeys | None:
        """Get the sparse embedding batch key, if available."""
        return self._embedding_index.primary_sparse if self._embedding_index else None

    @property
    def embedding_batch_id(self) -> UUID7 | None:
        """Get the embedding batch ID, if available.

        Returns the ID from the dense batch key for backward compatibility.
        """
        return batch_key.id if (batch_key := self.dense_batch_key) else None

    @property
    def dense_embeddings(self) -> EmbeddingBatchInfo | None:
        """Get the dense embeddings info, if available."""
        if not self.dense_batch_key:
            return None
        registry = _get_registry()
        return registry[self.chunk_id].dense if self.chunk_id in registry else None

    @property
    def sparse_embeddings(self) -> EmbeddingBatchInfo | None:
        """Get the sparse embeddings info, if available."""
        if not self.sparse_batch_key:
            return None
        registry = _get_registry()
        return registry[self.chunk_id].sparse if self.chunk_id in registry else None

    def _serialize_metadata_for_cli(self) -> dict[str, Any]:
        """Serialize the metadata for CLI output."""
        if not self.metadata:
            return {}
        return {
            k: v.serialize_for_cli() if hasattr(v, "serialize_for_cli") else v  # type: ignore
            for k, v in self.metadata.items()
            if k in ("name", "context", "semantic_meta")
        }  # type: ignore

    def serialize_for_embedding(self) -> str:
        """Serialize the CodeChunk for embedding.

        Returns a JSON string containing the most relevant fields for semantic search.
        """
        # Build a plain dict with only the fields we want to include in the embedding
        # This avoids Pydantic serialization issues with computed fields and circular refs
        data = {
            "title": self.title,
            "name": self.name,
            "content": self.content,
            "file_path": str(self.file_path) if self.file_path else None,
            "language": str(self.language) if self.language else None,
            "source": str(self.source) if self.source else None,
            "chunk_version": self._version,
        }

        # Include select metadata if available
        if self.metadata:
            metadata = {
                k: v for k, v in self.metadata.items() if k in ("name", "tags", "semantic_meta")
            }
            if metadata:
                data["metadata"] = metadata

        # Use pydantic_core.to_json for fast, reliable serialization
        return to_json({k: v for k, v in data.items() if v is not None}).decode("utf-8")

    @property
    def _base_excludes(self) -> set[str]:
        """Get the base fields to exclude during serialization."""
        return {
            "_version",
            "_embedding_index",
            "chunk_version",
            "timestamp",
            "chunk_id",
            "parent_id",
            "length",
            "dense_batch_key",
            "sparse_batch_key",
            "token_estimate",
            "line_start",
            "line_end",
            "title",
        }

    def set_batch_keys(self, batch_keys: BatchKeys, *, secondary: bool = False) -> Self:
        """Set the batch keys for the code chunk.

        Returns a new CodeChunk instance with updated batch keys.
        Explicitly copies metadata dict to prevent shared references between instances.

        Args:
            batch_keys: The batch keys to set

        Returns:
            New CodeChunk instance with batch keys set
        """
        if self._embedding_index and (
            (
                not batch_keys.sparse
                and self._embedding_index.primary_dense
                and self._embedding_index.primary_dense == batch_keys
            )
            or (
                batch_keys.sparse
                and self._embedding_index.primary_sparse
                and self._embedding_index.primary_sparse == batch_keys
            )
            or (
                not batch_keys.sparse
                and self._embedding_index.secondary_dense
                and self._embedding_index.secondary_dense == batch_keys
            )
            or (
                batch_keys.sparse
                and self._embedding_index.secondary_sparse
                and self._embedding_index.secondary_sparse == batch_keys
            )
        ):
            return self

        metadata_copy = dict(self.metadata.items()) if self.metadata else None
        embedding_index = self._embedding_index or BatchKeyIndex()
        new_index = BatchKeyIndex(
            primary_dense=embedding_index.primary_dense
            or (batch_keys if not batch_keys.sparse and not secondary else None),
            primary_sparse=embedding_index.primary_sparse
            or (batch_keys if batch_keys.sparse and not secondary else None),
            secondary_dense=embedding_index.secondary_dense
            or (batch_keys if not batch_keys.sparse and secondary else None),
            secondary_sparse=embedding_index.secondary_sparse
            or (batch_keys if batch_keys.sparse and secondary else None),
        )
        return self.model_copy(
            update={"_embedding_index": new_index, "metadata": metadata_copy},
            deep=False,  # Shallow copy to avoid pickling issues with SgNode in metadata
        )

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
        """Create a CodeChunk from a file. (This creates a chunk that consists of the entire file contents. To create smaller chunks, use a chunker.)."""
        return cls.model_validate({
            "file_path": file.path,
            "line_range": line_range,
            "content": content,
            "language": file.ext_kind.language
            if file.ext_kind
            else getattr(ExtKind.from_file(file.path), "language", None),
            "source": ChunkSource.FILE,
            "parent_id": file.source_id,
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
        """Return the length of the chunk content in characters."""
        return len(self.content)

    @computed_field
    @property
    def token_estimate(self) -> PositiveInt:
        """Estimate token count for the chunk content.

        Uses rough approximation of 1 token per 4 characters.
        """
        return len(self.content) // 4

    def token_count(self, tokenizer_instance: Tokenizer[Any]) -> PositiveInt:
        """Return the token count for the chunk content."""
        return tokenizer_instance.estimate(cast(str, self.serialize_for_embedding()))

    @computed_field
    @cached_property
    def line_start(self) -> PositiveInt:
        """Return the starting line number from line_range."""
        return self.line_range.start

    @computed_field
    @cached_property
    def line_end(self) -> PositiveInt:
        """Return the ending line number from line_range."""
        return self.line_range.end

    # Aliases for common naming conventions
    @property
    def start_line(self) -> PositiveInt:
        """Alias for line_start for compatibility."""
        return self.line_start

    @property
    def end_line(self) -> PositiveInt:
        """Alias for line_end for compatibility."""
        return self.line_end

    @classmethod
    def chunkify(cls, text: StructuredDataInput) -> Iterator[CodeChunk]:
        """Convert text to a CodeChunk."""
        from codeweaver.core.utils import ensure_iterable

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
            if isinstance(chunk, str | bytes | bytearray):  # type: ignore
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
    "SerializedCodeChunk",
    "SerializedStrOnlyCodeChunk",
    "StructuredDataInput",
)

import contextlib


# Rebuild models to resolve forward references
# Force rebuild even if it fails - better to have working models than perfect ones
# Re-enabled after resolving circular import issues

if not CodeChunk.__pydantic_complete__:
    with contextlib.suppress(Exception):
        _ = CodeChunk.model_rebuild(force=True)
