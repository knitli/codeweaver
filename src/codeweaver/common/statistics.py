# sourcery skip: lambdas-should-be-short, no-complex-if-expressions
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""
Statistics tracking for CodeWeaver, including file indexing, retrieval, and session performance metrics.
"""

from __future__ import annotations

import contextlib
import statistics
import time

from collections import Counter, defaultdict
from collections.abc import Awaitable, Callable, Sequence
from datetime import UTC, datetime
from functools import cache
from pathlib import Path
from types import MappingProxyType
from typing import TYPE_CHECKING, Annotated, Any, ClassVar, Literal, NamedTuple, cast

from fastmcp import Context
from pydantic import (
    ConfigDict,
    Field,
    FieldSerializationInfo,
    NonNegativeFloat,
    NonNegativeInt,
    PositiveFloat,
    SerializerFunctionWrapHandler,
    ValidatorFunctionWrapHandler,
    computed_field,
    field_serializer,
    field_validator,
)
from pydantic.dataclasses import dataclass
from starlette.responses import PlainTextResponse

from codeweaver.common.types import (
    McpComponentRequests,
    McpOperationRequests,
    McpTimingDict,
    OperationsKey,
    ResourceUri,
    SummaryKey,
    TimingStatisticsDict,
    ToolOrPromptName,
)
from codeweaver.common.utils import uuid7
from codeweaver.core.language import ConfigLanguage, SemanticSearchLanguage
from codeweaver.core.metadata import ChunkKind, ExtKind
from codeweaver.core.types.enum import AnonymityConversion, BaseEnum
from codeweaver.core.types.models import DATACLASS_CONFIG, DataclassSerializationMixin


if TYPE_CHECKING:
    from codeweaver.core.types import AnonymityConversion, FilteredKeyT


@dataclass(config=DATACLASS_CONFIG | ConfigDict(extra="forbid", defer_build=True))
class TimingStatistics(DataclassSerializationMixin):
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
    health_http: Annotated[
        list[PositiveFloat],
        Field(
            default_factory=list,
            description="""Time taken for health status http requests in milliseconds.""",
        ),
    ]
    version_http: Annotated[
        list[PositiveFloat],
        Field(
            default_factory=list,
            description="""Time taken for version check http requests in milliseconds.""",
        ),
    ]
    state_http: Annotated[
        list[PositiveFloat],
        Field(
            default_factory=list,
            description="""Time taken for state http requests in milliseconds.""",
        ),
    ]
    statistics_http: Annotated[
        list[PositiveFloat],
        Field(
            default_factory=list,
            description="""Time taken for statistics http requests in milliseconds.""",
        ),
    ]
    settings_http: Annotated[
        list[PositiveFloat],
        Field(
            default_factory=list,
            description="""Time taken for settings http requests in milliseconds.""",
        ),
    ]

    def _telemetry_keys(self) -> None:
        return None

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

    def update_http_requests(
        self,
        response_time: PositiveFloat,
        component: Literal["health", "version", "statistics", "state", "settings"],
    ) -> None:
        """Update the timing statistics for a specific HTTP request type."""
        key = f"{component}_http"
        requests_list = getattr(self, key)
        if requests_list is not None and isinstance(requests_list, list):
            self.__setattr__(key, [*requests_list, response_time])
        else:
            self.__setattr__(key, [response_time])

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
                "http_requests": {
                    "health": safe_mean(self.health_http),
                    "version": safe_mean(self.version_http),
                    "state": safe_mean(self.state_http),
                    "statistics": safe_mean(self.statistics_http),
                    "settings": safe_mean(self.settings_http),
                },
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
                "http_requests": {
                    "health": len(self.health_http),
                    "version": len(self.version_http),
                    "statistics": len(self.statistics_http),
                    "state": len(self.state_http),
                    "settings": len(self.settings_http),
                },
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
                "http_requests": {
                    "health": safe_min(self.health_http),
                    "version": safe_min(self.version_http),
                    "statistics": safe_min(self.statistics_http),
                    "state": safe_min(self.state_http),
                    "settings": safe_min(self.settings_http),
                },
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
                "http_requests": {
                    "health": safe_median(self.health_http),
                    "version": safe_median(self.version_http),
                    "state": safe_median(self.state_http),
                    "statistics": safe_median(self.statistics_http),
                    "settings": safe_median(self.settings_http),
                },
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
                "http_requests": {
                    "health": safe_max(self.health_http),
                    "version": safe_max(self.version_http),
                    "state": safe_max(self.state_http),
                    "statistics": safe_max(self.statistics_http),
                    "settings": safe_max(self.settings_http),
                },
            },
        }


@dataclass(config=DATACLASS_CONFIG | ConfigDict(extra="forbid", defer_build=True))
class _LanguageStatistics(DataclassSerializationMixin):
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
    unique_files: ClassVar[Annotated[set[Path], Field(init=False, repr=False, exclude=True)]] = (
        set()
    )

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        from codeweaver.core.types import AnonymityConversion, FilteredKey

        return {FilteredKey("unique_files"): AnonymityConversion.FORBIDDEN}

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


@dataclass(config=DATACLASS_CONFIG | ConfigDict(extra="forbid", defer_build=True))
class _CategoryStatistics(DataclassSerializationMixin):
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

    def _telemetry_keys(self) -> None:
        return None

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

    @field_serializer(
        "semantic_languages",
        mode="wrap",
        when_used="json",
        return_type=dict[SemanticSearchLanguage, _LanguageStatistics],
    )
    def _serialize_semantic_languages(
        self,
        value: MappingProxyType[SemanticSearchLanguage, _LanguageStatistics],
        nxt: SerializerFunctionWrapHandler,
        _info: FieldSerializationInfo,
    ) -> str:
        """Serialize semantic languages for JSON output."""
        return nxt(dict(value))  # type: ignore

    @field_validator("semantic_languages", mode="wrap")
    @classmethod
    def _validate_semantic_languages(
        cls, value: Any, nxt: ValidatorFunctionWrapHandler
    ) -> MappingProxyType[SemanticSearchLanguage, _LanguageStatistics]:
        """Validate semantic languages for JSON input."""
        if isinstance(value, MappingProxyType) and all(
            isinstance(k, SemanticSearchLanguage) and isinstance(v, _LanguageStatistics)
            for k, v in value.items()  # type: ignore
            if k and v  # type: ignore
        ):
            return value  # type: ignore
        if isinstance(value, MappingProxyType | dict):
            return MappingProxyType({nxt(k): nxt(v) for k, v in value.items()})  # type: ignore
        if isinstance(value, str | bytes | bytearray):
            return cls._validate_semantic_languages(nxt(value), nxt)
        raise ValueError("Invalid type for semantic_languages")

    @property
    def _semantic_language_values(self) -> frozenset[str]:
        """Get the string values of all semantic search languages in this category."""
        return frozenset(lang.variable for lang in self.semantic_languages)

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


@dataclass(config=DATACLASS_CONFIG | ConfigDict(extra="forbid", defer_build=True))
class FileStatistics(DataclassSerializationMixin):
    """Comprehensive file statistics tracking categories, languages, and operations."""

    categories: dict[ChunkKind, _CategoryStatistics] = Field(
        default_factory=lambda: {
            ChunkKind.CODE: _CategoryStatistics(category=ChunkKind.CODE, languages={}),
            ChunkKind.CONFIG: _CategoryStatistics(category=ChunkKind.CONFIG, languages={}),
            ChunkKind.DOCS: _CategoryStatistics(category=ChunkKind.DOCS, languages={}),
            ChunkKind.OTHER: _CategoryStatistics(category=ChunkKind.OTHER, languages={}),
        }
    )

    _other_files: ClassVar[Annotated[set[Path], Field(init=False, repr=False, exclude=True)]] = (
        set()
    )

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        from codeweaver.core.types import AnonymityConversion, FilteredKey

        return {FilteredKey("_other_files"): AnonymityConversion.COUNT}

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
    SPARSE_EMBEDDING = "sparse_embedding"
    """Tokens generated for storing/using in sparse embedding operations."""
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

    SAVED_BY_CONTEXT_AGENT = "saved_by_context_agent"
    """Tokens that were saved by the context agent."""

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

    @property
    def is_cost_token(self) -> bool:
        """Check if the token category represents a cost for the user."""
        return self in (
            TokenCategory.CONTEXT_AGENT,
            TokenCategory.EMBEDDING,
            TokenCategory.RERANKING,
        )

    @property
    def is_value_token(self) -> bool:
        """Check if the token category represents value for the user."""
        return self in (
            TokenCategory.USER_AGENT,
            TokenCategory.SEARCH_RESULTS,
            TokenCategory.SAVED_BY_RERANKING,
        )

    @property
    def is_context_agent_token(self) -> bool:
        """Check if the token category represents a context agent token."""
        return self in (TokenCategory.CONTEXT_AGENT, TokenCategory.SAVED_BY_CONTEXT_AGENT)


class TokenCounter(Counter[TokenCategory]):
    """A counter for tracking token usage by operation."""

    def __init__(self) -> None:
        """Initialize the TokenCounter with zero counts for all token categories."""
        super().__init__()
        self.update({
            TokenCategory.EMBEDDING: 0,
            TokenCategory.RERANKING: 0,
            TokenCategory.SPARSE_EMBEDDING: 0,
            TokenCategory.CONTEXT_AGENT: 0,
            TokenCategory.USER_AGENT: 0,
            TokenCategory.SEARCH_RESULTS: 0,
        })

    @computed_field
    @property
    def total_generated(self) -> NonNegativeInt:
        """Get the total number of tokens generated across all operations."""
        return sum((
            self[TokenCategory.EMBEDDING],
            self[TokenCategory.RERANKING],
            self[TokenCategory.SPARSE_EMBEDDING],
        ))

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

    @computed_field
    @property
    def money_saved(self) -> float:
        """
        Estimate the money saved by using CodeWeaver based on token savings.

        This is a work in progress, and currently uses a simple heuristic to approximate savings.  Longter term we'd like to make it more accurate by pulling actual prices for models used, and ideally getting actual token counts from the user's agent (with their permission of course).


        For now we're using simple 'back-of-the-envelope' calculations. We assume:
        - The average cost per 1,000 tokens for embedding models is $0.00018 (Voyage AI as of October 2025)
        - The average cost per 1,000 tokens for reranking models is $0.00005 (Voyage AI as of October 2025)
        - Sparse models we consider `free` for this calculation, as compared to everything else, the costs to run them are miniscule.
        - CodeWeaver itself doesn't have control over what model is used for the context agent, but CodeWeaver does *recommend* models to the user's client. We choose light-weight, low-cost models because we don't need frontline models for the context agent to do its job well, and we want it to be fast.
            - Assuming the user's client chooses to listen to our recommendation (a big assumption), we assume the selected model is Claude-Haiku-4.5. As of October 2025, Claude-Haiku-4.5 is priced at $0.25/million tokens, or $0.00025/1,000 tokens for input, and $2/M tokens for output, or $0.002/1,000 tokens.
        - We assume the user's agent is using a frontline model. As of October 2025, by far the most used model for coding is Anthropic's Claude 4.5 Sonnet. The costs for Sonnet are complex because they vary heavily based on context length and caching (for example, if the message is over 200,000 tokens, output cost jumps from $15/M to $22.5/M tokens).
            - We assume the lower end of the pricing, which is $3/M input and $15/M output. Which is $0.003/1,000 tokens for input and $0.015/1,000 tokens for output.
            - Generally, about 80% of token use is for input, and 20% is for output, so we use that ratio to calculate an average cost per 1,000 tokens.
            - Any "savings" are calculated against this assumed cost.
          - You can probably tell from the pricing that it is *much* more expensive to use an LLM, especially a front-line model, than it is to use embedding, reranking, and sparse models paired with lower cost agents (about two orders of magnitude less if my math is right).
        """
        embedding_cost_per_1k = 0.00018
        reranking_cost_per_1k = 0.00005
        _sparse_cost_per_1k = 0.0  # we don't track sparse token use because costs are negligible compared to everything else
        context_agent_cost_per_1k = 0.00025
        user_agent_cost_per_1k = (0.8 * 0.003) + (0.2 * 0.015)

        # costs incurred by CodeWeaver
        embedding_cost: float = self[TokenCategory.EMBEDDING] / 1000 * embedding_cost_per_1k
        reranking_cost: float = self[TokenCategory.RERANKING] / 1000 * reranking_cost_per_1k
        context_agent_cost: float = (
            self[TokenCategory.CONTEXT_AGENT] / 1000 * context_agent_cost_per_1k
        )

        user_agent_received: float = self[TokenCategory.USER_AGENT] / 1000 * user_agent_cost_per_1k
        user_agent_savings: float = self.context_saved / 1000 * user_agent_cost_per_1k

        return user_agent_savings - (
            embedding_cost + reranking_cost + context_agent_cost + user_agent_received
        )


type UUID7_STR = Annotated[
    str, Field(pattern=r"^[0-9a-f]{8}-?[0-9a-f]{4}-?7[0-9a-f]{3}-?[89ab][0-9a-f]{3}-?[0-9a-f]{12}$")
]


class Identifier(NamedTuple):
    """A named tuple for request identifiers."""

    request_id: str | int | None = None
    uuid: UUID7_STR | None = str(uuid7())

    @property
    def timestamp(self) -> int:
        """Get the timestamp from the UUID7."""
        int_uuid = int(str(self.uuid).replace("-", ""), base=16)
        x = int.to_bytes(int_uuid, length=16, byteorder="big")
        return int.from_bytes(x[:6])

    @property
    def as_datetime(self) -> datetime:
        """Get the datetime from the timestamp."""
        return datetime.fromtimestamp(self.timestamp / 1_000, tz=UTC)


@dataclass(kw_only=True, config=DATACLASS_CONFIG | ConfigDict(defer_build=True))
class SessionStatistics(DataclassSerializationMixin):
    """Statistics for tracking session performance and usage."""

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
    semantic_statistics: Annotated[
        Any | None,
        Field(
            default=None,
            description="""Semantic category usage metrics. Uses UsageMetrics from semantic.classifications.""",
        ),
    ]

    _successful_request_log: Annotated[
        list[Identifier], Field(default_factory=list, init=False, repr=False)
    ]
    _failed_request_log: Annotated[
        list[Identifier], Field(default_factory=list, init=False, repr=False)
    ]
    _successful_http_request_log: Annotated[
        list[Identifier], Field(default_factory=list, init=False, repr=False)
    ]
    _failed_http_request_log: Annotated[
        list[Identifier], Field(default_factory=list, init=False, repr=False)
    ]

    def __post_init__(self) -> None:
        """Post-initialization processing."""
        if not self.index_statistics:
            self.index_statistics = FileStatistics()
        if not self.token_statistics:
            self.token_statistics = TokenCounter()
        if not self.semantic_statistics:
            # Lazy import to avoid circular dependencies
            try:
                from collections import Counter

                from codeweaver.semantic.classifications import UsageMetrics

                self.semantic_statistics = UsageMetrics(category_usage_counts=Counter())
            except ImportError:
                # If semantic module not available, leave as None
                self.semantic_statistics = None
        self.timing_statistics = TimingStatistics(
            on_call_tool_requests={},
            on_read_resource_requests={},
            on_get_prompt_requests={},
            on_list_tools_requests=[],
            on_list_resources_requests=[],
            on_list_resource_templates_requests=[],
            on_list_prompts_requests=[],
            health_http=[],
            version_http=[],
            state_http=[],
            settings_http=[],
            statistics_http=[],
        )
        for attr in (
            "_successful_http_request_log",
            "_failed_http_request_log",
            "_successful_request_log",
            "_failed_request_log",
        ):
            if (hasattr(self, attr) and getattr(self, attr)) is None or (not hasattr(self, attr)):
                setattr(self, attr, [])

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        from codeweaver.core.types import AnonymityConversion, FilteredKey

        return {
            FilteredKey("_successful_request_log"): AnonymityConversion.FORBIDDEN,
            FilteredKey("_failed_request_log"): AnonymityConversion.FORBIDDEN,
            FilteredKey("_successful_http_request_log"): AnonymityConversion.FORBIDDEN,
            FilteredKey("_failed_http_request_log"): AnonymityConversion.FORBIDDEN,
        }

    @computed_field
    @property
    def total_requests(self) -> NonNegativeInt:
        """Total requests made during the session."""
        return len(self._successful_request_log) + len(self._failed_request_log)

    @computed_field
    @property
    def total_http_requests(self) -> NonNegativeInt:
        """Total HTTP requests made during the session."""
        return len(self._successful_http_request_log) + len(self._failed_http_request_log)

    @computed_field
    @property
    def successful_requests(self) -> NonNegativeInt:
        """Total successful requests during the session."""
        return len(self._successful_request_log)

    @computed_field
    @property
    def failed_requests(self) -> NonNegativeInt:
        """Total failed requests during the session."""
        return len(self._failed_request_log)

    @computed_field
    @property
    def successful_http_requests(self) -> NonNegativeInt:
        """Total successful HTTP requests during the session."""
        return len(self._successful_http_request_log)

    @computed_field
    @property
    def failed_http_requests(self) -> NonNegativeInt:
        """Total failed HTTP requests during the session."""
        return len(self._failed_http_request_log)

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
            health_http=[],
            version_http=[],
            state_http=[],
            settings_http=[],
            statistics_http=[],
        )
        return self.timing_statistics.timing_summary

    @staticmethod
    def _set_id(request_id: str | int | None | Identifier) -> Identifier:
        """Set the request ID to a consistent Identifier type."""
        if isinstance(request_id, Identifier):
            return request_id
        return Identifier(request_id=request_id)

    def add_successful_request(
        self, request_id: str | int | None | Identifier = None, *, is_http: bool = False
    ) -> None:
        """Add a successful request count."""
        iden = self._set_id(request_id)
        self._add_request(successful=True, request_id=iden, is_http=is_http)

    def add_failed_request(
        self, request_id: str | int | None | Identifier = None, *, is_http: bool = False
    ) -> None:
        """Add a failed request count."""
        iden = self._set_id(request_id)
        self._add_request(successful=False, request_id=iden, is_http=is_http)

    def _add_request(
        self, *, successful: bool, request_id: Identifier, is_http: bool = False
    ) -> None:
        """Internal method to add a request count."""
        if is_http:
            if successful:
                self._successful_http_request_log.append(request_id)
            else:
                self._failed_http_request_log.append(request_id)
        elif request_id:
            if successful:
                self._successful_request_log.append(request_id)
            else:
                self._failed_request_log.append(request_id)

    def request_in_log(self, request_id: Identifier) -> bool:
        """Check if a request ID is in the successful or failed request logs."""
        return request_id in self._successful_request_log or request_id in self._failed_request_log

    @computed_field
    @property
    def success_rate(self) -> NonNegativeFloat:
        """Calculate the success rate of requests."""
        if self.total_requests and self.total_requests > 0:
            return (self.successful_requests or 0) / self.total_requests
        return 0

    @computed_field
    @property
    def failure_rate(self) -> NonNegativeFloat:
        """Calculate the failure rate of requests."""
        if self.total_requests and self.total_requests > 0:
            return (self.failed_requests or 0) / self.total_requests
        return 0

    @computed_field
    @property
    def http_success_rate(self) -> NonNegativeFloat:
        """Calculate the HTTP success rate of requests."""
        if self.total_http_requests and self.total_http_requests > 0:
            return (self.successful_http_requests or 0) / self.total_http_requests
        return 0

    @computed_field
    @property
    def http_failure_rate(self) -> NonNegativeFloat:
        """Calculate the HTTP failure rate of requests."""
        if self.total_http_requests and self.total_http_requests > 0:
            return (self.failed_http_requests or 0) / self.total_http_requests
        return 0

    def add_token_usage(
        self,
        *,
        embedding_generated: NonNegativeInt = 0,
        sparse_embedding_generated: NonNegativeInt = 0,
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
        self.token_statistics[TokenCategory.SPARSE_EMBEDDING] += sparse_embedding_generated
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
        self.timing_statistics = TimingStatistics(
            on_call_tool_requests={},
            on_read_resource_requests={},
            on_get_prompt_requests={},
            on_list_tools_requests=[],
            on_list_resources_requests=[],
            on_list_resource_templates_requests=[],
            on_list_prompts_requests=[],
            health_http=[],
            version_http=[],
            settings_http=[],
            state_http=[],
            statistics_http=[],
        )
        self.index_statistics = FileStatistics()
        self.token_statistics = TokenCounter()

    def report(self) -> bytes:
        """Generate a report of the current statistics."""
        return self.dump_json(
            exclude_unset=True,
            exclude_none=True,
            exclude={
                "_successful_request_log",
                "_failed_request_log",
                "_successful_http_request_log",
                "_failed_http_request_log",
            },
        )

    def log_request_from_context(
        self, context: Context | None = None, *, successful: bool = True
    ) -> None:
        """Log a request from the given context.

        Note: This is fastmcp.Context, *not* fastmcp.middleware.MiddlewareContext
        """
        from typing import TYPE_CHECKING

        if TYPE_CHECKING:
            from mcp.shared.context import RequestContext

            from codeweaver.server import AppState

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
            and (identifier := Identifier(request_id=request_id))
            and not self.request_in_log(request_id=identifier)
        ):
            if successful:
                self.add_successful_request(request_id=identifier)
            else:
                self.add_failed_request(request_id=identifier)
        elif successful:
            self.add_successful_request(request_id=None)
        else:
            self.add_failed_request(request_id=None)


_statistics: SessionStatistics = SessionStatistics(
    index_statistics=FileStatistics(),
    token_statistics=TokenCounter(),
    semantic_statistics=None,
    _successful_request_log=[],
    _failed_request_log=[],
    _successful_http_request_log=[],
    _failed_http_request_log=[],
)


def add_failed_request(
    request_id: str | int | Identifier | None = None, *, is_http: bool = False
) -> None:
    """Add a failed request to the log."""
    if _statistics:
        _statistics.add_failed_request(request_id=request_id, is_http=is_http)


def add_successful_request(
    request_id: str | int | Identifier | None = None, *, is_http: bool = False
) -> None:
    """Add a successful request to the log."""
    if _statistics:
        _statistics.add_successful_request(request_id=request_id, is_http=is_http)


def record_timed_http_request(
    request_type: Literal["health", "version", "settings", "state", "statistics"],
    time_taken: PositiveFloat,
) -> None:
    """Record the time taken for an HTTP request of a given type."""
    if _statistics and _statistics.timing_statistics:
        _statistics.timing_statistics.update_http_requests(time_taken, request_type)


def get_session_statistics() -> SessionStatistics:
    """Get the current session statistics."""
    return _statistics


# ===========================================================================
# *                            HTTP Timing Decorator
# ===========================================================================


def timed_http(
    request_type: Literal["health", "version", "settings", "state", "statistics"],
) -> Callable[
    [Callable[..., Awaitable[PlainTextResponse]]], Callable[..., Awaitable[PlainTextResponse]]
]:
    """Decorator to time HTTP endpoints and record success/failure counts.

    Measures end-to-end handler execution time, records duration in milliseconds,
    and increments HTTP success/failed counters based on response status.
    """

    def decorator(
        func: Callable[..., Awaitable[PlainTextResponse]],
    ) -> Callable[..., Awaitable[PlainTextResponse]]:
        async def wrapper(*args: Any, **kwargs: Any) -> PlainTextResponse:
            start = time.perf_counter()
            success: bool | None = None
            try:
                response = await func(*args, **kwargs)
                status = getattr(response, "status_code", 500)
                success = 200 <= int(status) < 400
            except Exception:
                success = False
                raise
            else:
                return response
            finally:
                duration_ms = (time.perf_counter() - start) * 1000
                # Record timing, suppressing any metric errors
                with contextlib.suppress(Exception):
                    record_timed_http_request(request_type, duration_ms)
                # Record HTTP success/failure
                with contextlib.suppress(Exception):
                    if success:
                        add_successful_request(is_http=True)
                    else:
                        add_failed_request(is_http=True)

        return wrapper

    return decorator


__all__ = (
    "FileStatistics",
    "Identifier",
    "LanguageSummary",
    "McpComponentRequests",
    "SessionStatistics",
    "TimingStatistics",
    "TokenCategory",
    "TokenCounter",
    "add_failed_request",
    "add_successful_request",
    "get_session_statistics",
    "record_timed_http_request",
    "timed_http",
)
