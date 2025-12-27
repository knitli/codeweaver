# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Agent provider package. Re-exports agent provider classes, toolsets, and utilities from Pydantic AI.

The agent package is a thin wrapper around Pydantic AI's agent capabilities, aligning its organization and naming conventions with CodeWeaver's architecture.
"""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from codeweaver.core import create_lazy_getattr


if TYPE_CHECKING:
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

_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "AbstractToolset": (__spec__.parent, "agent_providers"),
    "AgentModel": (__spec__.parent, "agent_models"),
    "AgentModelSettings": (__spec__.parent, "agent_models"),
    "AgentProvider": (__spec__.parent, "agent_providers"),
    "CombinedToolset": (__spec__.parent, "agent_providers"),
    "DownloadedItem": (__spec__.parent, "agent_models"),
    "ExternalToolset": (__spec__.parent, "agent_providers"),
    "FilteredToolset": (__spec__.parent, "agent_providers"),
    "FunctionToolset": (__spec__.parent, "agent_providers"),
    "KnownAgentModelName": (__spec__.parent, "agent_models"),
    "PrefixedToolset": (__spec__.parent, "agent_providers"),
    "PreparedToolset": (__spec__.parent, "agent_providers"),
    "RenamedToolset": (__spec__.parent, "agent_providers"),
    "ToolsetTool": (__spec__.parent, "agent_providers"),
    "WrapperToolset": (__spec__.parent, "agent_providers"),
    "cached_async_http_client": (__spec__.parent, "agent_models"),
    "download_item": (__spec__.parent, "agent_models"),
    "get_agent_model_provider": (__spec__.parent, "agent_providers"),
    "infer_agent_provider_class": (__spec__.parent, "agent_providers"),
    "infer_model": (__spec__.parent, "agent_models"),
    "load_default_agent_providers": (__spec__.parent, "agent_providers"),
    "override_allow_model_requests": (__spec__.parent, "agent_models"),
})

__getattr__ = create_lazy_getattr(_dynamic_imports, globals(), __name__)


__all__ = (
    "AbstractToolset",
    "AgentModel",
    "AgentModelSettings",
    "AgentProfile",
    "AgentProfileSpec",
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


def __dir__() -> list[str]:
    """List available attributes for the agent package."""
    return list(__all__)
