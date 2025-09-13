# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0

# sourcery skip: snake-case-variable-declarations
"""Initialize the FastMCP application with default middleware and settings."""

from __future__ import annotations

import importlib
import logging
import os
import re
import time

from collections.abc import AsyncIterator, Iterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import (
    TYPE_CHECKING,
    Annotated,
    Any,
    Literal,
    NotRequired,
    Required,
    Self,
    TypedDict,
    cast,
)

from fastmcp import FastMCP
from fastmcp.server.middleware.error_handling import ErrorHandlingMiddleware, RetryMiddleware
from fastmcp.server.middleware.logging import LoggingMiddleware, StructuredLoggingMiddleware
from fastmcp.server.middleware.middleware import Middleware
from fastmcp.server.middleware.rate_limiting import RateLimitingMiddleware
from pydantic import ConfigDict, Field, NonNegativeInt, computed_field
from pydantic.dataclasses import dataclass
from pydantic_core import to_json

from codeweaver import __version__ as version
from codeweaver._common import BasedModel, BaseEnum, DataclassSerializationMixin, DictView
from codeweaver._logger import setup_logger
from codeweaver._utils import get_project_root, lazy_importer, rpartial
from codeweaver.exceptions import InitializationError
from codeweaver.provider import (
    Provider as Provider,  # we need this in the namespace for building the server
)
from codeweaver.settings import (
    CodeWeaverSettings,
    FastMcpServerSettings,
    FileFilterSettings,
    get_settings,
    get_settings_map,
)
from codeweaver.settings_types import (
    CodeWeaverSettingsDict,
    ErrorHandlingMiddlewareSettings,
    FastMcpServerSettingsDict,
    LoggingMiddlewareSettings,
    LoggingSettings,
    MiddlewareOptions,
    RateLimitingMiddlewareSettings,
    RetryMiddlewareSettings,
)


if TYPE_CHECKING:
    from codeweaver._registry import (
        Feature,
        ModelRegistry,
        ProviderRegistry,
        ServiceCard,
        ServicesRegistry,
    )
    from codeweaver._statistics import SessionStatistics
else:
    # Pydantic needs these at runtime, but we want to lazy load them until needed.
    codeweaver_registry = lazy_importer("codeweaver._registry")
    Feature = codeweaver_registry.Feature
    ModelRegistry = codeweaver_registry.ModelRegistry
    ProviderRegistry = codeweaver_registry.ProviderRegistry
    ServiceCard = codeweaver_registry.ServiceCard
    ServicesRegistry = codeweaver_registry.ServicesRegistry
    SessionStatistics = lazy_importer("codeweaver._statistics").SessionStatistics

# Lazy import of registries to delay until needed
get_model_registry = lazy_importer("codeweaver._registry").get_model_registry
get_provider_registry = lazy_importer("codeweaver._registry").get_provider_registry
get_services_registry = lazy_importer("codeweaver._registry").get_services_registry


# this is initialized after we setup logging.
logger: logging.Logger

_STATE: AppState | None = None
_logger: logging.Logger | None = None

BRACKET_PATTERN: re.Pattern[str] = re.compile(r"\[.+\]")


def _get_session_statistics() -> SessionStatistics:
    """Get or create the session statistics instance."""
    statistics = importlib.import_module("codeweaver._statistics")

    return statistics.get_session_statistics()


def get_state() -> AppState:
    """Get the current application state."""
    global _STATE
    if _STATE is None:
        raise RuntimeError("Application state has not been initialized.")
    return _STATE


