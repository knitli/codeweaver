# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

import pytest

from codeweaver_tokenizers import get_tokenizer


def test_get_tokenizer_tiktoken():
    # cl100k_base is used by gpt-4
    tokenizer = get_tokenizer("tiktoken", "cl100k_base")
    assert tokenizer is not None

    text = "Hello world"
    tokens = tokenizer.encode(text)
    assert len(tokens) > 0
    assert tokenizer.decode(tokens) == text

def test_tokenizer_estimate():
    tokenizer = get_tokenizer("tiktoken", "cl100k_base")
    text = "This is a test of the emergency broadcast system."
    estimate = tokenizer.estimate(text)
    actual = len(tokenizer.encode(text))
    assert estimate == actual

def test_invalid_tokenizer_type():
    with pytest.raises(ValueError, match="Unsupported tokenizer type"):
        get_tokenizer("invalid", "model")
