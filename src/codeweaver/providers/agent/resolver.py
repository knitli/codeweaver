# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Resolver implementation for agentic models."""

from collections.abc import Sequence
from types import MappingProxyType

from codeweaver.providers.agent.capabilities import (
    AgentModelCapabilities,
    KnownAgentModelName,
    get_agent_capabilities_for_model,
    get_agent_model_capabilities,
)
from codeweaver.providers.types import BaseResolver


class AgentCapabilityResolver(BaseResolver[AgentModelCapabilities]):
    """Resolver for agent model capabilities."""

    def __init__(self) -> None:
        """Initialize the resolver."""
        super().__init__()
        self._capabilities_by_name: MappingProxyType[
            KnownAgentModelName | str, AgentModelCapabilities
        ] = MappingProxyType({})

    def _ensure_loaded(self) -> None:
        """Ensure that the resolver has loaded all model profiles."""
        if not self._loaded:
            self._load()
            self._loaded = True

    def _load(self) -> None:
        """Load all model profiles into the resolver."""
        self._capabilities_by_name = MappingProxyType(get_agent_model_capabilities())

    def resolve(self, model_name: str) -> AgentModelCapabilities:
        """Resolve the capabilities for a given model name."""
        self._ensure_loaded()
        if found_capability := self._capabilities_by_name.get(model_name):
            return found_capability
        try:
            profile = get_agent_capabilities_for_model(model_name)
        except (ValueError, KeyError) as e:
            raise ValueError(
                "We could find or create capabilities for the specified model. Please make sure it's in the correct format."
            ) from e
        else:
            self._capabilities_by_name = MappingProxyType({
                **self._capabilities_by_name,
                model_name: profile,
            })
            return profile

    def all_model_names(self) -> Sequence[str]:
        """Return a list of all known model names."""
        self._ensure_loaded()
        return list(self._capabilities_by_name)


def get_agent_resolver() -> AgentCapabilityResolver:
    """Get a singleton instance of the agent capability resolver."""
    return AgentCapabilityResolver()


__all__ = ("AgentCapabilityResolver", "get_agent_resolver")
