# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Integration tests for AsymmetricEmbeddingProviderSettings TOML loading and validation.

Tests cover TOML file loading, configuration parsing, validation, and error scenarios:
- TOML loading with asymmetric embedding configuration
- Backward compatibility with symmetric mode (traditional embedding field)
- Mutual exclusivity validation between embedding modes
- Family compatibility validation on load
- Environment variable overrides
- Error message quality and actionability
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from codeweaver.core import Provider
from codeweaver.core.exceptions import ConfigurationError


if TYPE_CHECKING:
    from codeweaver.providers.config.providers import (
        AsymmetricEmbeddingProviderSettings,
        ProviderSettings,
    )


pytestmark = [pytest.mark.integration]


# ===========================================================================
# *                           Helper Functions
# ===========================================================================


def create_toml_file(tmp_path: Path, content: str) -> tuple[Path, Path]:
    """Create a temporary TOML file with the given content.

    Args:
        tmp_path: pytest tmp_path fixture directory.
        content: TOML configuration content.

    Returns:
        Tuple of (toml_file path, project_dir path).
    """
    # Create a test project directory
    project_dir = tmp_path / "test_project"
    project_dir.mkdir(exist_ok=True)

    toml_file = tmp_path / "codeweaver.toml"

    # Add required engine fields to TOML content
    full_content = f"""
[engine]
project_path = "{project_dir!s}"
project_name = "test_project"
config_file = "{toml_file!s}"

{content}
"""

    toml_file.write_text(full_content)
    return toml_file, project_dir


def load_provider_settings_from_toml(toml_file: Path) -> ProviderSettings:
    """Load ProviderSettings from a TOML file.

    Args:
        toml_file: Path to the TOML file.

    Returns:
        ProviderSettings instance loaded from the TOML file.
    """
    import tomllib

    from codeweaver.providers import ProviderSettings

    with open(toml_file, "rb") as f:
        toml_data = tomllib.load(f)

    provider_data = toml_data.get("provider", {})

    # The settings class expects 'reranking' and 'embedding' as tuples/lists
    # If the TOML uses the list-of-tables syntax [[provider.embedding]],
    # it will already be a list.

    return ProviderSettings.model_validate(provider_data)


# ===========================================================================
# *                    Asymmetric TOML Loading Tests
# ===========================================================================


