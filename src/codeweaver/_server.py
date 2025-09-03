# sourcery skip: snake-case-variable-declarations
"""Initialize the FastMCP application with default middleware and settings."""

from __future__ import annotations

import logging
import re
import time

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from types import FunctionType
from typing import Annotated, Any, Literal, cast

from fastmcp import FastMCP
from fastmcp.server.middleware.error_handling import ErrorHandlingMiddleware, RetryMiddleware
from fastmcp.server.middleware.logging import LoggingMiddleware, StructuredLoggingMiddleware
from fastmcp.server.middleware.middleware import Middleware
from fastmcp.server.middleware.rate_limiting import RateLimitingMiddleware
from pydantic import ConfigDict, Field, NonNegativeInt, computed_field
from pydantic.dataclasses import dataclass

from codeweaver import __version__ as version
from codeweaver._common import BaseEnum
from codeweaver._logger import setup_logger
from codeweaver._settings import (
    ErrorHandlingMiddlewareSettings,
    FastMcpHttpRunArgs,
    FastMcpServerSettingsType,
    LoggingMiddlewareSettings,
    MiddlewareOptions,
    RateLimitingMiddlewareSettings,
    RetryMiddlewareSettings,
    UvicornServerSettings,
    UvicornServerSettingsType,
)
from codeweaver._settings_registry import ProviderRegistry, get_provider_registry
from codeweaver._statistics import SessionStatistics
from codeweaver._utils import rpartial
from codeweaver.exceptions import InitializationError
from codeweaver.middleware import StatisticsMiddleware
from codeweaver.settings import (
    CodeWeaverSettings,
    FastMcpServerSettings,
    FileFilterSettings,
    get_settings,
)


# this is initialized after we setup logging.
logger: logging.Logger

_STORE: dict[Literal["settings", "runargs", "server", "lifespan_func", "app_start_func"], Any]
_STATE: AppState | None = None

BRACKET_PATTERN: re.Pattern[str] = re.compile(r"\[.+\]")


def get_state() -> AppState:
    """Get the current application state."""
    global _STATE
    if _STATE is None:
        raise RuntimeError("Application state has not been initialized.")
    return _STATE


def get_store() -> dict[
    Literal["settings", "runargs", "server", "lifespan_func", "app_start_func"], Any
]:
    """Get the current application store."""
    global _STORE
    if _STORE is None:  # type: ignore  # we're going to check anyway
        raise RuntimeError("Application store has not been initialized.")
    return _STORE


def get_statistics() -> SessionStatistics:
    """Get the current session statistics."""
    state = get_state()
    if not state.statistics:
        raise RuntimeError("Session statistics have not been initialized.")
    return state.statistics


def get_health_info() -> HealthInfo:
    """Get the current health information."""
    state = get_state()
    if not state.health:
        raise RuntimeError("Health information has not been initialized.")
    return state.health


@dataclass(order=True, kw_only=True, config=ConfigDict(extra="forbid", str_strip_whitespace=True))
class StoredSettings:
    """A simple container for storing/caching."""

    settings: Annotated[CodeWeaverSettings, Field(description="""Resolved CodeWeaver settings""")]
    server: Annotated[
        FastMcpServerSettingsType, Field(description="""Resolved FastMCP server settings""")
    ]
    runargs: Annotated[
        FastMcpHttpRunArgs | None, Field(description="""Run arguments for the FastMCP server""")
    ]
    lifespan_func: Annotated[
        FunctionType, Field(description="""Lifespan function for the application""")
    ]
    app_start_func: Annotated[
        FunctionType, Field(description="""Function to start the FastMCP application""")
    ]

    def __post_init__(self) -> None:
        from pydantic import TypeAdapter

        global _STORE
        _STORE = TypeAdapter(self).dump_python(mode="python")  # type: ignore


