<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Pydantic-Graph and Pydantic-Evals - Complete API Research Report

*Expert API Analyst Research - Foundation for CodeWeaver Clean Rebuild*

## Summary

**Feature Name**: Pydantic-Graph Pipeline Foundation & Pydantic-Evals Testing Framework  
**Feature Description**: Graph-based state machine execution engine with comprehensive evaluation and testing framework  
**Feature Goal**: Enable CodeWeaver's multi-stage resolution pipeline (intent → retrieval → ranking → assembly) with systematic performance evaluation and quality monitoring

**Primary External Surface(s)**: `Graph` execution engine, `BaseNode` pipeline components, `Dataset` evaluation framework, `Evaluator` scoring system, state persistence mechanisms

**Integration Confidence**: High - Both libraries are core components of pydantic-ai ecosystem with extensive documentation, clear patterns, and strong alignment with CodeWeaver's architectural goals

## Core Types

| Name | Kind | Definition | Role |
|------|------|------------|------|
| `Graph[StateT, DepsT, EndT]` | Generic Class | Main graph execution engine | Orchestrates pipeline execution and node transitions |
| `BaseNode[StateT, DepsT, EndT]` | Generic Base Class | Pipeline component abstraction | Individual processing steps in CodeWeaver's resolution pipeline |
| `GraphRunContext[StateT]` | Generic Class | Execution context with state/deps | Provides state management and dependency injection during graph runs |
| `End[EndT]` | Generic Class | Graph termination signal | Indicates successful pipeline completion with final result |
| `Edge` | Annotation Class | Graph edge labeling for visualization | Enhances Mermaid diagram generation with custom labels |
| `Dataset[InputT, OutputT, MetadataT]` | Generic Class | Evaluation test suite container | Manages collections of test cases for pipeline assessment |
| `Case` | Class | Individual test scenario | Defines inputs, expected outputs, and metadata for evaluation |
| `Evaluator[InputT, OutputT]` | Abstract Base Class | Custom evaluation logic | Scoring functions for assessing pipeline performance |
| `EvaluatorContext[InputT, OutputT]` | Generic Class | Evaluation execution context | Provides access to inputs, outputs, and test case metadata |

## Signatures

### Pydantic-Graph Core API

**Name**: `Graph.__init__`  
**Import Path**: `from pydantic_graph import Graph`  
**Concrete Path**: `pydantic_graph/graph.py:Graph.__init__`  
**Signature**: `def __init__(self, nodes: List[Type[BaseNode]], state_type: Type[StateT] = None)`

**Params**:
- `nodes: List[Type[BaseNode]]` (required) - List of node class types that can be executed in this graph
- `state_type: Type[StateT]` (optional) - Type for shared state across graph execution

**Returns**: `Graph[StateT, DepsT, EndT]` instance  
**Errors**: `ValueError` if nodes contain invalid types, `TypeError` if state_type incompatible  
**Notes**: Nodes define execution flow through return type annotations, enabling type-safe pipeline construction

### Graph Execution Methods

**Name**: `Graph.run_sync`  
**Import Path**: `from pydantic_graph import Graph`  
**Signature**: `def run_sync(self, start_node: BaseNode, *, state: StateT = None, deps: DepsT = None, persistence: StatePersistence = None) -> GraphResult[EndT]`

**Params**:
- `start_node: BaseNode` (required) - Initial node to begin graph execution
- `state: StateT` (optional) - Initial state for the graph run
- `deps: DepsT` (optional) - Dependencies injected into all nodes via GraphRunContext
- `persistence: StatePersistence` (optional) - State persistence strategy for resumable execution

**Returns**: `GraphResult[EndT]` with final output and execution history  
**Errors**: `GraphExecutionError`, `NodeExecutionError`, `StateValidationError`  
**Notes**: Synchronous execution suitable for non-async contexts, supports full pipeline tracing

**Name**: `Graph.run`  
**Signature**: `async def run(self, start_node: BaseNode, **kwargs) -> GraphResult[EndT]`  
**Notes**: Async version with identical parameters, preferred for I/O intensive pipelines

**Name**: `Graph.iter`  
**Signature**: `def iter(self, start_node: BaseNode, **kwargs) -> AsyncContextManager[GraphRun[EndT]]`  
**Returns**: `GraphRun` context manager for step-by-step execution control  
**Notes**: Enables manual graph control, node inspection, and early termination

