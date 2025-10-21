"""Global type definitions for CodeWeaver.

We usually try to keep types close to where they are used, but some types
are used so widely that it makes sense to define them globally here.

## Conventions

- We use `NewType` for strings (and occasionally other things) that have specific meanings. This helps clarify the intended use of these strings and prevents accidental misuse. If you're unfamiliar, `NewType` creates a *static*, distinct, type alias for an existing type. It doesn't exist at runtime, but type checkers will treat it as a separate type, which makes it easier to see misuse while developing. (at the cost of some verbosity and more `cast` calls).
"""

from os import PathLike
from pathlib import Path
from typing import Annotated, LiteralString, NewType

from pydantic import Field, GetPydanticSchema

from codeweaver._types.base import (
    BASEDMODEL_CONFIG,
    DATACLASS_CONFIG,
    BaseDataclassEnum,
    BasedModel,
    BaseEnum,
    BaseEnumData,
    DataclassSerializationMixin,
    DictView,
    RootedRoot,
)
from codeweaver._types.sentinel import UNSET, Sentinel, Unset


type LiteralStringT = Annotated[
    LiteralString, GetPydanticSchema(lambda _schema, handler: handler(str))
]
"""A string that is known at type-checking time. This alias for LiteralString is also compatible with Pydantic schemas, unlike LiteralString itself.

We occasionally skirt the restrictions on LiteralString, such as for config settings. In those cases, we just want to indicate that the string is intended to be a literal string, even if we can't enforce it. But they effectively are known strings because they must validate against a set of known values.
"""

# ================================================
# *       File and Directory Types
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

FileExt = NewType("FileExt", LiteralStringT)
"""A file extension string, including the leading dot. E.g. ".txt". May also be an exact filename like "Makefile" that has no extension."""

type FileExtensionT = Annotated[
    FileExt,
    Field(
        description="""A file extension string as the `FileExt` NewType, including the leading dot. E.g. '.txt'. May also be an exact filename like 'Makefile' that has no extension.""",
        pattern=r"""^(\.[^<>:;,?*|\\]+|[^<>:;,?*|\\]+)$""",
        max_length=20,
    ),
]

# ================================================
# *           Language-Related Types
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


__all__ = (
    "BASEDMODEL_CONFIG",
    "DATACLASS_CONFIG",
    "UNSET",
    "BaseDataclassEnum",
    "BaseEnum",
    "BaseEnumData",
    "BasedModel",
    "CategoryName",
    "CategoryNameT",
    "DataclassSerializationMixin",
    "DictView",
    "DirectoryPath",
    "DirectoryPathT",
    "FileExt",
    "FileExtensionT",
    "FilePath",
    "FilePathT",
    "LanguageName",
    "LanguageNameT",
    "LiteralStringT",
    "ModelName",
    "ModelNameT",
    "Role",
    "RoleT",
    "RootedRoot",
    "Sentinel",
    "ThingName",
    "ThingNameT",
    "Unset",
)
