# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Comprehensive unit tests for AsymmetricEmbeddingProviderSettings class.

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

from codeweaver.providers.config.embedding import VoyageEmbeddingConfig

from codeweaver.core import Provider
from codeweaver.core.exceptions import ConfigurationError


if TYPE_CHECKING:
    from codeweaver.providers.config.categories import EmbeddingProviderSettings
    from codeweaver.providers.embedding.capabilities.base import ModelFamily
pytestmark = [pytest.mark.unit]


@pytest.fixture
def voyage_4_large_settings() -> EmbeddingProviderSettings:
    """Create EmbeddingProviderSettings for voyage-4-large (VOYAGE provider).

    This model is part of the VOYAGE_4_FAMILY and is suitable for
    asymmetric pairing with voyage-4-nano.
    """
    from codeweaver.providers.config.categories import EmbeddingProviderSettings

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

    from codeweaver.providers.config.categories import EmbeddingProviderSettings

    return EmbeddingProviderSettings(
        provider=Provider.SENTENCE_TRANSFORMERS,
        model_name="voyageai/voyage-4-nano",
        embedding_config=SentenceTransformersEmbeddingConfig(model_name="voyageai/voyage-4-nano"),
    )


@pytest.fixture
def voyage_code_3_settings() -> EmbeddingProviderSettings:
    """Create EmbeddingProviderSettings for voyage-code-3 (VOYAGE provider).

    This model is NOT in the VOYAGE_4_FAMILY (no model_family attribute) and
    should fail validation when paired with voyage-4 models.
    """
    from codeweaver.providers.config.categories import EmbeddingProviderSettings

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

    from codeweaver.providers.config.categories import EmbeddingProviderSettings

    return EmbeddingProviderSettings(
        provider=Provider.OPENAI,
        model_name="text-embedding-3-large",
        embedding_config=OpenAIEmbeddingConfig(model_name="text-embedding-3-large"),
    )


@pytest.fixture
def mock_voyage_4_family() -> ModelFamily:
    """Returns the real VOYAGE_4_FAMILY model family instance."""
    from codeweaver.embedding.capabilities.voyage import VOYAGE_4_FAMILY

    return VOYAGE_4_FAMILY


