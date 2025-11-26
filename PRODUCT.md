<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# CodeWeaver: Product Overview

## Product Vision

### Mission
Bridge the gap between human (developer) expectations and AI agent capabilities through "exquisite context."

### Current Focus: Best-in-Class Agent Search (MVP)
**What We're Building Now**: A really fantastic agent search tool that delivers exquisite context through hybrid semantic search, AST-aware analysis, and agent-driven curation.

**Why This Matters**: This is the foundation. Without solving precision context delivery, everything else falls apart. We need to prove we can deliver exactly what agents need, nothing more, nothing less.

### Strategic Vision: The Context Platform
**Where We're Going**: CodeWeaver becomes the **context gatekeeper**—an intelligent middleman that tailors context for every agent interaction.

**The Core Insight**: The fundamental service isn't search—it's **context management**. Search is just the first use case.

### Evolution: From Search Tool to Context Platform

#### Phase 1: Search Excellence (Current - 2025)
**Goal**: Prove we can deliver precise, relevant context better than anyone else
- Hybrid semantic search with AST awareness, task and repo-aware response ranking
- Single-tool interface eliminating tool confusion
- Agent-driven curation using MCP sampling
- 60-80% context reduction over naive agentic discovery with >90% relevance

**Success Metric**: Developers choose CodeWeaver over built-in IDE search because agent results are measurably better.

#### Phase 2: Context Intelligence (2025-2026)
**Goal**: Integrate Thread for real-time semantic codebase understanding

**Thread Integration**:
- **What Thread Is**: Rust-based codebase intelligence tool creating real-time, editable semantic graphs of entire codebases (pre-release and paused while CodeWeaver achieves phase 1 and official release)
- **Why It Matters**: Move beyond static AST analysis to live semantic understanding
- **Open Core Strategy**: Thread is AGPL 3.0 (open source with competitive moat)
- **Technical Evolution**: Thread augments or replaces ast-grep, providing deeper semantic awareness

**Capabilities Unlocked**:
- Real-time code change propagation analysis
- Semantic relationship tracking (dependencies, call graphs, import hierarchies)
- Architectural pattern recognition and enforcement
- Live codebase health metrics

**Success Metric**: Context quality improves 40%+ through deeper semantic understanding; agents can reason about code architecture, not just search for snippets.

#### Phase 3: Unified Context Hub (2026+)
**Goal**: CodeWeaver becomes the MCP server *and* client—the central context orchestration layer

**The Problem We Solve**:
Current state: Developers load 10-100+ MCP tools (often with duplicate instances), each exposing multiple endpoints
- **Context Bloat**: 25K-40K+ tokens (20% of context window) just for tool descriptions
- **Context Poisoning**: Information overload misdirects agents
- **Cost**: ~$5 per conversation in unused tool prompt overhead
- **Cognitive Load**: Agents choose between similar tools instead of solving problems (more turns, more context, more time)

**The Solution: Context-Aware Tool Orchestration**

CodeWeaver sits between the agent and all other MCP tools:

```
┌─────────────────────────────────────────────────┐
│            AI Agent (Claude, GPT-5, etc.)        │
└────────────────────┬────────────────────────────┘
                     │
                     ▼
┌─────────────────────────────────────────────────┐
│          CodeWeaver Context Platform             │
│                                                  │
│  • Intelligent context tailoring per turn       │
│  • Tool exposure based on task context          │
│  • Unified search across all data sources       │
│  • Context budgeting and optimization           │
└────────────┬───────────┬────────────┬───────────┘
             │           │            │
             ▼           ▼            ▼
        ┌────────┐  ┌────────┐  ┌──────────┐
        │ Serena │  │ Tavily │  │  Other   │
        │  MCP   │  │  MCP   │  │ MCP Tools│
        └────────┘  └────────┘  └──────────┘
```

