<!--
SPDX-FileCopyrightText: 2026 Knitli Inc.

SPDX-License-Identifier: MIT OR Apache-2.0
-->

# Provider Config Consolidation Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Fix bugs in the provider defaults system, align all model names to constants.py as the single source of truth, and enforce proper auth checks before auto-selecting cloud providers.

**Architecture:** Three-file touch — `constants.py` gains one new constant; `providers.py` gets five bug fixes and constant imports; `profiles.py` gets two bug fixes and constant imports. No structural changes to either system; the defaults and profiles continue to coexist.

**Tech Stack:** Python 3.12+, pydantic, pytest, `unittest.mock.patch`

---

## Background

Two bugs in `providers/config/providers.py` make reranking defaults completely broken for sentence_transformers and fastembed_gpu:
- The `_get_default_reranking_settings` loop iterates over `"sentence_transformers"` and `"fastembed_gpu"` (underscores) but the inner conditionals compare against `"sentence-transformers"` and `"fastembed-gpu"` (hyphens) — dead code that never executes.
- All three reranking model names have invalid colon prefixes (`"voyage:rerank-2.5"`, `"fastembed:jinaai/..."`, `"sentence-transformers:BAAI/..."`). For non-agent providers the model name must be exactly what the provider SDK expects (no prefix); the `"provider:model"` format is pydantic-ai's agent-only syntax.
- Voyage reranking default doesn't check `has_env_auth` — it activates even without a Voyage API key.
- Agent default only checks package presence, not API key — same problem.

`providers/config/profiles.py` has two independent bugs:
- `_recommended_default` uses `"voyage-4-nano"` as the sentence_transformers query model; sentence_transformers loads HuggingFace models and needs the org prefix `"voyageai/voyage-4-nano"`.
- `_quickstart_default` has a trailing-dash typo: `"jinaai/jina-reranker-v1-en-"` (should be `ULTRALIGHT_RERANKING_MODEL = "jinaai/jina-reranker-v1-tiny-en"`).

Neither file imports the model name constants already defined in `core/constants.py`.

---

## Task 1: Add bare agent model name constant to `constants.py`

**Files:**
- Modify: `src/codeweaver/core/constants.py` (around line 720 — after `RECOMMENDED_CLOUD_CONTEXT_AGENT_MODEL`)

**Why:** `RECOMMENDED_CLOUD_CONTEXT_AGENT_MODEL = "anthropic:claude-haiku-4.5"` uses pydantic-ai's `"provider:model"` format, which is correct when constructing a `pydantic_ai.Agent`. But `AnthropicAgentProviderSettings.model_name` is a provider-specific field where `provider=Provider.ANTHROPIC` is already set — it expects the bare model name. We need a single source of truth for the bare string too.

**Step 1: Write the failing test**

Create `tests/unit/providers/config/test_providers_defaults.py`:

```python
# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Unit tests for provider default detection and model name correctness."""

from __future__ import annotations

import pytest

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
```

**Step 2: Run to verify it fails**

```bash
mise run test tests/unit/providers/config/test_providers_defaults.py -v
```
Expected: `ImportError` — `RECOMMENDED_CLOUD_CONTEXT_AGENT_MODEL_BARE` does not exist yet.

**Step 3: Add the constant**

In `src/codeweaver/core/constants.py`, after line 721 (after `RECOMMENDED_CLOUD_CONTEXT_AGENT_MODEL`):

```python
RECOMMENDED_CLOUD_CONTEXT_AGENT_MODEL_BARE = "claude-haiku-4.5"
"""Bare model name for use in provider-specific settings (e.g. AnthropicAgentProviderSettings.model_name).

This is the part after ':' in RECOMMENDED_CLOUD_CONTEXT_AGENT_MODEL. Provider-specific
settings classes already capture the provider via their 'provider' field, so model_name
must be the bare string the provider SDK expects, not the pydantic-ai 'provider:model' format.
"""
```

Also add it to `__all__` in `constants.py` after `"RECOMMENDED_CLOUD_CONTEXT_AGENT_MODEL"`.

**Step 4: Run tests to verify they pass**

```bash
mise run test tests/unit/providers/config/test_providers_defaults.py -v
```
Expected: PASS (2 tests).

**Step 5: Commit**

```bash
git add src/codeweaver/core/constants.py tests/unit/providers/config/test_providers_defaults.py
git commit -m "feat(constants): add RECOMMENDED_CLOUD_CONTEXT_AGENT_MODEL_BARE for provider-specific agent settings"
```

---

## Task 2: Fix reranking detection bugs in `providers.py`

**Files:**
- Modify: `src/codeweaver/providers/config/providers.py` (`_get_default_reranking_settings`, lines 327–357)
- Modify: `tests/unit/providers/config/test_providers_defaults.py`

