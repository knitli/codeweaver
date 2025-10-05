# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
# We need to override our generic models with specific types, and type overrides for narrower values is a good thing.
# pyright: reportIncompatibleMethodOverride=false,reportIncompatibleVariableOverride=false
"""Unified configuration system for CodeWeaver.

Provides a centralized settings system using pydantic-settings with
clear precedence hierarchy and validation.
"""

from __future__ import annotations

import contextlib
import importlib
import inspect
import logging

from collections.abc import Callable
from functools import cached_property
from importlib import util
from pathlib import Path
from textwrap import dedent
from typing import Annotated, Any, Literal, Self, Unpack, cast

from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.server.server import DuplicateBehavior
from fastmcp.tools.tool import Tool
from mcp.server.auth.settings import AuthSettings
from pydantic import (
    ConfigDict,
    Field,
    FilePath,
    PositiveInt,
    PrivateAttr,
    ValidationError,
    computed_field,
    field_validator,
)
from pydantic.fields import ComputedFieldInfo, FieldInfo
from pydantic_ai.settings import ModelSettings as AgentModelSettings
from pydantic_ai.settings import merge_model_settings
from pydantic_core import from_json
from pydantic_settings import BaseSettings, PydanticBaseSettingsSource, SettingsConfigDict

from codeweaver._common import UNSET, BasedModel, DictView, Unset
from codeweaver._constants import DEFAULT_EXCLUDED_DIRS, DEFAULT_EXCLUDED_EXTENSIONS
from codeweaver.provider import Provider
from codeweaver.settings_types import (
    AVAILABLE_MIDDLEWARE,
    AgentProviderSettings,
    CodeWeaverSettingsDict,
    CustomDelimiter,
    CustomLanguage,
    DataProviderSettings,
    EmbeddingModelSettings,
    EmbeddingProviderSettings,
    ErrorHandlingMiddlewareSettings,
    FileFilterSettingsDict,
    LoggingMiddlewareSettings,
    LoggingSettings,
    MiddlewareOptions,
    RateLimitingMiddlewareSettings,
    RerankingModelSettings,
    RerankingProviderSettings,
    RetryMiddlewareSettings,
    RignoreSettings,
    SparseEmbeddingModelSettings,
    UvicornServerSettings,
    default_config_file_locations,
)


logger = logging.getLogger(__name__)


DefaultDataProviderSettings = (
    DataProviderSettings(provider=Provider.TAVILY, enabled=False, api_key=None, other=None),
    # DuckDuckGo
    DataProviderSettings(provider=Provider.DUCKDUCKGO, enabled=True, api_key=None, other=None),
)

DefaultEmbeddingProviderSettings = (
    EmbeddingProviderSettings(
        provider=Provider.VOYAGE,
        enabled=True,
        model_settings=EmbeddingModelSettings(model="voyage:voyage-code-3"),
    ),
)
HAS_ST = util.find_spec("sentence_transformers") is not None
DefaultSparseEmbeddingProviderSettings = (
    EmbeddingProviderSettings(
        provider=Provider.SENTENCE_TRANSFORMERS,
        enabled=HAS_ST,
        sparse_model_settings=SparseEmbeddingModelSettings(
            model="opensearch:opensearch-neural-sparse-encoding-doc-v3-gte"
        ),
    ),
)

DefaultRerankingProviderSettings = (
    RerankingProviderSettings(
        provider=Provider.VOYAGE,
        enabled=True,
        model_settings=RerankingModelSettings(model="voyage:rerank-2.5"),
    ),
)
HAS_ANTHROPIC = util.find_spec("anthropic") is not None
DefaultAgentProviderSettings = (
    AgentProviderSettings(
        provider=Provider.ANTHROPIC,
        enabled=HAS_ANTHROPIC,
        model="claude-sonnet-4-latest",
        model_settings=AgentModelSettings(),
    ),
)

