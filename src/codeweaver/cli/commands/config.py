# sourcery skip: avoid-global-variables, name-type-suffix, no-complex-if-expressions
# sourcery skip: avoid-global-variables, no-complex-if-expressions
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Config-related CLI commands for CodeWeaver."""

from __future__ import annotations

from pathlib import Path
from typing import TYPE_CHECKING, Annotated, Literal

import cyclopts

from cyclopts import App
from pydantic import FilePath
from rich.table import Table

from codeweaver.cli.ui import CLIErrorHandler, StatusDisplay, get_display
from codeweaver.core.config.settings_type import CodeWeaverSettingsType
from codeweaver.core.config.types import CodeWeaverSettingsDict
from codeweaver.core.dependencies import ResolvedProjectPathDep, SettingsDep
from codeweaver.core.di import INJECTED
from codeweaver.core.utils import detect_root_package, is_codeweaver_config_path
from codeweaver.engine import ConfigChangeAnalyzerDep
from codeweaver.providers import ProviderSettings, ProviderSettingsDep


if TYPE_CHECKING:
    from codeweaver.core import DictView

display: StatusDisplay = get_display()
app = App("config", help="Manage and view your CodeWeaver config.", console=display.console)


def _project_path(project_path: ResolvedProjectPathDep) -> Path:
    return project_path


def _settings(settings: SettingsDep) -> CodeWeaverSettingsType:
    return settings


@app.default()
async def config(
    *,
    project_path: Annotated[
        Path | None, cyclopts.Parameter(name=["--project", "-p"], help="Path to project directory")
    ] = None,
    config_file: Annotated[
        FilePath | None,
        cyclopts.Parameter(
            name=["--config-file", "-c"], help="Path to a specific config file to use"
        ),
    ] = None,
    verbose: Annotated[
        bool, cyclopts.Parameter(name=["--verbose", "-v"], help="Enable verbose logging")
    ] = False,
    debug: Annotated[
        bool, cyclopts.Parameter(name=["--debug", "-d"], help="Enable debug logging")
    ] = False,
) -> None:
    """Manage CodeWeaver configuration."""
    from codeweaver.core import CodeWeaverError

    error_handler = CLIErrorHandler(display, verbose=verbose, debug=debug)
    if config_file and not is_codeweaver_config_path(config_file):
        try:
            from codeweaver.core.dependencies import bootstrap_settings

            settings = await bootstrap_settings(config_file=config_file)
        except Exception as e:
            error_handler.handle_error(e, "Configuration", exit_code=1)

        settings.project_path = project_path or settings.project_path

    else:
        try:
            settings = _settings()  # ty:ignore[missing-argument]
            settings.project_path = project_path or settings.project_path
        except CodeWeaverError as e:
            error_handler.handle_error(e, "Configuration", exit_code=1)
        except Exception as e:
            error_handler.handle_error(e, "Configuration", exit_code=1)
    _show_config(settings.view())


def _show_config(settings: DictView[CodeWeaverSettingsDict]) -> None:
    """Display current configuration."""
    from codeweaver.core import Unset

    display.print_command_header("CodeWeaver Configuration")

    table = Table(show_header=True, header_style="bold blue")
    table.add_column("Setting", style="cyan", no_wrap=True)
    table.add_column("Value", style="white")

    # Core settings
    table.add_row("Project Path", str(settings["project_path"]))
    table.add_row("Project Name", settings["project_name"] or "auto-detected")
    table.add_row("Token Limit", str(settings["token_limit"]))
    table.add_row("Max File Size", f"{settings['max_file_size']:,} bytes")
    table.add_row("Max Results", str(settings["max_results"]))

    # Feature flags
    table.add_row(
        "Background Indexing",
        "❌"
        if settings["indexer"].get("only_index_on_command")
        and not isinstance(settings["indexer"].get("only_index_on_command"), Unset)
        else "✅",
    )
    table.add_row("Telemetry", "❌" if settings["telemetry"].get("disable_telemetry") else "✅")

    display.print_table(table)

    # Provider configuration
    if provider_settings := settings.get("provider"):
        _show_provider_config(provider_settings)


def _normalize_provider_configs(
    configs: ProviderSettings | tuple[ProviderSettings, ...],
    field: Literal["vector_store", "reranking", "embedding", "sparse_embedding", "agent", "data"],
) -> tuple[ProviderSettings, ...]:
    """Normalize provider configs to a tuple of valid config dicts."""
    from codeweaver.core.types import Unset

    if isinstance(configs, tuple):
        return configs
    if configs is None or isinstance(configs, Unset):
        if detect_root_package() == "core":
            return ()
        from codeweaver.providers.config.profiles import ProviderProfile

        profile = ProviderProfile.RECOMMENDED
        return getattr(profile.value, field, ())
    return (configs,)


def _build_provider_details(config) -> str:
    """Build a human-readable details string for a provider config."""
    details: list[str] = []

    if (model_settings := config.get("model_settings")) and (model := model_settings.get("model")):
        details.append(f"Model: {model}")

    if provider_settings_dict := config.get("provider_settings"):
        if url := provider_settings_dict.get("url"):
            url_display = url if len(url) < 50 else f"{url[:47]}..."
            details.append(f"URL: {url_display}")
        if collection := provider_settings_dict.get("collection_name"):
            details.append(f"Collection: {collection}")
        if path := provider_settings_dict.get("persistence_path"):
            details.append(f"Path: {path}")

    return " | ".join(details) if details else "Default settings"


def _show_provider_config(provider_settings: ProviderSettingsDep = INJECTED) -> None:
    """Display provider configuration details."""
    from codeweaver.core import Unset

    display.print_section("Provider Configuration")

    if not provider_settings or isinstance(provider_settings, Unset):
        display.print_warning("No providers configured")
        return

    valid_categories = (
        "data",
        "embedding",
        "sparse_embedding",
        "reranking",
        "vector_store",
        "agent",
    )

    for category, configs in provider_settings.items():
        if category not in valid_categories or not configs or isinstance(configs, Unset):
            continue

        config_list = _normalize_provider_configs(configs, field=category)  # ty:ignore[invalid-argument-type]
        table = Table(
            title=f"{category.replace('_', ' ').title()}",
            show_header=True,
            header_style="bold cyan",
        )
        table.add_column("Provider", style="cyan")
        table.add_column("Status", style="white", no_wrap=True)
        table.add_column("Details", style="white")

        for config in config_list:
            if config is None or isinstance(config, Unset):
                continue

            provider = config.get("provider")
            enabled = config.get("enabled", True)
            status = "✅ Enabled" if enabled else "⚠️ Disabled"
            details_str = _build_provider_details(config)

            table.add_row(
                provider.as_title if hasattr(provider, "as_title") else str(provider),
                status,
                details_str,
            )

        display.print_table(table)
        display.console.print()


@app.command()
async def set_config(
    key: str,
    value: str,
    force: Annotated[
        bool,
        cyclopts.Parameter(
            name=["--force", "-f"], help="Skip validation and apply change immediately"
        ),
    ] = False,
    config_analyzer: ConfigChangeAnalyzerDep = INJECTED,
    settings: SettingsDep = INJECTED,
) -> None:
    """Set a configuration value with proactive validation.

    Validates embedding configuration changes before applying them to prevent
    incompatible index states.

    Args:
        key: Configuration key (e.g., "provider.embedding.dimension")
        value: New value for the key
        force: Skip validation and apply change immediately
        config_analyzer: DI-injected configuration analyzer
        settings: DI-injected settings service
    """
    from rich.prompt import Confirm

    display.print_command_header("Set Configuration")

    # Validate change using injected analyzer
    if not force and key.startswith("provider.embedding"):
        try:
            analysis = await config_analyzer.validate_config_change(key, value)

            if analysis:
                from codeweaver.engine.managers.checkpoint_manager import ChangeImpact

                display.console.print()
                match analysis.impact:
                    case ChangeImpact.BREAKING:
                        display.print_error("Configuration change is incompatible!")
                        display.console.print(f"  {analysis.accuracy_impact}")
                        display.console.print()
                        display.console.print("Options:")
                        for i, rec in enumerate(analysis.recommendations, 1):
                            display.console.print(f"  {i}. {rec}")
                        if not Confirm.ask("Continue anyway?"):
                            display.print_warning("Configuration change cancelled")
                            return

                    case ChangeImpact.QUANTIZABLE | ChangeImpact.TRANSFORMABLE:
                        display.print_warning("Transformation available")
                        display.console.print(f"  Accuracy impact: {analysis.accuracy_impact}")
                        display.console.print(
                            f"  Time estimate: ~{analysis.estimated_time.total_seconds():.0f}s"
                        )
                        display.console.print()
                        display.console.print("Recommendations:")
                        for i, rec in enumerate(analysis.recommendations, 1):
                            display.console.print(f"  {i}. {rec}")

                    case _:
                        display.print_success("Configuration change is compatible")

        except Exception as e:
            display.print_warning(f"Could not validate change: {e}")
            if not force and not Confirm.ask("Continue without validation?"):
                display.print_warning("Configuration change cancelled")
                return

    # Apply change using settings service
    try:
        # Note: Settings update mechanism needs to be implemented
        # For now, this is a placeholder for the actual implementation
        # Options:
        # 1. Use settings.model_copy(update={key: value})
        # 2. Implement a .set() method on Settings
        # 3. Write directly to config file and reload
        display.print_warning("Settings update not yet implemented")
        display.console.print(f"Would update: {key} = {value}")
        # TODO: Implement actual settings update mechanism
    except Exception as e:
        display.print_error(f"Failed to update configuration: {e}")
        raise


def main() -> None:
    """Main entry point for config CLI."""
    display_instance = StatusDisplay()
    error_handler = CLIErrorHandler(display_instance, verbose=True, debug=True)

    try:
        app()
    except KeyboardInterrupt:
        display_instance.print_warning("Operation cancelled by user")
    except Exception as e:
        error_handler.handle_error(e, "CLI", exit_code=1)


if __name__ == "__main__":
    main()

__all__ = ()
