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
import inspect

from collections.abc import Callable
from functools import cached_property
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, Literal, cast

from fastmcp.server.auth.auth import OAuthProvider
from fastmcp.server.middleware import Middleware
from fastmcp.server.server import DuplicateBehavior
from fastmcp.tools.tool import Tool
from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    FieldSerializationInfo,
    GetPydanticSchema,
    PositiveInt,
    ValidationInfo,
    computed_field,
    field_serializer,
    field_validator,
)
from pydantic_ai.settings import ModelSettings as AgentModelSettings
from pydantic_ai.settings import merge_model_settings
from pydantic_core import from_json, to_json
from pydantic_settings import BaseSettings, SettingsConfigDict

from codeweaver._common import UNSET, Unset
from codeweaver._constants import DEFAULT_EXCLUDED_DIRS, DEFAULT_EXCLUDED_EXTENSIONS
from codeweaver._utils import walk_down_to_git_root
from codeweaver.exceptions import MissingValueError
from codeweaver.provider import Provider, ProviderKind
from codeweaver.settings_types import (
    AVAILABLE_MIDDLEWARE,
    AgentProviderSettings,
    DataProviderSettings,
    EmbeddingModelSettings,
    EmbeddingProviderSettings,
    FileFilterSettingsDict,
    RerankingModelSettings,
    RerankingProviderSettings,
    RignoreSettings,
    UvicornServerSettings,
    default_config_file_locations,
)


if TYPE_CHECKING:
    from codeweaver.settings_types import LoggingSettings, MiddlewareOptions


DefaultDataProviderSettings = (
    DataProviderSettings(provider=Provider.TAVILY, enabled=False, api_key=None, other=None),
    # DuckDuckGo
    DataProviderSettings(provider=Provider.DUCKDUCKGO, enabled=True, api_key=None, other=None),
)

DefaultEmbeddingProviderSettings = (
    EmbeddingProviderSettings(
        provider=Provider.VOYAGE,
        enabled=True,
        model_settings=EmbeddingModelSettings(model="voyage-code-3"),
    ),
)

DefaultRerankingProviderSettings = (
    RerankingProviderSettings(
        provider=Provider.VOYAGE,
        enabled=True,
        model_settings=RerankingModelSettings(model="rerank-2.5"),
    ),
)

DefaultAgentProviderSettings = (
    AgentProviderSettings(
        provider=Provider.ANTHROPIC,
        enabled=True,
        model="claude-sonnet-4-latest",
        model_settings=AgentModelSettings(),
    ),
)


def merge_agent_model_settings(
    base: AgentModelSettings | None, override: AgentModelSettings | None
) -> AgentModelSettings | None:
    """A convenience re-export of `merge_model_settings` for agent model settings."""
    return merge_model_settings(base, override)


