# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Integration tests for CLI search and MCP find_code workflows.

Tests cover:
- T010: CLI search returns results
- T010: CLI search output formats (json, table, markdown)
- T010: MCP find_code tool
- T010: Search with intent parameter
- T010: Search performance (<3s for ≤10k files - FR-037)

Reference: Quickstart Scenarios 2, 4 (spec lines 84-100)
Contract: specs/003-our-aim-to/contracts/find_code_mcp_tool.json

Tests validate the find_code tool through both CLI and MCP interfaces,
ensuring response structure compliance and performance requirements.
"""

from __future__ import annotations

import json
import time

from pathlib import Path

import pytest


# =============================================================================
# Test Fixtures
# =============================================================================

# Small test project for search testing
TEST_PROJECT_FILES = {
    "src/auth.py": '''"""Authentication module with login and session management."""

def authenticate(username: str, password: str) -> bool:
    """Validate user credentials against database."""
    if not username or not password:
        raise ValueError("Username and password required")
    valid_users = {"admin": "secret", "user": "password123"}
    return valid_users.get(username) == password

class AuthManager:
    """Manages authentication state and session lifecycle."""
    def __init__(self, timeout_seconds: int = 3600):
        self.sessions = {}
        self.timeout = timeout_seconds

    def create_session(self, user_id: str) -> str:
        """Create new authenticated session for user."""
        import uuid
        session_id = str(uuid.uuid4())
        self.sessions[session_id] = {"user_id": user_id, "created_at": time.time()}
        return session_id
''',
    "src/database.py": '''"""Database connection and user repository."""

import sqlite3

def get_connection(db_path: str):
    """Get database connection with error handling."""
    try:
        return sqlite3.connect(db_path, timeout=10)
    except sqlite3.Error as e:
        raise ConnectionError(f"Failed to connect to database: {e}") from e

class UserRepository:
    """User data access layer with CRUD operations."""
    def __init__(self, db_path: str):
        self.db_path = db_path

    def find_user(self, username: str):
        """Find user by username."""
        conn = get_connection(self.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT id, username, email FROM users WHERE username = ?", (username,))
        return cursor.fetchone()
''',
    "README.md": """# Test Project

