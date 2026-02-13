# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Doctor command for validating prerequisites and configuration.

Validates system requirements, configuration, providers, and file permissions
to help diagnose issues with CodeWeaver installations.
"""

from __future__ import annotations

import os
import sys

from pathlib import Path
from types import ModuleType
from typing import TYPE_CHECKING, Annotated, Any, Literal, cast

import cyclopts

from cyclopts import App
from pydantic import AnyUrl, FilePath, ValidationError
from rich.table import Table

from codeweaver.cli.dependencies import setup_cli_di
from codeweaver.cli.ui import CLIErrorHandler, StatusDisplay, get_display
from codeweaver.cli.utils import check_provider_package_available
from codeweaver.core import (
    CodeWeaverSettingsType,
    ProviderCategory,
    SettingsMapDep,
    Unset,
    get_codeweaver_config_paths,
    get_project_path,
    is_git_dir,
)
from codeweaver.core.config.types import CodeWeaverSettingsDict
from codeweaver.core.di import INJECTED
from codeweaver.core.types.dictview import DictView
from codeweaver.core.utils import has_package
from codeweaver.engine import ConfigChangeAnalyzerDep


if TYPE_CHECKING:
    from codeweaver.core import Provider
    from codeweaver.providers import ProviderSettings
    from codeweaver.server import CodeWeaverSettings


# Module-level display for check functions
_display: StatusDisplay = get_display()


def _get_settings_map(settings: SettingsMapDep = INJECTED) -> DictView[CodeWeaverSettingsDict]:
    """Get the settings map for CodeWeaver provider settings."""
    return settings


def _get_display() -> StatusDisplay:
    """Get the current display instance.

    Returns:
        Current StatusDisplay instance
    """
    return _display


class _ConsoleProxy:
    """Dynamic proxy that always uses the current display's console.

    This allows tests to replace the display and have all console operations
    use the new display's console automatically.
    """

    def __getattr__(self, name: str):
        """Delegate all attribute access to current display's console."""
        return getattr(_get_display().console, name)


# Console proxy that dynamically delegates to current display
console = _ConsoleProxy()


app = App(
    "doctor",
    help="Validate prerequisites and configuration for CodeWeaver.",
    console=_display.console,
)


class DoctorCheck:
    """Represents a single doctor check with results and suggestions."""

    def __init__(
        self,
        name: str,
        status: str = "pending",
        message: str = "",
        suggestions: list[str] | None = None,
    ) -> None:
        """Initialize a doctor check.

        Args:
            name: Name of the check
            status: Status icon (✅, ❌, ⚠️)
            message: Status message
            suggestions: List of actionable suggestions if check fails
        """
        self.name = name
        self.status = status
        self.message = message
        self.suggestions = suggestions or []

    @classmethod
    def set_check(
        cls,
        name: str,
        status: Literal["success", "fail", "warn"],
        message: str,
        suggestions: list[str],
    ) -> DoctorCheck:
        """Create a doctor check with given status.

        Args:
            name: Name of the check
            status: Status of the check
            message: Message to display
            suggestions: List of actionable suggestions for resolution

        Returns:
            DoctorCheck instance with given status
        """
        status_symbol = {"success": "✅", "fail": "❌", "warn": "⚠️"}.get(status, "❓")
        return cls(name, status=status_symbol, message=message, suggestions=suggestions)


def check_python_version() -> DoctorCheck:
    """Check if Python version meets minimum requirements."""
    current_version = sys.version_info
    required_version = (3, 12)

    is_valid = current_version >= required_version
    version_str = f"{current_version.major}.{current_version.minor}.{current_version.micro}"

    return DoctorCheck.set_check(
        "Python Version",
        "success" if is_valid else "fail",
        version_str
        if is_valid
        else f"{version_str} (requires ≥{required_version[0]}.{required_version[1]})",
        []
        if is_valid
        else [
            f"Upgrade Python to version {required_version[0]}.{required_version[1]} or higher",
            "Visit https://www.python.org/downloads/ for installation instructions",
        ],
    )


