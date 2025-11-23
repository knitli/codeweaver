#!/usr/bin/env sh
set -eu

EMBED_PROVIDER="${CODEWEAVER_EMBEDDING_PROVIDER:-}"
RERANK_PROVIDER="${CODEWEAVER_RERANKING_PROVIDER:-}"
DEFAULT_PROVIDER="voyage"

# Normalize provider names to lowercase for leniency
if [ -n "$EMBED_PROVIDER" ]; then
    EMBED_PROVIDER="$(printf '%s' "$EMBED_PROVIDER" | tr '[:upper:]' '[:lower:]')"
else
    EMBED_PROVIDER="$DEFAULT_PROVIDER"
fi

if [ -n "$RERANK_PROVIDER" ]; then
    RERANK_PROVIDER="$(printf '%s' "$RERANK_PROVIDER" | tr '[:upper:]' '[:lower:]')"
else
    RERANK_PROVIDER="$DEFAULT_PROVIDER"
fi

if [ "$EMBED_PROVIDER" = "$DEFAULT_PROVIDER" ] || [ "$RERANK_PROVIDER" = "$DEFAULT_PROVIDER" ]; then
        if [ -z "${VOYAGE_API_KEY:-}" ]; then
                cat >&2 <<'EOF'
CodeWeaver needs a Voyage API key

You are using the default Voyage provider for embeddings and/or reranking, but the
VOYAGE_API_KEY environment variable is not set. Voyage requires an API key for all
requests, so the server would fail to index any code.

We recommend signing up for a free Voyage account at https://voyage.ai/ to get an API key. The free tier is generous and should be sufficient for most use cases.
Using a cloud provider, especially Voyage, gives you cutting-edge models and keeps your computer from getting overworked 😫. You'll also get embeddings in seconds, not minutes.

Set VOYAGE_API_KEY before starting the container, for example:

    docker run -e VOYAGE_API_KEY="sk-..." knitli/codeweaver:latest

Or, override CODEWEAVER_EMBEDDING_PROVIDER / CODEWEAVER_RERANKING_PROVIDER with a
provider that does not require an API key (e.g. fastembed) if you prefer local-only
models.

This build also uses a local qdrant vector store to minimize setup time. However, for some of the same reasons, we recommend using a [qdrant cloud instance](https://qdrant.io/cloud). Like Voyage, the free tier is generous and should be sufficient for most use cases.

EOF
                exit 78
        fi
fi

exec "$@"
