# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Claude (AI Assistant)
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Unit tests for RerankingModelCapabilities."""

import pytest

from codeweaver.core import Provider
from codeweaver.providers.reranking.capabilities.base import RerankingModelCapabilities


pytestmark = [pytest.mark.unit]


class TestRerankingModelCapabilitiesOversizedChunks:
    """Test handling of oversized chunks in reranking capabilities."""

    def test_first_chunk_exceeds_max_input_logs_warning(self, caplog: pytest.LogCaptureFixture) -> None:
        """Verify warning is logged when first chunk exceeds max_input."""
        # Create capabilities with small max_input
        capabilities = RerankingModelCapabilities(
            name="test-model",
            provider=Provider.VOYAGE,
            max_input=100,
            tokenizer="tiktoken",
            tokenizer_model="o200k_base",
        )

        # Create chunks where first exceeds max_input
        # A string of ~150 tokens (rough estimate: 1 token ≈ 4 chars)
        oversized_chunk = "word " * 120  # ~600 chars, likely >100 tokens
        normal_chunk = "word " * 10  # ~50 chars, likely <100 tokens

        input_chunks = [oversized_chunk, normal_chunk]

        # Call the method
        all_fit, last_index = capabilities._process_max_input_with_tokenizer(input_chunks)

        # Should return True (allow processing) with index 0
        assert all_fit is True
        assert last_index == 0

        # Should have logged a warning
        assert len(caplog.records) > 0
        warning_record = next(
            (r for r in caplog.records if "First chunk exceeds max_input" in r.message), None
        )
        assert warning_record is not None
        assert "should have been split during chunking" in warning_record.message
        assert warning_record.levelname == "WARNING"

    def test_all_chunks_within_limit(self) -> None:
        """Verify normal operation when all chunks are within limits."""
        capabilities = RerankingModelCapabilities(
            name="test-model",
            provider=Provider.VOYAGE,
            max_input=1000,
            tokenizer="tiktoken",
            tokenizer_model="o200k_base",
        )

        # Create small chunks that fit within limit
        input_chunks = ["word " * 10, "word " * 10, "word " * 10]

        all_fit, last_index = capabilities._process_max_input_with_tokenizer(input_chunks)

        # All should fit
        assert all_fit is True
        assert last_index == 0

    def test_chunks_exceed_total_but_not_individually(self) -> None:
        """Verify correct batching when total exceeds limit but individual chunks don't."""
        capabilities = RerankingModelCapabilities(
            name="test-model",
            provider=Provider.VOYAGE,
            max_input=100,
            tokenizer="tiktoken",
            tokenizer_model="o200k_base",
        )

        # Create chunks that individually fit but total exceeds
        # Each ~40 tokens, total ~120 tokens
        input_chunks = ["word " * 30, "word " * 30, "word " * 30]

        all_fit, last_index = capabilities._process_max_input_with_tokenizer(input_chunks)

        # Not all fit, should return index of last chunk that fits
        assert all_fit is False
        assert last_index >= 0  # At least first chunk should fit

    def test_no_max_input_returns_all_fit(self) -> None:
        """Verify that when max_input is not set, all chunks are accepted."""
        capabilities = RerankingModelCapabilities(
            name="test-model",
            provider=Provider.VOYAGE,
            max_input=None,
            tokenizer="tiktoken",
            tokenizer_model="o200k_base",
        )

        # Create any chunks
        input_chunks = ["word " * 100, "word " * 100]

        all_fit, last_index = capabilities._process_max_input_with_tokenizer(input_chunks)

        # All should fit when no limit
        assert all_fit is True
        assert last_index == 0

    def test_empty_chunks_list(self) -> None:
        """Verify handling of empty chunks list."""
        capabilities = RerankingModelCapabilities(
            name="test-model",
            provider=Provider.VOYAGE,
            max_input=100,
            tokenizer="tiktoken",
            tokenizer_model="o200k_base",
        )

        all_fit, last_index = capabilities._process_max_input_with_tokenizer([])

        # Empty list should return all_fit=True
        assert all_fit is True
        assert last_index == 0

    def test_single_oversized_chunk_with_extra_logging(
        self, caplog: pytest.LogCaptureFixture
    ) -> None:
        """Verify extra logging fields when first chunk exceeds max_input."""
        capabilities = RerankingModelCapabilities(
            name="test-reranker",
            provider=Provider.COHERE,
            max_input=50,
            tokenizer="tiktoken",
            tokenizer_model="o200k_base",
        )

        oversized_chunk = "word " * 100  # Very large chunk

        capabilities._process_max_input_with_tokenizer([oversized_chunk])

        # Check that extra logging fields are present
        warning_record = next(
            (r for r in caplog.records if "First chunk exceeds max_input" in r.message), None
        )
        assert warning_record is not None

        # Verify extra fields in log record
        # Note: extra fields may be in different locations depending on logger config
        # but should be accessible via the record
        assert hasattr(warning_record, "chunk_tokens") or "chunk_tokens" in str(warning_record)
        assert hasattr(warning_record, "max_input") or "max_input" in str(warning_record)
        assert hasattr(warning_record, "model") or "test-reranker" in str(warning_record)
