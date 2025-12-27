# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Abstract base class for tokenizers."""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Sequence
from typing import Any, LiteralString


type EncoderName = LiteralString


class Tokenizer[Encoder](ABC):
    """Abstract base class for tokenizers."""

    _encoder: Encoder

    @abstractmethod
    def __init__(self, encoder: EncoderName, **kwargs: Any) -> None:
        """Initialize the tokenizer with a specific encoder."""

    @abstractmethod
    def encode(self, text: str | bytes, **kwargs: Any) -> Sequence[int]:
        """Encode text into a list of token IDs."""

    @abstractmethod
    def encode_batch(
        self, texts: Sequence[str] | Sequence[bytes], **kwargs: Any
    ) -> Sequence[Sequence[int]]:
        """Encode a batch of texts into a list of token ID lists."""

    @abstractmethod
    def decode(self, tokens: Sequence[int], **kwargs: Any) -> str:
        """Decode a list of token IDs back into text."""

    @abstractmethod
    def decode_batch(
        self, token_lists: Sequence[Sequence[int]], **kwargs: Any
    ) -> Sequence[str]:
        """Decode a batch of token ID lists back into text."""

    @staticmethod
    @abstractmethod
    def encoders() -> Sequence[str]:
        """List all available encoder names."""

    @property
    def encoder(self) -> Encoder:
        """Get the encoder instance."""
        return self._encoder

    def _to_string(self, value: str | bytes) -> str:
        """Convert bytes to string if necessary."""
        if isinstance(value, bytes):
            return value.decode("utf-8", errors="ignore")
        return value

    def estimate(self, text: str | bytes, **kwargs: Any) -> int:
        """Estimate the number of tokens in the given text."""
        return len(self.encode(text, **kwargs))

    def estimate_batch(
        self, texts: Sequence[str] | Sequence[bytes], **kwargs: Any
    ) -> int:
        """Estimate the number of tokens in a batch of texts."""
        return sum(len(batch) for batch in self.encode_batch(texts, **kwargs))


__all__ = ("Tokenizer",)