DefaultMiddlewareSettings = MiddlewareOptions(
    error_handling=ErrorHandlingMiddlewareSettings(
        include_traceback=True, error_callback=None, transform_errors=False
    ),
    retry=RetryMiddlewareSettings(
        max_retries=5, base_delay=1.0, max_delay=60.0, backoff_multiplier=2.0
    ),
    logging=LoggingMiddlewareSettings(log_level=20, include_payloads=False),
    rate_limiting=RateLimitingMiddlewareSettings(
        max_requests_per_second=75, get_client_id=None, burst_capacity=150, global_limit=True
    ),
)


def merge_agent_model_settings(
    base: AgentModelSettings | None, override: AgentModelSettings | None
) -> AgentModelSettings | None:
    """A convenience re-export of `merge_model_settings` for agent model settings."""
    return merge_model_settings(base, override)


class FileFilterSettings(BasedModel):
    """Settings for file filtering.

    ## Path Resolution and Deconfliction

    Any configured paths or path patterns should be relative to the project root directory.

    CodeWeaver deconflicts paths in the following ways:
    - If a file is specifically defined in `forced_includes`, it will always be included, even if it matches an exclude pattern.
      - This doesn't apply if it is defined in `forced_includes` with a glob pattern that matches an excluded file (by extension or glob/path).
      - This also doesn't apply to directories.
    - Other filters like `use_gitignore`, `use_other_ignore_files`, and `ignore_hidden` will apply to all files **not in `forced_includes`**.
      - Files in `forced_includes`, including files defined from glob patterns, will *not* be filtered by these settings.
    - if `include_github_dir` is True (default), the glob `**/.github/**` will be added to `forced_includes`.
    """

    model_config = (
        ConfigDict(
            json_schema_extra={"NoTelemetryProps": ["forced_includes", "excludes"]},
            defer_build=True,
        )
        | BasedModel.model_config
    )

    forced_includes: Annotated[
        frozenset[str | Path],
        Field(
            description="""Directories, files, or [glob patterns](https://docs.python.org/3/library/pathlib.html#pathlib-pattern-language) to include in search and indexing. This is a set of strings, so you can use glob patterns like `**/src/**` or `**/*.py` to include directories or files."""
        ),
    ] = frozenset()
    excludes: Annotated[
        frozenset[str | Path],
        Field(
            description="""Directories, files, or [glob patterns](https://docs.python.org/3/library/pathlib.html#pathlib-pattern-language) to exclude from search and indexing. This is a set of strings, so you can use glob patterns like `**/node_modules/**` or `**/*.log` to exclude directories or files."""
        ),
    ] = DEFAULT_EXCLUDED_DIRS
    excluded_extensions: Annotated[
        frozenset[str], Field(description="""File extensions to exclude from search and indexing""")
    ] = DEFAULT_EXCLUDED_EXTENSIONS
    use_gitignore: Annotated[
        bool, Field(description="""Whether to use .gitignore for filtering""")
    ] = True
    use_other_ignore_files: Annotated[
        bool,
        Field(
            description="""Whether to read *other* ignore files (besides .gitignore) for filtering"""
        ),
    ] = False
    ignore_hidden: Annotated[
        bool,
        Field(description="""Whether to ignore hidden files (starting with .) for filtering"""),
    ] = True
    include_github_dir: Annotated[
        bool,
        Field(
            description="""Whether to include the .github directory in search and indexing. Because the .github directory is hidden, it wouldn't be included in default settings. Most people want to include it for work on GitHub Actions, workflows, and other GitHub-related files."""
        ),
    ] = True
    other_ignore_kwargs: Annotated[
        RignoreSettings | Unset,
        Field(
            default_factory=dict,
            description="""Other kwargs to pass to `rignore`. See <https://pypi.org/project/rignore/>. By default we set max_filesize to 5MB and same_file_system to True.""",
        ),
    ] = UNSET

    default_rignore_settings: Annotated[
        RignoreSettings,
        Field(
            description="""Default settings for rignore. These are used if not overridden by user settings."""
        ),
    ] = RignoreSettings({"max_filesize": 5 * 1024 * 1024, "same_file_system": True})

    def model_post_init(self, _context: MiddlewareContext[Any] | None = None, /) -> None:
        """Post-initialization processing."""
        if self.include_github_dir:
            self.forced_includes |= {"**/.github/**"}

    @staticmethod
    def _self_to_kwargs(self_kind: FileFilterSettings | FileFilterSettingsDict) -> RignoreSettings:
        """Convert self, either as an instance or as a serialized python dictionary, to kwargs for rignore."""
        if isinstance(self_kind, FileFilterSettings):
            self_kind = FileFilterSettingsDict(**self_kind.model_dump())
        return RignoreSettings(
            **cast(
                RignoreSettings,
                {
                    "additional_ignores": [
                        *(
                            f"*.{ext}"
                            if not ext.startswith("*") or ext.startswith(".")
                            else (ext if ext.startswith("*") else f"*{ext}")
                            for ext in self_kind.get("excluded_extensions", [])
                        ),
                        *self_kind.get("excludes", []),
                    ],
                    "read_git_ignore": self_kind.get("use_gitignore", True),
                    "read_ignore_files": self_kind.get("use_other_ignore_files", False),
                    "ignore_hidden": self_kind.get("ignore_hidden", True),
                    **self_kind.get("default_rignore_settings", {}),
                    **(
                        cast(
                            RignoreSettings,
                            {}
                            if isinstance(self_kind.get("other_ignore_kwargs", {}), Unset)
                            else self_kind.get("other_ignore_kwargs", {}),
                        )
                    ),
                },
            )
        )

    def construct_filter(self) -> Callable[[Path], bool]:
        """Constructs the filter function for rignore."""

        def filter_func(path: Path | str) -> bool:
            """Filter function that respects forced includes."""
            path_obj = Path(path) if isinstance(path, str) else path
            return any(path_obj.match(str(include)) for include in self.forced_includes)

        return filter_func

    @cached_property
    def filter(self) -> Callable[[Path], bool]:
        """Cached property for the filter function."""
        return self.construct_filter()

    def _adjust_settings(self) -> RignoreSettings:
        """Adjusts a few settings, primarily to reform keywords. `rignore`'s choice of keywords is a bit odd, so we wrapped them in clearer alternatives."""
        return self._self_to_kwargs(self)

    def to_kwargs(self) -> RignoreSettings:
        """Serialize to kwargs for rignore."""
        return self._adjust_settings()