**The bugs (all in `_get_default_reranking_settings`):**

| Bug | Current (broken) | Correct |
|-----|-----------------|---------|
| Dead code — lib never matches | `lib in {"fastembed-gpu", "fastembed"}` | `lib in {"fastembed_gpu", "fastembed"}` |
| Dead code — lib never matches | `lib == "sentence-transformers"` | `lib == "sentence_transformers"` |
| Colon prefix — wrong format | `"voyage:rerank-2.5"` | `RECOMMENDED_CLOUD_RERANKING_MODEL` |
| Colon prefix — wrong format | `"fastembed:jinaai/jina-reranking-v2-base-multilingual"` | `RECOMMENDED_LOCAL_RERANKING_MODEL` |
| Colon prefix — wrong format | `"sentence-transformers:BAAI/bge-reranking-v2-m3"` | `RECOMMENDED_LOCAL_RERANKING_MODEL` |
| No auth check | Voyage selected if voyageai package present | Only if `Provider.VOYAGE.has_env_auth` too |

Note: After fixing the dead-code bugs, the ST and fastembed paths both map to `RECOMMENDED_LOCAL_RERANKING_MODEL = "Alibaba-NLP/gte-reranker-modernbert-base"` which the constants confirm works with both providers. Using a single model for both simplifies the code.

**Step 1: Write the failing tests**

Append to `tests/unit/providers/config/test_providers_defaults.py`:

```python
from unittest.mock import patch

from codeweaver.core.constants import (
    RECOMMENDED_CLOUD_RERANKING_MODEL,
    RECOMMENDED_LOCAL_RERANKING_MODEL,
    ULTRALIGHT_RERANKING_MODEL,
)
from codeweaver.core.types import Provider


def _reranking_defaults_with_mocked_packages(
    available_packages: set[str], voyage_has_auth: bool = False
):
    """Helper to call _get_default_reranking_settings with controlled environment."""
    from codeweaver.providers.config import providers as pmod

    def mock_has_package(name: str):
        return name if name in available_packages else None

    with (
        patch.object(pmod, "has_package", side_effect=mock_has_package),
        patch.object(Provider.VOYAGE, "has_env_auth", new=voyage_has_auth),
    ):
        return pmod._get_default_reranking_settings()


def test_reranking_default_voyage_requires_auth():
    """Voyage reranking must not be selected if voyageai package is present but no API key."""
    result = _reranking_defaults_with_mocked_packages({"voyageai"}, voyage_has_auth=False)
    assert result.provider != Provider.VOYAGE
    assert result.enabled is False  # falls through to no-provider warning


def test_reranking_default_voyage_with_auth():
    """Voyage reranking selected when voyageai package present and API key configured."""
    result = _reranking_defaults_with_mocked_packages({"voyageai"}, voyage_has_auth=True)
    assert result.provider == Provider.VOYAGE
    assert result.model == RECOMMENDED_CLOUD_RERANKING_MODEL
    assert ":" not in str(result.model)  # no provider-prefix in model name


def test_reranking_default_fastembed_no_colon_prefix():
    """FastEmbed reranking model name must not have a colon prefix."""
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
    assert ":" not in str(result.model)
    assert str(result.model) == RECOMMENDED_LOCAL_RERANKING_MODEL


def test_reranking_default_sentence_transformers_no_colon_prefix():
    """Sentence Transformers reranking model name must not have a colon prefix."""
    result = _reranking_defaults_with_mocked_packages({"sentence_transformers"})
    assert result.enabled is True
    assert ":" not in str(result.model)
```

**Step 2: Run to verify they fail**

```bash
mise run test tests/unit/providers/config/test_providers_defaults.py::test_reranking_default_voyage_requires_auth -v
mise run test tests/unit/providers/config/test_providers_defaults.py::test_reranking_default_sentence_transformers_detected -v
```
Expected: FAIL — voyage has no auth check, ST detection is dead code.

**Step 3: Add the constants import to providers.py**

At the top of `src/codeweaver/providers/config/providers.py`, in the `codeweaver.core.constants` import (line 27), add:

```python
from codeweaver.core.constants import (
    ENV_EXPLICIT_TRUE_VALUES,
    LOCALHOST,
    ONE,
    RECOMMENDED_CLOUD_RERANKING_MODEL,
    RECOMMENDED_LOCAL_RERANKING_MODEL,
    ZERO,
)
```

**Step 4: Rewrite `_get_default_reranking_settings`**

Replace the entire function body (lines 327–357) with:

```python
def _get_default_reranking_settings() -> DeterminedDefaults:
    """Determine the default reranking provider and model based on available libraries.

    Cloud providers (Voyage) require both the client library and a configured API key.
    Local providers (FastEmbed, SentenceTransformers) only require the library.
    Priority: Voyage (cloud, auth required) > FastEmbed > SentenceTransformers.
    """
    for lib in ("voyageai", "fastembed_gpu", "fastembed", "sentence_transformers"):
        if has_package(lib):
            if lib == "voyageai" and Provider.VOYAGE.has_env_auth:
                return DeterminedDefaults(
                    provider=Provider.VOYAGE,
                    model=ModelName(RECOMMENDED_CLOUD_RERANKING_MODEL),
                    enabled=True,
                )
            if lib in {"fastembed_gpu", "fastembed"}:
                return DeterminedDefaults(
                    provider=Provider.FASTEMBED,
                    model=ModelName(RECOMMENDED_LOCAL_RERANKING_MODEL),
                    enabled=True,
                )
            if lib == "sentence_transformers":
                return DeterminedDefaults(
                    provider=Provider.SENTENCE_TRANSFORMERS,
                    model=ModelName(RECOMMENDED_LOCAL_RERANKING_MODEL),
                    enabled=True,
                )
    possible_libs = [lib for lib in ("boto3", "cohere") if has_package(lib)]
    logger.warning(
        "No default reranking provider libraries found. Reranking functionality will be "
        "disabled unless explicitly set in your config or environment variables. %s",
        (
            f"It looks like you have "
            f"{'these libraries' if len(possible_libs) > 1 else 'this library'} installed "
            f"that support reranking: {', '.join(possible_libs)}."
            if possible_libs
            else "You have no known reranking libraries installed."
        ),
    )
    return DeterminedDefaults(provider=Provider.NOT_SET, model=None, enabled=False)
```

**Step 5: Run tests to verify they pass**

```bash
mise run test tests/unit/providers/config/test_providers_defaults.py -v
```
Expected: All reranking tests PASS.

**Step 6: Commit**

```bash
git add src/codeweaver/providers/config/providers.py tests/unit/providers/config/test_providers_defaults.py
git commit -m "fix(providers): correct reranking defaults — fix dead code, colon prefixes, and missing auth check"
```

---

## Task 3: Fix agent defaults auth check in `providers.py`

**Files:**
- Modify: `src/codeweaver/providers/config/providers.py` (`_get_default_agent_provider_settings`, lines 397–408)
- Modify: `tests/unit/providers/config/test_providers_defaults.py`

**Step 1: Write the failing test**

Append to the test file:

```python
from codeweaver.core.constants import RECOMMENDED_CLOUD_CONTEXT_AGENT_MODEL_BARE


def _agent_defaults_with_mocked_env(has_anthropic: bool, has_auth: bool):
    """Helper to test agent defaults with controlled environment."""
    from codeweaver.providers.config import providers as pmod

    def mock_has_package(name: str):
        if name in {"anthropic", "claude-agent-sdk"} and has_anthropic:
            return name
        return None

    with (
        patch.object(pmod, "has_package", side_effect=mock_has_package),
        patch.object(Provider.ANTHROPIC, "has_env_auth", new=has_auth),
    ):
        return pmod._get_default_agent_provider_settings()


def test_agent_default_requires_auth():
    """Agent default must not activate when anthropic is installed but no API key present."""
    result = _agent_defaults_with_mocked_env(has_anthropic=True, has_auth=False)
    assert result is None


def test_agent_default_with_auth():
    """Agent default activates when anthropic installed AND API key is configured."""
    result = _agent_defaults_with_mocked_env(has_anthropic=True, has_auth=True)
    assert result is not None
    assert len(result) == 1
    agent_settings = result[0]
    assert agent_settings.provider == Provider.ANTHROPIC
    # model_name must be bare (no provider prefix) for provider-specific settings
    assert ":" not in str(agent_settings.model_name)
    assert str(agent_settings.model_name) == RECOMMENDED_CLOUD_CONTEXT_AGENT_MODEL_BARE


def test_agent_default_no_package():
    """Agent default returns None when no anthropic package is present."""
    result = _agent_defaults_with_mocked_env(has_anthropic=False, has_auth=False)
    assert result is None
```

**Step 2: Run to verify they fail**

```bash
mise run test tests/unit/providers/config/test_providers_defaults.py::test_agent_default_requires_auth -v
```
Expected: FAIL — no auth check.

**Step 3: Update `_get_default_agent_provider_settings`**

Replace the function (around lines 397–408):

```python
def _get_default_agent_provider_settings() -> tuple[AgentProviderSettingsType, ...] | None:
    """Get default agent provider settings.

    Only activates if both the Anthropic package is present AND an API key is configured.
    Installing the anthropic SDK for unrelated reasons must not silently enable the
    CodeWeaver agent.
    """
    if not HAS_ANTHROPIC or not Provider.ANTHROPIC.has_env_auth:
        return None
    return (
        AnthropicAgentProviderSettings(
            provider=Provider.ANTHROPIC,
            model_name=RECOMMENDED_CLOUD_CONTEXT_AGENT_MODEL_BARE,
            agent_config=None,
        ),
    )
```

