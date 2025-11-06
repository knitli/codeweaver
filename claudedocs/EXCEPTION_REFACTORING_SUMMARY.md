<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Exception Refactoring Summary

**Task**: Replace generic builtin exceptions with custom CodeWeaver exceptions in provider implementations

**Scope**: `/home/knitli/codeweaver-mcp/src/codeweaver/providers/*/providers/`

## Completed Files

### Embedding Providers - Base

**File**: `src/codeweaver/providers/embedding/providers/base.py`

- **Line 117**: `ValueError` → `ProviderError`
  - Context: Unexpected embedding provider output format
  - Added details: output_type, output_preview
  - Added suggestions for checking provider response format

- **Line 591**: `ValueError` → `CodeWeaverValidationError`
  - Context: Missing token_count or from_docs parameters
  - Added details: token_count_provided, from_docs_provided
  - Added suggestions for providing required parameters
  - **IMPORTANT**: Fixed logic bug - changed unconditional raise to else block

- **Line 608**: `ValueError` → `CodeWeaverValidationError`
  - Context: Embedding contains non-finite values (NaN/Inf)
  - Added details: embedding_size, has_nan, has_inf
  - Added suggestions for numerical stability checks

### Embedding Providers - OpenAI Factory

**File**: `src/codeweaver/providers/embedding/providers/openai_factory.py`

- **Line 263**: `ValueError` → `ProviderError`
  - Context: No response from OpenAI embeddings endpoint
  - Added details: provider, model, base_url, has_response, has_data
  - Added suggestions: API key validation, network connectivity, rate limits
  - Marked as potentially transient error

- **Line 273**: `TypeError` → `CodeWeaverValidationError`
  - Context: Expected CodeChunk instances for embedding
  - Added details: received_type, document_count
  - Added suggestions for proper document conversion

### Embedding Providers - Bedrock

**File**: `src/codeweaver/providers/embedding/providers/bedrock.py`

- **Line 513**: `TypeError` → `ProviderError`
  - Context: AWS Bedrock invalid response format for Cohere embedding
  - Added details: provider, model, expected_type, received_type
  - Added suggestions: model ID verification, API format validation

- **Line 582** (NOT YET COMPLETED): `ValueError` → `CodeWeaverValidationError`
  - Context: Input text exceeds Titan Embedding V2 maximum length (50,000 chars)
  - Needs: details (max_length, actual_length, excess_chars)
  - Needs: suggestions (chunk splitting, alternative models)

### Reranking Providers - Voyage

**File**: `src/codeweaver/providers/reranking/providers/voyage.py`

- **Line 73**: `RuntimeError` → `ProviderError`
  - Context: Voyage AI reranking request failed
  - Added details: provider, model, query_length, document_count, error_type
  - Added suggestions: API key check, network connectivity, rate limits, model validation
  - Preserved original exception as `__cause__`

### Reranking Providers - FastEmbed

**File**: `src/codeweaver/providers/reranking/providers/fastembed.py`

- **Line 99**: `RuntimeError` → `ProviderError`
  - Context: FastEmbed reranking execution failed
  - Added details: provider, model, query_length, document_count, batch_size, error_type
  - Added suggestions: model initialization, GPU/CUDA availability, memory issues, document validation
  - Preserved original exception as `__cause__`

## Pending Files (Not Yet Updated)

### Embedding Providers

1. **cohere.py** - No generic exceptions found (already uses ConfigurationError)
2. **mistral.py** - Need to check for generic exceptions
3. **google.py** - Need to check for generic exceptions
4. **huggingface.py** - Need to check for generic exceptions
5. **sentence_transformers.py** - Need to check for generic exceptions
6. **litellm.py** - Need to check for generic exceptions
7. **fastembed.py** (embedding) - Need to check for generic exceptions

### Reranking Providers

1. **bedrock.py** (reranking)
   - **Line 146**: `ValueError` → `CodeWeaverValidationError`
   - Context: "Exactly one of json_document or text_document must be provided"

2. **cohere.py** (reranking) - Need to check for generic exceptions

3. **sentence_transformers.py** (reranking)
   - **Line 107**: `TypeError` → `CodeWeaverValidationError`
   - Context: "Expected model_name to be str"

### Vector Store Providers

1. **vector_stores/utils.py**
   - **Line 26**: `ValueError` → `ConfigurationError`
   - Context: "No embedding model configured"

2. **vector_stores/base.py**
   - **Line 151**: `RuntimeError` → `ProviderError`
   - Context: "Vector store client is not initialized"

3. **vector_stores/__init__.py**
   - **Line 61**: `ValueError` → `ConfigurationError`
   - Context: "Qdrant provider selected but no qdrant config provided"
   - **Line 66**: `ValueError` → `ConfigurationError`
   - Context: Unknown vector store provider

### Registry and Configuration Files

1. **embedding/registry.py**
   - **Line 74**: `ValueError` - Need context check

2. **embedding/types.py**
   - **Line 162**: `ValueError` - Need context check
   - **Line 166**: `ValueError` - Need context check

3. **reranking/__init__.py**
   - **Line 72**: `ValueError` → `ConfigurationError`
   - Context: "Unknown reranking provider"

4. **reranking/capabilities/base.py**
   - **Line 135**: `TypeError` → `CodeWeaverValidationError`
   - Context: "Expected max_input to be an int"

5. **reranking/capabilities/voyage.py**
   - **Line 57**: `ValueError` - Need context check

6. **agent/agent_providers.py**
   - **Line 132**: `ValueError` → `ConfigurationError`
   - Context: "Unknown provider"

## Exception Mapping Reference

### ProviderError
**Use for**: API failures, provider integration issues, transient network errors
- API key issues
- Network connectivity problems
- Rate limiting
- Provider response format errors
- Model initialization failures

### ConfigurationError
**Use for**: Missing configuration, invalid settings, setup issues
- Missing API keys
- Invalid provider configuration
- Missing required configuration values
- Unknown provider names

### ValidationError (CodeWeaverValidationError)
**Use for**: Input validation, data format issues, business logic constraints
- Invalid input types
- Data exceeding limits (token counts, character limits)
- Missing required parameters
- Invalid parameter combinations

## Best Practices Applied

1. **Preserve Original Exceptions**: All `from e` clauses maintained
2. **Detailed Context**: Every exception includes relevant details dict
3. **Actionable Suggestions**: 3-5 concrete suggestions for each error
4. **Provider-Specific Info**: Model name, endpoint used, provider identifier
5. **Transient Error Marking**: API failures marked as potentially transient
6. **Error Type Tracking**: Original exception type captured in details

## Verification Checklist

- [x] All custom exceptions imported from `codeweaver.exceptions`
- [x] Original exception preserved with `from e`
- [x] Details dict includes provider, model, relevant metrics
- [x] Suggestions list provides 3-5 actionable items
- [x] Files compile without syntax errors
- [ ] Full test suite passes (pending)
- [ ] All remaining files updated
- [ ] Documentation updated

## Statistics

- **Total Files Examined**: 11 provider files
- **Files Fully Updated**: 5 (base.py, openai_factory.py, bedrock.py-partial, voyage.py, fastembed.py)
- **Generic Exceptions Replaced**: 7 instances
- **Pending Updates**: ~15 instances across remaining files

## Next Steps

1. Complete bedrock.py Line 582 update
2. Update remaining reranking providers (bedrock, sentence_transformers)
3. Update vector_stores files (utils.py, base.py, __init__.py)
4. Update registry and configuration files
5. Run full test suite
6. Verify no regressions in error handling
7. Update provider documentation if needed
