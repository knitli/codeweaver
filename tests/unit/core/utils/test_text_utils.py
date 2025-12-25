"""Unit tests for codeweaver.core.utils.text module."""

import logging
import re

import pytest

from codeweaver.core.utils.text import (
    _NESTED_QUANTIFIER_RE,
    MAX_REGEX_PATTERN_LENGTH,
    _walk_pattern,
    validate_regex_pattern,
)
from codeweaver.exceptions import ConfigurationError


@pytest.mark.unit
@pytest.mark.parametrize(
    ("input_value", "expected"),
    [
        pytest.param(r"abc", "abc", id="simple-literal-no-escapes"),
        pytest.param(r"\n\t\r", r"\n\t\r", id="standard-escapes-kept"),
        pytest.param(r"\d+\w*", r"\d+\w*", id="valid-predefined-classes-and-quantifiers"),
        pytest.param(r"\.", r"\.", id="escaped-metachar-dot"),
        pytest.param(r"\y", r"\\y", id="unknown-escape-doubled"),
        pytest.param("\\y\\n", r"\\y\n", id="mixed-unknown-and-known-escapes"),
        pytest.param("\\", r"\\", id="single-trailing-backslash-doubled"),
        pytest.param("a\\", r"a\\", id="char-followed-by-trailing-backslash"),
        pytest.param(r"[a\-z]", r"[a\-z]", id="character-class-with-escape"),
        pytest.param(r"\A\Z\b\B\G", r"\A\Z\b\B\G", id="various-anchor-and-boundary-escapes"),
        pytest.param(
            r"\x41\u0042\N{LATIN CAPITAL LETTER C}",
            r"\x41\u0042\N{LATIN CAPITAL LETTER C}",
            id="hex-unicode-and-named-escapes",
        ),
        pytest.param(r".*+", r".*+", id="quantifier-followed-by-quantifier-still-legal"),
        pytest.param(r"\\", r"\\", id="already-escaped-backslash"),
    ],
)
def test_walk_pattern_happy_and_edge_cases(input_value, expected) -> None:
    """Test _walk_pattern with various inputs."""
    # Act

    result = _walk_pattern(input_value)

    # Assert

    assert result == expected


@pytest.mark.unit
@pytest.mark.parametrize(
    "input_value",
    [
        pytest.param(123, id="non-string-int"),
        pytest.param(12.34, id="non-string-float"),
        pytest.param([], id="non-string-list"),
        pytest.param(None, id="non-string-none"),
    ],
)
def test_walk_pattern_type_error_non_string(input_value) -> None:
    """Test _walk_pattern raises TypeError for non-string inputs."""
    # Act

    with pytest.raises(TypeError) as exc_info:
        _walk_pattern(input_value)  # type: ignore[arg-type]

    # Assert

    assert "Pattern must be a string." in str(exc_info.value)


@pytest.mark.unit
@pytest.mark.parametrize(
    ("value", "expected_pattern"),
    [
        pytest.param(None, None, id="none-returns-none"),
        pytest.param(
            re.compile(r"precompiled"),
            re.compile(r"precompiled"),
            id="compiled-pattern-returned-as_is",
        ),
    ],
)
def test_validate_regex_pattern_none_and_compiled(value, expected_pattern) -> None:
    """Test validate_regex_pattern with None and pre-compiled patterns."""
    # Act

    result = validate_regex_pattern(value)

    # Assert

    if value is None:
        assert result is None
    else:
        assert isinstance(result, re.Pattern)
        assert result is value


@pytest.mark.unit
@pytest.mark.parametrize(
    ("pattern", "test_string", "should_match"),
    [
        pytest.param(r"abc", "xxabcxx", True, id="simple-literal-match"),
        pytest.param(r"\d+", "abc123def", True, id="digits-class-match"),
        pytest.param(r"[a-z]{2,3}", "AxyZ", True, id="range-with-quantifier-match"),
        pytest.param(r"\w+\s\w+", "hello world", True, id="word-space-word-match"),
        pytest.param(r"\Astart", "start of line", True, id="anchor-start-match"),
        pytest.param(r"end\Z", "line end", False, id="anchor-end-no-match"),
        pytest.param(r"\y", r"\y", False, id="unknown-escape-handled-no-match"),
        pytest.param(r"a\\", r"a\\", True, id="trailing-backslash-normalized-match"),
    ],
)
def test_validate_regex_pattern_happy_paths(pattern, test_string, should_match):
    """Test validate_regex_pattern with valid patterns."""
    # Act

    compiled = validate_regex_pattern(pattern)

    # Assert

    assert isinstance(compiled, re.Pattern)
    if should_match:
        assert compiled.search(test_string) is not None
    else:
        assert compiled.search(test_string) is None