def check_required_dependencies() -> DoctorCheck:
    """Check if required dependencies are installed using find_spec."""
    from importlib import metadata

    # Special case mapping for packages where PyPI name differs from import name
    package_to_module_map = {"uuid7": "uuid_extensions"}

    missing: list[str] = []
    _installed: list[tuple[str, str]] = []

    if our_dependencies := metadata.metadata("codeweaver").get_all("Requires-Dist") or []:
        missing, _installed = _check_required_dependencies(
            our_dependencies, package_to_module_map, metadata
        )
    return DoctorCheck.set_check(
        "Required Dependencies",
        "fail" if missing else "success",
        f"Missing packages: {', '.join(missing)}" if missing else "All required packages installed",
        [
            "Run: uv pip install code-weaver[full]",
            "Or: pip install code-weaver[full]",
            f"Missing: {', '.join(missing)}",
        ]
        if missing
        else [],
    )


def _check_required_dependencies(
    our_dependencies: list[str], package_to_module_map: dict[str, str], metadata: ModuleType
) -> tuple[list[str], list[tuple[str, str]]]:
    """Check for required dependencies and return missing and installed packages."""
    missing: list[str] = []
    installed: list[tuple[str, str]] = []
    missing, installed = _identify_missing_dependencies(
        our_dependencies, package_to_module_map, metadata, missing, installed
    )
    return missing, installed


def _identify_missing_dependencies(
    our_dependencies: list[str],
    package_to_module_map: dict[str, str],
    metadata: ModuleType,
    missing: list[str],
    installed: list[tuple[str, str]],
):
    """Identify missing dependencies from the list of required dependencies."""
    import re

    dependency_pattern = re.compile(r"^(?P<name>[\w\-]+)>=(?P<version>\d+\.\d+\.\d+\.?\d*)$")
    dependencies = [
        dep.split(";")[0].strip() if ";" in dep else dep.strip()
        for dep in our_dependencies
        if "extra" not in dep
    ]
    matches = [
        dependency_pattern.match(dep) for dep in dependencies if dependency_pattern.match(dep)
    ]
    required_packages: list[tuple[str, str, str]] = [
        (
            match["name"],
            package_to_module_map.get(match["name"], match["name"].replace("-", "_")),
            match["version"] or "",
        )
        for match in matches
        if match
        and match["name"]
        != "py-cpuinfo"  # it's technically required, but it's for optimizations; not strictly required
    ]
    python_version = sys.version_info
    if python_version >= (3, 14) and any(pkg[0] == "uuid_extensions" for pkg in required_packages):
        required_packages = [pkg for pkg in required_packages if pkg[0] != "uuid_extensions"]

    for display_name, module_name, _version in required_packages:
        if has_package(module_name):
            pkg_version = metadata.version(display_name)
            installed.append((display_name, pkg_version))
        else:
            missing.append(display_name)
    return missing, installed


def check_project_path(settings: CodeWeaverSettings) -> DoctorCheck:
    """Check if project path exists and is accessible."""
    project_path = (
        settings.project_path if isinstance(settings.project_path, Path) else get_project_path()
    )

    error_message = ""
    suggestions: list[str] = []

    if not project_path.exists():
        error_message = f"Path does not exist: {project_path}"
        suggestions = [
            "Ensure the project path is correct in your configuration",
            "Create the directory or update the project_path setting",
        ]
    elif not project_path.is_dir():
        error_message = f"Path is not a directory: {project_path}"
        suggestions = ["Project path must be a directory, not a file"]
    elif not os.access(project_path, os.R_OK):
        error_message = f"No read permission: {project_path}"
        suggestions = [
            "Fix file permissions with: chmod +r <path>",
            "Ensure your user has read access to the project directory",
        ]

    has_error = bool(error_message)

    return DoctorCheck.set_check(
        "Project Path",
        "fail" if has_error else "success",
        error_message
        if has_error
        else f"{project_path}" + (" (git repository)" if is_git_dir(project_path) else ""),
        suggestions,
    )


