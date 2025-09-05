<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Cyclopts CLI Framework - Complete API Research Report

*Expert API Analyst Research - Foundation for CodeWeaver CLI Architecture*

## Summary

**Feature Name**: CodeWeaver CLI Framework  
**Feature Description**: Modern, type-safe command-line interface implementation using cyclopts for CodeWeaver MCP server management, configuration, and development workflows  
**Feature Goal**: Provide an intuitive, powerful CLI that seamlessly integrates with pydantic-settings configuration system while supporting FastMCP server management patterns and pydantic-ai provider workflows

**Primary External Surface(s)**: `cyclopts.App`, `cyclopts.Parameter`, `cyclopts.Group`, configuration sources (`cyclopts.config.*`), async command support, validation framework

**Integration Confidence**: High - Mature API with excellent type safety, proven FastAPI-like patterns, comprehensive configuration integration, and strong async support aligned with CodeWeaver's architecture

## Core Types

| Name | Kind | Definition | Role |
|------|------|------------|------|
| `cyclopts.App` | Main Class | CLI application container | Primary application orchestrator and command registry |
| `cyclopts.Parameter` | Configuration Class | Parameter behavior configuration | Type annotation for argument parsing and validation |
| `cyclopts.Group` | Organization Class | Parameter and command grouping | UI organization and validation scoping |
| `cyclopts.config.Toml` | Config Source | TOML file configuration | Integration with pyproject.toml and .codeweaver.toml |
| `cyclopts.config.Json` | Config Source | JSON file configuration | JSON-based configuration loading |
| `cyclopts.config.Yaml` | Config Source | YAML file configuration | YAML configuration support |
| `cyclopts.config.Env` | Config Source | Environment variable configuration | Environment-based configuration |
| `cyclopts.validators.*` | Validator Classes | Input validation framework | Type and value validation |
| `Annotated[T, Parameter(...)]` | Type Pattern | Type annotation pattern | Enhanced type hints with behavior |

## Signatures

### Core App Class

**Name**: `cyclopts.App.__init__`  
**Import Path**: `from cyclopts import App`  
**Concrete Path**: `https://github.com/brianpugh/cyclopts/blob/main/cyclopts/core.py:App.__init__`  
**Signature**: 
```python
def __init__(
    self,
    *,
    name: Optional[Union[str, Iterable[str]]] = None,
    alias: Optional[Union[str, Iterable[str]]] = None,
    help: Optional[str] = None,
    help_flags: Union[str, Iterable[str]] = ("--help", "-h"),
    help_format: Optional[Literal["plaintext", "markdown", "md", "restructuredtext", "rst"]] = None,
    help_on_error: Optional[bool] = None,
    version: Optional[str] = None,
    version_flags: Union[str, Iterable[str]] = ("--version",),
    version_format: Optional[Literal["plaintext", "markdown", "md", "restructuredtext", "rst"]] = None,
    usage: Optional[str] = None,
    show: bool = True,
    config: Optional[Union[BaseConfig, Iterable[BaseConfig]]] = None,
    default_parameter: Optional[Parameter] = None,
    validator: Optional[Callable] = None,
)
```

**Params**:
- `name: Optional[Union[str, Iterable[str]]]` (optional) - Application name for help and CLI identification
- `help: Optional[str]` (optional) - Help text displayed on help screen
- `config: Optional[Union[BaseConfig, Iterable[BaseConfig]]]` (optional) - Configuration sources for fallback values
- `default_parameter: Optional[Parameter]` (optional) - Default parameter behavior for all commands
- `validator: Optional[Callable]` (optional) - Global argument collection validator

**Returns**: `App` instance  
**Errors**: `ValueError` for invalid configuration, `TypeError` for incompatible parameters  
**Notes**: Supports multiple configuration sources, automatic help generation, and global parameter defaults

**Type Information**:
```python
class App:
    def command(
        self,
        func: Callable | None = None,
        *,
        name: Iterable[str] | str | None = None,
        alias: Iterable[str] | str | None = None,
        help: str | None = None,
        show: bool = True,
        group: Group | str | None = None,
    ) -> Callable | Callable[[Callable], Callable]
    
    def default(
        self, 
        func: Callable | None = None
    ) -> =Callable | Callable[[Callable], Callable]
    
    def __call__(
        self, 
        args: Iterable[str] | None = None, 
        **kwargs: dict[str, Any]
    ) -> Any
```

