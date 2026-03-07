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


# ---------------------------------------------------------------------------
# Task 3: agent defaults auth check tests
# ---------------------------------------------------------------------------


def _agent_defaults_with_mocked_env(has_anthropic: bool, has_auth: bool):
    """Helper: test agent defaults with controlled environment."""
    from codeweaver.providers.config import providers as pmod

    with (
        patch.object(pmod, "HAS_ANTHROPIC", new=has_anthropic),
        patch.object(Provider.ANTHROPIC, "has_env_auth", new=has_auth),
    ):
        return pmod._get_default_agent_provider_settings()


def test_agent_default_requires_auth():
    """Agent default must not activate when anthropic installed but no API key present."""
    result = _agent_defaults_with_mocked_env(has_anthropic=True, has_auth=False)
    assert result is None


def test_agent_default_with_auth():
    """Agent default activates when anthropic installed AND API key configured."""
    from codeweaver.core.constants import RECOMMENDED_CLOUD_CONTEXT_AGENT_MODEL_BARE

    result = _agent_defaults_with_mocked_env(has_anthropic=True, has_auth=True)
    assert result is not None
    assert len(result) == 1
    agent_settings = result[0]
    assert agent_settings.provider == Provider.ANTHROPIC
    assert ":" not in str(agent_settings.model_name)
    assert str(agent_settings.model_name) == RECOMMENDED_CLOUD_CONTEXT_AGENT_MODEL_BARE


def test_agent_default_no_package():
    """Agent default returns None when no anthropic package present."""
    result = _agent_defaults_with_mocked_env(has_anthropic=False, has_auth=False)
    assert result is None


# ---------------------------------------------------------------------------
# Task 6: embedding and sparse embedding defaults tests
# ---------------------------------------------------------------------------


def _embedding_defaults_with_mocked_packages(
    available_packages: set[str], voyage_auth: bool = False
):
    from codeweaver.providers.config import providers as pmod

    def mock_has_package(name: str):
        return name if name in available_packages else None

    with (
        patch.object(pmod, "has_package", side_effect=mock_has_package),
        patch.object(Provider.VOYAGE, "has_env_auth", new=voyage_auth),
    ):
        return pmod._get_default_embedding_settings()


def test_embedding_default_voyage_uses_recommended_model():
    """Voyage embedding default must use RECOMMENDED_CLOUD_EMBEDDING_MODEL (voyage-4-large, not voyage-4)."""
    from codeweaver.core.constants import RECOMMENDED_CLOUD_EMBEDDING_MODEL

    result = _embedding_defaults_with_mocked_packages({"voyageai"}, voyage_auth=True)
    assert result.provider == Provider.VOYAGE
    assert str(result.model) == RECOMMENDED_CLOUD_EMBEDDING_MODEL
    assert ":" not in str(result.model)


def test_embedding_default_fastembed_uses_recommended_query_model():
    """FastEmbed embedding default must use RECOMMENDED_QUERY_EMBEDDING_MODEL without colon prefix."""
    from codeweaver.core.constants import RECOMMENDED_QUERY_EMBEDDING_MODEL

    result = _embedding_defaults_with_mocked_packages({"fastembed"})
    assert result.provider == Provider.FASTEMBED
    assert ":" not in str(result.model)
    assert str(result.model) == RECOMMENDED_QUERY_EMBEDDING_MODEL


def test_embedding_default_sentence_transformers_uses_recommended_query_model():
    """SentenceTransformers embedding default must use RECOMMENDED_QUERY_EMBEDDING_MODEL."""
    from codeweaver.core.constants import RECOMMENDED_QUERY_EMBEDDING_MODEL

    result = _embedding_defaults_with_mocked_packages({"sentence_transformers"})
    assert result.provider == Provider.SENTENCE_TRANSFORMERS
    assert ":" not in str(result.model)
    assert str(result.model) == RECOMMENDED_QUERY_EMBEDDING_MODEL


def test_sparse_embedding_default_uses_sparse_constant():
    """Sparse embedding default model must match RECOMMENDED_SPARSE_EMBEDDING_MODEL."""
    from codeweaver.core.constants import RECOMMENDED_SPARSE_EMBEDDING_MODEL
    from codeweaver.providers.config import providers as pmod

    def mock_has_package(name: str):
        return name if name == "fastembed" else None

    with patch.object(pmod, "has_package", side_effect=mock_has_package):
        result = pmod._get_default_sparse_embedding_settings()

    assert str(result.model) == RECOMMENDED_SPARSE_EMBEDDING_MODEL
