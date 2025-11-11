# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# pyright: reportUnsupportedDunderAll=none
"""Type aliases and base models used throughout the CodeWeaver project."""

from __future__ import annotations

from importlib import import_module
from types import MappingProxyType
from typing import TYPE_CHECKING


if TYPE_CHECKING:
    from codeweaver.core.types.aliases import (
        CategoryName,
        CategoryNameT,
        DevToolName,
        DevToolNameT,
        DirectoryName,
        DirectoryNameT,
        DirectoryPath,
        DirectoryPathT,
        EmbeddingModelName,
        EmbeddingModelNameT,
        FileExt,
        FileExtensionT,
        FileGlob,
        FileGlobT,
        FileName,
        FileNameT,
        FilePath,
        FilePathT,
        FilteredKey,
        FilteredKeyT,
        LanguageName,
        LanguageNameT,
        LiteralStringT,
        LlmToolName,
        LlmToolNameT,
        ModelName,
        ModelNameT,
        RerankingModelName,
        RerankingModelNameT,
        Role,
        RoleT,
        SentinelName,
        SentinelNameT,
        ThingName,
        ThingNameT,
        ThingOrCategoryNameT,
        UUID7Hex,
        UUID7HexT,
    )
    from codeweaver.core.types.dictview import DictView
    from codeweaver.core.types.enum import (
        AnonymityConversion,
        BaseDataclassEnum,
        BaseEnum,
        BaseEnumData,
    )
    from codeweaver.core.types.models import (
        BASEDMODEL_CONFIG,
        DATACLASS_CONFIG,
        FROZEN_BASEDMODEL_CONFIG,
        BasedModel,
        DataclassSerializationMixin,
        DeserializationKwargs,
        RootedRoot,
        SerializationKwargs,
        generate_field_title,
        generate_title,
    )
    from codeweaver.core.types.sentinel import UNSET, Sentinel, Unset


_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "AnonymityConversion": (__spec__.parent, "enum"),
    "BASEDMODEL_CONFIG": (__spec__.parent, "models"),
    "BaseDataclassEnum": (__spec__.parent, "enum"),
    "BaseEnum": (__spec__.parent, "enum"),
    "BaseEnumData": (__spec__.parent, "enum"),
    "BasedModel": (__spec__.parent, "models"),
    "CategoryName": (__spec__.parent, "aliases"),
    "CategoryNameT": (__spec__.parent, "aliases"),
    "DATACLASS_CONFIG": (__spec__.parent, "models"),
    "DataclassSerializationMixin": (__spec__.parent, "models"),
    "DeserializationKwargs": (__spec__.parent, "models"),
    "DevToolName": (__spec__.parent, "aliases"),
    "DevToolNameT": (__spec__.parent, "aliases"),
    "DictView": (__spec__.parent, "dictview"),
    "DirectoryName": (__spec__.parent, "aliases"),
    "DirectoryNameT": (__spec__.parent, "aliases"),
    "DirectoryPath": (__spec__.parent, "aliases"),
    "DirectoryPathT": (__spec__.parent, "aliases"),
    "EmbeddingModelName": (__spec__.parent, "aliases"),
    "EmbeddingModelNameT": (__spec__.parent, "aliases"),
    "FROZEN_BASEDMODEL_CONFIG": (__spec__.parent, "models"),
    "FileExt": (__spec__.parent, "aliases"),
    "FileExtensionT": (__spec__.parent, "aliases"),
    "FileGlob": (__spec__.parent, "aliases"),
    "FileGlobT": (__spec__.parent, "aliases"),
    "FileName": (__spec__.parent, "aliases"),
    "FileNameT": (__spec__.parent, "aliases"),
    "FilePath": (__spec__.parent, "aliases"),
    "FilePathT": (__spec__.parent, "aliases"),
    "FilteredKey": (__spec__.parent, "aliases"),
    "FilteredKeyT": (__spec__.parent, "aliases"),
    "LanguageName": (__spec__.parent, "aliases"),
    "LanguageNameT": (__spec__.parent, "aliases"),
    "LiteralStringT": (__spec__.parent, "aliases"),
    "LlmToolName": (__spec__.parent, "aliases"),
    "LlmToolNameT": (__spec__.parent, "aliases"),
    "ModelName": (__spec__.parent, "aliases"),
    "ModelNameT": (__spec__.parent, "aliases"),
    "RerankingModelName": (__spec__.parent, "aliases"),
    "RerankingModelNameT": (__spec__.parent, "aliases"),
    "Role": (__spec__.parent, "aliases"),
    "RoleT": (__spec__.parent, "aliases"),
    "RootedRoot": (__spec__.parent, "models"),
    "Sentinel": (__spec__.parent, "sentinel"),
    "SentinelName": (__spec__.parent, "aliases"),
    "SentinelNameT": (__spec__.parent, "aliases"),
    "SerializationKwargs": (__spec__.parent, "models"),
    "ThingName": (__spec__.parent, "aliases"),
    "ThingNameT": (__spec__.parent, "aliases"),
    "ThingOrCategoryNameT": (__spec__.parent, "aliases"),
    "UNSET": (__spec__.parent, "sentinel"),
    "UUID7Hex": (__spec__.parent, "aliases"),
    "UUID7HexT": (__spec__.parent, "aliases"),
    "Unset": (__spec__.parent, "sentinel"),
    "generate_field_title": (__spec__.parent, "models"),
    "generate_title": (__spec__.parent, "models"),
})


def __getattr__(name: str) -> object:
    """Dynamically import submodules and classes for the core types package."""
    if name in _dynamic_imports:
        module_name, submodule_name = _dynamic_imports[name]
        module = import_module(f"{module_name}.{submodule_name}")
        result = getattr(module, name)
        globals()[name] = result  # Cache in globals for future access
        return result
    if globals().get(name) is not None:
        return globals()[name]
    raise AttributeError(f"module {__name__} has no attribute {name}")


__all__ = (
    "BASEDMODEL_CONFIG",
    "DATACLASS_CONFIG",
    "FROZEN_BASEDMODEL_CONFIG",
    "UNSET",
    "AnonymityConversion",
    "BaseDataclassEnum",
    "BaseEnum",
    "BaseEnumData",
    "BasedModel",
    "CategoryName",
    "CategoryNameT",
    "DataclassSerializationMixin",
    "DeserializationKwargs",
    "DevToolName",
    "DevToolNameT",
    "DictView",
    "DirectoryName",
    "DirectoryNameT",
    "DirectoryPath",
    "DirectoryPathT",
    "EmbeddingModelName",
    "EmbeddingModelNameT",
    "FileExt",
    "FileExtensionT",
    "FileGlob",
    "FileGlobT",
    "FileName",
    "FileNameT",
    "FilePath",
    "FilePathT",
    "FilteredKey",
    "FilteredKeyT",
    "LanguageName",
    "LanguageNameT",
    "LiteralStringT",
    "LlmToolName",
    "LlmToolNameT",
    "ModelName",
    "ModelNameT",
    "RerankingModelName",
    "RerankingModelNameT",
    "Role",
    "RoleT",
    "RootedRoot",
    "Sentinel",
    "SentinelName",
    "SentinelNameT",
    "SerializationKwargs",
    "ThingName",
    "ThingNameT",
    "ThingOrCategoryNameT",
    "UUID7Hex",
    "UUID7HexT",
    "Unset",
    "generate_field_title",
    "generate_title",
)


def __dir__() -> list[str]:
    """List available attributes for the core types package."""
    return list(__all__)
