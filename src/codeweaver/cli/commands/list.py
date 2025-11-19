# sourcery skip: lambdas-should-be-short
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""List command for displaying available providers and models in CodeWeaver."""

from __future__ import annotations

import sys

from collections.abc import Sequence
from typing import TYPE_CHECKING, Annotated, Literal, TypedDict, is_typeddict

import cyclopts

from cyclopts import App
from rich.table import Table

from codeweaver.cli.ui import CLIErrorHandler, get_display
from codeweaver.providers.embedding.capabilities.base import EmbeddingModelCapabilities
from codeweaver.providers.provider import Provider, ProviderKind
from codeweaver.providers.reranking.capabilities.base import RerankingModelCapabilities


if TYPE_CHECKING:
    from rich.console import Console

    from codeweaver.cli.ui import StatusDisplay
    from codeweaver.providers.embedding.capabilities.base import SparseEmbeddingModelCapabilities

_display: StatusDisplay = get_display()
console: Console = _display.console
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
    """Get human-readable type for a provider with color coding."""
    if provider.always_local:
        return "[green]local[/green]"
    return "[magenta]local/cloud[/magenta]" if provider.is_local_provider else "[blue]cloud[/blue]"


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

    display = _display
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
            display.print_error("Invalid provider kind")
            display.print_list(
                [prov.variable for prov in ProviderKind if prov != ProviderKind.UNSET],  # ty: ignore[invalid-argument-type]
                title="The following are valid provider kinds:",
            )
            sys.exit(1)

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
            elif capability and provider_map.get(provider) and is_typeddict(provider_map[provider]):
                provider_map[provider]["capabilities"].append(capability)  # ty: ignore[non-subscriptable]  # not sure how else to prove it..

    # Count valid providers
    valid_providers = [p for p, info in provider_map.items() if info]
    provider_count = len(valid_providers)

    # Build table with count
    title_text = (
        f"Available {kind.as_title} Providers ({provider_count} found)"
        if kind_filter
        else f"Available Providers ({provider_count} found)"
    )
    table = Table(show_header=True, header_style="bold blue", title=title_text)
    table.add_column("Provider", style="cyan", no_wrap=True)
    table.add_column("Kind", style="white")
    table.add_column("Type", style="white")
    table.add_column("Status", style="white")

    for provider, info in provider_map.items():
        if not info:
            continue
        joined_caps = ", ".join(cap.as_title for cap in info["capabilities"])
        provider_type = info["kind"]
        status = info["status"]
        table.add_row(provider.as_title, joined_caps, provider_type, status)

    if table.row_count == 0:
        display.print_warning(f"No providers found for kind: {kind}")
    else:
        display.console.print(table)


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
    display = _display

    # Validate provider
    try:
        provider = (
            provider_name
            if isinstance(provider_name, Provider)
            else Provider.from_string(provider_name)
        )
    except (AttributeError, KeyError, ValueError):
        from codeweaver.exceptions import CodeWeaverError

        error_handler = CLIErrorHandler(display)
        error = CodeWeaverError(
            f"Invalid provider: {provider_name}",
            suggestions=["Use 'codeweaver list providers' to see available providers"],
        )
        error_handler.handle_error(error, "List models", exit_code=1)

    if provider == Provider.NOT_SET:
        from codeweaver.exceptions import CodeWeaverError

        error_handler = CLIErrorHandler(display)
        error = CodeWeaverError(
            "Invalid provider: not_set",
            suggestions=["Use 'codeweaver list providers' to see available providers"],
        )
        error_handler.handle_error(error, "List models", exit_code=1)

    # Get provider capabilities to determine what kind of models it supports
    from codeweaver.common.registry.models import get_model_registry

    registry = get_model_registry()
    capabilities = registry.models_for_provider(provider)
    if not capabilities:
        display.print_warning(f"No models found for provider: {provider_name}")
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
        display.print_warning("Agent models listing not yet implemented.")


def _list_embedding_models(
    provider: Provider, models: Sequence[EmbeddingModelCapabilities]
) -> None:
    """List embedding models for a provider."""
    display = _display
    try:
        if not models:
            display.print_warning(f"No embedding models available for {provider.as_title}")
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

        display.console.print(table)

    except ImportError as e:
        display.print_warning(f"Cannot list models for {provider.value}: {e}")
        display.print_info(
            f"Install provider dependencies: pip install 'codeweaver[provider-{provider.value}]'"
        )


def _list_reranking_models(
    provider: Provider, models: Sequence[RerankingModelCapabilities]
) -> None:
    """List reranking models for a provider."""
    display = _display
    try:
        if not models:
            display.print_warning(f"No reranking models available for {provider.as_title}")
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

        display.console.print(table)

    except ImportError as e:
        display.print_warning(f"Cannot list models for {provider.value}: {e}")
        display.print_info(
            f"Install provider dependencies: pip install 'codeweaver[provider-{provider.variable}]'"
        )


def _list_sparse_embedding_models(
    provider: Provider, models: Sequence[SparseEmbeddingModelCapabilities]
) -> None:
    """List sparse embedding models for a provider."""
    display = _display
    try:
        if not models:
            display.print_warning(f"No sparse embedding models available for {provider.as_title}")
            return

        table = Table(
            show_header=True,
            header_style="bold blue",
            title=f"{provider.as_title} Sparse Embedding Models",
        )
        table.add_column("Model Name", style="cyan", no_wrap=True)

        for model in models:
            table.add_row(model.name)

        display.console.print(table)

    except ImportError as e:
        display.print_warning(f"Cannot list models for {provider.value}: {e}")
        display.print_info(
            f"Install provider dependencies: pip install 'codeweaver[provider-{provider.value}]'"
        )


@app.command(alias="embed")
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
def vector_store(alias="vec") -> None:
    """List all vector-store providers (shortcut).

    Equivalent to: codeweaver list providers --kind vector-store
    """
    providers(kind=ProviderKind.VECTOR_STORE)


@app.command(alias="rerank")
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
    display = _display
    error_handler = CLIErrorHandler(display)

    try:
        app()
    except KeyboardInterrupt:
        display.print_warning("Looks like you cancelled the operation. Exiting...")
        sys.exit(1)
    except Exception as e:
        error_handler.handle_error(e, "List command", exit_code=1)


if __name__ == "__main__":
    app()