Also update the import at the top of the file to include `RECOMMENDED_CLOUD_CONTEXT_AGENT_MODEL_BARE`:

```python
from codeweaver.core.constants import (
    ENV_EXPLICIT_TRUE_VALUES,
    LOCALHOST,
    ONE,
    RECOMMENDED_CLOUD_CONTEXT_AGENT_MODEL_BARE,
    RECOMMENDED_CLOUD_RERANKING_MODEL,
    RECOMMENDED_LOCAL_RERANKING_MODEL,
    ZERO,
)
```

**Step 4: Run tests to verify they pass**

```bash
mise run test tests/unit/providers/config/test_providers_defaults.py -v
```
Expected: All tests PASS.

**Step 5: Run the full check**

```bash
mise run check
```
Expected: No new errors.

**Step 6: Commit**

```bash
git add src/codeweaver/providers/config/providers.py tests/unit/providers/config/test_providers_defaults.py
git commit -m "fix(providers): add has_env_auth check to agent default, use canonical model name constant"
```

---

## Task 4: Fix model name bugs in `profiles.py`

**Files:**
- Modify: `src/codeweaver/providers/config/profiles.py`
- Create: `tests/unit/providers/config/test_profiles.py`

**The bugs:**

| Location | Current (wrong) | Correct |
|----------|----------------|---------|
| `_recommended_default` L215 | `"voyage-4-nano"` (ST provider, missing org prefix) | `"voyageai/voyage-4-nano"` |
| `_quickstart_default` L284 | `"jinaai/jina-reranker-v1-en-"` (trailing dash typo) | `ULTRALIGHT_RERANKING_MODEL` |

**Step 1: Write the failing tests**

Create `tests/unit/providers/config/test_profiles.py`:

```python
# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Unit tests for provider profiles — model name correctness and consistency."""

from __future__ import annotations

import pytest

from codeweaver.core.constants import (
    RECOMMENDED_CLOUD_EMBEDDING_MODEL,
    RECOMMENDED_CLOUD_RERANKING_MODEL,
    RECOMMENDED_SPARSE_EMBEDDING_MODEL,
    ULTRALIGHT_EMBEDDING_MODEL,
    ULTRALIGHT_RERANKING_MODEL,
    ULTRALIGHT_SPARSE_EMBEDDING_MODEL,
)
from codeweaver.core import Provider
from codeweaver.providers.config.categories import AsymmetricEmbeddingProviderSettings


def test_recommended_query_provider_has_huggingface_prefix(monkeypatch):
    """voyage-4-nano loaded via SentenceTransformers needs 'voyageai/' org prefix."""
    # Force HAS_ST = True so we hit the ST query_provider branch
    import codeweaver.providers.config.profiles as pmod
    monkeypatch.setattr(pmod, "HAS_ST", True)

    from codeweaver.providers.config.providers import ProviderSettingsDict
    with pytest.MonkeyPatch().context() as m:
        m.setattr(pmod, "HAS_ST", True)
        result = pmod._recommended_default("local")

    embedding_config = result["embedding"]
    assert embedding_config is not None
    first = embedding_config[0] if isinstance(embedding_config, tuple) else embedding_config
    assert isinstance(first, AsymmetricEmbeddingProviderSettings)
    query_model = str(first.query_provider.model_name)
    assert query_model.startswith("voyageai/"), (
        f"SentenceTransformers query model must use HuggingFace 'voyageai/' prefix, got: {query_model!r}"
    )


def test_quickstart_reranking_model_name_no_trailing_dash(monkeypatch):
    """Quickstart reranking model must be a valid model name without trailing dash."""
    import codeweaver.providers.config.profiles as pmod
    monkeypatch.setattr(pmod, "HAS_ST", False)
    monkeypatch.setattr(pmod, "HAS_FASTEMBED", True)

    result = pmod._quickstart_default("local")
    reranking = result.get("reranking")
    assert reranking is not None
    first = reranking[0] if isinstance(reranking, tuple) else reranking
    model_name = str(first.model_name)
    assert not model_name.endswith("-"), (
        f"Reranking model name must not end with '-', got: {model_name!r}"
    )
    assert model_name == ULTRALIGHT_RERANKING_MODEL


def test_quickstart_reranking_model_with_st(monkeypatch):
    """Quickstart reranking model (ST path) must also be a valid name."""
    import codeweaver.providers.config.profiles as pmod
    monkeypatch.setattr(pmod, "HAS_ST", True)

    result = pmod._quickstart_default("local")
    reranking = result.get("reranking")
    assert reranking is not None
    first = reranking[0] if isinstance(reranking, tuple) else reranking
    model_name = str(first.model_name)
    assert not model_name.endswith("-"), (
        f"Reranking model name must not end with '-', got: {model_name!r}"
    )
```

