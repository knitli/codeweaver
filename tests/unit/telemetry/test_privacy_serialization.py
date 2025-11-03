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

from codeweaver.common.telemetry.events import (
    PerformanceBenchmarkEvent,
    SemanticValidationEvent,
    SessionSummaryEvent,
)
from codeweaver.core.types import (
    DATACLASS_CONFIG,
    AnonymityConversion,
    BasedModel,
    DataclassSerializationMixin,
    FilteredKey,
    FilteredKeyT,
)


pytestmark = [pytest.mark.unit, pytest.mark.telemetry]


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


class TestTelemetryEventsSerialization:
    """Test that telemetry events properly serialize."""

    def test_session_summary_event_serializes(self) -> None:
        """Test that SessionSummaryEvent serializes correctly."""
        event = SessionSummaryEvent(
            session_duration_minutes=5.5,
            total_searches=10,
            successful_searches=9,
            failed_searches=1,
            success_rate=0.9,
            avg_response_ms=1250.0,
            median_response_ms=1100.0,
            p95_response_ms=2000.0,
            total_tokens_generated=50000,
            total_tokens_delivered=15000,
            total_tokens_saved=35000,
            context_reduction_pct=70.0,
            estimated_cost_savings_usd=0.189,
            languages={"python": 6, "typescript": 2},
            semantic_frequencies={"definition_callable": 0.25},
        )

        serialized = event.serialize_for_telemetry()

        # Verify all fields are present
        assert "session_duration_minutes" in serialized
        assert serialized["session_duration_minutes"] == 5.5
        assert "total_searches" in serialized
        assert serialized["total_searches"] == 10

    def test_performance_benchmark_event_serializes(self) -> None:
        """Test that PerformanceBenchmarkEvent serializes correctly."""
        event = PerformanceBenchmarkEvent(
            comparison_type="naive_vs_codeweaver",
            baseline_approach="grep_full_files",
            baseline_estimated_files=50,
            baseline_estimated_lines=10000,
            baseline_estimated_tokens=40000,
            baseline_estimated_cost_usd=0.216,
            codeweaver_files_returned=5,
            codeweaver_lines_returned=500,
            codeweaver_tokens_delivered=2000,
            codeweaver_actual_cost_usd=0.0108,
            files_reduction_pct=90.0,
            lines_reduction_pct=95.0,
            tokens_reduction_pct=95.0,
            cost_savings_pct=95.0,
        )

        serialized = event.serialize_for_telemetry()

        # Verify all fields are present
        assert "comparison_type" in serialized
        assert serialized["comparison_type"] == "naive_vs_codeweaver"
        assert "baseline_approach" in serialized
        assert serialized["baseline_approach"] == "grep_full_files"

    def test_semantic_validation_event_serializes(self) -> None:
        """Test that SemanticValidationEvent serializes correctly."""
        event = SemanticValidationEvent(
            period="daily",
            total_chunks_analyzed=1000,
            category_usage={"definition_callable": 250, "definition_class": 150},
            usage_frequencies={"definition_callable": 0.25, "definition_class": 0.15},
            correlation=0.85,
            note="Strong correlation observed",
        )

        serialized = event.serialize_for_telemetry()

        # Verify all fields are present
        assert "period" in serialized
        assert serialized["period"] == "daily"
        assert "total_chunks_analyzed" in serialized
        assert serialized["total_chunks_analyzed"] == 1000

    def test_event_to_posthog_format(self) -> None:
        """Test that events convert to PostHog format correctly."""
        event = SessionSummaryEvent(
            session_duration_minutes=5.5,
            total_searches=10,
            successful_searches=9,
            failed_searches=1,
            success_rate=0.9,
            avg_response_ms=1250.0,
            median_response_ms=1100.0,
            p95_response_ms=2000.0,
            total_tokens_generated=50000,
            total_tokens_delivered=15000,
            total_tokens_saved=35000,
            context_reduction_pct=70.0,
            estimated_cost_savings_usd=0.189,
            languages={"python": 6, "typescript": 2},
            semantic_frequencies={"definition_callable": 0.25},
        )

        event_name, properties = event.to_posthog_event()

        assert event_name == "codeweaver_session_summary"
        assert isinstance(properties, dict)
        assert "total_searches" in properties
        assert properties["total_searches"] == 10
        assert "timing" in properties
        assert "tokens" in properties


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
