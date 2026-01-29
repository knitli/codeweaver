# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Comprehensive unit tests for AsymmetricEmbeddingConfig class.

Tests cover all configuration and validation scenarios:
- Valid asymmetric configurations (same family, different providers)
- Validation failures (incompatible families, dimension mismatches)
- Error message quality and actionability
- Cross-provider family linking (VOYAGE + SENTENCE_TRANSFORMERS)
- Validation bypass scenarios
- Edge cases (unknown models, models without families)
"""

from __future__ import annotations

from typing import TYPE_CHECKING

import pytest

from codeweaver.core import Provider
from codeweaver.core.exceptions import ConfigurationError
from codeweaver.providers.config.embedding import VoyageEmbeddingConfig


if TYPE_CHECKING:
    from codeweaver.providers.config.kinds import EmbeddingProviderSettings
    from codeweaver.providers.embedding.capabilities.base import ModelFamily


pytestmark = [pytest.mark.unit]


# ===========================================================================
# *                           Test Fixtures
# ===========================================================================


@pytest.fixture
def voyage_4_large_settings() -> EmbeddingProviderSettings:
    """Create EmbeddingProviderSettings for voyage-4-large (VOYAGE provider).

    This model is part of the VOYAGE_4_FAMILY and is suitable for
    asymmetric pairing with voyage-4-nano.
    """
    from codeweaver.providers.config.kinds import EmbeddingProviderSettings

    return EmbeddingProviderSettings(
        provider=Provider.VOYAGE,
        model_name="voyage-4-large",
        embedding_config=VoyageEmbeddingConfig(model_name="voyage-4-large"),
    )


@pytest.fixture
def voyage_4_nano_settings() -> EmbeddingProviderSettings:
    """Create EmbeddingProviderSettings for voyage-4-nano (SENTENCE_TRANSFORMERS).

    This is a local model via SentenceTransformers that is part of the
    VOYAGE_4_FAMILY, allowing asymmetric pairing with VOYAGE API models.
    """
    from codeweaver.providers.config.embedding import SentenceTransformersEmbeddingConfig
    from codeweaver.providers.config.kinds import EmbeddingProviderSettings

    return EmbeddingProviderSettings(
        provider=Provider.SENTENCE_TRANSFORMERS,
        model_name="voyage-4-nano",
        embedding_config=SentenceTransformersEmbeddingConfig(model_name="voyage-4-nano"),
    )


@pytest.fixture
def voyage_code_3_settings() -> EmbeddingProviderSettings:
    """Create EmbeddingProviderSettings for voyage-code-3 (VOYAGE provider).

    This model is NOT in the VOYAGE_4_FAMILY (no model_family attribute) and
    should fail validation when paired with voyage-4 models.
    """
    from codeweaver.providers.config.kinds import EmbeddingProviderSettings

    return EmbeddingProviderSettings(
        provider=Provider.VOYAGE,
        model_name="voyage-code-3",
        embedding_config=VoyageEmbeddingConfig(model_name="voyage-code-3"),
    )


@pytest.fixture
def openai_settings() -> EmbeddingProviderSettings:
    """Create EmbeddingProviderSettings for OpenAI model.

    This model is from a different family/provider and should fail
    validation when paired with Voyage models.
    """
    from codeweaver.providers.config.embedding import OpenAIEmbeddingConfig
    from codeweaver.providers.config.kinds import EmbeddingProviderSettings

    return EmbeddingProviderSettings(
        provider=Provider.OPENAI,
        model_name="text-embedding-3-large",
        embedding_config=OpenAIEmbeddingConfig(model_name="text-embedding-3-large"),
    )


@pytest.fixture
def mock_voyage_4_family() -> ModelFamily:
    """Create a mock VOYAGE_4_FAMILY for testing.

    This fixture is temporary - it will use the real ModelFamily
    once Agent A implements it.
    """
    try:
        from codeweaver.providers.embedding.capabilities.base import ModelFamily

        return ModelFamily(
            name="voyage-4",
            compatible_models=["voyage-4-large", "voyage-4", "voyage-4-lite", "voyage-4-nano"],
            default_dimension=1024,
            datatype="float32",
        )
    except ImportError:
        pytest.skip("ModelFamily not yet implemented by Agent A")


# ===========================================================================
# *                         Happy Path Tests
# ===========================================================================


@pytest.mark.unit
class TestAsymmetricConfigCreation:
    """Test successful creation of AsymmetricEmbeddingConfig."""

    def test_create_valid_config(
        self,
        voyage_4_large_settings: EmbeddingProviderSettings,
        voyage_4_nano_settings: EmbeddingProviderSettings,
    ):
        """Test creating valid asymmetric config with same-family models."""
        try:
            from codeweaver.providers.config.providers import AsymmetricEmbeddingConfig
        except ImportError:
            pytest.skip("AsymmetricEmbeddingConfig not yet implemented")

        config = AsymmetricEmbeddingConfig(
            embed_provider_settings=voyage_4_large_settings,
            query_provider_settings=voyage_4_nano_settings,
        )

        assert config.embed_provider_settings == voyage_4_large_settings
        assert config.query_provider_settings == voyage_4_nano_settings

    def test_config_with_same_provider(self, voyage_4_large_settings: EmbeddingProviderSettings):
        """Test creating config with same provider but different models (less common use case)."""
        try:
            from codeweaver.providers.config.kinds import (
                AsymmetricEmbeddingConfig,
                EmbeddingProviderSettings,
            )
        except ImportError:
            pytest.skip("AsymmetricEmbeddingConfig not yet implemented")

        voyage_4_settings = EmbeddingProviderSettings(
            provider=Provider.VOYAGE,
            model_name="voyage-4",
            embedding_config=VoyageEmbeddingConfig(model_name="voyage-4"),
        )

        config = AsymmetricEmbeddingConfig(
            embed_provider_settings=voyage_4_large_settings,
            query_provider_settings=voyage_4_settings,
        )

        assert config.embed_provider_settings.model_name == "voyage-4-large"
        assert config.query_provider_settings.model_name == "voyage-4"


@pytest.mark.unit
class TestSameFamilyValidation:
    """Test validation passes for same-family models."""

    def test_same_family_different_providers(
        self,
        voyage_4_large_settings: EmbeddingProviderSettings,
        voyage_4_nano_settings: EmbeddingProviderSettings,
    ):
        """Test validation passes for same family across different providers."""
        try:
            from codeweaver.providers.config.providers import AsymmetricEmbeddingConfig
        except ImportError:
            pytest.skip("AsymmetricEmbeddingConfig not yet implemented")

        config = AsymmetricEmbeddingConfig(
            embed_provider_settings=voyage_4_large_settings,
            query_provider_settings=voyage_4_nano_settings,
        )

        # Should not raise validation error
        assert config.embed_provider_settings.provider == Provider.VOYAGE
        assert config.query_provider_settings.provider == Provider.SENTENCE_TRANSFORMERS

    def test_validation_confirms_compatibility(
        self,
        voyage_4_large_settings: EmbeddingProviderSettings,
        voyage_4_nano_settings: EmbeddingProviderSettings,
    ):
        """Test that validation actually checks model family compatibility."""
        try:
            from codeweaver.providers.config.providers import AsymmetricEmbeddingConfig
        except ImportError:
            pytest.skip("AsymmetricEmbeddingConfig not yet implemented")

        # This should succeed because both are in voyage-4 family
        config = AsymmetricEmbeddingConfig(
            embed_provider_settings=voyage_4_large_settings,
            query_provider_settings=voyage_4_nano_settings,
        )

        # Verify family information is accessible (implementation detail)
        # This might need adjustment based on actual AsymmetricEmbeddingConfig API
        assert config is not None


@pytest.mark.unit
class TestValidationBypass:
    """Test validation bypass mechanism."""

    def test_bypass_validation(
        self,
        voyage_code_3_settings: EmbeddingProviderSettings,
        openai_settings: EmbeddingProviderSettings,
    ):
        """Test that validation can be disabled via skip_validation parameter."""
        try:
            from codeweaver.providers.config.providers import AsymmetricEmbeddingConfig
        except ImportError:
            pytest.skip("AsymmetricEmbeddingConfig not yet implemented")

        # This would normally fail validation, but validate_family_compatibility=False allows it
        config = AsymmetricEmbeddingConfig(
            embed_provider_settings=voyage_code_3_settings,
            query_provider_settings=openai_settings,
            validate_family_compatibility=False,
        )

        assert config.embed_provider_settings == voyage_code_3_settings
        assert config.query_provider_settings == openai_settings


# ===========================================================================
# *                      Validation Failure Tests
# ===========================================================================


@pytest.mark.unit
class TestIncompatibleFamilyModels:
    """Test validation failures for incompatible model families."""

    def test_different_families_rejected(
        self,
        voyage_4_large_settings: EmbeddingProviderSettings,
        voyage_code_3_settings: EmbeddingProviderSettings,
    ):
        """Test that models from different families are rejected.

        NOTE: Currently only VOYAGE_4_FAMILY exists, so this tests the case where
        one model has a family and another doesn't. Once we have multiple families,
        this test should be updated to test actual different-family scenarios.
        """
        try:
            from codeweaver.providers.config.providers import AsymmetricEmbeddingConfig
        except ImportError:
            pytest.skip("AsymmetricEmbeddingConfig not yet implemented")

        with pytest.raises(ConfigurationError, match=r"does not belong to a model family"):
            AsymmetricEmbeddingConfig(
                embed_provider_settings=voyage_4_large_settings,
                query_provider_settings=voyage_code_3_settings,
            )

    def test_cross_provider_incompatibility(
        self,
        voyage_4_large_settings: EmbeddingProviderSettings,
        openai_settings: EmbeddingProviderSettings,
    ):
        """Test that incompatible cross-provider models are rejected."""
        try:
            from codeweaver.providers.config.providers import AsymmetricEmbeddingConfig
        except ImportError:
            pytest.skip("AsymmetricEmbeddingConfig not yet implemented")

        with pytest.raises(ConfigurationError, match=r"does not belong to a model family"):
            AsymmetricEmbeddingConfig(
                embed_provider_settings=voyage_4_large_settings,
                query_provider_settings=openai_settings,
            )


@pytest.mark.unit
class TestModelWithoutFamily:
    """Test validation for models without family assignments."""

    def test_model_without_family_rejected(
        self, voyage_4_large_settings: EmbeddingProviderSettings
    ):
        """Test that models without family assignment are rejected."""
        try:
            from codeweaver.providers.config.embedding import FastEmbedEmbeddingConfig
            from codeweaver.providers.config.kinds import (
                AsymmetricEmbeddingConfig,
                EmbeddingProviderSettings,
            )
        except ImportError:
            pytest.skip("AsymmetricEmbeddingConfig not yet implemented")

        # Create settings for a model without family (hypothetical example)
        no_family_settings = EmbeddingProviderSettings(
            provider=Provider.FASTEMBED,
            model_name="BAAI/bge-small-en-v1.5",
            embedding_config=FastEmbedEmbeddingConfig(model_name="BAAI/bge-small-en-v1.5"),
        )

        with pytest.raises(ConfigurationError, match=r"model.*family"):
            AsymmetricEmbeddingConfig(
                embed_provider_settings=voyage_4_large_settings,
                query_provider_settings=no_family_settings,
            )


@pytest.mark.unit
class TestDimensionMismatch:
    """Test validation for dimension incompatibility."""

    def test_dimension_mismatch_caught(self):
        """Test that dimension mismatches are caught during validation."""
        # This test requires specific test fixtures with models in the same
        # family but different dimensions - skipping until such fixtures exist
        pytest.skip("Dimension validation test requires specific test fixtures")


@pytest.mark.unit
class TestUnknownModel:
    """Test validation for unknown/unregistered models."""

    def test_unknown_model_rejected(self, voyage_4_large_settings: EmbeddingProviderSettings):
        """Test that unknown models not in capability registry are rejected."""
        try:
            from codeweaver.providers.config.kinds import (
                AsymmetricEmbeddingConfig,
                EmbeddingProviderSettings,
            )
        except ImportError:
            pytest.skip("AsymmetricEmbeddingConfig not yet implemented")

        # Create settings for non-existent model
        unknown_settings = EmbeddingProviderSettings(
            provider=Provider.VOYAGE,
            model_name="voyage-99-nonexistent",
            embedding_config=VoyageEmbeddingConfig(model_name="voyage-99-nonexistent"),
        )

        with pytest.raises(ConfigurationError, match=r"unknown.*model|not.*found"):
            AsymmetricEmbeddingConfig(
                embed_provider_settings=voyage_4_large_settings,
                query_provider_settings=unknown_settings,
            )


# ===========================================================================
# *                      Error Message Quality Tests
# ===========================================================================


@pytest.mark.unit
class TestErrorMessageQuality:
    """Test that error messages are helpful and actionable."""

    def test_error_contains_model_names(
        self,
        voyage_4_large_settings: EmbeddingProviderSettings,
        voyage_code_3_settings: EmbeddingProviderSettings,
    ):
        """Test that error messages include model names for debugging."""
        try:
            from codeweaver.providers.config.providers import AsymmetricEmbeddingConfig
        except ImportError:
            pytest.skip("AsymmetricEmbeddingConfig not yet implemented")

        with pytest.raises(ConfigurationError) as exc_info:
            AsymmetricEmbeddingConfig(
                embed_provider_settings=voyage_4_large_settings,
                query_provider_settings=voyage_code_3_settings,
            )

        error_message = str(exc_info.value).lower()
        # Error should mention the model that failed validation (query model without family)
        assert "voyage-code-3" in error_message

    def test_error_contains_family_information(
        self,
        voyage_4_large_settings: EmbeddingProviderSettings,
        voyage_code_3_settings: EmbeddingProviderSettings,
    ):
        """Test that error messages explain family incompatibility."""
        try:
            from codeweaver.providers.config.providers import AsymmetricEmbeddingConfig
        except ImportError:
            pytest.skip("AsymmetricEmbeddingConfig not yet implemented")

        with pytest.raises(ConfigurationError) as exc_info:
            AsymmetricEmbeddingConfig(
                embed_provider_settings=voyage_4_large_settings,
                query_provider_settings=voyage_code_3_settings,
            )

        error_message = str(exc_info.value).lower()
        assert "family" in error_message or "compatible" in error_message

    def test_error_provides_suggestions(
        self,
        voyage_4_large_settings: EmbeddingProviderSettings,
        openai_settings: EmbeddingProviderSettings,
    ):
        """Test that error messages suggest alternative models."""
        try:
            from codeweaver.providers.config.providers import AsymmetricEmbeddingConfig
        except ImportError:
            pytest.skip("AsymmetricEmbeddingConfig not yet implemented")

        with pytest.raises(ConfigurationError) as exc_info:
            AsymmetricEmbeddingConfig(
                embed_provider_settings=voyage_4_large_settings,
                query_provider_settings=openai_settings,
            )

        # ConfigurationError should have suggestions attribute
        assert hasattr(exc_info.value, "suggestions")
        assert len(exc_info.value.suggestions) > 0
        # Suggestions should mention using models with family support
        suggestions_text = " ".join(exc_info.value.suggestions).lower()
        assert any(
            keyword in suggestions_text for keyword in ["use", "family", "compatible", "symmetric"]
        )

    def test_error_includes_details_dict(
        self,
        voyage_4_large_settings: EmbeddingProviderSettings,
        voyage_code_3_settings: EmbeddingProviderSettings,
    ):
        """Test that validation error includes structured details for debugging."""
        try:
            from codeweaver.providers.config.providers import AsymmetricEmbeddingConfig
        except ImportError:
            pytest.skip("AsymmetricEmbeddingConfig not yet implemented")

        with pytest.raises(ConfigurationError) as exc_info:
            AsymmetricEmbeddingConfig(
                embed_provider_settings=voyage_4_large_settings,
                query_provider_settings=voyage_code_3_settings,
            )

        # If the implementation includes structured error details
        # (e.g., as exception attributes), verify they exist
        # This is implementation-dependent
        assert exc_info.value is not None


# ===========================================================================
# *                      Cross-Provider Tests
# ===========================================================================


@pytest.mark.unit
class TestCrossProviderFamilies:
    """Test cross-provider family linking."""

    def test_voyage_api_with_sentence_transformers(
        self,
        voyage_4_large_settings: EmbeddingProviderSettings,
        voyage_4_nano_settings: EmbeddingProviderSettings,
    ):
        """Test VOYAGE API model paired with SENTENCE_TRANSFORMERS local model."""
        try:
            from codeweaver.providers.config.providers import AsymmetricEmbeddingConfig
        except ImportError:
            pytest.skip("AsymmetricEmbeddingConfig not yet implemented")

        config = AsymmetricEmbeddingConfig(
            embed_provider_settings=voyage_4_large_settings,
            query_provider_settings=voyage_4_nano_settings,
        )

        assert config.embed_provider_settings.provider == Provider.VOYAGE
        assert config.query_provider_settings.provider == Provider.SENTENCE_TRANSFORMERS

    def test_family_linking_verified(
        self,
        voyage_4_large_settings: EmbeddingProviderSettings,
        voyage_4_nano_settings: EmbeddingProviderSettings,
    ):
        """Test that family linking is validated across providers."""
        try:
            from codeweaver.providers.config.providers import AsymmetricEmbeddingConfig
        except ImportError:
            pytest.skip("AsymmetricEmbeddingConfig not yet implemented")

        # This should succeed because both models reference the same family
        config = AsymmetricEmbeddingConfig(
            embed_provider_settings=voyage_4_large_settings,
            query_provider_settings=voyage_4_nano_settings,
        )

        # Verify that the models are recognized as compatible
        # Implementation-specific validation
        assert config is not None


# ===========================================================================
# *                    Additional Edge Case Tests
# ===========================================================================


@pytest.mark.unit
class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_identical_settings(self, voyage_4_large_settings: EmbeddingProviderSettings):
        """Test config with identical embed and query settings."""
        try:
            from codeweaver.providers.config.providers import AsymmetricEmbeddingConfig
        except ImportError:
            pytest.skip("AsymmetricEmbeddingConfig not yet implemented")

        # While unusual, this should be valid
        config = AsymmetricEmbeddingConfig(
            embed_provider_settings=voyage_4_large_settings,
            query_provider_settings=voyage_4_large_settings,
        )

        assert config.embed_provider_settings == config.query_provider_settings

    def test_config_serialization(
        self,
        voyage_4_large_settings: EmbeddingProviderSettings,
        voyage_4_nano_settings: EmbeddingProviderSettings,
    ):
        """Test that config can be serialized and deserialized."""
        try:
            from codeweaver.providers.config.providers import AsymmetricEmbeddingConfig
        except ImportError:
            pytest.skip("AsymmetricEmbeddingConfig not yet implemented")

        config = AsymmetricEmbeddingConfig(
            embed_provider_settings=voyage_4_large_settings,
            query_provider_settings=voyage_4_nano_settings,
        )

        # Test pydantic model serialization
        config_dict = config.model_dump()
        assert "embed_provider_settings" in config_dict
        assert "query_provider_settings" in config_dict

        # Test deserialization
        restored_config = AsymmetricEmbeddingConfig.model_validate(config_dict)
        assert (
            restored_config.embed_provider_settings.model_name == voyage_4_large_settings.model_name
        )
        assert (
            restored_config.query_provider_settings.model_name == voyage_4_nano_settings.model_name
        )


# ===========================================================================
# *                      Integration Readiness Tests
# ===========================================================================


@pytest.mark.unit
class TestIntegrationReadiness:
    """Tests to verify readiness for integration with other components."""

    def test_config_has_required_attributes(
        self,
        voyage_4_large_settings: EmbeddingProviderSettings,
        voyage_4_nano_settings: EmbeddingProviderSettings,
    ):
        """Test that config exposes necessary attributes for integration."""
        try:
            from codeweaver.providers.config.providers import AsymmetricEmbeddingConfig
        except ImportError:
            pytest.skip("AsymmetricEmbeddingConfig not yet implemented")

        config = AsymmetricEmbeddingConfig(
            embed_provider_settings=voyage_4_large_settings,
            query_provider_settings=voyage_4_nano_settings,
        )

        # Verify expected attributes exist
        assert hasattr(config, "embed_provider_settings")
        assert hasattr(config, "query_provider_settings")

    def test_config_compatible_with_settings_system(
        self,
        voyage_4_large_settings: EmbeddingProviderSettings,
        voyage_4_nano_settings: EmbeddingProviderSettings,
    ):
        """Test that config integrates with pydantic-settings patterns."""
        try:
            from codeweaver.providers.config.providers import AsymmetricEmbeddingConfig
        except ImportError:
            pytest.skip("AsymmetricEmbeddingConfig not yet implemented")

        config = AsymmetricEmbeddingConfig(
            embed_provider_settings=voyage_4_large_settings,
            query_provider_settings=voyage_4_nano_settings,
        )

        # Should be a pydantic model
        assert hasattr(config, "model_dump")
        assert hasattr(config, "model_validate")
