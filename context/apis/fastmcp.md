<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# FastMCP v2.10.6 - Complete API Research Report

*Expert API Analyst Research - Foundation for CodeWeaver Clean Rebuild*

## Summary

FastMCP v2.10.6 is a modern Python framework that provides a FastAPI-like experience for building Model Context Protocol (MCP) servers. It abstracts away the complexity of MCP protocol implementation while offering powerful features including dependency injection, middleware, authentication, custom HTTP routes, and advanced AI capabilities like sampling and elicitation.

**Key Architectural Benefits for CodeWeaver:**
- **Unified Server Architecture**: Single codebase handling both MCP protocol and custom HTTP endpoints
- **Direct Implementation Patterns**: Avoids over-abstraction through decorator-based tool definition
- **Advanced AI Integration**: Built-in sampling/elicitation for LLM-driven workflows
- **Pydantic Ecosystem Integration**: Native support for pydantic-settings, pydantic-ai patterns
- **Flexible Transport Support**: stdio, HTTP/SSE (deprecated), StreamableHTTP with automatic protocol handling

## Core Types

### Server and Context Types

```python
from fastmcp import FastMCP
from fastmcp.context import Context
from pydantic import BaseModel
from typing import Any, Dict, Optional

# Core server instance
app = FastMCP("codeweaver")

# Context injection - primary dependency injection mechanism
@mcp.tool()
async def find_code(query: str, context: Context) -> str:
    """Context provides access to all server capabilities"""
    # context.request_id, context.client_info, context.server
    pass

# Settings integration via pydantic-settings
from pydantic_settings import BaseSettings

class CodeWeaverSettings(BaseSettings):
    embedding_provider: str = "voyage"
    vector_store_url: str = "http://localhost:6333"
    max_tokens: int = 10000
    
    class Config:
        env_prefix = "CODEWEAVER_"
```

### Tool and Resource Definition

```python
# Tool definition with Context injection
@mcp.tool()
async def find_code(
    query: str,
    intent: Optional[str] = None,
    token_limit: int = 10000,
    context: Context = None
) -> Dict[str, Any]:
    """
    Single interface for intelligent codebase context discovery
    
    Args:
        query: Description of needed information or task context
        intent: Optional task intent (familiarize, implement, debug, etc.)
        token_limit: Maximum tokens in response (respects server config limits)
    """
    return {"context": "...", "sources": [...]}

# Resource definition for dynamic content
from fastmcp.resources import Resource

@mcp.resource(uri_template="codebase://project/{project_id}/files")
async def codebase_files(project_id: str, context: Context) -> Resource:
    """Dynamic resource for project file structure"""
    return Resource(
        uri=f"codebase://project/{project_id}/files",
        name=f"Files in {project_id}",
        mimeType="application/json",
        text=await get_project_files(project_id)
    )
```

### Authentication and Middleware

```python
from fastmcp.auth import BearerAuthProvider, AuthResult
from fastmcp.middleware import Middleware

# Custom authentication
class CodeWeaverAuth(BearerAuthProvider):
    async def authenticate(self, token: str, context: Context) -> AuthResult:
        # Validate API key, return scopes
        if await validate_token(token):
            return AuthResult(
                success=True,
                scopes=["read:codebase", "embed:generate", "search:execute"]
            )
        return AuthResult(success=False, error="Invalid token")

# Custom middleware
class IndexingMiddleware(Middleware):
    async def __call__(self, request, context: Context, next_handler):
        # Pre-request: Check if indexing is current
        if await needs_reindexing(context):
            await trigger_background_indexing()
        
        response = await next_handler(request, context)
        
        # Post-request: Update usage metrics
        await log_usage_metrics(context, response)
        return response

# Apply to server
app.add_auth_provider(CodeWeaverAuth())
app.add_middleware(IndexingMiddleware())
```

## Signatures

### Core Server Methods

