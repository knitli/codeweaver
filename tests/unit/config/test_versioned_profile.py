# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Unit tests for VersionedProfile."""

from __future__ import annotations

import pytest

from codeweaver._version import __version__
from codeweaver.providers.config.categories import EmbeddingProviderSettings
from codeweaver.providers.config.profiles import VersionedProfile
from codeweaver.providers.config.sdk import VoyageEmbeddingConfig


@pytest.mark.unit
class TestVersionedProfile:
    """Test suite for VersionedProfile dataclass."""

    @pytest.fixture
    def sample_embedding_config(self) -> EmbeddingProviderSettings:
        """Create a sample embedding configuration."""
        from codeweaver.core import ModelName, Provider

        return EmbeddingProviderSettings(
            model_name=ModelName("voyage-4-large"),
            provider=Provider.VOYAGE,
            embedding_config=VoyageEmbeddingConfig(model_name=ModelName("voyage-4-large")),
        )

    @pytest.fixture
    def sample_profile(
        self, sample_embedding_config: EmbeddingProviderSettings
    ) -> VersionedProfile:
        """Create a sample versioned profile."""
        return VersionedProfile(
            name="test_profile",
            version="0.1.0",
            embedding_config=sample_embedding_config,
            changelog=["v0.1.0: Initial release", "v0.0.1: Beta version"],
        )

    def test_initialization(self, sample_profile: VersionedProfile) -> None:
        """Test that VersionedProfile initializes correctly."""
        assert sample_profile.name == "test_profile"
        assert sample_profile.version == "0.1.0"
        assert sample_profile.embedding_config is not None
        assert len(sample_profile.changelog) == 2
        assert isinstance(sample_profile.changelog, tuple)

    def test_initialization_with_list_changelog(
        self, sample_embedding_config: EmbeddingProviderSettings
    ) -> None:
        """Test initialization with list changelog converts to tuple."""
        profile = VersionedProfile(
            name="test",
            version="0.1.0",
            embedding_config=sample_embedding_config,
            changelog=["entry1", "entry2"],
        )
        assert isinstance(profile.changelog, tuple)
        assert profile.changelog == ("entry1", "entry2")

    def test_is_compatible_with_same_major_version(self) -> None:
        """Test compatibility check with same major version."""
        assert VersionedProfile.is_compatible_with("0.1.0", "0.2.5")
        assert VersionedProfile.is_compatible_with("1.0.0", "1.5.3")
        assert VersionedProfile.is_compatible_with("2.1.0", "2.0.0")

    def test_is_compatible_with_different_major_version(self) -> None:
        """Test incompatibility with different major versions."""
        assert not VersionedProfile.is_compatible_with("0.1.0", "1.0.0")
        assert not VersionedProfile.is_compatible_with("1.5.0", "2.0.0")
        assert not VersionedProfile.is_compatible_with("2.0.0", "0.9.0")

    def test_is_compatible_with_prerelease(self) -> None:
        """Test compatibility with pre-release versions."""
        assert VersionedProfile.is_compatible_with("0.1.0a6", "0.1.0")
        assert VersionedProfile.is_compatible_with("0.1.0", "0.1.0a6")
        assert VersionedProfile.is_compatible_with("0.1.0rc1", "0.2.0")

    def test_is_compatible_with_dev_versions(self) -> None:
        """Test compatibility with development versions."""
        assert VersionedProfile.is_compatible_with("0.1.0.dev1", "0.2.0")
        assert VersionedProfile.is_compatible_with("0.1.0", "0.1.0.dev152+g358bbdf4")

    def test_is_compatible_with_invalid_versions(self) -> None:
        """Test that invalid version strings return False."""
        assert not VersionedProfile.is_compatible_with("invalid", "0.1.0")
        assert not VersionedProfile.is_compatible_with("0.1.0", "invalid")
        assert not VersionedProfile.is_compatible_with("invalid", "invalid")

    def test_get_changelog_for_newer_version(self, sample_profile: VersionedProfile) -> None:
        """Test getting changelog when upgrading to newer version."""
        entries = sample_profile.get_changelog_for_version("0.2.0")
        assert len(entries) == 2
        assert entries == list(sample_profile.changelog)

    def test_get_changelog_for_same_version(self, sample_profile: VersionedProfile) -> None:
        """Test getting changelog for same version returns empty."""
        entries = sample_profile.get_changelog_for_version("0.1.0")
        assert entries == []

    def test_get_changelog_for_older_version(self, sample_profile: VersionedProfile) -> None:
        """Test getting changelog for older version returns empty."""
        entries = sample_profile.get_changelog_for_version("0.0.5")
        assert entries == []

    def test_get_changelog_for_invalid_version(self, sample_profile: VersionedProfile) -> None:
        """Test that invalid version returns all entries to be safe."""
        entries = sample_profile.get_changelog_for_version("invalid")
        assert len(entries) == 2

    def test_validate_against_collection_matching_profile(
        self, sample_profile: VersionedProfile
    ) -> None:
        """Test validation succeeds with matching profile name and compatible version."""
        is_valid, error = sample_profile.validate_against_collection("test_profile", "0.1.5")
        assert is_valid
        assert error is None

    def test_validate_against_collection_no_metadata(
        self, sample_profile: VersionedProfile
    ) -> None:
        """Test validation succeeds with no collection metadata (backward compatibility)."""
        is_valid, error = sample_profile.validate_against_collection(None, None)
        assert is_valid
        assert error is None

        is_valid, error = sample_profile.validate_against_collection("test_profile", None)
        assert is_valid
        assert error is None

    def test_validate_against_collection_name_mismatch(
        self, sample_profile: VersionedProfile
    ) -> None:
        """Test validation fails with different profile name."""
        is_valid, error = sample_profile.validate_against_collection("other_profile", "0.1.0")
        assert not is_valid
        assert error is not None
        assert "Profile name mismatch" in error
        assert "other_profile" in error
        assert "test_profile" in error

    def test_validate_against_collection_version_incompatible(
        self, sample_profile: VersionedProfile
    ) -> None:
        """Test validation fails with incompatible major version."""
        is_valid, error = sample_profile.validate_against_collection("test_profile", "1.0.0")
        assert not is_valid
        assert error is not None
        assert "Incompatible versions" in error
        assert "1.0.0" in error

    def test_telemetry_keys(self, sample_profile: VersionedProfile) -> None:
        """Test that telemetry keys returns None."""
        assert sample_profile._telemetry_keys() is None

    def test_frozen_dataclass(
        self, sample_profile: VersionedProfile, sample_embedding_config: EmbeddingProviderSettings
    ) -> None:
        """Test that VersionedProfile is immutable."""
        with pytest.raises(AttributeError):
            sample_profile.name = "new_name"

        with pytest.raises(AttributeError):
            sample_profile.version = "1.0.0"

    def test_serialization(self, sample_profile: VersionedProfile) -> None:
        """Test that VersionedProfile can be serialized via DataclassSerializationMixin."""
        # Test dump_python
        data = sample_profile.dump_python()
        assert data["name"] == "test_profile"
        assert data["version"] == "0.1.0"
        assert "embedding_config" in data
        assert "changelog" in data

        # Test dump_json
        json_bytes = sample_profile.dump_json()
        assert isinstance(json_bytes, bytes)
        assert b"test_profile" in json_bytes

    def test_deserialization(
        self, sample_profile: VersionedProfile, sample_embedding_config: EmbeddingProviderSettings
    ) -> None:
        """Test that VersionedProfile can be deserialized."""
        # Serialize
        data = sample_profile.dump_python()

        # Deserialize
        restored = VersionedProfile.validate_python(data)
        assert restored.name == sample_profile.name
        assert restored.version == sample_profile.version
        assert len(restored.changelog) == len(sample_profile.changelog)

    def test_integration_with_current_version(
        self, sample_embedding_config: EmbeddingProviderSettings
    ) -> None:
        """Test creating a profile with current CodeWeaver version."""
        profile = VersionedProfile(
            name="current",
            version=__version__,
            embedding_config=sample_embedding_config,
            changelog=["Current version"],
        )
        assert profile.version == __version__
        # Should be compatible with itself
        assert VersionedProfile.is_compatible_with(__version__, __version__)


