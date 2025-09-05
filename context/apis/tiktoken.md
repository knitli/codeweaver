<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# tiktoken - Token Counting and Cost Estimation API

## Summary

Feature Name: Token counting and cost estimation
Feature Description: Fast BPE tokenization for OpenAI models with token counting capabilities
Feature Goal: Enable accurate token usage tracking, cost estimation, and quota management for CodeWeaver

Primary External Surface(s): `tiktoken.get_encoding()`, `tiktoken.encoding_for_model()`, `Encoding.encode()`, `Encoding.decode()`

Integration Confidence: high - Well-established OpenAI library with simple, stable API

## Core Types

Name | Kind | Definition | Role
--- | --- | --- | ---
Encoding | Class | BPE tokenizer instance | Main tokenization interface
EncodingName | str | Encoding identifier | Specifies tokenization method
ModelName | str | OpenAI model identifier | Maps to appropriate encoding

## Signatures

### Function: get_encoding

Name: get_encoding
Import Path: `import tiktoken`
Concrete Path: https://github.com/openai/tiktoken/blob/main/tiktoken/core.py
Signature: `tiktoken.get_encoding(encoding_name: str) -> Encoding`
Params: 
- encoding_name: str (required) - Name of encoding ("o200k_base", "cl100k_base", etc.)
Returns: Encoding - Tokenizer instance for the specified encoding
Errors: ValueError -> Invalid encoding name
Notes: Primary entry point for getting tokenizer by encoding name

Type Information:
```python
from tiktoken import Encoding
```

### Function: encoding_for_model

Name: encoding_for_model  
Import Path: `import tiktoken`
Concrete Path: https://github.com/openai/tiktoken/blob/main/tiktoken/core.py
Signature: `tiktoken.encoding_for_model(model_name: str) -> Encoding`
Params:
- model_name: str (required) - OpenAI model name ("gpt-4o", "gpt-3.5-turbo", etc.)
Returns: Encoding - Appropriate tokenizer for the specified model
Errors: KeyError -> Unknown model name
Notes: Convenience function that maps model names to encodings automatically

### Class: Encoding

Name: Encoding
Import Path: `from tiktoken import Encoding`
Concrete Path: https://github.com/openai/tiktoken/blob/main/tiktoken/core.py
Methods:
- `encode(text: str, *, allowed_special: Union[Literal["all"], AbstractSet[str]] = set(), disallowed_special: Union[Literal["all"], AbstractSet[str]] = "all") -> List[int]`
- `decode(tokens: List[int]) -> str`
- `decode_single_token_bytes(token: int) -> bytes`

## Type Graph

Encoding -> contains -> encode: str -> List[int]
Encoding -> contains -> decode: List[int] -> str
get_encoding -> returns -> Encoding
encoding_for_model -> returns -> Encoding

## Request/Response Schemas

### Token Encoding
Purpose: Convert text to tokens for counting/processing
Request Shape: `{"text": str, "allowed_special": set, "disallowed_special": set}`
Response Shape: `List[int]` (token IDs)
Variants: Special token handling via parameters
Auth Requirements: None (offline operation)

### Token Decoding  
Purpose: Convert tokens back to text for verification
Request Shape: `{"tokens": List[int]}`
Response Shape: `str` (decoded text)
Variants: Single token decoding available
Auth Requirements: None (offline operation)

## Patterns

### Token Counting Pattern
```python
import tiktoken

# Get encoding for specific model
enc = tiktoken.encoding_for_model("gpt-4o")
tokens = enc.encode(text)
token_count = len(tokens)
```

### Cost Estimation Pattern
```python
# Token count × model pricing = estimated cost
token_count = len(enc.encode(text))
estimated_cost = token_count * MODEL_PRICE_PER_TOKEN
```

### Quota Management Pattern
```python
# Check if request would exceed quota
current_tokens = len(enc.encode(current_text))
if current_tokens > user_quota:
    raise QuotaExceededError()
```

## Differences vs Project

Gap: CodeWeaver needs integration with FastMCP middleware for request/response token tracking
Impact: Medium - Requires middleware instrumentation for automatic token counting
Suggested Adapter: Create TikTokenMiddleware that wraps MCP requests/responses with token counting

Blocking Questions:
- Which OpenAI models should CodeWeaver support by default?
- Should token counting be per-request, per-session, or per-user?
- How granular should cost tracking be (per tool call vs aggregated)?

Non-blocking Questions:
- Should we cache Encoding instances for performance?
- Do we need custom encodings for specialized use cases?

## Sources

[tiktoken-github | official | main | 5] - https://github.com/openai/tiktoken/blob/main/README.md
[context7-tiktoken | official | latest | 4] - Context7 documentation snippets from /openai/tiktoken
[openai-api-docs | official | current | 5] - Referenced through model compatibility