def check_configuration_file(settings: CodeWeaverSettings) -> DoctorCheck:
    """Check if configuration file exists and is valid."""
    check = DoctorCheck("Configuration File")

    try:
        possible_config_locations = get_codeweaver_config_paths()

        # The function also checks for environment variable config file
        if found_config := next((loc for loc in possible_config_locations if loc.exists()), None):
            check.status = "✅"
            check.message = f"Valid config at {found_config}"
        elif (
            settings.config_file
            and not isinstance(settings.config_file, Unset)
            and settings.config_file.exists()
        ):
            # Fallback to settings.config_file if set
            check.status = "✅"
            check.message = f"Valid config at {settings.config_file}"
        else:
            check.status = "⚠️"
            check.message = "No config file (using defaults or environment variables)"
            check.suggestions = [
                "Create your config file for custom configuration",
                "Run: cw init config",
                "Or: cw init",
            ]

    except ValidationError as e:
        check.status = "❌"
        check.message = "Configuration validation failed"
        check.suggestions = [
            "Check your configuration file for syntax errors",
            f"Validation error: {e.errors()[0]['msg'] if e.errors() else 'Unknown error'}",
        ]
    except Exception as e:
        check.status = "❌"
        check.message = f"Failed to load configuration: {e!s}"
        check.suggestions = ["Check file permissions and syntax"]

    return check


def _docker_is_running() -> bool:
    """Check if Docker daemon is running."""
    import shutil
    import subprocess

    if not (docker := shutil.which("docker")):
        return False

    try:
        result = subprocess.run([docker, "info"], capture_output=True, timeout=2)  # noqa: S603
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False
    else:
        return result.returncode == 0


async def _qdrant_running_at_url(url: Any | None = None) -> bool:
    """Check if Qdrant is running at the given URL."""
    import re

    import httpx

    # Ensure URL has protocol
    if url:
        url_str = str(url)
        if not url_str.startswith(("http://", "https://")):
            url_str = f"http://{url_str}"
    else:
        url_str = "http://127.0.0.1:6333"

    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{url_str}/metrics", timeout=2.0)
    except (httpx.ConnectError, httpx.TimeoutException, httpx.RemoteProtocolError):
        return False
    else:
        return response.status_code == 200 and bool(
            re.search(r'app_info{name="qdrant"}', response.text)
        )


type DeploymentType = Literal["local docker", "cloud", "local", "remote", "in-memory", "unknown"]


