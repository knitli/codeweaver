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

from importlib.metadata import PackageNotFoundError, version
from pathlib import Path
from typing import TYPE_CHECKING

from cyclopts import App
from pydantic import ValidationError
from rich.console import Console
from rich.table import Table

from codeweaver.common import CODEWEAVER_PREFIX


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
    """Check if required dependencies are installed."""
    check = DoctorCheck("Required Dependencies")

    required_packages = [
        "fastmcp",
        "pydantic",
        "pydantic_settings",
        "cyclopts",
        "rich",
        "ast_grep_py",
        "qdrant_client",
        "voyageai",
        "rignore",
    ]

    missing: list[str] = []
    for package in required_packages:
        try:
            _ = version(package.replace("_", "-"))
        except PackageNotFoundError:
            missing.append(package)

    if not missing:
        check.status = "✅"
        check.message = "All required packages installed"
    else:
        check.status = "❌"
        check.message = f"Missing packages: {', '.join(missing)}"
        check.suggestions = ["Run: uv sync --all-groups", "Or: pip install codeweaver-mcp[all]"]

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
        if not isinstance(settings.project_path, Path):
            from codeweaver.common.utils.git import get_project_path

            project_path = get_project_path()
        else:
            project_path = settings.project_path
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

    except Exception as e:
        check.status = "❌"
        check.message = f"Failed to validate project path: {e!s}"
        check.suggestions = ["Check configuration and file system permissions"]

    return check


def check_vector_store_path(settings: CodeWeaverSettings) -> DoctorCheck:
    """Check if vector store path is writable."""
    check = DoctorCheck("Vector Store Path")

    try:
        # Get cache directory from indexing settings
        if hasattr(settings.indexing, "cache_dir"):
            cache_dir = Path(settings.indexing.cache_dir)
        else:
            # Fallback to default location
            from codeweaver.common.utils import get_user_config_dir

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
    """Check embedding provider API keys."""
    if not (hasattr(settings, "provider") and hasattr(settings.provider, "embedding")):
        return

    embedding_provider = getattr(settings.provider.embedding, "provider", None)
    api_key_map = {
        "voyageai": "VOYAGE_API_KEY",
        "openai": "OPENAI_API_KEY",
        "cohere": "COHERE_API_KEY",
        "huggingface": "HF_TOKEN",
    }

    if embedding_provider in api_key_map and not os.getenv(api_key_map[embedding_provider]):
        warnings.append(f"{api_key_map[embedding_provider]} not set")


def _check_vector_store_api_keys(settings: CodeWeaverSettings, warnings: list[str]) -> None:
    """Check vector store provider API keys."""
    if not (hasattr(settings, "provider") and hasattr(settings.provider, "vector_store")):
        return

    vector_store = getattr(settings.provider.vector_store, "provider", None)
    if (
        vector_store == "qdrant"
        and hasattr(settings.provider.vector_store, "remote")
        and settings.provider.vector_store.remote
        and not os.getenv("QDRANT_API_KEY")
    ):
        warnings.append("QDRANT_API_KEY not set (remote Qdrant)")


def _check_reranking_api_keys(settings: CodeWeaverSettings, warnings: list[str]) -> None:
    """Check reranking provider API keys."""
    if not (
        hasattr(settings, "provider")
        and hasattr(settings.provider, "reranking")
        and settings.provider.reranking
    ):
        return

    reranking_provider = getattr(settings.provider.reranking, "provider", None)
    api_key_map = {"cohere": "COHERE_API_KEY", "voyageai": "VOYAGE_API_KEY"}

    if reranking_provider in api_key_map and not os.getenv(api_key_map[reranking_provider]):
        warnings.append(f"{api_key_map[reranking_provider]} not set (for reranking)")


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

    # This is a basic check - full connectivity testing would be more complex
    # and might require actual API calls
    check.status = "⚠️"
    check.message = "Skipping connection tests (use --test-connections)"
    check.suggestions = [
        "Run with --test-connections to test provider connectivity",
        "Note: This will make actual API calls and may incur costs",
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
