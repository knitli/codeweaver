# sourcery skip: name-type-suffix, no-complex-if-expressions
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
import logging
import re

from collections.abc import Callable
from functools import cached_property, partial
from importlib import util
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, Literal, NamedTuple, Self, Unpack, cast

from fastmcp.server.middleware import Middleware, MiddlewareContext
from fastmcp.server.server import DuplicateBehavior
from fastmcp.tools.tool import Tool
from mcp.server.auth.settings import AuthSettings
from pydantic import (
    DirectoryPath,
    Field,
    FilePath,
    PositiveInt,
    PrivateAttr,
    PydanticUserError,
    ValidationError,
    computed_field,
    field_validator,
)
from pydantic.fields import ComputedFieldInfo, FieldInfo
from pydantic_ai.settings import merge_model_settings
from pydantic_core import from_json
from pydantic_settings import (
    BaseSettings,
    JsonConfigSettingsSource,
    PydanticBaseSettingsSource,
    SettingsConfigDict,
    TomlConfigSettingsSource,
    YamlConfigSettingsSource,
)

from codeweaver.common.utils.lazy_importer import lazy_import
from codeweaver.config.chunker import ChunkerSettings
from codeweaver.config.logging import LoggingSettings
from codeweaver.config.middleware import (
    AVAILABLE_MIDDLEWARE,
    ErrorHandlingMiddlewareSettings,
    LoggingMiddlewareSettings,
    MiddlewareOptions,
    RateLimitingMiddlewareSettings,
    RetryMiddlewareSettings,
)
from codeweaver.config.providers import (
    AgentModelSettings,
    AgentProviderSettings,
    DataProviderSettings,
    EmbeddingModelSettings,
    EmbeddingProviderSettings,
    RerankingModelSettings,
    RerankingProviderSettings,
    SparseEmbeddingModelSettings,
    VectorStoreSettings,
)
from codeweaver.config.types import (
    CodeWeaverSettingsDict,
    RignoreSettings,
    UvicornServerSettings,
    default_config_file_locations,
)
from codeweaver.core.file_extensions import DEFAULT_EXCLUDED_DIRS, DEFAULT_EXCLUDED_EXTENSIONS
from codeweaver.core.types.dictview import DictView
from codeweaver.core.types.enum import AnonymityConversion
from codeweaver.core.types.models import BasedModel
from codeweaver.core.types.sentinel import UNSET, Unset
from codeweaver.providers.provider import Provider


if TYPE_CHECKING:
    from codeweaver.core.types.aliases import FilteredKeyT
    from codeweaver.core.types.enum import AnonymityConversion


logger = logging.getLogger(__name__)

BRACKET_PATTERN: re.Pattern[str] = re.compile("\\[.+\\]")


DefaultDataProviderSettings = (
    DataProviderSettings(provider=Provider.TAVILY, enabled=False, api_key=None, other=None),
    # DuckDuckGo
    DataProviderSettings(provider=Provider.DUCKDUCKGO, enabled=True, api_key=None, other=None),
)


# TODO: move defaault computation to provider module.
class DeterminedDefaults(NamedTuple):
    """Tuple for determined default embedding settings."""

    provider: Provider
    model: str
    enabled: bool


def _get_default_embedding_settings() -> DeterminedDefaults:
    """Determine the default embedding provider, model, and enabled status based on available libraries."""
    for lib in (
        "voyageai",
        "mistral",
        "google",
        "fastembed_gpu",
        "fastembed",
        "sentence_transformers",
    ):
        if util.find_spec(lib) is not None:
            # all three of the top defaults are extremely capable
            if lib == "voyageai":
                return DeterminedDefaults(
                    provider=Provider.VOYAGE, model="voyage:voyage-code-3", enabled=True
                )
            if lib == "mistral":
                return DeterminedDefaults(
                    provider=Provider.MISTRAL, model="mistral:codestral-embed", enabled=True
                )
            if lib == "google":
                return DeterminedDefaults(
                    provider=Provider.GOOGLE, model="google/gemini-embedding-001", enabled=True
                )
            if lib in {"fastembed_gpu", "fastembed"}:
                return DeterminedDefaults(
                    # showing its age but it's still a solid lightweight option
                    provider=Provider.FASTEMBED,
                    model="fastembed:BAAI/bge-small-en-v1.5",
                    enabled=True,
                )
            if lib == "sentence_transformers":
                return DeterminedDefaults(
                    provider=Provider.SENTENCE_TRANSFORMERS,
                    # embedding-small-english-r2 is *very lightweight* and quite capable with a good context window (8192 tokens)
                    model="sentence-transformers:ibm-granite/granite-embedding-small-english-r2",
                    enabled=True,
                )
    logger.warning(
        "No default embedding provider libraries found. Embedding functionality will be disabled unless explicitly set in your config or environment variables."
    )
    return DeterminedDefaults(provider=Provider.UNSET, model="NONE", enabled=False)


