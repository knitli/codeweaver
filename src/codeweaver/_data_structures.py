# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""A foundational enum class for the CodeWeaver project for common functionality."""

from __future__ import annotations

import contextlib
import copy
import os
import sys
import textwrap

from collections.abc import Callable, ItemsView, Iterator, KeysView, Sequence, ValuesView
from datetime import UTC, datetime
from functools import cache, cached_property
from pathlib import Path
from types import MappingProxyType
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    ClassVar,
    Literal,
    NamedTuple,
    NewType,
    NotRequired,
    Required,
    Self,
    TypedDict,
    TypeGuard,
    TypeVar,
    cast,
    is_typeddict,
)
from weakref import WeakValueDictionary

from ast_grep_py import SgNode
from pydantic import (
    UUID7,
    AfterValidator,
    ConfigDict,
    Field,
    NonNegativeFloat,
    NonNegativeInt,
    PositiveFloat,
    PositiveInt,
    PrivateAttr,
    Tag,
    computed_field,
    model_validator,
)
from pydantic.dataclasses import dataclass
from pydantic_core import to_json
from typing_extensions import TypeIs

from codeweaver._common import BasedModel, BaseEnum, DataclassSerializationMixin
from codeweaver._constants import get_ext_lang_pairs
from codeweaver._utils import (
    ensure_iterable,
    get_git_branch,
    lazy_importer,
    normalize_ext,
    sanitize_unicode,
    set_relative_path,
    uuid7,
)
from codeweaver.semantic._ast_grep import AstThing


if TYPE_CHECKING:
    from codeweaver.language import ConfigLanguage, SemanticSearchLanguage
else:
    # this prevents a very big circular import situation
    # While they're only type annotations, because of pydantic serialization/deserialization/validation, we need the types at runtime
    language_module = lazy_importer("codeweaver.language")
    ConfigLanguage = language_module.ConfigLanguage
    SemanticSearchLanguage = language_module.SemanticSearchLanguage

try:
    # there are a handful of rare situations where users might not be able to install blake3
    # luckily the apis are the same
    from blake3 import blake3
except ImportError:
    from hashlib import blake2b as blake3


BlakeKey = NewType("BlakeKey", str)
BlakeHashKey = Annotated[
    BlakeKey, Field(description="""A blake3 hash key string""", min_length=64, max_length=64)
]

# ------------------------------------------------
# *          Metadata Types and Enums          *
# ------------------------------------------------

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


class ChunkKind(BaseEnum):
    """Represents the kind of a code chunk."""

    CODE = "code"
    CONFIG = "config"
    DOCS = "docs"
    OTHER = "other"


class ChunkType(BaseEnum):
    """Represents the type of a code chunk -- basically how it was extracted."""

    TEXT_BLOCK = "text_block"
    FILE = "file"  # the whole file is the chunk
    SEMANTIC = "semantic"  # semantic chunking, e.g. from AST nodes
    EXTERNAL = "external"  # from internet or similar external sources, not from code files


