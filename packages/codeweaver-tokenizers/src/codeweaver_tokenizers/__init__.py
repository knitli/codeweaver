# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Entry point for CodeWeaver's tokenizer system. Provides the `get_tokenizer` function to retrieve the appropriate tokenizer class based on the specified type and model."""

from __future__ import annotations

from typing import Any, Literal

from codeweaver_tokenizers.base import Tokenizer
from codeweaver_tokenizers.tiktoken import TiktokenTokenizer
from codeweaver_tokenizers.tokenizers import Tokenizers


def get_tokenizer(
    tokenizer: Literal["tiktoken", "tokenizers"], model: str
) -> Tokenizer[Any]:
    """
    Get the tokenizer class based on the specified tokenizer type and model.

    Args:
        tokenizer: The type of tokenizer to use (e.g., "tiktoken", "tokenizers").
        model: The specific model name for the tokenizer.

    Returns:
        The tokenizer class corresponding to the specified type and model.
    """
    if tokenizer == "tiktoken":
        from codeweaver_tokenizers.tiktoken import TiktokenTokenizer

        return TiktokenTokenizer(model)

    if tokenizer == "tokenizers":
        from codeweaver_tokenizers.tokenizers import Tokenizers

        return Tokenizers(model)

    raise ValueError(f"Unsupported tokenizer type: {tokenizer}")


def estimate_tokens(text: str | bytes, encoder: str = "cl100k_base") -> int:
    """Estimate the number of tokens in a text using tiktoken. Defaults to cl100k_base encoding."""
    import tiktoken

    encoding = tiktoken.get_encoding(encoder)
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="ignore")
    return len(encoding.encode(text))


__all__ = (
    "TiktokenTokenizer",
    "Tokenizer",
    "Tokenizers",
    "estimate_tokens",
    "get_tokenizer",
)
