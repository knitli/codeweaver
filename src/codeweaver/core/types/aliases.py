# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Common NewTypes and type aliases used throughout CodeWeaver."""

from os import PathLike
from pathlib import Path
from typing import Annotated, LiteralString, NewType

from pydantic import Field, GetPydanticSchema


type LiteralStringT = Annotated[
    LiteralString, GetPydanticSchema(lambda _schema, handler: handler(str))
]
"""A string that is known at type-checking time. This alias for LiteralString is also compatible with Pydantic schemas, unlike LiteralString itself.

We occasionally skirt the restrictions on LiteralString, such as for config settings. In those cases, we just want to indicate that the string is intended to be a literal string, even if we can't enforce it. But they effectively are known strings because they must validate against a set of known values.
"""

SentinelName = NewType("SentinelName", LiteralStringT)
"""The name of a sentinel value, e.g. "UNSET"."""

FilteredKey = NewType("FilteredKey", LiteralStringT)
"""A key in a dictionary that must go through a privacy filter for telemetry purposes."""

# ================================================
# *       File and Directory NewTypes/Aliases
# ================================================


# If you want a type that requires the path to exist, use `pydantic.FilePath` or
# `pydantic.DirectoryPath` instead.
# If you want a path object that doesn't have to exist, use `pathlib.Path`.

type FilePath = PathLike[str]
"""A filesystem path to a file. Does not have to exist."""

type DirectoryPath = PathLike[str]
"""A filesystem path to a directory. Does not have to exist."""

type FilePathT = Annotated[
    FilePath | Path,
    Field(
        description="""A filesystem path to a file. It doesn't need to exist, but must be a valid unix-style file path, like '/home/user/docs/file.txt' or '/mnt/c/Users/myuser/file.txt' (not 'c:\\Users\\myuser\\file.txt'). It may be relative or absolute.""",
        pattern=r"^([A-Za-z]:/)?\.?[^<>:;,?*|\\]+$",
        max_length=255,
    ),
]

type DirectoryPathT = Annotated[
    DirectoryPath | Path,
    Field(
        description="""A filesystem path to a directory. It doesn't need to exist, but must be a valid unix-style directory path, like '/home/user/docs' or 'c:/Users/myuser' (not 'c:\\Users\\myuser'). It may be relative or absolute.""",
        pattern=r"^([A-Za-z]:/)?\.?[^<>:;,?*|\\]+$",
        max_length=255,
    ),
]

# A simple directory name without any path components.

DirectoryName = NewType("DirectoryName", LiteralStringT)
"""A directory name string, e.g. "src"."""

type DirectoryNameT = Annotated[
    DirectoryName,
    Field(
        description="""A directory name string, e.g. 'src'.""",
        pattern=r"^[^<>:;,?*|\\]+$",
        max_length=100,
    ),
]

FileName = NewType("FileName", LiteralStringT)
"""A filename string, e.g. "document.txt"."""

type FileNameT = Annotated[
    FileName,
    Field(
        description="""A filename string as the `FileName` NewType, e.g. 'document.txt'.""",
        pattern=r"^[^<>:;,?*|\\]+$",
        max_length=100,
    ),
]

FileExt = NewType("FileExt", LiteralStringT)
"""A file extension string, including the leading dot. E.g. ".txt". May also be an exact filename like "Makefile" that has no extension."""

type FileExtensionT = Annotated[
    FileExt,
    Field(
        description="""A file extension string as the `FileExt` NewType, including the leading dot. E.g. '.txt'. May also be an exact filename like 'Makefile' that has no extension.""",
        pattern=r"""^(\.[^<>:;,?*|\\]+|[^<>:;,?*|\\]+)$""",
        min_length=2,
        max_length=20,
    ),
]

FileGlob = NewType("FileGlob", LiteralStringT)
"""A file glob pattern string, e.g. "*.py" or "src/**/*.js"."""

type FileGlobT = Annotated[
    FileGlob,
    Field(
        description="""A file glob pattern string as the `FileGlob` NewType, e.g. '*.py' or 'src/**/*.js'.""",
        max_length=255,
    ),
]


# ================================================
# *      Language-Related NewTypes/Aliases
# ================================================

LanguageName = NewType("LanguageName", LiteralStringT)
"""The name of a programming language, e.g. "python", "javascript", "cpp"."""

