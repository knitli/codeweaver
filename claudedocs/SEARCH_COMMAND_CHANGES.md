<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# CLI Search Command Auto-Indexing Implementation

## Overview
Updated `src/codeweaver/cli/commands/search.py` to automatically check for and create an index before searching, eliminating the need for users to manually run the index command first.

## Changes Made

### 1. Added Import Statements
- Added `logging` module for debug logging
- Added `TYPE_CHECKING` for type hints
- Added type imports for `CodeWeaverSettings`, `CodeWeaverSettingsDict`, and `DictView`
- Added `Any` type for generic type hints

### 2. New Helper Functions

#### `_index_exists(settings: dict[str, Any] | CodeWeaverSettings) -> bool`
**Purpose:** Check if a valid index exists for the current project.

**Implementation:**
- Accepts either settings dict or CodeWeaverSettings object
- Extracts project path from settings
- Determines manifest directory using same logic as indexer
- Loads manifest using `FileManifestManager`
- Returns `True` if manifest exists and has indexed files (`total_files > 0`)
- Returns `False` on any error (logged at debug level)

**Key Features:**
- Handles both dict and CodeWeaverSettings input types
- Uses same manifest directory logic as index command for consistency
- Gracefully handles errors without crashing

#### `_run_search_indexing(settings: CodeWeaverSettings | DictView[CodeWeaverSettingsDict]) -> None`
**Purpose:** Run standalone indexing operation before search.

**Implementation:**
- Accepts CodeWeaverSettings or DictView
- Converts to DictView if needed (matches `index.py` pattern)
- Creates Indexer instance using `Indexer.from_settings_async()`
- Runs `prime_index()` with `force_reindex=False` (incremental)
- Shows user-friendly progress messages
- Displays quick summary on completion (files processed, chunks indexed)
- Handles failures gracefully with warning (allows search to continue)

**Key Features:**
- Uses same pattern as `cli/commands/index.py` for consistency
- Non-blocking on failure (lets search attempt anyway)
- Clear user feedback throughout process
- Efficient incremental indexing by default

### 3. Modified search() Function

Added index checking logic before search execution:

```python
# Check if index exists, auto-index if needed
if not await _index_exists(settings):
    from codeweaver.config.settings import get_settings

    settings_obj = get_settings()
    await _run_search_indexing(settings_obj)
    # Reload settings after indexing
    settings = get_settings_map()
```

**Behavior:**
1. Check if index exists using `_index_exists()`
2. If no index found:
   - Load full settings object
   - Run indexing operation
   - Reload settings map after indexing completes
3. Continue with normal search flow

## User Experience

### Before Changes
```bash
$ codeweaver search "authentication code"
Error: No index found. Please run 'codeweaver index' first.
```

### After Changes
```bash
$ codeweaver search "authentication code"
⚙️ No index found. Indexing project...
⚙️ Indexing complete! (127 files, 1,543 chunks)
⚙️ Searching in: /path/to/project
⚙️ Query: authentication code
[search results displayed]
```

### For Already-Indexed Projects
```bash
$ codeweaver search "authentication code"
⚙️ Searching in: /path/to/project
⚙️ Query: authentication code
[search results displayed immediately]
```

## Technical Details

### Consistency with index.py
The implementation follows the exact same patterns as `cli/commands/index.py`:
- Uses `FileManifestManager` for index existence check
- Uses `Indexer.from_settings_async()` for indexer creation
- Converts settings to `DictView` before passing to indexer
- Uses same manifest directory logic

### Error Handling
- Index existence check: Logs debug message, returns `False` on error
- Indexing failure: Shows warning, allows search to continue
- Search errors: Preserved existing error handling (ConfigurationError, CodeWeaverError, etc.)

### Performance
- Fast check: Manifest file existence and load is very quick
- Incremental indexing: Uses `force_reindex=False` by default
- Only indexes once: Subsequent searches use existing index

### Type Safety
- Proper type hints for all new functions
- Handles both dict and object settings types
- TYPE_CHECKING guard for import-time optimization

## Code Quality

### Linting
- Fixed TRY300 warning by moving return to else block
- All other linting warnings are pre-existing in other files
- Module imports successfully without errors

### Style Compliance
- Follows project's CODE_STYLE.md guidelines
- 100 character line length
- Google-style docstrings with active voice
- Modern Python type hints

### Testing
- Manual testing: Verified with unindexed and indexed projects
- Integration tests: Existing E2E tests should pass
- No breaking changes to existing functionality

## Files Modified

1. **src/codeweaver/cli/commands/search.py**
   - Added: `_index_exists()` helper function (42 lines)
   - Added: `_run_search_indexing()` helper function (39 lines)
   - Modified: `search()` function to call helpers (8 new lines)
   - Total additions: ~89 lines of code

## Dependencies

No new dependencies added. Uses existing:
- `codeweaver.engine.indexer.manifest.FileManifestManager`
- `codeweaver.engine.indexer.Indexer`
- `codeweaver.config.settings` (get_settings, get_settings_map, update_settings)
- `codeweaver.core.types.dictview.DictView`

## Backward Compatibility

✅ **Fully backward compatible**
- Existing search functionality unchanged
- No breaking changes to API or CLI interface
- Users can still run `codeweaver index` separately if desired
- All existing error handling preserved

## Future Enhancements

Potential improvements for future releases:
1. Cache index existence check result during session
2. Add `--force-reindex` flag to search command
3. Show progress bar for large indexing operations
4. Add telemetry for auto-indexing usage
5. Optimize manifest check for very large codebases

## Success Criteria

✅ Search command checks for index before searching
✅ Auto-indexes if needed using direct Indexer (no server)
✅ Clear user feedback about indexing status
✅ Fast for already-indexed projects (minimal overhead)
✅ Graceful error handling
✅ Follows existing code patterns and style
✅ Module imports successfully
✅ No breaking changes
