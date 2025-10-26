# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

"""Configuration models for user-defined languages and delimiters in CodeWeaver."""

from __future__ import annotations

from typing import Annotated, Any, Literal, Self

from pydantic import ConfigDict, Field, NonNegativeFloat, PositiveInt, model_validator

from codeweaver.core.file_extensions import ALL_LANGUAGES
from codeweaver.core.metadata import ExtLangPair
from codeweaver.core.secondary_languages import SecondarySupportedLanguage
from codeweaver.core.types.aliases import LanguageNameT
from codeweaver.core.types.models import FROZEN_BASEDMODEL_CONFIG, BasedModel
from codeweaver.engine.chunker.delimiters import DelimiterPattern, LanguageFamily


class CustomLanguage(BasedModel):
    """A custom programming language for language specific parsing.

    By default, CodeWeaver only indexes extensions it recognizes. There are a lot (~170 languages and 200+ extensions) but not everything. If you want it to index files with extensions it doesn't recognize, you can define a custom language here. You only need to do this if you **don't** want to define a custom delimiter for your language. CodeWeaver will try to detect the best chunking strategy for your language, and will probably do a decent job, but if you want to define custom delimiters, use the `CustomDelimiter` class instead.
    """

    model_config = FROZEN_BASEDMODEL_CONFIG

    extensions: Annotated[
        list[ExtLangPair],
        Field(
            min_length=1,
            description="""List of file extensions and their associated languages to apply this custom language to. An ExtLangPair is a tuple of `ext: FileExt, language: LanguageName | SemanticSearchLanguage | ConfigLanguage`. **If the language and extensions are already defined in `codeweaver.core.file_extensions` or `codeweaver.core.language`, then this is not required.**""",
        ),
    ]
    language_family: Annotated[
        LanguageFamily | None,
        Field(
            description="The language family this language belongs to. This is used to determine the best chunking strategy for the language. If not provided, CodeWeaver will test it against known language families."
        ),
    ] = None

    def _telemetry_keys(self) -> None:
        return None


class CustomDelimiter(BasedModel):
    """A custom delimiter for separating multiple prompts in a single input string. If you only want to define a new language and extensions but not a delimiter, use the `CustomLanguage` class instead."""

    model_config = FROZEN_BASEDMODEL_CONFIG

    delimiters: Annotated[
        list[DelimiterPattern],
        Field(
            default_factory=list,
            min_length=1,
            description="List of delimiters to use. You must provide at least one delimiter.",
        ),
    ]

    extensions: Annotated[
        list[ExtLangPair] | None,
        Field(
            description="""List of file extensions and their associated languages to apply this delimiter to. If you are defining delimiters for a language that does not currently have support see `codeweaver.core.file_extensions.CODE_FILES_EXTENSIONS`, `codeweaver.core.file_extensions.DATA_FILES_EXTENSIONS`, and `codeweaver.core.file_extensions.DOC_FILES_EXTENSIONS`. An ExtLangPair is a tuple of `ext: FileExt, language: LanguageName` (str NewTypes for FileExt and LanguageName) or `ConfigLanguage` or `SemanticSearchLanguage` enums. If the language and extensions are already defined in `codeweaver.core.file_extensions` then you don't need to provide these, but you DO need to provide a language."""
        ),
    ] = None

    language: Annotated[
        SecondarySupportedLanguage | LanguageNameT | None,
        Field(
            min_length=1,
            max_length=30,
            description="""The programming language this delimiter applies to. Must be one of the languages defined in `codeweaver.core.file_extensions`. If you want to define delimiters for a new language and/or file extensions, leave this field as `None` and provide the `extensions` field.""",
        ),
    ] = None

    def _telemetry_keys(self) -> None:
        return None

    @model_validator(mode="after")
    def validate_instance(self) -> Self:
        """Validate the instance after initialization."""
        if self.language not in ALL_LANGUAGES and not self.extensions:
            raise ValueError(
                f"If you are defining a delimiter for a language that does not currently have support see `codeweaver.core.file_extensions.CODE_FILES_EXTENSIONS`, `codeweaver.core.file_extensions.DATA_FILES_EXTENSIONS`, and `codeweaver.core.file_extensions.DOC_FILES_EXTENSIONS`. You must provide the `extensions` field if the language '{self.language}' is not supported."
            )
        if not self.delimiters:
            raise ValueError("You must provide at least one delimiter.")
        if (
            self.language
            and self.extensions
            and not all(ext.language for ext in self.extensions if ext.language == self.language)
        ):
            raise ValueError(
                f"The language '{self.language}' must match the language in all provided extensions: {[ext.language for ext in self.extensions]}. You also don't need to provide a language if all extensions have the same language as the one you're defining the delimiter for (which it should)."
            )
        return self