### Node Implementation Pattern

**Name**: `BaseNode.run`  
**Import Path**: `from pydantic_graph import BaseNode`  
**Signature**: `async def run(self, ctx: GraphRunContext[StateT, DepsT]) -> NextNode | End[EndT]`

**Params**:
- `ctx: GraphRunContext[StateT, DepsT]` (required) - Execution context with state and dependency access

**Returns**: Next node in pipeline or `End[EndT]` to terminate graph  
**Errors**: Node-specific exceptions, `StateUpdateError`, `DependencyError`  
**Notes**: Abstract method requiring implementation, return type defines graph edges

**Type Information**:
```python
@dataclass
class AnalyzeIntent(BaseNode[CodeSearchState, CodeWeaverDeps, ContentMatch]):
    query: str
    
    async def run(self, ctx: GraphRunContext[CodeSearchState, CodeWeaverDeps]) -> EmbedQuery | SearchFiles | End[ContentMatch]:
        # Access injected dependencies
        intent_result = await ctx.deps.intent_analyzer.analyze(self.query)
        
        # Update shared state
        ctx.state.intent = intent_result.intent
        ctx.state.confidence = intent_result.confidence
        
        # Return next node based on analysis
        if intent_result.intent == "semantic_search":
            return EmbedQuery(self.query, intent_result.parameters)
        elif intent_result.intent == "file_search":
            return SearchFiles(intent_result.file_patterns)
        else:
            return End(ContentMatch([], "insufficient_context"))
```

### Visualization and Debugging

**Name**: `Graph.mermaid_code`  
**Import Path**: `from pydantic_graph import Graph`  
**Signature**: `def mermaid_code(self, start_node: BaseNode, direction: str = "TB") -> str`

**Params**:
- `start_node: BaseNode` (required) - Starting point for diagram generation
- `direction: str = "TB"` (optional) - Mermaid diagram direction ("TB", "LR", "BT", "RL")

**Returns**: Mermaid syntax string for graph visualization  
**Notes**: Automatically generates state diagrams, supports edge labels via `Edge(label="...")` annotations

**Name**: `Graph.mermaid_image`  
**Signature**: `def mermaid_image(self, start_node: BaseNode) -> bytes`  
**Returns**: PNG image bytes of the graph diagram  
**Notes**: Useful for Jupyter notebook integration and documentation

### State Persistence

**Name**: `FileStatePersistence.__init__`  
**Import Path**: `from pydantic_graph.persistence.file import FileStatePersistence`  
**Signature**: `def __init__(self, file_path: Path)`

**Name**: `StatePersistence.load_next`  
**Signature**: `async def load_next(self) -> Optional[StateSnapshot]`  
**Returns**: Next state snapshot for resumable execution or None if no saved state  

**Name**: `StatePersistence.save`  
**Signature**: `async def save(self, snapshot: StateSnapshot) -> None`  
**Notes**: Enables multi-session pipeline execution with interruption/resumption support

### Pydantic-Evals Core API

**Name**: `Dataset.__init__`  
**Import Path**: `from pydantic_evals import Dataset`  
**Concrete Path**: `pydantic_evals/dataset.py:Dataset.__init__`  
**Signature**: `def __init__(self, cases: List[Case], evaluators: List[Evaluator] = None)`

**Params**:
- `cases: List[Case]` (required) - Test cases to evaluate against
- `evaluators: List[Evaluator]` (optional) - Global evaluators applied to all cases

**Returns**: `Dataset[InputT, OutputT, MetadataT]` instance  
**Notes**: Type-safe evaluation framework with support for case-specific and global evaluators

**Name**: `Dataset.evaluate_sync`  
**Signature**: `def evaluate_sync(self, func: Callable[[InputT], OutputT], *, max_concurrency: int = None) -> EvaluationReport`

