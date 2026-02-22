# sourcery skip: lambdas-should-be-short
# SPDX-FileCopyrightText: 2025 Knitli Inc.
# SPDX-FileContributor: Adam Poulemanos <adam@knit.li>
#
# SPDX-License-Identifier: MIT OR Apache-2.0
"""List command for displaying available providers and models in CodeWeaver."""

from __future__ import annotations

import sys

from collections.abc import Sequence
from typing import TYPE_CHECKING, Annotated, Any, Literal, TypedDict, cast

import cyclopts

from cyclopts import App
from rich.table import Table

from codeweaver.cli.ui import CLIErrorHandler, get_display
from codeweaver.cli.utils import check_provider_package_available
from codeweaver.core import Provider, ProviderCategory, TypeIs, get_container
from codeweaver.providers import EmbeddingModelCapabilities, RerankingModelCapabilities


if TYPE_CHECKING:
    from rich.console import Console

    from codeweaver.cli.ui import StatusDisplay
    from codeweaver.providers import SparseEmbeddingModelCapabilities

_display: StatusDisplay = get_display()
console: Console = _display.console
app = App("list", help="List available CodeWeaver resources.", console=console)

type CategoryDisplay = Literal[
    "[green]local[/green]", "[magenta]local/cloud[/magenta]", "[blue]cloud[/blue]"
]
type ApiStatus = Literal["[yellow]⚠️  needs key[/yellow]", "[green]✅ ready[/green]"]


def _check_api_key(provider: Provider, category: ProviderCategory) -> bool:
    """Check if API key is configured for a provider.

    Returns True if API key is configured or not required.
    """
    if provider == Provider.NOT_SET:
        return False

    if provider.always_local:
        return True

    if provider.is_local_provider:
        return check_provider_package_available(provider, category)
    return provider.has_env_auth


def _get_status_indicator(provider: Provider, *, has_key: bool) -> ApiStatus:
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


def _get_provider_type(provider: Provider) -> CategoryDisplay:
    """Get human-readable type for a provider with color coding."""
    if provider.always_local:
        return "[green]local[/green]"
    return "[magenta]local/cloud[/magenta]" if provider.is_local_provider else "[blue]cloud[/blue]"


class ProviderDict(TypedDict):
    """TypedDict for provider information."""

    capabilities: list[ProviderCategory]
    category: CategoryDisplay
    status: ApiStatus


type ProviderMap = dict[Provider, ProviderDict]


def _is_definitely_real_provider_dict(d: Any) -> TypeIs[ProviderDict]:
    """Type guard to check if a dict is definitely a ProviderDict."""
    if not isinstance(d, dict):
        return False
    required_keys = {"capabilities", "category", "status"}
    return (
        all(key in d for key in required_keys)
        and isinstance(d["capabilities"], list)
        and isinstance(d["category"], str)
        and isinstance(d["status"], str)
    )


def _validate_category_filter(category: ProviderCategory | None) -> ProviderCategory | None:
    """Validate and convert category filter to ProviderCategory enum.

    Args:
        category: The category to validate

    Returns:
        The validated ProviderCategory or None

    Raises:
        SystemExit: If category is invalid
    """
    if not category:
        return None

    try:
        return ProviderCategory.from_string(category) if isinstance(category, str) else category
    except (AttributeError, KeyError, ValueError):
        display = _display
        display.print_error("Invalid provider category")
        display.print_list(
            [prov.variable for prov in ProviderCategory if prov != ProviderCategory.UNSET],
            title="The following are valid provider categories:",
        )
        sys.exit(1)


def _build_provider_map(
    providers_list: list[Provider], capability_categories: dict[ProviderCategory, list[Provider]]
) -> ProviderMap:
    """Build provider information map with capabilities and status.

    Args:
        providers_list: List of providers to include
        capability_categories: Mapping of categories to providers

    Returns:
        Dictionary mapping providers to their information
    """
    provider_map: ProviderMap = {}

    for capability, p_list in capability_categories.items():
        for provider in p_list:
            if provider not in providers_list:
                continue

            if provider not in provider_map:
                has_key = _check_api_key(provider, category=capability)
                provider_map[provider] = ProviderDict(
                    capabilities=[capability],
                    category=_get_provider_type(provider),
                    status=_get_status_indicator(provider, has_key=has_key),
                )
            else:
                # Provider already exists, append new capability
                provider_map[provider]["capabilities"].append(capability)

    return provider_map


