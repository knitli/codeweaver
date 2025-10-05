"""# Implementation of the find_code tool.

CodeWeaver differentiates between *internal* and *external* tools. External tools -- and there is only one, this one, the **`find_code`** tool -- are exposed to the user and user's AI agents. `find_code` is intentionally very simple. This module contains the back-end, execution-side, of the `find_code` tool. The entry-point exposed to users and agents is in `codeweaver.app_bindings`.

## How it Works

You, or your AI agents, simply ask a question, explain what you are trying to do or what you need information for, and CodeWeaver will answer it.

For example, your agent might say:
    > Note: The main parameters for `find_code` that are exposed to users and agents are `query`, `intent`, and `focus_languages`. There are also `token_limit` and `include_tests`, but those are fairly self-explanatory.
    ```
    ```

`find_code` is different from other MCP tools in that it:
    1) Is intentionally designed to reduce "*cognitive load*"[^1] on *agents*. Put simply, AI agents have "great minds and terrible hands." `find_code` aims to bridge that gap between intellect and action. The explosion of MCP tools has also increased the cognitive load on agents -- when there are 100 tools, which one do you use? It's a hard task for a human, and harder for an AI. `find_code` aims to be a simple, universal tool that can be used in many situations.
    2) `find_code`, and all of CodeWeaver, is entirely designed to *narrow context*. AI agents are very prone to "*context poisoning*" and "*context overload*". In even small codebases, this can happen very quickly -- often before the agent even gets to the point of using a tool. `find_code` intentionally filters and shields the user's agent from unnecessary context, and only provides the context that is relevant to the query. This is a key part of CodeWeaver's design philosophy.
    3) It's context-aware. `find_code` understands the context of your project, the files, the languages, and the structure. It uses this context to provide relevant results.

    [^1]: AI agents don't experience 'cognitive load' in the human sense, but we use the term here metaphorically. Practically speaking, two things actually happen: 1) Context 'poisoning' -- the agent's context gets filled with irrelevant information that steers it away from the results you want, 2) The agent, which really doesn't 'think' in the human sense, can't tell what tool to use, so it often picks the wrong one -- tool use is more of a side effect of their training to generate language.
"""

from __future__ import annotations

import time

from collections.abc import Sequence
from pathlib import Path
from typing import TYPE_CHECKING, NamedTuple, cast

from pydantic import NonNegativeInt, PositiveInt

from codeweaver._common import DictView
from codeweaver._data_structures import DiscoveredFile, Span
from codeweaver._statistics import SessionStatistics
from codeweaver._utils import estimate_tokens, uuid7
from codeweaver.exceptions import QueryError
from codeweaver.language import SemanticSearchLanguage
from codeweaver.models.core import CodeMatch, CodeMatchType, FindCodeResponseSummary, SearchStrategy
from codeweaver.models.intent import IntentType
from codeweaver.services.discovery import FileDiscoveryService
from codeweaver.settings_types import CodeWeaverSettingsDict


if TYPE_CHECKING:
    from codeweaver.settings import CodeWeaverSettings


class MatchedSection(NamedTuple):
    """Represents a matched section within a file."""

    content: str
    span: Span
    score: NonNegativeInt
    filename: str | None = None
    file_path: Path | None = None
    chunk_number: PositiveInt | None = None


async def find_code_implementation(
    query: str,
    settings: DictView[CodeWeaverSettingsDict],
    *,
    intent: IntentType | None = None,
    token_limit: int = 10000,
    include_tests: bool = False,
    focus_languages: tuple[SemanticSearchLanguage, ...] | Sequence[str] | None = None,
    max_results: PositiveInt = 50,
    statistics: SessionStatistics | None = None,
) -> FindCodeResponseSummary:
    """Phase 1 implementation of find_code tool.

    Uses basic keyword-based text search with file discovery.
    This will be enhanced in Phase 2 with semantic search.

    Args:
        query: Search query
        settings: An immutable view of the current CodeWeaver settings
        intent: Query intent (optional)
        token_limit: Maximum tokens in response
        include_tests: Whether to include test files
        focus_languages: Languages to focus the search on

    Returns:
        Structured response with code matches
    """
    start_time = time.time()
    try:
        discovery_service = FileDiscoveryService(settings)
        discovered_files, _filtered_files = await discovery_service.get_discovered_files()
        if statistics:
            for file in discovered_files:
                statistics.add_file_operation(file.path, "retrieved")
        if focus_languages:
            test_languages: set[str] = {str(lang) for lang in focus_languages}
            focus_filtered_languages: list[DiscoveredFile] = [
                file for file in discovered_files if str(file.ext_kind.language) in test_languages
            ]
            discovered_files = focus_filtered_languages
        matches = await basic_text_search(query, discovered_files, settings, token_limit)
        execution_time_ms = (time.time() - start_time) * 1000
        if statistics:
            processed_files = {match.file.path for match in matches}
            for file_path in processed_files:
                statistics.add_file_operation(file_path, "processed")
            total_tokens = sum(estimate_tokens(match.content) for match in matches)
            statistics.add_token_usage(search_results=total_tokens)
    except Exception as e:
        raise QueryError(
            f"Failed to execute find_code query: {query}",
            details={"error": str(e)},
            suggestions=[
                "Check that the query is valid",
                "Ensure the project directory is accessible",
                "Try a simpler query",
            ],
        ) from e
    else:
        return FindCodeResponseSummary(
            matches=matches,
            summary=f"Found {len(matches)} matches for '{query}'",
            query_intent=intent,
            total_matches=len(matches),
            token_count=sum(estimate_tokens(match.content) for match in matches),
            execution_time_ms=execution_time_ms,
            search_strategy=(SearchStrategy.FILE_DISCOVERY, SearchStrategy.TEXT_SEARCH),
            languages_found=cast(
                tuple[SemanticSearchLanguage | str, ...],
                tuple(str(file.ext_kind.language) for file in discovered_files),
            ),
        )