```python
class FastMCP:
    def __init__(
        self,
        name: str,
        version: str = "1.0.0",
        description: Optional[str] = None,
        settings: Optional[BaseSettings] = None
    ) -> None: ...
    
    # Tool registration
    def tool(
        self,
        name: Optional[str] = None,
        description: Optional[str] = None,
        schema: Optional[Dict] = None
    ) -> Callable: ...
    
    # Resource registration  
    def resource(
        self,
        uri_template: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        mimeType: str = "text/plain"
    ) -> Callable: ...
    
    # HTTP route registration (custom endpoints)
    def get(self, path: str) -> Callable: ...
    def post(self, path: str) -> Callable: ...
    
    # Middleware and auth
    def add_middleware(self, middleware: Middleware) -> None: ...
    def add_auth_provider(self, provider: AuthProvider) -> None: ...
    
    # Server composition
    def mount(self, path: str, app: FastMCP) -> None: ...
    
    # Execution
    async def run(
        self,
        transport: str = "stdio",
        host: str = "localhost", 
        port: int = 8000
    ) -> None: ...
```

### Context Object Interface

```python
class Context:
    # Request metadata
    request_id: str
    client_info: Optional[Dict[str, Any]]
    
    # Server access
    server: FastMCP
    settings: BaseSettings
    
    # Authentication state
    auth_result: Optional[AuthResult]
    scopes: List[str]
    
    # AI capabilities
    async def sample(
        self,
        messages: List[Dict],
        model: str = "default",
        max_tokens: int = 1000,
        temperature: float = 0.7
    ) -> str: ...
    
    async def elicit(
        self,
        prompt: str,
        schema: Optional[Dict] = None
    ) -> Dict[str, Any]: ...
    
    # Logging and observability
    def log_info(self, message: str, **kwargs) -> None: ...
    def log_error(self, message: str, error: Exception = None) -> None: ...
```

### Advanced Features

```python
# Sampling for LLM-driven workflows
async def intelligent_intent_analysis(query: str, context: Context) -> Dict:
    messages = [
        {"role": "system", "content": "You are a code intent analyzer..."},
        {"role": "user", "content": f"Analyze this query: {query}"}
    ]
    
    response = await context.sample(
        messages=messages,
        model="anthropic/claude-3-sonnet-20241022",
        max_tokens=500,
        temperature=0.3
    )
    
    return {"intent": response, "confidence": 0.95}

# Elicitation for interactive clarification
async def clarify_search_parameters(initial_query: str, context: Context) -> Dict:
    schema = {
        "type": "object",
        "properties": {
            "refined_query": {"type": "string"},
            "file_types": {"type": "array", "items": {"type": "string"}},
            "search_scope": {"type": "string", "enum": ["current", "dependencies", "all"]}
        },
        "required": ["refined_query"]
    }
    
    return await context.elicit(
        prompt=f"Please refine this search query for better results: {initial_query}",
        schema=schema
    )
```

## Type Graph

```mermaid
graph TD
    A[FastMCP Server] --> B[Tool Registry]
    A --> C[Resource Registry]
    A --> D[Middleware Stack]
    A --> E[Auth Providers]
    A --> F[HTTP Router]
    
    B --> G[@mcp.tool Decorators]
    C --> H[@mcp.resource Decorators]
    D --> I[Custom Middleware]
    E --> J[Bearer/JWT/OAuth]
    F --> K[Custom Routes]
    
    G --> L[Context Injection]
    H --> L
    I --> L
    
    L --> M[Sampling API]
    L --> N[Elicitation API]
    L --> O[Server State]
    L --> P[Settings Access]
    
    M --> Q[LLM Integration]
    N --> Q
    
    R[Pydantic Settings] --> A
    S[BaseModel Schemas] --> G
    S --> H
    
    T[Transport Layer] --> A
    T --> U[stdio]
    T --> V[HTTP/SSE]
    T --> W[StreamableHTTP]
```

## Request/Response Schemas

### MCP Tool Execution Flow

