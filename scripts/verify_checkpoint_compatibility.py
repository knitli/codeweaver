#!/usr/bin/env python3
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Verification script for checkpoint compatibility logic.

This script demonstrates the unified checkpoint compatibility interface
without requiring the full codeweaver import chain.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Literal


class ChangeImpact(Enum):
    """Classification of configuration change impact."""

    NONE = "none"
    COMPATIBLE = "compatible"
    QUANTIZABLE = "quantizable"
    TRANSFORMABLE = "transformable"
    BREAKING = "breaking"


@dataclass(frozen=True)
class CheckpointSettingsFingerprint:
    """Family-aware configuration fingerprint."""

    embedding_config_type: Literal["symmetric", "asymmetric"]
    embed_model: str
    embed_model_family: str | None
    query_model: str | None
    sparse_model: str | None
    vector_store: str
    config_hash: str

    def is_compatible_with(
        self, other: CheckpointSettingsFingerprint
    ) -> tuple[bool, ChangeImpact]:
        """Check compatibility and classify change impact."""
        # Check vector store changes
        if self.vector_store != other.vector_store:
            return False, ChangeImpact.BREAKING

        # Check sparse model changes
        if self.sparse_model != other.sparse_model:
            return False, ChangeImpact.BREAKING

        # Handle asymmetric embedding configuration
        if self.embedding_config_type == "asymmetric":
            if (
                self.embed_model_family
                and other.embed_model_family
                and self.embed_model_family == other.embed_model_family
            ):
                if self.embed_model == other.embed_model:
                    if self.query_model != other.query_model:
                        return True, ChangeImpact.COMPATIBLE
                    return True, ChangeImpact.NONE
                else:
                    return False, ChangeImpact.BREAKING
            return False, ChangeImpact.BREAKING

        # Symmetric mode
        if self.embed_model != other.embed_model:
            return False, ChangeImpact.BREAKING

        return True, ChangeImpact.NONE


