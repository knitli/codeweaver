# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""
Critical privacy tests for serialize_for_telemetry.

These tests validate that BasedModel and DataclassSerializationMixin correctly
filter PII and sensitive information from telemetry events using the
_telemetry_keys configuration.

IMPORTANT: These tests are CRITICAL for privacy compliance.
All tests must pass before deploying telemetry to production.
"""

from __future__ import annotations

from typing import Any, override

import pytest

from codeweaver.core import AnonymityConversion, BasedModel, FilteredKey, FilteredKeyT


class MockSensitiveModel(BasedModel):
    """A mock model with various sensitive fields."""

    public_id: str
    user_email: str
    secret_key: str
    project_path: str
    tags: list[str]
    description: str
    meta: dict[str, int]

    @override
    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion] | None:
        return {
            FilteredKey("user_email"): AnonymityConversion.FORBIDDEN,
            FilteredKey("secret_key"): AnonymityConversion.FORBIDDEN,
            FilteredKey("project_path"): AnonymityConversion.HASH,
            FilteredKey("tags"): AnonymityConversion.COUNT,
            FilteredKey("description"): AnonymityConversion.TEXT_COUNT,
            FilteredKey("meta"): AnonymityConversion.BOOLEAN,
        }


class MockOverrideModel(BasedModel):
    """A mock model that overrides the telemetry handler."""

    data: str
    special_value: str

    @override
    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion] | None:
        return {FilteredKey("data"): AnonymityConversion.HASH}

    @override
    def _telemetry_handler(self, serialized_self: dict[str, Any], /) -> dict[str, Any]:
        """Override specific fields."""
        return {"special_value": "REDACTED", "extra_field": "injected"}


@pytest.mark.unit
class TestTelemetryPrivacy:
    """Test suite for telemetry privacy serialization."""

    def test_forbidden_fields_are_removed(self):
        """CRITICAL: Ensure FORBIDDEN fields are completely removed."""
        model = MockSensitiveModel(
            public_id="pub-123",
            user_email="user@example.com",
            secret_key="sk-12345",
            project_path="/home/user/project",
            tags=["a", "b"],
            description="A long description",
            meta={"a": 1},
        )

        serialized = model.serialize_for_telemetry()

        assert "public_id" in serialized
        assert serialized["public_id"] == "pub-123"
        assert "user_email" not in serialized, "Email should be removed"
        assert "secret_key" not in serialized, "Secret key should be removed"

    def test_hash_conversion(self):
        """CRITICAL: Ensure HASH conversion works."""
        model = MockSensitiveModel(
            public_id="pub-123",
            user_email="u",
            secret_key="s",
            project_path="/home/user/project",
            tags=[],
            description="",
            meta={},
        )

        serialized = model.serialize_for_telemetry()

        assert "project_path" in serialized
        # Should be an integer (hash)
        assert isinstance(serialized["project_path"], int)
        # Should be consistent
        assert serialized["project_path"] == model.serialize_for_telemetry()["project_path"]

        # Verify different inputs give different hashes
        model2 = model.model_copy(update={"project_path": "/other/path"})
        assert serialized["project_path"] != model2.serialize_for_telemetry()["project_path"]

    def test_count_conversion(self):
        """Ensure COUNT conversion works."""
        model = MockSensitiveModel(
            public_id="pub",
            user_email="u",
            secret_key="s",
            project_path="p",
            tags=["tag1", "tag2", "tag3"],
            description="",
            meta={},
        )

        serialized = model.serialize_for_telemetry()
        assert serialized["tags"] == 3

    def test_text_count_conversion(self):
        """Ensure TEXT_COUNT conversion works."""
        desc = "Hello World"
        model = MockSensitiveModel(
            public_id="pub",
            user_email="u",
            secret_key="s",
            project_path="p",
            tags=[],
            description=desc,
            meta={},
        )

        serialized = model.serialize_for_telemetry()
        assert serialized["description"] == len(desc)

    def test_boolean_conversion(self):
        """Ensure BOOLEAN conversion works."""
        model_true = MockSensitiveModel(
            public_id="pub",
            user_email="u",
            secret_key="s",
            project_path="p",
            tags=[],
            description="",
            meta={"key": 1},
        )
        assert model_true.serialize_for_telemetry()["meta"] is True

        model_false = MockSensitiveModel(
            public_id="pub",
            user_email="u",
            secret_key="s",
            project_path="p",
            tags=[],
            description="",
            meta={},
        )
        assert model_false.serialize_for_telemetry()["meta"] is False

    def test_telemetry_handler_override(self):
        """Ensure _telemetry_handler can override values."""
        model = MockOverrideModel(data="sensitive", special_value="secret")

        serialized = model.serialize_for_telemetry()

        # Normal conversion from _telemetry_keys
        assert isinstance(serialized["data"], int)

        # Override from handler
        assert serialized["special_value"] == "REDACTED"

    def test_default_safe_fields(self):
        """Ensure fields not in _telemetry_keys are passed through."""
        model = MockSensitiveModel(
            public_id="safe-value",
            user_email="u",
            secret_key="s",
            project_path="p",
            tags=[],
            description="",
            meta={},
        )

        serialized = model.serialize_for_telemetry()
        assert serialized["public_id"] == "safe-value"


# Mark as telemetry test
pytestmark = pytest.mark.telemetry
