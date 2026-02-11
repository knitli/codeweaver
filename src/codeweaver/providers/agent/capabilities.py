# SPDX-FileCopyrightText: 2026 Knitli Inc.
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Agent model capabilities.

To maintain consistent naming across CodeWeaver, we re-export `ModelProfile`s from `pydantic_ai.profiles` as `AgentModelCapabilities` and the `ModelProfileSpec` type alias as `AgentModelCapabilitiesT`.
"""

import contextlib
import importlib

from functools import cache

from pydantic_ai.models import KnownModelName as KnownAgentModelName
from pydantic_ai.profiles import ModelProfile as AgentModelCapabilities
from pydantic_ai.profiles import ModelProfileSpec as AgentModelCapabilitiesT

from codeweaver.core.constants import PYDANTIC_AI_MODEL_CAPABILITIES_PROVIDERS


def _parse_model_name(name: str) -> tuple[str, str]:
    provider, model = name.split(":", 1)
    model_lower = model.lower()
    if provider.startswith("gateway"):
        provider = provider.split("/", 1)[-1]
    if "gpt-oss" in model_lower:
        provider = "harmony"
    elif provider.startswith("google"):
        provider = "google"
    elif "provider" == "groq":
        return "groq", model
    if "amazon" in model_lower or "nova" in model_lower:
        provider = "amazon"
    elif "claude" in model_lower:
        provider = "anthropic"
    elif "mistral" in model_lower:
        provider = "mistral"
    elif "cohere" in model_lower or "command" in model_lower:
        provider = "cohere"
    elif "deepseek" in model_lower:
        provider = "deepseek"
    return provider, model


def _attempt_to_get_profile(provider: str, full_name: str) -> AgentModelCapabilities | None:
    with contextlib.suppress(ImportError):
        module = importlib.import_module(f"pydantic_ai.profiles.{provider}")
        if profile_getter := getattr(module, f"{provider}_model_profile", None):
            return profile_getter(full_name)
    return None


@cache
def get_agent_model_capabilities() -> dict[KnownAgentModelName, AgentModelCapabilities]:
    """Get all available model profiles."""
    model_names = [name for name in KnownAgentModelName.__value__.__args__ if name != "test"]
    profiles: dict[KnownAgentModelName, AgentModelCapabilities] = {}
    for name in model_names:
        provider, _model = _parse_model_name(name)
        try:
            profile = None
            module = importlib.import_module(f"pydantic_ai.profiles.{provider}")
            if profile_getter := getattr(module, f"{provider}_model_profile", None):
                profile = profile_getter(name)
            profile = profile or AgentModelCapabilities()
            profiles[name] = profile
        except ImportError:
            continue
    return profiles


def get_agent_capabilities_for_model(name: KnownAgentModelName | str) -> AgentModelCapabilities:
    """Get the profile for a specific model."""
    if known_capability := get_agent_model_capabilities().get(name, AgentModelCapabilities()):
        return known_capability
    provider, _model = _parse_model_name(name)
    if profile := _attempt_to_get_profile(provider, name):
        return profile
    return AgentModelCapabilities()


_model_providers = PYDANTIC_AI_MODEL_CAPABILITIES_PROVIDERS

__all__ = (
    "AgentModelCapabilities",
    "AgentModelCapabilitiesT",
    "get_agent_capabilities_for_model",
    "get_agent_model_capabilities",
)
