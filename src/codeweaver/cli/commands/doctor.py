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

from importlib.util import find_spec
from pathlib import Path
from typing import TYPE_CHECKING

from cyclopts import App
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from codeweaver.common import CODEWEAVER_PREFIX
from codeweaver.common.utils.git import get_project_path, is_git_dir
from codeweaver.common.utils.utils import get_user_config_dir


if TYPE_CHECKING:
    from codeweaver.config.settings import CodeWeaverSettings


console = Console(markup=True, emoji=True)
app = App(
    "doctor", help="Validate prerequisites and configuration for CodeWeaver.", console=console
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


def check_python_version() -> DoctorCheck:
    """Check if Python version meets minimum requirements."""
    check = DoctorCheck("Python Version")

    current_version = sys.version_info
    required_version = (3, 12)

    if current_version >= required_version:
        check.status = "✅"
        check.message = f"{current_version.major}.{current_version.minor}.{current_version.micro}"
    else:
        check.status = "❌"
        check.message = (
            f"{current_version.major}.{current_version.minor}.{current_version.micro} "
            f"(requires ≥{required_version[0]}.{required_version[1]})"
        )
        check.suggestions = [
            f"Upgrade Python to version {required_version[0]}.{required_version[1]} or higher",
            "Visit https://www.python.org/downloads/ for installation instructions",
        ]

    return check


def check_required_dependencies() -> DoctorCheck:
    """Check if required dependencies are installed using find_spec."""
    check = DoctorCheck("Required Dependencies")

    required_packages = [
        ("fastmcp", "fastmcp"),
        ("pydantic", "pydantic"),
        ("pydantic_settings", "pydantic_settings"),
        ("cyclopts", "cyclopts"),
        ("rich", "rich"),
        ("ast_grep_py", "ast_grep_py"),
        ("qdrant_client", "qdrant_client"),
        ("voyageai", "voyageai"),
        ("rignore", "rignore"),
    ]

    missing: list[str] = []
    installed: list[tuple[str, str]] = []

    for display_name, module_name in required_packages:
        if spec := find_spec(module_name):
            # Try to get version if available
            try:
                module = __import__(module_name)
                pkg_version = getattr(module, "__version__", "installed")
            except Exception:
                pkg_version = "installed"
            installed.append((display_name, pkg_version))
        else:
            missing.append(display_name)

    if not missing:
        check.status = "✅"
        check.message = "All required packages installed"
    else:
        check.status = "❌"
        check.message = f"Missing packages: {', '.join(missing)}"
        check.suggestions = [
            "Run: uv sync --all-groups",
            "Or: pip install codeweaver-mcp[all]",
            f"Missing: {', '.join(missing)}",
        ]

    return check


def check_configuration_file(settings: CodeWeaverSettings | None = None) -> DoctorCheck:
    """Check if configuration file exists and is valid."""
    check = DoctorCheck("Configuration File")

    try:
        if settings is None:
            from codeweaver.config.settings import get_settings

            settings = get_settings()

        if settings.config_file:
            check.status = "✅"
            check.message = f"Valid config at {settings.config_file}"
        else:
            check.status = "⚠️"
            check.message = "No config file (using defaults)"
            check.suggestions = [
                "Create .codeweaver.toml in project root for custom configuration",
                "Run: codeweaver config --generate",
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
        check.suggestions = [
            "Check file permissions and syntax",
            "Run: codeweaver config --show to diagnose",
        ]

    return check


def check_project_path(settings: CodeWeaverSettings) -> DoctorCheck:
    """Check if project path exists and is accessible."""
    check = DoctorCheck("Project Path")

    try:
        # Use helper function to get project path
        project_path = (
            settings.project_path
            if isinstance(settings.project_path, Path)
            else get_project_path()
        )

        if not project_path.exists():
            check.status = "❌"
            check.message = f"Path does not exist: {project_path}"
            check.suggestions = [
                "Ensure the project path is correct in your configuration",
                "Create the directory or update the project_path setting",
            ]
        elif not project_path.is_dir():
            check.status = "❌"
            check.message = f"Path is not a directory: {project_path}"
            check.suggestions = ["Project path must be a directory, not a file"]
        elif not os.access(project_path, os.R_OK):
            check.status = "❌"
            check.message = f"No read permission: {project_path}"
            check.suggestions = [
                "Fix file permissions with: chmod +r <path>",
                "Ensure your user has read access to the project directory",
            ]
        else:
            check.status = "✅"
            check.message = f"{project_path}"
            # Show git status if available
            if is_git_dir(project_path):
                check.message += " (git repository)"

    except Exception as e:
        check.status = "❌"
        check.message = f"Failed to validate project path: {e!s}"
        check.suggestions = ["Check configuration and file system permissions"]

    return check


def _is_docker_running() -> bool:
    """Check if Docker daemon is running."""
    import subprocess

    try:
        result = subprocess.run(
            ["docker", "info"],
            capture_output=True,
            timeout=2,
        )
        return result.returncode == 0
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def check_vector_store_config(settings: CodeWeaverSettings) -> DoctorCheck:
    """Check vector store configuration with Docker/Cloud detection."""
    from codeweaver.core.types.sentinel import Unset

    check = DoctorCheck("Vector Store Configuration")

    # Check if vector store is configured in provider settings
    if not (
        hasattr(settings, "provider")
        and hasattr(settings.provider, "vector_store")
        and not isinstance(settings.provider.vector_store, Unset)
    ):
        check.status = "⚠️"
        check.message = "No vector store configured"
        check.suggestions = ["Run: codeweaver config init"]
        return check

    vector_config = settings.provider.vector_store

    # Detect deployment type
    deployment_type = "unknown"
    url = None

    if hasattr(vector_config, "url") and not isinstance(vector_config.url, Unset):
        url = str(vector_config.url)
        if "cloud.qdrant.io" in url:
            deployment_type = "cloud"
        elif "localhost" in url or "127.0.0.1" in url:
            deployment_type = "docker"
        else:
            deployment_type = "remote"
    elif hasattr(vector_config, "location") and not isinstance(vector_config.location, Unset):
        location = str(vector_config.location)
        if location == "memory" or location == ":memory:":
            deployment_type = "in-memory"
        elif location == "local":
            deployment_type = "local"

    console.print(f"\nVector Store: [cyan]qdrant[/cyan] ({deployment_type})")

    # Deployment-specific checks
    match deployment_type:
        case "cloud":
            console.print("  [green]✓[/green] Qdrant Cloud detected")
            if not os.getenv("QDRANT_API_KEY"):
                console.print("  [yellow]⚠[/yellow] QDRANT_API_KEY not set (may cause auth errors)")
                check.status = "⚠️"
                check.message = f"Qdrant Cloud at {url}"
                check.suggestions = ["Set QDRANT_API_KEY environment variable"]
            else:
                console.print("  [green]✓[/green] QDRANT_API_KEY configured")
                check.status = "✅"
                check.message = f"Qdrant Cloud at {url}"

        case "docker":
            console.print("  [green]✓[/green] Docker Qdrant detected")
            # Check if Docker is running
            if _is_docker_running():
                console.print("  [green]✓[/green] Docker is running")
                check.status = "✅"
                check.message = f"Docker Qdrant at {url}"
            else:
                console.print("  [yellow]⚠[/yellow] Docker may not be running")
                check.status = "⚠️"
                check.message = f"Docker Qdrant at {url} (Docker not detected)"
                check.suggestions = ["Start Docker", "Run: docker run -p 6333:6333 qdrant/qdrant"]

        case "local":
            if hasattr(vector_config, "path") and not isinstance(vector_config.path, Unset):
                path = Path(vector_config.path)
                if path.exists():
                    console.print(f"  [green]✓[/green] Data directory exists: {path}")
                    check.status = "✅"
                    check.message = f"Local Qdrant at {path}"
                else:
                    console.print(f"  [yellow]~[/yellow] Data directory will be created: {path}")
                    check.status = "✅"
                    check.message = f"Local Qdrant at {path} (will be created)"

        case "in-memory":
            console.print("  [yellow]⚠[/yellow] In-memory mode (data lost on restart)")
            check.status = "⚠️"
            check.message = "In-memory Qdrant (not persistent)"
            check.suggestions = ["Use local or cloud Qdrant for production"]

        case "remote":
            console.print(f"  [green]✓[/green] Remote Qdrant at {url}")
            check.status = "✅"
            check.message = f"Remote Qdrant at {url}"

        case _:
            check.status = "⚠️"
            check.message = "Vector store type unknown"

    return check


def check_vector_store_path(settings: CodeWeaverSettings) -> DoctorCheck:
    """Check if vector store path is writable."""
    check = DoctorCheck("Vector Store Path")

    try:
        # Get cache directory from indexing settings using helper
        if hasattr(settings.indexing, "cache_dir"):
            cache_dir = Path(settings.indexing.cache_dir)
        else:
            # Fallback to default location using helper
            cache_dir = get_user_config_dir() / "cache"

        # Create if doesn't exist
        if not cache_dir.exists():
            try:
                cache_dir.mkdir(parents=True, exist_ok=True)
                check.status = "✅"
                check.message = f"Created cache directory: {cache_dir}"
            except PermissionError:
                check.status = "❌"
                check.message = f"Cannot create cache directory: {cache_dir}"
                check.suggestions = [
                    "Fix directory permissions",
                    "Ensure your user can write to the parent directory",
                ]
                return check
        elif not os.access(cache_dir, os.W_OK):
            check.status = "❌"
            check.message = f"No write permission: {cache_dir}"
            check.suggestions = [
                "Fix permissions with: chmod +w <path>",
                "Ensure your user has write access to the cache directory",
            ]
        else:
            check.status = "✅"
            check.message = f"{cache_dir}"

    except Exception as e:
        check.status = "❌"
        check.message = f"Failed to validate cache directory: {e!s}"
        check.suggestions = ["Check configuration and file system permissions"]

    return check


def _check_embedding_api_keys(settings: CodeWeaverSettings, warnings: list[str]) -> None:
    """Check embedding provider API keys using Provider.other_env_vars."""
    if not (hasattr(settings, "provider") and hasattr(settings.provider, "embedding")):
        return

    from codeweaver.providers.provider import Provider

    embedding_provider_name = getattr(settings.provider.embedding, "provider", None)
    if not embedding_provider_name:
        return

    provider = Provider.from_string(embedding_provider_name)
    if not provider or not (env_vars_list := provider.other_env_vars):
        return

    # Check required environment variables
    for env_vars in env_vars_list:
        if "api_key" in env_vars and not os.getenv(env_vars["api_key"].env):
            warnings.append(f"{env_vars['api_key'].env} not set ({env_vars['api_key'].description})")

        # Also check TLS certs if they exist
        if "tls_cert_path" in env_vars:
            cert_path_env = env_vars["tls_cert_path"].env
            cert_path = os.getenv(cert_path_env)
            if cert_path and not Path(cert_path).exists():
                warnings.append(f"{cert_path_env} points to non-existent file: {cert_path}")


def _check_vector_store_api_keys(settings: CodeWeaverSettings, warnings: list[str]) -> None:
    """Check vector store provider API keys using Provider.other_env_vars."""
    if not (hasattr(settings, "provider") and hasattr(settings.provider, "vector_store")):
        return

    from codeweaver.providers.provider import Provider

    vector_store_name = getattr(settings.provider.vector_store, "provider", None)
    if not vector_store_name:
        return

    # Only check if remote Qdrant (local doesn't need API keys)
    if vector_store_name == "qdrant":
        is_remote = (
            hasattr(settings.provider.vector_store, "remote")
            and settings.provider.vector_store.remote
        )
        if not is_remote:
            return

    provider = Provider.from_string(vector_store_name)
    if not provider or not (env_vars_list := provider.other_env_vars):
        return

    # Check required environment variables
    for env_vars in env_vars_list:
        if "api_key" in env_vars and not os.getenv(env_vars["api_key"].env):
            warnings.append(f"{env_vars['api_key'].env} not set ({env_vars['api_key'].description})")

        # Check TLS certificates if configured
        if "tls_cert_path" in env_vars:
            cert_path_env = env_vars["tls_cert_path"].env
            cert_path = os.getenv(cert_path_env)
            if cert_path and not Path(cert_path).exists():
                warnings.append(f"{cert_path_env} points to non-existent file: {cert_path}")


def _check_reranking_api_keys(settings: CodeWeaverSettings, warnings: list[str]) -> None:
    """Check reranking provider API keys using Provider.other_env_vars."""
    if not (
        hasattr(settings, "provider")
        and hasattr(settings.provider, "reranking")
        and settings.provider.reranking
    ):
        return

    from codeweaver.providers.provider import Provider

    reranking_provider_name = getattr(settings.provider.reranking, "provider", None)
    if not reranking_provider_name:
        return

    provider = Provider.from_string(reranking_provider_name)
    if not provider or not (env_vars_list := provider.other_env_vars):
        return

    # Check required environment variables
    for env_vars in env_vars_list:
        if "api_key" in env_vars and not os.getenv(env_vars["api_key"].env):
            warnings.append(f"{env_vars['api_key'].env} not set (for reranking: {env_vars['api_key'].description})")


def check_provider_api_keys(settings: CodeWeaverSettings) -> DoctorCheck:
    """Check if provider API keys are configured."""
    check = DoctorCheck("Provider API Keys")
    warnings: list[str] = []
    errors: list[str] = []

    try:
        _check_embedding_api_keys(settings, warnings)
        _check_vector_store_api_keys(settings, warnings)
        _check_reranking_api_keys(settings, warnings)
    except Exception as e:
        check.status = "⚠️"
        check.message = f"Could not validate API keys: {e!s}"
        return check

    if errors:
        check.status = "❌"
        check.message = "; ".join(errors)
        check.suggestions = [
            "Set missing API keys as environment variables",
            "Add them to .env file in project root",
            "Or configure in .codeweaver.toml",
        ]
    elif warnings:
        check.status = "⚠️"
        check.message = "; ".join(warnings)
        check.suggestions = [
            "Provider may work without API key (e.g., local models)",
            "Set API keys if using cloud providers",
        ]
    else:
        check.status = "✅"
        check.message = "API keys configured or not required"

    return check


def check_provider_connections(settings: CodeWeaverSettings) -> DoctorCheck:
    """Test basic connectivity to configured providers."""
    check = DoctorCheck("Provider Connections")

    try:
        from codeweaver.common.registry import get_provider_registry
        from codeweaver.core.types.sentinel import Unset

        registry = get_provider_registry()
        all_passed = True
        tested_providers: list[str] = []

        # Test embedding provider
        if (
            hasattr(settings, "provider")
            and hasattr(settings.provider, "embedding")
            and not isinstance(settings.provider.embedding, Unset)
        ):
            provider_name = getattr(settings.provider.embedding, "provider", None)
            if provider_name:
                try:
                    # Basic connectivity check: try to get the provider instance
                    from codeweaver.providers.provider import ProviderKind

                    if registry.is_provider_available(provider_name, ProviderKind.EMBEDDING):
                        tested_providers.append(f"✅ Embedding: {provider_name}")
                    else:
                        tested_providers.append(f"❌ Embedding: {provider_name} (not available)")
                        all_passed = False
                except Exception as e:
                    tested_providers.append(f"❌ Embedding: {provider_name} ({e!s})")
                    all_passed = False

        # Test vector store
        if (
            hasattr(settings, "provider")
            and hasattr(settings.provider, "vector_store")
            and not isinstance(settings.provider.vector_store, Unset)
        ):
            provider_name = getattr(settings.provider.vector_store, "provider", None)
            if provider_name:
                try:
                    from codeweaver.providers.provider import ProviderKind

                    if registry.is_provider_available(provider_name, ProviderKind.VECTOR_STORE):
                        tested_providers.append(f"✅ Vector Store: {provider_name}")
                    else:
                        tested_providers.append(
                            f"❌ Vector Store: {provider_name} (not available)"
                        )
                        all_passed = False
                except Exception as e:
                    tested_providers.append(f"❌ Vector Store: {provider_name} ({e!s})")
                    all_passed = False

        if not tested_providers:
            check.status = "⚠️"
            check.message = "No providers configured to test"
            check.suggestions = ["Configure providers in .codeweaver.toml"]
        elif all_passed:
            check.status = "✅"
            check.message = "; ".join(tested_providers)
        else:
            check.status = "❌"
            check.message = "; ".join(tested_providers)
            check.suggestions = [
                "Check provider API keys and environment variables",
                "Verify network connectivity",
                "Run: codeweaver config --show to review configuration",
            ]

    except Exception as e:
        check.status = "❌"
        check.message = f"Connection test failed: {e!s}"
        check.suggestions = [
            "Check provider configuration",
            "Verify API keys are set correctly",
        ]

    return check


def _print_check_suggestions(
    checks: list[DoctorCheck],
    verbose: bool,  # noqa: FBT001
) -> tuple[bool, bool]:
    """Print suggestions for failed/warning checks.

    Args:
        checks: List of doctor checks
        verbose: Whether to show warnings

    Returns:
        Tuple of (has_failures, has_warnings)
    """
    has_failures = False
    has_warnings = False

    for check in checks:
        if check.status == "❌":
            has_failures = True
            if check.suggestions:
                console.print(f"\n[red]✗[/red] [bold]{check.name}[/bold]")
                for suggestion in check.suggestions:
                    console.print(f"  • {suggestion}")
        elif check.status == "⚠️" and verbose:
            has_warnings = True
            if check.suggestions:
                console.print(f"\n[yellow]⚠[/yellow] [bold]{check.name}[/bold]")
                for suggestion in check.suggestions:
                    console.print(f"  • {suggestion}")

    return has_failures, has_warnings


def _print_summary(has_failures: bool, has_warnings: bool) -> None:  # noqa: FBT001
    """Print summary and exit with appropriate code.

    Args:
        has_failures: Whether any checks failed
        has_warnings: Whether any checks have warnings
    """
    console.print()
    if not has_failures and not has_warnings:
        console.print(f"{CODEWEAVER_PREFIX} [green]✓ All checks passed[/green]")
        sys.exit(0)
    elif not has_failures:
        console.print(
            f"{CODEWEAVER_PREFIX} [yellow]⚠ Some checks have warnings (use --verbose for details)[/yellow]"
        )
        sys.exit(0)
    else:
        console.print(f"{CODEWEAVER_PREFIX} [red]✗ Some checks failed[/red]")
        sys.exit(1)


@app.default
def doctor(*, test_connections: bool = False, verbose: bool = False) -> None:
    """Validate prerequisites and configuration.

    Args:
        test_connections: Test actual connectivity to providers (may incur costs)
        verbose: Show detailed information for all checks
    """
    from codeweaver.exceptions import CodeWeaverError

    console.print(f"\n{CODEWEAVER_PREFIX} [bold blue]Running diagnostic checks...[/bold blue]\n")

    checks: list[DoctorCheck] = []
    settings: CodeWeaverSettings | None = None

    checks.extend((check_python_version(), check_required_dependencies()))
    # Configuration checks
    config_failed = False
    try:
        from codeweaver.config.settings import get_settings

        settings = get_settings()
        checks.append(check_configuration_file(settings))

    except CodeWeaverError as e:
        config_failed = True
        error_check = DoctorCheck("Configuration Loading")
        error_check.status = "❌"
        error_check.message = e.message
        error_check.suggestions = e.suggestions
        checks.append(error_check)
    except Exception as e:
        config_failed = True
        error_check = DoctorCheck("Configuration Loading")
        error_check.status = "❌"
        error_check.message = f"Unexpected error: {e!s}"
        error_check.suggestions = ["Check logs for details", "Report issue if this persists"]
        checks.append(error_check)

    # Only run dependent checks if settings loaded successfully
    if not config_failed and settings is not None:
        checks.extend((
            check_project_path(settings),
            check_vector_store_config(settings),
            check_vector_store_path(settings),
            check_provider_api_keys(settings),
        ))
        if test_connections:
            checks.append(check_provider_connections(settings))

    # Display results table
    table = Table(show_header=True, header_style="bold blue", box=None)
    table.add_column("Status", style="white", no_wrap=True, width=6)
    table.add_column("Check", style="cyan", no_wrap=True)
    table.add_column("Result", style="white")

    for check in checks:
        table.add_row(check.status, check.name, check.message)

    console.print(table)

    # Show suggestions for failed/warning checks
    has_failures, has_warnings = _print_check_suggestions(checks, verbose)

    # Print summary and exit with appropriate code
    _print_summary(has_failures, has_warnings)


def main() -> None:
    """Entry point for the doctor CLI command."""
    try:
        app()
    except KeyboardInterrupt:
        console.print("\n[red]Operation cancelled by user.[/red]")
        sys.exit(1)
    except Exception:
        console.print_exception()
        sys.exit(1)


if __name__ == "__main__":
    app()
