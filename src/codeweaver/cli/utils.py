# SPDX-FileCopyrightText: 2026 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""CLI utility functions."""

from __future__ import annotations

from typing import TYPE_CHECKING

from codeweaver.core.utils import has_package


if TYPE_CHECKING:
    from codeweaver.core import Provider, ProviderKind


def check_provider_package_available(provider: Provider, kind: ProviderKind) -> bool:
    """Check if the required package for a provider is installed.

    This replaces the registry.is_provider_available logic.
    """
    from codeweaver.core.types.provider import SDK_MAP, SDKClient

    # Get SDK client(s) for the provider
    sdk_clients = SDK_MAP.get((provider, kind))
    if not sdk_clients:
        # Fallback to defaults or assume available (e.g. Memory)
        return provider.value == "memory"
    # Normalize to tuple
    if not isinstance(sdk_clients, tuple):
        sdk_clients = (sdk_clients,)

    # Map SDKClient to package name
    client_to_package = {
        SDKClient.BEDROCK: "boto3",
        SDKClient.COHERE: "cohere",
        SDKClient.FASTEMBED: "fastembed",
        SDKClient.GOOGLE: "google.genai",
        SDKClient.GROQ: "groq",
        SDKClient.HUGGINGFACE_INFERENCE: "huggingface_hub",
        SDKClient.MISTRAL: "mistralai",
        SDKClient.OPENAI: "openai",
        SDKClient.QDRANT: "qdrant_client",
        SDKClient.SENTENCE_TRANSFORMERS: "sentence_transformers",
        SDKClient.VOYAGE: "voyageai",
    }

    # Check if all required packages are available
    for client in sdk_clients:
        pkg_name = client_to_package.get(client)
        if not pkg_name:
            continue
        if not has_package(pkg_name):
            # Special case for fastembed-gpu fallback
            if pkg_name == "fastembed" and has_package("fastembed_gpu"):
                continue
            return False

    return True
