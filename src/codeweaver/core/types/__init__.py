# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Type aliases and base models used throughout the CodeWeaver project."""

from __future__ import annotations

from types import MappingProxyType
from typing import TYPE_CHECKING

from codeweaver.common.utils.lazy_getter import create_lazy_getattr


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
    from codeweaver.core.types.dataclasses import (
        DATACLASS_CONFIG,
        BaseEnumData,
        DataclassSerializationMixin,
        DeserializationKwargs,
        SerializationKwargs,
    )
    from codeweaver.core.types.dictview import DictView
    from codeweaver.core.types.enum import AnonymityConversion, BaseDataclassEnum, BaseEnum
    from codeweaver.core.types.env import EnvFormat, EnvVarInfo
    from codeweaver.core.types.models import (
        BASEDMODEL_CONFIG,
        FROZEN_BASEDMODEL_CONFIG,
        BasedModel,
        RootedRoot,
    )
    from codeweaver.core.types.sentinel import UNSET, Sentinel, Unset
    from codeweaver.core.types.utils import generate_field_title, generate_title


_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "AnonymityConversion": (__spec__.parent, "enum"),
    "BASEDMODEL_CONFIG": (__spec__.parent, "models"),
    "BaseDataclassEnum": (__spec__.parent, "enum"),
    "BaseEnum": (__spec__.parent, "enum"),
    "BaseEnumData": (__spec__.parent, "dataclasses"),
    "BasedModel": (__spec__.parent, "models"),
    "CategoryName": (__spec__.parent, "aliases"),
    "CategoryNameT": (__spec__.parent, "aliases"),
    "DATACLASS_CONFIG": (__spec__.parent, "dataclasses"),
    "DataclassSerializationMixin": (__spec__.parent, "dataclasses"),
    "DeserializationKwargs": (__spec__.parent, "dataclasses"),
    "DevToolName": (__spec__.parent, "aliases"),
    "DevToolNameT": (__spec__.parent, "aliases"),
    "DictView": (__spec__.parent, "dictview"),
    "DirectoryName": (__spec__.parent, "aliases"),
    "DirectoryNameT": (__spec__.parent, "aliases"),
    "DirectoryPath": (__spec__.parent, "aliases"),
    "DirectoryPathT": (__spec__.parent, "aliases"),
    "EmbeddingModelName": (__spec__.parent, "aliases"),
    "EmbeddingModelNameT": (__spec__.parent, "aliases"),
    "EnvFormat": (__spec__.parent, "env"),
    "EnvVarInfo": (__spec__.parent, "env"),
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
    "SerializationKwargs": (__spec__.parent, "dataclasses"),
    "ThingName": (__spec__.parent, "aliases"),
    "ThingNameT": (__spec__.parent, "aliases"),
    "ThingOrCategoryNameT": (__spec__.parent, "aliases"),
    "UNSET": (__spec__.parent, "sentinel"),
    "UUID7Hex": (__spec__.parent, "aliases"),
    "UUID7HexT": (__spec__.parent, "aliases"),
    "Unset": (__spec__.parent, "sentinel"),
    "generate_field_title": (__spec__.parent, "utils"),
    "generate_title": (__spec__.parent, "utils"),
})


__getattr__ = create_lazy_getattr(_dynamic_imports, globals(), __name__)

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
    "EnvFormat",
    "EnvVarInfo",
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
