# sourcery skip: lambdas-should-be-short
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""List command for displaying available providers and models in CodeWeaver."""

from __future__ import annotations

import sys

from collections.abc import Sequence
from typing import TYPE_CHECKING, Annotated, Literal, TypedDict

import cyclopts

from cyclopts import App
from rich.console import Console
from rich.table import Table

from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities
from codeweaver.providers.provider import Provider, ProviderKind
from codeweaver.providers.reranking.capabilities.base import RerankingModelCapabilities


if TYPE_CHECKING:
    from codeweaver.providers.embedding.capabilities.base import SparseEmbeddingModelCapabilities


console = Console(markup=True, emoji=True)
app = App("list", help="List available CodeWeaver resources.", console=console)


def _check_api_key(provider: Provider, kind: ProviderKind) -> bool:
    """Check if API key is configured for a provider.

    Returns True if API key is configured or not required.
    """
    if provider == Provider.NOT_SET:
        return False

    if provider.always_local:
        return True

    if provider.is_local_provider:
        from codeweaver.common.registry.provider import get_provider_registry

        registry = get_provider_registry()
        return registry.is_provider_available(provider, kind)
    return provider.has_env_auth


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
    if provider.always_local:
        return "local"
    return "local/cloud" if provider.is_local_provider else "cloud"


class ProviderDict(TypedDict):
    """TypedDict for provider information."""

    capabilities: list[ProviderKind]
    kind: Literal["local", "cloud", "local/cloud"]
    status: Literal["[yellow]⚠️  needs key[/yellow]", "[green]✅ ready[/green]"]


type ProviderMap = dict[Provider, ProviderDict]


@app.command
def providers(
    kind: Annotated[
        ProviderKind | None,
        cyclopts.Parameter(name=["--kind", "-k"], help="Filter by provider kind"),
    ] = ProviderKind.EMBEDDING,
) -> None:
    """List all available providers.

    Shows provider name, capabilities, and status (ready or needs configuration).
    """
    from codeweaver.common.registry.provider import get_provider_registry

    registry = get_provider_registry()
    provider_capabilities = {
        p: registry.list_providers(p) for p in ProviderKind if p != ProviderKind.UNSET
    }

    # Filter by kind if specified
    kind_filter = None
    if kind:
        try:
            kind_filter = ProviderKind.from_string(kind) if isinstance(kind, str) else kind
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

    providers = sorted(
        (provider for provider in Provider if provider != Provider.NOT_SET),
        key=lambda p: p.variable,
    )

    provider_capabilities = {
        k: v
        for k, v in provider_capabilities.items()
        if ((kind_filter and k == kind_filter) or not kind_filter)
    }
    provider_map = dict.fromkeys(providers)
    for capability, providers_list in provider_capabilities.items():
        for provider in providers_list:
            if provider not in provider_map:
                continue
            if not provider_map.get(provider):
                has_key = _check_api_key(provider, kind=capability)
                provider_map[provider] = {
                    "capabilities": [capability],
                    "kind": _get_provider_type(provider),
                    "status": _get_status_indicator(provider, has_key=has_key),
                }
            else:
                provider_map[provider]["capabilities"].append(capability)

    for provider, info in provider_map.items():
        if not info:
            continue
        joined_caps = ", ".join(cap.as_title for cap in info["capabilities"])
        provider_type = info["kind"]
        status = info["status"]
        table.add_row(provider.as_title, joined_caps, provider_type, status)

    if table.row_count == 0:
        console.print(f"[yellow]No providers found for kind: {kind}[/yellow]")
    else:
        console.print(table)


@app.command
def models(
    provider_name: Annotated[
        Provider | str,
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
        provider = (
            Provider if isinstance(provider_name, Provider) else Provider.from_string(provider_name)
        )
    except (AttributeError, KeyError, ValueError):
        console.print(f"[red]Invalid provider: {provider_name}[/red]")
        console.print("Use 'codeweaver list providers' to see available providers")
        sys.exit(1)

    if provider == Provider.NOT_SET:
        console.print("[red]Invalid provider: not_set[/red]")
        sys.exit(1)

    # Get provider capabilities to determine what kind of models it supports
    from codeweaver.common.registry.models import get_model_registry

    registry = get_model_registry()
    capabilities = registry.models_for_provider(provider)
    if not capabilities:
        console.print(f"[yellow]No models found for provider: {provider_name}[/yellow]")
        return

    # Check if provider supports embedding models
    if capabilities.embedding:
        _list_embedding_models(provider, capabilities.embedding)

    if capabilities.sparse_embedding:
        _list_sparse_embedding_models(provider, capabilities.sparse_embedding)

    # Check if provider supports reranking models
    if capabilities.reranking:
        _list_reranking_models(provider, capabilities.reranking)

    if capabilities.agent:
        console.print("[yellow]Agent models listing not yet implemented.[/yellow]")


def _list_embedding_models(
    provider: Provider, models: Sequence[EmbeddingModelCapabilities]
) -> None:
    """List embedding models for a provider."""
    try:
        if not models:
            console.print(f"[yellow]No embedding models available for {provider.as_title}[/yellow]")
            return

        table = Table(
            show_header=True,
            header_style="bold blue",
            title=f"{provider.as_title} Embedding Models",
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


def _list_reranking_models(
    provider: Provider, models: Sequence[RerankingModelCapabilities]
) -> None:
    """List reranking models for a provider."""
    try:
        if not models:
            console.print(f"[yellow]No reranking models available for {provider.as_title}[/yellow]")
            return

        table = Table(
            show_header=True,
            header_style="bold blue",
            title=f"{provider.as_title} Reranking Models",
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


def _list_sparse_embedding_models(
    provider: Provider, models: Sequence[SparseEmbeddingModelCapabilities]
) -> None:
    """List sparse embedding models for a provider."""
    try:
        if not models:
            console.print(
                f"[yellow]No sparse embedding models available for {provider.as_title}[/yellow]"
            )
            return

        table = Table(
            show_header=True,
            header_style="bold blue",
            title=f"{provider.as_title} Sparse Embedding Models",
        )
        table.add_column("Model Name", style="cyan", no_wrap=True)

        for model in models:
            table.add_row(model.name)

        console.print(table)

    except ImportError as e:
        console.print(f"[yellow]Cannot list models for {provider.value}: {e}[/yellow]")
        console.print(
            f"Install provider dependencies: pip install 'codeweaver[provider-{provider.value}]'"
        )


@app.command
def embedding() -> None:
    """List all embedding providers (shortcut).

    Equivalent to: codeweaver list providers --kind embedding
    """
    providers(kind=ProviderKind.EMBEDDING)


@app.command
def sparse_embedding() -> None:
    """List all sparse-embedding providers (shortcut).

    Equivalent to: codeweaver list providers --kind sparse-embedding
    """
    providers(kind=ProviderKind.SPARSE_EMBEDDING)


@app.command
def vector_store() -> None:
    """List all vector-store providers (shortcut).

    Equivalent to: codeweaver list providers --kind vector-store
    """
    providers(kind=ProviderKind.VECTOR_STORE)


@app.command
def reranking() -> None:
    """List all reranking providers (shortcut).

    Equivalent to: codeweaver list providers --kind reranking
    """
    providers(kind=ProviderKind.RERANKING)


@app.command
def agent() -> None:
    """List all agent providers (shortcut).

    Equivalent to: codeweaver list providers --kind agent
    """
    providers(kind=ProviderKind.AGENT)


@app.command
def data() -> None:
    """List all data providers (shortcut).

    Equivalent to: codeweaver list providers --kind data
    """
    providers(kind=ProviderKind.DATA)


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
