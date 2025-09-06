# sourcery skip: lambdas-should-be-short, no-complex-if-expressions
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""
Statistics tracking for CodeWeaver, including file indexing, retrieval, and session performance metrics.
"""

from __future__ import annotations

import statistics

from collections import Counter, defaultdict
from collections.abc import Sequence
from functools import cache
from pathlib import Path
from types import MappingProxyType
from typing import Annotated, ClassVar, Literal, TypedDict, cast

from fastmcp import Context
from pydantic import (
    AnyUrl,
    ConfigDict,
    Field,
    NonNegativeFloat,
    NonNegativeInt,
    PositiveFloat,
    computed_field,
    field_serializer,
)
from pydantic.dataclasses import dataclass

from codeweaver._common import BaseEnum
from codeweaver._data_structures import ChunkKind, ExtKind
from codeweaver.language import ConfigLanguage, SemanticSearchLanguage


type ToolOrPromptName = str
type ResourceUri = AnyUrl

type McpComponentRequests = Literal[
    "on_call_tool_requests", "on_read_resource_requests", "on_get_prompt_requests"
]
type McpOperationRequests = Literal[
    "on_call_tool_requests",
    "on_read_resource_requests",
    "on_get_prompt_requests",
    "on_list_tools_requests",
    "on_list_resources_requests",
    "on_list_resource_templates_requests",
    "on_list_prompts_requests",
]


class McpTimingDict(TypedDict):
    combined: NonNegativeFloat
    by_component: dict[ToolOrPromptName | ResourceUri, NonNegativeFloat]


class McpComponentTimingDict(TypedDict):
    on_call_tool_requests: McpTimingDict
    on_read_resource_requests: McpTimingDict
    on_get_prompt_requests: McpTimingDict


class CallHookTimingDict(TypedDict):
    """Typed dictionary for MCP timing statistics."""

    on_call_tool_requests: McpTimingDict
    on_read_resource_requests: McpTimingDict
    on_get_prompt_requests: McpTimingDict
    on_list_tools_requests: NonNegativeFloat
    on_list_resources_requests: NonNegativeFloat
    on_list_resource_templates_requests: NonNegativeFloat
    on_list_prompts_requests: NonNegativeFloat


class TimingStatisticsDict(TypedDict):
    """Typed dictionary for MCP timing statistics."""

    averages: CallHookTimingDict
    counts: CallHookTimingDict
    lows: CallHookTimingDict
    medians: CallHookTimingDict
    highs: CallHookTimingDict


type RequestKind = Literal[
    "on_call_tool",
    "on_read_resource",
    "on_get_prompt",
    "on_list_tools",
    "on_list_resources",
    "on_list_resource_templates",
    "on_list_prompts",
]

type OperationsKey = Literal["indexed", "retrieved", "processed", "reindexed", "skipped"]
type SummaryKey = Literal["total_operations", "unique_files"]
type CategoryKey = Literal["code", "config", "docs", "other"]


@dataclass(config=ConfigDict(extra="forbid"))
class TimingStatistics:
    """By-operation timing statistics for CodeWeaver operations."""

    on_call_tool_requests: Annotated[
        dict[ToolOrPromptName, list[PositiveFloat]],
        Field(
            default_factory=dict,
            description="""Time taken for on_call_tool requests in milliseconds.""",
        ),
    ]
    on_read_resource_requests: Annotated[
        dict[ResourceUri, list[PositiveFloat]],
        Field(
            default_factory=dict,
            description="""Time taken for on_read_resource requests in milliseconds.""",
        ),
    ]
    on_get_prompt_requests: Annotated[
        dict[ToolOrPromptName, list[PositiveFloat]],
        Field(
            default_factory=dict,
            description="""Time taken for on_get_prompt requests in milliseconds.""",
        ),
    ]
    on_list_tools_requests: Annotated[
        list[PositiveFloat],
        Field(
            default_factory=list,
            description="""Time taken for on_list_tools requests in milliseconds.""",
        ),
    ]
    on_list_resources_requests: Annotated[
        list[PositiveFloat],
        Field(
            default_factory=list,
            description="""Time taken for on_list_resources requests in milliseconds.""",
        ),
    ]
    on_list_resource_templates_requests: Annotated[
        list[PositiveFloat],
        Field(
            default_factory=list,
            description="""Time taken for on_list_resource_templates requests in milliseconds.""",
        ),
    ]
    on_list_prompts_requests: Annotated[
        list[PositiveFloat],
        Field(
            default_factory=list,
            description="""Time taken for on_list_prompts requests in milliseconds.""",
        ),
    ]

    def update(
        self,
        key: McpOperationRequests,
        response_time: PositiveFloat,
        tool_or_resource_name: ToolOrPromptName | ResourceUri | None = None,
    ) -> None:
        """Update the timing statistics for a specific request type."""
        if key in ("on_call_tool_requests", "on_read_resource_requests", "on_get_prompt_requests"):
            if tool_or_resource_name is None:
                raise ValueError(
                    f"{key} requires a tool or resource name to update timing statistics."
                )
            # Ensure the dictionary exists for the specific tool/resource
            request_dict = getattr(self, key, {})
            if tool_or_resource_name not in request_dict:
                request_dict[tool_or_resource_name] = []
            request_dict[tool_or_resource_name].append(response_time)
        if (request_list := getattr(self, key)) and isinstance(request_list, list):
            self.__setattr__(key, [*request_list, response_time])

    def _compute_for_mcp_timing_dict(
        self, key: McpComponentRequests
    ) -> dict[Literal["averages", "counts", "highs", "medians", "lows"], McpTimingDict]:
        """Compute the timing statistics for a specific MCP operation."""
        component_data = getattr(self, key)
        combined_times = [time for times in component_data.values() for time in times if times]

        return {
            "averages": {
                "combined": statistics.mean(combined_times) if combined_times else 0.0,
                "by_component": {
                    k: statistics.mean(v) if v else 0.0 for k, v in component_data.items()
                },
            },
            "counts": {
                "combined": len(combined_times),
                "by_component": {k: len(v) for k, v in component_data.items()},
            },
            "highs": {
                "combined": max(combined_times, default=0.0),
                "by_component": {k: max(v, default=0.0) for k, v in component_data.items()},
            },
            "medians": {
                "combined": statistics.median(combined_times) if combined_times else 0.0,
                "by_component": {
                    k: statistics.median(v) if v else 0.0 for k, v in component_data.items()
                },
            },
            "lows": {
                "combined": min(combined_times, default=0.0),
                "by_component": {k: min(v, default=0.0) for k, v in component_data.items()},
            },
        }

    @computed_field
    @property
    def timing_summary(self) -> TimingStatisticsDict:
        """Get a summary of timing statistics."""
        # Compute all statistics for component-based requests once
        tool_stats = self._compute_for_mcp_timing_dict("on_call_tool_requests")
        resource_stats = self._compute_for_mcp_timing_dict("on_read_resource_requests")
        prompt_stats = self._compute_for_mcp_timing_dict("on_get_prompt_requests")

        # Helper for simple list-based statistics
        def safe_mean(data: list[PositiveFloat]) -> NonNegativeFloat:
            return statistics.mean(data) if data else 0.0

        def safe_median(data: list[PositiveFloat]) -> NonNegativeFloat:
            return statistics.median(data) if data else 0.0

        def safe_max(data: list[PositiveFloat]) -> NonNegativeFloat:
            return max(data) if data else 0.0

        def safe_min(data: list[PositiveFloat]) -> NonNegativeFloat:
            return min(data) if data else 0.0

        return {
            "averages": {
                "on_call_tool_requests": tool_stats["averages"],
                "on_read_resource_requests": resource_stats["averages"],
                "on_get_prompt_requests": prompt_stats["averages"],
                "on_list_tools_requests": safe_mean(self.on_list_tools_requests),
                "on_list_resources_requests": safe_mean(self.on_list_resources_requests),
                "on_list_resource_templates_requests": safe_mean(
                    self.on_list_resource_templates_requests
                ),
                "on_list_prompts_requests": safe_mean(self.on_list_prompts_requests),
            },
            "counts": {
                "on_call_tool_requests": tool_stats["counts"],
                "on_read_resource_requests": resource_stats["counts"],
                "on_get_prompt_requests": prompt_stats["counts"],
                "on_list_tools_requests": len(self.on_list_tools_requests),
                "on_list_resources_requests": len(self.on_list_resources_requests),
                "on_list_resource_templates_requests": len(
                    self.on_list_resource_templates_requests
                ),
                "on_list_prompts_requests": len(self.on_list_prompts_requests),
            },
            "lows": {
                "on_call_tool_requests": tool_stats["lows"],
                "on_read_resource_requests": resource_stats["lows"],
                "on_get_prompt_requests": prompt_stats["lows"],
                "on_list_tools_requests": safe_min(self.on_list_tools_requests),
                "on_list_resources_requests": safe_min(self.on_list_resources_requests),
                "on_list_resource_templates_requests": safe_min(
                    self.on_list_resource_templates_requests
                ),
                "on_list_prompts_requests": safe_min(self.on_list_prompts_requests),
            },
            "medians": {
                "on_call_tool_requests": tool_stats["medians"],
                "on_read_resource_requests": resource_stats["medians"],
                "on_get_prompt_requests": prompt_stats["medians"],
                "on_list_tools_requests": safe_median(self.on_list_tools_requests),
                "on_list_resources_requests": safe_median(self.on_list_resources_requests),
                "on_list_resource_templates_requests": safe_median(
                    self.on_list_resource_templates_requests
                ),
                "on_list_prompts_requests": safe_median(self.on_list_prompts_requests),
            },
            "highs": {
                "on_call_tool_requests": tool_stats["highs"],
                "on_read_resource_requests": resource_stats["highs"],
                "on_get_prompt_requests": prompt_stats["highs"],
                "on_list_tools_requests": safe_max(self.on_list_tools_requests),
                "on_list_resources_requests": safe_max(self.on_list_resources_requests),
                "on_list_resource_templates_requests": safe_max(
                    self.on_list_resource_templates_requests
                ),
                "on_list_prompts_requests": safe_max(self.on_list_prompts_requests),
            },
        }


@dataclass(
    config=ConfigDict(extra="forbid", json_schema_extra={"noTelemetryProps": ["unique_files"]})
)
class _LanguageStatistics:
    """Statistics for a specific language within a category."""

    language: Annotated[
        str | SemanticSearchLanguage | ConfigLanguage,
        Field(
            description="""`SemanticSearchLanguage` member, `ConfigLanguage` member, or string representing the language."""
        ),
    ]
    indexed: Annotated[
        NonNegativeInt, Field(description="""Number of files indexed for this language.""")
    ] = 0
    retrieved: Annotated[
        NonNegativeInt, Field(description="""Number of files retrieved for this language.""")
    ] = 0
    processed: Annotated[
        NonNegativeInt, Field(description="""Number of files processed for this language.""")
    ] = 0
    reindexed: Annotated[
        NonNegativeInt, Field(description="""Number of files reindexed for this language.""")
    ] = 0
    skipped: Annotated[
        NonNegativeInt, Field(description="""Number of files skipped for this language.""")
    ] = 0
    unique_files: ClassVar[
        Annotated[set[Path], Field(default_factory=set, init=False, repr=False, exclude=True)]
    ] = set()

    @computed_field
    @property
    def unique_count(self) -> NonNegativeInt:
        """Get the number of unique files for this language (excluding skipped)."""
        return len(self.unique_files) if self.unique_files else 0

    @computed_field
    @property
    def total_operations(self) -> NonNegativeInt:
        """Get the total number of operations for this language."""
        return self.indexed + self.retrieved + self.processed + self.reindexed + self.skipped

    def add_operation(self, operation: OperationsKey, path: Path | None = None) -> None:
        """Add an operation count and optionally track the file."""
        if operation == "indexed":
            self.indexed += 1
        elif operation == "retrieved":
            self.retrieved += 1
        elif operation == "processed":
            self.processed += 1
        elif operation == "reindexed":
            self.reindexed += 1
        elif operation == "skipped":
            self.skipped += 1

        # Track unique files (except for skipped operations)
        if path and path.is_file() and operation != "skipped":
            self.unique_files.add(path)


LanguageSummary = dict[OperationsKey | SummaryKey, NonNegativeInt]


@cache
def normalize_language(language: str) -> str | SemanticSearchLanguage | ConfigLanguage:
    """Normalize a language string to a SemanticSearchLanguage or ConfigLanguage."""
    if language in SemanticSearchLanguage.values():
        return SemanticSearchLanguage.from_string(language)
    if language in ConfigLanguage.values():
        return ConfigLanguage.from_string(language)
    return language


@dataclass(
    config=ConfigDict(extra="forbid", json_schema_extra={"noTelemetryProps": ["unique_files"]})
)
class _CategoryStatistics:
    """Statistics for a file category (code, config, docs, other)."""

    category: Annotated[
        ChunkKind,
        Field(
            description="""The category of the files, e.g. 'code', 'config', 'docs', 'other'. A [`_data_structures.ChunkKind`] member."""
        ),
    ]
    languages: Annotated[
        dict[str | SemanticSearchLanguage | ConfigLanguage, _LanguageStatistics],
        Field(
            default_factory=dict,
            description="""Language statistics in this category. Keys are language names, SemanticSearchLanguage members, or ConfigLanguage members; values are _LanguageStatistics objects.""",
        ),
    ]

    def get_language_stats(
        self, language: str | SemanticSearchLanguage | ConfigLanguage
    ) -> _LanguageStatistics:
        """Get or create language statistics for this category."""
        if isinstance(language, str) and not isinstance(
            language, (SemanticSearchLanguage | ConfigLanguage)
        ):
            language = normalize_language(language)
        if language not in self.languages:
            self.languages[language] = _LanguageStatistics(language=language)
        return self.languages[language]

    @computed_field
    @property
    def unique_count(self) -> NonNegativeInt:
        """Get the total unique file count across all languages in this category."""
        all_files: set[Path] = set()
        for lang_stats in self.languages.values():
            all_files.update(lang_stats.unique_files)
        return len(all_files)

    @computed_field(return_type=dict[SemanticSearchLanguage, _LanguageStatistics])
    @property
    def semantic_languages(self) -> MappingProxyType[SemanticSearchLanguage, _LanguageStatistics]:
        """Get all semantic search languages in this category."""
        # This is verbose to keep the type checker happy
        filtered_languages: set[SemanticSearchLanguage | ConfigLanguage | None] = {
            lang.as_semantic_search_language
            if isinstance(lang, ConfigLanguage)
            else (lang if isinstance(lang, SemanticSearchLanguage) else None)
            for lang in self.languages
            if lang
        }
        filtered_languages.discard(None)
        mapped_languages: dict[SemanticSearchLanguage, _LanguageStatistics] = {}
        for lang in filtered_languages:
            if isinstance(lang, SemanticSearchLanguage):
                mapped_languages[lang] = self.languages[lang]
            elif isinstance(lang, ConfigLanguage):
                mapped_languages[cast(SemanticSearchLanguage, lang.as_semantic_search_language)] = (
                    self.languages[lang]
                )
        return MappingProxyType(mapped_languages)

    @property
    def _semantic_language_values(self) -> frozenset[str]:
        """Get the string values of all semantic search languages in this category."""
        return frozenset(lang.value for lang in self.semantic_languages)

    @property
    def operations_with_semantic_support(self) -> NonNegativeInt:
        """Get the total operations with semantic support across all languages in this category."""
        return sum(lang_stats.total_operations for lang_stats in self.semantic_languages.values())

    @property
    def unique_files(self) -> frozenset[Path]:
        """Get the unique files across all languages in this category."""
        all_files: set[Path] = set()
        for lang_stats in self.languages.values():
            all_files.update(lang_stats.unique_files)
        return frozenset(all_files)

    @property
    def total_operations(self) -> NonNegativeInt:
        """Get the total operations across all languages in this category."""
        return sum(lang_stats.total_operations for lang_stats in self.languages.values())

    def add_operation(
        self,
        language: str | SemanticSearchLanguage | ConfigLanguage,
        operation: OperationsKey,
        path: Path | None = None,
    ) -> None:
        """Add an operation for a specific language in this category."""
        lang_stats = self.get_language_stats(language)
        lang_stats.add_operation(operation, path)

    @classmethod
    def from_ext_kind(cls, ext_kind: ExtKind) -> _CategoryStatistics:
        """Create a _CategoryStatistics from an ExtKind."""
        return cls(
            category=ext_kind.kind,
            languages={ext_kind.language: _LanguageStatistics(language=ext_kind.language)},
        )


@dataclass(
    config=ConfigDict(extra="forbid", json_schema_extra={"noTelemetryProps": ["_other_files"]})
)
class FileStatistics:
    """Comprehensive file statistics tracking categories, languages, and operations."""

    categories: dict[ChunkKind, _CategoryStatistics] = Field(
        default_factory=lambda: {
            ChunkKind.CODE: _CategoryStatistics(category=ChunkKind.CODE, languages={}),
            ChunkKind.CONFIG: _CategoryStatistics(category=ChunkKind.CONFIG, languages={}),
            ChunkKind.DOCS: _CategoryStatistics(category=ChunkKind.DOCS, languages={}),
            ChunkKind.OTHER: _CategoryStatistics(category=ChunkKind.OTHER, languages={}),
        }
    )

    _other_files: ClassVar[
        Annotated[set[Path], Field(default_factory=set, init=False, repr=False, exclude=True)]
    ] = set()

    def add_file(
        self, path: Path, operation: OperationsKey, ext_kind: ExtKind | None = None
    ) -> None:
        """Add a file operation, automatically categorizing by extension."""
        if not path.is_file():
            raise ValueError(f"{path} is not a valid file")
        # Use ExtKind to determine file category and language
        if ext_kind := ext_kind or ExtKind.from_file(path):
            category = ext_kind.kind
            language = ext_kind.language
            self.categories[category].add_operation(language, operation, path)
        elif self._other_files and path in self._other_files:
            # Handle explicitly added "other" files
            language_name = f".{path.stem}" if "." in path.name else path.name
            self.categories[ChunkKind.OTHER].add_operation(language_name, operation, path)

    def add_other_files(self, *files: Path) -> None:
        """Add files to the 'other' category."""
        # TODO: We'd ideally want to make sure these are pushed to the indexer, unless we receive these in the same action
        self._other_files.update(files)

    @property
    def total_unique_files(self) -> NonNegativeInt:
        """Get the total unique files across all categories."""
        all_files: set[Path] = set()
        for category_stats in self.categories.values():
            for lang_stats in category_stats.languages.values():
                all_files.update(lang_stats.unique_files)
        return len(all_files)

    @property
    def total_operations(self) -> NonNegativeInt:
        """Get the total operations across all categories."""
        return sum(cat_stats.total_operations for cat_stats in self.categories.values())

    def get_summary_by_category(self) -> dict[ChunkKind, dict[str, NonNegativeInt]]:
        """Get a summary of unique files and operations by category."""
        return {
            category: {
                "unique_files": cat_stats.unique_count,
                "total_operations": cat_stats.total_operations,
                "languages": len(cat_stats.languages),
            }
            for category, cat_stats in self.categories.items()
        }

    def get_summary_by_language(
        self,
    ) -> MappingProxyType[str | SemanticSearchLanguage | ConfigLanguage, LanguageSummary]:
        """Get a summary of statistics by language across all categories."""
        language_summary: dict[str | SemanticSearchLanguage | ConfigLanguage, LanguageSummary] = (
            defaultdict(
                lambda: {
                    "unique_files": 0,
                    "total_operations": 0,
                    "indexed": 0,
                    "retrieved": 0,
                    "processed": 0,
                    "reindexed": 0,
                    "skipped": 0,
                }
            )
        )

        all_files_by_language: dict[str | SemanticSearchLanguage | ConfigLanguage, set[Path]] = (
            defaultdict(set)
        )

        for cat_stats in self.categories.values():
            for lang, lang_stats in cat_stats.languages.items():
                all_files_by_language[lang].update(lang_stats.unique_files)
                language_summary[lang]["unique_files"] += lang_stats.unique_count
                language_summary[lang] = self._summarize_stats_for_language(lang_stats)

        return MappingProxyType(language_summary)

    def _summarize_stats_for_language(self, lang_stats: _LanguageStatistics) -> LanguageSummary:
        """Summarize language statistics into the overall language summary."""
        return {
            "total_operations": lang_stats.total_operations,
            "indexed": lang_stats.indexed,
            "retrieved": lang_stats.retrieved,
            "processed": lang_stats.processed,
            "reindexed": lang_stats.reindexed,
            "skipped": lang_stats.skipped,
        }


class TokenCategory(BaseEnum):
    """Categories of token usage for vector store operations."""

    EMBEDDING = "embedding"
    """Tokens generated for storing/using in embedding operations. Includes query tokens."""
    RERANKING = "reranking"
    """Embeddings generated for reranking search results."""

    CONTEXT_AGENT = "context_agent"
    """Tokens expended by CodeWeaver's internal agent to process the user's request. It's the number of tokens used during the execution of the `find_code` tool."""
    SEARCH_RESULTS = "search_results"
    """Represents the *agent* token equivalent of total search results (from all strategies/sources). Many of these are never actually turned *into* tokens. The difference between these tokens and the `user_agent` tokens is the number of tokens that CodeWeaver saved from the users agent's context (and API costs)."""
    USER_AGENT = "user_agent"
    """Tokens that CodeWeaver *returned* to the user's agent after intelligently sifting through results. It's the number of tokens for the results returned by the `find_code` tool."""

    SAVED_BY_RERANKING = "saved_by_reranking"
    """Tokens that were saved by reranking the results."""

    @property
    def is_agent_token(self) -> bool:
        """Check if the token category is related to agent usage."""
        return self in (TokenCategory.CONTEXT_AGENT, TokenCategory.USER_AGENT)

    @property
    def is_data_token(self) -> bool:
        """Check if the token category is related to data usage."""
        return self == TokenCategory.SEARCH_RESULTS

    @property
    def is_embedding_type_token(self) -> bool:
        """Represents tokens generated for embedding operations."""
        return self in (TokenCategory.EMBEDDING, TokenCategory.RERANKING)


