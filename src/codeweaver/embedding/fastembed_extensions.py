"""Some added models for fastembed provider to modernize the offerings a bit."""

try:
    from dataclasses import asdict

    from fastembed.common.model_description import (
        DenseModelDescription,
        ModelSource,
        SparseModelDescription,
    )
    from fastembed.sparse import SparseTextEmbedding
    from fastembed.text import TextEmbedding

except ImportError as e:
    raise ImportError(
        "fastembed is not installed. Please install it with `pip install fastembed`."
    ) from e

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

DENSE_MODELS = (
    DenseModelDescription(
        model="BAAI/bge-m3",
        license="mit",
        sources=ModelSource(hf="BAAI/bge-m3"),
        # if this seems like a strange description, it's because it mirror the FastEmbed format, which gets parsed
        description="Text embeddings, Unimodal (text), multilingual, 8192 input tokens truncation, Prefixes for queries/documents: not necessary, 2024 year.",
        model_file="model.onnx",
        size_in_GB=2.27,
        dim=1024,
    ),
    DenseModelDescription(
        model="WhereIsAI/UAE-Large-V1",
        license="mit",
        sources=ModelSource(hf="WhereIsAI/UAE-Large-V1"),
        description="Text embeddings, Unimodal (text), multilingual, 512 input tokens truncation, Prefixes for queries/documents: necessary, 2024 year.",
        model_file="model.onnx",
        size_in_GB=0.67,
        dim=1024,
    ),
    DenseModelDescription(
        model="snowflake/snowflake-arctic-embed-l-v2.0",
        license="apache-2.0",
        sources=ModelSource(hf="Snowflake/snowflake-arctic-embed-l-v2.0"),
        description="Text embeddings, Unimodal (text), multilingual, 8192 input tokens truncation, Prefixes for queries/documents: necessary, 2024 year.",
        model_file="model.onnx",
        size_in_GB=2.27,
        dim=1024,
    ),
    DenseModelDescription(
        model="snowflake/snowflake-arctic-embed-m-v2.0",
        license="apache-2.0",
        sources=ModelSource(hf="Snowflake/snowflake-arctic-embed-m-v2.0"),
        description="Text embeddings, Unimodal (text), multilingual, 8192 input tokens truncation, Prefixes for queries/documents: necessary, 2024 year.",
        model_file="model.onnx",
        size_in_GB=1.23,
        dim=768,
    ),
)


def get_sparse_embedder() -> type[SparseTextEmbedding]:
    """
    Get the sparse text embedder with added custom models.
    """
    embedder = SparseTextEmbedding
    for model in SPARSE_MODELS:
        embedder.add_custom_model(asdict(model))
    return embedder


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
        params = asdict(model) | additional_params[model.model]
        embedder.add_custom_model(**params)
    return embedder