@pytest.mark.unit
def test_validate_regex_pattern_too_long_raises():
    """Test validate_regex_pattern raises ConfigurationError for overly long patterns."""
    # Arrange

    long_pattern = "a" * (MAX_REGEX_PATTERN_LENGTH + 1)

    # Act

    with pytest.raises(ConfigurationError) as exc_info:
        validate_regex_pattern(long_pattern)

    # Assert

    assert "Regex pattern is too long" in str(exc_info.value)


@pytest.mark.unit
@pytest.mark.parametrize(
    "pattern",
    [
        pytest.param(r"(.+)+", id="simple-nested-plus-plus"),
        pytest.param(r"(\w+)*", id="word-class-plus-star"),
        pytest.param(r"(a|aa)+", id="alternation-nested-quantifier"),
        pytest.param(r"([a-z]{1,3}){4,5}", id="braced-quantifiers-nested"),
    ],
)
def test_validate_regex_pattern_nested_quantifiers_rejected(pattern) -> None:
    # Act

    # Verify our heuristic would detect this after normalization as well
    normalized = _walk_pattern(pattern)
    assert _NESTED_QUANTIFIER_RE.search(normalized) is not None

    with pytest.raises(ConfigurationError) as exc_info:
        validate_regex_pattern(pattern)

    # Assert

    assert "nested quantifiers" in str(exc_info.value)


def _make_many_groups_pattern(count: int) -> str:
    return "".join("(a)" for _ in range(count))


@pytest.mark.unit
def test_validate_regex_pattern_too_many_groups_raises() -> None:
    # Arrange

    too_many_groups_pattern = _make_many_groups_pattern(101)

    # Act

    with pytest.raises(ConfigurationError) as exc_info:
        validate_regex_pattern(too_many_groups_pattern)

    # Assert

    assert "too many capturing/non-capturing groups" in str(exc_info.value)


@pytest.mark.unit
def test_validate_regex_pattern_group_count_logging_on_exception(monkeypatch, caplog) -> None:
    """Test that validate_regex_pattern logs debug info if group counting fails."""
    # Arrange

    class WeirdSeq(str):
        __slots__ = ()

        def __iter__(self):
            raise RuntimeError("iteration not allowed")

    bad_string = WeirdSeq("(a)")

    original_sum = sum

    def sum_raising(*args, **kwargs):
        raise RuntimeError("sum failure")

    monkeypatch.setattr("codeweaver.core.utils.text.sum", sum_raising)

    caplog.set_level(logging.DEBUG)

    # Act

    with pytest.raises(ConfigurationError):
        validate_regex_pattern(bad_string)

    # Assert

    assert any(
        "Failed to count groups in regex safety check" in message
        for logger_name, level, message in caplog.record_tuples
    )

    monkeypatch.setattr("codeweaver.core.utils.text.sum", original_sum)


@pytest.mark.unit
@pytest.mark.parametrize(
    "pattern",
    [
        pytest.param("(", id="unbalanced-parenthesis"),
        pytest.param("[a-", id="unterminated-character-class"),
        pytest.param(r"(\k<1>)", id="invalid-backreference"),
    ],
)
def test_validate_regex_pattern_invalid_regex_raises_configuration_error(pattern) -> None:
    """Test validate_regex_pattern raises ConfigurationError for invalid regex patterns."""
    # Act

    with pytest.raises(ConfigurationError) as exc_info:
        validate_regex_pattern(pattern)

    # Assert

    assert "Invalid regex pattern" in str(exc_info.value)