### Parameter Configuration

**Name**: `cyclopts.Parameter.__init__`  
**Import Path**: `from cyclopts import Parameter`  
**Concrete Path**: `https://github.com/brianpugh/cyclopts/blob/main/cyclopts/parameter.py:Parameter.__init__`  
**Signature**:
```python
def __init__(
    self,
    *,
    name: str | Iterable[str] = None,
    alias: str | Iterable[str] = None,
    help: str | None = None,
    show: bool = True,
    group: Group | str | None = None,
    converter: Callable | None = None,
    validator: Callable, Iterable[Callable] | None = None,
    parse: bool = True,
    consume_multiple: bool = False,
    accepts_keys: bool = True,
    negative_none: str | None = None,
)
```

**Params**:
- `name: str | Iterable[str] | None` (optional) - Custom parameter names and aliases
- `group: Group | str | None` (optional) - Parameter grouping for organization
- `validator: Callable | Iterable[Callable] | None` (optional) - Input validation functions
- `converter: Callable | None` (optional) - Custom type conversion function
- `consume_multiple: bool` (optional, default=False) - Consume multiple tokens for lists
- `parse: bool` (optional, default=True) - Enable/disable parsing for this parameter

**Returns**: `Parameter` instance  
**Errors**: `ValueError` for invalid configuration  
**Notes**: Used with `Annotated[Type, Parameter(...)]` pattern for enhanced type hints

### Configuration Integration

**Name**: `cyclopts.config.Toml.__init__`  
**Import Path**: `from cyclopts.config import Toml`  
**Signature**:
```python
def __init__(
    self,
    path: Union[str, Path],
    *,
    root_keys: str | Iterable[str] = None,
    must_exist: bool = False,
    search_parents: bool = False,
    allow_unknown: bool = False,
    use_commands_as_keys: bool = True,
)
```

**Params**:
- `path: str` (required) - Path to TOML configuration file
- `root_keys: str | Iterable[str] | None` (optional) - Key path to configuration section
- `search_parents: bool` (optional, default=False) - Search parent directories for config file
- `use_commands_as_keys: bool` (optional, default=True) - Use command names as config keys

**Returns**: `Toml` configuration source  
**Errors**: `FileNotFoundError` if must_exist=True and file missing  
**Notes**: Integrates with pydantic-settings patterns, supports pyproject.toml

### Async Command Support

**Name**: Async Command Definition  
**Pattern**: Standard async function decoration  
**Signature**: `@app.command` decorator on async functions  

**Example**:
```python
@app.command
async def index_codebase(path: Path, *, background: bool = False):
    """Asynchronously index codebase for semantic search"""
    await indexer.process_directory(path)
```

**Notes**: Full asyncio support, automatic event loop handling, compatible with FastMCP async patterns

## Type Graph

```
App -> contains -> Dict[str, Command]
App -> uses -> List[BaseConfig]
App -> contains -> default_parameter: Parameter
App -> executes -> Callable (command functions)

Parameter -> annotates -> Type (via Annotated[T, Parameter])
Parameter -> contains -> Group
Parameter -> validates -> Callable (validators)
Parameter -> converts -> Callable (converters)

BaseConfig -> implemented_by -> Toml
BaseConfig -> implemented_by -> Json  
BaseConfig -> implemented_by -> Yaml
BaseConfig -> implemented_by -> Env

Group -> contains -> List[Parameter]
Group -> validates -> Callable (group validators)

Toml -> reads -> Path
Toml -> parses -> TOML content
Toml -> maps -> Dict[str, Any]

Annotated -> combines -> Type + Parameter
Annotated -> enables -> Enhanced type behavior
```

## Request/Response Schemas

### Command Registration Pattern