**Step 2: Run to verify they fail**

```bash
mise run test tests/unit/providers/config/test_profiles.py -v
```
Expected: FAIL — `test_recommended_query_provider_has_huggingface_prefix` fails because "voyage-4-nano" lacks the prefix; `test_quickstart_reranking_model_name_no_trailing_dash` fails due to trailing dash.

**Step 3: Fix `_recommended_default` — voyage-4-nano prefix**

In `src/codeweaver/providers/config/profiles.py`, find line ~215:

```python
# WRONG:
query_provider=EmbeddingProviderSettings(
    model_name=ModelName("voyage-4-nano"),
    provider=Provider.SENTENCE_TRANSFORMERS,
    embedding_config=SentenceTransformersEmbeddingConfig(
        model_name=ModelName("voyage-4-nano")
    ),
),
```

Change both occurrences of `"voyage-4-nano"` to `"voyageai/voyage-4-nano"`:

```python
query_provider=EmbeddingProviderSettings(
    model_name=ModelName("voyageai/voyage-4-nano"),
    provider=Provider.SENTENCE_TRANSFORMERS,
    embedding_config=SentenceTransformersEmbeddingConfig(
        model_name=ModelName("voyageai/voyage-4-nano")
    ),
),
```

**Step 4: Fix `_quickstart_default` — trailing dash typo**

Find line ~284 in `profiles.py`:

```python
# WRONG:
reranking_model = ModelName("jinaai/jina-reranker-v1-en-")
```

Replace with (after the constants import added in Task 6):

```python
reranking_model = ModelName(ULTRALIGHT_RERANKING_MODEL)
```

For now (before Task 6 imports are in place), use the literal:

```python
reranking_model = ModelName("jinaai/jina-reranker-v1-tiny-en")
```

**Step 5: Run tests to verify they pass**

```bash
mise run test tests/unit/providers/config/test_profiles.py -v
```
Expected: All PASS.

**Step 6: Commit**

```bash
git add src/codeweaver/providers/config/profiles.py tests/unit/providers/config/test_profiles.py
git commit -m "fix(profiles): correct voyage-4-nano HF prefix in recommended profile, fix trailing-dash typo in quickstart reranker"
```

---

## Task 5: Import and use constants in `profiles.py`

**Files:**
- Modify: `src/codeweaver/providers/config/profiles.py`

**Purpose:** Replace all hardcoded model name strings in `profiles.py` with imports from `core.constants`. This creates a single place to update models without touching profile logic.

**Model name mapping (profiles.py → constant):**

| Hardcoded string | Constant |
|-----------------|----------|
| `"voyage-4-large"` | `RECOMMENDED_CLOUD_EMBEDDING_MODEL` |
| `"voyageai/voyage-4-nano"` | `RECOMMENDED_QUERY_EMBEDDING_MODEL` (when ST) or direct use after Task 4 fix |
| `"prithivida/Splade_PP_en_v1"` | `RECOMMENDED_SPARSE_EMBEDDING_MODEL` |
| `"voyage-rerank-2.5"` | `RECOMMENDED_CLOUD_RERANKING_MODEL` |
| `"claude-haiku-4.5"` (agent) | `RECOMMENDED_CLOUD_CONTEXT_AGENT_MODEL_BARE` |
| `"minishlab/potion-base-8M"` | `ULTRALIGHT_EMBEDDING_MODEL` |
| `"jinaai/jina-reranker-v1-tiny-en"` | `ULTRALIGHT_RERANKING_MODEL` |
| `"qdrant/bm25"` | `ULTRALIGHT_SPARSE_EMBEDDING_MODEL` |

Note on `RECOMMENDED_QUERY_EMBEDDING_MODEL`: `constants.py` already computes this conditionally at import time (fastembed → ONNX model; ST → `"voyageai/voyage-4-nano"`; else cloud-lite). `profiles.py` currently repeats similar logic with `HAS_ST`. After this task, `profiles.py` can just use `ModelName(RECOMMENDED_QUERY_EMBEDDING_MODEL)` directly, removing the internal logic duplication.

**Step 1: Write the test extension**

Append to `tests/unit/providers/config/test_profiles.py`:

```python
def test_recommended_profile_uses_constants_for_model_names():
    """Profile model names must match the canonical constants."""
    from codeweaver.providers.config.profiles import _recommended_default

    result = _recommended_default("local")

    embedding = result.get("embedding")
    assert embedding is not None
    first = embedding[0] if isinstance(embedding, tuple) else embedding
    if isinstance(first, AsymmetricEmbeddingProviderSettings):
        assert str(first.embed_provider.model_name) == RECOMMENDED_CLOUD_EMBEDDING_MODEL
    else:
        assert str(first.model_name) == RECOMMENDED_CLOUD_EMBEDDING_MODEL

    sparse = result.get("sparse_embedding")
    assert sparse is not None
    sparse_first = sparse[0] if isinstance(sparse, tuple) else sparse
    assert str(sparse_first.model_name) == RECOMMENDED_SPARSE_EMBEDDING_MODEL

    reranking = result.get("reranking")
    assert reranking is not None
    rerank_first = reranking[0] if isinstance(reranking, tuple) else reranking
    assert str(rerank_first.model_name) == RECOMMENDED_CLOUD_RERANKING_MODEL


def test_testing_profile_uses_ultralight_constants():
    """Testing profile must use the ultralight model name constants."""
    from codeweaver.core.constants import ULTRALIGHT_SPARSE_EMBEDDING_MODEL
    from codeweaver.providers.config.profiles import _testing_profile

    result = _testing_profile()

    embedding = result.get("embedding")
    assert embedding is not None
    emb_first = embedding[0] if isinstance(embedding, tuple) else embedding
    assert str(emb_first.model_name) == ULTRALIGHT_EMBEDDING_MODEL

    sparse = result.get("sparse_embedding")
    assert sparse is not None
    sparse_first = sparse[0] if isinstance(sparse, tuple) else sparse
    assert str(sparse_first.model_name) == ULTRALIGHT_SPARSE_EMBEDDING_MODEL

    reranking = result.get("reranking")
    assert reranking is not None
    rerank_first = reranking[0] if isinstance(reranking, tuple) else reranking
    assert str(rerank_first.model_name) == ULTRALIGHT_RERANKING_MODEL
```

**Step 2: Run to see baseline (should pass already after Task 4 for reranking, may fail for others)**

```bash
mise run test tests/unit/providers/config/test_profiles.py -v
```

**Step 3: Add constants imports to `profiles.py`**

In `src/codeweaver/providers/config/profiles.py`, add a new import block after the existing imports from `codeweaver.core`:

```python
from codeweaver.core.constants import (
    RECOMMENDED_CLOUD_CONTEXT_AGENT_MODEL_BARE,
    RECOMMENDED_CLOUD_EMBEDDING_MODEL,
    RECOMMENDED_CLOUD_RERANKING_MODEL,
    RECOMMENDED_QUERY_EMBEDDING_MODEL,
    RECOMMENDED_SPARSE_EMBEDDING_MODEL,
    ULTRALIGHT_EMBEDDING_MODEL,
    ULTRALIGHT_RERANKING_MODEL,
    ULTRALIGHT_SPARSE_EMBEDDING_MODEL,
)
```

**Step 4: Replace hardcoded strings throughout `profiles.py`**

Apply these substitutions in `_recommended_default`:
- `ModelName("voyage-4-large")` → `ModelName(RECOMMENDED_CLOUD_EMBEDDING_MODEL)` (2 occurrences in embed_provider)
- `ModelName("voyage-4-nano")` and `ModelName("voyageai/voyage-4-nano")` → `ModelName(RECOMMENDED_QUERY_EMBEDDING_MODEL)` (query_provider, 2 occurrences)
- `ModelName("prithivida/Splade_PP_en_v1")` → `ModelName(RECOMMENDED_SPARSE_EMBEDDING_MODEL)` (2 occurrences)
- `ModelName("voyage-rerank-2.5")` → `ModelName(RECOMMENDED_CLOUD_RERANKING_MODEL)` (2 occurrences)
- `model_name="claude-haiku-4.5"` (agent) → `model_name=RECOMMENDED_CLOUD_CONTEXT_AGENT_MODEL_BARE` (both `_recommended_default` and `_quickstart_default`)

In `_testing_profile`:
- `"minishlab/potion-base-8M"` string → `ULTRALIGHT_EMBEDDING_MODEL` (then ModelName wrapping stays)
- `"jinaai/jina-reranker-v1-tiny-en"` → `ULTRALIGHT_RERANKING_MODEL`
- `ModelName("qdrant/bm25")` → `ModelName(ULTRALIGHT_SPARSE_EMBEDDING_MODEL)`