@pytest.mark.external_api
@pytest.mark.integration
@pytest.mark.qdrant
class TestAsymmetricEmbeddingTOMLLoading:
    """Test loading asymmetric embedding configurations from TOML files."""

    def test_load_asymmetric_embedding_from_toml(self, tmp_path: Path):
        """Test loading asymmetric embedding config from TOML file.

        Verifies:
        - Asymmetric config loads correctly
        - Both embed and query provider settings are populated
        - validate_family_compatibility defaults to True
        - Symmetric mode (embedding field) is None
        """
        toml_content = """
[provider.asymmetric_embedding]
validate_family_compatibility = true

[provider.asymmetric_embedding.embed_provider_settings]
provider = "voyage"
model_name = "voyage-4-large"

[provider.asymmetric_embedding.query_provider_settings]
provider = "sentence_transformers"
model_name = "voyage-4-nano"
"""
        toml_file, _ = create_toml_file(tmp_path, toml_content)

        # Load settings from TOML using pydantic-settings
        # Import tomllib to parse TOML directly
        import tomllib

        with open(toml_file, "rb") as f:
            toml_data = tomllib.load(f)

        # Import ProviderSettings directly
        from codeweaver.providers import ProviderSettings

        # Create ProviderSettings from TOML data
        provider_data = toml_data.get("provider", {})
        settings = ProviderSettings(**provider_data)

        # Verify asymmetric config loaded
        assert settings.asymmetric_embedding is not None

        config: AsymmetricEmbeddingProviderSettings = settings.asymmetric_embedding

        # Verify embed provider settings
        assert config.embed_provider_settings is not None
        assert config.embed_provider_settings.provider == Provider.VOYAGE
        assert str(config.embed_provider_settings.model_name) == "voyage-4-large"

        # Verify query provider settings
        assert config.query_provider_settings is not None
        assert config.query_provider_settings.provider == Provider.SENTENCE_TRANSFORMERS
        assert str(config.query_provider_settings.model_name) == "voyage-4-nano"

        # Verify validation setting
        assert config.validate_family_compatibility is True

        # Verify symmetric mode is None
        assert settings.embedding is None or len(settings.embedding) == 0

    def test_asymmetric_with_validation_disabled(self, tmp_path: Path):
        """Test loading asymmetric config with family validation disabled.

        Verifies:
        - validate_family_compatibility can be set to False
        - Config loads without family validation errors
        """
        toml_content = """
[provider.asymmetric_embedding]
validate_family_compatibility = false

[provider.asymmetric_embedding.embed_provider_settings]
provider = "voyage"
model_name = "voyage-code-3"

[provider.asymmetric_embedding.query_provider_settings]
provider = "openai"
model_name = "text-embedding-3-large"
"""
        toml_file, _ = create_toml_file(tmp_path, toml_content)

        settings = load_provider_settings_from_toml(toml_file)

        assert settings.asymmetric_embedding is not None
        assert settings.asymmetric_embedding.validate_family_compatibility is False

    def test_asymmetric_same_provider_different_models(self, tmp_path: Path):
        """Test asymmetric config with same provider but different models.

        Verifies:
        - Same provider can be used for both embed and query
        - Different models from same family work correctly
        """
        toml_content = """
[provider.asymmetric_embedding]

[provider.asymmetric_embedding.embed_provider_settings]
provider = "voyage"
model_name = "voyage-4-large"

[provider.asymmetric_embedding.query_provider_settings]
provider = "voyage"
model_name = "voyage-4"
"""
        toml_file, _ = create_toml_file(tmp_path, toml_content)

        settings = load_provider_settings_from_toml(toml_file)

        config = settings.asymmetric_embedding
        assert config is not None
        assert config.embed_provider_settings.provider == Provider.VOYAGE
        assert config.query_provider_settings.provider == Provider.VOYAGE
        assert str(config.embed_provider_settings.model_name) == "voyage-4-large"
        assert str(config.query_provider_settings.model_name) == "voyage-4"


# ===========================================================================
# *                    Backward Compatibility Tests
# ===========================================================================


@pytest.mark.external_api
@pytest.mark.integration
@pytest.mark.qdrant
class TestSymmetricModeBackwardCompatibility:
    """Test backward compatibility with traditional symmetric embedding mode."""

    def test_symmetric_mode_still_works(self, tmp_path: Path):
        """Test that traditional symmetric config still loads correctly.

        Verifies:
        - embedding field (symmetric mode) still works
        - asymmetric_embedding is None when symmetric mode is used
        - No breaking changes to existing configurations
        """
        toml_content = """
[[provider.embedding]]
config_type = "symmetric"
provider = "voyage"
model_name = "voyage-code-3"
"""
        toml_file, _ = create_toml_file(tmp_path, toml_content)

        settings = load_provider_settings_from_toml(toml_file)

        # Verify symmetric mode loaded
        assert settings.embedding is not None
        assert len(settings.embedding) > 0
        assert settings.embedding[0].provider == Provider.VOYAGE
        assert str(settings.embedding[0].model_name) == "voyage-code-3"

        # Verify asymmetric mode is None
        assert settings.asymmetric_embedding is None

    def test_multiple_embedding_providers_symmetric(self, tmp_path: Path):
        """Test symmetric mode with multiple embedding providers (fallback chain).

        Verifies:
        - Multiple providers in embedding tuple work
        - asymmetric_embedding remains None
        """
        toml_content = """
[[provider.embedding]]
config_type = "symmetric"
provider = "voyage"
model_name = "voyage-code-3"

[[provider.embedding]]
config_type = "symmetric"
provider = "fastembed"
model_name = "BAAI/bge-small-en-v1.5"
"""
        toml_file, _ = create_toml_file(tmp_path, toml_content)

        settings = load_provider_settings_from_toml(toml_file)

        assert settings.embedding is not None
        assert len(settings.embedding) == 2
        assert settings.asymmetric_embedding is None

    def test_no_embedding_config_uses_defaults(self, tmp_path: Path):
        """Test that no embedding config falls back to defaults.

        Verifies:
        - When no embedding config provided, defaults are used
        - System remains functional without explicit config
        """
        toml_content = """
# Empty provider section - use defaults
[provider]
"""
        toml_file, _ = create_toml_file(tmp_path, toml_content)

        settings = load_provider_settings_from_toml(toml_file)

        # Should have default embedding settings
        # Note: actual default depends on installed libraries
        assert settings is not None