async def check_vector_store_config(settings: ProviderSettings) -> DoctorCheck:
    # sourcery skip: low-code-quality
    """Check vector store configuration with Docker/Cloud detection."""
    from codeweaver.core import Provider

    check = DoctorCheck("Vector Store Configuration")

    # Check if vector store is configured in provider settings
    if isinstance(settings.vector_store, Unset):
        return DoctorCheck.set_check(
            check.name,
            "warn",
            "No vector store configured",
            ["Run: cw config init to set up a vector store"],
        )

    vector_config = (
        settings.vector_store[0]
        if isinstance(settings.vector_store, tuple)
        else settings.vector_store
    )

    # Detect deployment type
    deployment_type = "unknown"
    url = None
    if (provider := vector_config.provider) != Provider.MEMORY and (
        url := vector_config.client_options.url
    ):
        host = cast(url, AnyUrl)  # ty:ignore[invalid-type-form]
        if host and (host == "qdrant.io" or host.endswith(".qdrant.io")):
            deployment_type = "cloud"
        # if they have port in the path we need to check for inclusion, not membership or equality
        elif "localhost" not in str(url) and "127.0.0.1" not in str(url):
            deployment_type = "remote"
        else:
            deployment_type = (
                "local docker"
                if _docker_is_running()
                else "local"
                if await _qdrant_running_at_url(url)
                else "unknown"
            )
    elif provider == Provider.QDRANT:
        deployment_type = "local" if await _qdrant_running_at_url() else "unknown"
    elif provider == Provider.MEMORY:
        deployment_type = "local"
    else:
        deployment_type = "unknown"
    _display.console.print(
        f"\nVector Store: [cyan]{provider.as_title}[/cyan] ({deployment_type})"
        if deployment_type != "unknown"
        else f"\nVector Store: [cyan]{provider.as_title}[/cyan] -- [bold yellow]Unknown Deployment Type[/bold yellow]"
    )

    # Deployment-specific checks
    match deployment_type:
        case "cloud":
            return _check_qdrant_cloud_api_key(provider, settings, check, str(url))
        case "local" | "local docker":
            _display.console.print(
                f"  [green]✓[/green] Local Qdrant {'docker container' if deployment_type == 'local docker' else 'install'} detected"
            )
            # Check if Docker is running
            _display.console.print(
                f"  [green]✓[/green] {'Docker' if deployment_type == 'local docker' else 'Local Qdrant'} is running at {url!s}"
            )
        case "unknown":
            user_os = sys.platform
            _display.print_warning("Docker may not be running")
            check.status = "⚠️"
            check.message = f"We didn't find a running local Qdrant instance at {url!s}"
            check.suggestions = [
                "The quickest way to fix this is with docker",
                f"If you don't have docker, you should probably start with docker desktop: https://docs.docker.com/desktop/setup/install/{'linux' if user_os.startswith('linux') else 'windows-install' if user_os.startswith('win') else 'macos-install'}/",
                "Start Docker",
                "Run: docker run -p 6333:6333 qdrant/qdrant",
                "or use the desktop gui to find and start Qdrant",
                "more info: https://qdrant.tech/documentation/guides/installation/",
            ]

        case "in-memory":
            _display.console.print(
                "  [yellow]⚠[/yellow] You're using in-memory Qdrant. While we do try to persist data to json, this isn't suitable for any serious use. If you're testing or playing around, cool. If not, consider switching to a more robust solution."
            )
            _set_warning_status(
                check,
                "In-memory Qdrant detected",
                "We don't recommend the in-memory store for general use. Use local or cloud Qdrant instead.",
            )
        case "remote":
            if _has_auth_configured(provider, settings):
                _print_vector_store_status(
                    "  [green]✓[/green] Remote Qdrant at ", url, check, "Remote Qdrant at "
                )
            else:
                _display.console.print(
                    "  [yellow]⚠[/yellow] No API key or TLS certificates found for remote Qdrant. This may not be a problem if you have other authentication methods configured outside of the CodeWeaver settings."
                )
    return check


def _has_auth_configured(provider: Provider, settings: ProviderSettings) -> bool:
    """Check if the user has configured API keys or TLS certs for the provider."""
    return settings.has_auth_configured(provider)


def _check_qdrant_cloud_api_key(
    provider: Provider, settings: ProviderSettings, check: DoctorCheck, url: str | None
) -> DoctorCheck:
    _display.console.print("  [green]✓[/green] Qdrant Cloud detected")
    if not _has_auth_configured(provider, settings):
        return _check_qdrant_api_key_env_vars(provider, check)
    _display.console.print("  [green]✓[/green] We found your api_key for Qdrant Cloud")
    check.status = "✅"
    check.message = f"Qdrant Cloud at {url}"
    return check


def _check_qdrant_api_key_env_vars(provider: Provider, check: DoctorCheck) -> DoctorCheck:
    possible_keys = cast(tuple[str, ...], provider.api_key_env_vars)

    # Check if env vars are actually set (for debugging)
    import os

    set_vars = [key for key in possible_keys if os.getenv(key)]

    if set_vars:
        # Env var is set but not being detected by has_auth_configured
        _display.console.print(
            f"  [yellow]⚠[/yellow] Found {', '.join(set_vars)} in environment, but authentication check failed."
        )
        _display.console.print(
            "  [yellow]⚠[/yellow] This might be an issue with how the provider checks credentials."
        )
    else:
        # Env var not set
        _display.console.print(
            f"  [yellow]⚠[/yellow] You need to set your Qdrant API key. You can set using one of these environment variables: {', '.join(possible_keys)}"
            if len(possible_keys) > 1
            else f"  [yellow]⚠[/yellow] You need to set your Qdrant API key. You can set using the environment variable: {possible_keys[0]}"
        )
    check.status = "⚠️"
    check.suggestions = [
        "Check provider authentication logic"
        if set_vars
        else f"Set {possible_keys[0]} environment variable",
        "Or configure api_key in your codeweaver.toml file",
    ]
    return check


