---
title: tokenizers
description: API reference for tokenizers
---

# tokenizers

Entry point for CodeWeaver's tokenizer system. Provides the `get_tokenizer` function to retrieve the appropriate tokenizer class based on the specified type and model.

## Functions

## `get_tokenizer(tokenizer: Literal['tiktoken', 'tokenizers'], model: str) -> Tokenizer[Any]`

Get the tokenizer class based on the specified tokenizer type and model.

Args:
    tokenizer: The type of tokenizer to use (e.g., "tiktoken", "tokenizers").
    model: The specific model name for the tokenizer.

Returns:
    The tokenizer class corresponding to the specified type and model.

