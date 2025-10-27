<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# CodeWeaver Chunking Architecture

This document outlines a practical, extensible architecture for chunking files into context-preserving `CodeChunk`s, grounded in the project’s existing data structures and capabilities.

Goals:
- Preserve as much useful context as possible while staying under model limits
- Prefer semantic boundaries (AST nodes, headings) over arbitrary splits
- Be token-aware and robust to metadata overhead
- Keep behavior predictable, configurable, and testable


## Core Concepts

- Inputs/Outputs
  - Input: `DiscoveredFile` (path, `ExtKind`) and file contents
  - Output: `list[CodeChunk]` with accurate `line_range: Span`, `language`, `ext_kind`, and metadata
- Constraints
  - Respect effective token budget derived from model capabilities (embedding and, optionally, reranking)
  - Minimize overlap unless textual splits inside a semantic unit are unavoidable
  - Account for metadata overhead in budgets


## High-level Flow

- ChunkRouter (strategy selection)
  1. If semantic (AST) available: AstChunker
  2. Else if language-specific splitter: StructuredTextChunker (e.g., Markdown, reST)
  3. Else: FallbackChunker (token-aware, line-aligned)

- Post-processing
  - Final token check (serialized-for-embedding), micro-adjust splits if needed
  - Attach/normalize metadata (`name`, `tags`, `semantic_meta`), compute title


## Governing Objects

- ChunkGovernor
  - Source of hard limits and defaults derived from model capabilities
  - Fields used:
    - `capabilities: tuple[EmbeddingModelCapabilities | RerankingModelCapabilities, ...]`
    - `chunk_limit: PositiveInt` (min of contexts)
    - `simple_overlap: int` (20% of chunk_limit, clamped 50–200)
  - Extensions (suggested):
    - safety_margin_pct: float (default 0.1) reserved for metadata/serialization overhead
    - prefer_zero_overlap_on_semantics: bool (default True)
    - min_chunk_tokens: int (avoid pathological tiny chunks)

- ChunkMicroManager
  - Per-file decision maker; computes the effective budget and overlap for current file
  - Responsibilities:
    - Selects concrete chunker via router
    - Provides access to token estimator and effective limits (adjusted for safety margin)
    - Performs final pass checks and micro-adjustments


## Token Budgeting

- Compute `effective_chunk_limit = min(cap.context_window) * (1 - safety_margin_pct)`
- Use project utilities (see `estimate_tokens` in `_utils`) with the embedding model’s tokenizer settings (`tokenizer`, `tokenizer_model` in capabilities)
- For splits created inside a semantic unit, apply `overlap = governor.simple_overlap`; otherwise, use zero overlap


## Strategy 1: AstChunker (Semantic languages)

- Sources: `codeweaver._ast_grep`, `SemanticSearchLanguage`
- Unit of split: language-appropriate AST nodes (functions, classes, modules, top-level declarations)
- Approach:
  1. Parse file using ast-grep
  2. Build an ordered list of candidate nodes with their `Range` -> convert to line `Span`
  3. Normalize: collapse trivial nodes (e.g., docstring-only or 1–2 line stubs) into neighbors up to budget
  4. Size control:
     - If node ≤ budget: emit one chunk at node boundary (overlap 0)
     - If node > budget: recursively descend into child nodes; if still > budget, degrade to textual split (line/paragraph), apply overlap
  5. Metadata:
     - `metadata.semantic_meta` includes `language`, node kind(s), symbol name, parents, file-level imports/exports if available
     - `metadata.name` = best available display name (e.g., function/class identifier)
  6. Parent-child:
     - Set `parent_id` to a stable per-file UUID for all chunks from the same file (see Span source id strategy below)



## Strategy 2: DelimiterChunker (Structured Text and Fallback)

- Uses language-specific delimiter patterns for chunking when semantic parsing is unavailable
- Supports 170+ languages through pattern-based boundary detection
- Markdown specifics:
  - Split by headers using delimiter patterns; use the lowest header level that keeps chunks ≤ budget
  - Keep YAML frontmatter as a single preamble chunk or attach to first section's metadata
  - If a section > budget, recursively split by subheaders; if none, split by paragraphs/fences with overlap
  - Metadata:
    - `metadata.context` contains delimiter information, nesting levels, and boundary types
    - `metadata.name` is section title when available