**Pattern**: Decorator-based command registration
```python
from cyclopts import App
from typing import Annotated, Optional
from pathlib import Path

app = App(name="codeweaver")

@app.command
def index(
    path: Annotated[Path, Parameter(help="Path to index")] = Path("."),
    *,
    collection: str = "codebase", # nominal
    force: bool = False,
    background: bool = False
) -> None:
    """Index codebase for intelligent search"""
    # Implementation
```

### Configuration Integration Pattern

**Pattern**: Multi-source configuration with TOML
```python
from cyclopts import App
from cyclopts.config import Toml
from pydantic_settings import BaseSettings

# Integration with pydantic-settings
class CodeWeaverConfig(BaseSettings):
    max_tokens: int = 10000
    vector_store_url: str = "http://localhost:6333"

app = App(
    name="codeweaver",
    config=Toml(
        "pyproject.toml",
        root_keys=["tool", "codeweaver"],
        search_parents=True
    )
)

@app.command  
def serve(
    *,
    host: str = "localhost",
    port: int = 8000,
    config: Annotated[Optional[Path], Parameter(help="Config file path")] = None
) -> None:
    """Start CodeWeaver MCP server"""
    # Load configuration with fallback hierarchy
```

### Validation and Error Handling Pattern

**Pattern**: Type-safe validation with rich error messages
```python
from cyclopts import App, Parameter, validators
from cyclopts.types import PositiveInt, ExistingPath
from typing import Annotated

app = App()

@app.command
def deploy(
    config_path: Annotated[ExistingPath, Parameter(help="Configuration file")],
    *,
    workers: Annotated[PositiveInt, Parameter(validator=validators.Number(le=16))] = 4,
    environment: Literal["dev", "staging", "prod"] = "dev"
) -> None:
    """Deploy CodeWeaver with validation"""
    # Cyclopts handles validation and provides rich error messages
```

## Patterns

### FastMCP Integration Pattern

**Comparison with FastMCP CLI**:
```python
# FastMCP pattern (direct server execution)
# fastmcp run server.py --transport http

# CodeWeaver with cyclopts pattern (enhanced workflow)
from cyclopts import App
from fastmcp import FastMCP
import asyncio

app = App(name="codeweaver")

@app.command
async def serve(
    *,
    transport: Literal["stdio", "http"] = "stdio",
    host: str = "localhost", 
    port: int = 8000,
    config: Optional[Path] = None,
    dev: bool = False
) -> None:
    """Start CodeWeaver MCP server with enhanced configuration"""
    
    # Load CodeWeaver configuration
    settings = load_settings(config)
    
    # Initialize FastMCP server
    server = FastMCP()
    server.add_tool(find_code)  # CodeWeaver's primary tool
    
    if dev:
        # Development mode with hot reload
        await server.run_dev(transport=transport, host=host, port=port)
    else:
        # Production mode
        await server.run(transport=transport, host=host, port=port)

@app.command
def install(
    client: Literal["claude-desktop", "claude-code", "cursor"],
    *,
    name: str = "codeweaver",
    copy: bool = False
) -> None:
    """Install CodeWeaver in client applications"""
    # Wrap FastMCP's install functionality with CodeWeaver-specific config
    fastmcp_install(client, server_path="codeweaver", name=name, copy=copy)
```

### Pydantic-AI CLI Integration Pattern

**Comparison with pydantic-ai CLI**:
```python
# pydantic-ai pattern (simple interactive CLI)
# uvx clai --model anthropic:claude-sonnet-4-0

# CodeWeaver enhanced pattern (structured workflow)
@app.command  
async def query(
    query: str,
    *,
    model: str = "anthropic:claude-sonnet-4-0",
    context_limit: int = 10000,
    interactive: bool = False,
    save_context: bool = False
) -> None:
    """Query codebase with AI assistance"""
    
    if interactive:
        # Interactive session like pydantic-ai clai
        await run_interactive_session(model=model)
    else:
        # Single query with codebase context
        context = await find_code(query, token_limit=context_limit)
        result = await query_with_context(query, context, model=model)
        
        if save_context:
            save_context_for_session(context, result)
            
        print(result)

@app.command
def precontext(
    goal: str,
    *,
    output: Optional[Path] = None,
    format: Literal["markdown", "json", "text"] = "markdown"
) -> None:
    """Generate precontext for development session"""
    # CodeWeaver's precontext generation capability
    context = generate_precontext(goal)
    
    if output:
        output.write_text(context)
    else:
        print(context)
```

