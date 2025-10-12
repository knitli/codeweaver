# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Base chunker services and definitions.

CodeWeaver has a robust chunking system that allows it to extract meaningful information from any codebase. Chunks are created based on a few factors:

1. The kind of chunk available.

    - When we have a tree-sitter grammar for a language (there are currently 26 supported languages, see `codeweaver.language.SemanticSearchLanguage`), then semantic chunking is the primary strategy.
    - If semantic chunking isn't available, we fall back to specialized chunkers for the language, if we have one. These come from `langchain_text_splitters` and include chunkers for markdown, latex, protobuf, restructuredtext, perl, powershell, and visualbasic6.
    - If one of those isn't available, we again fall back to a set of chunkers defined in
"""

from __future__ import annotations

import logging

from abc import ABC, abstractmethod
from datetime import UTC, datetime
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, NamedTuple, cast

from ast_grep_py import SgNode
from langchain_core.documents import Document
from langchain_text_splitters import (
    ExperimentalMarkdownSyntaxTextSplitter,
    Language,
    LatexTextSplitter,
    MarkdownTextSplitter,
    RecursiveCharacterTextSplitter,
)
from pydantic import UUID7, ConfigDict, Field, PositiveInt, computed_field

from codeweaver._common import BasedModel
from codeweaver._data_structures import (
    ChunkType,
    CodeChunk,
    DiscoveredFile,
    ExtKind,
    Metadata,
    SemanticMetadata,
)
from codeweaver._utils import uuid7
from codeweaver.embedding.capabilities.base import EmbeddingModelCapabilities
from codeweaver.language import Chunker, ConfigLanguage, SemanticSearchLanguage
from codeweaver.reranking.capabilities.base import RerankingModelCapabilities


if TYPE_CHECKING:
    from codeweaver.semantic._ast_grep import AstNode


SAFETY_MARGIN = 0.1
"""A safety margin to apply to chunk sizes to account for metadata and tokenization variability."""

SPLITTER_AVAILABLE = {
    "protobuf": "proto",
    "restructuredtext": "rst",
    "markdown": "markdown",
    "latex": "latex",
    "perl": "perl",
    "powershell": "powershell",
    "visualbasic6": "visualbasic6",
}
"""Languages with langchain_text_splitters support that don't have semantic search support. The keys are the name of the language as defined in `codeweaver._supported_languages.SecondarySupportedLanguage`, and the values are the name of the language as defined in `langchain_text_splitters.Language`."""


class ChunkerEntry(NamedTuple):
    """An entry in the chunker registry."""

    chunker_kind: Chunker
    chunker: type[BaseChunker]


class ChunkGovernor(BasedModel):
    """Configuration for chunking behavior."""

    model_config = BasedModel.model_config | ConfigDict(validate_assignment=True, defer_build=True)

    capabilities: Annotated[
        tuple[EmbeddingModelCapabilities | RerankingModelCapabilities, ...],
        Field(description="""The model capabilities to infer chunking behavior from."""),
    ] = ()

    @computed_field
    @cached_property
    def chunk_limit(self) -> PositiveInt:
        """The absolute maximum chunk size in tokens."""
        return min(capability.context_window for capability in self.capabilities)

    @computed_field
    @cached_property
    def simple_overlap(self) -> int:
        """A simple overlap value to use for chunking without context or external factors.

        Calculates as 20% of the chunk_limit, clamped between 50 and 200 tokens. Practically, we only use this value when we can't determine a better overlap based on the tokenizer or other factors. `ChunkMicroManager` may override this value based on more complex logic, aiming to identify and encapsulate logical boundaries within the text with no need for overlap.
        """
        return int(max(50, min(200, self.chunk_limit * 0.2)))


class BaseChunker(ABC):
    """Base class for chunkers."""

    _governor: ChunkGovernor
    chunker: Chunker

    def __init__(self, governor: ChunkGovernor) -> None:
        """Initialize the chunker."""
        self._governor = governor

    @abstractmethod
    def chunk(
        self, content: str, *, file_path: Path | None = None, context: dict[str, Any] | None = None
    ) -> list[CodeChunk]:
        """Chunk the given content into code chunks using `self._governor` settings."""

    def next_chunker(self) -> ChunkMicroManager:
        """Get a ChunkMicroManager instance for this chunker."""
        return ChunkMicroManager(self._governor)

    @property
    def governor(self) -> ChunkGovernor:
        """Get the ChunkGovernor instance."""
        return self._governor

    @property
    def chunk_limit(self) -> PositiveInt:
        """Get the chunk limit from the governor."""
        return self._governor.chunk_limit

    @property
    def simple_overlap(self) -> int:
        """Get the simple overlap from the governor."""
        return self._governor.simple_overlap


