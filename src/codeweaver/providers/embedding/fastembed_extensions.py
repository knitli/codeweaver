# sourcery skip: name-type-suffix
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Some added models for fastembed provider to modernize the offerings a bit."""

from __future__ import annotations


try:
    from fastembed.common.model_description import (
        DenseModelDescription,
        ModelSource,
        PoolingType,
        #    SparseModelDescription,
    )
    from fastembed.sparse import SparseTextEmbedding
    from fastembed.text import TextEmbedding, custom_text_embedding

except ImportError as e:
    from codeweaver.exceptions import ConfigurationError

    raise ConfigurationError(
        "fastembed is not installed. Please install it with `pip install codeweaver[fastembed]` or `codeweaver[fastembed-gpu]`."
    ) from e

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

# FastEmbed hasn't implemented custom model addition for sparse models yet
# but we only need one for now, and it's the next version of one already implemented
# so we just subclass and add it ourselves

CUSTOM_DENSE_MODELS = tuple(model.model for model in DENSE_MODELS)
# CUSTOM_SPARSE_MODELS = tuple(model.model for model in SPARSE_MODELS)


def get_sparse_embedder() -> type[SparseTextEmbedding]:
    """
    Get the sparse embedder with added custom models.

    TODO: Temporarily disabled until we can work out the bugs on added sparse models in Fastembed.
    """
    # splade_pp.supported_splade_models.append(SPARSE_MODELS[0])
    return SparseTextEmbedding


def get_text_embedder() -> type[TextEmbedding]:
    """
    Get the text embedder with added custom models.

    Only adds models that aren't already in FastEmbed's native registry to avoid conflicts.
    """
    """
    additional_params = {
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
    """
    embedder = TextEmbedding
    """
    TODO: Temporarily disabled until we can work out the bugs on added dense models in Fastembed.
    # Get existing model names from native FastEmbed registry
    existing_model_names = {model.get("model") for model in embedder.list_supported_models()}

    if models_to_add := [
        model for model in DENSE_MODELS if model.model not in existing_model_names
    ]:
        custom_embedder = custom_text_embedding.CustomTextEmbedding
        for model in models_to_add:
            custom_embedder.add_model(model, **additional_params[model.model])  # type: ignore

        embedder.EMBEDDINGS_REGISTRY = [
            cls
            for cls in TextEmbedding.EMBEDDINGS_REGISTRY
            if cls is not custom_text_embedding.CustomTextEmbedding
        ]
        embedder.EMBEDDINGS_REGISTRY.append(custom_embedder)
    """
    return embedder


__all__ = ("get_sparse_embedder", "get_text_embedder")
