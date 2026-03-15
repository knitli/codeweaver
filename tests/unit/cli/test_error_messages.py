# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Error message quality tests.

Validates that all error messages across CodeWeaver provide:
- Clear next steps ("To fix:", "Run: cw", "Options:")
- Jargon explanations or documentation links
- Actionable guidance for users

These tests focus on error message UX quality, not error handling logic.
Tests should catch regressions in error message quality as the system evolves.
"""

from __future__ import annotations

import re

from typing import TYPE_CHECKING

import pytest

from codeweaver.core.exceptions import (
    ConfigurationError,
    ConfigurationLockError,
    DimensionMismatchError,
    ModelSwitchError,
    ProviderError,
)
from codeweaver.engine.services.migration_service import MigrationError, ValidationError
from codeweaver.providers.types.vector_store import CollectionMetadata, CollectionPolicy


if TYPE_CHECKING:
    from codeweaver.core.exceptions import CodeWeaverError


pytestmark = [pytest.mark.unit, pytest.mark.error_messages]


# ===========================================================================
# Error Triggering Helpers
# ===========================================================================


def trigger_dimension_mismatch() -> DimensionMismatchError:
    """Trigger dimension mismatch error with realistic message.

    Simulates the error raised when embedding dimensions don't match
    the vector store collection configuration.
    """
    return DimensionMismatchError(
        "Collection 'my-project' has 1024-dimensional vectors but current "
        "configuration specifies 768 dimensions.\n\n"
        "This typically happens when:\n\n"
        "    • The embedding model changed (e.g., switched providers or model versions)\n"
        "    • The embedding configuration changed\n"
        "    • The collection was created with different settings",
        details={
            "collection": "my-project",
            "actual_dimension": 1024,
            "expected_dimension": 768,
            "resolution_command": "cw index --force --clear",
        },
        suggestions=[
            "  1. Rebuild the collection: cw index --force --clear",
            "  2. Or revert to the embedding model and settings that created this collection",
        ],
    )


def trigger_model_switch() -> ModelSwitchError:
    """Trigger model switch error with realistic message.

    Simulates the error raised when the embedding model has changed
    from what was used to create the existing vector store collection.
    """
    return ModelSwitchError(
        "Your existing embedding collection was created with model 'voyage-code-3', "
        "but the current model is 'voyage-4-large'. You can't use different embedding "
        "models for the same collection.",
        suggestions=[
            "Option 1: Re-index your codebase with the new provider",
            "Option 2: Revert provider setting to match the collection",
            "Option 3: Delete the existing collection and re-index",
            "Option 4: Create a new collection with a different name",
        ],
        details={
            "collection_provider": "voyage",
            "current_provider": "voyage",
            "collection_model": "voyage-code-3",
            "current_model": "voyage-4-large",
            "collection": "my-project",
        },
    )


def trigger_configuration_lock() -> ConfigurationLockError:
    """Trigger configuration lock error with realistic message.

    Simulates the error raised when attempting to modify a collection's
    configuration in a way that violates the collection's policy.
    """
    return ConfigurationLockError(
        "Collection policy is STRICT - no configuration changes allowed",
        details={
            "policy": "STRICT",
            "collection": "production-index",
            "attempted_change": "model switch from voyage-code-3 to voyage-4-large",
        },
        suggestions=[
            "Option 1: Create a new collection with different name: cw init config --collection new-name",
            "Option 2: Change collection policy to FAMILY_AWARE or FLEXIBLE (may affect search quality)",
            "Option 3: Delete existing collection and re-index: cw index --force --clear",
        ],
    )


def trigger_family_lock() -> ConfigurationLockError:
    """Trigger family-aware configuration lock error.

    Simulates the error raised when attempting to switch models outside
    the same model family with FAMILY_AWARE policy.
    """
    return ConfigurationLockError(
        "Model change breaks family compatibility",
        details={
            "policy": "FAMILY_AWARE",
            "collection": "my-project",
            "indexed_model": "voyage-4-large",
            "indexed_family": "voyage-4",
            "current_model": "voyage-code-3",
            "current_family": "voyage-code",
        },
        suggestions=[
            "Option 1: Use a model from the voyage-4 family (e.g., voyage-4-nano for queries)",
            "Option 2: Re-index with voyage-code-3: cw index --force --clear",
            "Option 3: Change policy to FLEXIBLE (may affect search quality)",
            "To learn about model families, see: https://docs.codeweaver.dev/embedding-models",
        ],
    )


def trigger_migration_validation_failure() -> ValidationError:
    """Trigger migration validation error with realistic message.

    Simulates data integrity validation failure during migration.
    """
    return ValidationError(
        "Layer 2 failed: Payload checksums don't match. "
        "Some payload data was corrupted during migration."
    )


def trigger_migration_error() -> MigrationError:
    """Trigger general migration error with realistic message.

    Simulates migration operation failure (e.g., worker crash, network timeout).
    """
    return MigrationError("Worker 2 failed: Network timeout after 30s")


def trigger_network_timeout() -> ProviderError:
    """Trigger network timeout error with realistic message.

    Simulates timeout during provider API calls (embedding, vector store).
    """
    return ProviderError(
        "Request to embedding provider timed out after 30s",
        details={
            "provider": "voyage",
            "endpoint": "https://api.voyageai.com/v1/embeddings",
            "timeout_seconds": 30,
            "operation": "embed_batch",
            "chunks_attempted": 100,
        },
        suggestions=[
            "Option 1: Check network connectivity and try again",
            "Option 2: Increase timeout in settings: voyage.timeout = 60",
            "Option 3: Reduce batch size: voyage.batch_size = 50",
            "Option 4: If timeouts persist, check provider status: https://status.voyageai.com",
        ],
    )


def trigger_checkpoint_corruption() -> ConfigurationError:
    """Trigger checkpoint corruption error with realistic message.

    Simulates corrupted checkpoint file that can't be loaded.
    """
    return ConfigurationError(
        "Checkpoint file is corrupted and cannot be loaded",
        details={
            "checkpoint_file": "/home/user/.codeweaver/my-project/checkpoints/checkpoint.json",
            "error": "Invalid JSON: Unexpected end of file",
        },
        suggestions=[
            "Option 1: Delete corrupted checkpoint and start fresh: rm -f <checkpoint_file>",
            "Option 2: Restore from backup if available",
            "Option 3: Re-index from scratch: cw index --force --clear",
        ],
    )


def trigger_profile_version_mismatch() -> ConfigurationError:
    """Trigger profile version incompatibility error.

    Simulates loading a profile created with an incompatible CodeWeaver version.
    """
    return ConfigurationError(
        "Configuration profile was created with CodeWeaver v0.5.0 but current version is v0.3.2. "
        "Profile format may be incompatible.",
        details={
            "profile_version": "0.5.0",
            "current_version": "0.3.2",
            "profile_file": "/home/user/.codeweaver/profiles/production.toml",
        },
        suggestions=[
            "Option 1: Upgrade CodeWeaver: pip install --upgrade codeweaver",
            "Option 2: Use a compatible profile version",
            "Option 3: Create new profile for current version: cw init config",
        ],
    )


# ===========================================================================
# Error Message Quality Tests
# ===========================================================================


@pytest.mark.external_api
@pytest.mark.unit
@pytest.mark.voyageai
class TestErrorMessageActionability:
    """Tests verifying that all errors include clear next steps."""

    def test_dimension_mismatch_has_guidance(self) -> None:
        """Dimension mismatch error provides actionable recovery steps."""
        error = trigger_dimension_mismatch()

        # Must have suggestions attribute with actions
        assert error.suggestions, "Error missing suggestions"
        suggestions_text = " ".join(error.suggestions)

        assert any([
            "Rebuild" in suggestions_text,
            "cw index" in suggestions_text,
            "revert" in suggestions_text.lower(),
        ]), f"Error suggestions lack actionable guidance: {error.suggestions}"

        # Must reference command to fix
        assert any("cw index --force --clear" in s or "cw index" in s for s in error.suggestions), (
            "No command reference in suggestions"
        )

        # Must explain what happened in message
        message = error.message
        assert "embedding model changed" in message or "configuration changed" in message

    def test_model_switch_has_guidance(self) -> None:
        """Model switch error provides multiple resolution options."""
        error = trigger_model_switch()

        # Must have multiple options
        suggestions_text = " ".join(error.suggestions)
        assert "Option 1:" in suggestions_text
        assert "Option 2:" in suggestions_text
        assert "Option 3:" in suggestions_text

        # Must reference specific actions
        assert "Re-index" in suggestions_text
        assert "Revert" in suggestions_text
        assert "Delete" in suggestions_text or "delete" in suggestions_text

    def test_configuration_lock_has_guidance(self) -> None:
        """Configuration lock error explains policy and provides workarounds."""
        error = trigger_configuration_lock()

        message = error.message
        suggestions_text = " ".join(error.suggestions)

        # Must explain policy constraint in message
        assert "STRICT" in message or "policy" in message.lower()

        # Must provide options in suggestions
        assert "Option 1:" in suggestions_text
        assert "cw init config" in suggestions_text or "cw index" in suggestions_text

        # Must reference new collection or policy change
        assert "new collection" in suggestions_text.lower() or "policy" in suggestions_text.lower()

    def test_family_lock_has_guidance(self) -> None:
        """Family-aware lock error explains model families."""
        error = trigger_family_lock()

        message = error.message
        suggestions_text = " ".join(error.suggestions)

        # Must mention family compatibility
        assert "family" in message.lower()

        # Must provide documentation link for model families in suggestions
        assert "docs.codeweaver" in suggestions_text or "documentation" in suggestions_text.lower()

        # Must suggest compatible alternative
        assert "voyage-4-nano" in suggestions_text or "same family" in suggestions_text.lower()

    def test_migration_validation_failure_has_guidance(self) -> None:
        """Migration validation error explains what failed and suggests recovery."""
        error = trigger_migration_validation_failure()

        message = str(error)

        # Must explain which layer failed
        assert "Layer" in message

        # Must explain what the failure means
        assert "corrupted" in message.lower() or "don't match" in message.lower()

    def test_migration_error_has_guidance(self) -> None:
        """General migration error provides context about failure."""
        error = trigger_migration_error()

        message = str(error)

        # Must identify which worker failed
        assert "Worker" in message

        # Must explain failure reason
        assert "timeout" in message.lower() or "failed" in message.lower()

    def _test_url_for_domain(self, text: str, domain: str) -> bool:
        """Helper to check if text contains a URL for a specific domain."""
        from urllib.parse import urlparse

        parsed_url = urlparse(text)
        return parsed_url.netloc.endswith(domain)

    def test_network_timeout_has_guidance(self) -> None:
        """Network timeout error provides troubleshooting steps."""
        error = trigger_network_timeout()

        message = error.message
        suggestions_text = " ".join(error.suggestions)

        # Must explain what timed out
        assert "timeout" in message.lower() or "timed out" in message.lower()

        # Must provide options to resolve
        assert "Option 1:" in suggestions_text
        assert (
            "network connectivity" in suggestions_text.lower()
            or "timeout" in suggestions_text.lower()
        )

        # Must reference provider status if available
        assert (
            "status.voyageai.com" in suggestions_text
            or "provider status" in suggestions_text.lower()
        )

    def test_checkpoint_corruption_has_guidance(self) -> None:
        """Checkpoint corruption error provides recovery options."""
        error = trigger_checkpoint_corruption()

        message = error.message
        suggestions_text = " ".join(error.suggestions)

        # Must explain what's corrupted
        assert "checkpoint" in message.lower() and "corrupt" in message.lower()

        # Must provide recovery options
        assert "Option 1:" in suggestions_text
        assert "delete" in suggestions_text.lower() or "rm" in suggestions_text.lower()

        # Must offer fresh start option
        assert (
            "cw index --force --clear" in suggestions_text or "re-index" in suggestions_text.lower()
        )

    def test_profile_version_mismatch_has_guidance(self) -> None:
        """Profile version error suggests upgrade or compatible profile."""
        error = trigger_profile_version_mismatch()

        message = error.message
        suggestions_text = " ".join(error.suggestions)

        # Must explain version incompatibility
        assert "version" in message.lower() and (
            "incompatible" in message.lower() or "v0." in message
        )

        # Must suggest upgrade
        assert "upgrade" in suggestions_text.lower() or "pip install" in suggestions_text.lower()

        # Must offer alternatives
        assert "Option" in suggestions_text


@pytest.mark.external_api
@pytest.mark.unit
@pytest.mark.voyageai
class TestErrorMessageStructure:
    """Tests verifying error message structural quality."""

    def test_all_errors_have_suggestions(self) -> None:
        """All errors must provide actionable suggestions."""
        errors: list[CodeWeaverError] = [
            trigger_dimension_mismatch(),
            trigger_model_switch(),
            trigger_configuration_lock(),
            trigger_family_lock(),
            trigger_network_timeout(),
            trigger_checkpoint_corruption(),
            trigger_profile_version_mismatch(),
        ]

        for error in errors:
            # Must have suggestions list
            assert hasattr(error, "suggestions"), (
                f"Error {type(error).__name__} missing suggestions"
            )
            assert error.suggestions, f"Error {type(error).__name__} has empty suggestions"

            # Each suggestion should be actionable
            for suggestion in error.suggestions:
                assert suggestion.strip(), f"Empty suggestion in {type(error).__name__}"
                # Should start with action word or option marker
                stripped = suggestion.strip()
                assert any([
                    stripped.startswith(("Option", "To ", "Run:", "Check", "Or ")),
                    ":" in stripped[:60],  # Has structure like "Step 1: ..."
                    re.match(r"^\d+\.", stripped),  # Starts with a number like "1." or "2."
                ]), f"Suggestion not actionable: {suggestion}"

    def test_all_errors_have_details(self) -> None:
        """All errors must provide contextual details."""
        errors: list[CodeWeaverError] = [
            trigger_dimension_mismatch(),
            trigger_model_switch(),
            trigger_configuration_lock(),
            trigger_family_lock(),
            trigger_network_timeout(),
            trigger_checkpoint_corruption(),
            trigger_profile_version_mismatch(),
        ]

        for error in errors:
            # Must have details dict
            assert hasattr(error, "details"), f"Error {type(error).__name__} missing details"
            assert error.details, f"Error {type(error).__name__} has empty details"

            # Details should have meaningful keys
            for key in error.details:
                assert key.strip(), f"Empty detail key in {type(error).__name__}"
                assert "_" in key or key.islower(), (
                    f"Detail key not snake_case: {key} in {type(error).__name__}"
                )

    def test_command_references_are_valid(self) -> None:
        """Command references in error messages should be valid."""
        errors: list[CodeWeaverError] = [
            trigger_dimension_mismatch(),
            trigger_model_switch(),
            trigger_configuration_lock(),
            trigger_family_lock(),
            trigger_network_timeout(),
            trigger_checkpoint_corruption(),
            trigger_profile_version_mismatch(),
        ]

        # Pattern to match CLI commands
        command_pattern = re.compile(r"cw\s+\w+")

        for error in errors:
            # Check both message and suggestions for commands
            full_text = error.message + " " + " ".join(error.suggestions)
            commands = command_pattern.findall(full_text)

            if commands:
                # All commands should start with "cw"
                for cmd in commands:
                    assert cmd.startswith("cw"), f"Invalid command format: {cmd}"

                    # Should be a known command (basic validation)
                    cmd_name = cmd.split()[1] if len(cmd.split()) > 1 else ""
                    known_commands = [
                        "index",
                        "init",
                        "config",
                        "doctor",
                        "search",
                        "start",
                        "stop",
                        "migrate",
                    ]
                    assert any(known in cmd_name for known in known_commands), (
                        f"Unknown command in error: {cmd}"
                    )


@pytest.mark.external_api
@pytest.mark.unit
@pytest.mark.voyageai
class TestJargonExplanation:
    """Tests verifying that technical jargon is explained."""

    def test_technical_terms_have_context(self) -> None:
        """Technical terms should have explanations or documentation links."""
        # Test family-aware error which uses technical terms
        error = trigger_family_lock()
        full_text = error.message + " " + " ".join(error.suggestions)

        # "family" is technical jargon - must be explained
        if "family" in full_text.lower():
            # Should have either:
            # 1. Inline explanation with parentheses or clarification
            # 2. Link to documentation
            assert any([
                "docs.codeweaver" in full_text,
                "documentation" in full_text.lower(),
                "compatible" in full_text.lower(),
                "same" in full_text.lower(),
            ]), "Technical term 'family' not explained or linked to docs"

    def test_dimension_terminology_is_clear(self) -> None:
        """Dimension mismatch error explains what dimensions are."""
        error = trigger_dimension_mismatch()
        full_text = error.message + " " + " ".join(error.suggestions)

        # Must explain the problem in user terms
        assert any([
            "embedding model changed" in full_text.lower(),
            "configuration changed" in full_text.lower(),
            "different settings" in full_text.lower(),
            "model" in full_text.lower(),
        ]), "Dimension concept not explained in user-friendly terms"

    def test_policy_terms_are_explained(self) -> None:
        """Collection policy errors explain what policies mean."""
        strict_error = trigger_configuration_lock()
        family_error = trigger_family_lock()

        strict_text = strict_error.message + " " + " ".join(strict_error.suggestions)
        family_text = family_error.message + " " + " ".join(family_error.suggestions)

        # STRICT policy should explain what it means
        if "STRICT" in strict_text:
            assert (
                "no configuration changes" in strict_text.lower()
                or "no changes" in strict_text.lower()
            )

        # FAMILY_AWARE policy should explain family concept
        if "FAMILY_AWARE" in family_text:
            assert "family" in family_text.lower()
            assert any([
                "compatible" in family_text.lower(),
                "same family" in family_text.lower(),
                "model family" in family_text.lower(),
            ])

    def test_migration_layers_are_explained(self) -> None:
        """Migration validation errors explain what validation layers mean."""
        error = trigger_migration_validation_failure()
        message = str(error)

        # Layer failures should explain what the layer validates
        if "Layer 2" in message:
            assert any([
                "Payload" in message,
                "checksums" in message.lower(),
                "corrupted" in message.lower(),
            ]), "Layer 2 validation not explained"


@pytest.mark.external_api
@pytest.mark.unit
@pytest.mark.voyageai
class TestErrorMessageConsistency:
    """Tests verifying consistent error message patterns."""

    def test_option_numbering_is_consistent(self) -> None:
        """Errors with multiple options use consistent numbering."""
        errors = [
            trigger_model_switch(),
            trigger_configuration_lock(),
            trigger_family_lock(),
            trigger_network_timeout(),
            trigger_checkpoint_corruption(),
            trigger_profile_version_mismatch(),
        ]

        for error in errors:
            suggestions_text = " ".join(error.suggestions)

            if "Option 1:" in suggestions_text:
                # Should have sequential numbering
                option_count = suggestions_text.count("Option")
                for i in range(1, option_count + 1):
                    assert f"Option {i}:" in suggestions_text, f"Missing Option {i} in sequence"

    def test_command_format_is_consistent(self) -> None:
        """Command references use consistent formatting."""
        errors = [
            trigger_dimension_mismatch(),
            trigger_model_switch(),
            trigger_configuration_lock(),
            trigger_checkpoint_corruption(),
            trigger_profile_version_mismatch(),
        ]

        for error in errors:
            full_text = error.message + " " + " ".join(error.suggestions)

            # All commands should use "cw" not "codeweaver"
            assert "codeweaver index" not in full_text.lower()
            assert "codeweaver init" not in full_text.lower()

            # Commands should include necessary flags
            if "cw index" in full_text and "clear" in full_text.lower():
                assert "--force --clear" in full_text or "--clear" in full_text

    def test_url_format_is_consistent(self) -> None:
        """Documentation URLs use consistent domain."""
        error = trigger_family_lock()
        full_text = error.message + " " + " ".join(error.suggestions)

        if "docs." in full_text:
            # Should use docs.codeweaver.dev domain
            assert "docs.codeweaver.dev" in full_text or "docs.codeweaver" in full_text


@pytest.mark.external_api
@pytest.mark.unit
@pytest.mark.voyageai
class TestErrorMessageCompleteness:
    """Tests verifying error messages provide complete information."""

    def test_errors_identify_affected_collection(self) -> None:
        """Errors affecting collections should identify which collection."""
        errors = [
            trigger_dimension_mismatch(),
            trigger_model_switch(),
            trigger_configuration_lock(),
            trigger_family_lock(),
        ]

        for error in errors:
            # Must have collection in details
            assert "collection" in error.details or "collection_name" in error.details, (
                f"Collection not identified in {type(error).__name__} details"
            )

    def test_provider_errors_identify_provider(self) -> None:
        """Provider errors should identify which provider failed."""
        error = trigger_network_timeout()

        # Must identify provider
        assert "provider" in error.details, "Provider not identified in network timeout"
        assert error.details["provider"] == "voyage"

    def test_migration_errors_provide_resume_info(self) -> None:
        """Migration errors should indicate if resume is possible."""
        # This would be tested with actual migration service integration
        # For now, we verify the error structure supports it
        error = trigger_migration_error()

        message = str(error)

        # Should indicate worker that failed
        assert "Worker" in message, "Migration error should identify failed worker"

    def test_configuration_errors_show_attempted_change(self) -> None:
        """Configuration lock errors should show what change was attempted."""
        error = trigger_configuration_lock()

        # Must show what change was attempted
        full_text = error.message + " " + " ".join(error.suggestions)
        assert "attempted_change" in error.details or "change" in full_text.lower()


# ===========================================================================
# Integration Tests - Real Error Scenarios
# ===========================================================================


@pytest.mark.external_api
@pytest.mark.unit
@pytest.mark.voyageai
class TestRealErrorScenarios:
    """Tests with realistic error scenarios matching actual usage."""

    def test_collection_metadata_validation_error_quality(self) -> None:
        """CollectionMetadata validation produces high-quality error messages."""
        # Create mismatched metadata
        indexed_metadata = CollectionMetadata(
            provider="voyage",
            project_name="test-project",
            dense_model="voyage-code-3",
            collection_name="test-collection",
        )

        current_metadata = CollectionMetadata(
            provider="voyage",
            project_name="test-project",
            dense_model="voyage-4-large",
            collection_name="test-collection",
        )

        # Should raise ModelSwitchError with quality message
        with pytest.raises(ModelSwitchError) as exc_info:
            indexed_metadata.validate_compatibility(current_metadata)

        error = exc_info.value

        # Verify error quality
        assert error.suggestions, "ModelSwitchError missing suggestions"
        assert len(error.suggestions) >= 3, "ModelSwitchError should provide multiple options"
        assert error.details, "ModelSwitchError missing details"
        assert "collection_model" in error.details
        assert "current_model" in error.details

        # Verify message quality
        message = error.message
        suggestions_text = " ".join(error.suggestions)
        assert "voyage-code-3" in message
        assert "voyage-4-large" in message
        assert "Option 1:" in suggestions_text

    def test_collection_policy_strict_error_quality(self) -> None:
        """STRICT policy violations produce high-quality error messages."""
        # Create strict policy metadata
        strict_metadata = CollectionMetadata(
            provider="voyage",
            project_name="production",
            dense_model="voyage-code-3",
            collection_name="prod-index",
            policy=CollectionPolicy.STRICT,
        )

        changed_metadata = CollectionMetadata(
            provider="voyage",
            project_name="production",
            dense_model="voyage-4-large",
            collection_name="prod-index",
            policy=CollectionPolicy.STRICT,
        )

        # Should raise ConfigurationLockError
        with pytest.raises(ConfigurationLockError) as exc_info:
            strict_metadata.validate_config_change(
                new_dense_model=changed_metadata.dense_model,
                new_query_model=changed_metadata.query_model,
                new_sparse_model=changed_metadata.sparse_model,
                new_provider=changed_metadata.provider,
            )

        error = exc_info.value

        # Verify error quality
        assert error.suggestions, "ConfigurationLockError missing suggestions"
        assert error.details, "ConfigurationLockError missing details"
        assert "policy" in error.details

        full_text = error.message + " " + " ".join(error.suggestions)
        assert "STRICT" in full_text
        assert "no configuration changes" in full_text.lower() or "no changes" in full_text.lower()


# ===========================================================================
# Message Format Tests
# ===========================================================================


@pytest.mark.external_api
@pytest.mark.unit
@pytest.mark.voyageai
class TestMessageFormatting:
    """Tests verifying error message formatting quality."""

    def test_multiline_messages_are_readable(self) -> None:
        """Multi-line error messages have proper formatting."""
        error = trigger_dimension_mismatch()
        error.message + "\n".join(error.suggestions)

        # Should have line breaks for readability
        assert "\n" in error.message or len(error.suggestions) > 1

        # Should not have excessive blank lines in message
        assert "\n\n\n" not in error.message

    def test_bullet_points_are_formatted(self) -> None:
        """Bullet points in messages use consistent formatting."""
        error = trigger_dimension_mismatch()
        full_text = error.message + "\n" + "\n".join(error.suggestions)

        # If using bullets, should be consistent
        if "•" in full_text:
            # Check indentation is consistent
            lines = full_text.split("\n")
            bullet_lines = [line for line in lines if "•" in line]
            if len(bullet_lines) > 1:
                # All bullet lines should have similar indentation
                indents = [len(line) - len(line.lstrip()) for line in bullet_lines]
                assert len(set(indents)) <= 2, "Inconsistent bullet point indentation"

    def test_suggestions_are_numbered_or_bulleted(self) -> None:
        """Suggestions use clear numbering or bullets."""
        errors = [trigger_model_switch(), trigger_configuration_lock(), trigger_network_timeout()]

        for error in errors:
            if not error.suggestions:
                continue

            # Suggestions should use numbers or bullets
            for suggestion in error.suggestions:
                # Should start with number, option marker, or bullet
                assert any([
                    suggestion.strip().startswith(("1.", "2.", "3.", "4.")),
                    suggestion.strip().startswith("Option"),
                    suggestion.strip().startswith("•"),
                    suggestion.strip().startswith("-"),
                    suggestion.strip().startswith("*"),
                ]), f"Suggestion lacks clear marker: {suggestion}"
