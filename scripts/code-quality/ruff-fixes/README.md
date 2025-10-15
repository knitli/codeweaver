<!--
SPDX-FileCopyrightText: 2025 Knitli Inc.

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Ruff Pattern Fixer Scripts

These scripts automatically fix common ruff linting violations that can't be auto-fixed by ruff itself.

## Scripts

### `fix-ruff-patterns.sh`
Main orchestration script that fixes three types of violations:
- **G004**: F-strings in logging calls → converted to `%` format  
- **TRY401**: Redundant exception references in `logging.exception()` calls
- **TRY300**: Return statements in try blocks → moved to else blocks

### `f_string_converter.py`
Python AST-based converter for logging f-strings that handles complex expressions and variable extraction.

## Usage

```bash
# Fix patterns in current directory
./fix-ruff-patterns.sh

# Fix patterns in specific files/directories  
./fix-ruff-patterns.sh src/ tests/ main.py

# Skip ruff verification (useful if ruff hangs)
./fix-ruff-patterns.sh --skip-verify src/

# Test the f-string converter directly
python3 f_string_converter.py src/
```

## What Gets Fixed

### G004 - Logging F-strings
**Before:**
```python
logger.info(f"Processing user {user_id}")
logger.error(f"Error with {value} in function")
```

**After:**
```python
logger.info("Processing user %s", user_id)
logger.error("Error with %s in function", value)
```

### TRY401 - Redundant Exception Logging with Smart Punctuation Cleanup
**Before:**
```python
try:
    risky_operation()
except Exception as e:
    logger.exception("Failed: %s", e)         # e is redundant  
    logging.exception(f"Database error - {e}") # {e} is redundant
    logger.exception("Connection timeout (%s)", e)  # e is redundant
```

**After:**
```python
try:
    risky_operation()
except Exception as e:
    logger.exception("Failed")                # Cleaned trailing ": %s"
    logging.exception("Database error")       # Cleaned trailing " - %s" 
    logger.exception("Connection timeout")    # Cleaned trailing " (%s)"
```

**Smart Cleanup Patterns:**
- `"Error: %s", e` → `"Error"`
- `"Error - %s", e` → `"Error"`  
- `"Error (%s)", e` → `"Error"`
- `"Error, %s", e` → `"Error"`
- `"Error %s.", e` → `"Error"`

### TRY300 - Return in Try Block
**Before:**
```python
try:
    result = calculate()
    return result          # Should be in else block
except ValueError:
    return None
```

**After:**
```python
try:
    result = calculate()
except ValueError:
    return None
else:
    return result          # Moved to else block
```

## AST-Grep Rules

The `rules/` directory contains 10 ast-grep pattern files:

- `fix-exception-logging-with-var.yml` - TRY401 for `%` format logging
- `fix-exception-logging-fstring-*.yml` - TRY401 for f-string patterns (3 files)
- `fix-try-return-*.yml` - TRY300 for various try/return patterns (5 files)
- `fix-logging-fstring-simple.yml` - G004 basic f-string pattern

## Requirements

- `python3` - For f-string converter
- `ast-grep` - For pattern-based transformations
- `ruff` (optional) - For verification

## Troubleshooting

If the script hangs during ruff verification:
```bash
# Use --skip-verify flag
./fix-ruff-patterns.sh --skip-verify your_files

# Or manually verify afterwards
ruff check your_files --select=TRY401,G004,TRY300
```

## Architecture

1. **Step 1**: Python AST parser handles complex f-string → `%` format conversion
2. **Step 2a**: AST-grep rules fix basic redundant exception references  
3. **Step 2b**: Python AST parser intelligently cleans trailing punctuation when removing exceptions
4. **Step 3**: AST-grep rules move returns from try to else blocks
5. **Step 4**: Optional ruff verification with timeout protection

The hybrid approach (Python AST + ast-grep) handles edge cases that pure pattern matching can't solve while maintaining speed and reliability.

### Smart Punctuation Cleanup

The `punctuation_cleaner.py` script uses AST analysis to intelligently clean up trailing punctuation when removing redundant exception arguments:

- **Pattern Recognition**: Identifies common punctuation patterns (`:`, `-`, `()`, `,`, `.`)
- **Context Aware**: Only removes punctuation when it's trailing an exception reference
- **Safe Transformation**: Preserves message meaning while cleaning up redundant syntax

**Supported Patterns:**
```python
# All of these become logger.exception("Error occurred")
logger.exception("Error occurred: %s", e)      # Colon cleanup
logger.exception("Error occurred - %s", e)     # Dash cleanup  
logger.exception("Error occurred (%s)", e)     # Parentheses cleanup
logger.exception("Error occurred, %s", e)      # Comma cleanup
logger.exception("Error occurred %s.", e)      # Period cleanup
```