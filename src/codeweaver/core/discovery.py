# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Defines the DiscoveredFile dataclass representing files found during project scanning."""

from __future__ import annotations

import contextlib
import logging

from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, cast

from pydantic import UUID7, AfterValidator, Field, NonNegativeInt, computed_field, model_validator
from pydantic.dataclasses import dataclass

from codeweaver.common.utils import get_git_branch, sanitize_unicode, set_relative_path, uuid7
from codeweaver.common.utils.git import MISSING, Missing
from codeweaver.core.chunks import CodeChunk
from codeweaver.core.language import is_semantic_config_ext
from codeweaver.core.metadata import ExtKind
from codeweaver.core.stores import BlakeHashKey, BlakeKey, get_blake_hash
from codeweaver.core.types.dataclasses import DATACLASS_CONFIG, DataclassSerializationMixin


if TYPE_CHECKING:
    from ast_grep_py import SgRoot

    from codeweaver.core.types import AnonymityConversion, FilteredKeyT
    from codeweaver.semantic.ast_grep import FileThing


logger = logging.getLogger(__name__)


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
    ext_kind: ExtKind | None = None
    project_path: Path | None = None

    _file_hash: Annotated[
        BlakeHashKey | None,
        Field(
            description="""blake3 hash of the file contents. File hashes are from non-normalized content, so two files with different line endings, white spaces, unicode characters, etc. will have different hashes."""
        ),
    ] = None
    _git_branch: Annotated[
        str | Missing, Field(description="""Git branch the file was discovered in, if detected.""")
    ] = MISSING

    source_id: Annotated[
        UUID7,
        Field(
            description="Unique identifier for the source of the file. All chunks from this file will share this ID."
        ),
    ] = uuid7()

    @model_validator(mode="before")
    @classmethod
    def _ensure_ext_kind(cls, data: Any) -> Any:
        """Ensure ext_kind is set based on path if not provided."""
        if (
            isinstance(data, dict)
            and ("ext_kind" not in data or data["ext_kind"] is None)
            and (path := data["path"])  # type: ignore
            and isinstance(path, (Path, str))
        ):
            data["ext_kind"] = ExtKind.from_file(path if isinstance(path, Path) else Path(path))
        return data  # type: ignore

    def __init__(
        self,
        path: Path,
        ext_kind: ExtKind | None = None,
        file_hash: BlakeKey | None = None,
        git_branch: str | None = None,
        project_path: Path | None = None,
        **kwargs: Any,
    ) -> None:
        """Initialize DiscoveredFile with optional file_hash and git_branch."""
        object.__setattr__(self, "path", path)
        object.__setattr__(self, "project_path", project_path)
        if ext_kind:
            object.__setattr__(self, "ext_kind", ext_kind)
        else:
            object.__setattr__(self, "ext_kind", ExtKind.from_file(path))
        if file_hash:
            object.__setattr__(self, "_file_hash", file_hash)
        elif path.is_file():
            object.__setattr__(self, "_file_hash", get_blake_hash(path.read_bytes()))
        else:
            # For non-existent files (e.g., test fixtures), use None
            object.__setattr__(self, "_file_hash", None)
        if git_branch and git_branch is not Missing:
            object.__setattr__(self, "_git_branch", git_branch)
        elif path.exists():
            object.__setattr__(self, "_git_branch", get_git_branch(path) or Missing)
        else:
            object.__setattr__(self, "_git_branch", Missing)
        object.__setattr__(self, "source_id", kwargs.get("source_id", uuid7()))
        super().__init__(**kwargs)

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        from codeweaver.core.types import AnonymityConversion, FilteredKey

        return {
            FilteredKey("path"): AnonymityConversion.HASH,
            FilteredKey("git_branch"): AnonymityConversion.HASH,
        }

    @classmethod
    def from_path(
        cls, path: Path, *, file_hash: BlakeKey | None = None, project_path: Path | None = None
    ) -> DiscoveredFile | None:
        """Create a DiscoveredFile from a file path."""
        branch = get_git_branch(path if path.is_dir() else path.parent) or "main"
        if ext_kind := ExtKind.from_file(path):
            new_hash = get_blake_hash(path.read_bytes())
            if file_hash and new_hash != file_hash:
                logger.warning(
                    "Provided file_hash does not match computed hash for %s. Using computed hash.",
                    path,
                )

            # Ensure path is relative to project_path if provided
            final_path = set_relative_path(path, base_path=project_path) or path

            return cls(
                path=final_path,
                ext_kind=ext_kind,
                file_hash=new_hash,
                git_branch=cast(str, branch),
                project_path=project_path,
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
    def git_branch(self) -> str | Missing:
        """Return the git branch the file was discovered in, if available."""
        if self._git_branch is Missing:
            return get_git_branch(self.path.parent) or Missing  # type: ignore
        return self._git_branch

    @property
    def absolute_path(self) -> Path:
        """Return the absolute path to the file."""
        if self.path.is_absolute():
            return self.path
        if self.project_path:
            return self.project_path / self.path

        from codeweaver.core.utils import get_project_path

        try:
            return get_project_path() / self.path
        except FileNotFoundError:
            return self.path

    @computed_field
    @property
    def size(self) -> NonNegativeInt:
        """Return the size of the file in bytes."""
        if self.ext_kind and self.absolute_path.exists() and self.absolute_path.is_file():
            return self.absolute_path.stat().st_size
        return 0  # Return 0 for non-existent files (e.g., test fixtures)

    @computed_field
    @property
    def file_hash(self) -> BlakeHashKey:
        """Return the blake3 hash of the file contents, if available."""
        if self._file_hash is not None:
            return self._file_hash
        # We can look at Difftastic to see how they do AST-based diffs/hashes
        # Try to compute hash if file exists
        if self.path.exists() and self.path.is_file():
            content_hash = get_blake_hash(self.path.read_bytes())
            with contextlib.suppress(Exception):
                object.__setattr__(self, "_file_hash", content_hash)
            return content_hash

        # For non-existent files, return hash of empty bytes (for test fixtures)
        return get_blake_hash(b"")

    def is_same(self, other_path: Path) -> bool:
        """Checks if a file at other_path is the same as this one, by comparing blake3 hashes.

        The other can be in a different location (paths not the same), useful for checking if a file has been moved or copied, or deduping files (we can just point to one copy).
        """
        if other_path.is_file() and other_path.exists():
            file = type(self).from_path(other_path)
            return bool(file and file.file_hash == self.file_hash)
        return False

    @staticmethod
    def is_path_binary(path: Path) -> bool:
        """Check if a file at path is binary by reading its first 1024 bytes."""
        try:
            with path.open("rb") as f:
                chunk = f.read(1024)
                if not chunk:
                    return False
                if b"\0" in chunk:
                    return True
                text_characters = bytearray({7, 8, 9, 10, 12, 13, 27} | set(range(0x20, 0x100)))
                nontext = chunk.translate(None, text_characters)
                return bool(nontext) / len(chunk) > 0.30
        except Exception:
            return False

    @staticmethod
    def is_path_text(path: Path) -> bool:
        """Check if a file at path is text."""
        if DiscoveredFile.is_path_binary(path):
            return False
        try:
            content = path.read_text(encoding="utf-8", errors="replace")
            return bool(content.strip())
        except Exception:
            return False

    @computed_field
    @cached_property
    def is_binary(self) -> bool:
        """Check if a file is binary by reading its first 1024 bytes."""
        return self.is_path_binary(self.path)

    @computed_field
    @cached_property
    def is_text(self) -> bool:
        """Check if a file is text by reading its first 1024 bytes."""
        return self.is_path_text(self.path)

    @property
    def contents(self) -> str:
        """Return the normalized contents of the file."""
        with contextlib.suppress(Exception):
            return self.normalize_content(self.absolute_path.read_text(errors="replace"))
        return ""

    @property
    def raw_contents(self) -> bytes:
        """Return the raw contents of the file."""
        with contextlib.suppress(Exception):
            return self.absolute_path.read_bytes()
        return b""

    @property
    def is_config_file(self) -> bool:
        """Return True if the file is a recognized configuration file."""
        return is_semantic_config_ext(self.absolute_path.suffix)

    def ast(self) -> FileThing[SgRoot] | None:
        """Return the AST of the file, if applicable."""
        from codeweaver.core.language import SemanticSearchLanguage

        if (
            self.is_text
            and self.ext_kind is not None
            and self.ext_kind.language in SemanticSearchLanguage
            and isinstance(self.ext_kind.language, SemanticSearchLanguage)
        ):
            from codeweaver.semantic.ast_grep import FileThing

            return cast(FileThing[SgRoot], FileThing.from_file(self.absolute_path))
        return None

    @staticmethod
    def normalize_content(content: str | bytes | bytearray) -> str:
        """Normalize file content by ensuring it's a UTF-8 string."""
        return sanitize_unicode(content)