[!NOTE]


```python
# Incoming MCP tool call
{
    "jsonrpc": "2.0",
    "id": "req-123",
    "method": "tools/call",
    "params": {
        "name": "find_code",
        "arguments": {
            "query": "authentication middleware patterns",
            "intent": "implement",
            "token_limit": 5000
        }
    }
}

# Tool response
{
    "jsonrpc": "2.0",
    "id": "req-123",
    "result": {
        "content": [
            {
                "type": "text",
                "text": "Found 3 authentication patterns:\n\n1. JWT Bearer Token Middleware..."
            }
        ],
        "isError": false
    }
}
```

### Custom HTTP Endpoint Flow

```python
# Admin dashboard endpoint
@app.get("/admin/stats")
async def get_server_stats(context: Context) -> Dict[str, Any]:
    if "admin:read" not in context.scopes:
        raise HTTPException(403, "Insufficient permissions")
    
    return {
        "tools_called": await get_tool_call_count(),
        "active_sessions": await get_active_session_count(),
        "index_status": await get_indexing_status()
    }

# HTTP Response
{
    "tools_called": 1247,
    "active_sessions": 12,
    "index_status": {
        "last_updated": "2024-01-15T10:30:00Z",
        "files_indexed": 2840,
        "embeddings_count": 15670
    }
}
```

### Sampling/Elicitation Schemas

```python
# Sampling request (internal)
sampling_request = {
    "messages": [
        {"role": "system", "content": "You analyze code queries..."},
        {"role": "user", "content": "How do I implement rate limiting?"}
    ],
    "model": "anthropic/claude-3-sonnet-20241022",
    "max_tokens": 1000,
    "temperature": 0.7
}

# Elicitation request (interactive)
elicitation_request = {
    "prompt": "Please specify the type of authentication you need",
    "schema": {
        "type": "object",
        "properties": {
            "auth_type": {
                "type": "string",
                "enum": ["jwt", "oauth", "api_key", "session"]
            },
            "security_level": {
                "type": "string",
                "enum": ["basic", "standard", "high_security"]
            }
        },
        "required": ["auth_type"]
    }
}
```

## Implementation Patterns

### 1. Server Bootstrap Pattern

> [!NOTE]
> FastMCP also uses `pydantic-settings` for configuration. It may make more sense to subclass FastMCP's BaseSettings object -- `fastmcp.settings.Settings`. We could protect attributes required for CodeWeaver and expose others as config options directly in CodeWeaver's config. If we did that, suggest also wrapping `fastmcp.settings.ExtendedEnvSettingsSource` to translate equivalent `CW_` prefixed env vars to `FASTMCP_` to provide a unified config surface.

```python
# main.py - CodeWeaver server setup
from fastmcp import FastMCP
from pydantic_settings import BaseSettings
import asyncio

class CodeWeaverSettings(BaseSettings):
    # Core settings
    server_name: str = "CodeWeaver"
    version: str = "0.1.0"
    
    # Vector store
    qdrant_url: str = "http://localhost:6333"
    collection_name: str = "codebase"
    
    # Embedding provider
    voyage_api_key: str = ""
    embedding_model: str = "voyage-code-3"
    
    # Search settings
    max_search_results: int = 50
    similarity_threshold: float = 0.7
    
    class Config:
        env_prefix = "CODEWEAVER_"
        env_file = ".env"

async def create_server() -> FastMCP:
    settings = CodeWeaverSettings()
    app = FastMCP(
        name=settings.server_name,
        version=settings.version,
        description="Intelligent codebase context discovery",
        settings=settings
    )
    
    # Register core components
    await setup_tools(app)
    await setup_resources(app) 
    await setup_middleware(app)
    await setup_custom_routes(app)
    
    return app

if __name__ == "__main__":
    app = asyncio.run(create_server())
    asyncio.run(app.run(transport="stdio"))
```

### 2. Tool Implementation Pattern