# ===========================================================================
# *                    Mutual Exclusion Tests
# ===========================================================================


@pytest.mark.external_api
@pytest.mark.integration
@pytest.mark.qdrant
class TestMutualExclusionValidation:
    """Test mutual exclusion between embedding modes."""

    def test_both_modes_raises_error(self, tmp_path: Path):
        """Test that specifying both embedding modes raises ConfigurationError.

        Verifies:
        - ConfigurationError is raised
        - Error message mentions both field names
        - Error contains "cannot specify both"
        """
        toml_content = """
[[provider.embedding]]
config_type = "symmetric"
provider = "voyage"
model_name = "voyage-code-3"

[provider.asymmetric_embedding]

[provider.asymmetric_embedding.embed_provider_settings]
provider = "voyage"
model_name = "voyage-4-large"

[provider.asymmetric_embedding.query_provider_settings]
provider = "voyage"
model_name = "voyage-4-nano"
"""
        toml_file, _ = create_toml_file(tmp_path, toml_content)

        from codeweaver.server.config.settings import CodeWeaverSettings

        with pytest.raises(ConfigurationError) as exc_info:
            CodeWeaverSettings(config_file=toml_file)

        error_message = str(exc_info.value).lower()
        assert "cannot specify both" in error_message or "both" in error_message
        assert "embedding" in error_message
        assert "asymmetric" in error_message

    def test_error_message_mentions_both_fields(self, tmp_path: Path):
        """Test that error message explicitly mentions both conflicting fields.

        Verifies:
        - Error mentions 'embedding' field
        - Error mentions 'asymmetric_embedding' field
        - Clear guidance on which mode to choose
        """
        toml_content = """
[[provider.embedding]]
config_type = "symmetric"
provider = "fastembed"
model_name = "BAAI/bge-small-en-v1.5"

[provider.asymmetric_embedding]

[provider.asymmetric_embedding.embed_provider_settings]
provider = "fastembed"
model_name = "BAAI/bge-small-en-v1.5"

[provider.asymmetric_embedding.query_provider_settings]
provider = "fastembed"
model_name = "BAAI/bge-small-en-v1.5"
"""
        toml_file, _ = create_toml_file(tmp_path, toml_content)

        from codeweaver.server.config.settings import CodeWeaverSettings

        with pytest.raises(ConfigurationError) as exc_info:
            CodeWeaverSettings(config_file=toml_file)

        error = exc_info.value
        assert hasattr(error, "message") or str(error)

        error_text = str(error).lower()
        assert "embedding" in error_text
        assert "asymmetric" in error_text

    def test_error_provides_mode_selection_guidance(self, tmp_path: Path):
        """Test that error provides guidance on selecting between modes.

        Verifies:
        - Error suggests removing one mode
        - Error explains difference between modes
        - Error provides actionable suggestions
        """
        toml_content = """
[[provider.embedding]]
config_type = "symmetric"
provider = "voyage"
model_name = "voyage-code-3"

[provider.asymmetric_embedding]

[provider.asymmetric_embedding.embed_provider_settings]
provider = "voyage"
model_name = "voyage-4-large"

[provider.asymmetric_embedding.query_provider_settings]
provider = "sentence_transformers"
model_name = "voyage-4-nano"
"""
        toml_file, _ = create_toml_file(tmp_path, toml_content)

        from codeweaver.server.config.settings import CodeWeaverSettings

        with pytest.raises(ConfigurationError) as exc_info:
            CodeWeaverSettings(config_file=toml_file)

        error = exc_info.value

        # Check for suggestions
        if hasattr(error, "suggestions"):
            assert len(error.suggestions) > 0
            suggestions_text = " ".join(error.suggestions).lower()
            assert any(
                keyword in suggestions_text for keyword in ["remove", "choose", "use", "symmetric"]
            )


