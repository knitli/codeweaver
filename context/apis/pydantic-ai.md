<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Pydantic-AI v0.62+ - Complete API Research Report

*Expert API Analyst Research - Foundation for CodeWeaver Clean Rebuild*

## Summary

**Feature Name**: Pydantic-AI Framework Integration  
**Feature Description**: Multi-provider AI agent framework with structured output, tool integration, and pipeline capabilities  
**Feature Goal**: Enable CodeWeaver's intent analysis, sampling workflows, precontext generation, and multi-provider AI capabilities

**Primary External Surface(s)**: `Agent` class, model providers (OpenAI, Anthropic, local models), tool system, pydantic-graph integration, pydantic-evals framework

**Integration Confidence**: High - Well-documented API with clear patterns, extensive provider support, and strong pydantic ecosystem integration

## Core Types

| Name | Kind | Definition | Role |
|------|------|------------|------|
| `Agent[DepsT, OutputT]` | Generic Class | Main interface for AI interactions | Primary agent abstraction with dependency injection and structured output |
| `RunContext[DepsT]` | Generic Class | Execution context with dependencies | Dependency injection and tool access during runs |
| `ModelProvider` | Abstract Base | Provider abstraction for different APIs | Unified interface for OpenAI, Anthropic, local models, etc. |
| `ToolDefinition` | Dataclass | Tool schema and metadata | Defines function tools available to agents |
| `AgentRunResult` | Class | Run execution results | Contains output, usage statistics, message history |
| `UsageLimits` | Class | Token/request constraints | Controls resource consumption during runs |
| `BaseNode[StateT, DepsT, EndT]` | Generic Base | Graph node abstraction | Pipeline building blocks for pydantic-graph integration |

## Signatures

### Core Agent Class

**Name**: `Agent.__init__`  
**Import Path**: `from pydantic_ai import Agent`  
**Concrete Path**: `pydantic_ai/agent.py:Agent.__init__`  
**Signature**: `def __init__(self, model: Union[str, Model], *, deps_type: Type[DepsT] = None, output_type: Type[OutputT] = None, system_prompt: str = None, tools: List[Union[Tool, Callable]] = None, toolsets: List[Toolset] = None, retries: int = 0, model_settings: BaseSettings = None)`

**Params**:
- `model: Union[str, Model]` (required) - Model identifier (e.g., 'openai:gpt-4o', 'anthropic:claude-3-5-sonnet-latest') or explicit model instance
- `deps_type: Type[DepsT]` (optional) - Type for dependency injection, enables type-safe context passing
- `output_type: Type[OutputT]` (optional) - Pydantic model or type for structured output validation
- `system_prompt: str` (optional) - Static system prompt for agent behavior
- `tools: List[Union[Tool, Callable]]` (optional) - Function tools available to the agent
- `toolsets: List[Toolset]` (optional) - Collections of related tools
- `retries: int = 0` (optional) - Number of retry attempts for failed operations
- `model_settings: BaseSettings` (optional) - Provider-specific configuration

**Returns**: `Agent[DepsT, OutputT]` instance  
**Errors**: `ValueError` if model string format invalid, `ImportError` if provider not installed  
**Notes**: Generic type parameters enable type-safe dependency injection and output validation

### Agent Execution Methods

**Name**: `Agent.run_sync`  
**Import Path**: `from pydantic_ai import Agent`  
**Signature**: `def run_sync(self, prompt: str, *, deps: DepsT = None, message_history: List[ModelMessage] = None, usage_limits: UsageLimits = None) -> AgentRunResult[OutputT]`

**Params**:
- `prompt: str` (required) - User prompt for the agent
- `deps: DepsT` (optional) - Dependencies injected into RunContext for tools and system prompts
- `message_history: List[ModelMessage]` (optional) - Previous conversation context
- `usage_limits: UsageLimits` (optional) - Token and request limits
  
**Returns**: `AgentRunResult[OutputT]` with validated output and usage statistics  
**Errors**: `UsageLimitExceeded`, `UnexpectedModelBehavior`, `ModelRetry`

**Name**: `Agent.run`  
**Signature**: `async def run(self, prompt: str, **kwargs) -> AgentRunResult[OutputT]`  
**Notes**: Async version with identical parameters and behavior