class ProviderSettings(BasedModel):
    """Settings for provider configuration."""

    data: Annotated[
        tuple[DataProviderSettings, ...] | Unset,
        Field(description="""Data provider configuration"""),
    ] = DefaultDataProviderSettings

    embedding: Annotated[
        tuple[EmbeddingProviderSettings, ...] | Unset,
        Field(description="""Embedding provider configuration"""),
    ] = DefaultEmbeddingProviderSettings

    reranking: Annotated[
        tuple[RerankingProviderSettings, ...] | Unset,
        Field(description="""Reranking provider configuration"""),
    ] = DefaultRerankingProviderSettings
    """
    vector: Annotated[
        tuple[BaseVectorStoreConfig, ...],
        Field(default_factory=QdrantVectorStore, description="Vector store provider configuration"),
    ] = QdrantConfig()
    """
    agent: Annotated[
        tuple[AgentProviderSettings, ...] | Unset,
        Field(description="""Agent provider configuration"""),
    ] = DefaultAgentProviderSettings


AllDefaultProviderSettings = ProviderSettings.model_construct(
    data=DefaultDataProviderSettings,
    embedding=DefaultEmbeddingProviderSettings,
    reranking=DefaultRerankingProviderSettings,
    agent=DefaultAgentProviderSettings,
)


