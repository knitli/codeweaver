# sourcery skip: avoid-global-variables, name-type-suffix, no-complex-if-expressions
# sourcery skip: avoid-global-variables, no-complex-if-expressions
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""Config-related CLI commands for CodeWeaver."""

from __future__ import annotations

import sys

from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Annotated

import cyclopts

from cyclopts import App
from rich.console import Console
from rich.prompt import Confirm, Prompt
from rich.table import Table

from codeweaver.common import CODEWEAVER_PREFIX
from codeweaver.common.utils.git import get_project_path, is_git_dir
from codeweaver.common.utils.utils import get_user_config_dir
from codeweaver.providers.provider import Provider


if TYPE_CHECKING:
    from codeweaver.config.types import CodeWeaverSettingsDict
    from codeweaver.core.types.dictview import DictView

console = Console(markup=True, emoji=True)
app = App(
    "config",
    help="Manage and view your CodeWeaver config.",
    console=console,
)


class ConfigProfile(str, Enum):
    """Configuration profiles for quick setup."""

    RECOMMENDED = "recommended"
    LOCAL_ONLY = "local-only"
    MINIMAL = "minimal"


def _show_secrets_manager_info(console: Console) -> None:
    """Show information about secrets manager integration."""
    console.print("\n[bold]💡 Advanced: Secrets Manager Integration[/bold]\n")

    console.print("CodeWeaver supports loading secrets from cloud providers:")
    console.print("  • [cyan]AWS Secrets Manager[/cyan] - Set AWS_SECRETS_MANAGER_SECRET_ID")
    console.print("  • [cyan]Azure Key Vault[/cyan] - Set AZURE_KEY_VAULT_URL")
    console.print("  • [cyan]Google Secret Manager[/cyan] - Set GOOGLE_SECRET_MANAGER_PROJECT_ID\n")

    console.print("[dim]Secrets managers are checked automatically if environment variables are set.[/dim]")
    console.print("[dim]They take precedence over .env files and config files.[/dim]")
    console.print("[dim]See docs: https://github.com/knitli/codeweaver-mcp#secrets-management[/dim]")
    console.print()


def _show_sparse_embedding_info(console: Console) -> None:
    """Show sparse embedding capabilities and limitations."""
    console.print("\n[bold]📊 Sparse Embeddings for Hybrid Search:[/bold]\n")

    console.print("[green]Benefits:[/green]")
    console.print("  • Improved keyword matching (technical terms, variable names)")
    console.print("  • Better recall for exact phrase matches")
    console.print("  • Complements dense embeddings for hybrid search")
    console.print("  • Local execution (no API costs)\n")

    console.print("[yellow]Important Limitations:[/yellow]")
    console.print("  • [bold]Only 2 providers support sparse embeddings:[/bold]")
    console.print("    - fastembed (prithivida/Splade-PP_en_v2)")
    console.print("    - sentence-transformers (specific models only)")
    console.print("  • [bold]VoyageAI, OpenAI, Cohere do NOT support sparse[/bold]")
    console.print("  • If dense provider doesn't support sparse, use fastembed for sparse\n")

    console.print("[cyan]Recommended Setup:[/cyan]")
    console.print("  • Dense: voyage-code-3 (VoyageAI) - High quality")
    console.print("  • Sparse: prithivida/Splade-PP_en_v2 (FastEmbed) - Local, fast")
    console.print("  • Result: Best of both worlds (semantic + keyword matching)\n")


@app.default
def config(
    *,
    show: bool = True,
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
    quick: Annotated[bool, cyclopts.Parameter(name=["--quick", "-q"])] = False,
    profile: Annotated[ConfigProfile | None, cyclopts.Parameter(name=["--profile"])] = None,
    user: Annotated[bool, cyclopts.Parameter(name=["--user"])] = False,
    local: Annotated[bool, cyclopts.Parameter(name=["--local"])] = False,
) -> None:
    """Interactive configuration wizard for first-time setup.

    [DEPRECATED] Use 'codeweaver init' instead for unified config + MCP setup.
    This command will be removed in v0.2.

    Creates a new .codeweaver.toml configuration file with guided prompts.

    Quick start: codeweaver config init --quick
    With profile: codeweaver config init --profile local-only
    User config: codeweaver config init --user
    """
    console.print(
        "[yellow]⚠ NOTICE: 'codeweaver config init' is deprecated. "
        "Use 'codeweaver init' instead.[/yellow]"
    )
    console.print(
        "[yellow]   The unified 'init' command handles both config creation and MCP client setup.[/yellow]\n"
    )

    from pydantic import SecretStr, ValidationError

    from codeweaver.common.registry import get_provider_registry
    from codeweaver.config.providers import (
        EmbeddingModelSettings,
        EmbeddingProviderSettings,
        QdrantConfig,
        RerankingModelSettings,
        RerankingProviderSettings,
        SparseEmbeddingModelSettings,
        SparseEmbeddingProviderSettings,
        VectorStoreProviderSettings,
    )
    from codeweaver.config.settings import CodeWeaverSettings
    from codeweaver.exceptions import CodeWeaverError
    from codeweaver.providers.provider import ProviderKind

    # Handle quick setup flag
    if quick:
        _quick_setup(output, force, user, local)
        return

    # Handle profile-based setup
    if profile:
        _profile_setup(profile, output, force, user, local)
        return

    console.print("\n{CODEWEAVER_PREFIX} [bold cyan]CodeWeaver Configuration Wizard[/bold cyan]\n")
    console.print("This wizard will help you create a configuration file for your project.")
    console.print("Press Ctrl+C at any time to cancel.\n")

    try:
        # 1. Project path - use git helper
        default_path = str(get_project_path())
        project_path_str = Prompt.ask("[cyan]Project path[/cyan]", default=default_path)
        project_path = Path(project_path_str).expanduser().resolve()

        # Validate path exists and is directory
        if not project_path.exists():
            console.print(f"[red]✗[/red] Path does not exist: {project_path}")
            console.print(
                "[yellow]Please create the directory first or provide a valid path.[/yellow]"
            )
            sys.exit(1)

        if not project_path.is_dir():
            console.print(f"[red]✗[/red] Path is not a directory: {project_path}")
            sys.exit(1)

        # Check if git repository using helper
        if is_git_dir(project_path):
            console.print(f"[green]✓[/green] Git repository detected at {project_path}")

        # 2. Config file location - respect user/local flags
        config_path = _get_config_path(output, user, local, project_path)

        if config_path.exists() and not force:
            overwrite = Confirm.ask(
                f"[yellow]Configuration file already exists at {config_path}. Overwrite?[/yellow]",
                default=False,
            )
            if not overwrite:
                console.print("[yellow]Configuration cancelled.[/yellow]")
                sys.exit(0)

        # 3. Embedding provider selection - USE REGISTRY
        console.print("\n[bold]Embedding Provider[/bold]")
        console.print("Choose a provider for generating code embeddings:")

        registry = get_provider_registry()

        # Get all available embedding providers from registry
        embedding_providers = [
            provider
            for provider in registry.list_providers(ProviderKind.EMBEDDING)
            if registry.is_provider_available(provider, ProviderKind.EMBEDDING)
        ]

        # Show common options with availability info
        common_providers = {
            "voyage": ("VoyageAI (recommended, requires API key)", Provider.VOYAGE),
            "openai": ("OpenAI (requires API key)", Provider.OPENAI),
            "fastembed": ("FastEmbed (local, no API key needed)", Provider.FASTEMBED),
            "cohere": ("Cohere (requires API key)", Provider.COHERE),
        }

        console.print("\n[bold]Common Providers:[/bold]")
        available_common = {}
        idx = 1
        for key, (desc, provider_enum) in common_providers.items():
            if provider_enum in embedding_providers:
                console.print(f"  {idx}. [cyan]{key}[/cyan] - {desc}")
                available_common[str(idx)] = key
                available_common[key] = key
                idx += 1

        console.print(
            f"  {idx}. [dim]other[/dim] - See all {len(embedding_providers)} available providers"
        )
        available_common[str(idx)] = "other"
        available_common["other"] = "other"

        provider_choice = Prompt.ask(
            "\n[cyan]Select embedding provider[/cyan]",
            choices=list(available_common.keys()),
            default="1",
        )

        if available_common[provider_choice] == "other":
            console.print("\n[bold]All embedding providers:[/bold]")
            for idx, provider in enumerate(embedding_providers, 1):
                # Check if provider needs API key
                is_local = provider in (Provider.FASTEMBED, Provider.SENTENCE_TRANSFORMERS)
                api_note = "local, no API key" if is_local else "requires API key"
                console.print(f"  {idx}. [cyan]{provider.value}[/cyan] - {api_note}")

            other_choice = Prompt.ask(
                "\n[cyan]Enter provider name[/cyan]",
                choices=[p.value for p in embedding_providers],
            )
            embedding_provider_name = other_choice
        else:
            embedding_provider_name = available_common[provider_choice]

        # 4. API key if needed (not for fastembed or local models)
        api_key = None
        if embedding_provider_name not in ("fastembed", "sentence-transformers"):
            needs_key = Confirm.ask(
                f"\n[cyan]Does your {embedding_provider_name} setup require an API key?[/cyan]",
                default=True,
            )

            if needs_key:
                api_key = Prompt.ask(
                    f"[cyan]Enter {embedding_provider_name.upper()} API key[/cyan]", password=True
                )

                if not api_key or api_key.strip() == "":
                    console.print(
                        "[yellow]⚠[/yellow]  No API key provided. You'll need to set it via environment variable."
                    )
                    api_key = None

        # 5. Sparse embedding with enhanced guidance
        _show_sparse_embedding_info(console)

        current_provider = Provider.from_string(embedding_provider_name)
        if current_provider in (Provider.FASTEMBED, Provider.SENTENCE_TRANSFORMERS):
            console.print(
                f"[cyan]Note:[/cyan] {embedding_provider_name} supports both dense and sparse embeddings"
            )

        use_sparse = Confirm.ask("\n[cyan]Enable sparse embedding?[/cyan]", default=True)

        sparse_provider_name = None
        if use_sparse:
            # Get sparse providers from registry
            sparse_providers = [
                provider
                for provider in registry.list_providers(ProviderKind.SPARSE_EMBEDDING)
                if registry.is_provider_available(provider, ProviderKind.SPARSE_EMBEDDING)
            ]

            # Check if current provider supports sparse
            current_provider = Provider.from_string(embedding_provider_name)
            if current_provider and current_provider in sparse_providers:
                sparse_provider_name = embedding_provider_name
                console.print(
                    f"[green]✓[/green] Using {embedding_provider_name} for sparse embeddings"
                )
            else:
                console.print(
                    f"[yellow]⚠[/yellow]  {embedding_provider_name} doesn't support sparse embeddings."
                )
                if Provider.FASTEMBED in sparse_providers:
                    console.print("Using fastembed (local, recommended) for sparse embeddings.")
                    sparse_provider_name = "fastembed"
                elif sparse_providers:
                    console.print(f"Using {sparse_providers[0].value} for sparse embeddings.")
                    sparse_provider_name = sparse_providers[0].value

        # 6. Reranking provider
        console.print("\n[bold]Reranking (Optional)[/bold]")
        console.print("Reranking improves search result quality by re-scoring results.")

        use_reranking = Confirm.ask("[cyan]Enable reranking?[/cyan]", default=False)

        reranking_provider_name = None
        reranking_api_key = None

        if use_reranking:
            # Get reranking providers from registry
            reranking_providers = [
                provider
                for provider in registry.list_providers(ProviderKind.RERANKING)
                if registry.is_provider_available(provider, ProviderKind.RERANKING)
            ]

            console.print("\n[bold]Reranking providers:[/bold]")
            common_rerank = []
            if Provider.VOYAGE in reranking_providers:
                common_rerank.append(("voyage", "VoyageAI (requires API key)"))
            if Provider.COHERE in reranking_providers:
                common_rerank.append(("cohere", "Cohere (requires API key)"))
            if Provider.FASTEMBED in reranking_providers:
                common_rerank.append(("fastembed", "FastEmbed (local)"))

            for idx, (key, desc) in enumerate(common_rerank, 1):
                console.print(f"  {idx}. [cyan]{key}[/cyan] - {desc}")
            console.print(f"  {len(common_rerank) + 1}. [dim]skip[/dim] - Skip reranking")

            rerank_choice = Prompt.ask(
                "\n[cyan]Select reranking provider[/cyan]",
                choices=[str(i) for i in range(1, len(common_rerank) + 2)]
                + [k for k, _ in common_rerank]
                + ["skip"],
                default=str(len(common_rerank) + 1),
            )

            if rerank_choice == "skip" or rerank_choice == str(len(common_rerank) + 1):
                reranking_provider_name = None
            else:
                try:
                    idx = int(rerank_choice) - 1
                    reranking_provider_name = common_rerank[idx][0]
                except (ValueError, IndexError):
                    reranking_provider_name = rerank_choice

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

        # 7. Vector store location with cloud recommendations
        console.print("\n[bold]Vector Store Selection:[/bold]\n")
        console.print("Choose vector database for storing code embeddings:\n")

        console.print("  1. [cyan]qdrant-local[/cyan] - Local Qdrant (disk persistence)")
        console.print("     Best for: Development, small projects (<50k files)")
        console.print("     Pros: No API keys, fast, offline-capable")
        console.print("     Cons: Limited to single machine\n")

        console.print("  2. [cyan]qdrant-cloud[/cyan] - Qdrant Cloud (recommended for production)")
        console.print("     Best for: Production, large projects, team collaboration")
        console.print("     Pros: Managed service, automatic backups, high availability")
        console.print("     Cons: Requires API key, monthly cost")
        console.print("     Setup: https://cloud.qdrant.io (free tier available)\n")

        console.print("  3. [cyan]qdrant-docker[/cyan] - Self-hosted Qdrant (Docker)")
        console.print("     Best for: Production on-premises, custom deployments")
        console.print("     Pros: Full control, scalable, no vendor lock-in")
        console.print("     Cons: Requires Docker, manual management\n")

        vector_choice = Prompt.ask("Select vector store", choices=["1", "2", "3"], default="1")

        vector_path = None
        vector_url = None
        vector_api_key = None

        match vector_choice:
            case "1":
                default_vector_path = str(project_path / ".codeweaver" / "qdrant")
                vector_path_str = Prompt.ask(
                    "[cyan]Vector store location[/cyan]", default=default_vector_path
                )
                vector_path = Path(vector_path_str).expanduser().resolve()

            case "2":
                console.print("\n[bold]Qdrant Cloud Setup:[/bold]")
                console.print("1. Sign up: https://cloud.qdrant.io")
                console.print("2. Create cluster (free tier: 1GB)")
                console.print("3. Get API key from cluster settings\n")

                vector_url = Prompt.ask("Qdrant Cloud URL", default="https://xyz.cloud.qdrant.io")
                vector_api_key = Prompt.ask("Qdrant API key", password=True)

                console.print("\n[yellow]⚠[/yellow] Set QDRANT_API_KEY environment variable:")
                console.print(f"  export QDRANT_API_KEY='{vector_api_key}'\n")

            case "3":
                console.print("\n[bold]Qdrant Docker Setup:[/bold]")
                console.print("Run: docker run -p 6333:6333 qdrant/qdrant\n")

                host = Prompt.ask("Qdrant host", default="localhost")
                port = Prompt.ask("Qdrant port", default="6333")

                vector_url = f"http://{host}:{port}"

        # Generate configuration using pydantic-settings
        console.print("\n[bold cyan]Generating configuration...[/bold cyan]\n")

        # Build provider settings using proper TypedDict structures
        embedding_model_settings: EmbeddingModelSettings = {
            "model": f"{embedding_provider_name}:default"
        }

        embedding_provider_settings: EmbeddingProviderSettings = {
            "provider": Provider.from_string(embedding_provider_name),
            "enabled": True,
            "model_settings": embedding_model_settings,
        }

        if api_key:
            embedding_provider_settings["api_key"] = SecretStr(api_key)

        provider_settings_tuple: tuple[EmbeddingProviderSettings, ...] = (
            embedding_provider_settings,
        )

        # Build sparse embedding settings if enabled
        sparse_settings_tuple: tuple[SparseEmbeddingProviderSettings, ...] | None = None
        if sparse_provider_name:
            sparse_model_settings: SparseEmbeddingModelSettings = {
                "model": f"{sparse_provider_name}:default"
            }
            sparse_provider_settings: SparseEmbeddingProviderSettings = {
                "provider": Provider.from_string(sparse_provider_name),
                "enabled": True,
                "model_settings": sparse_model_settings,
            }
            sparse_settings_tuple = (sparse_provider_settings,)

        # Build reranking settings if enabled
        reranking_settings_tuple: tuple[RerankingProviderSettings, ...] | None = None
        if reranking_provider_name:
            reranking_model_settings: RerankingModelSettings = {
                "model": f"{reranking_provider_name}:default"
            }
            reranking_provider_settings: RerankingProviderSettings = {
                "provider": Provider.from_string(reranking_provider_name),
                "enabled": True,
                "model_settings": reranking_model_settings,
            }
            if reranking_api_key:
                reranking_provider_settings["api_key"] = SecretStr(reranking_api_key)
            reranking_settings_tuple = (reranking_provider_settings,)

        # Build vector store settings based on deployment type
        if vector_url:
            # Cloud or Docker deployment
            qdrant_config: QdrantConfig = {"client_options": {"url": vector_url}}
            if vector_api_key:
                qdrant_config["client_options"]["api_key"] = vector_api_key
        else:
            # Local deployment
            qdrant_config: QdrantConfig = {"client_options": {"path": str(vector_path)}}

        vector_store_settings: VectorStoreProviderSettings = {
            "provider": Provider.QDRANT,
            "enabled": True,
            "provider_settings": qdrant_config,
        }
        vector_settings_tuple: tuple[VectorStoreProviderSettings, ...] = (
            vector_store_settings,
        )

        # Create settings object - let pydantic-settings handle precedence
        # pydantic-settings will merge with:
        # 1. Env vars (CODEWEAVER_PROJECT_PATH, VOYAGE_API_KEY, etc.)
        # 2. .env file
        # 3. Secrets managers (if configured)
        # 4. Existing config files
        try:
            settings = CodeWeaverSettings(
                project_path=project_path,
                provider={
                    "embedding": provider_settings_tuple,
                    "sparse_embedding": sparse_settings_tuple,
                    "reranking": reranking_settings_tuple,
                    "vector": vector_settings_tuple,
                },
            )

            # Save to config file
            # Only explicit values are saved, runtime will merge with env vars/secrets
            settings.save_to_file(config_path)

        except ValidationError as e:
            console.print(f"[red]✗[/red] Configuration validation failed: {e}")
            sys.exit(1)

        # Success message
        console.print(f"[green]✓[/green] Configuration saved to [cyan]{config_path}[/cyan]\n")

        # Show secrets manager info
        _show_secrets_manager_info(console)

        # Display next steps
        console.print("[bold]Next Steps:[/bold]")
        console.print("  1. Review your configuration: [cyan]codeweaver config --show[/cyan]")
        console.print("  2. Index your codebase: [cyan]codeweaver index[/cyan]")
        console.print("  3. Start the MCP server: [cyan]codeweaver serve[/cyan]")

        # Show environment variable hints using Provider.other_env_vars
        if embedding_provider_name not in ("fastembed", "sentence-transformers") and not api_key:
            provider = Provider.from_string(embedding_provider_name)
            if provider and (env_vars_list := provider.other_env_vars):
                console.print(f"\n[yellow]⚠[/yellow]  [bold]Environment variables for {embedding_provider_name}:[/bold]")
                for env_vars in env_vars_list:
                    if "note" in env_vars:
                        console.print(f"  [dim]{env_vars['note']}[/dim]")
                    if "api_key" in env_vars:
                        api_key_info = env_vars["api_key"]
                        console.print(f"  • {api_key_info.env}: {api_key_info.description}")
                    if "endpoint" in env_vars:
                        endpoint_info = env_vars["endpoint"]
                        console.print(f"  • {endpoint_info.env}: {endpoint_info.description} [dim](optional)[/dim]")
                    if "other" in env_vars:
                        for var_info in env_vars["other"].values():
                            console.print(f"  • {var_info.env}: {var_info.description} [dim](optional)[/dim]")

        if (
            reranking_provider_name
            and reranking_provider_name != "fastembed"
            and not reranking_api_key
        ):
            provider = Provider.from_string(reranking_provider_name)
            if provider and (env_vars_list := provider.other_env_vars):
                console.print(f"\n[yellow]⚠[/yellow]  [bold]Environment variables for {reranking_provider_name} (reranking):[/bold]")
                for env_vars in env_vars_list:
                    if "note" in env_vars:
                        console.print(f"  [dim]{env_vars['note']}[/dim]")
                    if "api_key" in env_vars:
                        api_key_info = env_vars["api_key"]
                        console.print(f"  • {api_key_info.env}: {api_key_info.description}")
                    if "endpoint" in env_vars:
                        endpoint_info = env_vars["endpoint"]
                        console.print(f"  • {endpoint_info.env}: {endpoint_info.description} [dim](optional)[/dim]")

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


def _get_config_path(
    output: Path | None,
    user: bool,
    local: bool,
    project_path: Path,
) -> Path:
    """Determine config path based on flags."""
    if output:
        return output
    if user:
        config_path = get_user_config_dir() / "config.toml"
        config_path.parent.mkdir(parents=True, exist_ok=True)
        return config_path
    if local:
        return Path.cwd() / ".codeweaver.toml"
    # Default: project config
    return project_path / "codeweaver.toml"


def _quick_setup(
    output: Path | None,
    force: bool,
    user: bool,
    local: bool,
) -> None:
    """Quick setup using recommended defaults."""
    from codeweaver.config.profiles import recommended_default
    from codeweaver.config.settings import CodeWeaverSettings

    console.print(
        "[bold green]Creating quick configuration with recommended defaults...[/bold green]\n"
    )
    console.print(
        "[cyan]Profile:[/cyan] Voyage (embedding + reranking) + Qdrant (vector store)"
    )
    console.print("[cyan]Features:[/cyan] High-quality embeddings, optimized for code search\n")

    # Get project path
    default_path = get_project_path()
    project_path = Path(default_path).expanduser().resolve()

    # Determine config path
    config_path = _get_config_path(output, user, local, project_path)

    if config_path.exists() and not force:
        overwrite = Confirm.ask(
            f"[yellow]Configuration file already exists at {config_path}. Overwrite?[/yellow]",
            default=False,
        )
        if not overwrite:
            console.print("[yellow]Configuration cancelled.[/yellow]")
            sys.exit(0)

    # Get recommended profile
    provider_settings = recommended_default()

    # Create settings with profile
    settings = CodeWeaverSettings(
        project_path=project_path,
        provider=provider_settings,
    )

    # Save to config file
    settings.save_to_file(config_path)

    console.print(f"[green]✓[/green] Configuration created: [cyan]{config_path}[/cyan]\n")
    console.print("[bold]Next steps:[/bold]")
    console.print("  1. Set [cyan]VOYAGE_API_KEY[/cyan] environment variable")
    console.print("  2. Run: [cyan]codeweaver index[/cyan]")
    console.print("  3. Run: [cyan]codeweaver serve[/cyan]")


def _profile_setup(
    profile: ConfigProfile,
    output: Path | None,
    force: bool,
    user: bool,
    local: bool,
) -> None:
    """Setup using a named profile."""
    from codeweaver.config.profiles import recommended_default
    from codeweaver.config.providers import (
        DataProviderSettings,
        EmbeddingProviderSettings,
        SparseEmbeddingProviderSettings,
        VectorStoreProviderSettings,
    )
    from codeweaver.config.settings import CodeWeaverSettings

    console.print(f"[bold]Creating config from profile: {profile.value}[/bold]\n")

    # Get project path
    default_path = get_project_path()
    project_path = Path(default_path).expanduser().resolve()

    # Determine config path
    config_path = _get_config_path(output, user, local, project_path)

    if config_path.exists() and not force:
        overwrite = Confirm.ask(
            f"[yellow]Configuration file already exists at {config_path}. Overwrite?[/yellow]",
            default=False,
        )
        if not overwrite:
            console.print("[yellow]Configuration cancelled.[/yellow]")
            sys.exit(0)

    # Create settings based on profile
    match profile:
        case ConfigProfile.RECOMMENDED:
            console.print("[cyan]Profile:[/cyan] Voyage (embedding + reranking) + Qdrant")
            provider_settings = recommended_default()
            settings = CodeWeaverSettings(
                project_path=project_path,
                provider=provider_settings,
            )
            env_vars = ["VOYAGE_API_KEY"]

        case ConfigProfile.LOCAL_ONLY:
            console.print("[cyan]Profile:[/cyan] FastEmbed (dense + sparse) + local Qdrant")
            console.print(
                "[cyan]Features:[/cyan] No API keys required, runs completely offline\n"
            )
            provider_settings = {
                "embedding": (
                    EmbeddingProviderSettings(
                        provider=Provider.FASTEMBED,
                        enabled=True,
                        model_settings={"model": "BAAI/bge-small-en-v1.5"},
                    ),
                ),
                "sparse_embedding": (
                    SparseEmbeddingProviderSettings(
                        provider=Provider.FASTEMBED,
                        enabled=True,
                        model_settings={"model": "prithivida/Splade_PP_en_v1"},
                    ),
                ),
                "data": (DataProviderSettings(enabled=True),),
                "vector": (
                    VectorStoreProviderSettings(
                        provider=Provider.QDRANT,
                        enabled=True,
                        provider_settings={"client_options": {"path": ":memory:"}},
                    ),
                ),
            }
            settings = CodeWeaverSettings(
                project_path=project_path,
                provider=provider_settings,
            )
            env_vars = []

        case ConfigProfile.MINIMAL:
            console.print("[cyan]Profile:[/cyan] Minimal configuration")
            console.print("[cyan]Features:[/cyan] Bare minimum, customize as needed\n")
            settings = CodeWeaverSettings(
                project_path=project_path,
            )
            env_vars = []

    # Save to config file
    settings.save_to_file(config_path)

    console.print(f"[green]✓[/green] Configuration created: [cyan]{config_path}[/cyan]\n")
    console.print("[bold]Next steps:[/bold]")
    if env_vars:
        console.print(
            f"  1. Set environment variables: {', '.join(f'[cyan]{v}[/cyan]' for v in env_vars)}"
        )
        console.print("  2. Run: [cyan]codeweaver index[/cyan]")
        console.print("  3. Run: [cyan]codeweaver serve[/cyan]")
    else:
        console.print("  1. Run: [cyan]codeweaver index[/cyan]")
        console.print("  2. Run: [cyan]codeweaver serve[/cyan]")


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
