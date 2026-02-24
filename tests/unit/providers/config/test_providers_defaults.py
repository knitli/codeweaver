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