**Name**: `Agent.run_stream`  
**Signature**: `async def run_stream(self, prompt: str, **kwargs) -> StreamedRunResult[OutputT]`  
**Returns**: `StreamedRunResult` with streaming text/output capabilities  
**Notes**: Enables real-time response streaming with partial validation

### Tool Definition and Registration

**Name**: `@Agent.tool`  
**Signature**: `def tool(self, *, retries: int = 0, name: str = None) -> Callable`

**Name**: `@Agent.tool_plain`  
**Signature**: `def tool_plain(self, *, retries: int = 0, name: str = None) -> Callable`  
**Notes**: For tools that don't require RunContext injection

**Name**: `Tool.from_schema`  
**Signature**: `@classmethod def from_schema(cls, function: Callable, *, name: str, description: str, json_schema: Dict[str, Any], strict: bool = None) -> Tool`

### Model Provider Classes

**Name**: `OpenAIModel.__init__`  
**Import Path**: `from pydantic_ai.models.openai import OpenAIModel`  
**Signature**: `def __init__(self, model_name: str, provider: OpenAIProvider = None, profile: ModelProfile = None)`

**Name**: `AnthropicModel.__init__`  
**Import Path**: `from pydantic_ai.models.anthropic import AnthropicModel`  
**Signature**: `def __init__(self, model_name: str, provider: AnthropicProvider = None)`

**Name**: `OpenAIProvider.__init__`  
**Import Path**: `from pydantic_ai.providers.openai import OpenAIProvider`  
**Signature**: `def __init__(self, base_url: str, api_key: str, http_client: AsyncClient = None)`

### Context and Dependency Injection

**Name**: `RunContext` attributes  
**Import Path**: `from pydantic_ai import RunContext`  
**Signature**: 
```python
class RunContext[DepsT]:
    deps: DepsT  # Injected dependencies
    usage: Usage  # Current usage statistics
    model: Model  # Current model instance
    
    async def sample(self, messages: List[Dict], model: str = None, **kwargs) -> str
    async def elicit(self, prompt: str, schema: Dict = None) -> Dict[str, Any]
```

### Graph Integration (pydantic-graph)

**Name**: `BaseNode.__init__`  
**Import Path**: `from pydantic_graph import BaseNode`  
**Signature**: Generic `BaseNode[StateT, DepsT, EndT]` for pipeline nodes

**Name**: `Graph.__init__`  
**Import Path**: `from pydantic_graph import Graph`  
**Signature**: `def __init__(self, nodes: List[Type[BaseNode]], state_type: Type = None)`

**Name**: `Graph.run_sync`  
**Signature**: `def run_sync(self, start_node: BaseNode, *, state: StateT = None, deps: DepsT = None) -> GraphResult[EndT]`

## Type Graph

```
Agent[DepsT, OutputT] -> contains -> Model
Agent[DepsT, OutputT] -> contains -> List[Tool]
Agent[DepsT, OutputT] -> contains -> List[Toolset]
Agent[DepsT, OutputT] -> returns -> AgentRunResult[OutputT]

Model -> extends -> ModelProvider
OpenAIModel -> extends -> Model
AnthropicModel -> extends -> Model
CohereModel -> extends -> Model

Tool -> contains -> ToolDefinition
Tool -> contains -> Callable
ToolDefinition -> contains -> JSONSchema

RunContext[DepsT] -> contains -> DepsT
RunContext[DepsT] -> contains -> Usage
RunContext[DepsT] -> contains -> Model

AgentRunResult[OutputT] -> contains -> OutputT
AgentRunResult[OutputT] -> contains -> Usage
AgentRunResult[OutputT] -> contains -> List[ModelMessage]

BaseNode[StateT, DepsT, EndT] -> contains -> StateT
BaseNode[StateT, DepsT, EndT] -> returns -> Union[BaseNode, End[EndT]]
Graph -> contains -> List[BaseNode]
Graph -> returns -> GraphResult[EndT]

UsageLimits -> contains -> Optional[int] response_tokens_limit
UsageLimits -> contains -> Optional[int] request_limit
```