class Feature(BaseEnum):
    """Enum for features supported by the CodeWeaver server."""

    BASIC_SEARCH = "basic_search"
    SEMANTIC_SEARCH = "semantic_search"
    VECTOR_SEARCH = "vector_search"
    HYBRID_SEARCH = "hybrid_search"

    WEB_SEARCH = "web_search"  # tavily, duckduckgo

    SPARSE_INDEXING = "sparse_indexing"
    VECTOR_INDEXING = "vector_indexing"

    FILE_DISCOVERY = "file_discovery"
    PROVIDER_REGISTRY = "registry"

    MCP_CONTEXT_AGENT = "mcp_context_agent"
    NON_MCP_CONTEXT_AGENT = "non_mcp_context_agent"

    HEALTH = "health"
    LOGGING = "logging"
    ERROR_HANDLING = "error_handling"
    RATE_LIMITING = "rate_limiting"
    STATISTICS = "statistics"

    _UNKNOWN = "unknown"


class HealthStatus(BaseEnum):
    """Enum for health status of the CodeWeaver server."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"


@dataclass(order=True, kw_only=True, config=ConfigDict(extra="forbid", str_strip_whitespace=True))
class HealthInfo:
    """Health information for the CodeWeaver server."""

    status: Annotated[HealthStatus, Field(description="""Health status of the server""")] = (
        HealthStatus.HEALTHY
    )
    version: Annotated[str, Field(description="""Version of the CodeWeaver server""")] = version
    startup_time: Annotated[float, Field(description="""Startup time of the server""")] = (
        time.time()
    )
    # TODO: This should come from the registry, not hardcoded
    features: Annotated[
        tuple[Feature],
        Field(default_factory=tuple, description="""List of features supported by the server"""),
    ] = (
        Feature.BASIC_SEARCH,
        Feature.FILE_DISCOVERY,
        Feature.PROVIDER_REGISTRY,
        Feature.STATISTICS,
    )  # type: ignore
    error: Annotated[str | None, Field(description="""Error message if any""")] = None

    @classmethod
    def initialize(cls) -> HealthInfo:
        """Initialize health information with default values."""
        return cls(
            status=HealthStatus.HEALTHY,
            version=version,
            startup_time=time.time(),
            features=(
                Feature.BASIC_SEARCH,
                Feature.FILE_DISCOVERY,
                Feature.PROVIDER_REGISTRY,
                Feature.STATISTICS,
            ),  # type: ignore
        )


@dataclass(
    order=True,
    kw_only=True,
    config=ConfigDict(extra="forbid", str_strip_whitespace=True, arbitrary_types_allowed=True),
)
class AppState:
    """Application state for CodeWeaver server."""

    initialized: Annotated[
        bool, Field(description="""Indicates if the server has been initialized""")
    ] = False

    settings: Annotated[
        CodeWeaverSettings | None,
        Field(
            default_factory=CodeWeaverSettings, description="""CodeWeaver configuration settings"""
        ),
    ] = None

    config_path: Annotated[
        Path | None,
        Field(
            default_factory=lambda data: data["settings"].get("config_file", None),
            description="""Path to the configuration file, if any""",
        ),
    ] = None
    # Provider registry integration
    registry: Annotated[
        ProviderRegistry,
        Field(
            default_factory=ProviderRegistry.get_instance,
            description="""Provider registry for dynamic provider management""",
        ),
    ]

    # Statistics and performance tracking
    statistics: Annotated[
        SessionStatistics,
        Field(
            default_factory=SessionStatistics,
            description="""Session statistics and performance tracking""",
        ),
    ]

    # Health status
    health: Annotated[
        HealthInfo,
        Field(default_factory=HealthInfo.initialize, description="""Health status information"""),
    ]

    # TODO: Future implementation
    indexer: None = None  # Placeholder for background indexer

    middleware_stack: Annotated[
        tuple[Middleware, ...],
        Field(
            default_factory=lambda data: tuple(data["settings"]["middleware"]),
            description="""Loaded middleware stack""",
        ),
    ]

    def __post_init__(self) -> None:
        global _STATE
        _STATE = self  # type: ignore  # Store the state globally for easy access

    @computed_field
    @property
    def request_count(self) -> NonNegativeInt:
        """Computed field for the number of requests handled by the server."""
        return (
            self.statistics.total_requests
            if self.statistics and self.statistics.total_requests is not None
            else 0
        )


@asynccontextmanager
async def lifespan(
    app: FastMCP[AppState],
    settings: CodeWeaverSettings | None,
    statistics: SessionStatistics | None = None,
) -> AsyncIterator[AppState]:
    """Context manager for application lifespan with proper initialization."""
    statistics = statistics or SessionStatistics()
    settings = settings or get_settings()
    if not hasattr(app, "state"):
        setattr(  # noqa: B010  # Ruff, it's not safer, but it does make pylance complain less
            app,
            "state",
            AppState(
                initialized=False,
                settings=settings,
                health=HealthInfo.initialize(),
                statistics=statistics,
                config_path=settings.config_file if settings else None,
                registry=get_provider_registry(),
                middleware_stack=tuple(getattr(app, "middleware", ())),
            ),
        )
    state: AppState = app.state  # type: ignore
    if not isinstance(state, AppState):
        raise InitializationError(
            "AppState should be an instance of AppState, but isn't. Something is wrong. Please report this issue.",
            details={"state": state},
        )
    if not hasattr(state, "registry"):
        state.registry = ProviderRegistry.get_instance()
    state.registry.add_settings(settings)
    try:
        # Initialize health status
        state.health = HealthInfo(
            status=HealthStatus.HEALTHY,
            version=version,
            startup_time=time.time(),
            features=(
                Feature.BASIC_SEARCH,
                Feature.FILE_DISCOVERY,
                Feature.PROVIDER_REGISTRY,
                Feature.STATISTICS,
            ),  # type: ignore
        )

        state.initialized = True
        # Yield the initialized state
        yield state

    except Exception as e:
        # Handle initialization errors
        state.health.status = HealthStatus.UNHEALTHY  # type: ignore
        import json

        state.health.error = json.dumps({"error": e})  # type: ignore
        state.initialized = False
        raise

    finally:
        # Cleanup resources
        state.initialized = False


def get_default_middleware_settings(
    app_logger: logging.Logger, log_level: int
) -> MiddlewareOptions:
    """Get the default middleware settings."""
    return MiddlewareOptions(
        error_handling=ErrorHandlingMiddlewareSettings(
            logger=app_logger, include_traceback=True, error_callback=None, transform_errors=False
        ),
        retry=RetryMiddlewareSettings(
            max_retries=5, base_delay=1.0, max_delay=60.0, backoff_multiplier=2.0, logger=app_logger
        ),
        logging=LoggingMiddlewareSettings(
            logger=app_logger, log_level=log_level, include_payloads=False
        ),
        rate_limiting=RateLimitingMiddlewareSettings(
            max_requests_per_second=75, get_client_id=None, burst_capacity=150, global_limit=True
        ),
    )


def resolve_globs(path_string: str, repo_root: Path) -> set[Path]:
    """Resolve glob patterns in a path string."""
    if "*" in path_string or "?" in path_string or BRACKET_PATTERN.search(path_string):
        return set(repo_root.glob(path_string))
    if (path := (repo_root / path_string)) and path.exists():
        return {path} if path.is_file() else set(path.glob("**/*"))
    return set()


def resolve_includes_and_excludes(
    filter_settings: FileFilterSettings, repo_root: Path
) -> tuple[frozenset[Path], frozenset[Path]]:
    """Resolve included and excluded files based on filter settings.

    Resolves glob patterns for include and exclude paths, filtering includes for excluded extensions.
    If a file is specifically included in the `forced_includes`, it will not be excluded even if it matches an excluded extension or excludes.
    "Specifically included" means that it was defined directly in the `forced_includes`, and **not** as a glob pattern.
    """
    settings = filter_settings.model_dump(mode="python")
    other_files: set[Path] = set()
    specifically_included_files = {
        Path(file)
        for file in settings.get("forced_includes", set())
        if file
        and "*" not in file
        and "?" not in file
        and Path(file).exists()
        and Path(file).is_file()
    }
    for include in settings.get("forced_includes", set()):
        other_files |= resolve_globs(include, repo_root)
    for ext in settings.get("excluded_extensions", set()):
        # we only exclude `other_files` if the file was not specifically included (not by globs)
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
            excludes |= resolve_globs(exclude, repo_root)
    excludes |= specifically_included_files
    other_files -= {exclude for exclude in excludes if exclude not in specifically_included_files}
    other_files -= {None, Path(), Path("./"), Path("./.")}  # Remove empty paths
    excludes -= {None, Path(), Path("./"), Path("./.")}  # Remove empty paths
    return frozenset(other_files), frozenset(excludes)


def setup_local_logger(level: int = logging.INFO) -> None:
    """Set up a local logger for the current module."""
    global logger
    logger = logging.getLogger(__name__)
    logger.setLevel(level)


def _setup_logger(settings: CodeWeaverSettings) -> tuple[logging.Logger, int]:
    """Set up the logger from settings.

    Returns:
        Tuple of (logger, log_level)
    """
    app_logger_settings = settings.logging or {}
    level = app_logger_settings.get("level", 20)
    rich = app_logger_settings.get("use_rich", True)
    rich_kwargs = app_logger_settings.get("rich_kwargs", {})
    logging_kwargs = app_logger_settings.get("dict_config", None)
    app_logger = setup_logger(
        name="codeweaver",
        level=level,
        rich=rich,
        rich_kwargs=rich_kwargs,
        logging_kwargs=logging_kwargs,
    )
    setup_local_logger(level)
    return app_logger, level


def _configure_middleware(
    settings: CodeWeaverSettings, app_logger: logging.Logger, level: int
) -> tuple[MiddlewareOptions, Any]:
    """Configure middleware settings and determine logging middleware type.

    Returns:
        Tuple of (middleware_settings, logging_middleware_class)
    """
    middleware_settings = settings.middleware_settings or {}
    middleware_logging_settings = middleware_settings.get("logging", {}) or {}
    use_structured_logging = middleware_logging_settings.get("use_structured_logging", False)
    logging_middleware = (
        StructuredLoggingMiddleware if use_structured_logging else LoggingMiddleware
    )
    middleware_defaults: MiddlewareOptions = get_default_middleware_settings(app_logger, level)
    if middleware_settings := settings.middleware_settings or None:  # type: ignore
        middleware_defaults |= middleware_settings
    middleware_settings: MiddlewareOptions = middleware_defaults
    return middleware_settings, logging_middleware


def _create_base_fastmcp_settings(
    session_statistics: SessionStatistics,
    app_logger: logging.Logger,
    level: int,
    middleware_settings: MiddlewareOptions,
    logging_middleware: type[LoggingMiddleware | StructuredLoggingMiddleware],
) -> FastMcpServerSettingsType:
    """Create the base FastMCP settings dictionary.

    Returns:
        Dictionary with base FastMCP configuration
    """
    return {
        "instructions": "Ask a question, describe what you're trying to do, and get the exact context you need. CodeWeaver is an advanced code search and code context tool. It keeps an updated vector, AST, and text index of your codebase, and uses intelligent intent analysis to provide the most relevant context for AI Agents to complete tasks. It's just one easy-to-use tool - the `find_code` tool. To use it, you only need to provide a plain language description of what you want to find, and what you are trying to do. CodeWeaver will return the most relevant code matches, along with their context and precise locations.",
        "version": version,
        "lifespan": lifespan,
        "include_tags": {"external", "user", "context"},
        "exclude_tags": {"internal", "system", "admin"},
        "middleware": [
            StatisticsMiddleware(session_statistics, logger=app_logger, log_level=level),
            logging_middleware(**middleware_settings["logging"]),  # pyright: ignore[reportTypedDictNotRequiredAccess,reportCallIssue]
            ErrorHandlingMiddleware(**middleware_settings["error_handling"]),  # pyright: ignore[reportTypedDictNotRequiredAccess,reportCallIssue]
            RetryMiddleware(**middleware_settings["retry"]),  # pyright: ignore[reportTypedDictNotRequiredAccess,reportCallIssue]
            RateLimitingMiddleware(**middleware_settings["rate_limiting"]),  # pyright: ignore[reportTypedDictNotRequiredAccess,reportCallIssue]
        ],
        "tools": [],
    }


type SettingsKey = Literal["dependencies", "middleware", "tools"]


def _integrate_user_settings(
    settings: FastMcpServerSettings, base_fast_mcp_settings: FastMcpServerSettingsType
) -> FastMcpServerSettingsType:
    """Integrate user-provided settings with base FastMCP settings.

    Args:
        settings: CodeWeaver settings containing user preferences
        base_fast_mcp_settings: Base FastMCP configuration to extend

    Returns:
        Updated FastMCP settings dictionary
    """
    additional_keys = ("additional_dependencies", "additional_middleware", "additional_tools")
    for key in additional_keys:
        if (value := getattr(settings, key, None)) and isinstance(value, list):
            if key in {"additional_dependencies", "additional_tools"} and (
                all(isinstance(item, str) for item in value)  # pyright: ignore[reportUnknownVariableType]  # the type of `item` doesn't matter, because we filter for strings
            ):
                # If it's a list of strings, we can directly append it
                settings_key: SettingsKey = cast(SettingsKey, key.replace("additional_", ""))
                base_fast_mcp_settings[settings_key].extend(value)  # pyright: ignore[reportUnknownArgumentType, reportTypedDictNotRequiredAccess,reportOptionalMemberAccess] # we established the types right above it
                continue
            if key == "additional_middleware" and (
                all(isinstance(item, Middleware | Callable) for item in value)
            ):
                base_fast_mcp_settings["middleware"].extend(value)  # pyright: ignore[reportUnknownArgumentType, reportTypedDictNotRequiredAccess,reportOptionalMemberAccess]

    server_settings = settings.model_dump(
        mode="python", exclude_defaults=True, exclude_unset=True, exclude_none=True
    )

    return {**base_fast_mcp_settings, **cast(FastMcpServerSettingsType, server_settings)}


def _setup_file_filters_and_lifespan(
    settings: CodeWeaverSettings, session_statistics: SessionStatistics
) -> Any:
    """Set up file filters and create lifespan function.

    Args:
        settings: CodeWeaver settings
        session_statistics: Session statistics instance

    Returns:
        Configured lifespan function
    """
    settings.filter_settings.forced_includes, settings.filter_settings.excludes = (
        resolve_includes_and_excludes(settings.filter_settings, settings.project_path)
    )
    return rpartial(lifespan, settings, session_statistics)


def _filter_server_settings(server_settings: FastMcpServerSettings) -> FastMcpServerSettingsType:
    """Filter server settings to remove keys not recognized by FastMCP."""
    filtered_settings = server_settings.model_dump(mode="python")
    to_remove = ("additional_middleware", "additional_tools", "additional_dependencies")
    for key in to_remove:
        filtered_settings.pop(key, None)
    return cast(FastMcpServerSettingsType, filtered_settings)


def _get_start_method_name(transport_setting: Literal["http", "stdio"]) -> str:
    """Create the start method for the FastMCP application.

    Args:
        settings: CodeWeaver settings
        app_state: Application state instance

    Returns:
        Function to start the FastMCP application
    """
    return "run_http_async" if transport_setting == "http" else "run_async"


def _get_fastmcp_run_args(
    server_settings: FastMcpServerSettings, uvicorn_config: UvicornServerSettings, log_level: int
) -> FastMcpHttpRunArgs | None:
    """Get the FastMCP run arguments from the server settings.

    Args:
        server_settings: The server settings to extract run arguments from.

    Returns:
        The FastMCP run arguments, or None if not found.
    """
    if not server_settings:
        return None
    # We only need runargs for http transport, as other transports do not use it.
    if server_settings.transport != "http":
        return None

    match log_level:
        case 0:
            stringified_log_level = "debug"
        case 10:
            stringified_log_level = "debug"
        case 20:
            stringified_log_level = "info"
        case 30:
            stringified_log_level = "warning"
        case 40:
            stringified_log_level = "error"
        case 50:
            stringified_log_level = "error"
        case _:
            stringified_log_level = "info"

    return FastMcpHttpRunArgs(
        transport=server_settings.transport,
        host=server_settings.host,
        port=server_settings.port,
        log_level=stringified_log_level,
        path=server_settings.path,
        uvicorn_config=cast(
            UvicornServerSettingsType, uvicorn_config.model_dump(mode="python", exclude_none=True)
        ),
        # TODO: Allow for custom uvicorn middleware
    )


async def initialize_app() -> tuple[FastMCP[AppState], FunctionType]:
    """Initialize the FastMCP application."""
    session_statistics = SessionStatistics()
    settings = get_settings()
    app_logger, level = _setup_logger(settings)
    local_logger: logging.Logger = globals()["logger"]  # type: ignore  # we set it in setup_local_logger
    local_logger.info("Initializing CodeWeaver server. Initial settings retrieved. Logging setup.")
    local_logger.debug("Settings dump \n", extra=settings.model_dump())
    middleware_settings, logging_middleware = _configure_middleware(settings, app_logger, level)
    filtered_server_settings = _filter_server_settings(settings.server or {})
    base_fast_mcp_settings = _create_base_fastmcp_settings(
        session_statistics, app_logger, level, middleware_settings, logging_middleware
    )
    base_fast_mcp_settings = _integrate_user_settings(settings.server, filtered_server_settings)
    local_logger.info("Base FastMCP settings created and merged with user settings.")
    local_logger.debug("Base FastMCP settings dump \n", extra=base_fast_mcp_settings)
    lifespan_fn = _setup_file_filters_and_lifespan(settings, session_statistics)
    base_fast_mcp_settings["lifespan"] = lifespan_fn

    runargs = _get_fastmcp_run_args(
        settings.server, settings.uvicorn_settings or UvicornServerSettings(), level
    )
    run_method: FunctionType = getattr(  # type: ignore
        FastMCP,
        _get_start_method_name(
            cast(Literal["http", "stdio"], base_fast_mcp_settings.pop("transport", "http"))
        ),
        FastMCP.run_http_async,  # type: ignore
    )  # type: ignore
    if runargs:
        run_method = rpartial(run_method, **runargs)  # type: ignore  # good luck typing this
        for key in runargs:
            _ = base_fast_mcp_settings.pop(key, None)
    local_logger.info("FastMCP run arguments extracted and stored.")
    local_logger.debug("FastMCP run arguments dump \n", extra=runargs or {})
    local_logger.debug("Lifespan function: ", extra={"lifespan_fn": lifespan_fn})
    local_logger.debug("Run method: ", extra={"run_method": run_method})
    _ = StoredSettings(
        settings=settings,
        server=filtered_server_settings,
        runargs=runargs,
        lifespan_func=lifespan_fn,
        app_start_func=run_method,
    )
    return FastMCP[AppState](**base_fast_mcp_settings), run_method  # pyright: ignore[reportCallIssue]  # we popped those keys a few lines up
