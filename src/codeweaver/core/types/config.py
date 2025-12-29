# SPDX-License_Identifier: MIT OR Apache-2.0
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
"""Foundational types for CodeWeaver's configuration system. These are building-block style types.

Any concrete types are in the configuration modules.
"""

from __future__ import annotations

import logging

from collections import defaultdict
from collections.abc import Callable
from typing import Any, Literal, LiteralString, NamedTuple, TypedDict, TypeVar, cast

from codeweaver.core.types.enum import BaseEnum


logger = logging.getLogger(__name__)

T = TypeVar("T")
U = TypeVar("U")


class ConfigSourceType(BaseEnum):
    """An enumeration of possible configuration sources."""

    MODEL_SETTINGS = "model_settings"
    """Configuration sourced from a model's settings (like `EmbeddingModelSettings`)."""

    PROVIDER_SETTINGS = "provider_settings"
    """Configuration sourced from a provider's settings (like `EmbeddingProviderSettings`)."""

    PROVIDER_SPECIFIC_SETTINGS = "provider_specific_settings"
    """Some providers have unique settings objects for their specific configurations; this is for those. For example, `AWSBedrockProviderSettings`."""

    CAPABILITIES = "capabilities"
    """Setting is from a model's capabilities object (for static capabilities that can't be set, like context window size)."""


class ConfigTargetType(BaseEnum):
    """An enumeration of possible configuration targets."""

    PROVIDER = "provider_settings"
    """Setting provided to a provider class's constructor."""

    CLIENT = "client_settings"
    """Setting provided to a provider client's constructor (like a Boto3 client)."""

    MODEL = "model_settings"
    """For providers with model objects, like SentenceTransformers models, settings provided to the model's constructor."""

    FUNCTION = "function_settings"
    """For settings provided to the core function call to the client (like `embed` or `rerank` calls)."""


class FunctionKind(BaseEnum):
    """The kind of function that a setting applies to."""

    TEXT_EMBEDDING = "text_embedding"
    """Settings for text embedding functions."""

    QUERY_EMBEDDING = "query_embedding"
    """Settings for query embedding functions."""

    EMBEDDING = "embedding"
    """Settings for any embedding function."""

    RERANKING = "reranking"
    """Settings for reranking functions."""

    UPSERT = "upsert"
    """Settings for upsert functions (vector stores)."""

    CREATE_COLLECTION = "create_collection"
    """Settings for create collection functions (vector stores)."""


def deep_merge(base: dict[str, Any], update: dict[str, Any]) -> dict[str, Any]:
    """Recursively merge `update` into `base`, modifying `base` in place.

    For nested dicts, values are merged rather than replaced. For all other types,
    values from `update` overwrite values in `base`.

    Args:
        base: The base dictionary to merge into.
        update: The dictionary to merge from.

    Returns:
        The merged dictionary (same object as `base`).
    """
    for key, value in update.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            deep_merge(base[key], value)
        else:
            base[key] = value
    return base


class SettingBridge(NamedTuple):
    """A bridge or mapping between a codeweaver setting and an external configuration source (like a model or provider).

    Anything can provide a `SettingBridge`, and they are used to translate settings from one place to another. Typically, these are defined as either a ClassVar or as an attribute for an implementing class.
    """

    source: LiteralString
    """The source setting name for the origin (i.e. a CodeWeaver setting name)."""
    source_type: ConfigSourceType
    """The type of source for the setting (i.e. whether it's from model settings, provider settings, etc)."""

    target: LiteralString | list[LiteralString] | None
    """The target setting name for the destination (i.e. a provider's client setting name). If a list, the values are names of nested keys to reach the target setting.

    If `None`, there is no corresponding target setting, and the bridge is only for informational purposes.
    """

    target_type: ConfigTargetType | None
    """The type of target for the setting (i.e. whether it's for a provider, client, model, or function)."""

    function_kind: FunctionKind | None = None
    """The kind of function this setting applies to (like text embedding, reranking, etc). If `None`, applies to all function kinds. Only relevant if target_type is `ConfigTargetType.FUNCTION`."""

    transform: Callable[[T], U] | None = None
    """Optional transformation from CodeWeaver's value to the provider's expected format.

    Example: `lambda v: "END" if v else "NONE"` for Cohere's truncation enum.
    """

    specific_source: type | str | None = None
    """For provider-specific settings, the specific provider settings type to use (like `AWSBedrockProviderSettings`).

    If a string, the import path to the specific type (can be used to prevent circular imports).
    """

    is_required: bool = False
    """Whether this bridge is required to have a value when used. If `True` and no value is provided, an error should be raised."""

    @property
    def has_target(self) -> bool:
        """Whether this bridge has a target setting defined."""
        return self.target is not None and self.target_type is not None

    @property
    def is_nested_target(self) -> bool:
        """Whether this bridge's target is a nested setting (i.e. a list of keys)."""
        return isinstance(self.target, list)

    def as_kwarg(self, item: tuple[str, Any]) -> dict[str, Any]:
        """Convert an item-like tuple to a kwarg dictionary item for use in function calls.

        Args:
            item: A tuple of (key, value) where key should match `self.source`.

        Returns:
            A dictionary suitable for use as keyword arguments. For nested targets,
            returns a nested dictionary structure.
        """
        key, value = item
        if key != self.source:
            logger.warning("Key '%s' does not match source '%s' in SettingBridge", key, self.source)
            return {}
        if self.transform:
            value = self.transform(value)
        if not self.has_target:
            return {}
        if self.is_nested_target:
            return self._build_nested_dict_from_kwargs(value)
        return {cast(str, self.target): value}

    def _build_nested_dict_from_kwargs(self, value: str | Any) -> dict[str, Any]:
        """Build a nested dictionary from the target list of keys."""
        # Build nested dictionary
        nested_kwargs: dict[str, Any] = {}
        current = nested_kwargs
        target_parts = cast(list[str], self.target)
        for part in target_parts[:-1]:
            current[part] = {}
            current = current[part]
        current[target_parts[-1]] = value
        return nested_kwargs


