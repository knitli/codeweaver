# CodeWeaver v0.1 UX Improvement Plan

**Status**: Ready for Implementation
**Estimated Total Effort**: 1-2 weeks
**Priority**: Critical for v0.1 launch
**Last Updated**: 2025-01-05

---

## Table of Contents

1. [Architecture Context](#architecture-context)
2. [Critical Issues Summary](#critical-issues-summary)
3. [Implementation Roadmap](#implementation-roadmap)
4. [Tier 0: Critical Blockers](#tier-0-critical-blockers)
5. [Tier 1: Essential UX](#tier-1-essential-ux)
6. [Tier 2: Important Polish](#tier-2-important-polish)
7. [Tier 3: Future Enhancements](#tier-3-future-enhancements)
8. [Exception Usage Consistency](#exception-usage-consistency)
9. [Testing Strategy](#testing-strategy)
10. [Success Metrics](#success-metrics)

---

## Architecture Context

### CodeWeaver Interaction Modes

CodeWeaver operates in three distinct modes, each requiring different UX considerations:

#### 1. CLI Tool (Human Interface)
- **Communication**: stdout/stderr
- **Context**: No MCP Context object
- **Progress**: Rich CLI progress bars, spinners
- **Errors**: Formatted console output with colors
- **Primary users**: Developers using terminal

#### 2. MCP Server (Agent Interface)
- **Communication**: MCP protocol (FastMCP handles conversion)
- **Context**: `Context` object available in tool functions
- **Progress**: FastMCP progress notifications `(progress, total, message)`
- **Errors**: Structured exceptions + logging to client
- **Transports**:
  - STDIO (local 1:1, creates new instance per client)
  - HTTP streaming (default, shared instance across clients)
- **Primary users**: AI agents (Claude, etc.)

#### 3. HTTP Endpoints (Status Interface)
- **Communication**: REST/JSON
- **Context**: None
- **Purpose**: Health checks, status queries, metrics
- **Endpoints**: `/health`, `/metrics`, etc.
- **Primary users**: Monitoring, debugging, status checks

### FastMCP Capabilities We Should Leverage

#### Structured Logging
```python
# MCP log format
{
    "msg": "Human-readable message",
    "extra": {
        "field1": value1,
        "field2": value2,
        # Rich, machine-parseable context
    }
}
```

**Usage in CodeWeaver**:
```python
log_to_client_or_fallback(
    logger,
    "Embedding query",
    level="info",
    extra={
        "query_length": len(query),
        "intent": intent,
        "provider": "voyage"
    },
    ctx=context  # Falls back to logging if None (CLI mode)
)
```

#### Progress Monitoring
```python
# FastMCP progress_handler receives:
async def progress_handler(
    progress: float,      # Current progress value
    total: float | None,  # Expected total (or None)
    message: str | None   # Status message
):
    if total:
        percentage = (progress / total) * 100
        print(f"Progress: {percentage:.1f}% - {message}")
```

**CodeWeaver should send**:
- Indexing: `(files_processed, files_discovered, "Processing file.py")`
- Embedding: `(batch_number, total_batches, "Embedding batch 5/47")`
- Search: `(step, total_steps, "Reranking results")`

#### Message Handlers

FastMCP supports notifications for:
- `on_tool_list_changed` - when tools change
- `on_resource_list_changed` - when resources change
- `on_progress` - progress updates
- `on_logging_message` - structured logs

**CodeWeaver opportunities**:
- Notify when indexing completes
- Notify when configuration changes
- Notify when providers become degraded/unavailable

#### Existing Middleware

CodeWeaver already uses:
- **ErrorHandlingMiddleware** - catches unhandled exceptions
- **RetryMiddleware** - retries transient failures
- **StructuredLoggingMiddleware** - ensures log formatting
- **RateLimitingMiddleware** - prevents API abuse
- **TimingMiddleware** (custom) - tracks operation timing for statistics

**Implications**:
- Middleware catches exceptions → our `__str__` methods must be user-friendly
- Retry middleware exists → we should mark transient vs permanent errors
- Logging middleware → we get structured logs automatically
- Timing tracked → we should expose this to users

---

## Critical Issues Summary

### 🔴 Show-Stopping Issues

1. **CLI completely broken** - syntax error in `metadata.py:90` prevents all command execution
2. **MCP tool disabled** - `find_code` marked `enabled=False`, core functionality non-functional
3. **No MCP context threading** - `log_to_client_or_fallback` exists but Context never passed
4. **Zero progress visibility** - long operations (5-180s) with no feedback in any mode
5. **Exception inconsistency** - 52% of raises use generic builtins instead of custom exceptions

### 💡 Key Insight

**Infrastructure exists but isn't connected**:
- ✅ `log_to_client_or_fallback` implemented
- ✅ `IndexingStats` tracks everything
- ✅ `HealthService` exposes status
- ✅ Chunking exceptions are exemplary
- ✅ FastMCP middleware handles errors

**What's missing**: Wiring these together and using them consistently.

---

## Implementation Roadmap

### Week 1: Critical Path (Tier 0 + Core Tier 1)

**Day 1: Unblock Everything**
- [ ] Fix `metadata.py:90` syntax error
- [ ] Re-enable MCP tool (`app_bindings.py:319`)
- [ ] Fix configuration parameter naming mismatch
- [ ] Verify basic functionality works

**Day 2-3: MCP Context Threading**
- [ ] Add `Context | None` parameter to all MCP tool functions
- [ ] Thread Context through pipeline: `find_code` → `embed_query` → `execute_vector_search` → `rerank_results`
- [ ] Add structured logging with `extra` dicts throughout
- [ ] Test MCP client receives log messages

**Day 4-5: Response Schema + State Awareness**
- [ ] Add `status`, `warnings`, `indexing_state` to `FindCodeResponseSummary`
- [ ] Implement indexing state checks before search
- [ ] Add degraded mode warnings (sparse-only, no reranking, etc.)
- [ ] Update MCP tool description with new response fields

### Week 2: Polish + Exception Consistency (Tier 1 + Tier 2)

**Day 6-7: Progress Reporting**
- [ ] Implement progress notifications for indexing
- [ ] Add CLI progress bars (Rich library)
- [ ] Add phase tracking (discovering → chunking → embedding → indexing)
- [ ] Test progress in both CLI and MCP modes

**Day 8-9: Exception Replacement**
- [ ] Create exception usage guidelines
- [ ] Replace generic exceptions in `agent_api/find_code/`
- [ ] Replace generic exceptions in `providers/`
- [ ] Replace generic exceptions in `server/app_bindings.py`
- [ ] Add pre-commit hook for exception checking

**Day 10: Configuration + Documentation**
- [ ] Create accurate `codeweaver.toml.example`
- [ ] Add `codeweaver doctor` command
- [ ] Add `codeweaver config init` wizard
- [ ] Update README with new getting started flow

---

## Tier 0: Critical Blockers

**Must Fix Before ANY Release** (4-6 hours)

### B1: Fix CLI Syntax Error ⚠️ BLOCKS ALL USAGE

**File**: `src/codeweaver/core/metadata.py:90`
**Issue**: Incomplete if statement prevents module import
**Impact**: CLI completely non-functional
**Effort**: 5 minutes

**Action**:
```python
# Find the incomplete if statement and complete the logic
# Add test to prevent similar issues
```

### B2: Re-enable MCP Tool ⚠️ CORE FEATURE DISABLED

**File**: `src/codeweaver/server/app_bindings.py:319`
**Issue**: Tool marked `enabled=False`
**Impact**: Primary user workflow non-functional
**Effort**: 5 minutes + validation testing

**Action**:
```python
app.add_tool(
    Tool.from_function(
        find_code_tool,
        name="find_code",
        description="Find code in the codebase using semantic search",
        enabled=True,  # ← Change this
    )
)
```

### B3: Fix Configuration Documentation Mismatch

**Files**: `README.md:466`, `src/codeweaver/cli/commands/search.py:44`
**Issue**: README shows `--format`, code uses `--output-format`
**Impact**: Copy-paste examples fail immediately
**Effort**: 15 minutes

**Action**:
```python
# Standardize on --format (shorter, clearer)
# Update README and code to match
# Update help text
```

---

## Tier 1: Essential UX

**Must Have for v0.1** (2-3 days)

### E1: Thread MCP Context Through Pipeline ⚠️ ENABLES ALL FEEDBACK

**Why Critical**: Unlocks `log_to_client_or_fallback` and progress notifications
**Effort**: 3-4 hours

**Files to Modify**:

#### 1. `src/codeweaver/agent_api/find_code/__init__.py:90`

```python
async def find_code(
    query: str,
    *,
    intent: IntentType | None = None,
    token_limit: int = 10000,
    include_tests: bool = False,
    focus_languages: tuple[str, ...] | None = None,
    max_results: int = 50,
    context: Context | None = None,  # ← ADD THIS
) -> FindCodeResponseSummary:
    """Find code matching the query with semantic search.

    Args:
        context: FastMCP context for client communication (MCP mode only)
    """
    # Send initial status to client
    if context:
        log_to_client_or_fallback(
            logger,
            "Starting code search",
            level="info",
            extra={
                "query": query[:100],
                "intent": intent.value if intent else None,
                "max_results": max_results,
            },
            ctx=context,
        )

    # ... rest of implementation
```

#### 2. `src/codeweaver/server/app_bindings.py:101-108`

```python
async def find_code_tool(
    query: str,
    # ... other params
    context: Context | None = None,  # ← Already present, just pass it through
) -> FindCodeResponseSummary:
    """MCP tool wrapper for find_code."""

    response = await find_code(
        query=query,
        intent=intent,
        token_limit=token_limit,
        include_tests=include_tests,
        focus_languages=focus_langs,
        max_results=50,
        context=context,  # ← PASS THIS
    )
    return response
```

#### 3. `src/codeweaver/agent_api/find_code/pipeline.py`

Add Context parameter and structured logging to:

```python
async def embed_query(
    query: str,
    context: Context | None = None,  # ← ADD
) -> QueryResult:
    """Embed query using configured providers."""
    if context:
        log_to_client_or_fallback(
            logger,
            "Generating query embeddings",
            level="info",
            extra={"query_length": len(query)},
            ctx=context,
        )

    # ... existing logic

    if dense_failed:
        if context:
            log_to_client_or_fallback(
                logger,
                "Dense embeddings unavailable - using sparse-only (reduced accuracy)",
                level="warning",
                extra={"provider": dense_provider_enum},
                ctx=context,
            )

async def execute_vector_search(
    query_vector: StrategizedQuery,
    context: Context | None = None,  # ← ADD
) -> list[SearchResult]:
    """Execute vector search."""
    if context:
        log_to_client_or_fallback(
            logger,
            "Searching vector store",
            level="info",
            extra={
                "search_mode": "hybrid" if query_vector.is_hybrid() else "single",
            },
            ctx=context,
        )
    # ... existing logic

async def rerank_results(
    query: str,
    candidates: list[SearchResult],
    context: Context | None = None,  # ← ADD
) -> list[SearchResult]:
    """Rerank results."""
    if context:
        log_to_client_or_fallback(
            logger,
            f"Reranking {len(candidates)} results",
            level="info",
            extra={"candidate_count": len(candidates)},
            ctx=context,
        )
    # ... existing logic
```

**Testing**:
```python
# Test with MCP client
async with client:
    # Should see log messages in client
    result = await client.call_tool("find_code", {"query": "test"})

# Test with CLI (no context)
codeweaver search "test"  # Should log normally to file/stdout
```

---

### E2: Add Status/Warnings to MCP Response ⚠️ AGENT DECISION-MAKING

**Why Critical**: Agents need to distinguish success/partial/error states
**Effort**: 2-3 hours

**File**: `src/codeweaver/agent_api/find_code/types.py:132`

```python
class FindCodeResponseSummary(BasedModel):
    """Response from find_code with enhanced operational context."""

    # Core results (existing)
    matches: Annotated[
        list[CodeMatch],
        Field(description="Code matches found"),
    ]
    summary: Annotated[
        str,
        Field(description="Human-readable summary of results"),
    ]

    # NEW: Operational status
    status: Annotated[
        Literal["success", "partial", "error"],
        Field(
            default="success",
            description="Query execution status: success=complete, partial=degraded mode, error=failed"
        ),
    ]

    warnings: Annotated[
        list[str],
        Field(
            default_factory=list,
            description="Non-fatal issues encountered (e.g., 'Reranking unavailable')"
        ),
    ]

    indexing_state: Annotated[
        Literal["complete", "in_progress", "not_started", "unknown"] | None,
        Field(
            default=None,
            description="Current indexing state when query was executed"
        ),
    ]

    index_coverage: Annotated[
        float | None,
        Field(
            default=None,
            ge=0.0,
            le=1.0,
            description="Fraction of codebase indexed (0.0-1.0)"
        ),
    ]

    search_mode: Annotated[
        Literal["hybrid", "dense_only", "sparse_only", "keyword"] | None,
        Field(
            default=None,
            description="Search mode used (indicates quality level)"
        ),
    ]

    # Existing fields
    search_strategy: tuple[SearchStrategy, ...]
    total_matches: int
    total_results: int
    # ... rest unchanged
```

**Update Response Builders**:

```python
# src/codeweaver/agent_api/find_code/response.py

def build_success_response(
    # ... existing params
    warnings: list[str] | None = None,
    indexing_state: str | None = None,
    index_coverage: float | None = None,
    search_mode: str | None = None,
) -> FindCodeResponseSummary:
    """Build successful response with operational context."""
    return FindCodeResponseSummary(
        status="partial" if warnings else "success",
        warnings=warnings or [],
        indexing_state=indexing_state,
        index_coverage=index_coverage,
        search_mode=search_mode,
        # ... existing fields
    )

def build_error_response(
    error: Exception,
    # ... existing params
) -> FindCodeResponseSummary:
    """Build error response with structured details."""
    return FindCodeResponseSummary(
        status="error",
        matches=[],
        summary=f"Search failed: {error}",
        warnings=[],
        error_details={  # NEW field
            "error_type": type(error).__name__,
            "message": str(error),
            "suggestions": getattr(error, 'suggestions', []),
        },
        # ... existing fields
    )
```

---

### E3: Check Indexing State Before Search ⚠️ PREVENTS MISLEADING RESULTS

**Why Critical**: Users need to know if results are complete or partial
**Effort**: 2-3 hours

**File**: `src/codeweaver/agent_api/find_code/__init__.py:133`

```python
async def find_code(
    query: str,
    # ... params
    context: Context | None = None,
) -> FindCodeResponseSummary:
    """Find code with indexing state awareness."""

    # Step 1: Detect query intent (existing)
    intent = intent or await detect_intent(query)

    # Step 2: Check indexing state (NEW)
    indexing_state = "unknown"
    index_coverage = None
    warnings = []

    try:
        from codeweaver.server.server import get_state

        state = get_state()
        if state.health_service:
            health_response = state.health_service.get_health_response()
            indexing_state = health_response.indexing.state

            if indexing_state == "indexing":
                progress = health_response.indexing.progress
                if progress.files_discovered > 0:
                    index_coverage = progress.files_processed / progress.files_discovered
                else:
                    index_coverage = 0.0

                warning_msg = (
                    f"Index building in progress ({index_coverage:.0%} complete) - "
                    "results may be incomplete"
                )
                warnings.append(warning_msg)

                if context:
                    log_to_client_or_fallback(
                        logger,
                        warning_msg,
                        level="warning",
                        extra={
                            "indexing_state": indexing_state,
                            "coverage": index_coverage,
                            "files_processed": progress.files_processed,
                            "files_total": progress.files_discovered,
                        },
                        ctx=context,
                    )
            elif indexing_state == "not_started":
                warnings.append("Index not yet built - search will return no results")

    except Exception as e:
        logger.warning("Failed to check indexing state: %s", e)
        indexing_state = "unknown"

    # Step 3: Embed query (pass context and collect warnings)
    # ... existing logic

    # Step 4: Execute search with accumulated warnings
    return build_success_response(
        # ... existing params
        warnings=warnings,
        indexing_state=indexing_state,
        index_coverage=index_coverage,
        search_mode=determine_search_mode(embeddings),
    )
```

---

### E4: Improve Error Message Specificity ⚠️ USER RECOVERY

**Why Critical**: Users need actionable guidance to fix errors
**Effort**: 4-6 hours

**Pattern to Apply Throughout**:

```python
# BEFORE (generic)
raise ValueError("No embedding providers configured")

# AFTER (specific with context and suggestions)
raise ConfigurationError(
    "No embedding providers configured",
    details={
        "config_file": str(settings.config_path),
        "required_providers": ["dense_embedding", "sparse_embedding"],
        "configured_providers": [],
    },
    suggestions=[
        "Set VOYAGE_API_KEY environment variable for cloud embeddings",
        "Or configure local provider: [[provider.embedding]] provider = 'fastembed'",
        "See configuration guide: https://docs.codeweaver.ai/config/providers",
    ]
)
```

**Files to Update** (15-20 instances):

1. `src/codeweaver/agent_api/find_code/pipeline.py` (3 instances)
2. `src/codeweaver/providers/embedding/providers/*.py` (5+ instances)
3. `src/codeweaver/providers/reranking/providers/*.py` (5+ instances)
4. `src/codeweaver/server/app_bindings.py` (2 instances)
5. `src/codeweaver/config/settings.py` (3+ instances)

**Implementation Checklist per Instance**:
- [ ] Identify appropriate custom exception type
- [ ] Gather contextual details (file paths, values, etc.)
- [ ] Write 2-3 actionable suggestions
- [ ] Include documentation link if relevant
- [ ] Test error message clarity

---

### E5: Add Progress Indicators ⚠️ ELIMINATE ANXIETY

**Why Critical**: Users need feedback during long operations
**Effort**: 4-5 hours

#### For MCP Mode: Progress Notifications

**File**: `src/codeweaver/engine/indexer.py`

```python
from mcp.server.fastmcp import Context

class Indexer(BaseModel):
    """Indexer with progress notification support."""

    _progress_context: Context | None = PrivateAttr(default=None)

    def set_progress_context(self, context: Context | None) -> None:
        """Set MCP context for progress notifications."""
        self._progress_context = context

    async def _notify_progress(
        self,
        phase: str,
        current: int,
        total: int,
        message: str | None = None,
    ) -> None:
        """Send progress notification to MCP client."""
        if self._progress_context:
            # FastMCP handles progress notifications automatically
            # Just use log_to_client_or_fallback with structured data
            log_to_client_or_fallback(
                logger,
                message or f"{phase}: {current}/{total}",
                level="info",
                extra={
                    "phase": phase,
                    "progress": current,
                    "total": total,
                    "percentage": (current / total * 100) if total > 0 else 0,
                },
                ctx=self._progress_context,
            )

    async def _index_file(self, path: Path) -> None:
        """Index single file with progress notification."""
        self._current_file = path

        await self._notify_progress(
            phase="indexing",
            current=self._stats.files_processed,
            total=self._stats.files_discovered,
            message=f"Processing {path.name}",
        )

        # ... existing logic
```

#### For CLI Mode: Rich Progress Bars

**File**: `src/codeweaver/cli/commands/search.py`

```python
from rich.progress import Progress, SpinnerColumn, TextColumn, BarColumn

@click.command()
async def search(query: str, ...):
    """Search codebase with progress indicator."""

    with Progress(
        SpinnerColumn(),
        TextColumn("[blue]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
    ) as progress:
        task = progress.add_task("Searching codebase...", total=None)

        try:
            response = await find_code_tool(
                query=query,
                # ... params
            )
            progress.update(task, completed=True, description="[green]Search complete")
        except Exception as e:
            progress.update(task, description=f"[red]Search failed: {e}")
            raise
```

**File**: `src/codeweaver/cli/commands/server.py`

```python
@click.command()
def server(...):
    """Start server with indexing progress."""

    console.print(f"{CODEWEAVER_PREFIX} Starting MCP server...")

    # Show initial indexing progress
    console.print("\n[blue]Indexing codebase...[/blue]")

    with Progress(
        SpinnerColumn(),
        TextColumn("[blue]{task.description}"),
        BarColumn(),
        TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
    ) as progress:
        # Poll health endpoint for progress
        task = progress.add_task("Discovering files...", total=100)

        # ... server startup logic

        # Update progress by polling health endpoint
        while indexing_in_progress():
            health = get_health()
            if health.indexing.progress.files_discovered > 0:
                pct = (
                    health.indexing.progress.files_processed /
                    health.indexing.progress.files_discovered * 100
                )
                progress.update(
                    task,
                    completed=pct,
                    description=f"Indexing: {health.indexing.progress.current_file or ''}",
                )
            time.sleep(1)
```

---

### E6: Add CLI Status Command ⚠️ VISIBILITY INTO SYSTEM

**Why Critical**: Users need to check progress without server logs
**Effort**: 2-3 hours

**New File**: `src/codeweaver/cli/commands/status.py`

```python
import click
import httpx
from rich.console import Console
from rich.table import Table
from rich.progress import Progress, BarColumn, TextColumn

console = Console()

@click.command()
@click.option(
    "--watch",
    is_flag=True,
    help="Continuously update status (Ctrl+C to stop)",
)
@click.option(
    "--port",
    default=9328,
    help="Server port (default: 9328)",
)
def status(watch: bool, port: int) -> None:
    """Check CodeWeaver server status and indexing progress.

    Examples:
        codeweaver status
        codeweaver status --watch
        codeweaver status --port 9329
    """

    def fetch_status() -> dict:
        """Fetch status from health endpoint."""
        try:
            response = httpx.get(f"http://localhost:{port}/health", timeout=5.0)
            response.raise_for_status()
            return response.json()
        except httpx.ConnectError:
            console.print(f"[red]✗[/red] Server not running on port {port}")
            console.print(f"\nStart server with: [cyan]codeweaver server[/cyan]")
            raise SystemExit(1)
        except Exception as e:
            console.print(f"[red]Error fetching status:[/red] {e}")
            raise SystemExit(1)

    def display_status(health: dict) -> None:
        """Display formatted status information."""
        console.clear()
        console.print(f"\n[bold]CodeWeaver Status[/bold] (Port {port})\n")

        # Server status
        console.print(f"[green]✓[/green] Server running")

        # Indexing status
        indexing = health.get("indexing", {})
        state = indexing.get("state", "unknown")
        progress_info = indexing.get("progress", {})

        if state == "idle":
            console.print(f"[green]✓[/green] Indexing complete")
            console.print(f"  Files indexed: {progress_info.get('files_discovered', 0)}")
            console.print(f"  Chunks created: {progress_info.get('chunks_created', 0)}")
        elif state == "indexing":
            files_processed = progress_info.get("files_processed", 0)
            files_total = progress_info.get("files_discovered", 0)

            console.print(f"[blue]→[/blue] Indexing in progress")

            if files_total > 0:
                pct = (files_processed / files_total) * 100
                console.print(f"  Progress: {files_processed}/{files_total} files ({pct:.1f}%)")

                # Progress bar
                with Progress(
                    TextColumn("[blue]{task.description}"),
                    BarColumn(),
                    TextColumn("[progress.percentage]{task.percentage:>3.0f}%"),
                ) as p:
                    task = p.add_task("", total=files_total, completed=files_processed)
                    # Just display, don't update

            current_file = progress_info.get("current_file")
            if current_file:
                console.print(f"  Current: {current_file}")
        else:
            console.print(f"[yellow]?[/yellow] Indexing state: {state}")

        # Service health
        services = health.get("services", {})
        if services:
            console.print("\n[bold]Services:[/bold]")
            for service, status in services.items():
                icon = "✓" if status == "healthy" else "✗"
                color = "green" if status == "healthy" else "red"
                console.print(f"  [{color}]{icon}[/{color}] {service}: {status}")

    # Single status check
    if not watch:
        health = fetch_status()
        display_status(health)
        return

    # Watch mode - continuous updates
    console.print("[dim]Press Ctrl+C to stop...[/dim]\n")
    try:
        while True:
            health = fetch_status()
            display_status(health)
            time.sleep(2)
    except KeyboardInterrupt:
        console.print("\n[dim]Stopped monitoring[/dim]")
```

**Register Command**:

```python
# src/codeweaver/cli/__main__.py

from codeweaver.cli.commands import status

app.command(status, name="status")
```

---

### E7: Create Accurate Configuration Template

**Why Critical**: First-run success depends on clear configuration
**Effort**: 2-3 hours

**New File**: `codeweaver.toml.example` (repository root)

```toml
# CodeWeaver Configuration Example
# Copy this file to codeweaver.toml and customize for your project
#
# Documentation: https://docs.codeweaver.ai/configuration

# ============================================================================
# PROJECT SETTINGS (Required)
# ============================================================================

[codeweaver]

# REQUIRED: Absolute path to the codebase you want to index
# Do not use ~ or $HOME - provide full absolute path
project_path = "/absolute/path/to/your/codebase"

# Project identifier (default: directory name of project_path)
# Used for collection names and logging
project_name = "my-project"

# Maximum tokens per code chunk (default: 800, range: 200-4000)
# Larger chunks = more context but slower search
# Smaller chunks = faster but may miss context
token_limit = 800

# Maximum file size to process in bytes (default: 1MB)
# Files larger than this are skipped during indexing
max_file_size = 1048576

# Maximum search results to return (default: 75)
# Higher values = more comprehensive but slower
max_results = 75

# Enable anonymous usage telemetry (default: true)
# Helps improve CodeWeaver by sharing usage patterns
enable_telemetry = true

# ============================================================================
# EMBEDDING PROVIDERS
# ============================================================================

# Dense embeddings for semantic search (RECOMMENDED)
# Choose ONE of the following providers:

# --- Option 1: VoyageAI (Cloud, Best Quality) ---
# Requires: export VOYAGE_API_KEY="your-key"
# Get key: https://www.voyageai.com/api-keys
# Pricing: ~$0.10 per million tokens
[[provider.embedding]]
provider = "voyage"
enabled = true
model_settings = { model = "voyage-code-3" }

# --- Option 2: OpenAI (Cloud, Good Quality) ---
# Requires: export OPENAI_API_KEY="your-key"
# [[provider.embedding]]
# provider = "openai"
# enabled = true
# model_settings = { model = "text-embedding-3-large" }

# --- Option 3: FastEmbed (Local, No API Key, Reduced Quality) ---
# Runs locally, no API costs, completely private
# First run downloads ~500MB model
# [[provider.embedding]]
# provider = "fastembed"
# enabled = true
# model_settings = { model = "BAAI/bge-small-en-v1.5" }

# ============================================================================
# SPARSE EMBEDDINGS (Optional but Recommended)
# ============================================================================

# Sparse embeddings improve keyword matching
# Recommended to combine with dense embeddings for hybrid search

[[provider.sparse_embedding]]
provider = "fastembed"  # Runs locally, no API key needed
enabled = true
model_settings = { model = "prithivida/Splade_PP_en_v2" }

# ============================================================================
# RERANKING (Optional, Improves Result Quality)
# ============================================================================

# Reranking re-orders results for better relevance
# Choose ONE of the following providers:

# --- Option 1: VoyageAI (Cloud, Best Quality) ---
# Requires: VOYAGE_API_KEY (same as embedding provider)
[[provider.reranking]]
provider = "voyage"
enabled = true
model_settings = { model = "rerank-2" }

# --- Option 2: Cohere (Cloud, Good Quality) ---
# Requires: export COHERE_API_KEY="your-key"
# [[provider.reranking]]
# provider = "cohere"
# enabled = true
# model_settings = { model = "rerank-english-v3.0" }

# --- Option 3: Local Reranking (No API Key) ---
# [[provider.reranking]]
# provider = "sentence-transformers"
# enabled = true
# model_settings = { model = "cross-encoder/ms-marco-MiniLM-L-6-v2" }

# ============================================================================
# VECTOR STORE
# ============================================================================

# --- Option 1: Local Qdrant (Recommended for Getting Started) ---
[[provider.vector_store]]
provider = "qdrant"
enabled = true
provider_settings = {
    location = "local",
    path = ".codeweaver/qdrant",  # Storage location (relative to project_path)
    collection_name = "my-project"
}

# --- Option 2: Remote Qdrant (For Production/Sharing) ---
# Requires Qdrant Cloud account: https://cloud.qdrant.io
# [[provider.vector_store]]
# provider = "qdrant"
# enabled = true
# provider_settings = {
#     url = "https://your-cluster.cloud.qdrant.io",
#     api_key = "${QDRANT_API_KEY}",  # Use env var for security
#     collection_name = "my-project",
#     prefer_grpc = true
# }

# ============================================================================
# ADVANCED SETTINGS
# ============================================================================

# Chunking strategy (default: semantic)
# Options: semantic, delimiter, hybrid
# chunking_strategy = "semantic"

# File discovery patterns (gitignore-style)
# include_patterns = ["**/*.py", "**/*.js", "**/*.ts"]
# exclude_patterns = ["**/node_modules/**", "**/.venv/**"]

# Performance tuning
# max_concurrent_files = 10  # Parallel file processing
# embedding_batch_size = 32  # Batch size for embeddings
# indexing_timeout = 30      # Timeout per file in seconds

# Logging level (default: INFO)
# Options: DEBUG, INFO, WARNING, ERROR
# log_level = "INFO"
```

---

## Tier 2: Important Polish

**Should Have for v0.1** (2-3 days)

### P1: Add `codeweaver doctor` Command

**Effort**: 3-4 hours

Validates prerequisites and configuration before use.

### P2: Add `codeweaver config init` Wizard

**Effort**: 4-5 hours

Interactive configuration setup for new users.

### P3: Add Phase Tracking to Indexing

**Effort**: 3-4 hours

Distinguish discovering → chunking → embedding → indexing phases.

### P4: Add Periodic Progress Logging

**Effort**: 2 hours

Regular updates during indexing (every 50 files or 30 seconds).

### P5: Surface Degraded Mode in Responses

**Effort**: 2-3 hours

Warn when reranking unavailable, sparse-only search, etc.

### P6: Document Local-Only Setup

**Effort**: 2 hours

Guide for running without API keys using local providers.

---

## Tier 3: Future Enhancements

**Post-v0.1** (1-2 weeks)

- Interactive REPL search mode
- Configuration edit command (`codeweaver config set`)
- Shell completion scripts
- Telemetry opt-out prompt on first run
- Search result actions (`--open` in editor)
- Multi-codebase MCP configuration
- Advanced validation with suggestions

---

## Exception Usage Consistency

### Current State

- **Total raises**: 227
- **Builtin exceptions**: 118 (52%)
- **Custom exceptions**: 76 (33.5%)
- **Chunking exceptions**: Exemplary (7 specific types with rich context)
- **Everything else**: Mostly generic ValueError/RuntimeError

### Target Pattern (From Chunking)

```python
class OversizedChunkError(ChunkingError):
    """Specific error with comprehensive context."""

    def __init__(
        self,
        message: str,
        *,
        actual_tokens: int | None = None,
        max_tokens: int | None = None,
        chunk_content: str | None = None,
        details: dict[str, Any] | None = None,
        suggestions: list[str] | None = None,
    ):
        error_details = details or {}
        # Populate details with metrics
        if actual_tokens:
            error_details["actual_tokens"] = actual_tokens
        # ... more details

        default_suggestions = suggestions or [
            "Actionable step 1",
            "Alternative approach",
            "Documentation link",
        ]

        super().__init__(message, details=error_details, suggestions=default_suggestions)
```

### Exception Mapping Guide

| Generic Exception | Custom Exception | Use Case |
|-------------------|------------------|----------|
| `ValueError("No providers")` | `ConfigurationError` | Missing/invalid configuration |
| `RuntimeError("Provider failed")` | `ProviderError` | External service failures |
| `ValueError("Invalid query")` | `QueryError` | Search query validation |
| `RuntimeError("Index failed")` | `IndexingError` | File processing failures |
| `TypeError("Wrong type")` | `ValidationError` | Type/schema validation |
| `ImportError("Missing dep")` | `ConfigurationError` | Optional dependency missing |

### Implementation Plan

**Phase 1: High-Impact Modules** (Day 8-9 of Week 2)
1. `agent_api/find_code/` - Core search path
2. `server/app_bindings.py` - MCP tool entry
3. `providers/*/providers/` - All provider implementations

**Phase 2: Supporting Modules** (If time permits)
4. `config/settings.py` - Configuration validation
5. `engine/indexer.py` - Indexing operations
6. `semantic/` - AST operations

**Deliverables**:
- Exception usage guidelines document
- Pre-commit hook for exception checking
- ~50 exception replacements with proper context

---

## Testing Strategy

### Critical User Journeys

#### Journey 1: First-Time Setup
```
install → doctor → config init → server start → first search
```
**Success**: <10 minutes, >90% success rate

#### Journey 2: Daily Usage (CLI)
```
codeweaver search "query" → view results → refine
```
**Success**: <30 seconds per search, clear feedback

#### Journey 3: MCP Integration
```
Add to claude_desktop_config.json → restart → verify → query
```
**Success**: <5 minutes, clear error messages if issues

#### Journey 4: Error Recovery
```
Configuration error → doctor → fix → retry
```
**Success**: >80% self-recovery without docs

### Automated Tests

**Unit Tests**:
- [ ] Context threading through all layers
- [ ] Status field population in responses
- [ ] Indexing state detection logic
- [ ] Exception context and suggestions
- [ ] Progress notification formatting

**Integration Tests**:
- [ ] MCP tool invocation with logging
- [ ] CLI commands with progress bars
- [ ] Health endpoint response structure
- [ ] Configuration validation with suggestions

**E2E Tests**:
- [ ] Full indexing with progress tracking
- [ ] Search with various intents
- [ ] Error scenarios (missing API key, invalid config)
- [ ] Degraded mode operation (sparse-only, no reranking)

---

## Success Metrics

### v0.1 Launch Targets

**Time Metrics**:
- Time to first successful search: **<10 minutes** (currently 30-40 min)
- Search response time perception: **"fast"** (with progress indicators)
- Error recovery time: **<2 minutes** (with actionable messages)

**Quality Metrics**:
- Configuration success rate: **>90%** (currently ~40%)
- Self-service error recovery: **>80%** (currently ~20%)
- Documentation accuracy: **100%** (examples must work)
- MCP client log visibility: **100%** (all operations logged)

**User Satisfaction** (Survey after 2 weeks):
- "I know what the system is doing": **>85%**
- "Errors are clear and actionable": **>80%**
- "Getting started was smooth": **>75%**
- "MCP integration was straightforward": **>80%**

---

## Appendix: Quick Reference

### FastMCP Integration Checklist

When adding user-facing functionality:

- [ ] Add `Context | None` parameter to function
- [ ] Use `log_to_client_or_fallback` with structured `extra` dict
- [ ] Send progress notifications for long operations
- [ ] Include warnings in response for degraded mode
- [ ] Test in both MCP and CLI modes
- [ ] Ensure errors have good `__str__` representation

### Exception Checklist

Before raising any exception:

- [ ] Is this the most specific exception type?
- [ ] Does it include structured `details` dict?
- [ ] Does it have at least 2 actionable `suggestions`?
- [ ] Is the message user-facing (not developer jargon)?
- [ ] Would this help someone troubleshoot at 2am?

### Progress Reporting Checklist

For operations >5 seconds:

- [ ] **CLI**: Show Rich progress bar with spinner
- [ ] **MCP**: Send progress logs with `extra` dict
- [ ] **HTTP**: Update health endpoint status
- [ ] Include current item being processed
- [ ] Show percentage complete if known
- [ ] Provide ETA if calculable

---

## Implementation Notes

### Key Principles

1. **Context is King**: Thread Context through all MCP tool paths
2. **Structured Everything**: Use `extra` dicts for machine-parseable context
3. **Progress is Mandatory**: No operation >5s without feedback
4. **Errors are Opportunities**: Every error is a chance to help the user
5. **Test Both Modes**: CLI and MCP have different UX needs

### Common Pitfalls to Avoid

1. **Don't**: Use generic exceptions without context
2. **Don't**: Log important info without using `log_to_client_or_fallback`
3. **Don't**: Assume Context is always available (CLI mode has None)
4. **Don't**: Forget to test error paths
5. **Don't**: Skip suggestions in exceptions

### Resources

- **FastMCP Docs**: https://gofastmcp.com
- **CodeWeaver Constitution**: `.specify/memory/constitution.md`
- **Chunking Exceptions**: `src/codeweaver/engine/chunker/exceptions.py` (gold standard)
- **Health Service**: `src/codeweaver/server/health_service.py`

---

**Last Updated**: 2025-01-05
**Next Review**: After Tier 0 completion