class ChunkMicroManager:
    """Handles decision logic based on factors like chunk size and type, max chunk_size, etc. Deciding on where definitive splits should occur at a per-chunk basis."""

    def __init__(self, governor: ChunkGovernor) -> None:
        """Initialize the ChunkMicroManager with a ChunkGovernor. The governor provides the limits and settings for chunking."""
        self._governor = governor

    def governor(self) -> ChunkGovernor:
        """Get the ChunkGovernor instance."""
        return self._governor

    def _semantic_available(self, ext: ExtKind) -> bool:
        """Check if semantic chunking is available for the given file extension."""
        lang = ext.language
        return isinstance(lang, SemanticSearchLanguage) or (
            isinstance(lang, ConfigLanguage) and lang.is_semantic_search_language
        )

    def _special_splitter_available(self, ext: ExtKind) -> bool:
        """Check if a special splitter is available for the given file extension."""
        if not isinstance(ext.language, str):
            return False
        language = ext.language.lower()
        return (
            language in Language.__members__
            or language in Language._value2member_map_
            or language in SPLITTER_AVAILABLE
        )

    def decide_chunking(self, file: DiscoveredFile, content: str) -> list[CodeChunk]:
        """Decide how to chunk the text based on the governor's settings."""
        if file.is_binary and not file.is_text:
            return []
        content = content.rstrip()
        if not content.strip():
            return []

        if self._semantic_available(file.ext_kind):
            return self._chunk_with_ast(file, content)

        if self._special_splitter_available(file.ext_kind):
            # Use langchain text splitters
            return self._chunk_with_langchain(file, content)

        # Fallback chunking logic
        return self._chunk_fallback(file, content)

    def _chunk_with_langchain(self, file: DiscoveredFile, content: str) -> list[CodeChunk]:
        """Chunk using langchain text splitters."""
        from codeweaver._utils import estimate_tokens
        from codeweaver.services.chunker.registry import source_id_for

        logger = logging.getLogger(__name__)

        # Calculate effective limits with safety margin
        effective_chunk_limit = int(self._governor.chunk_limit * (1 - SAFETY_MARGIN))
        overlap = self._governor.simple_overlap

        language_name = str(file.ext_kind.language).lower()
        source_id = source_id_for(file.path)

        try:
            # Use specialized splitters for specific languages
            if language_name == "markdown":
                # Use ExperimentalMarkdownSyntaxSplitter for better semantic chunking
                headers_to_split_on = [("#", "Header 1"), ("##", "Header 2"), ("###", "Header 3")]
                splitter = ExperimentalMarkdownSyntaxTextSplitter(
                    headers_to_split_on=headers_to_split_on, strip_headers=False
                )
                # Get documents with header metadata
                docs = splitter.split_text(content)

                # If chunks are too large, further split them
                if any(estimate_tokens(doc.page_content) > effective_chunk_limit for doc in docs):
                    text_splitter = MarkdownTextSplitter(
                        chunk_size=effective_chunk_limit,
                        chunk_overlap=overlap,
                        length_function=estimate_tokens,
                    )
                    final_docs: list[Document] = []
                    for doc in docs:
                        if estimate_tokens(doc.page_content) > effective_chunk_limit:
                            split_docs = text_splitter.split_documents([doc])
                            final_docs.extend(split_docs)
                        else:
                            final_docs.append(doc)
                    docs = final_docs

                return self._convert_langchain_docs_to_chunks(docs, file, source_id)

            if language_name == "latex":
                # Use specialized LaTeX splitter
                splitter = LatexTextSplitter(
                    chunk_size=effective_chunk_limit,
                    chunk_overlap=overlap,
                    length_function=estimate_tokens,
                )
                text_chunks = splitter.split_text(content)
                return self._convert_text_chunks_to_code_chunks(text_chunks, file, source_id)

            if language_name in SPLITTER_AVAILABLE:
                # Use language-specific recursive splitter
                lang_enum = Language(SPLITTER_AVAILABLE[language_name])
                splitter = RecursiveCharacterTextSplitter.from_language(
                    language=lang_enum,
                    chunk_size=effective_chunk_limit,
                    chunk_overlap=overlap,
                    length_function=estimate_tokens,
                )
                text_chunks = splitter.split_text(content)
                return self._convert_text_chunks_to_code_chunks(text_chunks, file, source_id)

        except Exception as e:
            # Fall back to basic chunking if langchain fails
            logger.warning("langchain chunking failed for %s: %s", file.path, e)

        return self._chunk_fallback(file, content)

    def _chunk_fallback(self, file: DiscoveredFile, content: str) -> list[CodeChunk]:
        """Basic fallback chunking."""
        from codeweaver._utils import estimate_tokens
        from codeweaver.services.chunker.registry import source_id_for

        # Calculate effective limits with safety margin
        effective_chunk_limit = int(self._governor.chunk_limit * (1 - SAFETY_MARGIN))
        overlap = self._governor.simple_overlap

        source_id = source_id_for(file.path)

        # Use basic text splitter
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=effective_chunk_limit,
            chunk_overlap=overlap,
            length_function=estimate_tokens,
            separators=["\n\n", "\n", ".", "!", "?", ";", " ", ""],
        )

        text_chunks = splitter.split_text(content)
        return self._convert_text_chunks_to_code_chunks(text_chunks, file, source_id)

    def _convert_langchain_docs_to_chunks(
        self, docs: list[Document], file: DiscoveredFile, source_id: UUID7
    ) -> list[CodeChunk]:
        """Convert langchain Documents to CodeChunk objects."""
        chunks: list[CodeChunk] = []
        current_line = 1

        for doc_idx, doc in enumerate(docs):
            if not doc.page_content.strip():
                continue

            # Find line range for this chunk
            chunk_lines = doc.page_content.count("\n") + 1
            start_line = current_line
            end_line = current_line + chunk_lines - 1

            # Create metadata from langchain document metadata
            metadata: Metadata = {
                "chunk_id": uuid7(),
                "created_at": datetime.now(UTC).timestamp(),
                "name": f"{file.path.name}, part {doc_idx + 1}",
                "semantic_meta": None,
                "tags": (str(file.ext_kind.language),),  # tuple[str]
                "context": doc.metadata or {},  # type: ignore
            }

            # Add header information if available
            if (
                doc.metadata  # type: ignore
                and doc.metadata.get("Header")  # type: ignore
                and any(key.lower().startswith("header") for key in doc.metadata)  # type: ignore
                and (
                    header_levels := sorted([  # type: ignore
                        (int(key.split()[-1]), value)  # type: ignore
                        for key, value in doc.metadata.items()  # type: ignore
                        if key.lower().startswith("header")  # pyright: ignore[reportUnknownMemberType]
                    ])
                )
            ):
                metadata["name"] = header_levels[-1][1]  # Most specific header

            chunk = self._create_chunk_from_parts(
                content=doc.page_content.rstrip(),
                start_line=start_line,
                end_line=end_line,
                file=file,
                source_id=source_id,
                metadata=metadata,
            )
            chunks.append(chunk)
            current_line = end_line + 1

        return chunks

    def _convert_text_chunks_to_code_chunks(
        self, text_chunks: list[str], file: DiscoveredFile, source_id: UUID7
    ) -> list[CodeChunk]:
        """Convert text chunks to CodeChunk objects."""
        chunks: list[CodeChunk] = []
        current_line = 1

        for chunk_idx, chunk_text in enumerate(text_chunks):
            if not chunk_text.strip():
                continue

            # Estimate line range
            chunk_lines = chunk_text.count("\n") + 1
            start_line = current_line
            end_line = current_line + chunk_lines - 1

            metadata: Metadata = {
                "chunk_id": uuid7(),
                "created_at": datetime.now(UTC).timestamp(),
                "name": f"{file.path.name}, part {chunk_idx + 1}",
                "semantic_meta": None,
                "tags": (str(file.ext_kind.language),),  # tuple[str]
            }

            chunk = self._create_chunk_from_parts(
                content=chunk_text.rstrip(),
                start_line=start_line,
                end_line=end_line,
                file=file,
                source_id=source_id,
                metadata=metadata,
            )
            chunks.append(chunk)
            current_line = end_line + 1

        return chunks

    def _chunk_with_ast(self, file: DiscoveredFile, content: str) -> list[CodeChunk]:
        """Chunk using AST-based semantic analysis."""
        from codeweaver.semantic._ast_grep import AstNode
        from codeweaver.services.chunker.registry import source_id_for

        logger = logging.getLogger(__name__)

        try:
            # Parse the content using ast-grep
            language = file.ext_kind.language
            if not isinstance(language, SemanticSearchLanguage):
                # Fallback to non-semantic chunking
                return self._chunk_fallback(file, content)

            from ast_grep_py import SgRoot as AstGrepRoot

            root = AstGrepRoot(content, str(language))
            ast_node: AstNode[SgNode] = AstNode.from_sg_node(root.root(), language)  # type: ignore

            # Calculate effective limits with safety margin
            effective_chunk_limit = int(self._governor.chunk_limit * (1 - SAFETY_MARGIN))
            source_id = source_id_for(file.path)

            # Extract semantic chunks from AST
            chunks = self._extract_semantic_chunks(
                ast_node, content, file, source_id, effective_chunk_limit
            )

            if not chunks:
                # Fallback if AST parsing didn't produce useful chunks
                logger.debug("AST parsing produced no chunks for %s, falling back", file.path)
                return self._chunk_fallback(file, content)

        except Exception as e:
            # Fallback to non-semantic chunking if AST parsing fails
            logger.warning("AST chunking failed for %s: %s, falling back", file.path, e)
            return self._chunk_fallback(file, content)
        else:
            return chunks

    def _extract_semantic_chunks(
        self,
        root_node: AstNode[SgNode],
        content: str,
        file: DiscoveredFile,
        source_id: UUID7,
        effective_limit: int,
    ) -> list[CodeChunk]:
        """Extract semantic chunks from AST nodes with importance-based prioritization."""
        chunks: list[CodeChunk] = []
        content_lines = content.splitlines(keepends=True)

        # Collect all meaningful nodes using modern semantic analysis
        candidate_nodes: list[AstNode[SgNode]] = []
        self._collect_semantic_nodes(root_node, candidate_nodes)

        if not candidate_nodes:
            # If no semantic nodes found, try to get top-level nodes
            candidate_nodes = list(root_node.children)

        # Score and prioritize nodes by importance and position
        scored_nodes = self._score_and_prioritize_nodes(candidate_nodes)

        # Process each candidate node with importance-aware chunking
        for node, importance_score in scored_nodes:
            if not node.text.strip():
                continue

            node_chunks = self._process_semantic_node_with_importance(
                node, importance_score, content_lines, file, source_id, effective_limit
            )
            chunks.extend(node_chunks)

        # Handle any gaps between semantic chunks with fallback chunking
        return self._fill_gaps_with_fallback(chunks, content, file, source_id, effective_limit)

    def _collect_semantic_nodes(
        self, root_node: AstNode[SgNode], candidate_nodes: list[AstNode[SgNode]]
    ) -> None:
        """Recursively collect all meaningful AST nodes for semantic analysis."""
        # Add current node if it's named and meaningful
        if root_node.is_named and root_node.text.strip():
            candidate_nodes.append(root_node)

        # Recursively process children
        for child in root_node.children:
            self._collect_semantic_nodes(child, candidate_nodes)

    def _score_and_prioritize_nodes(
        self, nodes: list[AstNode[SgNode]]
    ) -> list[tuple[AstNode[SgNode], float]]:
        """Score nodes by importance and return them sorted by priority and position."""
        scored_nodes = [
            (node, node.importance_score) for node in nodes if hasattr(node, "importance_score")
        ]

        # Sort by importance (descending) then by position (ascending)
        scored_nodes.sort(key=lambda x: (-x[1], x[0].range.start.line, x[0].range.start.column))
        return cast(list[tuple[AstNode[SgNode], float]], scored_nodes)

    def _process_semantic_node_with_importance(
        self,
        node: AstNode[SgNode],
        importance_score: float,
        content_lines: list[str],
        file: DiscoveredFile,
        source_id: UUID7,
        effective_limit: int,
    ) -> list[CodeChunk]:
        """Process a semantic node with importance-aware chunk creation."""
        # Use the original process_semantic_node method but enhance metadata with importance
        chunks = self._process_semantic_node(node, content_lines, file, source_id, effective_limit)

        # Add importance metadata to all chunks
        for chunk in chunks:
            if chunk.metadata and chunk.metadata.get("semantic_meta"):
                chunk.metadata["semantic_meta"]["importance_score"] = importance_score  # type: ignore
                chunk.metadata["semantic_meta"]["category"] = str(node.semantic_category)  # type: ignore

        return chunks

    def _get_semantic_node_kinds(self, language: str) -> list[str]:
        """Get the semantic node kinds to look for based on language."""
        # Language-specific node kinds for semantic boundaries
        language_kinds = {
            "python": [
                "function_definition",
                "class_definition",
                "import_statement",
                "import_from_statement",
            ],
            "javascript": [
                "function_declaration",
                "function_expression",
                "class_declaration",
                "method_definition",
                "import_statement",
            ],
            "typescript": [
                "function_declaration",
                "function_expression",
                "class_declaration",
                "method_definition",
                "interface_declaration",
                "import_statement",
            ],
            "java": [
                "method_declaration",
                "class_declaration",
                "interface_declaration",
                "import_declaration",
            ],
            "rust": ["function_item", "struct_item", "impl_item", "trait_item", "use_declaration"],
            "go": [
                "function_declaration",
                "method_declaration",
                "type_declaration",
                "import_declaration",
            ],
            "cpp": [
                "function_definition",
                "class_specifier",
                "namespace_definition",
                "template_declaration",
            ],
            "c": ["function_definition", "struct_specifier", "typedef_declaration"],
        }

        return language_kinds.get(language.lower(), ["function_definition", "class_definition"])

    def _process_semantic_node(
        self,
        node: AstNode[SgNode],
        content_lines: list[str],
        file: DiscoveredFile,
        source_id: UUID7,
        effective_limit: int,
    ) -> list[CodeChunk]:
        """Process a single semantic node, potentially splitting if too large."""
        from codeweaver._utils import estimate_tokens

        node_text = node.text
        if estimate_tokens(node_text) <= effective_limit:
            # Node fits within limit, create single chunk
            return [self._create_semantic_chunk_from_node(node, file, source_id)]

        # Node is too large, try to split it
        return self._split_large_semantic_node(
            node, content_lines, file, source_id, effective_limit
        )

    def _split_large_semantic_node(
        self,
        node: AstNode[SgNode],
        content_lines: list[str],
        file: DiscoveredFile,
        source_id: UUID7,
        effective_limit: int,
    ) -> list[CodeChunk]:
        """Split a large semantic node into smaller chunks."""
        from codeweaver._utils import estimate_tokens

        chunks: list[CodeChunk] = []

        # Try to find child nodes that are semantic units
        child_nodes = list(node.children)
        if child_nodes:
            for child in child_nodes:
                if (
                    child.text.strip() and estimate_tokens(child.text) > 20
                ):  # Skip punctuation nodes
                    child_chunks = self._process_semantic_node(
                        child, content_lines, file, source_id, effective_limit
                    )
                    chunks.extend(child_chunks)

        if not chunks:
            # No useful child nodes, fall back to textual splitting
            chunk = self._create_semantic_chunk_from_node(node, file, source_id)
            # Split the chunk content using textual approach
            text_chunks = self._split_chunk_textually(chunk, effective_limit)
            chunks.extend(text_chunks)

        return chunks

    def _split_chunk_textually(self, chunk: CodeChunk, effective_limit: int) -> list[CodeChunk]:
        """Split a chunk using textual approach when semantic splitting fails."""
        from langchain_text_splitters import RecursiveCharacterTextSplitter

        from codeweaver._utils import estimate_tokens

        overlap = self._governor.simple_overlap
        splitter = RecursiveCharacterTextSplitter(
            chunk_size=effective_limit,
            chunk_overlap=overlap,
            length_function=estimate_tokens,
            separators=["\n\n", "\n", ".", "!", "?", ";", " ", ""],
        )

        text_parts = splitter.split_text(chunk.content)
        if len(text_parts) <= 1:
            return [chunk]

        chunks: list[CodeChunk] = []
        current_line = chunk.line_range.start

        for idx, part in enumerate(text_parts):
            if not part.strip():
                continue

            lines = part.count("\n") + 1
            start_line = current_line
            end_line = current_line + lines - 1

            # Create metadata for the split chunk
            base_name = chunk.metadata.get("name") if chunk.metadata else None
            name = f"{base_name}, part {idx + 1}" if base_name else f"Split part {idx + 1}"

            metadata: Metadata = {
                "chunk_id": chunk.chunk_id if idx == 0 else uuid7(),
                "created_at": datetime.now(UTC).timestamp(),
                "name": name,
                "semantic_meta": chunk.metadata.get("semantic_meta") if chunk.metadata else None,
                "tags": chunk.metadata.get("tags") if chunk.metadata else None,
            }

            # Create a temporary DiscoveredFile for the chunk
            from codeweaver.services.chunker.registry import source_id_for

            temp_file = DiscoveredFile.from_chunk(chunk)
            split_chunk = self._create_chunk_from_parts(
                content=part.rstrip(),
                start_line=start_line,
                end_line=end_line,
                file=temp_file,
                source_id=chunk.parent_id or source_id_for(cast(Path, chunk.file_path)),
                metadata=metadata,
                chunk_type=ChunkType.SEMANTIC,
            )
            chunks.append(split_chunk)
            current_line = end_line + 1

        return chunks

    def _create_semantic_chunk_from_node(
        self, node: AstNode[SgNode], file: DiscoveredFile, source_id: UUID7
    ) -> CodeChunk:
        """Create a CodeChunk from an AST node with semantic metadata."""
        # Convert ast-grep Range to line numbers
        start_line = node.range.start.line
        end_line = node.range.end.line

        # Extract semantic information
        node_kind = node.kind
        node_text = node.text

        # Create rich semantic metadata
        semantic_meta = SemanticMetadata.model_validate({
            "language": node.language,
            "symbol": node.symbol,
            "primary_node": node,
            "children": node.children,
            "node_id": node.node_id,
            "parent_node_id": node.parent_node_id,
            "is_partial_node": True,
        })
        metadata: Metadata = {
            "chunk_id": uuid7(),
            "created_at": datetime.now(UTC).timestamp(),
            "name": semantic_meta.symbol or f"{node_kind.replace('_', ' ').title()}",
            "semantic_meta": semantic_meta,
            "tags": (str(file.ext_kind.language), node_kind),
            "context": self._extract_context_info(node),
        }

        return self._create_chunk_from_parts(
            content=node_text.rstrip(),
            start_line=start_line,
            end_line=end_line,
            file=file,
            source_id=source_id,
            metadata=metadata,
            chunk_type=ChunkType.SEMANTIC,
        )

    def _extract_function_name(self, node: AstNode[SgNode]) -> str | None:
        """Extract function name from node."""
        name_node = node.get_match("name")
        if name_node:
            return name_node.text.strip()

        return next(
            (
                child.text.strip()
                for child in node.children
                if child.kind == "identifier" and child.text.strip()
            ),
            None,
        )

    def _extract_class_name(self, node: AstNode[SgNode]) -> str | None:
        """Extract class name from node."""
        name_node = node.get_match("name")
        if name_node:
            return name_node.text.strip()

        return next(
            (
                child.text.strip()
                for child in node.children
                if child.kind == "identifier" and child.text.strip()
            ),
            None,
        )

    def _extract_import_name(self, node: AstNode[SgNode]) -> str | None:
        """Extract import name from node."""
        text = node.text.strip()
        return text.split("\n")[0] if text else None

    def _extract_context_info(self, node: AstNode[SgNode]) -> dict[str, Any] | None:
        """Extract additional context information from the node."""
        try:
            context: dict[str, Any] = {}

            # Try to find parent context (class, namespace, etc.)
            parent = node.parent
            if (
                parent
                and parent.kind in ["class_definition", "class_declaration", "namespace_definition"]
                and (parent_name := parent.symbol)
            ):
                context["parent_scope"] = {"name": parent_name, "kind": parent.kind}
        except Exception:
            return None
        else:
            return context or None

    def _fill_gaps_with_fallback(
        self,
        semantic_chunks: list[CodeChunk],
        content: str,
        file: DiscoveredFile,
        source_id: UUID7,
        effective_limit: int,
    ) -> list[CodeChunk]:
        """Fill gaps between semantic chunks with fallback chunking if needed."""
        # for now we just return them.
        # TODO: implement gap filling logic
        return semantic_chunks

    def _create_chunk_from_parts(
        self,
        content: str,
        start_line: int,
        end_line: int,
        file: DiscoveredFile,
        source_id: UUID7,
        metadata: Metadata | None = None,
        chunk_type: ChunkType = ChunkType.TEXT_BLOCK,
    ) -> CodeChunk:
        """Create a CodeChunk from component parts."""
        from codeweaver._data_structures import CodeChunk, Span

        # Create span
        span = Span(start=start_line, end=end_line, _source_id=source_id)

        return CodeChunk(
            content=content,
            line_range=span,
            chunk_id=(metadata.get("chunk_id") if metadata else uuid7()),
            parent_id=source_id,
            chunk_type=chunk_type,
            file_path=file.path,
            language=str(file.ext_kind.language),
            ext_kind=file.ext_kind,
            metadata=metadata,
        )