def verify_scenarios():
    """Verify key compatibility scenarios."""
    print("=" * 70)
    print("Checkpoint Compatibility Verification")
    print("=" * 70)

    # Scenario 1: Asymmetric query model change (COMPATIBLE)
    print("\n✅ Scenario 1: Asymmetric query model change within family")
    old = CheckpointSettingsFingerprint(
        embedding_config_type="asymmetric",
        embed_model="voyage-3",
        embed_model_family="voyage-3",
        query_model="voyage-3",
        sparse_model=None,
        vector_store="qdrant",
        config_hash="abc123",
    )
    new = CheckpointSettingsFingerprint(
        embedding_config_type="asymmetric",
        embed_model="voyage-3",
        embed_model_family="voyage-3",
        query_model="voyage-3-lite",
        sparse_model=None,
        vector_store="qdrant",
        config_hash="def456",
    )
    is_compatible, impact = new.is_compatible_with(old)
    print(f"   Old: {old.embed_model} / {old.query_model}")
    print(f"   New: {new.embed_model} / {new.query_model}")
    print(f"   Result: {impact.value.upper()} (compatible={is_compatible})")
    assert is_compatible and impact == ChangeImpact.COMPATIBLE, "Failed!"

    # Scenario 2: Model family change (BREAKING)
    print("\n❌ Scenario 2: Model family change")
    old = CheckpointSettingsFingerprint(
        embedding_config_type="asymmetric",
        embed_model="voyage-2",
        embed_model_family="voyage-2",
        query_model="voyage-2",
        sparse_model=None,
        vector_store="qdrant",
        config_hash="abc123",
    )
    new = CheckpointSettingsFingerprint(
        embedding_config_type="asymmetric",
        embed_model="voyage-3",
        embed_model_family="voyage-3",
        query_model="voyage-3",
        sparse_model=None,
        vector_store="qdrant",
        config_hash="def456",
    )
    is_compatible, impact = new.is_compatible_with(old)
    print(f"   Old: {old.embed_model_family}")
    print(f"   New: {new.embed_model_family}")
    print(f"   Result: {impact.value.upper()} (compatible={is_compatible})")
    assert not is_compatible and impact == ChangeImpact.BREAKING, "Failed!"

    # Scenario 3: Symmetric model change (BREAKING)
    print("\n❌ Scenario 3: Symmetric embed model change")
    old = CheckpointSettingsFingerprint(
        embedding_config_type="symmetric",
        embed_model="voyage-2",
        embed_model_family="voyage-2",
        query_model=None,
        sparse_model=None,
        vector_store="qdrant",
        config_hash="abc123",
    )
    new = CheckpointSettingsFingerprint(
        embedding_config_type="symmetric",
        embed_model="voyage-3",
        embed_model_family="voyage-3",
        query_model=None,
        sparse_model=None,
        vector_store="qdrant",
        config_hash="def456",
    )
    is_compatible, impact = new.is_compatible_with(old)
    print(f"   Old: {old.embed_model}")
    print(f"   New: {new.embed_model}")
    print(f"   Result: {impact.value.upper()} (compatible={is_compatible})")
    assert not is_compatible and impact == ChangeImpact.BREAKING, "Failed!"

    # Scenario 4: Sparse model change (BREAKING)
    print("\n❌ Scenario 4: Sparse model change")
    old = CheckpointSettingsFingerprint(
        embedding_config_type="symmetric",
        embed_model="voyage-3",
        embed_model_family="voyage-3",
        query_model=None,
        sparse_model=None,
        vector_store="qdrant",
        config_hash="abc123",
    )
    new = CheckpointSettingsFingerprint(
        embedding_config_type="symmetric",
        embed_model="voyage-3",
        embed_model_family="voyage-3",
        query_model=None,
        sparse_model="bm25",
        vector_store="qdrant",
        config_hash="def456",
    )
    is_compatible, impact = new.is_compatible_with(old)
    print(f"   Old sparse: {old.sparse_model}")
    print(f"   New sparse: {new.sparse_model}")
    print(f"   Result: {impact.value.upper()} (compatible={is_compatible})")
    assert not is_compatible and impact == ChangeImpact.BREAKING, "Failed!"

    # Scenario 5: No changes (NONE)
    print("\n✅ Scenario 5: No configuration changes")
    old = CheckpointSettingsFingerprint(
        embedding_config_type="symmetric",
        embed_model="voyage-3",
        embed_model_family="voyage-3",
        query_model=None,
        sparse_model=None,
        vector_store="qdrant",
        config_hash="abc123",
    )
    new = CheckpointSettingsFingerprint(
        embedding_config_type="symmetric",
        embed_model="voyage-3",
        embed_model_family="voyage-3",
        query_model=None,
        sparse_model=None,
        vector_store="qdrant",
        config_hash="abc123",
    )
    is_compatible, impact = new.is_compatible_with(old)
    print(f"   Old: {old.embed_model}")
    print(f"   New: {new.embed_model}")
    print(f"   Result: {impact.value.upper()} (compatible={is_compatible})")
    assert is_compatible and impact == ChangeImpact.NONE, "Failed!"

    # Scenario 6: Embed model change within family (BREAKING)
    print("\n❌ Scenario 6: Embed model change within same family")
    old = CheckpointSettingsFingerprint(
        embedding_config_type="asymmetric",
        embed_model="voyage-3",
        embed_model_family="voyage-3",
        query_model="voyage-3",
        sparse_model=None,
        vector_store="qdrant",
        config_hash="abc123",
    )
    new = CheckpointSettingsFingerprint(
        embedding_config_type="asymmetric",
        embed_model="voyage-3-lite",
        embed_model_family="voyage-3",
        query_model="voyage-3-lite",
        sparse_model=None,
        vector_store="qdrant",
        config_hash="def456",
    )
    is_compatible, impact = new.is_compatible_with(old)
    print(f"   Old embed: {old.embed_model}")
    print(f"   New embed: {new.embed_model}")
    print(f"   Family: {new.embed_model_family}")
    print(f"   Result: {impact.value.upper()} (compatible={is_compatible})")
    assert not is_compatible and impact == ChangeImpact.BREAKING, "Failed!"

    print("\n" + "=" * 70)
    print("✓ All scenarios verified successfully!")
    print("=" * 70)


if __name__ == "__main__":
    verify_scenarios()
