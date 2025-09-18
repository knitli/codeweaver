<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# rignore - File Walking with Ignore Support API

## Summary

Feature Name: Intelligent file system traversal with ignore patterns
Feature Description: Rust-powered Python library for efficient directory walking that respects .gitignore and other ignore files
Feature Goal: Provide high-performance file discovery for CodeWeaver's indexing while respecting developer ignore preferences

Primary External Surface(s): `rignore.walk()`, `Walker` class (iterator protocol)

Integration Confidence: high - Simple API with excellent performance, well-maintained Rust backend

## Core Types

Name | Kind | Definition | Role
--- | --- | --- | ---
Walker | Iterator[Path] | File system iterator | Main traversal interface  
FilterFunc | Callable[[Path], bool] | Custom filtering function | Additional entry filtering
IgnorePattern | str | Glob-style pattern | File matching rule

## Signatures

### Function: walk

Name: walk
Import Path: `import rignore`
Concrete Path: https://github.com/patrick91/rignore/blob/main/src/lib.rs (Python bindings)
Signature: `rignore.walk(path: Path, **kwargs) -> Iterator[Path]`
Params:
- path: Path (required) - Root directory for traversal
- ignore_hidden: bool (optional, default=True) - Skip hidden files/directories
- read_ignore_files: bool (optional, default=True) - Process .ignore files
- read_parents_ignores: bool (optional, default=True) - Read ignore files from parent dirs
- read_git_ignore: bool (optional, default=True) - Respect .gitignore files
- read_global_git_ignore: bool (optional, default=True) - Use global Git ignore
- read_git_exclude: bool (optional, default=True) - Use Git exclude files
- require_git: bool (optional, default=False) - Require Git repository
- additional_ignores: List[str] (optional) - Extra ignore patterns
- additional_ignore_paths: List[str] (optional) - Extra ignore file paths
- max_depth: int (optional) - Maximum traversal depth
- max_filesize: int (optional) - Maximum file size in bytes
- follow_links: bool (optional, default=False) - Follow symbolic links
- case_insensitive: bool (optional, default=False) - Case-insensitive patterns
- same_file_system: bool (optional, default=False) - Stay on same filesystem
- should_exclude_entry: Callable[[Path], bool] (optional) - Custom filter function

Returns: Iterator[Path] - Lazy iterator of filtered file paths
Errors: OSError -> File system access errors, ValueError -> Invalid parameters
Notes: Returns Path objects, not strings; lazy evaluation for memory efficiency

Type Information:
```python
from pathlib import Path
from typing import Iterator, List, Optional, Callable
```

### Class: Walker

Name: Walker
Import Path: `from rignore import Walker`
Concrete Path: https://github.com/patrick91/rignore/ (internal implementation)
Constructor: `Walker(path: Path, **same_params_as_walk)`
Methods:
- `__iter__() -> Iterator[Path]` - Iterator protocol
- `__next__() -> Optional[Path]` - Iterator protocol

### Complete Signatures

```python
from pathlib import Path
from typing import Callable, Iterator, List, Optional

class Walker:
    def __init__(
        self,
        path: Path,
        ignore_hidden: Optional[bool] = None,
        read_ignore_files: Optional[bool] = None,
        read_parents_ignores: Optional[bool] = None,
        read_git_ignore: Optional[bool] = None,
        read_global_git_ignore: Optional[bool] = None,
        read_git_exclude: Optional[bool] = None,
        require_git: Optional[bool] = None,
        additional_ignores: Optional[List[str]] = None,
        additional_ignore_paths: Optional[List[str]] = None,
        max_depth: Optional[int] = None,
        max_filesize: Optional[int] = None,
        follow_links: Optional[bool] = None,
        case_insensitive: Optional[bool] = None,
        same_file_system: Optional[bool] = None,
        should_exclude_entry: Optional[Callable[[Path], bool]] = None,
    ) -> None: ...
    def __iter__(self) -> Iterator[Path]: ...
    def __next__(self) -> Optional[Path]: ...

def walk(
    path: Path,
    ignore_hidden: Optional[bool] = None,
    read_ignore_files: Optional[bool] = None,
    read_parents_ignores: Optional[bool] = None,
    read_git_ignore: Optional[bool] = None,
    read_global_git_ignore: Optional[bool] = None,
    read_git_exclude: Optional[bool] = None,
    require_git: Optional[bool] = None,
    additional_ignores: Optional[List[str]] = None,
    additional_ignore_paths: Optional[List[str]] = None,
    max_depth: Optional[int] = None,
    max_filesize: Optional[int] = None,
    follow_links: Optional[bool] = None,
    case_insensitive: Optional[bool] = None,
    same_file_system: Optional[bool] = None,
    should_exclude_entry: Optional[Callable[[Path], bool]] = None,
) -> Walker: ...

```

