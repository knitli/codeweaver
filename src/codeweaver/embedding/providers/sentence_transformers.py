"""Provider for Sentence Transformers models."""

try:
    from sentence_transformers import SentenceTransformer, SparseEncoder
except ImportError as e:
    raise ImportError(
        'Please install the `sentence-transformers` package to use the Sentence Transformers provider, \nyou can use the `sentence-transformers` optional group — `pip install "codeweaver[sentence-transformers]"`'
    ) from e

_client: SentenceTransformer | SparseEncoder | None = None