type LanguageNameT = Annotated[
    LanguageName,
    Field(
        description="""The name of a programming language as the `LanguageName` NewType, e.g. 'python', 'javascript', 'cpp'.""",
        pattern=r"^[a-z0-9_+-]+$",
        max_length=30,
    ),
]

ModelName = NewType("ModelName", LiteralStringT)
"""The name of a model for reranking, embeddings, or text generation, e.g. "gpt-4", "bert-base-uncased"."""

type ModelNameT = Annotated[
    ModelName,
    Field(
        description="""The name of a model as the `ModelName` NewType, e.g. 'gpt-4', 'bert-base-uncased'.""",
        pattern=r"^[A-Za-z0-9_+-]+$",
        max_length=50,
    ),
]

CategoryName = NewType("CategoryName", LiteralStringT)
"""The name of a semantic category (i.e. an abstract type) like "expression"."""

type CategoryNameT = Annotated[
    CategoryName,
    Field(
        description="""The name of a semantic category as the `CategoryName` NewType, e.g. 'expression'.""",
        pattern=r"^[A-Za-z0-9_+-]+$",
        max_length=30,
    ),
]

ThingName = NewType("ThingName", LiteralStringT)
"""The name of a semantic thing (i.e. a concrete node) like "if_statement"."""

type ThingNameT = Annotated[
    ThingName,
    Field(
        description="""The name of a semantic thing as the `ThingName` NewType, e.g. 'if_statement'.""",
        pattern=r"^[A-Za-z0-9_+-]+$",
        max_length=30,
    ),
]

Role = NewType("Role", LiteralStringT)
"""The role of a thing in a particular context (i.e. the relationship between a thing and its parent in a DirectConnection, also known as a field), e.g. "name", "condition", "body"."""

type RoleT = Annotated[
    Role,
    Field(
        description="""The role of a thing as the `Role` NewType, e.g. 'name', 'condition', 'body'.""",
        pattern=r"^[A-Za-z0-9_+-]+$",
        max_length=30,
    ),
]

# ================================================
# * NewTypes for Embedding and Reranking Model Names
# ================================================

EmbeddingModelName = NewType("EmbeddingModelName", ModelName)
"""The name of an embedding model, e.g. "text-embedding-ada-002"."""

type EmbeddingModelNameT = Annotated[
    EmbeddingModelName,
    Field(
        description="""The name of an embedding model as the `EmbeddingModelName` NewType, e.g. 'text-embedding-ada-002'.""",
        pattern=r"^[A-Za-z0-9_+-]+$",
        max_length=50,
    ),
]

RerankingModelName = NewType("RerankingModelName", ModelName)
"""The name of a reranking model, e.g. "sentencetransformers/ms-marco-MiniLM-L-6-v2"."""

type RerankingModelNameT = Annotated[
    RerankingModelName,
    Field(
        description="""The name of a reranking model as the `RerankingModelName` NewType, e.g. 'sentencetransformers/ms-marco-MiniLM-L-6-v2'.""",
        pattern=r"^[A-Za-z0-9_+-]+$",
        max_length=50,
    ),
]

# ================================================
# *   NewTypes/Aliases for Dev/LLM Tooling
# ================================================

DevToolName = NewType("DevToolName", LiteralStringT)
"""The name of a development tool, e.g. "cargo", "mise", "pytest"."""

type DevToolNameT = Annotated[
    DevToolName,
    Field(
        description="""The name of a development tool as the `DevToolName` NewType, e.g. 'cargo', 'mise', 'pytest'.""",
        pattern=r"^[A-Za-z0-9_+-]+$",
        max_length=30,
    ),
]

LlmToolName = NewType("LlmToolName", LiteralStringT)
"""The name of an LLM tool, e.g. "claude", "codeweaver"."""

type LlmToolNameT = Annotated[
    LlmToolName,
    Field(
        description="""The name of an LLM tool as the `LlmToolName` NewType, e.g. 'claude', 'codeweaver'.""",
        pattern=r"^[A-Za-z0-9_+-]+$",
        max_length=30,
    ),
]


__all__ = (
    "CategoryName",
    "CategoryNameT",
    "DevToolName",
    "DevToolNameT",
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
    "SentinelName",
    "ThingName",
    "ThingNameT",
)