@pytest.mark.unit
class TestVersionedProfileIntegrationWithCollectionMetadata:
    """Test integration between VersionedProfile and CollectionMetadata."""

    @pytest.fixture
    def sample_profile(self) -> VersionedProfile:
        """Create a sample versioned profile."""
        from codeweaver.core import ModelName, Provider
        from codeweaver.providers.config.categories import EmbeddingProviderSettings
        from codeweaver.providers.config.sdk import VoyageEmbeddingConfig

        return VersionedProfile(
            name="recommended",
            version="0.1.0",
            embedding_config=EmbeddingProviderSettings(
                model_name=ModelName("voyage-4-large"),
                provider=Provider.VOYAGE,
                embedding_config=VoyageEmbeddingConfig(model_name=ModelName("voyage-4-large")),
            ),
            changelog=["v0.1.0: Initial recommended profile"],
        )

    @pytest.fixture
    def collection_metadata(self) -> dict:
        """Create sample collection metadata."""
        from datetime import UTC, datetime

        return {
            "provider": "voyage",
            "created_at": datetime.now(UTC),
            "project_name": "test_project",
            "dense_model": "voyage-4-large",
            "profile_name": "recommended",
            "profile_version": "0.1.0",
            "version": "1.4.0",
        }

    def test_profile_validation_against_collection(
        self, sample_profile: VersionedProfile, collection_metadata: dict
    ) -> None:
        """Test that profile validates against compatible collection metadata."""
        is_valid, error = sample_profile.validate_against_collection(
            collection_metadata["profile_name"], collection_metadata["profile_version"]
        )
        assert is_valid
        assert error is None

    def test_profile_validation_detects_incompatible_version(
        self, sample_profile: VersionedProfile
    ) -> None:
        """Test that profile detects incompatible collection version."""
        is_valid, error = sample_profile.validate_against_collection("recommended", "1.0.0")
        assert not is_valid
        assert "Incompatible versions" in str(error)

    def test_profile_validation_detects_name_mismatch(
        self, sample_profile: VersionedProfile
    ) -> None:
        """Test that profile detects profile name mismatch."""
        is_valid, error = sample_profile.validate_against_collection("quickstart", "0.1.0")
        assert not is_valid
        assert "Profile name mismatch" in str(error)
