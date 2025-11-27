# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""
Tests for telemetry privacy serialization.

Tests verify that serialize_for_telemetry() correctly filters sensitive data
according to _telemetry_keys() mappings.
"""

from __future__ import annotations

import pytest

from pydantic.dataclasses import dataclass

from codeweaver.core.types import (
    DATACLASS_CONFIG,
    AnonymityConversion,
    BasedModel,
    DataclassSerializationMixin,
    FilteredKey,
    FilteredKeyT,
)


pytestmark = [pytest.mark.unit, pytest.mark.telemetry]


@pytest.mark.benchmark
@pytest.mark.performance
class TestBasedModelPrivacySerialization:
    """Test privacy serialization for BasedModel instances."""

    def test_basedmodel_filters_forbidden_keys(self) -> None:
        """Test that FORBIDDEN keys are excluded from serialized output."""

        class TestModel(BasedModel):
            public_field: str = "safe_value"
            sensitive_field: str = "secret_value"

            def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
                return {FilteredKey("sensitive_field"): AnonymityConversion.FORBIDDEN}

        model = TestModel()
        serialized = model.serialize_for_telemetry()

        assert "public_field" in serialized
        assert "sensitive_field" not in serialized
        assert serialized["public_field"] == "safe_value"

    def test_basedmodel_converts_to_boolean(self) -> None:
        """Test that BOOLEAN conversion works correctly."""

        class TestModel(BasedModel):
            has_value: str = "some_string"

            def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
                return {FilteredKey("has_value"): AnonymityConversion.BOOLEAN}

        model = TestModel()
        serialized = model.serialize_for_telemetry()

        assert "has_value" in serialized
        assert serialized["has_value"] is True
        assert isinstance(serialized["has_value"], bool)

    def test_basedmodel_counts_items(self) -> None:
        """Test that COUNT conversion returns count of items."""

        from pydantic import Field

        class TestModel(BasedModel):
            items: list[str] = Field(default_factory=lambda: ["a", "b", "c"])

            def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
                return {FilteredKey("items"): AnonymityConversion.COUNT}

        model = TestModel()
        serialized = model.serialize_for_telemetry()

        assert "items" in serialized
        assert serialized["items"] == 3

    def test_basedmodel_hashes_values(self) -> None:
        """Test that HASH conversion returns hashed value."""

        class TestModel(BasedModel):
            path: str = "/home/user/secret.py"

            def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
                return {FilteredKey("path"): AnonymityConversion.HASH}

        model = TestModel()
        serialized = model.serialize_for_telemetry()

        assert "path" in serialized
        assert isinstance(serialized["path"], int)
        assert serialized["path"] != "/home/user/secret.py"

    def test_basedmodel_distribution(self) -> None:
        """Test that DISTRIBUTION conversion returns value distribution."""

        from pydantic import Field

        class TestModel(BasedModel):
            languages: list[str] = Field(default_factory=lambda: ["python", "rust", "python", "go"])

            def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
                return {FilteredKey("languages"): AnonymityConversion.DISTRIBUTION}

        model = TestModel()
        serialized = model.serialize_for_telemetry()

        assert "languages" in serialized
        assert isinstance(serialized["languages"], dict)
        assert serialized["languages"]["python"] == 2
        assert serialized["languages"]["rust"] == 1
        assert serialized["languages"]["go"] == 1
        assert serialized["languages"]["go"] == 1

    def test_basedmodel_no_telemetry_keys(self) -> None:
        """Test that models without telemetry keys serialize normally."""

        class TestModel(BasedModel):
            field1: str = "value1"
            field2: int = 42

            def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion] | None:
                return None

        model = TestModel()
        serialized = model.serialize_for_telemetry()

        assert "field1" in serialized
        assert "field2" in serialized
        assert serialized["field1"] == "value1"
        assert serialized["field2"] == 42


@pytest.mark.benchmark
@pytest.mark.performance
class TestDataclassPrivacySerialization:
    """Test privacy serialization for DataclassSerializationMixin instances."""

    def test_dataclass_filters_forbidden_keys(self) -> None:
        """Test that FORBIDDEN keys are excluded from dataclass serialized output."""

        @dataclass(config=DATACLASS_CONFIG)
        class TestDataclass(DataclassSerializationMixin):
            public_field: str = "safe_value"
            sensitive_field: str = "secret_value"

            def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
                return {FilteredKey("sensitive_field"): AnonymityConversion.FORBIDDEN}

        instance = TestDataclass()
        serialized = instance.serialize_for_telemetry()

        assert "public_field" in serialized
        assert "sensitive_field" not in serialized
        assert serialized["public_field"] == "safe_value"

    def test_dataclass_counts_items(self) -> None:
        """Test that COUNT conversion works for dataclasses."""

        from pydantic import Field

        @dataclass(config=DATACLASS_CONFIG)
        class TestDataclass(DataclassSerializationMixin):
            items: list[str] = Field(default_factory=lambda: ["a", "b", "c"])

            def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
                return {FilteredKey("items"): AnonymityConversion.COUNT}

        instance = TestDataclass()
        serialized = instance.serialize_for_telemetry()

        assert "items" in serialized
        assert serialized["items"] == 3


@pytest.mark.benchmark
@pytest.mark.performance
class TestTelemetryHandlerOverride:
    """Test that _telemetry_handler allows custom overrides."""

    def test_telemetry_handler_override(self) -> None:
        """Test that _telemetry_handler can override serialized values."""

        class TestModel(BasedModel):
            value: int = 42

            def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion] | None:
                return None

            def _telemetry_handler(self, _serialized_self: dict) -> dict:
                return {"value": 100}  # Override with custom value

        model = TestModel()
        serialized = model.serialize_for_telemetry()

        assert "value" in serialized
        assert serialized["value"] == 100  # Should be overridden value, not original 42
