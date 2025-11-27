# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Reference query test suite for validating search quality on CodeWeaver's codebase.

This test suite implements T014 requirements:
- Dogfooding: CodeWeaver searches its own codebase
- 25+ hand-crafted query/result pairs covering all IntentTypes
- Precision@3 and Precision@5 metrics calculation
- Quality targets: P@3 ≥70%, P@5 ≥80%

Test Structure:
    1. Load reference queries from YAML fixture
    2. Execute find_code for each query
    3. Calculate precision metrics per query
    4. Aggregate and report overall precision
    5. Fail if quality targets not met
"""

from __future__ import annotations

import logging

from pathlib import Path
from typing import NamedTuple

import pytest
import yaml

from codeweaver.agent_api.find_code import find_code
from codeweaver.agent_api.find_code.intent import IntentType


logger = logging.getLogger(__name__)


# ============================================================================
# Test Data Models
# ============================================================================


class ReferenceQuery(NamedTuple):
    """Reference query with expected results for precision calculation."""

    query: str
    intent: IntentType
    precision_target: int  # 3 or 5
    expected_files: list[str]
    description: str

    @property
    def expected_file_names(self) -> set[str]:
        """Extract file names (not full paths) for matching."""
        return {Path(f).name for f in self.expected_files}


class QueryResult(NamedTuple):
    """Result of executing a reference query."""

    query: ReferenceQuery
    actual_files: list[str]  # Top N files returned by find_code
    hits: int  # Number of expected files found in top N
    precision: float  # hits / len(expected_files)
    recall: float  # hits / len(expected_files) (same as precision for this test)


# ============================================================================
# Fixture Loading
# ============================================================================


def load_reference_queries() -> list[ReferenceQuery]:
    """Load reference queries from YAML fixture file.

    Returns:
        List of ReferenceQuery objects

    Raises:
        FileNotFoundError: If reference_queries.yml not found
        yaml.YAMLError: If YAML is malformed
    """
    fixture_path = Path(__file__).parent.parent / "fixtures" / "reference_queries.yml"

    if not fixture_path.exists():
        raise FileNotFoundError(f"Reference queries fixture not found: {fixture_path}")

    with fixture_path.open() as f:
        data = yaml.safe_load(f)

    queries = []
    for item in data["queries"]:
        query = ReferenceQuery(
            query=item["query"],
            intent=IntentType(item["intent"].lower()),
            precision_target=item["precision_target"],
            expected_files=item["expected_files"],
            description=item.get("description", ""),
        )
        queries.append(query)

    logger.info("Loaded %d reference queries from %s", len(queries), fixture_path)
    return queries


# ============================================================================
# Precision Calculation
# ============================================================================


def calculate_precision(
    expected_files: list[str], actual_files: list[str], top_k: int
) -> tuple[int, float]:
    """Calculate precision@K for a query result.

    Args:
        expected_files: List of expected file paths
        actual_files: List of actual file paths returned by find_code
        top_k: Number of top results to consider (3 or 5)

    Returns:
        Tuple of (hits, precision) where:
        - hits: number of expected files found in top K
        - precision: hits / len(expected_files)
    """
    # Extract file names for comparison (ignore full paths)
    expected_names = {Path(f).name for f in expected_files}
    actual_names = {Path(f).name for f in actual_files[:top_k]}

    # Calculate hits
    hits = len(expected_names & actual_names)

    # Calculate precision (what % of expected files were found)
    precision = hits / len(expected_files) if expected_files else 0.0

    return hits, precision


# ============================================================================
# Test Execution
# ============================================================================


@pytest.fixture(scope="module")
def reference_queries() -> list[ReferenceQuery]:
    """Fixture providing loaded reference queries."""
    return load_reference_queries()


@pytest.mark.integration
@pytest.mark.asyncio
async def test_reference_queries_comprehensive(
    reference_queries: list[ReferenceQuery], configured_providers
) -> None:
    """Execute all reference queries and validate precision targets.

    This is the main comprehensive test that:
    1. Runs all reference queries
    2. Calculates precision@3 and precision@5
    3. Reports detailed results
    4. Fails if quality targets not met

    Quality Targets (from T014):
    - Precision@3 ≥ 70% (14/20 queries)
    - Precision@5 ≥ 80% (16/20 queries)

    Note: This test requires real providers with real embeddings and vector store.
    When using mock providers (configured_providers fixture), the test will pass
    basic validation but skip quality target assertions.
    """
    # Check if we're using mock providers by checking provider type
    is_mock_provider = "Mock" in str(type(configured_providers))

    results: list[QueryResult] = []
    precision_at_3_scores: list[float] = []
    precision_at_5_scores: list[float] = []

    # Execute each query and collect results
    for test_case in reference_queries:
        logger.info(
            "Executing query: '%s' (intent=%s, target=P@%d)",
            test_case.query,
            test_case.intent.value,
            test_case.precision_target,
        )

        # Execute find_code
        response = await find_code(test_case.query, intent=test_case.intent, max_results=10)

        # Extract file paths from matches
        actual_files = [match.file.path.as_posix() for match in response.matches]

        # Calculate precision at target level
        hits, precision = calculate_precision(
            test_case.expected_files, actual_files, test_case.precision_target
        )

        # Store result
        result = QueryResult(
            query=test_case,
            actual_files=actual_files[: test_case.precision_target],
            hits=hits,
            precision=precision,
            recall=precision,  # Same as precision for this test design
        )
        results.append(result)

        # Collect by precision level
        if test_case.precision_target == 3:
            precision_at_3_scores.append(precision)
        elif test_case.precision_target == 5:
            precision_at_5_scores.append(precision)

        logger.info(
            "  Result: P@%d = %.2f%% (%d/%d hits)",
            test_case.precision_target,
            precision * 100,
            hits,
            len(test_case.expected_files),
        )

    # ========================================================================
    # Calculate aggregate metrics
    # ========================================================================

    precision_at_3 = (
        sum(precision_at_3_scores) / len(precision_at_3_scores) if precision_at_3_scores else 0.0
    )
    precision_at_5 = (
        sum(precision_at_5_scores) / len(precision_at_5_scores) if precision_at_5_scores else 0.0
    )

    overall_precision = sum([r.precision for r in results]) / len(results) if results else 0.0

    # ========================================================================
    # Report detailed results
    # ========================================================================

    logger.info("\n%s", "=" * 80)
    logger.info("REFERENCE QUERY TEST RESULTS")
    logger.info("%s", "=" * 80)
    logger.info("Total queries: %d", len(results))
    logger.info("Precision@3 queries: %d", len(precision_at_3_scores))
    logger.info("Precision@5 queries: %d", len(precision_at_5_scores))
    logger.info("")
    logger.info("AGGREGATE METRICS:")
    logger.info("  Overall Precision: %.2f%%", overall_precision * 100)
    logger.info("  Precision@3: %.2f%%", precision_at_3 * 100)
    logger.info("  Precision@5: %.2f%%", precision_at_5 * 100)
    logger.info("")
    logger.info("QUALITY TARGETS:")
    logger.info(
        "  P@3 Target: 70%% (Actual: %.2f%%) %s",
        precision_at_3 * 100,
        "✓" if precision_at_3 >= 0.70 else "✗",
    )
    logger.info(
        "  P@5 Target: 80%% (Actual: %.2f%%) %s",
        precision_at_5 * 100,
        "✓" if precision_at_5 >= 0.80 else "✗",
    )
    logger.info("=" * 80)

    # ========================================================================
    # Report per-query details
    # ========================================================================

    logger.info("\nPER-QUERY RESULTS:")
    logger.info("-" * 80)

    by_intent: dict[IntentType, list[QueryResult]] = {}
    for result in results:
        intent = result.query.intent
        by_intent.setdefault(intent, []).append(result)

    for intent in sorted(by_intent.keys(), key=lambda x: x.value):
        intent_results = by_intent[intent]
        intent_precision = sum(r.precision for r in intent_results) / len(intent_results)
        logger.info("\n%s Intent (%.2f%% average):", intent.value.upper(), intent_precision * 100)

        for result in intent_results:
            status = "✓" if result.precision >= 0.67 else "✗"
            logger.info(
                "  %s [P@%d=%.0f%%] %s",
                status,
                result.query.precision_target,
                result.precision * 100,
                result.query.query[:60],
            )

            if result.hits < len(result.query.expected_files):
                # Show what was missed
                expected_names = result.query.expected_file_names
                actual_names = {Path(f).name for f in result.actual_files}
                missed = expected_names - actual_names
                if missed:
                    logger.info("      Missed: %s", ", ".join(sorted(missed)))

    logger.info("\n%s\n", "=" * 80)

    # ========================================================================
    # Assert quality targets (skip for mock providers)
    # ========================================================================

    if is_mock_provider:
        logger.warning(
            "Using mock providers - skipping quality target assertions. "
            "Test validates basic functionality only."
        )
        # Just verify the test infrastructure works
        assert len(results) > 0, "Should have executed at least one query"
        return

    # Real provider assertions
    assert precision_at_3 >= 0.70, (
        f"Precision@3 ({precision_at_3:.2%}) below target (70%). "
        f"Search quality needs improvement for top-3 results."
    )

    assert precision_at_5 >= 0.80, (
        f"Precision@5 ({precision_at_5:.2%}) below target (80%). "
        f"Search quality needs improvement for top-5 results."
    )


# ============================================================================
# Individual Query Tests (for targeted debugging)
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.skip_ci  # This test uses real providers and times out in CI; use for local debugging only
@pytest.mark.parametrize(
    "query_index",
    range(25),  # 25 reference queries in fixture
)
async def test_individual_reference_query(query_index: int) -> None:
    """Test individual reference queries for targeted debugging.

    This parametrized test allows running specific queries:
        pytest tests/integration/test_reference_queries.py::test_individual_reference_query[5]

    Useful for debugging specific query failures without running full suite.
    """
    queries = load_reference_queries()

    if query_index >= len(queries):
        pytest.skip(f"Query index {query_index} out of range (max: {len(queries) - 1})")

    test_case = queries[query_index]

    logger.info("Testing query: '%s'", test_case.query)

    # Execute find_code
    response = await find_code(test_case.query, intent=test_case.intent, max_results=10)

    # Extract file paths
    actual_files = [match.file.path.as_posix() for match in response.matches]

    # Calculate precision
    hits, precision = calculate_precision(
        test_case.expected_files, actual_files, test_case.precision_target
    )

    # Report
    logger.info(
        "Result: P@%d = %.2f%% (%d/%d hits)",
        test_case.precision_target,
        precision * 100,
        hits,
        len(test_case.expected_files),
    )

    if hits < len(test_case.expected_files):
        expected_names = test_case.expected_file_names
        actual_names = {Path(f).name for f in actual_files[: test_case.precision_target]}
        missed = expected_names - actual_names
        logger.warning("Missed expected files: %s", missed)

    # Soft assertion for individual queries (don't fail, just warn)
    if precision < 0.5:
        logger.warning("Query precision (%.2f%%) significantly below expectations", precision * 100)


# ============================================================================
# Intent Coverage Validation
# ============================================================================


@pytest.mark.integration
def test_intent_coverage_complete(reference_queries: list[ReferenceQuery]) -> None:
    """Validate that all IntentTypes are covered in reference queries.

    Ensures comprehensive testing across all query intent categories.
    """
    covered_intents = {q.intent for q in reference_queries}
    all_intents = set(IntentType)

    missing_intents = all_intents - covered_intents

    assert not missing_intents, (
        f"Reference queries missing coverage for intents: {missing_intents}. "
        f"Add queries for all IntentType values."
    )

    # Report coverage statistics
    intent_counts = dict.fromkeys(IntentType, 0)
    for query in reference_queries:
        intent_counts[query.intent] += 1

    logger.info("\nIntent Coverage:")
    for intent, count in sorted(intent_counts.items(), key=lambda x: x[1], reverse=True):
        logger.info("  %s: %d queries", intent.value.upper(), count)


# ============================================================================
# Query Diversity Validation
# ============================================================================


@pytest.mark.integration
def test_query_diversity_metrics(reference_queries: list[ReferenceQuery]) -> None:
    """Validate query diversity and balance across intents and difficulties.

    Ensures test suite has good coverage of:
    - All intent types (minimum 2 per intent)
    - Mix of P@3 and P@5 targets
    - Variety of expected file counts (1-5 files)
    """
    # Check intent distribution
    intent_counts = dict.fromkeys(IntentType, 0)
    for query in reference_queries:
        intent_counts[query.intent] += 1

    for intent, count in intent_counts.items():
        assert count >= 2, f"Intent {intent.value} has insufficient coverage ({count} queries)"

    # Check precision target distribution
    p3_count = sum(1 for q in reference_queries if q.precision_target == 3)
    p5_count = sum(1 for q in reference_queries if q.precision_target == 5)

    logger.info("\nPrecision Target Distribution:")
    logger.info("  P@3 queries: %d", p3_count)
    logger.info("  P@5 queries: %d", p5_count)

    assert p3_count >= 10, "Need at least 10 P@3 queries for valid metrics"
    assert p5_count >= 10, "Need at least 10 P@5 queries for valid metrics"

    # Check expected file count diversity
    file_counts = [len(q.expected_files) for q in reference_queries]
    avg_files = sum(file_counts) / len(file_counts)
    min_files = min(file_counts)
    max_files = max(file_counts)

    logger.info("\nExpected Files per Query:")
    logger.info("  Average: %.1f files", avg_files)
    logger.info("  Range: %d-%d files", min_files, max_files)

    assert max_files >= 3, "Include some queries with 3+ expected files"
    assert min_files <= 3, "Include some queries with 1-3 expected files"


__all__ = (
    "QueryResult",
    "ReferenceQuery",
    "calculate_precision",
    "load_reference_queries",
    "test_individual_reference_query",
    "test_intent_coverage_complete",
    "test_query_diversity_metrics",
    "test_reference_queries_comprehensive",
)