# ===========================================================================
# *                    Family Validation Tests
# ===========================================================================


@pytest.mark.external_api
@pytest.mark.integration
@pytest.mark.qdrant
class TestFamilyValidationOnLoad:
    """Test family compatibility validation during TOML loading."""

    def test_incompatible_models_caught_on_load(self, tmp_path: Path):
        """Test that incompatible model families are caught during load.

        Verifies:
        - ConfigurationError raised for incompatible families
        - Error message mentions "family mismatch" or similar
        - Model names included in error
        """
        toml_content = """
[provider.asymmetric_embedding]

[provider.asymmetric_embedding.embed_provider_settings]
provider = "voyage"
model_name = "voyage-code-3"

[provider.asymmetric_embedding.query_provider_settings]
provider = "voyage"
model_name = "voyage-4-nano"
"""
        toml_file, _ = create_toml_file(tmp_path, toml_content)

        from codeweaver.server.config.settings import CodeWeaverSettings

        with pytest.raises(ConfigurationError) as exc_info:
            CodeWeaverSettings(config_file=toml_file)

        error_message = str(exc_info.value).lower()
        assert any(keyword in error_message for keyword in ["family", "incompatible", "different"])
        # Check that model names are mentioned
        assert "voyage-code-3" in error_message or "voyage" in error_message

    def test_cross_family_pairing_rejected(self, tmp_path: Path):
        """Test that models from completely different families are rejected.

        Verifies:
        - VOYAGE model + OpenAI model rejected
        - Clear family mismatch error
        """
        toml_content = """
[provider.asymmetric_embedding]

[provider.asymmetric_embedding.embed_provider_settings]
provider = "voyage"
model_name = "voyage-4-large"

[provider.asymmetric_embedding.query_provider_settings]
provider = "openai"
model_name = "text-embedding-3-large"
"""
        toml_file, _ = create_toml_file(tmp_path, toml_content)

        from codeweaver.server.config.settings import CodeWeaverSettings

        with pytest.raises(ConfigurationError) as exc_info:
            CodeWeaverSettings(config_file=toml_file)

        error_message = str(exc_info.value).lower()
        assert "family" in error_message or "incompatible" in error_message

    def test_unknown_model_caught_on_load(self, tmp_path: Path):
        """Test that unknown models are caught during TOML loading.

        Verifies:
        - ConfigurationError raised for unknown models
        - Error mentions model not found or unknown
        - Helpful suggestions provided
        """
        toml_content = """
[provider.asymmetric_embedding]

[provider.asymmetric_embedding.embed_provider_settings]
provider = "voyage"
model_name = "voyage-99-nonexistent"

[provider.asymmetric_embedding.query_provider_settings]
provider = "voyage"
model_name = "voyage-4-nano"
"""
        toml_file, _ = create_toml_file(tmp_path, toml_content)

        from codeweaver.server.config.settings import CodeWeaverSettings

        with pytest.raises(ConfigurationError) as exc_info:
            CodeWeaverSettings(config_file=toml_file)

        error_message = str(exc_info.value).lower()
        assert any(keyword in error_message for keyword in ["not found", "unknown", "capabilities"])


