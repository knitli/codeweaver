# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Initialize the FastMCP application with default middleware and settings."""

from __future__ import annotations

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
from codeweaver.common.logging import setup_logger
from codeweaver.common.utils import get_project_path, lazy_import, rpartial
from codeweaver.config.logging import LoggingSettings
from codeweaver.config.middleware import (
    ErrorHandlingMiddlewareSettings,
    LoggingMiddlewareSettings,
    MiddlewareOptions,
    RateLimitingMiddlewareSettings,
    RetryMiddlewareSettings,
)
from codeweaver.config.settings import (
    CodeWeaverSettings,
    CodeWeaverSettingsDict,
    FastMcpServerSettings,
    get_settings_map,
)
from codeweaver.config.types import FastMcpServerSettingsDict
from codeweaver.core.types.dictview import DictView
from codeweaver.core.types.enum import AnonymityConversion, BaseEnum
from codeweaver.core.types.models import DATACLASS_CONFIG, DataclassSerializationMixin
from codeweaver.exceptions import InitializationError
from codeweaver.providers.provider import Provider as Provider


if TYPE_CHECKING:
    from codeweaver.common.registry import (
        Feature,
        ModelRegistry,
        ProviderRegistry,
        ServiceCard,
        ServicesRegistry,
    )
    from codeweaver.common.statistics import SessionStatistics
    from codeweaver.common.utils import LazyImport
    from codeweaver.core.types import AnonymityConversion, FilteredKeyT
else:
    # lazy types for pydantic at runtime
    ProviderRegistry: LazyImport[ProviderRegistry] = lazy_import(
        "codeweaver.common.registry", "ProviderRegistry"
    )
    ServicesRegistry: LazyImport[ServicesRegistry] = lazy_import(
        "codeweaver.common.registry", "ServicesRegistry"
    )
    ModelRegistry: LazyImport[ModelRegistry] = lazy_import(
        "codeweaver.common.registry", "ModelRegistry"
    )
    SessionStatistics: LazyImport[SessionStatistics] = lazy_import(
        "codeweaver.common.statistics", "SessionStatistics"
    )

# lazy imports for default factory functions
get_provider_registry: LazyImport[ProviderRegistry] = lazy_import(
    "codeweaver.common.registry", "get_provider_registry"
)
get_services_registry: LazyImport[ServicesRegistry] = lazy_import(
    "codeweaver.common.registry", "get_services_registry"
)
get_model_registry: LazyImport[ModelRegistry] = lazy_import(
    "codeweaver.common.registry", "get_model_registry"
)
get_session_statistics: LazyImport[SessionStatistics] = lazy_import(
    "codeweaver.common.statistics", "get_session_statistics"
)
get_settings: LazyImport[CodeWeaverSettings] = lazy_import(
    "codeweaver.config.settings", "get_settings"
)

logger: logging.Logger
_logger: logging.Logger | None = None
BRACKET_PATTERN: re.Pattern[str] = re.compile("\\[.+\\]")


# ================================================
# *     Application State and Health
# ================================================