class SemanticMetadata(BasedModel):
    """Metadata associated with the semantics of a code chunk."""

    model_config = BasedModel.model_config | ConfigDict(frozen=True, validate_assignment=True)

    language: Annotated[
        SemanticSearchLanguage | str,
        Field(description="""The programming language of the code chunk"""),
    ]
    primary_node: AstThing[SgNode] | None
    children: tuple[AstThing[SgNode], ...] = ()
    # TODO: Logic for symbol extraction from AST nodes
    symbol: Annotated[
        str | None,
        Field(
            description="""The symbol represented by the node""",
            default_factory=lambda data: data["primary_node"],
        ),
    ] = None
    node_id: UUID7 = uuid7()
    parent_node_id: UUID7 | None = None
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
            primary_node=child,
            children=tuple(child.children),
            node_id=child.node_id or uuid7(),
            parent_node_id=parent_meta.node_id,
            **overrides,
        )

    @classmethod
    def from_node(
        cls, node: AstThing[SgNode] | SgNode, language: SemanticSearchLanguage | None
    ) -> Self:
        """Create a SemanticMetadata instance from an AST node."""
        if isinstance(node, SgNode):
            node = AstThing.from_sg_node(node, language=language)  # pyright: ignore[reportUnknownVariableType]
        return cls(
            language=language or node.language or "",
            primary_node=node,
            children=tuple(node.children),
            node_id=node.node_id,
            symbol=node.symbol,
            parent_node_id=node.parent_node_id,
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


# ===========================================================================
# *                            Span API
# ===========================================================================

SpanTuple = tuple[
    PositiveInt, PositiveInt, UUID7
]  # Type alias for a span tuple (start, end, source_id)

ONE_LINE = 1
"""Represents a single line span."""


@dataclass(frozen=True, slots=True, config=BasedModel.model_config)
class Span(DataclassSerializationMixin):
    """
    An immutable span of lines in a file, defined by a start and end line number, and a source identifier.

    `Span`s are a big part of CodeWeaver's foundational data structures, so they have a robust API for manipulation and comparison.
    `Span` supports intersection, union, difference, and symmetric difference operations (both by using operators and methods), as well as containment checks and subset/superset checks.

    All spans have an identifier, that they should share with the source (e.g. file) of the span. This allows for operations between spans from different sources to be safely handled, as they will not interfere with each other.

    While we want it to be intuitive to us, it might not be intuitive for everyone, so let's break down the key features and caveats:

        - Spans are inclusive of their start and end lines.
        - Operations between spans from different sources will not interfere with each other (but can return None in some cases, so get your null checks ready).
        - All spans have an identifier that they should share with the source (e.g. file) of the span.
        - Spans are immutable and cannot be modified after creation, but you can easily create new spans based on existing ones, including with a Span.
        - Spans are iterable, *and iterate over the lines*. If you want to iterate over the attributes, use `span.as_tuple`.
        - Operations:

            - `in` can test if an integer (i.e. line number), a tuple (i.e. (start, end)), or another `Span` is contained within the span.
              - For line numbers and tuples, it only checks the start and end lines, not the source identifier.
              - For spans, or tuples with a source identifier, it checks if the span overlaps with the current span in the source.
            - `difference` (`-`) operation can return a single span (if the difference is contiguous), a tuple of spans (if the other span is fully contained), or None (if the spans do not overlap).
            - `union` (`|`) operation will return a new span that covers both spans, but only if they share the same source identifier. Otherwise returns the original span.
            - `intersection` (`&`) operation will return a new span that is the overlap of both spans, or None if they do not overlap.
            - `symmetric_difference` (`^`) operation will return a tuple of spans that are the parts of each span that do not overlap with the other, or None if they do not overlap.
            - `equals` (`==`) operation will return True if the spans are equal, and False otherwise. Spans are only equal if they have the same start, end, **and** source identifier.

    Why immutable? Because we don't want to accidentally modify a span that is being used elsewhere, and we want to ensure that spans are always in a valid state. It also allows us to comfortably use them as keys, and in sets, and supports our data-safe set-like operations here.
    """

    start: PositiveInt
    end: PositiveInt

    _source_id: Annotated[
        UUID7,
        Field(
            default_factory=uuid7,
            description="""The identifier for the span's source, such as a file.""",
            repr=True,
            init=True,
            serialization_alias="source_id",
            validation_alias="source_id",
            exclude=False,
        ),
    ]  # Unique identifier for the source of the span, usually a `chunk_id` or `file_id`.

    __match_args__: ClassVar[tuple[str, str]] = ("start", "end")

    def __hash__(self):
        return hash((self.start, self.end, self._source_id))

    def __str__(self) -> str:
        """Return a string representation of the span."""
        return f"lines {self.start}-{self.end} (source: {self._source_id})"

    def __repr__(self):
        """Return a string representation of the span."""
        return f"Span({self.start}, {self.end}, {self._source_id})"

    def __or__(self, other: Span) -> Span:  # Union
        """Return the union of two spans."""
        if self._source_id != other._source_id:
            return self
        return Span(min(self.start, other.start), max(self.end, other.end), self._source_id)

    def __and__(self, other: Span) -> Span | None:  # Intersection
        """Return the intersection between two spans."""
        if self._source_id != other._source_id:
            return None
        start = max(self.start, other.start)
        end = min(self.end, other.end)
        return Span(start, end, self._source_id) if start <= end else None

    def __sub__(self, other: Span) -> Span | tuple[Span, Span] | None:  # Difference
        """Return the difference between two spans."""
        if self._source_id != other._source_id:
            return self  # Cannot subtract spans from different sources

        if self.end < other.start or self.start > other.end:
            return self  # No overlap
        if other.start <= self.start and other.end >= self.end:
            return None  # Fully covered
        if other.start > self.start and other.end < self.end:
            return (
                Span(self.start, other.start - ONE_LINE, self._source_id),
                Span(other.end + ONE_LINE, self.end, self._source_id),
            )
        if other.start <= self.start:
            return (
                Span(other.end + ONE_LINE, self.end, self._source_id)
                if other.end < self.end
                else None
            )
        return (
            Span(self.start, other.start - ONE_LINE, self._source_id)
            if other.start > self.start
            else None
        )

    def __xor__(self, other: Span) -> tuple[Span, ...] | None:  # Symmetric Difference
        """Return the symmetric difference between two spans."""
        if self._source_id.hex != other._source_id.hex or not self & other:
            return (self, other)
        diff1 = self - other
        diff2 = other - self
        result: list[Span] = []
        if diff1:
            result.extend(diff1 if isinstance(diff1, tuple) else [diff1])
        if diff2:
            result.extend(diff2 if isinstance(diff2, tuple) else [diff2])
        return tuple(result) if result else None

    def __le__(self, other: Span) -> bool:  # Subset
        if self._source_id.hex != other._source_id.hex:
            return False
        return self.start >= other.start and self.end <= other.end

    def __ge__(self, other: Span) -> bool:  # Superset
        if self._source_id.hex != other._source_id.hex:
            return False
        return self.start <= other.start and self.end >= other.end

    def __eq__(self, other: object) -> bool:  # Equality
        if not isinstance(other, Span) or self._source_id.hex != other._source_id.hex:
            return False
        return self.start == other.start and self.end == other.end

    def __iter__(self) -> Iterator[PositiveInt]:
        """Return an iterator *over the lines* in the span."""
        current = self.start
        while current <= self.end:
            yield current
            current += ONE_LINE

    def __len__(self) -> NonNegativeInt:
        """Return the number of lines in the span."""
        return self.end - self.start + ONE_LINE

    @staticmethod
    def _is_span_tuple(
        span: Span
        | SpanTuple
        | tuple[PositiveInt, PositiveInt]
        | tuple[PositiveInt, PositiveInt, None]
        | int,
    ) -> TypeGuard[SpanTuple]:
        """Check if the given span is a SpanTuple."""
        return isinstance(span, tuple) and len(span) == 3 and hasattr(span[2], "hex")

    @staticmethod
    def _is_start_end_tuple(
        span: Span
        | SpanTuple
        | tuple[PositiveInt, PositiveInt]
        | tuple[PositiveInt, PositiveInt, None]
        | int,
    ) -> TypeGuard[tuple[PositiveInt, PositiveInt] | tuple[PositiveInt, PositiveInt, None]]:
        """Check if the given span is a (start, end) tuple."""
        return (
            isinstance(span, tuple)
            and (len(span) == 2 or (len(span) == 3 and span[2] is None))
            and span[1] >= span[0]
        )  # type: ignore

    def _is_contained(self, number: int) -> bool:
        """Check if the given number is contained in the span."""
        return self.start <= number <= self.end

    def __contains__(
        self,
        span: Span
        | SpanTuple
        | tuple[PositiveInt, PositiveInt]
        | tuple[PositiveInt, PositiveInt, None]
        | int,
    ) -> bool:
        """
        Check if the span contains a line number or another span or a tuple of (start, end).

        This is naive for tuples and line numbers, but does consider the source for span comparisons.
        """
        if isinstance(span, int):
            return self._is_contained(span)
        if isinstance(span, tuple) and len(span) == 3 and self._is_span_tuple(span):
            return bool(self & Span.from_tuple(span))
        if self._is_start_end_tuple(span):
            start, end = span[:2]
            return self._is_contained(start) or self._is_contained(end)
        return bool(self & span) if isinstance(span, Span) else False

    @classmethod
    def __call__(
        cls, span: SpanTuple | Span | tuple[PositiveInt, PositiveInt, UUID7 | None]
    ) -> Span:
        """Create a Span from a tuple of (start, end, source_id)."""
        if isinstance(span, Span):
            return cls(*span.as_tuple)
        start, end, source_id = span
        return cls(start=start, end=end, _source_id=source_id or uuid7())

    @classmethod
    def from_tuple(cls, span: SpanTuple) -> Span:
        """Create a Span from a tuple of (start, end, source_id)."""
        return cls(*span)

    @property
    def as_tuple(self) -> SpanTuple:
        """Return the span as a tuple of (start, end, source_id)."""
        return (self.start, self.end, self._source_id)

    @property
    def source_id(self) -> str:
        """The identifier for the source of the span."""
        return self._source_id.hex

    def from_sourced_lines(self, start: NonNegativeInt, end: NonNegativeInt) -> Span:
        """Create a Span for the same source as this one, but with a new start and end."""
        return Span(start=start, end=end, _source_id=self._source_id)

    @model_validator(mode="after")
    def check_span(self) -> Span:
        """Ensure that the start is less than or equal to the end."""
        if self.start > self.end:
            raise ValueError("Start must be less than or equal to end")
        return self

    def union(self, other: Span) -> Span:
        """Combine this span with another span."""
        return self | other

    def intersection(self, other: Span) -> Span | None:
        """Return the intersection of this span with another span."""
        return None if self._source_id.hex != other._source_id.hex else self & other

    def difference(self, other: Span) -> Span | tuple[Span, Span] | None:
        """
        Return the difference between this span and another span.

        If the spans don't overlap,
        """
        return self - other

    def symmetric_difference(self, other: Span) -> tuple[Span, ...] | None:
        """Return the symmetric difference between this span and another span."""
        return self ^ other

    def contains_line(self, line: int) -> bool:
        """
        Check if this span contains a specific line.

        Note: This is a naive check that assumes the line is from the same source.

        """
        return line in self

    def is_subset(self, other: Span) -> bool:
        """Check if this span is a subset of another span."""
        return self.start >= other.start and self.end <= other.end

    def is_superset(self, other: Span) -> bool:
        """Check if this span is a superset of another span."""
        return self.start <= other.start and self.end >= other.end

    def is_adjacent(self, other: Span) -> bool:
        """Check if this span is adjacent to another span."""
        return (
            self.end == other.start
            or self.start == other.end
            or self.end + ONE_LINE == other.start
            or self.start - ONE_LINE == other.end
        )


@dataclass(slots=True, config=BasedModel.model_config)
class SpanGroup(DataclassSerializationMixin):
    """A group of spans that can be manipulated as a single unit.

    SpanGroups allow for set-like operations on groups of spans, including union, intersection, difference, and symmetric difference.

    SpanGroups normalize spans on creation and when spans are added, merging overlapping or adjacent spans with the same source_id. This ensures that the spans in a SpanGroup are always non-overlapping and non-adjacent within the same source.
    """

    spans: Annotated[
        set[Span],
        Field(
            default_factory=set,
            description="""A set of spans that can be manipulated as a group.""",
        ),
    ]

    def __post_init__(self) -> None:
        self.spans = self.spans or set()
        self._normalize()

    @computed_field
    @property
    def is_uniform(self) -> bool:
        """Check if the span group is uniform, meaning all spans have the same source_id."""
        if not self.spans:
            return True
        first_source_id = next(iter(self.spans)).source_id
        return all(span.source_id == first_source_id for span in self.spans)

    @computed_field
    @property
    def source_id(self) -> str | None:
        """Get the source_id of the span group."""
        if not self.spans or not self.is_uniform:
            return None
        return next(iter(self.spans)).source_id

    @computed_field
    @property
    def sources(self) -> frozenset[str]:
        """Get the source_ids of the span group."""
        return frozenset(span.source_id for span in self.spans)

    @classmethod
    def from_simple_spans(
        cls, simple_spans: Sequence[tuple[PositiveInt, PositiveInt]]
    ) -> SpanGroup:
        """
        Create a SpanGroup from a sequence of simple spans. Assumes all input spans are from the same source.

        Intended for ingestion, where a parser identifies spans as simple tuples of (start, end) from a single source/file, and passes them for grouping into a SpanGroup.
        """
        source_id = uuid7()  # Default source_id for the group
        spans = {Span(start, end, source_id) for start, end in simple_spans}
        return cls(spans)

    def _ensure_set(self, spans: Sequence[Any]) -> TypeGuard[set[Span]]:
        """Ensure that spans is a set of Span objects."""
        return bool(spans and isinstance(spans, set) and all(isinstance(s, Span) for s in spans))

    def _normalize(self) -> None:
        """Merge overlapping/adjacent spans with same source_id."""
        normalized: list[Span] = []
        for span in sorted(self.spans, key=lambda s: (s.source_id, s.start)):
            if normalized and normalized[-1] & span:
                normalized[-1] |= span
            else:
                normalized.append(span)
        self.spans = set(normalized)

    # ---- Set-like operators ----
    def __or__(self, other: Self) -> SpanGroup:  # Union
        """Return a new SpanGroup that is the union of this group and another."""
        return SpanGroup(self.spans | other.spans)

    def __and__(self, other: Self) -> SpanGroup:  # Intersection
        intersected = {
            s1 & s2
            for s1 in self.spans
            for s2 in other.spans
            if s1.source_id == s2.source_id and (s1 & s2) is not None
        }
        return SpanGroup({s for s in intersected if s})

    def __sub__(self, other: Self) -> SpanGroup:  # Difference
        """Return a new SpanGroup that is the difference between this group and another."""
        result: set[Span] = set()
        for s1 in self.spans:
            leftovers = [s1]
            for s2 in other.spans:
                if s1.source_id == s2.source_id:
                    new_leftovers: list[Span] = []
                    for lf in leftovers:
                        if diff := lf - s2:
                            new_leftovers.extend(diff if isinstance(diff, tuple) else [diff])
                    leftovers = new_leftovers
            result.update(leftovers)
        return SpanGroup({r for r in result if r})

    def __xor__(self, other: Self) -> SpanGroup:  # Symmetric difference
        """Return a new SpanGroup that is the symmetric difference between this group and another."""
        return (self - other) | (other - self)

    # ---- Utility ----
    def add(self, span: Span) -> Self:
        """Add a span to the group."""
        self.spans.add(span)
        self._normalize()
        return self

    def __iter__(self) -> Iterator[Span]:
        """Iterate over the spans in the group, sorted by source_id and start line."""
        yield from sorted(self.spans, key=lambda s: (s.source_id, s.start))

    def __len__(self) -> int:
        return len(self.spans)

    def __repr__(self) -> str:
        return f"SpanGroup({list(self)})"


# ---------------------------------------------------------------------------
# *                    Code Search and Chunks
# ---------------------------------------------------------------------------


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
    chunk_type: NotRequired[ChunkType | None]
    timestamp: NotRequired[PositiveFloat]
    chunk_id: NotRequired[UUID7]
    parent_id: NotRequired[UUID7 | None]
    metadata: NotRequired[Metadata | None]
    _embedding_batch: NotRequired[UUID7 | None]


def determine_ext_kind(validated_data: dict[str, Any]) -> ExtKind | None:
    """Determine the ExtKind based on the validated data."""
    if "file_path" in validated_data:
        return ExtKind.from_file(validated_data["file_path"])
    chunk_type = validated_data.get("chunk_type", ChunkType.TEXT_BLOCK)
    if (
        chunk_type == ChunkType.SEMANTIC
        and "metadata" in validated_data
        and "semantic_meta" in validated_data["metadata"]
        and (language := validated_data["metadata"]["semantic_meta"].get("language"))
    ):
        return ExtKind.from_string(language, "code")
    if "language" in validated_data and chunk_type != chunk_type.TEXT_BLOCK:
        if chunk_type == ChunkType.EXTERNAL:
            return ExtKind.from_string(validated_data["language"], ChunkKind.OTHER)
        if chunk_type in (ChunkType.FILE):
            return ExtKind.from_string(validated_data["language"], "docs")
        return ExtKind.from_string(validated_data["language"], "code")
    return None


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
    chunk_type: ChunkType = ChunkType.TEXT_BLOCK
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
            "chunk_type": self_map.get("chunk_type"),
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
        if self.chunk_type:
            title_parts.append(f"Category: {str(self.chunk_type).capitalize()}")
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


@dataclass(frozen=True, slots=True, config=BasedModel.model_config)
class DiscoveredFile(DataclassSerializationMixin):
    """Represents a file discovered during project scanning.

    `DiscoveredFile` instances are immutable and hashable, making them suitable for use in sets and as dictionary keys, and ensuring that their state cannot be altered after creation.
    In CodeWeaver operations, they are created using the `from_path` method when scanning and indexing a codebase.
    """

    path: Annotated[
        Path,
        Field(description="""Relative path to the discovered file from the project root."""),
        AfterValidator(set_relative_path),
    ]
    ext_kind: ExtKind

    file_hash: Annotated[
        BlakeHashKey,
        Field(
            default_factory=lambda data: BlakeKey(blake3(data["path"].read_bytes()).hexdigest()),
            description="""blake3 hash of the file contents. File hashes are from non-normalized content, so two files with different line endings, white spaces, unicode characters, etc. will have different hashes.""",
            init=False,
        ),
    ]
    git_branch: Annotated[
        str | None,
        Field(
            default_factory=lambda data: get_git_branch(data["path"]),
            description="""Git branch the file was discovered in, if detected.""",
            init=False,
        ),
    ] = None

    @classmethod
    def from_path(cls, path: Path, *, file_hash: BlakeKey | None = None) -> DiscoveredFile | None:
        """Create a DiscoveredFile from a file path."""
        branch = get_git_branch(path if path.is_dir() else path.parent) or "main"
        if ext_kind := (ext_kind := ExtKind.from_file(path)):
            new_hash = BlakeKey(blake3(path.read_bytes()).hexdigest())
            if file_hash and new_hash != file_hash:
                raise ValueError("Provided file_hash does not match the computed hash.")
            return cls(
                path=path, ext_kind=ext_kind, file_hash=new_hash, git_branch=cast(str, branch)
            )
        return None

    @classmethod
    def from_chunk(cls, chunk: CodeChunk) -> DiscoveredFile:
        """Create a DiscoveredFile from a CodeChunk, if it has a valid file_path."""
        if chunk.file_path and chunk.file_path.is_file() and chunk.file_path.exists():
            return cast(DiscoveredFile, cls.from_path(chunk.file_path))
        raise ValueError("CodeChunk must have a valid file_path to create a DiscoveredFile.")

    @computed_field
    @property
    def size(self) -> NonNegativeInt:
        """Return the size of the file in bytes."""
        return self.path.stat().st_size

    def is_same(self, other_path: Path) -> bool:
        """Checks if a file at other_path is the same as this one, by comparing blake3 hashes.

        The other can be in a different location (paths not the same), useful for checking if a file has been moved or copied, or deduping files (we can just point to one copy).
        """
        # TODO: A better approach for files that we can semantically analyze is to hash the AST or structure instead of the raw file contents and compare those.
        if other_path.is_file() and other_path.exists():
            file = type(self).from_path(other_path)
            return bool(file and file.file_hash == self.file_hash)
        return False

    @computed_field
    @cached_property
    def is_binary(self) -> bool:
        """Check if a file is binary by reading its first 1024 bytes."""
        try:
            with self.path.open("rb") as f:
                chunk = f.read(1024)
                if b"\0" in chunk:
                    return True
                text_characters = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)))
                nontext = chunk.translate(None, text_characters)
                return bool(nontext) / len(chunk) > 0.30
        except Exception:
            return False

    @computed_field
    @cached_property
    def is_text(self) -> bool:
        """Check if a file is text by reading its first 1024 bytes."""
        if not self.is_binary and self.contents.rstrip():
            return True
        if self.is_binary:
            try:
                if self.path.read_text(encoding="utf-8", errors="replace").rstrip():
                    return True
            except Exception:
                return False
        return False

    @property
    def contents(self) -> str:
        """Return the normalized contents of the file."""
        with contextlib.suppress(Exception):
            return self.normalize_content(self.path.read_text(errors="replace"))
        return ""

    @staticmethod
    def normalize_content(content: str | bytes | bytearray) -> str:
        """Normalize file content by ensuring it's a UTF-8 string."""
        return sanitize_unicode(content)


