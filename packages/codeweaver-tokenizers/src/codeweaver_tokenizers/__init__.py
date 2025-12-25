# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Entry point for CodeWeaver's tokenizer system. Provides the `get_tokenizer` function to retrieve the appropriate tokenizer class based on the specified type and model."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING, Any, Literal

from codeweaver_tokenizers.utils import create_lazy_getattr


if TYPE_CHECKING:
    from codeweaver_tokenizers.base import Tokenizer
    from codeweaver_tokenizers.tiktoken import TiktokenTokenizer
    from codeweaver_tokenizers.tokenizers import Tokenizers


_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "Tokenizer": ("codeweaver_tokenizers", "base"),
    "TiktokenTokenizer": ("codeweaver_tokenizers", "tiktoken"),
    "Tokenizers": ("codeweaver_tokenizers", "tokenizers"),
})

__getattr__ = create_lazy_getattr(_dynamic_imports, globals(), __name__)


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
        from codeweaver_tokenizers.tiktoken import TiktokenTokenizer

        return TiktokenTokenizer(model)

    if tokenizer == "tokenizers":
        from codeweaver_tokenizers.tokenizers import Tokenizers

        return Tokenizers(model)

    raise ValueError(f"Unsupported tokenizer type: {tokenizer}")


__all__ = ("TiktokenTokenizer", "Tokenizer", "Tokenizers", "get_tokenizer")


def __dir__() -> list[str]:
    return list(__all__)
