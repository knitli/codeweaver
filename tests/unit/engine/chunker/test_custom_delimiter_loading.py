# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Tests for custom delimiter loading from ChunkerSettings.

Covers:
- Custom delimiters are prepended (override built-in family patterns).
- Type-correct language comparison for SemanticSearchLanguage, ConfigLanguage,
  and plain LanguageName string values.
- Error handling: a single invalid pattern does not break loading.
- New-language detection in ChunkerSelector via custom extension mappings.
"""

from __future__ import annotations

from pathlib import Path
from typing import cast
from unittest.mock import Mock, patch

import pytest

from codeweaver.core import (
    ConfigLanguage,
    DelimiterPattern,
    ExtLangPair,
    LanguageName,
    SemanticSearchLanguage,
)
from codeweaver.core.types import DelimiterKind, FileExt
from codeweaver.core.types.aliases import LiteralStringT
from codeweaver.engine import ChunkGovernor, DelimiterChunker
from codeweaver.engine.config import ChunkerSettings, PerformanceSettings
from codeweaver.engine.config.chunker import CustomDelimiter
from codeweaver.providers import EmbeddingModelCapabilities


pytestmark = [pytest.mark.unit]


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_pattern(start: str = "myfunc", end: str = "endmyfunc") -> DelimiterPattern:
    """Return a minimal DelimiterPattern for test use."""
    return DelimiterPattern(
        starts=[start],
        ends=[end],
        kind=DelimiterKind.FUNCTION,
        inclusive=True,
        take_whole_lines=True,
        nestable=False,
    )


def _make_governor(settings: ChunkerSettings) -> ChunkGovernor:
    """Return a ChunkGovernor wired to *settings*."""
    mock_cap = Mock(spec=EmbeddingModelCapabilities)
    mock_cap.context_window = 2000
    mock_cap.max_batch_size = 100
    return ChunkGovernor(capabilities=(mock_cap,), settings=settings)


def _make_settings(custom_delimiters: list[CustomDelimiter]) -> ChunkerSettings:
    return ChunkerSettings(custom_delimiters=custom_delimiters, performance=PerformanceSettings())


def _make_mock_file(suffix: str, *, ext_category: object = None) -> Mock:
    """Return a minimal DiscoveredFile-like Mock."""
    mock_stat = Mock()
    mock_stat.st_size = 512

    mock_path = Mock(spec=Path)
    mock_path.stat.return_value = mock_stat
    mock_path.suffix = suffix
    mock_path.__str__ = Mock(return_value=f"file{suffix}")

    file = Mock()
    file.path = mock_path
    file.absolute_path = mock_path
    file.ext_category = ext_category
    return file


# ---------------------------------------------------------------------------
# Tests: delimiter loading (prepend / override)
# ---------------------------------------------------------------------------


@pytest.mark.benchmark
@pytest.mark.mock_only
@pytest.mark.performance
@pytest.mark.unit
class TestCustomDelimiterPrepend:
    """Custom delimiters are placed before family patterns so they take priority."""

    def test_custom_delimiter_is_first_for_known_language(self) -> None:
        """Custom delimiter for 'python' appears before built-in patterns."""
        pattern = _make_pattern("myfunc", "endmyfunc")
        # 'python' is a SemanticSearchLanguage; extensions are required when the
        # language name is not in the secondary ALL_LANGUAGES registry.
        ext = ExtLangPair(
            ext=FileExt(cast(LiteralStringT, ".py")), language=SemanticSearchLanguage.PYTHON
        )
        cd = CustomDelimiter(
            language=LanguageName(cast(LiteralStringT, "python")),
            extensions=[ext],
            delimiters=[pattern],
        )
        gov = _make_governor(_make_settings([cd]))
        chunker = DelimiterChunker(gov, language="python")
        assert chunker._delimiters, "Expected at least one delimiter"
        assert chunker._delimiters[0].start == "myfunc", (
            "Custom delimiter should be first (prepended)"
        )

    def test_family_patterns_still_present_after_custom(self) -> None:
        """Built-in family patterns remain alongside the custom delimiter."""
        pattern = _make_pattern()
        ext = ExtLangPair(
            ext=FileExt(cast(LiteralStringT, ".py")), language=SemanticSearchLanguage.PYTHON
        )
        cd = CustomDelimiter(
            language=LanguageName(cast(LiteralStringT, "python")),
            extensions=[ext],
            delimiters=[pattern],
        )
        gov = _make_governor(_make_settings([cd]))
        chunker = DelimiterChunker(gov, language="python")
        # More than 1 delimiter means family patterns were also loaded
        assert len(chunker._delimiters) > 1, "Family patterns should still be present"


# ---------------------------------------------------------------------------
# Tests: type-correct language comparison
# ---------------------------------------------------------------------------


@pytest.mark.benchmark
@pytest.mark.mock_only
@pytest.mark.performance
@pytest.mark.unit
class TestLanguageTypeComparison:
    """Language matching normalises SemanticSearchLanguage / ConfigLanguage enums."""

    def test_match_by_semantic_search_language_enum_in_extension(self) -> None:
        """ExtLangPair.language = SemanticSearchLanguage is matched correctly."""
        pattern = _make_pattern("sstart", "send")
        ext = ExtLangPair(
            ext=FileExt(cast(LiteralStringT, ".py")), language=SemanticSearchLanguage.PYTHON
        )
        cd = CustomDelimiter(extensions=[ext], delimiters=[pattern])
        gov = _make_governor(_make_settings([cd]))
        chunker = DelimiterChunker(gov, language="python")
        starts = [d.start for d in chunker._delimiters]
        assert "sstart" in starts, (
            "Custom delimiter from SemanticSearchLanguage extension should be loaded"
        )

    def test_match_by_config_language_enum(self) -> None:
        """CustomDelimiter.language = ConfigLanguage enum is matched correctly."""
        pattern = _make_pattern("cfgfunc", "cfgend")
        # ConfigLanguage.BASH is not in the secondary ALL_LANGUAGES registry, so
        # extensions are required for validation.
        ext = ExtLangPair(ext=FileExt(cast(LiteralStringT, ".sh")), language=ConfigLanguage.BASH)
        cd = CustomDelimiter(language=ConfigLanguage.BASH, extensions=[ext], delimiters=[pattern])
        gov = _make_governor(_make_settings([cd]))
        # ConfigLanguage.BASH.variable should resolve to "bash"
        chunker = DelimiterChunker(gov, language="bash")
        starts = [d.start for d in chunker._delimiters]
        assert "cfgfunc" in starts, (
            "Custom delimiter identified by ConfigLanguage enum should be loaded for 'bash'"
        )

    def test_plain_language_name_matches(self) -> None:
        """A plain LanguageName string matches the normalised language key."""
        pattern = _make_pattern("rustfunc", "rustend")
        # 'rust' is not in ALL_LANGUAGES, so extensions are needed for validation.
        ext = ExtLangPair(
            ext=FileExt(cast(LiteralStringT, ".rs")),
            language=LanguageName(cast(LiteralStringT, "rust")),
        )
        cd = CustomDelimiter(
            language=LanguageName(cast(LiteralStringT, "rust")),
            extensions=[ext],
            delimiters=[pattern],
        )
        gov = _make_governor(_make_settings([cd]))
        chunker = DelimiterChunker(gov, language="rust")
        starts = [d.start for d in chunker._delimiters]
        assert "rustfunc" in starts


# ---------------------------------------------------------------------------
# Tests: error handling
# ---------------------------------------------------------------------------


@pytest.mark.benchmark
@pytest.mark.mock_only
@pytest.mark.performance
@pytest.mark.unit
class TestCustomDelimiterErrorHandling:
    """A single bad pattern must not abort loading for the whole language."""

    def test_invalid_pattern_is_skipped_with_warning(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Loading continues and emits a warning when one pattern is invalid."""
        valid_pattern = _make_pattern("goodfunc", "goodend")
        invalid_pattern = _make_pattern("badstart", "badend")

        # 'cobol' is in the secondary ALL_LANGUAGES registry, so no extensions needed.
        cd = CustomDelimiter(
            language=LanguageName(cast(LiteralStringT, "cobol")),
            delimiters=[valid_pattern, invalid_pattern],
        )
        gov = _make_governor(_make_settings([cd]))

        # Patch Delimiter.from_pattern to raise on the second call
        call_count = 0

        import codeweaver.engine.chunker.delimiter_model as dm

        _real = dm.Delimiter.from_pattern

        def patched_from_pattern(pattern: object) -> list:
            nonlocal call_count
            call_count += 1
            if call_count == 2:  # second pattern is "bad"
                raise ValueError("Simulated bad pattern")
            return _real(pattern)

        import logging

        with patch.object(dm.Delimiter, "from_pattern", side_effect=patched_from_pattern):
            with caplog.at_level(logging.WARNING, logger="codeweaver.engine.chunker.delimiter"):
                chunker = DelimiterChunker(gov, language="cobol")

        # Should still load valid pattern
        starts = [d.start for d in chunker._delimiters]
        assert "goodfunc" in starts, "Valid pattern should be loaded even when a sibling fails"
        # Warning should be recorded
        assert any("Skipping invalid" in r.message for r in caplog.records), (
            "A warning should be logged for the skipped pattern"
        )