## Type Graph

Path -> walk -> Iterator[Path]
Path -> Walker -> Iterator[Path]  
Walker -> implements -> Iterator[Path]
Callable[[Path], bool] -> filters -> Path

## Request/Response Schemas

### Basic File Walking
Purpose: Traverse directory tree with ignore patterns
Request Shape: `{"path": Path, "read_git_ignore": bool, "ignore_hidden": bool}`
Response Shape: `Iterator[Path]` (lazy file path iterator)
Variants: Extensive configuration options for filtering
Auth Requirements: File system read permissions

### Advanced Filtering  
Purpose: Custom file filtering with size/depth limits
Request Shape: `{"path": Path, "max_depth": int, "max_filesize": int, "should_exclude_entry": Callable}`
Response Shape: `Iterator[Path]` (filtered results)
Variants: Combine multiple filtering strategies
Auth Requirements: File system read permissions

## Patterns

### Basic Directory Walking
```python
import rignore
from pathlib import Path

for file_path in rignore.walk(Path("./src")):
    print(file_path)
```

### Configured Filtering
```python
import rignore
from pathlib import Path

for file_path in rignore.walk(
    Path("./project"),
    ignore_hidden=True,
    read_git_ignore=True,
    max_depth=5,
    max_filesize=1024 * 1024 * 4 # 4MB
):
    # Process only non-ignored files under 4MB
    process_file(file_path)
```

### Custom Filtering
```python
import rignore
from pathlib import Path

from codeweaver.language import SemanticSearchLanguage
from co

def is_source_file(path: Path) -> bool:
    return path.suffix.lstrip(".") in SemanticSearchLanguage.extensions_map()

def is_config_file(path: Path) -> bool:
    return path in SemanticSearchLanguage.all_config_paths()

for file_path in rignore.walk(
    Path("./codebase"),
    should_exclude_entry=lambda p: not is_source_file(p)
):
    index_source_file(file_path)

# Note: Actual implementation should incorporate config settings 
```

## Differences vs Project

Gap: Current filtering.py implementation adds additional filtering layers on top of rignore
Impact: Medium - Existing implementation works but could be optimized to use more rignore-native features
Suggested Adapter: Refactor FileFilteringMiddleware to leverage rignore's native filtering more extensively

### Current Implementation Analysis

**Strengths of existing filtering.py:**
- Good FastMCP middleware integration
- Defensive programming with fallbacks
- Additional filtering (file size, extensions) beyond rignore
- Proper error handling and logging
- Configuration-driven behavior

**Recommended Improvements:**
1. **Use rignore's max_filesize parameter** instead of post-filtering
2. **Leverage additional_ignores parameter** for custom patterns 
3. **Use should_exclude_entry** for extension filtering instead of post-processing
4. **Consider using Walker class** for better control over iteration
5. **Full shift to path-based filtering** from string-based approach.

**Optimized Integration Pattern:**
```python
def find_files_optimized(self, base_path: Path, patterns: list[str] | None = None) -> list[Path]:
    """Optimized rignore integration using native filtering."""
    
    def extension_filter(path: Path) -> bool:
        if self.included_extensions:
            return path.suffix.lower() in self.included_extensions
        return True
    
    walker = rignore.walk(
        base_path,
        ignore_hidden=self.ignore_hidden,
        read_git_ignore=self.use_gitignore,
        max_filesize=self.max_file_size,  # Native size filtering
        additional_ignores=self.additional_ignore_patterns,  # Native pattern filtering
        should_exclude_entry=extension_filter  # Native extension filtering
    )
    
    return [p for p in walker if self._matches_patterns(p, patterns or ["*"])]
```

Non-blocking Questions:
- Should we expose Walker class directly for advanced use cases?
- Do we need caching for repeated directory scans?
- Should we add progress reporting for large directory scans?

## Sources

[rignore-github | official | main | 4] - https://github.com/patrick91/rignore/
[rignore-pypi | official | 0.6.4 | 4] - https://pypi.org/project/rignore/
[rust-ignore-crate | underlying | latest | 5] - Rust ignore crate documentation (referenced by rignore)
[existing-filtering-py | codebase | current | 5] - /home/knitli/codeweaver-mcp/src/codeweaver/middleware/filtering.py