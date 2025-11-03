# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Represents a search result from vector search operations."""

from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any

from pydantic import AfterValidator, ConfigDict, Field, NonNegativeFloat

from codeweaver.agent_api.find_code.types import StrategizedQuery
from codeweaver.common.utils import set_relative_path
from codeweaver.core.chunks import CodeChunk
from codeweaver.core.discovery import DiscoveredFile
from codeweaver.core.metadata import Metadata
from codeweaver.core.types.models import BasedModel


if TYPE_CHECKING:
    from codeweaver.core.types.aliases import FilteredKeyT
    from codeweaver.core.types.enum import AnonymityConversion


class SearchResult(BasedModel):
    """Result from vector search operations."""

    model_config = ConfigDict(validate_assignment=False, extra="allow")

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
    strategized_query: Annotated[
        StrategizedQuery | None, Field(description="""The query used for the search""")
    ] = None

    # Fields for hybrid search and rescoring (set dynamically by find_code)
    dense_score: NonNegativeFloat | None = None
    sparse_score: NonNegativeFloat | None = None
    rerank_score: NonNegativeFloat | None = None
    relevance_score: NonNegativeFloat | None = None

    @property
    def chunk(self) -> CodeChunk | str:
        """Alias for content field for backward compatibility."""
        return self.content

    @property
    def file(self) -> Any:
        """Property to access file info from chunk.

        Returns the file info from the chunk if available, otherwise returns
        a minimal object with just the path.
        """
        if isinstance(self.content, CodeChunk) and hasattr(self.content, "file"):
            return DiscoveredFile.from_chunk(self.content)

        # Return minimal file-like object with path
        class _FileInfo:
            def __init__(self, path: Path) -> None:
                self.path = path

        return _FileInfo(self.file_path) if self.file_path else None

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        from codeweaver.core.types import AnonymityConversion, FilteredKey

        base = {FilteredKey("content"): AnonymityConversion.TEXT_COUNT}
        return {
            FilteredKey("file_path"): AnonymityConversion.BOOLEAN,
            FilteredKey("metadata"): AnonymityConversion.BOOLEAN,
        } | (base if isinstance(self.content, str) else {})


__all__ = ("SearchResult",)
