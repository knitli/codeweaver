# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Entry point for CodeWeaver's tokenizer system. Provides the `get_tokenizer` function to retrieve the appropriate tokenizer class based on the specified type and model."""

from typing import Any, Literal

from codeweaver.tokenizers.base import Tokenizer


def get_tokenizer(tokenizer: Literal["tiktoken", "tokenizers"], model: str) -> Tokenizer[Any]:
    """
    Get the tokenizer class based on the specified tokenizer type and model.

    Args:
        tokenizer: The type of tokenizer to use (e.g., "tiktoken", "tokenizers").
        model: The specific model name for the tokenizer.

    Returns:
        The tokenizer class corresponding to the specified type and model.
    """
    if tokenizer == "tiktoken":
        from codeweaver.tokenizers.tiktoken import TiktokenTokenizer

        return TiktokenTokenizer(model)

    if tokenizer == "tokenizers":
        from codeweaver.tokenizers.tokenizers import Tokenizers

        return Tokenizers(model)

    raise ValueError(f"Unsupported tokenizer type: {tokenizer}")


__all__ = ("get_tokenizer",)
