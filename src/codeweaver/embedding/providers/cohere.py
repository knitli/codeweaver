"""Cohere embedding provider."""
# SPDX-FileCopyrightText: 2025 (c) 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
# applies to new/modified code in this directory (`src/codeweaver/embedding_providers/`)

"""
for Azure implementation, see: https://github.com/Azure/azureml-examples/blob/main/sdk/python/foundation-models/cohere/cohere-embed.ipynb

We'll need to make the provider flexible to handle both cohere.com and Azure endpoints. Bedrock uses the AWS API, but Azure uses Cohere for Cohere models.


"""