@cache
def _is_semantic_config_ext(ext: str) -> bool:
    """Check if the given extension is a semantic config file."""
    ext = normalize_ext(ext)
    return any(ext == config_ext for config_ext in SemanticSearchLanguage.config_language_exts())


@cache
def _has_semantic_extension(ext: str) -> SemanticSearchLanguage | None:
    """Check if the given extension is a semantic search language."""
    if found_lang := next(
        (lang for lang_ext, lang in SemanticSearchLanguage.ext_pairs() if lang_ext == ext), None
    ):
        return found_lang
    return None


class ExtKind(NamedTuple):
    """Represents a file extension and its associated kind."""

    language: str | SemanticSearchLanguage | ConfigLanguage
    kind: ChunkKind

    def __str__(self) -> str:
        """Return a string representation of the extension kind."""
        return f"{self.kind}: {self.language}"

    @classmethod
    def from_string(
        cls, language: str | SemanticSearchLanguage, kind: str | ChunkKind
    ) -> ExtKind | None:
        """Create an ExtKind from a string representation."""
        if isinstance(language, SemanticSearchLanguage):
            if isinstance(kind, ChunkKind):
                return cls(language=language, kind=kind)
            return cls(
                language=language,
                kind=ChunkKind.CONFIG if language.is_config_language else ChunkKind.CODE,
            )
        with contextlib.suppress(KeyError):
            if semantic := SemanticSearchLanguage.from_string(language):
                return cls.from_string(semantic, kind)
        from codeweaver._constants import CODE_LANGUAGES, CONFIG_FILE_LANGUAGES, DOCS_LANGUAGES

        if language in CONFIG_FILE_LANGUAGES:
            return cls(language=language, kind=ChunkKind.CONFIG)
        if language in CODE_LANGUAGES:
            return cls(language=language, kind=ChunkKind.CODE)
        if language in DOCS_LANGUAGES:
            return cls(language=language, kind=ChunkKind.DOCS)
        if isinstance(kind, ChunkKind):
            return cls(language=language, kind=kind)
        if found_kind := ChunkKind.from_string(kind):
            return cls(language=language, kind=found_kind)  # pyright: ignore[reportArgumentType]
        return cls(language=language, kind=ChunkKind.OTHER)  # pyright: ignore[reportArgumentType]

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
            semantic_config_language := _has_semantic_extension(extension)
        ) and _is_semantic_config_ext(extension):
            return cls(language=semantic_config_language.value, kind=ChunkKind.CONFIG)

        if semantic_language := _has_semantic_extension(extension):
            return cls(language=semantic_language.value, kind=ChunkKind.CODE)

        return next(
            (
                cls(language=extpair.language, kind=ChunkKind.from_string(extpair.category))  # pyright: ignore[reportArgumentType]
                for extpair in get_ext_lang_pairs()
                if extpair.is_same(filename)
            ),
            None,
        )