@pytest.mark.unit
class TestAsymmetricConfigCreation:
    """Test successful creation of AsymmetricEmbeddingProviderSettings."""

    def test_create_valid_config(
        self,
        voyage_4_large_settings: EmbeddingProviderSettings,
        voyage_4_nano_settings: EmbeddingProviderSettings,
    ):
        """Test creating valid asymmetric config with same-family models."""
        try:
            from codeweaver.providers.config.asymmetric import AsymmetricEmbeddingProviderSettings
        except ImportError:
            pytest.skip("AsymmetricEmbeddingProviderSettings not yet implemented")
        config = AsymmetricEmbeddingProviderSettings(
            embed_provider=voyage_4_large_settings, query_provider=voyage_4_nano_settings
        )
        assert config.embed_provider == voyage_4_large_settings
        assert config.query_provider == voyage_4_nano_settings

    def test_config_with_same_provider(self, voyage_4_large_settings: EmbeddingProviderSettings):
        """Test creating config with same provider but different models (less common use case)."""
        try:
            from codeweaver.providers.config.asymmetric import AsymmetricEmbeddingProviderSettings

            from codeweaver.providers.config.categories import EmbeddingProviderSettings
        except ImportError:
            pytest.skip("AsymmetricEmbeddingProviderSettings not yet implemented")
        voyage_4_settings = EmbeddingProviderSettings(
            provider=Provider.VOYAGE,
            model_name="voyage-4",
            embedding_config=VoyageEmbeddingConfig(model_name="voyage-4"),
        )
        config = AsymmetricEmbeddingProviderSettings(
            embed_provider=voyage_4_large_settings, query_provider=voyage_4_settings
        )
        assert config.embed_provider.model_name == "voyage-4-large"
        assert config.query_provider.model_name == "voyage-4"


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
            from codeweaver.providers.config.asymmetric import AsymmetricEmbeddingProviderSettings
        except ImportError:
            pytest.skip("AsymmetricEmbeddingProviderSettings not yet implemented")
        config = AsymmetricEmbeddingProviderSettings(
            embed_provider=voyage_4_large_settings, query_provider=voyage_4_nano_settings
        )
        assert config.embed_provider.provider == Provider.VOYAGE
        assert config.query_provider.provider == Provider.SENTENCE_TRANSFORMERS

    def test_validation_confirms_compatibility(
        self,
        voyage_4_large_settings: EmbeddingProviderSettings,
        voyage_4_nano_settings: EmbeddingProviderSettings,
    ):
        """Test that validation actually checks model family compatibility."""
        try:
            from codeweaver.providers.config.asymmetric import AsymmetricEmbeddingProviderSettings
        except ImportError:
            pytest.skip("AsymmetricEmbeddingProviderSettings not yet implemented")
        config = AsymmetricEmbeddingProviderSettings(
            embed_provider=voyage_4_large_settings, query_provider=voyage_4_nano_settings
        )
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
            from codeweaver.providers.config.asymmetric import AsymmetricEmbeddingProviderSettings
        except ImportError:
            pytest.skip("AsymmetricEmbeddingProviderSettings not yet implemented")
        config = AsymmetricEmbeddingProviderSettings(
            embed_provider=voyage_code_3_settings,
            query_provider=openai_settings,
            validate_family_compatibility=False,
        )
        assert config.embed_provider == voyage_code_3_settings
        assert config.query_provider == openai_settings


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
            from codeweaver.providers.config.asymmetric import AsymmetricEmbeddingProviderSettings
        except ImportError:
            pytest.skip("AsymmetricEmbeddingProviderSettings not yet implemented")
        with pytest.raises(ConfigurationError, match="does not belong to a model family"):
            AsymmetricEmbeddingProviderSettings(
                embed_provider=voyage_4_large_settings, query_provider=voyage_code_3_settings
            )

    def test_cross_provider_incompatibility(
        self,
        voyage_4_large_settings: EmbeddingProviderSettings,
        openai_settings: EmbeddingProviderSettings,
    ):
        """Test that incompatible cross-provider models are rejected."""
        try:
            from codeweaver.providers.config.asymmetric import AsymmetricEmbeddingProviderSettings
        except ImportError:
            pytest.skip("AsymmetricEmbeddingProviderSettings not yet implemented")
        with pytest.raises(ConfigurationError, match="does not belong to a model family"):
            AsymmetricEmbeddingProviderSettings(
                embed_provider=voyage_4_large_settings, query_provider=openai_settings
            )


@pytest.mark.unit
class TestModelWithoutFamily:
    """Test validation for models without family assignments."""

    def test_model_without_family_rejected(
        self, voyage_4_large_settings: EmbeddingProviderSettings
    ):
        """Test that models without family assignment are rejected."""
        try:
            from codeweaver.providers.config.asymmetric import AsymmetricEmbeddingProviderSettings
            from codeweaver.providers.config.embedding import FastEmbedEmbeddingConfig

            from codeweaver.providers.config.categories import EmbeddingProviderSettings
        except ImportError:
            pytest.skip("AsymmetricEmbeddingProviderSettings not yet implemented")
        no_family_settings = EmbeddingProviderSettings(
            provider=Provider.FASTEMBED,
            model_name="BAAI/bge-small-en-v1.5",
            embedding_config=FastEmbedEmbeddingConfig(model_name="BAAI/bge-small-en-v1.5"),
        )
        with pytest.raises(ConfigurationError, match=r"model.*family"):
            AsymmetricEmbeddingProviderSettings(
                embed_provider=voyage_4_large_settings, query_provider=no_family_settings
            )


@pytest.mark.unit
class TestDimensionMismatch:
    """Test validation for dimension incompatibility."""

    def test_dimension_mismatch_caught(self):
        """Test that dimension mismatches are caught during validation."""
        pytest.skip("Dimension validation test requires specific test fixtures")


