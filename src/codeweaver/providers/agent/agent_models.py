# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Re-exports for agent models from pydantic_ai."""

from pydantic_ai.models import (
    DownloadedItem,
    cached_async_http_client,
    download_item,
    infer_model,
    override_allow_model_requests,
)
from pydantic_ai.models import KnownModelName as KnownAgentModelName
from pydantic_ai.settings import ModelSettings as AgentModelSettings


__all__ = (
    "AgentModelSettings",
    "DownloadedItem",
    "KnownAgentModelName",
    "cached_async_http_client",
    "download_item",
    "infer_model",
    "override_allow_model_requests",
)