def _print_vector_store_status(
    intro: str, url: str | Any | None, check: DoctorCheck, message: str
) -> None:
    _display.console.print(f"{intro}{url!s}")
    check.status = "✅"
    check.message = f"{message}{url!s}"


def _set_warning_status(check: DoctorCheck, message: str, suggestion: str) -> None:
    check.status = "⚠️"
    check.message = message
    check.suggestions = [suggestion]


def check_indexer_config(settings: CodeWeaverSettings) -> DoctorCheck:
    """Check if the indexer is properly configured and cache directory is writable."""
    from codeweaver.engine.config import IndexerSettings

    check = DoctorCheck("Indexer Configuration")

    try:
        if not isinstance(settings.indexer, IndexerSettings):
            return DoctorCheck.set_check(
                check.name,
                "warn",
                "No indexer settings configured",
                ["Configure indexer settings in your configuration file"],
            )
        # the cache_dir is created on access if it doesn't exist
        # so it should always exist here unless there's a permission issue
        cache_dir = settings.indexer.cache_dir
        # cache dir will exist or there's an exception so we won't get here
        if not os.access(cache_dir, os.W_OK):
            check.status = "❌"
            check.message = f"No write permission: {cache_dir}"
            check.suggestions = [
                f"Fix permissions with: chmod +w {cache_dir!s}",
                "Ensure your user has write access to the cache directory",
            ]
        else:
            check.status = "✅"
            check.message = f"{cache_dir}"
    except OSError as e:
        check.status = "❌"
        check.message = f"OS error accessing cache directory: {e.strerror}"
        check.suggestions = [
            "Check file system permissions",
            "Ensure the cache directory path is valid",
        ]
    except Exception as e:
        check.status = "❌"
        check.message = f"Failed to validate cache directory: {e!s}"
        check.suggestions = ["Check configuration"]

    return check


def _report_unimplemented_status(
    category: ProviderCategory, provider: Provider, *, is_available: bool, has_auth: bool
) -> DoctorCheck | None:
    """Report unimplemented provider status checks for DATA and AGENT providers."""
    if category not in {ProviderCategory.DATA, ProviderCategory.AGENT}:
        return None
    name = f"{category.as_title} ({provider.as_title})"
    if category == ProviderCategory.DATA:
        message = "We're still integrating data providers into CodeWeaver. Stay tuned!"
        return DoctorCheck.set_check(name, "warn", message, [])
    message = (
        "CodeWeaver is set up for agents, but they aren't integrated into the search pipeline yet."
    )
    if is_available and has_auth:
        message += " You've done everything right; we're just working on the integration!"
    if is_available and not has_auth:
        message += " The provider is available, but authentication isn't set up yet. You can get ready for v0.2 by configuring authentication."
    return DoctorCheck.set_check(name, "warn", message, [])