class TokenCounter(Counter[TokenCategory]):
    """A counter for tracking token usage by operation."""

    def __init__(self) -> None:
        super().__init__()
        self.update({
            TokenCategory.EMBEDDING: 0,
            TokenCategory.RERANKING: 0,
            TokenCategory.CONTEXT_AGENT: 0,
            TokenCategory.USER_AGENT: 0,
            TokenCategory.SEARCH_RESULTS: 0,
        })

    @computed_field
    @property
    def total_generated(self) -> NonNegativeInt:
        """Get the total number of tokens generated across all operations."""
        return sum((self[TokenCategory.EMBEDDING], self[TokenCategory.RERANKING]))

    @computed_field
    @property
    def total_used(self) -> NonNegativeInt:
        """Get the total number of tokens used across all operations."""
        return sum((self[TokenCategory.CONTEXT_AGENT], self[TokenCategory.USER_AGENT]))

    @computed_field
    @property
    def context_saved(self) -> NonNegativeInt:
        """
        Get the total number of tokens that CodeWeaver saved from the user_agent.

        !!! note
            The number returned by `context_saved` is a low estimate of the actual number of tokens saved.

            CodeWeaver doesn't have access to the full context of the user's agent's request. To get the full picture we would need:

            - The total tokens used by the user's agent after CodeWeaver's response
            - The number of 'turns' it took for the user agent to complete the task *after* CodeWeaver's response

            Even if we had those numbers, they would still be lower bounds, because they don't account for increases in overall turns and token expenditure if CodeWeaver was never used. Let's call this the "blind bumbling savings" of CodeWeaver.
        """
        return (self[TokenCategory.SEARCH_RESULTS] - self[TokenCategory.USER_AGENT]) + self[
            TokenCategory.SAVED_BY_RERANKING
        ]

    @property
    def money_saved(self) -> NonNegativeFloat:
        """
        Estimate the money saved by using CodeWeaver based on token savings.

        TODO: To implement this correctly, we need to pull the model name from the fastmcp.Context object and use the pricing for that model. We could use [`genai_prices`](https://github.com/pydantic/genai-prices) to get the pricing information, either remotely or as a dependency.
        """
        raise NotImplementedError("Money saved estimation is not implemented yet.")


