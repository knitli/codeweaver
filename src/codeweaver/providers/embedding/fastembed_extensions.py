# sourcery skip: name-type-suffix
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Some added models for fastembed provider to modernize the offerings a bit."""

from __future__ import annotations


try:
    from dataclasses import asdict

    from fastembed.common.model_description import (
        DenseModelDescription,
        ModelSource,
        #    SparseModelDescription,
    )
    from fastembed.sparse import SparseTextEmbedding
    from fastembed.text import TextEmbedding

except ImportError as e:
    from codeweaver.exceptions import ConfigurationError

    raise ConfigurationError(
        "fastembed is not installed. Please install it with `pip install codeweaver[provider-fastembed]` or `codeweaver[provider-fastembed-gpu]`."
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
        model="BAAI/bge-m3",
        license="mit",
        sources=ModelSource(hf="BAAI/bge-m3"),
        # if this seems like a strange description, it's because it mirror the FastEmbed format, which gets parsed
        description="""Text embeddings, Unimodal (text), multilingual, 8192 input tokens truncation, Prefixes for queries/documents: not necessary, 2024 year.""",
        model_file="model.onnx",
        size_in_GB=2.27,
        dim=1024,
    ),
    DenseModelDescription(
        model="WhereIsAI/UAE-Large-V1",
        license="mit",
        sources=ModelSource(hf="WhereIsAI/UAE-Large-V1"),
        description="""Text embeddings, Unimodal (text), multilingual, 512 input tokens truncation, Prefixes for queries/documents: necessary, 2024 year.""",
        model_file="model.onnx",
        size_in_GB=0.67,
        dim=1024,
    ),
    DenseModelDescription(
        model="snowflake/snowflake-arctic-embed-l-v2.0",
        license="apache-2.0",
        sources=ModelSource(hf="Snowflake/snowflake-arctic-embed-l-v2.0"),
        description="""Text embeddings, Unimodal (text), multilingual, 8192 input tokens truncation, Prefixes for queries/documents: necessary, 2024 year.""",
        model_file="model.onnx",
        size_in_GB=2.27,
        dim=1024,
    ),
    DenseModelDescription(
        model="snowflake/snowflake-arctic-embed-m-v2.0",
        license="apache-2.0",
        sources=ModelSource(hf="Snowflake/snowflake-arctic-embed-m-v2.0"),
        description="""Text embeddings, Unimodal (text), multilingual, 8192 input tokens truncation, Prefixes for queries/documents: necessary, 2024 year.""",
        model_file="model.onnx",
        size_in_GB=1.23,
        dim=768,
    ),
)

# FastEmbed hasn't implemented custom model addition for sparse models yet
# but we only need one for now, and it's the next version of one already implemented
# so we just subclass and add it ourselves


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
    """
    additional_params = {
        "BAAI/bge-m3": {"pooling": "cls", "normalization": True},
        "WhereIsAI/UAE-Large-V1": {"pooling": "cls", "normalization": True},
        "snowflake/snowflake-arctic-embed-l-v2.0": {"pooling": "cls", "normalization": True},
        "snowflake/snowflake-arctic-embed-m-v2.0": {"pooling": "cls", "normalization": True},
    }
    embedder = TextEmbedding
    for model in DENSE_MODELS:
        # there's a lot of bugginess in custom model addition in Fastembed
        # 1) There's a mismatch in the naming of this field within Fastembed. DenseModelDescription will only accept `size_in_GB` and `TextEmbedding` will only accept `size_in_gb`.
        # 2) `tasks` is not a valid parameter for `TextEmbedding.add_custom_model`, but it's *added* by `DenseModelDescription`
        model_as_dict = {k: v for k, v in asdict(model).items() if k != "tasks"}
        gb_size = model_as_dict.pop("size_in_GB")
        params = model_as_dict | additional_params[model.model] | {"size_in_gb": gb_size}
        embedder.add_custom_model(**params)
    return embedder


__all__ = ("get_sparse_embedder", "get_text_embedder")