class FileFilterSettings(BaseModel):
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

    model_config = ConfigDict(
        json_schema_extra={"NoTelemetryProps": ["forced_includes", "excludes"]}
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
            description="""Whether to include the .github directory in search and indexing. Because the .github directory is hidden, it would be otherwise discluded from default settings. Most people want to include it for work on GitHub Actions, workflows, and other GitHub-related files."""
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

    def model_post_init(self, __context: Any, /) -> None:
        """Post-initialization processing."""
        if self.include_github_dir:
            self.forced_includes = self.forced_includes.union(frozenset({"**/.github/**"}))

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
        base_kwargs = self._self_to_kwargs(self)
        base_kwargs["filter"] = self.filter
        return base_kwargs

    def to_kwargs(self) -> RignoreSettings:
        """Serialize to kwargs for rignore."""
        return self._adjust_settings()


class ProviderSettings(BaseModel):
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


class FastMcpServerSettings(BaseModel):
    """Settings for the FastMCP server.

    These settings don't represent the complete set of FastMCP server settings, but the ones users can configure. The remaining settings, if changed, could break functionality or cause unexpected behavior.
    """

    model_config = ConfigDict(
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

    transport: Annotated[
        Literal["stdio", "http"] | None,
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
    path: Annotated[
        str | None,
        Field(description="""Route path for the FastMCP server. Defaults to '/codeweaver/'"""),
    ] = "/codeweaver/"
    auth: Annotated[
        OAuthProvider | None,
        Field(description="""OAuth provider configuration"""),
        GetPydanticSchema(lambda _schema, handler: handler(Any)),
    ] = None
    cache_expiration_seconds: float | None = None
    on_duplicate_tools: DuplicateBehavior | None = None
    on_duplicate_resources: DuplicateBehavior | None = None
    on_duplicate_prompts: DuplicateBehavior | None = None
    resource_prefix_format: Literal["protocol", "path"] | None = None
    # these are each "middleware", "tools", and "dependencies" for FastMCP. But we prefix them with "additional_" to make it clear these are *in addition to* the ones we provide by default.
    additional_middleware: Annotated[
        list[
            Annotated[Middleware, GetPydanticSchema(lambda _s, handler: handler(Any))]
            | Callable[..., Any]
        ]
        | None,
        Field(
            description="""Additional middleware to add to the FastMCP server.""",
            serialization_alias="middleware",
        ),
    ] = None
    additional_tools: Annotated[
        list[Tool | Callable[..., Any]] | None,
        Field(
            description="""Additional tools to add to the FastMCP server.""",
            serialization_alias="tools",
        ),
    ] = None
    additional_dependencies: Annotated[
        list[str] | None,
        Field(
            description="""Additional dependencies to add to the FastMCP server.""",
            serialization_alias="dependencies",
        ),
    ] = None

    def _serialize_additional_for_json(self, _v: Any, info: FieldSerializationInfo) -> bytes:
        """Helper to serialize additional fields for JSON output."""
        if info.field_name == "additional_middleware":
            return to_json({
                "additional_middleware": [
                    mw.__class__.__qualname__ if isinstance(mw, Middleware) else str(mw)
                    for mw in (self.additional_middleware or [])
                ]
            })
        if info.field_name == "additional_tools":
            return to_json({
                "additional_tools": [
                    tool.name if isinstance(tool, Tool) else str(tool)
                    for tool in (self.additional_tools or [])
                ]
            })
        if info.field_name == "additional_dependencies":
            return to_json({"additional_dependencies": self.additional_dependencies or []})
        return b"{}"

    def _serialize_additional_for_python(
        self, _v: Any, info: FieldSerializationInfo
    ) -> dict[Literal["middleware", "tools", "dependencies"], list[Any]]:
        """Helper to serialize additional fields for Python output."""
        if info.field_name == "additional_middleware":
            return {"middleware": self.additional_middleware or []}
        if info.field_name == "additional_tools":
            return {"tools": self.additional_tools or []}
        if info.field_name == "additional_dependencies":
            return {"dependencies": self.additional_dependencies or []}
        return {}

    @field_serializer(
        *("additional_middleware", "additional_tools", "additional_dependencies"),
        mode="plain",
        when_used="always",
    )
    def serialize_additional_fields(
        self, _v: Any, info: FieldSerializationInfo
    ) -> dict[Literal["middleware", "tools", "dependencies"], list[Any]] | bytes:
        """
        Serialize additional fields for the FastMCP server settings.
        """
        if info.mode == "json":
            return self._serialize_additional_for_json(_v, info)
        return self._serialize_additional_for_python(_v, info)

    @classmethod
    def _validate_additional_from_python(cls, value: list[Any], info: ValidationInfo) -> list[Any]:
        """Validate additional fields from Python input."""
        if info.field_name and info.field_name.startswith("additional_"):
            if "middleware" in info.field_name and isinstance(value, str) and "." in value:
                return [cls._try_to_find_middleware(v) or v for v in (value or []) if value and v]
            if "tools" in info.field_name:
                return [cls._try_to_find_tool(v) or v for v in (value or []) if value and v]
            if "dependencies" in info.field_name:
                return [v for v in (value or []) if value and isinstance(v, str)]
        return value

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
    def _return_if_subclass(value: str, cls: type[Tool | Middleware]) -> type | str | None:
        """Return the value if it is a subclass of the given class."""
        common_name = "Middleware" if cls is Middleware else "Tool"
        return next(
            (
                subclass
                for subclass in cls.__subclasses__()
                if subclass.__name__ == value
                or subclass.__qualname__ == value
                or (str(subclass) in value and str(subclass) != common_name)
            ),
            value,
        )

    @classmethod
    def _try_to_find_middleware(cls, value: Any) -> Middleware | Callable[..., Any] | str | None:
        """Try to find a middleware class or callable from a string or other input."""
        if isinstance(value, Middleware) or callable(value):
            return value
        if not value:
            return None
        if isinstance(value, str) and any(
            mw.__name__ == value or mw.__qualname__ == value for mw in AVAILABLE_MIDDLEWARE
        ):
            return next(
                (
                    mw
                    for mw in AVAILABLE_MIDDLEWARE
                    if mw.__name__ == value or mw.__qualname__ == value
                ),
                value,
            )
        if isinstance(value, str) and "." in value and (imported := cls._attempt_import(value)):
            return imported
        return cls._return_if_subclass(value, Middleware)

    @classmethod
    def _try_to_find_tool(cls, value: Any) -> Tool | Callable[..., Any] | str | None:
        """Try to find a tool class or callable from a string or other input."""
        if isinstance(value, Tool) or callable(value):
            return value
        if not value:
            return None
        if isinstance(value, str) and "." in value and (imported := cls._attempt_import(value)):
            return imported
        return cls._return_if_subclass(value, Tool)

    @classmethod
    @field_validator(
        *("additional_middleware", "additional_tools", "additional_dependencies"), mode="plain"
    )
    def validate_additional_fields(
        cls,
        value: str | bytes | bytearray | list[str | Middleware | Tool | Callable[..., Any]] | None,
        info: ValidationInfo,
    ) -> Any:
        """
        Validate additional fields for the FastMCP server settings.
        """
        if not value:
            return []
        if isinstance(value, str | bytes | bytearray):
            return cls.validate_additional_fields(from_json(value), info=info)
        return cls._validate_additional_from_python(value, info=info)


DefaultFastMcpServerSettings = FastMcpServerSettings.model_validate({
    "transport": "stdio",
    "auth": None,
    "cache_expiration_seconds": None,
    "on_duplicate_tools": "warn",
    "on_duplicate_resources": "warn",
    "on_duplicate_prompts": "warn",
    "resource_prefix_format": "path",
    "middleware": None,
    "tools": None,
    "dependencies": None,
})


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
        env_prefix="CODEWEAVER_",
        env_nested_delimiter="__",
        env_file=(".codeweaver.local.env", ".env", ".codeweaver.env"),
        toml_file=default_config_file_locations(),
        yaml_file=default_config_file_locations(as_yaml=True),
        json_file=default_config_file_locations(as_json=True),
        case_sensitive=False,
        validate_assignment=True,
        cli_kebab_case=True,
        extra="allow",  # Allow extra fields in the configuration for plugins/extensions
        json_schema_extra={
            "NoTelemetryProps": ["project_path", "project_root", "project_name", "config_file"]
        },
    )

    # Core settings
    project_path: Annotated[
        Path,
        Field(
            description="""Root path of the codebase to analyze. CodeWeaver will try to detect the project root automatically if you don't provide one."""
        ),
    ] = walk_down_to_git_root()

    project_name: Annotated[
        str | None, Field(description="""Project name (auto-detected from directory if None)""")
    ] = None

    config_file: Annotated[
        Path | None, Field(description="""Path to the configuration file, if any""", exclude=True)
    ] = None

    # Performance settings
    token_limit: Annotated[
        PositiveInt, Field(le=130_000, description="""Maximum tokens per response""")
    ] = 10_000
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
    ] = None

    filter_settings: Annotated[
        FileFilterSettings, Field(description="""File filtering settings""")
    ] = FileFilterSettings()

    embedding: Annotated[
        tuple[EmbeddingModelSettings, ...] | None,
        Field(description="""Embedding provider configuration"""),
    ] = None  # TODO: Add defaults

    """
    vector_store: Annotated[
        BaseVectorStoreConfig,
        Field(default_factory=QdrantConfig, description="Vector store provider configuration"),
    ] = QdrantConfig()
    """
    # Feature flags
    enable_background_indexing: Annotated[
        bool,
        Field(
            description="""Enable automatic background indexing (default behavior and recommended)"""
        ),
    ] = True
    enable_telemetry: Annotated[
        bool,
        Field(
            description="""Enable privacy-friendly usage telemetry. On by default. We do not collect any identifying information -- we hash all file and directory paths, repository names, and other identifiers to ensure privacy while still gathering useful aggregate data for improving CodeWeaver. You can see exactly what we collect, and how we collect it [here](services/telemetry.py). You can disable this if you prefer not to send any data. You can also provide your own PostHog Project Key to collect your own telemetry data. We will not use this information for anything else -- it is only used to improve CodeWeaver."""
        ),
    ] = True
    enable_health_endpoint: Annotated[
        bool, Field(description="""Enable the health check endpoint""")
    ] = True
    health_endpoint_path: Annotated[
        str | None, Field(description="""Path for the health check endpoint""")
    ] = "/health/"
    enable_statistics_endpoint: Annotated[
        bool, Field(description="""Enable the statistics endpoint""")
    ] = True
    statistics_endpoint_path: Annotated[
        str | None, Field(description="""Path for the statistics endpoint""")
    ] = "/statistics/"
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

    agent_settings: Annotated[
        AgentModelSettings | None,
        Field(description="""Model settings for ai agents. Required for `enable_precontext`"""),
    ] = None

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

    def model_post_init(self, __context: Any, /) -> None:
        """Post-initialization validation."""
        # Ensure project path exists and is readable
        if not self.project_name:
            self.project_name = self.project_root.name

    @computed_field
    @cached_property
    def project_root(self) -> Path:
        """Get the project root directory."""
        if not self.project_path:
            self.project_path = walk_down_to_git_root()
        return self.project_path.resolve()


# Global settings instance
_settings: CodeWeaverSettings | None = None


def get_settings(path: Path | None = None) -> CodeWeaverSettings:
    """Get the global settings instance."""
    global _settings
    if path:
        return CodeWeaverSettings(config_file=path)
    if _settings is None:
        _settings = CodeWeaverSettings()
    return _settings


def reload_settings() -> CodeWeaverSettings:
    """Reload settings from configuration sources."""
    global _settings
    _settings = None
    return get_settings()


def get_provider_settings(provider_kind: ProviderKind | str) -> Any:
    """Check a setting value by a tuple of keys (the path to the setting)."""
    if isinstance(provider_kind, str):
        provider_kind = ProviderKind.from_string(provider_kind)
    if provider_kind == ProviderKind.UNSET:  # type: ignore
        raise MissingValueError(
            "Provider kind cannot be _UNSET",
            "settings.get_provider_settings: `provider_kind` is _UNSET",
            None,
            ["This may be a bug in CodeWeaver, please report it."],
        )