### Advanced Configuration Integration

**Pattern**: Seamless pydantic-settings integration
```python
from cyclopts import App
from cyclopts.config import Toml, Json, Env
from pydantic_settings import BaseSettings

class CodeWeaverSettings(BaseSettings):
    """CodeWeaver configuration with multiple sources"""
    model_config = SettingsConfigDict(
        env_prefix="CW",
        env_nested_delimiter="__"
    )
    
    server_name: str = "CodeWeaver"
    max_tokens: int = 10000
    providers: List[ProviderConfig] = Field(default_factory=list)

# Multi-source configuration
app = App(
    name="codeweaver",
    config=[
        Env("CW"),  # Environment variables
        Toml("pyproject.toml", root_keys=["tool", "codeweaver"]),  # Project config
        Json(".codeweaver.json"),  # Local overrides
        Toml(".codeweaver.toml")   # Local TOML config
    ]
)

@app.command
def config_show() -> None:
    """Display current configuration"""
    settings = CodeWeaverSettings()
    print(settings.model_dump_json(indent=2))
```

### Async and Background Operations

**Pattern**: FastMCP-compatible async operations
```python
@app.command
async def index_background(
    path: Path = Path("."),
    *,
    watch: bool = False,
    collection: str = "codebase"
) -> None:
    """Index codebase in background with optional watching"""
    
    indexer = CodebaseIndexer(collection=collection)
    
    if watch:
        # Start background watcher (like watchfiles integration)
        watcher = start_file_watcher(path, indexer.update_file)
        print(f"Watching {path} for changes...")
        
        try:
            await indexer.index_directory(path)
            await watcher.wait()  # Keep running
        except KeyboardInterrupt:
            await watcher.stop()
    else:
        # Single indexing operation
        await indexer.index_directory(path)
        print(f"Indexed {path} successfully")

@app.command
async def query_interactive() -> None:
    """Start interactive CodeWeaver session"""
    
    print("CodeWeaver Interactive Session")
    print("Commands: /exit, /context, /clear, /save")
    
    session = InteractiveSession()
    
    while True:
        try:
            query = input("\n> ")
            
            if query.startswith('/'):
                await handle_special_command(query, session)
                continue
                
            # Query with codebase context
            result = await session.query_with_context(query)
            print(f"\n{result}")
            
        except KeyboardInterrupt:
            break
        except EOFError:
            break
    
    print("\nGoodbye!")
```

## Differences vs Project Requirements

### Alignment Strengths

1. **Type Safety Excellence**: Native support for Python type hints with enhanced `Annotated` patterns aligns perfectly with pydantic ecosystem

2. **Configuration Integration**: Built-in support for TOML, JSON, YAML, and environment variables enables seamless pydantic-settings integration

3. **FastAPI-like Patterns**: Decorator-based command registration and dependency injection patterns align with FastMCP and pydantic-ai architectures

4. **Async Native**: Full asyncio support enables seamless integration with FastMCP's async server patterns and pydantic-ai's async workflows

5. **Validation Framework**: Rich validation system with custom validators supports CodeWeaver's data integrity requirements

6. **Error Handling**: Rich, user-friendly error messages improve developer experience compared to basic argparse

7. **Extensibility**: Plugin-like architecture supports CodeWeaver's extensible design philosophy

### FastMCP CLI Enhancement Strategy

**CodeWeaver CLI as FastMCP Extension**:
```python
# Enhanced workflow vs FastMCP's basic commands
# FastMCP: fastmcp run server.py
# CodeWeaver: codeweaver serve --dev --watch --config .codeweaver.toml

# FastMCP: fastmcp install claude-desktop server.py
# CodeWeaver: codeweaver install claude-desktop --name codeweaver --providers voyage,qdrant
```

### Pydantic-AI CLI Enhancement Strategy

**CodeWeaver CLI as Structured Alternative**:
```python  
# Pydantic-AI: uvx clai --model anthropic:claude-sonnet-4-0
# CodeWeaver: codeweaver query "explain authentication" --model anthropic:claude-sonnet-4-0 --context-limit 15000

# Pydantic-AI: Interactive only
# CodeWeaver: codeweaver interactive + codeweaver precontext + codeweaver serve
```

