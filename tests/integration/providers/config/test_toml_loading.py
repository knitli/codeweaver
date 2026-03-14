# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Integration tests for AsymmetricEmbeddingProviderSettings TOML loading and validation.

Tests cover TOML file loading, configuration parsing, validation, and error scenarios.
Note: asymmetric embedding configs are now stored in the unified `embedding` tuple field
with config_type="asymmetric" discriminator.
"""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING

import pytest

from codeweaver.core import Provider
from codeweaver.core.exceptions import ConfigurationError


if TYPE_CHECKING:
    from codeweaver.providers.config.categories.embedding import AsymmetricEmbeddingProviderSettings
    from codeweaver.providers.config.providers import ProviderSettings


pytestmark = [pytest.mark.integration]


# ===========================================================================
# *                           Helper Functions
# ===========================================================================


def create_toml_file(tmp_path: Path, content: str) -> tuple[Path, Path]:
    """Create a temporary TOML file with the given content."""
    project_dir = tmp_path / "test_project"
    project_dir.mkdir(exist_ok=True)
    toml_file = tmp_path / "codeweaver.toml"
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
    """Load ProviderSettings from a TOML file."""
    import tomllib

    from codeweaver.providers import ProviderSettings

    with open(toml_file, "rb") as f:
        toml_data = tomllib.load(f)

    provider_data = toml_data.get("provider", {})
    return ProviderSettings.model_validate(provider_data)


def _get_asymmetric_config(
    settings: ProviderSettings,
) -> AsymmetricEmbeddingProviderSettings | None:
    """Extract first asymmetric embedding config from settings.embedding."""
    from codeweaver.providers.config.categories.embedding import AsymmetricEmbeddingProviderSettings

    if not settings.embedding:
        return None
    for config in settings.embedding:
        if isinstance(config, AsymmetricEmbeddingProviderSettings):
            return config
    return None


def _make_asymmetric_provider_data(
    embed_provider: str,
    embed_model: str,
    query_provider: str,
    query_model: str,
    validate_family: bool = True,
) -> dict:
    """Build data dict for an AsymmetricEmbeddingProviderSettings entry."""
    from codeweaver.providers.config.sdk.embedding import VoyageEmbeddingConfig

    def _make_embed_config(prov: str, model: str) -> dict:
        if prov == "voyage":
            cfg = VoyageEmbeddingConfig(model_name=model)
            return {"provider": prov, "model_name": model, "embedding_config": cfg.model_dump()}
        # fastembed/sentence_transformers have default factories
        return {"provider": prov, "model_name": model}

    return {
        "config_type": "asymmetric",
        "validate_family_compatibility": validate_family,
        "embed_provider": _make_embed_config(embed_provider, embed_model),
        "query_provider": _make_embed_config(query_provider, query_model),
    }


# ===========================================================================
# *                    Asymmetric Config Loading Tests
# ===========================================================================


@pytest.mark.external_api
@pytest.mark.integration
@pytest.mark.qdrant
class TestAsymmetricEmbeddingLoading:
    """Test loading asymmetric embedding configurations."""

    def test_load_asymmetric_from_dict(self):
        """Test loading asymmetric embedding config from a dict (like TOML would produce).

        Verifies:
        - Asymmetric config loads correctly via model_validate
        - Both embed and query provider settings are populated
        - validate_family_compatibility defaults to True
        """
        from codeweaver.providers import ProviderSettings
        from codeweaver.providers.config.sdk.embedding import VoyageEmbeddingConfig

        voyage_large_cfg = VoyageEmbeddingConfig(model_name="voyage-4-large")
        voyage_nano_cfg = VoyageEmbeddingConfig(model_name="voyage-4-nano")

        data = {
            "embedding": [
                {
                    "config_type": "asymmetric",
                    "embed_provider": {
                        "provider": "voyage",
                        "model_name": "voyage-4-large",
                        "embedding_config": voyage_large_cfg.model_dump(),
                    },
                    "query_provider": {
                        "provider": "voyage",
                        "model_name": "voyage-4-nano",
                        "embedding_config": voyage_nano_cfg.model_dump(),
                    },
                }
            ]
        }

        settings = ProviderSettings.model_validate(data)
        config = _get_asymmetric_config(settings)

        assert config is not None
        assert config.embed_provider.provider == Provider.VOYAGE
        assert str(config.embed_provider.model_name) == "voyage-4-large"
        assert config.query_provider.provider == Provider.VOYAGE
        assert str(config.query_provider.model_name) == "voyage-4-nano"
        assert config.validate_family_compatibility is True

    def test_asymmetric_with_validation_disabled(self):
        """Test asymmetric config with family validation disabled."""
        from codeweaver.providers import ProviderSettings
        from codeweaver.providers.config.sdk.embedding import VoyageEmbeddingConfig

        cfg3 = VoyageEmbeddingConfig(model_name="voyage-code-3")
        from codeweaver.providers.config.sdk.embedding import OpenAIEmbeddingConfig

        openai_cfg = OpenAIEmbeddingConfig(model_name="text-embedding-3-large")

        data = {
            "embedding": [
                {
                    "config_type": "asymmetric",
                    "validate_family_compatibility": False,
                    "embed_provider": {
                        "provider": "voyage",
                        "model_name": "voyage-code-3",
                        "embedding_config": cfg3.model_dump(),
                    },
                    "query_provider": {
                        "provider": "openai",
                        "model_name": "text-embedding-3-large",
                        "embedding_config": openai_cfg.model_dump(),
                    },
                }
            ]
        }
        settings = ProviderSettings.model_validate(data)
        config = _get_asymmetric_config(settings)

        assert config is not None
        assert config.validate_family_compatibility is False

    def test_asymmetric_same_provider_different_models(self):
        """Test asymmetric config with same provider but different models."""
        from codeweaver.providers import ProviderSettings
        from codeweaver.providers.config.sdk.embedding import VoyageEmbeddingConfig

        large_cfg = VoyageEmbeddingConfig(model_name="voyage-4-large")
        nano_cfg = VoyageEmbeddingConfig(model_name="voyage-4")

        data = {
            "embedding": [
                {
                    "config_type": "asymmetric",
                    "embed_provider": {
                        "provider": "voyage",
                        "model_name": "voyage-4-large",
                        "embedding_config": large_cfg.model_dump(),
                    },
                    "query_provider": {
                        "provider": "voyage",
                        "model_name": "voyage-4",
                        "embedding_config": nano_cfg.model_dump(),
                    },
                }
            ]
        }
        settings = ProviderSettings.model_validate(data)
        config = _get_asymmetric_config(settings)

        assert config is not None
        assert config.embed_provider.provider == Provider.VOYAGE
        assert config.query_provider.provider == Provider.VOYAGE
        assert str(config.embed_provider.model_name) == "voyage-4-large"
        assert str(config.query_provider.model_name) == "voyage-4"


# ===========================================================================
# *                    Backward Compatibility Tests (Symmetric)
# ===========================================================================


@pytest.mark.external_api
@pytest.mark.integration
@pytest.mark.qdrant
class TestSymmetricModeBackwardCompatibility:
    """Test backward compatibility with traditional symmetric embedding mode."""

    def test_symmetric_mode_still_works(self, tmp_path: Path):
        """Test that traditional symmetric config still loads correctly via TOML."""
        toml_content = """
