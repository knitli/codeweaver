# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Agent provider package. Re-exports agent provider classes, toolsets, and utilities from Pydantic AI.

The agent package is a thin wrapper around Pydantic AI's agent capabilities, aligning its organization and naming conventions with CodeWeaver's architecture.
"""

from collections.abc import Callable
from typing import Any

from codeweaver.providers.agent.agent_models import (
    AgentModel,
    AgentModelSettings,
    DownloadedItem,
    KnownAgentModelName,
    cached_async_http_client,
    download_item,
    infer_model,
    override_allow_model_requests,
)
from codeweaver.providers.agent.agent_providers import (
    AbstractToolset,
    AgentProvider,
    CombinedToolset,
    ExternalToolset,
    FilteredToolset,
    FunctionToolset,
    PrefixedToolset,
    PreparedToolset,
    RenamedToolset,
    ToolsetTool,
    WrapperToolset,
    get_agent_model_provider,
    infer_agent_provider_class,
    load_default_agent_providers,
)


type AgentProfile = Any
type AgentProfileSpec = Callable[[str], Any] | Any | None

__all__ = (
    "AbstractToolset",
    "AgentModel",
    "AgentModelSettings",
    "AgentProfile",
    "AgentProvider",
    "CombinedToolset",
    "DownloadedItem",
    "ExternalToolset",
    "FilteredToolset",
    "FunctionToolset",
    "KnownAgentModelName",
    "PrefixedToolset",
    "PreparedToolset",
    "RenamedToolset",
    "ToolsetTool",
    "WrapperToolset",
    "cached_async_http_client",
    "download_item",
    "get_agent_model_provider",
    "infer_agent_provider_class",
    "infer_model",
    "load_default_agent_providers",
    "override_allow_model_requests",
)
