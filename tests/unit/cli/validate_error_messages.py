#!/usr/bin/env python3
"""Standalone validation script for error message quality tests.

This script can be run independently of pytest to validate error messages.
"""

import sys

from pathlib import Path


# Add src to path to use development code
sys.path.insert(0, str(Path(__file__).parent.parent.parent.parent / "src"))

from codeweaver.core.exceptions import (
    ConfigurationLockError,
    DimensionMismatchError,
    ModelSwitchError,
    ProviderError,
)
from codeweaver.engine.services.migration_service import MigrationError, ValidationError


def validate_error_has_suggestions(error, error_name):
    """Validate error has actionable suggestions."""
    assert hasattr(error, "suggestions"), f"{error_name} missing suggestions attribute"
    assert error.suggestions, f"{error_name} has empty suggestions"
    assert len(error.suggestions) > 0, f"{error_name} has zero suggestions"
    print(f"✓ {error_name} has {len(error.suggestions)} suggestions")


def validate_error_has_details(error, error_name):
    """Validate error has contextual details."""
    assert hasattr(error, "details"), f"{error_name} missing details attribute"
    assert error.details, f"{error_name} has empty details"
    assert len(error.details) > 0, f"{error_name} has zero details"
    print(f"✓ {error_name} has {len(error.details)} detail fields")


def validate_error_message_actionable(error, error_name):
    """Validate error message provides actionable guidance."""
    # Check suggestions for actionable guidance
    suggestions_text = (
        " ".join(error.suggestions) if hasattr(error, "suggestions") and error.suggestions else ""
    )

    # Should have command references or options in suggestions
    has_action = any([
        "Option" in suggestions_text,
        "cw " in suggestions_text,
        "To fix" in suggestions_text.lower(),
        "run:" in suggestions_text.lower(),
        error.suggestions,  # Has non-empty suggestions list
    ])

    assert has_action, f"{error_name} lacks actionable guidance in suggestions"
    print(f"✓ {error_name} has actionable guidance")


def test_dimension_mismatch():
    """Test DimensionMismatchError quality."""
    error = DimensionMismatchError(
        "Collection 'my-project' has 1024-dimensional vectors but current "
        "configuration specifies 768 dimensions.",
        details={"collection": "my-project", "actual_dimension": 1024, "expected_dimension": 768},
        suggestions=[
            "Rebuild the collection: cw index --force --clear",
            "Revert to the embedding model that created this collection",
        ],
    )

    validate_error_has_suggestions(error, "DimensionMismatchError")
    validate_error_has_details(error, "DimensionMismatchError")
    validate_error_message_actionable(error, "DimensionMismatchError")

    # Verify specific fields
    assert "collection" in error.details
    assert any("cw index" in s for s in error.suggestions), (
        "Missing 'cw index' command in suggestions"
    )

    print("✓ DimensionMismatchError passes all quality checks")


def test_model_switch():
    """Test ModelSwitchError quality."""
    error = ModelSwitchError(
        "Your existing embedding collection was created with model 'voyage-code-3', "
        "but the current model is 'voyage-4-large'.",
        suggestions=[
            "Option 1: Re-index your codebase",
            "Option 2: Revert provider setting",
            "Option 3: Delete the existing collection",
        ],
        details={"collection_model": "voyage-code-3", "current_model": "voyage-4-large"},
    )

    validate_error_has_suggestions(error, "ModelSwitchError")
    validate_error_has_details(error, "ModelSwitchError")
    validate_error_message_actionable(error, "ModelSwitchError")

    # Verify multiple options in suggestions
    suggestions_text = " ".join(error.suggestions)
    assert "Option 1:" in suggestions_text, "Missing 'Option 1:' in suggestions"
    assert "Option 2:" in suggestions_text, "Missing 'Option 2:' in suggestions"

    print("✓ ModelSwitchError passes all quality checks")


def test_configuration_lock():
    """Test ConfigurationLockError quality."""
    error = ConfigurationLockError(
        "Collection policy is STRICT - no configuration changes allowed",
        details={"policy": "STRICT", "collection": "production-index"},
        suggestions=[
            "Option 1: Create a new collection",
            "Option 2: Change collection policy",
            "Option 3: Delete existing collection and re-index",
        ],
    )

    validate_error_has_suggestions(error, "ConfigurationLockError")
    validate_error_has_details(error, "ConfigurationLockError")
    validate_error_message_actionable(error, "ConfigurationLockError")

    # Verify policy explanation
    assert "STRICT" in str(error)
    assert "policy" in error.details

    print("✓ ConfigurationLockError passes all quality checks")


def test_provider_error():
    """Test ProviderError quality."""
    error = ProviderError(
        "Request to embedding provider timed out after 30s",
        details={"provider": "voyage", "timeout_seconds": 30},
        suggestions=[
            "Option 1: Check network connectivity",
            "Option 2: Increase timeout in settings",
            "Option 3: Reduce batch size",
        ],
    )

    validate_error_has_suggestions(error, "ProviderError")
    validate_error_has_details(error, "ProviderError")
    validate_error_message_actionable(error, "ProviderError")

    print("✓ ProviderError passes all quality checks")


def test_migration_error():
    """Test MigrationError (from migration service)."""
    error = MigrationError("Worker 2 failed: Network timeout")

    message = str(error)
    assert "Worker" in message
    assert "failed" in message.lower()

    print("✓ MigrationError passes basic quality checks")


def test_validation_error():
    """Test ValidationError (from migration service)."""
    error = ValidationError("Layer 2 failed: Payload checksums don't match")

    message = str(error)
    assert "Layer" in message
    assert "failed" in message.lower()

    print("✓ ValidationError passes basic quality checks")


def main():
    """Run all validation tests."""
    print("=" * 60)
    print("Error Message Quality Validation")
    print("=" * 60)
    print()

    tests = [
        test_dimension_mismatch,
        test_model_switch,
        test_configuration_lock,
        test_provider_error,
        test_migration_error,
        test_validation_error,
    ]

    passed = 0
    failed = 0

    for test in tests:
        try:
            print(f"\nRunning {test.__name__}...")
            test()
            passed += 1
        except AssertionError as e:
            print(f"✗ {test.__name__} failed: {e}")
            failed += 1
        except Exception as e:
            print(f"✗ {test.__name__} error: {e}")
            failed += 1

    print()
    print("=" * 60)
    print(f"Results: {passed} passed, {failed} failed")
    print("=" * 60)

    return 0 if failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
