# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# pyright: reportUnsupportedDunderAll=none
"""Global type definitions for CodeWeaver.

We usually try to keep types close to where they are used, but some types
are used so widely that it makes sense to define them globally here.
"""

from importlib import import_module
from types import MappingProxyType


_dynamic_imports: MappingProxyType[str, tuple[str, str]] = MappingProxyType({
    "BASEDMODEL_CONFIG": (__spec__.parent, "types"),
    "DATACLASS_CONFIG": (__spec__.parent, "types"),
    "FROZEN_BASEDMODEL_CONFIG": (__spec__.parent, "types"),
    "UNSET": (__spec__.parent, "types"),
    "AnonymityConversion": (__spec__.parent, "types"),
    "BaseDataclassEnum": (__spec__.parent, "types"),
    "BaseEnum": (__spec__.parent, "types"),
    "BaseEnumData": (__spec__.parent, "types"),
    "BasedModel": (__spec__.parent, "types"),
    "CategoryName": (__spec__.parent, "types"),
    "CategoryNameT": (__spec__.parent, "types"),
    "DataclassSerializationMixin": (__spec__.parent, "types"),
    "DeserializationKwargs": (__spec__.parent, "types"),
    "DevToolName": (__spec__.parent, "aliases"),
    "DevToolNameT": (__spec__.parent, "aliases"),
    "DirectoryName": (__spec__.parent, "aliases"),
    "DirectoryNameT": (__spec__.parent, "aliases"),
    "DirectoryPath": (__spec__.parent, "aliases"),
    "DirectoryPathT": (__spec__.parent, "aliases"),
    "EmbeddingModelName": (__spec__.parent, "aliases"),
    "EmbeddingModelNameT": (__spec__.parent, "aliases"),
    "ExtLangPair": (__spec__.parent, "metadata"),
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
    "RootedRoot": (__spec__.parent, "types"),
    "Sentinel": (__spec__.parent, "sentinel"),
    "SentinelName": (__spec__.parent, "aliases"),
    "SerializationKwargs": (__spec__.parent, "types"),
    "ThingName": (__spec__.parent, "aliases"),
    "ThingNameT": (__spec__.parent, "aliases"),
    "Unset": (__spec__.parent, "sentinel"),
    "generate_field_title": (__spec__.parent, "types"),
    "generate_title": (__spec__.parent, "types"),
    "ChunkSequence": (__spec__.parent, "chunks"),
    "CodeChunk": (__spec__.parent, "chunks"),
    "CodeChunkDict": (__spec__.parent, "chunks"),
    "SearchResult": (__spec__.parent, "chunks"),
    "SerializedCodeChunk": (__spec__.parent, "chunks"),
    "StructuredDataInput": (__spec__.parent, "chunks"),
    "DictView": (__spec__.parent, "dictview"),
    "DiscoveredFile": (__spec__.parent, "discovery"),
    "Chunker": (__spec__.parent, "language"),
    "ConfigLanguage": (__spec__.parent, "language"),
    "ConfigNamePair": (__spec__.parent, "language"),
    "ExtPair": (__spec__.parent, "metadata"),
    "LanguageConfigFile": (__spec__.parent, "language"),
    "SemanticSearchLanguage": (__spec__.parent, "language"),
    "find_config_paths": (__spec__.parent, "language"),
    "has_semantic_extension": (__spec__.parent, "language"),
    "is_semantic_config_ext": (__spec__.parent, "language"),
    "language_from_config_file": (__spec__.parent, "language"),
    "languages_present_from_configs": (__spec__.parent, "language"),
    "Metadata": (__spec__.parent, "metadata"),
    "ChunkKind": (__spec__.parent, "metadata"),
    "ChunkSource": (__spec__.parent, "metadata"),
    "ExtKind": (__spec__.parent, "metadata"),
    "SemanticMetadata": (__spec__.parent, "metadata"),
    "Span": (__spec__.parent, "spans"),
    "SpanGroup": (__spec__.parent, "spans"),
    "SpanTuple": (__spec__.parent, "spans"),
    "BlakeHashKey": (__spec__.parent, "stores"),
    "BlakeKey": (__spec__.parent, "stores"),
    "BlakeStore": (__spec__.parent, "stores"),
    "StoreDict": (__spec__.parent, "stores"),
    "UUIDStore": (__spec__.parent, "stores"),
    "make_blake_store": (__spec__.parent, "stores"),
    "make_uuid_store": (__spec__.parent, "stores"),
    "to_uuid": (__spec__.parent, "stores"),
})
"""Dynamically import submodules and classes for the core types package.

Maps class/function/type names to their respective module paths for lazy loading.
"""


def __getattr__(name: str) -> object:
    """Dynamically import submodules and classes for the semantic package."""
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
    "BlakeHashKey",
    "BlakeKey",
    "BlakeStore",
    "CategoryName",
    "CategoryNameT",
    "ChunkKind",
    "ChunkSequence",
    "ChunkSource",
    "Chunker",
    "CodeChunk",
    "CodeChunkDict",
    "ConfigLanguage",
    "ConfigNamePair",
    "DataclassSerializationMixin",
    "DevToolName",
    "DevToolNameT",
    "DictView",
    "DirectoryName",
    "DirectoryNameT",
    "DirectoryPath",
    "DirectoryPathT",
    "DiscoveredFile",
    "EmbeddingModelName",
    "EmbeddingModelNameT",
    "ExtKind",
    "ExtLangPair",
    "ExtPair",
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
    "LanguageConfigFile",
    "LanguageName",
    "LanguageNameT",
    "LiteralStringT",
    "LlmToolName",
    "LlmToolNameT",
    "Metadata",
    "ModelName",
    "ModelNameT",
    "RerankingModelName",
    "RerankingModelNameT",
    "Role",
    "RoleT",
    "RootedRoot",
    "SearchResult",
    "SemanticMetadata",
    "SemanticSearchLanguage",
    "Sentinel",
    "SerializedCodeChunk",
    "Span",
    "SpanGroup",
    "SpanTuple",
    "StoreDict",
    "StructuredDataInput",
    "ThingName",
    "ThingNameT",
    "UUIDStore",
    "Unset",
    "find_config_paths",
    "generate_field_title",
    "generate_title",
    "has_semantic_extension",
    "is_semantic_config_ext",
    "language_from_config_file",
    "languages_present_from_configs",
    "make_blake_store",
    "make_uuid_store",
    "to_uuid",
)


def __dir__() -> list[str]:
    """List available attributes for the semantic package."""
    return list(__all__)
