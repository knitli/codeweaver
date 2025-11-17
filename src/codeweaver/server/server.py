# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Initialize the FastMCP application with default middleware and settings."""

from __future__ import annotations

import asyncio
import logging
import re
import time

from collections.abc import AsyncIterator, Callable
from contextlib import asynccontextmanager
from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Any, Literal, NotRequired, Required, TypedDict, cast

from fastmcp import FastMCP
from fastmcp.server.middleware.error_handling import ErrorHandlingMiddleware, RetryMiddleware
from fastmcp.server.middleware.logging import LoggingMiddleware, StructuredLoggingMiddleware
from fastmcp.server.middleware.middleware import Middleware
from fastmcp.server.middleware.rate_limiting import RateLimitingMiddleware
from pydantic import ConfigDict, DirectoryPath, Field, NonNegativeInt, computed_field
from pydantic.dataclasses import dataclass

from codeweaver import __version__ as version
from codeweaver.common.logging import setup_logger
from codeweaver.common.registry import ModelRegistry, ProviderRegistry, ServicesRegistry
from codeweaver.common.statistics import SessionStatistics
from codeweaver.common.telemetry.client import PostHogClient
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
from codeweaver.core.types.enum import AnonymityConversion
from codeweaver.core.types.models import DATACLASS_CONFIG, DataclassSerializationMixin
from codeweaver.core.types.sentinel import Unset
from codeweaver.engine.failover import VectorStoreFailoverManager
from codeweaver.engine.indexer import Indexer
from codeweaver.exceptions import InitializationError
from codeweaver.providers.provider import Provider as Provider
from codeweaver.server.health_service import HealthService


if TYPE_CHECKING:
    from codeweaver.common.utils import LazyImport
    from codeweaver.core.types import AnonymityConversion, FilteredKeyT

# lazy imports for default factory functions
get_provider_registry: LazyImport[Callable[[], ProviderRegistry]] = lazy_import(
    "codeweaver.common.registry", "get_provider_registry"
)
get_services_registry: LazyImport[Callable[[], ServicesRegistry]] = lazy_import(
    "codeweaver.common.registry", "get_services_registry"
)
get_model_registry: LazyImport[Callable[[], ModelRegistry]] = lazy_import(
    "codeweaver.common.registry", "get_model_registry"
)
get_session_statistics: LazyImport[Callable[[], SessionStatistics]] = lazy_import(
    "codeweaver.common.statistics", "get_session_statistics"
)
get_settings: LazyImport[Callable[[], CodeWeaverSettings]] = lazy_import(
    "codeweaver.config.settings", "get_settings"
)

logger: logging.Logger
_logger: logging.Logger | None = None
BRACKET_PATTERN: re.Pattern[str] = re.compile("\\[.+\\]")


# ================================================
# *     Application State and Health
# ================================================