def check_provider_availability(settings: ProviderSettings) -> list[DoctorCheck]:
    """Test basic connectivity to configured providers."""
    check = DoctorCheck("Provider Availability")

    try:
        tested_providers: list[DoctorCheck] = []

        if not (configs := settings.provider_configs):
            return [
                DoctorCheck.set_check(
                    check.name,
                    "fail",
                    "No provider configurations found",
                    ["Configure providers in your codeweaver configuration."],
                )
            ]
        from codeweaver.core import ProviderCategory

        for category, provider_configs in configs.items():
            if not provider_configs:
                continue
            for provider_config in provider_configs:
                category = ProviderCategory.from_string(cast(str, category))
                provider = provider_config["provider"]
                # Check package availability manually (Registry replacement)
                is_package_available = check_provider_package_available(provider, category)
                has_auth = provider.has_env_auth or provider.is_local_provider
                if category in {ProviderCategory.DATA, ProviderCategory.AGENT}:
                    tested_providers.append(
                        _report_unimplemented_status(
                            category, provider, is_available=is_package_available, has_auth=has_auth
                        )  # type: ignore
                    )
                    continue

                if is_package_available and has_auth:
                    # Package installed AND credentials configured
                    tested_providers.append(
                        DoctorCheck.set_check(
                            f"{category.as_title} ({provider.as_title})",
                            "success",
                            "Package installed and configured",
                            [],
                        )
                    )
                elif is_package_available:
                    # Package installed but missing credentials
                    env_vars = provider.api_key_env_vars
                    tested_providers.append(
                        DoctorCheck.set_check(
                            f"{category.as_title} ({provider.as_title})",
                            "warn",
                            "Package installed but missing credentials",
                            [
                                f"Set environment variable: {env_vars[0]}"
                                if env_vars
                                else "Configure API key in settings",
                                "Or configure in your codeweaver.toml file",
                            ],
                        )
                    )
                else:
                    # Package not installed
                    tested_providers.append(
                        DoctorCheck.set_check(
                            f"{category.as_title} ({provider.as_title})",
                            "fail",
                            "Package not installed",
                            [
                                f"Install extra dependencies for {provider.as_title}",
                                "Run: uv pip install code-weaver[full]",
                                "Or: pip install code-weaver[full]",
                            ],
                        )
                    )
        if not configs.get("embedding") and not configs.get("sparse_embedding"):
            return [
                DoctorCheck.set_check(
                    check.name,
                    "warn",
                    "No embedding providers configured",
                    ["Configure at least one embedding provider in your codeweaver configuration."],
                )
            ]

    except Exception as e:
        return [
            DoctorCheck.set_check(
                check.name,
                "fail",
                f"Failed to test provider availability: {e!s}",
                ["Check logs for details", "Report issue if this persists"],
            )
        ]

    return tested_providers


def _get_health_endpoint():
    settings_map = _get_settings_map()
    host = settings_map.get("management_host", "localhost")
    port = settings_map.get("management_port", 9329)
    return f"http://{host}:{port}/health/"


def _print_check_suggestions(
    checks: list[DoctorCheck],
    verbose: bool,  # noqa: FBT001
    display: StatusDisplay,
) -> tuple[bool, bool]:
    """Print suggestions for failed/warning checks.

    Args:
        checks: List of doctor checks
        verbose: Whether to show warnings
        display: StatusDisplay for output

    Returns:
        Tuple of (has_failures, has_warnings)
    """
    has_failures = False
    has_warnings = False

    for check in checks:
        if check.status == "❌":
            has_failures = True
            if check.suggestions:
                display.console.print(f"\n[bold]{check.name}[/bold]")
                for suggestion in check.suggestions:
                    display.console.print(f"  • {suggestion}")
        elif check.status == "⚠️" and verbose:
            has_warnings = True
            if check.suggestions:
                display.console.print(f"\n[bold]{check.name}[/bold]")
                for suggestion in check.suggestions:
                    display.console.print(f"  • {suggestion}")

    return has_failures, has_warnings


def _print_summary(has_failures: bool, has_warnings: bool, display: StatusDisplay) -> None:  # noqa: FBT001
    """Print summary and exit with appropriate code.

    Args:
        has_failures: Whether any checks failed
        has_warnings: Whether any checks have warnings
        display: StatusDisplay for output
    """
    display.console.print()
    if not has_failures and not has_warnings:
        display.print_success("All checks passed")
        sys.exit(0)
    elif not has_failures:
        display.print_warning("Some checks have warnings (use --verbose for details)")
        sys.exit(0)
    else:
        display.print_error("Some checks failed")
        sys.exit(1)


