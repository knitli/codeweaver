# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# ruff: noqa: E402
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
        model: The specific model name for the tokenizer. In many cases, this may be different from the model you are using. This is always true for `tiktoken`, and may be true for `tokenizers`. For tokenizers, you can usually find this information in the model's HuggingFace card or documentation.

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


def estimate_tokens(text: str | bytes, encoder: str = "o200k_base") -> int:
    """Estimate the number of tokens in a text using tiktoken. Defaults to o200k_base encoding."""
    import tiktoken

    encoding = tiktoken.get_encoding(encoder)
    if isinstance(text, bytes):
        text = text.decode("utf-8", errors="ignore")
    return len(encoding.encode(text))


# === MANAGED EXPORTS ===

# Exportify manages this section. It contains lazy-loading infrastructure
# for the package: imports and runtime declarations (__all__, __getattr__,
# __dir__). Manual edits will be overwritten by `exportify fix`.

from types import MappingProxyType
from typing import TYPE_CHECKING

from lateimport import create_late_getattr

if TYPE_CHECKING:
    from codeweaver_tokenizers.base import (
        EncoderName,
        Tokenizer,
    )
    from codeweaver_tokenizers.tiktoken import (
        TiktokenTokenizer,
    )
    from codeweaver_tokenizers.tokenizers import (
        Tokenizers,
    )

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType(
    {
        "TiktokenTokenizer": (__spec__.parent, "tiktoken"),
        "Tokenizer": (__spec__.parent, "base"),
        "Tokenizers": (__spec__.parent, "tokenizers"),
    }
)

__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)

__all__ = (
    "EncoderName",
    "TiktokenTokenizer",
    "Tokenizer",
    "Tokenizers",
    "estimate_tokens",
    "get_tokenizer",
)


def __dir__() -> list[str]:
    """List available attributes for the package."""
    return list(__all__)