- reStructuredText specifics:
  - Split by underline-style sections and directives; similar recursive approach


## Strategy 3: FallbackChunker (Token-aware, line-aligned)

- Split by lines with soft paragraph boundaries when possible
- Use `effective_chunk_limit` and `simple_overlap`
- Keep chunk boundaries on newline; avoid splitting mid-code-fence or mid-UTF-8 sequence
- Metadata minimal; only `name` (e.g., “Filename: X, lines A–B”) and `ext_kind`


## Span and Stability

`CodeChunk.line_range` is a `Span` with a `source_id` used to relate spans within the same source. For chunk operations on a file to be consistent, all spans from a file should share the same `source_id`.

- Strategy:
  - Maintain a per-process `dict[Path, UUID7]` registry so all `Span`s for the same file share an ID
  - When creating a chunk, use `Span(start, end, source_id_for(file))`

This enables robust set-like span operations and clean merging/splitting in future passes.


## Metadata and Serialization Overhead

- `serialize_for_embedding` includes only selected metadata keys; still, reserve margin (`safety_margin_pct`)
- Finalization step: serialize each chunk and estimate tokens; if above budget, trim/adjust by:
  1. Dropping non-essential metadata (not in the selected keys)
  2. If still over: re-split the content (small paragraph split with overlap)


## Interfaces (sketch)

- IChunker
  - `chunk(file: DiscoveredFile, governor: ChunkGovernor) -> list[CodeChunk]`

- ChunkRouter
  - `select(ext_kind: ExtKind) -> IChunker` (AstChunker | StructuredTextChunker | FallbackChunker)

- TokenEstimator
  - Provided by MicroManager via embedding capabilities; wraps `estimate_tokens`


## Edge Cases and Mitigations

- Huge single node/section > budget: descend or textual split with overlap; optionally include a synthetic “header” sub-chunk for context
- Extremely long lines: prefer line-aware but allow character-based fallback within a line, then rejoin on nearest delimiter
- Mixed encodings: open in binary then decode with `errors="replace"`; record decoding issues in metadata
- Frontmatter/metadata blocks in docs: treat as atomic preamble
- Very small files: avoid tiny chunks by `min_chunk_tokens` gate; emit single chunk


## Phased Implementation Plan

- Phase 1 (MVP)
  - Implement FallbackChunker (line-aware, token-aware), registry for per-file Span IDs
  - Implement Markdown splitter via headers; recursive paragraph fallback
  - Route selection via ChunkRouter + MicroManager
  - Tests: tiny files, large files, markdown with headers, paragraphs fallback

- Phase 2 (Semantic Code)
  - AstChunker for ast-grep supported languages (SemanticSearchLanguage's members)t; node patterns and metadata population
  - Recursive node descent and merging of small neighbors
  - Tests per language (happy path + oversized node)

- Phase 3 (Enhancements)
  - Add reST, LaTeX structures; language-specific refinements (Java, Go, Rust, etc.)
  - Summarization hooks to populate `metadata.name` and lightweight section summaries
  - Optional: context chunk embedding support (governor flag + extra context field)


## Minimal Contracts to Validate

- For any file, `sum(len(c.content) for c in chunks) ≈ len(file_contents)` up to intentional overlaps
- No chunk exceeds `effective_chunk_limit` on serialized-for-embedding token estimate
- Spans cover the intended lines; per-file span source IDs are stable within a run
- Metadata keys used by `serialize_for_embedding` are set where applicable


## Testing Suggestions

- Unit tests per chunker with fixtures:
  - Happy path (semantic boundaries fit)
  - Oversized semantic unit (recursive descent)
  - No semantic support (fallback behavior, overlaps)
  - Markdown with deep heading hierarchy and code fences

- Property-ish checks:
  - Token budget never exceeded
  - Stable `parent_id` and Span source IDs per file


## Notes

- Keep overlap minimal; it’s a crutch when we can’t split at semantic boundaries
- Prefer setting `metadata.name` and a compact `semantic_meta` over large summaries
- Defer expensive token checks to a final pass rather than every candidate split
