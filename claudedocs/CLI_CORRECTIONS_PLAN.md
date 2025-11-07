<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# CLI Commands Corrections Plan - Evidence-Based Analysis

**Status**: Ready for Implementation
**Priority**: CRITICAL - Blocks v0.1 correctness and UX
**Estimated Effort**: 3-5 days
**Last Updated**: 2025-01-06

---

## Table of Contents

1. [Executive Summary](#executive-summary)
2. [Investigation Findings](#investigation-findings)
3. [Correction Roadmap](#correction-roadmap)
4. [Detailed Corrections by File](#detailed-corrections-by-file)
5. [Testing Strategy](#testing-strategy)
6. [Success Criteria](#success-criteria)

---

## Executive Summary

Investigation of CLI commands revealed **68 distinct correctness issues** across 5 command files that violate the Project Constitution and existing codebase patterns. These issues fall into 8 categories:

| Category | Issues | Severity | Files Affected |
|----------|--------|----------|----------------|
| Registry Usage | 15 | HIGH | config.py, list.py |
| Provider Enum Usage | 12 | HIGH | config.py, doctor.py, list.py |
| Settings Construction | 8 | CRITICAL | config.py, doctor.py |
| Unset Sentinel Handling | 9 | CRITICAL | doctor.py |
| Helper Utilities | 7 | MEDIUM | config.py, doctor.py |
| Architecture Compliance | 6 | HIGH | init.py, index.py |
| Missing Features | 8 | MEDIUM | config.py, doctor.py, list.py |
| Code Quality | 3 | LOW | config.py, list.py |

**Key Constitutional Violations**:
- ❌ Evidence-Based Development: Hardcoded values contradict actual registry data
- ❌ Proven Patterns: Reimplements existing utilities and infrastructure
- ❌ Simplicity: Duplicate logic and unnecessary complexity

**Impact on Users**:
- **Config Init**: Wrong env vars, missing 75% of providers, no quick setup
- **Doctor**: False positives/negatives due to Unset mishandling, hardcoded paths
- **Init**: Architectural mismatch with CodeWeaver's HTTP streaming design
- **List**: Shows only 25% of actual capabilities, missing sparse embeddings
- **Index**: Doesn't integrate with server lifecycle as users expect

---

## Investigation Findings

### File: config.py (9 major issues)

**Lines of Code**: 379 lines
**Lines Requiring Changes**: ~180 (47%)
**Severity**: HIGH to CRITICAL

#### Issue Summary

1. **Hardcoded Provider Lists** (Lines 162-184) - HIGH
   - Only shows 4 providers, missing 20+
   - Doesn't use provider registry or capabilities map
   - Impact: Outdated as new providers added

2. **Missing Provider.other_env_vars** (Lines 200-365) - HIGH
   - Hardcoded env var name patterns
   - Misses provider-specific setup (TLS certs, endpoints, httpx proxy)
   - Impact: Wrong env var names told to users

3. **Incorrect Settings Construction** (Lines 302-342) - CRITICAL
   - Builds dict manually, bypasses pydantic-settings hierarchy
   - Ignores env vars, dotenv, secrets managers
   - Impact: Loses entire settings precedence chain

4. **Static Config Paths** (Lines 138-297) - MEDIUM
   - Only supports `.codeweaver.toml` in project root
   - Doesn't use settings_customise_sources locations
   - Impact: Can't create local/user configs

5. **Missing CODEWEAVER_PREFIX** (Line 117) - LOW
   - String literal `{CODEWEAVER_PREFIX}` not interpolated
   - Impact: Inconsistent branding

6. **No Helper Usage** (Lines 123-213) - MEDIUM
   - Reimplements path validation, git checks
   - Doesn't use CLI utils for terminal detection
   - Impact: Duplicate logic, no adaptive UX

7. **No Config Profiles** (Lines 102-379) - HIGH
   - Forces step-by-step interactive wizard
   - No quick defaults option
   - Impact: Time-consuming setup, decision fatigue

8. **Missing Features** (Lines 215-289) - MEDIUM
   - No secrets manager documentation
   - No Qdrant Cloud recommendations
   - No sparse embedding limitations
   - Impact: Incomplete guidance

9. **JSON Usage** - LOW
   - Uses stdlib json patterns instead of pydantic_core
   - Impact: Future compatibility

### File: doctor.py (8 major issues)

**Lines of Code**: 346 lines
**Lines Requiring Changes**: ~150 (43%)
**Severity**: CRITICAL

#### Issue Summary

1. **Hardcoded Path Assumptions** (Lines 130-139) - HIGH
   - Assumes `settings.config_file` indicates configuration
   - Reality: Config can come from 7+ sources
   - Impact: False warnings when config via env vars

2. **Config Requirement Assumption** (Lines 120-156) - HIGH
   - Treats missing config file as warning
   - Reality: Config files are completely optional
   - Impact: Confuses users with valid env-only setup

3. **Unset Sentinel Mishandling** (Multiple) - CRITICAL
   - Line 164-169: Checks `isinstance(x, Path)` instead of `isinstance(x, Unset)`
   - Lines 206-207: Uses `hasattr()` instead of Unset check
   - Lines 249-285: Uses `hasattr()` for nested settings
   - Impact: Runtime type errors, false positives/negatives

4. **Wrong Import** (Line 210) - CRITICAL
   - Imports `get_user_config_dir` from wrong module
   - Reality: Function is in `utils.utils`, not `utils.git`
   - Impact: Import error

5. **Qdrant Assumptions** (Lines 270-276) - HIGH
   - Doesn't account for Docker (most common)
   - Doesn't account for Qdrant Cloud (recommended)
   - Uses hardcoded `QDRANT_API_KEY` check
   - Impact: False warnings for valid setups

6. **Hardcoded Env Vars** (Lines 254-293) - HIGH
   - Manual `api_key_map` dictionary
   - Should use `Provider.other_env_vars`
   - Impact: Wrong env var names, missing providers

7. **Wrong Dependency Checks** (Lines 86-117) - MEDIUM
   - Uses `importlib.metadata.version()` not `find_spec()`
   - Hardcoded package list
   - Doesn't account for optional dependencies
   - Impact: False positives, wrong suggestions

8. **Unimplemented Connection Tests** (Lines 332-346) - LOW
   - Function does nothing even with `--test-connections`
   - Impact: Missing feature

### File: init.py (3 major issues)

**Lines of Code**: 137 lines
**Lines Requiring Changes**: Full redesign needed
**Severity**: HIGH (Architectural)

#### Issue Summary

1. **Command Confusion** - HIGH
   - Both `config init` and `init` exist
   - Unclear which to use when
   - Impact: User confusion

2. **Hardcoded MCP Config** (Lines 124-137) - HIGH
   - Manually constructs JSON
   - Duplicates fastmcp's logic
   - Impact: Fragile, hard to maintain

3. **Architecture Mismatch** (Fundamental) - CRITICAL
   - CodeWeaver uses HTTP streaming (shared instance)
   - `fastmcp install` assumes STDIO (per-client instances)
   - Background indexing requires persistent server
   - Impact: `fastmcp install` is incompatible

#### Architectural Analysis

**CodeWeaver's Design** (Evidence from settings.py:156-161):
```python
transport: ... = "http"  # Default is HTTP, not STDIO
```

**Why HTTP Streaming**:
- Single server instance shared across all clients
- Background indexing persists between client sessions
- Concurrent request handling
- Independent lifecycle from client connections

**Why STDIO Won't Work**:
- Each client connection spawns new process
- Background indexing dies with client disconnect
- No shared state across clients
- Defeats CodeWeaver's architecture

**Recommendation**: Keep custom MCP setup, unify commands, document architecture difference

### File: list.py (4 major issues)

**Lines of Code**: 327 lines
**Lines Requiring Changes**: ~200 (61%)
**Severity**: HIGH

#### Issue Summary

1. **Hardcoded Local Providers** (Lines 36-89) - HIGH
   - Manual sets of local vs cloud providers
   - Should derive from CLIENT_MAP
   - Missing 15+ OpenAI-compatible providers
   - Impact: Incomplete, inaccurate

2. **Missing Sparse Embeddings** (Lines 107-198) - HIGH
   - No `ProviderKind.SPARSE_EMBEDDING` check
   - CodeWeaver's key hybrid search feature invisible
   - Impact: Users can't discover sparse models

3. **Hardcoded Module Paths** (Lines 275-327) - HIGH
   - Manual capability function mappings
   - Only 8 embedding, 5 reranking providers
   - Should use ModelRegistry
   - Impact: Shows 25% of actual capabilities

4. **No Registry Integration** (Lines 107-149) - HIGH
   - Uses static PROVIDER_CAPABILITIES
   - Doesn't check actual availability
   - Should use ProviderRegistry
   - Impact: Shows unavailable providers

#### Coverage Analysis

**Current**:
- Embedding providers: 8 shown
- Reranking providers: 5 shown
- Sparse providers: 0 shown
- Total unique providers: ~8

**After Fixes**:
- Embedding providers: 25+
- Reranking providers: 10+
- Sparse providers: 2
- Total unique providers: 35+

### File: index.py (1 major issue)

**Lines of Code**: 56 lines
**Lines Requiring Changes**: ~30 (54%) + server.py integration
**Severity**: MEDIUM (UX)

#### Issue Summary

1. **No Server Integration** - MEDIUM
   - Runs standalone, doesn't check/start server
   - User expectation: "codeweaver running = server running"
   - Architecture doc promises background indexing
   - Impact: Confusing UX, manual process

#### Recommended Solution

**Phase 1**: Server Auto-Indexes
- Integrate `prime_index()` into server lifespan
- Start FileWatcher as background task
- Expose indexing progress in health service

**Phase 2**: Index Command Enhancement
- Check if server running (health endpoint)
- If running: Send re-index trigger via MCP tool
- If not: Fall back to standalone (current)
- Add `--standalone` flag

---

## Correction Roadmap

### Week 1: Critical Infrastructure (Days 1-3)

#### Day 1: Unset Handling + Settings Construction (CRITICAL)
**Files**: doctor.py, config.py
**Priority**: BLOCKS ALL - These cause runtime errors

**Tasks**:
1. Fix all Unset checks in doctor.py (9 locations)
2. Fix settings construction in config.py (lines 302-342)
3. Fix import error in doctor.py (line 210)
4. Add unit tests for Unset handling

**Validation**:
```bash
# Should not error
codeweaver doctor
codeweaver config init --quick
```

#### Day 2: Registry Integration (HIGH)
**Files**: config.py, list.py
**Priority**: Correctness foundation

**Tasks**:
1. Replace hardcoded providers in config.py with registry
2. Replace hardcoded providers in list.py with registry
3. Add ModelRegistry integration to list.py
4. Add sparse embedding support to list.py

**Validation**:
```bash
# Should show all 35+ providers
codeweaver list providers

# Should show sparse providers
codeweaver list providers --kind sparse_embedding

# Should use registry data
codeweaver config init  # Shows all available providers
```

#### Day 3: Provider.other_env_vars Integration (HIGH)
**Files**: config.py, doctor.py
**Priority**: Correct env var guidance

**Tasks**:
1. Use `Provider.other_env_vars` in config.py (lines 200-365)
2. Use `Provider.other_env_vars` in doctor.py (lines 254-293)
3. Add Qdrant Cloud/Docker detection to doctor.py
4. Add secrets manager documentation to config.py

**Validation**:
```bash
# Should show correct env var names
codeweaver config init  # For each provider

# Should detect Docker/Cloud setups
codeweaver doctor
```

### Week 2: UX + Architecture (Days 4-6)

#### Day 4: Config Profiles + Quick Setup (HIGH)
**Files**: config.py
**Priority**: User experience

**Tasks**:
1. Add `--quick` flag support using `profiles.recommended_default()`
2. Add `--profile` option (recommended, local-only, minimal)
3. Support all config locations from `settings_customise_sources`
4. Add sparse embedding guidance

**Validation**:
```bash
# Should complete in <30 seconds
codeweaver config init --quick

# Should create user config
codeweaver config init --user

# Should create local override
codeweaver config init --local
```

#### Day 5: Command Unification (ARCHITECTURAL)
**Files**: init.py, config.py
**Priority**: UX clarity

**Tasks**:
1. Unify `init` and `config init` into single command
2. Add `--config-only` and `--mcp-only` flags
3. Document CodeWeaver's HTTP architecture
4. Generate correct HTTP streaming MCP config

**Validation**:
```bash
# Should do both config + MCP
codeweaver init

# Should only do config
codeweaver init --config-only

# Should only do MCP
codeweaver init --mcp-only
```

#### Day 6: Server Auto-Indexing (ARCHITECTURAL)
**Files**: index.py, server/server.py
**Priority**: User expectations

**Tasks**:
1. Add `prime_index()` call to server lifespan
2. Start FileWatcher as background task
3. Update index command to check/communicate with server
4. Add `--standalone` flag for local indexing

**Validation**:
```bash
# Should auto-index on startup
codeweaver server

# Should trigger server re-index
codeweaver index  # (with server running)

# Should work standalone
codeweaver index --standalone
```

### Week 3: Polish + Testing (Days 7-9)

#### Day 7: Helper Utilities Integration
**Files**: config.py, doctor.py
**Priority**: Code quality

**Tasks**:
1. Use git/checks/utils helpers in config.py
2. Use CLI utils for terminal adaptation
3. Fix dependency checks in doctor.py (use `find_spec()`)
4. Add installation extras detection

**Validation**: Code review for helper usage

#### Day 8: Missing Features
**Files**: config.py, doctor.py
**Priority**: Completeness

**Tasks**:
1. Add secrets manager documentation
2. Add Qdrant Cloud recommendations
3. Implement connection tests in doctor.py
4. Add sparse embedding limitations docs

**Validation**: Manual testing of all features

#### Day 9: Comprehensive Testing
**Files**: All CLI commands
**Priority**: Quality assurance

**Tasks**:
1. Add unit tests for all corrected logic
2. Add integration tests for command workflows
3. Add E2E tests for user journeys
4. Validate against real user scenarios

**Validation**: All tests passing, user journeys validated

---

## Detailed Corrections by File

### config.py Corrections

#### Correction 1: Use Provider Registry (Lines 162-184)

**Current** (WRONG):
```python
console.print("  1. [cyan]voyage[/cyan]     - VoyageAI (recommended, requires API key)")
console.print("  2. [cyan]openai[/cyan]     - OpenAI (requires API key)")
console.print("  3. [cyan]fastembed[/cyan]  - FastEmbed (local, no API key needed)")
console.print("  4. [cyan]cohere[/cyan]     - Cohere (requires API key)")
```

**Correct** (NEW):
```python
from codeweaver.common.registry import get_provider_registry
from codeweaver.providers.provider import ProviderKind

registry = get_provider_registry()
embedding_providers = [
    (provider, registry.get_service_card(provider))
    for provider in registry.list_providers(ProviderKind.EMBEDDING)
    if registry.is_provider_available(provider, ProviderKind.EMBEDDING)
]

console.print("\n[bold]Available Embedding Providers:[/bold]\n")
for idx, (provider, card) in enumerate(embedding_providers, 1):
    api_required = "requires API key" if provider.other_env_vars else "local"
    console.print(f"  {idx}. [cyan]{provider.value}[/cyan] - {api_required}")
```

**Evidence**: `/home/knitli/codeweaver-mcp/src/codeweaver/common/registry/provider.py` lines 1345-1410

#### Correction 2: Use Provider.other_env_vars (Lines 200-365)

**Current** (WRONG):
```python
if embedding_provider_name not in ("fastembed", "sentence-transformers") and not api_key:
    console.print(
        f"\n[yellow]⚠[/yellow]  Don't forget to set your {embedding_provider_name.upper()}_API_KEY environment variable!"
    )
```

**Correct** (NEW):
```python
from codeweaver.providers.provider import Provider

provider_enum = Provider.from_string(embedding_provider_name)
if provider_enum and (env_vars := provider_enum.other_env_vars):
    for env_var_tuple in (env_vars if isinstance(env_vars, tuple) else (env_vars,)):
        if api_key_info := env_var_tuple.get("api_key"):
            console.print(f"\n[yellow]⚠[/yellow] Set {api_key_info.env}: {api_key_info.description}")
            if env_var_tuple.get("note"):
                console.print(f"[dim]{env_var_tuple['note']}[/dim]")
```

**Evidence**: `/home/knitli/codeweaver-mcp/src/codeweaver/providers/provider.py` lines 122-356

#### Correction 3: Fix Settings Construction (Lines 302-342)

**Current** (WRONG):
```python
settings_data: dict = {
    "project_path": project_path,
    "provider": {"embedding": {"provider": embedding_provider_name, "enabled": True}},
}
settings = CodeWeaverSettings(**settings_data)
settings.save_to_file(config_path)
```

**Correct** (NEW):
```python
import tomli_w

# Write config file FIRST
config_data = {
    "project_path": str(project_path),
    "provider": {
        "embedding": [{"provider": embedding_provider_name, "enabled": True}]
    }
}
config_path.write_text(tomli_w.dumps(config_data))

# Then let CodeWeaverSettings resolve hierarchy
settings = CodeWeaverSettings(config_file=config_path)

# Show resolved settings (includes env vars, secrets, etc.)
console.print("\n[bold green]Configuration created successfully![/bold green]")
console.print(f"\n[bold]Resolved Settings:[/bold]")
console.print(settings.view())
```

**Evidence**: `/home/knitli/codeweaver-mcp/src/codeweaver/config/settings.py` lines 556-694

#### Correction 4: Add Config Profiles (Lines 102-379)

**NEW FUNCTION**:
```python
def _quick_setup(project_path: Path, output: Path | None = None) -> None:
    """Quick setup using recommended defaults."""
    from codeweaver.config.profiles import recommended_default

    console.print(f"\n{CODEWEAVER_PREFIX} [bold cyan]Quick Setup[/bold cyan]\n")
    console.print("Using recommended configuration:")
    console.print("  • Voyage for embeddings (voyage-code-3)")
    console.print("  • Voyage for reranking (voyage-rerank-2.5)")
    console.print("  • Qdrant for vector store")
    console.print("  • FastEmbed for sparse embeddings (optional)")

    # Just ask for API key
    voyage_key = Prompt.ask("\n[cyan]VOYAGE_API_KEY[/cyan]", password=True)

    # Generate config with recommended defaults
    profile = recommended_default()
    config_data = {
        "project_path": str(project_path),
        "provider": profile,
    }

    config_path = output or project_path / ".codeweaver.toml"
    import tomli_w
    config_path.write_text(tomli_w.dumps(config_data))

    # Set env var
    os.environ["VOYAGE_API_KEY"] = voyage_key

    console.print(f"\n[green]✓[/green] Configuration created at {config_path}")
    console.print(f"\n[yellow]Don't forget to add to your shell profile:[/yellow]")
    console.print(f"  export VOYAGE_API_KEY='{voyage_key}'")

# Modify init() to add quick mode
def init(..., quick: bool = False) -> None:
    if quick:
        _quick_setup(project_path, output)
        return

    # Existing interactive wizard...
```

**Evidence**: `/home/knitli/codeweaver-mcp/src/codeweaver/config/profiles.py` lines 28-54

### doctor.py Corrections

#### Correction 1: Fix Unset Checks (Multiple Lines)

**Current** (WRONG - Line 164):
```python
if not isinstance(settings.project_path, Path):
    from codeweaver.common.utils.git import get_project_path
    project_path = get_project_path()
else:
    project_path = settings.project_path
```

**Correct** (NEW):
```python
from codeweaver.core.types.sentinel import Unset

if isinstance(settings.project_path, Unset):
    from codeweaver.common.utils.git import get_project_path
    project_path = get_project_path()
else:
    project_path = settings.project_path
```

**Apply same pattern to**:
- Line 206: `settings.indexing.cache_dir`
- Lines 249-285: All `hasattr()` checks in provider validation

**Evidence**: `/home/knitli/codeweaver-mcp/src/codeweaver/core/types/sentinel.py` lines 148-158

#### Correction 2: Fix Import (Line 210)

**Current** (WRONG):
```python
from codeweaver.common.utils import get_user_config_dir
```

**Correct** (NEW):
```python
from codeweaver.common.utils.utils import get_user_config_dir
```

**Evidence**: `/home/knitli/codeweaver-mcp/src/codeweaver/common/utils/utils.py` line 153

#### Correction 3: Use Provider.other_env_vars (Lines 254-293)

**Current** (WRONG):
```python
api_key_map = {
    "voyageai": "VOYAGE_API_KEY",
    "openai": "OPENAI_API_KEY",
    "cohere": "COHERE_API_KEY",
    "huggingface": "HF_TOKEN",
}
```

**Correct** (NEW):
```python
def _check_embedding_api_keys(settings: CodeWeaverSettings, warnings: list[str]) -> None:
    from codeweaver.providers.provider import Provider
    from codeweaver.core.types.sentinel import Unset

    if isinstance(settings.provider, Unset):
        return
    if isinstance(settings.provider.embedding, Unset):
        return

    embedding_provider_name = settings.provider.embedding.provider
    try:
        provider_enum = Provider.from_string(embedding_provider_name)
        if env_vars := provider_enum.other_env_vars:
            for env_var_dict in (env_vars if isinstance(env_vars, tuple) else (env_vars,)):
                if api_key_info := env_var_dict.get("api_key"):
                    if not os.getenv(api_key_info.env):
                        warnings.append(f"{api_key_info.env} not set")
    except (AttributeError, ValueError):
        pass  # Provider not in enum, skip
```

**Evidence**: `/home/knitli/codeweaver-mcp/src/codeweaver/providers/provider.py` lines 122-356

### list.py Corrections

#### Correction 1: Use ProviderRegistry (Lines 107-149)

**Current** (WRONG):
```python
from codeweaver.providers.capabilities import PROVIDER_CAPABILITIES
# ... static capabilities dict
```

**Correct** (NEW):
```python
def providers(*, kind: str | None = None) -> None:
    from codeweaver.common.registry.provider import get_provider_registry
    from codeweaver.providers.capabilities import PROVIDER_CAPABILITIES

    registry = get_provider_registry()

    # Parse kind filter
    kind_filter = None
    if kind:
        kind_filter = ProviderKind.from_string(kind)

    # Get available providers from registry
    if kind_filter:
        available_providers = registry.list_providers(kind_filter)
    else:
        # Get all providers across all kinds
        available_providers = set()
        for pk in ProviderKind:
            if pk != ProviderKind.UNSET:
                available_providers.update(registry.list_providers(pk))

    # Build table with availability checks
    for provider in sorted(available_providers):
        capabilities = PROVIDER_CAPABILITIES.get(provider, ())
        if kind_filter and kind_filter not in capabilities:
            continue

        # Check actual availability
        is_available = any(
            registry.is_provider_available(provider, cap)
            for cap in capabilities
        )
        if not is_available:
            continue

        # ... table building
```

**Evidence**: `/home/knitli/codeweaver-mcp/src/codeweaver/common/registry/provider.py` lines 1345-1410

#### Correction 2: Add Sparse Embeddings (Lines 185-198)

**Current** (MISSING):
```python
# Only checks EMBEDDING and RERANKING
if ProviderKind.EMBEDDING in capabilities:
    _list_embedding_models(provider)
if ProviderKind.RERANKING in capabilities:
    _list_reranking_models(provider)
# NO SPARSE_EMBEDDING CHECK
```

**Correct** (NEW):
```python
if ProviderKind.EMBEDDING in capabilities:
    embedding_models = model_registry.list_embedding_models(provider)
    if embedding_models:
        _display_embedding_models(provider, embedding_models)

if ProviderKind.SPARSE_EMBEDDING in capabilities:
    sparse_models = model_registry.list_sparse_embedding_models(provider)
    if sparse_models:
        _display_sparse_embedding_models(provider, sparse_models)

if ProviderKind.RERANKING in capabilities:
    reranking_models = model_registry.list_reranking_models(provider)
    if reranking_models:
        _display_reranking_models(provider, reranking_models)
```

**Evidence**: `/home/knitli/codeweaver-mcp/src/codeweaver/providers/capabilities.py` lines 43-66

### init.py Corrections

#### Correction: Unify Commands and Document Architecture

**New Structure**:
```python
@app.command()
def init(
    *,
    config_only: bool = False,
    mcp_only: bool = False,
    quick: bool = False,
) -> None:
    """Initialize CodeWeaver configuration and MCP client setup.

    Examples:
        codeweaver init                  # Interactive: config + MCP
        codeweaver init --quick          # Quick setup with defaults
        codeweaver init --config-only    # Just create .codeweaver.toml
        codeweaver init --mcp-only       # Just configure MCP clients
    """
    if config_only:
        # Call config.init()
        pass
    elif mcp_only:
        # Current init.add() logic
        pass
    else:
        # Do both interactively
        pass
```

**MCP Config Generation** (Lines 124-137):
```python
def _create_codeweaver_config(project_path: Path) -> dict[str, Any]:
    """Create CodeWeaver MCP server configuration.

    NOTE: CodeWeaver uses HTTP streaming transport, not STDIO.
    This means:
    - Single server instance shared across all clients
    - Background indexing persists between client sessions
    - Concurrent request handling
    - Server must be started independently: `codeweaver serve`

    See: https://docs.codeweaver.ai/architecture/http-transport
    """
    return {
        "command": "codeweaver",
        "args": ["serve", "--project", str(project_path)],
        "env": {
            "CODEWEAVER_HOST": "127.0.0.1",
            "CODEWEAVER_PORT": "9328",
            "CODEWEAVER_TRANSPORT": "streamable-http",
        }
    }
```

**Evidence**: Architecture analysis from investigation

### index.py Corrections

#### Correction: Integrate with Server Lifecycle

**Current** (Lines 19-54):
```python
def index(...) -> None:
    """Index the codebase."""
    # Standalone indexing, no server interaction
```

**Correct** (NEW):
```python
def index(
    *,
    project_path: Path | None = None,
    force: bool = False,
    standalone: bool = False,
) -> None:
    """Trigger codebase indexing.

    By default, this command checks if the CodeWeaver server is running
    and triggers re-indexing via the server. If the server is not running
    or --standalone is specified, runs indexing locally.

    Examples:
        codeweaver index                  # Trigger server re-index
        codeweaver index --force          # Force full re-index
        codeweaver index --standalone     # Run locally regardless of server
    """
    from codeweaver.config.settings import get_settings
    import httpx

    settings = get_settings()
    host = settings.server.host if settings.server else "127.0.0.1"
    port = settings.server.port if settings.server else 9328

    # Check if server is running (unless --standalone)
    server_running = False
    if not standalone:
        try:
            response = httpx.get(f"http://{host}:{port}/health", timeout=2.0)
            server_running = response.status_code == 200
        except (httpx.ConnectError, httpx.TimeoutException):
            pass

    if server_running:
        console.print(f"{CODEWEAVER_PREFIX} Server detected, triggering re-index...")
        # TODO: Call internal MCP tool to trigger re-index
        # For now, inform user
        console.print("[yellow]Server indexing integration coming soon.[/yellow]")
        console.print("For now, the server auto-indexes on startup.")
    else:
        if not standalone:
            console.print(f"{CODEWEAVER_PREFIX} Server not detected, running standalone indexing...")
        # Current standalone logic
        _run_standalone_index(project_path, force)
```

**Server Integration** (server/server.py):
```python
async def lifespan(
    settings: CodeWeaverSettings, init_settings: PydanticSettings
) -> AsyncIterator[AppState]:
    # ... existing setup

    state = AppState(..., indexer=Indexer.from_settings())

    # NEW: Auto-index on startup
    if settings.server.auto_index:  # Default True
        console.print("[bold green]Starting initial indexing...[/bold green]")
        await state.indexer.prime_index(force_reindex=False)

    # NEW: Start background file watching
    from codeweaver.engine.indexer import FileWatcher
    watcher = FileWatcher(
        paths=[settings.project_path],
        indexer=state.indexer,
        file_filter=FileFilter(
            include=settings.indexing.include_patterns,
            exclude=settings.indexing.exclude_patterns,
        ),
    )
    watcher_task = asyncio.create_task(watcher.run())

    try:
        yield state
    finally:
        watcher_task.cancel()
        # ... cleanup
```

**Evidence**: Architecture document promises background indexing

---

## Testing Strategy

### Unit Tests

#### test_cli_config.py (NEW)
```python
def test_config_init_uses_registry():
    """Config init should use provider registry for available options."""
    # Mock registry with known providers
    # Call config init, capture prompts
    # Assert all registry providers shown

def test_config_init_uses_other_env_vars():
    """Config init should show correct env vars from Provider enum."""
    # For each provider, check env var names match Provider.other_env_vars

def test_config_quick_setup():
    """Config init --quick should use profiles.recommended_default()."""
    # Call with --quick flag
    # Assert uses profile, minimal prompts

def test_config_settings_construction():
    """Config init should write file then resolve via CodeWeaverSettings."""
    # Call config init
    # Verify .codeweaver.toml created
    # Verify CodeWeaverSettings() loads correctly
    # Verify env vars override file settings
```

#### test_cli_doctor.py (NEW)
```python
def test_doctor_unset_handling():
    """Doctor should correctly check for Unset sentinel."""
    # Create settings with various Unset fields
    # Run doctor checks
    # Assert no type errors, correct warnings

def test_doctor_config_optional():
    """Doctor should not warn about missing config file."""
    # Set env vars only, no config file
    # Run doctor
    # Assert no warnings about missing file

def test_doctor_qdrant_detection():
    """Doctor should detect Docker and Cloud Qdrant setups."""
    # Test local, Docker, Cloud scenarios
    # Assert correct detection
```

#### test_cli_list.py (NEW)
```python
def test_list_providers_uses_registry():
    """List providers should use ProviderRegistry."""
    # Get providers from list command
    # Compare with registry.list_providers()
    # Assert match

def test_list_sparse_embeddings():
    """List models should show sparse embedding models."""
    # List models for fastembed
    # Assert sparse models shown

def test_list_coverage():
    """List should show >90% of actual capabilities."""
    # Count providers in registry
    # Count providers shown by list
    # Assert >90% coverage
```

### Integration Tests

#### test_cli_workflows.py (NEW)
```python
async def test_config_to_server_workflow():
    """Full workflow: config init -> server start -> search."""
    # Run config init
    # Start server
    # Verify auto-indexing
    # Run search query
    # Assert results

async def test_doctor_diagnosis():
    """Doctor should correctly diagnose common issues."""
    # Create broken configs
    # Run doctor
    # Assert correct issue detection

async def test_index_server_integration():
    """Index command should communicate with server."""
    # Start server
    # Run index command
    # Verify server re-indexes
```

### E2E Tests

#### test_user_journeys.py (NEW)
```python
def test_first_time_setup_journey():
    """New user: install -> init -> search."""
    # Simulate new user
    # Run codeweaver init --quick
    # Start server
    # Run search
    # Assert <10 min total time

def test_daily_usage_journey():
    """Daily use: start server -> search -> refine."""
    # Start server (with auto-index)
    # Run searches
    # Assert <30s per search
```

---

## Success Criteria

### Correctness Metrics

- [ ] **0 hardcoded provider lists** - All use registries
- [ ] **0 hardcoded env var names** - All use Provider.other_env_vars
- [ ] **0 Unset handling errors** - All use isinstance(x, Unset)
- [ ] **100% registry coverage** - List shows all available providers
- [ ] **Sparse embeddings visible** - List includes sparse models
- [ ] **Settings construction correct** - Respects precedence hierarchy

### UX Metrics

- [ ] **Config init <2 min** with --quick flag
- [ ] **Config init <5 min** interactive mode
- [ ] **Doctor 0 false positives** on valid configs
- [ ] **Doctor 0 false negatives** on broken configs
- [ ] **List shows 35+ providers** (up from 8)
- [ ] **Server auto-indexes** on startup
- [ ] **Index integrates** with server lifecycle

### Quality Metrics

- [ ] **Unit test coverage >80%** for corrected code
- [ ] **Integration tests** for all workflows
- [ ] **E2E tests** for user journeys
- [ ] **Constitutional compliance** validated
- [ ] **Documentation updated** for new patterns

---

## Implementation Order (Parallel Where Possible)

### Batch 1: Critical Fixes (Parallel)
- **Agent 1**: config.py Unset + settings construction
- **Agent 2**: doctor.py Unset fixes + import fix
- **Agent 3**: Unit tests for Batch 1

### Batch 2: Registry Integration (Parallel)
- **Agent 1**: config.py provider registry integration
- **Agent 2**: list.py provider/model registry integration
- **Agent 3**: list.py sparse embeddings support

### Batch 3: Provider.other_env_vars (Parallel)
- **Agent 1**: config.py env var usage
- **Agent 2**: doctor.py env var usage
- **Agent 3**: Qdrant detection in doctor.py

### Batch 4: UX Improvements (Parallel)
- **Agent 1**: config.py profiles + quick setup
- **Agent 2**: init.py command unification
- **Agent 3**: index.py server integration

### Batch 5: Testing & Documentation (Parallel)
- **Agent 1**: Comprehensive unit tests
- **Agent 2**: Integration tests
- **Agent 3**: E2E tests + documentation

---

**Document Version**: 1.0
**Last Updated**: 2025-01-06
**Ready for Implementation**: YES