HashKeyKind = TypeVar(
    "HashKeyKind", Annotated[UUID7, Tag("uuid")], Annotated[BlakeHashKey, Tag("blake")]
)


def get_blake_hash[AnyStr: (str, bytes)](value: AnyStr) -> BlakeHashKey:
    """Hash a value using blake3 and return the hex digest."""
    return BlakeKey(blake3(value.encode("utf-8") if isinstance(value, str) else value).hexdigest())


def get_blake_hash_generic(value: str | bytes) -> BlakeHashKey:
    """Hash a value using blake3 and return the hex digest - generic version."""
    return BlakeKey(blake3(value.encode("utf-8") if isinstance(value, str) else value).hexdigest())


def to_uuid() -> UUID7:
    """Generate a new UUID7."""
    return uuid7()


class StoreDict(TypedDict, total=False):
    """Dictionary representation of a SimpleTypedStore.

    Note: This schema was simplified in the 2025 refactor.
    Legacy fields like 'use_uuid' and 'sub_value_type' are no longer supported.
    Use make_uuid_store() or make_blake_store() factory functions instead.
    """

    value_type: Required[type]
    store: NotRequired[dict[UUID7 | BlakeHashKey, Any]]
    _size_limit: NotRequired[PositiveInt | None]
    _id: NotRequired[UUID7]