class FastMcpServerSettings(BasedModel):
    """Settings for the FastMCP server.

    These settings don't represent the complete set of FastMCP server settings, but the ones users can configure. The remaining settings, if changed, could break functionality or cause unexpected behavior.
    """

    model_config = (
        ConfigDict(
            json_schema_extra={
                "TelemetryBoolProps": [  # properties to convert to bool for telemetry -- just 'property is set' or 'property is not set'
                    "host",
                    "port",
                    "path",
                    "additional_dependencies",
                    "additional_middleware",
                    "additional_tools",
                ]
            }
        )
        | BasedModel.model_config
    )

    transport: Annotated[
        Literal["stdio", "http", "streamable-http"] | None,
        Field(
            description="""Transport protocol to use for the FastMCP server. Stdio is for local use and cannot support concurrent requests. HTTP (streamable HTTP) can be used for local or remote use and supports concurrent requests. Unlike many MCP servers, CodeWeaver **defaults to http**."""
        ),
    ] = "http"
    host: Annotated[str | None, Field(description="""Host address for the FastMCP server.""")] = (
        "127.0.0.1"
    )
    port: Annotated[
        PositiveInt | None,
        Field(description="""Port number for the FastMCP server. Default is 9328 ('WEAV')"""),
    ] = 9328

    auth: Annotated[AuthSettings | None, Field(description="""OAuth provider configuration""")] = (
        None
    )
    on_duplicate_tools: DuplicateBehavior | None = None
    on_duplicate_resources: DuplicateBehavior | None = None
    on_duplicate_prompts: DuplicateBehavior | None = None
    resource_prefix_format: Literal["protocol", "path"] | None = None
    # these are each "middleware", "tools", and "dependencies" for FastMCP. But we prefix them with "additional_" to make it clear these are *in addition to* the ones we provide by default.
    additional_middleware: Annotated[
        list[str] | None,
        Field(
            description="""Additional middleware to add to the FastMCP server. Values should be full path import strings, like `codeweaver.middleware.statistics.StatisticsMiddleware`.""",
            validation_alias="middleware",
            serialization_alias="middleware",
        ),
    ] = None
    additional_tools: Annotated[
        list[str] | None,
        Field(
            description="""Additional tools to add to the FastMCP server. Values can be either full path import strings, like `codeweaver.tools.git.GitTool`, or just the tool name, like `GitTool`.""",
            validation_alias="tools",
            serialization_alias="tools",
        ),
    ] = None

    @staticmethod
    def _attempt_import(suspected_path: str) -> Any | None:
        """Attempt to import a class or callable."""
        module_path, class_name = suspected_path.rsplit(".", 1)
        with contextlib.suppress(ImportError, AttributeError):
            module = __import__(module_path, fromlist=[class_name])
            cls = getattr(module, class_name, None)
            if cls and (inspect.isclass(cls) or callable(cls)):
                return cls
        return None

    @staticmethod
    def _dotted_name(obj: Any) -> str | None:
        """Return a stable 'module.qualname' for a class/callable/instance when possible."""
        with contextlib.suppress(ImportError, AttributeError):
            if inspect.isclass(obj) or inspect.isfunction(obj) or inspect.ismethod(obj):
                module = getattr(obj, "__module__", None)
                qual = getattr(obj, "__qualname__", None)
                if module and qual:
                    return f"{module}.{qual}"
            # Instance -> use its class
            cls_obj = getattr(obj, "__class__", None)
            module = getattr(cls_obj, "__module__", None)
            qual = getattr(cls_obj, "__qualname__", None)
            if module and qual:
                return f"{module}.{qual}"
        return None

    @classmethod
    def _callable_to_path(cls, value: Any, field: Literal["middleware", "tools"]) -> str | None:
        """Normalize middleware inputs (class/instance/callable/str) into 'module.qualname' strings."""
        if not value:
            return None
        if isinstance(value, str) and field == "tools":
            return value
        # Strings
        if isinstance(value, str) and field == "middleware":
            # If it matches a known middleware class name, expand to dotted path
            for mw in AVAILABLE_MIDDLEWARE:
                if value in (mw.__name__, mw.__qualname__, str(mw)):
                    return f"{mw.__module__}.{mw.__qualname__}"
            # If dotted import path, keep as-is
            return value
        # Known class/instance/callable
        if (isinstance(value, Middleware | Tool) or inspect.isclass(value) or callable(value)) and (
            dotted := cls._dotted_name(value)
        ):
            return dotted
        return None

    @classmethod
    @field_validator("additional_middleware", mode="before")
    def _validate_additional_middleware(cls, value: Any) -> list[str] | None:
        """Validate and normalize additional middleware inputs."""
        if value is None or value is UNSET:
            return None
        if isinstance(value, str | bytes | bytearray):
            try:
                value = from_json(value)
            except Exception:
                value = [value]
        return [s for s in (cls._callable_to_path(v, "middleware") for v in value) if s]

    @classmethod
    @field_validator("additional_tools", mode="before")
    def _validate_additional_tools(cls, value: Any) -> list[str] | None:
        """Validate and normalize additional tool inputs."""
        if value is None or value is UNSET:
            return None
        if isinstance(value, str | bytes | bytearray):
            try:
                value = from_json(value)
            except Exception:
                value = [value]
        return [s for s in (cls._callable_to_path(v, "tools") for v in value) if s]