class HealthStatus(BaseEnum):
    """Enum for health status of the CodeWeaver server."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    DEGRADED = "degraded"


def _get_available_features_and_services() -> Iterator[tuple[Feature, ServiceCard]]:
    """Get the list of features supported by the CodeWeaver server."""
    from codeweaver.common.registry import get_services_registry

    services_instance = get_services_registry()
    yield from (
        (feature, card)
        for feature, cards in services_instance.list_available_services().items()
        for card in cards
    )


@dataclass(order=True, kw_only=True, config=DATACLASS_CONFIG | ConfigDict(extra="forbid"))
class HealthInfo(DataclassSerializationMixin):
    """Health information for the CodeWeaver server.

    TODO: Expand to be more dynamic, computing health based on service status, etc.
    """

    from codeweaver.common.registry import Feature, ServiceCard

    status: Annotated[HealthStatus, Field(description="Health status of the server")] = (
        HealthStatus.HEALTHY
    )
    version: Annotated[str, Field(description="Version of the CodeWeaver server")] = version
    startup_time: Annotated[float, Field(description="Startup time of the server")] = time.time()
    error: Annotated[str | bytes | None, Field(description="Error message if any")] = None

    def _telemetry_keys(self) -> None:
        return None

    @classmethod
    def initialize(cls) -> HealthInfo:
        """Initialize health information with default values."""
        return cls()

    @computed_field
    @property
    def available_features(self) -> frozenset[Feature]:
        """Computed field for available features based on the services registry."""
        return frozenset((feature for feature, _ in _get_available_features_and_services()))

    @computed_field
    @property
    def available_services(self) -> tuple[ServiceCard, ...]:
        """Computed field for available services based on the services registry."""
        return tuple((card for _, card in _get_available_features_and_services()))

    @computed_field
    @property
    def available_features_and_services(self) -> tuple[tuple[Feature, ServiceCard], ...]:
        """Computed field for available service features based on the services registry."""
        return tuple(((feature, card) for feature, card in _get_available_features_and_services()))

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


_health_info: HealthInfo | None = None


def get_health_info() -> HealthInfo:
    """Get the current health information."""
    global _health_info
    if _health_info is None:
        _health_info = HealthInfo.initialize()
    return _health_info


@dataclass(
    order=True, kw_only=True, config=DATACLASS_CONFIG | ConfigDict(extra="forbid", defer_build=True)
)
class AppState(DataclassSerializationMixin):
    """Application state for CodeWeaver server."""

    initialized: Annotated[
        bool, Field(description="Indicates if the server has been initialized")
    ] = False
    settings: Annotated[
        CodeWeaverSettings | None,
        Field(default_factory=get_settings, description="CodeWeaver configuration settings"),
    ]
    config_path: Annotated[
        Path | None,
        Field(
            default_factory=lambda data: data["settings"].get("config_file"),
            description="Path to the configuration file, if any",
        ),
    ]
    project_path: Annotated[
        Path,
        Field(
            default_factory=lambda data: data["settings"].get("project_path") or get_project_path(),
            description="Path to the project root",
        ),
    ]
    provider_registry: Annotated[
        ProviderRegistry,
        Field(
            default_factory=get_provider_registry,
            description="Provider registry for dynamic provider management",
        ),
    ]
    services_registry: Annotated[
        ServicesRegistry,
        Field(
            default_factory=get_services_registry,
            description="Service registry for managing available services",
        ),
    ]
    model_registry: Annotated[
        ModelRegistry,
        Field(
            default_factory=get_model_registry,
            description="Model registry for managing AI and embedding/reranking models",
        ),
    ]
    statistics: Annotated[
        SessionStatistics,
        Field(
            default_factory=get_session_statistics,
            description="Session statistics and performance tracking",
        ),
    ]
    health: Annotated[
        HealthInfo, Field(default_factory=get_health_info, description="Health status information")
    ]
    middleware_stack: Annotated[
        tuple[Middleware, ...],
        Field(description="Tuple of FastMCP middleware instances applied to the server"),
    ] = ()
    indexer: None = None

    def __post_init__(self) -> None:
        """Post-initialization to set the global state reference."""
        global _state
        _state = self

    def _telemetry_keys(self) -> dict[FilteredKeyT, AnonymityConversion]:
        # Each of the values that are BasedModel or DataclassSerializationMixin have their own filters
        from codeweaver.core.types import AnonymityConversion, FilteredKey

        return {
            # TODO: These can all be boolean but need to differentiate from defaults vs set values
            # We'd need to make broader use of the Unset sentinel for that to work well
            FilteredKey("config_path"): AnonymityConversion.BOOLEAN,
            FilteredKey("project_path"): AnonymityConversion.HASH,
            FilteredKey("middleware_stack"): AnonymityConversion.COUNT,
        }

    @computed_field
    @property
    def request_count(self) -> NonNegativeInt:
        """Computed field for the number of requests handled by the server."""
        if self.statistics:
            return self.statistics.total_requests + (self.statistics.total_http_requests or 0)
        return 0


_state: AppState | None = None


def get_state() -> AppState:
    """Get the current application state."""
    global _state
    if _state is None:
        raise InitializationError(
            "AppState has not been initialized yet. Ensure the server is properly set up before accessing the state."
        )
    return _state


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
    if not hasattr(app, "state"):
        state = AppState(  # type: ignore
            initialized=False,
            settings=settings,
            health=get_health_info(),
            statistics=statistics or get_session_statistics(),
            project_path=settings.project_path
            if settings
            else get_settings().project_path or get_project_path(),
            config_path=settings.config_file if settings else get_settings().config_file,
            provider_registry=get_provider_registry(),
            services_registry=get_services_registry(),
            model_registry=get_model_registry(),
            middleware_stack=tuple(getattr(app, "middleware", ())),
        )
        object.__setattr__(app, "state", state)
    state: AppState = app.state  # type: ignore
    from codeweaver.common import CODEWEAVER_PREFIX

    if not isinstance(state, AppState):
        raise InitializationError(
            "AppState should be an instance of AppState, but isn't. Something is wrong. Please report this issue.",
            details={"state": state},
        )
    try:
        console.print(f"{CODEWEAVER_PREFIX} [bold green]Ensuring services set up...[/bold green]")
        if not state.health:
            state.health.initialize()
        console.print(
            f"{CODEWEAVER_PREFIX} [bold aqua]Lifespan start actions complete, server initialized.[/bold aqua]"
        )
        state.initialized = True
        yield state
    except Exception as e:
        state.health.status = HealthStatus.UNHEALTHY
        state.health.error = to_json({"error": e})
        state.initialized = False
        raise
    finally:
        # TODO: Add state caching/saving and cleanup logic here
        console.print(
            f"{CODEWEAVER_PREFIX} [bold red]Exiting CodeWeaver lifespan context manager...[/bold red]"
        )
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
    return (
        setup_logger(
            name="codeweaver", level=level, rich=True, rich_kwargs={}, logging_kwargs=None
        ),
        level,
    )


LEVEL_MAP: dict[
    Literal[0, 10, 20, 30, 40, 50], Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
] = {0: "DEBUG", 10: "DEBUG", 20: "INFO", 30: "WARNING", 40: "ERROR", 50: "CRITICAL"}
"""Mapping of integer log levels to FastMCP log level strings.

