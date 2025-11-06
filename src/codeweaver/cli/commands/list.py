# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""List command for displaying available providers and models in CodeWeaver."""

from __future__ import annotations

import os
import sys

from typing import Annotated

import cyclopts

from cyclopts import App
from rich.console import Console
from rich.table import Table

from codeweaver.providers.provider import Provider, ProviderKind


console = Console(markup=True, emoji=True)
app = App("list", help="List available providers and models.", console=console)


def _check_api_key(provider: Provider) -> bool:
    """Check if API key is configured for a provider.

    Returns True if API key is configured or not required.
    """
    if provider == Provider.NOT_SET:
        return False

    # Local providers don't need API keys
    local_providers = {
        Provider.FASTEMBED,
        Provider.SENTENCE_TRANSFORMERS,
        Provider.QDRANT,  # Can be local
        Provider.MEMORY,
        Provider.OLLAMA,  # Can be local
    }

    if provider in local_providers:
        return True

    # Check for provider-specific API key environment variables
    env_vars = provider.other_env_vars
    if not env_vars:
        return True  # No API key requirement known

    # Check if any API key env var is set
    # pyright incorrectly reports isinstance check as unnecessary here
    env_vars_list = env_vars if isinstance(env_vars, tuple) else (env_vars,)  # type: ignore[reportUnnecessaryIsInstance]
    for env_var_dict in env_vars_list:
        if (api_key_info := env_var_dict.get("api_key")) and os.getenv(api_key_info.env):
            return True

    return False


def _get_status_indicator(provider: Provider, *, has_key: bool) -> str:
    """Get status indicator for a provider.

    Args:
        provider: The provider enum value
        has_key: Whether the provider has required API key configured

    Returns:
        Status string with emoji indicator
    """
    if not has_key:
        return "[yellow]⚠️  needs key[/yellow]"
    return "[green]✅ ready[/green]"


def _get_provider_type(provider: Provider) -> str:
    """Get human-readable type for a provider."""
    local_providers = {Provider.FASTEMBED, Provider.SENTENCE_TRANSFORMERS, Provider.MEMORY}

    # Check if it's always local
    if provider in local_providers:
        return "local"

    # Check if it can be local
    if provider in {Provider.QDRANT, Provider.OLLAMA}:
        return "local/cloud"

    return "cloud"


@app.command
def providers(
    *,
    kind: Annotated[
        str | None,
        cyclopts.Parameter(
            name=["--kind", "-k"],
            help="Filter by provider kind (embedding, reranking, vector-store, agent, data)",
        ),
    ] = None,
) -> None:
    """List all available providers.

    Shows provider name, capabilities, and status (ready or needs configuration).
    """
    from codeweaver.providers.capabilities import PROVIDER_CAPABILITIES

    # Filter by kind if specified
    kind_filter = None
    if kind:
        try:
            kind_filter = ProviderKind.from_string(kind)
        except (AttributeError, KeyError, ValueError):
            console.print(f"[red]Invalid provider kind: {kind}[/red]")
            console.print(
                f"Valid kinds: {', '.join(k.value for k in ProviderKind if k != ProviderKind.UNSET)}"
            )
            sys.exit(1)

    # Build table
    table = Table(show_header=True, header_style="bold blue", title="Available Providers")
    table.add_column("Provider", style="cyan", no_wrap=True)
    table.add_column("Capabilities", style="white")
    table.add_column("Type", style="white")
    table.add_column("Status", style="white")

    # Sort providers by name (filter NOT_SET at type level for pyright)
    sorted_providers = sorted(
        ((p, caps) for p, caps in PROVIDER_CAPABILITIES.items()), key=lambda x: x[0].value
    )

    for provider, capabilities in sorted_providers:
        # Filter by kind if specified
        if kind_filter and kind_filter not in capabilities:
            continue

        has_key = _check_api_key(provider)
        provider_type = _get_provider_type(provider)
        status = _get_status_indicator(provider, has_key=has_key)
        caps_str = ", ".join(cap.value for cap in capabilities)

        table.add_row(provider.value, caps_str, provider_type, status)

    if table.row_count == 0:
        console.print(f"[yellow]No providers found for kind: {kind}[/yellow]")
    else:
        console.print(table)


@app.command
def models(
    provider_name: Annotated[
        str,
        cyclopts.Parameter(
            help="Provider name to list models for (voyage, fastembed, cohere, etc.)"
        ),
    ],
) -> None:
    """List available models for a specific provider.

    Shows model name, dimensions, and other capabilities.
    """
    # Validate provider
    try:
        provider = Provider.from_string(provider_name)
    except (AttributeError, KeyError, ValueError):
        console.print(f"[red]Invalid provider: {provider_name}[/red]")
        console.print("Use 'codeweaver list providers' to see available providers")
        sys.exit(1)

    if provider == Provider.NOT_SET:
        console.print("[red]Invalid provider: not_set[/red]")
        sys.exit(1)

    # Get provider capabilities to determine what kind of models it supports
    from codeweaver.providers.capabilities import PROVIDER_CAPABILITIES

    capabilities = PROVIDER_CAPABILITIES.get(provider)  # type: ignore[arg-type]
    if not capabilities:
        console.print(f"[yellow]No models found for provider: {provider_name}[/yellow]")
        return

    # Check if provider supports embedding models
    if ProviderKind.EMBEDDING in capabilities:
        _list_embedding_models(provider)

    # Check if provider supports reranking models
    if ProviderKind.RERANKING in capabilities:
        _list_reranking_models(provider)

    # Check if provider only supports agent/vector-store/data
    if not (ProviderKind.EMBEDDING in capabilities or ProviderKind.RERANKING in capabilities):
        console.print(f"[yellow]Provider {provider_name} does not expose model listings.[/yellow]")
        console.print(
            "This provider may be configured through settings rather than model selection."
        )


