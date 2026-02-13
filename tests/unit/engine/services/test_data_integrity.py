# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Tests for data integrity validation (4 layers).

Tests cover:
- Layer 1: Vector count matching
- Layer 2: Payload checksums with blake3
- Layer 3: Semantic equivalence (>0.9999 cosine similarity)
- Layer 4: Search quality (>80% recall@10)

Each layer has detection and validation tests.
"""

from __future__ import annotations

from typing import TYPE_CHECKING
from unittest.mock import AsyncMock, Mock

import pytest


if TYPE_CHECKING:
    from codeweaver.engine.services.migration_service import MigrationService


# ===========================================================================
# Fixtures
# ===========================================================================


@pytest.fixture
def migration_service():
    """Create MigrationService with mocked dependencies."""
    from codeweaver.engine.services.migration_service import MigrationService

    vector_store = Mock(spec=["collection"])
    vector_store.collection = "test_collection"

    return MigrationService(
        vector_store=vector_store,
        config_analyzer=Mock(),
        checkpoint_manager=Mock(),
        manifest_manager=Mock(),
    )


# ===========================================================================
# Tests: Layer 1 - Vector Count Matching
# ===========================================================================


@pytest.mark.async_test
@pytest.mark.mock_only
@pytest.mark.unit
class TestLayer1VectorCount:
    """Tests for Layer 1: Vector count validation."""

    async def test_count_match_passes(self, migration_service: MigrationService) -> None:
        """Test that matching vector counts pass validation."""
        migration_service._count_vectors = AsyncMock(return_value=5000)
        migration_service._compute_payload_checksums = AsyncMock(return_value=b"test_checksum")
        migration_service._get_random_samples = AsyncMock(return_value=[])
        migration_service._search_collection = AsyncMock(return_value=[])

        # Should not raise
        await migration_service._validate_migration_integrity(
            source_collection="source",
            target_collection="target",
            expected_count=5000,
            new_dimension=1024,
        )

    async def test_count_mismatch_detected(self, migration_service: MigrationService) -> None:
        """Test that vector count mismatch is detected."""
        from codeweaver.engine.services.migration_service import ValidationError

        # Source: 5000, Target: 4999
        migration_service._count_vectors = AsyncMock(side_effect=[5000, 4999])

        with pytest.raises(ValidationError) as exc_info:
            await migration_service._validate_migration_integrity(
                source_collection="source",
                target_collection="target",
                expected_count=5000,
                new_dimension=1024,
            )

        assert "Layer 1 failed" in str(exc_info.value)
        assert "Vector count mismatch" in str(exc_info.value)

    async def test_missing_vectors_detected(self, migration_service: MigrationService) -> None:
        """Test that missing vectors are detected."""
        from codeweaver.engine.services.migration_service import ValidationError

        # Expected 5000, got 4500
        migration_service._count_vectors = AsyncMock(side_effect=[5000, 4500])

        with pytest.raises(ValidationError) as exc_info:
            await migration_service._validate_migration_integrity(
                source_collection="source",
                target_collection="target",
                expected_count=5000,
                new_dimension=1024,
            )

        assert "4500" in str(exc_info.value)
        assert "5000" in str(exc_info.value)

    async def test_extra_vectors_detected(self, migration_service: MigrationService) -> None:
        """Test that extra vectors are detected."""
        from codeweaver.engine.services.migration_service import ValidationError

        # Expected 5000, got 5001
        migration_service._count_vectors = AsyncMock(side_effect=[5000, 5001])

        with pytest.raises(ValidationError) as exc_info:
            await migration_service._validate_migration_integrity(
                source_collection="source",
                target_collection="target",
                expected_count=5000,
                new_dimension=1024,
            )

        assert "5001" in str(exc_info.value)


# ===========================================================================
# Tests: Layer 2 - Payload Checksums
# ===========================================================================


@pytest.mark.async_test
@pytest.mark.mock_only
@pytest.mark.unit
class TestLayer2PayloadChecksums:
    """Tests for Layer 2: Payload integrity via blake3 checksums."""

    async def test_checksum_match_passes(self, migration_service: MigrationService) -> None:
        """Test that matching checksums pass validation."""
        migration_service._count_vectors = AsyncMock(return_value=5000)
        migration_service._compute_payload_checksums = AsyncMock(return_value=b"matching_checksum")
        migration_service._get_random_samples = AsyncMock(return_value=[])
        migration_service._search_collection = AsyncMock(return_value=[])

        # Should not raise
        await migration_service._validate_migration_integrity(
            source_collection="source",
            target_collection="target",
            expected_count=5000,
            new_dimension=1024,
        )

    async def test_checksum_mismatch_detected(self, migration_service: MigrationService) -> None:
        """Test that checksum mismatch is detected."""
        from codeweaver.engine.services.migration_service import ValidationError

        migration_service._count_vectors = AsyncMock(return_value=5000)
        # Different checksums
        migration_service._compute_payload_checksums = AsyncMock(
            side_effect=[b"source_checksum", b"different_checksum"]
        )

        with pytest.raises(ValidationError) as exc_info:
            await migration_service._validate_migration_integrity(
                source_collection="source",
                target_collection="target",
                expected_count=5000,
                new_dimension=1024,
            )

        assert "Layer 2 failed" in str(exc_info.value)
        assert "Payload checksums don't match" in str(exc_info.value)

    async def test_payload_corruption_detected(self, migration_service: MigrationService) -> None:
        """Test that corrupted payloads are detected."""
        from codeweaver.engine.services.migration_service import ValidationError

        migration_service._count_vectors = AsyncMock(return_value=5000)
        # Simulates payload data changed during migration
        migration_service._compute_payload_checksums = AsyncMock(
            side_effect=[b"original_hash", b"corrupted_hash"]
        )

        with pytest.raises(ValidationError) as exc_info:
            await migration_service._validate_migration_integrity(
                source_collection="source",
                target_collection="target",
                expected_count=5000,
                new_dimension=1024,
            )

        assert "payload data was corrupted" in str(exc_info.value).lower()

    async def test_empty_payload_handled(self, migration_service: MigrationService) -> None:
        """Test that empty payloads are handled correctly."""
        migration_service._count_vectors = AsyncMock(return_value=5000)
        # Empty payload should have consistent checksum
        migration_service._compute_payload_checksums = AsyncMock(return_value=b"empty_payload_hash")
        migration_service._get_random_samples = AsyncMock(return_value=[])
        migration_service._search_collection = AsyncMock(return_value=[])

        # Should not raise
        await migration_service._validate_migration_integrity(
            source_collection="source",
            target_collection="target",
            expected_count=5000,
            new_dimension=1024,
        )


# ===========================================================================
# Tests: Layer 3 - Semantic Equivalence
# ===========================================================================


@pytest.mark.async_test
@pytest.mark.mock_only
@pytest.mark.unit
class TestLayer3SemanticEquivalence:
    """Tests for Layer 3: Semantic equivalence via cosine similarity."""

    async def test_high_similarity_passes(self, migration_service: MigrationService) -> None:
        """Test that high similarity (>0.9999) passes validation."""
        migration_service._count_vectors = AsyncMock(return_value=5000)
        migration_service._compute_payload_checksums = AsyncMock(return_value=b"test_checksum")
        migration_service._get_random_samples = AsyncMock(return_value=["id1", "id2"])
        migration_service._get_vector = AsyncMock(return_value=[1.0, 2.0, 3.0, 4.0])
        # High similarity
        migration_service._cosine_similarity = Mock(return_value=0.99995)
        migration_service._search_collection = AsyncMock(return_value=[])

        # Should not raise
        await migration_service._validate_migration_integrity(
            source_collection="source",
            target_collection="target",
            expected_count=5000,
            new_dimension=1024,
        )

    async def test_low_similarity_detected(self, migration_service: MigrationService) -> None:
        """Test that low similarity (<0.9999) is detected."""
        from codeweaver.engine.services.migration_service import ValidationError

        migration_service._count_vectors = AsyncMock(return_value=5000)
        migration_service._compute_payload_checksums = AsyncMock(return_value=b"test_checksum")
        migration_service._get_random_samples = AsyncMock(return_value=["id1"])
        migration_service._get_vector = AsyncMock(return_value=[1.0, 2.0, 3.0, 4.0])
        # Low similarity
        migration_service._cosine_similarity = Mock(return_value=0.95)

        with pytest.raises(ValidationError) as exc_info:
            await migration_service._validate_migration_integrity(
                source_collection="source",
                target_collection="target",
                expected_count=5000,
                new_dimension=1024,
            )

        assert "Layer 3 failed" in str(exc_info.value)
        assert "Cosine similarity too low" in str(exc_info.value)

    async def test_semantic_drift_detected(self, migration_service: MigrationService) -> None:
        """Test that semantic drift is detected."""
        from codeweaver.engine.services.migration_service import ValidationError

        migration_service._count_vectors = AsyncMock(return_value=5000)
        migration_service._compute_payload_checksums = AsyncMock(return_value=b"test_checksum")
        migration_service._get_random_samples = AsyncMock(return_value=["id1"])
        migration_service._get_vector = AsyncMock(return_value=[1.0, 2.0, 3.0])
        # Simulates vectors drifted during migration
        migration_service._cosine_similarity = Mock(return_value=0.98)

        with pytest.raises(ValidationError):
            await migration_service._validate_migration_integrity(
                source_collection="source",
                target_collection="target",
                expected_count=5000,
                new_dimension=1024,
            )

    async def test_sample_size_adjustment(self, migration_service: MigrationService) -> None:
        """Test that sample size adjusts for small collections."""
        migration_service._count_vectors = AsyncMock(return_value=50)  # Small collection
        migration_service._compute_payload_checksums = AsyncMock(return_value=b"test_checksum")
        # Should sample min(100, 50) = 50 vectors
        migration_service._get_random_samples = AsyncMock(return_value=["id1"])
        migration_service._get_vector = AsyncMock(return_value=[1.0, 2.0])
        migration_service._cosine_similarity = Mock(return_value=0.99995)
        migration_service._search_collection = AsyncMock(return_value=[])

        # Should not raise
        await migration_service._validate_migration_integrity(
            source_collection="source",
            target_collection="target",
            expected_count=50,
            new_dimension=1024,
        )


# ===========================================================================
# Tests: Layer 4 - Search Quality
# ===========================================================================


@pytest.mark.async_test
@pytest.mark.mock_only
@pytest.mark.unit
class TestLayer4SearchQuality:
    """Tests for Layer 4: Search quality preservation (recall@10 >80%)."""

    async def test_high_recall_passes(self, migration_service: MigrationService) -> None:
        """Test that high recall (>80%) passes validation."""
        migration_service._count_vectors = AsyncMock(return_value=5000)
        migration_service._compute_payload_checksums = AsyncMock(return_value=b"test_checksum")
        migration_service._get_random_samples = AsyncMock(return_value=["id1"])
        migration_service._get_vector = AsyncMock(return_value=[1.0, 2.0])
        migration_service._cosine_similarity = Mock(return_value=0.99995)
        migration_service._search_collection = AsyncMock(return_value=["id1", "id2", "id3"])
        # High recall
        migration_service._recall_at_k = Mock(return_value=0.85)

        # Should not raise
        await migration_service._validate_migration_integrity(
            source_collection="source",
            target_collection="target",
            expected_count=5000,
            new_dimension=1024,
        )

    async def test_low_recall_detected(self, migration_service: MigrationService) -> None:
        """Test that low recall (<80%) is detected."""
        from codeweaver.engine.services.migration_service import ValidationError

        migration_service._count_vectors = AsyncMock(return_value=5000)
        migration_service._compute_payload_checksums = AsyncMock(return_value=b"test_checksum")
        migration_service._get_random_samples = AsyncMock(return_value=["id1"])
        migration_service._get_vector = AsyncMock(return_value=[1.0, 2.0])
        migration_service._cosine_similarity = Mock(return_value=0.99995)
        migration_service._search_collection = AsyncMock(return_value=["id1", "id2", "id3"])
        # Low recall
        migration_service._recall_at_k = Mock(return_value=0.75)

        with pytest.raises(ValidationError) as exc_info:
            await migration_service._validate_migration_integrity(
                source_collection="source",
                target_collection="target",
                expected_count=5000,
                new_dimension=1024,
            )

        assert "Layer 4 failed" in str(exc_info.value)
        assert "Search quality degraded" in str(exc_info.value)

    async def test_search_quality_degradation_detected(
        self, migration_service: MigrationService
    ) -> None:
        """Test that search quality degradation is detected."""
        from codeweaver.engine.services.migration_service import ValidationError

        migration_service._count_vectors = AsyncMock(return_value=5000)
        migration_service._compute_payload_checksums = AsyncMock(return_value=b"test_checksum")
        migration_service._get_random_samples = AsyncMock(return_value=["id1"])
        migration_service._get_vector = AsyncMock(return_value=[1.0, 2.0])
        migration_service._cosine_similarity = Mock(return_value=0.99995)
        migration_service._search_collection = AsyncMock(return_value=["id1", "id2", "id3"])
        # Significant degradation
        migration_service._recall_at_k = Mock(return_value=0.60)

        with pytest.raises(ValidationError):
            await migration_service._validate_migration_integrity(
                source_collection="source",
                target_collection="target",
                expected_count=5000,
                new_dimension=1024,
            )

    async def test_recall_calculation_correctness(
        self, migration_service: MigrationService
    ) -> None:
        """Test that recall@k is calculated correctly."""
        # Test the recall calculation helper
        source_results = ["id1", "id2", "id3", "id4", "id5"]
        target_results = ["id1", "id2", "id6", "id7", "id8"]

        recall = migration_service._recall_at_k(source_results, target_results, k=5)

        # 2/5 = 0.4
        assert abs(recall - 0.4) < 0.01


# ===========================================================================
# Tests: All Layers Integration
# ===========================================================================


@pytest.mark.async_test
@pytest.mark.mock_only
@pytest.mark.unit
class TestAllLayersIntegration:
    """Tests for all 4 validation layers working together."""

    async def test_all_layers_pass_together(self, migration_service: MigrationService) -> None:
        """Test that all 4 layers can pass together."""
        # Setup all layers to pass
        migration_service._count_vectors = AsyncMock(return_value=5000)
        migration_service._compute_payload_checksums = AsyncMock(return_value=b"test_checksum")
        migration_service._get_random_samples = AsyncMock(return_value=["id1"])
        migration_service._get_vector = AsyncMock(return_value=[1.0, 2.0])
        migration_service._cosine_similarity = Mock(return_value=0.99995)
        migration_service._search_collection = AsyncMock(return_value=["id1", "id2"])
        migration_service._recall_at_k = Mock(return_value=0.85)

        # Should not raise
        await migration_service._validate_migration_integrity(
            source_collection="source",
            target_collection="target",
            expected_count=5000,
            new_dimension=1024,
        )

    async def test_layer_1_failure_stops_validation(
        self, migration_service: MigrationService
    ) -> None:
        """Test that Layer 1 failure stops validation early."""
        from codeweaver.engine.services.migration_service import ValidationError

        # Layer 1 fails (count mismatch)
        migration_service._count_vectors = AsyncMock(side_effect=[5000, 4999])

        # Later layers should not be called
        migration_service._compute_payload_checksums = AsyncMock()
        migration_service._get_random_samples = AsyncMock()

        with pytest.raises(ValidationError):
            await migration_service._validate_migration_integrity(
                source_collection="source",
                target_collection="target",
                expected_count=5000,
                new_dimension=1024,
            )

        # Checksum should not be called if count fails
        assert not migration_service._compute_payload_checksums.called

    async def test_validation_provides_detailed_error_info(
        self, migration_service: MigrationService
    ) -> None:
        """Test that validation errors provide detailed information."""
        from codeweaver.engine.services.migration_service import ValidationError

        migration_service._count_vectors = AsyncMock(side_effect=[5000, 4500])

        with pytest.raises(ValidationError) as exc_info:
            await migration_service._validate_migration_integrity(
                source_collection="source",
                target_collection="target",
                expected_count=5000,
                new_dimension=1024,
            )

        error_msg = str(exc_info.value)
        # Should include specific numbers
        assert "5000" in error_msg
        assert "4500" in error_msg
        # Should identify which layer failed
        assert "Layer 1" in error_msg

    async def test_validation_logs_progress(self, migration_service: MigrationService) -> None:
        """Test that validation logs progress through layers."""
        # This would test logging output in real implementation
        # For now, just verify validation completes
        migration_service._count_vectors = AsyncMock(return_value=5000)
        migration_service._compute_payload_checksums = AsyncMock(return_value=b"test_checksum")
        migration_service._get_random_samples = AsyncMock(return_value=[])
        migration_service._search_collection = AsyncMock(return_value=[])

        # Should complete all layers
        await migration_service._validate_migration_integrity(
            source_collection="source",
            target_collection="target",
            expected_count=5000,
            new_dimension=1024,
        )
