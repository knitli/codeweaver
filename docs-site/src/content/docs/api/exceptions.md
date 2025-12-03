---
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

title: exceptions
description: API reference for exceptions
---

# exceptions

Unified exception hierarchy for CodeWeaver.

This module provides a single, unified exception hierarchy to prevent exception
proliferation. All CodeWeaver exceptions inherit from CodeWeaverError and
are organized into five primary categories.

## Classes

## class `LocationInfo(NamedTuple)`

Location information for where an exception was raised.

Attributes:
    filename: The name of the file
    line_number: The line number in the file

### Methods

#### `from_frame(cls, frame: int = 2) -> LocationInfo | None`

Create LocationInfo from a stack frame.

Args:
    frame: The stack frame to inspect (default: 2)

Returns:
    LocationInfo instance or None if unavailable.


## class `CodeWeaverError(Exception)`

Base exception for all CodeWeaver errors.

Provides structured error information including details and suggestions
for resolution.

### Methods


## class `InitializationError(CodeWeaverError)`

Initialization and startup errors.

Raised when there are issues during application startup, such as missing
dependencies, configuration errors, or environment setup problems.


## class `ConfigurationError(CodeWeaverError)`

Configuration and settings errors.

Raised when there are issues with configuration files, environment variables,
settings validation, or provider configuration.


## class `ProviderError(CodeWeaverError)`

Provider integration errors.

Raised when there are issues with embedding providers, vector stores,
or other external service integrations.


## class `ModelSwitchError(ProviderError)`

Model switching detection error.

Raised when the system detects that the embedding model has changed
from what was used to create the existing vector store collection.


## class `RerankingProviderError(ProviderError)`

Reranking provider errors.

Raised when there are issues specific to the reranking provider, such as
invalid input formats, failed API calls, or unexpected response structures.


## class `ProviderSwitchError(ProviderError)`

Provider switching detection error.

Raised when the system detects that the vector store collection was created
with a different provider than the currently configured one.


## class `DimensionMismatchError(ProviderError)`

Embedding dimension mismatch error.

Raised when embedding dimensions don't match the vector store collection
configuration.


## class `CollectionNotFoundError(ProviderError)`

Collection not found error.

Raised when attempting operations on a non-existent collection.


## class `PersistenceError(ProviderError)`

Persistence operation error.

Raised when in-memory provider persistence operations fail.


## class `IndexingError(CodeWeaverError)`

File indexing and processing errors.

Raised when there are issues with file discovery, content processing,
or index building operations.


## class `QueryError(CodeWeaverError)`

Query processing and search errors.

Raised when there are issues with query validation, search execution,
or result processing.


## class `ValidationError(CodeWeaverError)`

Input validation and schema errors.

Raised when there are issues with input validation, data model validation,
or schema compliance.


## class `MissingValueError(CodeWeaverError)`

Missing value errors.

Raised when a required value is missing in the context of an operation.
This is a specific case of validation error.

### Methods


## Functions