In `_quickstart_default`, simplify the model selection:
- Remove the duplicated `HAS_ST/HAS_FASTEMBED` logic for `embedding_model` and use `ModelName(RECOMMENDED_QUERY_EMBEDDING_MODEL)` directly (since `RECOMMENDED_QUERY_EMBEDDING_MODEL` already encodes the same detection logic in `constants.py`)
- Simplify sparse model to `ModelName(RECOMMENDED_SPARSE_EMBEDDING_MODEL)` (same model works for both providers)
- Set `reranking_model = ModelName(ULTRALIGHT_RERANKING_MODEL)` (already done in Task 4, now uses constant)

**Step 5: Run tests to verify they pass**

```bash
mise run test tests/unit/providers/config/test_profiles.py -v
```
Expected: All PASS.

**Step 6: Run full quality check**

```bash
mise run check
```
Expected: No new errors.

**Step 7: Commit**

```bash
git add src/codeweaver/providers/config/profiles.py tests/unit/providers/config/test_profiles.py
git commit -m "refactor(profiles): import model name constants from core.constants, remove hardcoded strings"
```

---

## Task 6: Import and use constants in `providers.py` (remaining defaults)

**Files:**
- Modify: `src/codeweaver/providers/config/providers.py`
- Modify: `tests/unit/providers/config/test_providers_defaults.py`

**Purpose:** Complete the constants migration for `providers.py` — Tasks 2 and 3 already fixed reranking and agent. This task covers the embedding and sparse embedding defaults.

**Model name mapping (providers.py → constant):**

| Hardcoded string | Constant |
|-----------------|----------|
| `"voyage-4"` (embedding default) | `RECOMMENDED_CLOUD_EMBEDDING_MODEL` (or keep as explicit non-large model — see note) |
| `"voyageai/voyage-4-nano"` (ST embedding fallback) | `RECOMMENDED_QUERY_EMBEDDING_MODEL` |
| `"BAAI/bge-small-en-v1.5"` (fastembed embedding fallback) | `RECOMMENDED_QUERY_EMBEDDING_MODEL` |
| `"prithivida/Splade_PP_en_v1"` (sparse embedding) | `RECOMMENDED_SPARSE_EMBEDDING_MODEL` |

> **Note on `"voyage-4"` vs `RECOMMENDED_CLOUD_EMBEDDING_MODEL = "voyage-4-large"`:** The defaults use `"voyage-4"` (standard) while the recommended profile uses `"voyage-4-large"`. These have different costs and dimensions. The defaults system intentionally selects a lighter model. If keeping this distinction is intentional, add `RECOMMENDED_CLOUD_EMBEDDING_MODEL_STANDARD = "voyage-4"` to constants.py. If unintentional (i.e., defaults should match the recommended profile), change to `RECOMMENDED_CLOUD_EMBEDDING_MODEL`. **Verify with project owner before implementing.** The plan below assumes adding the `_STANDARD` variant.

**Step 1: Write the failing tests**

Append to `tests/unit/providers/config/test_providers_defaults.py`:

```python
from codeweaver.core.constants import (
    RECOMMENDED_CLOUD_EMBEDDING_MODEL_STANDARD,  # to be added
    RECOMMENDED_QUERY_EMBEDDING_MODEL,
    RECOMMENDED_SPARSE_EMBEDDING_MODEL,
)


def _embedding_defaults_with_mocked_packages(
    available_packages: set[str],
    voyage_auth: bool = False,
    mistral_auth: bool = False,
    google_auth: bool = False,
):
    from codeweaver.providers.config import providers as pmod

    def mock_has_package(name: str):
        return name if name in available_packages else None

    with (
        patch.object(pmod, "has_package", side_effect=mock_has_package),
        patch.object(Provider.VOYAGE, "has_env_auth", new=voyage_auth),
        patch.object(Provider.MISTRAL, "has_env_auth", new=mistral_auth),
        patch.object(Provider.GOOGLE, "has_env_auth", new=google_auth),
    ):
        return pmod._get_default_embedding_settings()


def test_embedding_default_fastembed_no_colon():
    """FastEmbed embedding model must not have a colon prefix."""
    result = _embedding_defaults_with_mocked_packages({"fastembed"})
    assert result.provider == Provider.FASTEMBED
    assert ":" not in str(result.model)
    assert str(result.model) == RECOMMENDED_QUERY_EMBEDDING_MODEL


def test_embedding_default_sentence_transformers_no_colon():
    """SentenceTransformers embedding model must not have a colon prefix."""
    result = _embedding_defaults_with_mocked_packages({"sentence_transformers"})
    assert result.provider == Provider.SENTENCE_TRANSFORMERS
    assert ":" not in str(result.model)
    assert str(result.model) == RECOMMENDED_QUERY_EMBEDDING_MODEL


def test_sparse_embedding_default_uses_constant():
    """Sparse embedding default model must match the canonical constant."""
    from codeweaver.providers.config import providers as pmod

    def mock_has_package(name: str):
        return name if name in {"fastembed"} else None

    with patch.object(pmod, "has_package", side_effect=mock_has_package):
        result = pmod._get_default_sparse_embedding_settings()

    assert str(result.model) == RECOMMENDED_SPARSE_EMBEDDING_MODEL
```

