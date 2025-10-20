<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Code Style Guide

## Design Principles

1. **AI-First Context**: Deliver precise codebase context for agent requests
2. **Simple AI Interface**: Agents don't need to create requests that fit complex data structures. Tool calls should be in plain language with no more than one required parameter.
2. **Transparency**: Clear, understandable processes and results for developers
3. **Simple Modularity**: Extensible yet intuitive - purpose should be obvious
4. **Ecosystem Alignment**: Leverage pydantic ecosystem (`pydantic`, `pydantic-settings`, `pydantic-ai`, `FastMCP` (uses pydantic)) over reinvention
5. **Proven Patterns**: Follow established abstractions - simple, powerful, well-validated interfaces

## Pydantic Architecture

**Why**: Familiar patterns reduce learning curve, plus it's clean and effective.

Study pydantic ecosystem patterns: [pydantic](https://github.com/pydantic/pydantic), [FastAPI](https://github.com/fastapi/fastapi), [FastMCP](https://github.com/jlowin/fastmcp), [pydantic-ai](https://github.com/pydantic/pydantic-ai/tree/main/pydantic_ai_slim/).

### Key Patterns

- **Flexible Generics**: Few broadly-defined models/protocols/ABCs for wide reuse
- **Smart Decorators**: Extend class/function roles cleanly (think: '`@pydantic.after_validator` or basically **all of `FastAPI`**)
- **Dependency Injection**: Explicit dependencies, organized pipelines
- **Flat Structure**: Group closely related modules in packages (e.g. all providers), otherwise keep root-level
    - Core types in `__init__.py` if a subpackage (not root __init__.py)
    - Foundations in private mirror modules (`chunking.py` ← `_chunking.py`)
    - Extensive internal logic in an `_internals` subpackage.
- **Types as Functionality**: Types *are* the behavior, not separate from it

## Style Standards

- **Docstrings**: Google convention, plain language, active voice, present tense
    - Start with verbs: "Adds numbers" not "This function adds numbers"
    - **But not exacting**: Don't waste space explaining the obvious. We have strong typing that makes args/returns clear. A brief sentence may be enough. 
- **Line length**: 100 characters
- **Auto-formatting**: Ruff configuration enabled
- **Python typing**: Modern (≥3.11) - `typing.Self`, `typing.Literal`, piped unions (`int | str`), constructors as types (`list[str]`), `type` keyword for `typing.TypeAliasType`.

## Lazy Evaluation & Immutability

**Why**: Performance + memory efficiency + fewer debugging headaches

- **Sequences**: Use `Generator`/`AsyncGenerator`, `tuple`/`NamedTuple` over lists. Use `frozenset` for set-like objects
- **Dicts**: Read-only dicts use `types.MappingProxyType`
- **Models**: Use `frozen=True` for dataclasses/models set at instantiation
    - Need modifications? Create new instances rather than mutating [^1]
    - Need computed properties? Use factory functions or classmethods

[^1]: But be reasonable. If you really need to make a lot of incremental updates to an object, then *use a mutable type* -- it's a guideline, not a rule.

## Typing Guidelines 🏴‍☠️

**Why**: Maintainability, self-documentation, easier debugging. Get it right upfront.

- **Strict typing** with [opinionated pyright rules](pyproject.toml)
- **Structured data**: Use `TypedDict`, `Protocol`, `NamedTuple`, `enum.Enum`, `typing_extensions.TypeIs` (similar to typing.TypeGuard but more flexible, typing.TypeGuard also OK)
    - Use the project's derivative for these: 
      - `dataclass` -> `pydantic.dataclasses.dataclass` **and** `codeweaver._common.DataclassSerializationMixin`
      - `pydantic.BaseModel` -> `codeweaver._common.BasedModel`
      - `pydantic.ConfigDict` -> 
      - `enum.Enum` -> `codeweaver._common.BaseEnum`
- **Define structures**: Don't be lazy - use `TypedDict`, `NamedTuple`, `dataclass` or `BasedModel` to define structured data. Only use vague/generic types like `dict[str, Any]` when the types/structure are truly unknown or have many possibilities.
    - Complex objects: `dataclass` or `BaseModel` descendants
    - Simple objects: `NamedTuple` if the object would benefit from methods or will be nested; `TypedDict` otherwise. 
- **Generics**: Define proper generic types/protocols/guards
    - Use newer python parameterized generics syntax: `class SomeClass[SomeGeneric]:` -- don't use `typing.Generic`
    - Use newer `type` keyword for aliases: `type MyAlias = tuple[Literal["like this"]]` not `TypeAlias`
- **Avoid string literals**: For most cases, favor `enum.Enum` (using `BaseEnum`) over `typing.Literal` (CLI: `cyclopts` handles enum parsing).
    - Exception: If the type will only be used once in one small section, and there are only 1-3 valid values, `Literal` is OK, but must be typed with `Literal`
    - Keep properties with their objects. Use `enum` methods to keep logic related to members with the class. You shouldn't add/define properties or attributes for members elsewhere (see `codeweaver.language.SemanticSearchLanguage` for an extreme example).

### Pydantic Models

```python
from typing import Annotated
from pydantic import ConfigDict, Field

from codeweaver._common import BasedModel

class MyModel(BasedModel):
    model_config = ConfigDict(extra="allow")

    name: Annotated[str, Field(description="Item name")]
    value: Annotated[int, Field(ge=0, description="Non-negative value")] = 0
```

- Use `ConfigDict` for configuration (`extra="allow"` for plugins, `extra="forbid"` for strict)
- Prefer domain-specific subclasses (codeweaver's `BasedModel` for most, `BaseNode` for pydantic graph) over raw `BaseModel`

## Common Linting Issues

### Logging

- **No f-strings in log statements**: Use `%s` formatting or `extra={"key": value}`
- **No print statements**: Use logging in production
- **Use logging.exception**: For exceptions with **no exception object in the statements** (logging.exception automatically includes the object)
  - Don't use logging.error if you can use logging.exception

### Exception Handling

- **Specify exception types**: No bare `except:`
- **Use `else` for returns**: After `try` blocks for clarity
- **Use `raise from`**: Maintain exception context
- **Use `contextlib.suppress`**: For intentional exception suppression

- If raising an exception, raise to a specific, codeweaver exception (`codeweaver.exceptions`)

### Functions

- **Type all call arguments/parameters and returns**: Including `-> None`
- **Boolean kwargs only**: Use `*` separator for boolean parameters (booleans should not be positional arguments)


```python
def my_function(arg1: str, *, flag: bool = False) -> None:
    pass
```

Follow [Google Python Style Guide](https://google.github.io/styleguide/pyguide.html). See [auto-fix script](scripts/fix-ruff-patterns.sh).

### IsInstance

- Use `|` syntax, not tuple: `isinstance(value, str | int | MyClass)` (not `(str, int, MyClass)`) (yes, it really is valid python, I promise.)

## Testing Philosophy

**Effectiveness over coverage.** We prioritize meaningful tests over metrics.

### Why Not 100% Coverage?

- Doesn't improve user experience
- Doesn't prevent important bugs
- Tests implementation details, not behavior
- Creates barriers to innovation and change ("ugh, we have to update all those tests...")
- Wastes time maintaining low-value tests

### Focus Instead On

- **Critical behavior** affecting user experience
- **Realistic integration scenarios**
- **Input/output validation** for important functions

**One solid, realistic test is better than 10 implementation detail tests**

**Integration testing > unit testing** for most cases.

### Make Sure to Include Appropriate Marks for New Tests

We have a long (probably too long) list of pytest marks that allow us to run granular tests.  **If you write a new test, review [the list](./pyproject.toml#L307), and apply all applicable marks.**