[[provider.embedding]]
config_type = "symmetric"
provider = "fastembed"
model_name = "BAAI/bge-small-en-v1.5"
"""
        toml_file, _ = create_toml_file(tmp_path, toml_content)
        settings = load_provider_settings_from_toml(toml_file)

        assert settings.embedding is not None
        assert len(settings.embedding) > 0
        assert str(settings.embedding[0].model_name) == "BAAI/bge-small-en-v1.5"
        # No asymmetric configs present
        assert _get_asymmetric_config(settings) is None

    def test_multiple_embedding_providers_symmetric(self, tmp_path: Path):
        """Test symmetric mode with multiple embedding providers (fallback chain)."""
        toml_content = """
[[provider.embedding]]
config_type = "symmetric"
provider = "fastembed"
model_name = "BAAI/bge-small-en-v1.5"

[[provider.embedding]]
config_type = "symmetric"
provider = "fastembed"
model_name = "BAAI/bge-base-en-v1.5"
"""
        toml_file, _ = create_toml_file(tmp_path, toml_content)
        settings = load_provider_settings_from_toml(toml_file)

        assert settings.embedding is not None
        assert len(settings.embedding) == 2
        assert _get_asymmetric_config(settings) is None

    def test_no_embedding_config_uses_defaults(self, tmp_path: Path):
        """Test that no embedding config falls back to defaults."""
        toml_content = """
