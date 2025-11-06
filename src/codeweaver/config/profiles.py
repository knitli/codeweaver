# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Prebuilt settings profiles for CodeWeaver quick setup.

A few important things to note about profiles (or any provider settings):
- Most providers are *not* available with the default installation of CodeWeaver. CodeWeaver has multiple install paths that include different sets of providers. The `recommended` install flag (`pip install codeweaver[recommended]`) includes *most* of the providers available in CodeWeaver, but not all.
The `full` or `full-gpu` install flags (`pip install codeweaver[full]` or `pip install codeweaver[full-gpu]`) include *all* providers, and all optional dependencies, such as auth providers and GPU support (for the gpu flag).
The recommended flag gives you access to:
    - All current vector, agent and data providers
    - All embedding and reranking providers except for Sentence Transformers (because these install paths are aligned with pydantic-ai's default dependencies, and Sentence Transformers is not a default dependency of pydantic-ai).
- A-la-Carte installations: You can also use the `required-core` install flag (`pip install codeweaver[required-core]`) to install only the core dependencies of CodeWeaver, and then add individual providers using their own install flags (all prefixed with `provider-`), like:
    `pip install codeweaver[required-core,provider-openai,provider-qdrant]`

"""

from codeweaver.config.providers import (
    AgentProviderSettings,
    DataProviderSettings,
    EmbeddingProviderSettings,
    ProviderSettingsDict,
    RerankingProviderSettings,
    VectorStoreProviderSettings,
)


def recommended_default() -> ProviderSettingsDict:
    """Recommended default settings profile.

    This profile leans towards high-quality providers, but without excessive cost or setup.
    """
    from codeweaver.providers.provider import Provider

    return ProviderSettingsDict(
        embedding=(
            EmbeddingProviderSettings(
                provider=Provider.VOYAGE, enabled=True, model="voyage-code-3"
            ),
        ),
        reranking=(
            RerankingProviderSettings(
                provider=Provider.VOYAGE, enabled=True, model="voyage-rerank-2.5"
            ),
        ),
        agent=(
            AgentProviderSettings(
                provider=Provider.ANTHROPIC, enabled=True, model="claude-haiku-4.5"
            ),
        ),
        data=(DataProviderSettings(enabled=True),),
        vector=(VectorStoreProviderSettings(provider=Provider.QDRANT, enabled=True),),
    )
