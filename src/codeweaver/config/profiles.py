# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Prebuilt settings profiles for CodeWeaver quick setup."""


def recommended_default() -> CodeWeaverProvidersDict:
    """Recommended default settings profile."""
    return {
        "providers": {
            "llm": {"provider": "openai", "model": "gpt-4-turbo", "temperature": 0.2},
            "embedding": {"provider": "openai", "model": "text-embedding-3-small"},
            "vector_store": {"provider": "pinecone"},
        }
    }
