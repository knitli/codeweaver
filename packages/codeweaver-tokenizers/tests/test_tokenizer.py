# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

import pytest

from codeweaver_tokenizers import get_tokenizer


@pytest.mark.unit
def test_get_tokenizer_tiktoken() -> None:
    """Test getting the Tiktoken tokenizer."""
    tokenizer = get_tokenizer("tiktoken", "cl100k_base")
    assert tokenizer is not None

    text = "Hello world"
    tokens = tokenizer.encode(text)
    assert len(tokens) > 0
    assert tokenizer.decode(tokens) == text


@pytest.mark.unit
def test_tokenizer_estimate() -> None:
    """Test the estimate method of the tokenizer."""
    tokenizer = get_tokenizer("tiktoken", "cl100k_base")
    text = "This is a test of the emergency broadcast system."
    estimate = tokenizer.estimate(text)
    actual = len(tokenizer.encode(text))
    assert estimate == actual


@pytest.mark.unit
def test_invalid_tokenizer_type() -> None:
    """Test that an invalid tokenizer type raises a ValueError."""
    with pytest.raises(ValueError, match="Unsupported tokenizer type"):
        get_tokenizer("invalid", "model")