**Step 2: Run to verify current state**

```bash
mise run test tests/unit/providers/config/test_providers_defaults.py -v
```
Some tests may already pass; others (like the `_STANDARD` constant) will fail until constants.py is updated.

**Step 3: Add `RECOMMENDED_CLOUD_EMBEDDING_MODEL_STANDARD` to `constants.py`** (if the voyage-4 vs voyage-4-large distinction is intentional — confirm first):

```python
RECOMMENDED_CLOUD_EMBEDDING_MODEL_STANDARD = "voyage-4"
"""Standard tier recommended cloud embedding model. Lighter than voyage-4-large with lower cost,
suitable for general use. Used as the auto-detected default when Voyage auth is configured.
For the highest quality, see RECOMMENDED_CLOUD_EMBEDDING_MODEL (voyage-4-large).
"""
```

Add to `__all__` in `constants.py`.

**Step 4: Update the constants import in providers.py**

The import block at the top of `providers.py` should now be:

```python
from codeweaver.core.constants import (
    ENV_EXPLICIT_TRUE_VALUES,
    LOCALHOST,
    ONE,
    RECOMMENDED_CLOUD_CONTEXT_AGENT_MODEL_BARE,
    RECOMMENDED_CLOUD_EMBEDDING_MODEL_STANDARD,
    RECOMMENDED_CLOUD_RERANKING_MODEL,
    RECOMMENDED_LOCAL_RERANKING_MODEL,
    RECOMMENDED_QUERY_EMBEDDING_MODEL,
    RECOMMENDED_SPARSE_EMBEDDING_MODEL,
    ZERO,
)
```

**Step 5: Replace hardcoded strings in providers.py embedding/sparse functions**

In `_get_default_embedding_settings` (lines 143–184), change:
- `ModelName("voyage-4")` → `ModelName(RECOMMENDED_CLOUD_EMBEDDING_MODEL_STANDARD)` (Voyage branch)
- `ModelName("voyageai/voyage-4-nano")` → `ModelName(RECOMMENDED_QUERY_EMBEDDING_MODEL)` (ST branch)
- `ModelName("BAAI/bge-small-en-v1.5")` → `ModelName(RECOMMENDED_QUERY_EMBEDDING_MODEL)` (fastembed branch)

In `_get_default_sparse_embedding_settings` (lines 269–289), change:
- `ModelName("opensearch/opensearch-neural-sparse-encoding-doc-v3-gte")` → `ModelName(RECOMMENDED_SPARSE_EMBEDDING_MODEL)` (ST branch — or confirm if this is intentional)
- `ModelName("prithivida/Splade_PP_en_v1")` → `ModelName(RECOMMENDED_SPARSE_EMBEDDING_MODEL)` (fastembed branch)

**Step 6: Run all config tests**

```bash
mise run test tests/unit/providers/config/ -v
```
Expected: All PASS.

**Step 7: Run full quality check and full test suite**

```bash
mise run check
mise run test
```
Expected: No regressions.

**Step 8: Commit**

```bash
git add src/codeweaver/core/constants.py src/codeweaver/providers/config/providers.py tests/unit/providers/config/test_providers_defaults.py
git commit -m "refactor(providers): use constants for all remaining model names in defaults, add RECOMMENDED_CLOUD_EMBEDDING_MODEL_STANDARD"
```

---

## Summary of Changes

| File | Type | Changes |
|------|------|---------|
| `src/codeweaver/core/constants.py` | Enhancement | Add `RECOMMENDED_CLOUD_CONTEXT_AGENT_MODEL_BARE`, `RECOMMENDED_CLOUD_EMBEDDING_MODEL_STANDARD` |
| `src/codeweaver/providers/config/providers.py` | Bug fix + enhancement | Fix 5 reranking bugs, add 2 auth checks, import + use constants |
| `src/codeweaver/providers/config/profiles.py` | Bug fix + enhancement | Fix voyage-4-nano prefix, fix trailing dash, import + use constants |
| `tests/unit/providers/config/test_providers_defaults.py` | New | Tests for reranking/agent defaults correctness |
| `tests/unit/providers/config/test_profiles.py` | New | Tests for profile model name correctness |

**Tests written:** ~20 new unit tests across both test files.

**Execution order:** Tasks 1 → 2 → 3 → 4 → 5 → 6. Each task is independently committable. Task 6 depends on Task 1 (for the bare constant) and Task 2 (for the reranking import). Tasks 4 and 5 are independent of Tasks 2 and 3 (different files).
