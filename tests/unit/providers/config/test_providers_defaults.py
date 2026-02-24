# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Unit tests for provider default detection and model name correctness."""

from __future__ import annotations

from codeweaver.core.constants import (
    RECOMMENDED_CLOUD_CONTEXT_AGENT_MODEL,
    RECOMMENDED_CLOUD_CONTEXT_AGENT_MODEL_BARE,
)


def test_bare_agent_model_constant_is_suffix_of_full():
    """Bare model name must match the part after ':' in the full constant."""
    provider_prefix, bare = RECOMMENDED_CLOUD_CONTEXT_AGENT_MODEL.split(":", 1)
    assert bare == RECOMMENDED_CLOUD_CONTEXT_AGENT_MODEL_BARE
    assert provider_prefix == "anthropic"


def test_bare_agent_model_constant_has_no_prefix():
    """Bare model name must not contain ':'."""
    assert ":" not in RECOMMENDED_CLOUD_CONTEXT_AGENT_MODEL_BARE


# ---------------------------------------------------------------------------
# Task 2: reranking defaults tests
# ---------------------------------------------------------------------------
from unittest.mock import patch

from codeweaver.core.constants import (
    RECOMMENDED_CLOUD_RERANKING_MODEL,
    RECOMMENDED_LOCAL_RERANKING_MODEL,
)
from codeweaver.core.types import Provider


def _reranking_defaults_with_mocked_packages(
    available_packages: set[str], voyage_has_auth: bool = False
):
    """Helper: call _get_default_reranking_settings with controlled environment."""
    from codeweaver.providers.config import providers as pmod

    def mock_has_package(name: str):
        return name if name in available_packages else None

    with (
        patch.object(pmod, "has_package", side_effect=mock_has_package),
        patch.object(Provider.VOYAGE, "has_env_auth", new=voyage_has_auth),
    ):
        return pmod._get_default_reranking_settings()


def test_reranking_default_voyage_requires_auth():
    """Voyage reranking must not be selected when voyageai is present but no API key."""
    result = _reranking_defaults_with_mocked_packages({"voyageai"}, voyage_has_auth=False)
    assert result.provider != Provider.VOYAGE
    assert result.enabled is False


def test_reranking_default_voyage_with_auth():
    """Voyage reranking selected when voyageai present and API key configured."""
    result = _reranking_defaults_with_mocked_packages({"voyageai"}, voyage_has_auth=True)
    assert result.provider == Provider.VOYAGE
    assert str(result.model) == RECOMMENDED_CLOUD_RERANKING_MODEL
    assert ":" not in str(result.model)


def test_reranking_default_fastembed_no_colon_prefix():
    """FastEmbed reranking model must not have a colon prefix."""
    result = _reranking_defaults_with_mocked_packages({"fastembed"})
    assert result.provider == Provider.FASTEMBED
    assert ":" not in str(result.model)
    assert str(result.model) == RECOMMENDED_LOCAL_RERANKING_MODEL


def test_reranking_default_fastembed_gpu_detected():
    """fastembed_gpu (underscore) package must be detected correctly."""
    result = _reranking_defaults_with_mocked_packages({"fastembed_gpu"})
    assert result.provider == Provider.FASTEMBED
    assert result.enabled is True


def test_reranking_default_sentence_transformers_detected():
    """sentence_transformers (underscore) package must be detected correctly."""
    result = _reranking_defaults_with_mocked_packages({"sentence_transformers"})
    assert result.provider == Provider.SENTENCE_TRANSFORMERS
    assert result.enabled is True
    assert ":" not in str(result.model)
    assert str(result.model) == RECOMMENDED_LOCAL_RERANKING_MODEL
