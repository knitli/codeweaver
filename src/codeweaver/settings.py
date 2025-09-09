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

from collections.abc import Callable
from functools import cached_property
from pathlib import Path
from typing import Annotated, Any, Literal, cast

from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.server.server import DuplicateBehavior
from fastmcp.tools.tool import Tool
from mcp.server.auth.settings import AuthSettings
from pydantic import BaseModel, ConfigDict, Field, PositiveInt, computed_field, field_validator
from pydantic_ai.settings import ModelSettings as AgentModelSettings
from pydantic_ai.settings import merge_model_settings
from pydantic_core import from_json
from pydantic_settings import BaseSettings, SettingsConfigDict

from codeweaver._common import UNSET, Unset
from codeweaver._constants import DEFAULT_EXCLUDED_DIRS, DEFAULT_EXCLUDED_EXTENSIONS
from codeweaver.exceptions import MissingValueError
from codeweaver.provider import Provider, ProviderKind
from codeweaver.settings_types import (
    AVAILABLE_MIDDLEWARE,
    AgentProviderSettings,
    DataProviderSettings,
    EmbeddingModelSettings,
    EmbeddingProviderSettings,
    FileFilterSettingsDict,
    LoggingSettings,
    MiddlewareOptions,
    RerankingModelSettings,
    RerankingProviderSettings,
    RignoreSettings,
    UvicornServerSettings,
    default_config_file_locations,
)


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

    def model_post_init(self, _context: MiddlewareContext[Any] | None = None, /) -> None:
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
            description="Additional middleware to add to the FastMCP server. Values should be full path import strings, like `codeweaver.middleware.statistics.StatisticsMiddleware`.",
            validation_alias="middleware",
            serialization_alias="middleware",
        ),
    ] = None
    additional_tools: Annotated[
        list[str] | None,
        Field(
            description="Additional tools to add to the FastMCP server. Values can be either full path import strings, like `codeweaver.tools.git.GitTool`, or just the tool name, like `GitTool`.",
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
            default_factory=lambda: importlib.import_module("codeweaver._utils").get_project_root(),
            description="""Root path of the codebase to analyze. CodeWeaver will try to detect the project root automatically if you don't provide one.""",
        ),
    ]

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
            self.project_path = importlib.import_module("codeweaver._utils").get_project_root()
        return self.project_path.resolve()


# Global settings instance
_settings: CodeWeaverSettings | None = None


def get_settings(path: Path | None = None) -> CodeWeaverSettings:
    """Get the global settings instance."""
    global _settings

    if path:
        return CodeWeaverSettings(project_path=path)
    if _settings is None:
        _settings = CodeWeaverSettings(project_path=Path.cwd())
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
    "get_provider_settings",
    "get_settings",
    "merge_agent_model_settings",
    "reload_settings",
)
