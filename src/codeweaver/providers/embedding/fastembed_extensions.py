# sourcery skip: name-type-suffix
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Some added models for fastembed provider to modernize the offerings a bit."""

from __future__ import annotations

from typing import TYPE_CHECKING, Any, overload

from codeweaver.core.di import dependency_provider
from codeweaver.core.utils import has_package

_FASTEMBED_AVAILABLE = has_package("fastembed") or has_package("fastembed-gpu")

if TYPE_CHECKING:
    from fastembed.common.model_description import (
        BaseModelDescription,
        DenseModelDescription,
        ModelSource,
        PoolingType,
        #    SparseModelDescription,
    )
    from fastembed.rerank.cross_encoder import TextCrossEncoder
    from fastembed.sparse import SparseTextEmbedding
    from fastembed.text import TextEmbedding
elif _FASTEMBED_AVAILABLE:
    try:
        from fastembed.common.model_description import (
            BaseModelDescription,
            DenseModelDescription,
            ModelSource,
            PoolingType,
        )
        from fastembed.rerank.cross_encoder import TextCrossEncoder
        from fastembed.sparse import SparseTextEmbedding
        from fastembed.text import TextEmbedding
    except ImportError:
        _FASTEMBED_AVAILABLE = False

if not (TYPE_CHECKING or _FASTEMBED_AVAILABLE):
    BaseModelDescription = Any
    DenseModelDescription = Any
    ModelSource = Any
    PoolingType = Any
    TextCrossEncoder = Any
    SparseTextEmbedding = Any
    TextEmbedding = Any


def _require_fastembed() -> None:
    """Raise ConfigurationError if fastembed is not installed."""
    if not _FASTEMBED_AVAILABLE:
        from codeweaver.core import ConfigurationError

        raise ConfigurationError(
            "fastembed is not installed. Please install it with "
            "`pip install code-weaver[fastembed]` or `pip install code-weaver[fastembed-gpu]`."
        )


if _FASTEMBED_AVAILABLE:
    """
    SPARSE_MODELS = (
        SparseModelDescription(
            model="prithivida/Splade_PP_en_v2",
            vocab_size=30522,  # BERT base uncased vocab
            description="SPLADE++ v2",
            license="apache-2.0",
            size_in_GB=0.6,
            sources=ModelSource(hf="prithivida/Splade_PP_en_v2"),
            model_file="model.onnx",
        ),
    )
    """
    DENSE_MODELS = (
        DenseModelDescription(
            model="Alibaba-NLP/gte-modernbert-base",
            license="apache-2.0",
            sources=ModelSource(hf="Alibaba-NLP/gte-modernbert-base"),
            description="""Text embeddings, Unimodal (text), multilingual, 8192 input tokens truncation, Prefixes for queries/documents: not necessary, 2024 year.""",
            model_file="onnx/model.onnx",
            size_in_GB=0.60,
            dim=768,
        ),
        DenseModelDescription(
            model="BAAI/bge-m3",
            license="mit",
            sources=ModelSource(hf="BAAI/bge-m3"),
            # if this seems like a strange description, it's because it mirrors the FastEmbed format, which gets parsed
            description="""Text embeddings, Unimodal (text), multilingual, 8192 input tokens truncation, Prefixes for queries/documents: not necessary, 2024 year.""",
            model_file="onnx/model.onnx",
            additional_files=["onnx/model.onnx_data"],
            size_in_GB=2.27,
            dim=1024,
        ),
        DenseModelDescription(
            model="WhereIsAI/UAE-Large-V1",
            license="mit",
            sources=ModelSource(hf="WhereIsAI/UAE-Large-V1"),
            description="""Text embeddings, Unimodal (text), multilingual, 512 input tokens truncation, Prefixes for queries/documents: necessary, 2024 year.""",
            model_file="onnx/model.onnx",
            size_in_GB=1.23,
            dim=1024,
        ),
        DenseModelDescription(
            model="snowflake/snowflake-arctic-embed-l-v2.0",
            license="apache-2.0",
            sources=ModelSource(hf="Snowflake/snowflake-arctic-embed-l-v2.0"),
            description="""Text embeddings, Unimodal (text), multilingual, 8192 input tokens truncation, Prefixes for queries/documents: necessary, 2024 year.""",
            model_file="onnx/model.onnx",
            size_in_GB=1.79,
            dim=1024,
        ),
        DenseModelDescription(
            model="snowflake/snowflake-arctic-embed-m-v2.0",
            license="apache-2.0",
            sources=ModelSource(hf="Snowflake/snowflake-arctic-embed-m-v2.0"),
            description="""Text embeddings, Unimodal (text), multilingual, 8192 input tokens truncation, Prefixes for queries/documents: necessary, 2024 year.""",
            model_file="onnx/model.onnx",
            size_in_GB=1.23,
            dim=768,
        ),
    )

    RERANKING_MODELS: tuple[BaseModelDescription, ...] = (
        BaseModelDescription(
            model="Alibaba-NLP/gte-reranker-modernbert-base",
            license="apache-2.0",
            sources=ModelSource(hf="Alibaba-NLP/gte-reranker-modernbert-base"),
            description="""A lightweight high-performance cross-encoder with 8192 token context length.""",
            model_file="onnx/model_fp16.onnx",
            size_in_GB=0.3,
        ),
    )
else:
    DENSE_MODELS = ()
    RERANKING_MODELS = ()


@overload
def add_models[T: type[TextEmbedding]](cls: T, models: tuple[DenseModelDescription, ...]) -> T: ...
@overload
def add_models[T: type[TextCrossEncoder]](
    cls: T, models: tuple[BaseModelDescription, ...]
) -> T: ...


def add_models[T: type[TextCrossEncoder | TextEmbedding]](
    cls: T, models: tuple[BaseModelDescription, ...] | tuple[DenseModelDescription, ...]
) -> T:
    """Add custom models to the input cls.

    Models are added to the *class*; the function returns the input class, not an instance.
    """
    known_models = {
        model["model"] if isinstance(model, dict) else model.model
        for model in cls.list_supported_models()
    }
    for model in models:
        if model.model not in known_models:
            if isinstance(model, DenseModelDescription):
                # New fastembed API requires individual parameters for TextEmbedding
                cls.add_custom_model(
                    model.model,
                    pooling=PoolingType.MEAN,
                    normalization=True,
                    sources=model.sources,
                    dim=model.dim or 768,
                    model_file=model.model_file,
                    description=model.description,
                    license=model.license,
                    size_in_gb=model.size_in_GB,
                    additional_files=model.additional_files or [],
                )
            else:
                # TextCrossEncoder uses a simpler API
                cls.add_custom_model(
                    model.model,
                    sources=model.sources,
                    model_file=model.model_file,
                    description=model.description,
                    license=model.license,
                    size_in_gb=model.size_in_GB,
                    additional_files=model.additional_files or [],
                )
    return cls


@dependency_provider(type[TextCrossEncoder], scope="singleton")
def get_cross_encoder() -> type[TextCrossEncoder]:
    """
    Get the cross encoder with added custom models.
    """
    _require_fastembed()
    return add_models(TextCrossEncoder, RERANKING_MODELS)


@dependency_provider(type[SparseTextEmbedding], scope="singleton")
def get_sparse_embedder() -> type[SparseTextEmbedding]:
    """
    Get the sparse embedder with added custom models.

    TODO: Temporarily disabled until we can work out the bugs on added sparse models in FastEmbed.
    """
    _require_fastembed()
    # splade_pp.supported_splade_models.append(SPARSE_MODELS[0])
    return SparseTextEmbedding


@dependency_provider(type[TextEmbedding], scope="singleton")
def get_text_embedder() -> type[TextEmbedding]:
    """
    Get the text embedder with added custom models.

    Only adds models that aren't already in FastEmbed's native registry to avoid conflicts.
    """
    _require_fastembed()
    from fastembed.common.model_description import PoolingType

    # we don't add these yet, but they're here for when we do
    _additional_params = {
        "Alibaba-NLP/gte-modernbert-base": {"pooling": PoolingType.CLS, "normalization": True},
        "BAAI/bge-m3": {"pooling": PoolingType.CLS, "normalization": True},
        "WhereIsAI/UAE-Large-V1": {"pooling": PoolingType.CLS, "normalization": True},
        "snowflake/snowflake-arctic-embed-l-v2.0": {
            "pooling": PoolingType.CLS,
            "normalization": True,
        },
        "snowflake/snowflake-arctic-embed-m-v2.0": {
            "pooling": PoolingType.CLS,
            "normalization": True,
        },
    }
    return add_models(TextEmbedding, DENSE_MODELS)


__all__ = (
    "DENSE_MODELS",
    "RERANKING_MODELS",
    "add_models",
    "get_cross_encoder",
    "get_sparse_embedder",
    "get_text_embedder",
)