async def check_embedding_compatibility(
    config_analyzer: ConfigChangeAnalyzerDep = INJECTED,
) -> DoctorCheck:
    """Check if current embedding config matches collection.

    This check validates that the current embedding configuration is compatible
    with any existing indexed collection. It identifies:
    - No changes (index remains valid)
    - Compatible changes (query model changes in asymmetric config)
    - Transformations (quantization or dimension reduction possible)
    - Breaking changes (requires reindexing)

    ARCHITECTURE NOTE: Service automatically injected by DI container.
    Service itself has plain __init__ with no DI markers.
    """
    try:
        # Analyze current configuration
        analysis = await config_analyzer.analyze_current_config()

        if analysis is None:
            return DoctorCheck.set_check(
                "Embedding Configuration",
                "warn",
                "No existing collection found",
                ["Run 'cw index' to create initial index"],
            )

        from codeweaver.engine.managers.checkpoint_manager import ChangeImpact

        match analysis.impact:
            case ChangeImpact.NONE:
                return DoctorCheck.set_check(
                    "Embedding Configuration",
                    "success",
                    "Configuration matches indexed collection",
                    [],
                )

            case ChangeImpact.COMPATIBLE:
                return DoctorCheck.set_check(
                    "Embedding Configuration",
                    "success",
                    "Configuration change is compatible with indexed collection",
                    ["No reindex needed (same family)"],
                )

            case ChangeImpact.QUANTIZABLE:
                if analysis.transformations:
                    trans = analysis.transformations[0]
                    return DoctorCheck.set_check(
                        "Embedding Configuration",
                        "warn",
                        "Quantization available",
                        [
                            f"Can quantize {trans.old_value} → {trans.new_value}",
                            f"Time: {trans.time_estimate}",
                            f"Accuracy: {trans.accuracy_impact}",
                            "Run: cw migrate --quantize-only",
                        ],
                    )
                return DoctorCheck.set_check(
                    "Embedding Configuration",
                    "warn",
                    "Quantization possible",
                    ["No quantization transformations found"],
                )

            case ChangeImpact.TRANSFORMABLE:
                return DoctorCheck.set_check(
                    "Embedding Configuration",
                    "warn",
                    "Dimension reduction available",
                    [
                        "Can transform without full reindexing",
                        f"Time: ~{analysis.estimated_time.total_seconds():.0f}s",
                        f"Cost: ${analysis.estimated_cost:.4f}",
                        f"Accuracy: {analysis.accuracy_impact}",
                        "Run: cw migrate --dimension-reduction",
                    ],
                )

            case ChangeImpact.BREAKING:
                return DoctorCheck.set_check(
                    "Embedding Configuration",
                    "fail",
                    "Incompatible configuration change detected",
                    [
                        f"Reason: {analysis.accuracy_impact}",
                        f"Reindex required (~{analysis.estimated_time.total_seconds():.0f}s)",
                        "Options:",
                        "  1. Revert config: cw config revert",
                        "  2. Reindex: cw index --force",
                        "  3. Migrate: cw migrate",
                    ],
                )

    except Exception as e:
        return DoctorCheck.set_check(
            "Embedding Configuration",
            "fail",
            f"Error checking compatibility: {e}",
            ["Check logs for details"],
        )