## Request/Response Schemas

### Agent Execution Flow

**Request Shape**:
```python
{
    "prompt": "string - user input",
    "deps": "DepsT - injected dependencies", 
    "message_history": "List[ModelMessage] - conversation context",
    "usage_limits": {
        "response_tokens_limit": "Optional[int]",
        "request_limit": "Optional[int]"
    }
}
```

**Response Shape**:
```python
AgentRunResult[OutputT] {
    "output": "OutputT - validated structured output",
    "usage": {
        "requests": "int",
        "request_tokens": "int", 
        "response_tokens": "int",
        "total_tokens": "int"
    },
    "new_messages": "List[ModelMessage] - conversation updates"
}
```

### Model Provider Authentication

**OpenAI/Compatible Providers**:
```python
{
    "api_key": "string - API key",
    "base_url": "string - API endpoint",
    "http_client": "Optional[AsyncClient] - custom HTTP client"
}
```

**Environment Variables**: `OPENAI_API_KEY`, `ANTHROPIC_API_KEY`, `GROQ_API_KEY`, etc.

### Tool Invocation Schema

**Tool Definition**:
```python
{
    "name": "string - function name",
    "description": "string - function purpose",
    "parameters_json_schema": {
        "type": "object",
        "properties": {"param_name": {"type": "param_type"}},
        "required": ["required_params"]
    }
}
```

**Tool Call**:
```python
{
    "tool_name": "string",
    "args": "Dict[str, Any]",
    "tool_call_id": "string"
}
```

## Patterns

### Multi-Provider Architecture

Pydantic-AI uses a consistent provider pattern across all LLM services:

```python
# Automatic provider detection
agent = Agent('openai:gpt-4o')
agent = Agent('anthropic:claude-3-5-sonnet-latest') 
agent = Agent('groq:llama-3.3-70b-versatile')

# Explicit provider configuration
provider = OpenAIProvider(base_url="http://localhost:11434/v1", api_key="local")
model = OpenAIModel('llama3.2', provider=provider)
agent = Agent(model)
```

### Structured Output with Validation

```python
class CodeContext(BaseModel):
    relevant_files: List[str]
    confidence_score: float = Field(ge=0.0, le=1.0)
    reasoning: str

agent = Agent('openai:gpt-4o', output_type=CodeContext)
result = agent.run_sync("Find relevant authentication code")
# result.output is guaranteed to be a validated CodeContext instance
```

### Dependency Injection Pattern

```python
@dataclass
class SearchDeps:
    vector_store: QdrantClient
    embedding_client: VoyageEmbedding

agent = Agent('anthropic:claude-3-5-sonnet-latest', deps_type=SearchDeps)

@agent.tool
async def search_codebase(ctx: RunContext[SearchDeps], query: str) -> List[str]:
    embeddings = await ctx.deps.embedding_client.embed([query])
    results = ctx.deps.vector_store.search(embeddings[0])
    return [r.payload['content'] for r in results]
```

### Sampling for Internal LLM Usage

```python
async def intent_analyzer(query: str, context: RunContext[Any]) -> Dict[str, str]:
    messages = [
        {"role": "system", "content": "Analyze code search intent..."},
        {"role": "user", "content": f"Query: {query}"}
    ]
    
    analysis = await context.sample(
        messages=messages,
        model="anthropic:claude-3-haiku-20240307",  # Fast model for analysis
        max_tokens=200,
        temperature=0.3
    )
    return {"intent": analysis, "strategy": "vector_search"}
```

### Graph-Based Pipeline Integration

```python
@dataclass  
class AnalyzeIntent(BaseNode[CodeSearchState]):
    query: str
    
    async def run(self, ctx: GraphRunContext[CodeSearchState]) -> EmbedQuery | SearchFiles:
        # Use agent for intent analysis
        result = await intent_agent.run(self.query, deps=ctx.deps)
        
        if result.output.intent == "semantic_search":
            return EmbedQuery(self.query)
        else:
            return SearchFiles(result.output.file_patterns)

pipeline = Graph(nodes=[AnalyzeIntent, EmbedQuery, SearchFiles, RankResults])
```

## Differences vs Project