@dataclass(
    kw_only=True,
    config=ConfigDict(extra="forbid", str_strip_whitespace=True, arbitrary_types_allowed=True),
)
class SessionStatistics:
    """Statistics for tracking session performance and usage."""

    total_requests: Annotated[
        NonNegativeInt | None, Field(description="""Total requests made during the session.""")
    ] = None
    successful_requests: Annotated[
        NonNegativeInt | None,
        Field(description="""Total successful requests during the session."""),
    ] = None
    failed_requests: Annotated[
        NonNegativeInt | None, Field(description="""Total failed requests during the session.""")
    ] = None
    timing_statistics: Annotated[
        TimingStatistics | None, Field(description="""Timing statistics for the session.""")
    ] = None

    index_statistics: Annotated[
        FileStatistics | None,
        Field(
            default_factory=FileStatistics,
            description="""Comprehensive file statistics tracking categories, languages, and operations.""",
        ),
    ]
    token_statistics: Annotated[
        TokenCounter | None,
        Field(
            default_factory=TokenCounter,
            description="""A typed Counter that tracks token usage statistics.""",
        ),
    ]

    _successful_request_log: list[str | int] = Field(default_factory=list, init=False, repr=False)  # pyright: ignore[reportUnknownVariableType]
    _failed_request_log: list[str | int] = Field(default_factory=list, init=False, repr=False)  # pyright: ignore[reportUnknownVariableType]

    def __post_init__(self) -> None:
        """Post-initialization processing."""
        if not self.index_statistics:
            self.index_statistics = FileStatistics()
        if not self.token_statistics:
            self.token_statistics = TokenCounter()
        self.timing_statistics = TimingStatistics(
            on_call_tool_requests={},
            on_read_resource_requests={},
            on_get_prompt_requests={},
            on_list_tools_requests=[],
            on_list_resources_requests=[],
            on_list_resource_templates_requests=[],
            on_list_prompts_requests=[],
        )
        self._successful_request_log = self._successful_request_log or []
        self._failed_request_log = self._failed_request_log or []
        self.successful_requests = self.successful_requests or 0
        self.failed_requests = self.failed_requests or 0
        self.total_requests = self.total_requests or 0

    @field_serializer("token_statistics")
    def serialize_token_statistics(
        self, value: TokenCounter
    ) -> dict[TokenCategory, NonNegativeInt]:
        """Serialize the token statistics to a dictionary."""
        return dict(value)

    def get_timing_statistics(self) -> TimingStatisticsDict:
        """Get the current timing statistics."""
        if self.timing_statistics:
            return self.timing_statistics.timing_summary
        self.timing_statistics = TimingStatistics(
            on_call_tool_requests={},
            on_read_resource_requests={},
            on_get_prompt_requests={},
            on_list_tools_requests=[],
            on_list_resources_requests=[],
            on_list_resource_templates_requests=[],
            on_list_prompts_requests=[],
        )
        return self.timing_statistics.timing_summary

    def add_successful_request(self, request_id: str | int | None = None) -> None:
        """Add a successful request count."""
        self._add_request(successful=True, request_id=request_id)

    def add_failed_request(self, request_id: str | int | None = None) -> None:
        """Add a failed request count."""
        self._add_request(successful=False, request_id=request_id)

    def _add_request(self, *, successful: bool, request_id: str | int | None = None) -> None:
        """Internal method to add a request count."""
        if self.total_requests is None:
            self.total_requests = 0
        if self.successful_requests is None:
            self.successful_requests = 0
        if self.failed_requests is None:
            self.failed_requests = 0
        if request_id and successful:
            self._successful_request_log.append(request_id)
        elif request_id:
            self._failed_request_log.append(request_id)

        self.total_requests += 1
        if successful:
            self.successful_requests += 1
        else:
            self.failed_requests += 1

    def request_in_log(self, request_id: str | int) -> bool:
        """Check if a request ID is in the successful or failed request logs."""
        return request_id in self._successful_request_log or request_id in self._failed_request_log

    @computed_field
    @property
    def success_rate(self) -> NonNegativeFloat | None:
        """Calculate the success rate of requests."""
        if self.total_requests and self.total_requests > 0:
            return (self.successful_requests or 0) / self.total_requests
        return None

    @computed_field
    @property
    def failure_rate(self) -> NonNegativeFloat | None:
        """Calculate the failure rate of requests."""
        if self.total_requests and self.total_requests > 0:
            return (self.failed_requests or 0) / self.total_requests
        return None

    def add_token_usage(
        self,
        *,
        embedding_generated: NonNegativeInt = 0,
        reranking_generated: NonNegativeInt = 0,
        context_agent_used: NonNegativeInt = 0,
        user_agent_received: NonNegativeInt = 0,
        search_results: NonNegativeInt = 0,
        saved_by_reranking: NonNegativeInt = 0,
    ) -> None:
        """Add token usage statistics."""
        if self.token_statistics is None:
            self.token_statistics = TokenCounter()

        self.token_statistics[TokenCategory.EMBEDDING] += embedding_generated
        self.token_statistics[TokenCategory.RERANKING] += reranking_generated
        self.token_statistics[TokenCategory.CONTEXT_AGENT] += context_agent_used
        self.token_statistics[TokenCategory.USER_AGENT] += user_agent_received
        self.token_statistics[TokenCategory.SEARCH_RESULTS] += search_results
        self.token_statistics[TokenCategory.SAVED_BY_RERANKING] += saved_by_reranking

    def get_token_usage(self) -> TokenCounter:
        """Get the current token usage statistics."""
        return self.token_statistics or TokenCounter()

    def add_file_operation(self, path: Path, operation: OperationsKey) -> None:
        """Add a file operation to the index statistics."""
        if not self.index_statistics:
            self.index_statistics = FileStatistics()
        self.index_statistics.add_file(path, operation)

    def add_file_operations_by_extkind(
        self, operations: Sequence[tuple[Path, ExtKind, OperationsKey]]
    ) -> None:
        """Add file operations to the index statistics by extension kind."""
        if not self.index_statistics:
            self.index_statistics = FileStatistics()
        for path, ext_kind, operation in operations:
            self.index_statistics.add_file(path, operation, ext_kind=ext_kind)

    def add_file_operations(self, *file_operations: tuple[Path, OperationsKey]) -> None:
        """Add multiple file operations to the index statistics."""
        for file, operation in file_operations:
            self.add_file_operation(file, operation)

    def add_other_files(self, *files: Path) -> None:
        """Add files to the 'other' category in index statistics."""
        if not self.index_statistics:
            self.index_statistics = FileStatistics()
        self.index_statistics.add_other_files(*files)

    def reset(self) -> None:
        """Reset all statistics to their initial state."""
        self.total_requests = None
        self.successful_requests = None
        self.failed_requests = None
        self.timing_statistics = TimingStatistics(
            on_call_tool_requests={},
            on_read_resource_requests={},
            on_get_prompt_requests={},
            on_list_tools_requests=[],
            on_list_resources_requests=[],
            on_list_resource_templates_requests=[],
            on_list_prompts_requests=[],
        )
        self.index_statistics = FileStatistics()
        self.token_statistics = TokenCounter()

    def log_request_from_context(
        self, context: Context | None = None, *, successful: bool = True
    ) -> None:
        """Log a request from the given context.

        Note: This is fastmcp.Context, *not* fastmcp.middleware.MiddlewareContext
        """
        from typing import TYPE_CHECKING, Any

        if TYPE_CHECKING:
            from mcp.shared.context import RequestContext

            from codeweaver._server import AppState

        if context is None:
            return
        ctx: RequestContext[Any, AppState, Any] | None = None
        try:
            if (
                context
                and hasattr(context, "request_context")
                and (request_ctx := getattr(context, "request_context", None))
                and request_ctx is not None
            ):
                ctx = request_ctx
            else:
                ctx = None
        except (LookupError, ValueError):
            return

        if (
            ctx
            and (request_id := ctx.request_id)
            and not self.request_in_log(request_id=request_id)
        ):
            if successful:
                self.add_successful_request(request_id=request_id)
            else:
                self.add_failed_request(request_id=request_id)


_statistics: SessionStatistics = SessionStatistics(
    index_statistics=FileStatistics(), token_statistics=TokenCounter()
)


def get_session_statistics() -> SessionStatistics:
    """Get the current session statistics."""
    return _statistics
