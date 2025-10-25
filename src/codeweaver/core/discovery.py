# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Defines the DiscoveredFile dataclass representing files found during project scanning."""

from __future__ import annotations

import contextlib

from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, cast

from pydantic import AfterValidator, Field, NonNegativeInt, computed_field
from pydantic.dataclasses import dataclass

from codeweaver.common.utils import get_git_branch, sanitize_unicode, set_relative_path
from codeweaver.core.chunks import CodeChunk
from codeweaver.core.language import is_semantic_config_ext
from codeweaver.core.metadata import ExtKind
from codeweaver.core.stores import BlakeHashKey, BlakeKey, get_blake_hash
from codeweaver.core.types.models import DATACLASS_CONFIG, DataclassSerializationMixin


if TYPE_CHECKING:
    from ast_grep_py import SgRoot

    from codeweaver.core.types import AnonymityConversion, FilteredKeyT
    from codeweaver.semantic.ast_grep import FileThing


@dataclass(frozen=True, slots=True, config=DATACLASS_CONFIG)
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
            default_factory=lambda data: get_blake_hash(data["path"].read_bytes()),
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
    ]

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        from codeweaver.core.types import AnonymityConversion, FilteredKey

        return {
            FilteredKey("path"): AnonymityConversion.HASH,
            FilteredKey("file_hash"): AnonymityConversion.FORBIDDEN,
            FilteredKey("git_branch"): AnonymityConversion.HASH,
        }

    @classmethod
    def from_path(cls, path: Path, *, file_hash: BlakeKey | None = None) -> DiscoveredFile | None:
        """Create a DiscoveredFile from a file path."""
        branch = get_git_branch(path if path.is_dir() else path.parent) or "main"
        if ext_kind := (ext_kind := ExtKind.from_file(path)):
            new_hash = get_blake_hash(path.read_bytes())
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

    @property
    def raw_contents(self) -> bytes:
        """Return the raw contents of the file."""
        with contextlib.suppress(Exception):
            return self.path.read_bytes()
        return b""

    @property
    def is_config_file(self) -> bool:
        """Return True if the file is a recognized configuration file."""
        return is_semantic_config_ext(self.path.suffix)

    @property
    def ast(self) -> FileThing[SgRoot] | None:
        """Return the AST of the file, if applicable."""
        from codeweaver.core.language import SemanticSearchLanguage

        if (
            self.is_text
            and self.ext_kind.language in SemanticSearchLanguage
            and isinstance(self.ext_kind.language, SemanticSearchLanguage)
        ):
            from codeweaver.semantic.ast_grep import FileThing

            return cast(FileThing[SgRoot], FileThing.from_file(self.path))
        return None

    @staticmethod
    def normalize_content(content: str | bytes | bytearray) -> str:
        """Normalize file content by ensuring it's a UTF-8 string."""
        return sanitize_unicode(content)
