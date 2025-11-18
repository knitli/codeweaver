# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Intelligent chunker selection based on file language and capabilities.

This module implements the ChunkerSelector which routes files to the appropriate
chunker implementation based on language detection and capability analysis. It
provides graceful degradation from semantic to delimiter-based chunking when
parsing fails or languages are unsupported.

The selector creates fresh chunker instances per file to ensure isolation and
prevent state contamination across chunking operations.
"""

from __future__ import annotations

import logging

from typing import TYPE_CHECKING, Any

from codeweaver.core.language import ConfigLanguage, SemanticSearchLanguage
from codeweaver.engine.chunker.base import BaseChunker
from codeweaver.engine.chunker.delimiter import DelimiterChunker
from codeweaver.engine.chunker.exceptions import ParseError
from codeweaver.engine.chunker.semantic import SemanticChunker


if TYPE_CHECKING:
    from codeweaver.core.chunks import CodeChunk
    from codeweaver.core.discovery import DiscoveredFile
    from codeweaver.engine.chunker.base import ChunkGovernor


logger = logging.getLogger(__name__)


class ChunkerSelector:
    """Selects appropriate chunker based on file language and capabilities.

    The selector uses language detection from file extensions to determine which
    chunking strategy to employ. It prefers semantic (AST-based) chunking for
    supported languages and gracefully falls back to delimiter-based chunking
    when semantic parsing fails or the language is unsupported.

    Attributes:
        governor: ChunkGovernor instance providing resource limits and configuration

    Examples:
        Basic usage with file discovery:

        >>> from codeweaver.engine.chunker.base import ChunkGovernor
        >>> from codeweaver.core.discovery import DiscoveredFile
        >>> from pathlib import Path
        >>>
        >>> governor = ChunkGovernor(capabilities=(...))
        >>> selector = ChunkerSelector(governor)
        >>>
        >>> # Select chunker for a Python file
        >>> file = DiscoveredFile.from_path(Path("script.py"))
        >>> chunker = selector.select_for_file(file)
        >>> # Returns SemanticChunker for Python
        >>>
        >>> # Process the file
        >>> chunks = chunker.chunk(file.path.read_text(), file_path=file.path)

    Selection Algorithm:
        1. Detect language from file extension using SemanticSearchLanguage
        2. If language is in SemanticSearchLanguage enum:
           - Attempt to create SemanticChunker
           - On ParseError or NotImplementedError, log warning and fall back
        3. Fall back to DelimiterChunker (TODO: not yet implemented)
        4. Return fresh chunker instance (never reused across files)
    """

    def __init__(self, governor: ChunkGovernor) -> None:
        """Initialize selector with chunk governor.

        Args:
            governor: ChunkGovernor instance for resource management and
                configuration. Passed to created chunker instances.
        """
        self.governor = governor

    def select_for_file_path(self, file_path: Any) -> BaseChunker:
        """Select best chunker for given file path (convenience method).

        Creates a DiscoveredFile from the path and delegates to select_for_file.
        This is a convenience method for when you only have a Path object.

        Args:
            file_path: Path to the file (Path object or path-like)

        Returns:
            Fresh BaseChunker instance appropriate for file's language.

        Examples:
            >>> from pathlib import Path
            >>> file_path = Path("example.py")
            >>> chunker = selector.select_for_file_path(file_path)
        """
        from pathlib import Path

        from codeweaver.core.discovery import DiscoveredFile

        file_path = file_path if isinstance(file_path, Path) else Path(file_path)
        if discovered_file := DiscoveredFile.from_path(file_path):
            return self.select_for_file(discovered_file)
        return DelimiterChunker(self.governor, language="unknown")

    def select_for_file(self, file: DiscoveredFile) -> BaseChunker:
        """Select best chunker for given file (creates fresh instance).

        Analyzes the file's extension to determine the appropriate chunking
        strategy. Always creates a new chunker instance to ensure isolation
        between file operations.

        Args:
            file: DiscoveredFile with path attribute for language detection

        Returns:
            Fresh BaseChunker instance appropriate for file's language.
            Returns SemanticChunker for supported languages or
            DelimiterChunker for unsupported languages.

        Notes:
            - Each call creates a new chunker instance (no reuse)
            - Falls back to DelimiterChunker for unsupported languages
            - Falls back to delimiter chunking on semantic parse errors
            - Logs warnings when fallback occurs
            - Checks max_file_size_mb from settings before chunking

        Examples:
            >>> from pathlib import Path
            >>> from codeweaver.core.discovery import DiscoveredFile
            >>>
            >>> file = DiscoveredFile.from_path(Path("example.py"))
            >>> chunker1 = selector.select_for_file(file)
            >>> chunker2 = selector.select_for_file(file)
            >>> assert chunker1 is not chunker2  # Fresh instances
        """
        # Check file size limit if settings are available
        if self.governor.settings is not None:
            max_size_bytes = self.governor.settings.performance.max_file_size_mb * 1024 * 1024
            try:
                file_size = file.path.stat().st_size
                if file_size > max_size_bytes:
                    logger.warning(
                        "File %s exceeds max size limit (%d MB > %d MB). Skipping chunking.",
                        file.path,
                        file_size / (1024 * 1024),
                        self.governor.settings.performance.max_file_size_mb,
                        extra={
                            "file_path": str(file.path),
                            "file_size_mb": file_size / (1024 * 1024),
                            "max_size_mb": self.governor.settings.performance.max_file_size_mb,
                        },
                    )
                    # Return empty chunker or raise exception
                    # For now, return semantic chunker which will handle it gracefully
                    # TODO: Consider returning a NullChunker or raising FileTooLargeError
            except OSError as e:
                logger.warning(
                    "Could not stat file %s: %s",
                    file.path,
                    e,
                    extra={"file_path": str(file.path), "error": str(e)},
                )

        language = self._detect_language(file)

        # Try semantic first for supported languages
        if isinstance(language, SemanticSearchLanguage):
            try:
                return SemanticChunker(self.governor, language)
            except (ParseError, NotImplementedError) as e:
                logger.warning(
                    "Semantic chunking unavailable for %s: %s. Using delimiter fallback.",
                    file.path,
                    e,
                    extra={"file_path": str(file.path), "language": str(language)},
                )
        # Delimiter fallback for unsupported languages
        language_repr = (
            language.variable
            if isinstance(language, SemanticSearchLanguage | ConfigLanguage)
            else language
        )
        # Ensure language_repr is always a string
        if isinstance(language_repr, ConfigLanguage):
            language_repr = language_repr.variable
        logger.info(
            "Using DelimiterChunker for %s (detected language: %s)",
            file.path,
            language_repr,
            extra={"file_path": str(file.path), "detected_language": language_repr},
        )
        return DelimiterChunker(self.governor, language=language_repr)

    def _detect_language(
        self, file: DiscoveredFile
    ) -> SemanticSearchLanguage | ConfigLanguage | str:
        """Detect language from file extension.

        Uses the SemanticSearchLanguage.from_extension() method to map file
        extensions to language enums. Returns the extension string if no
        mapping is found.

        Also checks custom language mappings from settings if available.

        Args:
            file: DiscoveredFile with path attribute containing extension

        Returns:
            SemanticSearchLanguage enum if supported, else extension string
            (without leading dot, lowercased)

        Examples:
            >>> file_py = DiscoveredFile.from_path(Path("script.py"))
            >>> selector._detect_language(file_py)
            <SemanticSearchLanguage.PYTHON: 'python'>

            >>> file_xyz = DiscoveredFile.from_path(Path("data.xyz"))
            >>> selector._detect_language(file_xyz)
            'xyz'
        """
        ext = file.path.suffix

        # SemanticSearchLanguage.from_extension returns None for unknown
        return file.ext_kind.language if file.ext_kind else ext.lstrip(".").lower()


class GracefulChunker(BaseChunker):
    """Wraps chunker with graceful degradation to fallback.

    This wrapper implements a fallback pattern where a primary chunker is
    attempted first, and on any failure a fallback chunker is used instead.
    This enables robust chunking with seamless degradation from sophisticated
    strategies (semantic) to simpler ones (delimiter, text splitting).

    Attributes:
        primary: First chunker to attempt
        fallback: Backup chunker to use on primary failure

    Examples:
        Wrapping semantic chunker with delimiter fallback:

        >>> from codeweaver.engine.chunker.semantic import SemanticChunker
        >>> from codeweaver.engine.chunker.delimiter import DelimiterChunker
        >>>
        >>> primary = SemanticChunker(governor, SemanticSearchLanguage.PYTHON)
        >>> fallback = DelimiterChunker(governor, LanguageFamily.C_LIKE)
        >>> chunker = GracefulChunker(primary, fallback)
        >>>
        >>> # This will try semantic first, fall back on error
        >>> chunks = chunker.chunk(content, file_path=path)

    Error Handling:
        - Catches all exceptions from primary chunker
        - Logs warning with error details
        - Attempts fallback chunker
        - Propagates fallback chunker exceptions (no double-fallback)
    """

    def __init__(self, primary: BaseChunker, fallback: BaseChunker) -> None:
        """Initialize with primary and fallback chunkers.

        Args:
            primary: First chunker to try (e.g., SemanticChunker)
            fallback: Fallback chunker if primary fails (e.g., DelimiterChunker)

        Note:
            Both chunkers should use the same governor for consistent resource
            limits and configuration.
        """
        super().__init__(primary.governor)
        self.primary = primary
        self.fallback = fallback

    def chunk(
        self,
        content: str,
        *,
        file: DiscoveredFile | None = None,
        context: dict[str, Any] | None = None,
    ) -> list[CodeChunk]:
        """Try primary chunker, fall back on error.

        Attempts to chunk content using the primary chunker. If any exception
        occurs, logs a warning and retries with the fallback chunker.

        Args:
            content: Source code content to chunk
            file: Optional DiscoveredFile with metadata and source_id
            context: Optional additional context for chunking

        Returns:
            List of CodeChunk objects from either primary or fallback chunker

        Raises:
            Any exception raised by the fallback chunker. Primary exceptions
            are caught and logged but not propagated.

        Examples:
            >>> from codeweaver.core.discovery import DiscoveredFile
            >>> from pathlib import Path
            >>> content = "def foo(): pass"
            >>> file = DiscoveredFile.from_path(Path("test.py"))
            >>> chunks = graceful_chunker.chunk(content, file=file)
            >>> # Returns chunks from primary if successful, fallback on error
        """
        try:
            return self.primary.chunk(content, file=file, context=context)
        except Exception as e:
            logger.warning(
                "Primary chunker failed: %s. Using fallback.",
                e,
                extra={
                    "file_path": str(file.path) if file else None,
                    "primary_chunker": type(self.primary).__name__,
                    "fallback_chunker": type(self.fallback).__name__,
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
            return self.fallback.chunk(content, file=file, context=context)


__all__ = ("ChunkerSelector", "GracefulChunker")