```python
# tools/find_code.py - Core CodeWeaver tool
from fastmcp import FastMCP
from fastmcp.context import Context
from typing import Any
from pydantic import BaseModel, Field

class CodeSearchResult(BaseModel):
    content: str = Field(description="Relevant code context")
    file_path: str = Field(description="Source file path")
    line_range: tuple[int, int] = Field(description="Start and end line numbers")
    confidence: float = Field(description="Relevance confidence score")
    metadata: Dict[str, Any] = Field(default_factory=dict)

class FindCodeResponseSummary(BaseModel):
    results: List[CodeSearchResult]
    total_tokens: int
    search_strategy: str
    suggestions: List[str] = Field(default_factory=list)

@app.tool()
async def find_code(
    query: str = Field(description="Description of needed information or task context"),
    intent: Optional[str] = Field(None, description="Task intent: familiarize, implement, debug, optimize"),
    token_limit: int = Field(10000, description="Maximum tokens in response"),
    file_types: Optional[List[str]] = Field(None, description="Restrict to specific file types"),
    context: Context = None
) -> FindCodeResponseSummary:
    """
    Single interface for intelligent codebase context discovery.
    
    Uses multi-stage resolution:
    1. Intent analysis and strategy selection
    2. Multi-source data retrieval (vector search, AST analysis, file discovery)
    3. Intelligent ranking and context assembly
    4. Token-budget-aware response construction
    """
    
    # Intent analysis using sampling
    if context and intent is None:
        intent_analysis = await analyze_intent(query, context)
        intent = intent_analysis.get("intent", "general")
        context.log_info(f"Inferred intent: {intent}")
    
    # Strategy selection based on intent
    strategy = select_search_strategy(intent, query, token_limit)
    context.log_info(f"Using search strategy: {strategy}")
    
    # Multi-source retrieval
    results = await execute_search_strategy(
        strategy=strategy,
        query=query,
        file_types=file_types,
        context=context
    )
    
    # Token-aware response assembly
    response = await assemble_response(
        results=results,
        token_limit=token_limit,
        strategy=strategy,
        context=context
    )
    
    return response

async def analyze_intent(query: str, context: Context) -> Dict[str, Any]:
    """Use sampling to analyze user intent"""
    messages = [
        {
            "role": "system", 
            "content": """Analyze the user's query to determine their intent.
            
            Intent types:
            - familiarize: Understanding codebase structure, patterns, conventions
            - implement: Creating new features, adding functionality
            - debug: Finding and fixing bugs, troubleshooting issues  
            - optimize: Performance improvements, refactoring
            - document: Understanding for documentation purposes
            - test: Writing tests, understanding test patterns
            
            Return JSON with 'intent' and 'confidence' fields."""
        },
        {"role": "user", "content": f"Query: {query}"}
    ]
    
    response = await context.sample(
        messages=messages,
        max_tokens=200,
        temperature=0.3
    )
    
    try:
        import json
        return json.loads(response)
    except:
        return {"intent": "general", "confidence": 0.5}
```

### 3. Middleware Pattern

```python
# middleware/indexing.py - Background indexing middleware
from fastmcp.middleware import Middleware
from fastmcp.context import Context
import asyncio
from datetime import datetime, timedelta

class IndexingMiddleware(Middleware):
    def __init__(self, check_interval: int = 300):  # 5 minutes
        self.check_interval = check_interval
        self.last_check = datetime.now() - timedelta(seconds=check_interval)
    
    async def __call__(self, request, context: Context, next_handler):
        # Pre-request: Check if indexing is needed
        if await self._should_check_indexing():
            asyncio.create_task(self._check_and_update_index(context))
            self.last_check = datetime.now()
        
        # Process request
        response = await next_handler(request, context)
        
        # Post-request: Log usage for future optimizations
        await self._log_usage_metrics(request, response, context)
        
        return response
    
    async def _should_check_indexing(self) -> bool:
        now = datetime.now()
        return (now - self.last_check).seconds >= self.check_interval
    
    async def _check_and_update_index(self, context: Context):
        """Background task to update index if needed"""
        try:
            settings = context.settings
            
            # Check for file system changes
            if await self._has_filesystem_changes():
                context.log_info("Filesystem changes detected, starting background indexing")
                await self._trigger_incremental_indexing(context)
            
        except Exception as e:
            context.log_error("Error in background indexing check", error=e)
    
    async def _log_usage_metrics(self, request, response, context: Context):
        """Log usage patterns for optimization"""
        # Implementation would log to PostHog or similar
        pass
```

