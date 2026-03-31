# SPDX-FileCopyrightText: 2026 Knitli Inc.
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

import contextlib
import logging

from typing import TYPE_CHECKING, Any

import textcase

from codeweaver.core import ConfigLanguage, SemanticSearchLanguage
from codeweaver.engine.chunker.base import BaseChunker
from codeweaver.engine.chunker.delimiter import DelimiterChunker
from codeweaver.engine.chunker.exceptions import FileTooLargeError, ParseError
from codeweaver.engine.chunker.semantic import SemanticChunker


if TYPE_CHECKING:
    from codeweaver.core import CodeChunk, DiscoveredFile
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
        >>> from codeweaver.core import DiscoveredFile
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
        3. Fall back to DelimiterChunker
        4. Return fresh chunker instance (never reused across files)
    """

    def __init__(self, governor: ChunkGovernor, tokenizer: Any | None = None) -> None:
        """Initialize selector with chunk governor.

        Args:
            governor: ChunkGovernor instance for resource management and
                configuration. Passed to created chunker instances.
            tokenizer: Optional tokenizer for accurate token counting.
        """
        self.governor = governor
        self.tokenizer = tokenizer

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

        from codeweaver.core import DiscoveredFile

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
            >>> from codeweaver.core import DiscoveredFile
            >>>
            >>> file = DiscoveredFile.from_path(Path("example.py"))
            >>> chunker1 = selector.select_for_file(file)
            >>> chunker2 = selector.select_for_file(file)
            >>> assert chunker1 is not chunker2  # Fresh instances
        """
        if self.governor.settings is not None:
            max_size_bytes = self.governor.settings.performance.max_file_size_mb * 1024 * 1024
            try:
                file_size = file.absolute_path.stat().st_size
            except OSError as e:
                logger.warning(
                    "Could not stat file %s: %s",
                    file.absolute_path,
                    e,
                    extra={"file_path": str(file.absolute_path), "error": str(e)},
                )
            else:
                if file_size > max_size_bytes:
                    file_size_mb = file_size / (1024 * 1024)
                    raise FileTooLargeError(
                        f"File {file.absolute_path} exceeds maximum size limit "
                        f"({file_size_mb:.2f} MB > "
                        f"{self.governor.settings.performance.max_file_size_mb} MB)",
                        file_size_mb=file_size_mb,
                        max_size_mb=self.governor.settings.performance.max_file_size_mb,
                        file_path=str(file.absolute_path),
                    )
        is_large_file = False
        with contextlib.suppress(OSError, AttributeError):
            if file.absolute_path.stat().st_size > 500 * 1024:
                is_large_file = True
        language = self._detect_language(file)
        if isinstance(language, SemanticSearchLanguage) and (not is_large_file):
            try:
                semantic_chunker = SemanticChunker(self.governor, language, self.tokenizer)
                language_name = (
                    language.variable if hasattr(language, "variable") else str(language)
                )
                fallback = DelimiterChunker(self.governor, language=language_name)
            except (ParseError, NotImplementedError) as e:
                logger.warning(
                    "Semantic chunking unavailable for %s: %s. Using delimiter fallback.",
                    file.path,
                    e,
                    extra={"file_path": str(file.path), "language": str(language)},
                )
            else:
                return GracefulChunker(primary=semantic_chunker, fallback=fallback)
        language_repr = (
            language.variable
            if isinstance(language, SemanticSearchLanguage | ConfigLanguage)
            else language
        )
        if isinstance(language_repr, ConfigLanguage):
            language_repr = language_repr.variable
        logger.info(
            "Using DelimiterChunker for %s (detected language: %s)",
            file.path,
            language_repr,
            extra={"file_path": str(file.path), "detected_language": language_repr},
        )
        return DelimiterChunker(self.governor, language=language_repr)

    def _detect_language_from_custom_ext(
        self, file_ext: str
    ) -> SemanticSearchLanguage | ConfigLanguage | str | None:
        """Resolve a file extension against custom delimiter extension maps in settings.

        Called only when the standard extension registry has no match.

        Args:
            file_ext: File extension including the leading dot (e.g. ``'.myl'``).

        Returns:
            Detected language (enum or plain string), or ``None`` when no
            custom mapping is found.
        """
        if self.governor.settings is None:
            return None

        custom_delimiters = getattr(self.governor.settings, "custom_delimiters", None)
        if not custom_delimiters:
            return None

        for custom_delim in custom_delimiters:
            if lang := self._match_custom_ext_pair(custom_delim, file_ext):
                return lang
        return None

    @staticmethod
    def _match_custom_ext_pair(  # noqa: C901
        custom_delim: object, file_ext: str
    ) -> SemanticSearchLanguage | ConfigLanguage | str | None:
        """Return the language for a matching extension pair in *custom_delim*.

        Args:
            custom_delim: A ``CustomDelimiter`` instance from settings.
            file_ext: File extension including the leading dot.

        Returns:
            Matching language, or ``None``.
        """
        extensions = getattr(custom_delim, "extensions", None)
        if not extensions:
            return None
        for pair in extensions:
            if not (hasattr(pair, "ext") and pair.ext):
                continue
            pair_ext = str(pair.ext)
            if not pair_ext.startswith("."):
                pair_ext = f".{pair_ext}"
            if pair_ext.lower() != file_ext.lower():
                continue
            pair_lang = getattr(pair, "language", None)
            delim_lang = getattr(custom_delim, "language", None)
            # Prefer per-extension language over the top-level custom_delim language.
            if pair_lang is not None:
                if delim_lang is not None and str(delim_lang) != str(pair_lang):
                    logger.warning(
                        "Custom delimiter language mismatch for extension %s: "
                        "using pair.language=%r over custom_delim.language=%r",
                        pair_ext,
                        pair_lang,
                        delim_lang,
                    )
                if isinstance(pair_lang, SemanticSearchLanguage | ConfigLanguage):
                    return pair_lang
                return textcase.snake(str(pair_lang))
            if delim_lang is not None:
                if isinstance(delim_lang, SemanticSearchLanguage | ConfigLanguage):
                    return delim_lang
                return textcase.snake(str(delim_lang))
        return None

    def _detect_language(
        self, file: DiscoveredFile
    ) -> SemanticSearchLanguage | ConfigLanguage | str:
        """Detect language from file extension.

        Uses the SemanticSearchLanguage.from_extension() method to map file
        extensions to language enums. Returns the extension string if no
        mapping is found.

        Also checks custom delimiter extension mappings from settings when the
        standard extension registry has no match, allowing users to introduce
        new languages via ``ChunkerSettings.custom_delimiters``.

        Args:
            file: DiscoveredFile with path attribute containing extension

        Returns:
            SemanticSearchLanguage enum if supported, else a plain language
            name string (without leading dot, lowercased)

        Examples:
            >>> file_py = DiscoveredFile.from_path(Path("script.py"))
            >>> selector._detect_language(file_py)
            <SemanticSearchLanguage.PYTHON: 'python'>

            >>> file_xyz = DiscoveredFile.from_path(Path("data.xyz"))
            >>> selector._detect_language(file_xyz)
            'xyz'
        """
        if file.ext_category:
            return (
                file.ext_category.language
                if isinstance(file.ext_category.language, (SemanticSearchLanguage, ConfigLanguage))
                else str(file.ext_category.language)
            )

        file_ext = file.absolute_path.suffix  # includes the leading dot
        if custom_lang := self._detect_language_from_custom_ext(file_ext):
            return custom_lang
        return file_ext.lstrip(".").lower()


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
        """Try primary chunker, fall back on error."""
        try:
            return self.primary.chunk(content, file=file, context=context)
        except Exception as e:
            from codeweaver.engine.chunker.exceptions import ChunkLimitExceededError

            error_msg = str(e).splitlines()[0] if str(e) else type(e).__name__
            if isinstance(e, ChunkLimitExceededError):
                logger.info(
                    "Switching to fallback chunker for %s: %s",
                    file.path if file else "<unknown>",
                    error_msg,
                )
            else:
                logger.warning(
                    "Primary chunker (%s) failed for %s: %s. Using fallback (%s).",
                    type(self.primary).__name__,
                    file.path if file else "<unknown>",
                    error_msg,
                    type(self.fallback).__name__,
                    extra={
                        "file_path": str(file.path) if file else None,
                        "primary_chunker": type(self.primary).__name__,
                        "fallback_chunker": type(self.fallback).__name__,
                        "error_type": type(e).__name__,
                    },
                )
            logger.debug("Primary chunker failure details:", exc_info=True)
            return self.fallback.chunk(content, file=file, context=context)


__all__ = ("ChunkerSelector", "GracefulChunker")