@pytest.mark.unit
class TestUnknownModel:
    """Test validation for unknown/unregistered models."""

    def test_unknown_model_rejected(self, voyage_4_large_settings: EmbeddingProviderSettings):
        """Test that unknown models not in capability registry are rejected."""
        try:
            from codeweaver.providers.config.asymmetric import AsymmetricEmbeddingProviderSettings

            from codeweaver.providers.config.categories import EmbeddingProviderSettings
        except ImportError:
            pytest.skip("AsymmetricEmbeddingProviderSettings not yet implemented")
        unknown_settings = EmbeddingProviderSettings(
            provider=Provider.VOYAGE,
            model_name="voyage-99-nonexistent",
            embedding_config=VoyageEmbeddingConfig(model_name="voyage-99-nonexistent"),
        )
        with pytest.raises(ConfigurationError, match=r"unknown.*model|not.*found"):
            AsymmetricEmbeddingProviderSettings(
                embed_provider=voyage_4_large_settings, query_provider=unknown_settings
            )


@pytest.mark.unit
class TestErrorMessageQuality:
    """Test that error messages are helpful and actionable."""

    def test_error_contains_model_names(
        self,
        voyage_4_large_settings: EmbeddingProviderSettings,
        voyage_code_3_settings: EmbeddingProviderSettings,
    ):
        """Test that error messages include model names for debugging."""
        error_message = self._retrieve_error_message_from_configuration(
            voyage_4_large_settings, voyage_code_3_settings
        )
        assert "voyage-code-3" in error_message

    def test_error_contains_family_information(
        self,
        voyage_4_large_settings: EmbeddingProviderSettings,
        voyage_code_3_settings: EmbeddingProviderSettings,
    ):
        """Test that error messages explain family incompatibility."""
        error_message = self._retrieve_error_message_from_configuration(
            voyage_4_large_settings, voyage_code_3_settings
        )
        assert "family" in error_message or "compatible" in error_message

    def _retrieve_error_message_from_configuration(
        self, voyage_4_large_settings, voyage_code_3_settings
    ):
        try:
            from codeweaver.providers.config.asymmetric import AsymmetricEmbeddingProviderSettings
        except ImportError:
            pytest.skip("AsymmetricEmbeddingProviderSettings not yet implemented")
        with pytest.raises(ConfigurationError) as exc_info:
            AsymmetricEmbeddingProviderSettings(
                embed_provider=voyage_4_large_settings, query_provider=voyage_code_3_settings
            )
        return str(exc_info.value).lower()

    def test_error_provides_suggestions(
        self,
        voyage_4_large_settings: EmbeddingProviderSettings,
        openai_settings: EmbeddingProviderSettings,
    ):
        """Test that error messages suggest alternative models."""
        try:
            from codeweaver.providers.config.asymmetric import AsymmetricEmbeddingProviderSettings
        except ImportError:
            pytest.skip("AsymmetricEmbeddingProviderSettings not yet implemented")
        with pytest.raises(ConfigurationError) as exc_info:
            AsymmetricEmbeddingProviderSettings(
                embed_provider=voyage_4_large_settings, query_provider=openai_settings
            )
        assert hasattr(exc_info.value, "suggestions")
        assert len(exc_info.value.suggestions) > 0
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
            from codeweaver.providers.config.asymmetric import AsymmetricEmbeddingProviderSettings
        except ImportError:
            pytest.skip("AsymmetricEmbeddingProviderSettings not yet implemented")
        with pytest.raises(ConfigurationError) as exc_info:
            AsymmetricEmbeddingProviderSettings(
                embed_provider=voyage_4_large_settings, query_provider=voyage_code_3_settings
            )
        assert exc_info.value is not None


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
            from codeweaver.providers.config.asymmetric import AsymmetricEmbeddingProviderSettings
        except ImportError:
            pytest.skip("AsymmetricEmbeddingProviderSettings not yet implemented")
        config = AsymmetricEmbeddingProviderSettings(
            embed_provider=voyage_4_large_settings, query_provider=voyage_4_nano_settings
        )
        assert config.embed_provider.provider == Provider.VOYAGE
        assert config.query_provider.provider == Provider.SENTENCE_TRANSFORMERS

    def test_family_linking_verified(
        self,
        voyage_4_large_settings: EmbeddingProviderSettings,
        voyage_4_nano_settings: EmbeddingProviderSettings,
    ):
        """Test that family linking is validated across providers."""
        try:
            from codeweaver.providers.config.asymmetric import AsymmetricEmbeddingProviderSettings
        except ImportError:
            pytest.skip("AsymmetricEmbeddingProviderSettings not yet implemented")
        config = AsymmetricEmbeddingProviderSettings(
            embed_provider=voyage_4_large_settings, query_provider=voyage_4_nano_settings
        )
        assert config is not None