### Alignment Strengths

1. **Multi-Provider Support**: Perfect match for CodeWeaver's provider flexibility requirements (Voyage, OpenAI, local models, etc.)

2. **Structured Output**: Native support for pydantic models aligns with CodeWeaver's type-safe architecture

3. **Dependency Injection**: RunContext pattern enables clean integration with vector stores, embedding providers, and other services

4. **Tool System**: Flexible tool registration supports CodeWeaver's internal tool needs (vector search, file discovery, etc.)

5. **Sampling Capability**: Direct support for "sampling" requests enables CodeWeaver's intent analysis without separate MCP sessions

6. **Graph Integration**: Native pydantic-graph support enables CodeWeaver's planned pipeline architecture

7. **Evaluation Framework**: pydantic-evals integration supports CodeWeaver's quality and performance monitoring

### Key Implementation Considerations

1. **Provider Configuration**: Use pydantic-settings for unified configuration of all AI providers alongside other CodeWeaver settings

2. **Sampling vs MCP Context**: Leverage sampling for internal analysis when FastMCP Context is available, maintain fallback strategies for CLI usage

3. **Tool Integration**: Register CodeWeaver's core search and discovery functions as agent tools for internal use

4. **Graph Pipeline Architecture**: Use pydantic-graph nodes for CodeWeaver's multi-stage resolution pipeline (intent → retrieval → ranking → assembly)

5. **Error Handling**: Implement ModelRetry patterns for robust handling of provider failures and rate limits

### Potential Gaps

1. **Embedding Provider Abstraction**: Pydantic-AI doesn't provide unified embedding provider interface - CodeWeaver needs to implement this separately

2. **Vector Store Integration**: No built-in vector store abstraction - requires direct integration with qdrant-client

3. **Streaming for CLI**: Streaming responses work well for web interfaces but need adaptation for CLI progress indication

4. **Config Integration**: Need to bridge pydantic-ai's provider configuration with CodeWeaver's unified settings system

5. **Token Estimation**: No built-in token counting for budget management - requires separate tiktoken integration

## Blocking Questions

1. **Provider Settings Integration**: How should CodeWeaver merge pydantic-ai provider settings with pydantic-settings configuration? Should we subclass pydantic-ai provider classes or use composition?

2. **Sampling vs Context Isolation**: Can pydantic-ai sampling be used safely within FastMCP tools without context leakage to the client agent?

3. **Graph State Persistence**: Does pydantic-graph's persistence system work reliably for CodeWeaver's multi-session workflows, or do we need custom state management?

4. **Tool Argument Validation**: Does pydantic-ai perform argument validation for custom tools, or does CodeWeaver need to implement this separately?

## Non-blocking Questions

1. **Performance Optimization**: What are the performance characteristics of pydantic-ai's agent execution vs direct model API calls?

2. **Custom Model Integration**: How complex is adding support for additional model providers not covered by pydantic-ai's built-in support?

3. **Testing Strategy**: What are best practices for testing pydantic-ai agents without consuming API tokens?

4. **Memory Management**: How does pydantic-ai handle long conversation histories and memory usage optimization?

## Sources

[Context7 Official Documentation | Context7 ID: /pydantic/pydantic-ai | Reliability: 5]
- Core API patterns, agent initialization, tool system
- Provider configuration and model integration
- pydantic-graph integration patterns
- Testing utilities and TestModel usage
- Real-world examples and best practices

[Pydantic-AI GitHub Repository | https://github.com/pydantic/pydantic-ai | Reliability: 5]
- Source code structure and implementation details
- API reference documentation and examples
- Integration patterns with pydantic ecosystem
- Provider implementation patterns

[Pydantic-AI Documentation | https://ai.pydantic.dev/ | Reliability: 5]  
- Complete API reference and guides
- Model provider configuration
- Tool and toolset integration
- Graph execution and pipeline patterns
- Evaluation framework integration

---

*This research provides comprehensive technical foundation for integrating pydantic-ai into CodeWeaver's clean rebuild. All patterns and examples are based on pydantic-ai v0.62+ and designed to align with CodeWeaver's architectural goals of simplicity, type safety, and extensibility.*