### 4. Server Composition Pattern

> [!NOTE]
> FastMCP recommends against trying to apply `@resource`, `@tool`, or `@prompt` decorators to class methods. Instead, use a decorated helper function to call the method. 

```python
# composition/server_structure.py - Modular server composition
from enum import Enum, unique

from fastmcp import FastMCP, Context

@unique
class Focus(Enum):
    FAMILIARIZE = "familiarize",
    UNDERSTAND = "understand",
    IMPLEMENT = "implement",
    DESIGN = "design",
    DEBUG = "debug",
    DOCUMENT = "document"

async def create_composed_server() -> FastMCP:
    # Main server
    main_app = FastMCP("codeweaver-main")
    
    # Core search service
    search_app = FastMCP("codeweaver-search")
    await setup_search_tools(search_app)
    
    # Indexing service  
    indexing_app = FastMCP("codeweaver-indexing")
    await setup_indexing_tools(indexing_app)
    
    # Analytics/admin service
    admin_app = FastMCP("codeweaver-admin")
    await setup_admin_routes(admin_app)
    
    # Mount services
    main_app.mount("/search", search_app)
    main_app.mount("/indexing", indexing_app)  
    main_app.mount("/admin", admin_app)
    
    # Add cross-cutting concerns to main app
    await setup_auth(main_app)
    await setup_monitoring_middleware(main_app)
    
    return main_app

# You can use tags to control how/when tools, resources, and prompts are exposed to agents.
# Here was use tags that could expose these internal tools to a Context agent
async def setup_search_tools(app: FastMCP):
    """Search-specific tools"""
    
    @app.tool(tags={"internal", "gather"})
    async def vector_search(query: str, limit: int = 10, context: Context | None = None):
        """Pure vector similarity search"""
        # Implementation
        pass
    
    @app.tool(tags={"internal", "gather"})
    async def semantic_search(query: str, context: Context | None = None):
        """AST-based semantic search"""
        # Implementation  
        pass

async def setup_indexing_tools(app: FastMCP):
    """Indexing-specific tools"""
    
    @app.tool(tags={"internal", "index"})  
    async def reindex_project(project_path: str, context: Context | None = None):
        """Full project reindexing"""
        # Implementation
        pass
    
    @app.tool(tags={"internal", "index"})
    async def incremental_index(changed_files: list[str], context: Context | None = None):
        """Incremental indexing of changed files"""
        # Implementation
        pass

@app.tool(tags={"external", "resolution"})
async def find_code(query: str, project: str, focus: Focus)

# the tool for the developer's agent
```
### 5. Settings Integration Pattern