**Params**:
- `func: Callable[[InputT], OutputT]` (required) - Function to evaluate (CodeWeaver's find_code pipeline)
- `max_concurrency: int` (optional) - Limit concurrent evaluations, None for unlimited

**Returns**: `EvaluationReport` with scores, assertions, and detailed results  
**Errors**: `EvaluationError`, `ConcurrencyLimitError`, `FunctionTimeoutError`

### Case Definition

**Name**: `Case.__init__`  
**Import Path**: `from pydantic_evals import Case`  
**Signature**: `def __init__(self, name: str, inputs: InputT, expected_output: OutputT = None, metadata: MetadataT = None, evaluators: List[Evaluator] = None)`

**Params**:
- `name: str` (required) - Unique identifier for the test case
- `inputs: InputT` (required) - Input parameters for the function under test
- `expected_output: OutputT` (optional) - Expected output for comparison evaluators
- `metadata: MetadataT` (optional) - Additional case-specific data
- `evaluators: List[Evaluator]` (optional) - Case-specific evaluators

**Returns**: `Case` instance for dataset inclusion  
**Notes**: Flexible test case definition supporting various CodeWeaver evaluation scenarios

### Custom Evaluator Implementation

**Name**: `Evaluator.evaluate`  
**Import Path**: `from pydantic_evals.evaluators import Evaluator`  
**Signature**: `def evaluate(self, ctx: EvaluatorContext[InputT, OutputT]) -> float | Dict[str, Any]`

**Params**:
- `ctx: EvaluatorContext[InputT, OutputT]` (required) - Evaluation context with inputs, outputs, and metadata

**Returns**: Score between 0.0-1.0 or dictionary with multiple metrics  
**Errors**: `EvaluatorError`, `ValidationError` if return type invalid  
**Notes**: Abstract method for custom evaluation logic, supports both simple scores and complex metrics

**Type Information**:
```python
class CodeWeaverRelevanceEvaluator(Evaluator[str, FindCodeResponseSummary]):
    def evaluate(self, ctx: EvaluatorContext[str, FindCodeResponseSummary]) -> Dict[str, Any]:
        response = ctx.output
        query = ctx.inputs
        
        # Calculate relevance metrics
        relevance_score = self._calculate_relevance(query, response.results)
        token_efficiency = min(1.0, 10000 / response.total_tokens)
        coverage_score = self._calculate_coverage(response.results)
        
        return {
            "relevance": relevance_score,
            "efficiency": token_efficiency, 
            "coverage": coverage_score,
            "overall": (relevance_score * 0.5 + token_efficiency * 0.3 + coverage_score * 0.2)
        }
```

## Type Graph

```
Graph[StateT, DepsT, EndT] -> contains -> List[Type[BaseNode]]
Graph[StateT, DepsT, EndT] -> contains -> Type[StateT]
Graph[StateT, DepsT, EndT] -> returns -> GraphResult[EndT]

BaseNode[StateT, DepsT, EndT] -> contains -> StateT
BaseNode[StateT, DepsT, EndT] -> contains -> DepsT
BaseNode[StateT, DepsT, EndT] -> returns -> Union[BaseNode, End[EndT]]

GraphRunContext[StateT, DepsT] -> contains -> StateT
GraphRunContext[StateT, DepsT] -> contains -> DepsT
GraphRunContext[StateT, DepsT] -> provides -> state_access
GraphRunContext[StateT, DepsT] -> provides -> dependency_injection

End[EndT] -> contains -> EndT
End[EndT] -> terminates -> Graph

StatePersistence -> enables -> graph_resumption
FileStatePersistence -> extends -> StatePersistence
FullStatePersistence -> extends -> StatePersistence

Dataset[InputT, OutputT, MetadataT] -> contains -> List[Case]
Dataset[InputT, OutputT, MetadataT] -> contains -> List[Evaluator]
Dataset[InputT, OutputT, MetadataT] -> returns -> EvaluationReport

Case -> contains -> InputT
Case -> contains -> OutputT
Case -> contains -> MetadataT
Case -> contains -> List[Evaluator]

Evaluator[InputT, OutputT] -> processes -> EvaluatorContext[InputT, OutputT]
Evaluator[InputT, OutputT] -> returns -> Union[float, Dict[str, Any]]

EvaluatorContext[InputT, OutputT] -> contains -> InputT
EvaluatorContext[InputT, OutputT] -> contains -> OutputT
EvaluatorContext[InputT, OutputT] -> contains -> Case
EvaluatorContext[InputT, OutputT] -> contains -> Optional[SpanTree]

EvaluationReport -> contains -> scores
EvaluationReport -> contains -> assertions
EvaluationReport -> contains -> durations
EvaluationReport -> provides -> detailed_analysis
```

## Request/Response Schemas

### Graph Pipeline Execution

**Pipeline Invocation**:
```python
# CodeWeaver resolution pipeline
{
    "start_node": "AnalyzeIntent(query='authentication patterns')",
    "state": {
        "query": "authentication patterns",
        "intent": None,
        "confidence": 0.0,
        "results": []
    },
    "deps": {
        "vector_store": "QdrantClient(...)",
        "embedding_client": "VoyageEmbedding(...)",
        "file_discovery": "AstGrepService(...)"
    },
    "persistence": "FileStatePersistence('/tmp/pipeline.json')"
}
```

**Pipeline Result**:
```python
GraphResult[ContentMatch] {
    "output": ContentMatch(
        results=[
            CodeSearchResult(content="...", file_path="auth.py", line_range=(45, 67)),
            CodeSearchResult(content="...", file_path="middleware.py", line_range=(12, 34))
        ],
        strategy="hybrid_search",
        confidence=0.87
    ),
    "persistence": {
        "history": [
            "AnalyzeIntent(query='authentication patterns')",
            "EmbedQuery(query='authentication patterns', params={...})",
            "SearchVectors(embeddings=[...], limit=10)",
            "RerankResults(results=[...], strategy='voyage')",
            "End(data=ContentMatch(...))"
        ]
    }
}
```

### Evaluation Framework Execution

**Dataset Evaluation**:
```python
{
    "cases": [
        {
            "name": "auth_implementation_query",
            "inputs": "how to implement JWT authentication?",
            "expected_output": None,  # No specific expected output
            "metadata": {"complexity": "medium", "domain": "security"}
        },
        {
            "name": "performance_optimization_query", 
            "inputs": "optimize database query performance",
            "expected_output": None,
            "metadata": {"complexity": "high", "domain": "performance"}
        }
    ],
    "evaluators": [
        "RelevanceEvaluator(min_score=0.7)",
        "TokenEfficiencyEvaluator(max_tokens=10000)",
        "CoverageEvaluator(min_files=2)"
    ],
    "max_concurrency": 3
}
```

**Evaluation Report**:
```python
EvaluationReport {
    "summary": {
        "total_cases": 2,
        "passed_assertions": 6,
        "failed_assertions": 0,
        "average_scores": {
            "RelevanceEvaluator": 0.85,
            "TokenEfficiencyEvaluator": 0.92,
            "CoverageEvaluator": 0.78
        }
    },
    "case_results": [
        {
            "case_id": "auth_implementation_query",
            "inputs": "how to implement JWT authentication?",
            "outputs": "FindCodeResponseSummary(...)",
            "scores": {
                "RelevanceEvaluator": 0.87,
                "TokenEfficiencyEvaluator": 0.94,
                "CoverageEvaluator": 0.82
            },
            "assertions": "✔",
            "duration": "245ms"
        }
    ]
}
```

### OpenTelemetry Integration

**Tracing Configuration**:
```python
{
    "service_name": "codeweaver-evaluation",
    "environment": "development",
    "send_to_logfire": "if-token-present",
    "enable_otel_tracing": True
}
```

**Span Tree Analysis**:
```python
SpanQuery {
    "name_contains": "vector_search",
    "duration_gt": 100.0,  # milliseconds
    "has_errors": False
}
```

## Patterns

### Multi-Stage Resolution Pipeline

```python
@dataclass
class CodeSearchState:
    query: str
    intent: Optional[str] = None
    confidence: float = 0.0
    intermediate_results: List[Any] = field(default_factory=list)
    final_results: List[CodeSearchResult] = field(default_factory=list)

@dataclass 
class CodeWeaverDeps:
    vector_store: QdrantClient
    embedding_client: VoyageEmbedding
    ast_grep_client: AstGrepService
    intent_analyzer: IntentAnalyzer

# Intent analysis node
@dataclass
class AnalyzeIntent(BaseNode[CodeSearchState, CodeWeaverDeps, ContentMatch]):
    query: str
    
    async def run(self, ctx: GraphRunContext[CodeSearchState, CodeWeaverDeps]) -> EmbedQuery | SearchFiles:
        analysis = await ctx.deps.intent_analyzer.analyze(self.query)
        ctx.state.intent = analysis.intent
        ctx.state.confidence = analysis.confidence
        
        if analysis.intent == "semantic_search":
            return EmbedQuery(self.query, analysis.parameters)
        else:
            return SearchFiles(analysis.file_patterns)

# Vector embedding node
@dataclass
class EmbedQuery(BaseNode[CodeSearchState, CodeWeaverDeps, ContentMatch]):
    query: str
    parameters: Dict[str, Any]
    
    async def run(self, ctx: GraphRunContext[CodeSearchState, CodeWeaverDeps]) -> SearchVectors:
        embeddings = await ctx.deps.embedding_client.embed([self.query])
        return SearchVectors(embeddings[0], self.parameters.get("limit", 10))

# Graph definition
codeweaver_graph = Graph(
    nodes=[AnalyzeIntent, EmbedQuery, SearchFiles, SearchVectors, RerankResults, AssembleResponse],
    state_type=CodeSearchState
)
```

### Comprehensive Evaluation Framework

```python
# Define evaluation cases for CodeWeaver
codeweaver_cases = [
    Case(
        name="auth_implementation",
        inputs="how to implement authentication middleware?",
        expected_output=None,
        metadata={"complexity": "medium", "domain": "security"},
        evaluators=[
            LLMJudge(rubric="Results must contain relevant authentication code examples"),
            TokenEfficiencyEvaluator(max_tokens=8000)
        ]
    ),
    Case(
        name="performance_optimization",
        inputs="optimize slow database queries",
        expected_output=None,
        metadata={"complexity": "high", "domain": "performance"},
        evaluators=[
            CoverageEvaluator(min_files=3),
            RelevanceEvaluator(min_score=0.8)
        ]
    )
]

# Global evaluators applied to all cases
global_evaluators = [
    IsInstance(type_name="FindCodeResponseSummary"),  # Type checking
    ResponseTimeEvaluator(max_duration_ms=2000),  # Performance requirement
    CodeQualityEvaluator()  # Custom quality assessment
]

codeweaver_dataset = Dataset(
    cases=codeweaver_cases,
    evaluators=global_evaluators
)

# Evaluation execution with tracing
async def evaluate_codeweaver_pipeline():
    report = codeweaver_dataset.evaluate_sync(
        find_code_pipeline,  # CodeWeaver's main pipeline function
        max_concurrency=5
    )
    
    # Print comprehensive report
    report.print(
        include_input=True,
        include_output=True,
        include_durations=True
    )
    
    return report
```

### Human-in-the-Loop Graph Pattern

```python
@dataclass 
class InteractiveRefinement(BaseNode[CodeSearchState, CodeWeaverDeps, ContentMatch]):
    initial_results: List[CodeSearchResult]
    
    async def run(self, ctx: GraphRunContext[CodeSearchState, CodeWeaverDeps]) -> RefineQuery | End[ContentMatch]:
        # Check if results meet quality threshold
        if self._assess_quality(self.initial_results) >= 0.8:
            return End(ContentMatch(self.initial_results, "high_quality"))
        
        # Request human feedback via elicitation (FastMCP)
        if hasattr(ctx.deps, 'context') and ctx.deps.context:
            refinement = await ctx.deps.context.elicit(
                prompt="The initial results may not fully address your query. How would you like to refine the search?",
                schema={
                    "type": "object",
                    "properties": {
                        "refined_query": {"type": "string"},
                        "focus_areas": {"type": "array", "items": {"type": "string"}},
                        "exclude_patterns": {"type": "array", "items": {"type": "string"}}
                    }
                }
            )
            return RefineQuery(refinement["refined_query"], refinement)
        else:
            # Fallback for non-interactive contexts
            return End(ContentMatch(self.initial_results, "partial_results"))
```

## Differences vs Project

### Alignment Strengths

1. **Pipeline Architecture Perfect Match**: pydantic-graph's node-based execution model directly implements CodeWeaver's planned multi-stage resolution pipeline (intent → retrieval → ranking → assembly)

2. **State Management**: GraphRunContext provides exactly the state sharing and dependency injection patterns CodeWeaver needs for maintaining context across pipeline stages

3. **Visualization and Debugging**: Automatic Mermaid diagram generation supports CodeWeaver's goal of providing clear developer experience and system transparency

4. **Evaluation Integration**: pydantic-evals directly addresses CodeWeaver's need for systematic pipeline performance assessment and continuous improvement

5. **FastMCP Integration**: Both libraries work seamlessly with FastMCP's Context and sampling capabilities for interactive refinement workflows

6. **Type Safety**: Full generic type support ensures CodeWeaver's pydantic-based architecture maintains type safety throughout pipeline execution

7. **State Persistence**: Built-in persistence mechanisms enable CodeWeaver's multi-session workflows and resumable operations

### Implementation Considerations

1. **Graph Node Design**: Structure CodeWeaver nodes as focused, single-responsibility components (AnalyzeIntent, EmbedQuery, SearchVectors, RerankResults, AssembleResponse)

2. **State Schema**: Define comprehensive CodeSearchState with query tracking, intermediate results, confidence scoring, and metadata collection

3. **Dependency Injection**: Use GraphRunContext.deps for clean service injection (vector stores, embedding clients, file discovery services)

4. **Error Handling**: Implement robust error boundaries at node level with graceful degradation and alternative pathway options

5. **Evaluation Strategy**: Create domain-specific evaluators for CodeWeaver use cases (relevance, token efficiency, coverage, response quality)

6. **Persistence Strategy**: Use FileStatePersistence for development and FullStatePersistence for production monitoring

### Potential Integration Challenges

1. **Complex State Management**: CodeWeaver's shared state between nodes requires careful design to avoid state pollution and maintain thread safety

2. **Performance Overhead**: Graph execution adds minimal overhead but needs monitoring for high-frequency CodeWeaver operations

3. **Error Propagation**: Node-level errors need consistent handling patterns across the entire pipeline

4. **Evaluation Latency**: Comprehensive evaluation suites may impact CodeWeaver development velocity - requires balanced evaluation strategy

## Blocking Questions

1. **Graph State Thread Safety**: Can pydantic-graph handle concurrent graph executions with shared dependencies safely, or does CodeWeaver need instance isolation?

2. **Persistence Performance**: What are the performance characteristics of FileStatePersistence for CodeWeaver's expected usage patterns (frequent small state updates)?

3. **Evaluation Resource Usage**: How does pydantic-evals handle memory usage during large-scale evaluation runs with complex CodeWeaver outputs?

4. **FastMCP Integration Depth**: Can pydantic-graph nodes access FastMCP Context for sampling/elicitation, or does this require wrapper patterns?

5. **Type System Compatibility**: Are there any edge cases where pydantic-graph's generic constraints conflict with CodeWeaver's planned type hierarchy?

## Non-blocking Questions

1. **Optimization Patterns**: What are best practices for optimizing pydantic-graph performance in high-throughput scenarios?

2. **Custom Persistence**: How complex is implementing custom StatePersistence backends for CodeWeaver's specific requirements (Redis, database storage)?

3. **Evaluation Extensions**: Can pydantic-evals evaluators access external services (vector stores, APIs) for dynamic evaluation criteria?

4. **Graph Composition**: Is there support for composing multiple graphs or creating hierarchical pipeline structures?

5. **Debug Tooling**: What additional debugging and profiling tools are available beyond Mermaid visualization?

## Sources

[Context7 Documentation | /pydantic/pydantic-ai | pydantic-graph pydantic-evals | Reliability: 5]
- Complete API reference for both pydantic-graph and pydantic-evals
- Graph execution patterns, node implementation examples
- State persistence mechanisms and resumable execution
- Evaluation framework patterns and custom evaluator implementation
- OpenTelemetry integration and monitoring capabilities
- Human-in-the-loop patterns and interactive graph execution
- Mermaid visualization and debugging capabilities

[Pydantic-AI GitHub Repository | https://github.com/pydantic/pydantic-ai | Reliability: 5]
- Source code for both libraries within pydantic-ai ecosystem
- Implementation details and advanced usage patterns
- Integration examples with FastMCP and other ecosystem components
- Test patterns and evaluation strategies

[Pydantic-AI Documentation | https://ai.pydantic.dev/graph/ and https://ai.pydantic.dev/evals/ | Reliability: 5]
- Comprehensive guides for graph-based pipeline construction
- Evaluation framework best practices and patterns
- Integration with broader pydantic-ai ecosystem
- Performance optimization and debugging guidance

---

*This research provides comprehensive technical foundation for integrating pydantic-graph and pydantic-evals into CodeWeaver's clean rebuild. Both libraries align perfectly with CodeWeaver's architectural goals and provide essential capabilities for building robust, evaluable, and maintainable AI-powered developer tools.*