_embedding_defaults = _get_default_embedding_settings()

DefaultEmbeddingProviderSettings = (
    EmbeddingProviderSettings(
        provider=_embedding_defaults.provider,
        enabled=_embedding_defaults.enabled,
        model_settings=EmbeddingModelSettings(model=_embedding_defaults.model),
    ),
)


def _get_default_sparse_embedding_settings() -> DeterminedDefaults:
    """Determine the default sparse embedding provider, model, and enabled status based on available libraries."""
    for lib in ("sentence_transformers", "fastembed_gpu", "fastembed"):
        if util.find_spec(lib) is not None:
            if lib == "sentence_transformers":
                return DeterminedDefaults(
                    provider=Provider.SENTENCE_TRANSFORMERS,
                    model="opensearch:opensearch-neural-sparse-encoding-doc-v3-gte",
                    enabled=True,
                )
            if lib in {"fastembed_gpu", "fastembed"}:
                return DeterminedDefaults(
                    provider=Provider.FASTEMBED, model="prithivida/Splade_PP_en_v2", enabled=True
                )
    # Sentence-Transformers and Fastembed are the *only* sparse embedding options we support
    logger.warning(
        "No sparse embedding provider libraries found. Sparse embedding functionality disabled."
    )
    return DeterminedDefaults(provider=Provider.UNSET, model="NONE", enabled=False)


_sparse_embedding_defaults = _get_default_sparse_embedding_settings()

DefaultSparseEmbeddingProviderSettings = (
    EmbeddingProviderSettings(
        provider=_sparse_embedding_defaults.provider,
        enabled=_sparse_embedding_defaults.enabled,
        sparse_model_settings=SparseEmbeddingModelSettings(model=_sparse_embedding_defaults.model),
    ),
)


def _get_default_reranking_settings() -> DeterminedDefaults:
    """Determine the default reranking provider, model, and enabled status based on available libraries."""
    for lib in ("voyageai", "fastembed_gpu", "fastembed", "sentence_transformers"):
        if util.find_spec(lib) is not None:
            if lib == "voyageai":
                return DeterminedDefaults(
                    provider=Provider.VOYAGE, model="voyage:rerank-2.5", enabled=True
                )
            if lib in {"fastembed_gpu", "fastembed"}:
                return DeterminedDefaults(
                    provider=Provider.FASTEMBED,
                    model="fastembed:jinaai/jina-reranker-v2-base-multilingual",
                    enabled=True,
                )
            if lib == "sentence_transformers":
                return DeterminedDefaults(
                    provider=Provider.SENTENCE_TRANSFORMERS,
                    # on the heavier side for what we aim for as a default but very capable
                    model="sentence-transformers:BAAI/bge-reranker-v2-m3",
                    enabled=True,
                )
    logger.warning(
        "No default reranking provider libraries found. Reranking functionality will be disabled unless explicitly set in your config or environment variables."
    )
    return DeterminedDefaults(provider=Provider.UNSET, model="NONE", enabled=False)


_reranking_defaults = _get_default_reranking_settings()

