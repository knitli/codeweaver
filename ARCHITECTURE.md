<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# CodeWeaver Architecture & Design Decisions

**Purpose**: This document serves as the authoritative reference for CodeWeaver's architectural decisions, design principles, and technical philosophy. It consolidates design decisions scattered across multiple project files into a unified resource.

**Status**: Living document - Updated as architectural decisions evolve  
**Version**: 1.1.0  
**Last Updated**: 2025-11-23

---

## Table of Contents

1. [Project Constitution](#project-constitution)
2. [Core Philosophy](#core-philosophy)
3. [Design Principles](#design-principles)
4. [Architectural Goals](#architectural-goals)
5. [Technical Architecture](#technical-architecture)
6. [API Architecture](#api-architecture)
7. [Provider Architecture](#provider-architecture)
8. [Code Design Patterns](#code-design-patterns)
9. [Testing Philosophy](#testing-philosophy)
10. [Development Workflow](#development-workflow)
11. [Brand Voice & Terminology](#brand-voice--terminology)
12. [Key Technical Decisions](#key-technical-decisions)
13. [Trade-offs & Constraints](#trade-offs--constraints)

---

## Project Constitution

**AUTHORITATIVE SOURCE**: [`.specify/memory/constitution.md`](.specify/memory/constitution.md) v2.0.1

The CodeWeaver Constitution is the highest authority for all technical and architectural decisions. This constitution supersedes all other development practices and guidelines.

### Constitutional Principles (Non-Negotiable)

#### I. AI-First Context
Deliver precise codebase context for plain language agent requests. Every feature must enhance the ability of AI agents to understand and work with code through "exquisite context." Design APIs, documentation, and tooling with AI consumption as the primary interface, not an afterthought.

**Rationale**: CodeWeaver's mission is to bridge the gap between human expectations and AI agent capabilities, making AI-first design essential for success.

#### II. Proven Patterns
Leverage established abstractions and ecosystem alignment over reinvention. Channel proven architectural patterns from FastAPI, pydantic ecosystem, and established open source projects. Use familiar interfaces that reduce learning curve and increase adoption.

**Rationale**: Established patterns reduce development risk, accelerate onboarding, and provide battle-tested solutions to common problems.

#### III. Evidence-Based Development (NON-NEGOTIABLE)
All technical decisions must be supported by verifiable evidence: documentation, testing, metrics, or reproducible demonstrations. No workarounds, mock implementations, or placeholder code without explicit user authorization. "No code beats bad code."

**Rationale**: Evidence-based development ensures reliability, maintainability, and prevents technical debt from accumulating.

#### IV. Testing Philosophy
Effectiveness over coverage. Focus on critical behavior affecting user experience, realistic integration scenarios, and input/output validation. Integration testing preferred over unit testing. One solid, realistic test beats ten implementation detail tests.

**Rationale**: Testing should validate real-world usage patterns and prevent user-affecting bugs, not just achieve coverage metrics.

#### V. Simplicity Through Architecture
Transform complexity into clarity. Use simple modularity with extensible yet intuitive design where purpose should be obvious. Implement flat structure grouping related modules in packages while avoiding unnecessary nesting.

**Rationale**: Simplicity enables maintainability, reduces bugs, and makes the codebase accessible to contributors.

### Constitutional Governance

- **Amendment Process**: Constitution changes require documentation of rationale, impact analysis, and migration plan for affected code
- **Enforcement**: All code reviews, feature planning, and technical decisions must verify compliance with constitutional principles
- **Complexity Justification**: Any deviation requires documented rationale and consideration of simpler alternatives

---

## Core Philosophy

### Mission Statement

Bridge the gap between human expectations and AI agent capabilities through "exquisite context." Create beneficial cycles where AI-first tools enhance both agent and human capabilities.

### The Problem We Solve

AI coding agents face **too much irrelevant context** (70-80% unused), causing token waste, missed patterns, and hallucinations.

**Root Causes**: Tool confusion (5-20+ discovery tools), context bloat (25K-40K tokens in tool descriptions), proprietary lock-in, search fragmentation.

**Our Solution**: Single `find_code` tool + agent-driven curation + hybrid search (text + semantic + AST) + platform extensibility.

**Impact**: 60-80% context reduction, >90% relevance, 5x cost savings per query.

**For Complete Analysis**: See [PRODUCT.md - The Problem We Solve](PRODUCT.md#the-problem-we-solve) for detailed user impact, competitive landscape, and market positioning.

---

## Design Principles

CodeWeaver is built on five core principles that guide every technical decision:

### 1. AI-First Context
Every feature enhances AI agent understanding of code through precise context delivery. We design for AI consumption first, human inspection second.

**In Practice**:
- Single-tool interface (`find_code`) eliminates tool selection cognitive load
- Natural language queries over rigid syntax
- Span-based precision (exact line/column references)
- Task-aware context ranking

### 2. Proven Patterns Over Reinvention
We use proven patterns from successful open source projects in the pydantic ecosystem (FastAPI, pydantic-ai, FastMCP). Familiar interfaces reduce learning curve and increase adoption.

**In Practice**:
- FastAPI-style dependency injection and middleware patterns
- pydantic models for all structured data
- Plugin architecture inspired by VS Code and Babel
- Configuration via pydantic-settings

### 3. Evidence-Based Development
All technical decisions backed by verifiable evidence: documentation, testing, metrics, or reproducible demonstrations. No workarounds, no placeholder code, no "it should work" assumptions.

**In Practice**:
- No `NotImplementedError` or `TODO` shortcuts
- All features backed by tests or documentation
- Architectural decisions documented with rationale
- Performance claims backed by benchmarks

### 4. Effectiveness Over Coverage
Testing focuses on critical behavior affecting user experience. One realistic integration test beats ten implementation detail tests. Code coverage scores don't measure outcomes.

**In Practice**:
- Integration tests over unit tests
- Test realistic user workflows
- Focus on user-affecting behavior
- Coverage as indicator, not goal

### 5. Simplicity Through Architecture
We transform complexity into clarity using simple modularity with extensible design where purpose is obvious. Flat structure, clear naming, minimal nesting.

**In Practice**:
- Flat project structure with obvious purpose
- Single responsibility modules
- Clear naming conventions
- Extensible through composition, not inheritance

---

## Architectural Goals

### Goal 1: Semantically-Rich, Ranked Context Delivery

**What**: Provide developers and AI agents with weighted, prioritized search results using AST analysis and multiple embedding/reranking models.

**How**:
- ast-grep for semantic code analysis
- Support for dozens of embedding and reranking models (local and remote)
- Fully pluggable provider architecture
- Integration of arbitrary data sources beyond codebase

### Goal 2: Eliminate Cognitive Load on Agents

**What**: Reduce all operations to a single, simple, plain language tool.

**How**:
- Single `find_code` tool replaces 5-20+ specialized tools
- Natural language queries with optional structured filters
- MCP sampling for context curation (separate agent instance)
- Agent evaluates needs without polluting primary agent's context

### Goal 3: Significantly Reduce Context Bloat and Costs

**What**: Restrict context to only what agents need while maintaining precision.

**How**:
- Span-based code intelligence (exact line/column tracking)
- Token-aware context assembly
- Agent-driven curation for precision
- Background indexing keeps context current

---

## Technical Architecture

### Span-Based Core

**Design Decision**: Use immutable span-based architecture for precise code location tracking.

**Components**:
- `Span`: Represents precise code locations (line/column)
- `SpanGroup`: Composition of spans with set operations (union, intersection, difference)
- `CodeChunk`: Carries spans and metadata for token-aware assembly
- `CodeMatch`: Search results with span-based location tracking

**Rationale**:
- Exact references eliminate "nearby code" confusion
- Immutable operations enable thread-safe concurrent processing
- Set operations allow accurate merging across search passes
- Superior to offset-based or line-only approaches

### Semantic Metadata from AST-Aware Indexing

**Design Decision**: Comprehensive semantic metadata classification system.

**Components**:
- `ExtKind`: Enumerates language and chunk types
- `SemanticMetadata`: Tracks AST nodes and classifications
- Task-based priority ranking for nuanced searches
- Support for 26 programming languages

**Rationale**:
- AST awareness improves chunk boundary detection
- Semantic classification enables intelligent ranking
- Task-aware priorities deliver contextually relevant results

### Backup Code-Aware Indexing (170+ Languages)

**Design Decision**: Sophisticated heuristic fallback for languages without AST support.

**Features**:
- Pattern-based context identification for 170+ languages
- Support for legacy codebases (COBOL, Pascal, Fortran, etc.)
- Custom language support via configuration
- Family pattern association (C-style, Python, ML, Lisp, etc.)

**Rationale**:
- Enables CodeWeaver to work with any codebase, not just modern languages
- Maintains value proposition for legacy code maintenance
- Graceful degradation when AST unavailable

### Hybrid Search Pipeline

**Design Decision**: Combine multiple search signals with unified ranking.

**Architecture**:
```
┌─────────────────────────────────────────┐
│        Hybrid Search Pipeline            │
│                                          │
│  ┌──────────┐  ┌──────────┐  ┌────────┐│
│  │   Text   │  │ Semantic │  │  AST   ││
│  │  Search  │  │Embeddings│  │Analysis││
│  └──────────┘  └──────────┘  └────────┘│
│                                          │
│  ┌────────────────────────────────────┐ │
│  │      Unified Ranking               │ │
│  │   (Span-based Assembly)            │ │
│  └────────────────────────────────────┘ │
└─────────────────────────────────────────┘
```

**Rationale**:
- Text search: Fast keyword matching
- Semantic search: Intent understanding
- AST analysis: Structure awareness
- Unified ranking: Best of all approaches

---

## API Architecture

### Three-Tier API Design

**Design Decision**: Different interfaces optimized for different users.

#### 1. Human API: Deep Configurability

**Interface**: Configuration files (TOML/YAML), CLI commands, environment variables

**Philosophy**: Humans want control, customization, and understanding

**Surface Area**: Extensive
- Provider selection and configuration (10+ embedding providers)
- Chunking strategies and parameters
- Ranking algorithms and weights
- Token budgets and caching policies
- Plugin architecture for custom middleware
- Integration with existing infrastructure

**Example**:
```toml
[embedding]
provider = "voyageai"
model = "voyage-code-3"
batch_size = 32

[chunking]
strategy = "ast-aware"
max_tokens = 512
overlap_tokens = 50

[ranking]
weights = { semantic = 0.4, keyword = 0.3, ast = 0.3 }
```

#### 2. User Agent API: Radical Simplicity

**Interface**: MCP tools

**Philosophy**: Agents focus on *what* to find, not *how* to search

**Surface Area**: 1-3 tools
- `find_code(query, intent?, filters?)` - primary interface
- `change_code(...)` - (future) for code modification
- `get_context(...)` - (future) for explicit context requests

**Example**:
```
Agent uses: find_code
Query: "authentication middleware patterns"
Intent: "implementation" (optional)
Filters: { language: "python", file_type: "code" } (optional)

→ Returns: Precise, ranked results with provenance
```

#### 3. Context Agent API: Controlled Expansion

**Interface**: Extended MCP tools for context curation agents

**Philosophy**: Context agents need more capability than user agents, but still bounded

**Surface Area**: 3-8 specialized tools
- `find_code` - same as user agent
- `get_semantic_neighbors` - explore related code
- `get_call_graph` - understand execution flow
- `get_import_tree` - track dependencies
- `analyze_context_coverage` - assess completeness

**Rationale**: Enables sophisticated curation via MCP sampling without exposing complexity to end users

### Why This Architecture Matters

**Eliminates False Trade-off**: Traditional thinking says "powerful features OR simple interface—pick one." CodeWeaver provides both through appropriate interfaces for each user type.

**Each API Optimized for Its User**:
- **Humans**: Understand, configure, customize, debug, extend
- **User Agents**: Get work done without cognitive overhead
- **Context Agents**: Targeted tools for sophisticated curation

**Addresses Different Pain Points**:
- **Human API** → Solves "locked into vendor decisions"
- **User Agent API** → Solves "tool confusion and context bloat"
- **Context Agent API** → Enables "intelligent curation without complexity"

---

## Provider Architecture

### Design Decision: Pluggable Provider Ecosystem

**Philosophy**: Infrastructure freedom - use what you already have

**Provider Types**:

#### Provider Coverage

**Embedding**: 10+ providers including VoyageAI, OpenAI, Bedrock, Cohere, Google, Mistral, Hugging Face, fastembed, sentence-transformers

**Rerank**: VoyageAI, Bedrock, Cohere, fastembed, sentence-transformers

**Agent**: Full pydantic-ai ecosystem (OpenAI, Anthropic, Google, Mistral, Groq, Hugging Face, Bedrock, and more)

**Vector Stores**: Qdrant (production), in-memory (development)

**Data Sources**: Filesystem (with file watching), Tavily, DuckDuckGo | Planned: Context7

**Complete Details**: See [README.md - Providers](README.md#providers-and-optional-extras) for installation options and [Provider Documentation](docs/providers.md) for configuration guides.

**Implementation Pattern**:
```python
# Abstract base protocol
class EmbeddingProvider(Protocol):
    async def embed(self, texts: list[str]) -> list[list[float]]: ...
    def get_dimensions(self) -> int: ...

# Concrete implementation
class VoyageAIProvider(EmbeddingProvider):
    def __init__(self, api_key: str, model: str = "voyage-code-3"): ...
    async def embed(self, texts: list[str]) -> list[list[float]]: ...
    def get_dimensions(self) -> int: ...

# Registration
ProviderRegistry.register_embedding_provider("voyageai", VoyageAIProvider)
```

**Rationale**:
- No vendor lock-in
- Use existing infrastructure investments
- Community can contribute custom providers
- Platform positioning vs. point solution

### Configuration Management

**Design Decision**: Hierarchical configuration via pydantic-settings

**Features**:
- Multi-source: Environment variables, TOML files, defaults
- Capability-based provider selection
- Dynamic instantiation with health monitoring
- All settings documentable and validateable

**Rationale**:
- Proven pattern from pydantic ecosystem
- Type-safe configuration with validation
- Clear precedence rules
- No hardcoded values in implementation

---

## Code Design Patterns

### Pydantic Architecture Patterns

**Design Decision**: Channel FastAPI/pydantic ecosystem patterns

**Key Patterns**:

#### Flexible Generics
Few broadly-defined models/protocols/ABCs for wide reuse

```python
class BasedModel(BaseModel):
    """Base for all CodeWeaver models with common config"""
    model_config = ConfigDict(frozen=True, extra="forbid")
```

#### Smart Decorators
Extend class/function roles cleanly

```python
@wrap_filters(filterable_fields=DEFAULT_FILTERABLE_FIELDS)
async def find_code(query: str, **dynamic_filters): ...
```

#### Dependency Injection
Explicit dependencies, organized pipelines

```python
async def search(
    query: str,
    embedding_provider: EmbeddingProvider = Depends(get_embedding_provider),
    vector_store: VectorStore = Depends(get_vector_store),
): ...
```

#### Flat Structure
Group closely related modules, otherwise keep root-level

```
src/codeweaver/
├── _common.py           # Shared utilities
├── embedding/          # All embedding providers
├── vector_stores/      # All vector store providers
├── services/           # Business logic services
└── middleware/         # FastMCP middleware
```

#### Types as Functionality
Types ARE the behavior, not separate from it

```python
class Span:
    """Immutable code location with set operations"""
    def union(self, other: Span) -> SpanGroup: ...
    def intersection(self, other: Span) -> SpanGroup | None: ...
```

### Lazy Evaluation & Immutability

**Design Decision**: Performance + memory efficiency + fewer debugging headaches

**Patterns**:
- **Sequences**: Use `Generator`/`AsyncGenerator`, `tuple` over lists
- **Sets**: Use `frozenset` for set-like objects
- **Dicts**: Read-only dicts use `types.MappingProxyType`
- **Models**: Use `frozen=True` for dataclasses/models

**Rationale**:
- Immutable data structures are thread-safe
- Lazy evaluation reduces memory footprint
- Functional patterns reduce bugs
- Easier to reason about code flow

### Type System Discipline

**Design Decision**: Strict typing with opinionated pyright rules

**Requirements**:
- All public functions have type annotations (including `-> None`)
- Use `TypedDict`, `Protocol`, `NamedTuple`, `enum.Enum` for structured data
- Avoid generic types like `dict[str, Any]` when structure is known
- Modern Python ≥3.12 syntax (`int | str`, `typing.Self`, `type` keyword)

**Project-Specific Types**:
```python
from codeweaver.core.types import BasedModel, BaseEnum, DataclassSerializationMixin

# Use BasedModel instead of BaseModel
class MyModel(BasedModel): ...

# Use BaseEnum instead of Enum
class MyEnum(BaseEnum): ...

# Use pydantic dataclass with serialization mixin
@dataclass
class MyData(DataclassSerializationMixin): ...
```

**Rationale**:
- Maintainability and self-documentation
- Catch errors at development time
- Enable better IDE support
- Make refactoring safer

---

## Testing Philosophy

### Effectiveness Over Coverage

**Core Principle**: Testing focuses on critical behavior affecting user experience, not coverage metrics.

**Priorities**:
1. Realistic integration scenarios
2. User-affecting behavior
3. Input/output validation for important functions
4. Edge cases that could cause failures

**Anti-Patterns** (What We Don't Do):
- Chase 100% coverage for its own sake
- Test implementation details
- Create barriers to innovation with rigid tests
- Maintain low-value tests that don't prevent bugs

### Testing Strategy

**Integration Testing > Unit Testing**: One solid, realistic test beats ten implementation detail tests.

**Test Categories** (via pytest markers):
- `unit`: Individual component tests (when appropriate)
- `integration`: Component interaction tests (preferred)
- `e2e`: End-to-end workflow tests
- `benchmark`: Performance validation
- `network`/`external_api`: Tests requiring external services
- `async_test`: Asynchronous test cases

**Example**: Testing `find_code`
```python
# Good: Integration test of realistic workflow
@pytest.mark.integration
async def test_find_code_authentication_query():
    """Test that find_code returns relevant authentication code"""
    result = await find_code("how do we handle authentication?")
    
    assert len(result.matches) > 0
    assert any("auth" in match.file_path.lower() for match in result.matches)
    assert result.metadata.token_count < 10000

# Avoid: Testing implementation details
# def test_find_code_internal_query_parser(): ...  # Too low-level
```

**Rationale**: This approach ensures tests validate real-world usage and prevent user-affecting bugs, not just achieve arbitrary coverage numbers.

---

## Development Workflow

### Code Quality Standards

**Docstrings**: Google convention (loose), plain language, active voice, present tense
- Start with verbs: "Adds numbers" not "This function adds numbers"
- Don't waste space explaining the obvious—strong typing makes args/returns clear

**Line length**: 100 characters

**Auto-formatting**: Ruff configuration enabled

**Python typing**: Modern ≥3.12 syntax

### Common Linting Patterns

**Logging**:
- No f-strings in log statements (use `%s` formatting or `extra=`)
- Most errors should use `logging.warning` to allow them to get handled by codeweaver's UI (logging.exception bypasses our UI)
- No print statements in production code

**Exception Handling**:
- Specify exception types (no bare `except:`)
- Use `raise from` to maintain exception context
- Use `contextlib.suppress` for intentional suppression
- Raise to specific CodeWeaver exceptions (`codeweaver.exceptions`)

**Functions**:
- Type all parameters and returns (including `-> None`)
- Boolean kwargs only: use `*` separator

```python
def my_function(arg1: str, *, flag: bool = False) -> None:
    pass
```

### Red Flag Protocol for Agents

**When to Stop and Investigate**:
- API behavior differs from expectations
- Files/functions aren't where expected
- Code behavior contradicts documentation

**Response Protocol**:
1. **Stop** current work immediately
2. **Review** understanding and plans systematically
3. **Assess** approach:
   - Does it comply with Project Constitution?
   - Is it consistent with requirements?
   - Do you have sufficient information?
4. **Research** using available tools
5. **Ask** user for clarification if still unclear
6. **Never** create workarounds without explicit authorization

**Bottom Line**: No code beats bad code (Constitutional Principle III).

---

## Brand Voice & Terminology

### Mission Alignment

Bridge the gap between human expectations and AI agent capabilities through "exquisite context." This mission directly implements Constitutional Principle I (AI-First Context).

### User Terms

**Agent/AI Agent** (not "model", "LLM", "tool")
- **Developer's Agent**: Focused on developer tasks
- **Context Agent**: Internal agents delivering information

**Developer/End User**: People using CodeWeaver
- **Developer User**: Uses CodeWeaver as development tool
- **Platform Developer**: Builds with/extends CodeWeaver

**Us**: First person plural (not "Knitli" or "team")  
**Contributors**: External contributors when distinction needed

### Core Values

- **Simplicity**: Transform complexity into clarity, eliminate jargon
- **Humanity**: Enhance human creativity, design people-first
- **Utility**: Solve real problems, meet users where they are
- **Integration**: Power through synthesis, connect disparate elements

### Personality

**We are**: Approachable, thoughtful, clear, empowering, purposeful

**We aren't**: Intimidating, unnecessarily complex, cold, AI-for-AI's-sake

### Communication Style

- Plain language accessible to all skill levels
- Simple examples with visual aids
- Conversational and human, not robotic
- Honest about capabilities and limitations
- Direct focus on user needs and goals

---

## Key Technical Decisions

### Decision: Single-Tool Interface

**Context**: How many tools should CodeWeaver expose via MCP?

**Options Considered**:
1. Multiple specialized tools (`search_code`, `get_definitions`, `find_references`)
2. Single flexible tool (`find_code` with intent parameter)
3. Agent-specific tools (`quick_search`, `deep_analysis`)

**Decision**: Single `find_code` tool with optional intent parameter for user's agent

**Rationale** (Constitutional Principles Applied):
- **Simplicity Through Architecture**: One interface reduces cognitive load
- **AI-First Context**: Agents express natural language queries without tool selection
- **Proven Patterns**: FastAPI-style flexible parameters vs. endpoint proliferation
- **Evidence-Based**: User testing showed tool selection added complexity without value

**Outcome**:
- Lower barrier to adoption (one tool to learn)
- Cleaner agent prompts (no tool selection logic)
- Easier to extend (intent parameter can evolve)
- Better user feedback (focus on single interface quality)

### Decision: Full Plugin Architecture

**Context**: Build extensibility now or ship faster with fixed providers?

**Options Considered**:
1. Hardcode VoyageAI + Qdrant, ship immediately
2. Abstract providers minimally, add more later
3. Full plugin architecture from start

**Decision**: Full plugin architecture (Constitutional Principle II: Proven Patterns)

**Rationale**:
- FastAPI demonstrates value of dependency injection and extensibility
- User research showed diverse infrastructure preferences
- Platform thinking: enable ecosystem to extend
- Evidence: Successful platforms (VS Code, Babel) prioritize plugins early

**Outcome**:
- 10+ embedding providers supported
- Vendor independence (no lock-in)
- Community can contribute custom providers
- Platform positioning vs. point solution

### Decision: Span-Based Architecture

**Context**: How to represent code locations precisely?

**Options Considered**:
1. Line numbers only
2. Character offsets
3. Span-based with line/column and set operations

**Decision**: Immutable span-based architecture with set operations

**Rationale**:
- Exact references eliminate "nearby code" confusion
- Set operations enable accurate merging across search passes
- Immutable operations are thread-safe
- Superior composition capabilities

**Outcome**:
- Precise code location tracking
- Clean composition of results
- Thread-safe concurrent processing
- Better than alternatives in every dimension

### Decision: Hybrid Search with Unified Ranking

**Context**: How to combine different search approaches?

**Options Considered**:
1. Text search only (fast but imprecise)
2. Semantic search only (precise but expensive)
3. Parallel search with simple score combination
4. Hybrid pipeline with unified span-based ranking

**Decision**: Hybrid pipeline with unified ranking across all signals

**Rationale**:
- Text search provides speed and keyword matching
- Semantic search provides intent understanding
- AST analysis provides structural awareness
- Unified ranking leverages best of all approaches

**Outcome**:
- Best precision and recall characteristics
- Handles both keyword and semantic queries well
- Graceful degradation when components unavailable
- Extensible to additional signals

### Decision: MCP Sampling for Context Curation

**Context**: How to curate context without polluting agent's context?

**Options Considered**:
1. Return all potentially relevant results
2. Use heuristics to filter results
3. Use separate agent instance for curation (MCP sampling)

**Decision**: MCP sampling - separate agent evaluates and curates

**Rationale**:
- **AI-First Context**: Well-prompted agents can better shape context delivery
- Zero context pollution in primary agent
- 40-60% better precision vs. heuristics
- Leverages MCP protocol capability

**Outcome**:
- Superior result quality
- No context overhead in primary agent
- Natural language curation logic
- Innovative use of MCP protocol

### Decision: MCP-Independent Context Curation

**Context**: How to ensure premium context gets delivered in the first turn? (MCP tools activate only after agents call them)

**Options Considered**:
1. MCP-only with prompting to encourage early use
2. Independent agent handling for proactive delivery
3. Dual approach: MCP sampling + independent agent handling + CLI exposure

**Decision**: Dual approach with both MCP and independent paths

**Rationale**:
- **User Control**: Direct context retrieval via CLI before starting agent interactions
- **Strategic Flexibility**: Not locked into MCP protocol evolution
- **First-Turn Context**: Optimal delivery doesn't wait for agent tool selection
- **Future-Proof**: Enables HTTP dashboards, IDE integrations, custom workflows
- **Proven Stack**: pydantic-ai provides production-ready agent handling

**Outcome**:
- Users proactively request tailored context (CLI: `codeweaver search "auth patterns"`)
- Agents receive context-rich initial state, biased toward CodeWeaver for follow-ups
- MCP protocol changes don't break core functionality
- Foundation for Phase 3 platform evolution (MCP orchestration hub)

**Trade-off**: More implementation complexity → Greater strategic flexibility + better UX

### Decision: Only Index Known or User-Defined File Types

**Context**: Prevent irrelevant files from polluting agent context while maintaining comprehensive coverage.

**Options Considered**:
1. Index all text files (simple binary check only)
2. Constrain to well-known paths only (src/, docs/, etc.)
3. Comprehensive known-filetype catalog with user extensibility

**Decision**: Option 3 - Catalog 300+ known extensions across 170+ languages, allow user configuration for additions

**Rationale**:
- **Quality over Coverage**: Unknown filetypes risk high-noise, low-value context pollution
- **Smart Inference**: Finite set of common filetypes enables confident purpose/importance estimation before indexing
- **User-Friendly**: Doesn't require users to manually configure common cases
- **Security Benefit**: Avoids indexing hidden/unusual files that could contain injection attacks

**Outcome**:
- 300+ known code, documentation, and configuration extensions defined
- Repository pattern mapping for type/language/purpose/importance classification
- User extensibility via simple configuration for edge cases
- Optimal balance: comprehensive coverage without noise

**Trade-off**: More upfront cataloging work → Superior precision and user experience

### Decision: Generate Backup Embeddings and Storage

**Context**: Prevent offline or unexpected vector store unavailability from disabling CodeWeaver's core functions.

**Options Considered**:
1. Offer a backup system but don't enable by default
2. Let CodeWeaver fail, explaining the root issue with the vector store.
3. Automatic backup-as-a-feature.

**Decision**: Option 3 -- Create a robust backup/fallback system by default, continually prepared to take over. Use lightweight models and persisted json to keep an effective but relatively lightweight backup using the in-memory provider.

**Rationale**:
- **Resilience**: CodeWeaver's single point of failure is the vector store. Without a backup, if the vector store is unavailable, such as by being offline or disrupted service, then CodeWeaver can't function. A backup allows for service to continue.
- **Flexibility**: User's don't have to worry about whether CodeWeaver will work or not. It always will be available, with slightly degraded capabilities.
- **Reduces Confusion**: AI Agents don't encounter cryptic errors about CodeWeaver's internals. They can continue to focus on their job.

**Trade-off**: Increased implementation and complexity; more resource demand (mitigated by smart/low priority resource management)

## Strategic Design Principles

These principles guide CodeWeaver's technical decision-making and differentiate our approach from typical MCP servers.

### 1. Deep Quality as Competitive Moat

**Principle**: Favor time-intensive, high-quality implementations over fast iterations.

**Rationale**:
- Unknown products in crowded spaces (MCP ecosystem) must differentiate through exceptional quality
- Technical debt is expensive for small teams - build maintainable platforms from the start
- "Build in the open" benefits from showing polished progress vs. frequent pivots
- Quality compounds: each well-built component makes future work easier

**In Practice**:
- Full plugin architecture instead of hardcoded providers (Decision: Full Plugin Architecture)
- Span-based architecture with set operations vs. simple line numbers (Decision: Span-Based Architecture)
- 170+ language support with sophisticated heuristics (not just "the big 10")

**Trade-off**: Longer time to market → Higher quality at launch → Stronger positioning

### 2. Principle-Driven vs. Convention-Driven Design

**Principle**: Design decisions derive from constitutional principles and user needs, not "what others have done."

**Rationale**:
- MCP is young with no established "right way" yet
- CodeWeaver is a **platform using MCP**, not an "MCP tool" - different goals require different approaches
- Primary goal: Better development experience through exquisite context (MCP is means, not end)
- Following conventions blindly risks optimizing for wrong outcomes

**In Practice**:
- Single-tool interface while others expose 5-20+ tools (Decision: Single-Tool Interface)
- MCP-independent agent handling for premium context delivery (Decision: MCP-Independent Context Curation)
- Three-tier API architecture vs. one-size-fits-all (Decision: Three-Tier API Design in PRODUCT.md)

**Trade-off**: Less "idiomatic" MCP → Better user outcomes → Strategic differentiation

### Connection to Product Vision

These principles support CodeWeaver's evolution from search tool → context platform → unified MCP orchestration hub (see [PRODUCT.md - Product Vision](PRODUCT.md#product-vision)).

**Phase 1 (Current)**: Deep quality in search establishes credibility
**Phase 2 (2025-2026)**: Thread integration builds on solid foundation; rudimentary cloud offerings
**Phase 3 (2026+)**: Platform play enabled by principle-driven architecture 

---

## Trade-offs & Constraints

### Trade-off: Complexity vs. Capability

**Choice**: Rich semantic metadata and span-based architecture

**Cost**: More complex type system, steeper learning curve

**Benefit**: Superior precision, extensibility, and composability

**Justification**: Aligns with Constitutional Principle I (AI-First Context) - precision is the core value proposition. Complexity is managed through clear architecture and documentation.

### Trade-off: Configuration Flexibility vs. Simplicity

**Choice**: Three-tier API architecture

**Cost**: More surfaces to maintain, more documentation needed

**Benefit**: Each user type gets optimized interface

**Justification**: Eliminates false dichotomy between power and simplicity. Maintenance cost is offset by user satisfaction and broader adoption.

### Trade-off: Plugin Architecture vs. Time to Market

**Choice**: Full plugin architecture from the start

**Cost**: Longer initial development time

**Benefit**: No vendor lock-in, community extensibility, platform positioning, easier maintenance, less technical debt

**Justification**: Evidence from successful platforms (VS Code, FastAPI) shows early investment in extensibility pays off. Aligns with Proven Patterns principle. Better long-term to keep technical debt low.


### Trade-off: Testing Coverage vs. Development Speed

**Choice**: Effectiveness over coverage

**Cost**: Lower coverage metrics, potential for blind spots

**Benefit**: Faster iteration, focus on user-affecting behavior

**Justification**: Constitutional Principle IV (Testing Philosophy) - one realistic integration test beats ten implementation tests. Coverage metrics don't prevent user-affecting bugs.

### Constraint: Python ≥3.12 Required

**Reason**: Modern type syntax, performance improvements

**Impact**: Excludes some legacy environments

**Mitigation**: Clear documentation, most users on 3.12+ already

**Justification**: Modern syntax enables better type safety and code clarity (Simplicity Through Architecture)

### Constraint: MCP Protocol Dependency

**Reason**: Primary interface for AI agents

**Impact**: Tied to MCP ecosystem evolution

**Mitigation**: Abstract MCP-specific code, design for protocol flexibility (MCP is a transport, not the product)

**Justification**: MCP is the emerging standard for agent tools. CodeWeaver designed to work with and without MCP.

### Constraint: Embedding Provider Costs

**Reason**: Semantic search requires embedding models

**Impact**: Cloud providers have API costs

**Mitigation**: Local embedding options (fastembed), caching strategies, token budgeting

**Justification**: Value proposition (60-80% context reduction) significantly outweighs embedding costs; free tiers keep use free or very cheap for most independent/open source developers.

---

## References

### Primary Documents

- [Project Constitution](.specify/memory/constitution.md) - Authoritative governance
- [README.md](README.md) - Project overview and quickstart
- [PRODUCT.md](PRODUCT.md) - Product vision and strategy
- [CODE_STYLE.md](CODE_STYLE.md) - Code style and patterns
- [AGENTS.md](AGENTS.md) - Agent development guidelines
- [IMPLEMENTATION_PLAN.md](plans/IMPLEMENTATION_PLAN.md) - Technical roadmap

### Architecture Decisions Evolution

As the project evolves, architectural decisions should be documented with:
- Context: What problem are we solving?
- Options: What alternatives were considered?
- Decision: What did we choose?
- Rationale: Why this choice? Which constitutional principles apply?
- Outcome: What were the results?

This document serves as the historical record of significant architectural decisions and should be updated as new patterns emerge.

---

**Document Maintenance**: This document should be updated when:
- New architectural patterns are established
- Significant technical decisions are made
- Constitutional principles are amended
- Design patterns evolve

**Version History**:
- v1.0.0 (2025-10-21): Initial unified architecture document
- v1.1.0 (2025-11-23): Updated to include recent design decisions and project structure changes.
