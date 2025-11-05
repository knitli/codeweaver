# sourcery skip: no-complex-if-expressions
# sourcery skip: avoid-global-variables, no-complex-if-expressions
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Config-related CLI commands for CodeWeaver."""

from __future__ import annotations

import sys

from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import cyclopts

from cyclopts import App
from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table

from codeweaver.common import CODEWEAVER_PREFIX


if TYPE_CHECKING:
    from codeweaver.config.types import CodeWeaverSettingsDict
    from codeweaver.core.types.dictview import DictView

console = Console(markup=True, emoji=True)
app = App(
    "config",
    default_command="config",
    help="Manage and view your CodeWeaver config.",
    console=console,
)


@app.command(default_parameter="show")
def config(
    *,
    show: bool = False,
    project_path: Annotated[Path | None, cyclopts.Parameter(name=["--project", "-p"])] = None,
) -> None:
    """Manage CodeWeaver configuration."""
    from codeweaver.config.settings import get_settings_map
    from codeweaver.exceptions import CodeWeaverError

    try:
        settings = get_settings_map()
        if project_path:
            from codeweaver.config.settings import update_settings

            settings = update_settings(project_path=project_path)  # type: ignore

        if show:
            _show_config(settings)
        else:
            console.print("Use --show to display configuration")

    except CodeWeaverError as e:
        console.print(f"{CODEWEAVER_PREFIX} [red]Configuration Error: {e.message}[/red]")
        if e.suggestions:
            console.print(f"{CODEWEAVER_PREFIX} [yellow]Suggestions:[/yellow]")
            for suggestion in e.suggestions:
                console.print(f"  • {suggestion}")
        sys.exit(1)


def _show_config(settings: DictView[CodeWeaverSettingsDict]) -> None:
    """Display current configuration."""
    from codeweaver.core.types.sentinel import Unset

    console.print("[bold blue]CodeWeaver Configuration[/bold blue]\n")

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
        if settings["indexing"].get("only_index_on_command")
        and not isinstance(settings["indexing"].get("only_index_on_command"), Unset)
        else "✅",
    )
    table.add_row("Telemetry", "❌" if settings["telemetry"].get("disable_telemetry") else "✅")

    console.print(table)


@app.command
def init(
    output: Annotated[Path | None, cyclopts.Parameter(name=["--output", "-o"])] = None,
    force: Annotated[bool, cyclopts.Parameter(name=["--force", "-f"])] = False,
) -> None:
    """Interactive configuration wizard for first-time setup.

    Creates a new .codeweaver.toml configuration file with guided prompts.
    """
    from pydantic import ValidationError

    from codeweaver.config.settings import CodeWeaverSettings
    from codeweaver.exceptions import CodeWeaverError
    from codeweaver.providers.capabilities import PROVIDER_CAPABILITIES
    from codeweaver.providers.provider import Provider, ProviderKind

    console.print("\n[bold cyan]CodeWeaver Configuration Wizard[/bold cyan]\n")
    console.print("This wizard will help you create a configuration file for your project.")
    console.print("Press Ctrl+C at any time to cancel.\n")

    try:
        # 1. Project path
        default_path = str(Path.cwd())
        project_path_str = Prompt.ask(
            "[cyan]Project path[/cyan]",
            default=default_path,
        )
        project_path = Path(project_path_str).expanduser().resolve()

        if not project_path.exists():
            console.print(f"[red]✗[/red] Path does not exist: {project_path}")
            console.print(
                "[yellow]Please create the directory first or provide a valid path.[/yellow]"
            )
            sys.exit(1)

        if not project_path.is_dir():
            console.print(f"[red]✗[/red] Path is not a directory: {project_path}")
            sys.exit(1)

        # 2. Config file location
        config_path = output or project_path / ".codeweaver.toml"

        if config_path.exists() and not force:
            overwrite = Confirm.ask(
                f"[yellow]Configuration file already exists at {config_path}. Overwrite?[/yellow]",
                default=False,
            )
            if not overwrite:
                console.print("[yellow]Configuration cancelled.[/yellow]")
                sys.exit(0)

        # 3. Embedding provider selection
        console.print("\n[bold]Embedding Provider[/bold]")
        console.print("Choose a provider for generating code embeddings:")

        # Filter embedding providers
        embedding_providers = [
            (provider.value, provider)
            for provider, kinds in PROVIDER_CAPABILITIES.items()
            if ProviderKind.EMBEDDING in kinds
        ]

        # Show common options with descriptions
        console.print("  1. [cyan]voyage[/cyan]     - VoyageAI (recommended, requires API key)")
        console.print("  2. [cyan]openai[/cyan]     - OpenAI (requires API key)")
        console.print("  3. [cyan]fastembed[/cyan]  - FastEmbed (local, no API key needed)")
        console.print("  4. [cyan]cohere[/cyan]     - Cohere (requires API key)")
        console.print("  5. [dim]other[/dim]       - See all available providers")

        provider_choice = Prompt.ask(
            "\n[cyan]Select embedding provider[/cyan]",
            choices=[
                "1",
                "2",
                "3",
                "4",
                "5",
                "voyage",
                "openai",
                "fastembed",
                "cohere",
                "other",
            ],
            default="1",
        )

        # Map choices
        provider_map = {
            "1": "voyage",
            "2": "openai",
            "3": "fastembed",
            "4": "cohere",
            "voyage": "voyage",
            "openai": "openai",
            "fastembed": "fastembed",
            "cohere": "cohere",
        }

        if provider_choice in ("5", "other"):
            console.print("\n[bold]All embedding providers:[/bold]")
            for idx, (name, _) in enumerate(embedding_providers, 1):
                console.print(f"  {idx}. {name}")

            other_choice = Prompt.ask(
                "\n[cyan]Enter provider name[/cyan]",
                choices=[name for name, _ in embedding_providers],
            )
            embedding_provider_name = other_choice
        else:
            embedding_provider_name = provider_map[provider_choice]

        # 4. API key if needed (not for fastembed or local models)
        api_key = None
        if embedding_provider_name not in ("fastembed", "sentence-transformers"):
            needs_key = Confirm.ask(
                f"\n[cyan]Does your {embedding_provider_name} setup require an API key?[/cyan]",
                default=True,
            )

            if needs_key:
                api_key = Prompt.ask(
                    f"[cyan]Enter {embedding_provider_name.upper()} API key[/cyan]",
                    password=True,
                )

                if not api_key or api_key.strip() == "":
                    console.print(
                        "[yellow]⚠[/yellow]  No API key provided. You'll need to set it via environment variable."
                    )
                    api_key = None

        # 5. Sparse embedding
        console.print("\n[bold]Sparse Embedding (Optional)[/bold]")
        console.print(
            "Sparse embeddings complement dense embeddings for better search accuracy."
        )

        use_sparse = Confirm.ask(
            "[cyan]Enable sparse embedding?[/cyan]",
            default=True,
        )

        sparse_provider_name = None
        if use_sparse:
            # Check if current provider supports sparse
            current_provider = Provider.from_string(embedding_provider_name)
            if current_provider and current_provider.is_sparse_provider():
                sparse_provider_name = embedding_provider_name
                console.print(
                    f"[green]✓[/green] Using {embedding_provider_name} for sparse embeddings"
                )
            else:
                console.print(
                    f"[yellow]⚠[/yellow]  {embedding_provider_name} doesn't support sparse embeddings."
                )
                console.print("Using fastembed (local, recommended) for sparse embeddings.")
                sparse_provider_name = "fastembed"

        # 6. Reranking provider
        console.print("\n[bold]Reranking (Optional)[/bold]")
        console.print("Reranking improves search result quality by re-scoring results.")

        use_reranking = Confirm.ask(
            "[cyan]Enable reranking?[/cyan]",
            default=False,
        )

        reranking_provider_name = None
        reranking_api_key = None

        if use_reranking:
            console.print("\n[bold]Reranking providers:[/bold]")
            console.print("  1. [cyan]voyage[/cyan]   - VoyageAI (requires API key)")
            console.print("  2. [cyan]cohere[/cyan]   - Cohere (requires API key)")
            console.print("  3. [cyan]fastembed[/cyan] - FastEmbed (local)")
            console.print("  4. [dim]skip[/dim]      - Skip reranking")

            rerank_choice = Prompt.ask(
                "\n[cyan]Select reranking provider[/cyan]",
                choices=["1", "2", "3", "4", "voyage", "cohere", "fastembed", "skip"],
                default="4",
            )

            rerank_map = {
                "1": "voyage",
                "2": "cohere",
                "3": "fastembed",
                "4": None,
                "voyage": "voyage",
                "cohere": "cohere",
                "fastembed": "fastembed",
                "skip": None,
            }

            reranking_provider_name = rerank_map[rerank_choice]

            if reranking_provider_name and reranking_provider_name != "fastembed":
                # Check if we can reuse the embedding API key
                if reranking_provider_name == embedding_provider_name and api_key:
                    console.print(
                        f"[green]✓[/green] Reusing {embedding_provider_name} API key for reranking"
                    )
                    reranking_api_key = api_key
                else:
                    reranking_api_key = Prompt.ask(
                        f"[cyan]Enter {reranking_provider_name.upper()} API key for reranking[/cyan]",
                        password=True,
                    )

                    if not reranking_api_key or reranking_api_key.strip() == "":
                        console.print(
                            "[yellow]⚠[/yellow]  No API key provided. You'll need to set it via environment variable."
                        )
                        reranking_api_key = None

        # 7. Vector store location
        console.print("\n[bold]Vector Store[/bold]")
        default_vector_path = str(project_path / ".codeweaver" / "qdrant")
        vector_path_str = Prompt.ask(
            "[cyan]Vector store location[/cyan]",
            default=default_vector_path,
        )
        vector_path = Path(vector_path_str).expanduser().resolve()

        # Generate configuration
        console.print("\n[bold cyan]Generating configuration...[/bold cyan]\n")

        # Build settings dict for customization
        settings_data: dict = {
            "project_path": str(project_path),
            "provider": {
                "embedding": {
                    "provider": embedding_provider_name,
                    "enabled": True,
                },
            },
        }

        # Add API key if provided
        if api_key:
            settings_data["provider"]["embedding"]["api_key"] = api_key

        # Add sparse embedding
        if sparse_provider_name:
            settings_data["provider"]["sparse_embedding"] = {
                "provider": sparse_provider_name,
                "enabled": True,
            }

        # Add reranking
        if reranking_provider_name:
            settings_data["provider"]["reranking"] = {
                "provider": reranking_provider_name,
                "enabled": True,
            }
            if reranking_api_key:
                settings_data["provider"]["reranking"]["api_key"] = reranking_api_key

        # Add vector store configuration
        settings_data["provider"]["vector_store"] = {
            "provider": "qdrant",
            "enabled": True,
            "client_options": {
                "path": str(vector_path),
            },
        }

        # Create settings object with custom values
        try:
            settings = CodeWeaverSettings(**settings_data)
            settings.save_to_file(config_path)
        except ValidationError as e:
            console.print(f"[red]✗[/red] Configuration validation failed: {e}")
            sys.exit(1)

        # Success message
        console.print(f"[green]✓[/green] Configuration saved to [cyan]{config_path}[/cyan]\n")

        # Display next steps
        console.print("[bold]Next Steps:[/bold]")
        console.print("  1. Review your configuration: [cyan]codeweaver config --show[/cyan]")
        console.print("  2. Index your codebase: [cyan]codeweaver index[/cyan]")
        console.print("  3. Start the MCP server: [cyan]codeweaver serve[/cyan]")

        # Show environment variable hints if API keys weren't provided
        if (
            embedding_provider_name not in ("fastembed", "sentence-transformers")
            and not api_key
        ):
            console.print(
                f"\n[yellow]⚠[/yellow]  Don't forget to set your {embedding_provider_name.upper()}_API_KEY environment variable!"
            )

        if (
            reranking_provider_name
            and reranking_provider_name != "fastembed"
            and not reranking_api_key
        ):
            console.print(
                f"[yellow]⚠[/yellow]  Don't forget to set your {reranking_provider_name.upper()}_API_KEY environment variable!"
            )

    except CodeWeaverError as e:
        console.print(f"{CODEWEAVER_PREFIX} [red]Configuration Error: {e.message}[/red]")
        if e.suggestions:
            console.print(f"{CODEWEAVER_PREFIX} [yellow]Suggestions:[/yellow]")
            for suggestion in e.suggestions:
                console.print(f"  • {suggestion}")
        sys.exit(1)
    except KeyboardInterrupt:
        console.print("\n[yellow]Configuration cancelled by user.[/yellow]")
        sys.exit(0)
    except Exception as e:
        console.print(f"[red]✗[/red] An unexpected error occurred: {e}")
        sys.exit(1)


def main() -> None:
    """Entry point for the config CLI command."""
    try:
        app()
    except KeyboardInterrupt:
        console.print("\n[red]Operation cancelled by user.[/red]")
        sys.exit(1)
    except Exception as e:
        console.print(f"[red]An unexpected error occurred: {e}[/red]")
        sys.exit(1)


if __name__ == "__main__":
    app()