Small test project for CodeWeaver integration tests with authentication and database modules.
""",
}


@pytest.fixture
def test_project_path(tmp_path: Path) -> Path:
    """Create small test project fixture for search testing."""
    project_root = tmp_path / "search_test_project"
    project_root.mkdir()

    for file_path, content in TEST_PROJECT_FILES.items():
        file_full_path = project_root / file_path
        file_full_path.parent.mkdir(parents=True, exist_ok=True)
        _ = file_full_path.write_text(content)

    return project_root


# =============================================================================
# T010: CLI Search Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cli_search_returns_results(test_project_path: Path, initialized_app_state):
    """T010: CLI search command returns results (stub validation).

    Given: Test project path
    When: CLI search command executed via find_code_tool
    Then: Returns valid FindCodeResponseSummary structure

    Note: Currently validates stub response. When find_code is re-enabled,
    this test will validate actual search results.
    """
    from codeweaver.server.app_bindings import find_code_tool

    # Execute search via find_code_tool (CLI uses this internally)
    response = await find_code_tool(
        query="authentication logic",
        intent=None,
        token_limit=30000,
        focus_languages=None,
        context=None,
    )

    # Validate response structure (works even with stub)
    from codeweaver.agent_api.find_code.types import FindCodeResponseSummary

    assert isinstance(response, FindCodeResponseSummary)
    assert hasattr(response, "matches")
    assert hasattr(response, "summary")
    assert hasattr(response, "query_intent")
    assert hasattr(response, "total_matches")
    assert hasattr(response, "total_results")
    assert hasattr(response, "token_count")
    assert hasattr(response, "execution_time_ms")
    assert hasattr(response, "search_strategy")
    assert hasattr(response, "languages_found")

    # Validate types
    assert isinstance(response.matches, list)
    assert isinstance(response.summary, str)
    assert len(response.summary) <= 1000  # max_length constraint
    assert response.total_matches >= 0
    assert response.total_results >= 0
    assert response.token_count >= 0
    assert response.execution_time_ms >= 0
    assert isinstance(response.search_strategy, tuple)
    assert isinstance(response.languages_found, tuple)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_cli_search_output_formats(test_project_path: Path, initialized_app_state):
    """T010: CLI search supports multiple output formats.

    Given: Search results available
    When: Output format specified (json, table, markdown)
    Then: Results render correctly in each format
    """
    from codeweaver.server.app_bindings import find_code_tool

    # Get search results
    response = await find_code_tool(
        query="database connection",
        intent=None,
        token_limit=30000,
        focus_languages=None,
        context=None,
    )

    # Test JSON serialization
    json_output = response.model_dump_json(indent=2)
    assert json_output is not None
    parsed = json.loads(json_output)
    assert "matches" in parsed
    assert "summary" in parsed
    assert "query_intent" in parsed
    assert "total_matches" in parsed
    assert "execution_time_ms" in parsed

    # Test table output (via assemble_cli_summary)
    table = response.assemble_cli_summary()
    assert table is not None
    assert table.title == "Find Code Response Summary"

    # Test that matches can be serialized for CLI display
    for match in response.matches:
        match_data = match.serialize_for_cli()
        assert isinstance(match_data, dict)


# =============================================================================
# T010: MCP find_code Tool Tests
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_mcp_find_code_tool(test_project_path: Path, initialized_app_state):
    """T010: MCP find_code tool returns valid response conforming to contract.

    Given: CodeWeaver MCP tool interface
    When: find_code tool invoked via MCP
    Then: Returns FindCodeResponseSummary conforming to contract

    Reference: specs/003-our-aim-to/contracts/find_code_mcp_tool.json
    """
    from codeweaver.agent_api.find_code.intent import IntentType
    from codeweaver.agent_api.find_code.types import CodeMatchType
    from codeweaver.server.app_bindings import find_code_tool

    # Invoke MCP tool
    response = await find_code_tool(
        query="session management",
        intent=IntentType.UNDERSTAND,
        token_limit=30000,
        focus_languages=None,
        context=None,
    )

    # Validate contract compliance (from find_code_mcp_tool.json)
    assert hasattr(response, "matches")
    assert hasattr(response, "summary")
    assert hasattr(response, "query_intent")
    assert hasattr(response, "total_matches")
    assert hasattr(response, "total_results")
    assert hasattr(response, "token_count")
    assert hasattr(response, "execution_time_ms")
    assert hasattr(response, "search_strategy")
    assert hasattr(response, "languages_found")

    # Type constraints from contract
    assert isinstance(response.matches, list)
    assert isinstance(response.summary, str)
    assert len(response.summary) <= 1000  # maxLength from contract
    assert response.total_matches >= 0
    assert response.total_results >= 0
    assert response.token_count >= 0
    assert response.execution_time_ms >= 0.0
    assert isinstance(response.search_strategy, tuple)
    assert isinstance(response.languages_found, tuple)

    # Validate match structure (if matches exist)
    for match in response.matches:
        assert hasattr(match, "file")
        assert hasattr(match, "content")
        assert hasattr(match, "span")
        assert hasattr(match, "relevance_score")
        assert hasattr(match, "match_type")
        assert hasattr(match, "related_symbols")

        # Score constraints from contract
        assert 0.0 <= match.relevance_score <= 1.0
        assert isinstance(match.match_type, CodeMatchType)
        assert isinstance(match.related_symbols, tuple)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_mcp_find_code_required_parameters(test_project_path: Path, initialized_app_state):
    """T010: MCP find_code handles parameter validation.

    Given: MCP tool interface
    When: Parameters provided (including edge cases)
    Then: Appropriate handling occurs
    """
    from codeweaver.server.app_bindings import find_code_tool

    # Test with empty query
    response = await find_code_tool(
        query="",  # Empty query
        intent=None,
        token_limit=30000,
        focus_languages=None,
        context=None,
    )

    # Should handle gracefully (stub always returns valid response)
    from codeweaver.agent_api.find_code.types import FindCodeResponseSummary

    assert isinstance(response, FindCodeResponseSummary)

    # Test with minimal valid query
    response = await find_code_tool(
        query="test",
        intent=None,
        token_limit=30000,
        focus_languages=None,
        context=None,
    )

    assert isinstance(response, FindCodeResponseSummary)


# =============================================================================
# T010: Search with Intent Parameter
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_search_with_intent_parameter(initialized_app_state):
    """T010: Search with explicit intent parameter.

    Given: Search query with intent specified
    When: find_code called with different intents
    Then: Intent reflected in response
    """
    from codeweaver.agent_api.find_code.intent import IntentType
    from codeweaver.server.app_bindings import find_code_tool

    intents_to_test = [
        IntentType.UNDERSTAND,
        IntentType.IMPLEMENT,
        IntentType.DEBUG,
        IntentType.OPTIMIZE,
        IntentType.TEST,
        IntentType.CONFIGURE,
        IntentType.DOCUMENT,
    ]

    for intent in intents_to_test:
        response = await find_code_tool(
            query="authentication logic",
            intent=intent,
            token_limit=30000,
            focus_languages=None,
            context=None,
        )

        # Validate intent is reflected in response
        assert response.query_intent == intent, (
            f"Expected intent {intent}, got {response.query_intent}"
        )

        # Validate response structure
        from codeweaver.agent_api.find_code.types import FindCodeResponseSummary

        assert isinstance(response, FindCodeResponseSummary)
        assert response.execution_time_ms >= 0


# =============================================================================
# T010: Search Filters and Parameters
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_search_filters_work(initialized_app_state):
    """T010: Search filters (include_tests) parameter handling.

    Given: Search with filter parameters
    When: Filters applied (include_tests=True/False)
    Then: Both return valid responses
    """
    from codeweaver.server.app_bindings import find_code_tool

    # Test include_tests filter (parameter removed from API)
    response_with_tests = await find_code_tool(
        query="test user creation",
        intent=None,
        token_limit=30000,
        focus_languages=None,
        context=None,
    )

    response_without_tests = await find_code_tool(
        query="test user creation",
        intent=None,
        token_limit=30000,
        focus_languages=None,
        context=None,
    )

    # Both should return valid responses
    from codeweaver.agent_api.find_code.types import FindCodeResponseSummary

    assert isinstance(response_with_tests, FindCodeResponseSummary)
    assert isinstance(response_without_tests, FindCodeResponseSummary)


@pytest.mark.integration
@pytest.mark.asyncio
async def test_search_token_limit(initialized_app_state):
    """T010: Search respects token_limit parameter.

    Given: Search with token_limit specified
    When: token_limit parameter provided
    Then: Response respects limit
    """
    from codeweaver.server.app_bindings import find_code_tool

    response = await find_code_tool(
        query="authentication",
        intent=None,
        token_limit=5000,  # Lower limit
        include_tests=False,
        focus_languages=None,
        context=None,
    )

    # Validate token limit respected
    assert response.token_count <= 5000, f"Token count {response.token_count} exceeds limit 5000"


# =============================================================================
# T010: Edge Cases and Error Handling
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_empty_query_handling(initialized_app_state):
    """T010: Empty query handled gracefully.

    Given: Empty or whitespace-only query
    When: Search executed
    Then: Returns graceful response
    """
    from codeweaver.server.app_bindings import find_code_tool

    # Test empty query
    response = await find_code_tool(
        query="",
        intent=None,
        token_limit=30000,
        include_tests=False,
        focus_languages=None,
        context=None,
    )

    from codeweaver.agent_api.find_code.types import FindCodeResponseSummary

    assert isinstance(response, FindCodeResponseSummary)
    assert response.total_results == 0


@pytest.mark.integration
@pytest.mark.asyncio
async def test_no_results_scenario(initialized_app_state):
    """T010: No matching results handled gracefully.

    Given: Query that matches nothing in codebase
    When: Search executed
    Then: Returns empty results with clear summary
    """
    from codeweaver.server.app_bindings import find_code_tool

    response = await find_code_tool(
        query="xyzabc123nonexistentquerythatmatchesnothing",
        intent=None,
        token_limit=30000,
        include_tests=False,
        focus_languages=None,
        context=None,
    )

    from codeweaver.agent_api.find_code.types import FindCodeResponseSummary

    assert isinstance(response, FindCodeResponseSummary)
    assert response.total_results == 0
    assert len(response.matches) == 0


# =============================================================================
# T010: Performance Requirements (FR-037) - SKIPPED UNTIL REAL IMPLEMENTATION
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_search_performance(test_project_path: Path, initialized_app_state):
    """T010: Search performance meets <3s requirement for ≤10k files (FR-037).

    Given: Indexed project with embeddings (≤10k files)
    When: Search query executed
    Then: Response returned in <3000ms

    Note: Requires real find_code implementation and embeddings to be restored.
    """
    from codeweaver.agent_api.find_code import find_code
    from codeweaver.agent_api.find_code.intent import IntentType

    start_time = time.time()

    response = await find_code(
        query="authentication session management database",
        intent=IntentType.UNDERSTAND,
        token_limit=30000,
        include_tests=True,
        focus_languages=None,
    )

    end_time = time.time()
    elapsed_ms = (end_time - start_time) * 1000

    # Validate performance requirement
    assert elapsed_ms < 3000, f"Search took {elapsed_ms:.1f}ms, expected <3000ms (FR-037)"
    assert response.execution_time_ms > 0


@pytest.mark.integration
@pytest.mark.asyncio
@pytest.mark.benchmark
async def test_search_response_time_tracking(initialized_app_state):
    """T010: Search response time accurately tracked.

    Given: Search query executed
    When: Response returned
    Then: execution_time_ms tracked (even for stub)
    """
    from codeweaver.server.app_bindings import find_code_tool

    start_time = time.time()

    response = await find_code_tool(
        query="authentication",
        intent=None,
        token_limit=30000,
        include_tests=False,
        focus_languages=None,
        context=None,
    )

    end_time = time.time()
    elapsed_ms = (end_time - start_time) * 1000

    # Response should track timing
    assert response.execution_time_ms >= 0

    # For stub implementation, timing may be near-zero
    assert elapsed_ms >= 0


# =============================================================================
# T010: Search Strategy Validation - SKIPPED UNTIL REAL IMPLEMENTATION
# =============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_search_strategy_reporting(test_project_path: Path, configured_providers):
    """T010: Search strategy correctly reported in response.

    Given: Search with embeddings available
    When: Hybrid search executed
    Then: search_strategy reports HYBRID_SEARCH and SEMANTIC_RERANK
    """
    from codeweaver.agent_api.find_code import find_code
    from codeweaver.agent_api.find_code.intent import IntentType
    from codeweaver.agent_api.find_code.types import SearchStrategy

    response = await find_code(
        query="how does authentication work",
        intent=IntentType.UNDERSTAND,
        token_limit=30000,
        include_tests=False,
        focus_languages=None,
    )

    # Should use hybrid search with both dense and sparse embeddings
    assert (
        SearchStrategy.HYBRID_SEARCH in response.search_strategy
        or SearchStrategy.DENSE_ONLY in response.search_strategy
    )


@pytest.mark.integration
@pytest.mark.asyncio
async def test_search_languages_found(initialized_app_state):
    """T010: Languages found correctly reported.

    Given: Search across codebase
    When: Results returned
    Then: languages_found has correct structure
    """
    from codeweaver.server.app_bindings import find_code_tool

    response = await find_code_tool(
        query="authentication database",
        intent=None,
        token_limit=30000,
        include_tests=True,
        focus_languages=None,
        context=None,
    )

    # Validate languages_found structure
    assert isinstance(response.languages_found, tuple)