DefaultFastMcpServerSettings = FastMcpServerSettings.model_validate({
    "transport": "http",
    "auth": None,
    "on_duplicate_tools": "warn",
    "on_duplicate_resources": "warn",
    "on_duplicate_prompts": "warn",
    "resource_prefix_format": "path",
    "middleware": [],
    "tools": [],
})


_ = ProviderSettings.model_rebuild()


class CodeWeaverSettings(BaseSettings):
    """Main configuration model following pydantic-settings patterns.

    Configuration precedence (highest to lowest):
    1. Environment variables (CODEWEAVER_*)
    2. Local config (.codeweaver.local.toml (or .yaml, .yml, .json) in current directory)
    3. Project config (.codeweaver.toml (or .yaml, .yml, .json) in project root)
    4. User config (~/.codeweaver.toml (or .yaml, .yml, .json))
    5. Global config (/etc/codeweaver.toml (or .yaml, .yml, .json))
    6. Defaults
    """

    model_config = SettingsConfigDict(
        case_sensitive=False,
        cli_kebab_case=True,
        env_file=(".codeweaver.local.env", ".env", ".codeweaver.env"),
        env_ignore_empty=True,
        env_nested_delimiter="__",
        env_parse_enums=True,
        env_prefix="CODEWEAVER_",
        extra="allow",  # Allow extra fields in the configuration for plugins/extensions
        field_title_generator=cast(
            Callable[[str, FieldInfo | ComputedFieldInfo], str],
            BasedModel.model_config["field_title_generator"],  # type: ignore
        ),
        json_file=default_config_file_locations(as_json=True),
        json_schema_extra={
            "NoTelemetryProps": ["project_path", "project_root", "project_name", "config_file"]
        },
        nested_model_default_partial_update=True,
        str_strip_whitespace=True,
        title="CodeWeaver Settings",
        toml_file=default_config_file_locations(),
        use_attribute_docstrings=True,
        use_enum_values=True,
        validate_assignment=True,
        yaml_file=default_config_file_locations(as_yaml=True),
    )

    # Core settings
    project_path: Annotated[
        Path,
        Field(
            default_factory=importlib.import_module("codeweaver._utils").get_project_root(),
            description="""Root path of the codebase to analyze. CodeWeaver will try to detect the project root automatically if you don't provide one.""",
        ),
    ]

    project_name: Annotated[
        str | None, Field(description="""Project name (auto-detected from directory if None)""")
    ] = None

    provider: Annotated[
        ProviderSettings,
        Field(
            default_factory=ProviderSettings,
            description="""Provider and model configurations for agents, data, embedding, reranking, sparse embedding, and vector store providers. Will default to default profile if not provided.""",
        ),
    ] = AllDefaultProviderSettings

    config_file: Annotated[
        FilePath | None,
        Field(description="""Path to the configuration file, if any""", exclude=True),
    ] = None

    # Performance settings
    token_limit: Annotated[
        PositiveInt, Field(le=200_000, description="""Maximum tokens per response""")
    ] = 30_000
    max_file_size: Annotated[
        PositiveInt, Field(ge=51_200, description="""Maximum file size to process in bytes""")
    ] = 1_048_576  # 1 MB
    max_results: Annotated[
        PositiveInt,
        Field(
            le=500,
            description="""Maximum code matches to return. Because CodeWeaver primarily indexes ast-nodes, a page can return multiple matches per file, so this is not the same as the number of files returned. This is the maximum number of code matches returned in a single response.""",
        ),
    ] = 75
    server: Annotated[
        FastMcpServerSettings,
        Field(description="""Optionally customize FastMCP server settings."""),
    ] = DefaultFastMcpServerSettings

    logging: Annotated[
        LoggingSettings | None, Field(default_factory=dict, description="""Logging configuration""")
    ] = None

    middleware_settings: Annotated[
        MiddlewareOptions | None, Field(description="""Middleware settings""")
    ] = DefaultMiddlewareSettings

    filter_settings: Annotated[
        FileFilterSettings, Field(description="""File filtering settings""")
    ] = FileFilterSettings()

    custom_languages: Annotated[
        list[CustomLanguage] | None,
        Field(
            description=dedent("""
            If CodeWeaver's built-in language support doesn't cover your codebase sufficiently, you can do one of two things:
            1. Define custom delimiters for the languages you want to improve support for. This is the recommended approach if you just want to improve chunking for a specific language or file type. Or if you want full control over how chunking is done for a specific language or file type. Do that with the `custom_delimiters` setting, by providing a list of `CustomDelimiter` objects.
            2. You can optionally provide a list of custom languages for your codebase. This is useful if you use a language or file type that isn't natively supported by CodeWeaver. You can define the language name, file extensions, and the language's family for CodeWeaver to infer a chunking strategy. You can't define custom delimiters here -- use `custom_delimiters` for that.

            Note that CodeWeaver has very extensive built-in language support (currently around 170 languages and 200+ file types), so you should only need to use this if you have a very niche or uncommon language or file type, or if we just missed the extension you are using in our definitions. In either case, please consider submitting a pull request to add it to our built-in definitions, or [file an issue](https://github.com/knitli/codeweaver-mcp/issues/) to let us know!
            """)
        ),
    ] = None

    custom_delimiters: Annotated[
        list[CustomDelimiter] | None,
        Field(
            description=dedent("""
        You can optionally provide a list of custom delimiters for your codebase. There are two scenarios where you might want to do this:
        1. You use a language or file type that isn't natively supported by CodeWeaver, and you want to add support for it by defining custom delimiters (you could also submit a pull request! Our builtin delimiters are very extensive, and do a decent job of covering unknown languages, but anything explicitly defined will probably do better.
        2. You want to override the default delimiters for a language or file type. For example, if you don't think the delimiters are providing good results, you can override them here.
        3. (I said two...) You should NOT do this if you want a completely custom chunking strategy. You can add one programmatically to the `Chunker` class with `register._chunker.` Your chunker should subclass `codeweaver.services.chunker.base.BaseChunker`.
        """)
        ),
    ] = None

    enable_background_indexing: Annotated[
        bool,
        Field(
            description="""Enable automatic background indexing (default behavior and recommended). If disabled, it will only index files when you explicitly tell it to, which will make it much harder to deliver quality context to your agents."""
        ),
    ] = True
    enable_telemetry: Annotated[
        bool,
        Field(
            description="""Enable privacy-friendly usage telemetry. ON by default. We do not collect any identifying information -- we hash all file and directory paths, repository names, and other identifiers to ensure privacy while still gathering useful aggregate data for improving CodeWeaver. We add a second round of filters within Posthog cloud before we get the data just to be sure we caught everything. You can see exactly what we collect, and how we collect it [here](services/telemetry.py). You can disable telemetry if you prefer not to send any data. You can also provide your own PostHog Project Key to collect your own telemetry data. **We will only ever use this data to improve CodeWeaver. We will never sell or share it with anyone else, and we won't use it for targeted marketing (we will use high level aggregate data, like how many people use it, and how many tokens CodeWeaver has saved.)**"""
        ),
    ] = True
    # TODO: I don't think we're actually checking for these before initializing the server. We should.
    enable_health_endpoint: Annotated[
        bool, Field(description="""Enable the health check endpoint""")
    ] = True
    enable_statistics_endpoint: Annotated[
        bool, Field(description="""Enable the statistics endpoint""")
    ] = True
    enable_settings_endpoint: Annotated[
        bool, Field(description="""Enable the settings endpoint""")
    ] = True
    enable_version_endpoint: Annotated[
        bool, Field(description="""Enable the version endpoint""")
    ] = True
    allow_identifying_telemetry: Annotated[
        bool,
        Field(
            description="""DISABLED BY DEFAULT. If you want to *really* help us improve CodeWeaver, you can allow us to collect potentially identifying telemetry data. It's not intrusive, it's more like what *most* telemetry collects. If it's enabled, we *won't hash file and repository names. We'll still try our best to screen out potential secrets, as well as names and emails, but we can't guarantee complete anonymity. This helps us by giving us real-world usage patterns and information on queries and results. We can use that to make everyone's results better. Like with the default telemetry, we **will not use it for anything else**."""
        ),
    ] = False
    enable_ai_intent_analysis: Annotated[
        bool, Field(description="""Enable AI-powered intent analysis via FastMCP sampling""")
    ] = False  # ! Phase 2 feature, switch to True when implemented
    enable_precontext: Annotated[
        bool,
        Field(
            description="""Enable precontext code generation. Recommended, but requires you set up an agent model. This allows CodeWeaver to call an agent model outside of an MCP tool request (it still requires either a CLI call from you or a hook you setup). This is required for our recommended *precontext workflow*. This setting dictionary is a `pydantic_ai.settings.ModelSettings` object. If you already use `pydantic_ai.settings.ModelSettings`, then you can provide the same settings here."""
        ),
    ] = False  # ! Phase 2 feature, switch to True when implemented

    uvicorn_settings: Annotated[
        UvicornServerSettings | None,
        Field(
            default_factory=UvicornServerSettings, description="""Settings for the Uvicorn server"""
        ),
    ] = None

    __version__: Annotated[
        str,
        Field(
            description="""Schema version for CodeWeaver settings""",
            pattern=r"\d{1,2}\.\d{1,3}\.\d{1,3}",
        ),
    ] = "1.0.0"

    _map: Annotated[DictView[CodeWeaverSettingsDict] | None, PrivateAttr()] = None

    def model_post_init(self, __context: Any, /) -> None:
        """Post-initialization validation."""
        # Ensure project path exists and is readable
        if not self.project_name and self.project_root:
            self.project_name = self.project_root.name
        if type(self).__pydantic_complete__:
            self._map = cast(DictView[CodeWeaverSettingsDict], DictView(self.model_dump()))
            globals()["_mapped_settings"] = self._map

    @classmethod
    def from_config(cls, path: FilePath, **kwargs: Unpack[CodeWeaverSettingsDict]) -> Self:
        """Create a CodeWeaverSettings instance from a configuration file."""
        extension = path.suffix.lower()
        match extension:
            case ".json":
                cls.model_config["json_file"] = path
            case ".toml":
                cls.model_config["toml_file"] = path
            case ".yaml" | ".yml":
                cls.model_config["yaml_file"] = path
            case _:
                raise ValueError(f"Unsupported configuration file format: {extension}")
        from codeweaver._utils import get_project_root

        return cls(project_path=get_project_root(), **{**kwargs, "config_file": path})  # type: ignore

    @computed_field
    @cached_property
    def project_root(self) -> Path:
        """Get the project root directory."""
        if not hasattr(self, "project_path") or not self.project_path:
            self.project_path = importlib.import_module("codeweaver._utils").get_project_root()
        return self.project_path.resolve()

    @classmethod  # spellchecker:off
    def settings_customise_sources(
        # spellchecker:on
        cls,
        settings_cls: type[BaseSettings],
        init_settings: PydanticBaseSettingsSource,
        env_settings: PydanticBaseSettingsSource,
        dotenv_settings: PydanticBaseSettingsSource,
        file_secret_settings: PydanticBaseSettingsSource,
    ) -> tuple[PydanticBaseSettingsSource, ...]:
        """Customize the sources of settings for a specific settings class."""
        # spellchecker:off
        return super().settings_customise_sources(
            settings_cls, init_settings, env_settings, dotenv_settings, file_secret_settings
        )
        # spellchecker:on

    def _update_settings(self, **kwargs: CodeWeaverSettingsDict) -> Self:
        """Update settings, validating a new CodeWeaverSettings instance and updating the global instance."""
        new_settings = self.model_copy().model_dump() | kwargs
        try:
            new_self = self.model_validate(new_settings)
        except ValidationError:
            logger.exception(
                "`CodeWeaverSettings` received invalid settings for an update. The settings failed to validate. We did not update the settings."
            )
            return self
        globals()["_settings"] = new_self
        globals()["_mapped_settings"] = (
            None  # reset the mapping, it will be regenerated on next access
        )
        self._map = None  # reset the instance mapping, it will be regenerated on next access
        return new_self.model_copy()

    @property
    def view(self) -> DictView[CodeWeaverSettingsDict]:
        """Get a read-only mapping view of the settings."""
        if self._map is None or not self._map:
            try:
                self._map = DictView(self.model_dump())  # type: ignore
            except Exception:
                logger.exception("Failed to create settings map view")
                _ = type(self).model_rebuild()
                self._map = DictView(self.model_dump())  # type: ignore
        if not self._map:
            raise TypeError("Settings map view is not a valid DictView[CodeWeaverSettingsDict]")
        return self._map


