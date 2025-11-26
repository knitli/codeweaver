<!-- SPDX-FileCopyrightText: 2025 Knitli Inc.
SPDX-FileContributor: Adam Poulemanos <adam@knit.li>

 SPDX-License-Identifier: MIT OR Apache-2.0
-->
# CodeWeaver Supported Providers

## Embedding Providers
- Azure
- AWS Bedrock
- Cohere
- Fastembed (`quickstart` profile's default)
- Fireworks
- Github
- Google
- Groq
- Heroku
- Hf Inference
- Mistral
- Ollama
- Openai
- Sentence Transformers [^1]
- Together
- Vercel
- Voyage (`recommended` profile's default)

## Sparse Embedding Providers
- Fastembed (`recommended` profile's default)
- Sentence Transformers [^1]

## Reranking Providers
- AWS Bedrock
- Cohere
- Fastembed (`quickstart` profile's default)
- Sentence Transformers [^1]
- Voyage (`recommended` profile's default)

## Vector Store Providers
- Memory (for testing)
- Qdrant (default for `recommended` and `quickstart`)

[^1]: Sentence Transformers requires one of the following extra install flags: `sentence-transformers`, `full`. For example: `uv pip install "codeweaver[sentence-transformers]"`