class PerformanceSettings(BasedModel):
    """Performance and resource limit configuration."""

    max_file_size_mb: Annotated[
        PositiveInt, Field(description="""Maximum file size in MB to attempt chunking""")
    ] = 10

    chunk_timeout_seconds: Annotated[
        PositiveInt, Field(description="""Maximum time allowed for chunking a single file""")
    ] = 30

    parse_timeout_seconds: Annotated[
        PositiveInt, Field(description="""Maximum time for AST parsing operation""")
    ] = 10

    max_chunks_per_file: Annotated[
        PositiveInt, Field(description="""Maximum chunks to generate from single file""")
    ] = 5000

    max_memory_mb_per_operation: Annotated[
        PositiveInt,
        Field(ge=10, le=1024, description="""Peak memory limit per chunking operation"""),
    ] = 100

    max_ast_depth: Annotated[PositiveInt, Field(description="""Maximum AST nesting depth""")] = 200

    def _telemetry_keys(self) -> None:
        return None


class ConcurrencySettings(BasedModel):
    """Concurrency configuration."""

    max_parallel_files: Annotated[
        PositiveInt,
        Field(
            description="""Maximum files to chunk concurrently (equivalent to number of workers or threads)"""
        ),
    ] = 4

    executor: Annotated[
        Literal["process", "thread"],
        Field(
            description="""Use ProcessPoolExecutor (process) vs ThreadPoolExecutor (thread) for concurrent chunking. Process-based execution is more robust for CPU-bound tasks like chunking and parsing, but thread-based execution can be more memory efficient in some environments. Thread-based may also improve performance when I/O becomes a bottleneck (e.g. remote file access and network calls). We default to process-based execution for better overall reliability."""
        ),
    ] = "process"

    def _telemetry_keys(self) -> None:
        return None


class ChunkerSettings(BasedModel):
    """Configuration for chunker system.

    You can use these settings to customize how CodeWeaver chunks files for indexing, and to add support for custom languages or delimiters.

    Note: If you're adding support for another language, we'd love you to open a pull request to add it to our built-in language definitions! See `codeweaver.core.file_extensions` and `codeweaver.engine.chunker.delimiters` for more details.
    """

    model_config = BasedModel.model_config | ConfigDict(validate_assignment=True)

    # Delimiter chunker settings (placeholder for future)
    custom_delimiters: Annotated[
        list[CustomDelimiter] | None,
        Field(
            description="""If you want to change or customize delimiter-based chunking, or add support for a new language, define custom delimiters here. You can also define custom languages with `custom_languages`."""
        ),
    ] = None

    custom_languages: Annotated[
        dict[LanguageNameT, LanguageFamily] | None,
        Field(
            description="""Associate a new language with an existing CodeWeaver language family for chunking purposes. If you want to define custom delimiters for a new language, use `custom_delimiters` instead. Most languages can be reasonably chunked by CodeWeaver's existing delimiter strategies once you tell it what language to use."""
        ),
    ] = None

    # Semantic chunker settings
    semantic_importance_threshold: Annotated[
        NonNegativeFloat,
        Field(
            ge=0.0,
            le=1.0,
            description="""Minimum importance score to consider a code element for semantic chunking. Values range from 0.0 (include all) to 1.0 (include none). CodeWeaver defaults to 0.3, which balances chunk size and relevance.""",
        ),
    ] = 0.3

    # Resource settings
    performance: Annotated[
        PerformanceSettings,
        Field(description="""Performance and resource limit configuration settings."""),
    ] = PerformanceSettings()

    concurrency: Annotated[
        ConcurrencySettings, Field(description="""Concurrency configuration settings.""")
    ] = ConcurrencySettings()

    def _telemetry_keys(self) -> None:
        return None

    def __init__(
        self,
        *,
        custom_delimiters: list[CustomDelimiter] | None = None,
        custom_languages: dict[LanguageNameT, LanguageFamily] | None = None,
        **data: Any,
    ) -> None:
        """Initialize ChunkerSettings with optional custom delimiters."""
        # Pass values through to super().__init__ instead of setting them directly
        super().__init__(
            custom_delimiters=custom_delimiters or [],
            custom_languages=custom_languages or {},
            **data
        )


__all__ = (
    "ChunkerSettings",
    "ConcurrencySettings",
    "CustomDelimiter",
    "CustomLanguage",
    "PerformanceSettings",
)