### Integration Gaps (Minor)

1. **Configuration Mapping**: Need adapter layer between cyclopts config sources and pydantic-settings for unified configuration

2. **Command Chaining**: Cyclopts doesn't natively support command chaining (like `git add . && git commit`), but this can be implemented via meta commands

3. **Plugin Loading**: Dynamic command registration would require custom implementation on top of cyclopts

### Recommended Architecture

**Hybrid Approach**:
```python
from cyclopts import App
from fastmcp import FastMCP
from pydantic_ai import Agent
from pydantic_settings import BaseSettings

class CodeWeaverCLI:
    """Unified CLI combining cyclopts + FastMCP + pydantic-ai"""
    
    def __init__(self):
        self.app = App(name="codeweaver")
        self.fastmcp = FastMCP()
        self.settings = CodeWeaverSettings()
        self._register_commands()
    
    def _register_commands(self):
        """Register all CLI commands"""
        
        # Server management (FastMCP integration)
        self.app.command(self.serve)
        self.app.command(self.install)
        
        # AI interaction (pydantic-ai integration) 
        self.app.command(self.query)
        self.app.command(self.interactive)
        
        # CodeWeaver-specific
        self.app.command(self.index)
        self.app.command(self.config_show)

# Usage: python -m codeweaver serve --dev
#        python -m codeweaver query "how does auth work?"
#        python -m codeweaver index --watch
```

## Blocking Questions

1. **Configuration Precedence**: How should cyclopts configuration sources integrate with pydantic-settings hierarchy? Should cyclopts handle CLI-specific config while pydantic-settings handles application config?

2. **Command Organization**: Should CodeWeaver use sub-apps (like `codeweaver server start`) or flat commands (like `codeweaver serve`)? Sub-apps provide better organization but may complicate configuration inheritance.

3. **Async Event Loop**: How should the CLI handle async commands in different contexts (direct invocation vs. embedded in other async applications)?

4. **Plugin Architecture**: Does CodeWeaver need dynamic command registration for plugins? This would require custom implementation beyond cyclopts' static decorator approach.

## Non-blocking Questions

1. **Performance Impact**: What's the startup performance impact of cyclopts configuration loading vs. argparse?

2. **Help System Integration**: Should CodeWeaver provide additional help formats (interactive help, web-based docs) beyond cyclopts' built-in help?

3. **Testing Strategy**: What's the best approach for testing cyclopts commands with complex async behavior and configuration dependencies?

4. **Shell Completion**: How comprehensive is cyclopts' shell completion compared to dedicated tools like click?

## Sources

[Context7 Cyclopts Documentation | Context7 ID: /brianpugh/cyclopts | Trust Score: 9.6 | Code Snippets: 312]
- Core API patterns, App and Parameter configuration
- Configuration source integration (TOML, JSON, YAML, Env)
- Async command support and validation framework
- Type annotation patterns with Annotated and Parameter
- Advanced features: custom validators, group organization, error handling

[FastMCP CLI Documentation | URL: https://gofastmcp.com/patterns/cli | Reliability: 5]
- CLI command structure and entrypoint patterns
- Server management workflows and configuration handling
- Integration examples and best practices for MCP server deployment

[Pydantic-AI CLI Documentation | URL: https://ai.pydantic.dev/cli/ | Reliability: 5] 
- Interactive CLI patterns and model integration
- Agent configuration and custom CLI implementations
- Environment variable handling and extensibility patterns

[Cyclopts GitHub Repository | URL: https://github.com/brianpugh/cyclopts | Reliability: 5]
- Source code implementation details and advanced patterns
- Integration examples with pydantic, FastAPI, and async frameworks
- Community examples and real-world usage patterns

---

*This research provides comprehensive API intelligence for implementing CodeWeaver's CLI using cyclopts, with detailed comparisons to FastMCP and pydantic-ai CLI patterns. The analysis identifies optimal integration strategies while maintaining CodeWeaver's architectural principles of simplicity, extensibility, and type safety.*