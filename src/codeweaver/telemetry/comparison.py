# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""
Baseline comparison calculator for efficiency metrics.

Estimates what naive search approaches would return to compare against
CodeWeaver's actual results, proving efficiency claims with concrete data.

Baseline Approaches:
- Naive Grep: Return entire files that match keywords
- File-Based: Return files with matching names + related files
- Directory-Based: Return entire directories
"""

from __future__ import annotations

from pathlib import Path
from typing import Annotated, ClassVar

from pydantic import Field, NonNegativeFloat, NonNegativeInt, computed_field
from pydantic.dataclasses import dataclass

from codeweaver.core.types import (
    DATACLASS_CONFIG,
    DataclassSerializationMixin,
    LanguageName,
    LanguageNameT,
)


@dataclass(config=DATACLASS_CONFIG)
class BaselineMetrics(DataclassSerializationMixin):
    """Metrics from baseline (naive) search approach."""

    approach: Annotated[str, Field(description="Baseline approach name")]

    files_matched: Annotated[NonNegativeInt, Field(description="Number of files matched")]

    total_lines: Annotated[NonNegativeInt, Field(description="Total lines in matched files")]

    estimated_tokens: Annotated[
        NonNegativeInt, Field(description="Estimated token count for all matched content")
    ]

    estimated_cost_usd: Annotated[NonNegativeFloat, Field(description="Estimated API cost in USD")]

    def _telemetry_keys(self) -> None:
        return None


@dataclass(config=DATACLASS_CONFIG)
class CodeWeaverMetrics(DataclassSerializationMixin):
    """Metrics from actual CodeWeaver search results."""

    files_returned: Annotated[NonNegativeInt, Field(description="Number of files returned")]

    lines_returned: Annotated[NonNegativeInt, Field(description="Total lines returned")]

    actual_tokens: Annotated[NonNegativeInt, Field(description="Actual token count delivered")]

    actual_cost_usd: Annotated[NonNegativeFloat, Field(description="Actual API cost in USD")]

    def _telemetry_keys(self) -> None:
        return None


@dataclass(config=DATACLASS_CONFIG)
class ComparisonReport(DataclassSerializationMixin):
    """Comparison report between baseline and CodeWeaver."""

    baseline: BaselineMetrics
    codeweaver: CodeWeaverMetrics

    def _telemetry_keys(self) -> None:
        return None

    @computed_field
    @property
    def files_reduction_pct(self) -> float:
        """Calculate file count reduction percentage."""
        if self.baseline.files_matched == 0:
            return 0.0
        return (1 - self.codeweaver.files_returned / self.baseline.files_matched) * 100

    @computed_field
    @property
    def lines_reduction_pct(self) -> float:
        """Calculate line count reduction percentage."""
        if self.baseline.total_lines == 0:
            return 0.0
        return (1 - self.codeweaver.lines_returned / self.baseline.total_lines) * 100

    @computed_field
    @property
    def tokens_reduction_pct(self) -> float:
        """Calculate token count reduction percentage."""
        if self.baseline.estimated_tokens == 0:
            return 0.0
        return (1 - self.codeweaver.actual_tokens / self.baseline.estimated_tokens) * 100

    @computed_field
    @property
    def cost_savings_pct(self) -> float:
        """Calculate cost savings percentage."""
        if self.baseline.estimated_cost_usd == 0:
            return 0.0
        return (1 - self.codeweaver.actual_cost_usd / self.baseline.estimated_cost_usd) * 100

    def to_dict(self) -> dict[str, object]:
        """Convert comparison to dictionary format."""
        return self.dump_python(round_trip=True)


class BaselineComparator:
    """
    Calculator for baseline comparison metrics.

    Estimates what naive search approaches would return for comparison
    against CodeWeaver's actual results.
    """

    # Average tokens per 1000 bytes by language
    # Based on typical tokenizer behavior (GPT-style tokenizers)
    TOKENS_PER_KB: ClassVar[dict[LanguageNameT, NonNegativeInt]] = {
        LanguageName("python"): 250,  # ~4 bytes per token
        LanguageName("typescript"): 220,  # ~4.5 bytes per token
        LanguageName("javascript"): 220,
        LanguageName("rust"): 200,  # ~5 bytes per token
        LanguageName("go"): 200,
        LanguageName("java"): 200,
        LanguageName("c"): 200,
        LanguageName("cpp"): 200,
        LanguageName("csharp"): 210,
        LanguageName("markdown"): 300,  # ~3.3 bytes per token
        LanguageName("text"): 300,
        LanguageName("json"): 180,
        LanguageName("yaml"): 200,
        LanguageName("toml"): 200,
        LanguageName("default"): 220,  # Conservative default
    }

    # Cost per 1000 tokens for frontend models (Claude Sonnet 4)
    # Weighted average: 80% input ($0.003/1K) + 20% output ($0.015/1K)
    COST_PER_1K_TOKENS_USD = (0.8 * 0.003) + (0.2 * 0.015)  # = 0.0054

    def estimate_naive_grep_approach(
        self, query_keywords: list[str], repository_files: list[tuple[Path, LanguageNameT, int]]
    ) -> BaselineMetrics:
        """
        Estimate naive grep approach metrics.

        Logic:
        1. Search all files for keyword matches
        2. Return ENTIRE files that match (not just matched sections)
        3. Count total tokens in all matched files

        Args:
            query_keywords: Keywords extracted from query
            repository_files: List of (path, language, size_bytes) tuples

        Returns:
            BaselineMetrics for naive grep approach
        """
        # Simulate grep matching
        matched_files: list[tuple[Path, LanguageNameT, int]] = []
        total_bytes = 0

        for path, language, size_bytes in repository_files:
            # Simple simulation: match if any keyword appears in filename
            # In real implementation, would check file contents
            file = str(path).lower()
            if any(keyword.lower() in file for keyword in query_keywords):
                matched_files.append((path, language, size_bytes))
                total_bytes += size_bytes

        return self._assemble_estimate(matched_files, total_bytes, "grep_full_files")

    def estimate_file_based_search(
        self, query_keywords: list[str], repository_files: list[tuple[Path, LanguageNameT, int]]
    ) -> BaselineMetrics:
        """
        Estimate file-name based search metrics.

        Logic:
        1. Search for query terms in file names
        2. Return matched files + files in same directory
        3. Count total tokens

        Args:
            query_keywords: Keywords extracted from query
            repository_files: List of (path, language, size_bytes) tuples

        Returns:
            BaselineMetrics for file-based search
        """
        matched_files: list[tuple[Path, LanguageNameT, int]] = []
        matched_dirs: set[Path] = set()
        total_bytes = 0

        # Find directly matched files and their directories
        for path, language, size_bytes in repository_files:
            filename = path.name.lower()
            if any(keyword.lower() in filename for keyword in query_keywords):
                matched_files.append((path, language, size_bytes))
                matched_dirs.add(path.parent)
                total_bytes += size_bytes

        # Add all files from matched directories
        for path, language, size_bytes in repository_files:
            if path.parent in matched_dirs and (path, language, size_bytes) not in matched_files:
                matched_files.append((path, language, size_bytes))
                total_bytes += size_bytes

        return self._assemble_estimate(matched_files, total_bytes, "file_name_with_directory")

    def _assemble_estimate(
        self, matched_files: list[tuple[Path, LanguageNameT, int]], total_bytes: int, approach: str
    ) -> BaselineMetrics:
        total_tokens = self._estimate_tokens(matched_files)
        estimated_cost = total_tokens / 1000 * self.COST_PER_1K_TOKENS_USD
        total_lines = total_bytes // 50
        return BaselineMetrics(
            approach=approach,
            files_matched=len(matched_files),
            total_lines=total_lines,
            estimated_tokens=total_tokens,
            estimated_cost_usd=estimated_cost,
        )

    def compare(self, baseline: BaselineMetrics, codeweaver: CodeWeaverMetrics) -> ComparisonReport:
        """
        Generate comparison report.

        Args:
            baseline: Baseline approach metrics
            codeweaver: CodeWeaver actual metrics

        Returns:
            ComparisonReport with improvement percentages
        """
        return ComparisonReport(baseline=baseline, codeweaver=codeweaver)

    def _estimate_tokens(self, files: list[tuple[Path, LanguageNameT, int]]) -> int:
        """
        Estimate token count for list of files.

        Args:
            files: List of (path, language, size_bytes) tuples

        Returns:
            Estimated total token count
        """
        total_tokens = 0

        for _, language, size_bytes in files:
            # Get tokens per KB for this language
            tokens_per_kb = type(self).TOKENS_PER_KB.get(
                LanguageName(language.lower()), type(self).TOKENS_PER_KB[LanguageName("default")]
            )

            # Convert bytes to KB and calculate tokens
            size_kb = size_bytes / 1000
            tokens = int(size_kb * tokens_per_kb)

            total_tokens += tokens

        return total_tokens


__all__ = ("BaselineComparator", "BaselineMetrics", "CodeWeaverMetrics", "ComparisonReport")