# Global settings instance
_settings: CodeWeaverSettings | None = None
"""The global settings instance. Use `get_settings()` to access it."""

_mapped_settings: DictView[CodeWeaverSettingsDict] | None = None
"""An immutable mapping view of the global settings instance."""


def get_settings(path: FilePath | None = None) -> CodeWeaverSettings:
    """Get the global settings instance.

    This should not be your first choice for getting settings. For most needs, you should. Use get_settings_map() to get a read-only mapping view of the settings. This map is a *live view*, meaning it will update if the settings are updated.

    If you **really** need to get the mutable settings instance, you can use this function. It will create the global instance if it doesn't exist, optionally loading from a configuration file (like, .codeweaver.toml) if you provide a path.
    """
    global _settings
    root = importlib.import_module("codeweaver._utils").get_project_root()
    if _settings and path and path.exists():
        _settings = CodeWeaverSettings.from_config(path, **dict(_settings))
    elif path and path.exists():
        _settings = CodeWeaverSettings(project_path=root, config_file=path)
    if _settings is None:
        _settings = CodeWeaverSettings(project_path=root)  # type: ignore
    if not CodeWeaverSettings.__pydantic_complete__:
        _ = CodeWeaverSettings.model_rebuild()

    return _settings


def update_settings(**kwargs: CodeWeaverSettingsDict) -> DictView[CodeWeaverSettingsDict]:
    """Update the global settings instance.

    Returns a read-only mapping view of the updated settings.
    """
    global _settings
    if _settings is None:
        try:
            _settings = get_settings()
        except Exception:
            logger.exception("Failed to get settings: ")
            _ = CodeWeaverSettings.model_rebuild()
            _settings = get_settings()
    _settings = _settings._update_settings(**kwargs)  # type: ignore
    return _settings.view