@dataclass(order=True, kw_only=True, config=DATACLASS_CONFIG | ConfigDict(extra="forbid"))
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
        Path | None, Field(default=None, description="Path to the configuration file, if any")
    ]
    project_path: Annotated[
        DirectoryPath,
        Field(default_factory=get_project_path, description="Path to the project root"),
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
    middleware_stack: Annotated[
        tuple[Middleware, ...],
        Field(description="Tuple of FastMCP middleware instances applied to the server"),
    ] = ()
    indexer: Annotated[
        Indexer | None, Field(default=None, description="Indexer instance for background indexing")
    ] = None
    health_service: Annotated[
        HealthService | None, Field(description="Health service instance", exclude=True)
    ] = None
    failover_manager: Annotated[
        VectorStoreFailoverManager | None,
        Field(description="Failover manager instance", exclude=True),
    ] = None
    startup_time: Annotated[
        float, Field(default_factory=time.time, description="Server startup timestamp")
    ] = time.time()

    telemetry: PostHogClient | None = None

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


def _get_health_service() -> HealthService:
    """Get the health service instance."""
    from codeweaver.server.health_service import HealthService

    state = get_state()

    return HealthService(
        provider_registry=state.provider_registry,
        statistics=state.statistics,
        indexer=state.indexer,
        startup_time=state.startup_time,
    )


async def _run_background_indexing(
    state: AppState, settings: CodeWeaverSettings, status_display: Any, *, verbose: bool = False
) -> None:
    """Background task for indexing and file watching.

    Args:
        state: Application state
        settings: Configuration settings
        status_display: StatusDisplay instance for user-facing output
        verbose: Whether to show verbose output
    """
    try:
        if verbose:
            logger.info("Starting background indexing...")

        if not state.indexer:
            if verbose:
                logger.warning("No indexer configured, skipping background indexing")
            return

        # Show discovery step to user
        status_display.print_step("Discovering files...")

        # Prime index (initial indexing)
        start_time = time.time()
        await state.indexer.prime_index(force_reindex=False)
        duration = time.time() - start_time

        # Get statistics from indexer
        stats = state.indexer.stats
        files_processed = stats.files_processed
        chunks_created = stats.chunks_created
        files_discovered = stats.files_discovered
        files_per_second = stats.processing_rate()

        # Show context: X of Y files
        if files_discovered > 0:
            status_display.print_step(
                f"Found {files_processed} changed files of {files_discovered} watched"
            )

        # Show indexing results
        status_display.print_step("Indexing...")
        status_display.print_indexing_stats(
            files_indexed=files_processed,
            chunks_created=chunks_created,
            duration_seconds=duration,
            files_per_second=files_per_second,
        )

        # Start file watcher for real-time updates
        if verbose:
            logger.info("Starting file watcher...")
        from codeweaver.common.utils import get_project_path
        from codeweaver.engine.watcher import FileWatcher, IgnoreFilter

        watcher = await FileWatcher.create(
            get_project_path()
            if isinstance(settings.project_path, Unset)
            else settings.project_path,
            file_filter=await IgnoreFilter.from_settings_async(),
            walker=state.indexer._walker,
            indexer=state.indexer,
        )

        # Run watcher (this will block until cancelled)
        await watcher.run()

    except asyncio.CancelledError:
        if verbose:
            logger.info("Background indexing cancelled")
        raise
    except Exception as e:
        status_display.print_error("Background indexing error", details=str(e))
        logger.exception("Background indexing error")


def _initialize_app_state(
    app: FastMCP[AppState], settings: CodeWeaverSettings, statistics: SessionStatistics | None
) -> AppState:
    """Initialize application state if not already present."""
    if hasattr(app, "state"):
        return cast(AppState, app.state)

    state = AppState(  # type: ignore
        initialized=False,
        settings=settings,
        statistics=statistics or get_session_statistics._resolve()(),
        project_path=get_project_path()
        if isinstance(settings.project_path, Unset)
        else settings.project_path,
        config_path=settings.config_file if settings else get_settings._resolve()().config_file,
        provider_registry=get_provider_registry._resolve()(),
        services_registry=get_services_registry._resolve()(),
        model_registry=get_model_registry._resolve()(),
        middleware_stack=tuple(getattr(app, "middleware", ())),
        health_service=None,  # Initialize as None, will be set after AppState construction
        failover_manager=None,  # Initialize as None, will be set after AppState construction
        telemetry=PostHogClient.from_settings(),
        indexer=Indexer.from_settings(),
        startup_time=time.time(),
    )
    object.__setattr__(app, "state", state)
    # Now that AppState is constructed and _state is set, create the HealthService
    state.health_service = _get_health_service()
    return state


async def _cleanup_state(
    state: AppState,
    indexing_task: asyncio.Task | None,
    status_display: Any,
    *,
    verbose: bool = False,
) -> None:
    """Clean up application state and shutdown services.

    Args:
        state: Application state
        indexing_task: Background indexing task to cancel
        status_display: StatusDisplay instance for user-facing output
        verbose: Whether to show verbose output
    """
    # Show clean shutdown message
    status_display.print_shutdown_start()

    # Cancel background indexing
    if indexing_task:
        indexing_task.cancel()
        try:
            await indexing_task
        except asyncio.CancelledError:
            if verbose:
                logger.info("Background indexing stopped")

    # Shutdown telemetry client to flush pending events
    if state.telemetry:
        try:
            state.telemetry.shutdown()
        except Exception:
            logging.getLogger(__name__).exception("Error shutting down telemetry client")

    if verbose:
        logger.info("Exiting CodeWeaver lifespan context manager...")

    status_display.print_shutdown_complete()
    state.initialized = False


@asynccontextmanager
async def lifespan(
    app: FastMCP[AppState],
    settings: CodeWeaverSettings | None,
    statistics: SessionStatistics | None = None,
    *,
    verbose: bool = False,
    debug: bool = False,
) -> AsyncIterator[AppState]:
    """Context manager for application lifespan with proper initialization.

    Args:
        app: FastMCP application instance
        settings: Configuration settings
        statistics: Session statistics instance
        verbose: Enable verbose logging
        debug: Enable debug logging
    """
    from codeweaver.cli.ui import StatusDisplay

    # Create StatusDisplay for clean user-facing output
    status_display = StatusDisplay()

    # Print clean header (not in verbose mode, as this is always shown)
    server_host = getattr(app, "host", "127.0.0.1") if hasattr(app, "host") else "127.0.0.1"
    server_port = getattr(app, "port", 9328) if hasattr(app, "port") else 9328
    status_display.print_header(host=server_host, port=server_port)

    if verbose or debug:
        logger.info("Entering lifespan context manager...")

    if settings is None:
        settings = get_settings._resolve()()
    if isinstance(settings.project_path, Unset):
        settings.project_path = get_project_path()

    state = _initialize_app_state(app, settings, statistics)

    if not isinstance(state, AppState):
        raise InitializationError(
            "AppState should be an instance of AppState, but isn't. Something is wrong. Please report this issue.",
            details={"state": state},
        )

    indexing_task = None

    try:
        if verbose or debug:
            logger.info("Ensuring services set up...")

        # Start background indexing task
        indexing_task = asyncio.create_task(
            _run_background_indexing(state, settings, status_display, verbose=verbose or debug)
        )

        # Perform health checks and display results
        status_display.print_step("")
        status_display.print_step("Health checks...")

        if state.health_service:
            health_response = await state.health_service.get_health_response()

            # Display service health
            status_display.print_health_check(
                "Vector store (Qdrant)", health_response.services.vector_store.status
            )
            status_display.print_health_check(
                "Embeddings (Voyage AI)",
                health_response.services.embedding_provider.status,
                model=health_response.services.embedding_provider.model,
            )
            status_display.print_health_check(
                f"Sparse embeddings ({health_response.services.sparse_embedding.provider})",
                health_response.services.sparse_embedding.status,
            )
        if not state.failover_manager:
            state.failover_manager = VectorStoreFailoverManager()
        status_display.print_ready()

        if verbose or debug:
            logger.info("Lifespan start actions complete, server initialized.")
        state.initialized = True
        yield state
    except Exception:
        state.initialized = False
        raise
    finally:
        await _cleanup_state(state, indexing_task, status_display, verbose=verbose or debug)


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


def setup_local_logger(level: int = logging.WARNING) -> None:
    """Set up a local logger for the current module."""
    global logger
    logger = logging.getLogger(__name__)
    logger.setLevel(level)


def __setup_interim_logger(
    *, verbose: bool = False, debug: bool = False
) -> tuple[logging.Logger, int]:
    """Set up the initial logger for the application.

    Because we need to fully resolve settings before we can set up logging properly,
    we set up a basic logger first, then reconfigure it later.

    Args:
        verbose: Enable verbose logging (INFO level with console output)
        debug: Enable debug logging (DEBUG level with console output)

    Returns:
        tuple of (logger, log_level)
    """
    # Determine log level based on flags
    if debug:
        level = logging.DEBUG
    elif verbose:
        level = logging.INFO
    else:
        level = logging.WARNING

    setup_local_logger(level)

    # Only set up rich console handler if verbose or debug mode
    if verbose or debug:
        return (
            setup_logger(
                name="codeweaver", level=level, rich=True, rich_options={}, logging_kwargs=None
            ),
            level,
        )
    # No console output - just set up basic logging
    logger = logging.getLogger("codeweaver")
    logger.setLevel(level)
    # Clear any existing handlers
    logger.handlers.clear()
    return (logger, level)


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
    rich_options = app_logger_settings.get("rich_options", {})
    logging_kwargs = app_logger_settings.get("dict_config", None)
    app_logger = setup_logger(
        name="codeweaver",
        level=level,
        rich=rich,
        rich_options=rich_options,
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
    middleware: MiddlewareOptions = MiddlewareOptions(middleware_defaults | middleware)
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
            _ = base_fast_mcp_settings.pop(key, None)  # ty: ignore[no-matching-overload]
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
    settings: CodeWeaverSettings,
    session_statistics: SessionStatistics,
    *,
    verbose: bool = False,
    debug: bool = False,
) -> Any:
    """Set up file filters and create lifespan function.

    Args:
        settings: CodeWeaver settings
        session_statistics: Session statistics instance
        verbose: Enable verbose logging
        debug: Enable debug logging

    Returns:
        Configured lifespan function
    """
    return rpartial(lifespan, settings, session_statistics, verbose=verbose, debug=debug)


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
    transport: NotRequired[Literal["streamable-http", "stdio"]]
    log_level: NotRequired[Literal["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]]
    middleware: NotRequired[set[Middleware] | set[type[Middleware]]]
    verbose: NotRequired[bool]
    debug: NotRequired[bool]


def build_app(
    *,
    verbose: bool = False,
    debug: bool = False,
    transport: Literal["streamable-http", "stdio"] = "streamable-http",
) -> ServerSetup:
    """Build and configure the FastMCP application without starting it.

    Args:
        verbose: Enable verbose logging (INFO level)
        debug: Enable debug logging (DEBUG level)
        transport: Transport type for MCP communication (streamable-http or stdio)
    """
    session_statistics = get_session_statistics._resolve()()

    # Set up logger with appropriate level based on flags
    app_logger, level = __setup_interim_logger(verbose=verbose, debug=debug)

    local_logger: logging.Logger = globals()["logger"]
    if verbose or debug:
        local_logger.info("Initializing CodeWeaver server. Logging set up.")
    settings_view = get_settings_map()
    if not settings_view:
        try:
            from codeweaver.config.settings import get_settings
            from codeweaver.core.types.dictview import DictView

            if settings := get_settings():
                settings_view = DictView(
                    CodeWeaverSettingsDict(**settings.model_dump(round_trip=True))
                )
                settings_module = settings.__class__.__module__
                settings_module._mapped_settings = settings_view  # type: ignore[attr-defined]
        except Exception as e:
            raise InitializationError("Failed to load CodeWeaver settings.") from e
    middleware_settings, logging_middleware = _configure_middleware(
        settings_view, app_logger, level
    )
    filtered_server_settings = _filter_server_settings(
        lazy_import("codeweaver.config.settings", "FastMcpServerSettings")().model_dump(  # type: ignore
            round_trip=True
        )
        if isinstance((server_settings := settings_view.get("server")), Unset)
        else server_settings
    )
    middleware = {logging_middleware, *get_default_middleware()}
    base_fast_mcp_settings = _create_base_fastmcp_settings()
    base_fast_mcp_settings = _integrate_user_settings(
        settings_view.get("server", {}), filtered_server_settings
    )
    from codeweaver.config.settings import get_settings

    if verbose or debug:
        local_logger.info("Base FastMCP settings created and merged with user settings.")
        local_logger.debug("Base FastMCP settings dump \n", extra=base_fast_mcp_settings)
    lifespan_fn = _setup_file_filters_and_lifespan(
        get_settings(), session_statistics, verbose=verbose, debug=debug
    )
    base_fast_mcp_settings["lifespan"] = lifespan_fn
    _ = base_fast_mcp_settings.pop("transport", "http")
    final_app_logger, _final_level = _setup_logger(settings_view)
    int_level = next((k for k, v in LEVEL_MAP.items() if v == _final_level), "INFO")
    for key, middleware_setting in middleware_settings.items():
        if "logger" in cast(dict[str, Any], middleware_setting):
            middleware_settings[key]["logger"] = final_app_logger  # ty: ignore[invalid-key]
        if "log_level" in cast(dict[str, Any], middleware_setting):
            middleware_settings[key]["log_level"] = int_level  # ty: ignore[invalid-key]
    global _logger
    _logger = final_app_logger
    host = base_fast_mcp_settings.pop("host", "127.0.0.1")
    port = base_fast_mcp_settings.pop("port", 9328)
    http_path = "/codeweaver"
    server = FastMCP[AppState](name="CodeWeaver", **base_fast_mcp_settings)  # type: ignore
    if verbose or debug:
        local_logger.info("FastMCP application initialized successfully.")
    return ServerSetup(
        app=server,
        settings=get_settings(),
        middleware_settings=middleware_settings,
        host=host or "127.0.0.1",
        port=port or 9328,
        streamable_http_path=cast(str, http_path or "/codeweaver"),
        transport=transport,
        log_level=_final_level or "INFO",
        middleware={*middleware},
        verbose=verbose,
        debug=debug,
    )


__all__ = ("AppState", "ServerSetup", "build_app", "get_state", "lifespan")