**How It Works**:
1. **Dynamic Tool Exposure**: CodeWeaver only exposes relevant tools based on current context and task
2. **Unified Search Interface**: One `find_code` tool searches across all data sources (codebase, docs, web, memory) (we may have to add a "change_code" tool...)
3. **Context Budgeting**: Intelligent token allocation across tool descriptions, search results, and conversation history
4. **Task-Aware Routing**: Agent requests "authentication patterns" → CodeWeaver determines whether to search code, docs, or web (or all three)

**Example Interaction**:
```
Agent: "How do we handle authentication?"

Without CodeWeaver Hub:
- Agent sees 50+ tools (search, grep, symbols, web, docs, memory...)
- Chooses wrong tool or makes multiple tool calls
- 40K tokens of tool descriptions on every turn
- Gets scattered results across multiple sources

With CodeWeaver Hub:
- Agent sees: find_code tool
- Makes one request with natural language
- CodeWeaver orchestrates: codebase search + docs lookup + examples from web + tool decision and selection
- Returns unified, ranked results with provenance, pre-configured tool exposure and calls
- 8K tokens total (tool descriptions + relevant context only)
```

**Capabilities**:
- **Selective Tool Exposure**: Only show tools relevant to current task context
- **Cross-Source Search**: Unified queries across codebase, documentation, web, team knowledge
- **Context Optimization**: Intelligent token budgeting per turn
- **Provenance Tracking**: Clear sourcing for all returned information
- **Memory Integration**: Learn from interaction patterns to improve relevance

**Success Metric Targets**: 
- 75%+ reduction in tool context use
- 50%+ increase in agent effectiveness (tbd: measurements)
- 80%+ reduction in context use over naive "read everything approach"

#### Phase 4: Context-as-a-Service (Future)
**Strategic Question**: How much is CodeWeaver vs. broader Knitli platform?

**Potential Models**:

**Open Source + SaaS Hybrid**:
- CodeWeaver core: Open source (MIT/Apache 2.0) - search and basic context management
- Thread: Open source (AGPL 3.0) - codebase intelligence with protective licensing
- Knitli Platform: Premium service for context-as-a-service with hosting, orchestration, team features

**Value Propositions**:
- **Self-Hosted (Free)**: Run CodeWeaver + Thread on your infrastructure, full control
- **Knitli Hosted (Paid)**: Managed context platform with SLA, team analytics, advanced orchestration
- **Enterprise**: Custom deployments, SSO, compliance, professional services

**Open Core Licensing Strategy**:
- **Permissive Core** (CodeWeaver): Maximum adoption, ecosystem growth
- **Protective Components** (Thread AGPL): Competitive moat—cloud providers can't just resell
- **Platform Services** (Knitli): Revenue model that doesn't restrict developer freedom. Use the Github (or Posthog, etc) marketing model (developer demand drives enterprise adoption) with minimal advertising/acquisition spend.

### Why This Vision Matters

**For Developers**: Single interface for all context needs, dramatically lower cognitive load and costs

**For Teams**: Unified context management across tools, codebases, and knowledge sources

**For the Ecosystem**: Open infrastructure that prevents vendor lock-in while supporting sustainable business models

**For AI Agents**: Purpose-built context delivery allowing them to focus on problem-solving, not tool orchestration

### Risk Mitigation

**Technical Risks**:
- **Complexity**: Phase 2-3 are significantly more complex than Phase 1; not a one person job!
- **Mitigation**: Prove search excellence first, build incrementally, validate at each phase

**Business Risks**:
- **Open source sustainability**: How to build business while keeping core (and plans like this) open (and, you know, have revenue... and eat)
- **Mitigation**: Open core strategy with AGPL protective licensing for key components

**Ecosystem Risks**:
- **MCP protocol evolution**: MCP is young and may change significantly
- **Mitigation**: Abstract MCP-specific code, design for protocol flexibility. CodeWeaver designed from start to work through MCP *and* independent of it.

**Competitive Risks**:
- **Large vendors**: Google, Microsoft, Meta could integrate similar capabilities, or integrate codeweaver themselves
- **Mitigation**: Open source moat, developer community, context expertise, faster iteration, being cool 😎

## The Problem We Solve

### Context Delivery Crisis in AI Coding

AI coding agents face a fundamental challenge: **too much irrelevant context**.