def _display_provider_table(provider_map: ProviderMap, category: ProviderCategory | None) -> None:
    """Display providers in a formatted table.

    Args:
        provider_map: Mapping of providers to their information
        category: Optional category filter for title
    """
    display = _display
    valid_providers = [p for p, info in provider_map.items() if info]
    provider_count = len(valid_providers)

    title_text = (
        f"Available {category.as_title} Providers ({provider_count} found)"
        if category
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
        table.add_row(provider.as_title, joined_caps, info["category"], info["status"])

    if table.row_count == 0:
        display.print_warning(f"No providers found for category: {category}")
    else:
        display.console.print(table)


@app.command
def providers(
    category: Annotated[
        ProviderCategory | None,
        cyclopts.Parameter(name=["--category", "-k"], help="Filter by provider category"),
    ] = ProviderCategory.EMBEDDING,
) -> None:
    """List all available providers.

    Shows provider name, capabilities, and status (ready or needs configuration).
    """
    # Validate and filter category
    category_filter = _validate_category_filter(category)

    # Get all providers sorted by name
    providers_list = sorted(
        (provider for provider in Provider if provider != Provider.NOT_SET),
        key=lambda p: p.variable,
    )

    # Build capability mapping for each category
    all_capabilities = {
        cat: cat.providers for cat in ProviderCategory if cat != ProviderCategory.UNSET
    }

    # Filter capabilities by category if specified
    filtered_capabilities = {
        k: cast(list[Provider], v)
        for k, v in all_capabilities.items()
        if not category_filter or k == category_filter
    }

    # Build provider map and display
    provider_map = _build_provider_map(providers_list, filtered_capabilities)
    _display_provider_table(provider_map, category_filter)


@app.command
async def models(
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
        from codeweaver.core import CodeWeaverError

        error_handler = CLIErrorHandler(display)
        error = CodeWeaverError(
            f"Invalid provider: {provider_name}",
            suggestions=["Use 'codeweaver list providers' to see available providers"],
        )
        error_handler.handle_error(error, "List models", exit_code=1)

    if provider == Provider.NOT_SET:
        from codeweaver.core import CodeWeaverError

        error_handler = CLIErrorHandler(display)
        error = CodeWeaverError(
            "Invalid provider: not_set",
            suggestions=["Use 'codeweaver list providers' to see available providers"],
        )
        error_handler.handle_error(error, "List models", exit_code=1)

    # Resolve capabilities using DI
    # We don't need full settings setup, just resolvers
    container = get_container()

    # We might need to ensure providers are loaded to populate resolvers?
    # Resolvers usually self-populate or are static.

    try:
        from codeweaver.providers.embedding.capabilities.resolver import (
            EmbeddingCapabilityResolver,
            SparseEmbeddingCapabilityResolver,
        )
        from codeweaver.providers.reranking.capabilities.resolver import RerankingCapabilityResolver

        embed_resolver = await container.resolve(EmbeddingCapabilityResolver)
        sparse_resolver = await container.resolve(SparseEmbeddingCapabilityResolver)
        rerank_resolver = await container.resolve(RerankingCapabilityResolver)

        embed_models = [
            cap for cap in embed_resolver.all_capabilities() if cap.provider == provider
        ]
        sparse_models = [
            cap for cap in sparse_resolver.all_capabilities() if cap.provider == provider
        ]
        rerank_models = [
            cap for cap in rerank_resolver.all_capabilities() if cap.provider == provider
        ]

    except Exception as e:
        display.print_warning(f"Failed to load model capabilities: {e}")
        return

    if not (embed_models or sparse_models or rerank_models):
        display.print_warning(f"No models found for provider: {provider_name}")
        return

    # Check if provider supports embedding models
    if embed_models:
        _list_embedding_models(provider, embed_models)

    if sparse_models:
        _list_sparse_embedding_models(provider, sparse_models)

    # Check if provider supports reranking models
    if rerank_models:
        _list_reranking_models(provider, rerank_models)


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
        display.print_warning(f"Cannot list models for {provider.variable.replace('_', '-')}: {e}")
        display.print_info(
            f"Install provider dependencies: pip install 'codeweaver[{provider.variable.replace('_', '-')}']"
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
        display.print_warning(f"Cannot list models for {provider.as_title}: {e}")
        display.print_info(
            f"Install provider dependencies: pip install 'codeweaver[{provider.variable.replace('_', '-')}']"
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
        display.print_warning(f"Cannot list models for {provider.as_title}: {e}")
        display.print_info(
            f"Install provider dependencies: pip install 'codeweaver[{provider.variable.replace('_', '-')}']'"
        )


@app.command(alias="embed")
def embedding() -> None:
    """List all embedding providers (shortcut).

    Equivalent to: codeweaver list providers --category embedding
    """
    providers(category=ProviderCategory.EMBEDDING)


@app.command
def sparse_embedding() -> None:
    """List all sparse-embedding providers (shortcut).

    Equivalent to: codeweaver list providers --category sparse-embedding
    """
    providers(category=ProviderCategory.SPARSE_EMBEDDING)


@app.command
def vector_store(alias="vec") -> None:
    """List all vector-store providers (shortcut).

    Equivalent to: codeweaver list providers --category vector-store
    """
    providers(category=ProviderCategory.VECTOR_STORE)


@app.command(alias="rerank")
def reranking() -> None:
    """List all reranking providers (shortcut).

    Equivalent to: codeweaver list providers --category reranking
    """
    providers(category=ProviderCategory.RERANKING)


@app.command
def agent() -> None:
    """List all agent providers (shortcut).

    Equivalent to: codeweaver list providers --category agent
    """
    providers(category=ProviderCategory.AGENT)


@app.command
def data() -> None:
    """List all data providers (shortcut).

    Equivalent to: codeweaver list providers --category data
    """
    providers(category=ProviderCategory.DATA)


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
