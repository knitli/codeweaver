# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Tests for delimiter pattern system.

Tests cover:
- Pattern expansion to DelimiterDict
- Pattern matching logic
- Language family detection
- DelimiterKind.PARAGRAPH priority
- Cross-platform line ending support
"""

from __future__ import annotations

import pytest

from codeweaver.engine.chunker.delimiters.families import (
    LanguageFamily,
    detect_family_characteristics,
    detect_language_family,
)
from codeweaver.engine.chunker.delimiters.kind import DelimiterKind
from codeweaver.engine.chunker.delimiters.patterns import (
    ALL_PATTERNS,
    CONDITIONAL_PATTERN,
    FUNCTION_PATTERN,
    HASH_COMMENT_PATTERN,
    PARAGRAPH_PATTERN,
    STRING_QUOTE_PATTERN,
    DelimiterDict,
    DelimiterPattern,
    expand_pattern,
    matches_pattern,
)


pytestmark = [pytest.mark.unit]


class TestDelimiterPattern:
    """Test DelimiterPattern DSL and expansion."""

    def test_pattern_creation(self) -> None:
        """Test basic pattern creation."""
        pattern = DelimiterPattern(
            starts=["if", "while"], ends=[":", "then"], kind=DelimiterKind.CONDITIONAL
        )

        assert pattern.starts == ["if", "while"]
        assert pattern.ends == [":", "then"]
        assert pattern.kind == DelimiterKind.CONDITIONAL
        assert pattern.priority_override is None

    def test_pattern_with_overrides(self) -> None:
        """Test pattern with explicit overrides."""
        pattern = DelimiterPattern(
            starts=["\n\n"],
            ends=["\n\n"],
            kind=DelimiterKind.PARAGRAPH,
            priority_override=40,
            inclusive=False,
            take_whole_lines=False,
            nestable=False,
        )

        assert pattern.priority_override == 40
        assert pattern.inclusive is False
        assert pattern.take_whole_lines is False
        assert pattern.nestable is False

    def test_expand_simple_pattern(self) -> None:
        """Test expanding pattern with explicit ends."""
        pattern = DelimiterPattern(
            starts=["if", "while"], ends=[":", "then"], kind=DelimiterKind.CONDITIONAL
        )

        delimiters = expand_pattern(pattern)

        assert len(delimiters) == 4  # 2 starts * 2 ends
        assert delimiters[0]["start"] == "if"
        assert delimiters[0]["end"] == ":"
        assert delimiters[1]["start"] == "if"
        assert delimiters[1]["end"] == "then"
        assert delimiters[2]["start"] == "while"
        assert delimiters[2]["end"] == ":"
        assert delimiters[3]["start"] == "while"
        assert delimiters[3]["end"] == "then"

    def test_expand_any_end_pattern(self) -> None:
        """Test expanding pattern with ANY end wildcard."""
        pattern = DelimiterPattern(
            starts=["def", "function"], ends="ANY", kind=DelimiterKind.FUNCTION
        )

        delimiters = expand_pattern(pattern)

        assert len(delimiters) == 2  # 2 starts * 1 wildcard end
        assert delimiters[0]["start"] == "def"
        assert delimiters[0]["end"] == ""  # ANY = empty string
        assert delimiters[1]["start"] == "function"
        assert delimiters[1]["end"] == ""

    def test_expand_uses_kind_defaults(self) -> None:
        """Test that expansion uses DelimiterKind defaults when not overridden."""
        pattern = DelimiterPattern(starts=["def"], ends="ANY", kind=DelimiterKind.FUNCTION)

        delimiters = expand_pattern(pattern)

        assert len(delimiters) == 1
        delimiter = delimiters[0]

        # Should use FUNCTION defaults
        assert delimiter.get("priority_override") == DelimiterKind.FUNCTION.default_priority  # 70
        assert delimiter.get("inclusive") is True  # code elements are inclusive
        assert delimiter.get("take_whole_lines") is True
        assert delimiter.get("nestable") is True

    def test_expand_uses_overrides(self) -> None:
        """Test that expansion respects explicit overrides."""
        pattern = DelimiterPattern(
            starts=["\n\n"],
            ends=["\n\n"],
            kind=DelimiterKind.PARAGRAPH,
            priority_override=40,
            inclusive=False,
            take_whole_lines=False,
            nestable=False,
        )

        delimiters = expand_pattern(pattern)

        assert len(delimiters) == 1
        delimiter = delimiters[0]

        assert delimiter.get("priority_override") == 40  # override, not PARAGRAPH default
        assert delimiter.get("inclusive") is False
        assert delimiter.get("take_whole_lines") is False
        assert delimiter.get("nestable") is False

    def test_expand_multiplatform_line_endings(self) -> None:
        """Test pattern with multiple line ending variants."""
        pattern = DelimiterPattern(
            starts=["#"], ends=["\n", "\r\n", "\r"], kind=DelimiterKind.COMMENT_LINE
        )

        delimiters = expand_pattern(pattern)

        assert len(delimiters) == 3
        assert delimiters[0]["end"] == "\n"
        assert delimiters[1]["end"] == "\r\n"
        assert delimiters[2]["end"] == "\r"

        # All should have same kind and priority
        for delimiter in delimiters:
            assert delimiter.get("kind") == DelimiterKind.COMMENT_LINE
            assert delimiter.get("priority_override") == 20


class TestPatternMatching:
    """Test pattern matching logic."""

    def test_matches_pattern_exact(self) -> None:
        """Test exact pattern matching."""
        pattern = DelimiterPattern(
            starts=["def", "function"], ends="ANY", kind=DelimiterKind.FUNCTION
        )

        assert matches_pattern("def", ":", pattern) is True
        assert matches_pattern("function", "end", pattern) is True

    def test_matches_pattern_case_insensitive(self) -> None:
        """Test case-insensitive matching."""
        pattern = DelimiterPattern(
            starts=["def", "function"], ends="ANY", kind=DelimiterKind.FUNCTION
        )

        assert matches_pattern("DEF", ":", pattern) is True
        assert matches_pattern("Function", "end", pattern) is True
        assert matches_pattern("FUNCTION", "", pattern) is True

    def test_matches_pattern_any_end(self) -> None:
        """Test ANY end wildcard matching."""
        pattern = DelimiterPattern(starts=["def"], ends="ANY", kind=DelimiterKind.FUNCTION)

        assert matches_pattern("def", ":", pattern) is True
        assert matches_pattern("def", "end", pattern) is True
        assert matches_pattern("def", "", pattern) is True
        assert matches_pattern("def", "anything", pattern) is True

    def test_matches_pattern_specific_ends(self) -> None:
        """Test specific end matching."""
        pattern = DelimiterPattern(
            starts=["if"], ends=[":", "then"], kind=DelimiterKind.CONDITIONAL
        )

        assert matches_pattern("if", ":", pattern) is True
        assert matches_pattern("if", "then", pattern) is True
        assert matches_pattern("if", "THEN", pattern) is True  # case-insensitive
        assert matches_pattern("if", "end", pattern) is False  # not in ends

    def test_matches_pattern_no_match(self) -> None:
        """Test non-matching patterns."""
        pattern = DelimiterPattern(starts=["def"], ends=[":", "end"], kind=DelimiterKind.FUNCTION)

        assert matches_pattern("class", ":", pattern) is False  # wrong start
        assert matches_pattern("def", "}", pattern) is False  # wrong end


class TestParagraphDelimiter:
    """Test PARAGRAPH delimiter kind and priority."""

    def test_paragraph_kind_exists(self) -> None:
        """Test PARAGRAPH kind is defined."""
        assert DelimiterKind.PARAGRAPH == "paragraph"

    def test_paragraph_priority(self) -> None:
        """Test PARAGRAPH has priority 40."""
        assert DelimiterKind.PARAGRAPH.default_priority == 40

    def test_paragraph_priority_ordering(self) -> None:
        """Test PARAGRAPH priority is between COMMENT_BLOCK and BLOCK."""
        comment_block_priority = DelimiterKind.COMMENT_BLOCK.default_priority
        block_priority = DelimiterKind.BLOCK.default_priority
        paragraph_priority = DelimiterKind.PARAGRAPH.default_priority

        assert comment_block_priority > paragraph_priority > block_priority
        assert comment_block_priority == 55
        assert paragraph_priority == 40
        assert block_priority == 30

    def test_paragraph_pattern_definition(self) -> None:
        """Test PARAGRAPH_PATTERN has correct configuration."""
        assert PARAGRAPH_PATTERN.kind == DelimiterKind.PARAGRAPH
        assert PARAGRAPH_PATTERN.priority_override == 40
        assert PARAGRAPH_PATTERN.inclusive is False
        assert PARAGRAPH_PATTERN.take_whole_lines is False
        assert PARAGRAPH_PATTERN.nestable is False

    def test_paragraph_cross_platform(self) -> None:
        """Test PARAGRAPH pattern includes Windows and Unix line endings."""
        assert "\n\n" in PARAGRAPH_PATTERN.starts
        assert "\r\n\r\n" in PARAGRAPH_PATTERN.starts
        assert "\n\n" in PARAGRAPH_PATTERN.ends
        assert "\r\n\r\n" in PARAGRAPH_PATTERN.ends

    def test_paragraph_expansion(self) -> None:
        """Test PARAGRAPH pattern expands correctly."""
        delimiters = expand_pattern(PARAGRAPH_PATTERN)

        # Should have Unix and Windows variants
        assert len(delimiters) >= 2

        for delimiter in delimiters:
            assert delimiter.get("kind") == DelimiterKind.PARAGRAPH
            assert delimiter.get("priority_override") == 40
            assert delimiter.get("inclusive") is False
            assert delimiter.get("nestable") is False


class TestLanguageFamilies:
    """Test language family classification."""

    @pytest.mark.asyncio
    async def test_c_style_detection(self) -> None:
        """Test C-style language detection."""
        code = """
        function foo() {
            if (x > 0) {
                return x;
            }
        }
        """
        family = await detect_language_family(code)
        assert family == LanguageFamily.C_STYLE

    @pytest.mark.asyncio
    async def test_python_style_detection(self) -> None:
        """Test Python-style language detection."""
        code = """
        # Python comment
        @decorator
        def foo():
            if x > 0:
                return x
        """
        family = await detect_language_family(code)
        assert family == LanguageFamily.PYTHON_STYLE

    @pytest.mark.asyncio
    async def test_lisp_style_detection(self) -> None:
        """Test Lisp-style language detection."""
        code = """
        ;;; Lisp function docstring
        ;; Another comment
        (defun foo (x)
          ;; Local comment
          (if (> x 0)
            x
            nil))
        """
        family = await detect_language_family(code)
        assert family == LanguageFamily.LISP_STYLE

    @pytest.mark.asyncio
    async def test_markup_style_detection(self) -> None:
        """Test Markup-style language detection."""
        code = """
        <div class="container">
            <p>Hello {{ name }}</p>
        </div>
        """
        family = await detect_language_family(code)
        assert family == LanguageFamily.MARKUP_STYLE

    @pytest.mark.asyncio
    async def test_shell_style_detection(self) -> None:
        """Test Shell-style language detection."""
        code = """
        #!/bin/bash
        function foo() {
            for i in 1 2 3; do
                echo $i
            done
        }
        """
        family = await detect_language_family(code)
        assert family == LanguageFamily.SHELL_STYLE

    @pytest.mark.asyncio
    async def test_unknown_detection(self) -> None:
        """Test unknown language detection for insufficient data."""
        code = "x = 42"  # Not enough to classify
        family = await detect_language_family(code)
        assert family == LanguageFamily.UNKNOWN

    @pytest.mark.asyncio
    async def test_min_confidence_threshold(self) -> None:
        """Test minimum confidence threshold."""
        code = "if x"  # Only one delimiter, below default threshold
        family = await detect_language_family(code, min_confidence=3)
        assert family == LanguageFamily.UNKNOWN

        # Lower threshold should allow classification
        family = await detect_language_family(code, min_confidence=1)
        assert family != LanguageFamily.UNKNOWN

    def test_detect_characteristics(self) -> None:
        """Test detailed family characteristic detection."""
        code = """
        function foo() {
            return 42;
        }
        """
        chars = detect_family_characteristics(code)

        # C-style should have matches
        assert chars[LanguageFamily.C_STYLE]["pattern_matches"] > 0
        assert chars[LanguageFamily.C_STYLE]["confidence"] > 0.0

        # Python-style should have fewer matches
        assert (
            chars[LanguageFamily.PYTHON_STYLE]["pattern_matches"]
            < chars[LanguageFamily.C_STYLE]["pattern_matches"]
        )


class TestCorePatterns:
    """Test core pattern definitions."""

    def test_function_pattern(self) -> None:
        """Test FUNCTION_PATTERN covers common keywords."""
        assert "def" in FUNCTION_PATTERN.starts
        assert "function" in FUNCTION_PATTERN.starts
        assert "fn" in FUNCTION_PATTERN.starts
        assert "lambda" in FUNCTION_PATTERN.starts
        assert FUNCTION_PATTERN.ends == "ANY"
        assert FUNCTION_PATTERN.kind == DelimiterKind.FUNCTION

    def test_conditional_pattern(self) -> None:
        """Test CONDITIONAL_PATTERN covers common keywords."""
        assert "if" in CONDITIONAL_PATTERN.starts
        assert "else" in CONDITIONAL_PATTERN.starts
        assert "switch" in CONDITIONAL_PATTERN.starts
        assert "match" in CONDITIONAL_PATTERN.starts
        assert CONDITIONAL_PATTERN.kind == DelimiterKind.CONDITIONAL

    def test_comment_patterns_cross_platform(self) -> None:
        """Test comment patterns include all line ending variants."""
        # Hash comments
        assert "#" in HASH_COMMENT_PATTERN.starts
        assert "\n" in HASH_COMMENT_PATTERN.ends
        assert "\r\n" in HASH_COMMENT_PATTERN.ends
        assert "\r" in HASH_COMMENT_PATTERN.ends

    def test_string_patterns_comprehensive(self) -> None:
        """Test string patterns cover common quote styles."""
        assert "'" in STRING_QUOTE_PATTERN.starts
        assert '"' in STRING_QUOTE_PATTERN.starts
        assert "`" in STRING_QUOTE_PATTERN.starts

    def test_all_patterns_collection(self) -> None:
        """Test ALL_PATTERNS includes expected patterns."""
        assert FUNCTION_PATTERN in ALL_PATTERNS
        assert CONDITIONAL_PATTERN in ALL_PATTERNS
        assert HASH_COMMENT_PATTERN in ALL_PATTERNS
        assert PARAGRAPH_PATTERN in ALL_PATTERNS
        assert STRING_QUOTE_PATTERN in ALL_PATTERNS

        # Should have substantial number of patterns
        assert len(ALL_PATTERNS) > 50


class TestPatternInference:
    """Test pattern-based delimiter inference."""

    def test_infer_function_delimiter(self) -> None:
        """Test inferring function delimiters."""
        # Find function pattern in ALL_PATTERNS
        for pattern in ALL_PATTERNS:
            if pattern.kind == DelimiterKind.FUNCTION:
                assert matches_pattern("def", ":", pattern) is True
                assert matches_pattern("function", "{", pattern) is True
                break
        else:
            pytest.fail("No FUNCTION pattern found in ALL_PATTERNS")

    def test_infer_unknown_delimiter(self) -> None:
        """Test handling unknown delimiter patterns."""
        # Unknown delimiter should not match any pattern
        start, end = "@@unknown@@", "@@end@@"

        matches = [p for p in ALL_PATTERNS if matches_pattern(start, end, p)]
        assert not matches

    def test_pattern_coverage(self) -> None:
        """Test pattern coverage of DelimiterKind values."""
        # Get all kinds represented in ALL_PATTERNS
        represented_kinds = {p.kind for p in ALL_PATTERNS}

        # Should cover most DelimiterKind values (excluding METHOD, DECORATOR edge cases)
        expected_kinds = {
            DelimiterKind.FUNCTION,
            DelimiterKind.CLASS,
            DelimiterKind.STRUCT,
            DelimiterKind.CONDITIONAL,
            DelimiterKind.LOOP,
            DelimiterKind.COMMENT_LINE,
            DelimiterKind.COMMENT_BLOCK,
            DelimiterKind.DOCSTRING,
            DelimiterKind.BLOCK,
            DelimiterKind.ARRAY,
            DelimiterKind.STRING,
            DelimiterKind.PARAGRAPH,
            DelimiterKind.WHITESPACE,
        }

        assert expected_kinds.issubset(represented_kinds)


class TestIntegration:
    """Integration tests for delimiter system."""

    def test_pattern_to_delimiter_roundtrip(self) -> None:
        """Test expanding pattern and using results."""
        pattern = DelimiterPattern(starts=["def"], ends=[":", "end"], kind=DelimiterKind.FUNCTION)

        delimiters = expand_pattern(pattern)

        assert len(delimiters) == 2
        assert all(d.get("kind") == DelimiterKind.FUNCTION for d in delimiters)
        assert all(d.get("priority_override") == 70 for d in delimiters)  # FUNCTION priority

    def test_family_pattern_expansion(self) -> None:
        """Test expanding all patterns for a language family."""
        from codeweaver.engine.chunker.delimiters.families import get_family_patterns

        c_patterns = get_family_patterns(LanguageFamily.C_STYLE)

        assert len(c_patterns) > 10  # Should have substantial patterns

        # Expand all patterns
        all_delimiters: list[DelimiterDict] = []
        for pattern in c_patterns:
            all_delimiters.extend(expand_pattern(pattern))

        # Should generate many concrete delimiters
        assert len(all_delimiters) > 50

        # All should be valid DelimiterDict entries
        for delim in all_delimiters:
            self._test_delimiter_dict(delim)

    def _test_delimiter_dict(self, delim):
        assert "start" in delim
        assert "end" in delim
        assert "kind" in delim
        assert "priority_override" in delim
        assert isinstance(delim["priority_override"], int)
        assert delim["priority_override"] > 0

    def test_unknown_language_fallback(self) -> None:
        """Test unknown language gets generic delimiters."""
        from codeweaver.engine.chunker.delimiters.families import get_family_patterns

        unknown_patterns = get_family_patterns(LanguageFamily.UNKNOWN)

        # Should have basic fallback patterns
        assert len(unknown_patterns) > 0

        # Should include PARAGRAPH for semantic chunking
        kinds = {p.kind for p in unknown_patterns}
        assert DelimiterKind.PARAGRAPH in kinds
        assert DelimiterKind.WHITESPACE in kinds
