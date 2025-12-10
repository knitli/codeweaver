# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Base dataclass and model implementations for CodeWeaver."""

from __future__ import annotations

import abc

from collections.abc import Generator, Iterator, Sequence
from typing import Any, cast, override

from pydantic import BaseModel, ConfigDict, RootModel

from codeweaver.core.types.aliases import FilteredKey, FilteredKeyT, LiteralStringT
from codeweaver.core.types.enum import AnonymityConversion
from codeweaver.core.types.utils import (
    clean_sentinel_from_schema,
    generate_field_title,
    generate_title,
)


FILTERED_KEYS: frozenset[FilteredKey] = frozenset({FilteredKey("api_key")})


# ================================================
# *      Pydantic Base Implementations
# ================================================

BASEDMODEL_CONFIG = ConfigDict(
    arbitrary_types_allowed=True,
    field_title_generator=generate_field_title,
    model_title_generator=generate_title,
    serialize_by_alias=True,
    str_strip_whitespace=True,
    use_attribute_docstrings=True,
    validate_by_alias=True,
    validate_by_name=True,
    cache_strings="all",
    json_schema_extra=clean_sentinel_from_schema,
)
FROZEN_BASEDMODEL_CONFIG = BASEDMODEL_CONFIG | ConfigDict(frozen=True)


class RootedRoot[RootType: Sequence[Any]](RootModel[Sequence[Any]]):
    """A pre-customized pydantic RootModel with common configuration for CodeWeaver."""

    model_config = BASEDMODEL_CONFIG

    root: RootType

    @override
    def __iter__(self) -> Generator[Any]:
        """Iterate over the root items."""
        yield from self.root

    def __getitem__(self, index: int) -> Any:
        """Get an item by index."""
        return self.root[index]

    def __len__(self) -> int:
        """Get the length of the root."""
        return len(self.root)

    def __contains__(self, item: Any) -> bool:
        """Check if an item is in the root."""
        return item in self.root

    def __next__(self) -> Any:
        """Get the next item in the root."""
        return next(iter(self.root))

    def serialize_for_cli(self) -> list[Any]:
        """Serialize the model for CLI output."""
        return [
            item.serialize_for_cli() if hasattr(item, "serialize_for_cli") else item
            for item in self.root
        ]


class BasedModel(BaseModel):
    """A baser `BaseModel` for all models in the CodeWeaver project."""

    model_config = BASEDMODEL_CONFIG

    def serialize_for_cli(self) -> dict[str, Any]:
        """Serialize the model for CLI output."""
        fields = set(type(self).model_fields.keys()) | set(type(self).model_computed_fields.keys())
        self_map: dict[str, Any] = {}
        for field in fields:
            if (attr := getattr(self, field, None)) and hasattr(attr, "serialize_for_cli"):
                self_map[field] = attr.serialize_for_cli()
            elif isinstance(attr, Sequence | Iterator) and not isinstance(attr, str):
                self_map[field] = [
                    item.serialize_for_cli()  # type: ignore
                    if hasattr(item, "serialize_for_cli")  # type: ignore
                    else item
                    for item in attr  # type: ignore
                ]
        # Get model dump, handling potential Missing/Undefined values
        base_dict = self.model_dump(mode="python", round_trip=True, exclude_none=True)
        # If model_dump returns a non-dict (like Missing), use empty dict
        if not isinstance(base_dict, dict):
            base_dict = {}
        return base_dict | self_map

    @abc.abstractmethod
    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion] | None:
        """Get telemetry keys for the dataclass."""
        raise NotImplementedError("Subclasses must implement _telemetry_keys method.")

    def _telemetry_handler(self, _serialized_self: dict[str, Any], /) -> dict[str, Any]:
        """An optional handler for subclasses to modify telemetry serialization. By default, it returns an empty dict.

        We use any returned keys as overrides for the serialized_self.
        """
        return {}

    def serialize_for_telemetry(self) -> dict[str, Any]:
        """Serialize the model for telemetry output, filtering sensitive keys."""
        from codeweaver.core.types.enum import AnonymityConversion

        excludes: set[str] = set()
        default_group: dict[FilteredKeyT, Any] = {}
        if telemetry_keys := (self._telemetry_keys() or {}):
            excludes = {
                str(key)
                for key, conversion in telemetry_keys.items()
                if conversion == AnonymityConversion.FORBIDDEN
            }
            default_group = {
                key: conversion.filtered(getattr(self, str(key), None))
                for key, conversion in telemetry_keys.items()
                if conversion != AnonymityConversion.FORBIDDEN
            }
        data = self.model_dump(round_trip=True, exclude_none=True, exclude=excludes)
        filtered_group: dict[str, Any] = self._telemetry_handler(data)
        return {
            key: (
                # First priority: handler override
                filtered_group[key]
                if key in filtered_group
                # Second priority: filtered conversion from telemetry_keys
                else default_group.get(FilteredKey(cast(LiteralStringT, key)), value)
            )
            for key, value in data.items()
        }


__all__ = ("BASEDMODEL_CONFIG", "FROZEN_BASEDMODEL_CONFIG", "BasedModel", "RootedRoot")