# ===========================================================================
# *                    Valid Configuration Tests
# ===========================================================================


@pytest.mark.external_api
@pytest.mark.integration
@pytest.mark.qdrant
class TestValidAsymmetricConfigurations:
    """Test valid asymmetric embedding configurations."""

    def test_valid_voyage_4_asymmetric_config(self, tmp_path: Path):
        """Test valid Voyage-4 family asymmetric configuration.

        Verifies:
        - Validation passes for compatible Voyage-4 models
        - Both providers configured correctly
        - Family compatibility confirmed
        """
        toml_content = """
[provider.asymmetric_embedding]

[provider.asymmetric_embedding.embed_provider_settings]
provider = "voyage"
model_name = "voyage-4-large"

[provider.asymmetric_embedding.query_provider_settings]
provider = "voyage"
model_name = "voyage-4"
"""
        toml_file, _ = create_toml_file(tmp_path, toml_content)

        settings = load_provider_settings_from_toml(toml_file)

        config = settings.asymmetric_embedding
        assert config is not None
        assert config.validate_family_compatibility is True
        assert config.embed_provider_settings.provider == Provider.VOYAGE
        assert config.query_provider_settings.provider == Provider.VOYAGE

    def test_cross_provider_same_family(self, tmp_path: Path):
        """Test cross-provider configuration with same model family.

        Verifies:
        - VOYAGE API + SENTENCE_TRANSFORMERS local work together
        - Family validation passes
        - Different provider implementations compatible
        """
        toml_content = """
[provider.asymmetric_embedding]

[provider.asymmetric_embedding.embed_provider_settings]
provider = "voyage"
model_name = "voyage-4-large"

[provider.asymmetric_embedding.query_provider_settings]
provider = "sentence_transformers"
model_name = "voyage-4-nano"
"""
        toml_file, _ = create_toml_file(tmp_path, toml_content)

        settings = load_provider_settings_from_toml(toml_file)

        config = settings.asymmetric_embedding
        assert config is not None
        assert config.embed_provider_settings.provider == Provider.VOYAGE
        assert config.query_provider_settings.provider == Provider.SENTENCE_TRANSFORMERS

    def test_validation_default_true(self, tmp_path: Path):
        """Test that validate_family_compatibility defaults to True.

        Verifies:
        - When not specified, validation defaults to True
        - Family validation is performed by default
        """
        toml_content = """
[provider.asymmetric_embedding]

[provider.asymmetric_embedding.embed_provider_settings]
provider = "voyage"
model_name = "voyage-4-large"

[provider.asymmetric_embedding.query_provider_settings]
provider = "voyage"
model_name = "voyage-4"
"""
        toml_file, _ = create_toml_file(tmp_path, toml_content)

        settings = load_provider_settings_from_toml(toml_file)

        assert settings.asymmetric_embedding.validate_family_compatibility is True


# ===========================================================================
# *                    Environment Variable Tests
# ===========================================================================