> [!NOTE]
> Settings patterns were identified as part of research for FastMCP. Defer to pydantic-settings researcher for authoritative patterns
```python
# config/settings.py - Comprehensive settings with pydantic-settings
from typing import Literal
from pydantic_settings import BaseSettings, Field, SettingsConfigDict
from pyantic import model_validator
from pathlib import Path
import platform
import tomli_w

from codeweaver._settings import DEFAULT_IGNORE_PATTERNS, DEFAULT_PROVIDERS_SETTINGS, DEFAULT_STRATEGY_SETTINGS, Provider, ConfigurationRegistry, ProviderKind, PerformanceProfile, _BaseProviderSettings, get_project_name
from codeweaver._semantic_search import SemanticLanguage

# This should actually import from _settings because we would use it to define the base settings types there, like _BaseProvider, which would subclass BaseCodeWeaverSettings (which would be _BaseCodeWeaverSettings))
class BaseCodeWeaverSettings(BaseSettings):
    # see above note about possible subclassing fastmcp.settings.Settings instead
    model_config = SettingsConfigDict(
        env_file=(".env", ".env.dev", ".env.prod"),
        env_file_encoding="utf-8",
        env_prefix="CW_",
        case_sensitive=False,
        extra="ignore"
        env_nested_delimiter='__', 
        nested_model_default_partial_update=True,
        # this is notional, most likely you'd need to implement `PydanticBaseSettingsSource` classes for hierarchical config
        toml_file=(
                    (
                    (os.environ.get("LOCALAPPDATA"), os.environ.get("USERPROFILE"), str(Path("/ProgramData"))).replace("\\", "/") if "win" in platform.platform() else
                    (os.environ.get("XDG_CONFIG_HOME", f"{os.environ.get('HOME', '~')}/.config"))
                    )
                     + "codeweaver/config.toml"
                , 
                ".codeweaver.toml",
                ".codeweaver/config.toml",
                ".codeweaver.local.toml",
                ".codeweaver/local.config.toml"
                )
    )

class ProviderSettings(_BaseProvider):
    # e.g. `ProviderKind.Rerank`
    provider_kind: ProviderKind
    # e.g. `Provider.VOYAGE`
    provider: Provider
    timeout: int = 30
    api_key: str | None = None
    # Allow arbitrary settings that pass to the implementation, but inherit base key-values from Provider and ProviderKind, if applicable. 
    # In implementation it would be best to make `provider_settings` a discriminated union, while allowing developers to pass custom provider_settings, either by registering their own Provider/ProviderKind (probably best) or by assuming unknown key-values are for the implemented provider (which a developer can also create)
    settings: type[BaseCodeWeaverSettings] | None = None

    @model_validator(mode="before")
    @classmethod
    def validate(cls, data: dict[str, Any]) -> Any:
        if not isinstance(data, dict):
            raise CodeWeaverSettingsError("We didn't receive a valid dictionary (toml table/json object)")
        if "settings" in data and (provider := data.get("provider")) and (provider_kind := data.get("provider_kind")):
            merged_settings = provider.default_settings | provider_kind.default_settings | data.get("settings", {})
            model = ProviderConfigurationRegistry.get_model(provider, provider_kind).model_validate(merged_settings)
            return cls(provider_kind, provider, data.get("timeout", 30), data.get("api_key"))
        raise CodeWeaverSettingsError("missing required settings")


class CodeWeaverSettings(BaseCodeWeaverSettings):
    # Server identification
    _name: str = "CodeWeaver"
    _version: str = "0.1.0"
    _description: str = "Intelligent codebase context discovery"

    server_transport: Literal["stdio", "stream"] = "stdio"

    # ignore settings
    ignore_hidden: bool = True
    use_gitignore: bool = True
    ignore_patterns: tuple[str] = DEFAULT_IGNORE_PATTERNS

    include_patterns: tuple[str] | None = None # optional list of override patterns to force include

    max_file_size: int = 10_000_000  # ~10MB
    
    # Performance
    # an enum with set profiles
    performance_profile: PerformanceProfile = PerformanceProfile.BALANCED
    max_concurrent_requests: int = PerformanceProfile.BALANCED.max_concurrent_requests
    request_timeout: int = PerformanceProfile.BALANCED.request_timeout
    enable_caching: bool = PerformanceProfile.BALANCED.enable_caching
    cache_ttl: int = PerformanceProfile.BALANCED.cache_ttl
    
    # Telemetry (opt-out)
    enable_telemetry: bool = True
    # specific telemetry configuration would be in the Provider's settings
    custom_parser_patterns: tuple[str] | None = None

    providers: tuple[Provider] = DEFAULT_PROVIDERS_SETTINGS
    strategies: tuple[Strategy] = DEFAULT_STRATEGIES_SETTINGS
      
    
    def save_to_file(self, path: Path) -> None:
        """Save current settings to TOML file"""
        # Note this is notional; tomli_w won't serialize enums...
        # you can either dump to json -> deserialize with tomllib -> serialize
        # or add a custom handler as an intermediate step
        config_dict = self.model_dump()
        with open(path, "wb") as f:
            tomli_w.dump(config_dict, f)


# Usage in main server
settings = CodeWeaverSettings()
app = FastMCP(
    name=settings.name,
    version=settings.version, 
    description=settings.description,
    settings=settings
)
```