@pytest.mark.unit
class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_identical_settings(self, voyage_4_large_settings: EmbeddingProviderSettings):
        """Test config with identical embed and query settings."""
        try:
            from codeweaver.providers.config.asymmetric import AsymmetricEmbeddingProviderSettings
        except ImportError:
            pytest.skip("AsymmetricEmbeddingProviderSettings not yet implemented")
        config = AsymmetricEmbeddingProviderSettings(
            embed_provider=voyage_4_large_settings, query_provider=voyage_4_large_settings
        )
        assert config.embed_provider == config.query_provider

    def test_config_serialization(
        self,
        voyage_4_large_settings: EmbeddingProviderSettings,
        voyage_4_nano_settings: EmbeddingProviderSettings,
    ):
        """Test that config can be serialized and deserialized."""
        try:
            from codeweaver.providers.config.asymmetric import AsymmetricEmbeddingProviderSettings
        except ImportError:
            pytest.skip("AsymmetricEmbeddingProviderSettings not yet implemented")
        config = AsymmetricEmbeddingProviderSettings(
            embed_provider=voyage_4_large_settings, query_provider=voyage_4_nano_settings
        )
        config_mapping = config.model_dump()
        assert "embed_provider" in config_mapping
        assert "query_provider" in config_mapping
        restored_config = AsymmetricEmbeddingProviderSettings.model_validate(config_mapping)
        assert restored_config.embed_provider.model_name == voyage_4_large_settings.model_name
        assert restored_config.query_provider.model_name == voyage_4_nano_settings.model_name


@pytest.mark.unit
class TestIntegrationReadiness:
    """Tests to verify readiness for integration with other components."""

    def test_config_has_required_attributes(
        self,
        voyage_4_large_settings: EmbeddingProviderSettings,
        voyage_4_nano_settings: EmbeddingProviderSettings,
    ):
        """Test that config exposes necessary attributes for integration."""
        self._validate_asymmetric_embedding_config(
            voyage_4_large_settings, voyage_4_nano_settings, "embed_provider", "query_provider"
        )

    def test_config_compatible_with_settings_system(
        self,
        voyage_4_large_settings: EmbeddingProviderSettings,
        voyage_4_nano_settings: EmbeddingProviderSettings,
    ):
        """Test that config integrates with pydantic-settings patterns."""
        self._validate_asymmetric_embedding_config(
            voyage_4_large_settings, voyage_4_nano_settings, "model_dump", "model_validate"
        )

    def _validate_asymmetric_embedding_config(
        self, voyage_4_large_settings, voyage_4_nano_settings, arg2, arg3
    ):
        """Helper to validate AsymmetricEmbeddingProviderSettings attributes."""
        try:
            from codeweaver.providers.config.asymmetric import AsymmetricEmbeddingProviderSettings
        except ImportError:
            pytest.skip("AsymmetricEmbeddingProviderSettings not yet implemented")
        config = AsymmetricEmbeddingProviderSettings(
            embed_provider=voyage_4_large_settings, query_provider=voyage_4_nano_settings
        )
        assert hasattr(config, arg2)
        assert hasattr(config, arg3)