# Empty provider section - use defaults
[provider]
"""
        toml_file, _ = create_toml_file(tmp_path, toml_content)
        settings = load_provider_settings_from_toml(toml_file)
        assert settings is not None


# ===========================================================================
# *                    Family Validation Tests
# ===========================================================================


@pytest.mark.external_api
@pytest.mark.integration
@pytest.mark.qdrant
class TestFamilyValidationOnLoad:
    """Test family compatibility validation during loading."""

    @pytest.mark.xfail(
        reason="Family compatibility check requires capabilities resolver which is not currently implemented; "
        "cross-family detection only works when capabilities return model_family info",
        strict=False,
    )
    def test_incompatible_models_caught_on_load(self):
        """Test that incompatible model families are caught during load.

        NOTE: This test is marked xfail because the capabilities resolver does not
        currently return model family info for Voyage models. When it does, this
        test should pass without xfail.
        """
        from codeweaver.core.exceptions import ConfigurationError
        from codeweaver.providers import ProviderSettings
        from codeweaver.providers.config.sdk.embedding import VoyageEmbeddingConfig

        code3_cfg = VoyageEmbeddingConfig(model_name="voyage-code-3")
        nano_cfg = VoyageEmbeddingConfig(model_name="voyage-4-nano")

        data = {
            "embedding": [
                {
                    "config_type": "asymmetric",
                    "embed_provider": {
                        "provider": "voyage",
                        "model_name": "voyage-code-3",
                        "embedding_config": code3_cfg.model_dump(),
                    },
                    "query_provider": {
                        "provider": "voyage",
                        "model_name": "voyage-4-nano",
                        "embedding_config": nano_cfg.model_dump(),
                    },
                }
            ]
        }
        with pytest.raises(ConfigurationError) as exc_info:
            ProviderSettings.model_validate(data)

        error_message = str(exc_info.value).lower()
        assert any(keyword in error_message for keyword in ["family", "incompatible", "compatible"])

    def test_cross_family_pairing_rejected(self):
        """Test that models from completely different families are rejected."""
        from codeweaver.core.exceptions import (
            ConfigurationError,
            DatatypeMismatchError,
            DimensionMismatchError,
        )
        from codeweaver.providers import ProviderSettings
        from codeweaver.providers.config.sdk.embedding import (
            OpenAIEmbeddingConfig,
            VoyageEmbeddingConfig,
        )

        large_cfg = VoyageEmbeddingConfig(model_name="voyage-4-large")
        openai_cfg = OpenAIEmbeddingConfig(model_name="text-embedding-3-large")

        data = {
            "embedding": [
                {
                    "config_type": "asymmetric",
                    "embed_provider": {
                        "provider": "voyage",
                        "model_name": "voyage-4-large",
                        "embedding_config": large_cfg.model_dump(),
                    },
                    "query_provider": {
                        "provider": "openai",
                        "model_name": "text-embedding-3-large",
                        "embedding_config": openai_cfg.model_dump(),
                    },
                }
            ]
        }
        with pytest.raises((ConfigurationError, DatatypeMismatchError, DimensionMismatchError)):
            ProviderSettings.model_validate(data)

    @pytest.mark.xfail(
        reason="Unknown model detection requires capabilities resolver which is not currently implemented; "
        "validation succeeds silently when capabilities cannot be resolved",
        strict=False,
    )
    def test_unknown_model_caught_on_load(self):
        """Test that unknown models are caught during loading.

        NOTE: This test is marked xfail because the capabilities resolver does not
        currently raise errors for unknown models - it returns None silently.
        When capability validation is stricter, this test should pass without xfail.
        """
        from codeweaver.core.exceptions import ConfigurationError
        from codeweaver.providers import ProviderSettings
        from codeweaver.providers.config.sdk.embedding import VoyageEmbeddingConfig

        bad_cfg = VoyageEmbeddingConfig(model_name="voyage-99-nonexistent")
        nano_cfg = VoyageEmbeddingConfig(model_name="voyage-4-nano")

        data = {
            "embedding": [
                {
                    "config_type": "asymmetric",
                    "embed_provider": {
                        "provider": "voyage",
                        "model_name": "voyage-99-nonexistent",
                        "embedding_config": bad_cfg.model_dump(),
                    },
                    "query_provider": {
                        "provider": "voyage",
                        "model_name": "voyage-4-nano",
                        "embedding_config": nano_cfg.model_dump(),
                    },
                }
            ]
        }
        # Unknown models may fail with various errors at validation or capability lookup
        with pytest.raises((ConfigurationError, ValueError, Exception)):
            ProviderSettings.model_validate(data)


# ===========================================================================
# *                    Valid Configuration Tests
# ===========================================================================


@pytest.mark.external_api
@pytest.mark.integration
@pytest.mark.qdrant
class TestValidAsymmetricConfigurations:
    """Test valid asymmetric embedding configurations."""

    def test_valid_voyage_4_asymmetric_config(self):
        """Test valid Voyage-4 family asymmetric configuration."""
        from codeweaver.providers import ProviderSettings
        from codeweaver.providers.config.sdk.embedding import VoyageEmbeddingConfig

        large_cfg = VoyageEmbeddingConfig(model_name="voyage-4-large")
        small_cfg = VoyageEmbeddingConfig(model_name="voyage-4")

        data = {
            "embedding": [
                {
                    "config_type": "asymmetric",
                    "embed_provider": {
                        "provider": "voyage",
                        "model_name": "voyage-4-large",
                        "embedding_config": large_cfg.model_dump(),
                    },
                    "query_provider": {
                        "provider": "voyage",
                        "model_name": "voyage-4",
                        "embedding_config": small_cfg.model_dump(),
                    },
                }
            ]
        }
        settings = ProviderSettings.model_validate(data)
        config = _get_asymmetric_config(settings)

        assert config is not None
        assert config.validate_family_compatibility is True
        assert config.embed_provider.provider == Provider.VOYAGE
        assert config.query_provider.provider == Provider.VOYAGE

    def test_cross_provider_same_family(self):
        """Test cross-provider configuration with same model family."""
        from codeweaver.providers import ProviderSettings
        from codeweaver.providers.config.sdk.embedding import (
            SentenceTransformersEmbeddingConfig,
            VoyageEmbeddingConfig,
        )

        large_cfg = VoyageEmbeddingConfig(model_name="voyage-4-large")
        nano_cfg = SentenceTransformersEmbeddingConfig(model_name="voyageai/voyage-4-nano")

        data = {
            "embedding": [
                {
                    "config_type": "asymmetric",
                    "embed_provider": {
                        "provider": "voyage",
                        "model_name": "voyage-4-large",
                        "embedding_config": large_cfg.model_dump(),
                    },
                    "query_provider": {
                        "provider": "sentence-transformers",
                        "model_name": "voyageai/voyage-4-nano",
                        "embedding_config": nano_cfg.model_dump(),
                    },
                }
            ]
        }
        settings = ProviderSettings.model_validate(data)
        config = _get_asymmetric_config(settings)

        assert config is not None
        assert config.embed_provider.provider == Provider.VOYAGE
        assert config.query_provider.provider == Provider.SENTENCE_TRANSFORMERS

    def test_validation_default_true(self):
        """Test that validate_family_compatibility defaults to True."""
        from codeweaver.providers import ProviderSettings
        from codeweaver.providers.config.sdk.embedding import VoyageEmbeddingConfig

        large_cfg = VoyageEmbeddingConfig(model_name="voyage-4-large")
        small_cfg = VoyageEmbeddingConfig(model_name="voyage-4")

        data = {
            "embedding": [
                {
                    "config_type": "asymmetric",
                    "embed_provider": {
                        "provider": "voyage",
                        "model_name": "voyage-4-large",
                        "embedding_config": large_cfg.model_dump(),
                    },
                    "query_provider": {
                        "provider": "voyage",
                        "model_name": "voyage-4",
                        "embedding_config": small_cfg.model_dump(),
                    },
                }
            ]
        }
        settings = ProviderSettings.model_validate(data)
        config = _get_asymmetric_config(settings)

        assert config is not None
        assert config.validate_family_compatibility is True


# ===========================================================================
# *                    TOML Structure Validation Tests
# ===========================================================================


@pytest.mark.external_api
@pytest.mark.integration
@pytest.mark.qdrant
class TestTOMLStructureValidation:
    """Test TOML structure and schema validation."""

    def test_missing_embed_provider(self):
        """Test that missing embed_provider is caught."""
        from codeweaver.providers import ProviderSettings
        from codeweaver.providers.config.sdk.embedding import VoyageEmbeddingConfig

        nano_cfg = VoyageEmbeddingConfig(model_name="voyage-4-nano")
        data = {
            "embedding": [
                {
                    "config_type": "asymmetric",
                    # embed_provider is missing
                    "query_provider": {
                        "provider": "voyage",
                        "model_name": "voyage-4-nano",
                        "embedding_config": nano_cfg.model_dump(),
                    },
                }
            ]
        }
        with pytest.raises((ConfigurationError, ValueError)) as exc_info:
            ProviderSettings.model_validate(data)
        assert exc_info.value is not None

    def test_missing_query_provider(self):
        """Test that missing query_provider is caught."""
        from codeweaver.providers import ProviderSettings
        from codeweaver.providers.config.sdk.embedding import VoyageEmbeddingConfig

        large_cfg = VoyageEmbeddingConfig(model_name="voyage-4-large")
        data = {
            "embedding": [
                {
                    "config_type": "asymmetric",
                    "embed_provider": {
                        "provider": "voyage",
                        "model_name": "voyage-4-large",
                        "embedding_config": large_cfg.model_dump(),
                    },
                    # query_provider is missing
                }
            ]
        }
        with pytest.raises((ConfigurationError, ValueError)) as exc_info:
            ProviderSettings.model_validate(data)
        assert exc_info.value is not None

    def test_invalid_provider_name(self):
        """Test that invalid provider names are caught."""
        from codeweaver.providers import ProviderSettings
        from codeweaver.providers.config.sdk.embedding import VoyageEmbeddingConfig

        nano_cfg = VoyageEmbeddingConfig(model_name="voyage-4-nano")
        data = {
            "embedding": [
                {
                    "config_type": "asymmetric",
                    "embed_provider": {
                        "provider": "invalid_provider_xyz",
                        "model_name": "some-model",
                    },
                    "query_provider": {
                        "provider": "voyage",
                        "model_name": "voyage-4-nano",
                        "embedding_config": nano_cfg.model_dump(),
                    },
                }
            ]
        }
        with pytest.raises((ConfigurationError, ValueError)) as exc_info:
            ProviderSettings.model_validate(data)
        assert exc_info.value is not None


# ===========================================================================
# *                    Full Configuration Tests
# ===========================================================================


@pytest.mark.external_api
@pytest.mark.integration
@pytest.mark.qdrant
class TestFullConfigurationIntegration:
    """Test asymmetric config as part of full CodeWeaver configuration."""

    def test_asymmetric_with_other_provider_settings(self):
        """Test asymmetric embedding alongside other provider configurations."""
        from codeweaver.providers import ProviderSettings
        from codeweaver.providers.config.sdk.embedding import VoyageEmbeddingConfig

        large_cfg = VoyageEmbeddingConfig(model_name="voyage-4-large")
        small_cfg = VoyageEmbeddingConfig(model_name="voyage-4")

        data = {
            "embedding": [
                {
                    "config_type": "asymmetric",
                    "embed_provider": {
                        "provider": "voyage",
                        "model_name": "voyage-4-large",
                        "embedding_config": large_cfg.model_dump(),
                    },
                    "query_provider": {
                        "provider": "voyage",
                        "model_name": "voyage-4",
                        "embedding_config": small_cfg.model_dump(),
                    },
                }
            ],
            "vector_store": [{"provider": "memory"}],
        }
        settings = ProviderSettings.model_validate(data)

        assert _get_asymmetric_config(settings) is not None
        assert settings.vector_store is not None

    def test_complete_config_with_asymmetric(self):
        """Test complete configuration with asymmetric embedding."""
        from codeweaver.providers import ProviderSettings
        from codeweaver.providers.config.sdk.embedding import (
            SentenceTransformersEmbeddingConfig,
            VoyageEmbeddingConfig,
        )

        large_cfg = VoyageEmbeddingConfig(model_name="voyage-4-large")
        nano_cfg = SentenceTransformersEmbeddingConfig(model_name="voyageai/voyage-4-nano")

        data = {
            "embedding": [
                {
                    "config_type": "asymmetric",
                    "validate_family_compatibility": True,
                    "embed_provider": {
                        "provider": "voyage",
                        "model_name": "voyage-4-large",
                        "embedding_config": large_cfg.model_dump(),
                    },
                    "query_provider": {
                        "provider": "sentence-transformers",
                        "model_name": "voyageai/voyage-4-nano",
                        "embedding_config": nano_cfg.model_dump(),
                    },
                }
            ],
            "vector_store": [{"provider": "memory"}],
        }
        settings = ProviderSettings.model_validate(data)

        assert settings is not None
        assert _get_asymmetric_config(settings) is not None
        assert settings.vector_store is not None


# ===========================================================================
# *                    Serialization Tests
# ===========================================================================


@pytest.mark.external_api
@pytest.mark.integration
@pytest.mark.qdrant
class TestConfigurationSerialization:
    """Test serialization and deserialization of loaded configurations."""

    def test_loaded_config_can_be_serialized(self):
        """Test that loaded asymmetric config can be serialized."""
        from codeweaver.providers import ProviderSettings
        from codeweaver.providers.config.sdk.embedding import VoyageEmbeddingConfig

        large_cfg = VoyageEmbeddingConfig(model_name="voyage-4-large")
        small_cfg = VoyageEmbeddingConfig(model_name="voyage-4")

        data = {
            "embedding": [
                {
                    "config_type": "asymmetric",
                    "embed_provider": {
                        "provider": "voyage",
                        "model_name": "voyage-4-large",
                        "embedding_config": large_cfg.model_dump(),
                    },
                    "query_provider": {
                        "provider": "voyage",
                        "model_name": "voyage-4",
                        "embedding_config": small_cfg.model_dump(),
                    },
                }
            ]
        }
        settings = ProviderSettings.model_validate(data)
        config = _get_asymmetric_config(settings)

        assert config is not None
        serialized = config.model_dump()
        assert "embed_provider" in serialized
        assert "query_provider" in serialized
        assert "validate_family_compatibility" in serialized

    def test_round_trip_serialization(self):
        """Test that config can be serialized and deserialized."""
        from codeweaver.providers import AsymmetricEmbeddingProviderSettings, ProviderSettings
        from codeweaver.providers.config.sdk.embedding import (
            SentenceTransformersEmbeddingConfig,
            VoyageEmbeddingConfig,
        )

        large_cfg = VoyageEmbeddingConfig(model_name="voyage-4-large")
        nano_cfg = SentenceTransformersEmbeddingConfig(model_name="voyageai/voyage-4-nano")

        data = {
            "embedding": [
                {
                    "config_type": "asymmetric",
                    "embed_provider": {
                        "provider": "voyage",
                        "model_name": "voyage-4-large",
                        "embedding_config": large_cfg.model_dump(),
                    },
                    "query_provider": {
                        "provider": "sentence-transformers",
                        "model_name": "voyageai/voyage-4-nano",
                        "embedding_config": nano_cfg.model_dump(),
                    },
                }
            ]
        }
        settings = ProviderSettings.model_validate(data)
        original_config = _get_asymmetric_config(settings)

        assert original_config is not None
        serialized = original_config.model_dump()
        restored = AsymmetricEmbeddingProviderSettings.model_validate(serialized)

        assert str(restored.embed_provider.model_name) == str(
            original_config.embed_provider.model_name
        )
        assert str(restored.query_provider.model_name) == str(
            original_config.query_provider.model_name
        )
        assert (
            restored.validate_family_compatibility == original_config.validate_family_compatibility
        )