# ---------------------------------------------------------------------------
# Tests: new language detection in ChunkerSelector
# ---------------------------------------------------------------------------


@pytest.mark.benchmark
@pytest.mark.mock_only
@pytest.mark.performance
@pytest.mark.unit
class TestNewLanguageDetection:
    """ChunkerSelector picks up custom extension→language mappings from settings."""

    def test_selector_detects_custom_extension_language(self) -> None:
        """Files with a custom extension are mapped to the declared language name."""
        from codeweaver.engine.chunker.selector import ChunkerSelector

        pattern = _make_pattern()
        ext = ExtLangPair(
            ext=FileExt(cast(LiteralStringT, ".myl")),
            language=LanguageName(cast(LiteralStringT, "mylang")),
        )
        cd = CustomDelimiter(
            language=LanguageName(cast(LiteralStringT, "mylang")),
            extensions=[ext],
            delimiters=[pattern],
        )
        gov = _make_governor(_make_settings([cd]))
        selector = ChunkerSelector(gov)

        # Simulate a file with the new extension (no ext_category since it's unknown)
        mock_file = _make_mock_file(".myl", ext_category=None)
        lang = selector._detect_language(mock_file)
        assert lang == "mylang", f"Expected 'mylang', got {lang!r}"

    def test_selector_returns_extension_fallback_for_truly_unknown(self) -> None:
        """Files whose extension is not in settings fall back to the extension string."""
        from codeweaver.engine.chunker.selector import ChunkerSelector

        gov = _make_governor(ChunkerSettings(performance=PerformanceSettings()))
        selector = ChunkerSelector(gov)

        mock_file = _make_mock_file(".xyz", ext_category=None)
        lang = selector._detect_language(mock_file)
        assert lang == "xyz", f"Expected 'xyz', got {lang!r}"
