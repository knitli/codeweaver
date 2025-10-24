"""Configuration models for user-defined languages and delimiters in CodeWeaver."""

from typing import Annotated, Self

from pydantic import Field, model_validator

from codeweaver.core.file_extensions import ALL_LANGUAGES, ExtLangPair
from codeweaver.core.secondary_languages import SecondarySupportedLanguage
from codeweaver.core.types.models import FROZEN_BASEDMODEL_CONFIG, BasedModel
from codeweaver.engine import DelimiterPattern, LanguageFamily


class CustomLanguage(BasedModel):
    """A custom programming language for language specific parsing.

    By default, CodeWeaver only indexes extensions it recognizes. There are a lot (~170 languages and 200+ extensions) but not everything. If you want it to index files with extensions it doesn't recognize, you can define a custom language here. You only need to do this if you **don't** want to define a custom delimiter for your language. CodeWeaver will try to detect the best chunking strategy for your language, and will probably do a decent job, but if you want to define custom delimiters, use the `CustomDelimiter` class instead.
    """

    model_config = FROZEN_BASEDMODEL_CONFIG

    extensions: Annotated[
        list[ExtLangPair],
        Field(
            min_length=1,
            description="""List of file extensions and their associated languages to apply this custom language to. An ExtLangPair is a tuple of `ext: str, language: str`. **If the language and extensions are already defined in `codeweaver._constants`, then this is not required.**""",
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
    """A custom delimiter for separating multiple prompts in a single input string. If you only want to define a new language and extensions but not a delimiter, use the `CustomLanguage` class instead.

    Attributes:
        delimiter (str): The delimiter string to use.
        description (str): A description of the delimiter.
    """

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
            default_factory=list,
            description="""List of file extensions and their associated languages to apply this delimiter to. If you are defining delimiters for a language that does not currently have support see `codeweaver._constants.CODE_FILES_EXTENSIONS`, `codeweaver._constants.DATA_FILES_EXTENSIONS`, and `codeweaver._constants.DOC_FILES_EXTENSIONS`. An ExtLangPair is a tuple of `ext: str, language: str`. If the language and extensions are already defined in `codeweaver._constants` then you don't need to provide these, but you DO need to provide a language.""",
        ),
    ] = None

    language: Annotated[
        SecondarySupportedLanguage | str | None,
        Field(
            min_length=1,
            max_length=30,
            description="""The programming language this delimiter applies to. Must be one of the languages defined in `codeweaver._constants`. If you want to define delimiters for a new language and/or file extensions, leave this field as `None` and provide the `extensions` field.""",
            default_factory=lambda data: None if data.get("extensions") else str,
        ),
    ] = None

    def _telemetry_keys(self) -> None:
        return None

    @model_validator(mode="after")
    def validate_instance(self) -> Self:
        """Validate the instance after initialization."""
        if self.language not in ALL_LANGUAGES and not self.extensions:
            raise ValueError(
                f"If you are defining a delimiter for a language that does not currently have support see `codeweaver._constants.CODE_FILES_EXTENSIONS`, `codeweaver._constants.DATA_FILES_EXTENSIONS`, and `codeweaver._constants.DOC_FILES_EXTENSIONS`. You must provide the `extensions` field if the language '{self.language}' is not supported."
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
