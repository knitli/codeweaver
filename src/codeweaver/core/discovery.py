# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""File discovery and metadata extraction for CodeWeaver."""

from __future__ import annotations

import mimetypes
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, Self

from pydantic import UUID7, ConfigDict, Field, NonNegativeInt

from codeweaver.common.utils import uuid7
from codeweaver.core.metadata import ExtKind
from codeweaver.core.stores import BlakeHashKey, get_blake_hash
from codeweaver.core.types.models import BASEDMODEL_CONFIG, BasedModel


if TYPE_CHECKING:
    from codeweaver.core.types import AnonymityConversion, FilteredKeyT


class DiscoveredFile(BasedModel):
    """Represents a discovered file with metadata.
    
    This class stores information about files discovered during indexing,
    including their paths, content hashes, sizes, and language metadata.
    """

    model_config = BASEDMODEL_CONFIG | ConfigDict(defer_build=True)

    # File identification
    path: Annotated[Path, Field(description="""Absolute path to the file""")]
    
    abs_path: Annotated[Path, Field(description="""Absolute path to the file (alias for path)""")]
    
    # File metadata
    file_hash: Annotated[
        BlakeHashKey,
        Field(description="""Blake3 hash of the file content for deduplication"""),
    ]
    
    size: Annotated[NonNegativeInt, Field(description="""File size in bytes""")]
    
    ext_kind: Annotated[
        ExtKind | None,
        Field(description="""File extension and language kind information"""),
    ] = None
    
    # Identification
    source_id: Annotated[
        UUID7,
        Field(
            description="""Unique identifier for this file""",
            default_factory=uuid7,
        ),
    ]
    
    # Content type
    is_text: Annotated[
        bool,
        Field(
            description="""Whether the file is a text file that can be indexed""",
            default=True,
        ),
    ]

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        from codeweaver.core.types import AnonymityConversion, FilteredKey

        return {
            FilteredKey("path"): AnonymityConversion.BOOLEAN,
            FilteredKey("abs_path"): AnonymityConversion.BOOLEAN,
            FilteredKey("file_hash"): AnonymityConversion.HASH,
        }

    @classmethod
    def from_path(cls, path: Path | str) -> Self | None:
        """Create a DiscoveredFile from a file path.
        
        Args:
            path: Path to the file to discover
            
        Returns:
            DiscoveredFile instance if the file exists and can be read, None otherwise
        """
        path = Path(path) if isinstance(path, str) else path
        
        # Check if file exists and is a file
        if not path.exists() or not path.is_file():
            return None
        
        try:
            # Get absolute path
            abs_path = path.resolve()
            
            # Read file content for hashing
            content = path.read_bytes()
            file_hash = get_blake_hash(content)
            
            # Get file size
            size = len(content)
            
            # Determine extension kind
            ext_kind = ExtKind.from_file(path)
            
            # Check if file is text
            is_text = cls._is_text_file(path, content)
            
            return cls(
                path=abs_path,
                abs_path=abs_path,
                file_hash=file_hash,
                size=size,
                ext_kind=ext_kind,
                is_text=is_text,
            )
        except Exception:
            # If we can't read the file or determine its properties, return None
            return None

    @staticmethod
    def _is_text_file(path: Path, content: bytes) -> bool:
        """Determine if a file is a text file.
        
        Args:
            path: Path to the file
            content: File content as bytes
            
        Returns:
            True if the file appears to be a text file, False otherwise
        """
        # Check mimetype first
        mime_type, _ = mimetypes.guess_type(str(path))
        if mime_type:
            if mime_type.startswith("text/"):
                return True
            if mime_type in ("application/json", "application/xml", "application/javascript"):
                return True
        
        # If we have an ext_kind with a known language, it's likely text
        ext_kind = ExtKind.from_file(path)
        if ext_kind is not None:
            return True
        
        # Check for binary content (heuristic: look for null bytes in first KB)
        sample_size = min(1024, len(content))
        if sample_size > 0:
            sample = content[:sample_size]
            # If there are null bytes, it's probably binary
            if b"\x00" in sample:
                return False
            
            # Try to decode as UTF-8
            try:
                sample.decode("utf-8")
                return True
            except UnicodeDecodeError:
                return False
        
        # Empty file - consider it text
        return True

    def serialize_for_cli(self) -> dict[str, Any]:
        """Serialize the DiscoveredFile for CLI display.
        
        Returns a dict suitable for rendering in CLI output formats.
        """
        return {
            "path": str(self.path),
            "size": self.size,
            "file_hash": self.file_hash,
            "language": self.ext_kind.serialize_for_cli() if self.ext_kind else None,
            "is_text": self.is_text,
        }


# Rebuild model to resolve forward references
if not DiscoveredFile.__pydantic_complete__:
    _ = DiscoveredFile.model_rebuild()


__all__ = ("DiscoveredFile",)