Note: FastMCP uses string log levels, while Python's logging uses integer levels.
This mapping helps convert between the two. FastMCP also has one less log level (no NOTSET).
"""


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
    return (app_logger, fast_mcp_log_level)


def _configure_middleware(
    settings: DictView[CodeWeaverSettingsDict], app_logger: logging.Logger, level: int
) -> tuple[MiddlewareOptions, type[LoggingMiddleware | StructuredLoggingMiddleware]]:
    """Configure middleware settings and determine logging middleware type.

    Returns:
        Tuple of (middleware, logging_middleware_class)
    """
    middleware = settings.get("middleware", settings.get("middleware", {})) or {}
    middleware_logging_settings = middleware.get("logging", {}) or {}
    use_structured_logging = middleware_logging_settings.get("use_structured_logging", False)
    logging_middleware = (
        StructuredLoggingMiddleware if use_structured_logging else LoggingMiddleware
    )
    middleware_defaults: MiddlewareOptions = get_default_middleware_settings(app_logger, level)
    middleware: MiddlewareOptions = middleware_defaults | middleware
    return (middleware, logging_middleware)


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
        # CodeWeaver has three APIs:
        #  - Human -- through config and CLI
        #  - *User* Agent: through the `find_code` tool
        #  - *Context* Agent: through a few internally exposed tools
        # The include and exclude tags help differentiate between the two agent APIs.
        # Because these are core to how CodeWeaver works, users can't change them (well, they can if they are persistent enough, but we don't recommend it).
        "include_tags": {"external", "user", "code-context"},
        "exclude_tags": {"internal", "system", "admin"},
    }


type SettingsKey = Literal["middleware", "tools"]
"""Type alias for `CodeWeaverSettings` keys that can have additional items."""


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
    for key in additional_keys:
        replacement_key = key.replace("additional_", "")
        if not base_fast_mcp_settings.get(replacement_key):
            base_fast_mcp_settings[replacement_key] = []  # type: ignore
        if not base_fast_mcp_settings[replacement_key] and base_fast_mcp_settings.get(key):  # type: ignore
            base_fast_mcp_settings[replacement_key] = [  # type: ignore
                string_to_class(s) if isinstance(s, str) else s
                for s in base_fast_mcp_settings[key]  # type: ignore
                if s
            ]
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
        )
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
    except (ImportError, AttributeError):
        return None
    else:
        return getattr(module, class_name, None)


class ServerSetup(TypedDict):
    """TypedDict for the CodeWeaver FastMCP server setup."""

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
    session_statistics = get_session_statistics()
    app_logger, level = __setup_interim_logger()
    local_logger: logging.Logger = globals()["logger"]
    local_logger.info("Initializing CodeWeaver server. Logging set up.")
    settings_view = get_settings_map()
    middleware_settings, logging_middleware = _configure_middleware(
        settings_view, app_logger, level
    )
    filtered_server_settings = _filter_server_settings(settings_view.get("server", {}))
    middleware = {logging_middleware, *get_default_middleware()}
    base_fast_mcp_settings = _create_base_fastmcp_settings()
    base_fast_mcp_settings = _integrate_user_settings(
        settings_view.get("server", {}), filtered_server_settings
    )
    local_logger.info("Base FastMCP settings created and merged with user settings.")
    local_logger.debug("Base FastMCP settings dump \n", extra=base_fast_mcp_settings)
    lifespan_fn = _setup_file_filters_and_lifespan(get_settings(), session_statistics)
    base_fast_mcp_settings["lifespan"] = lifespan_fn
    _ = base_fast_mcp_settings.pop("transport", "http")
    final_app_logger, _final_level = _setup_logger(settings_view)
    int_level = next((k for k, v in LEVEL_MAP.items() if v == _final_level), "INFO")
    for key, middleware_setting in middleware_settings.items():
        if "logger" in cast(dict[str, Any], middleware_setting):
            middleware_settings[key]["logger"] = final_app_logger
        if "log_level" in cast(dict[str, Any], middleware_setting):
            middleware_settings[key]["log_level"] = int_level
    global _logger
    _logger = final_app_logger
    host = base_fast_mcp_settings.pop("host", "127.0.0.1")
    port = base_fast_mcp_settings.pop("port", 9328)
    http_path = base_fast_mcp_settings.pop("streamable_http_path", "/codeweaver")
    server = FastMCP[AppState](name="CodeWeaver", **base_fast_mcp_settings)  # type: ignore
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