**The Impact:**
- **70-80% of returned code goes unused** by the agent
- **Token costs scale exponentially** with conversation length
- **Agents miss critical patterns** buried in noise and irrelevant results
- **Developers waste time** reviewing off-target suggestions and hallucinations and waiting for agents

**Root Causes:**

**1. Tool Confusion: Human APIs Overwhelm Agents**

Developers love flexibility and power—multiple specialized tools with rich options. AI agents need simplicity and clarity.

*The Problem:* Most MCP servers expose 5-20+ tools for code discovery (some even more...), forcing agents to choose *how* to get information before they can focus on *what* they need.

**Example:** [Serena MCP](https://github.com/oraios/serena) (excellent MCP tooling for agents):
- Exposes **19 total tools**
- **5 tools for search/discovery alone**: `find_file`, `list_dir`, `search_for_pattern`, `find_symbol`, `find_referencing_symbols`

  > Agent decision tree: *"Do I use Grep? Memory? List Files? Find Symbols? Search? Repository tool?"*

**Result:** Tool selection becomes a cognitive burden [^1]. Agents spend tokens and reasoning cycles choosing between tools instead of solving problems.

**2. Context Bloat: Tool Descriptions Scale Linearly, Value Doesn't**

Each tool requires detailed prompt instructions explaining usage, parameters, and when to use it.

**The Math:**
- Average developer MCP tool load: **25,000-40,000 tokens** (20% of Claude Sonnet 4.5's context window)
- Typical 20-turn conversation: **~$5 in API costs** just for tool prompts sent "just in case"
- Agent sees this bloat on *every single turn* whether tools are used or not

**Result:** Tool prompts misdirect agents, increase confusion, and waste money on unused context.

**3. Search Fragmentation: One Query, Multiple Tool Calls**

Current MCP tools split unified search concepts into separate tools:
- Semantic search → one tool
- Keyword search → different tool  
- Repository structure → another tool
- File trees → yet another tool

**Result:** Simple discovery requires orchestrating multiple tool calls, multiplying context overhead and increasing latency.

**4. The "Dump Everything" Fallback**

When tool confusion wins, agents default to the simplest option: **"read the entire file"**

**Reality Check:**
- File read: 2,000-10,000 tokens
- Actual need: single function or 5-10 lines
- Waste: 95%+ of context unused

Even with better tools available, cognitive overload from tool selection drives this inefficient pattern.

**5. Proprietary Lock-In: Walled Gardens and Redundant Indexes**

Modern IDEs have sophisticated semantic search—but lock it away:

**Examples:**
- **VS Code**: Exposes some tools to Copilot, but not publicly documented for other agents
- **Cursor**: Similar proprietary model with opaque data handling
- **Roo & others**: Each includes code indexing and discovery

**The Waste:** 
- Developers run 5-10 different indexes of the same codebase
- No data portability or user control
- Opaque data usage and processing
- Reinventing the wheel instead of building on shared infrastructure

**Why This Matters:** A single, solid open-source tool with a clear API could replace all these proprietary solutions while giving developers control over their code and data.

**Real-World Impact**:
```
Traditional Approach:
Query: "How do we handle authentication?"
→ Returns: 47 files, 12,000 lines, 45KB context
→ Agent uses: ~8 files, ~400 lines
→ Wasted: 85% of context, $0.15-$0.30 per query
→ Result: Slow, expensive, often misses key patterns

CodeWeaver Approach:
Query: "How do we handle authentication?"
→ Returns: 8 files, 450 lines, 12KB context
→ Agent uses: ~7 files, ~380 lines
→ Wasted: <20% of context, $0.03-$0.06 per query
→ Result: Fast, affordable, precise context
```

### Why Existing Solutions Fall Short

**LangChain/LlamaIndex**:
- Complex multi-tool interfaces increase cognitive load
- Generic RAG without code-aware chunking
- No semantic understanding of code structure

**IDE Extensions**:
- Tightly coupled to specific editors and tools
- No standalone context platform capability
- Limited to single codebase sources

**Custom RAG Implementations**:
- Reinventing semantic search and chunking
- No plugin architecture for extensibility
- Maintenance burden on each team

## Our Solution

### Core Product Principles

**1. AI-First Context**
Every feature enhances AI agent understanding of code through precise context delivery. We design APIs, documentation, and tooling with AI consumption as the primary interface.

**2. Proven Patterns Over Reinvention**
We leverage the FastAPI/pydantic ecosystem and established architectural patterns. Familiar interfaces reduce learning curve and increase adoption.

**3. Evidence-Based Development**
All technical decisions backed by verifiable evidence: documentation, testing, metrics, or reproducible demonstrations. No workarounds, no placeholder code.

**4. Testing Philosophy**
Effectiveness over coverage. We focus on critical behavior affecting user experience through realistic integration scenarios and input/output validation.

**5. Simplicity Through Architecture**
Transform complexity into clarity using simple modularity with extensible yet intuitive design where purpose is obvious.

### Key Product Differentiators

**Single-Tool Interface**
- One `find_code` tool vs. complex multi-endpoint APIs
- Natural language queries with optional structured filters
- Reduces cognitive load on both agents and developers

**Agent-Driven Curation**
- Uses MCP sampling to let agents curate their own context
- Separate agent instance evaluates needs without context pollution
- Improves precision by 40-60% over keyword matching alone

**Hybrid Search Foundation**
- Text search + semantic search + AST-aware analysis
- Unified task-aware ranking across multiple signals
- Span-based precision (exact line/column tracking)

**Platform Architecture**
- Pluggable embedding providers (10+ supported)
- Vendor-agnostic vector stores
- Extensible data sources beyond codebases
- Custom middleware and services via plugin system

### Three-Tier API Architecture

CodeWeaver exposes **three distinct API surfaces**, each optimized for its audience:

**1. Human API: Deep Configurability**
- **Interface**: Configuration files (`codeweaver.toml/yaml/json`), CLI commands, environment variables
- **Complexity**: High - expose full power and flexibility (with prebuilt pick-up-and-go configs)
- **Philosophy**: Humans want control, customization, and understanding of how things work
- **Surface Area**: Extensive
  - Provider selection and configuration (10+ embedding providers, multiple vector stores)
  - Chunking strategies and parameters
  - Ranking algorithms and weights
  - Token budgets and caching policies
  - Plugin architecture for custom middleware (via FastMCP)
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

**2. User Agent API: Radical Simplicity**
- **Interface**: MCP tools
- **Complexity**: Minimal - one primary tool
- **Philosophy**: Agents focus on *what* to find, not *how* to search
- **Surface Area**: 1-3 tools
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

**3. Context Agent API: Controlled Expansion**
- **Interface**: Extended MCP tools for context curation agents
- **Complexity**: Moderate - targeted tools for specific curation tasks
- **Philosophy**: Context agents need more capability than user agents, but still bounded
- **Surface Area**: 3-8 (goal: <= 5) specialized tools (examples are nominal and may be be further consolidated through graph orchestration strategies)
  - `find_code` - same as user agent
  - `get_semantic_neighbors` - explore related code
  - `get_call_graph` - understand execution flow
  - `get_import_tree` - track dependencies
  - `analyze_context_coverage` - assess completeness
  - `rank_results` - apply custom ranking logic
  - `filter_by_relevance` - refine result sets
  - `get_provenance` - understand information sources

**Example (MCP Sampling Flow)**:
```
1. User Agent requests: find_code("authentication")
2. CodeWeaver spawns Context Agent via MCP sampling
3. Context Agent assesses intent, scope, and task goals
4, Context agent uses:
   - find_code("authentication")
   - get_semantic_neighbors(top_results)
   - get_call_graph(middleware_functions)
   - analyze_context_coverage(gathered_context)
5. Context Agent curates and ranks final results
6. CodeWeaver returns refined context to User Agent
```

### Why This Architecture Matters

**Eliminates False Trade-off**:
Traditional thinking: "Powerful features OR simple interface—pick one."
CodeWeaver: "Powerful configuration for humans AND simple interface for agents."

**Each API Optimized for Its User**:
- **Humans**: Need to understand, configure, customize, debug, extend
- **User Agents**: Need to get work done without cognitive overhead
- **Context Agents**: Need targeted tools for sophisticated curation

**Addresses Different Pain Points**:
- **Human API** → Solves "locked into vendor decisions"
- **User Agent API** → Solves "tool confusion and context bloat"
- **Context Agent API** → Enables "intelligent curation without exposing complexity to end user"

**Enables Platform Evolution**:
- Phase 1-2: All three APIs serve single CodeWeaver instance
- Phase 3: Context Agent API becomes bridge to other MCP tools
- Phase 4: Platform can expose different capability levels (free vs. paid)

### API Design Principles

**For Human API**:
- Comprehensive documentation with examples
- Sensible defaults that work out-of-box
- Clear error messages guiding to solutions
- Progressive disclosure (simple → advanced)

**For User Agent API**:
- Natural language queries (no rigid syntax)
- Optional parameters (query alone should work)
- Self-documenting tool descriptions
- Predictable, structured responses

**For Context Agent API**:
- Composable tools (outputs work as inputs)
- Transparent operations (provenance tracking)
- Bounded complexity (no exponential tool combinations)
- Well-defined contracts (clear input/output schemas)

## Target Users & Personas

### Primary Persona: Sarah the Senior Developer

**Background**:
- 8+ years experience, works on large codebases (50K-500K LOC)
- Uses AI coding assistants daily (Claude, GPT-4, Copilot)
- Frustrated by irrelevant suggestions and high token costs

**Goals**:
- Get precise answers about unfamiliar code quickly
- Reduce time spent on code discovery and navigation
- Lower AI assistant costs without sacrificing quality

**Pain Points**:
- AI assistants hallucinate because they lack proper context
- Searching codebase returns too many false positives
- Manual context gathering and delivery is time-consuming

**How CodeWeaver Helps**:
- Natural language queries return exactly relevant code
- Semantic search understands intent and structure, not just keywords
- Context reduction saves 60-80% on token costs

### Secondary Persona: Alex the Platform Builder

**Background**:
- Technical lead building internal developer tools
- Maintains custom AI workflows and automations
- Needs extensible solutions, not black boxes

**Goals**:
- Integrate semantic code search into existing tools
- Customize behavior for specific codebase patterns
- Support team's unique workflows and requirements

**Pain Points**:
- Off-the-shelf solutions don't fit specialized needs
- Building from scratch is expensive and time-consuming
- Vendor lock-in limits future flexibility

**How CodeWeaver Helps**:
- Plugin architecture enables custom providers
- MCP protocol integrates with any AI agent
- Open source with dual licensing (MIT OR Apache-2.0)

### Tertiary Persona: Morgan the Legacy Maintainer

**Background**:
- Maintains aging codebases with mixed technologies
- Works with languages poorly supported by modern tools
- Needs to onboard new developers to unfamiliar systems

**Goals**:
- Make legacy code discoverable and understandable
- Support for older or niche programming languages
- Reduce knowledge transfer burden

**Pain Points**:
- Modern AI tools ignore COBOL, Pascal, Fortran codebases
- Junior developers struggle to navigate undocumented systems
- Tribal knowledge concentrated in few senior engineers

**How CodeWeaver Helps**:
- 26 languages with full AST-aware semantic analysis
- 170+ languages with sophisticated heuristic chunking (including COBOL, Pascal and Fortran)
- Custom language support via configuration (simple delimiter definitions or code family assignment)
- (Future) plug in *any tree-sitter grammar* (60+ mature grammars). 
- Precise line/column references help code understanding

## Success Metrics

### User Adoption Metrics
- **Setup completion rate**: Target >90% within 10 minutes
- **Time to first successful query**: Target <5 minutes
- **Weekly active usage**: Target 3+ queries per developer per week
- **AI adoption**: Evidence that AI's choose CodeWeaver over other tools for discovery tasks (need to figure out measurement -- the full MCP environment isn't exposed through the MCP interface).
- **Retention**: Target 80% month-over-month retention

### Quality Metrics
- **Search relevance**: Target >90% of results rated relevant
- **Context token reduction**: Target >90% over traditional search, >60% over naive RAG
- **Query latency**: Target <2 seconds for typical queries
- **Precision improvement**: Target 40-60% vs. keyword-only search

### Platform Metrics
- **Provider adoption**: Track which embedding/vector store providers users choose
- **Custom extension usage**: % of deployments with custom providers/middleware
- **Language coverage effectiveness**: Relevance scores across all 26+ semantically supported languages and 170+ secondary languages.
- **Background indexing performance**: Files indexed per second, incremental update latency

### Business Metrics
- **Cost per query**: Target <$0.10 per semantic search query (naive multi-step queries ~$0.20-$0.30)
- **Token cost savings**: Calculate savings vs. traditional "dump context" and RAG approaches (initial implementation already in [`statistics.py`](src/codeweaver/common/statistics.py)
- **Developer productivity gain**: Time saved on code discovery tasks (All requests/responses timed in statistics module)
- **Infrastructure efficiency**: Resource usage per indexed codebase

Open questions/decisions on measurement:
  - How would we best estimate "cumulative savings" (i.e. we can compare savings from what we retrieve vs what we deliver, but that savings should be compounded over the life of the conversation -- MCP doesn't expose that).
  - Without getting access to *non-CodeWeaver* tasks, how do we get data on time saved?
  - What's the best approach to getting data on usage *before* and *after* CodeWeaver?
  - We simply need to adopt a best-guess estimation for some of these and document our reasoning.

## Competitive Positioning

### vs. LangChain
**LangChain Strengths**: Mature ecosystem, broad LLM support, extensive documentation
**CodeWeaver Advantages**:
- Single-tool simplicity vs. complex chains
- Code-aware semantic chunking vs. generic text splitting
- Span-based precision (line/column) vs. document chunks
- Plugin architecture vs. monolithic framework

### vs. LlamaIndex
**LlamaIndex Strengths**: Purpose-built for RAG, strong indexing capabilities
**CodeWeaver Advantages**:
- AST-aware code understanding vs. generic document indexing
- Agent-driven curation using MCP sampling
- MCP protocol integration for AI agent workflows
- Semantic-awareness for 26 languages, 170+ language support including legacy codebases
- Tailored ranking strategies for specific development tasks.

### vs. Custom RAG Implementations
**Custom RAG Strengths**: Tailored to specific needs, full control
**CodeWeaver Advantages**:
- Production-ready with proven patterns
- Plugin architecture provides customization without reinvention
- Active development and community support
- Dual-licensed for maximum flexibility

### vs. IDE-Embedded and Agent Tool-Embedded Solutions (Cursor, GitHub Copilot, Claude Code, Roo)
**IDE Solutions Strengths**: Tight editor integration, seamless UX
**CodeWeaver Advantages**:
- Editor-agnostic via HTTP and MCP protocols, and through CLI
- Standalone context platform capability
- Support for multiple data sources beyond single codebase
- Programmatic access for automation and tooling
- Focus on doing one thing exceptionally

## Product Roadmap

### Phase 1: Core Integration (Current Focus)
**Timeline**: Q4 2025
**Goals**: Production-ready MCP server with working `find_code` tool

**Deliverables**:
- Complete provider registry and statistics integration
- Complete 'context agent' integration for agentic context curation
- Working `find_code` over text search with filter integration
- Basic test coverage for core workflows
- Documentation for installation and basic usage

**Success Criteria**:
- <5 minute setup time for recommended configuration
- Text search returning relevant results for common queries
- Stable MCP server with proper error handling

### Phase 2: Semantic Search (Next)
**Timeline**: Q4 2025-Q1 2026
**Goals**: Full hybrid search with semantic understanding

**Deliverables**:
- Integrate embeddings (VoyageAI, fastembed) and Qdrant vector store
- AST-aware chunking with semantic metadata
- Background indexing with watchfiles for incremental updates
- Hybrid search with unified ranking (text + semantic + AST)
- Query intent analysis using agent providers

**Success Criteria**:
- 60-80% context token reduction vs. keyword-only search
- >90% search relevance rating from users
- <2 second query latency for typical codebases
- Background indexing handles 1000+ file updates/minute

### Phase 3: Advanced Capabilities (Future)
**Timeline**: Q3-Q4 2025
**Goals**: Production-grade performance and extensibility

**Deliverables**:
- pydantic-graph pipelines for multi-stage workflows
- Multi-signal ranking (semantic + syntactic + keyword + usage patterns)
- Performance optimization and intelligent caching strategies
- Enhanced metadata leverage (import graphs, call hierarchies)
- Comprehensive test coverage with benchmarks
- Telemetry and observability dashboards

**Success Criteria**:
- <1 second query latency for cached frequent queries
- Support for codebases up to 1M+ lines of code
- Plugin marketplace with community extensions
- 95%+ test coverage for critical paths

### Future Possibilities (Exploration)
- **Multi-Repository Search**: Unified context across microservices and dependencies
- **Temporal Code Analysis**: Search across git history and branches
- **Code Pattern Learning**: Identify project-specific patterns and idioms
- **External API Integration**: Combine codebase context with external documentation
- **Team Knowledge Graphs**: Capture and surface team expertise and decisions

## User Journey

### Discovery → First Success (Target: <10 minutes)

**Step 1: Discovery** (30 seconds)
- User hears about CodeWeaver through:
  - MCP server listings
  - AI agent community forums
  - Developer tool reviews
  - GitHub trending repositories

**Step 2: Evaluation** (2 minutes)
- Reads README to understand value proposition
- Reviews supported languages and providers
- Checks installation requirements
- Decides on installation tier (recommended, local-only, or a-la-carte)

**Step 3: Installation** (3 minutes)
```bash
uv pip install "code-weaver[recommended]"
```
- Installs successfully with clear progress indicators
- Receives setup guidance for API keys (if needed)
- Runs basic configuration validation

**Step 4: First Query** (2 minutes)
```bash
codeweaver search "how do we handle user authentication?"
```
- Sees relevant results immediately (even without full indexing)
- Results include precise file:line references
- Context snippets show actual code patterns

**Step 5: MCP Integration** (2 minutes)
```bash
codeweaver server
```
- Adds to Claude Desktop / AI agent configuration
- Tests `find_code` tool through agent interface
- Sees agent successfully retrieve targeted context

**Success Moment**:
User's AI agent gives accurate, context-aware answer to question about unfamiliar codebase section without hallucination or irrelevant suggestions.

### Continued Usage → Power User (Target: 1-2 weeks)

**Week 1: Basic Adoption**
- Daily queries through CLI or MCP
- Learns natural language query patterns
- Discovers filter capabilities (language, file_type, date ranges)
- Observes token cost savings in AI conversations

**Week 2: Advanced Features**
- Configures custom providers for specific needs
- Sets up background indexing for active projects
- Integrates with team workflows and CI/CD
- Explores custom middleware for team-specific patterns

**Power User Capabilities**:
- Custom embedding providers for domain-specific code
- Reranking models tuned to project conventions
- Integration with documentation and external APIs
- Automated context delivery for routine tasks

## Go-to-Market Strategy

### Phase 1: Developer Community (Current)
**Channels**:
- GitHub repository with professional governance
- MCP server listings and directories
- Developer community forums (Reddit, HN, Discord)
- Technical blog posts and tutorials

**Messaging**:
- "Precise AI context without the token waste"
- "Single tool, infinite extensibility"
- "From COBOL to Rust: context for every codebase"

### Phase 2: Platform Adoption
**Channels**:
- Integration partnerships (Claude, MCP ecosystem partners)
- Developer tool reviews and comparisons
- Conference talks and workshops
- Case studies and success stories

**Messaging**:
- "The context platform for AI-first development"
- "Build on proven patterns, extend for your needs"
- "Open source foundation, enterprise-ready"

### Phase 3: Enterprise & Teams
**Channels**:
- Enterprise feature development (SSO, audit logs, team analytics)
- Sales and customer success programs
- Training and certification programs
- Professional services and support

**Messaging**:
- "Secure, compliant AI context for enterprise codebases"
- "Reduce AI costs while improving code quality"
- "Platform for internal developer productivity tools"

## Open Questions & Areas for Research

### User Research Needed
1. **Query Patterns**: What natural language patterns do developers use when searching code? Agents?
2. **Context Preferences**: How much context is "just right" for different task types?
3. **Integration Workflows**: How do teams want to integrate CodeWeaver into existing tools?
4. **Pricing Sensitivity**: What's the value perception for token savings vs. subscription costs?

### Technical Validation
1. **Scale Testing**: Performance characteristics at 100K, 500K, 1M+ LOC codebases?
2. **Provider Comparison**: Which embedding models perform best for code vs. general text?
3. **Caching Strategies**: Optimal cache invalidation and update strategies?
4. **Ranking Algorithms**: How to weight semantic vs. keyword vs. AST signals?

### Market Understanding
1. **Competitive Response**: How will established players (LangChain, LlamaIndex) respond?
2. **MCP Ecosystem**: How fast will MCP adoption grow in AI agent space?
3. **Platform Revenue**: What business models work for developer infrastructure?
4. **Partnership Opportunities**: Which integrations provide most user value?

## Product Principles in Action

### Example: Single-Tool Interface Decision

**Challenge**: How many tools should CodeWeaver expose via MCP?

**Options Considered**:
1. Multiple specialized tools (`search_code`, `get_definitions`, `find_references`, `get_imports`)
2. Single flexible tool (`find_code` with intent parameter)
3. Agent-specific tools (`quick_search`, `deep_analysis`, `context_gathering`)

**Decision**: Single `find_code` tool with optional intent parameter

**Rationale** (Constitutional Principles Applied):
- **Simplicity Through Architecture**: One interface reduces cognitive load
- **AI-First Context**: Agents can express natural language queries without tool selection
- **Proven Patterns**: FastAPI-style flexible parameters vs. endpoint proliferation
- **Evidence-Based**: User testing showed tool selection added complexity without value

**Outcome**:
- Lower barrier to adoption (one tool to learn)
- Cleaner agent prompts (no tool selection logic)
- Easier to extend (intent parameter can evolve)
- Better user feedback (focus on single interface quality)

### Example: Plugin Architecture Investment

**Challenge**: Build extensibility now or ship faster with fixed providers?

**Options Considered**:
1. Hardcode VoyageAI + Qdrant, ship immediately
2. Abstract providers minimally, add more later
3. Full plugin architecture from start

**Decision**: Full plugin architecture (Constitutional Principle II: Proven Patterns)

**Rationale**:
- FastAPI demonstrates value of dependency injection and extensibility
- User research showed diverse infrastructure preferences, particularly among enterprise developers tied to company decisions (AWS, GCP, local-only)
- Platform thinking: enable ecosystem to extend vs. us building everything
- Evidence: Successful platforms (VS Code, Babel) prioritize plugins early

**Outcome**:
- 10+ embedding providers supported
- Vendor independence (no lock-in)
- Community can contribute custom providers
- Platform positioning vs. point solution

---

## Contact & Resources

**Product Feedback**: https://github.com/knitli/codeweaver/discussions
**Bug Reports**: https://github.com/knitli/codeweaver/issues
**Knitli Home**: https://knitli.com
**Documentation**: https://dev.knitli.com/codeweaver (coming soon)
**Community**: [Email me](mailto:adam@knit.li)!

**For Platform Developers**: See [CONTRIBUTING.md](CONTRIBUTING.md) for extension development guides

**For Enterprise Inquiries**: Contact [enterprise@knit.li](mailto:enterprise@knit.li) for SSO, SLA, and professional services

[^1]: We know that agents don't experience "cognitive burden" like humans do, but the effects of context noise and bloat produce very similar outcomes. It's a helpful metaphor.