class SimpleTypedStore[KeyT: (UUID7, BlakeHashKey), T](BasedModel):
    """A key-value store with precise typing for keys and values.

    - KeyT is either UUID7 or BlakeHashKey, determined by the concrete subclass.
    - T is the value type for all items in the store.

    The store protects data integrity by copying data on get, pushes removed items to a trash heap for
    potential recovery, and can optionally limit the total size (default is 3MB).

    As an added bonus, the store itself is:

        1. Entirely serializable. You can save and load it as JSON. Weakrefs are *not serialized*.
        2. Supports complex data types. You can store any picklable Python object, including nested structures.
        3. Has an API that mimics a standard Python dictionary, making it easy to use.

    Example:
    ```python
    # Use concrete subclasses for type safety:
    store = UUIDStore[list[str]](value_type=list)
    store["item1"] = ["value1"]
    ```

    Hey, it started simple!
    """

    model_config = BasedModel.model_config | ConfigDict(validate_assignment=True)

    store: Annotated[
        dict[KeyT, T],
        Field(
            init=False,
            default_factory=dict,
            description="""The key-value store. Keys are UUID7 or Blake3 hash keys depending on configuration.""",
        ),
    ]

    _value_type: Annotated[type[T], PrivateAttr(init=False)]

    _keygen: Callable[[], UUID7] | Callable[[str | bytes], BlakeHashKey] = to_uuid

    _size_limit: Annotated[PositiveInt | None, Field(repr=False, kw_only=True)] = (
        3 * 1024 * 1024
    )  # 3 MB default limit

    # Per-instance trash heap; avoid sharing weakrefs across instances (don't want to accidentally maintain pointers across instances)
    _trash_heap: WeakValueDictionary[KeyT, T] = PrivateAttr(
        default_factory=lambda: WeakValueDictionary[KeyT, T]()
    )

    _id: Annotated[
        UUID7,
        Field(default_factory=uuid7, description="""Unique identifier for the store""", init=False),
    ] = to_uuid()

    def __init__(self, **data: Any) -> None:
        """Initialize the store with type checks and post-init processing."""
        if data.get("store") is not None:
            self.store = data.pop("store")
        if data.get("value_type"):
            self._value_type = data.pop("value_type")
        if data.get("_value_type"):
            self._value_type = data.pop("_value_type")
        elif not self._value_type and data:
            self._value_type = next(iter(data.values())).__class__  # type: ignore
        if not hasattr(self, "_value_type") or not self._value_type:
            raise ValueError(
                "`You must either provide `_value_type` or provide values to infer it from.`"
            )

    def __model_post_init__(self) -> None:
        """Post-initialization processing.

        Override this to customize initialization behavior.
        """

    def __pydantic_extra__(self, name: str, value: Any) -> dict[str, Any]:  # type: ignore
        """This is to prevent a pydantic bug that tries to set extra fields, when this method is deprecated.
        We'll remove once I get around to submitting a PR for it.
        """
        return {}

    @computed_field
    @property
    def value_type(self) -> type[T]:
        """Return the type of values stored in the store."""
        if not hasattr(self, "_value_type"):
            raise ValueError("No value_type set! You must provide it on initialization.")
        return self._value_type

    @computed_field
    @property
    def data_size(self) -> NonNegativeInt:
        """Return the size of the store in bytes."""
        return sum(sys.getsizeof(key) + sys.getsizeof(value) for key, value in self.store.items())

    @property
    def id(self) -> UUID7:
        """Return the unique identifier for the store."""
        return self._id

    @staticmethod
    def _trial_and_error_copy(item: T) -> Literal["deepcopy", "copy", "constructor", "iter"] | None:
        """Attempt to copy an item, falling back to a simpler method on failure."""
        with contextlib.suppress(Exception):
            if copy.deepcopy(item):
                return "deepcopy"
        with contextlib.suppress(Exception):
            if copy.copy(item):
                return "copy"
        with contextlib.suppress(Exception):
            # does it have a constructor that returns itself?
            if callable(item) and item(item) is item:
                return "constructor"
        if hasattr(item, "__iter__") and callable(item):
            with contextlib.suppress(Exception):
                if item(iter(item)):  # pyright: ignore[reportCallIssue, reportArgumentType]
                    return "iter"
        return None

    @cached_property
    def _get_copy_strategy(self) -> Callable[[T], T] | None:
        """Determine the best strategy for copying items from the store."""
        sample_item: T | None = None
        if self.values():
            sample_item = next(iter(self.values()))
        elif callable(self.value_type):
            with contextlib.suppress(Exception):
                sample_item = self.value_type()
        if not sample_item:
            return lambda item: item  # no-op copy
        if isinstance(sample_item, list | set | tuple):
            return lambda item: item.copy()  # pyright: ignore[reportUnknownMemberType, reportUnknownLambdaType, reportAttributeAccessIssue]
        if copy_strategy := self._trial_and_error_copy(sample_item):
            if copy_strategy == "deepcopy":
                return copy.deepcopy
            if copy_strategy == "copy":
                return copy.copy
            if copy_strategy == "constructor":
                return lambda item: type(item)(item)  # type: ignore  # we know it's callable from trial_and_error_copy
            # copy_strategy == "iter"
            return lambda item: type(item)(iter(item))  # type: ignore
        return lambda item: item  # no-op copy

    def get(self, key: KeyT, default: Any = None) -> T | None:
        """Get a value from the store."""
        if item := self.store.get(key):
            return self._get_copy_strategy(item) if self._get_copy_strategy else item
        # Try to recover from trash first, then return default
        return self.store.get(key, default) if self.recover(key) else default

    def __iter__(self) -> Iterator[KeyT]:  # pyright: ignore[reportIncompatibleMethodOverride]
        """Return an iterator over the keys in the store."""
        return iter(self.store)

    def __delitem__(self, key: KeyT) -> None:
        """Delete a value from the store."""
        if key in self:
            self.delete(key)
        raise KeyError(key)

    def __getitem__(self, key: KeyT) -> T:
        """Get an item from the store by key."""
        if key in self:
            return cast(T, self.get(key))
        raise KeyError(key)

    def __contains__(self, key: KeyT) -> bool:
        """Check if a key is in the store."""
        return key in self.store

    def __len__(self) -> int:
        return len(self.store)

    def __setitem__(self, key: KeyT, value: Any) -> None:
        """Set an item in the store by key."""
        self.set(key, value)

    def __and__(self, other: SimpleTypedStore[KeyT, T]) -> SimpleTypedStore[KeyT, T]:
        """Return a new store with items from both stores."""
        if self.value_type != other.value_type or type(self) is not type(other):
            return self
        new_store = type(self)(value_type=self.value_type, store={}, _size_limit=self._size_limit)
        new_store.store = self.store.copy()
        new_store.store |= other.store
        return new_store

    def _guard(self, item: Any) -> TypeIs[T]:
        """Ensure the item is of the correct type."""
        return isinstance(item, self.value_type)

    @property
    def keygen(self) -> Callable[[], UUID7] | Callable[[str | bytes], BlakeHashKey]:
        """Return the key generator function."""
        return self._keygen

    @property
    def view(self) -> MappingProxyType[KeyT, T]:
        """Return a read-only view of the store."""
        return MappingProxyType(self.store)

    def generate(self, value: str | bytes | None = None) -> KeyT:
        """Generate a new key for the store."""
        if self._keygen == to_uuid:
            return cast(KeyT, to_uuid())
        # we're dealing with BlakeHashKey:
        if not value:
            rand = os.urandom(16)
            value = rand
        return cast(KeyT, self._keygen(value))  # pyright: ignore[reportCallIssue]

    def keys(self) -> KeysView[KeyT]:
        """Return the keys in the store."""
        return self.store.keys()

    def values(self) -> ValuesView[T]:
        """Return the values in the store."""
        return self.store.values()

    def items(self) -> ItemsView[KeyT, T]:
        """Return the items in the store."""
        return self.store.items()

    def _validate_value(self, value: Any) -> TypeGuard[T]:
        """Validate that the value is of the correct type."""
        return self._guard(value)

    def _check_and_set(self, key: KeyT, value: T) -> KeyT:
        """Check the value type and set the sub-value type if needed."""
        if key in self.store:
            return key
        self.set(key, value)
        return key

    def update(self, values: dict[KeyT, T]) -> Iterator[KeyT]:
        """Update multiple items in the store."""
        if values and type(next(iter(values.keys()))) is type(next(iter(self.store.keys()))):
            for key, value in values.items():
                self[key] = value
            yield from values.keys()
        else:
            yield from (self.add(value) for value in values.values())

    def add(self, value: Any, *, hash_value: bytes | bytearray | None = None) -> KeyT:
        """Add a value to the store and return its key.

        Optionally provide a value to hash for the key if not using UUIDs and the value is large or complex.
        """
        if not self._validate_value(value):
            raise TypeError(f"Invalid value: {value}")
        key: UUID7 | None = to_uuid() if self.keygen == to_uuid else None  # pyright: ignore[reportAssignmentType]
        if key:
            return self._check_and_set(cast(KeyT, key), value)
        if hash_value:
            blake_key: BlakeHashKey = (  # pyright: ignore[reportRedeclaration]
                get_blake_hash(hash_value)
                if isinstance(hash_value, bytes)
                else get_blake_hash(bytes(hash_value))
            )
        else:
            # For Blake stores, generate a random value to hash if the value can't be hashed directly
            rand_value = os.urandom(16)
            blake_key = get_blake_hash_generic(rand_value)
        return self._check_and_set(cast(KeyT, blake_key), value)

    def _make_room(self, required_space: int) -> None:
        """Make room in the store by removing the least recently used items."""
        if not self._size_limit or required_space <= 0:
            return
        weight_loss_goal = (self._size_limit - self.data_size) + required_space
        if not self.store or weight_loss_goal <= 0:
            # We either have no items, or the item is too large to fit
            self.store.clear()
            return
        while self._size_limit and weight_loss_goal > 0:
            # LIFO removal strategy for simplicity
            removed = self.store.popitem()
            weight_loss_goal -= sys.getsizeof(removed[0]) + sys.getsizeof(removed[1])
            self._trash_heap[removed[0]] = removed[1]
            if weight_loss_goal <= 0:
                break

    def set(self, key: KeyT, value: Any) -> None:
        """Set a value in the store."""
        if not self._validate_value(value):
            raise TypeError(f"Invalid value: {value}")
        if not self.has_room(sys.getsizeof(value) + sys.getsizeof(key)):
            self._make_room(sys.getsizeof(value) + sys.getsizeof(key))
        if key in self.store:
            if value == self.store[key]:
                return
            _ = self._check_and_set(key, value)
        if key in self._trash_heap and self._trash_heap[key] is not None:
            del self._trash_heap[key]
        self.store[key] = value

    def has_room(self, additional_size: int = 0) -> bool:
        """Check if the store has room for additional data."""
        return not self._size_limit or (self.data_size + additional_size) <= self._size_limit

    def delete(self, key: KeyT) -> None:
        """Delete a value from the store."""
        if key in self.store:
            del self.store[key]
        if key in self._trash_heap:
            del self._trash_heap[key]

    def clear(self) -> None:
        """Clear the store."""
        self._trash_heap.update(self.store)
        self.store.clear()

    def clear_trash(self) -> None:
        """Clear the trash heap."""
        self._trash_heap.clear()

    def recover(self, key: KeyT) -> bool:
        """Recover a value from the trash heap."""
        if (
            key in self._trash_heap
            and key not in self.store
            and (actually_there := self._trash_heap.get(key)) is not None
        ):
            self.set(key, actually_there)
            return True
        return False


class UUIDStore[T](SimpleTypedStore[UUID7, T]):
    """Typed store specialized for UUID keys."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._keygen = to_uuid


class BlakeStore[T](SimpleTypedStore[BlakeHashKey, T]):
    """Typed store specialized for Blake3-hash keys."""

    def __init__(self, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._keygen = get_blake_hash_generic


def make_uuid_store[T](
    *, value_type: type[T], size_limit: PositiveInt | None = None
) -> UUIDStore[T]:
    """Create a UUIDStore with the specified value type."""
    return UUIDStore[T](_value_type=value_type, store={}, _size_limit=size_limit)


def make_blake_store[T](
    *, value_type: type[T], size_limit: PositiveInt | None = None
) -> BlakeStore[T]:
    """Create a BlakeStore with the specified value type."""
    return BlakeStore[T](_value_type=value_type, store={}, _size_limit=size_limit)


__all__ = (
    "BlakeStore",
    "CodeChunk",
    "DiscoveredFile",
    "SearchResult",
    "Span",
    "SpanGroup",
    "UUIDStore",
    "make_blake_store",
    "make_uuid_store",
)
