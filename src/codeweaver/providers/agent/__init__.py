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

from lateimport import create_late_getattr


if TYPE_CHECKING:
    from codeweaver.providers.agent.capabilities import (
        AgentModelCapabilities,
        KnownAgentModelName,
        get_agent_capabilities_for_model,
        get_agent_model_capabilities,
    )
    from codeweaver.providers.agent.providers import (
        AgentProvider,
        get_agent_model_provider,
        infer_agent_provider_class,
        load_default_agent_providers,
    )
    from codeweaver.providers.agent.resolver import AgentCapabilityResolver, get_agent_resolver


_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "AgentModelCapabilities": (__spec__.parent, "capabilities"),
    "AgentProvider": (__spec__.parent, "providers"),
    "AgentCapabilityResolver": (__spec__.parent, "resolver"),
    "KnownAgentModelName": (__spec__.parent, "capabilities"),
    "get_agent_capabilities_for_model": (__spec__.parent, "capabilities"),
    "get_agent_model_capabilities": (__spec__.parent, "capabilities"),
    "get_agent_model_provider": (__spec__.parent, "providers"),
    "get_agent_resolver": (__spec__.parent, "resolver"),
    "infer_agent_provider_class": (__spec__.parent, "providers"),
    "load_default_agent_providers": (__spec__.parent, "providers"),
})

__getattr__ = create_late_getattr(_dynamic_imports, globals(), __name__)


__all__ = (
    "AgentCapabilityResolver",
    "AgentModelCapabilities",
    "AgentProvider",
    "KnownAgentModelName",
    "get_agent_capabilities_for_model",
    "get_agent_model_capabilities",
    "get_agent_model_provider",
    "get_agent_resolver",
    "infer_agent_provider_class",
    "load_default_agent_providers",
)


def __dir__() -> list[str]:
    """List available attributes for the agent package."""
    return list(__all__)
