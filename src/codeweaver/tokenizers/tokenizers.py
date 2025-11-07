# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""
Tokenizer for the Tokenizers library.
"""

from __future__ import annotations

import logging

from collections.abc import Sequence
from typing import Any

from typing_extensions import TypeIs

from codeweaver.tokenizers.base import Tokenizer


logger = logging.getLogger(__name__)

try:
    from tokenizers import Tokenizer as TokenizersTokenizer
except ImportError as e:
    logger.exception("Failed to import 'tokenizers' package, you may need to install it.")
    raise ImportError(
        "The 'tokenizers' package is required for this module. Please install it with 'pip install tokenizers'."
    ) from e


def _is_tokenizer(obj: Any) -> TypeIs[TokenizersTokenizer]:
    return isinstance(obj, TokenizersTokenizer)


class Tokenizers(Tokenizer[TokenizersTokenizer]):
    """Tokenizer for the Tokenizers library.

    Inherits `estimate` and `estimate_batch` from its base class, `Tokenizer`.
    """

    _encoder: TokenizersTokenizer

    def __init__(self, encoder: str, **kwargs: dict[str, Any] | None) -> None:
        """Initialize tokenizers encoder."""
        # pyright can't handle the dynamic import of tokenizers, even with `TypeIs`, so we use a few ignores here
        self._encoder = TokenizersTokenizer.from_pretrained(encoder, **(kwargs or {}))
        if not _is_tokenizer(self._encoder):
            raise TypeError(f"Expected a Tokenizers instance, got {type(self._encoder)}")

    def encode(self, text: str | bytes, **kwargs: Any) -> list[int]:
        """Encode text into a list of token IDs."""
        return self._encoder.encode(self._to_string(text), **kwargs)

    def encode_batch(self, texts: Sequence[str | bytes], **kwargs: Any) -> Sequence[Sequence[int]]:
        """Encode a batch of texts into a list of token ID lists."""
        return self._encoder.encode_batch((self._to_string(txt) for txt in texts), **kwargs)

    def decode(self, tokens: Sequence[int], **kwargs: Any) -> str:
        """Decode a list of token IDs back into text."""
        return self._encoder.decode(tokens, **kwargs)

    def decode_batch(self, token_lists: Sequence[Sequence[int]], **kwargs: Any) -> Sequence[str]:
        """Decode a batch of token ID lists back into texts."""
        return self._encoder.decode_batch(token_lists, **kwargs)

    @staticmethod
    def encoders() -> Sequence[str]:
        """List all available encoder names.

        The Tokenizers library can load any Hugging Face tokenizer, but they're all based on four models, so we return those.
        """
        return ["BPE", "WordPiece", "WordLevel", "Unigram"]


__all__ = ("Tokenizers",)
