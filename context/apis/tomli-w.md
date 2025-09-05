<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# tomli-w - TOML Writing API

## Summary

Feature Name: TOML configuration file writing
Feature Description: Pure Python TOML writer for generating configuration files
Feature Goal: Enable CodeWeaver to generate and write TOML configuration files programmatically

Primary External Surface(s): `tomli_w.dump()`, `tomli_w.dumps()`

Integration Confidence: high - Simple, stable API with clear documentation and wide adoption

## Core Types

Name | Kind | Definition | Role
--- | --- | --- | ---
TOMLDocument | Dict[str, Any] | Python dictionary with TOML-compatible values | Document structure
FileObject | BinaryIO | File opened in binary write mode | Output destination

## Signatures

### Function: dumps

Name: dumps
Import Path: `import tomli_w`
Concrete Path: https://pypi.org/project/tomli-w/ (Python package)
Signature: `tomli_w.dumps(doc: Dict[str, Any], *, indent: int = 4, multiline_strings: bool = False) -> str`
Params:
- doc: Dict[str, Any] (required) - Python dictionary containing TOML data
- indent: int (optional, default=4) - Array content indent width
- multiline_strings: bool (optional, default=False) - Allow multiline string format
Returns: str - TOML-formatted string representation
Errors: TypeError -> Invalid data types in dictionary
Notes: Converts Python dict to TOML string format, preserves input sort order

### Function: dump

Name: dump
Import Path: `import tomli_w` 
Concrete Path: https://pypi.org/project/tomli-w/ (Python package)
Signature: `tomli_w.dump(doc: Dict[str, Any], fp: BinaryIO, *, indent: int = 4, multiline_strings: bool = False) -> None`
Params:
- doc: Dict[str, Any] (required) - Python dictionary containing TOML data
- fp: BinaryIO (required) - File object opened in binary write mode
- indent: int (optional, default=4) - Array content indent width  
- multiline_strings: bool (optional, default=False) - Allow multiline string format
Returns: None - Writes directly to file
Errors: TypeError -> Invalid data types, OSError -> File write errors
Notes: Writes TOML data directly to file, requires binary mode

Type Information:
```python
from typing import Dict, Any, BinaryIO
```

## Type Graph

Dict[str, Any] -> dumps -> str
Dict[str, Any] -> dump -> BinaryIO -> None
dumps -> returns -> str
dump -> writes_to -> BinaryIO

## Request/Response Schemas

### String Generation
Purpose: Convert Python dict to TOML string for programmatic use
Request Shape: `{"doc": Dict[str, Any], "indent": int, "multiline_strings": bool}`
Response Shape: `str` (TOML-formatted string)
Variants: Configurable indentation and string formatting
Auth Requirements: None (local operation)

### File Writing
Purpose: Write TOML configuration directly to file
Request Shape: `{"doc": Dict[str, Any], "fp": BinaryIO, "indent": int, "multiline_strings": bool}`
Response Shape: None (side effect - file written)
Variants: Same configuration options as dumps()
Auth Requirements: File system write permissions

## Patterns

### Config Generation Pattern
```python
import tomli_w

config = {
    "server": {
        "host": "localhost", 
        "port": 8000
    },
    "features": ["indexing", "search"]
}

toml_string = tomli_w.dumps(config)
```

### File Writing Pattern  
```python
import tomli_w

config_data = {"app": {"name": "CodeWeaver"}}

with open("config.toml", "wb") as f:
    tomli_w.dump(config_data, f)
```

### Pydantic Integration Pattern
```python
import tomli_w
from pydantic import BaseModel

class Config(BaseModel):
    name: str
    version: str

config = Config(name="CodeWeaver", version="1.0")
toml_output = tomli_w.dumps(config.model_dump())
```

## Differences vs Project

Gap: CodeWeaver uses pydantic-settings for config management, needs integration with BaseSettings
Impact: Low - tomli-w complements pydantic-settings for config generation/export
Suggested Adapter: Create ConfigExporter that converts pydantic models to TOML via tomli-w

Blocking Questions: None - straightforward integration

Non-blocking Questions:
- Should CodeWeaver provide config templates via tomli-w?
- Do we need custom indentation settings for different config types?
- Should generated configs include comments (requires alternative library)?

## Sources

[tomli-w-pypi | official | 1.1.0 | 5] - https://pypi.org/project/tomli-w/
[real-python-tutorial | tutorial | current | 4] - https://realpython.com/lessons/write-toml-tomli-w/
[python-toml-guide | tutorial | current | 4] - https://realpython.com/python-toml/