# sourcery skip: avoid-single-character-names-variables
# Copyright (c) 2024 to present Pydantic Services Inc
# SPDX-License-Identifier: MIT
# Applies to original code in this directory (`src/codeweaver/embedding_providers/`) from `pydantic_ai`.
#
# SPDX-FileCopyrightText: 2025 (c) 2025 Knitli Inc.
# SPDX-License-Identifier: MIT OR Apache-2.0
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
# applies to new/modified code in this directory (`src/codeweaver/embedding_providers/`)
"""OpenAI embedding provider."""

from __future__ import annotations as _annotations


def raise_import_error() -> None:
    """Raise an import error for the OpenAI package."""
    raise ImportError(
        'Please install the `openai` package to use the OpenAI provider, \nyou can use the `openai` optional group — `pip install "codeweaver[openai]"`'
    )


try:
    from importlib.util import find_spec

    if not find_spec("openai"):
        raise_import_error()
except ImportError as e:
    raise ImportError(
        'Please install the `openai` package to use the OpenAI provider, \nyou can use the `openai` optional group — `pip install "codeweaver[openai]"`'
    ) from e