class HealthStatus(BaseEnum):
    """Enum for health status of the CodeWeaver server."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"


def _get_available_features_and_services() -> Iterator[tuple[Feature, ServiceCard]]:
    """Get the list of features supported by the CodeWeaver server."""
    from codeweaver._registry import get_services_registry

    services_instance = get_services_registry()
    yield from (
        (feature, card)
        for feature, cards in services_instance.list_available_services().items()
        for card in cards
    )


@dataclass(order=True, kw_only=True, config=BasedModel.model_config | ConfigDict(extra="forbid"))
class HealthInfo(DataclassSerializationMixin):
    """Health information for the CodeWeaver server.

    TODO: Expand to be more dynamic, computing health based on service status, etc.
    """

    from codeweaver._registry import Feature, ServiceCard

    status: Annotated[HealthStatus, Field(description="""Health status of the server""")] = (
        HealthStatus.HEALTHY
    )
    version: Annotated[str, Field(description="""Version of the CodeWeaver server""")] = version
    startup_time: Annotated[float, Field(description="""Startup time of the server""")] = (
        time.time()
    )

    error: Annotated[str | None, Field(description="""Error message if any""")] = None

    @classmethod
    def initialize(cls) -> HealthInfo:
        """Initialize health information with default values."""
        return cls()

    @computed_field
    @property
    def available_features(self) -> frozenset[Feature]:
        """Computed field for available features based on the services registry."""
        return frozenset(feature for feature, _ in _get_available_features_and_services())

    @computed_field
    @property
    def available_services(self) -> tuple[ServiceCard, ...]:
        """Computed field for available services based on the services registry."""
        return tuple(card for _, card in _get_available_features_and_services())

    @computed_field
    @property
    def available_features_and_services(self) -> tuple[tuple[Feature, ServiceCard], ...]:
        """Computed field for available service features based on the services registry."""
        return tuple((feature, card) for feature, card in _get_available_features_and_services())

    def update_status(
        self,
        new_status: HealthStatus | Literal["healthy", "unhealthy", "degraded"],
        error: str | None = None,
    ) -> Self:
        """Update the health status of the server."""
        if not isinstance(new_status, HealthStatus):
            new_status = HealthStatus.from_string(new_status)
        self.status = new_status
        self.error = error
        return self

    def report(self) -> bytes:
        """Generate a health report in JSON format."""
        return self.dump_json(
            exclude_none=True,
            exclude_unset=True,
            exclude={"_module", "_adapter", "available_features_and_services"},
        )


_health_info: HealthInfo = HealthInfo.initialize()


def get_health_info() -> HealthInfo:
    """Get the current health information."""
    return _health_info


@dataclass(
    order=True,
    kw_only=True,
    config=BasedModel.model_config
    | ConfigDict(extra="forbid", arbitrary_types_allowed=True, defer_build=True),
)
class AppState(DataclassSerializationMixin):
    """Application state for CodeWeaver server."""

    initialized: Annotated[
        bool, Field(description="""Indicates if the server has been initialized""")
    ] = False

    settings: Annotated[
        CodeWeaverSettings | None,
        Field(
            default_factory=importlib.import_module("codeweaver.settings").get_settings,
            description="""CodeWeaver configuration settings""",
        ),
    ]

    config_path: Annotated[
        Path | None,
        Field(
            default_factory=lambda data: data["settings"].get("config_file"),
            description="""Path to the configuration file, if any""",
        ),
    ]
    project_root: Annotated[
        Path,
        Field(
            default_factory=lambda data: data["settings"].get("project_root") or get_project_root(),
            description="""Path to the project root""",
        ),
    ]
    # Provider registry integration
    provider_registry: Annotated[
        ProviderRegistry,
        Field(
            default_factory=get_provider_registry,
            description="""Provider registry for dynamic provider management""",
        ),
    ]

    services_registry: Annotated[
        ServicesRegistry,
        Field(
            default_factory=get_services_registry,
            description="""Service registry for managing available services""",
        ),
    ]

    model_registry: Annotated[
        ModelRegistry,
        Field(
            default_factory=get_model_registry,
            description="""Model registry for managing AI and embedding/reranking models""",
        ),
    ]

    # Statistics and performance tracking
    statistics: Annotated[
        SessionStatistics,
        Field(
            default_factory=_get_session_statistics,
            description="""Session statistics and performance tracking""",
        ),
    ]

    # Health status
    health: Annotated[
        HealthInfo,
        Field(
            default_factory=lambda: _health_info or get_health_info(),
            description="""Health status information""",
        ),
    ]

    # Middleware stack
    middleware_stack: Annotated[
        tuple[Middleware, ...],
        Field(description="""Tuple of FastMCP middleware instances applied to the server"""),
    ] = ()

    # TODO: Future implementation
    indexer: None = None  # Placeholder for background indexer

    def __post_init__(self) -> None:
        global _STATE
        _STATE = self  # type: ignore  # Store the state globally for easy access

    @computed_field
    @property
    def request_count(self) -> NonNegativeInt:
        """Computed field for the number of requests handled by the server."""
        if self.statistics:
            return self.statistics._total_requests + (self.statistics._total_http_requests or 0)  # type: ignore
        return 0


@asynccontextmanager
async def lifespan(
    app: FastMCP[AppState],
    settings: CodeWeaverSettings | None,
    statistics: SessionStatistics | None = None,
) -> AsyncIterator[AppState]:
    """Context manager for application lifespan with proper initialization."""
    from rich.console import Console

    console = Console(markup=True)
    console.print("[bold red]Entering lifespan context manager...[/bold red]")
    statistics = statistics or _get_session_statistics()
    settings = settings or get_settings()
    if not hasattr(app, "state"):
        setattr(  # noqa: B010  # Ruff, it's not safer, but it does make pylance complain less
            app,
            "state",
            AppState(
                initialized=False,
                settings=settings,
                health=get_health_info(),
                statistics=statistics,
                project_root=settings.project_root or get_project_root(),
                config_path=settings.config_file if settings else None,
                provider_registry=get_provider_registry(),
                services_registry=get_services_registry(),
                model_registry=get_model_registry(),
                middleware_stack=tuple(getattr(app, "middleware", ())),
            ),
        )
    state: AppState = app.state  # type: ignore
    if not isinstance(state, AppState):
        raise InitializationError(
            "AppState should be an instance of AppState, but isn't. Something is wrong. Please report this issue.",
            details={"state": state},
        )
    try:
        console.print("[bold green]Ensuring services set up...[/bold green]")
        if not state.health:
            state.health.initialize()
        console.print("[bold aqua]Lifespan start actions complete, server initialized.[/bold aqua]")
        state.initialized = True
        # Yield the initialized state
        yield state

    except Exception as e:
        # Handle initialization errors
        state.health.status = HealthStatus.UNHEALTHY  # type: ignore

        state.health.error = to_json({"error": e})  # type: ignore
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


def __setup_interim_logger() -> tuple[logging.Logger, int]:
    """Set up the initial logger for the application.

    Because we need to fully resolve settings before we can set up logging properly,
    we set up a basic logger first, then reconfigure it later.

    Returns:
        tuple of (logger, log_level)
    """
    level = int(os.environ.get("CODEWEAVER_LOG_LEVEL", "20"))
    setup_local_logger(level)
    return setup_logger(
        name="codeweaver", level=level, rich=True, rich_kwargs={}, logging_kwargs=None
    ), level


LEVEL_MAP: dict[
    Literal[0, 10, 20, 30, 40, 50], Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
] = {0: "DEBUG", 10: "DEBUG", 20: "INFO", 30: "WARNING", 40: "ERROR", 50: "CRITICAL"}


def _setup_logger(
    settings: DictView[CodeWeaverSettingsDict],
) -> tuple[logging.Logger, Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]]:
    """Set up the logger from settings.

    Returns:
        Tuple of (logger, log_level)
    """
    app_logger_settings: LoggingSettings = cast(LoggingSettings, settings.get("logging", {}))
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
    fast_mcp_log_level = LEVEL_MAP.get(level, "INFO")
    return app_logger, fast_mcp_log_level


def _configure_middleware(
    settings: DictView[CodeWeaverSettingsDict], app_logger: logging.Logger, level: int
) -> tuple[MiddlewareOptions, Any]:
    """Configure middleware settings and determine logging middleware type.

    Returns:
        Tuple of (middleware_settings, logging_middleware_class)
    """
    middleware_settings = settings.get("middleware_settings", settings.get("middleware", {})) or {}
    middleware_logging_settings = middleware_settings.get("logging", {}) or {}
    use_structured_logging = middleware_logging_settings.get("use_structured_logging", False)
    logging_middleware = (
        StructuredLoggingMiddleware if use_structured_logging else LoggingMiddleware
    )
    middleware_defaults: MiddlewareOptions = get_default_middleware_settings(app_logger, level)
    middleware_settings: MiddlewareOptions = middleware_defaults | middleware_settings
    return middleware_settings, logging_middleware


def get_default_middleware() -> list[type[Middleware]]:
    """Get the default middleware settings."""
    return [ErrorHandlingMiddleware, RetryMiddleware, RateLimitingMiddleware]


def _create_base_fastmcp_settings() -> FastMcpServerSettingsDict:
    """Create the base FastMCP settings dictionary.

    Returns:
        Dictionary with base FastMCP configuration
    """
    return {
        "instructions": "Ask a question, describe what you're trying to do, and get the exact context you need. CodeWeaver is an advanced code search and code context tool. It keeps an updated vector, AST, and text index of your codebase, and uses intelligent intent analysis to provide the most relevant context for AI Agents to complete tasks. It's just one easy-to-use tool - the `find_code` tool. To use it, you only need to provide a plain language description of what you want to find, and what you are trying to do. CodeWeaver will return the most relevant code matches, along with their context and precise locations.",
        "version": version,
        "lifespan": lifespan,
        "include_tags": {"external", "user", "code-context"},
        "exclude_tags": {"internal", "system", "admin"},
    }


type SettingsKey = Literal["middleware", "tools"]


def _integrate_user_settings(
    settings: FastMcpServerSettings, base_fast_mcp_settings: FastMcpServerSettingsDict
) -> FastMcpServerSettingsDict:
    """Integrate user-provided settings with base FastMCP settings.

    Args:
        settings: CodeWeaver settings containing user preferences
        base_fast_mcp_settings: Base FastMCP configuration to extend

    Returns:
        Updated FastMCP settings dictionary
    """
    additional_keys = ("additional_middleware", "additional_tools")
    # Excuse the many type: ignore comments. It's because we're amending the TypedDict structure before passing it to the server.
    for key in additional_keys:
        replacement_key = key.replace("additional_", "")
        if not base_fast_mcp_settings.get(replacement_key):
            base_fast_mcp_settings[replacement_key] = []  # type: ignore
        if not base_fast_mcp_settings[replacement_key] and base_fast_mcp_settings.get(key):  # type: ignore
            base_fast_mcp_settings[replacement_key] = [  # type: ignore
                string_to_class(s) if isinstance(s, str) else s
                for s in base_fast_mcp_settings[key]  # type: ignore
                if s
            ]  # type: ignore
        if key in base_fast_mcp_settings:
            _ = base_fast_mcp_settings.pop(key, None)
        if (value := getattr(settings, key, None)) and isinstance(value, list):
            base_fast_mcp_settings[replacement_key].extend(  # type: ignore
                string_to_class(item) if isinstance(item, str) else item
                for item in value  # type: ignore
                if item and item not in base_fast_mcp_settings[replacement_key]  # type: ignore
            )
        base_fast_mcp_settings[replacement_key] = (  # type: ignore
            list(set(base_fast_mcp_settings[replacement_key]))  # type: ignore
            if base_fast_mcp_settings[replacement_key]  # type: ignore
            else []
        )  # type: ignore
    return base_fast_mcp_settings


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
        resolve_includes_and_excludes(settings.filter_settings, settings.project_root)
    )
    return rpartial(lifespan, settings, session_statistics)


def _filter_server_settings(server_settings: FastMcpServerSettings) -> FastMcpServerSettingsDict:
    """Filter server settings to remove keys not recognized by FastMCP."""
    to_remove = ("additional_middleware", "additional_tools", "additional_dependencies")
    return cast(
        FastMcpServerSettingsDict,
        {k: v for k, v in cast(dict[str, Any], server_settings).items() if k not in to_remove},
    )


def string_to_class(s: str) -> type[Any] | None:
    """Convert a string representation of a class to the actual class."""
    components = s.split(".")
    module_name = ".".join(components[:-1])
    class_name = components[-1]
    try:
        module = __import__(module_name, fromlist=[class_name])
        return getattr(module, class_name, None)
    except (ImportError, AttributeError):
        return None


class ServerSetup(TypedDict):
    app: Required[FastMCP[AppState]]
    settings: Required[CodeWeaverSettings]
    middleware_settings: NotRequired[MiddlewareOptions]
    host: NotRequired[str | None]
    port: NotRequired[int | None]
    streamable_http_path: NotRequired[str | None]
    log_level: NotRequired[Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]]
    middleware: NotRequired[set[Middleware] | set[type[Middleware]]]


def build_app() -> ServerSetup:
    """Build and configure the FastMCP application without starting it."""
    session_statistics = _get_session_statistics()
    app_logger, level = __setup_interim_logger()
    local_logger: logging.Logger = globals()["logger"]  # type: ignore
    local_logger.info("Initializing CodeWeaver server. Logging set up.")
    settings_view = get_settings_map()
    middleware_settings, logging_middleware = _configure_middleware(
        settings_view, app_logger, level
    )
    filtered_server_settings = _filter_server_settings(settings_view.get("server", {}))  # type: ignore
    middleware = {logging_middleware, *get_default_middleware()}
    base_fast_mcp_settings = _create_base_fastmcp_settings()
    base_fast_mcp_settings = _integrate_user_settings(
        settings_view.get("server", {}),  # type: ignore
        filtered_server_settings,
    )
    local_logger.info("Base FastMCP settings created and merged with user settings.")
    local_logger.debug("Base FastMCP settings dump \n", extra=base_fast_mcp_settings)
    lifespan_fn = _setup_file_filters_and_lifespan(get_settings(), session_statistics)
    base_fast_mcp_settings["lifespan"] = lifespan_fn

    # Transport selection is handled by the caller; remove from constructor kwargs.
    _ = base_fast_mcp_settings.pop("transport", "http")

    final_app_logger, _final_level = _setup_logger(settings_view)
    int_level = next((k for k, v in LEVEL_MAP.items() if v == _final_level), "INFO")
    for key, middleware_setting in middleware_settings.items():
        if "logger" in cast(dict[str, Any], middleware_setting):
            middleware_settings[key]["logger"] = final_app_logger
        if "log_level" in cast(dict[str, Any], middleware_setting):
            middleware_settings[key]["log_level"] = int_level
    # Rebind loggers for any logging middleware safely
    global _logger
    _logger = final_app_logger
    host = base_fast_mcp_settings.pop("host", "127.0.0.1")
    port = base_fast_mcp_settings.pop("port", 9328)
    http_path = base_fast_mcp_settings.pop("streamable_http_path", "/codeweaver")
    server = FastMCP[AppState](
        name="CodeWeaver",
        **base_fast_mcp_settings,  # type: ignore
    )  # pyright: ignore[reportCallIssue]
    local_logger.info("FastMCP application initialized successfully.")
    return ServerSetup(
        app=server,
        settings=get_settings(),
        middleware_settings=middleware_settings,
        host=host or "127.0.0.1",
        port=port or 9328,
        streamable_http_path=cast(str, http_path or "/codeweaver"),
        log_level=_final_level or "INFO",
        middleware={*middleware},
    )


__all__ = (
    "AppState",
    "HealthInfo",
    "HealthStatus",
    "ServerSetup",
    "build_app",
    "get_state",
    "lifespan",
)