async def process_checks(
    display: StatusDisplay, settings: CodeWeaverSettings, container: Any = None
) -> list[DoctorCheck]:
    """Process all doctor checks and return the results.

    Args:
        display: StatusDisplay for output
        settings: CodeWeaver settings object
        container: Optional DI container for resolving services

    Returns:
        List of DoctorCheck results
    """
    from codeweaver.core import CodeWeaverError

    checks: list[DoctorCheck] = [check_python_version(), check_required_dependencies()]
    # Configuration checks
    config_failed = False
    try:
        checks.append(check_configuration_file(settings))

    except CodeWeaverError as e:
        checks.append(
            DoctorCheck.set_check(
                "Configuration Loading",
                "fail",
                e.message,
                e.suggestions or ["Check configuration file for errors"],
            )
        )
        config_failed = True
    except Exception as e:
        config_failed = True
        checks.append(
            DoctorCheck.set_check(
                "Configuration Loading",
                "fail",
                f"Unexpected error: {e!s}",
                ["Check logs for details", "Report issue if this persists"],
            )
        )
    if config_failed or settings is None or isinstance(settings, Unset):
        return checks
    checks.extend((check_project_path(settings), check_indexer_config(settings)))
    if not (provider_settings := settings.provider) or isinstance(provider_settings, Unset):
        checks.append(
            DoctorCheck.set_check(
                "Provider Settings",
                "warn",
                "No provider settings configured",
                ["Configure providers in your codeweaver configuration."],
            )
        )
        return checks
    checks.extend((
        await check_vector_store_config(provider_settings),
        *check_provider_availability(provider_settings),
    ))

    # Check embedding configuration compatibility if container is available
    if container:
        try:
            embedding_check = await container.resolve(check_embedding_compatibility)
            checks.append(embedding_check)
        except Exception as e:
            checks.append(
                DoctorCheck.set_check(
                    "Embedding Configuration",
                    "warn",
                    f"Could not check embedding compatibility: {e}",
                    ["This check is optional and doesn't affect core functionality"],
                )
            )

    if remote_providers := {
        provider for provider in provider_settings.providers if provider.requires_auth
    }:
        for provider in remote_providers:
            if not _has_auth_configured(provider, provider_settings):
                checks.append(
                    DoctorCheck.set_check(
                        f"{provider.as_title} Authentication",
                        "warn",
                        f"No authentication configured for {provider.as_title}",
                        [
                            f"Set up authentication for {provider.as_title} in your configuration",
                            "Refer to the documentation for required API keys or credentials",
                        ],
                    )
                )
            else:
                checks.append(
                    DoctorCheck.set_check(
                        f"{provider.as_title} Authentication",
                        "success",
                        f"Authentication configured for {provider.as_title}",
                        [],
                    )
                )

    return checks


@app.default
async def doctor(
    *,
    verbose: bool = False,
    display: StatusDisplay | None = None,
    config_file: Annotated[
        FilePath | None,
        cyclopts.Parameter(
            name=["--config-file", "-c"], help="Path to a specific config file to use"
        ),
    ] = None,
    project_path: Annotated[Path | None, cyclopts.Parameter(name=["--project", "-p"])] = None,
) -> None:
    """Validate prerequisites and configuration.

    Args:
        verbose: Show detailed information for all checks
        display: StatusDisplay instance for output
        config_file: Path to a specific config file to use
        project_path: Path to project directory
    """
    global _display
    if display is None:
        display = _display
    _display = display  # Set module-level display for check functions

    display.console.print()
    display.print_section("Running diagnostic checks...")
    display.console.print()

    # Setup DI Container
    container = setup_cli_di(config_file, project_path, verbose=verbose)
    settings = await container.resolve(CodeWeaverSettingsType)

    checks: list[DoctorCheck] = await process_checks(display, settings, container)
    # Display results table
    table = Table(show_header=True, header_style="bold blue", box=None)
    table.add_column("Status", style="white", no_wrap=True, width=6)
    table.add_column("Check", style="cyan", no_wrap=True)
    table.add_column("Result", style="white")

    for check in checks:
        table.add_row(check.status, check.name, check.message)

    display.print_table(table)

    # Show suggestions for failed/warning checks
    has_failures, has_warnings = _print_check_suggestions(checks, verbose, display)

    # Print summary and exit with appropriate code
    _print_summary(has_failures, has_warnings, display)


def main() -> None:
    """Entry point for the doctor CLI command."""
    display = StatusDisplay()
    error_handler = CLIErrorHandler(display, verbose=True, debug=True)

    try:
        app()
    except KeyboardInterrupt:
        display.console.print()
        display.print_warning("Operation cancelled by user")
        sys.exit(1)
    except Exception as e:
        error_handler.handle_error(e, "Doctor", exit_code=1)


if __name__ == "__main__":
    app()