async def basic_text_search(
    query: str, files: Sequence[DiscoveredFile], settings: CodeWeaverSettings, token_limit: int
) -> list[CodeMatch]:
    """Basic keyword-based search implementation for Phase 1.

    Args:
        query: Search query
        files: List of files to search
        settings: CodeWeaver settings
        token_limit: Maximum tokens for results

    Returns:
        List of code matches
    """
    matches: list[CodeMatch] = []
    query_terms = query.lower().split()
    current_token_count = 0
    for file in files:
        abs_path = file.path.absolute()
        try:
            content = abs_path.read_text(encoding="utf-8", errors="ignore")
            if content and len(content) > 3 and (content[:3] == "ï»¿"):
                continue
        except OSError:
            continue
        content_lower = content.lower()
        score = sum(content_lower.count(term) for term in query_terms)
        if score > 0:
            lines = content.split("\n")
            if best_section := find_best_section(lines, query_terms):
                match = CodeMatch(
                    file=file,
                    related_symbols=("",),
                    content=best_section.content,
                    span=best_section.span,
                    relevance_score=min(score / 10.0, 1.0),
                    match_type=CodeMatchType.KEYWORD,
                    surrounding_context=get_surrounding_context(lines, best_section.span),
                )
                match_tokens = len(match.content)
                if current_token_count + match_tokens <= token_limit:
                    matches.append(match)
                    current_token_count += match_tokens
                else:
                    break
    matches.sort(key=lambda m: m.relevance_score, reverse=True)
    return matches


def find_best_section(lines: list[str], query_terms: list[str]) -> MatchedSection | None:
    """Find the best matching section in a file.

    Args:
        lines: File lines
        query_terms: Search terms

    Returns:
        Best matching section or None
    """
    if not lines:
        return None
    best_score = 0
    best_start = 0
    best_end = min(50, len(lines))
    window_size = 50
    source_id = uuid7()
    for start in range(0, len(lines), 25):
        end = min(start + window_size, len(lines))
        section_lines = lines[start:end]
        section_content = "\n".join(section_lines).lower()
        score = sum(section_content.count(term) for term in query_terms)
        if score > best_score:
            best_score = score
            best_start = start
            best_end = end
    if best_score == 0:
        return MatchedSection(
            content="\n".join(lines[:window_size]),
            span=Span(1, min(window_size, len(lines)), source_id),
            score=0,
        )
    return MatchedSection(
        content="\n".join(lines[best_start:best_end]),
        span=Span(best_start + 1, best_end, source_id),
        score=best_score,
    )


def get_surrounding_context(lines: list[str], span: Span, context_lines: int = 5) -> str:
    """Get surrounding context for a code match.

    Args:
        lines: All file lines
        span: Range of matched lines (1-indexed)
        context_lines: Number of context lines before/after

    Returns:
        Context string
    """
    start_line, end_line = span
    start_idx = max(0, start_line - 1 - context_lines)
    end_idx = min(len(lines), end_line + context_lines)
    context_section = lines[start_idx:end_idx]
    result_lines: list[str] = []
    for i, line in enumerate(context_section):
        line_num = start_idx + i + 1
        if start_line <= line_num <= end_line:
            result_lines.append(f"> {line_num:4d}: {line}")
        else:
            result_lines.append(f"  {line_num:4d}: {line}")
    return "\n".join(result_lines)


__all__ = (
    "MatchedSection",
    "find_best_section",
    "find_code_implementation",
    "get_surrounding_context",
)