## Differences vs Project Requirements

### Alignment Strengths

1. **Single Tool Interface**: FastMCP perfectly supports CodeWeaver's `find_code` single-tool strategy through the `@mcp.tool()` decorator with Context injection.

2. **Pydantic Integration**: Native pydantic-settings support aligns with CodeWeaver's configuration strategy and dependency plan.

3. **Advanced AI Capabilities**: Sampling and elicitation features directly support CodeWeaver's intent resolution and context refinement workflows.

4. **Extensibility without Over-Engineering**: FastMCP's decorator-based approach avoids the abstraction complexity that plagued the previous CodeWeaver implementation.

5. **Transport Flexibility**: Supports both stdio (for local development) and HTTP/StreamableHTTP (for remote deployment) without code changes.

### Key Implementation Considerations

1. **Context Injection Strategy**: CodeWeaver should leverage Context heavily for accessing server state, settings, and AI capabilities rather than global state.

2. **Middleware for Background Services**: Use FastMCP middleware for indexing, file watching, and telemetry rather than separate service layers.

3. **Settings Architecture**: Structure settings as nested pydantic models (VectorStoreSettings, EmbeddingSettings, etc.) rather than flat configuration.

4. **Custom Routes for Admin**: Utilize FastMCP's HTTP route capabilities for admin dashboards and debugging interfaces.

5. **Server Composition**: Consider modular composition (search service, indexing service, admin service) mounted on main server for better separation of concerns.

### Potential Gaps

1. **File System Monitoring**: FastMCP doesn't provide built-in file watching - CodeWeaver will need to integrate watchfiles directly.

2. **Vector Store Integration**: No built-in vector store abstraction - CodeWeaver needs to implement qdrant-client integration within tools.

3. **Background Task Management**: Limited background task coordination - may need asyncio task management for indexing workflows.

4. **CLI Integration**: FastMCP provides server capabilities but CodeWeaver needs separate cyclopts CLI integration.

## Sources

- FastMCP Documentation: https://docs.gofastmcp.com/
- FastMCP Server Implementation Guide: https://docs.gofastmcp.com/servers/
- FastMCP Tools and Resources: https://docs.gofastmcp.com/servers/tools-resources/
- FastMCP Context and Dependency Injection: https://docs.gofastmcp.com/servers/context/
- FastMCP Middleware System: https://docs.gofastmcp.com/servers/middleware/
- FastMCP Authentication: https://docs.gofastmcp.com/servers/auth/
- FastMCP Custom Routes: https://docs.gofastmcp.com/deployment/running-server/
- FastMCP Sampling and Elicitation: https://docs.gofastmcp.com/servers/sampling-elicitation/
- FastMCP Server Composition: https://docs.gofastmcp.com/servers/composition/
- Pydantic Settings Integration: https://docs.pydantic.dev/latest/concepts/pydantic_settings/
- MCP Protocol Specification: https://modelcontextprotocol.io/docs/
- FastMCP GitHub Repository: https://github.com/pydantic/fastmcp

---

*This research report provides the comprehensive technical foundation needed for CodeWeaver's clean rebuild using FastMCP v2.10.6. All implementation patterns are designed to avoid over-abstraction while leveraging FastMCP's powerful capabilities for building a robust, extensible MCP server.*