class BridgeSource(NamedTuple):
    """A NamedTuple representing the source of a bridged setting."""

    bridges: list[SettingBridge]
    """A list of SettingBridges for the source."""

    source: Any
    """The source object to read values from."""

    use_keys: bool = False
    """Whether to use keys from the source (if it's a dict-like object), or to use property access."""

    def extract_values(self) -> dict[str, Any]:
        """Extract values from the source object for all bridges.

        Returns:
            A dictionary mapping source names to their values.
        """
        values: dict[str, Any] = {}
        for bridge in self.bridges:
            try:
                if self.use_keys:
                    value = self.source.get(bridge.source)
                else:
                    value = getattr(self.source, bridge.source, None)
                if value is not None:
                    values[bridge.source] = value
            except (KeyError, AttributeError, TypeError):
                continue
        return values


class BridgedKwargsDict(TypedDict):
    """A TypedDict representing a dictionary of bridged keyword arguments."""

    provider_settings: dict[str, Any]
    """A dictionary of keyword arguments for provider settings."""

    client_settings: dict[str, Any]
    """A dictionary of keyword arguments for client settings."""

    model_settings: dict[str, Any]
    """A dictionary of keyword arguments for model settings."""

    function_settings: dict[str, Any]
    """A dictionary of keyword arguments for function settings."""


class BridgedSettings(NamedTuple):
    """A NamedTuple representing settings that have been bridged from one source to another.

    This class holds the bridge definitions (not the values). Values are passed at
    resolution time via `to_setting()` or `to_kwargs_dict()`.
    """

    provider_settings: list[SettingBridge] | None = None
    """A list of SettingBridges for provider settings."""

    client_settings: list[SettingBridge] | None = None
    """A list of SettingBridges for client settings."""

    model_settings: list[SettingBridge] | None = None
    """A list of SettingBridges for model settings."""

    function_settings: list[SettingBridge] | None = None
    """A list of SettingBridges for function settings."""

    @classmethod
    def sort_bridges(
        cls, sources: list[BridgeSource]
    ) -> dict[ConfigTargetType, list[SettingBridge] | None]:
        """Sort bridges from a list of BridgeSources into a dictionary keyed by ConfigTargetType.

        Args:
            sources: A list of BridgeSource objects containing bridges to sort.

        Returns:
            A dictionary mapping each ConfigTargetType to its list of bridges.
            Types with no bridges will have `None` as their value.
        """
        sorted_bridges: dict[ConfigTargetType, list[SettingBridge]] = defaultdict(list)
        for source in sources:
            for bridge in source.bridges:
                if bridge.target_type is not None:
                    sorted_bridges[bridge.target_type].append(bridge)
        # Return dict with None for any target types that have no bridges
        return {k: sorted_bridges.get(k) for k in ConfigTargetType}

    @classmethod
    def from_sources(cls, sources: list[BridgeSource] | None = None) -> BridgedSettings:
        """Create a BridgedSettings object from a list of BridgeSources.

        Args:
            sources: A list of BridgeSource objects. If None, returns empty BridgedSettings.

        Returns:
            A BridgedSettings instance with bridges sorted by target type.
        """
        if sources is None:
            return cls()
        sorted_bridges = cls.sort_bridges(sources)
        return cls(**{k.value: v for k, v in sorted_bridges.items()})

    def to_setting(
        self,
        settings_type: ConfigTargetType
        | Literal["provider_settings", "client_settings", "model_settings", "function_settings"],
        values: dict[str, Any],
    ) -> dict[str, Any]:
        """Convert the bridged settings to a dictionary of settings for the given ConfigTargetType.

        Uses deep merging to properly handle multiple bridges targeting different
        leaves of the same nested structure.

        Args:
            settings_type: The type of settings to convert to.
            values: A dictionary of values to use for the source settings.
                The dictionary keys should match the source names in the SettingBridges.

        Returns:
            A dictionary of settings ready to be passed as keyword arguments.
        """
        setting_key = (
            settings_type.value if isinstance(settings_type, ConfigTargetType) else settings_type
        )
        bridges = self._asdict()[setting_key]
        if not bridges:
            return {}

        result: dict[str, Any] = {}
        for bridge in bridges:
            if bridge.source in values:
                kwarg = bridge.as_kwarg((bridge.source, values[bridge.source]))
                deep_merge(result, kwarg)
        return result

    def to_kwargs_dict(self, values: dict[str, Any]) -> BridgedKwargsDict:
        """Convert the bridged settings to a BridgedKwargsDict.

        Args:
            values: A dictionary of values to use for the source settings.
                The dictionary keys should match the source names in the SettingBridges.

        Returns:
            A BridgedKwargsDict with settings organized by target type.
        """
        return BridgedKwargsDict(
            provider_settings=self.to_setting(ConfigTargetType.PROVIDER, values),
            client_settings=self.to_setting(ConfigTargetType.CLIENT, values),
            model_settings=self.to_setting(ConfigTargetType.MODEL, values),
            function_settings=self.to_setting(ConfigTargetType.FUNCTION, values),
        )


__all__ = (
    "BridgeSource",
    "BridgedKwargsDict",
    "BridgedSettings",
    "ConfigSourceType",
    "ConfigTargetType",
    "SettingBridge",
    "deep_merge",
)
