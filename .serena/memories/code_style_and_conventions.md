# Code Style and Conventions

## Core Style Standards

### Line Length and Formatting
- **Line length**: 100 characters maximum
- **Auto-formatting**: Ruff (configuration in ruff.toml and pyproject.toml)
- **Shell formatting**: shfmt for bash/zsh scripts

### Docstrings
- **Convention**: Google style
- **Voice**: Active, present tense
- **Start with verbs**: "Adds numbers" not "This function adds numbers"
- **Brevity**: Don't explain the obvious - strong typing makes args/returns clear
- **Plain language**: Avoid jargon when simple terms work

Example:
```python
def calculate_total(items: list[int]) -> int:
    """Calculates sum of all items.
    
    Args:
        items: Numbers to sum
        
    Returns:
        Total sum of all items
    """
```

## Python Typing Standards

### Modern Python >=3.12 Syntax
- Use `typing.Self` for self-references
- Use `typing.Literal` for string literals
- Use piped unions: `int | str` (not `Union[int, str]`)
- Use constructors as types: `list[str]` (not `List[str]`)
- Use `type` keyword: `type MyAlias = tuple[str]` (not `TypeAlias`)
- Use parameterized generics: `class MyClass[T]:` (not `Generic[T]`)

### Structured Data Types
**Prefer domain-specific types over generic dicts:**
- Complex objects: `pydantic.BaseModel` descendants (use project's `BasedModel`)
- Simple objects with methods: `NamedTuple`
- Simple objects for typing: `TypedDict`
- Enumerations: `enum.Enum` (use project's `BaseEnum`)
- Type guards: `typing_extensions.TypeIs` or `typing.TypeGuard`

**Project-Specific Base Classes:**
- `dataclass` → `codeweaver.core.types.models.DataclassSerializationMixin`
- `BaseModel` → `codeweaver.core.types.models.BasedModel`
- `Enum` → `codeweaver.core.types.enum.BaseEnum`

### Type Hints Requirements
- **All public functions** must have type annotations including `-> None`
- **Strict typing** with opinionated pyright/ty rules
- **Boolean kwargs only**: Use `*` separator for boolean parameters

Example:
```python
def my_function(arg1: str, *, flag: bool = False) -> None:
    """Does something with flag."""
    pass
```

### When to Use Each Type
- **Literal vs Enum**: Prefer `BaseEnum` over `Literal` except for 1-3 values used once
- **Avoid vague types**: Only use `dict[str, Any]` when structure is truly unknown
- **Define structures**: Use TypedDict/NamedTuple/dataclass/BaseModel for known structures

## Pydantic Architecture Patterns

### Key Design Patterns (from FastAPI/pydantic ecosystem)
- **Flexible Generics**: Few broadly-defined models/protocols for wide reuse
- **Smart Decorators**: Extend class/function roles cleanly
- **Dependency Injection**: Explicit dependencies, organized pipelines
- **Flat Structure**: Group related modules in packages, keep root-level otherwise
- **Types as Functionality**: Types *are* the behavior, not separate

### Pydantic Models
```python
from typing import Annotated
from pydantic import ConfigDict, Field
from codeweaver.core.types import BasedModel

class MyModel(BasedModel):
    model_config = ConfigDict(extra="forbid")  # or "allow" for plugins
    
    name: Annotated[str, Field(description="Item name")]
    value: Annotated[int, Field(ge=0, description="Non-negative value")] = 0
```

## Lazy Evaluation & Immutability

### Why: Performance + memory efficiency + fewer bugs

**Sequences**:
- Use `Generator`/`AsyncGenerator` over lists when possible
- Use `tuple`/`NamedTuple` for fixed sequences
- Use `frozenset` for set-like immutable objects

**Dicts**:
- Use `types.MappingProxyType` for read-only dicts

**Models**:
- Use `frozen=True` for dataclasses/models set at instantiation
- Create new instances rather than mutating (but be reasonable)

## Common Patterns and Anti-Patterns

### Logging
✅ **DO**: Use `%s` formatting or `extra={"key": value}`
❌ **DON'T**: Use f-strings in log statements
❌ **DON'T**: Use print statements in production code
✅ **DO**: Use `logging.exception` for exceptions (includes traceback automatically)

### Exception Handling
✅ **DO**: Specify exception types (no bare `except:`)
✅ **DO**: Use `else` for returns after `try` blocks
✅ **DO**: Use `raise from` to maintain exception context
✅ **DO**: Use `contextlib.suppress` for intentional suppression
✅ **DO**: Raise to specific codeweaver exceptions (`codeweaver.exceptions`)

### isinstance Calls
✅ **DO**: Use `|` syntax: `isinstance(value, str | int | MyClass)`
❌ **DON'T**: Use tuple syntax: `isinstance(value, (str, int, MyClass))`

## Import Organization
Follow standard Python import ordering:
1. Standard library imports
2. Third-party imports
3. Local/project imports

Ruff will automatically organize and fix imports.