def get_settings_map() -> DictView[CodeWeaverSettingsDict]:
    """Get a read-only mapping view of the global settings instance.

    Almost nothing in CodeWeaver should need to modify settings at runtime,
    so instead we distribute a live, read-only view of the global settings. It's thread-safe and will update if the settings are changed.
    """
    global _mapped_settings
    global _settings
    try:
        settings = _settings or get_settings()
    except Exception:
        logger.exception("Failed to get settings: ")
        _ = CodeWeaverSettings.model_rebuild()
        settings = get_settings()
    if _mapped_settings is None or _mapped_settings != settings.view:
        _mapped_settings = settings.view
    return _mapped_settings


def reset_settings() -> None:
    """Reload settings from configuration sources."""
    global _settings
    global _mapped_settings
    _settings = None
    _mapped_settings = None  # the mapping will be regenerated on next access


__all__ = (
    "CodeWeaverSettings",
    "DefaultAgentProviderSettings",
    "DefaultDataProviderSettings",
    "DefaultEmbeddingProviderSettings",
    "DefaultFastMcpServerSettings",
    "DefaultRerankingProviderSettings",
    "FastMcpServerSettings",
    "FileFilterSettings",
    "FileFilterSettingsDict",
    "get_settings",
    "get_settings_map",
    "merge_agent_model_settings",
    "reset_settings",
    "update_settings",
)
