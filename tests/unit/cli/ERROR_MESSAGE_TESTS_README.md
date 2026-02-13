# Error Message Quality Tests

## Overview

This directory contains comprehensive error message quality tests as specified in Phase 3 of the unified implementation plan. These tests ensure that all error messages across CodeWeaver provide clear, actionable guidance to users.

## Files

### `test_error_messages.py`

Main pytest test file containing comprehensive error message quality tests organized into test classes:

- **TestErrorMessageActionability**: Verifies errors provide clear next steps
- **TestErrorMessageStructure**: Validates structural quality (suggestions, details, commands)
- **TestJargonExplanation**: Ensures technical terms are explained
- **TestErrorMessageConsistency**: Validates consistent patterns
- **TestErrorMessageCompleteness**: Ensures complete information
- **TestRealErrorScenarios**: Integration tests with real error scenarios
- **TestMessageFormatting**: Validates formatting quality

### `validate_error_messages.py`

Standalone validation script that can be run independently of pytest. Useful for:
- Quick validation during development
- CI/CD environments with import issues
- Debugging specific error message patterns

Run with: `python tests/unit/cli/validate_error_messages.py`

## Error Scenarios Tested

### 1. Dimension Mismatch Error
**Scenario**: Embedding dimensions don't match vector store collection configuration

**Quality Requirements**:
- Clear explanation of what happened
- Command to rebuild collection
- Suggestion to revert to original model
- Details include actual vs expected dimensions

### 2. Model Switch Error
**Scenario**: Embedding model changed from what was used to create collection

**Quality Requirements**:
- Multiple resolution options (3+)
- Explanation of incompatibility
- Specific model names in details
- Commands for re-indexing or reverting

### 3. Configuration Lock Error
**Scenario**: Attempted configuration change violates collection policy

**Quality Requirements**:
- Policy explanation (STRICT, FAMILY_AWARE, etc.)
- Multiple workaround options
- Commands for creating new collection or changing policy
- Details include attempted change

### 4. Family Lock Error
**Scenario**: Model change breaks family compatibility

**Quality Requirements**:
- Explanation of model families
- Documentation link for model families
- Suggestion of compatible alternatives
- Details include current and indexed families

### 5. Network Timeout Error
**Scenario**: Provider API call timed out

**Quality Requirements**:
- Explanation of what timed out
- Troubleshooting steps (network, timeout settings, batch size)
- Provider status link if available
- Details include timeout duration and provider

### 6. Checkpoint Corruption Error
**Scenario**: Checkpoint file cannot be loaded

**Quality Requirements**:
- Explanation of corruption
- Recovery options (delete, restore from backup)
- Fresh start option
- File path in details

### 7. Profile Version Mismatch Error
**Scenario**: Profile created with incompatible CodeWeaver version

**Quality Requirements**:
- Version incompatibility explanation
- Upgrade suggestion
- Compatible profile alternative
- Version numbers in details

### 8. Migration Validation Error
**Scenario**: Data integrity validation failed during migration

**Quality Requirements**:
- Layer identification (Layer 1, Layer 2, etc.)
- Explanation of validation failure
- Recovery guidance

### 9. Migration Worker Error
**Scenario**: Migration worker failed (crash, timeout, etc.)

**Quality Requirements**:
- Worker identification
- Failure reason
- Resume capability indication

## Quality Standards

All error messages must meet these standards:

### Actionability
- ✅ Clear next steps ("To fix:", "Run: cw", "Options:")
- ✅ Multiple resolution options when appropriate
- ✅ Specific commands with necessary flags

### Structure
- ✅ Suggestions list with actionable items
- ✅ Details dict with contextual information
- ✅ Valid command references

### Clarity
- ✅ Technical jargon explained or linked to docs
- ✅ User-friendly terminology
- ✅ Consistent formatting

### Completeness
- ✅ Affected collection identified
- ✅ Provider identified for provider errors
- ✅ Configuration details included

### Consistency
- ✅ Sequential option numbering (Option 1:, Option 2:, etc.)
- ✅ Consistent command format (cw, not codeweaver)
- ✅ Consistent documentation URLs (docs.codeweaver.dev)

## Running Tests

### Full pytest suite
```bash
pytest tests/unit/cli/test_error_messages.py -v
```

### Specific test class
```bash
pytest tests/unit/cli/test_error_messages.py::TestErrorMessageActionability -v
```

### Single test
```bash
pytest tests/unit/cli/test_error_messages.py::TestErrorMessageActionability::test_dimension_mismatch_has_guidance -v
```

### Standalone validation
```bash
python tests/unit/cli/validate_error_messages.py
```

## Implementation Notes

### Error Structure

CodeWeaver errors follow this structure:

```python
class CodeWeaverError(Exception):
    def __init__(
        self,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        suggestions: list[str] | None = None,
        location: LocationInfo | None = None,
    ):
        ...
```

**Important**: The `__str__` method does NOT include suggestions in the output. Tests must check:
1. `error.message` - The main error message
2. `error.suggestions` - List of actionable suggestions
3. `error.details` - Contextual information dict

### Testing Pattern

```python
def test_error_quality():
    error = create_error()

    # Check message content
    assert "important info" in error.message

    # Check suggestions
    suggestions_text = " ".join(error.suggestions)
    assert "Option 1:" in suggestions_text
    assert "cw command" in suggestions_text

    # Check details
    assert "key_field" in error.details
```

### Common Patterns

**Multiple Options**:
```python
suggestions=[
    "Option 1: Do this",
    "Option 2: Or do that",
    "Option 3: Or try this",
]
```

**Command References**:
```python
suggestions=[
    "Rebuild: cw index --force --clear",
    "Check status: cw doctor",
]
```

**Documentation Links**:
```python
suggestions=[
    "Learn more: https://docs.codeweaver.dev/topic",
]
```

## Integration with Unified Implementation Plan

These tests implement **Phase 3: Error Message Quality** from the unified implementation plan (lines 2212-2246):

- [x] Test all errors have clear next steps
- [x] Test all errors have error codes for documentation lookup (via details)
- [x] Test jargon explanations or links
- [x] Test dimension mismatch errors
- [x] Test network timeout errors
- [x] Test checkpoint corruption errors
- [x] Test migration failure errors
- [x] Test configuration lock errors
- [x] Test profile version incompatibility errors

## Future Enhancements

### Additional Error Scenarios
- WAL configuration errors
- Sparse embedding errors
- Reranking provider errors
- Persistence errors

### Enhanced Validation
- Error code registry validation
- Documentation link validation (actual link checking)
- Translation/i18n support
- Accessibility validation (screen reader friendly)

### Automation
- Auto-generate error documentation from test cases
- Error message linting in CI/CD
- User feedback integration for error message improvement

## Contributing

When adding new error types:

1. Create error trigger function in `test_error_messages.py`
2. Add test methods for:
   - Actionability
   - Structure
   - Clarity
   - Completeness
3. Add to standalone validation script
4. Update this README with the new scenario
5. Ensure all quality standards are met

## References

- **Unified Implementation Plan**: `claudedocs/unified-implementation-plan.md` (lines 2212-2246)
- **Exception Definitions**: `src/codeweaver/core/exceptions.py`
- **Migration Service**: `src/codeweaver/engine/services/migration_service.py`
- **Vector Store Types**: `src/codeweaver/providers/types/vector_store.py`
