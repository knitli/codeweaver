# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Unit tests for provider profiles -- model name correctness and consistency."""

from __future__ import annotations

import sys

from codeweaver.core.constants import ULTRALIGHT_RERANKING_MODEL


def _get_profiles_module(monkeypatch):
    """Import profiles module with mocked dependencies to avoid circular imports."""
    # If already imported, clear cached version so monkeypatching HAS_ST works
    for key in list(sys.modules.keys()):
        if "codeweaver.providers.config.profiles" in key:
            del sys.modules[key]

    import codeweaver.providers.config.profiles as pmod

    return pmod


def test_recommended_query_provider_has_huggingface_prefix(monkeypatch):
    """voyage-4-nano loaded via SentenceTransformers needs voyageai/ org prefix."""
    pmod = _get_profiles_module(monkeypatch)
    monkeypatch.setattr(pmod, "HAS_ST", True)

    result = pmod._recommended_default("local")

    embedding_config = result.get("embedding")
    assert embedding_config is not None
    first = embedding_config[0] if isinstance(embedding_config, tuple) else embedding_config
    # It should be an AsymmetricEmbeddingProviderSettings with query_provider
    assert hasattr(first, "query_provider"), (
        f"Expected AsymmetricEmbeddingProviderSettings, got {type(first)}"
    )
    query_model = str(first.query_provider.model_name)
    assert query_model.startswith(("voyageai/", "onnx-community/")), (
        f"SentenceTransformers query model must use HuggingFace voyageai/ or onnx-community/ prefix, got: {query_model!r}"
    )


def test_quickstart_reranking_model_name_no_trailing_dash(monkeypatch):
    """Quickstart reranking model must be a valid model name without trailing dash."""
    pmod = _get_profiles_module(monkeypatch)
    monkeypatch.setattr(pmod, "HAS_ST", False)
    monkeypatch.setattr(pmod, "HAS_FASTEMBED", True)

    result = pmod._quickstart_default("local")
    reranking = result.get("reranking")
    assert reranking is not None
    first = reranking[0] if isinstance(reranking, tuple) else reranking
    model_name = str(first.model_name)
    assert not model_name.endswith("-"), (
        f"Reranking model name must not end with -, got: {model_name!r}"
    )
    assert model_name == ULTRALIGHT_RERANKING_MODEL


def test_quickstart_reranking_model_with_st(monkeypatch):
    """Quickstart reranking model (ST path) must also be a valid name."""
    pmod = _get_profiles_module(monkeypatch)
    monkeypatch.setattr(pmod, "HAS_ST", True)
    monkeypatch.setattr(pmod, "HAS_FASTEMBED", False)

    result = pmod._quickstart_default("local")
    reranking = result.get("reranking")
    assert reranking is not None
    first = reranking[0] if isinstance(reranking, tuple) else reranking
    model_name = str(first.model_name)
    assert not model_name.endswith("-"), (
        f"Reranking model name must not end with -, got: {model_name!r}"
    )


def test_recommended_profile_uses_constants_for_model_names():
    """Profile model names must match the canonical constants."""
    from codeweaver.core.constants import (
        RECOMMENDED_CLOUD_EMBEDDING_MODEL,
        RECOMMENDED_CLOUD_RERANKING_MODEL,
        RECOMMENDED_SPARSE_EMBEDDING_MODEL,
    )
    from codeweaver.providers.config.profiles import _recommended_default

    result = _recommended_default("local")

    embedding = result.get("embedding")
    assert embedding is not None
    first = embedding[0] if isinstance(embedding, tuple) else embedding
    # AsymmetricEmbeddingProviderSettings has embed_provider
    if hasattr(first, "embed_provider"):
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


def test_testing_profile_uses_ultralight_constants_fastembed_branch(monkeypatch):
    """Testing profile must use fastembed's ultralight sparse model when HAS_FASTEMBED.

    On Python 3.12/3.13 (fastembed available), the sparse embedder is
    FastEmbed's `qdrant/bm25`. Dense is ST's Potion 8M and reranker is
    fastembed's jina-reranker-v1-tiny-en.
    """
    from codeweaver.core.constants import (
        ULTRALIGHT_EMBEDDING_MODEL,
        ULTRALIGHT_RERANKING_MODEL,
        ULTRALIGHT_SPARSE_EMBEDDING_MODEL,
    )

    pmod = _get_profiles_module(monkeypatch)
    monkeypatch.setattr(pmod, "HAS_ST", True)
    monkeypatch.setattr(pmod, "HAS_FASTEMBED", True)

    result = pmod._testing_profile()

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


def test_testing_profile_uses_ultralight_constants_st_sparse_branch(monkeypatch):
    """Testing profile falls back to ST SparseEncoder sparse model when !HAS_FASTEMBED.

    On Python 3.14 (fastembed unavailable — py-rust-stemmers has no
    cp314/cp314t wheels), the testing profile gates its sparse embedder
    onto sentence-transformers' SparseEncoder with the lightweight
    `ibm-granite/granite-embedding-30m-sparse` model. Every profile is
    dense + sparse + reranking by design; 3.14 should not regress to
    dense-only just because one local embedder library doesn't build.
    """
    from codeweaver.core.constants import (
        ULTRALIGHT_EMBEDDING_MODEL,
        ULTRALIGHT_ST_RERANKING_MODEL,
        ULTRALIGHT_ST_SPARSE_EMBEDDING_MODEL,
    )

    pmod = _get_profiles_module(monkeypatch)
    monkeypatch.setattr(pmod, "HAS_ST", True)
    monkeypatch.setattr(pmod, "HAS_FASTEMBED", False)

    result = pmod._testing_profile()

    embedding = result.get("embedding")
    assert embedding is not None
    emb_first = embedding[0] if isinstance(embedding, tuple) else embedding
    assert str(emb_first.model_name) == ULTRALIGHT_EMBEDDING_MODEL

    sparse = result.get("sparse_embedding")
    assert sparse is not None
    sparse_first = sparse[0] if isinstance(sparse, tuple) else sparse
    assert str(sparse_first.model_name) == ULTRALIGHT_ST_SPARSE_EMBEDDING_MODEL

    reranking = result.get("reranking")
    assert reranking is not None
    rerank_first = reranking[0] if isinstance(reranking, tuple) else reranking
    # On the ST branch (no fastembed), the profile gates to
    # ULTRALIGHT_ST_RERANKING_MODEL because the original
    # ULTRALIGHT_RERANKING_MODEL (jinaai/jina-reranker-v1-tiny-en) is
    # only compatible with fastembed's ONNX loader — loading it via
    # sentence_transformers.CrossEncoder crashes on transformers 5.x
    # because the model's remote configuration_bert.py imports the
    # removed `transformers.onnx` module. See commit 7b735d2a.
    assert str(rerank_first.model_name) == ULTRALIGHT_ST_RERANKING_MODEL
