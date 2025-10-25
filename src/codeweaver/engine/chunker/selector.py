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

from pathlib import Path
from typing import TYPE_CHECKING, Any

from codeweaver.core.language import SemanticSearchLanguage
from codeweaver.engine.chunker.base import BaseChunker
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

    def select_for_file(self, file: DiscoveredFile) -> BaseChunker:
        """Select best chunker for given file (creates fresh instance).

        Analyzes the file's extension to determine the appropriate chunking
        strategy. Always creates a new chunker instance to ensure isolation
        between file operations.

        Args:
            file: DiscoveredFile with path attribute for language detection

        Returns:
            Fresh BaseChunker instance appropriate for file's language.
            Currently returns SemanticChunker for supported languages or
            SemanticChunker with Python fallback (DelimiterChunker TODO).

        Notes:
            - Each call creates a new chunker instance (no reuse)
            - Falls back to delimiter chunking on semantic parse errors
            - Logs warnings when fallback occurs
            - TODO: Implement DelimiterChunker for proper fallback

        Examples:
            >>> from pathlib import Path
            >>> from codeweaver.core.discovery import DiscoveredFile
            >>>
            >>> file = DiscoveredFile.from_path(Path("example.py"))
            >>> chunker1 = selector.select_for_file(file)
            >>> chunker2 = selector.select_for_file(file)
            >>> assert chunker1 is not chunker2  # Fresh instances
        """
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

        # Delimiter fallback (TODO: implement DelimiterChunker)
        # For now, return semantic even for unsupported (will fail gracefully)
        logger.warning(
            "DelimiterChunker not yet implemented. Attempting semantic for %s",
            file.path,
            extra={"file_path": str(file.path), "detected_language": str(language)},
        )
        return SemanticChunker(
            self.governor,
            SemanticSearchLanguage.PYTHON,  # default fallback
        )

    def _detect_language(self, file: DiscoveredFile) -> SemanticSearchLanguage | str:
        """Detect language from file extension.

        Uses the SemanticSearchLanguage.from_extension() method to map file
        extensions to language enums. Returns the extension string if no
        mapping is found.

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
        result = SemanticSearchLanguage.from_extension(ext)
        if result is not None:
            return result

        # Unknown language, return extension string
        return ext.lstrip(".").lower()


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
        >>> # from codeweaver.engine.chunker.delimiter import DelimiterChunker  # TODO
        >>>
        >>> primary = SemanticChunker(governor, SemanticSearchLanguage.PYTHON)
        >>> # fallback = DelimiterChunker(governor, LanguageFamily.C_LIKE)  # TODO
        >>> # chunker = GracefulChunker(primary, fallback)
        >>>
        >>> # This will try semantic first, fall back on error
        >>> # chunks = chunker.chunk(content, file_path=path)

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
        self, content: str, *, file_path: Path | None = None, context: dict[str, Any] | None = None
    ) -> list[CodeChunk]:
        """Try primary chunker, fall back on error.

        Attempts to chunk content using the primary chunker. If any exception
        occurs, logs a warning and retries with the fallback chunker.

        Args:
            content: Source code content to chunk
            file_path: Optional file path for context and logging
            context: Optional additional context for chunking

        Returns:
            List of CodeChunk objects from either primary or fallback chunker

        Raises:
            Any exception raised by the fallback chunker. Primary exceptions
            are caught and logged but not propagated.

        Examples:
            >>> content = "def foo(): pass"
            >>> chunks = graceful_chunker.chunk(content, file_path=Path("test.py"))
            >>> # Returns chunks from primary if successful, fallback on error
        """
        try:
            return self.primary.chunk(content, file_path=file_path, context=context)
        except Exception as e:
            logger.warning(
                "Primary chunker failed: %s. Using fallback.",
                e,
                extra={
                    "file_path": str(file_path) if file_path else None,
                    "primary_chunker": type(self.primary).__name__,
                    "fallback_chunker": type(self.fallback).__name__,
                    "error_type": type(e).__name__,
                },
                exc_info=True,
            )
            return self.fallback.chunk(content, file_path=file_path, context=context)


__all__ = ("ChunkerSelector", "GracefulChunker")