DefaultRerankingProviderSettings = (
    RerankingProviderSettings(
        provider=_reranking_defaults.provider,
        enabled=_reranking_defaults.enabled,
        model_settings=RerankingModelSettings(model=_reranking_defaults.model),
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


def _get_project_name() -> str:
    """Get the current project name from settings."""
    # we'll try to get it from the project root but it might not be initialized yet
    with contextlib.suppress(PydanticUserError, ValidationError, ValueError):
        settings = get_settings()
        if settings.project_name:
            return settings.project_name
        return settings.project_path.name
    return "your_project_name"


def get_storage_path() -> Path:
    """Get the default storage path for index data."""
    from codeweaver.common.utils import get_user_config_dir

    return Path(get_user_config_dir()) / f"{_get_project_name()}_index.json"


def _resolve_globs(path_string: str, repo_root: Path) -> set[Path]:
    """Resolve glob patterns in a path string."""
    if "*" in path_string or "?" in path_string or BRACKET_PATTERN.search(path_string):
        return set(repo_root.glob(path_string))
    if (path := (repo_root / path_string)) and path.exists():
        return {path} if path.is_file() else set(path.glob("**/*"))
    return set()


class FilteredPaths(NamedTuple):
    """Tuple of included and excluded file paths."""

    includes: frozenset[Path]
    excludes: frozenset[Path]

    @classmethod
    async def from_settings(cls, indexing: IndexerSettings, repo_root: Path) -> FilteredPaths:
        """Resolve included and excluded files based on filter settings.

        Resolves glob patterns for include and exclude paths, filtering includes for excluded extensions.

        If a file is specifically included in the `forced_includes`, it will not be excluded even if it matches an excluded extension or excludes.

        "Specifically included" means that it was defined directly in the `forced_includes`, and **not** as a glob pattern.

        This constructor is async so that it can resolve quietly in the background without slowing initialization.
        """
        settings = indexing.model_dump(mode="python")
        other_files: set[Path] = set()
        specifically_included_files = {
            Path(file)
            for file in settings.get("forced_includes", set())
            if file
            and "*" not in file
            and ("?" not in file)
            and Path(file).exists()
            and Path(file).is_file()
        }
        for include in settings.get("forced_includes", set()):
            other_files |= _resolve_globs(include, repo_root)
        for ext in settings.get("excluded_extensions", set()):
            if not ext:
                continue
            ext = ext.lstrip("*?[]")
            ext = ext if ext.startswith(".") else f".{ext}"
            other_files -= {
                file
                for file in other_files
                if file.suffix == ext and file not in specifically_included_files
            }
        excludes: set[Path] = set()
        excluded_files = settings.get("excluded_files", set())
        for exclude in excluded_files:
            if exclude:
                excludes |= _resolve_globs(exclude, repo_root)
        excludes |= specifically_included_files
        other_files -= {
            exclude for exclude in excludes if exclude not in specifically_included_files
        }
        other_files -= {None, Path(), Path("./"), Path("./.")}
        excludes -= {None, Path(), Path("./"), Path("./.")}
        return FilteredPaths(frozenset(other_files), frozenset(excludes))


class IndexerSettings(BasedModel):
    """Settings for indexing and file filtering.

    ## Path Resolution and Deconfliction

    Any configured paths or path patterns should be relative to the project root directory.

    CodeWeaver deconflicts paths in the following ways:
    - If a file is specifically defined in `forced_includes`, it will always be included, even if it matches an exclude pattern.
      - This doesn't apply if it is defined in `forced_includes` with a glob pattern that matches an excluded file (by extension or glob/path).
      - This also doesn't apply to directories.
    - Other filters like `use_gitignore`, `use_other_ignore_files`, and `ignore_hidden` will apply to all files **not in `forced_includes`**.
      - Files in `forced_includes`, including files defined from glob patterns, will *not* be filtered by these settings.
    - if `include_github_dir` is True (default), the glob `**/.github/**` will be added to `forced_includes`.
    - if `include_tooling_dirs` is True (default and recommended), common hidden tooling directories will be included *if they aren't .gitignored* (assuming `use_gitignore` is enabled, which is default). Any gitignored files will be excluded. This includes directories like `.vscode`, `.idea`, but also more specialized ones like `.moon`, `.husky`, and LLM-specific ones like `.codeweaver`, `.claude`, `.codex`, `.roo`, and more.
    """

    forced_includes: Annotated[
        frozenset[str | Path],
        Field(
            description="""Directories, files, or [glob patterns](https://docs.python.org/3/library/pathlib.html#pathlib-pattern-language) to include in search and indexing. This is a set of strings, so you can use glob patterns like `**/src/**` or `**/*.py` to include directories or files."""
        ),
    ] = frozenset()
    excludes: Annotated[
        frozenset[str | Path],
        Field(
            description="""Directories, files, or [glob patterns](https://docs.python.org/3/library/pathlib.html#pathlib-pattern-language) to exclude from search and indexing. This is a set of strings, so you can use glob patterns like `**/node_modules/**` or `**/*.log` to exclude directories or files. You don't need to provide gitignored paths here if `use_gitignore` is enabled (default)."""
        ),
    ] = DEFAULT_EXCLUDED_DIRS
    excluded_extensions: Annotated[
        frozenset[str], Field(description="""File extensions to exclude from search and indexing""")
    ] = DEFAULT_EXCLUDED_EXTENSIONS
    use_gitignore: Annotated[
        bool, Field(description="""Whether to use .gitignore for filtering. Enabled by default.""")
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
            description="""Whether to include the .github directory in search and indexing. Because the .github directory is hidden, it wouldn't be included in default settings. Most people want to include it for work on GitHub Actions, workflows, and other GitHub-related files. Note: this setting will also include `.circleci` if present. Any subdirectories or files within `.github` or `.circleci` that are gitignored will still be excluded."""
        ),
    ] = True
    include_tooling_dirs: Annotated[
        bool,
        Field(
            description="""Whether to include common hidden tooling directories in search and indexing. This is enabled by default and recommended for most users. Still respects .gitignore rules, so any gitignored files will be excluded."""
        ),
    ] = True
    other_ignore_kwargs: Annotated[
        RignoreSettings | Unset,
        Field(
            description="""Other kwargs to pass to `rignore`. See <https://pypi.org/project/rignore/>. By default we set max_filesize to 5MB and same_file_system to True."""
        ),
    ] = UNSET

    default_rignore_settings: Annotated[
        RignoreSettings,
        Field(
            description="""Default settings for rignore. These are used if not overridden by user settings in `other_ignore_kwargs`."""
        ),
    ] = RignoreSettings({
        "max_filesize": 5 * 1024 * 1024,
        "same_file_system": True,
        "follow_links": False,
    })
    only_index_on_command: Annotated[
        bool,
        Field(
            description="""Disabled by default and usually **not recommended**. This setting disables background indexing, requiring you to manually trigger indexing by command or program call. CodeWeaver uses background indexing to ensure it always has an accurate view of the codebase, so disabling this can severely impact the quality of results. We expose this setting for troubleshooting, debugging, and some isolated use cases where codeweaver may be orchestrated externally or supplied with data from other sources."""
        ),
    ] = False
    _index_storage_path: Annotated[
        Path | None,
        Field(
            description=rf"""\
            Path to store index data locally. The default is in your user configuration directory (like ~/.config/codeweaver/{_get_project_name()}_index.json or c:\Users\your_username\AppData\Roaming\codeweaver\your_project_name_index.json).  If not set, CodeWeaver will use the default path.

            Developer Note: We set the default lazily after initialization to avoid circular import issues. Internally, we use the `cache_dir` property to get the effective storage path. We recommend you do too if you need to programmatically access this value. We only keep this field public for user configuration.
            """,
            serialization_alias="index_storage_path",
            validation_alias="index_storage_path",
        ),
    ] = None

    _inc_exc_set: Annotated[bool, PrivateAttr()] = False

    @computed_field
    @property
    def cache_dir(self) -> DirectoryPath:
        """Effective storage path for index data."""
        path = self._index_storage_path or get_storage_path()
        if not path.parent.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
        if not path.exists():
            path.touch()
        return path

    @computed_field
    @property
    def storage_file(self) -> FilePath:
        """Effective storage file path for index data."""
        if self._index_storage_path:
            return self._index_storage_path
        project_name = _get_project_name()
        self._index_storage_path = self.cache_dir / f"{project_name}_index.json"
        return self._index_storage_path

    @computed_field
    @property
    def inc_exc_set(self) -> bool:
        """Whether includes and excludes have been set."""
        return self._inc_exc_set

    @computed_field
    @property
    def checkpoint_file(self) -> FilePath:
        """Path to the checkpoint file for indexing progress."""
        return self.cache_dir / "indexing_checkpoint.json"

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        from codeweaver.core.types import AnonymityConversion, FilteredKey

        return {
            FilteredKey("_index_storage_path"): AnonymityConversion.HASH,
            FilteredKey("additional_ignores"): AnonymityConversion.COUNT,
            FilteredKey("cache_dir"): AnonymityConversion.HASH,
            FilteredKey("checkpoint_file"): AnonymityConversion.HASH,
            FilteredKey("excluded_extensions"): AnonymityConversion.COUNT,
            FilteredKey("excludes"): AnonymityConversion.COUNT,
            FilteredKey("forced_includes"): AnonymityConversion.COUNT,
            FilteredKey("storage_file"): AnonymityConversion.HASH,
        }

    def model_post_init(self, _context: MiddlewareContext[Any] | None = None, /) -> None:
        """Post-initialization processing."""
        if self.include_github_dir:
            self.forced_includes |= {"**/.github/**"}
        if self.include_tooling_dirs:
            from codeweaver.core.file_extensions import (
                COMMON_LLM_TOOLING_PATHS,
                COMMON_TOOLING_PATHS,
            )

            file_endings = {
                ".json",
                ".yaml",
                ".yml",
                ".toml",
                ".lock",
                ".sbt",
                ".properties",
                ".js",
                ".ts",
                ".cmd",
                ".xml",
            }

            tooling_dirs = {
                path
                for tool in COMMON_TOOLING_PATHS
                for path in tool[1]
                if path.name.startswith(".")
                or (str(path).startswith(".") and path.suffix not in file_endings)
            } | {
                path
                for tool in COMMON_LLM_TOOLING_PATHS
                for path in tool[1]
                if path.name.startswith(".")
                or (str(path).startswith(".") and path.suffix not in file_endings)
            }
            self.forced_includes |= {f"**/{directory}/**" for directory in tooling_dirs}

    async def set_inc_exc(self, project_path: Path) -> None:
        """Set that includes and excludes have been configured."""
        self.forced_includes, self.excludes = await FilteredPaths.from_settings(self, project_path)
        self._inc_exc_set = True

    def _as_settings(self) -> RignoreSettings:
        """Convert self, either as an instance or as a serialized python dictionary, to kwargs for rignore."""
        rignore_settings = self.default_rignore_settings | (
            {} if isinstance(self.other_ignore_kwargs, Unset) else self.other_ignore_kwargs
        )
        rignore_settings["path"] = get_settings_map()["project_path"]
        rignore_settings["ignore_hidden"] = bool(
            self.ignore_hidden and not self.include_github_dir and not self.include_tooling_dirs
        )
        rignore_settings["read_ignore_files"] = self.use_other_ignore_files
        rignore_settings["read_git_ignore"] = self.use_gitignore
        rignore_settings["additional_ignore_paths"] = [
            str(p) for p in self.excludes if not any(char for char in ("*?[]") if char in str(p))
        ]
        rignore_settings["additional_ignores"] = [
            str(p)
            for p in self.excludes
            if str(p) not in rignore_settings["additional_ignore_paths"]
        ]
        rignore_settings["should_exclude_entry"] = self.filter
        return RignoreSettings(rignore_settings)

    def construct_filter(self) -> Callable[[Path], bool]:
        """Constructs the filter function for rignore's `should_exclude_entry` parameter.

        Returns *True* for paths that should **not** be included (i.e., excluded paths).
        """

        def filter_func(settings: IndexerSettings, path: Path | str) -> bool:
            """Default filter function that respects forced includes and other settings."""
            path_obj = Path(path) if isinstance(path, str) else path
            if settings.ignore_hidden and (
                settings.include_github_dir or settings.include_tooling_dirs
            ):
                # We need to check for .github/ and tooling dirs first
                if settings.include_github_dir and (
                    path_obj.match("**/.github/**") or path_obj.match("**/.circleci/**")
                ):
                    return False
                if settings.include_tooling_dirs:
                    from codeweaver.core.file_extensions import (
                        COMMON_LLM_TOOLING_PATHS,
                        COMMON_TOOLING_PATHS,
                    )

                    # filter for tooling dirs that are hidden (i.e., start with .)
                    if {
                        p
                        for p in {
                            path
                            for tool in COMMON_TOOLING_PATHS
                            for path in tool[1]
                            if path_obj.match(f"**/{path}/**")
                        }
                        | {
                            path
                            for tool in COMMON_LLM_TOOLING_PATHS
                            for path in tool[1]
                            if path_obj.match(f"**/{path}/**")
                        }
                        if p
                        and (
                            (str(p).startswith(".") or p.name.startswith("."))
                            and ("." not in p.name[1:] or "." not in p.parts[0][1:])
                        )
                    }:
                        return False
                return True
            return False

        return partial(filter_func, self)

    @property
    def filter(self) -> Callable[[Path], bool]:
        """Cached property for the filter function."""
        return self.construct_filter()

    def to_settings(self) -> RignoreSettings:
        """Serialize to `RignoreSettings`."""
        return self._as_settings()


class ProviderSettings(BasedModel):
    """Settings for provider configuration."""

    data: Annotated[
        tuple[DataProviderSettings, ...] | Unset,
        Field(description="""Data provider configuration"""),
    ] = DefaultDataProviderSettings

    embedding: Annotated[
        tuple[EmbeddingProviderSettings, EmbeddingProviderSettings]
        | tuple[EmbeddingProviderSettings]
        | Unset,
        Field(
            description="""Embedding provider configuration. You can provide up to two embedding providers: one for dense embeddings and one for sparse embeddings."""
        ),
    ] = DefaultEmbeddingProviderSettings

    reranking: Annotated[
        tuple[RerankingProviderSettings, ...] | Unset,
        Field(
            description="""Reranking provider configuration. Note: while this field is a tuple (for consistency across settings), you can only configure one active reranking provider at a time."""
        ),
    ] = DefaultRerankingProviderSettings

    vector_store: Annotated[
        VectorStoreSettings,
        Field(
            default_factory=lambda: VectorStoreSettings(provider="memory"),
            description="""Vector store provider configuration (Qdrant or in-memory)""",
        ),
    ]

    agent: Annotated[
        tuple[AgentProviderSettings, ...] | Unset,
        Field(description="""Agent provider configuration"""),
    ] = DefaultAgentProviderSettings

    def _telemetry_keys(self) -> None:
        return None


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
            description="""Additional tools to add to the FastMCP server. Values can be either full path import strings, like `codeweaver.agent_api.git.GitTool`, or just the tool name, like `GitTool`.""",
            validation_alias="tools",
            serialization_alias="tools",
        ),
    ] = None

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        from codeweaver.core.types import AnonymityConversion, FilteredKey

        return {
            FilteredKey("auth"): AnonymityConversion.BOOLEAN,
            FilteredKey("host"): AnonymityConversion.BOOLEAN,
            FilteredKey("port"): AnonymityConversion.BOOLEAN,
            FilteredKey("additional_middleware"): AnonymityConversion.COUNT,
            FilteredKey("additional_tools"): AnonymityConversion.COUNT,
        }

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
        DirectoryPath,
        Field(
            default_factory=lambda: lazy_import("codeweaver.common.utils").get_project_path(),  # type: ignore
            description="""Root path of the codebase to analyze. CodeWeaver will try to detect the project root automatically if you don't provide one.""",
        ),
    ]

    project_name: Annotated[
        str | None, Field(description="""Project name (auto-detected from directory if None)""")
    ] = None

    provider: Annotated[
        ProviderSettings,
        Field(
            description="""Provider and model configurations for agents, data, embedding, reranking, sparse embedding, and vector store providers. Will default to default profile if not provided."""
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

    logging: Annotated[LoggingSettings | None, Field(description="""Logging configuration""")] = (
        None
    )

    middleware: Annotated[
        MiddlewareOptions | None, Field(description="""Middleware settings""")
    ] = DefaultMiddlewareSettings

    indexing: Annotated[
        IndexerSettings,
        Field(
            description="""File filtering settings""", init=False, default_factory=IndexerSettings
        ),
    ]

    chunker: Annotated[
        ChunkerSettings,
        Field(
            description="""Chunker system configuration""",
            init=False,
            default_factory=ChunkerSettings,
        ),
    ]

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

    enable_telemetry: Annotated[
        bool,
        Field(
            description="""Enable privacy-friendly usage telemetry. ON by default. We do not collect any identifying information -- we hash all file and directory paths, repository names, and other identifiers to ensure privacy while still gathering useful aggregate data for improving CodeWeaver. We add a second round of filters within Posthog cloud before we get the data just to be sure we caught everything. You can see exactly what we collect, and how we collect it [here](../telemetry). You can disable telemetry if you prefer not to send any data. You can also provide your own PostHog Project Key to collect your own telemetry data. **We will only ever use this data to improve CodeWeaver. We will never sell or share it with anyone else, and we won't use it for targeted marketing (we will use high level aggregate data, like how many people use it, and how many tokens CodeWeaver has saved.)**"""
        ),
    ] = True

    uvicorn: Annotated[
        UvicornServerSettings | None, Field(description="""Settings for the Uvicorn server""")
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
        if not self.project_name and self.project_path:
            self.project_name = self.project_path.name
        if not self.indexing:
            if not IndexerSettings.__pydantic_complete__:
                result = IndexerSettings.model_rebuild()
                logger.debug(
                    "Rebuilt IndexerSettings during CodeWeaverSettings post-init, result: %s",
                    result,
                )
            self.indexing = IndexerSettings()
            if not self.chunker:
                if not ChunkerSettings.__pydantic_complete__:
                    result = ChunkerSettings.model_rebuild()
                    logger.debug(
                        "Rebuilt ChunkerSettings during CodeWeaverSettings post-init, result: %s",
                        result,
                    )
                self.chunker = ChunkerSettings()
        if not type(self).__pydantic_complete__:
            result = type(self).model_rebuild()
            logger.debug("Rebuilt CodeWeaverSettings during post-init, result: %s", result)
        if type(self).__pydantic_complete__:
            self._map = cast(DictView[CodeWeaverSettingsDict], DictView(self.model_dump()))
            globals()["_mapped_settings"] = self._map

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        from codeweaver.core.types import AnonymityConversion, FilteredKey

        return {
            FilteredKey("project_path"): AnonymityConversion.HASH,
            FilteredKey("project_name"): AnonymityConversion.BOOLEAN,
            FilteredKey("config_file"): AnonymityConversion.HASH,
        }

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
        from codeweaver.common.utils import get_project_path

        return cls(project_path=get_project_path(), **{**kwargs, "config_file": path})  # type: ignore

    @computed_field
    @cached_property
    def project_root(self) -> Path:
        """Get the project root directory. Alias for `project_path`."""
        if not hasattr(self, "project_path") or not self.project_path:
            from codeweaver.common.utils.git import get_project_path

            self.project_path = get_project_path()
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
        """Customize the sources of settings for a specific settings class.

        Configuration precedence (highest to lowest):
        1. init_settings - Direct initialization arguments
        2. env_settings - Environment variables (CODEWEAVER_*)
        3. dotenv_settings - .env files
        4. toml_sources - TOML config files (.codeweaver.local.toml, .codeweaver.toml, etc.)
        5. yaml_sources - YAML config files (.codeweaver.local.yaml, .codeweaver.yaml, etc.)
        6. json_sources - JSON config files (.codeweaver.local.json, .codeweaver.json, etc.)
        7. file_secret_settings - Secret files (lowest priority)
        """
        sources: list[PydanticBaseSettingsSource] = [init_settings, env_settings, dotenv_settings]

        # Add TOML config source if configured
        if toml_file := settings_cls.model_config.get("toml_file"):
            sources.append(TomlConfigSettingsSource(settings_cls, toml_file=toml_file))

        # Add YAML config source if configured
        if yaml_file := settings_cls.model_config.get("yaml_file"):
            sources.append(YamlConfigSettingsSource(settings_cls, yaml_file=yaml_file))

        # Add JSON config source if configured
        if json_file := settings_cls.model_config.get("json_file"):
            sources.append(JsonConfigSettingsSource(settings_cls, json_file=json_file))

        # Add file secret settings last (lowest priority)
        sources.append(file_secret_settings)

        return tuple(sources)

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
    from codeweaver.common.utils.git import get_project_path

    root = get_project_path()
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
    "IndexerSettings",
    "get_settings",
    "get_settings_map",
    "merge_agent_model_settings",
    "reset_settings",
    "update_settings",
)