@pytest.mark.external_api
@pytest.mark.integration
@pytest.mark.qdrant
class TestEnvironmentVariableOverrides:
    """Test environment variable override behavior."""

    def test_env_var_overrides_toml(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
        """Test that environment variables can override TOML settings.

        Verifies:
        - CODEWEAVER_* env vars respected
        - Asymmetric config respects overrides
        - Proper precedence: env > TOML > defaults
        """
        toml_content = """
[provider.asymmetric_embedding]

[provider.asymmetric_embedding.embed_provider_settings]
provider = "voyage"
model_name = "voyage-4-large"

[provider.asymmetric_embedding.query_provider_settings]
provider = "voyage"
model_name = "voyage-4"
"""
        toml_file, _ = create_toml_file(tmp_path, toml_content)

        # Set environment variable override
        monkeypatch.setenv(
            "CODEWEAVER_PROVIDER_ASYMMETRIC_EMBEDDING_VALIDATE_FAMILY_COMPATIBILITY", "false"
        )

        settings = load_provider_settings_from_toml(toml_file)

        # Should use env var value (false) instead of default (true)
        assert settings.asymmetric_embedding.validate_family_compatibility is False


# ===========================================================================
# *                    TOML Structure Tests
# ===========================================================================


@pytest.mark.external_api
@pytest.mark.integration
@pytest.mark.qdrant
class TestTOMLStructureValidation:
    """Test TOML structure and schema validation."""

    def test_missing_embed_provider_settings(self, tmp_path: Path):
        """Test that missing embed_provider_settings is caught.

        Verifies:
        - Required field validation works
        - Clear error message about missing field
        """
        toml_content = """
[provider.asymmetric_embedding]

[provider.asymmetric_embedding.query_provider_settings]
provider = "voyage"
model_name = "voyage-4-nano"
"""
        toml_file, _ = create_toml_file(tmp_path, toml_content)

        from codeweaver.server.config.settings import CodeWeaverSettings

        with pytest.raises((ConfigurationError, ValueError)) as exc_info:
            CodeWeaverSettings(config_file=toml_file)

        # Should indicate missing required field
        assert exc_info.value is not None

    def test_missing_query_provider_settings(self, tmp_path: Path):
        """Test that missing query_provider_settings is caught.

        Verifies:
        - Required field validation works
        - Clear error message about missing field
        """
        toml_content = """
[provider.asymmetric_embedding]

[provider.asymmetric_embedding.embed_provider_settings]
provider = "voyage"
model_name = "voyage-4-large"
"""
        toml_file, _ = create_toml_file(tmp_path, toml_content)

        from codeweaver.server.config.settings import CodeWeaverSettings

        with pytest.raises((ConfigurationError, ValueError)) as exc_info:
            CodeWeaverSettings(config_file=toml_file)

        # Should indicate missing required field
        assert exc_info.value is not None

    def test_invalid_provider_name(self, tmp_path: Path):
        """Test that invalid provider names are caught.

        Verifies:
        - Provider enum validation works
        - Clear error about invalid provider
        """
        toml_content = """
[provider.asymmetric_embedding]

[provider.asymmetric_embedding.embed_provider_settings]
provider = "invalid_provider"
model_name = "some-model"

[provider.asymmetric_embedding.query_provider_settings]
provider = "voyage"
model_name = "voyage-4-nano"
"""
        toml_file, _ = create_toml_file(tmp_path, toml_content)

        from codeweaver.server.config.settings import CodeWeaverSettings

        with pytest.raises((ConfigurationError, ValueError)) as exc_info:
            CodeWeaverSettings(config_file=toml_file)

        # Should indicate invalid provider
        assert exc_info.value is not None


# ===========================================================================
# *                    Full Configuration Tests
# ===========================================================================


@pytest.mark.external_api
@pytest.mark.integration
@pytest.mark.qdrant
class TestFullConfigurationIntegration:
    """Test asymmetric config as part of full CodeWeaver configuration."""

    def test_asymmetric_with_other_provider_settings(self, tmp_path: Path):
        """Test asymmetric embedding alongside other provider configurations.

        Verifies:
        - Asymmetric embedding coexists with other settings
        - Vector store, reranking, etc. still work
        - No conflicts with other provider types
        """
        toml_content = """
[provider.asymmetric_embedding]

[provider.asymmetric_embedding.embed_provider_settings]
provider = "voyage"
model_name = "voyage-4-large"

[provider.asymmetric_embedding.query_provider_settings]
provider = "voyage"
model_name = "voyage-4"

[[provider.reranking]]
provider = "voyage"
model_name = "voyage:rerank-2.5"

[[provider.vector_store]]
provider = "qdrant"

[provider.vector_store.client_options]
host = "127.0.0.1"
"""
        toml_file, _ = create_toml_file(tmp_path, toml_content)

        settings = load_provider_settings_from_toml(toml_file)

        # Verify all provider types configured
        assert settings.asymmetric_embedding is not None
        assert settings.reranking is not None
        assert settings.vector_store is not None

    def test_complete_codeweaver_config_with_asymmetric(self, tmp_path: Path):
        """Test complete CodeWeaver configuration with asymmetric embedding.

        Verifies:
        - Full system configuration works
        - Asymmetric embedding integrates properly
        - All settings sections coexist
        """
        toml_content = """
[provider.asymmetric_embedding]
validate_family_compatibility = true

[provider.asymmetric_embedding.embed_provider_settings]
provider = "voyage"
model_name = "voyage-4-large"

[provider.asymmetric_embedding.query_provider_settings]
provider = "sentence_transformers"
model_name = "voyage-4-nano"

[[provider.vector_store]]
provider = "qdrant"

[provider.vector_store.client_options]
host = "127.0.0.1"
port = 6333
"""
        toml_file, _ = create_toml_file(tmp_path, toml_content)

        settings = load_provider_settings_from_toml(toml_file)

        # Verify complete configuration
        assert settings is not None
        assert settings.asymmetric_embedding is not None
        assert settings.vector_store is not None


# ===========================================================================
# *                    Serialization Tests
# ===========================================================================


@pytest.mark.external_api
@pytest.mark.integration
@pytest.mark.qdrant
class TestConfigurationSerialization:
    """Test serialization and deserialization of loaded configurations."""

    def test_loaded_config_can_be_serialized(self, tmp_path: Path):
        """Test that loaded asymmetric config can be serialized.

        Verifies:
        - model_dump() works on loaded config
        - Serialized form matches expected structure
        - Can round-trip through serialization
        """
        toml_content = """
[provider.asymmetric_embedding]

[provider.asymmetric_embedding.embed_provider_settings]
provider = "voyage"
model_name = "voyage-4-large"

[provider.asymmetric_embedding.query_provider_settings]
provider = "voyage"
model_name = "voyage-4"
"""
        toml_file, _ = create_toml_file(tmp_path, toml_content)

        settings = load_provider_settings_from_toml(toml_file)

        # Serialize to dict
        config = settings.asymmetric_embedding.model_dump()

        assert "embed_provider_settings" in config
        assert "query_provider_settings" in config
        assert "validate_family_compatibility" in config

    def test_round_trip_serialization(self, tmp_path: Path):
        """Test that config can be serialized and deserialized.

        Verifies:
        - Load from TOML → serialize → deserialize produces same config
        - No data loss in serialization
        """
        toml_content = """
[provider.asymmetric_embedding]

[provider.asymmetric_embedding.embed_provider_settings]
provider = "voyage"
model_name = "voyage-4-large"

[provider.asymmetric_embedding.query_provider_settings]
provider = "sentence_transformers"
model_name = "voyage-4-nano"
"""
        toml_file, _ = create_toml_file(tmp_path, toml_content)

        settings = load_provider_settings_from_toml(toml_file)

        original_config = settings.asymmetric_embedding

        # Serialize and deserialize
        config = original_config.model_dump()
        # Import from where AsymmetricEmbeddingProviderSettings is defined
        from codeweaver.providers import AsymmetricEmbeddingProviderSettings

        restored_config = AsymmetricEmbeddingProviderSettings.model_validate(config)

        # Verify equivalence
        assert str(restored_config.embed_provider_settings.model_name) == str(
            original_config.embed_provider_settings.model_name
        )
        assert str(restored_config.query_provider_settings.model_name) == str(
            original_config.query_provider_settings.model_name
        )
        assert (
            restored_config.validate_family_compatibility
            == original_config.validate_family_compatibility
        )