def _list_embedding_models(provider: Provider) -> None:
    """List embedding models for a provider."""
    try:
        # Import capabilities dynamically based on provider
        capabilities_func = _get_embedding_capabilities_func(provider)
        if not capabilities_func:
            console.print(f"[yellow]No embedding models available for {provider.value}[/yellow]")
            return

        models = capabilities_func()

        if not models:
            console.print(f"[yellow]No embedding models available for {provider.value}[/yellow]")
            return

        table = Table(
            show_header=True, header_style="bold blue", title=f"{provider.value} Embedding Models"
        )
        table.add_column("Model Name", style="cyan", no_wrap=True)
        table.add_column("Dimensions", style="white")
        table.add_column("Context", style="white")
        table.add_column("Normalized", style="white")

        for model in models:
            dims = str(model.default_dimension)
            if model.output_dimensions and len(model.output_dimensions) > 1:
                dims = f"{model.default_dimension} (supports {len(model.output_dimensions)} sizes)"

            normalized = "✅" if model.is_normalized else "❌"

            table.add_row(model.name, dims, str(model.context_window), normalized)

        console.print(table)

    except ImportError as e:
        console.print(f"[yellow]Cannot list models for {provider.value}: {e}[/yellow]")
        console.print(
            f"Install provider dependencies: pip install 'codeweaver[provider-{provider.value}]'"
        )


def _list_reranking_models(provider: Provider) -> None:
    """List reranking models for a provider."""
    try:
        # Import capabilities dynamically based on provider
        capabilities_func = _get_reranking_capabilities_func(provider)
        if not capabilities_func:
            console.print(f"[yellow]No reranking models available for {provider.value}[/yellow]")
            return

        models = capabilities_func()

        if not models:
            console.print(f"[yellow]No reranking models available for {provider.value}[/yellow]")
            return

        table = Table(
            show_header=True, header_style="bold blue", title=f"{provider.value} Reranking Models"
        )
        table.add_column("Model Name", style="cyan", no_wrap=True)
        table.add_column("Max Input", style="white")
        table.add_column("Context Window", style="white")

        for model in models:
            table.add_row(model.name, str(model.max_input), str(model.context_window))

        console.print(table)

    except ImportError as e:
        console.print(f"[yellow]Cannot list models for {provider.value}: {e}[/yellow]")
        console.print(
            f"Install provider dependencies: pip install 'codeweaver[provider-{provider.value}]'"
        )


def _get_embedding_capabilities_func(provider: Provider):
    """Get the capabilities function for an embedding provider."""
    # Map providers to their capability modules
    capability_map = {
        Provider.VOYAGE: "codeweaver.providers.embedding.capabilities.voyage",
        Provider.FASTEMBED: "codeweaver.providers.embedding.capabilities.baai",
        Provider.COHERE: "codeweaver.providers.embedding.capabilities.cohere",
        Provider.OPENAI: "codeweaver.providers.embedding.capabilities.openai",
        Provider.GOOGLE: "codeweaver.providers.embedding.capabilities.google",
        Provider.MISTRAL: "codeweaver.providers.embedding.capabilities.mistral",
        Provider.BEDROCK: "codeweaver.providers.embedding.capabilities.amazon",
        Provider.SENTENCE_TRANSFORMERS: "codeweaver.providers.embedding.capabilities.sentence_transformers",
    }

    module_name = capability_map.get(provider)
    if not module_name:
        return None

    try:
        import importlib

        module = importlib.import_module(module_name)
        # Function names follow pattern: get_{provider}_embedding_capabilities
        func_name = f"get_{module_name.split('.')[-1]}_embedding_capabilities"
        return getattr(module, func_name, None)
    except (ImportError, AttributeError):
        return None


def _get_reranking_capabilities_func(provider: Provider):
    """Get the capabilities function for a reranking provider."""
    # Map providers to their capability modules
    capability_map = {
        Provider.VOYAGE: "codeweaver.providers.reranking.capabilities.voyage",
        Provider.FASTEMBED: "codeweaver.providers.reranking.capabilities.baai",
        Provider.COHERE: "codeweaver.providers.reranking.capabilities.cohere",
        Provider.BEDROCK: "codeweaver.providers.reranking.capabilities.amazon",
        Provider.SENTENCE_TRANSFORMERS: "codeweaver.providers.reranking.capabilities.mixed_bread_ai",
    }

    module_name = capability_map.get(provider)
    if not module_name:
        return None

    try:
        import importlib

        module = importlib.import_module(module_name)
        # Function names follow pattern: get_{provider}_reranking_capabilities
        func_name = f"get_{module_name.split('.')[-1]}_reranking_capabilities"
        return getattr(module, func_name, None)
    except (ImportError, AttributeError):
        return None


@app.command
def embedding() -> None:
    """List all embedding providers (shortcut).

    Equivalent to: codeweaver list providers --kind embedding
    """
    providers(kind="embedding")


@app.command
def reranking() -> None:
    """List all reranking providers (shortcut).

    Equivalent to: codeweaver list providers --kind reranking
    """
    providers(kind="reranking")


def main() -> None:
    """Entry point for the list CLI command."""
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
